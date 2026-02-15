// LLM call logger for database persistence
import { db, llmCalls } from '../../db';
import type { LLMCallMetadata } from './types';

/**
 * Log LLM API call to database for debugging and cost tracking
 */
export async function logLLMCall(metadata: LLMCallMetadata): Promise<void> {
  await db.insert(llmCalls).values({
    userId: metadata.userId ?? null,
    gmailThreadId: metadata.threadId ?? null,
    callType: metadata.callType,
    model: metadata.model,
    systemPrompt: metadata.systemPrompt ?? null,
    userMessage: metadata.userMessage ?? null,
    responseText: metadata.response ?? null,
    promptTokens: metadata.promptTokens,
    completionTokens: metadata.completionTokens,
    totalTokens: metadata.totalTokens,
    latencyMs: metadata.latencyMs,
    error: metadata.error ?? null,
  });
}

/**
 * Wrap LLM call with automatic logging
 */
export async function withLogging<T>(
  metadata: Omit<LLMCallMetadata, 'latencyMs' | 'promptTokens' | 'completionTokens' | 'totalTokens'>,
  fn: () => Promise<{
    result: T;
    usage: {
      promptTokens: number;
      completionTokens: number;
      totalTokens: number;
    };
    response?: string;
  }>
): Promise<T> {
  const startTime = Date.now();

  try {
    const { result, usage, response } = await fn();
    const latencyMs = Date.now() - startTime;

    // Log successful call
    await logLLMCall({
      ...metadata,
      response,
      promptTokens: usage.promptTokens,
      completionTokens: usage.completionTokens,
      totalTokens: usage.totalTokens,
      latencyMs,
    });

    return result;
  } catch (error) {
    const latencyMs = Date.now() - startTime;
    const errorMessage = error instanceof Error ? error.message : String(error);

    // Log failed call
    await logLLMCall({
      ...metadata,
      promptTokens: 0,
      completionTokens: 0,
      totalTokens: 0,
      latencyMs,
      error: errorMessage,
    });

    throw error;
  }
}
