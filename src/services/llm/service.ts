import { generateStructuredObject, generateTextCompletion, getModelForOperation } from './client';
import { ClassificationOutputSchema, ContextQueryOutputSchema } from './types';
import type { ClassificationOutput, ContextQueryOutput, EmailMetadata, DraftInput } from './types';
import { buildClassificationPrompt } from './prompts/classification';
import { buildDraftPrompt } from './prompts/draft';
import { buildContextQueryPrompt } from './prompts/context';

export async function classifyEmail(params: { email: EmailMetadata }): Promise<ClassificationOutput> {
  const model = getModelForOperation('classify');
  const { system, prompt } = buildClassificationPrompt(params.email);
  const { object } = await generateStructuredObject<ClassificationOutput>({
    model, schema: ClassificationOutputSchema, system, prompt, temperature: 0.0, maxTokens: 256
  });
  return object;
}

export async function generateContextQueries(params: { email: EmailMetadata }): Promise<string[]> {
  const model = getModelForOperation('context');
  const { system, prompt } = buildContextQueryPrompt(params.email);
  const { object } = await generateStructuredObject<ContextQueryOutput>({
    model, schema: ContextQueryOutputSchema, system, prompt, temperature: 0.0, maxTokens: 256
  });
  return object.queries;
}

export async function generateDraft(params: { input: DraftInput }): Promise<string> {
  const model = getModelForOperation('draft');
  const { system, prompt } = buildDraftPrompt(params.input);
  const { text } = await generateTextCompletion({
    model, system, prompt, temperature: 0.3, maxTokens: 2048
  });
  return text;
}
