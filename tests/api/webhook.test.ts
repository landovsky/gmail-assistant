import { describe, it, beforeEach } from "node:test";
import assert from "node:assert";
import { app } from "../../src/api/app";
import { getDb, schema } from "../../src/db/index";

const db = getDb();

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

describe("Webhook API", () => {
  beforeEach(async () => {
    await cleanUsers();
  });

  it("should process Gmail webhook notification", async () => {
    // Create test user
    await db.insert(schema.users).values({
      email: "test@example.com",
      displayName: "Test User",
    });

    // Simulate Gmail Pub/Sub notification
    const notification = {
      message: {
        data: Buffer.from(
          JSON.stringify({
            emailAddress: "test@example.com",
            historyId: "12345",
          })
        ).toString("base64"),
        messageId: "test-message-id",
        publishTime: new Date().toISOString(),
      },
      subscription: "projects/test-project/subscriptions/test-sub",
    };

    const res = await app.request("/webhook/gmail", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(notification),
    });

    assert.strictEqual(res.status, 200);
    assert.strictEqual(await res.text(), "OK");
  });

  it("should handle invalid notification format", async () => {
    const res = await app.request("/webhook/gmail", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });

    assert.strictEqual(res.status, 400);
  });
});
