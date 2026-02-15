# Integration Test Cases

This document defines technology-agnostic integration and acceptance test cases that must pass regardless of implementation stack. These are separate from unit tests, which will be stack-specific.

## Test Organization

Tests organized by functional area:
- Classification accuracy
- Draft generation quality
- Email lifecycle transitions
- Background job processing
- Gmail integration
- Agent execution
- Routing decisions
- API contracts

## Classification Tests

### Test: Automation Detection (Rule-Based)

**Given**: Email from noreply@notifications.com with subject "Your order has shipped"

**When**: Email is classified

**Then**:
- is_automated flag is true
- Classification is "fyi"
- No draft job is enqueued
- Event logged: classified with category=fyi

### Test: Newsletter Classification

**Given**: Email with List-Unsubscribe header and promotional content

**When**: Email is classified

**Then**:
- Classification is "fyi"
- Confidence is high
- Reasoning mentions mailing list detection

### Test: Direct Question Classification

**Given**: Email with body "Can you send me the report by Friday?"

**When**: Email is classified

**Then**:
- Classification is "needs_response"
- Confidence is high or medium
- Reasoning mentions direct question
- Draft job is enqueued

### Test: Meeting Invite Classification

**Given**: Email with subject "Meeting invite" and body containing calendar event details

**When**: Email is classified

**Then**:
- Classification is "action_required"
- No draft job is enqueued
- Action Required label applied

### Test: Invoice Classification

**Given**: Email with subject "Invoice #12345" and body showing amount due

**When**: Email is classified

**Then**:
- Classification is "payment_request"
- vendor_name field is populated
- Payment Requests label applied
- No draft job is enqueued

### Test: Waiting Detection (Thread Context)

**Given**: Email thread where user's message is the last in conversation

**When**: Email is classified

**Then**:
- Classification is "waiting"
- Waiting label applied
- No draft job is enqueued

### Test: Style Resolution (Override)

**Given**:
- Email from important@client.com
- contacts.style_overrides maps "important@client.com" to "formal"

**When**: Email is classified

**Then**:
- resolved_style is "formal"
- Not the LLM-detected style

### Test: Language Detection

**Given**: Email body in Czech language

**When**: Email is classified

**Then**:
- detected_language is "cs"
- Draft will be generated in Czech

### Test: Reclassification

**Given**: Email previously classified as "fyi"

**When**: Reclassification is triggered via API

**Then**:
- Classification is re-run with fresh LLM call
- Email record updated with new classification
- Old label removed, new label added
- Event logged: classified

## Draft Generation Tests

### Test: Initial Draft Creation

**Given**: Email classified as "needs_response"

**When**: Draft job is processed

**Then**:
- Gmail draft is created
- draft_id is stored in email record
- Status is updated to "drafted"
- Outbox label applied
- Needs Response label removed
- Draft contains rework marker (✂️)
- Event logged: draft_created

### Test: Draft Matches Communication Style

**Given**: Email with resolved_style="formal"

**When**: Draft is generated

**Then**:
- Draft uses formal greeting and sign-off
- Tone is very polite and structured
- Matches formal style template guidelines

### Test: Draft Uses Related Context

**Given**:
- Email asks about "project timeline"
- Related thread exists discussing project timeline

**When**: Draft is generated

**Then**:
- Context gathering finds related thread
- Draft references information from related thread
- Response is informed by mailbox history

### Test: Draft Language Matches Email

**Given**: Email in Czech language

**When**: Draft is generated

**Then**:
- Draft is written in Czech
- Grammar and phrasing are natural
- Sign-off is Czech-appropriate

### Test: Rework Draft

**Given**:
- Email with existing draft
- User adds instruction above ✂️ marker: "Make this shorter"
- User applies Rework label

**When**: Rework job is processed

**Then**:
- Old draft is trashed
- New draft is created with same thread_id
- New draft is shorter than original
- rework_count is incremented
- Outbox label remains
- Event logged: draft_reworked

### Test: Rework Limit Enforcement

**Given**: Email with rework_count=3

**When**: User requests 4th rework

**Then**:
- Status is set to "skipped"
- Outbox label is removed
- Action Required label is applied
- Warning added to draft about limit
- No new draft is generated
- Event logged: rework_limit_reached

### Test: Manual Draft Request

**Given**: Email classified as "fyi"

**When**: User manually applies Needs Response label

**Then**:
- manual_draft job is enqueued
- Draft is generated (same as automatic flow)
- Email record is created/updated with classification override

## Email Lifecycle Tests

### Test: needs_response → drafted → sent

**Given**: Email classified as needs_response

**When**:
1. Draft job processes email (drafted)
2. User sends draft, Gmail deletes it
3. Cleanup job detects deletion

**Then**:
- Status transitions: pending → drafted → sent
- Labels: Needs Response → Outbox → (removed)
- Events logged: classified, draft_created, sent_detected

### Test: User Marks Done

**Given**: Email in any status (drafted, sent, skipped)

**When**: User applies Done label

**Then**:
- Status is set to "archived"
- All AI labels are removed
- INBOX label is removed (thread archived)
- acted_at timestamp is set
- Event logged: archived

### Test: Waiting Retriage

**Given**:
- Email with status=waiting
- New reply arrives on thread

**When**: Sync detects new message

**Then**:
- Waiting label is removed
- Email is reclassified
- May transition to needs_response → drafted
- Event logged: waiting_retriaged

### Test: Sent Detection

**Given**: Email with status=drafted and draft_id set

**When**: Gmail History API reports draft deletion

**Then**:
- Cleanup job verifies draft no longer exists
- Status is set to "sent"
- Outbox label is removed
- acted_at timestamp is set
- Event logged: sent_detected

## Background Job Tests

### Test: Job Queue FIFO

**Given**: 3 jobs enqueued at different times

**When**: Worker claims next job

**Then**:
- Oldest pending job is claimed
- Job status is set to "running"
- Job is not visible to other workers

### Test: Job Retry on Failure

**Given**: Job that throws exception on first attempt

**When**: Job is processed

**Then**:
- Status is set back to "pending"
- attempts is incremented
- error_message is stored
- Job re-enters queue for retry

### Test: Job Permanent Failure

**Given**: Job that fails 3 times

**When**: Job is processed on 4th attempt

**Then**:
- Status is set to "failed"
- Job is not retried
- error_message is preserved
- Job removed from active queue

### Test: Job Deduplication

**Given**: Pending job exists for thread T1

**When**: Sync tries to enqueue another job for T1

**Then**:
- Duplicate job is not created
- Existing job remains pending

### Test: Scheduled Sync

**Given**: Fallback sync interval is 15 minutes

**When**: 15 minutes elapse

**Then**:
- sync jobs are enqueued for all active users
- Jobs are processed by workers
- Gmail History API is queried

## Gmail Integration Tests

### Test: OAuth Flow (First-Time Setup)

**Given**: No token file exists

**When**: `/api/auth/init` is called

**Then**:
- Browser opens for OAuth consent
- User grants permissions
- Token is saved to file
- User email is fetched from Gmail
- User is onboarded

### Test: Token Refresh

**Given**: Expired access token with valid refresh token

**When**: Gmail API is called

**Then**:
- Token is automatically refreshed
- New access token is saved
- Gmail API call succeeds

### Test: Label Provisioning

**Given**: New user onboarding

**When**: User is onboarded

**Then**:
- 9 Gmail labels are created (1 parent + 8 children)
- Label IDs are stored in database
- Labels are visible in Gmail

### Test: History API Sync

**Given**:
- Last sync at history_id=12345
- New email arrived (history_id=12346)

**When**: Sync job processes

**Then**:
- history.list called with startHistoryId=12345
- messagesAdded event is processed
- classify or agent_process job is enqueued
- last_history_id is updated to 12346

### Test: Pub/Sub Webhook

**Given**: Gmail watch is registered

**When**: New email arrives in Gmail

**Then**:
- Gmail sends push notification to `/webhook/gmail`
- Webhook decodes base64 payload
- Sync job is enqueued with history_id
- Sync processes new email

### Test: Draft Creation in Gmail

**Given**: Draft job with email content

**When**: Job is processed

**Then**:
- MIME-encoded draft is created
- Threading headers are set (In-Reply-To, References)
- Draft appears in Gmail Drafts
- draft_id is returned

### Test: Label Application

**Given**: Email classified as "needs_response"

**When**: Classification job completes

**Then**:
- Needs Response label is applied to thread in Gmail
- Thread is visible in "🤖 AI/Needs Response" view

### Test: Batch Label Modification

**Given**: Multi-message thread with 5 messages

**When**: Label is applied to thread

**Then**:
- Single batch API call modifies all messages
- Not 5 separate API calls

## Agent System Tests

### Test: Route to Agent

**Given**:
- Email from info@dostupnost-leku.cz
- Routing rule: forwarded_from="info@dostupnost-leku.cz" → agent (pharmacy)

**When**: Sync processes email

**Then**:
- Email routes to agent (not pipeline)
- agent_process job is enqueued with profile=pharmacy
- Not classify job

### Test: Agent Tool Use

**Given**: Agent profile with search_drugs tool

**When**: Agent loop executes

**Then**:
- Agent calls search_drugs tool
- Tool result is returned to agent
- Agent uses result to formulate response
- Tool call logged in agent_runs table

### Test: Agent Auto-Send

**Given**: Pharmacy agent with send_reply tool

**When**: Agent decides to auto-send

**Then**:
- send_reply tool is called
- Email is sent via Gmail API (bypassing draft)
- No draft is created
- Event logged: reply_sent

### Test: Agent Create Draft

**Given**: Pharmacy agent with create_draft tool

**When**: Agent decides to create draft for review

**Then**:
- create_draft tool is called
- Gmail draft is created
- Outbox label is applied
- Event logged: draft_created

### Test: Agent Escalate

**Given**: Agent with escalate tool

**When**: Agent decides issue is out of scope

**Then**:
- escalate tool is called
- Action Required label is applied
- Status is set to "skipped"
- Event logged: escalated

### Test: Agent Max Iterations

**Given**: Agent profile with max_iterations=10

**When**: Agent loop runs 10 times without completing

**Then**:
- Loop stops at 10 iterations
- Status is set to "max_iterations"
- Agent run record shows iterations=10
- Error logged

### Test: Preprocessor Extraction (Crisp)

**Given**: Email forwarded from Crisp with patient name and email in body

**When**: Preprocessor parses email

**Then**:
- Patient name is extracted
- Patient email is extracted
- Original message is extracted
- Formatted context is provided to agent

## API Contract Tests

### Test: POST /api/auth/init

**Given**: Valid credentials.json file

**When**: POST /api/auth/init

**Then**:
- Status: 200
- Response: {"user_id": N, "email": "user@example.com", "onboarded": true}
- User created in database
- Labels provisioned in Gmail

### Test: GET /api/users/{user_id}/emails

**Given**: User with 5 pending emails

**When**: GET /api/users/1/emails?status=pending

**Then**:
- Status: 200
- Response: Array of 5 emails with status=pending
- Each email has: id, gmail_thread_id, subject, sender, classification, status

### Test: POST /api/sync?full=true

**Given**: User with last_history_id=12345

**When**: POST /api/sync?user_id=1&full=true

**Then**:
- Status: 200
- Response: {"queued": true, "user_id": 1, "full": true}
- Sync state is cleared (last_history_id=0)
- Full inbox scan is performed

### Test: GET /api/emails/{id}/debug

**Given**: Email with id=123

**When**: GET /api/emails/123/debug

**Then**:
- Status: 200
- Response includes: email, events[], llm_calls[], agent_runs[], timeline[], summary
- All debug data for email is returned

### Test: POST /api/emails/{id}/reclassify

**Given**: Email with id=123, current classification="fyi"

**When**: POST /api/emails/123/reclassify

**Then**:
- Status: 200
- Response: {"status": "queued", "job_id": N, "email_id": 123}
- classify job is enqueued with force=true

### Test: POST /webhook/gmail

**Given**: Valid Gmail Pub/Sub notification

**When**: POST /webhook/gmail with base64-encoded payload

**Then**:
- Status: 200
- Payload is decoded
- User is looked up by email
- sync job is enqueued with history_id

### Test: POST /api/reset

**Given**: Database with emails, jobs, events

**When**: POST /api/reset

**Then**:
- Status: 200
- Response: {"deleted": {"jobs": N, "emails": M, ...}, "total": T}
- All transient data is deleted
- Users, labels, settings are preserved

## End-to-End Workflow Tests

### Test: Complete Email Processing (needs_response)

**Given**: New email arrives in Gmail inbox

**When**: Full pipeline executes

**Then**:
1. Gmail Pub/Sub sends notification
2. Webhook enqueues sync job
3. Sync fetches email via History API
4. Router decides on pipeline route
5. classify job is enqueued
6. Classification: needs_response
7. draft job is enqueued
8. Draft is generated with context
9. Gmail draft is created
10. Outbox label is applied
11. User reviews draft in Gmail
12. User sends draft
13. Cleanup job detects deletion
14. Status is set to sent
15. All events logged in audit trail

**Assertions**:
- Email exists in database with status=sent
- LLM calls logged (classify + draft)
- Events logged (classified, draft_created, sent_detected)
- Labels applied and removed correctly in Gmail

### Test: Complete Email Processing (fyi)

**Given**: New newsletter email arrives

**When**: Full pipeline executes

**Then**:
1. Gmail Pub/Sub sends notification
2. Webhook enqueues sync job
3. Sync fetches email
4. Router decides on pipeline route
5. classify job is enqueued
6. Rules detect automation (List-Unsubscribe header)
7. Classification: fyi
8. No draft job is enqueued
9. FYI label is applied
10. Status is set to skipped
11. All events logged

**Assertions**:
- Email exists with status=skipped, classification=fyi
- No draft_id
- FYI label applied in Gmail
- No draft in Gmail

### Test: Complete Rework Flow

**Given**: Email with existing draft

**When**: User requests rework

**Then**:
1. User adds instruction above ✂️
2. User applies Rework label
3. Gmail History API detects label addition
4. Sync enqueues rework job
5. Rework job fetches draft
6. Extracts instruction
7. Generates new draft with feedback
8. Trashes old draft
9. Creates new draft
10. Increments rework_count
11. Outbox label remains

**Assertions**:
- rework_count=1
- New draft_id in database
- Old draft deleted from Gmail
- New draft in Gmail with updated content
- Event logged: draft_reworked

### Test: Complete Agent Flow (Pharmacy)

**Given**: Email forwarded from Crisp to pharmacy helpdesk

**When**: Full agent pipeline executes

**Then**:
1. Email arrives, Pub/Sub notification sent
2. Sync fetches email
3. Router matches forwarded_from rule → agent route
4. agent_process job is enqueued with profile=pharmacy
5. Preprocessor extracts patient info
6. Agent loop starts with pharmacy tools
7. Agent calls search_drugs tool
8. Tool returns availability data
9. Agent decides to auto-send (straightforward query)
10. Agent calls send_reply tool
11. Email is sent via Gmail API
12. Status is set to sent
13. Agent run record saved

**Assertions**:
- Email status=sent
- Agent run record with tool_calls_log
- No draft created (auto-sent)
- Events logged (agent_started, agent_completed, reply_sent)

## Performance and Reliability Tests

### Test: Concurrent Job Processing

**Given**: 10 pending jobs, 3 workers

**When**: Workers are started

**Then**:
- All 10 jobs are processed
- No job is processed twice
- Jobs complete in parallel (3 at a time)
- All jobs reach completed or failed status

### Test: Gmail API Retry

**Given**: Gmail API returns 503 (service unavailable)

**When**: API call is made

**Then**:
- Request is retried with exponential backoff
- Retry delays: 1s, 2s, 4s
- If still failing after 3 retries, error is logged
- Job is marked for retry

### Test: History API Pagination

**Given**: 150 history records (>100 per page)

**When**: Sync fetches history

**Then**:
- First page (100 records) is fetched
- nextPageToken is followed
- Second page (50 records) is fetched
- All 150 records are processed

### Test: Full Sync Fallback

**Given**:
- last_history_id=old_value (expired)
- History API returns 404

**When**: Sync job processes

**Then**:
- Sync detects expired history ID
- Falls back to full inbox scan
- Queries "in:inbox newer_than:10d"
- Processes all unclassified emails
- Updates last_history_id from getProfile

## Test Data Requirements

Each test should be self-contained and use:
- Synthetic email data (not real user data)
- Mocked LLM responses for deterministic tests
- Stubbed Gmail API for unit tests
- Real Gmail API for integration tests (separate test account)
- Clean database state (reset before each test)

## Test Markers

Tests should be marked for filtering:
- `@unit` - Fast, no external dependencies
- `@integration` - Requires database, may use mocks
- `@e2e` - Requires real LLM API and/or Gmail API
- `@smoke` - Critical path, run on every deploy
