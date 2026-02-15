import type { Job, JobType, JobPayload } from "../types.js";

export interface JobQueue {
  enqueue(
    jobType: JobType,
    userId: number,
    payload: JobPayload,
    maxAttempts?: number
  ): Promise<number>;
  claim(): Promise<Job | null>;
  complete(jobId: number): Promise<void>;
  fail(jobId: number, errorMessage: string): Promise<void>;
  retry(jobId: number, errorMessage: string): Promise<void>;
  cleanup(daysOld: number): Promise<number>;
  hasPendingJob(userId: number, jobType: JobType, threadId?: string): Promise<boolean>;
}
