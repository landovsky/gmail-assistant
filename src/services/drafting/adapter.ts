import type { DraftGenerationInput, DraftResult } from '../../shared/types/api.js';
import { generateEmailDraft } from './engine.js';

/**
 * Adapter: Maps shared API contract to draft generation engine
 */
export async function generateDraft(input: DraftGenerationInput): Promise<DraftResult> {
  // Fetch thread messages
  const thread = await input.client.getThread(input.threadId);
  const messages = (thread.messages || []).map(msg => {
    // Parse message details
    const headers = msg.payload?.headers || [];
    const fromHeader = headers.find(h => h.name?.toLowerCase() === 'from');
    const dateHeader = headers.find(h => h.name?.toLowerCase() === 'date');

    return {
      from: fromHeader?.value || '',
      date: dateHeader?.value || '',
      body: extractPlainTextBody(msg),
    };
  });

  // Create gmailSearch function
  const gmailSearch = async (query: string) => {
    const results = await input.client.listMessages(query);
    return results.map(msg => ({
      id: msg.threadId || '',
      subject: extractSubject(msg),
      snippet: msg.snippet || '',
    }));
  };

  // Call existing generateEmailDraft
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
  // Fetch existing draft
  const draft = await input.client.getDraft(input.draftId);
  const draftBody = extractPlainTextBody(draft.message!);

  // Extract instruction from draft
  const parts = draftBody.split('✂️');
  const instruction = parts[0]?.trim() || '';

  // Regenerate draft
  const newDraft = await generateDraft({
    ...input,
    userInstructions: instruction,
  });

  return {
    ...newDraft,
    instruction,
  };
}

// Helper functions
function extractPlainTextBody(message: any): string {
  if (!message.payload) return '';
  if (message.payload.body?.data) {
    return Buffer.from(message.payload.body.data, 'base64url').toString('utf-8');
  }
  // Handle multipart
  return '';
}

function extractSubject(message: any): string {
  const headers = message.payload?.headers || [];
  const subjectHeader = headers.find((h: any) => h.name?.toLowerCase() === 'subject');
  return subjectHeader?.value || '';
}
