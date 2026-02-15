import { describe, it, beforeEach } from "node:test";
import assert from "node:assert";
import { app } from "../../src/api/app";
import { getDb, schema } from "../../src/db/index";
import { eq } from "drizzle-orm";

const db = getDb();

/** Helper: remove all users (and cascading data) for test isolation */
async function cleanUsers() {
  await db.delete(schema.agentRuns);
  await db.delete(schema.llmCalls);
  await db.delete(schema.emailEvents);
  await db.delete(schema.jobs);
  await db.delete(schema.emails);
  await db.delete(schema.syncState);
  await db.delete(schema.userSettings);
  await db.delete(schema.userLabels);
  await db.delete(schema.users);
}

/** Helper: insert a user directly via DB */
async function seedUser(
  email: string,
  opts?: { displayName?: string; isActive?: boolean }
) {
  const [user] = await db
    .insert(schema.users)
    .values({
      email,
      displayName: opts?.displayName ?? null,
      isActive: opts?.isActive ?? true,
      onboardedAt: new Date().toISOString(),
    })
    .returning();
  return user;
}

// ---------------------------------------------------------------
// GET /api/users
// ---------------------------------------------------------------
describe("GET /api/users", () => {
  beforeEach(async () => {
    await cleanUsers();
  });

  it("should return empty array when no users exist", async () => {
    const res = await app.request("/api/users");
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.ok(Array.isArray(data));
    assert.strictEqual(data.length, 0);
  });

  it("should list only active users", async () => {
    await seedUser("active@example.com", { displayName: "Active" });
    await seedUser("inactive@example.com", {
      displayName: "Inactive",
      isActive: false,
    });

    const res = await app.request("/api/users");
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.length, 1);
    assert.strictEqual(data[0].email, "active@example.com");
    assert.strictEqual(data[0].display_name, "Active");
    assert.ok(data[0].onboarded_at);
  });

  it("should return expected fields", async () => {
    await seedUser("user@example.com", { displayName: "Test" });

    const res = await app.request("/api/users");
    const data = await res.json();

    assert.strictEqual(data.length, 1);
    const user = data[0];
    assert.ok("id" in user);
    assert.ok("email" in user);
    assert.ok("display_name" in user);
    assert.ok("onboarded_at" in user);
  });
});

// ---------------------------------------------------------------
// POST /api/users
// ---------------------------------------------------------------
describe("POST /api/users", () => {
  beforeEach(async () => {
    await cleanUsers();
  });

  it("should create a user", async () => {
    const res = await app.request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "new@example.com",
        display_name: "New User",
      }),
    });

    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.email, "new@example.com");
    assert.ok(data.id > 0);
  });

  it("should create user without display_name", async () => {
    const res = await app.request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "minimal@example.com" }),
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.email, "minimal@example.com");
  });

  it("should reject duplicate email", async () => {
    await app.request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "dup@example.com" }),
    });

    const res = await app.request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "dup@example.com" }),
    });

    assert.strictEqual(res.status, 409);
    const data = await res.json();
    assert.strictEqual(data.detail, "User already exists");
  });

  it("should reject invalid email", async () => {
    const res = await app.request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "not-an-email" }),
    });

    assert.strictEqual(res.status, 400);
  });

  it("should reject empty body", async () => {
    const res = await app.request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    assert.strictEqual(res.status, 400);
  });
});

// ---------------------------------------------------------------
// GET /api/users/:user_id/settings
// ---------------------------------------------------------------
describe("GET /api/users/:user_id/settings", () => {
  beforeEach(async () => {
    await cleanUsers();
  });

  it("should return empty object when no settings", async () => {
    const user = await seedUser("s@example.com");
    const res = await app.request(`/api/users/${user.id}/settings`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.deepStrictEqual(data, {});
  });

  it("should return all settings as key-value map", async () => {
    const user = await seedUser("s@example.com");

    await db.insert(schema.userSettings).values([
      { userId: user.id, settingKey: "language", settingValue: "cs" },
      { userId: user.id, settingKey: "tone", settingValue: "formal" },
    ]);

    const res = await app.request(`/api/users/${user.id}/settings`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.language, "cs");
    assert.strictEqual(data.tone, "formal");
  });

  it("should return 404 for non-existent user", async () => {
    const res = await app.request("/api/users/99999/settings");
    assert.strictEqual(res.status, 404);
  });

  it("should return 400 for invalid user_id", async () => {
    const res = await app.request("/api/users/abc/settings");
    assert.strictEqual(res.status, 400);
  });
});

// ---------------------------------------------------------------
// PUT /api/users/:user_id/settings
// ---------------------------------------------------------------
describe("PUT /api/users/:user_id/settings", () => {
  beforeEach(async () => {
    await cleanUsers();
  });

  it("should create a new setting", async () => {
    const user = await seedUser("s@example.com");

    const res = await app.request(`/api/users/${user.id}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "language", value: "en" }),
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.ok, true);

    // Verify in DB
    const settings = await db
      .select()
      .from(schema.userSettings)
      .where(eq(schema.userSettings.userId, user.id));
    assert.strictEqual(settings.length, 1);
    assert.strictEqual(settings[0].settingKey, "language");
    assert.strictEqual(settings[0].settingValue, "en");
  });

  it("should update an existing setting", async () => {
    const user = await seedUser("s@example.com");

    await db.insert(schema.userSettings).values({
      userId: user.id,
      settingKey: "language",
      settingValue: "cs",
    });

    const res = await app.request(`/api/users/${user.id}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "language", value: "en" }),
    });

    assert.strictEqual(res.status, 200);

    const settings = await db
      .select()
      .from(schema.userSettings)
      .where(eq(schema.userSettings.userId, user.id));
    assert.strictEqual(settings.length, 1);
    assert.strictEqual(settings[0].settingValue, "en");
  });

  it("should handle non-string values by serializing to JSON", async () => {
    const user = await seedUser("s@example.com");

    const res = await app.request(`/api/users/${user.id}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "max_drafts", value: 5 }),
    });

    assert.strictEqual(res.status, 200);

    const settings = await db
      .select()
      .from(schema.userSettings)
      .where(eq(schema.userSettings.userId, user.id));
    assert.strictEqual(settings[0].settingValue, "5");
  });

  it("should return 404 for non-existent user", async () => {
    const res = await app.request("/api/users/99999/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "language", value: "en" }),
    });
    assert.strictEqual(res.status, 404);
  });

  it("should return 400 for missing key", async () => {
    const user = await seedUser("s@example.com");

    const res = await app.request(`/api/users/${user.id}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: "en" }),
    });
    assert.strictEqual(res.status, 400);
  });
});

// ---------------------------------------------------------------
// GET /api/users/:user_id/labels
// ---------------------------------------------------------------
describe("GET /api/users/:user_id/labels", () => {
  beforeEach(async () => {
    await cleanUsers();
  });

  it("should return empty object when no labels", async () => {
    const user = await seedUser("l@example.com");
    const res = await app.request(`/api/users/${user.id}/labels`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.deepStrictEqual(data, {});
  });

  it("should return labels as key-value map", async () => {
    const user = await seedUser("l@example.com");

    await db.insert(schema.userLabels).values([
      {
        userId: user.id,
        labelKey: "needs_response",
        gmailLabelId: "Label_1",
        gmailLabelName: "AI/Needs Response",
      },
      {
        userId: user.id,
        labelKey: "fyi",
        gmailLabelId: "Label_2",
        gmailLabelName: "AI/FYI",
      },
    ]);

    const res = await app.request(`/api/users/${user.id}/labels`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.needs_response, "Label_1");
    assert.strictEqual(data.fyi, "Label_2");
  });

  it("should return 404 for non-existent user", async () => {
    const res = await app.request("/api/users/99999/labels");
    assert.strictEqual(res.status, 404);
  });
});

// ---------------------------------------------------------------
// GET /api/users/:user_id/emails
// ---------------------------------------------------------------
describe("GET /api/users/:user_id/emails", () => {
  beforeEach(async () => {
    await cleanUsers();
  });

  it("should return pending emails by default", async () => {
    const user = await seedUser("e@example.com");

    await db.insert(schema.emails).values([
      {
        userId: user.id,
        gmailThreadId: "thread_1",
        gmailMessageId: "msg_1",
        senderEmail: "a@test.com",
        subject: "Pending",
        classification: "needs_response",
        status: "pending",
      },
      {
        userId: user.id,
        gmailThreadId: "thread_2",
        gmailMessageId: "msg_2",
        senderEmail: "b@test.com",
        subject: "Sent",
        classification: "fyi",
        status: "sent",
      },
    ]);

    const res = await app.request(`/api/users/${user.id}/emails`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.length, 1);
    assert.strictEqual(data[0].subject, "Pending");
    assert.strictEqual(data[0].status, "pending");
  });

  it("should filter by status query parameter", async () => {
    const user = await seedUser("e@example.com");

    await db.insert(schema.emails).values([
      {
        userId: user.id,
        gmailThreadId: "thread_1",
        gmailMessageId: "msg_1",
        senderEmail: "a@test.com",
        subject: "Drafted",
        classification: "needs_response",
        status: "drafted",
      },
      {
        userId: user.id,
        gmailThreadId: "thread_2",
        gmailMessageId: "msg_2",
        senderEmail: "b@test.com",
        subject: "Pending",
        classification: "fyi",
        status: "pending",
      },
    ]);

    const res = await app.request(
      `/api/users/${user.id}/emails?status=drafted`
    );
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.length, 1);
    assert.strictEqual(data[0].subject, "Drafted");
  });

  it("should filter by classification query parameter", async () => {
    const user = await seedUser("e@example.com");

    await db.insert(schema.emails).values([
      {
        userId: user.id,
        gmailThreadId: "thread_1",
        gmailMessageId: "msg_1",
        senderEmail: "a@test.com",
        subject: "FYI Email",
        classification: "fyi",
        status: "pending",
      },
      {
        userId: user.id,
        gmailThreadId: "thread_2",
        gmailMessageId: "msg_2",
        senderEmail: "b@test.com",
        subject: "Urgent",
        classification: "needs_response",
        status: "pending",
      },
    ]);

    const res = await app.request(
      `/api/users/${user.id}/emails?classification=fyi`
    );
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.length, 1);
    assert.strictEqual(data[0].classification, "fyi");
  });

  it("should return expected fields", async () => {
    const user = await seedUser("e@example.com");

    await db.insert(schema.emails).values({
      userId: user.id,
      gmailThreadId: "thread_1",
      gmailMessageId: "msg_1",
      senderEmail: "sender@test.com",
      senderName: "Sender",
      subject: "Test Subject",
      snippet: "Preview...",
      classification: "needs_response",
      confidence: "high",
      status: "pending",
    });

    const res = await app.request(`/api/users/${user.id}/emails`);
    const data = await res.json();
    const email = data[0];

    assert.ok("id" in email);
    assert.ok("gmail_thread_id" in email);
    assert.ok("gmail_message_id" in email);
    assert.ok("subject" in email);
    assert.ok("sender_email" in email);
    assert.ok("sender_name" in email);
    assert.ok("snippet" in email);
    assert.ok("classification" in email);
    assert.ok("status" in email);
    assert.ok("confidence" in email);
    assert.ok("received_at" in email);
    assert.ok("processed_at" in email);
    assert.ok("drafted_at" in email);
    assert.ok("acted_at" in email);
  });

  it("should return 404 for non-existent user", async () => {
    const res = await app.request("/api/users/99999/emails");
    assert.strictEqual(res.status, 404);
  });

  it("should return emails in descending order by id", async () => {
    const user = await seedUser("e@example.com");

    for (let i = 0; i < 3; i++) {
      await db.insert(schema.emails).values({
        userId: user.id,
        gmailThreadId: `thread_${i}`,
        gmailMessageId: `msg_${i}`,
        senderEmail: `s${i}@test.com`,
        subject: `Email ${i}`,
        classification: "needs_response",
        status: "pending",
      });
    }

    const res = await app.request(`/api/users/${user.id}/emails`);
    const data = await res.json();

    assert.strictEqual(data.length, 3);
    // Newest first
    assert.ok(data[0].id > data[1].id);
    assert.ok(data[1].id > data[2].id);
  });
});
