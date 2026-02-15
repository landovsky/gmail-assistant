import { appConfig } from "../config/index.js";
import { getJobQueue } from "./queue/index.js";
import { getJobHandler, initializeHandlers } from "./handlers/index.js";
import type { Job } from "./types.js";

export class WorkerPool {
  private workers: Worker[] = [];
  private running = false;

  async start() {
    if (this.running) {
      console.warn("Worker pool already running");
      return;
    }

    this.running = true;
    const workerCount = appConfig.queue.workers;

    // Initialize handlers with queue instance
    const queue = getJobQueue();
    initializeHandlers(queue);

    console.log(`Starting worker pool with ${workerCount} workers`);

    for (let i = 0; i < workerCount; i++) {
      const worker = new Worker(i);
      this.workers.push(worker);
      worker.start();
    }
  }

  async stop() {
    if (!this.running) {
      return;
    }

    console.log("Stopping worker pool");
    this.running = false;

    for (const worker of this.workers) {
      worker.stop();
    }

    this.workers = [];
  }
}

class Worker {
  private id: number;
  private running = false;
  private queue = getJobQueue();

  constructor(id: number) {
    this.id = id;
  }

  start() {
    this.running = true;
    this.loop();
  }

  stop() {
    this.running = false;
  }

  private async loop() {
    while (this.running) {
      try {
        const job = await this.queue.claim();

        if (!job) {
          // Queue empty, sleep for 1 second
          await new Promise((resolve) => setTimeout(resolve, 1000));
          continue;
        }

        console.log(`[Worker ${this.id}] Processing job ${job.id} (${job.jobType})`);

        await this.processJob(job);
      } catch (error) {
        console.error(`[Worker ${this.id}] Error in worker loop:`, error);
        // Sleep briefly before retrying
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    }
  }

  private async processJob(job: Job) {
    try {
      const handler = getJobHandler(job.jobType);
      await handler.handle(job);

      // Job succeeded
      await this.queue.complete(job.id);
      console.log(`[Worker ${this.id}] Job ${job.id} completed successfully`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`[Worker ${this.id}] Job ${job.id} failed:`, errorMessage);

      // Check if we should retry
      if (job.attempts + 1 < job.maxAttempts) {
        // Retry
        await this.queue.retry(job.id, errorMessage);
        console.log(`[Worker ${this.id}] Job ${job.id} will retry (attempt ${job.attempts + 1}/${job.maxAttempts})`);
      } else {
        // Permanent failure
        await this.queue.fail(job.id, errorMessage);
        console.error(`[Worker ${this.id}] Job ${job.id} failed permanently after ${job.attempts + 1} attempts`);
      }
    }
  }
}

// Singleton instance
let workerPoolInstance: WorkerPool | null = null;

export function getWorkerPool(): WorkerPool {
  if (!workerPoolInstance) {
    workerPoolInstance = new WorkerPool();
  }
  return workerPoolInstance;
}
