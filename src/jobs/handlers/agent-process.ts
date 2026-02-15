import type { JobHandler } from "../types.js";
import type { Job, AgentProcessPayload } from "../types.js";

export class AgentProcessHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as AgentProcessPayload;
    
    // TODO: Implement by llm-worker
    // This will:
    // 1. Run preprocessor for agent
    // 2. Execute agent loop with tools
    // 3. Log agent run
    // 4. Handle auto-send or escalation
    
    console.log(`[STUB] Agent process job for thread ${payload.thread_id}, profile: ${payload.profile}`);
  }
}
