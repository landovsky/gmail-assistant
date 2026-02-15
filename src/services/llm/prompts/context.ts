// Context query generation prompt builder
import type { EmailMetadata } from '../types';

export function buildContextQueryPrompt(email: EmailMetadata): {
  system: string;
  prompt: string;
} {
  const system = `You are a Gmail search query generator.

Your task is to create Gmail search queries that find related email threads to provide context for drafting a response.

**Gmail Search Syntax:**
- from:email@example.com - Find emails from sender
- to:email@example.com - Find emails to recipient
- subject:keyword - Find emails with keyword in subject
- has:attachment - Find emails with attachments
- newer_than:7d - Find recent emails
- older_than:30d - Find older emails
- is:unread - Find unread emails
- label:labelname - Find labeled emails

**Query Guidelines:**
- Generate up to 3 targeted, specific queries
- Focus on finding genuinely relevant context (previous conversations, related topics)
- Use sender email to find past interactions
- Use subject keywords to find related discussions
- Prioritize recent emails (newer_than:7d or newer_than:30d)
- Avoid too-broad queries that return noise

**Output Format:**
Return valid JSON with array of query strings:
{
  "queries": [
    "from:sender@example.com subject:project",
    "subject:budget approval newer_than:30d",
    "from:sender@example.com newer_than:7d"
  ]
}

Maximum 3 queries. Be specific and relevant.`;

  const prompt = `Generate Gmail search queries to find context for this email:

From: ${email.senderEmail}${email.senderName ? ` (${email.senderName})` : ''}
Subject: ${email.subject || '(no subject)'}

Message:
${email.body.substring(0, 500)}${email.body.length > 500 ? '...' : ''}`;

  return { system, prompt };
}
