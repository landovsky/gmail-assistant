/**
 * Classification adapter - maps shared API to existing implementation
 */

import type { ClassificationInput, ClassificationResult } from '../../shared/types/api.js';
import { classifyEmailTwoTier } from './engine.js';

export async function classify(
  input: ClassificationInput,
  labelMappings: Array<{key: string, gmailLabelId: string}>
): Promise<ClassificationResult> {
  const result = await classifyEmailTwoTier({
    email: {
      senderEmail: input.from,
      senderName: input.senderName,
      subject: input.subject,
      body: input.body,
    },
    headers: input.headers,
    userId: input.userId,
    threadId: input.threadId,
  });

  const labelMapping = labelMappings.find(l => l.key === result.finalClassification);

  return {
    category: result.finalClassification as any,
    confidence: result.confidence,
    reasoning: result.reasoning,
    language: result.detected_language,
    communicationStyle: result.style as any,
    isAutomated: result.isAutomated,
    automationReason: result.automationReason,
    labelId: labelMapping?.gmailLabelId || '',
  };
}
