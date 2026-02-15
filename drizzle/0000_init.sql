-- Users table
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  onboarded_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Emails table
CREATE TABLE emails (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  gmail_thread_id TEXT NOT NULL,
  gmail_message_id TEXT NOT NULL,
  sender_email TEXT NOT NULL,
  sender_name TEXT,
  subject TEXT,
  snippet TEXT,
  received_at TEXT,
  classification TEXT NOT NULL CHECK(classification IN ('needs_response', 'action_required', 'payment_request', 'fyi', 'waiting')),
  confidence TEXT NOT NULL DEFAULT 'medium' CHECK(confidence IN ('high', 'medium', 'low')),
  reasoning TEXT,
  detected_language TEXT NOT NULL DEFAULT 'cs',
  resolved_style TEXT NOT NULL DEFAULT 'business',
  message_count INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'drafted', 'rework_requested', 'sent', 'skipped', 'archived')),
  draft_id TEXT,
  rework_count INTEGER NOT NULL DEFAULT 0,
  last_rework_instruction TEXT,
  vendor_name TEXT,
  processed_at TEXT NOT NULL DEFAULT (datetime('now')),
  drafted_at TEXT,
  acted_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, gmail_thread_id)
);

CREATE INDEX idx_emails_user_classification ON emails(user_id, classification);
CREATE INDEX idx_emails_user_status ON emails(user_id, status);
CREATE INDEX idx_emails_thread_id ON emails(gmail_thread_id);

-- User Labels table
CREATE TABLE user_labels (
  user_id INTEGER NOT NULL REFERENCES users(id),
  label_key TEXT NOT NULL,
  gmail_label_id TEXT NOT NULL,
  gmail_label_name TEXT NOT NULL,
  PRIMARY KEY (user_id, label_key)
);

-- User Settings table
CREATE TABLE user_settings (
  user_id INTEGER NOT NULL REFERENCES users(id),
  setting_key TEXT NOT NULL,
  setting_value TEXT NOT NULL,
  PRIMARY KEY (user_id, setting_key)
);

-- Sync State table
CREATE TABLE sync_state (
  user_id INTEGER PRIMARY KEY NOT NULL REFERENCES users(id),
  last_history_id TEXT NOT NULL DEFAULT '0',
  last_sync_at TEXT NOT NULL DEFAULT (datetime('now')),
  watch_expiration TEXT,
  watch_resource_id TEXT
);

-- Jobs table
CREATE TABLE jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_type TEXT NOT NULL CHECK(job_type IN ('sync', 'classify', 'draft', 'cleanup', 'rework', 'manual_draft', 'agent_process')),
  user_id INTEGER NOT NULL REFERENCES users(id),
  payload TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  started_at TEXT,
  completed_at TEXT
);

CREATE INDEX idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX idx_jobs_user_type ON jobs(user_id, job_type);

-- Email Events table
CREATE TABLE email_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  gmail_thread_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK(event_type IN ('classified', 'label_added', 'label_removed', 'draft_created', 'draft_trashed', 'draft_reworked', 'sent_detected', 'archived', 'rework_limit_reached', 'waiting_retriaged', 'error')),
  detail TEXT,
  label_id TEXT,
  draft_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_email_events_user_thread ON email_events(user_id, gmail_thread_id);
CREATE INDEX idx_email_events_type ON email_events(event_type);

-- LLM Calls table
CREATE TABLE llm_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  gmail_thread_id TEXT,
  call_type TEXT NOT NULL CHECK(call_type IN ('classify', 'draft', 'rework', 'context', 'agent')),
  model TEXT NOT NULL,
  system_prompt TEXT,
  user_message TEXT,
  response_text TEXT,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_llm_calls_thread ON llm_calls(gmail_thread_id);
CREATE INDEX idx_llm_calls_type ON llm_calls(call_type);
CREATE INDEX idx_llm_calls_user ON llm_calls(user_id);
CREATE INDEX idx_llm_calls_created ON llm_calls(created_at);

-- Agent Runs table
CREATE TABLE agent_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  gmail_thread_id TEXT NOT NULL,
  profile TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running', 'completed', 'error', 'max_iterations')),
  tool_calls_log TEXT NOT NULL DEFAULT '[]',
  final_message TEXT,
  iterations INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  completed_at TEXT
);

CREATE INDEX idx_agent_runs_user ON agent_runs(user_id);
CREATE INDEX idx_agent_runs_thread ON agent_runs(gmail_thread_id);
CREATE INDEX idx_agent_runs_status ON agent_runs(status);
