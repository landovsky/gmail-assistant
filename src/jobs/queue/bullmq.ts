import { Queue, Worker, Job as BullJob } from "bullmq";
import { appConfig } from "../../config/index.js";
import type { JobQueue } from "./interface.js";
import type { Job, JobType, JobPayload } from "../types.js";

export class BullMQJobQueue implements JobQueue {
  private queue: Queue;
  private connection;

  constructor() {
    if (!appConfig.queue.redis) {
      throw new Error("Redis config required for BullMQ");
    }

    this.connection = {
      host: appConfig.queue.redis.host,
      port: appConfig.queue.redis.port,
    };

    this.queue = new Queue("gmail-assistant", {
      connection: this.connection,
    });
  }

  async enqueue(
    jobType: JobType,
    userId: number,
    payload: JobPayload,
    maxAttempts: number = 3
  ): Promise<number> {
    const job = await this.queue.add(
      jobType,
      {
        jobType,
        userId,
        payload,
      },
      {
        attempts: maxAttempts,
        backoff: {
          type: "exponential",
          delay: 1000,
        },
      }
    );

    return parseInt(job.id || "0");
  }

  async claim(): Promise<Job | null> {
    // BullMQ handles claiming automatically through workers
    // This method is not used with BullMQ
    throw new Error("claim() not supported with BullMQ - use Worker instead");
  }

  async complete(jobId: number): Promise<void> {
    // BullMQ handles completion automatically
  }

  async fail(jobId: number, errorMessage: string): Promise<void> {
    // BullMQ handles failures automatically
  }

  async retry(jobId: number, errorMessage: string): Promise<void> {
    // BullMQ handles retries automatically
  }

  async cleanup(daysOld: number): Promise<number> {
    const cutoffDate = Date.now() - daysOld * 24 * 60 * 60 * 1000;
    const jobs = await this.queue.getJobs(["completed", "failed"]);
    
    let cleaned = 0;
    for (const job of jobs) {
      if (job.finishedOn && job.finishedOn < cutoffDate) {
        await job.remove();
        cleaned++;
      }
    }

    return cleaned;
  }

  async hasPendingJob(
    userId: number,
    jobType: JobType,
    threadId?: string
  ): Promise<boolean> {
    const waitingJobs = await this.queue.getJobs(["waiting", "active"]);
    
    return waitingJobs.some((job) => {
      const data = job.data;
      if (data.userId !== userId || data.jobType !== jobType) {
        return false;
      }
      if (threadId && data.payload.thread_id !== threadId) {
        return false;
      }
      return true;
    });
  }

  getQueue() {
    return this.queue;
  }

  getConnection() {
    return this.connection;
  }
}
