/**
 * Test Helpers for Database Tests
 * Provides utilities to quickly create test data
 */

import type { BetterSQLite3Database } from "drizzle-orm/better-sqlite3";
import * as schema from "../schema.js";
import type { NewUser, NewEmail, NewUserLabel, NewJob } from "../schema.js";

/**
 * Create a test user with minimal data
 */
export function createTestUser(
  db: BetterSQLite3Database<typeof schema>,
  overrides: Partial<NewUser> = {}
): schema.User {
  const email = overrides.email || `test-${Date.now()}@example.com`;
  return db
    .insert(schema.users)
    .values({
      email,
      displayName: overrides.displayName || "Test User",
      isActive: overrides.isActive ?? true,
      onboardedAt: overrides.onboardedAt || null,
    })
    .returning()
    .get();
}

/**
 * Create a test email with minimal data
 */
export function createTestEmail(
  db: BetterSQLite3Database<typeof schema>,
  userId: number,
  overrides: Partial<Omit<NewEmail, "userId">> = {}
): schema.Email {
  const timestamp = Date.now();
  return db
    .insert(schema.emails)
    .values({
      userId,
      gmailThreadId: overrides.gmailThreadId || `thread_${timestamp}`,
      gmailMessageId: overrides.gmailMessageId || `msg_${timestamp}`,
      senderEmail: overrides.senderEmail || "sender@example.com",
      senderName: overrides.senderName,
      subject: overrides.subject || "Test Subject",
      snippet: overrides.snippet || "Test snippet",
      receivedAt: overrides.receivedAt,
      classification: overrides.classification || "fyi",
      confidence: overrides.confidence || "medium",
      reasoning: overrides.reasoning,
      detectedLanguage: overrides.detectedLanguage || "cs",
      resolvedStyle: overrides.resolvedStyle || "business",
      messageCount: overrides.messageCount || 1,
      status: overrides.status || "pending",
      draftId: overrides.draftId,
      reworkCount: overrides.reworkCount || 0,
      lastReworkInstruction: overrides.lastReworkInstruction,
      vendorName: overrides.vendorName,
      processedAt: overrides.processedAt,
      draftedAt: overrides.draftedAt,
      actedAt: overrides.actedAt,
    })
    .returning()
    .get();
}

/**
 * Create test labels for a user
 */
export function createTestLabels(
  db: BetterSQLite3Database<typeof schema>,
  userId: number
): schema.UserLabel[] {
  const labelKeys = [
    "needs_response",
    "action_required",
    "payment_request",
    "fyi",
    "waiting",
    "outbox",
    "rework",
    "done",
  ];

  const labels: NewUserLabel[] = labelKeys.map((key, index) => ({
    userId,
    labelKey: key,
    gmailLabelId: `Label_${index + 1}`,
    gmailLabelName: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
  }));

  return db.insert(schema.userLabels).values(labels).returning().all();
}

/**
 * Create a test job
 */
export function createTestJob(
  db: BetterSQLite3Database<typeof schema>,
  userId: number,
  overrides: Partial<Omit<NewJob, "userId">> = {}
): schema.Job {
  return db
    .insert(schema.jobs)
    .values({
      userId,
      jobType: overrides.jobType || "sync",
      payload: overrides.payload || "{}",
      status: overrides.status || "pending",
      attempts: overrides.attempts || 0,
      maxAttempts: overrides.maxAttempts || 3,
      errorMessage: overrides.errorMessage,
      startedAt: overrides.startedAt,
      completedAt: overrides.completedAt,
    })
    .returning()
    .get();
}

/**
 * Create a complete test user with labels, settings, and sync state
 */
export function createCompleteTestUser(
  db: BetterSQLite3Database<typeof schema>,
  email?: string
): {
  user: schema.User;
  labels: schema.UserLabel[];
} {
  const user = createTestUser(db, { email });
  const labels = createTestLabels(db, user.id);

  // Create default settings
  db.insert(schema.userSettings)
    .values([
      {
        userId: user.id,
        settingKey: "default_language",
        settingValue: JSON.stringify("cs"),
      },
      {
        userId: user.id,
        settingKey: "sign_off_name",
        settingValue: JSON.stringify(user.displayName),
      },
    ])
    .run();

  // Create sync state
  db.insert(schema.syncState)
    .values({
      userId: user.id,
      lastHistoryId: "0",
    })
    .run();

  return { user, labels };
}

/**
 * Create a batch of test emails for a user
 */
export function createTestEmails(
  db: BetterSQLite3Database<typeof schema>,
  userId: number,
  count: number,
  baseOverrides: Partial<Omit<NewEmail, "userId">> = {}
): schema.Email[] {
  const emails: schema.Email[] = [];

  for (let i = 0; i < count; i++) {
    const email = createTestEmail(db, userId, {
      ...baseOverrides,
      gmailThreadId: `thread_test_${userId}_${i}`,
      gmailMessageId: `msg_test_${userId}_${i}`,
      subject: `Test Email ${i + 1}`,
    });
    emails.push(email);
  }

  return emails;
}

/**
 * Clear all data from the database (useful for test cleanup)
 */
export function clearDatabase(db: BetterSQLite3Database<typeof schema>) {
  // Delete in order respecting foreign keys
  db.delete(schema.agentRuns).run();
  db.delete(schema.llmCalls).run();
  db.delete(schema.emailEvents).run();
  db.delete(schema.jobs).run();
  db.delete(schema.emails).run();
  db.delete(schema.syncState).run();
  db.delete(schema.userSettings).run();
  db.delete(schema.userLabels).run();
  db.delete(schema.users).run();
}

/**
 * Create a minimal test dataset (1 user, labels, 3 emails)
 */
export function createMinimalTestDataset(db: BetterSQLite3Database<typeof schema>) {
  const { user, labels } = createCompleteTestUser(db);
  const emails = createTestEmails(db, user.id, 3, {
    classification: "needs_response",
  });

  return { user, labels, emails };
}
