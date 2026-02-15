import type { JobHandler } from "../types.js";
import type { Job, DraftPayload } from "../types.js";

export class DraftHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as DraftPayload;
    
    // TODO: Implement by llm-worker + gmail-worker
    // This will:
    // 1. Gather context for draft generation
    // 2. Call LLM to generate draft
    // 3. Create Gmail draft via API
    // 4. Update email record with draft_id and status
    // 5. Apply Outbox label
    
    console.log(`[STUB] Draft job for email ${payload.email_id}`);
  }
}
