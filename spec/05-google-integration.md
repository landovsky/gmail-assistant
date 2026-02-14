# 05 — Google API Integration

## Overview

The system integrates with three Google services:
1. **Gmail API** — Read messages, manage labels, create/manage drafts, track history
2. **Google Pub/Sub** — Receive real-time push notifications when Gmail changes occur
3. **Google OAuth 2.0** — Authenticate and authorize access to user Gmail accounts

---

## Authentication

### OAuth Scopes

The system requires a single OAuth scope:
```
https://www.googleapis.com/auth/gmail.modify
```

This grants read/write access to messages, labels, drafts, and settings, but does NOT grant full account access (no delete, no send on behalf).

### Authentication Modes

#### Personal OAuth (default)

For single-user deployments where the server operator is the Gmail user.

**Flow:**
1. On first run, check for cached token file
2. If no token: launch browser-based OAuth consent flow (localhost redirect)
3. User grants consent → receive authorization code
4. Exchange code for access token + refresh token
5. Store tokens to file for future use
6. On subsequent runs: load cached token, auto-refresh if expired using refresh token

**Required files:**
- `credentials.json` — OAuth client credentials (downloaded from Google Cloud Console)
- `token.json` — Cached access/refresh tokens (created automatically after first auth)

**Token lifecycle:**
- Access tokens expire after ~1 hour
- Refresh tokens are long-lived (revoked only by user or after 6 months of inactivity)
- Token refresh is automatic and transparent

#### Service Account

For multi-user deployments with Google Workspace domain-wide delegation.

**Flow:**
1. Load service account key file
2. Create credentials with subject impersonation for the target user's email
3. No user interaction required — service accounts authenticate automatically

**Required files:**
- `service-account-key.json` — Service account private key (from Google Cloud Console)

**Domain-wide delegation** must be configured in Google Workspace Admin to grant the service account access to users' Gmail.

---

## Gmail API Usage

### API Endpoints Used

| Gmail API Method | HTTP | Purpose | Called By |
|-----------------|------|---------|----------|
| `users.messages.list` | GET | Search/list messages | Search, full sync |
| `users.messages.get` | GET | Fetch single message (full or metadata) | Classification, draft context |
| `users.threads.get` | GET | Fetch thread with all messages | Draft generation, lifecycle |
| `users.messages.modify` | POST | Add/remove labels on one message | Apply classification label |
| `users.messages.batchModify` | POST | Add/remove labels on multiple messages | Label transitions |
| `users.drafts.create` | POST | Create draft reply in thread | Draft generation |
| `users.drafts.get` | GET | Fetch draft by ID | Sent detection, rework |
| `users.drafts.delete` | DELETE | Trash a draft | Draft cleanup, rework |
| `users.drafts.list` | GET | List all user drafts | Find thread drafts |
| `users.history.list` | GET | Get changes since historyId | Incremental sync |
| `users.watch` | POST | Register Pub/Sub push notifications | Watch setup |
| `users.stop` | POST | Stop push notifications | Watch teardown |
| `users.labels.list` | GET | List all labels | Label provisioning |
| `users.labels.create` | POST | Create custom label | Onboarding |
| `users.getProfile` | GET | Get user email and historyId | Onboarding, full sync |

All calls use `userId="me"` (authenticated user context).

### Message Parsing

Gmail API returns messages in a nested structure. The system parses:

**Headers extracted:** `From`, `To`, `Subject`, `Date`, `Message-ID`, `Auto-Submitted`, `Precedence`, `List-Id`, `List-Unsubscribe`, `X-Auto-Response-Suppress`, `Feedback-ID`, `X-Autoreply`, `X-Autorespond`, `X-Forwarded-From`, `Reply-To`

**Sender parsing:** The `From` header is parsed to extract both email and display name:
- `"Display Name" <email@domain.com>` → name: "Display Name", email: "email@domain.com"
- `email@domain.com` → name: "", email: "email@domain.com"

**Body extraction:** Recursive MIME traversal:
1. Check root payload for `text/plain`
2. Recurse through `parts[]` for multipart messages
3. Check nested `parts[]` within parts
4. Base64url-decode the `data` field with UTF-8 decoding (replace errors)
5. Return empty string if no plain text part found

### Draft Creation

Drafts are created as MIME messages:
- `From`: authenticated user's email
- `To`: original sender's email
- `Subject`: prefixed with `Re: ` if not already present
- `In-Reply-To`: original message's `Message-ID` header
- `References`: same as `In-Reply-To`
- `threadId`: set to keep the draft in the correct thread

The message body is plain text, base64url-encoded.

### Retry Logic

All Gmail API calls are wrapped in a retry handler with exponential backoff:

**Retryable errors:**
- Network errors: `socket.gaierror`, `ConnectionError`, `ConnectionResetError`, `TimeoutError`, `OSError`, `BrokenPipeError`
- HTTP status codes: 429 (rate limit), 500, 502, 503, 504

**Non-retryable errors** (fail immediately):
- HTTP 4xx (except 429): 400, 401, 403, 404
- Logic errors: `ValueError`, `TypeError`

**Strategy:** Up to 3 retries with exponential backoff (base delay 1s, doubling each attempt: 1s, 2s, 4s).

---

## Gmail History API Sync

The History API provides incremental change tracking since a known `historyId`.

### Incremental Sync Flow

1. Read `last_history_id` from `sync_state` table
2. Call `history.list(startHistoryId=last_history_id)`
3. Handle pagination via `nextPageToken`
4. Process each history record:
   - **messagesAdded**: For INBOX messages, route through the Router to determine job type (`classify` or `agent_process`). Deduplicate by `(job_type, thread_id)`.
   - **labelsAdded**: Check for Done, Rework, or Needs Response labels. Create corresponding cleanup/rework/manual_draft jobs. Deduplicate by `(action_type, thread_id)`.
   - **messagesDeleted**: Create `cleanup` jobs with `check_sent` action.
5. Update `sync_state` with the newest historyId

### Full Sync Fallback

Triggered when:
- User has no sync state record (first run after onboarding)
- `last_history_id` is too old (Gmail returns an error mentioning "historyId")

Process:
1. Build a Gmail search query: `in:inbox newer_than:{N}d` excluding all AI-labeled and trash/spam
2. Fetch up to 50 matching messages
3. Enqueue `classify` jobs for each
4. Get current historyId from `users.getProfile()` and store it

Default lookback: 10 days (configurable).

### Deduplication

Gmail History API reports one entry per message in a thread for a single action. For a thread with N messages, a single label change generates N history entries. The sync engine deduplicates using a per-sync-run `seen_jobs` set keyed by `(job_type, thread_id)`.

---

## Pub/Sub Integration

### Setup

1. A Google Cloud Pub/Sub topic must be pre-created (e.g., `projects/myproject/topics/gmail-push`)
2. The topic must grant publish permissions to `gmail-api-push@system.gserviceaccount.com`
3. A push subscription must be configured to send to the system's webhook URL: `POST /webhook/gmail`

### Watch Registration

The system calls `users.watch()` to tell Gmail to send notifications:

```
topicName: projects/{project}/topics/{topic}
labelIds: ["INBOX", "{needs_response_label}", "{rework_label}", "{done_label}"]
labelFilterBehavior: "INCLUDE"
```

**Label filter rationale:** Including INBOX catches new messages. Including the three action labels (`needs_response`, `rework`, `done`) catches user-initiated label changes that need processing.

**Watch expiration:** Gmail watches expire after 7 days. The system renews all watches every 24 hours proactively.

### Fallback Polling

As a safety net for missed Pub/Sub notifications, the system enqueues a `sync` job for every active user at a configurable interval (default: 15 minutes). This ensures processing continues even if Pub/Sub is temporarily disrupted.

---

## Label Management

### Standard Labels

During onboarding, 9 Gmail labels are created (or existing ones are found by name):

| Key | Gmail Label Name |
|-----|-----------------|
| `parent` | `🤖 AI` |
| `needs_response` | `🤖 AI/Needs Response` |
| `outbox` | `🤖 AI/Outbox` |
| `rework` | `🤖 AI/Rework` |
| `action_required` | `🤖 AI/Action Required` |
| `payment_request` | `🤖 AI/Payment Requests` |
| `fyi` | `🤖 AI/FYI` |
| `waiting` | `🤖 AI/Waiting` |
| `done` | `🤖 AI/Done` |

Labels are created with `labelListVisibility: "labelShow"` and `messageListVisibility: "show"`.

### Label ID Mapping

Gmail assigns opaque IDs to labels (e.g., `Label_abc123`). The mapping from logical key to Gmail ID is stored in the `user_labels` table and looked up at runtime. This supports multiple users with different Gmail accounts.

### Batch Label Operations

When modifying labels on a thread, the system applies changes to ALL messages in the thread using `messages.batchModify()`. This ensures consistent label visibility in Gmail regardless of which message view the user opens.

---

## Rate Limits and Quotas

[UNCLEAR: The system does not implement explicit Gmail API quota management beyond the retry logic for 429 responses. Gmail API quotas are typically 250 units/second for users. The current implementation relies on natural backpressure from the worker pool concurrency limit (default 3 workers) and retry backoff.]
