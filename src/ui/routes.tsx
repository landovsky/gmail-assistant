import { Hono } from "hono";
import { getDb, schema } from "../db/index.js";
import { eq, sql, like, or } from "drizzle-orm";
import { EmailListPage } from "./pages/email-list.js";
import { EmailDetailPage } from "./pages/email-detail.js";

export const uiRoutes = new Hono();
const db = getDb();

// GET /debug/emails - Email list with search/filter
uiRoutes.get("/emails", async (c) => {
  const status = c.req.query("status");
  const classification = c.req.query("classification");
  const q = c.req.query("q");

  let conditions = [];
  if (status) conditions.push(eq(schema.emails.status, status as any));
  if (classification) conditions.push(eq(schema.emails.classification, classification as any));
  if (q) {
    conditions.push(or(
      like(schema.emails.subject, `%${q}%`),
      like(schema.emails.senderEmail, `%${q}%`),
      like(schema.emails.gmailThreadId, `%${q}%`)
    )!);
  }

  const emailsQuery = db.select().from(schema.emails);
  if (conditions.length > 0) {
    emailsQuery.where(sql`${conditions.join(" AND ")}`);
  }

  const emails = await emailsQuery.limit(200);

  // Get counts for each email
  const emailsWithCounts = await Promise.all(
    emails.map(async (email) => {
      const [events, llmCalls] = await Promise.all([
        db.select({ count: sql<number>`count(*)` }).from(schema.emailEvents)
          .where(eq(schema.emailEvents.gmailThreadId, email.gmailThreadId)),
        db.select({ count: sql<number>`count(*)` }).from(schema.llmCalls)
          .where(eq(schema.llmCalls.gmailThreadId, email.gmailThreadId)),
      ]);
      return {
        ...email,
        event_count: events[0].count,
        llm_call_count: llmCalls[0].count,
      };
    })
  );

  return c.html(
    <EmailListPage
      emails={emailsWithCounts}
      count={emailsWithCounts.length}
      filters={{ status, classification, q }}
    />
  );
});

// GET /debug/email/:id - Email detail with timeline
uiRoutes.get("/email/:id", async (c) => {
  const emailId = parseInt(c.req.param("id"));

  const email = await db.select().from(schema.emails).where(eq(schema.emails.id, emailId)).limit(1);
  if (email.length === 0) {
    return c.text("Email not found", 404);
  }

  const threadId = email[0].gmailThreadId;

  const [events, llmCalls, agentRuns] = await Promise.all([
    db.select().from(schema.emailEvents).where(eq(schema.emailEvents.gmailThreadId, threadId)),
    db.select().from(schema.llmCalls).where(eq(schema.llmCalls.gmailThreadId, threadId)),
    db.select().from(schema.agentRuns).where(eq(schema.agentRuns.gmailThreadId, threadId)),
  ]);

  return c.html(
    <EmailDetailPage
      email={email[0]}
      events={events}
      llmCalls={llmCalls}
      agentRuns={agentRuns}
    />
  );
});
