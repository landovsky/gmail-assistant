# Data Model

## Entities

### Users
Represents Gmail account holders.

**Attributes:**
- ID (integer, auto-increment)
- Email (text, unique, required) - Gmail address
- Display name (text, optional)
- Active flag (boolean, default true)
- Onboarded timestamp (datetime, nullable) - When setup completed
- Created timestamp (datetime, auto)

**Constraints:**
- Unique email address
- Email required

### Emails
Represents processed Gmail threads with classification and draft state.

**Attributes:**
- ID (integer, auto-increment)
- User ID (foreign key to Users, required)
- Gmail thread ID (text, required) - Gmail API identifier
- Gmail message ID (text, required) - Latest message in thread
- Sender email (text, required)
- Sender name (text, optional)
- Subject (text, optional)
- Snippet (text, optional) - Preview text
- Received timestamp (datetime, optional)
- Classification (enum, required): needs_response | action_required | payment_request | fyi | waiting
- Confidence (enum, default medium): high | medium | low
- Reasoning (text, optional) - Classification explanation
- Detected language (text, default cs) - Language code (cs/en/de)
- Resolved style (text, default business) - Communication style (formal/business/informal)
- Message count (integer, default 1) - Thread message count for sync tracking
- Status (enum, default pending): pending | drafted | rework_requested | sent | skipped | archived
- Draft ID (text, optional) - Gmail draft identifier if created
- Rework count (integer, default 0) - Iteration counter
- Last rework instruction (text, optional) - Most recent user feedback
- Vendor name (text, optional) - For payment_request classification
- Processed timestamp (datetime, auto)
- Drafted timestamp (datetime, nullable)
- Acted timestamp (datetime, nullable)
- Created timestamp (datetime, auto)
- Updated timestamp (datetime, auto, updated on modification)

**Constraints:**
- Unique (user_id, gmail_thread_id)
- Valid classification value
- Valid confidence value
- Valid status value
- Foreign key to Users

**Indexes:**
- (user_id, classification)
- (user_id, status)
- (gmail_thread_id)

### User Labels
Maps logical label keys to Gmail label IDs per user.

**Attributes:**
- User ID (foreign key to Users, required)
- Label key (text, required) - Logical name (needs_response, outbox, rework, done, etc.)
- Gmail label ID (text, required) - Gmail API label identifier
- Gmail label name (text, required) - Display name

**Constraints:**
- Primary key: (user_id, label_key)
- Foreign key to Users

**Invariants:**
- Each user has their own label mapping
- Label keys are standardized across users
- Gmail label IDs are user-specific

### User Settings
Flexible key-value storage for per-user configuration.

**Attributes:**
- User ID (foreign key to Users, required)
- Setting key (text, required)
- Setting value (text, required) - JSON-encoded

**Constraints:**
- Primary key: (user_id, setting_key)
- Foreign key to Users

**Standard Settings:**
- communication_styles - Drafting style templates
- contacts - Email/domain style overrides, blacklist
- sign_off_name - Email signature
- default_language - Language preference

### Sync State
Tracks Gmail History API sync position per user.

**Attributes:**
- User ID (foreign key to Users, primary key)
- Last history ID (text, required, default 0) - Gmail history cursor
- Last sync timestamp (datetime, auto)
- Watch expiration (datetime, nullable) - Pub/Sub subscription expiry
- Watch resource ID (text, optional) - Pub/Sub resource identifier

**Constraints:**
- One-to-one with Users (user_id is primary key)
- Foreign key to Users

**Invariants:**
- Each user has exactly one sync state record
- History ID represents incremental sync cursor

### Jobs
Async task queue for background processing.

**Attributes:**
- ID (integer, auto-increment)
- Job type (text, required) - sync | classify | draft | cleanup | rework | manual_draft | agent_process
- User ID (foreign key to Users, required)
- Payload (text, default {}) - JSON-encoded job data
- Status (enum, default pending): pending | running | completed | failed
- Attempts (integer, default 0) - Retry counter
- Max attempts (integer, default 3) - Retry limit
- Error message (text, optional)
- Created timestamp (datetime, auto)
- Started timestamp (datetime, nullable)
- Completed timestamp (datetime, nullable)

**Constraints:**
- Valid status value
- Foreign key to Users

**Indexes:**
- (status, created_at) - For claim-next queries
- (user_id, job_type)

**Invariants:**
- Atomic claim via UPDATE RETURNING prevents race conditions
- Jobs fail permanently after max attempts reached
- Payload is always valid JSON

### Email Events
Immutable audit log of email lifecycle events.

**Attributes:**
- ID (integer, auto-increment)
- User ID (foreign key to Users, required)
- Gmail thread ID (text, required)
- Event type (enum, required): classified | label_added | label_removed | draft_created | draft_trashed | draft_reworked | sent_detected | archived | rework_limit_reached | waiting_retriaged | error
- Detail (text, optional) - Human-readable description
- Label ID (text, optional) - Related Gmail label
- Draft ID (text, optional) - Related Gmail draft
- Created timestamp (datetime, auto)

**Constraints:**
- Valid event type
- Foreign key to Users

**Indexes:**
- (user_id, gmail_thread_id)
- (event_type)

**Invariants:**
- Append-only (no updates or deletes)
- Every state transition generates an event

### LLM Calls
Tracks all LLM API calls for debugging and cost monitoring.

**Attributes:**
- ID (integer, auto-increment)
- User ID (foreign key to Users, nullable)
- Gmail thread ID (text, optional)
- Call type (enum, required): classify | draft | rework | context | agent
- Model (text, required) - LLM model identifier
- System prompt (text, optional)
- User message (text, optional)
- Response text (text, optional)
- Prompt tokens (integer, default 0)
- Completion tokens (integer, default 0)
- Total tokens (integer, default 0)
- Latency milliseconds (integer, default 0)
- Error (text, optional)
- Created timestamp (datetime, auto)

**Constraints:**
- Valid call type
- Foreign key to Users (nullable)

**Indexes:**
- (gmail_thread_id)
- (call_type)
- (user_id)
- (created_at)

### Agent Runs
Tracks agent execution sessions for debugging and audit.

**Attributes:**
- ID (integer, auto-increment)
- User ID (foreign key to Users, required)
- Gmail thread ID (text, required)
- Profile (text, required) - Agent profile name
- Status (enum, required, default running): running | completed | error | max_iterations
- Tool calls log (text, default []) - JSON array of tool invocations
- Final message (text, optional) - Agent's final output
- Iterations (integer, default 0) - Loop iteration count
- Error (text, optional)
- Created timestamp (datetime, auto)
- Completed timestamp (datetime, nullable)

**Constraints:**
- Valid status value
- Foreign key to Users

**Indexes:**
- (user_id)
- (gmail_thread_id)
- (status)

## Relationships

```
Users (1) ──┬─→ (many) Emails
            ├─→ (many) User Labels
            ├─→ (many) User Settings
            ├─→ (1) Sync State
            ├─→ (many) Jobs
            ├─→ (many) Email Events
            ├─→ (many) LLM Calls
            └─→ (many) Agent Runs

Emails (1) ──→ (many) Email Events [via gmail_thread_id]
           └─→ (many) LLM Calls [via gmail_thread_id]
           └─→ (many) Agent Runs [via gmail_thread_id]
```

## Domain Invariants

### Multi-User Isolation
- All core entities are user-scoped via User ID foreign key
- Gmail label IDs are user-specific (same logical label may have different IDs per user)
- Emails table enforces unique (user_id, gmail_thread_id)

### Email Classification Rules
- Exactly one classification category per email
- Confidence must be high, medium, or low
- Two-tier classification: rules first, then LLM
- Rule-based automation detection prevents drafts for machine-generated emails

### Email Lifecycle State Machine
Status transitions:
```
pending → drafted → sent
        ↓         ↓
   rework_requested → (back to drafted)
        ↓
     skipped (after 3 reworks)
        ↓
    archived (user marked done)
```

### Rework Limit Enforcement
- Hard limit: 3 rework iterations per thread
- On 4th attempt: status becomes skipped, moves to action_required label
- Counter tracked in rework_count field
- Event logged: rework_limit_reached

### Job Queue Semantics
- Atomic claiming via UPDATE RETURNING prevents duplicate processing
- Jobs retry up to max_attempts (default 3) before permanent failure
- Status progression: pending → running → (completed | failed)
- Deduplication checks prevent enqueueing duplicate jobs

### Sync State Management
- History ID enables Gmail History API incremental sync
- Message count on emails detects new replies on waiting threads
- Watch expiration tracks Pub/Sub subscription validity
- Retriage logic: new messages on waiting threads trigger reclassification

### Audit Trail Requirements
- Email Events is append-only (no updates/deletes)
- Every email status change generates an event
- All LLM calls logged with full prompts, responses, tokens, latency
- Agent runs log all tool calls as JSON

## Data Validation

### Database-Level
- Foreign keys enabled
- Check constraints for enum values
- Unique constraints prevent duplicates
- NOT NULL enforced on required fields
- Default values for sensible initialization

### Application-Level
- JSON serialization validation for payloads, settings, agent runs
- Email address format validated by Gmail API
- Language detection with fallback to Czech (cs)
- Style resolution with priority order
- Auto-timestamps maintained on changes

## Performance Optimizations

- 18 total indexes covering common query patterns
- SQLite WAL mode for concurrent reads
- Composite indexes on filtered queries
- Job queue index optimizes FIFO claim-next operation

## Data Retention

### Job Cleanup
- Retention: 7 days for completed/failed jobs
- Method: Delete old jobs via cleanup operation
- Scope: Only completed/failed; pending/running retained

### Persistent Data
- Email records are persistent
- Events are immutable audit logs
- LLM calls retained indefinitely for cost analysis
- Agent runs retained for debugging
