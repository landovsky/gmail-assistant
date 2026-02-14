# 02 — Data Model

## Overview

The system uses a relational database with 9 tables organized around a user-scoped design. All tables except the top-level `users` table carry a `user_id` foreign key. The schema enforces data integrity through CHECK constraints, UNIQUE constraints, and foreign keys.

---

## Tables

### users

The root entity. Each user corresponds to one Gmail account.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | integer | PK, auto-increment | |
| email | text | UNIQUE, NOT NULL | Gmail address |
| display_name | text | nullable | |
| is_active | boolean | default true | Soft-delete flag |
| onboarded_at | datetime | nullable | Set when onboarding completes |
| created_at | datetime | default now | |

**Domain invariants:**
- Email must be unique across all users.
- A user must be onboarded (labels provisioned, settings initialized, sync state seeded) before processing begins.

---

### user_labels

Maps logical label keys (e.g., `needs_response`) to Gmail API label IDs for each user. Gmail label IDs are opaque strings assigned by Google and differ per account.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| user_id | integer | PK (composite), FK → users.id | |
| label_key | text | PK (composite), NOT NULL | One of the 9 standard keys |
| gmail_label_id | text | NOT NULL | Google-assigned label ID |
| gmail_label_name | text | NOT NULL | Human-readable label name |

**Standard label keys:** `parent`, `needs_response`, `outbox`, `rework`, `action_required`, `payment_request`, `fyi`, `waiting`, `done`

**Standard label names:** `🤖 AI`, `🤖 AI/Needs Response`, `🤖 AI/Outbox`, `🤖 AI/Rework`, `🤖 AI/Action Required`, `🤖 AI/Payment Requests`, `🤖 AI/FYI`, `🤖 AI/Waiting`, `🤖 AI/Done`

---

### user_settings

Key-value store for per-user settings. Values are stored as JSON-serialized text.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| user_id | integer | PK (composite), FK → users.id | |
| setting_key | text | PK (composite), NOT NULL | |
| setting_value | text | NOT NULL | JSON-serialized |

**Known setting keys:**
- `communication_styles` — Draft style rules, sign-off, examples, per style name
- `contacts` — Style overrides per sender email, domain overrides, blacklist patterns
- `label_ids_yaml` — Legacy label ID mapping (imported from v1 config, not used at runtime)

**Current behavior:** Settings are loaded with a DB-first, YAML-fallback pattern. At runtime, `communication_styles` and `contacts` are read from the DB; if no DB value exists, the system falls back to reading `config/communication_styles.yml` and `config/contacts.yml` directly from disk. During user onboarding, `import_from_yaml()` copies the YAML content into the DB so subsequent reads use the DB. The API endpoints (`GET/PUT /api/users/{user_id}/settings`) allow runtime changes to DB-stored values.

---

### sync_state

Tracks Gmail History API synchronization progress and Pub/Sub watch status. One row per user.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| user_id | integer | PK, FK → users.id | 1:1 with users |
| last_history_id | text | NOT NULL, default '0' | Gmail History API cursor |
| last_sync_at | datetime | default now | |
| watch_expiration | datetime | nullable | Unix timestamp of watch expiry |
| watch_resource_id | text | nullable | Pub/Sub resource identifier |

**Domain invariants:**
- `last_history_id` of `'0'` indicates no sync has occurred (triggers full sync).
- Watch expiration is set by Gmail API; watches expire after 7 days.

---

### emails

Core email records. One row per Gmail thread that the system has processed. The `(user_id, gmail_thread_id)` pair is unique — the system tracks threads, not individual messages.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | integer | PK, auto-increment | |
| user_id | integer | NOT NULL, FK → users.id | |
| gmail_thread_id | text | NOT NULL | Google thread ID |
| gmail_message_id | text | NOT NULL | ID of the triggering message |
| sender_email | text | NOT NULL | |
| sender_name | text | nullable | |
| subject | text | nullable | |
| snippet | text | nullable | Gmail preview text |
| received_at | datetime | nullable | |
| classification | text | NOT NULL, CHECK | See allowed values below |
| confidence | text | default 'medium', CHECK | `high`, `medium`, `low` |
| reasoning | text | nullable | LLM explanation for classification |
| detected_language | text | default 'cs' | ISO language code |
| resolved_style | text | default 'business' | Communication style key |
| message_count | integer | default 1 | Messages in thread at classification time |
| status | text | default 'pending', CHECK | See state machine below |
| draft_id | text | nullable | Gmail draft ID |
| rework_count | integer | default 0 | Number of rework cycles |
| last_rework_instruction | text | nullable | Most recent rework instruction |
| vendor_name | text | nullable | Extracted vendor/company name |
| processed_at | datetime | default now | When classification happened |
| drafted_at | datetime | nullable | When draft was created |
| acted_at | datetime | nullable | When user acted (sent/archived) |
| created_at | datetime | default now | |
| updated_at | datetime | default now | Updated on any write |

**Classification values:** `needs_response`, `action_required`, `payment_request`, `fyi`, `waiting`

**Status values:** `pending`, `drafted`, `rework_requested`, `sent`, `skipped`, `archived`

**Indices:**
- `(user_id, classification)` — Filter by classification type
- `(user_id, status)` — Filter by processing status
- `(gmail_thread_id)` — Lookup by thread

**UNIQUE constraint:** `(user_id, gmail_thread_id)` — On conflict, upserts update classification fields but preserve status.

**Upsert behavior:** When a thread is re-encountered (e.g., during full sync), the upsert updates `gmail_message_id`, `classification`, `confidence`, `reasoning`, `detected_language`, `resolved_style`, `message_count`, and `updated_at`, but does NOT reset `status` — it stays at whatever state it was in.

---

### email_events

Immutable audit log. Every state transition, label change, draft creation, and error is recorded here.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | integer | PK, auto-increment | |
| user_id | integer | NOT NULL, FK → users.id | |
| gmail_thread_id | text | NOT NULL | |
| event_type | text | NOT NULL, CHECK | See allowed values below |
| detail | text | nullable | Human-readable description |
| label_id | text | nullable | Gmail label ID (for label events) |
| draft_id | text | nullable | Gmail draft ID (for draft events) |
| created_at | datetime | default now | |

**Event types:** `classified`, `label_added`, `label_removed`, `draft_created`, `draft_trashed`, `draft_reworked`, `sent_detected`, `archived`, `rework_limit_reached`, `waiting_retriaged`, `error`

**Indices:**
- `(user_id, gmail_thread_id)` — Thread audit trail
- `(event_type)` — Filter by event type

---

### jobs

Persistent job queue for asynchronous processing. Workers claim jobs atomically.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | integer | PK, auto-increment | |
| job_type | text | NOT NULL | See allowed values below |
| user_id | integer | NOT NULL, FK → users.id | |
| payload | text | default '{}' | JSON-serialized job parameters |
| status | text | default 'pending', CHECK | `pending`, `running`, `completed`, `failed` |
| attempts | integer | default 0 | Incremented on each claim |
| max_attempts | integer | default 3 | Maximum retries before permanent failure |
| error_message | text | nullable | Last error message |
| created_at | datetime | default now | |
| started_at | datetime | nullable | Set when claimed |
| completed_at | datetime | nullable | Set on completion or failure |

**Job types:** `sync`, `classify`, `draft`, `cleanup`, `rework`, `manual_draft`, `agent_process`

**Indices:**
- `(status, created_at)` — Efficient pending job lookup (FIFO)
- `(user_id, job_type)` — User-scoped job queries

**Atomic claiming:** The next pending job is claimed using an atomic `UPDATE ... RETURNING` pattern (subquery selects the oldest pending job with `attempts < max_attempts`, updates it to `running`, and returns it in one statement). This prevents duplicate processing when multiple workers compete.

---

### llm_calls

Audit log for every LLM API call. Used for debugging, cost monitoring, and latency tracking.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | integer | PK, auto-increment | |
| user_id | integer | nullable, FK → users.id | Null for non-user calls (e.g., health check) |
| gmail_thread_id | text | nullable | |
| call_type | text | NOT NULL, CHECK | `classify`, `draft`, `rework`, `context`, `agent` |
| model | text | NOT NULL | Model identifier (e.g., `gemini/gemini-2.0-flash`) |
| system_prompt | text | nullable | Full system prompt sent |
| user_message | text | nullable | Full user message sent |
| response_text | text | nullable | LLM response (truncated to 2000 chars for agent) |
| prompt_tokens | integer | default 0 | |
| completion_tokens | integer | default 0 | |
| total_tokens | integer | default 0 | |
| latency_ms | integer | default 0 | Wall-clock time |
| error | text | nullable | Error message if call failed |
| created_at | datetime | default now | |

**Indices:**
- `(gmail_thread_id)` — All LLM calls for a thread
- `(call_type)` — Filter by call type
- `(user_id)` — User-scoped queries
- `(created_at)` — Time-based queries

---

### agent_runs

Tracks agent framework executions. One row per agent invocation.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | integer | PK, auto-increment | |
| user_id | integer | NOT NULL, FK → users.id | |
| gmail_thread_id | text | NOT NULL | |
| profile | text | NOT NULL | Agent profile name |
| status | text | NOT NULL, default 'running', CHECK | `running`, `completed`, `error`, `max_iterations` |
| tool_calls_log | text | default '[]' | JSON array of tool call records |
| final_message | text | nullable | Agent's final text output |
| iterations | integer | default 0 | Number of LLM turns |
| error | text | nullable | Error message if failed |
| created_at | datetime | default now | |
| completed_at | datetime | nullable | |

**Indices:**
- `(user_id)` — User-scoped queries
- `(gmail_thread_id)` — Thread-scoped queries
- `(status)` — Filter by status

---

## Entity Relationships

```
users (1)
  ├── (1:N) user_labels
  ├── (1:N) user_settings
  ├── (1:1) sync_state
  ├── (1:N) emails
  ├── (1:N) email_events
  ├── (1:N) jobs
  ├── (1:N) llm_calls (user_id nullable)
  └── (1:N) agent_runs
```

Note: `email_events`, `llm_calls`, and `agent_runs` reference `emails` by `gmail_thread_id` logically, but this is NOT enforced as a foreign key at the database level.

---

## Email Status State Machine

```
                ┌────────────────────────────────────┐
                │                                    │
                ▼                                    │
    ┌─────── pending ────────┐                       │
    │           │             │                       │
    │     (draft created)  (agent/skip)               │
    │           │             │                       │
    │           ▼             ▼                       │
    │       drafted        skipped                    │
    │           │             │                       │
    │     ┌─────┴────┐       │                       │
    │     ▼          ▼       │                       │
    │   sent     rework_requested ──── (rework) ─────┘
    │     │                             (back to drafted)
    │     ▼
    │  archived ◄──── (done handler)
    │
    └── archived (done handler can also archive from pending)
```

Transitions:
- `pending` → `drafted`: Draft created successfully
- `pending` → `skipped`: Classified as anything other than `needs_response`, agent route, or rework limit exceeded
- `pending` → `archived`: User marks Done before drafting
- `drafted` → `sent`: Sent detection (draft disappeared from Gmail)
- `drafted` → `rework_requested` → `drafted`: Rework cycle (back to drafted with new draft_id)
- `drafted` → `archived`: User marks Done
- `drafted` → `skipped`: Rework limit (3) exceeded

---

## Migration Strategy

Migrations are applied sequentially on startup. Each migration uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` for idempotency. The migration sequence:

1. **001_v2_schema.sql** — Core tables: users, user_labels, user_settings, sync_state, emails, email_events, jobs
2. **002_llm_calls.sql** — Adds llm_calls table
3. **003_agent_runs.sql** — Adds agent_runs table; recreates llm_calls to add `agent` to the call_type CHECK constraint (required because the database engine used does not support `ALTER CHECK`)
