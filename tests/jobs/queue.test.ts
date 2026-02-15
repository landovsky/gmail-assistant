import { describe, it, beforeEach, expect } from "bun:test";
import { SQLiteJobQueue } from "../../src/jobs/queue/sqlite";
import { runMigrations } from "../../src/db/migrate";
import { unlinkSync, existsSync } from "fs";

const TEST_DB = "./data/test-queue.db";

describe("SQLiteJobQueue", () => {
  let queue: SQLiteJobQueue;

  beforeEach(() => {
    // Clean up test database
    if (existsSync(TEST_DB)) {
      unlinkSync(TEST_DB);
    }
    if (existsSync(`${TEST_DB}-shm`)) {
      unlinkSync(`${TEST_DB}-shm`);
    }
    if (existsSync(`${TEST_DB}-wal`)) {
      unlinkSync(`${TEST_DB}-wal`);
    }

    // Set test database
    process.env.DATABASE_URL = TEST_DB;

    // Run migrations
    runMigrations(TEST_DB);

    // Create queue instance
    queue = new SQLiteJobQueue();
  });

  it("should enqueue a job", async () => {
    const jobId = await queue.enqueue("sync", 1, {
      user_id: 1,
      force_full: false,
    });

    expect(jobId).toBeGreaterThan(0);
  });

  it("should claim a pending job", async () => {
    await queue.enqueue("sync", 1, {
      user_id: 1,
      force_full: false,
    });

    const job = await queue.claim();

    expect(job).not.toBeNull();
    expect(job?.jobType).toBe("sync");
    expect(job?.status).toBe("running");
  });

  it("should not claim the same job twice", async () => {
    await queue.enqueue("sync", 1, {
      user_id: 1,
      force_full: false,
    });

    const job1 = await queue.claim();
    const job2 = await queue.claim();

    expect(job1).not.toBeNull();
    expect(job2).toBeNull();
  });

  it("should complete a job", async () => {
    const jobId = await queue.enqueue("sync", 1, {
      user_id: 1,
      force_full: false,
    });

    const job = await queue.claim();
    expect(job).not.toBeNull();

    await queue.complete(jobId);

    const nextJob = await queue.claim();
    expect(nextJob).toBeNull();
  });

  it("should retry a failed job", async () => {
    const jobId = await queue.enqueue("sync", 1, {
      user_id: 1,
      force_full: false,
    });

    const job = await queue.claim();
    expect(job).not.toBeNull();

    await queue.retry(jobId, "Test error");

    const retriedJob = await queue.claim();
    expect(retriedJob).not.toBeNull();
    expect(retriedJob?.id).toBe(jobId);
    expect(retriedJob?.attempts).toBe(1);
  });

  it("should fail a job permanently after max attempts", async () => {
    const jobId = await queue.enqueue("sync", 1, {
      user_id: 1,
      force_full: false,
    }, 1); // max_attempts = 1

    const job = await queue.claim();
    expect(job).not.toBeNull();

    await queue.retry(jobId, "Test error");

    const nextJob = await queue.claim();
    expect(nextJob).toBeNull(); // Job should not be claimed again
  });

  it("should detect pending jobs", async () => {
    await queue.enqueue("classify", 1, {
      user_id: 1,
      thread_id: "thread123",
      message_id: "msg123",
    });

    const hasPending = await queue.hasPendingJob(1, "classify", "thread123");
    expect(hasPending).toBe(true);

    const hasOther = await queue.hasPendingJob(1, "classify", "other");
    expect(hasOther).toBe(false);
  });

  it("should cleanup old jobs", async () => {
    const jobId = await queue.enqueue("sync", 1, {
      user_id: 1,
      force_full: false,
    });

    const job = await queue.claim();
    await queue.complete(jobId);

    // This won't delete anything since job is recent
    const deleted = await queue.cleanup(7);
    expect(deleted).toBe(0);
  });
});
