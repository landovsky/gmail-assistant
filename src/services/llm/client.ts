import { anthropic } from '@ai-sdk/anthropic';
import { openai } from '@ai-sdk/openai';
import { google } from '@ai-sdk/google';
import { generateObject, generateText } from 'ai';
import { config } from '../../lib/config';

const PROVIDERS = { anthropic, openai, google } as const;
type ProviderName = keyof typeof PROVIDERS;

function parseModelString(modelStr: string): { provider: ProviderName; model: string } {
  const parts = modelStr.split('/');
  if (parts.length !== 2) throw new Error(`Invalid model format: ${modelStr}`);
  const [providerStr, modelName] = parts;
  const provider = providerStr as ProviderName;
  if (!(provider in PROVIDERS)) throw new Error(`Unknown provider: ${provider}`);
  return { provider, model: modelName };
}

export function getModel(modelStr: string) {
  const { provider, model } = parseModelString(modelStr);
  return PROVIDERS[provider](model);
}

export async function generateStructuredObject<T>(params: {
  model: string; schema: any; system?: string; prompt: string;
  temperature?: number; maxTokens?: number;
}) {
  const result = await generateObject({
    model: getModel(params.model),
    schema: params.schema,
    system: params.system,
    prompt: params.prompt,
    temperature: params.temperature ?? 0.0,
    maxTokens: params.maxTokens,
  });
  return { object: result.object as T, usage: result.usage };
}

export async function generateTextCompletion(params: {
  model: string; system?: string; prompt: string;
  temperature?: number; maxTokens?: number;
}) {
  const result = await generateText({
    model: getModel(params.model),
    system: params.system,
    prompt: params.prompt,
    temperature: params.temperature ?? 0.3,
    maxTokens: params.maxTokens,
  });
  return { text: result.text, usage: result.usage };
}

export function getModelForOperation(op: 'classify' | 'draft' | 'context'): string {
  return op === 'classify' ? config.llm.classificationModel :
         op === 'draft' ? config.llm.draftModel : config.llm.contextModel;
}
