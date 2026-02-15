import { SyncHandler } from "./sync.js";
import { ClassifyHandler } from "./classify.js";
import { DraftHandler } from "./draft.js";
import { CleanupHandler } from "./cleanup.js";
import { ReworkHandler } from "./rework.js";
import { ManualDraftHandler } from "./manual-draft.js";
import { AgentProcessHandler } from "./agent-process.js";
import type { JobHandler, JobType } from "../types.js";

const handlers: Record<JobType, JobHandler> = {
  sync: new SyncHandler(),
  classify: new ClassifyHandler(),
  draft: new DraftHandler(),
  cleanup: new CleanupHandler(),
  rework: new ReworkHandler(),
  manual_draft: new ManualDraftHandler(),
  agent_process: new AgentProcessHandler(),
};

export function getJobHandler(jobType: JobType): JobHandler {
  const handler = handlers[jobType];
  if (!handler) {
    throw new Error(`No handler registered for job type: ${jobType}`);
  }
  return handler;
}

export { SyncHandler, ClassifyHandler, DraftHandler, CleanupHandler, ReworkHandler, ManualDraftHandler, AgentProcessHandler };
