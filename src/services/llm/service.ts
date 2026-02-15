// Main LLM service with classification, drafting, and context gathering
import {
  generateStructuredObject,
  generateTextCompletion,
  getModelForOperation,
} from './client';
import { withLogging } from './logger';
import {
  ClassificationOutputSchema,
  ContextQueryOutputSchema,
  type ClassificationOutput,
  type ContextQueryOutput,
  type EmailMetadata,
  type DraftInput,
} from './types';
import { buildClassificationPrompt } from './prompts/classification';
import { buildDraftPrompt } from './prompts/draft';
import { buildContextQueryPrompt } from './prompts/context';

/**
 * Classify email using LLM (Tier 2 classification)
 */
export async function classifyEmail(params: {
  email: EmailMetadata;
  userId?: number;
  threadId?: string;
}): Promise<ClassificationOutput> {
  const model = getModelForOperation('classify');
  const { system, prompt } = buildClassificationPrompt(params.email);

  return withLogging(
    {
      userId: params.userId,
      threadId: params.threadId,
      callType: 'classify',
      model,
      systemPrompt: system,
      userMessage: prompt,
    },
    async () => {
      const { object, usage } = await generateStructuredObject<ClassificationOutput>({
        model,
        schema: ClassificationOutputSchema,
        system,
        prompt,
        temperature: 0.0,
        maxTokens: 256,
      });

      return {
        result: object,
        usage,
        response: JSON.stringify(object, null, 2),
      };
    }
  );
}

/**
 * Generate context search queries for finding related emails
 */
export async function generateContextQueries(params: {
  email: EmailMetadata;
  userId?: number;
}): Promise<string[]> {
  const model = getModelForOperation('context');
  const { system, prompt } = buildContextQueryPrompt(params.email);

  return withLogging(
    {
      userId: params.userId,
      callType: 'context',
      model,
      systemPrompt: system,
      userMessage: prompt,
    },
    async () => {
      const { object, usage } = await generateStructuredObject<ContextQueryOutput>({
        model,
        schema: ContextQueryOutputSchema,
        system,
        prompt,
        temperature: 0.0,
        maxTokens: 256,
      });

      return {
        result: object.queries,
        usage,
        response: JSON.stringify(object, null, 2),
      };
    }
  );
}

/**
 * Generate draft email response
 */
export async function generateDraft(params: {
  input: DraftInput;
  userId?: number;
  isRework?: boolean;
}): Promise<string> {
  const model = getModelForOperation('draft');
  const { system, prompt } = buildDraftPrompt(params.input);
  const callType = params.isRework ? 'rework' : 'draft';

  return withLogging(
    {
      userId: params.userId,
      threadId: params.input.thread.threadId,
      callType,
      model,
      systemPrompt: system,
      userMessage: prompt,
    },
    async () => {
      const { text, usage } = await generateTextCompletion({
        model,
        system,
        prompt,
        temperature: 0.3,
        maxTokens: 2048,
      });

      return {
        result: text,
        usage,
        response: text,
      };
    }
  );
}
