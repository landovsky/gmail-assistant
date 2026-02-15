/**
 * LLM Prompts Tests
 * Tests prompt builders for classification, draft, and context generation
 */

import { describe, test } from 'node:test';
import assert from 'node:assert';
import { buildClassificationPrompt } from '../../src/services/llm/prompts/classification';
import { buildDraftPrompt } from '../../src/services/llm/prompts/draft';
import { buildContextQueryPrompt } from '../../src/services/llm/prompts/context';
import type { EmailMetadata, DraftInput } from '../../src/services/llm/types';

describe('LLM Prompts', () => {
  describe('buildClassificationPrompt', () => {
    test('builds basic classification prompt', () => {
      const email: EmailMetadata = {
        senderEmail: 'test@example.com',
        senderName: 'Test Sender',
        subject: 'Quick question',
        body: 'Can you send me the report?',
      };

      const { system, prompt } = buildClassificationPrompt(email);

      assert.ok(system.includes('email classifier'));
      assert.ok(system.includes('needs_response'));
      assert.ok(system.includes('action_required'));
      assert.ok(system.includes('payment_request'));
      assert.ok(system.includes('fyi'));
      assert.ok(system.includes('waiting'));

      assert.ok(prompt.includes('test@example.com'));
      assert.ok(prompt.includes('Test Sender'));
      assert.ok(prompt.includes('Quick question'));
      assert.ok(prompt.includes('Can you send me the report?'));
    });

    test('includes thread context when provided', () => {
      const email: EmailMetadata = {
        senderEmail: 'test@example.com',
        subject: 'Re: Project',
        body: 'Thanks for the update',
        threadMessages: [
          {
            from: 'me@example.com',
            date: '2025-01-10',
            body: 'Here is the project update',
          },
        ],
      };

      const { prompt } = buildClassificationPrompt(email);

      assert.ok(prompt.includes('Thread History'));
      assert.ok(prompt.includes('me@example.com'));
      assert.ok(prompt.includes('Here is the project update'));
    });

    test('handles missing optional fields', () => {
      const email: EmailMetadata = {
        senderEmail: 'test@example.com',
        body: 'Test message',
      };

      const { prompt } = buildClassificationPrompt(email);

      assert.ok(prompt.includes('test@example.com'));
      assert.ok(prompt.includes('(no subject)'));
      assert.ok(prompt.includes('Test message'));
    });
  });

  describe('buildDraftPrompt', () => {
    test('builds basic draft prompt', () => {
      const input: DraftInput = {
        thread: {
          threadId: 'thread-123',
          subject: 'Question about project',
          messages: [
            {
              from: 'client@example.com',
              date: '2025-01-15',
              body: 'What is the project status?',
            },
          ],
        },
        style: 'business',
        language: 'en',
      };

      const { system, prompt } = buildDraftPrompt(input);

      assert.ok(system.includes('email assistant'));
      assert.ok(system.includes('business'));
      assert.ok(system.includes('English'));
      assert.ok(system.includes('Professional but approachable'));

      assert.ok(prompt.includes('Question about project'));
      assert.ok(prompt.includes('client@example.com'));
      assert.ok(prompt.includes('What is the project status?'));
    });

    test('includes formal style template', () => {
      const input: DraftInput = {
        thread: {
          threadId: 'thread-123',
          subject: 'Formal request',
          messages: [
            {
              from: 'vip@example.com',
              date: '2025-01-15',
              body: 'I request your assistance.',
            },
          ],
        },
        style: 'formal',
        language: 'en',
      };

      const { system } = buildDraftPrompt(input);

      assert.ok(system.includes('formal'));
      assert.ok(system.includes('Very polite'));
      assert.ok(system.includes('Kind regards'));
    });

    test('includes informal style template', () => {
      const input: DraftInput = {
        thread: {
          threadId: 'thread-123',
          subject: 'Hey there',
          messages: [
            {
              from: 'friend@example.com',
              date: '2025-01-15',
              body: "What's up?",
            },
          ],
        },
        style: 'informal',
        language: 'en',
      };

      const { system } = buildDraftPrompt(input);

      assert.ok(system.includes('informal'));
      assert.ok(system.includes('Casual, friendly'));
      assert.ok(system.includes('Thanks'));
    });

    test('includes related context', () => {
      const input: DraftInput = {
        thread: {
          threadId: 'thread-123',
          subject: 'Follow up',
          messages: [
            {
              from: 'client@example.com',
              date: '2025-01-15',
              body: 'Following up on our discussion',
            },
          ],
        },
        style: 'business',
        language: 'en',
        relatedContext: [
          'Previous discussion about budget on Jan 10',
          'Timeline agreed on Jan 5',
        ],
      };

      const { prompt } = buildDraftPrompt(input);

      assert.ok(prompt.includes('Related Context from Mailbox'));
      assert.ok(prompt.includes('Previous discussion about budget'));
      assert.ok(prompt.includes('Timeline agreed'));
    });

    test('includes user rework instructions', () => {
      const input: DraftInput = {
        thread: {
          threadId: 'thread-123',
          subject: 'Question',
          messages: [
            {
              from: 'client@example.com',
              date: '2025-01-15',
              body: 'Question here',
            },
          ],
        },
        style: 'business',
        language: 'en',
        userInstructions: 'Make it shorter and more direct',
      };

      const { prompt } = buildDraftPrompt(input);

      assert.ok(prompt.includes('User Feedback'));
      assert.ok(prompt.includes('Make it shorter and more direct'));
    });

    test('includes sign-off name', () => {
      const input: DraftInput = {
        thread: {
          threadId: 'thread-123',
          subject: 'Question',
          messages: [
            {
              from: 'client@example.com',
              date: '2025-01-15',
              body: 'Question here',
            },
          ],
        },
        style: 'business',
        language: 'en',
        signOffName: 'John Smith',
      };

      const { system } = buildDraftPrompt(input);

      assert.ok(system.includes('John Smith'));
    });
  });

  describe('buildContextQueryPrompt', () => {
    test('builds context query prompt', () => {
      const email: EmailMetadata = {
        senderEmail: 'client@example.com',
        senderName: 'Client Name',
        subject: 'Project update request',
        body: 'Can you provide an update on the Q1 project timeline?',
      };

      const { system, prompt } = buildContextQueryPrompt(email);

      assert.ok(system.includes('Gmail search query generator'));
      assert.ok(system.includes('from:'));
      assert.ok(system.includes('subject:'));
      assert.ok(system.includes('newer_than:'));

      assert.ok(prompt.includes('client@example.com'));
      assert.ok(prompt.includes('Client Name'));
      assert.ok(prompt.includes('Project update request'));
      assert.ok(prompt.includes('Can you provide an update'));
    });

    test('truncates long email body', () => {
      const longBody = 'a'.repeat(1000);
      const email: EmailMetadata = {
        senderEmail: 'test@example.com',
        body: longBody,
      };

      const { prompt } = buildContextQueryPrompt(email);

      assert.ok(prompt.length < longBody.length + 200);
      assert.ok(prompt.includes('...'));
    });
  });
});
