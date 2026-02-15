/**
 * Integration Test: Workflow Orchestration
 * Tests sync coordinator and email lifecycle workflows
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';
import { db } from '../../src/db/index.js';
import { emails, emailEvents } from '../../src/db/schema.js';
import { eq } from 'drizzle-orm';
import { handleClassificationComplete, handleDraftCreated, handleDoneRequested } from '../../src/workflows/email-lifecycle.js';
import { createTestUser, cleanTestDatabase } from '../helpers/test-fixtures.js';
import { MockGmailClient } from '../helpers/mock-clients.js';

describe('Integration: Email Lifecycle - State Transitions', () => {
  let user: any;
  let client: MockGmailClient;

  beforeEach(async () => {
    await cleanTestDatabase();
    user = await createTestUser();
    client = new MockGmailClient();
  });

  it('should transition from classification to pending', async () => {
    // Create email record
    const [email] = await db.insert(emails).values({
      userId: user.id,
      gmailThreadId: 'thread-123',
      gmailMessageId: 'msg-123',
      subject: 'Test Email',
      senderEmail: 'sender@example.com',
      classification: 'needs_response',
      status: 'pending',
      messageCount: 1,
    }).returning();

    // Handle classification complete
    const result = await handleClassificationComplete({
      userId: user.id,
      threadId: 'thread-123',
      classification: 'needs_response',
      labelId: 'label-needs_response',
      emailId: email.id,
    });

    assert.strictEqual(result.success, true);
    assert.strictEqual(result.newStatus, 'pending');

    // Verify event logged
    const events = await db.query.emailEvents.findMany({
      where: eq(emailEvents.gmailThreadId, 'thread-123'),
    });

    assert.strictEqual(events.length, 1);
    assert.strictEqual(events[0].eventType, 'classified');
  });

  it('should transition from pending to drafted', async () => {
    // Create email record
    const [email] = await db.insert(emails).values({
      userId: user.id,
      gmailThreadId: 'thread-123',
      gmailMessageId: 'msg-123',
      subject: 'Test Email',
      senderEmail: 'sender@example.com',
      classification: 'needs_response',
      status: 'pending',
      messageCount: 1,
    }).returning();

    client.addMessage({
      id: 'msg-123',
      threadId: 'thread-123',
      payload: { headers: [], body: { data: '' } },
    });

    const labelMappings = [
      { key: 'outbox', gmailLabelId: 'label-outbox' },
      { key: 'needs_response', gmailLabelId: 'label-needs_response' },
    ];

    // Handle draft created
    const result = await handleDraftCreated({
      userId: user.id,
      threadId: 'thread-123',
      draftId: 'draft-123',
      client,
      labelMappings,
    });

    assert.strictEqual(result.success, true);
    assert.strictEqual(result.newStatus, 'drafted');

    // Verify email updated
    const updatedEmail = await db.query.emails.findFirst({
      where: eq(emails.id, email.id),
    });

    assert.strictEqual(updatedEmail?.status, 'drafted');
    assert.strictEqual(updatedEmail?.draftId, 'draft-123');
    assert.ok(updatedEmail?.draftedAt);

    // Verify Outbox label applied
    const labels = client.getThreadLabels('thread-123');
    assert.ok(labels.includes('label-outbox'));
  });

  it('should transition to archived when Done is requested', async () => {
    // Create email record
    const [email] = await db.insert(emails).values({
      userId: user.id,
      gmailThreadId: 'thread-123',
      gmailMessageId: 'msg-123',
      subject: 'Test Email',
      senderEmail: 'sender@example.com',
      classification: 'needs_response',
      status: 'drafted',
      draftId: 'draft-123',
      messageCount: 1,
    }).returning();

    client.addMessage({
      id: 'msg-123',
      threadId: 'thread-123',
      payload: { headers: [], body: { data: '' } },
    });

    const labelMappings = [
      { key: 'outbox', gmailLabelId: 'label-outbox' },
      { key: 'needs_response', gmailLabelId: 'label-needs_response' },
      { key: 'done', gmailLabelId: 'label-done' },
    ];

    // Handle Done requested
    const result = await handleDoneRequested({
      userId: user.id,
      threadId: 'thread-123',
      client,
      labelMappings,
    });

    assert.strictEqual(result.success, true);
    assert.strictEqual(result.newStatus, 'archived');

    // Verify email archived
    const updatedEmail = await db.query.emails.findFirst({
      where: eq(emails.id, email.id),
    });

    assert.strictEqual(updatedEmail?.status, 'archived');
    assert.ok(updatedEmail?.actedAt);

    // Verify all labels removed
    const labels = client.getThreadLabels('thread-123');
    assert.strictEqual(labels.length, 0);
  });
});

describe('Integration: Email Lifecycle - Event Logging', () => {
  let user: any;

  beforeEach(async () => {
    await cleanTestDatabase();
    user = await createTestUser();
  });

  it('should log all state transition events', async () => {
    // Create email
    const [email] = await db.insert(emails).values({
      userId: user.id,
      gmailThreadId: 'thread-123',
      gmailMessageId: 'msg-123',
      subject: 'Test Email',
      senderEmail: 'sender@example.com',
      classification: 'needs_response',
      status: 'pending',
      messageCount: 1,
    }).returning();

    // Log classification event
    await handleClassificationComplete({
      userId: user.id,
      threadId: 'thread-123',
      classification: 'needs_response',
      labelId: 'label-needs_response',
      emailId: email.id,
    });

    // Verify event logged
    const events = await db.query.emailEvents.findMany({
      where: eq(emailEvents.gmailThreadId, 'thread-123'),
    });

    assert.strictEqual(events.length, 1);
    assert.strictEqual(events[0].eventType, 'classified');
    assert.strictEqual(events[0].userId, user.id);
    assert.ok(events[0].detail?.includes('needs_response'));
  });

  it('should maintain event timeline for thread', async () => {
    const [email] = await db.insert(emails).values({
      userId: user.id,
      gmailThreadId: 'thread-123',
      gmailMessageId: 'msg-123',
      subject: 'Test Email',
      senderEmail: 'sender@example.com',
      classification: 'needs_response',
      status: 'pending',
      messageCount: 1,
    }).returning();

    // Event 1: Classified
    await handleClassificationComplete({
      userId: user.id,
      threadId: 'thread-123',
      classification: 'needs_response',
      labelId: 'label-needs_response',
      emailId: email.id,
    });

    // Get events - should have timeline
    const events = await db.query.emailEvents.findMany({
      where: eq(emailEvents.gmailThreadId, 'thread-123'),
    });

    assert.ok(events.length >= 1);
    assert.ok(events.every(e => e.createdAt), 'All events should have timestamps');
  });
});
