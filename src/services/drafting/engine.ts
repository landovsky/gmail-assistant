// Draft generation engine
import { generateDraft } from '../llm/service';
import type { DraftInput } from '../llm/types';
import { gatherRelatedContext } from './context-gatherer';
import type { GmailThread, ContextGatherInput } from './context-gatherer';

export interface DraftGenerationInput {
  threadId: string;
  subject: string;
  messages: Array<{
    from: string;
    date: string;
    body: string;
  }>;
  senderEmail: string;
  style: 'formal' | 'business' | 'informal';
  language: string;
  signOffName?: string;
  userInstructions?: string; // For rework
  gmailSearch: (query: string) => Promise<GmailThread[]>;
  userId?: number;
}

export interface DraftResult {
  draftText: string;
  draftWithMarker: string;
  relatedContext: string[];
}

const SCISSORS_MARKER = '\n\n---\n✂️\n';

/**
 * Generate email draft with context gathering
 */
export async function generateEmailDraft(
  input: DraftGenerationInput
): Promise<DraftResult> {
  // Gather related context from mailbox
  const contextResult = await gatherRelatedContext({
    email: {
      senderEmail: input.senderEmail,
      subject: input.subject,
      body: input.messages[input.messages.length - 1]?.body || '',
    },
    gmailSearch: input.gmailSearch,
    userId: input.userId,
  });

  // Build draft input for LLM
  const draftInput: DraftInput = {
    thread: {
      threadId: input.threadId,
      subject: input.subject,
      messages: input.messages,
    },
    style: input.style,
    language: input.language,
    relatedContext: contextResult.formattedContext,
    userInstructions: input.userInstructions,
    signOffName: input.signOffName,
  };

  // Generate draft using LLM
  const draftText = await generateDraft({ input: draftInput });

  // Add scissors marker for rework instructions
  const draftWithMarker = draftText + SCISSORS_MARKER;

  return {
    draftText,
    draftWithMarker,
    relatedContext: contextResult.formattedContext,
  };
}

/**
 * Extract rework instruction from draft with scissors marker
 */
export function extractReworkInstruction(draftContent: string): string | null {
  const parts = draftContent.split('✂️');
  if (parts.length < 2) return null;

  const instruction = parts[0].trim();
  return instruction || null;
}

/**
 * Check if rework limit reached (max 3 iterations)
 */
export function isReworkLimitReached(reworkCount: number): boolean {
  return reworkCount >= 3;
}

/**
 * MIME encode draft for Gmail API
 * Creates proper email format with headers
 */
export function mimeEncodeDraft(params: {
  to: string;
  from: string;
  subject: string;
  body: string;
  threadId?: string;
  messageId?: string;
}): string {
  const lines: string[] = [];

  lines.push(`To: ${params.to}`);
  lines.push(`From: ${params.from}`);
  lines.push(`Subject: Re: ${params.subject}`);

  // Threading headers for proper Gmail conversation threading
  if (params.messageId) {
    lines.push(`In-Reply-To: ${params.messageId}`);
    lines.push(`References: ${params.messageId}`);
  }

  lines.push('Content-Type: text/plain; charset=UTF-8');
  lines.push('');
  lines.push(params.body);

  const mimeMessage = lines.join('\r\n');

  // Base64 encode for Gmail API
  return Buffer.from(mimeMessage)
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}
