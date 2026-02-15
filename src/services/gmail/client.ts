// Gmail API client wrapper with retry logic and operations
import { google, gmail_v1 } from 'googleapis';
import { OAuth2Client } from 'google-auth-library';
import { GaxiosError } from 'gaxios';

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

/**
 * Retry logic wrapper for Gmail API calls
 * Implements exponential backoff for transient errors
 */
async function withRetry<T>(
  operation: () => Promise<T>,
  retries = MAX_RETRIES
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error as Error;

      // Check if error is retryable
      if (!isRetryableError(error)) {
        throw error;
      }

      // Don't retry on last attempt
      if (attempt === retries) {
        break;
      }

      // Exponential backoff: 1s, 2s, 4s
      const delay = BASE_DELAY_MS * Math.pow(2, attempt);
      console.warn(
        `Gmail API error (attempt ${attempt + 1}/${retries + 1}): ${(error as Error).message}. Retrying in ${delay}ms...`
      );
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}

/**
 * Check if error is retryable (network, rate limit, server errors)
 */
function isRetryableError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const gaxiosError = error as GaxiosError;

  // Network errors
  if (gaxiosError.code === 'ECONNRESET' || gaxiosError.code === 'ETIMEDOUT') {
    return true;
  }

  // HTTP errors
  const status = gaxiosError.response?.status;
  if (status) {
    // Rate limiting
    if (status === 429) return true;
    // Server errors
    if (status >= 500 && status < 600) return true;
  }

  return false;
}

/**
 * Gmail API client class
 */
export class GmailClient {
  private gmail: gmail_v1.Gmail;
  private userId = 'me';

  constructor(auth: OAuth2Client) {
    this.gmail = google.gmail({ version: 'v1', auth });
  }

  /**
   * Get user profile (email address and current historyId)
   */
  async getProfile(): Promise<{ email: string; historyId: string }> {
    const response = await withRetry(() =>
      this.gmail.users.getProfile({ userId: this.userId })
    );

    if (!response.data.emailAddress || !response.data.historyId) {
      throw new Error('Failed to get user profile from Gmail');
    }

    return {
      email: response.data.emailAddress,
      historyId: response.data.historyId.toString(),
    };
  }

  /**
   * List messages with query
   */
  async listMessages(query?: string, maxResults = 50): Promise<gmail_v1.Schema$Message[]> {
    const response = await withRetry(() =>
      this.gmail.users.messages.list({
        userId: this.userId,
        q: query,
        maxResults,
      })
    );

    return response.data.messages || [];
  }

  /**
   * Get single message by ID
   */
  async getMessage(messageId: string, format: 'full' | 'metadata' = 'full'): Promise<gmail_v1.Schema$Message> {
    const response = await withRetry(() =>
      this.gmail.users.messages.get({
        userId: this.userId,
        id: messageId,
        format,
      })
    );

    return response.data;
  }

  /**
   * Get thread by ID
   */
  async getThread(threadId: string): Promise<gmail_v1.Schema$Thread> {
    const response = await withRetry(() =>
      this.gmail.users.threads.get({
        userId: this.userId,
        id: threadId,
        format: 'full',
      })
    );

    return response.data;
  }

  /**
   * List history records since a historyId (incremental sync)
   */
  async listHistory(
    startHistoryId: string,
    maxResults = 100
  ): Promise<{
    history: gmail_v1.Schema$History[];
    historyId: string;
    nextPageToken?: string;
  }> {
    try {
      const response = await withRetry(() =>
        this.gmail.users.history.list({
          userId: this.userId,
          startHistoryId,
          maxResults,
          historyTypes: ['messageAdded', 'messageDeleted', 'labelAdded', 'labelRemoved'],
        })
      );

      return {
        history: response.data.history || [],
        historyId: response.data.historyId?.toString() || startHistoryId,
        nextPageToken: response.data.nextPageToken,
      };
    } catch (error) {
      // historyId too old (404) - return empty to trigger full sync
      const gaxiosError = error as GaxiosError;
      if (gaxiosError.response?.status === 404) {
        console.warn('History ID too old, triggering full sync fallback');
        return { history: [], historyId: startHistoryId };
      }
      throw error;
    }
  }

  /**
   * List all labels
   */
  async listLabels(): Promise<gmail_v1.Schema$Label[]> {
    const response = await withRetry(() =>
      this.gmail.users.labels.list({ userId: this.userId })
    );

    return response.data.labels || [];
  }

  /**
   * Create a new label
   */
  async createLabel(name: string, parentLabelId?: string): Promise<gmail_v1.Schema$Label> {
    const labelObject: gmail_v1.Schema$Label = {
      name,
      labelListVisibility: 'labelShow',
      messageListVisibility: 'show',
    };

    const response = await withRetry(() =>
      this.gmail.users.labels.create({
        userId: this.userId,
        requestBody: labelObject,
      })
    );

    return response.data;
  }

  /**
   * Modify labels on a message (add/remove)
   */
  async modifyMessageLabels(
    messageId: string,
    addLabelIds: string[] = [],
    removeLabelIds: string[] = []
  ): Promise<void> {
    await withRetry(() =>
      this.gmail.users.messages.modify({
        userId: this.userId,
        id: messageId,
        requestBody: {
          addLabelIds,
          removeLabelIds,
        },
      })
    );
  }

  /**
   * Batch modify labels on multiple messages
   */
  async batchModifyMessages(
    messageIds: string[],
    addLabelIds: string[] = [],
    removeLabelIds: string[] = []
  ): Promise<void> {
    await withRetry(() =>
      this.gmail.users.messages.batchModify({
        userId: this.userId,
        requestBody: {
          ids: messageIds,
          addLabelIds,
          removeLabelIds,
        },
      })
    );
  }

  /**
   * Create a draft reply in a thread
   */
  async createDraft(
    threadId: string,
    to: string,
    subject: string,
    body: string,
    inReplyTo?: string,
    references?: string
  ): Promise<{ draftId: string; messageId: string }> {
    // Build RFC 822 email
    const email = [
      `To: ${to}`,
      `Subject: ${subject}`,
      inReplyTo ? `In-Reply-To: ${inReplyTo}` : null,
      references ? `References: ${references}` : null,
      'Content-Type: text/plain; charset=utf-8',
      '',
      body,
    ]
      .filter(Boolean)
      .join('\r\n');

    // Base64 URL-safe encode
    const encodedEmail = Buffer.from(email).toString('base64url');

    const response = await withRetry(() =>
      this.gmail.users.drafts.create({
        userId: this.userId,
        requestBody: {
          message: {
            threadId,
            raw: encodedEmail,
          },
        },
      })
    );

    if (!response.data.id || !response.data.message?.id) {
      throw new Error('Failed to create draft');
    }

    return {
      draftId: response.data.id,
      messageId: response.data.message.id,
    };
  }

  /**
   * Get draft by ID
   */
  async getDraft(draftId: string): Promise<gmail_v1.Schema$Draft> {
    const response = await withRetry(() =>
      this.gmail.users.drafts.get({
        userId: this.userId,
        id: draftId,
      })
    );

    return response.data;
  }

  /**
   * Trash a draft (soft delete)
   */
  async trashDraft(draftId: string): Promise<void> {
    await withRetry(() =>
      this.gmail.users.drafts.delete({
        userId: this.userId,
        id: draftId,
      })
    );
  }

  /**
   * Delete/trash a draft (alias for trashDraft)
   */
  async deleteDraft(draftId: string): Promise<void> {
    await this.trashDraft(draftId);
  }

  /**
   * List drafts
   */
  async listDrafts(): Promise<gmail_v1.Schema$Draft[]> {
    const response = await withRetry(() =>
      this.gmail.users.drafts.list({ userId: this.userId })
    );

    return response.data.drafts || [];
  }

  /**
   * Modify labels on a thread
   */
  async modifyThreadLabels(
    threadId: string,
    modifications: {
      addLabelIds?: string[];
      removeLabelIds?: string[];
    }
  ): Promise<void> {
    await withRetry(() =>
      this.gmail.users.threads.modify({
        userId: this.userId,
        id: threadId,
        requestBody: {
          addLabelIds: modifications.addLabelIds || [],
          removeLabelIds: modifications.removeLabelIds || [],
        },
      })
    );
  }

  /**
   * Watch mailbox for push notifications via Pub/Sub
   */
  async watch(topicName: string, labelIds: string[] = ['INBOX']): Promise<{
    historyId: string;
    expiration: number;
  }> {
    const response = await withRetry(() =>
      this.gmail.users.watch({
        userId: this.userId,
        requestBody: {
          topicName,
          labelIds,
          labelFilterAction: 'include',
        },
      })
    );

    if (!response.data.historyId || !response.data.expiration) {
      throw new Error('Failed to set up Gmail watch');
    }

    return {
      historyId: response.data.historyId.toString(),
      expiration: parseInt(response.data.expiration),
    };
  }

  /**
   * Stop watching mailbox
   */
  async stopWatch(): Promise<void> {
    await withRetry(() =>
      this.gmail.users.stop({ userId: this.userId })
    );
  }
}

/**
 * Extract plain text body from Gmail message
 * Handles multipart MIME structures
 */
export function extractPlainTextBody(message: gmail_v1.Schema$Message): string {
  if (!message.payload) {
    return '';
  }

  // Single part message
  if (message.payload.body?.data) {
    return Buffer.from(message.payload.body.data, 'base64url').toString('utf-8');
  }

  // Multipart message - recursively search for text/plain
  function findTextPart(part: gmail_v1.Schema$MessagePart): string | null {
    if (part.mimeType === 'text/plain' && part.body?.data) {
      return Buffer.from(part.body.data, 'base64url').toString('utf-8');
    }

    if (part.parts) {
      for (const subPart of part.parts) {
        const text = findTextPart(subPart);
        if (text) return text;
      }
    }

    return null;
  }

  return findTextPart(message.payload) || '';
}

/**
 * Extract header value from message
 */
export function getHeader(message: gmail_v1.Schema$Message, name: string): string | undefined {
  const headers = message.payload?.headers || [];
  const header = headers.find((h) => h.name?.toLowerCase() === name.toLowerCase());
  return header?.value;
}

/**
 * Parse sender name and email from "From" header
 * Format: "Name <email@example.com>" or "email@example.com"
 */
export function parseSender(fromHeader: string): { name: string; email: string } {
  const match = fromHeader.match(/^(.+?)\s*<(.+?)>$/);
  if (match) {
    return {
      name: match[1].trim().replace(/^["']|["']$/g, ''), // Remove quotes
      email: match[2].trim(),
    };
  }

  return {
    name: fromHeader.trim(),
    email: fromHeader.trim(),
  };
}
