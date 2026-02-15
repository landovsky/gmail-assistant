import { Hono } from "hono";
import { getDb, schema } from "../../db/index.js";
import { getJobQueue } from "../../jobs/index.js";
import { eq, and, sql, like, or } from "drizzle-orm";

export const debugRoutes = new Hono();
const db = getDb();
const queue = getJobQueue();

// GET /api/debug/emails - List emails with search, filter, and per-email debug counts
debugRoutes.get("/emails", async (c) => {
  const status = c.req.query("status");
  const classification = c.req.query("classification");
  const q = c.req.query("q");
  const limit = Math.min(parseInt(c.req.query("limit") || "50"), 500);

  let conditions = [];

  if (status) {
    conditions.push(eq(schema.emails.status, status as any));
  }

  if (classification) {
    conditions.push(eq(schema.emails.classification, classification as any));
  }

  if (q) {
    // Full-text search across multiple fields
    conditions.push(
      or(
        like(schema.emails.subject, `%${q}%`),
        like(schema.emails.snippet, `%${q}%`),
        like(schema.emails.reasoning, `%${q}%`),
        like(schema.emails.senderEmail, `%${q}%`),
        like(schema.emails.gmailThreadId, `%${q}%`)
      )!
    );
  }

  const query = conditions.length > 0 ? and(...conditions) : undefined;

  const emails = await db
    .select({
      id: schema.emails.id,
      user_id: schema.emails.userId,
      user_email: schema.users.email,
      gmail_thread_id: schema.emails.gmailThreadId,
      subject: schema.emails.subject,
      sender_email: schema.emails.senderEmail,
      classification: schema.emails.classification,
      status: schema.emails.status,
      confidence: schema.emails.confidence,
      received_at: schema.emails.receivedAt,
      processed_at: schema.emails.processedAt,
    })
    .from(schema.emails)
    .innerJoin(schema.users, eq(schema.users.id, schema.emails.userId))
    .where(query)
    .orderBy(sql`${schema.emails.id} DESC`)
    .limit(limit);

  // Get counts for each email
  const emailsWithCounts = await Promise.all(
    emails.map(async (email) => {
      const [eventCount, llmCount, agentCount] = await Promise.all([
        db
          .select({ count: sql<number>`count(*)` })
          .from(schema.emailEvents)
          .where(eq(schema.emailEvents.gmailThreadId, email.gmail_thread_id)),
        db
          .select({ count: sql<number>`count(*)` })
          .from(schema.llmCalls)
          .where(eq(schema.llmCalls.gmailThreadId, email.gmail_thread_id)),
        db
          .select({ count: sql<number>`count(*)` })
          .from(schema.agentRuns)
          .where(eq(schema.agentRuns.gmailThreadId, email.gmail_thread_id)),
      ]);

      return {
        ...email,
        event_count: eventCount[0].count,
        llm_call_count: llmCount[0].count,
        agent_run_count: agentCount[0].count,
      };
    })
  );

  return c.json({
    count: emails.length,
    limit,
    filters: {
      status: status || null,
      classification: classification || null,
      q: q || null,
    },
    emails: emailsWithCounts,
  });
});

// GET /api/emails/:email_id/debug - Get all debug data for a specific email
debugRoutes.get("/emails/:email_id", async (c) => {
  const emailId = parseInt(c.req.param("email_id"));

  const email = await db
    .select()
    .from(schema.emails)
    .where(eq(schema.emails.id, emailId))
    .limit(1);

  if (email.length === 0) {
    return c.json({ detail: `Email ${emailId} not found` }, 404);
  }

  const threadId = email[0].gmailThreadId;

  // Fetch all related data
  const [events, llmCalls, agentRuns] = await Promise.all([
    db
      .select()
      .from(schema.emailEvents)
      .where(eq(schema.emailEvents.gmailThreadId, threadId))
      .orderBy(sql`${schema.emailEvents.createdAt} DESC`),
    db
      .select()
      .from(schema.llmCalls)
      .where(eq(schema.llmCalls.gmailThreadId, threadId))
      .orderBy(sql`${schema.llmCalls.createdAt} DESC`),
    db
      .select()
      .from(schema.agentRuns)
      .where(eq(schema.agentRuns.gmailThreadId, threadId))
      .orderBy(sql`${schema.agentRuns.createdAt} DESC`),
  ]);

  // Build timeline by merging all events
  const timeline = [
    ...events.map((e) => ({ type: "event", timestamp: e.createdAt, data: e })),
    ...llmCalls.map((l) => ({ type: "llm_call", timestamp: l.createdAt, data: l })),
    ...agentRuns.map((a) => ({ type: "agent_run", timestamp: a.createdAt, data: a })),
  ].sort((a, b) => b.timestamp.localeCompare(a.timestamp));

  // Calculate summary
  const totalTokens = llmCalls.reduce((sum, call) => sum + call.totalTokens, 0);
  const totalLatency = llmCalls.reduce((sum, call) => sum + call.latencyMs, 0);
  const errorCount = llmCalls.filter((call) => call.error).length;

  const llmBreakdown: Record<string, any> = {};
  for (const call of llmCalls) {
    if (!llmBreakdown[call.callType]) {
      llmBreakdown[call.callType] = {
        count: 0,
        tokens: 0,
        latency_ms: 0,
      };
    }
    llmBreakdown[call.callType].count++;
    llmBreakdown[call.callType].tokens += call.totalTokens;
    llmBreakdown[call.callType].latency_ms += call.latencyMs;
  }

  return c.json({
    email: email[0],
    events,
    llm_calls: llmCalls,
    agent_runs: agentRuns,
    timeline,
    summary: {
      email_id: emailId,
      gmail_thread_id: threadId,
      classification: email[0].classification,
      status: email[0].status,
      event_count: events.length,
      llm_call_count: llmCalls.length,
      agent_run_count: agentRuns.length,
      total_tokens: totalTokens,
      total_latency_ms: totalLatency,
      error_count: errorCount,
      llm_breakdown: llmBreakdown,
      rework_count: email[0].reworkCount,
    },
  });
});

// POST /api/emails/:email_id/reclassify - Force reclassification of an email
debugRoutes.post("/emails/:email_id/reclassify", async (c) => {
  const emailId = parseInt(c.req.param("email_id"));

  const email = await db
    .select()
    .from(schema.emails)
    .where(eq(schema.emails.id, emailId))
    .limit(1);

  if (email.length === 0) {
    return c.json({ detail: `Email ${emailId} not found` }, 404);
  }

  if (!email[0].gmailMessageId) {
    return c.json({ detail: "Email has no Gmail message ID" }, 400);
  }

  // Enqueue classify job with force flag
  const jobId = await queue.enqueue("classify", email[0].userId, {
    user_id: email[0].userId,
    thread_id: email[0].gmailThreadId,
    message_id: email[0].gmailMessageId,
    force: true,
  });

  return c.json({
    status: "queued",
    job_id: jobId,
    email_id: emailId,
    current_classification: email[0].classification,
  });
});
