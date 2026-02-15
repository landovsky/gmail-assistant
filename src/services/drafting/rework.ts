// Rework handler for draft iteration
import { generateEmailDraft, extractReworkInstruction, isReworkLimitReached } from './engine';
import type { DraftGenerationInput, DraftResult } from './engine';

export interface ReworkInput {
  existingDraftContent: string;
  reworkCount: number;
  baseInput: DraftGenerationInput;
}

export interface ReworkResult {
  success: boolean;
  draft?: DraftResult;
  limitReached?: boolean;
  warning?: string;
}

/**
 * Handle draft rework with user feedback
 */
export async function handleDraftRework(
  input: ReworkInput
): Promise<ReworkResult> {
  // Check rework limit (max 3 iterations)
  if (isReworkLimitReached(input.reworkCount)) {
    return {
      success: false,
      limitReached: true,
      warning:
        'Maximum rework iterations (3) reached. Please edit manually or mark as done.',
    };
  }

  // Extract user instruction from draft
  const instruction = extractReworkInstruction(input.existingDraftContent);

  if (!instruction) {
    return {
      success: false,
      warning:
        'No rework instruction found. Add your feedback above the ✂️ marker.',
    };
  }

  // Generate new draft with user feedback
  const draft = await generateEmailDraft({
    ...input.baseInput,
    userInstructions: instruction,
  });

  return {
    success: true,
    draft,
  };
}

/**
 * Create warning message for rework limit
 */
export function createLimitWarningMessage(): string {
  return `
⚠️ REWORK LIMIT REACHED ⚠️

You've reached the maximum number of draft rework iterations (3).

Options:
1. Send this draft as-is
2. Edit it manually in Gmail
3. Mark the email as "Done" to handle later

The draft will not be regenerated automatically.
`.trim();
}
