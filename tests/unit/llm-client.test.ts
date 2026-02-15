/**
 * LLM Client Tests
 * Tests Vercel AI SDK integration with multi-provider support
 */

import { describe, test } from 'node:test';
import assert from 'node:assert';
import { getModel, getModelForOperation } from '../../src/services/llm/client';

describe('LLM Client', () => {
  describe('getModel', () => {
    test('parses anthropic model string', () => {
      const model = getModel('anthropic/claude-3-5-sonnet-20241022');
      assert.ok(model);
      assert.strictEqual(model.modelId, 'claude-3-5-sonnet-20241022');
      assert.strictEqual(model.provider, 'anthropic');
    });

    test('parses openai model string', () => {
      const model = getModel('openai/gpt-4o');
      assert.ok(model);
      assert.strictEqual(model.modelId, 'gpt-4o');
      assert.strictEqual(model.provider, 'openai');
    });

    test('parses google model string', () => {
      const model = getModel('google/gemini-2.0-flash-exp');
      assert.ok(model);
      assert.strictEqual(model.modelId, 'gemini-2.0-flash-exp');
      assert.strictEqual(model.provider, 'google');
    });

    test('throws on invalid format', () => {
      assert.throws(() => getModel('invalid-format'), /Invalid model format/);
    });

    test('throws on unknown provider', () => {
      assert.throws(() => getModel('unknown/model-name'), /Unknown provider/);
    });
  });

  describe('getModelForOperation', () => {
    test('returns classification model from config', () => {
      const model = getModelForOperation('classify');
      assert.ok(model);
      assert.strictEqual(typeof model, 'string');
      assert.ok(model.includes('/'));
    });

    test('returns draft model from config', () => {
      const model = getModelForOperation('draft');
      assert.ok(model);
      assert.strictEqual(typeof model, 'string');
      assert.ok(model.includes('/'));
    });

    test('returns context model from config', () => {
      const model = getModelForOperation('context');
      assert.ok(model);
      assert.strictEqual(typeof model, 'string');
      assert.ok(model.includes('/'));
    });
  });
});
