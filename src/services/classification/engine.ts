// Classification Engine - Two-tier email classification system
import { classifyEmail as llmClassify } from '../llm/service';
import type { EmailMetadata, ClassificationOutput } from '../llm/types';
import { detectAutomation } from './automation-detector';

export interface ClassificationInput {
  email: EmailMetadata;
  headers?: Record<string, string>;
  userBlacklist?: string[];
  userId?: number;
  threadId?: string;
}

export interface ClassificationResult extends ClassificationOutput {
  isAutomated: boolean;
  automationReason?: string;
  finalClassification: string;
}

/**
 * Two-tier classification engine
 * Tier 1: Rule-based automation detection
 * Tier 2: LLM classification
 */
export async function classifyEmailTwoTier(
  input: ClassificationInput
): Promise<ClassificationResult> {
  // Tier 1: Check if email is automated
  const automationCheck = detectAutomation({
    senderEmail: input.email.senderEmail,
    headers: input.headers,
    blacklist: input.userBlacklist,
  });

  // If automated, skip LLM and classify as FYI
  if (automationCheck.isAutomated) {
    return {
      isAutomated: true,
      automationReason: automationCheck.reason,
      classification: 'fyi',
      confidence: 'high',
      reasoning: `Automated email detected (${automationCheck.reason})`,
      detected_language: 'en',
      style: 'business',
      finalClassification: 'fyi',
    };
  }

  // Tier 2: LLM classification
  const llmResult = await llmClassify({
    email: input.email,
  });

  // Safety net: If LLM says needs_response but we detected automation, override
  const finalClassification =
    automationCheck.isAutomated && llmResult.classification === 'needs_response'
      ? 'fyi'
      : llmResult.classification;

  return {
    ...llmResult,
    isAutomated: false,
    finalClassification,
  };
}

/**
 * Style resolution with priority order:
 * 1. Exact email match
 * 2. Domain pattern match
 * 3. LLM-detected style
 * 4. Default (business)
 */
export function resolveStyle(
  senderEmail: string,
  llmStyle: string,
  styleOverrides?: Record<string, string>,
  domainOverrides?: Record<string, string>
): string {
  // Check exact email match
  if (styleOverrides?.[senderEmail]) {
    return styleOverrides[senderEmail];
  }

  // Check domain match
  const domain = senderEmail.split('@')[1];
  if (domain && domainOverrides?.[domain]) {
    return domainOverrides[domain];
  }

  // Use LLM-detected style
  if (llmStyle) {
    return llmStyle;
  }

  // Default fallback
  return 'business';
}

/**
 * Language resolution with priority order:
 * 1. Email/domain override
 * 2. LLM-detected language
 * 3. Default (cs)
 */
export function resolveLanguage(
  senderEmail: string,
  llmLanguage: string,
  languageOverrides?: Record<string, string>,
  defaultLanguage = 'cs'
): string {
  // Check email override
  if (languageOverrides?.[senderEmail]) {
    return languageOverrides[senderEmail];
  }

  // Check domain override
  const domain = senderEmail.split('@')[1];
  if (domain && languageOverrides?.[domain]) {
    return languageOverrides[domain];
  }

  // Use LLM-detected language
  if (llmLanguage) {
    return llmLanguage;
  }

  // Default fallback
  return defaultLanguage;
}
