import { describe, it, expect, beforeEach } from "bun:test";
import { app } from "../../src/api/app";
import { runMigrations } from "../../src/db/migrate";
import { getDb, schema } from "../../src/db";
import { unlinkSync, existsSync } from "fs";

const TEST_DB = "./data/test-webhook-api.db";

describe("Webhook API", () => {
  beforeEach(() => {
    // Clean up test database
    if (existsSync(TEST_DB)) {
      unlinkSync(TEST_DB);
    }
    if (existsSync(`${TEST_DB}-shm`)) {
      unlinkSync(`${TEST_DB}-shm`);
    }
    if (existsSync(`${TEST_DB}-wal`)) {
      unlinkSync(`${TEST_DB}-wal`);
    }

    process.env.DATABASE_URL = TEST_DB;
    runMigrations(TEST_DB);
  });

  it("should process Gmail webhook notification", async () => {
    const db = getDb();

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

    expect(res.status).toBe(200);
    expect(await res.text()).toBe("OK");
  });

  it("should handle invalid notification format", async () => {
    const res = await app.request("/webhook/gmail", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });

    expect(res.status).toBe(400);
  });
});
