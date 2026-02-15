import type { JobHandler } from "../types.js";
import type { Job, CleanupPayload } from "../types.js";

export class CleanupHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as CleanupPayload;
    
    // TODO: Implement by gmail-worker
    // This will:
    // - If action=done: Archive thread, update status to archived
    // - If action=check_sent: Detect if draft was sent, update status
    
    console.log(`[STUB] Cleanup job for thread ${payload.thread_id}, action: ${payload.action}`);
  }
}
