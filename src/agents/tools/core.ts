/**
 * Core Agent Tools
 * Essential tools available to all agents
 */

import { z } from 'zod';
import { toolRegistry, type ToolDefinition, type ToolContext } from './registry.js';
import { getDb } from '../../db/index.js';
import { emailEvents, userLabels } from '../../db/schema.js';
import { GmailClient, getHeader } from '../../services/gmail/client.js';
import { eq, and } from 'drizzle-orm';

/**
 * Extract the GmailClient from tool context.
 * The agent_process job handler must provide the client in the context.
 */
function getGmailClient(context?: ToolContext): GmailClient {
  if (!context?.gmailClient) {
    throw new Error(
      'Gmail client not available in tool context. Ensure agent_process handler provides it.'
    );
  }
  return context.gmailClient as GmailClient;
}

/**
 * Fetch thread metadata needed for replying (to address, subject, message-id headers).
 */
async function getReplyMetadata(
  client: GmailClient,
  threadId: string
): Promise<{
  to: string;
  subject: string;
  inReplyTo?: string;
  references?: string;
}> {
  const thread = await client.getThread(threadId);
  const messages = thread.messages || [];

  if (messages.length === 0) {
    throw new Error(`Thread ${threadId} has no messages`);
  }

  // Reply to the most recent message in the thread
  const lastMessage = messages[messages.length - 1];

  const from = getHeader(lastMessage, 'From') || '';
  const subject = getHeader(lastMessage, 'Subject') || '';
  const messageId = getHeader(lastMessage, 'Message-ID');
  const existingRefs = getHeader(lastMessage, 'References');

  // Build references chain
  const references = existingRefs ? `${existingRefs} ${messageId || ''}` : messageId || undefined;

  // Extract the reply-to address: prefer Reply-To, then From
  const replyTo = getHeader(lastMessage, 'Reply-To') || from;

  return {
    to: replyTo,
    subject: subject.startsWith('Re:') ? subject : `Re: ${subject}`,
    inReplyTo: messageId,
    references: references?.trim(),
  };
}

// ---------------------------------------------------------------------------
// send_reply
// ---------------------------------------------------------------------------

const sendReplySchema = z.object({
  message: z.string().describe('The email message content to send'),
  threadId: z.string().describe('Gmail thread ID to reply to'),
});

const sendReplyDefinition: ToolDefinition = {
  type: 'function',
  function: {
    name: 'send_reply',
    description:
      'Send an email reply immediately without human review. Use only for straightforward queries with high confidence. For complex or sensitive issues, use create_draft instead.',
    parameters: {
      type: 'object',
      properties: {
        message: {
          type: 'string',
          description: 'The email message content to send',
        },
        threadId: {
          type: 'string',
          description: 'Gmail thread ID to reply to',
        },
      },
      required: ['message', 'threadId'],
    },
  },
};

async function sendReplyHandler({
  userId,
  args,
  context,
}: {
  userId: number;
  args: z.infer<typeof sendReplySchema>;
  context?: ToolContext;
}): Promise<string> {
  const { message, threadId } = args;
  const client = getGmailClient(context);

  // Fetch reply metadata from the thread
  const meta = await getReplyMetadata(client, threadId);

  // Send the reply via Gmail API
  const result = await client.sendReply(
    threadId,
    meta.to,
    meta.subject,
    message,
    meta.inReplyTo,
    meta.references
  );

  // Log event
  const db = getDb();
  await db.insert(emailEvents).values({
    userId,
    gmailThreadId: threadId,
    eventType: 'sent_detected',
    detail: `Reply sent via agent auto-send (messageId: ${result.messageId})`,
  });

  return `Email reply sent successfully to thread ${threadId} (messageId: ${result.messageId})`;
}

// ---------------------------------------------------------------------------
// create_draft
// ---------------------------------------------------------------------------

const createDraftSchema = z.object({
  message: z.string().describe('The draft email message content'),
  threadId: z.string().describe('Gmail thread ID to reply to'),
});

const createDraftDefinition: ToolDefinition = {
  type: 'function',
  function: {
    name: 'create_draft',
    description:
      'Create a draft email reply for human review. Use this for complex queries, sensitive issues, or when uncertain about the appropriate response.',
    parameters: {
      type: 'object',
      properties: {
        message: {
          type: 'string',
          description: 'The draft email message content',
        },
        threadId: {
          type: 'string',
          description: 'Gmail thread ID to reply to',
        },
      },
      required: ['message', 'threadId'],
    },
  },
};

async function createDraftHandler({
  userId,
  args,
  context,
}: {
  userId: number;
  args: z.infer<typeof createDraftSchema>;
  context?: ToolContext;
}): Promise<string> {
  const { message, threadId } = args;
  const client = getGmailClient(context);

  // Fetch reply metadata from the thread
  const meta = await getReplyMetadata(client, threadId);

  // Create draft via Gmail API
  const result = await client.createDraft(
    threadId,
    meta.to,
    meta.subject,
    message,
    meta.inReplyTo,
    meta.references
  );

  // Log event
  const db = getDb();
  await db.insert(emailEvents).values({
    userId,
    gmailThreadId: threadId,
    eventType: 'draft_created',
    detail: `Draft created via agent (draftId: ${result.draftId})`,
    draftId: result.draftId,
  });

  return `Draft created successfully for thread ${threadId} (draftId: ${result.draftId}). Ready for human review.`;
}

// ---------------------------------------------------------------------------
// escalate
// ---------------------------------------------------------------------------

const escalateSchema = z.object({
  reason: z.string().describe('Reason for escalation'),
  threadId: z.string().describe('Gmail thread ID to escalate'),
});

const escalateDefinition: ToolDefinition = {
  type: 'function',
  function: {
    name: 'escalate',
    description:
      'Flag this message for urgent human attention. Use when the request is beyond your capabilities, requires medical/legal advice, or involves customer disputes.',
    parameters: {
      type: 'object',
      properties: {
        reason: {
          type: 'string',
          description: 'Reason for escalation',
        },
        threadId: {
          type: 'string',
          description: 'Gmail thread ID to escalate',
        },
      },
      required: ['reason', 'threadId'],
    },
  },
};

async function escalateHandler({
  userId,
  args,
  context,
}: {
  userId: number;
  args: z.infer<typeof escalateSchema>;
  context?: ToolContext;
}): Promise<string> {
  const { reason, threadId } = args;
  const client = getGmailClient(context);

  // Look up the "action_required" label for this user
  const db = getDb();
  const label = await db.query.userLabels.findFirst({
    where: and(eq(userLabels.userId, userId), eq(userLabels.labelKey, 'action_required')),
  });

  if (label) {
    // Apply the "Action Required" label to the thread
    await client.modifyThreadLabels(threadId, {
      addLabelIds: [label.gmailLabelId],
    });
  }

  // Log event
  await db.insert(emailEvents).values({
    userId,
    gmailThreadId: threadId,
    eventType: 'archived',
    detail: `Escalated: ${reason}`,
    labelId: label?.gmailLabelId,
  });

  return `Thread ${threadId} escalated for human attention. Reason: ${reason}`;
}

/**
 * Register all core tools
 */
export function registerCoreTools(): void {
  toolRegistry.register(sendReplyDefinition, sendReplySchema, sendReplyHandler);
  toolRegistry.register(createDraftDefinition, createDraftSchema, createDraftHandler);
  toolRegistry.register(escalateDefinition, escalateSchema, escalateHandler);
}
