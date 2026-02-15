import type { JobHandler } from "../types.js";
import type { Job, SyncPayload } from "../types.js";

export class SyncHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as SyncPayload;
    
    // TODO: Implement by gmail-worker
    // This will:
    // 1. Fetch Gmail changes since last sync using History API
    // 2. Route new messages to classify or agent_process jobs
    // 3. Handle label changes (Done, Rework, Needs Response)
    // 4. Update sync state with new history ID
    
    console.log(`[STUB] Sync job for user ${payload.user_id}, history_id: ${payload.history_id}, force_full: ${payload.force_full}`);
  }
}
