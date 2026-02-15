// Draft generation prompt builder
import type { DraftInput } from '../types';

const STYLE_TEMPLATES = {
  formal: {
    greeting: 'Vážený/á {name} / Dear {name}',
    signOff: 'S pozdravem / Kind regards',
    tone: 'Very polite, structured, traditional business language. Use complete sentences and proper formal grammar.',
  },
  business: {
    greeting: 'Dobrý den / Hello',
    signOff: 'S pozdravem / Best regards',
    tone: 'Professional but approachable. Clear and concise. Balance formality with friendliness.',
  },
  informal: {
    greeting: 'Ahoj / Hi',
    signOff: 'Díky / Thanks',
    tone: 'Casual, friendly, relaxed tone. Conversational style with personal connection.',
  },
};

export function buildDraftPrompt(input: DraftInput): {
  system: string;
  prompt: string;
} {
  const styleTemplate = STYLE_TEMPLATES[input.style];

  const system = `You are an email assistant helping draft responses to emails.

**Your Role:**
- Draft helpful, professional email responses
- Match the sender's communication style and language
- Be direct and address the sender's questions/requests
- Include relevant details from context
- Never make promises without data

**Communication Style: ${input.style}**
${styleTemplate.tone}

**Greeting Pattern:** ${styleTemplate.greeting}
**Sign-off Pattern:** ${styleTemplate.signOff}

**Language:** ${input.language}
Write the ENTIRE response in ${input.language === 'cs' ? 'Czech' : input.language === 'en' ? 'English' : input.language}.

**Content Guidelines:**
- Directly address the sender's questions or requests
- Be helpful and informative
- Include relevant details from related context if available
- Use clear, logical structure
- Keep proportional to the sender's email length
- Avoid unnecessary verbosity
- Grammar and spelling must be accurate
- Use culturally appropriate phrasing

**Structure:**
1. Appropriate greeting
2. Direct response to main points
3. Additional relevant information if needed
4. Clear sign-off
${input.signOffName ? `5. Name: ${input.signOffName}` : ''}

Write only the email body. Do not include subject line or metadata.`;

  // Build thread context
  let threadContext = `**Email Thread:**\n\nSubject: ${input.thread.subject}\n\n`;
  for (const msg of input.thread.messages) {
    threadContext += `From: ${msg.from} (${msg.date})\n${msg.body}\n\n---\n\n`;
  }

  // Build related context if available
  let relatedContext = '';
  if (input.relatedContext && input.relatedContext.length > 0) {
    relatedContext = `\n**Related Context from Mailbox:**\n\n`;
    for (const context of input.relatedContext) {
      relatedContext += `${context}\n\n---\n\n`;
    }
  }

  // Build user instructions for rework
  let userInstructions = '';
  if (input.userInstructions) {
    userInstructions = `\n**User Feedback (revise draft based on this):**\n${input.userInstructions}\n\n`;
  }

  const prompt = `${threadContext}${relatedContext}${userInstructions}Draft a response in ${input.language} using ${input.style} style:`;

  return { system, prompt };
}
