import type { JobHandler } from "../types.js";
import type { Job, ReworkPayload } from "../types.js";

export class ReworkHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as ReworkPayload;
    
    // TODO: Implement by llm-worker + gmail-worker
    // This will:
    // 1. Extract user instructions from draft
    // 2. Check rework_count < 3
    // 3. Regenerate draft with feedback
    // 4. Update rework_count
    // 5. If limit reached, move to Action Required
    
    console.log(`[STUB] Rework job for thread ${payload.thread_id}`);
  }
}
