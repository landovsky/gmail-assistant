import { Hono } from "hono";
import { getDb, schema } from "../../db/index.js";
import { eq } from "drizzle-orm";

export const watchRoutes = new Hono();
const db = getDb();

// POST /api/watch - Register Gmail push notifications
watchRoutes.post("/", async (c) => {
  const user_id = c.req.query("user_id");

  // TODO: Implement by gmail-worker
  // This will call Gmail API to register push notifications

  if (user_id) {
    const userId = parseInt(user_id);
    const user = await db
      .select()
      .from(schema.users)
      .where(eq(schema.users.id, userId))
      .limit(1);

    if (user.length === 0) {
      return c.json({ detail: `User ${userId} not found` }, 404);
    }

    return c.json({
      detail: "Not yet implemented - requires gmail-worker watch registration",
    }, 501);
  }

  // Register for all users
  return c.json({
    detail: "Not yet implemented - requires gmail-worker watch registration",
  }, 501);
});

// GET /api/watch/status - Show watch state for all users
watchRoutes.get("/status", async (c) => {
  const states = await db
    .select({
      user_id: schema.syncState.userId,
      email: schema.users.email,
      last_history_id: schema.syncState.lastHistoryId,
      last_sync_at: schema.syncState.lastSyncAt,
      watch_expiration: schema.syncState.watchExpiration,
      watch_resource_id: schema.syncState.watchResourceId,
    })
    .from(schema.syncState)
    .innerJoin(schema.users, eq(schema.users.id, schema.syncState.userId));

  return c.json(states);
});
