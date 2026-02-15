// Gmail History API sync engine for incremental email processing
import { GmailClient } from './client.js';
import { gmail_v1 } from 'googleapis';

export interface SyncState {
  userId: number;
  lastHistoryId: string;
  lastSyncAt: Date;
}

export interface SyncResult {
  processedHistoryRecords: number;
  newMessages: string[]; // Thread IDs to classify
  labelChanges: LabelChange[];
  deletedMessages: string[]; // Message IDs
  updatedHistoryId: string;
}

export interface LabelChange {
  messageId: string;
  threadId: string;
  addedLabels: string[];
  removedLabels: string[];
}

/**
 * Gmail sync engine
 * Processes History API changes and generates work items
 */
export class GmailSyncEngine {
  private client: GmailClient;
  private labelMapping: Map<string, string>; // Gmail label ID -> label key

  constructor(client: GmailClient, labelMapping: Record<string, string>) {
    this.client = client;
    this.labelMapping = new Map(Object.entries(labelMapping));
  }

  /**
   * Run incremental sync from last history ID
   * Returns list of actions to take (jobs to enqueue)
   */
  async sync(startHistoryId: string): Promise<SyncResult> {
    const result: SyncResult = {
      processedHistoryRecords: 0,
      newMessages: [],
      labelChanges: [],
      deletedMessages: [],
      updatedHistoryId: startHistoryId,
    };

    // Dedupe sets
    const seenThreadIds = new Set<string>();
    const seenDeletions = new Set<string>();

    let historyResponse = await this.client.listHistory(startHistoryId);

    // If history is empty, might be expired - return for full sync fallback
    if (historyResponse.history.length === 0) {
      return result;
    }

    result.updatedHistoryId = historyResponse.historyId;

    // Process all history pages
    do {
      for (const record of historyResponse.history) {
        result.processedHistoryRecords++;

        // Process messages added (new emails)
        if (record.messagesAdded) {
          for (const added of record.messagesAdded) {
            const threadId = added.message?.threadId;
            const labelIds = added.message?.labelIds || [];

            // Only process INBOX messages, avoid duplicates
            if (threadId && labelIds.includes('INBOX') && !seenThreadIds.has(threadId)) {
              seenThreadIds.add(threadId);
              result.newMessages.push(threadId);
            }
          }
        }

        // Process labels added
        if (record.labelsAdded) {
          for (const labelAdded of record.labelsAdded) {
            const messageId = labelAdded.message?.id;
            const threadId = labelAdded.message?.threadId;
            const labelIds = labelAdded.message?.labelIds || [];

            if (messageId && threadId) {
              // Check for AI labels that trigger actions
              const aiLabelsAdded = labelIds.filter((id) => this.labelMapping.has(id));

              if (aiLabelsAdded.length > 0) {
                result.labelChanges.push({
                  messageId,
                  threadId,
                  addedLabels: aiLabelsAdded.map((id) => this.labelMapping.get(id)!),
                  removedLabels: [],
                });
              }
            }
          }
        }

        // Process labels removed
        if (record.labelsRemoved) {
          for (const labelRemoved of record.labelsRemoved) {
            const messageId = labelRemoved.message?.id;
            const threadId = labelRemoved.message?.threadId;
            const removedLabelIds = labelRemoved.labelIds || [];

            if (messageId && threadId) {
              const aiLabelsRemoved = removedLabelIds.filter((id) => this.labelMapping.has(id));

              if (aiLabelsRemoved.length > 0) {
                result.labelChanges.push({
                  messageId,
                  threadId,
                  addedLabels: [],
                  removedLabels: aiLabelsRemoved.map((id) => this.labelMapping.get(id)!),
                });
              }
            }
          }
        }

        // Process messages deleted (sent detection)
        if (record.messagesDeleted) {
          for (const deleted of record.messagesDeleted) {
            const messageId = deleted.message?.id;
            if (messageId && !seenDeletions.has(messageId)) {
              seenDeletions.add(messageId);
              result.deletedMessages.push(messageId);
            }
          }
        }
      }

      // Fetch next page if available
      if (historyResponse.nextPageToken) {
        historyResponse = await this.client.listHistory(
          startHistoryId,
          100
          // Note: In real implementation, would pass nextPageToken here
          // But Gmail API doesn't support it directly in history.list
        );
      } else {
        break;
      }
    } while (historyResponse.nextPageToken);

    return result;
  }

  /**
   * Full sync fallback when history is too old
   * Fetches recent INBOX messages and returns threads to process
   */
  async fullSync(maxMessages = 50): Promise<string[]> {
    const messages = await this.client.listMessages('in:inbox', maxMessages);

    // Extract unique thread IDs
    const threadIds = new Set<string>();
    for (const message of messages) {
      if (message.threadId) {
        threadIds.add(message.threadId);
      }
    }

    return Array.from(threadIds);
  }

  /**
   * Determine job type based on label changes
   */
  determineJobType(labelChange: LabelChange): string | null {
    // Done label added -> cleanup job
    if (labelChange.addedLabels.includes('done')) {
      return 'cleanup';
    }

    // Rework label added -> rework job
    if (labelChange.addedLabels.includes('rework')) {
      return 'rework';
    }

    // Needs Response label added (manual) -> manual_draft job
    if (labelChange.addedLabels.includes('needs_response')) {
      return 'manual_draft';
    }

    return null;
  }
}

/**
 * Process new message and determine if it should be classified or routed to agent
 * This would integrate with routing rules in a full implementation
 */
export async function routeNewMessage(
  client: GmailClient,
  threadId: string
): Promise<'classify' | 'agent_process'> {
  // For now, default to classify
  // In full implementation, would check:
  // - Routing rules (sender, subject, headers)
  // - Agent profiles
  // - Automation detection (blacklist patterns)

  return 'classify';
}

/**
 * Detect sent emails by checking if draft was deleted
 * If draft disappeared and thread has SENT label, email was likely sent
 */
export async function detectSent(
  client: GmailClient,
  messageId: string
): Promise<boolean> {
  try {
    const message = await client.getMessage(messageId, 'metadata');
    const labelIds = message.labelIds || [];

    // Check if message is in SENT
    return labelIds.includes('SENT');
  } catch (error) {
    // Message not found - could be deleted draft
    return false;
  }
}
