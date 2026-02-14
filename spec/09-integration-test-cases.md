# 09 — Integration & Acceptance Test Cases

## Overview

These test cases define the expected system behavior regardless of implementation stack. They cover the happy paths and key failure modes for all major features. Each test case specifies preconditions, actions, and expected outcomes.

Tests are grouped by feature area. Mock or stub external services (Gmail API, LLM) as needed — the focus is on verifying the system's orchestration logic, not the external services themselves.

---

## 1. User Onboarding

### TC-1.1: First-time user onboarding

**Preconditions:** No users in the database. OAuth credentials available.

**Actions:**
1. Call `POST /api/auth/init`

**Expected:**
- User record created in `users` table with email from Gmail profile
- `onboarded_at` is set
- 9 labels created in Gmail (or existing ones found)
- All 9 label mappings stored in `user_labels`
- Communication styles and contacts imported to `user_settings`
- Sync state created with current historyId from Gmail profile
- Response contains user_id and email

### TC-1.2: Duplicate onboarding is idempotent

**Preconditions:** User already exists and is onboarded.

**Actions:**
1. Call `POST /api/auth/init` again

**Expected:**
- No duplicate user created
- Existing user_id returned
- Labels re-provisioned (idempotent)
- No errors

---

## 2. Webhook & Sync

### TC-2.1: Valid Pub/Sub notification triggers sync

**Preconditions:** User exists with sync state. Gmail has new messages.

**Actions:**
1. POST to `/webhook/gmail` with valid base64-encoded payload containing user's email and a historyId

**Expected:**
- Response: 200
- A `sync` job is enqueued with the provided historyId
- Worker processes the sync job
- History records are fetched from Gmail
- Downstream jobs (classify, cleanup, etc.) are enqueued based on history content

### TC-2.2: Webhook with unknown email is ignored gracefully

**Preconditions:** No user with email "unknown@example.com" exists.

**Actions:**
1. POST to `/webhook/gmail` with payload for "unknown@example.com"

**Expected:**
- Response: 200 (not 4xx — prevents Pub/Sub retry storms)
- No jobs enqueued
- Warning logged

### TC-2.3: Malformed webhook payload returns 400

**Actions:**
1. POST to `/webhook/gmail` with invalid JSON or missing `message.data`

**Expected:**
- Response: 400

### TC-2.4: Full sync triggered when no sync state exists

**Preconditions:** User exists but `sync_state` row is missing.

**Actions:**
1. Enqueue and process a `sync` job for the user

**Expected:**
- Full inbox scan executed (search for recent unclassified emails)
- Classify jobs enqueued for found messages
- Sync state created with current historyId

### TC-2.5: Full sync triggered when historyId is stale

**Preconditions:** User has sync state with very old historyId. Gmail API returns error about historyId.

**Actions:**
1. Enqueue and process a `sync` job

**Expected:**
- History API call fails gracefully
- Full sync fallback is executed
- New sync state stored

### TC-2.6: Deduplication within a single sync

**Preconditions:** Gmail History API returns 3 `messagesAdded` entries for the same thread (3 messages in a single thread).

**Actions:**
1. Process the sync

**Expected:**
- Only 1 classify job is enqueued (not 3)
- Deduplication key is `(job_type, thread_id)`

---

## 3. Classification

### TC-3.1: Normal email classified as needs_response triggers draft

**Preconditions:** User onboarded. Gmail returns a personal email with a question.

**Actions:**
1. Process a classify job for this email

**Expected:**
- LLM called with classification prompt
- Email record created with `classification=needs_response`
- "Needs Response" label applied to message in Gmail
- `classified` event logged
- `draft` job enqueued
- Email `status=pending`

### TC-3.2: Automated email overrides LLM needs_response to fyi

**Preconditions:** Email has `List-Unsubscribe` header. LLM returns `needs_response`.

**Actions:**
1. Process a classify job

**Expected:**
- Rule engine detects `is_automated=true`
- LLM classification of `needs_response` is overridden to `fyi`
- "FYI" label applied (not "Needs Response")
- No draft job enqueued

### TC-3.3: Blacklisted sender classified as fyi

**Preconditions:** User settings include blacklist pattern `*@spam.example.com`. Email is from `newsletter@spam.example.com`.

**Actions:**
1. Process a classify job

**Expected:**
- Rule engine matches blacklist
- Classified as `fyi` with high confidence
- LLM still called (rule shortcut disabled), but safety net applies
- No draft job enqueued

### TC-3.4: Already-classified thread is skipped

**Preconditions:** Thread already has an email record in the database.

**Actions:**
1. Process a classify job for a new message in the same thread

**Expected:**
- Job completes immediately with no changes
- No LLM call made
- No label changes

### TC-3.5: LLM returns unparseable response

**Preconditions:** LLM returns non-JSON text.

**Actions:**
1. Process a classify job

**Expected:**
- Defaults to `needs_response` with low confidence
- Reasoning contains parse error info
- Draft job is still enqueued (safer to over-triage)

### TC-3.6: Classification with communication style resolution

**Preconditions:** Contacts config has `style_overrides: {"friend@example.com": "casual"}`.

**Actions:**
1. Process a classify job for email from friend@example.com

**Expected:**
- `resolved_style` set to `casual` on the email record

---

## 4. Draft Generation

### TC-4.1: Successful draft creation

**Preconditions:** Email classified as `needs_response`, status `pending`.

**Actions:**
1. Process a draft job

**Expected:**
- Thread fetched from Gmail
- Context gathering attempted
- LLM called with draft prompt
- Draft body wrapped with `✂️` marker
- Gmail draft created in the thread
- "Needs Response" label removed from all thread messages
- "Outbox" label added to all thread messages
- Email status updated to `drafted`
- `draft_id` stored
- `draft_created` event logged

### TC-4.2: Draft skipped for non-pending email

**Preconditions:** Email exists but status is `drafted` (already processed).

**Actions:**
1. Process a draft job for this thread

**Expected:**
- Job completes immediately with no changes

### TC-4.3: Stale drafts are cleaned up

**Preconditions:** Thread already has a draft from a previous failed attempt.

**Actions:**
1. Process a draft job

**Expected:**
- Old draft trashed before new one is created
- Only one draft exists after processing

### TC-4.4: Context gathering failure does not block draft

**Preconditions:** Context gathering fails (e.g., Gmail search API error).

**Actions:**
1. Process a draft job

**Expected:**
- Draft generated without related context
- No error raised
- Warning logged

---

## 5. Rework Loop

### TC-5.1: First rework regenerates draft

**Preconditions:** Email with status `drafted`, rework_count=0. User wrote "make it shorter" above the `✂️` marker and applied Rework label.

**Actions:**
1. Process a rework job

**Expected:**
- User instruction "make it shorter" extracted from draft
- Old draft trashed
- New draft generated with rework prompt
- New Gmail draft created
- "Rework" label removed, "Outbox" label added
- `rework_count` incremented to 1
- `draft_reworked` event logged with instruction

### TC-5.2: Rework with no instruction uses default

**Preconditions:** User applied Rework label but didn't write any instructions above the marker.

**Actions:**
1. Process a rework job

**Expected:**
- Instruction defaults to "(no specific instruction provided)"
- Draft still regenerated

### TC-5.3: Third rework triggers limit

**Preconditions:** Email with rework_count=2.

**Actions:**
1. Process a rework job

**Expected:**
- Draft regenerated with warning prefix: "⚠️ This is the last automatic rework..."
- Labels: Rework → Action Required (not Outbox)
- Status remains `drafted` (rework_count=3)

### TC-5.4: Fourth rework attempt hits hard limit

**Preconditions:** Email with rework_count=3 (already at limit).

**Actions:**
1. Process a rework job

**Expected:**
- No LLM call made
- Labels: Rework → Action Required
- Status set to `skipped`
- `rework_limit_reached` event logged

---

## 6. Lifecycle Management

### TC-6.1: Done handler archives thread

**Preconditions:** Email exists with "Outbox" label. User applies "Done" label.

**Actions:**
1. Process a cleanup job with action=done

**Expected:**
- All AI labels removed from all thread messages
- INBOX label removed (thread archived)
- "Done" label kept
- Status updated to `archived`
- `archived` event logged

### TC-6.2: Sent detection when draft disappears

**Preconditions:** Email with draft_id. Draft no longer exists in Gmail (user sent it).

**Actions:**
1. Process a cleanup job with action=check_sent

**Expected:**
- Gmail draft GET returns null/not-found
- "Outbox" label removed
- Status updated to `sent`
- `sent_detected` event logged

### TC-6.3: Sent detection when draft still exists

**Preconditions:** Email with draft_id. Draft still exists in Gmail.

**Actions:**
1. Process a cleanup job with action=check_sent

**Expected:**
- No changes made
- Returns false

### TC-6.4: Manual draft triggered by user label

**Preconditions:** User applies "Needs Response" label to an unclassified thread.

**Actions:**
1. Sync detects label change, creates manual_draft job
2. Process the manual_draft job

**Expected:**
- Email record created with `classification=needs_response`, `reasoning="Manually requested by user"`
- Draft generated and created in Gmail
- Labels: Needs Response → Outbox
- `draft_created` event logged

---

## 7. Agent Framework

### TC-7.1: Routing to agent profile

**Preconditions:** Routing rule matches `forwarded_from: "info@pharmacy.com"` → agent profile "pharmacy".

**Actions:**
1. New email arrives from forwarded source
2. Sync engine processes it

**Expected:**
- Router returns route=agent, profile=pharmacy
- `agent_process` job enqueued (not `classify`)
- Payload includes `profile: "pharmacy"`

### TC-7.2: Agent loop completes with tool calls

**Preconditions:** Agent profile configured with tools. LLM returns tool calls then completes.

**Actions:**
1. Process agent_process job

**Expected:**
- Agent run record created with status `running`
- LLM called with tools in conversation
- Tools executed via registry
- Agent run updated: status=`completed`, tool_calls_log populated
- `classified` event logged with iteration/tool call summary

### TC-7.3: Agent loop hits max iterations

**Preconditions:** Agent profile with max_iterations=2. LLM keeps making tool calls.

**Actions:**
1. Process agent_process job

**Expected:**
- Agent runs for exactly 2 iterations
- Agent run updated: status=`max_iterations`
- Last assistant message preserved as final_message

### TC-7.4: Agent with unknown profile fails gracefully

**Preconditions:** Job payload references profile "nonexistent".

**Actions:**
1. Process agent_process job

**Expected:**
- Error logged about unknown profile
- Job completes (no crash)

---

## 8. Job Queue

### TC-8.1: Concurrent workers don't process same job

**Preconditions:** Single pending job. Multiple workers running.

**Actions:**
1. Two workers call claim_next simultaneously

**Expected:**
- Exactly one worker gets the job
- The other gets null
- Job is processed once

### TC-8.2: Failed job retries up to max_attempts

**Preconditions:** A job that will fail on processing (e.g., Gmail API error).

**Actions:**
1. Job fails on first attempt
2. Job retried on second attempt
3. Job fails again on second attempt
4. Job retried on third attempt
5. Job fails on third attempt (max_attempts=3)

**Expected:**
- After 3 failures: job status=`failed`, error_message set
- No more retries

### TC-8.3: Successful retry after transient failure

**Preconditions:** A job that fails once, then succeeds.

**Actions:**
1. Job fails on first attempt (transient error)
2. Job retried and succeeds on second attempt

**Expected:**
- Job status=`completed`
- attempts=2

---

## 9. API Endpoints

### TC-9.1: Health check returns ok

**Actions:**
1. GET /api/health

**Expected:**
- Response: 200, `{"status": "ok"}`

### TC-9.2: Create user with duplicate email

**Preconditions:** User with email "existing@example.com" exists.

**Actions:**
1. POST /api/users with `{"email": "existing@example.com"}`

**Expected:**
- Response: 409 with detail about existing user

### TC-9.3: Reset clears transient data but preserves users

**Preconditions:** Database has users, labels, settings, emails, events, jobs.

**Actions:**
1. POST /api/reset

**Expected:**
- emails, email_events, jobs, sync_state tables emptied
- users, user_labels, user_settings preserved
- Response contains deletion counts

### TC-9.4: Briefing returns categorized summary

**Preconditions:** User has emails in multiple classifications and statuses.

**Actions:**
1. GET /api/briefing/{user_email}

**Expected:**
- Summary grouped by classification with totals and active counts
- Items limited to 10 per category
- action_items combines needs_response and action_required
- pending_drafts count is accurate

### TC-9.5: Briefing for unknown user returns 404

**Actions:**
1. GET /api/briefing/nobody@example.com

**Expected:**
- Response: 404

### TC-9.6: Watch registration requires pubsub topic

**Preconditions:** No pubsub_topic configured.

**Actions:**
1. POST /api/watch

**Expected:**
- Response: 400 with detail about missing topic

---

## 10. Scheduler

### TC-10.1: Watch renewal runs on startup

**Preconditions:** User exists with active watch.

**Actions:**
1. Application starts

**Expected:**
- Watch renewed for all active users
- sync_state updated with new expiration

### TC-10.2: Fallback sync enqueues jobs periodically

**Preconditions:** Fallback interval set to 15 minutes. User exists.

**Actions:**
1. Wait for fallback interval to elapse

**Expected:**
- sync job enqueued for each active user
- Payload has empty history_id

---

## 11. End-to-End Scenarios

### TC-11.1: Full email lifecycle — classify, draft, send

1. Email arrives → webhook → sync → classify → draft
2. Verify: email record created, draft in Gmail, labels correct
3. User sends the draft in Gmail
4. Next sync detects deletion → sent detection
5. Verify: status=`sent`, "Outbox" label removed

### TC-11.2: Full email lifecycle — classify, draft, rework, send

1. Email arrives → classify as needs_response → draft created
2. User writes instructions above ✂️, applies Rework label
3. Next sync detects rework → regenerate draft
4. Verify: rework_count=1, new draft, labels correct
5. User sends the reworked draft
6. Verify: status=`sent`

### TC-11.3: Full email lifecycle — classify, draft, done

1. Email arrives → classify as needs_response → draft created
2. User applies Done label (decides not to respond)
3. Next sync detects done → archive
4. Verify: status=`archived`, all AI labels removed, INBOX removed

### TC-11.4: FYI email — no draft generated

1. Newsletter email arrives → classify as fyi
2. Verify: "FYI" label applied, no draft job enqueued, status=`pending`

### TC-11.5: Agent-routed email

1. Email from matching sender arrives → router selects agent route
2. Agent loop executes with tool calls
3. Verify: agent_run record created, tool_calls_log populated, events logged

### TC-11.6: Manual draft request

1. User applies "Needs Response" label to an unprocessed email
2. Sync detects label change → manual_draft job
3. Verify: email record created, draft generated, labels transitioned to Outbox
