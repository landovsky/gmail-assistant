/**
 * Test Fixtures and Helpers for E2E Testing
 */

import { db } from '../../src/db/index.js';
import { users, emails, userLabels, syncState } from '../../src/db/schema.js';

/**
 * Create a test user with labels
 */
export async function createTestUser() {
  const [user] = await db
    .insert(users)
    .values({
      email: 'test@example.com',
      displayName: 'Test User',
      isActive: true,
      onboardedAt: new Date().toISOString(),
    })
    .returning();

  // Create label mappings
  const labelKeys = [
    'needs_response',
    'action_required',
    'payment_request',
    'fyi',
    'waiting',
    'outbox',
    'rework',
    'done',
  ];

  for (const key of labelKeys) {
    await db.insert(userLabels).values({
      userId: user.id,
      labelKey: key,
      gmailLabelId: `label-${key}`,
      gmailLabelName: key.replace('_', ' ').toUpperCase(),
    });
  }

  // Create sync state
  await db.insert(syncState).values({
    userId: user.id,
    lastHistoryId: '0',
    lastSyncAt: new Date().toISOString(),
  });

  return user;
}

/**
 * Create a test email record
 */
export async function createTestEmail(params: {
  userId: number;
  gmailThreadId: string;
  gmailMessageId: string;
  subject: string;
  senderEmail: string;
  classification?: string;
  status?: string;
}) {
  const [email] = await db
    .insert(emails)
    .values({
      userId: params.userId,
      gmailThreadId: params.gmailThreadId,
      gmailMessageId: params.gmailMessageId,
      subject: params.subject,
      senderEmail: params.senderEmail,
      classification: params.classification || 'needs_response',
      status: params.status || 'pending',
      messageCount: 1,
    })
    .returning();

  return email;
}

/**
 * Mock Gmail message structure
 */
export function createMockGmailMessage(params: {
  messageId: string;
  threadId: string;
  from: string;
  subject: string;
  body: string;
  headers?: Record<string, string>;
}) {
  const headers: Array<{ name: string; value: string }> = [
    { name: 'From', value: params.from },
    { name: 'Subject', value: params.subject },
    { name: 'Date', value: new Date().toISOString() },
  ];

  if (params.headers) {
    Object.entries(params.headers).forEach(([key, value]) => {
      headers.push({ name: key, value });
    });
  }

  return {
    id: params.messageId,
    threadId: params.threadId,
    payload: {
      headers,
      body: {
        data: Buffer.from(params.body).toString('base64'),
      },
    },
    snippet: params.body.substring(0, 100),
  };
}

/**
 * Clean test database
 */
export async function cleanTestDatabase() {
  // Order matters due to foreign key constraints
  await db.delete(emails);
  await db.delete(syncState);
  await db.delete(userLabels);
  await db.delete(users);
}
