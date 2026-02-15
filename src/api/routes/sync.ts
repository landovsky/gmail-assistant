import { Hono } from "hono";
import { getDb, schema } from "../../db/index.js";
import { getJobQueue } from "../../jobs/index.js";
import { eq } from "drizzle-orm";

export const syncRoutes = new Hono();
const db = getDb();
const queue = getJobQueue();

// POST /api/sync - Enqueue a sync job for a user
syncRoutes.post("/", async (c) => {
  const user_id = parseInt(c.req.query("user_id") || "1");
  const force_full = c.req.query("full") === "true";

  // Check if user exists
  const user = await db
    .select()
    .from(schema.users)
    .where(eq(schema.users.id, user_id))
    .limit(1);

  if (user.length === 0) {
    return c.json(
      { detail: `User ${user_id} not found. Run POST /api/auth/init first.` },
      404
    );
  }

  // Enqueue sync job
  await queue.enqueue("sync", user_id, {
    user_id,
    force_full,
  });

  return c.json({
    queued: true,
    user_id,
    full: force_full,
  });
});

// POST /api/reset - Reset transient data
syncRoutes.post("/reset", async (c) => {
  const jobsDeleted = await db.delete(schema.jobs).returning({ id: schema.jobs.id });
  const emailsDeleted = await db.delete(schema.emails).returning({ id: schema.emails.id });
  const eventsDeleted = await db.delete(schema.emailEvents).returning({ id: schema.emailEvents.id });
  
  // Reset sync state to 0
  await db.update(schema.syncState).set({ lastHistoryId: "0" });

  return c.json({
    deleted: {
      jobs: jobsDeleted.length,
      emails: emailsDeleted.length,
      email_events: eventsDeleted.length,
      sync_state: 0,
    },
    total: jobsDeleted.length + emailsDeleted.length + eventsDeleted.length,
  });
});
