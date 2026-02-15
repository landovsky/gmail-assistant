import {
  sqliteTable,
  text,
  integer,
  index,
  uniqueIndex,
  primaryKey,
} from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";

// Users table
export const users = sqliteTable("users", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  email: text("email").notNull().unique(),
  displayName: text("display_name"),
  isActive: integer("is_active", { mode: "boolean" }).notNull().default(true),
  onboardedAt: text("onboarded_at"),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});

// Emails table
export const emails = sqliteTable(
  "emails",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    userId: integer("user_id")
      .notNull()
      .references(() => users.id),
    gmailThreadId: text("gmail_thread_id").notNull(),
    gmailMessageId: text("gmail_message_id").notNull(),
    senderEmail: text("sender_email").notNull(),
    senderName: text("sender_name"),
    subject: text("subject"),
    snippet: text("snippet"),
    receivedAt: text("received_at"),
    classification: text("classification", {
      enum: [
        "needs_response",
        "action_required",
        "payment_request",
        "fyi",
        "waiting",
      ],
    }).notNull(),
    confidence: text("confidence", { enum: ["high", "medium", "low"] })
      .notNull()
      .default("medium"),
    reasoning: text("reasoning"),
    detectedLanguage: text("detected_language").notNull().default("cs"),
    resolvedStyle: text("resolved_style").notNull().default("business"),
    messageCount: integer("message_count").notNull().default(1),
    status: text("status", {
      enum: [
        "pending",
        "drafted",
        "rework_requested",
        "sent",
        "skipped",
        "archived",
      ],
    })
      .notNull()
      .default("pending"),
    draftId: text("draft_id"),
    reworkCount: integer("rework_count").notNull().default(0),
    lastReworkInstruction: text("last_rework_instruction"),
    vendorName: text("vendor_name"),
    processedAt: text("processed_at")
      .notNull()
      .default(sql`(datetime('now'))`),
    draftedAt: text("drafted_at"),
    actedAt: text("acted_at"),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(datetime('now'))`),
    updatedAt: text("updated_at")
      .notNull()
      .default(sql`(datetime('now'))`),
  },
  (table) => ({
    userThreadIdx: uniqueIndex("emails_user_thread_idx").on(
      table.userId,
      table.gmailThreadId
    ),
    userClassificationIdx: index("emails_user_classification_idx").on(
      table.userId,
      table.classification
    ),
    userStatusIdx: index("emails_user_status_idx").on(
      table.userId,
      table.status
    ),
    gmailThreadIdx: index("emails_gmail_thread_idx").on(table.gmailThreadId),
  })
);

// User Labels table
export const userLabels = sqliteTable(
  "user_labels",
  {
    userId: integer("user_id")
      .notNull()
      .references(() => users.id),
    labelKey: text("label_key").notNull(),
    gmailLabelId: text("gmail_label_id").notNull(),
    gmailLabelName: text("gmail_label_name").notNull(),
  },
  (table) => ({
    pk: primaryKey({ columns: [table.userId, table.labelKey] }),
  })
);

// User Settings table
export const userSettings = sqliteTable(
  "user_settings",
  {
    userId: integer("user_id")
      .notNull()
      .references(() => users.id),
    settingKey: text("setting_key").notNull(),
    settingValue: text("setting_value").notNull(),
  },
  (table) => ({
    pk: primaryKey({ columns: [table.userId, table.settingKey] }),
  })
);

// Sync State table
export const syncState = sqliteTable("sync_state", {
  userId: integer("user_id")
    .primaryKey()
    .notNull()
    .references(() => users.id),
  lastHistoryId: text("last_history_id").notNull().default("0"),
  lastSyncAt: text("last_sync_at")
    .notNull()
    .default(sql`(datetime('now'))`),
  watchExpiration: text("watch_expiration"),
  watchResourceId: text("watch_resource_id"),
});

// Jobs table
export const jobs = sqliteTable(
  "jobs",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    jobType: text("job_type", {
      enum: [
        "sync",
        "classify",
        "draft",
        "cleanup",
        "rework",
        "manual_draft",
        "agent_process",
      ],
    }).notNull(),
    userId: integer("user_id")
      .notNull()
      .references(() => users.id),
    payload: text("payload").notNull().default("{}"),
    status: text("status", {
      enum: ["pending", "running", "completed", "failed"],
    })
      .notNull()
      .default("pending"),
    attempts: integer("attempts").notNull().default(0),
    maxAttempts: integer("max_attempts").notNull().default(3),
    errorMessage: text("error_message"),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(datetime('now'))`),
    startedAt: text("started_at"),
    completedAt: text("completed_at"),
  },
  (table) => ({
    statusCreatedIdx: index("jobs_status_created_idx").on(
      table.status,
      table.createdAt
    ),
    userJobTypeIdx: index("jobs_user_job_type_idx").on(
      table.userId,
      table.jobType
    ),
  })
);

// Email Events table
export const emailEvents = sqliteTable(
  "email_events",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    userId: integer("user_id")
      .notNull()
      .references(() => users.id),
    gmailThreadId: text("gmail_thread_id").notNull(),
    eventType: text("event_type", {
      enum: [
        "classified",
        "label_added",
        "label_removed",
        "draft_created",
        "draft_trashed",
        "draft_reworked",
        "sent_detected",
        "archived",
        "rework_limit_reached",
        "waiting_retriaged",
        "error",
      ],
    }).notNull(),
    detail: text("detail"),
    labelId: text("label_id"),
    draftId: text("draft_id"),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(datetime('now'))`),
  },
  (table) => ({
    userThreadIdx: index("email_events_user_thread_idx").on(
      table.userId,
      table.gmailThreadId
    ),
    eventTypeIdx: index("email_events_event_type_idx").on(table.eventType),
  })
);

// LLM Calls table
export const llmCalls = sqliteTable(
  "llm_calls",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    userId: integer("user_id").references(() => users.id),
    gmailThreadId: text("gmail_thread_id"),
    callType: text("call_type", {
      enum: ["classify", "draft", "rework", "context", "agent"],
    }).notNull(),
    model: text("model").notNull(),
    systemPrompt: text("system_prompt"),
    userMessage: text("user_message"),
    responseText: text("response_text"),
    promptTokens: integer("prompt_tokens").notNull().default(0),
    completionTokens: integer("completion_tokens").notNull().default(0),
    totalTokens: integer("total_tokens").notNull().default(0),
    latencyMs: integer("latency_ms").notNull().default(0),
    error: text("error"),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(datetime('now'))`),
  },
  (table) => ({
    gmailThreadIdx: index("llm_calls_gmail_thread_idx").on(
      table.gmailThreadId
    ),
    callTypeIdx: index("llm_calls_call_type_idx").on(table.callType),
    userIdIdx: index("llm_calls_user_id_idx").on(table.userId),
    createdAtIdx: index("llm_calls_created_at_idx").on(table.createdAt),
  })
);

// Agent Runs table
export const agentRuns = sqliteTable(
  "agent_runs",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    userId: integer("user_id")
      .notNull()
      .references(() => users.id),
    gmailThreadId: text("gmail_thread_id").notNull(),
    profile: text("profile").notNull(),
    status: text("status", {
      enum: ["running", "completed", "error", "max_iterations"],
    })
      .notNull()
      .default("running"),
    toolCallsLog: text("tool_calls_log").notNull().default("[]"),
    finalMessage: text("final_message"),
    iterations: integer("iterations").notNull().default(0),
    error: text("error"),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(datetime('now'))`),
    completedAt: text("completed_at"),
  },
  (table) => ({
    userIdIdx: index("agent_runs_user_id_idx").on(table.userId),
    gmailThreadIdx: index("agent_runs_gmail_thread_idx").on(
      table.gmailThreadId
    ),
    statusIdx: index("agent_runs_status_idx").on(table.status),
  })
);

// Type exports for application use
export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;

export type Email = typeof emails.$inferSelect;
export type NewEmail = typeof emails.$inferInsert;

export type UserLabel = typeof userLabels.$inferSelect;
export type NewUserLabel = typeof userLabels.$inferInsert;

export type UserSetting = typeof userSettings.$inferSelect;
export type NewUserSetting = typeof userSettings.$inferInsert;

export type SyncState = typeof syncState.$inferSelect;
export type NewSyncState = typeof syncState.$inferInsert;

export type Job = typeof jobs.$inferSelect;
export type NewJob = typeof jobs.$inferInsert;

export type EmailEvent = typeof emailEvents.$inferSelect;
export type NewEmailEvent = typeof emailEvents.$inferInsert;

export type LLMCall = typeof llmCalls.$inferSelect;
export type NewLLMCall = typeof llmCalls.$inferInsert;

export type AgentRun = typeof agentRuns.$inferSelect;
export type NewAgentRun = typeof agentRuns.$inferInsert;
