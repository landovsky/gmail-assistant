import type { EmailMetadata } from '../types';

export function buildClassificationPrompt(email: EmailMetadata): { system: string; prompt: string } {
  const system = `You are an email classifier. Categorize emails into: needs_response, action_required, payment_request, fyi, or waiting.
Return JSON: {"classification":"...", "confidence":"high|medium|low", "reasoning":"...", "detected_language":"cs|en|de", "style":"formal|business|informal", "vendor_name":"..."}`;
  
  let ctx = `From: ${email.senderEmail}${email.senderName ? ` (${email.senderName})` : ''}\nSubject: ${email.subject || '(no subject)'}\n\n${email.body}`;
  if (email.threadMessages?.length) {
    ctx += '\n\n--- Thread ---\n' + email.threadMessages.map(m => `${m.from} (${m.date}): ${m.body}`).join('\n');
  }
  return { system, prompt: `Classify:\n\n${ctx}` };
}
