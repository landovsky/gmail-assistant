# 03 — API Contracts

## Overview

The system exposes a JSON API for administration, webhook ingestion, and monitoring. There is **no authentication or authorization on any endpoint** — all endpoints are open. The system is designed to run on a private network or behind an authenticating reverse proxy.

All responses use `Content-Type: application/json`. Error responses use standard HTTP status codes with a JSON body containing a `detail` field.

---

## Webhook

### POST /webhook/gmail

Receives Gmail Pub/Sub push notifications. Google Cloud Pub/Sub sends these automatically when Gmail events occur for watched users.

**Request body** (sent by Google Pub/Sub):
```json
{
  "message": {
    "data": "<base64-encoded-json>",
    "messageId": "string",
    "publishTime": "string"
  },
  "subscription": "projects/{project}/subscriptions/{subscription}"
}
```

**Decoded `message.data`** (base64 → JSON):
```json
{
  "emailAddress": "user@example.com",
  "historyId": 12345
}
```

**Processing:**
1. Base64-decode `message.data`
2. Parse JSON to extract `emailAddress` and `historyId`
3. Look up user by email in the database
4. If user found: enqueue a `sync` job with the `history_id`
5. Return success

**Responses:**
- `200` — Notification processed (or safely ignored if user not found)
- `400` — Invalid notification format (missing/malformed data)
- `500` — Internal error during processing

**Edge cases:**
- Unknown email address: logged and ignored (200 returned to prevent Pub/Sub retries)
- Malformed base64 or JSON: returns 400
- Database errors: returns 500

---

## Admin API (prefix: /api)

### GET /api/health

Simple liveness probe.

**Response (200):**
```json
{
  "status": "ok"
}
```

---

### GET /api/users

List all active users.

**Response (200):**
```json
[
  {
    "id": 1,
    "email": "user@example.com",
    "display_name": "User Name",
    "onboarded_at": "2025-02-13T12:00:00"
  }
]
```

---

### POST /api/users

Create a new user account.

**Request body:**
```json
{
  "email": "newuser@example.com",
  "display_name": "Optional Name"  // optional
}
```

**Response (200):**
```json
{
  "id": 2,
  "email": "newuser@example.com"
}
```

**Error responses:**
- `409` — User with this email already exists

---

### GET /api/users/{user_id}/settings

Get all settings for a user.

**Response (200):**
```json
{
  "communication_styles": { ... },
  "contacts": { ... }
}
```

Returns an empty object `{}` if no settings are stored.

---

### PUT /api/users/{user_id}/settings

Update a single setting.

**Request body:**
```json
{
  "key": "setting_name",
  "value": <any JSON-serializable value>
}
```

**Response (200):**
```json
{
  "ok": true
}
```

Uses upsert semantics — creates the setting if it doesn't exist, replaces it if it does.

---

### GET /api/users/{user_id}/labels

Get Gmail label mappings for a user.

**Response (200):**
```json
{
  "needs_response": "Label_abc123",
  "outbox": "Label_def456",
  "rework": "Label_ghi789",
  ...
}
```

Keys are standard label keys; values are Gmail API label IDs.

---

### GET /api/users/{user_id}/emails

Get emails for a user with optional filtering.

**Query parameters:**
- `status` (optional) — Filter by email status
- `classification` (optional) — Filter by classification

If neither parameter is provided, defaults to `status=pending`.

**Response (200):**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "gmail_thread_id": "thread_123",
    "gmail_message_id": "msg_456",
    "sender_email": "sender@example.com",
    "sender_name": "Sender Name",
    "subject": "Email Subject",
    "snippet": "Preview text...",
    "received_at": "2025-02-13T10:00:00",
    "classification": "needs_response",
    "confidence": "high",
    "reasoning": "Direct question asked",
    "detected_language": "en",
    "resolved_style": "business",
    "message_count": 1,
    "status": "pending",
    "draft_id": null,
    "rework_count": 0,
    "last_rework_instruction": null,
    "vendor_name": null,
    "processed_at": "2025-02-13T10:05:00",
    "drafted_at": null,
    "acted_at": null,
    "created_at": "2025-02-13T10:00:00",
    "updated_at": "2025-02-13T10:05:00"
  }
]
```

---

### POST /api/sync

Trigger a sync job for a user.

**Query parameters:**
- `user_id` (integer, default: 1) — Which user to sync
- `full` (boolean, default: false) — If true, deletes existing sync state to force a full inbox scan

**Response (200):**
```json
{
  "queued": true,
  "user_id": 1,
  "full": false
}
```

---

### POST /api/reset

Clear transient data. Development/testing utility.

**Response (200):**
```json
{
  "deleted": {
    "jobs": 15,
    "emails": 42,
    "email_events": 128,
    "sync_state": 3
  },
  "total": 188
}
```

**Behavior:** Deletes all rows from `jobs`, `emails`, `email_events`, and `sync_state`. Preserves `users`, `user_labels`, and `user_settings`.

---

### POST /api/auth/init

Bootstrap OAuth and onboard the first user. Only relevant for personal OAuth mode.

**Query parameters:**
- `display_name` (string, optional) — Display name for the user
- `migrate_v1` (boolean, default: true) — Import label IDs from legacy config file

**Response (200):**
```json
{
  "user_id": 1,
  "email": "user@gmail.com",
  "onboarded": true,
  "migrated_v1": true
}
```

**Error responses:**
- `400` — OAuth credentials file not found
- `500` — Cannot retrieve email from Gmail profile

**Behavior:**
1. Triggers browser-based OAuth consent flow if no cached token exists
2. Gets user's email from Gmail profile
3. Creates user record
4. Provisions Gmail labels (creates 9 labels in Gmail)
5. Imports settings from YAML config files
6. Seeds sync state with current history ID

---

### POST /api/watch

Register Gmail watch() for Pub/Sub push notifications.

**Query parameters:**
- `user_id` (integer, optional) — Register for a specific user; if omitted, registers all active users

**Response (200) — single user:**
```json
{
  "user_id": 1,
  "email": "user@example.com",
  "watch_registered": true
}
```

**Response (200) — all users:**
```json
{
  "results": [
    {
      "user_id": 1,
      "email": "user@example.com",
      "watch_registered": true
    }
  ]
}
```

**Error responses:**
- `400` — No Pub/Sub topic configured
- `404` — User ID not found (when user_id provided)

---

### GET /api/watch/status

Show watch state for all users.

**Response (200):**
```json
[
  {
    "user_id": 1,
    "email": "user@example.com",
    "last_history_id": "123456",
    "last_sync_at": "2025-02-13T14:30:00",
    "watch_expiration": "1739472600",
    "watch_resource_id": "resource_xyz"
  }
]
```

---

## Briefing API (prefix: /api)

### GET /api/briefing/{user_email}

Get an inbox summary for a user.

**Path parameters:**
- `user_email` — User's email address

**Response (200):**
```json
{
  "user": "user@example.com",
  "summary": {
    "needs_response": {
      "total": 5,
      "active": 3,
      "items": [
        {
          "thread_id": "thread_123",
          "subject": "Subject line",
          "sender": "sender@example.com",
          "status": "pending",
          "confidence": "high"
        }
      ]
    },
    "action_required": { "total": 2, "active": 2, "items": [] },
    "payment_request": { "total": 0, "active": 0, "items": [] },
    "fyi": { "total": 12, "active": 5, "items": [] },
    "waiting": { "total": 3, "active": 1, "items": [] }
  },
  "pending_drafts": 2,
  "action_items": [ ... ]
}
```

**Notes:**
- Items are limited to 10 per classification category
- `action_items` combines `needs_response` and `action_required` active items
- `pending_drafts` counts `needs_response` emails with status `pending`

**Error responses:**
- `404` — User with given email not found

---

## Admin Dashboard

A web-based admin UI is mounted at `/admin/`. It provides **read-only** access to all database tables:

- **Users** — List, search by email, view details
- **User Labels** — View label mappings per user
- **User Settings** — View settings per user
- **Sync State** — View sync progress and watch status
- **Emails** — List with filtering by classification/status, search by subject/sender/thread_id, view full details including reasoning
- **Email Events** — Audit trail, search by thread_id/event_type, sorted by time
- **LLM Calls** — View call details including prompts, responses, tokens, latency, errors
- **Jobs** — View job queue status, filter by type/status

All admin views are strictly read-only (no create, edit, or delete operations).

---

## Error Response Format

All error responses follow this shape:

```json
{
  "detail": "Human-readable error description"
}
```

With the corresponding HTTP status code (400, 404, 409, 500).

---

## Pagination

No pagination is implemented on any endpoint. All list endpoints return full result sets. [UNCLEAR: Whether this is intentional for small-scale use or an omission. The briefing endpoint limits items to 10 per category, but other list endpoints have no limits.]
