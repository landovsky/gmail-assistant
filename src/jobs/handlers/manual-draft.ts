import type { JobHandler } from "../types.js";
import type { Job, ManualDraftPayload } from "../types.js";

export class ManualDraftHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as ManualDraftPayload;
    
    // TODO: Implement by llm-worker + gmail-worker
    // This will:
    // 1. Check if email already drafted
    // 2. Create DB record if doesn't exist
    // 3. Generate draft same as draft job
    
    console.log(`[STUB] Manual draft job for thread ${payload.thread_id}`);
  }
}
