import type { JobHandler } from "../types.js";
import type { Job, ClassifyPayload } from "../types.js";

export class ClassifyHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as ClassifyPayload;
    
    // TODO: Implement by llm-worker
    // This will:
    // 1. Run automation detection rules
    // 2. Call LLM for classification if not auto-detected
    // 3. Create email record with classification
    // 4. Enqueue draft job if needs_response
    
    console.log(`[STUB] Classify job for thread ${payload.thread_id}, message ${payload.message_id}`);
  }
}
