import type { ClassificationInput, ClassificationResult } from '../../shared/types/api.js';
import { classifyEmailTwoTier } from './engine.js';

/**
 * Adapter: Maps shared API contract to classification engine implementation
 */
export async function classify(
  input: ClassificationInput,
  labelMappings: Array<{key: string, gmailLabelId: string}>
): Promise<ClassificationResult> {
  // Call existing classifyEmailTwoTier function
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

  // Map category label key to Gmail label ID
  const labelMapping = labelMappings.find(l => l.key === result.finalClassification);

  // Return in shared contract format
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
