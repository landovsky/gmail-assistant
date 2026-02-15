import { Hono } from "hono";
import { getDb, schema } from "../../db/index.js";
import { eq, and, sql } from "drizzle-orm";

export const briefingRoutes = new Hono();
const db = getDb();

// GET /api/briefing/:user_email - Get inbox briefing/summary for a user
briefingRoutes.get("/:user_email", async (c) => {
  const userEmail = c.req.param("user_email");

  // Find user by email
  const user = await db
    .select()
    .from(schema.users)
    .where(eq(schema.users.email, userEmail))
    .limit(1);

  if (user.length === 0) {
    return c.json({ detail: "User not found" }, 404);
  }

  const userId = user[0].id;

  // Get email counts by classification and status
  const classifications = [
    "needs_response",
    "action_required",
    "payment_request",
    "fyi",
    "waiting",
  ] as const;

  const summary: Record<string, any> = {};

  for (const classification of classifications) {
    const total = await db
      .select({ count: sql<number>`count(*)` })
      .from(schema.emails)
      .where(
        and(
          eq(schema.emails.userId, userId),
          eq(schema.emails.classification, classification)
        )
      );

    const active = await db
      .select({ count: sql<number>`count(*)` })
      .from(schema.emails)
      .where(
        and(
          eq(schema.emails.userId, userId),
          eq(schema.emails.classification, classification),
          sql`${schema.emails.status} NOT IN ('sent', 'archived')`
        )
      );

    const items = await db
      .select({
        thread_id: schema.emails.gmailThreadId,
        subject: schema.emails.subject,
        sender: schema.emails.senderEmail,
        status: schema.emails.status,
        confidence: schema.emails.confidence,
      })
      .from(schema.emails)
      .where(
        and(
          eq(schema.emails.userId, userId),
          eq(schema.emails.classification, classification),
          sql`${schema.emails.status} NOT IN ('sent', 'archived')`
        )
      )
      .limit(10);

    summary[classification] = {
      total: total[0].count,
      active: active[0].count,
      items,
    };
  }

  // Calculate pending drafts and action items
  const pendingDrafts = await db
    .select({ count: sql<number>`count(*)` })
    .from(schema.emails)
    .where(
      and(
        eq(schema.emails.userId, userId),
        sql`${schema.emails.status} IN ('pending', 'drafted')`
      )
    );

  const actionItems =
    (summary.needs_response?.active || 0) + (summary.action_required?.active || 0);

  return c.json({
    user: userEmail,
    summary,
    pending_drafts: pendingDrafts[0].count,
    action_items: actionItems,
  });
});
