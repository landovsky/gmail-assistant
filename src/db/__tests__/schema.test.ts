/**
 * Database Schema Tests
 * Validates all tables, constraints, relationships, and indexes
 */

import { describe, test, expect, beforeAll, afterAll } from "bun:test";
import { drizzle } from "drizzle-orm/better-sqlite3";
import Database from "better-sqlite3";
import { migrate } from "drizzle-orm/better-sqlite3/migrator";
import { eq, and } from "drizzle-orm";
import * as schema from "../schema.js";

// Use in-memory database for tests
const sqlite = new Database(":memory:");
sqlite.pragma("foreign_keys = ON");
const db = drizzle(sqlite, { schema });

beforeAll(() => {
  // Run migrations once before all tests
  migrate(db, { migrationsFolder: "./drizzle" });
});

afterAll(() => {
  sqlite.close();
});

describe("Users Table", () => {
  test("should create user with all required fields", () => {
    const user = db
      .insert(schema.users)
      .values({
        email: "test1@gmail.com",
        displayName: "Test User",
      })
      .returning()
      .get();

    expect(user.id).toBeGreaterThan(0);
    expect(user.email).toBe("test1@gmail.com");
    expect(user.displayName).toBe("Test User");
    expect(user.isActive).toBe(1); // SQLite boolean as integer
    expect(user.createdAt).toBeTruthy();
  });

  test("should enforce unique email constraint", () => {
    db.insert(schema.users)
      .values({ email: "duplicate@gmail.com" })
      .run();

    expect(() => {
      db.insert(schema.users)
        .values({ email: "duplicate@gmail.com" })
        .run();
    }).toThrow();
  });

  test("should require email field", () => {
    expect(() => {
      db.insert(schema.users)
        .values({} as any)
        .run();
    }).toThrow();
  });
});

describe("Emails Table", () => {
  test("should create email with all required fields", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test2@gmail.com" })
      .returning()
      .get();

    const email = db
      .insert(schema.emails)
      .values({
        userId: user.id,
        gmailThreadId: "thread_123",
        gmailMessageId: "msg_456",
        senderEmail: "sender@example.com",
        classification: "needs_response",
      })
      .returning()
      .get();

    expect(email.id).toBeGreaterThan(0);
    expect(email.userId).toBe(user.id);
    expect(email.gmailThreadId).toBe("thread_123");
    expect(email.classification).toBe("needs_response");
    expect(email.confidence).toBe("medium");
    expect(email.status).toBe("pending");
    expect(email.detectedLanguage).toBe("cs");
    expect(email.resolvedStyle).toBe("business");
    expect(email.messageCount).toBe(1);
    expect(email.reworkCount).toBe(0);
  });

  test("should enforce unique (user_id, gmail_thread_id) constraint", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test3@gmail.com" })
      .returning()
      .get();

    db.insert(schema.emails)
      .values({
        userId: user.id,
        gmailThreadId: "thread_unique",
        gmailMessageId: "msg_1",
        senderEmail: "sender@example.com",
        classification: "fyi",
      })
      .run();

    expect(() => {
      db.insert(schema.emails)
        .values({
          userId: user.id,
          gmailThreadId: "thread_unique",
          gmailMessageId: "msg_2",
          senderEmail: "sender@example.com",
          classification: "fyi",
        })
        .run();
    }).toThrow();
  });

  test("should enforce foreign key to users", () => {
    expect(() => {
      db.insert(schema.emails)
        .values({
          userId: 9999,
          gmailThreadId: "thread_123",
          gmailMessageId: "msg_456",
          senderEmail: "sender@example.com",
          classification: "fyi",
        })
        .run();
    }).toThrow();
  });

  test("should allow different threads for same user", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test4@gmail.com" })
      .returning()
      .get();

    db.insert(schema.emails)
      .values({
        userId: user.id,
        gmailThreadId: "thread_1",
        gmailMessageId: "msg_1",
        senderEmail: "sender@example.com",
        classification: "fyi",
      })
      .run();

    const email2 = db
      .insert(schema.emails)
      .values({
        userId: user.id,
        gmailThreadId: "thread_2",
        gmailMessageId: "msg_2",
        senderEmail: "sender@example.com",
        classification: "needs_response",
      })
      .returning()
      .get();

    expect(email2.id).toBeGreaterThan(0);
  });

  test("should track rework iterations", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test5@gmail.com" })
      .returning()
      .get();

    const email = db
      .insert(schema.emails)
      .values({
        userId: user.id,
        gmailThreadId: "thread_rework",
        gmailMessageId: "msg_456",
        senderEmail: "sender@example.com",
        classification: "needs_response",
        status: "rework_requested",
        reworkCount: 2,
        lastReworkInstruction: "Make it more formal",
      })
      .returning()
      .get();

    expect(email.reworkCount).toBe(2);
    expect(email.lastReworkInstruction).toBe("Make it more formal");
  });
});

describe("User Labels Table", () => {
  test("should create user label mapping", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test6@gmail.com" })
      .returning()
      .get();

    const label = db
      .insert(schema.userLabels)
      .values({
        userId: user.id,
        labelKey: "needs_response",
        gmailLabelId: "Label_1",
        gmailLabelName: "Needs Response",
      })
      .returning()
      .get();

    expect(label.userId).toBe(user.id);
    expect(label.labelKey).toBe("needs_response");
    expect(label.gmailLabelId).toBe("Label_1");
  });

  test("should enforce composite primary key", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test7@gmail.com" })
      .returning()
      .get();

    db.insert(schema.userLabels)
      .values({
        userId: user.id,
        labelKey: "outbox",
        gmailLabelId: "Label_2",
        gmailLabelName: "Outbox",
      })
      .run();

    expect(() => {
      db.insert(schema.userLabels)
        .values({
          userId: user.id,
          labelKey: "outbox",
          gmailLabelId: "Label_3",
          gmailLabelName: "Different Outbox",
        })
        .run();
    }).toThrow();
  });
});

describe("User Settings Table", () => {
  test("should store JSON-encoded settings", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test8@gmail.com" })
      .returning()
      .get();

    const setting = db
      .insert(schema.userSettings)
      .values({
        userId: user.id,
        settingKey: "communication_styles",
        settingValue: JSON.stringify({ formal: "Dear...", business: "Hi..." }),
      })
      .returning()
      .get();

    expect(setting.userId).toBe(user.id);
    expect(setting.settingKey).toBe("communication_styles");
    const parsed = JSON.parse(setting.settingValue);
    expect(parsed.formal).toBe("Dear...");
  });

  test("should enforce composite primary key", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test9@gmail.com" })
      .returning()
      .get();

    db.insert(schema.userSettings)
      .values({
        userId: user.id,
        settingKey: "default_language",
        settingValue: '"cs"',
      })
      .run();

    expect(() => {
      db.insert(schema.userSettings)
        .values({
          userId: user.id,
          settingKey: "default_language",
          settingValue: '"en"',
        })
        .run();
    }).toThrow();
  });
});

describe("Sync State Table", () => {
  test("should create one sync state per user", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test10@gmail.com" })
      .returning()
      .get();

    const syncState = db
      .insert(schema.syncState)
      .values({
        userId: user.id,
        lastHistoryId: "12345",
      })
      .returning()
      .get();

    expect(syncState.userId).toBe(user.id);
    expect(syncState.lastHistoryId).toBe("12345");
    expect(syncState.lastSyncAt).toBeTruthy();
  });

  test("should enforce one-to-one relationship with users", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test11@gmail.com" })
      .returning()
      .get();

    db.insert(schema.syncState)
      .values({
        userId: user.id,
        lastHistoryId: "12345",
      })
      .run();

    expect(() => {
      db.insert(schema.syncState)
        .values({
          userId: user.id,
          lastHistoryId: "67890",
        })
        .run();
    }).toThrow();
  });
});

describe("Jobs Table", () => {
  test("should create job with default values", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test12@gmail.com" })
      .returning()
      .get();

    const job = db
      .insert(schema.jobs)
      .values({
        jobType: "classify",
        userId: user.id,
      })
      .returning()
      .get();

    expect(job.id).toBeGreaterThan(0);
    expect(job.jobType).toBe("classify");
    expect(job.status).toBe("pending");
    expect(job.attempts).toBe(0);
    expect(job.maxAttempts).toBe(3);
    expect(job.payload).toBe("{}");
  });

  test("should store JSON payload", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test13@gmail.com" })
      .returning()
      .get();

    const job = db
      .insert(schema.jobs)
      .values({
        jobType: "draft",
        userId: user.id,
        payload: JSON.stringify({ threadId: "thread_123", priority: "high" }),
      })
      .returning()
      .get();

    const parsed = JSON.parse(job.payload);
    expect(parsed.threadId).toBe("thread_123");
  });

  test("should track retry attempts", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test14@gmail.com" })
      .returning()
      .get();

    const job = db
      .insert(schema.jobs)
      .values({
        jobType: "sync",
        userId: user.id,
        status: "failed",
        attempts: 3,
        errorMessage: "Rate limit exceeded",
      })
      .returning()
      .get();

    expect(job.attempts).toBe(3);
    expect(job.errorMessage).toBe("Rate limit exceeded");
  });
});

describe("Email Events Table", () => {
  test("should create immutable audit event", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test15@gmail.com" })
      .returning()
      .get();

    const event = db
      .insert(schema.emailEvents)
      .values({
        userId: user.id,
        gmailThreadId: "thread_123",
        eventType: "classified",
        detail: "Classified as needs_response with high confidence",
      })
      .returning()
      .get();

    expect(event.id).toBeGreaterThan(0);
    expect(event.eventType).toBe("classified");
    expect(event.createdAt).toBeTruthy();
  });

  test("should allow multiple events for same thread", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test16@gmail.com" })
      .returning()
      .get();

    db.insert(schema.emailEvents)
      .values({
        userId: user.id,
        gmailThreadId: "thread_events",
        eventType: "classified",
      })
      .run();

    const event2 = db
      .insert(schema.emailEvents)
      .values({
        userId: user.id,
        gmailThreadId: "thread_events",
        eventType: "draft_created",
        draftId: "draft_456",
      })
      .returning()
      .get();

    expect(event2.eventType).toBe("draft_created");
    expect(event2.draftId).toBe("draft_456");
  });
});

describe("LLM Calls Table", () => {
  test("should track LLM API call with metrics", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test17@gmail.com" })
      .returning()
      .get();

    const call = db
      .insert(schema.llmCalls)
      .values({
        userId: user.id,
        gmailThreadId: "thread_123",
        callType: "classify",
        model: "claude-3-5-sonnet-20241022",
        systemPrompt: "You are a classifier...",
        userMessage: "Classify this email...",
        responseText: "Classification: needs_response",
        promptTokens: 150,
        completionTokens: 50,
        totalTokens: 200,
        latencyMs: 1250,
      })
      .returning()
      .get();

    expect(call.callType).toBe("classify");
    expect(call.model).toBe("claude-3-5-sonnet-20241022");
    expect(call.totalTokens).toBe(200);
    expect(call.latencyMs).toBe(1250);
  });

  test("should allow nullable user_id for system calls", () => {
    const call = db
      .insert(schema.llmCalls)
      .values({
        userId: null,
        callType: "context",
        model: "gpt-4",
        promptTokens: 100,
      })
      .returning()
      .get();

    expect(call.userId).toBeNull();
  });
});

describe("Agent Runs Table", () => {
  test("should track agent execution session", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test18@gmail.com" })
      .returning()
      .get();

    const run = db
      .insert(schema.agentRuns)
      .values({
        userId: user.id,
        gmailThreadId: "thread_123",
        profile: "payment_processor",
        status: "running",
        iterations: 3,
      })
      .returning()
      .get();

    expect(run.profile).toBe("payment_processor");
    expect(run.status).toBe("running");
    expect(run.iterations).toBe(3);
    expect(run.toolCallsLog).toBe("[]");
  });

  test("should store tool calls as JSON array", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test19@gmail.com" })
      .returning()
      .get();

    const toolCalls = [
      { tool: "extract_vendor", args: { text: "..." } },
      { tool: "create_payment", args: { amount: 100 } },
    ];

    const run = db
      .insert(schema.agentRuns)
      .values({
        userId: user.id,
        gmailThreadId: "thread_123",
        profile: "payment_processor",
        status: "completed",
        toolCallsLog: JSON.stringify(toolCalls),
        finalMessage: "Payment processed successfully",
      })
      .returning()
      .get();

    const parsed = JSON.parse(run.toolCallsLog);
    expect(parsed.length).toBe(2);
    expect(parsed[0].tool).toBe("extract_vendor");
  });
});

describe("Indexes", () => {
  test("should support queries on emails by classification and status", () => {
    const user = db
      .insert(schema.users)
      .values({ email: "test20@gmail.com" })
      .returning()
      .get();

    // Create multiple emails
    for (let i = 0; i < 10; i++) {
      db.insert(schema.emails)
        .values({
          userId: user.id,
          gmailThreadId: `thread_idx_${i}`,
          gmailMessageId: `msg_${i}`,
          senderEmail: "sender@example.com",
          classification: i % 2 === 0 ? "needs_response" : "fyi",
          status: i < 5 ? "pending" : "drafted",
        })
        .run();
    }

    // Query by classification - should use index
    const needsResponse = db
      .select()
      .from(schema.emails)
      .where(
        and(
          eq(schema.emails.userId, user.id),
          eq(schema.emails.classification, "needs_response")
        )
      )
      .all();

    expect(needsResponse.length).toBe(5);

    // Query by status - should use index
    const pending = db
      .select()
      .from(schema.emails)
      .where(
        and(eq(schema.emails.userId, user.id), eq(schema.emails.status, "pending"))
      )
      .all();

    expect(pending.length).toBe(5);
  });
});
