# 06 — Background Jobs & Async Processing

## Overview

All email processing happens asynchronously through a persistent job queue backed by the database. A worker pool of concurrent workers continuously polls for pending jobs, claims them atomically, and processes them. A scheduler runs periodic tasks (watch renewal, fallback sync).

---

## Job Queue

### Storage

Jobs are stored in the `jobs` table (see spec 02). Each job has a type, user scope, JSON payload, status, attempt counter, and timestamps.

### Job Lifecycle

```
                  enqueue()
                     │
                     ▼
    ┌──────────── pending ◄──────────────┐
    │                                    │
    │         claim_next()               │ retry()
    │                                    │ (attempts < max_attempts)
    │                ▼                   │
    │           running ─────────────────┤
    │               │                    │
    │        ┌──────┴──────┐             │
    │        ▼             ▼             │
    │   complete()     fail/error ───────┘
    │        │             │
    │        ▼             ▼ (attempts >= max_attempts)
    │   completed       failed
    │
    └── cleanup_old() removes completed/failed after 7 days
```

### Atomic Job Claiming

To prevent duplicate processing when multiple workers run concurrently, jobs are claimed using an atomic database operation:

```sql
UPDATE jobs
SET status = 'running',
    attempts = attempts + 1,
    started_at = CURRENT_TIMESTAMP
WHERE id = (
    SELECT id FROM jobs
    WHERE status = 'pending' AND attempts < max_attempts
    ORDER BY created_at
    LIMIT 1
)
RETURNING *
```

This selects the oldest pending job and atomically marks it as running in a single statement. The `RETURNING` clause provides the claimed job's data without a second query.

For PostgreSQL implementations, this should use `SELECT ... FOR UPDATE SKIP LOCKED` for better concurrent performance.

### Retry Behavior

- Default max attempts: 3
- On exception during processing: if `attempts < max_attempts`, job status is set back to `pending` (retry). Otherwise, status is set to `failed` with the error message.
- There is no delay between retries — a retried job is immediately eligible for re-claiming. [UNCLEAR: Whether this is intentional or if exponential backoff should be added between retries.]

---

## Job Types

### sync

**Trigger:** Webhook notification, fallback polling timer, or manual `/api/sync` call.

**Payload:**
```json
{
  "history_id": "12345"  // from Pub/Sub notification; empty string for polling
}
```

**Processing:**
1. Get sync state for user
2. If no sync state: run full sync (search inbox for unclassified emails)
3. Otherwise: fetch history records since `last_history_id`
4. For each history record, create downstream jobs (classify, agent_process, cleanup, rework, manual_draft)
5. Update `last_history_id`

**Side effects:** Creates downstream jobs. Updates `sync_state` table.

---

### classify

**Trigger:** Created by sync engine when a new INBOX message is detected and the router selects the "pipeline" route.

**Payload:**
```json
{
  "message_id": "msg_abc123",
  "thread_id": "thread_xyz789"
}
```

**Processing:**
1. Fetch message content from Gmail API
2. Skip if thread already has a classification record in the database
3. Load user settings (blacklist, contacts config)
4. Run classification engine (rules + LLM)
5. Apply classification label to the message in Gmail
6. Store email record in database
7. Log `classified` event
8. If classified as `needs_response`: enqueue a `draft` job

**Side effects:** Gmail label change. Database insert (emails, email_events). May enqueue `draft` job. LLM API call logged.

**Idempotency:** If thread already classified (exists in emails table), the job completes immediately without changes.

---

### draft

**Trigger:** Created by classify handler when classification is `needs_response`.

**Payload:**
```json
{
  "thread_id": "thread_xyz789",
  "message_id": "msg_abc123"
}
```

**Processing:**
1. Fetch email record; skip if status is not `pending`
2. Fetch full thread from Gmail
3. Gather related context (fail-safe)
4. Generate draft via LLM
5. Trash any stale drafts from previous attempts on this thread
6. Create new Gmail draft
7. Move labels: remove Needs Response, add Outbox (batch operation on all thread messages)
8. Update database: status → `drafted`, store `draft_id`
9. Log `draft_created` event

**Side effects:** Gmail draft creation. Gmail label changes. Database update. LLM API calls logged (context + draft).

**Idempotency:** If email status is not `pending`, the job completes without changes. Stale drafts are trashed before creating new ones.

---

### cleanup

**Trigger:** Created by sync engine for Done label additions and message deletions.

**Payload:**
```json
{
  "action": "done" | "check_sent",
  "thread_id": "thread_xyz789",
  "message_id": "msg_abc123"
}
```

**Processing (action=done):**
- Delegates to lifecycle manager's `handle_done()` (see spec 04)

**Processing (action=check_sent):**
- Delegates to lifecycle manager's `handle_sent_detection()` (see spec 04)

**Side effects:** Gmail label changes. Database status updates. Event logging.

---

### rework

**Trigger:** Created by sync engine when Rework label is added to a thread.

**Payload:**
```json
{
  "message_id": "msg_abc123"
}
```

**Processing:**
1. Fetch message to get thread_id
2. Load user settings (communication styles)
3. Delegate to lifecycle manager's `handle_rework()` (see spec 04)

**Side effects:** Gmail draft trashed and recreated. Gmail label changes. Database update (rework_count incremented). LLM API call. Event logging.

---

### manual_draft

**Trigger:** Created by sync engine when user manually applies the Needs Response label.

**Payload:**
```json
{
  "message_id": "msg_abc123"
}
```

**Processing:**
1. Fetch message to get thread_id
2. Skip if already drafted
3. Fetch thread for context
4. Look for user's existing notes draft in the thread — extract instructions from above `✂️` marker
5. Create/update database record with `classification=needs_response`
6. Gather context, generate draft (with user instructions if found)
7. Trash notes draft and stale AI drafts
8. Create new Gmail draft
9. Move labels: Needs Response → Outbox
10. Log event

**Side effects:** Same as `draft`, plus may trash user's notes draft.

---

### agent_process

**Trigger:** Created by sync engine when the router selects the "agent" route for a message.

**Payload:**
```json
{
  "message_id": "msg_abc123",
  "thread_id": "thread_xyz789",
  "profile": "pharmacy",
  "route_rule": "pharmacy_support"
}
```

**Processing:**
1. Verify agent loop and profile are configured
2. Fetch message and thread from Gmail
3. Preprocess email content (e.g., Crisp helpdesk parser for forwarded emails)
4. Create `agent_runs` record with status `running`
5. Execute agent loop (see spec 07)
6. Update `agent_runs` record with results (status, tool calls, iterations, final message)
7. Log event

**Side effects:** Multiple LLM API calls. Tool executions (side effects depend on tools). Database inserts (agent_runs, llm_calls). Event logging.

---

## Worker Pool

### Architecture

The worker pool starts N concurrent worker coroutines (configurable, default 3). Each worker runs an infinite loop:

1. Attempt to claim the next pending job (any type)
2. If a job is claimed: process it, then loop immediately
3. If no job available: sleep for 1 second, then loop

### Worker Processing

For each claimed job:
1. Look up the user record (fail job if user not found)
2. Create a per-user Gmail API client
3. Dispatch to the appropriate handler based on `job_type`
4. On success: mark job as `completed`
5. On exception: if retries remaining, mark as `pending` (retry). Otherwise, mark as `failed`.

### Concurrency Model

All blocking I/O (Gmail API calls, LLM calls, database queries) is executed in thread pool threads. The async event loop stays responsive for the web server and scheduler.

### Shutdown

On application shutdown:
1. Worker pool `_running` flag is set to False
2. Worker loops exit after their current job completes
3. Background asyncio tasks are cancelled

---

## Scheduler

### Watch Renewal

- **Frequency:** Runs immediately on startup, then every 24 hours
- **Action:** Calls `WatchManager.renew_all_watches()` for all active users
- **Rationale:** Gmail watches expire after 7 days. Daily renewal provides margin.
- **Failure handling:** Exceptions are caught and logged; the loop continues.

### Fallback Sync (incremental)

- **Frequency:** Every N minutes (configurable via `GMA_SYNC_FALLBACK_INTERVAL_MINUTES`, default 15)
- **Action:** Enqueues a `sync` job for each active user
- **Rationale:** Safety net for missed Pub/Sub notifications (network issues, topic misconfiguration, etc.)
- **Payload:** `{"history_id": ""}` — empty history_id means the sync engine uses the stored `last_history_id`
- **Limitation:** Only processes history records since the last known history ID. If an email was missed entirely (e.g. watch was down and history expired), this won't find it.

### Full Sync (catch-up scan)

- **Frequency:** Every N hours (configurable via `GMA_SYNC_FULL_SYNC_INTERVAL_HOURS`, default 1)
- **Action:** Enqueues a `sync` job with `force_full: true` for each active user
- **Rationale:** The fallback sync is incremental — it only replays history since the last checkpoint. If emails slipped through during a watch outage or history gap, the incremental sync will never find them. The full sync scans `in:inbox newer_than:{days}d` (configurable via `GMA_SYNC_FULL_SYNC_DAYS`, default 10, production: 60) excluding already-labeled emails, so it catches anything the incremental sync missed.
- **Payload:** `{"history_id": "", "force_full": true}`
- **Idempotency:** Already-classified emails (those with any AI label) are excluded from the Gmail search query, and the classify handler skips threads that already have a DB record. Running this frequently is safe.

### Why two sync schedules?

The two schedules complement each other:

| | Fallback Sync | Full Sync |
|---|---|---|
| **Method** | Gmail History API (incremental) | Gmail Search API (full scan) |
| **Frequency** | Every 15 min | Every 1 hour |
| **Catches** | Recent changes since last checkpoint | Any unlabeled inbox email within the time window |
| **Cost** | Cheap (small history delta) | More expensive (search + filter) |
| **Blind spot** | Emails missed before the checkpoint | None within the time window |

The fallback sync handles the common case (a few missed push notifications) cheaply. The full sync is the true safety net that guarantees no email stays unprocessed for more than an hour.

---

## Job Cleanup

Completed and failed jobs older than 7 days can be purged via `JobRepository.cleanup_old(days=7)`. [UNCLEAR: Whether this cleanup runs automatically on a schedule or must be triggered manually.]
