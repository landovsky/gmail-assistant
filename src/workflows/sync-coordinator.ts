/**
 * Gmail Sync Coordinator
 * Coordinates sync operations with classification and drafting workflows
 */

import { db } from "../db/index.js";
import { emails, jobs, syncState } from "../db/schema.js";
import { eq, and, inArray } from "drizzle-orm";
import { GmailClient } from "../services/gmail/client.js";
import { syncMessages } from "../services/gmail/sync.js";
import { classifyEmailTwoTier as classifyEmail } from "../services/classification/engine.js";
import { handleClassificationComplete } from "./email-lifecycle.js";
import type { JobQueue } from "../jobs/queue/interface.js";

export interface SyncResult {
  messagesProcessed: number;
  draftsCreated: number;
  labelsChanged: number;
  errors: string[];
}

/**
 * Full sync: fetch new messages, classify, and trigger draft generation
 */
export async function performFullSync(params: {
  userId: number;
  client: GmailClient;
  queue: JobQueue;
  labelMappings: Array<{ key: string; name: string; gmailLabelId: string }>;
}): Promise<SyncResult> {
  const result: SyncResult = {
    messagesProcessed: 0,
    draftsCreated: 0,
    labelsChanged: 0,
    errors: [],
  };

  try {
    // Get last sync history ID
    const state = await db.query.syncState.findFirst({
      where: eq(syncState.userId, params.userId),
    });

    const lastHistoryId = state?.lastHistoryId;

    // Fetch new messages via Gmail sync
    const syncResult = await syncMessages({
      userId: params.userId,
      client: params.client,
      lastHistoryId: lastHistoryId || undefined,
    });

    result.messagesProcessed = syncResult.newMessages.length;

    // Update sync state with new history ID
    if (syncResult.newHistoryId) {
      await db
        .update(syncState)
        .set({
          lastHistoryId: syncResult.newHistoryId,
          lastSyncAt: new Date().toISOString(),
        })
        .where(eq(syncState.userId, params.userId));
    }

    // Process each new message: classify and create email record
    for (const message of syncResult.newMessages) {
      try {
        // Classify the email
        const classification = await classifyEmail({
          userId: params.userId,
          threadId: message.threadId,
          subject: message.subject,
          from: message.from,
          body: message.body,
          headers: message.headers,
          labelMappings: params.labelMappings,
          client: params.client,
        });

        // Create email record
        const [email] = await db
          .insert(emails)
          .values({
            userId: params.userId,
            gmailThreadId: message.threadId,
            gmailMessageId: message.messageId,
            subject: message.subject,
            from: message.from,
            classification: classification.category,
            status: classification.category === "needs_response" ? "pending" : "skipped",
            classificationLabel: classification.labelId,
            communicationStyle: classification.communicationStyle,
            language: classification.language,
            messageCount: 1,
          })
          .returning();

        // Handle classification complete (applies labels, logs event)
        await handleClassificationComplete({
          userId: params.userId,
          threadId: message.threadId,
          classification: classification.category,
          labelId: classification.labelId,
          emailId: email.id,
        });

        // If needs response, enqueue draft job
        if (classification.category === "needs_response") {
          await params.queue.enqueue({
            type: "draft",
            userId: params.userId,
            payload: {
              threadId: message.threadId,
              emailId: email.id,
            },
          });

          result.draftsCreated++;
        }

        result.labelsChanged++;
      } catch (error: unknown) {
        const err = error as Error;
        result.errors.push(
          `Failed to process message ${message.messageId}: ${err.message}`
        );
      }
    }

    // Process Gmail History events (labels changed, drafts deleted, etc.)
    for (const event of syncResult.historyEvents) {
      try {
        if (event.type === "labelsAdded") {
          await handleLabelAdded({
            userId: params.userId,
            threadId: event.threadId,
            labelIds: event.labelIds || [],
            queue: params.queue,
            labelMappings: params.labelMappings,
          });
        } else if (event.type === "labelsRemoved") {
          await handleLabelRemoved({
            userId: params.userId,
            threadId: event.threadId,
            labelIds: event.labelIds || [],
          });
        } else if (event.type === "messagesDeleted") {
          await handleMessageDeleted({
            userId: params.userId,
            messageIds: event.messageIds || [],
            queue: params.queue,
          });
        }
      } catch (error: unknown) {
        const err = error as Error;
        result.errors.push(`Failed to process history event: ${err.message}`);
      }
    }

    return result;
  } catch (error: unknown) {
    const err = error as Error;
    result.errors.push(`Full sync failed: ${err.message}`);
    return result;
  }
}

/**
 * Handle label added events from Gmail History API
 */
async function handleLabelAdded(params: {
  userId: number;
  threadId: string;
  labelIds: string[];
  queue: JobQueue;
  labelMappings: Array<{ key: string; gmailLabelId: string }>;
}): Promise<void> {
  const reworkLabelId = params.labelMappings.find((l) => l.key === "rework")
    ?.gmailLabelId;
  const doneLabelId = params.labelMappings.find((l) => l.key === "done")
    ?.gmailLabelId;

  // Check if Rework label was added
  if (reworkLabelId && params.labelIds.includes(reworkLabelId)) {
    // Enqueue rework job
    const email = await db.query.emails.findFirst({
      where: and(
        eq(emails.userId, params.userId),
        eq(emails.gmailThreadId, params.threadId)
      ),
    });

    if (email) {
      await params.queue.enqueue({
        type: "rework",
        userId: params.userId,
        payload: {
          threadId: params.threadId,
          emailId: email.id,
        },
      });
    }
  }

  // Check if Done label was added
  if (doneLabelId && params.labelIds.includes(doneLabelId)) {
    // Enqueue cleanup job
    const email = await db.query.emails.findFirst({
      where: and(
        eq(emails.userId, params.userId),
        eq(emails.gmailThreadId, params.threadId)
      ),
    });

    if (email) {
      await params.queue.enqueue({
        type: "cleanup",
        userId: params.userId,
        payload: {
          threadId: params.threadId,
          emailId: email.id,
        },
      });
    }
  }
}

/**
 * Handle label removed events from Gmail History API
 */
async function handleLabelRemoved(params: {
  userId: number;
  threadId: string;
  labelIds: string[];
}): Promise<void> {
  // Currently no specific actions needed
  // Could track label removal events for audit purposes
}

/**
 * Handle message deleted events from Gmail History API
 */
async function handleMessageDeleted(params: {
  userId: number;
  messageIds: string[];
  queue: JobQueue;
}): Promise<void> {
  // Find emails with drafts matching deleted message IDs
  const emailsWithDeletedDrafts = await db.query.emails.findMany({
    where: and(
      eq(emails.userId, params.userId),
      inArray(emails.draftId, params.messageIds)
    ),
  });

  // For each deleted draft, enqueue sent detection job
  for (const email of emailsWithDeletedDrafts) {
    await params.queue.enqueue({
      type: "sync",
      userId: params.userId,
      payload: {
        action: "detect_sent",
        threadId: email.gmailThreadId,
        emailId: email.id,
      },
    });
  }
}

/**
 * Incremental sync: process only history changes since last sync
 */
export async function performIncrementalSync(params: {
  userId: number;
  client: GmailClient;
  queue: JobQueue;
  labelMappings: Array<{ key: string; name: string; gmailLabelId: string }>;
}): Promise<SyncResult> {
  // Get last sync state
  const state = await db.query.syncState.findFirst({
    where: eq(syncState.userId, params.userId),
  });

  if (!state?.lastHistoryId) {
    // No previous sync, fall back to full sync
    return performFullSync(params);
  }

  const result: SyncResult = {
    messagesProcessed: 0,
    draftsCreated: 0,
    labelsChanged: 0,
    errors: [],
  };

  try {
    // Fetch only history changes
    const syncResult = await syncMessages({
      userId: params.userId,
      client: params.client,
      lastHistoryId: state.lastHistoryId,
    });

    result.messagesProcessed = syncResult.newMessages.length;

    // Update sync state
    if (syncResult.newHistoryId) {
      await db
        .update(syncState)
        .set({
          lastHistoryId: syncResult.newHistoryId,
          lastSyncAt: new Date().toISOString(),
        })
        .where(eq(syncState.userId, params.userId));
    }

    // Process new messages (same as full sync)
    for (const message of syncResult.newMessages) {
      try {
        const classification = await classifyEmail({
          userId: params.userId,
          threadId: message.threadId,
          subject: message.subject,
          from: message.from,
          body: message.body,
          headers: message.headers,
          labelMappings: params.labelMappings,
          client: params.client,
        });

        const [email] = await db
          .insert(emails)
          .values({
            userId: params.userId,
            gmailThreadId: message.threadId,
            gmailMessageId: message.messageId,
            subject: message.subject,
            from: message.from,
            classification: classification.category,
            status: classification.category === "needs_response" ? "pending" : "skipped",
            classificationLabel: classification.labelId,
            communicationStyle: classification.communicationStyle,
            language: classification.language,
            messageCount: 1,
          })
          .returning();

        await handleClassificationComplete({
          userId: params.userId,
          threadId: message.threadId,
          classification: classification.category,
          labelId: classification.labelId,
          emailId: email.id,
        });

        if (classification.category === "needs_response") {
          await params.queue.enqueue({
            type: "draft",
            userId: params.userId,
            payload: {
              threadId: message.threadId,
              emailId: email.id,
            },
          });

          result.draftsCreated++;
        }

        result.labelsChanged++;
      } catch (error: unknown) {
        const err = error as Error;
        result.errors.push(
          `Failed to process message ${message.messageId}: ${err.message}`
        );
      }
    }

    // Process history events
    for (const event of syncResult.historyEvents) {
      try {
        if (event.type === "labelsAdded") {
          await handleLabelAdded({
            userId: params.userId,
            threadId: event.threadId,
            labelIds: event.labelIds || [],
            queue: params.queue,
            labelMappings: params.labelMappings,
          });
        } else if (event.type === "messagesDeleted") {
          await handleMessageDeleted({
            userId: params.userId,
            messageIds: event.messageIds || [],
            queue: params.queue,
          });
        }
      } catch (error: unknown) {
        const err = error as Error;
        result.errors.push(`Failed to process history event: ${err.message}`);
      }
    }

    return result;
  } catch (error: unknown) {
    const err = error as Error;
    result.errors.push(`Incremental sync failed: ${err.message}`);
    return result;
  }
}
