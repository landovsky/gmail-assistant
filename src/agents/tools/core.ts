/**
 * Core Agent Tools
 * Essential tools available to all agents
 */

import { z } from "zod";
import { toolRegistry, type ToolDefinition } from "./registry.js";
import { getDb } from "../../db/index.js";
import { emailEvents } from "../../db/schema.js";

/**
 * Send Reply Tool
 * Auto-sends email reply without human review
 */
const sendReplySchema = z.object({
  message: z.string().describe("The email message content to send"),
  threadId: z.string().describe("Gmail thread ID to reply to"),
});

const sendReplyDefinition: ToolDefinition = {
  type: "function",
  function: {
    name: "send_reply",
    description:
      "Send an email reply immediately without human review. Use only for straightforward queries with high confidence. For complex or sensitive issues, use create_draft instead.",
    parameters: {
      type: "object",
      properties: {
        message: {
          type: "string",
          description: "The email message content to send",
        },
        threadId: {
          type: "string",
          description: "Gmail thread ID to reply to",
        },
      },
      required: ["message", "threadId"],
    },
  },
};

async function sendReplyHandler({
  userId,
  args,
}: {
  userId: number;
  args: z.infer<typeof sendReplySchema>;
}): Promise<string> {
  const { message, threadId } = args;

  // TODO: Integrate with Gmail API to send reply
  // For now, this is stubbed
  console.log(`[send_reply] User ${userId}, Thread ${threadId}`);
  console.log(`Message: ${message}`);

  // Log event
  const db = getDb();
  await db.insert(emailEvents).values({
    userId,
    gmailThreadId: threadId,
    eventType: "sent_detected",
    detail: "Reply sent via agent auto-send",
  });

  return `Email reply sent successfully to thread ${threadId}`;
}

/**
 * Create Draft Tool
 * Creates draft for human review before sending
 */
const createDraftSchema = z.object({
  message: z.string().describe("The draft email message content"),
  threadId: z.string().describe("Gmail thread ID to reply to"),
});

const createDraftDefinition: ToolDefinition = {
  type: "function",
  function: {
    name: "create_draft",
    description:
      "Create a draft email reply for human review. Use this for complex queries, sensitive issues, or when uncertain about the appropriate response.",
    parameters: {
      type: "object",
      properties: {
        message: {
          type: "string",
          description: "The draft email message content",
        },
        threadId: {
          type: "string",
          description: "Gmail thread ID to reply to",
        },
      },
      required: ["message", "threadId"],
    },
  },
};

async function createDraftHandler({
  userId,
  args,
}: {
  userId: number;
  args: z.infer<typeof createDraftSchema>;
}): Promise<string> {
  const { message, threadId } = args;

  // TODO: Integrate with Gmail API to create draft
  console.log(`[create_draft] User ${userId}, Thread ${threadId}`);
  console.log(`Draft: ${message}`);

  // Log event
  const db = getDb();
  await db.insert(emailEvents).values({
    userId,
    gmailThreadId: threadId,
    eventType: "draft_created",
    detail: "Draft created via agent",
  });

  return `Draft created successfully for thread ${threadId}. Ready for human review.`;
}

/**
 * Escalate Tool
 * Flags message for human attention
 */
const escalateSchema = z.object({
  reason: z.string().describe("Reason for escalation"),
  threadId: z.string().describe("Gmail thread ID to escalate"),
});

const escalateDefinition: ToolDefinition = {
  type: "function",
  function: {
    name: "escalate",
    description:
      "Flag this message for urgent human attention. Use when the request is beyond your capabilities, requires medical/legal advice, or involves customer disputes.",
    parameters: {
      type: "object",
      properties: {
        reason: {
          type: "string",
          description: "Reason for escalation",
        },
        threadId: {
          type: "string",
          description: "Gmail thread ID to escalate",
        },
      },
      required: ["reason", "threadId"],
    },
  },
};

async function escalateHandler({
  userId,
  args,
}: {
  userId: number;
  args: z.infer<typeof escalateSchema>;
}): Promise<string> {
  const { reason, threadId } = args;

  // TODO: Apply "Action Required" label via Gmail API
  console.log(`[escalate] User ${userId}, Thread ${threadId}`);
  console.log(`Reason: ${reason}`);

  // Log event
  const db = getDb();
  await db.insert(emailEvents).values({
    userId,
    gmailThreadId: threadId,
    eventType: "archived",
    detail: `Escalated: ${reason}`,
  });

  return `Thread ${threadId} escalated for human attention. Reason: ${reason}`;
}

/**
 * Register all core tools
 */
export function registerCoreTools(): void {
  toolRegistry.register(sendReplyDefinition, sendReplySchema, sendReplyHandler);
  toolRegistry.register(
    createDraftDefinition,
    createDraftSchema,
    createDraftHandler
  );
  toolRegistry.register(escalateDefinition, escalateSchema, escalateHandler);
}
