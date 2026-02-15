# Gmail Integration

## Gmail API Operations

### Reading Operations
- **List messages**: Search messages by query with pagination
- **Get message**: Fetch individual message (full or metadata format)
- **Get thread**: Fetch entire conversation thread with all messages
- **List drafts**: List all draft messages
- **Get draft**: Fetch specific draft by ID
- **List history**: Incremental sync using History API (with pagination)
- **Get profile**: Get user email and current historyId

### Writing Operations
- **Modify message**: Add/remove labels on single message
- **Batch modify messages**: Batch label operations (multiple messages at once)
- **Create draft**: Create draft reply in thread (MIME-encoded)
- **Delete draft**: Trash/delete draft
- **List labels**: List all labels
- **Create label**: Create new Gmail label

### Webhook/Push Operations
- **Watch**: Subscribe to Gmail push notifications via Pub/Sub
- **Stop**: Unsubscribe from push notifications

### Implementation Notes
- All operations wrapped in retry logic for automatic retry on transient failures
- Messages use full format (body content) or metadata format (headers only)
- Draft creation uses RFC 822 MIME encoding with proper threading headers (In-Reply-To, References)
- Base64 URL-safe encoding for message bodies

## OAuth Flow and Authentication

### Personal OAuth (Single-User)
OAuth 2.0 consent flow process:

1. Download OAuth 2.0 Client ID credentials from Google Cloud Console
2. Save as credentials file
3. On first run: browser-based consent flow opens
4. User grants permissions
5. Token saved and auto-refreshed for subsequent runs

**Scope**: `https://www.googleapis.com/auth/gmail.modify` (read, send drafts, manage labels)

**Credential Lifecycle**:
1. Check if token exists and is valid
2. If expired and refresh token available → auto-refresh
3. If no valid credentials → trigger OAuth consent flow
4. Save refreshed/new tokens to disk for next run

### Service Account (Multi-User)
Domain-wide delegation for multi-tenant deployment:

1. Service account key from Google Cloud Console
2. Impersonate users to act on behalf of users
3. No per-user consent required (admin pre-authorizes domain-wide)

**Note**: Partially ready but designed for future Workspace deployments

## Pub/Sub Webhook Integration

### Gmail Notification Setup

**Watch Subscription**:
- Gmail's watch API subscribes mailbox to Google Cloud Pub/Sub topic
- System provides topic name to Gmail
- Filter by labels: Watches INBOX + user action labels (needs_response, rework, done)
- Expiration: Watch expires after ~7 days, requires renewal
- Response includes: historyId and expiration timestamp

**Push Notification Format**:
```
{
  "message": {
    "data": "<base64-encoded-json>",  // {emailAddress, historyId}
    "messageId": "...",
    "publishTime": "..."
  },
  "subscription": "..."
}
```

**Notification Processing Flow**:
1. Gmail sends HTTP POST to webhook endpoint when changes occur
2. Decode base64 payload → extract emailAddress and historyId
3. Look up user by email in database
4. Enqueue sync job with history_id for that user
5. Worker picks up job and runs incremental History API sync

**Watch Renewal**:
- Scheduled task checks watch expiration
- Renews watches expiring within 24 hours
- Updates database with new historyId and expiration

**Fallback**:
- If no Pub/Sub topic configured → periodic polling (every 15 min default)
- Full sync fallback if historyId too old (404 error)

## History API Sync Mechanism

### Incremental Sync Strategy

Gmail assigns a monotonically increasing historyId to every mailbox change. System tracks last known historyId per user, then fetches only changes since that point.

**Sync Process**:
1. Load last_history_id from database
2. Call history.list(startHistoryId=last_history_id)
3. Gmail returns changes: messagesAdded, messagesDeleted, labelsAdded, labelsRemoved
4. Process each history record and queue jobs
5. Update stored historyId to latest

**History Record Processing**:

```
messagesAdded (new INBOX messages):
  → Route to classify pipeline OR agent processing
  → Check routing rules (sender, subject, headers)
  → Enqueue job: "classify" or "agent_process"

labelsAdded:
  → Done label added → cleanup job (archive thread)
  → Rework label added → rework job (regenerate draft)
  → Needs Response label added → manual_draft job

messagesDeleted:
  → Sent detection (draft disappeared → likely sent)
  → Cleanup job to verify and update status
```

**Pagination**: Follows nextPageToken to fetch all history records

**Error Handling**:
- historyId too old → Triggers full sync fallback
- Full sync: Query inbox for recent unprocessed messages
- Avoids duplicate jobs: Checks for existing jobs per thread before queueing

**Deduplication**: Uses set tracking (job_type, thread_id) to avoid duplicate jobs when Gmail reports one label change per message in multi-message threads.

## Gmail-Specific Data Mapping

### Message Model
Internal representation of Gmail message:

- ID: Gmail message ID
- Thread ID: Gmail thread ID
- Sender email: Extracted from "From" header
- Sender name: Parsed from "Name <email>" format
- To: "To" header
- Subject: "Subject" header
- Snippet: Gmail's auto-generated preview
- Body: Extracted plain text (multipart-aware)
- Date: "Date" header
- Internal date: Gmail's internal timestamp
- Label IDs: Gmail label IDs (INBOX, SENT, custom)
- Headers: All headers (In-Reply-To, References, etc.)

**Body Extraction Logic**:
- Prefers text/plain MIME type
- Recursively searches multipart messages
- Handles nested multipart structures (multipart/alternative, multipart/mixed)
- Base64 decodes body data
- Falls back to empty string if no plain text found

### Thread Model
- ID: Gmail thread ID
- Messages: All messages in chronological order
- Snippet: Latest message snippet
- History ID: Thread's current historyId

### Draft Model
- ID: Gmail draft ID
- Message: Full message content (when fetched)
- Thread ID: Parent thread ID

### Label System

**8 AI Labels Provisioned on Onboarding**:
```
🤖 AI                     (parent label)
🤖 AI/Needs Response      (needs_response)
🤖 AI/Outbox              (outbox - draft ready)
🤖 AI/Rework              (rework - user feedback)
🤖 AI/Action Required     (action_required)
🤖 AI/Payment Requests    (payment_request)
🤖 AI/FYI                 (fyi)
🤖 AI/Waiting             (waiting)
🤖 AI/Done                (done)
```

**Database Mapping**:
```
user_id | label_key         | gmail_label_id | gmail_label_name
1       | needs_response    | Label_123      | 🤖 AI/Needs Response
1       | outbox            | Label_456      | 🤖 AI/Outbox
```

**Label Operations**:
- Labels created via API during user onboarding
- Label IDs persisted in database
- Batch operations preferred for thread-wide changes
- Standard Gmail labels used: INBOX, SENT, TRASH (uppercase IDs)

## Error Handling and Retry Logic

### Retry Strategy (Exponential Backoff)

**Retryable Errors**:
- Network errors: socket errors, connection errors, timeouts
- HTTP errors: 429 (rate limit), 500, 502, 503, 504 (server errors)
- Transient exceptions

**Non-Retryable Errors**:
- 4xx client errors (except 429) → fail immediately
- Invalid requests, auth failures → no retry

**Retry Parameters**:
- Max attempts: 3 retries (4 total attempts)
- Base delay: 1 second
- Exponential backoff: delay doubles each retry (1s, 2s, 4s)
- Sleep between retries

### Graceful Degradation

**Operation-Level Error Handling**:
- Every Gmail operation wrapped in try/except
- Returns None or empty list on failure (doesn't crash)
- Errors logged with context (message ID, thread ID, operation name)

**History API Special Cases**:
- Expired historyId detection
- Response: Log warning, return empty list
- Trigger: Sync engine detects empty result → initiates full sync

**Full Sync Fallback**:
- Query: inbox for recent unprocessed messages
- Fetches up to 50 unprocessed messages
- Updates last_history_id from getProfile API call
- Prevents duplicate work: Checks database and job queue before queueing

### Job Queue Resilience

**Job Retry System** (database-level):
- Failed jobs: status=failed, attempts incremented
- Max attempts: 3 (configurable)
- Error message stored
- Jobs not retried if max attempts reached

**Worker Pool Resilience**:
- N concurrent workers (default 3)
- Worker crashes don't affect other workers
- Jobs claimed atomically (no duplicate processing)
- Unclaimed jobs remain available if worker dies

## Integration Contract Summary

### What the System Does with Gmail

1. **Monitors** inbox for new messages via push notifications (or polling)
2. **Reads** message content, threads, and metadata
3. **Classifies** emails into categories
4. **Labels** messages with Gmail labels to surface state
5. **Creates** draft replies (never sends automatically except for specific agent profiles)
6. **Tracks** state transitions via label changes
7. **Detects** user actions (sent drafts, manual labels, done marking)
8. **Manages** label lifecycle (archive on done, rework flow)

### What Gmail Events Trigger

- **New message in INBOX** → classify OR agent_process job
- **Done label added** → cleanup job (strip labels, archive)
- **Rework label added** → rework job (regenerate draft)
- **Needs Response label added** → manual_draft job
- **Message deleted** → sent detection job (check if draft was sent)
- **New reply on Waiting thread** → retriage (remove Waiting label)

### Safety Invariants

- Never sends emails (only creates drafts), except for specific agent profiles configured to auto-send
- Never deletes emails (only moves to trash/archive via labels)
- Never modifies message content (only labels)
- All state changes logged to audit table
- All Gmail operations are idempotent (safe to retry)
- Human review required before sending (drafts in Outbox label), unless using auto-send agent profile

### Performance Characteristics

- **Push latency**: Near real-time (Pub/Sub typically <1 min)
- **History sync**: Incremental, only changed threads
- **Batch operations**: Multiple messages labeled in single API call
- **Retry overhead**: Max 7 seconds delay on transient failures (1+2+4)
- **Rate limiting**: 429 errors trigger exponential backoff
- **Concurrency**: 3 workers process jobs in parallel (configurable)
