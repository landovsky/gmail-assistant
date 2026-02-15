import type { EmailMetadata } from '../types';

export function buildContextQueryPrompt(email: EmailMetadata): { system: string; prompt: string } {
  const system = `Generate up to 3 Gmail search queries to find related context. Return JSON: {"queries":["query1","query2","query3"]}`;
  const prompt = `Email from ${email.senderEmail}, subject: ${email.subject || 'none'}\n${email.body.substring(0, 500)}`;
  return { system, prompt };
}
