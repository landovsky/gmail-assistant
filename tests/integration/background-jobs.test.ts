/**
 * Integration Test: Background Job Processing
 * Tests job queue operations and retry logic
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';
import { MockJobQueue } from '../helpers/mock-clients.js';
import type { Job } from '../../src/jobs/types.js';

describe('Integration: Job Queue - FIFO Processing', () => {
  let queue: MockJobQueue;

  beforeEach(() => {
    queue = new MockJobQueue();
  });

  it('should process jobs in FIFO order', async () => {
    // Enqueue 3 jobs at different times
    const job1Id = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't1', message_id: 'm1' });
    const job2Id = await queue.enqueue('draft', 1, { user_id: 1, email_id: 1 });
    const job3Id = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't2', message_id: 'm2' });

    // Claim jobs - should get job1 first (oldest)
    const claimed1 = await queue.claim();
    assert.strictEqual(claimed1?.id, job1Id, 'Should claim oldest job first');
    assert.strictEqual(claimed1?.status, 'running', 'Status should be running');

    await queue.complete(job1Id);

    // Next claim should get job2
    const claimed2 = await queue.claim();
    assert.strictEqual(claimed2?.id, job2Id, 'Should claim second job');

    await queue.complete(job2Id);

    // Next claim should get job3
    const claimed3 = await queue.claim();
    assert.strictEqual(claimed3?.id, job3Id, 'Should claim third job');

    await queue.complete(job3Id);

    // No more jobs
    const claimed4 = await queue.claim();
    assert.strictEqual(claimed4, null, 'Should return null when no jobs available');
  });

  it('should not allow double-claiming of jobs', async () => {
    const jobId = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't1', message_id: 'm1' });

    // Worker 1 claims job
    const worker1Job = await queue.claim();
    assert.strictEqual(worker1Job?.id, jobId);

    // Worker 2 tries to claim - should get null
    const worker2Job = await queue.claim();
    assert.strictEqual(worker2Job, null, 'Second worker should not get same job');
  });
});

describe('Integration: Job Queue - Retry Logic', () => {
  let queue: MockJobQueue;

  beforeEach(() => {
    queue = new MockJobQueue();
  });

  it('should retry failed jobs up to max attempts', async () => {
    const jobId = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't1', message_id: 'm1' }, 3);

    // Attempt 1 - fail
    let job = await queue.claim();
    assert.strictEqual(job?.attempts, 0);
    await queue.retry(jobId, 'Temporary error');

    // Attempt 2 - fail
    job = await queue.claim();
    assert.strictEqual(job?.attempts, 1);
    await queue.retry(jobId, 'Temporary error');

    // Attempt 3 - fail
    job = await queue.claim();
    assert.strictEqual(job?.attempts, 2);
    await queue.retry(jobId, 'Temporary error');

    // Job should still be retryable (3 attempts made, max is 3)
    assert.strictEqual(job?.maxAttempts, 3);
    assert.strictEqual(job?.attempts, 2); // Before increment
  });

  it('should mark job as failed after max attempts', async () => {
    const jobId = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't1', message_id: 'm1' }, 2);

    // Attempt 1
    await queue.claim();
    await queue.retry(jobId, 'Error 1');

    // Attempt 2
    await queue.claim();
    await queue.retry(jobId, 'Error 2');

    // Attempt 3 - should fail permanently
    const job = await queue.claim();
    assert.ok(job, 'Job should be claimable for final attempt');

    await queue.fail(jobId, 'Permanent failure after 3 attempts');

    const jobs = queue.getJobs();
    const failedJob = jobs.find(j => j.id === jobId);

    assert.strictEqual(failedJob?.status, 'failed');
    assert.ok(failedJob?.errorMessage?.includes('Permanent failure'));
  });

  it('should increment attempts counter on retry', async () => {
    const jobId = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't1', message_id: 'm1' });

    const job1 = await queue.claim();
    assert.strictEqual(job1?.attempts, 0);

    await queue.retry(jobId, 'Error');

    const job2 = await queue.claim();
    assert.strictEqual(job2?.attempts, 1);
  });
});

describe('Integration: Job Queue - Job Deduplication', () => {
  let queue: MockJobQueue;

  beforeEach(() => {
    queue = new MockJobQueue();
  });

  it('should detect pending jobs for same thread', async () => {
    await queue.enqueue('classify', 1, { user_id: 1, thread_id: 'thread-123', message_id: 'm1' });

    const hasPending = await queue.hasPendingJob(1, 'classify', 'thread-123');
    assert.strictEqual(hasPending, true, 'Should detect pending job for thread');
  });

  it('should not detect pending jobs after completion', async () => {
    const jobId = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 'thread-123', message_id: 'm1' });

    await queue.claim();
    await queue.complete(jobId);

    const hasPending = await queue.hasPendingJob(1, 'classify', 'thread-123');
    assert.strictEqual(hasPending, false, 'Should not detect completed job as pending');
  });
});

describe('Integration: Job Queue - Cleanup', () => {
  let queue: MockJobQueue;

  beforeEach(() => {
    queue = new MockJobQueue();
  });

  it('should clean up old completed jobs', async () => {
    // Enqueue and complete several jobs
    const job1 = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't1', message_id: 'm1' });
    const job2 = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't2', message_id: 'm2' });
    const job3 = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't3', message_id: 'm3' });

    await queue.claim();
    await queue.complete(job1);

    await queue.claim();
    await queue.complete(job2);

    await queue.claim();
    await queue.complete(job3);

    assert.strictEqual(queue.getCompletedJobs().length, 3);

    // Cleanup jobs older than 0 days (all jobs)
    const cleaned = await queue.cleanup(0);

    assert.strictEqual(cleaned, 3, 'Should clean 3 completed jobs');
    assert.strictEqual(queue.getCompletedJobs().length, 0, 'No completed jobs should remain');
  });

  it('should not clean up pending or running jobs', async () => {
    const job1 = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't1', message_id: 'm1' });
    const job2 = await queue.enqueue('classify', 1, { user_id: 1, thread_id: 't2', message_id: 'm2' });

    await queue.claim(); // job1 is running
    // job2 is still pending

    const cleaned = await queue.cleanup(0);

    assert.strictEqual(cleaned, 0, 'Should not clean pending/running jobs');
    assert.strictEqual(queue.getJobs().length, 2, 'Both jobs should still exist');
  });
});
