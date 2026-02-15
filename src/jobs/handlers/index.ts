import { SyncHandler } from "./sync.js";
import { ClassifyHandler } from "./classify.js";
import { DraftHandler } from "./draft.js";
import { CleanupHandler } from "./cleanup.js";
import { ReworkHandler } from "./rework.js";
import { ManualDraftHandler } from "./manual-draft.js";
import { AgentProcessHandler } from "./agent-process.js";
import type { JobHandler, JobType } from "../types.js";
import type { JobQueue } from "../queue/interface.js";

let handlersInstance: Record<JobType, JobHandler> | null = null;

export function initializeHandlers(queue: JobQueue): void {
  handlersInstance = {
    sync: new SyncHandler(queue),
    classify: new ClassifyHandler(queue),
    draft: new DraftHandler(),
    cleanup: new CleanupHandler(),
    rework: new ReworkHandler(),
    manual_draft: new ManualDraftHandler(),
    agent_process: new AgentProcessHandler(),
  };
}

export function getJobHandler(jobType: JobType): JobHandler {
  if (!handlersInstance) {
    throw new Error("Handlers not initialized. Call initializeHandlers() first.");
  }

  const handler = handlersInstance[jobType];
  if (!handler) {
    throw new Error(`No handler registered for job type: ${jobType}`);
  }
  return handler;
}

export { SyncHandler, ClassifyHandler, DraftHandler, CleanupHandler, ReworkHandler, ManualDraftHandler, AgentProcessHandler };
