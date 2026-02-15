// LLM service types and schemas
import { z } from 'zod';

// Classification output schema
export const ClassificationOutputSchema = z.object({
  classification: z.enum([
    'needs_response',
    'action_required',
    'payment_request',
    'fyi',
    'waiting',
  ]),
  confidence: z.enum(['high', 'medium', 'low']).default('medium'),
  reasoning: z.string(),
  detected_language: z.string().default('cs'),
  style: z.enum(['formal', 'business', 'informal']).default('business'),
  vendor_name: z.string().optional(),
});

export type ClassificationOutput = z.infer<typeof ClassificationOutputSchema>;

// Context query output schema
export const ContextQueryOutputSchema = z.object({
  queries: z.array(z.string()).max(3),
});

export type ContextQueryOutput = z.infer<typeof ContextQueryOutputSchema>;

// LLM call types
export type LLMCallType = 'classify' | 'draft' | 'rework' | 'context' | 'agent';

// LLM call metadata for logging
export interface LLMCallMetadata {
  userId?: number;
  threadId?: string;
  callType: LLMCallType;
  model: string;
  systemPrompt?: string;
  userMessage?: string;
  response?: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  latencyMs: number;
  error?: string;
}

// Email metadata for classification
export interface EmailMetadata {
  senderEmail: string;
  senderName?: string;
  subject?: string;
  body: string;
  threadMessages?: Array<{
    from: string;
    date: string;
    body: string;
  }>;
}

// Draft generation input
export interface DraftInput {
  thread: {
    threadId: string;
    subject: string;
    messages: Array<{
      from: string;
      date: string;
      body: string;
    }>;
  };
  style: 'formal' | 'business' | 'informal';
  language: string;
  relatedContext?: string[];
  userInstructions?: string; // For rework
  signOffName?: string;
}

// Agent tool definition (OpenAI function format)
export interface AgentTool {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: {
      type: 'object';
      properties: Record<string, any>;
      required?: string[];
    };
  };
}

// Agent completion message
export interface AgentMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: {
      name: string;
      arguments: string;
    };
  }>;
  tool_call_id?: string;
}
