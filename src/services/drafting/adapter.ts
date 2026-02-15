/**
 * Drafting adapter - maps shared API to existing implementation
 */

import type { DraftGenerationInput, DraftResult } from '../../shared/types/api.js';
import { generateEmailDraft } from './engine.js';
import { extractPlainTextBody } from '../gmail/message-parser.js';

export async function generateDraft(input: DraftGenerationInput): Promise<DraftResult> {
  const thread = await input.client.getThread(input.threadId);
  const messages = (thread.messages || []).map(msg => {
    const headers = msg.payload?.headers || [];
    const fromHeader = headers.find(h => h.name?.toLowerCase() === 'from');
    const dateHeader = headers.find(h => h.name?.toLowerCase() === 'date');

    return {
      from: fromHeader?.value || '',
      date: dateHeader?.value || '',
      body: extractPlainTextBody(msg),
    };
  });

  const gmailSearch = async (query: string) => {
    const results = await input.client.listMessages(query);
    return results.map(msg => ({
      threadId: msg.threadId || '',
      subject: getSubject(msg),
      snippet: msg.snippet || '',
    }));
  };

  const result = await generateEmailDraft({
    threadId: input.threadId,
    subject: input.subject,
    messages,
    senderEmail: input.from,
    style: input.communicationStyle,
    language: input.language,
    signOffName: input.signOffName,
    userInstructions: input.userInstructions,
    gmailSearch,
    userId: input.userId,
  });

  return {
    body: result.draftWithMarker,
    plainBody: result.draftText,
    relatedContext: result.relatedContext,
  };
}

export async function regenerateDraft(
  input: DraftGenerationInput & { draftId: string }
): Promise<DraftResult & { instruction: string }> {
  const draft = await input.client.getDraft(input.draftId);
  const draftBody = extractPlainTextBody(draft.message!);
  const parts = draftBody.split('✂️');
  const instruction = parts[0]?.trim() || '';

  const newDraft = await generateDraft({
    ...input,
    userInstructions: instruction,
  });

  return { ...newDraft, instruction };
}

function getSubject(message: any): string {
  const headers = message.payload?.headers || [];
  const h = headers.find((h: any) => h.name?.toLowerCase() === 'subject');
  return h?.value || '';
}
