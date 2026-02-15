// LLM client using Vercel AI SDK with multi-provider support
import { anthropic } from '@ai-sdk/anthropic';
import { openai } from '@ai-sdk/openai';
import { google } from '@ai-sdk/google';
import { generateObject, generateText, streamText } from 'ai';
import { config } from '../../lib/config';
import type { LLMCallMetadata } from './types';

// Provider registry
const PROVIDERS = {
  anthropic,
  openai,
  google,
} as const;

type ProviderName = keyof typeof PROVIDERS;

/**
 * Parse model string into provider and model name
 * Format: "provider/model-name" (e.g., "anthropic/claude-3-5-sonnet-20241022")
 */
function parseModelString(modelStr: string): {
  provider: ProviderName;
  model: string;
} {
  const parts = modelStr.split('/');
  if (parts.length !== 2) {
    throw new Error(
      `Invalid model format: ${modelStr}. Expected "provider/model-name"`
    );
  }

  const [providerStr, modelName] = parts;
  const provider = providerStr as ProviderName;

  if (!(provider in PROVIDERS)) {
    throw new Error(
      `Unknown provider: ${provider}. Supported: ${Object.keys(PROVIDERS).join(', ')}`
    );
  }

  return { provider, model: modelName };
}

/**
 * Get language model instance from model string
 */
export function getModel(modelStr: string) {
  const { provider, model } = parseModelString(modelStr);
  const providerInstance = PROVIDERS[provider];
  return providerInstance(model);
}

/**
 * Generate structured object output with schema validation
 */
export async function generateStructuredObject<T>(params: {
  model: string;
  schema: any; // Zod schema
  system?: string;
  prompt: string;
  temperature?: number;
  maxTokens?: number;
}): Promise<{
  object: T;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}> {
  const modelInstance = getModel(params.model);

  const result = await generateObject({
    model: modelInstance,
    schema: params.schema,
    system: params.system,
    prompt: params.prompt,
    temperature: params.temperature ?? 0.0,
    maxTokens: params.maxTokens,
  });

  return {
    object: result.object as T,
    usage: {
      promptTokens: result.usage.promptTokens,
      completionTokens: result.usage.completionTokens,
      totalTokens: result.usage.totalTokens,
    },
  };
}

/**
 * Generate text completion
 */
export async function generateTextCompletion(params: {
  model: string;
  system?: string;
  prompt: string;
  temperature?: number;
  maxTokens?: number;
}): Promise<{
  text: string;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}> {
  const modelInstance = getModel(params.model);

  const result = await generateText({
    model: modelInstance,
    system: params.system,
    prompt: params.prompt,
    temperature: params.temperature ?? 0.3,
    maxTokens: params.maxTokens,
  });

  return {
    text: result.text,
    usage: {
      promptTokens: result.usage.promptTokens,
      completionTokens: result.usage.completionTokens,
      totalTokens: result.usage.totalTokens,
    },
  };
}

/**
 * Generate streaming text (for future UI features)
 */
export async function generateStreamingText(params: {
  model: string;
  system?: string;
  prompt: string;
  temperature?: number;
  maxTokens?: number;
}) {
  const modelInstance = getModel(params.model);

  return streamText({
    model: modelInstance,
    system: params.system,
    prompt: params.prompt,
    temperature: params.temperature ?? 0.3,
    maxTokens: params.maxTokens,
  });
}

/**
 * Get model string for specific operation from config
 */
export function getModelForOperation(operation: 'classify' | 'draft' | 'context'): string {
  switch (operation) {
    case 'classify':
      return config.llm.classificationModel;
    case 'draft':
      return config.llm.draftModel;
    case 'context':
      return config.llm.contextModel;
  }
}
