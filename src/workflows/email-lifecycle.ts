/**
 * Email Lifecycle State Machine
 * Orchestrates email state transitions from classification → draft → sent → archived
 */

import { db } from "../db/index.js";
import { emails, emailEvents } from "../db/schema.js";
import { eq, and } from "drizzle-orm";
import { GmailClient } from "../services/gmail/client.js";

export type EmailStatus =
  | "pending"
  | "drafted"
  | "rework_requested"
  | "sent"
  | "skipped"
  | "archived";

export type Classification =
  | "needs_response"
  | "action_required"
  | "payment_request"
  | "fyi"
  | "waiting";

export interface StateTransitionResult {
  success: boolean;
  newStatus: EmailStatus;
  error?: string;
}

type EventType =
  | "classified"
  | "label_added"
  | "label_removed"
  | "draft_created"
  | "draft_trashed"
  | "draft_reworked"
  | "sent_detected"
  | "archived"
  | "rework_limit_reached"
  | "waiting_retriaged"
  | "error";

/**
 * Log state transition event
 */
async function logEvent(params: {
  userId: number;
  threadId: string;
  eventType: EventType;
  detail?: string;
  labelId?: string;
  draftId?: string;
}): Promise<void> {
  await db.insert(emailEvents).values({
    userId: params.userId,
    gmailThreadId: params.threadId,
    eventType: params.eventType,
    detail: params.detail,
    labelId: params.labelId,
    draftId: params.draftId,
  });
}

/**
 * Classification → pending or skipped
 * Called after email is classified
 */
export async function handleClassificationComplete(params: {
  userId: number;
  threadId: string;
  classification: Classification;
  labelId: string;
  emailId?: number;
}): Promise<StateTransitionResult> {
  const status: EmailStatus =
    params.classification === "needs_response" ? "pending" : "skipped";

  // Create or update email record
  const existing = await db.query.emails.findFirst({
    where: and(
      eq(emails.userId, params.userId),
      eq(emails.gmailThreadId, params.threadId)
    ),
  });

  let emailId = params.emailId || existing?.id;

  if (!emailId) {
    // Should not happen - email record should be created during classification
    throw new Error(`Email record not found for thread ${params.threadId}`);
  }

  // Update status
  await db
    .update(emails)
    .set({ status })
    .where(eq(emails.id, emailId));

  // Log event
  await logEvent({
    userId: params.userId,
    threadId: params.threadId,
    eventType: "classified",
    detail: `Classified as ${params.classification}`,
    labelId: params.labelId,
  });

  return { success: true, newStatus: status };
}

/**
 * pending → drafted
 * Called after draft job successfully creates Gmail draft
 */
export async function handleDraftCreated(params: {
  userId: number;
  threadId: string;
  draftId: string;
  client: GmailClient;
  labelMappings: Array<{ key: string; gmailLabelId: string }>;
}): Promise<StateTransitionResult> {
  const email = await db.query.emails.findFirst({
    where: and(
      eq(emails.userId, params.userId),
      eq(emails.gmailThreadId, params.threadId)
    ),
  });

  if (!email) {
    return {
      success: false,
      newStatus: "pending",
      error: "Email record not found",
    };
  }

  // Update email status
  await db
    .update(emails)
    .set({
      status: "drafted",
      draftId: params.draftId,
      draftedAt: new Date().toISOString(),
    })
    .where(eq(emails.id, email.id));

  // Update Gmail labels: add Outbox
  const outboxLabelId = params.labelMappings.find((l) => l.key === "outbox")
    ?.gmailLabelId;
  if (outboxLabelId) {
    await params.client.modifyThreadLabels(params.threadId, {
      addLabelIds: [outboxLabelId],
    });
  }

  // Log event
  await logEvent({
    userId: params.userId,
    threadId: params.threadId,
    eventType: "draft_created",
    draftId: params.draftId,
  });

  return { success: true, newStatus: "drafted" };
}

/**
 * drafted → rework_requested → drafted
 * Called when user applies Rework label
 */
export async function handleReworkRequested(params: {
  userId: number;
  threadId: string;
}): Promise<StateTransitionResult> {
  const email = await db.query.emails.findFirst({
    where: and(
      eq(emails.userId, params.userId),
      eq(emails.gmailThreadId, params.threadId)
    ),
  });

  if (!email) {
    return {
      success: false,
      newStatus: "drafted",
      error: "Email record not found",
    };
  }

  // Check rework limit
  const currentReworkCount = email.reworkCount || 0;
  if (currentReworkCount >= 3) {
    // Move to skipped with action required
    await db
      .update(emails)
      .set({ status: "skipped", reworkCount: currentReworkCount + 1 })
      .where(eq(emails.id, email.id));

    await logEvent({
      userId: params.userId,
      threadId: params.threadId,
      eventType: "rework_limit_reached",
      detail: `Rework limit reached (${currentReworkCount + 1} attempts)`,
    });

    return { success: true, newStatus: "skipped" };
  }

  // Increment rework count
  await db
    .update(emails)
    .set({ reworkCount: currentReworkCount + 1 })
    .where(eq(emails.id, email.id));

  // Log event (actual rework happens in job handler)
  await logEvent({
    userId: params.userId,
    threadId: params.threadId,
    eventType: "draft_reworked",
    detail: `Rework requested (attempt ${currentReworkCount + 1})`,
  });

  return { success: true, newStatus: "drafted" };
}

/**
 * drafted → sent
 * Called when draft deletion is detected (user likely sent the email)
 */
export async function handleSentDetected(params: {
  userId: number;
  threadId: string;
  client: GmailClient;
  labelMappings: Array<{ key: string; gmailLabelId: string }>;
}): Promise<StateTransitionResult> {
  const email = await db.query.emails.findFirst({
    where: and(
      eq(emails.userId, params.userId),
      eq(emails.gmailThreadId, params.threadId)
    ),
  });

  if (!email || !email.draftId) {
    return {
      success: false,
      newStatus: "drafted",
      error: "Email record or draft ID not found",
    };
  }

  // Verify draft no longer exists
  try {
    await params.client.getDraft(email.draftId);
    // Draft still exists, false alarm
    return { success: false, newStatus: "drafted", error: "Draft still exists" };
  } catch (error: unknown) {
    // Draft not found = likely sent
    // Update status
    await db
      .update(emails)
      .set({
        status: "sent",
        actedAt: new Date().toISOString(),
      })
      .where(eq(emails.id, email.id));

    // Remove Outbox label
    const outboxLabelId = params.labelMappings.find((l) => l.key === "outbox")
      ?.gmailLabelId;
    if (outboxLabelId) {
      await params.client.modifyThreadLabels(params.threadId, {
        removeLabelIds: [outboxLabelId],
      });
    }

    // Log event
    await logEvent({
      userId: params.userId,
      threadId: params.threadId,
      eventType: "sent_detected",
      draftId: email.draftId,
    });

    return { success: true, newStatus: "sent" };
  }
}

/**
 * * → archived
 * Called when user applies Done label
 */
export async function handleDoneRequested(params: {
  userId: number;
  threadId: string;
  client: GmailClient;
  labelMappings: Array<{ key: string; gmailLabelId: string }>;
}): Promise<StateTransitionResult> {
  const email = await db.query.emails.findFirst({
    where: and(
      eq(emails.userId, params.userId),
      eq(emails.gmailThreadId, params.threadId)
    ),
  });

  if (!email) {
    return {
      success: false,
      newStatus: "pending",
      error: "Email record not found",
    };
  }

  // Update status to archived
  await db
    .update(emails)
    .set({
      status: "archived",
      actedAt: new Date().toISOString(),
    })
    .where(eq(emails.id, email.id));

  // Remove all AI labels and INBOX label
  const allAiLabelIds = params.labelMappings.map((l) => l.gmailLabelId);
  await params.client.modifyThreadLabels(params.threadId, {
    removeLabelIds: [...allAiLabelIds, "INBOX"],
  });

  // Log event
  await logEvent({
    userId: params.userId,
    threadId: params.threadId,
    eventType: "archived",
  });

  return { success: true, newStatus: "archived" };
}

/**
 * waiting → reclassified
 * Called when new message arrives on waiting thread
 */
export async function handleWaitingRetriage(params: {
  userId: number;
  threadId: string;
  newMessageCount: number;
}): Promise<StateTransitionResult> {
  const email = await db.query.emails.findFirst({
    where: and(
      eq(emails.userId, params.userId),
      eq(emails.gmailThreadId, params.threadId)
    ),
  });

  if (!email) {
    return {
      success: false,
      newStatus: "pending",
      error: "Email record not found",
    };
  }

  // Check if message count actually increased
  if (params.newMessageCount <= (email.messageCount || 0)) {
    return {
      success: false,
      newStatus: email.status as EmailStatus,
      error: "Message count did not increase",
    };
  }

  // Update message count
  await db
    .update(emails)
    .set({ messageCount: params.newMessageCount })
    .where(eq(emails.id, email.id));

  // Log event (reclassification happens in job handler)
  await logEvent({
    userId: params.userId,
    threadId: params.threadId,
    eventType: "waiting_retriaged",
    detail: `New message arrived (count: ${params.newMessageCount})`,
  });

  return { success: true, newStatus: "pending" };
}
