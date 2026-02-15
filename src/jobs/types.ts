// Job type enum
export type JobType =
  | "sync"
  | "classify"
  | "draft"
  | "cleanup"
  | "rework"
  | "manual_draft"
  | "agent_process";

// Job status enum
export type JobStatus = "pending" | "running" | "completed" | "failed";

// Job payloads for each job type
export interface SyncPayload {
  user_id: number;
  history_id?: string;
  force_full?: boolean;
  action?: "detect_sent";
  thread_id?: string;
  email_id?: number;
}

export interface ClassifyPayload {
  user_id: number;
  thread_id: string;
  message_id: string;
  force?: boolean;
}

export interface DraftPayload {
  user_id: number;
  email_id: number;
}

export interface CleanupPayload {
  user_id: number;
  thread_id: string;
  email_id: number;
}

export interface ReworkPayload {
  user_id: number;
  thread_id: string;
  email_id: number;
}

export interface ManualDraftPayload {
  user_id: number;
  thread_id: string;
}

export interface AgentProcessPayload {
  user_id: number;
  thread_id: string;
  message_id: string;
  profile: string;
}

// Union type for all payloads
export type JobPayload =
  | SyncPayload
  | ClassifyPayload
  | DraftPayload
  | CleanupPayload
  | ReworkPayload
  | ManualDraftPayload
  | AgentProcessPayload;

// Job interface
export interface Job {
  id: number;
  jobType: JobType;
  userId: number;
  payload: JobPayload;
  status: JobStatus;
  attempts: number;
  maxAttempts: number;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

// Job handler interface
export interface JobHandler {
  handle(job: Job): Promise<void>;
}
