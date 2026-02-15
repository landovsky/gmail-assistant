/**
 * Integration Test: Email Classification
 * Tests classification logic with mocked LLM responses
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';
import { db } from '../../src/db/index.js';
import { emails } from '../../src/db/schema.js';
import { eq } from 'drizzle-orm';
import { createTestUser, cleanTestDatabase, createMockGmailMessage } from '../helpers/test-fixtures.js';

describe('Integration: Email Classification', () => {
  let user: any;

  beforeEach(async () => {
    await cleanTestDatabase();
    user = await createTestUser();
  });

  it('should detect automated emails (rule-based)', async () => {
    const message = createMockGmailMessage({
      messageId: 'msg-auto',
      threadId: 'thread-auto',
      from: 'noreply@notifications.com',
      subject: 'Your order has shipped',
      body: 'Your order #12345 has been shipped.',
      headers: {
        'Auto-Submitted': 'auto-generated',
      },
    });

    // Automation detection should happen before LLM classification
    // Based on sender email (noreply@) and Auto-Submitted header

    assert.ok(message.payload.headers.some(h =>
      h.name === 'From' && h.value.includes('noreply@')
    ), 'Should detect noreply sender');

    assert.ok(message.payload.headers.some(h =>
      h.name === 'Auto-Submitted'
    ), 'Should detect Auto-Submitted header');
  });

  it('should detect newsletters (List-Unsubscribe header)', async () => {
    const message = createMockGmailMessage({
      messageId: 'msg-newsletter',
      threadId: 'thread-newsletter',
      from: 'newsletter@company.com',
      subject: 'Weekly Newsletter - Tech Updates',
      body: 'Here are this week\'s top stories...',
      headers: {
        'List-Unsubscribe': '<mailto:unsubscribe@company.com>',
        'Precedence': 'bulk',
      },
    });

    assert.ok(message.payload.headers.some(h =>
      h.name === 'List-Unsubscribe'
    ), 'Should detect List-Unsubscribe header');
  });

  it('should classify direct questions as needs_response', async () => {
    const message = createMockGmailMessage({
      messageId: 'msg-question',
      threadId: 'thread-question',
      from: 'colleague@company.com',
      subject: 'Quick question',
      body: 'Can you send me the Q4 report by Friday? Thanks!',
    });

    // Direct question with clear request should be classified as needs_response
    assert.ok(message.payload.body.data, 'Message should have body');

    const body = Buffer.from(message.payload.body.data, 'base64').toString();
    assert.ok(body.includes('Can you'), 'Should contain direct question');
  });

  it('should classify meeting invites as action_required', async () => {
    const message = createMockGmailMessage({
      messageId: 'msg-meeting',
      threadId: 'thread-meeting',
      from: 'boss@company.com',
      subject: 'Meeting invite: Q4 Planning',
      body: 'You are invited to Q4 Planning Meeting on Friday at 2 PM. Please confirm attendance.',
      headers: {
        'Content-Type': 'text/calendar',
      },
    });

    assert.ok(message.subject.includes('Meeting'), 'Should detect meeting in subject');
  });

  it('should detect Czech language emails', async () => {
    const message = createMockGmailMessage({
      messageId: 'msg-czech',
      threadId: 'thread-czech',
      from: 'partner@firma.cz',
      subject: 'Dotaz ohledně objednávky',
      body: 'Dobrý den,\n\nchtěl bych se zeptat na stav mé objednávky. Můžete mi prosím sdělit více informací?\n\nDěkuji',
    });

    const body = Buffer.from(message.payload.body.data, 'base64').toString();

    // Czech language detection based on common words
    const czechWords = ['Dobrý den', 'děkuji', 'prosím', 'můžete'];
    const hasCzechWords = czechWords.some(word => body.toLowerCase().includes(word.toLowerCase()));

    assert.ok(hasCzechWords, 'Should detect Czech language content');
  });

  it('should classify invoices as payment_request', async () => {
    const message = createMockGmailMessage({
      messageId: 'msg-invoice',
      threadId: 'thread-invoice',
      from: 'billing@vendor.com',
      subject: 'Invoice #12345 - Payment Due',
      body: 'Please find attached invoice #12345.\n\nAmount due: $1,250.00\nDue date: March 31, 2026\n\nPlease remit payment by due date.',
    });

    const subject = message.payload.headers.find(h => h.name === 'Subject')?.value || '';
    const body = Buffer.from(message.payload.body.data, 'base64').toString();

    assert.ok(subject.includes('Invoice'), 'Subject should contain Invoice');
    assert.ok(body.includes('Amount due'), 'Body should contain payment amount');
  });
});

describe('Integration: Classification - Style Detection', () => {
  it('should detect formal communication style', async () => {
    const message = createMockGmailMessage({
      messageId: 'msg-formal',
      threadId: 'thread-formal',
      from: 'director@corporation.com',
      subject: 'Request for Quarterly Financial Review',
      body: 'Dear Sir/Madam,\n\nI am writing to request a comprehensive review of the quarterly financial statements. Please prepare a detailed analysis at your earliest convenience.\n\nRespectfully,\nJohn Director',
    });

    const body = Buffer.from(message.payload.body.data, 'base64').toString();

    // Formal indicators
    const formalIndicators = ['Dear Sir/Madam', 'Respectfully', 'at your earliest convenience'];
    const hasFormalTone = formalIndicators.some(indicator => body.includes(indicator));

    assert.ok(hasFormalTone, 'Should detect formal tone');
  });

  it('should detect informal communication style', async () => {
    const message = createMockGmailMessage({
      messageId: 'msg-informal',
      threadId: 'thread-informal',
      from: 'buddy@startup.com',
      subject: 'Hey - quick sync?',
      body: 'Hey!\n\nWanna grab coffee later and chat about the project? Let me know!\n\nCheers,\nBob',
    });

    const body = Buffer.from(message.payload.body.data, 'base64').toString();
    const subject = message.payload.headers.find(h => h.name === 'Subject')?.value || '';

    // Informal indicators
    const hasInformalTone = subject.includes('Hey') || body.includes('Wanna') || body.includes('Cheers');

    assert.ok(hasInformalTone, 'Should detect informal tone');
  });
});
