import type { DraftInput } from '../types';

const STYLES = {
  formal: { tone: 'Very polite, formal business language' },
  business: { tone: 'Professional but approachable' },
  informal: { tone: 'Casual, friendly' },
};

export function buildDraftPrompt(input: DraftInput): { system: string; prompt: string } {
  const system = `Draft email response. Style: ${input.style} (${STYLES[input.style].tone}). Language: ${input.language}. Be helpful, direct, professional.`;
  let prompt = `Thread: ${input.thread.subject}\n\n`;
  prompt += input.thread.messages.map(m => `${m.from} (${m.date}):\n${m.body}`).join('\n\n---\n\n');
  if (input.relatedContext) prompt += `\n\nContext:\n${input.relatedContext.join('\n')}`;
  if (input.userInstructions) prompt += `\n\nFeedback: ${input.userInstructions}`;
  prompt += `\n\nDraft response:`;
  return { system, prompt };
}
