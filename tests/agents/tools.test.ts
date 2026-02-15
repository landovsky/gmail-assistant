/**
 * Agent Tools Tests
 * Tests core tools (send_reply, create_draft, escalate) and pharmacy tools.
 * Uses MockGmailClient for Gmail operations.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import { ToolRegistry, type ToolContext } from '../../src/agents/tools/registry.js';
import { MockGmailClient } from '../helpers/mock-clients.js';
import { createMockGmailMessage } from '../helpers/test-fixtures.js';

// Register all tools once at module level (global singleton)
import { registerCoreTools } from '../../src/agents/tools/core.js';
import { registerPharmacyTools } from '../../src/agents/tools/pharmacy.js';
import { toolRegistry } from '../../src/agents/tools/registry.js';

// Register tools on the global registry (guarded against double-registration)
if (!toolRegistry.hasTool('send_reply')) {
  registerCoreTools();
}
if (!toolRegistry.hasTool('search_drugs')) {
  registerPharmacyTools();
}

/**
 * Create a MockGmailClient pre-loaded with a thread for tool testing
 */
function setupMockClient(): MockGmailClient {
  const client = new MockGmailClient();

  const message = createMockGmailMessage({
    messageId: 'msg_001',
    threadId: 'thread_001',
    from: 'patient@example.com',
    subject: 'Drug availability question',
    body: 'Is Ibuprofen 400mg available?',
    headers: {
      'Message-ID': '<msg_001@mail.example.com>',
      'Reply-To': 'patient@example.com',
    },
  });

  client.addMessage(message);
  return client;
}

// ---------------------------------------------------------------------------
// Tool Registry basics
// ---------------------------------------------------------------------------

describe('ToolRegistry', () => {
  it('should register and execute a tool', async () => {
    const { z } = await import('zod');
    const registry = new ToolRegistry();

    const schema = z.object({ name: z.string() });
    const handler = async () => 'ok';

    registry.register(
      {
        type: 'function',
        function: {
          name: 'test_tool',
          description: 'A test tool',
          parameters: {
            type: 'object',
            properties: { name: { type: 'string' } },
            required: ['name'],
          },
        },
      },
      schema,
      handler
    );

    assert.ok(registry.hasTool('test_tool'));

    const result = await registry.execute('test_tool', 1, { name: 'hello' });
    assert.strictEqual(result, 'ok');
  });

  it('should pass context through to handler', async () => {
    const { z } = await import('zod');
    const registry = new ToolRegistry();

    let receivedContext: ToolContext | undefined;
    const schema = z.object({ v: z.string() });
    const handler = async (params: { context?: ToolContext }) => {
      receivedContext = params.context;
      return 'done';
    };

    registry.register(
      {
        type: 'function',
        function: {
          name: 'ctx_tool',
          description: 'Context test',
          parameters: {
            type: 'object',
            properties: { v: { type: 'string' } },
            required: ['v'],
          },
        },
      },
      schema,
      handler
    );

    const ctx: ToolContext = { gmailClient: 'fake' };
    await registry.execute('ctx_tool', 1, { v: 'x' }, ctx);
    assert.deepStrictEqual(receivedContext, ctx);
  });

  it('should return error for unknown tool', async () => {
    const registry = new ToolRegistry();
    const result = await registry.execute('nonexistent', 1, {});
    assert.ok(result.includes('Error: Tool nonexistent not found'));
  });

  it('should return validation error for bad arguments', async () => {
    const { z } = await import('zod');
    const registry = new ToolRegistry();

    const schema = z.object({ count: z.number() });
    registry.register(
      {
        type: 'function',
        function: {
          name: 'typed_tool',
          description: 'Typed',
          parameters: {
            type: 'object',
            properties: { count: { type: 'number' } },
            required: ['count'],
          },
        },
      },
      schema,
      async () => 'ok'
    );

    const result = await registry.execute('typed_tool', 1, {
      count: 'not_a_number',
    });
    assert.ok(result.includes('Error: Invalid arguments'));
  });
});

// ---------------------------------------------------------------------------
// Core Tools - send_reply
// ---------------------------------------------------------------------------

describe('Core Tools - send_reply', () => {
  it('should send reply via Gmail API using mock client', async () => {
    const client = setupMockClient();
    const ctx: ToolContext = { gmailClient: client };

    const result = await toolRegistry.execute(
      'send_reply',
      1,
      { message: 'Hello, your drug is available.', threadId: 'thread_001' },
      ctx
    );

    assert.ok(result.includes('Email reply sent successfully'), `Unexpected result: ${result}`);
    assert.ok(result.includes('thread_001'), `Missing thread ID in result: ${result}`);
  });

  it('should fail without Gmail client in context', async () => {
    const result = await toolRegistry.execute('send_reply', 1, {
      message: 'Hello',
      threadId: 'thread_001',
    });

    assert.ok(result.includes('Error executing send_reply'), `Unexpected result: ${result}`);
    assert.ok(result.includes('Gmail client not available'), `Missing error detail: ${result}`);
  });

  it('should fail when thread does not exist', async () => {
    const client = new MockGmailClient(); // empty client, no threads
    const ctx: ToolContext = { gmailClient: client };

    const result = await toolRegistry.execute(
      'send_reply',
      1,
      { message: 'Hello', threadId: 'nonexistent_thread' },
      ctx
    );

    assert.ok(result.includes('Error executing send_reply'), `Unexpected result: ${result}`);
  });
});

// ---------------------------------------------------------------------------
// Core Tools - create_draft
// ---------------------------------------------------------------------------

describe('Core Tools - create_draft', () => {
  it('should create draft via Gmail API using mock client', async () => {
    const client = setupMockClient();
    const ctx: ToolContext = { gmailClient: client };

    const result = await toolRegistry.execute(
      'create_draft',
      1,
      { message: 'Draft response here.', threadId: 'thread_001' },
      ctx
    );

    assert.ok(result.includes('Draft created successfully'), `Unexpected result: ${result}`);
    assert.ok(result.includes('thread_001'), `Missing thread ID: ${result}`);
    assert.ok(result.includes('draftId:'), `Missing draft ID: ${result}`);

    // Verify draft was actually created in the mock
    const drafts = client.getDrafts();
    assert.ok(drafts.size > 0, 'Expected at least one draft in mock client');
  });

  it('should fail without Gmail client in context', async () => {
    const result = await toolRegistry.execute('create_draft', 1, {
      message: 'Draft',
      threadId: 'thread_001',
    });

    assert.ok(result.includes('Error executing create_draft'), `Unexpected result: ${result}`);
    assert.ok(result.includes('Gmail client not available'), `Missing error detail: ${result}`);
  });
});

// ---------------------------------------------------------------------------
// Core Tools - escalate
// ---------------------------------------------------------------------------

describe('Core Tools - escalate', () => {
  it('should escalate thread using mock client', async () => {
    const client = setupMockClient();
    const ctx: ToolContext = { gmailClient: client };

    const result = await toolRegistry.execute(
      'escalate',
      1,
      { reason: 'Medical advice requested', threadId: 'thread_001' },
      ctx
    );

    assert.ok(result.includes('Thread thread_001 escalated'), `Unexpected result: ${result}`);
    assert.ok(result.includes('Medical advice requested'), `Missing reason: ${result}`);
  });

  it('should fail without Gmail client in context', async () => {
    const result = await toolRegistry.execute('escalate', 1, {
      reason: 'Complex issue',
      threadId: 'thread_001',
    });

    assert.ok(result.includes('Error executing escalate'), `Unexpected result: ${result}`);
  });
});

// ---------------------------------------------------------------------------
// Pharmacy Tools (no Gmail client required)
// ---------------------------------------------------------------------------

describe('Pharmacy Tools - search_drugs', () => {
  it('should find available drug', async () => {
    const result = await toolRegistry.execute('search_drugs', 1, {
      drug_name: 'Ibuprofen 400mg',
    });
    assert.ok(result.includes('available'), `Expected available, got: ${result}`);
    assert.ok(result.includes('89 CZK'), `Expected price, got: ${result}`);
  });

  it('should report unavailable drug with alternatives', async () => {
    const result = await toolRegistry.execute('search_drugs', 1, {
      drug_name: 'Amoxicillin',
    });
    assert.ok(result.includes('not available'), `Expected not available, got: ${result}`);
    assert.ok(result.includes('Augmentin'), `Expected alternative, got: ${result}`);
  });

  it('should handle unknown drug', async () => {
    const result = await toolRegistry.execute('search_drugs', 1, {
      drug_name: 'NonexistentDrug12345',
    });
    assert.ok(result.includes('not found'), `Expected not found, got: ${result}`);
  });
});

describe('Pharmacy Tools - manage_reservation', () => {
  it('should create reservation', async () => {
    const result = await toolRegistry.execute('manage_reservation', 1, {
      action: 'create',
      drug_name: 'Ibuprofen',
      patient_name: 'Jan Novak',
      patient_email: 'jan@example.com',
    });
    assert.ok(result.includes('Reservation created'), `Expected creation, got: ${result}`);
    assert.ok(result.includes('RES-'), `Expected reservation ID, got: ${result}`);
    assert.ok(result.includes('Jan Novak'), `Expected patient name, got: ${result}`);
  });

  it('should check reservation', async () => {
    const result = await toolRegistry.execute('manage_reservation', 1, {
      action: 'check',
      drug_name: 'Ibuprofen',
      patient_name: 'Jan Novak',
      patient_email: 'jan@example.com',
    });
    assert.ok(
      result.includes('No active reservations'),
      `Expected no reservations, got: ${result}`
    );
  });

  it('should cancel reservation', async () => {
    const result = await toolRegistry.execute('manage_reservation', 1, {
      action: 'cancel',
      drug_name: 'Ibuprofen',
      patient_name: 'Jan Novak',
      patient_email: 'jan@example.com',
    });
    assert.ok(
      result.includes('No active reservation found'),
      `Expected no reservation, got: ${result}`
    );
  });
});

describe('Pharmacy Tools - web_search', () => {
  it('should return search results placeholder', async () => {
    const result = await toolRegistry.execute('web_search', 1, {
      query: 'Ibuprofen side effects',
    });
    assert.ok(result.includes('Web search results'), `Expected results, got: ${result}`);
    assert.ok(
      result.includes('Ibuprofen side effects'),
      `Expected query in results, got: ${result}`
    );
  });
});

// ---------------------------------------------------------------------------
// Full registration verification
// ---------------------------------------------------------------------------

describe('Full Tool Registration', () => {
  it('should have all 6 tools registered', () => {
    const tools = toolRegistry.getRegisteredTools();

    assert.ok(tools.includes('send_reply'), 'Missing send_reply');
    assert.ok(tools.includes('create_draft'), 'Missing create_draft');
    assert.ok(tools.includes('escalate'), 'Missing escalate');
    assert.ok(tools.includes('search_drugs'), 'Missing search_drugs');
    assert.ok(tools.includes('manage_reservation'), 'Missing manage_reservation');
    assert.ok(tools.includes('web_search'), 'Missing web_search');
  });

  it('should return definitions for all pharmacy profile tools', () => {
    const definitions = toolRegistry.getDefinitions([
      'send_reply',
      'create_draft',
      'escalate',
      'search_drugs',
      'manage_reservation',
      'web_search',
    ]);

    assert.strictEqual(definitions.length, 6);

    const names = definitions.map((d) => d.function.name);
    assert.deepStrictEqual(names, [
      'send_reply',
      'create_draft',
      'escalate',
      'search_drugs',
      'manage_reservation',
      'web_search',
    ]);
  });
});
