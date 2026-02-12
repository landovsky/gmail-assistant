CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_thread_id TEXT UNIQUE NOT NULL,
    gmail_message_id TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    sender_name TEXT,
    subject TEXT,
    snippet TEXT,
    received_at DATETIME,

    -- Classification
    classification TEXT NOT NULL
        CHECK (classification IN (
            'needs_response', 'action_required',
            'payment_request', 'fyi', 'waiting'
        )),
    confidence TEXT DEFAULT 'medium'
        CHECK (confidence IN ('high', 'medium', 'low')),
    reasoning TEXT,
    detected_language TEXT DEFAULT 'cs',
    resolved_style TEXT DEFAULT 'business',

    -- Thread tracking
    message_count INTEGER DEFAULT 1,

    -- Draft tracking
    status TEXT DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'drafted', 'rework_requested',
            'sent', 'skipped', 'archived'
        )),
    draft_id TEXT,
    rework_count INTEGER DEFAULT 0,
    last_rework_instruction TEXT,

    -- Payment request fields (nullable, only for classification=payment_request)
    vendor_name TEXT,

    -- Timestamps
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    drafted_at DATETIME,
    acted_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_emails_classification ON emails(classification);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(gmail_thread_id);

-- Audit log: every action the system takes on an email
CREATE TABLE IF NOT EXISTS email_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_thread_id TEXT NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'classified', 'label_added', 'label_removed',
            'draft_created', 'draft_trashed', 'draft_reworked',
            'sent_detected', 'archived', 'rework_limit_reached',
            'waiting_retriaged', 'error'
        )),
    detail TEXT,              -- human-readable description of what happened
    label_id TEXT,            -- which label was added/removed (if applicable)
    draft_id TEXT,            -- which draft was created/deleted (if applicable)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_thread ON email_events(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON email_events(event_type);
