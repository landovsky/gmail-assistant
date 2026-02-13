-- Migration: Agent Runs
-- Adds agent_runs table to track agent execution for debugging and audit.
-- For existing databases, also recreates llm_calls to allow the new 'agent' call_type.

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    gmail_thread_id TEXT NOT NULL,
    profile TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'error', 'max_iterations')),
    tool_calls_log TEXT DEFAULT '[]',  -- JSON array of tool call records
    final_message TEXT,
    iterations INTEGER DEFAULT 0,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_thread ON agent_runs(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);

-- Recreate llm_calls with updated CHECK constraint to allow 'agent' call_type.
-- SQLite does not support ALTER CHECK, so we recreate the table preserving data.
CREATE TABLE IF NOT EXISTS llm_calls_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    gmail_thread_id TEXT,
    call_type TEXT NOT NULL CHECK (call_type IN ('classify', 'draft', 'rework', 'context', 'agent')),
    model TEXT NOT NULL,
    system_prompt TEXT,
    user_message TEXT,
    response_text TEXT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO llm_calls_new SELECT * FROM llm_calls;
DROP TABLE IF EXISTS llm_calls;
ALTER TABLE llm_calls_new RENAME TO llm_calls;

CREATE INDEX IF NOT EXISTS idx_llm_calls_thread ON llm_calls(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_type ON llm_calls(call_type);
CREATE INDEX IF NOT EXISTS idx_llm_calls_user ON llm_calls(user_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_created ON llm_calls(created_at);
