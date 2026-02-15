/**
 * Shared API Contracts
 * All services must implement these interfaces for integration layer compatibility
 */

import type { GmailClient } from '../../services/gmail/client.js';

// ============================================================================
// CLASSIFICATION API
// ============================================================================

export interface ClassificationInput {
  userId: number;
  threadId: string;
  messageId: string;
  subject: string;
  from: string;
  body: string;
  headers: Record<string, string>;
  senderName?: string;
}

export interface ClassificationResult {
  category: 'needs_response' | 'action_required' | 'payment_request' | 'fyi' | 'waiting';
  confidence: 'high' | 'medium' | 'low';
  reasoning: string;
  language: string;
  communicationStyle: 'formal' | 'business' | 'informal';
  isAutomated: boolean;
  automationReason?: string;
  labelId: string; // Gmail label ID to apply
}

/**
 * Classification service interface
 * Implementations: src/services/classification/engine.ts
 */
export interface IClassificationService {
  classify(input: ClassificationInput, labelMappings: Array<{key: string, gmailLabelId: string}>): Promise<ClassificationResult>;
}

// ============================================================================
// DRAFT GENERATION API
// ============================================================================

export interface DraftGenerationInput {
  userId: number;
  threadId: string;
  subject: string;
  from: string;
  body: string;
  communicationStyle: 'formal' | 'business' | 'informal';
  language: string;
  signOffName?: string;
  userInstructions?: string; // For rework
  client: GmailClient;
}

export interface DraftResult {
  body: string; // Draft body with scissors marker
  plainBody: string; // Draft without marker
  relatedContext: string[];
}

/**
 * Draft generation service interface
 * Implementations: src/services/drafting/engine.ts
 */
export interface IDraftService {
  generateDraft(input: DraftGenerationInput): Promise<DraftResult>;
  regenerateDraft(input: DraftGenerationInput & { draftId: string }): Promise<DraftResult & { instruction: string }>;
}

// ============================================================================
// GMAIL SYNC API
// ============================================================================

export interface SyncMessageDetails {
  threadId: string;
  messageId: string;
  subject: string;
  from: string;
  to: string;
  body: string;
  headers: Record<string, string>;
  date: Date;
  labelIds: string[];
}

export interface SyncHistoryEvent {
  type: 'labelsAdded' | 'labelsRemoved' | 'messagesDeleted' | 'messagesAdded';
  threadId: string;
  messageId?: string;
  labelIds?: string[];
  messageIds?: string[];
}

export interface SyncResult {
  newMessages: SyncMessageDetails[]; // Full message details, not just IDs
  historyEvents: SyncHistoryEvent[];
  newHistoryId: string;
  processedRecords: number;
}

/**
 * Gmail sync service interface
 * Implementations: src/services/gmail/sync.ts (needs adapter)
 */
export interface ISyncService {
  /**
   * Sync messages from Gmail
   * @param userId User ID
   * @param client Authenticated Gmail client
   * @param lastHistoryId Last known history ID (undefined for full sync)
   * @returns Sync result with full message details and history events
   */
  sync(userId: number, client: GmailClient, lastHistoryId?: string): Promise<SyncResult>;
}

// ============================================================================
// LABEL MAPPING API
// ============================================================================

export interface LabelMapping {
  key: 'ai' | 'needs_response' | 'outbox' | 'rework' | 'action_required' | 'payment_request' | 'fyi' | 'waiting' | 'done';
  name: string;
  gmailLabelId: string;
}

/**
 * Label service interface
 * Implementations: src/services/gmail/labels.ts
 */
export interface ILabelService {
  provisionLabels(client: GmailClient): Promise<LabelMapping[]>;
  importExistingLabels(client: GmailClient): Promise<LabelMapping[]>;
}

// ============================================================================
// MESSAGE PARSING HELPERS
// ============================================================================

/**
 * Gmail message parser interface
 * Implementations: src/services/gmail/client.ts (needs helpers)
 */
export interface IGmailMessageParser {
  /**
   * Extract message details from Gmail API response
   */
  parseMessage(message: any): {
    subject: string;
    from: string;
    to: string;
    date: Date;
    body: string;
    headers: Record<string, string>;
  };
}
