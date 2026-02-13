-- Gmail Assistant v2 Schema
-- SQLite-first, user-scoped, with sync state and job queue.

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    is_active INTEGER DEFAULT 1,
    onboarded_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Per-user Gmail label IDs (replaces config/label_ids.yml)
CREATE TABLE IF NOT EXISTS user_labels (
    user_id INTEGER NOT NULL REFERENCES users(id),
    label_key TEXT NOT NULL,
    gmail_label_id TEXT NOT NULL,
    gmail_label_name TEXT NOT NULL,
    PRIMARY KEY (user_id, label_key)
);

-- Per-user settings (replaces config/*.yml)
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER NOT NULL REFERENCES users(id),
    setting_key TEXT NOT NULL,
    setting_value TEXT NOT NULL,  -- JSON
    PRIMARY KEY (user_id, setting_key)
);

-- Sync state per user
CREATE TABLE IF NOT EXISTS sync_state (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    last_history_id TEXT NOT NULL DEFAULT '0',
    last_sync_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    watch_expiration DATETIME,
    watch_resource_id TEXT
);

-- Emails table (user-scoped)
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    gmail_thread_id TEXT NOT NULL,
    gmail_message_id TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    sender_name TEXT,
    subject TEXT,
    snippet TEXT,
    received_at DATETIME,

    classification TEXT NOT NULL CHECK (classification IN (
        'needs_response', 'action_required', 'payment_request', 'fyi', 'waiting'
    )),
    confidence TEXT DEFAULT 'medium' CHECK (confidence IN ('high', 'medium', 'low')),
    reasoning TEXT,
    detected_language TEXT DEFAULT 'cs',
    resolved_style TEXT DEFAULT 'business',
    message_count INTEGER DEFAULT 1,

    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'drafted', 'rework_requested', 'sent', 'skipped', 'archived'
    )),
    draft_id TEXT,
    rework_count INTEGER DEFAULT 0,
    last_rework_instruction TEXT,

    vendor_name TEXT,

    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    drafted_at DATETIME,
    acted_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, gmail_thread_id)
);

CREATE INDEX IF NOT EXISTS idx_emails_user_classification ON emails(user_id, classification);
CREATE INDEX IF NOT EXISTS idx_emails_user_status ON emails(user_id, status);
CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(gmail_thread_id);

-- Audit log (user-scoped)
CREATE TABLE IF NOT EXISTS email_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    gmail_thread_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'classified', 'label_added', 'label_removed',
        'draft_created', 'draft_trashed', 'draft_reworked',
        'sent_detected', 'archived', 'rework_limit_reached',
        'waiting_retriaged', 'error'
    )),
    detail TEXT,
    label_id TEXT,
    draft_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_user_thread ON email_events(user_id, gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON email_events(event_type);

-- Job queue (SQLite-based for lite mode; PostgreSQL uses SKIP LOCKED)
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,          -- 'sync', 'classify', 'draft', 'cleanup', 'rework'
    user_id INTEGER NOT NULL REFERENCES users(id),
    payload TEXT DEFAULT '{}',       -- JSON payload
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, job_type);
