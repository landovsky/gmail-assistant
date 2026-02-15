// LLM service types and schemas
import { z } from 'zod';

export const ClassificationOutputSchema = z.object({
  classification: z.enum(['needs_response', 'action_required', 'payment_request', 'fyi', 'waiting']),
  confidence: z.enum(['high', 'medium', 'low']).default('medium'),
  reasoning: z.string(),
  detected_language: z.string().default('cs'),
  style: z.enum(['formal', 'business', 'informal']).default('business'),
  vendor_name: z.string().optional(),
});

export type ClassificationOutput = z.infer<typeof ClassificationOutputSchema>;

export const ContextQueryOutputSchema = z.object({
  queries: z.array(z.string()).max(3),
});

export type ContextQueryOutput = z.infer<typeof ContextQueryOutputSchema>;

export type LLMCallType = 'classify' | 'draft' | 'rework' | 'context' | 'agent';

export interface EmailMetadata {
  senderEmail: string;
  senderName?: string;
  subject?: string;
  body: string;
  threadMessages?: Array<{ from: string; date: string; body: string }>;
}

export interface DraftInput {
  thread: {
    threadId: string;
    subject: string;
    messages: Array<{ from: string; date: string; body: string }>;
  };
  style: 'formal' | 'business' | 'informal';
  language: string;
  relatedContext?: string[];
  userInstructions?: string;
  signOffName?: string;
}
