-- Migration: LLM Call Logging
-- Adds llm_calls table to track all LLM API calls for debugging and cost monitoring

CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    gmail_thread_id TEXT,
    call_type TEXT NOT NULL CHECK (call_type IN ('classify', 'draft', 'rework', 'context')),
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

-- Index for quick lookups by thread
CREATE INDEX IF NOT EXISTS idx_llm_calls_thread ON llm_calls(gmail_thread_id);

-- Index for filtering by call type
CREATE INDEX IF NOT EXISTS idx_llm_calls_type ON llm_calls(call_type);

-- Index for user-specific queries
CREATE INDEX IF NOT EXISTS idx_llm_calls_user ON llm_calls(user_id);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_llm_calls_created ON llm_calls(created_at);
