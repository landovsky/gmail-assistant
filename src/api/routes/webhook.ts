import { Hono } from "hono";
import { getDb, schema } from "../../db/index.js";
import { getJobQueue } from "../../jobs/index.js";
import { eq } from "drizzle-orm";

export const webhookRoutes = new Hono();
const db = getDb();
const queue = getJobQueue();

// POST /webhook/gmail - Receive Gmail Pub/Sub push notifications
webhookRoutes.post("/gmail", async (c) => {
  try {
    const body = await c.req.json();

    // Extract and decode the notification
    const message = body.message;
    if (!message || !message.data) {
      return c.text("Invalid notification format", 400);
    }

    // Decode base64 data
    const decodedData = Buffer.from(message.data, "base64").toString("utf-8");
    const data = JSON.parse(decodedData);

    const { emailAddress, historyId } = data;

    // Look up user by email
    const user = await db
      .select()
      .from(schema.users)
      .where(eq(schema.users.email, emailAddress))
      .limit(1);

    if (user.length === 0) {
      console.warn(`Webhook notification for unknown user: ${emailAddress}`);
      return c.text("User not found", 200); // Return 200 to avoid retries
    }

    // Enqueue sync job with history ID
    await queue.enqueue("sync", user[0].id, {
      user_id: user[0].id,
      history_id: historyId,
      force_full: false,
    });

    console.log(`Webhook: Enqueued sync for user ${user[0].id} (history ${historyId})`);
    return c.text("OK", 200);
  } catch (error) {
    console.error("Webhook processing error:", error);
    return c.text("Internal processing error", 500);
  }
});
