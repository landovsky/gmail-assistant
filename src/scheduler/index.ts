import { appConfig } from "../config/index.js";
import { getJobQueue } from "../jobs/queue/index.js";
import { getDb, schema } from "../db/index.js";
import { eq } from "drizzle-orm";

export class Scheduler {
  private intervals: NodeJS.Timeout[] = [];
  private running = false;
  private queue = getJobQueue();
  private db = getDb();

  async start() {
    if (this.running) {
      console.warn("Scheduler already running");
      return;
    }

    this.running = true;
    console.log("Starting scheduler");

    // Watch renewal - every 24 hours
    const watchInterval = setInterval(
      () => this.renewWatches(),
      appConfig.scheduler.watchRenewalInterval
    );
    this.intervals.push(watchInterval);

    // Fallback sync - every 15 minutes
    const fallbackInterval = setInterval(
      () => this.fallbackSync(),
      appConfig.scheduler.fallbackSyncInterval
    );
    this.intervals.push(fallbackInterval);

    // Full sync - every 1 hour
    const fullSyncInterval = setInterval(
      () => this.fullSync(),
      appConfig.scheduler.fullSyncInterval
    );
    this.intervals.push(fullSyncInterval);

    // Job cleanup - daily at 3am (approximate)
    const cleanupInterval = setInterval(
      () => this.cleanupJobs(),
      24 * 60 * 60 * 1000
    );
    this.intervals.push(cleanupInterval);

    console.log("Scheduler started with 4 periodic tasks");
  }

  async stop() {
    if (!this.running) {
      return;
    }

    console.log("Stopping scheduler");
    this.running = false;

    for (const interval of this.intervals) {
      clearInterval(interval);
    }

    this.intervals = [];
  }

  private async renewWatches() {
    console.log("[Scheduler] Running watch renewal");
    
    try {
      // TODO: Implement by gmail-worker
      // This will call Gmail API to renew push notification watches
      // For now, just log
      console.log("[Scheduler] Watch renewal not yet implemented");
    } catch (error) {
      console.error("[Scheduler] Watch renewal failed:", error);
    }
  }

  private async fallbackSync() {
    console.log("[Scheduler] Running fallback sync");
    
    try {
      const activeUsers = await this.db
        .select({ id: schema.users.id })
        .from(schema.users)
        .where(eq(schema.users.isActive, true));

      for (const user of activeUsers) {
        // Check if there's already a pending sync job
        const hasPending = await this.queue.hasPendingJob(user.id, "sync");
        if (!hasPending) {
          await this.queue.enqueue("sync", user.id, {
            user_id: user.id,
            force_full: false,
          });
        }
      }

      console.log(`[Scheduler] Enqueued fallback sync for ${activeUsers.length} users`);
    } catch (error) {
      console.error("[Scheduler] Fallback sync failed:", error);
    }
  }

  private async fullSync() {
    console.log("[Scheduler] Running full sync");
    
    try {
      const activeUsers = await this.db
        .select({ id: schema.users.id })
        .from(schema.users)
        .where(eq(schema.users.isActive, true));

      for (const user of activeUsers) {
        // Full sync scans entire inbox
        await this.queue.enqueue("sync", user.id, {
          user_id: user.id,
          force_full: true,
        });
      }

      console.log(`[Scheduler] Enqueued full sync for ${activeUsers.length} users`);
    } catch (error) {
      console.error("[Scheduler] Full sync failed:", error);
    }
  }

  private async cleanupJobs() {
    console.log("[Scheduler] Running job cleanup");
    
    try {
      const deleted = await this.queue.cleanup(7); // 7 days retention
      console.log(`[Scheduler] Deleted ${deleted} old jobs`);
    } catch (error) {
      console.error("[Scheduler] Job cleanup failed:", error);
    }
  }
}

// Singleton instance
let schedulerInstance: Scheduler | null = null;

export function getScheduler(): Scheduler {
  if (!schedulerInstance) {
    schedulerInstance = new Scheduler();
  }
  return schedulerInstance;
}
