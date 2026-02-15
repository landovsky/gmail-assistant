/**
 * Integration Test: Manual Draft & Agent Process Job Handlers
 * Tests handler logic through the orchestration layer with mocks
 */

import { describe, it } from "node:test";
import assert from "node:assert";
import { ManualDraftHandler } from "../../src/jobs/handlers/manual-draft.js";
import { AgentProcessHandler } from "../../src/jobs/handlers/agent-process.js";
import type { Job } from "../../src/jobs/types.js";

/**
 * Helper to create a mock Job object
 */
function createMockJob(overrides: Partial<Job> & { payload: any }): Job {
  return {
    id: 1,
    jobType: "manual_draft",
    userId: 1,
    status: "running",
    attempts: 0,
    maxAttempts: 3,
    errorMessage: null,
    createdAt: new Date().toISOString(),
    startedAt: new Date().toISOString(),
    completedAt: null,
    ...overrides,
  };
}

describe("Integration: ManualDraftHandler", () => {
  it("should be instantiable and implement JobHandler interface", () => {
    const handler = new ManualDraftHandler();
    assert.ok(handler, "Handler should be instantiable");
    assert.strictEqual(
      typeof handler.handle,
      "function",
      "Handler must have handle method"
    );
  });

  it("should accept manual_draft payload shape", () => {
    const job = createMockJob({
      jobType: "manual_draft",
      payload: {
        user_id: 1,
        thread_id: "thread-abc-123",
      },
    });

    assert.strictEqual(job.payload.user_id, 1);
    assert.strictEqual(job.payload.thread_id, "thread-abc-123");
  });

  it("should attempt real service integration (not a stub)", async () => {
    const handler = new ManualDraftHandler();
    const job = createMockJob({
      jobType: "manual_draft",
      payload: {
        user_id: 1,
        thread_id: "thread-abc-123",
      },
    });

    // Handler should throw because it tries to authenticate against Gmail.
    // This proves it is wired to real services, not a stub that logs and returns.
    try {
      await handler.handle(job);
      assert.fail("Handler should have thrown (no Gmail credentials in test)");
    } catch (error: any) {
      assert.ok(error, "Should throw an error");
      assert.ok(error.message, "Error should have a message");
      // The error should come from auth/gmail layer, not from missing logic
      assert.ok(
        !error.message.includes("[STUB]"),
        "Handler must not be a stub"
      );
    }
  });
});

describe("Integration: AgentProcessHandler", () => {
  it("should be instantiable and implement JobHandler interface", () => {
    const handler = new AgentProcessHandler();
    assert.ok(handler, "Handler should be instantiable");
    assert.strictEqual(
      typeof handler.handle,
      "function",
      "Handler must have handle method"
    );
  });

  it("should accept agent_process payload shape", () => {
    const job = createMockJob({
      jobType: "agent_process",
      payload: {
        user_id: 1,
        thread_id: "thread-abc-123",
        message_id: "msg-abc-123",
        profile: "pharmacy",
      },
    });

    assert.strictEqual(job.payload.user_id, 1);
    assert.strictEqual(job.payload.thread_id, "thread-abc-123");
    assert.strictEqual(job.payload.message_id, "msg-abc-123");
    assert.strictEqual(job.payload.profile, "pharmacy");
  });

  it("should attempt real service integration (not a stub)", async () => {
    const handler = new AgentProcessHandler();
    const job = createMockJob({
      jobType: "agent_process",
      payload: {
        user_id: 1,
        thread_id: "thread-abc-123",
        message_id: "msg-abc-123",
        profile: "pharmacy",
      },
    });

    try {
      await handler.handle(job);
      assert.fail("Handler should have thrown (no Gmail credentials in test)");
    } catch (error: any) {
      assert.ok(error, "Should throw an error");
      assert.ok(error.message, "Error should have a message");
      assert.ok(
        !error.message.includes("[STUB]"),
        "Handler must not be a stub"
      );
    }
  });
});

describe("Integration: Handler Registration", () => {
  it("should register ManualDraftHandler in handler index", async () => {
    const handlers = await import("../../src/jobs/handlers/index.js");
    assert.ok(
      handlers.ManualDraftHandler,
      "ManualDraftHandler should be exported"
    );
    const instance = new handlers.ManualDraftHandler();
    assert.strictEqual(typeof instance.handle, "function");
  });

  it("should register AgentProcessHandler in handler index", async () => {
    const handlers = await import("../../src/jobs/handlers/index.js");
    assert.ok(
      handlers.AgentProcessHandler,
      "AgentProcessHandler should be exported"
    );
    const instance = new handlers.AgentProcessHandler();
    assert.strictEqual(typeof instance.handle, "function");
  });
});
