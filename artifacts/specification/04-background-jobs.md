# Background Job Processing

## Job Types

The system defines 7 job types for async processing:

### Core Pipeline Jobs

**sync** - Incremental Gmail mailbox sync via History API
- Triggered by: Gmail Pub/Sub push notifications, scheduled fallback sync, manual API calls
- Payload: user_id, history_id (optional), force_full (boolean)
- Processing: Fetches Gmail changes since last sync, routes messages to classify or agent processing
- Error handling: Retries on transient failures, falls back to full sync if history too old

**classify** - Two-tier email classification (rules → LLM)
- Triggered by: Sync engine finding new inbox messages
- Payload: user_id, thread_id, message_id, force (boolean)
- Processing: Runs automation detection rules, then LLM classification if needed
- Result: Creates email record with classification, enqueues draft job if needs_response

**draft** - AI draft generation for emails needing responses
- Triggered by: Classification result = needs_response
- Payload: user_id, email_id
- Processing: Gathers context, calls LLM, creates Gmail draft, applies Outbox label
- Error handling: Validates email status before processing

**cleanup** - Lifecycle management (Done/Sent detection)
- Triggered by: Done label added, draft deletion detected
- Payload: user_id, thread_id, action (done | check_sent)
- Processing: Archives thread on "done", detects sent status on draft disappearance
- Result: Updates email status, removes labels, archives thread

**rework** - Draft regeneration based on user feedback
- Triggered by: Rework label added
- Payload: user_id, thread_id, email_id (optional)
- Processing: Extracts user instructions from draft, regenerates with feedback
- Limit: Max 3 rework iterations, then moves to Action Required
- Result: New draft created, rework_count incremented

**manual_draft** - User-initiated draft for manually labeled emails
- Triggered by: User manually applies Needs Response label
- Payload: user_id, thread_id
- Processing: Same as draft job but for manually marked emails
- Behavior: Skips if already drafted, creates DB record if doesn't exist

**agent_process** - Agent-routed email processing (tool use loop)
- Triggered by: Routing rules matching agent route
- Payload: user_id, thread_id, message_id, profile (agent profile name)
- Processing: Runs preprocessor, executes agent loop with tools, logs results
- Result: Agent can auto-send reply, create draft, or escalate to human

## Job Triggering and Queueing

### Webhook-Triggered (Real-Time)
- Gmail Pub/Sub push notifications → sync job

### Sync Engine (Event-Driven)
- New inbox messages → classify or agent_process (based on routing)
- Label additions:
  - Done label → cleanup job (action=done)
  - Rework label → rework job
  - Needs Response label → manual_draft job
- Message deletions → cleanup job (action=check_sent)

### Classification Pipeline (Sequential)
- Classification = needs_response → draft job
- Classification ≠ needs_response → mark as skipped

### Scheduled (Periodic)
- Every 15 minutes: fallback sync for all users
- Every 1 hour: full inbox scan sync
- Every 24 hours: Gmail watch renewal

### Manual (API)
- Admin endpoints can trigger manual sync
- Debug endpoint can trigger reclassification

## Queue Contract

### Database Implementation
- SQLite jobs table with atomic claim-next pattern
- Schema: job_type, user_id, payload (JSON), status, attempts, max_attempts, error_message
- Statuses: pending → running → completed or failed
- Concurrency-safe via UPDATE RETURNING

### Queue Operations

**Enqueue**: Creates job with pending status
- Returns: job ID
- Deduplication: Application-level checks prevent duplicate jobs for same thread

**Claim**: Atomically claims oldest pending job
- Query: UPDATE jobs SET status=running WHERE status=pending AND attempts<max_attempts ORDER BY created_at LIMIT 1 RETURNING *
- Prevents race conditions between workers

**Complete**: Marks job as completed
- Updates: status=completed, completed_at timestamp

**Fail**: Marks job as failed
- Updates: status=failed, error_message

**Retry**: Re-queues job for retry
- Updates: status=pending, attempts=attempts+1, error_message
- Only if attempts < max_attempts

## Worker Pool Architecture

### Concurrency Model

**Fixed-size pool**: N async worker coroutines (default: 3, configurable)

**Worker loop**:
1. Claim next pending job atomically
2. Process job (dispatch to handler)
3. Sleep 1 second if queue empty
4. Repeat while running

**Async I/O strategy**:
- All blocking operations (Gmail API, LLM, SQLite) pushed to threads
- Keeps event loop responsive
- True concurrency limited by SQLite write serialization

**Lifecycle**:
- Started during application startup
- Runs as background async tasks alongside scheduler
- Graceful shutdown on app termination

## Retry Behavior and Failure Handling

### Retry Logic

**Max attempts**: 3 (default, stored per-job in max_attempts column)

**Automatic retry**:
- On exception during job processing: sets status to pending, increments attempts
- Job re-enters queue for next worker to claim
- Only retries if attempts < max_attempts

**Permanent failure**:
- After 3 failed attempts: sets status to failed, records error message
- Job removed from active queue

### Error Handling Per Job Type

**sync**:
- Catches exceptions, logs warning, continues processing other history records
- Falls back to full sync on expired history ID

**classify**:
- Returns early on missing message/user
- LLM failures bubble up to retry logic

**draft**:
- Validates email status=pending before processing
- Draft creation failures throw RuntimeError

**cleanup**:
- Resolves thread_id from DB if missing from payload
- Handles deletion records gracefully

**rework**:
- Checks rework limit (3)
- Moves to Action Required if limit exceeded

**manual_draft**:
- Skips if already drafted
- Creates DB record if doesn't exist

**agent_process**:
- Validates message exists
- Logs agent execution errors
- Updates agent run status

### Domain-Specific Limits

**Rework limit**: 3 attempts per email
- On 3rd rework: moves email to Action Required, marks as skipped
- Prevents infinite LLM loops
- Tracked via emails.rework_count column

## Scheduled/Periodic Jobs

### Three Periodic Loops

**Watch renewal** - Every 24 hours:
- Renews Gmail push notification watches for all users
- Watches expire after 7 days; proactive renewal prevents gaps

**Fallback sync** - Every 15 minutes (configurable):
- Enqueues sync job for all active users
- Safety net for missed push notifications

**Full sync** - Every 1 hour (configurable):
- Enqueues sync job with force_full=true
- Scans entire inbox (last 10 days) for unclassified emails
- Catches emails missed during watch outages

## Job Lifecycle and State Transitions

### Job States

```
pending → running → completed
              ↓
           failed (after max_attempts retries)
              ↑
        retry ← (on exception, attempts < max_attempts)
```

### Job Flow Example (needs_response email)

1. Gmail Pub/Sub → sync job queued
2. Worker claims sync, processes history, finds new message
3. Sync handler enqueues classify job (or agent_process if routing matches)
4. Worker claims classify, runs LLM classification
5. Classification = needs_response → enqueue draft job
6. Worker claims draft, generates AI response, creates Gmail draft
7. Label transitions: Needs Response → Outbox
8. User applies Rework label → rework job queued
9. Worker regenerates draft with user instructions
10. User sends email, draft deleted → cleanup job (action=check_sent)
11. Sent detection updates status to sent

### State Machine Integration

Jobs trigger email lifecycle state transitions:
- pending → drafted (draft job creates Gmail draft)
- drafted → rework_requested (rework job)
- rework_requested → drafted (rework completion)
- drafted → sent (cleanup job detects draft deletion)
- Any → archived (cleanup job with Done label)
- Any → skipped (classification ≠ needs_response, or rework limit exceeded)

## Cleanup and Maintenance

### Job Retention
- Retention: 7 days for completed/failed jobs
- Method: Delete old jobs via cleanup operation
- Scope: Only completed/failed; pending/running retained

### Idempotency
- Duplicate job prevention: Application checks for pending jobs before enqueue
- Email status guards prevent duplicate work
- Thread-level deduplication in sync processing

## System Characteristics

The background job system prioritizes:

- **Reliability**: Retries, fallback syncs, idempotency checks
- **Responsiveness**: Async workers, non-blocking I/O
- **Observability**: Audit events, error logging, job status tracking
- **Concurrency**: Fixed worker pool with atomic job claiming
- **Fault tolerance**: Worker crashes don't affect other workers or pending jobs
