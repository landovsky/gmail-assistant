import { eq, and, sql, lt } from "drizzle-orm";
import { getDb, schema } from "../../db/index.js";
import type { JobQueue } from "./interface.js";
import type { Job, JobType, JobPayload } from "../types.js";

export class SQLiteJobQueue implements JobQueue {
  private db = getDb();

  async enqueue(
    jobType: JobType,
    userId: number,
    payload: JobPayload,
    maxAttempts: number = 3
  ): Promise<number> {
    const result = await this.db
      .insert(schema.jobs)
      .values({
        jobType,
        userId,
        payload: JSON.stringify(payload),
        maxAttempts,
      })
      .returning({ id: schema.jobs.id });

    return result[0].id;
  }

  async claim(): Promise<Job | null> {
    // Atomic claim using UPDATE RETURNING
    // This is safe for concurrent workers
    const result = await this.db
      .update(schema.jobs)
      .set({
        status: "running",
        startedAt: new Date().toISOString(),
      })
      .where(
        and(
          eq(schema.jobs.status, "pending"),
          lt(schema.jobs.attempts, schema.jobs.maxAttempts)
        )
      )
      .returning()
      .limit(1);

    if (result.length === 0) {
      return null;
    }

    const job = result[0];

    return {
      id: job.id,
      jobType: job.jobType as JobType,
      userId: job.userId,
      payload: JSON.parse(job.payload),
      status: job.status as "running",
      attempts: job.attempts,
      maxAttempts: job.maxAttempts,
      errorMessage: job.errorMessage,
      createdAt: job.createdAt,
      startedAt: job.startedAt,
      completedAt: job.completedAt,
    };
  }

  async complete(jobId: number): Promise<void> {
    await this.db
      .update(schema.jobs)
      .set({
        status: "completed",
        completedAt: new Date().toISOString(),
      })
      .where(eq(schema.jobs.id, jobId));
  }

  async fail(jobId: number, errorMessage: string): Promise<void> {
    await this.db
      .update(schema.jobs)
      .set({
        status: "failed",
        errorMessage,
        completedAt: new Date().toISOString(),
      })
      .where(eq(schema.jobs.id, jobId));
  }

  async retry(jobId: number, errorMessage: string): Promise<void> {
    await this.db
      .update(schema.jobs)
      .set({
        status: "pending",
        attempts: sql`${schema.jobs.attempts} + 1`,
        errorMessage,
      })
      .where(eq(schema.jobs.id, jobId));
  }

  async cleanup(daysOld: number): Promise<number> {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - daysOld);
    const cutoff = cutoffDate.toISOString();

    const result = await this.db
      .delete(schema.jobs)
      .where(
        and(
          sql`${schema.jobs.status} IN ('completed', 'failed')`,
          lt(schema.jobs.completedAt, cutoff)
        )
      )
      .returning({ id: schema.jobs.id });

    return result.length;
  }

  async hasPendingJob(
    userId: number,
    jobType: JobType,
    threadId?: string
  ): Promise<boolean> {
    const conditions = [
      eq(schema.jobs.userId, userId),
      eq(schema.jobs.jobType, jobType),
      sql`${schema.jobs.status} IN ('pending', 'running')`,
    ];

    // If threadId provided, check if payload contains it
    if (threadId) {
      conditions.push(sql`json_extract(${schema.jobs.payload}, '$.thread_id') = ${threadId}`);
    }

    const result = await this.db
      .select({ count: sql<number>`count(*)` })
      .from(schema.jobs)
      .where(and(...conditions));

    return result[0].count > 0;
  }
}
