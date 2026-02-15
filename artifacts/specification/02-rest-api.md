# REST API

## Base URL Structure

- Root: `/` - Redirects to `/debug/emails`
- API Routes: `/api/*` - Core REST endpoints
- Webhook: `/webhook/*` - Gmail Pub/Sub push notifications
- Debug UI: `/debug/*` - HTML debug interface
- Admin UI: `/admin/*` - Database browser

## Authentication

### HTTP Basic Authentication
- Used when configured via environment variables
- Protected endpoints return 401 with `WWW-Authenticate: Basic` header
- Public endpoints: `/webhook/*`, `/api/health`, `/admin/statics/*`

### No Authentication
- If credentials not configured, all endpoints are public
- Designed for single-user or trusted environments

## HTTP Endpoints

### Health & Status

#### GET `/api/health`
Health check endpoint.

**Authentication**: None required

**Response** (200):
```json
{
  "status": "ok"
}
```

### User Management

#### GET `/api/users`
List all active users.

**Authentication**: Required

**Response** (200):
```json
[
  {
    "id": 1,
    "email": "user@example.com",
    "display_name": "John Doe",
    "onboarded_at": "2025-01-15T10:30:00"
  }
]
```

#### POST `/api/users`
Create a new user.

**Authentication**: Required

**Request Body**:
```json
{
  "email": "user@example.com",
  "display_name": "John Doe"  // optional
}
```

**Response** (200):
```json
{
  "id": 1,
  "email": "user@example.com"
}
```

**Error** (409):
```json
{
  "detail": "User already exists"
}
```

#### GET `/api/users/{user_id}/settings`
Get all settings for a user.

**Authentication**: Required

**Path Parameters**:
- `user_id` (integer): User ID

**Response** (200):
```json
{
  "setting_key": "setting_value",
  "another_key": "another_value"
}
```

#### PUT `/api/users/{user_id}/settings`
Update a single user setting.

**Authentication**: Required

**Path Parameters**:
- `user_id` (integer): User ID

**Request Body**:
```json
{
  "key": "setting_name",
  "value": "any_value"  // can be string, number, boolean, object, etc.
}
```

**Response** (200):
```json
{
  "ok": true
}
```

#### GET `/api/users/{user_id}/labels`
Get Gmail labels for a user.

**Authentication**: Required

**Path Parameters**:
- `user_id` (integer): User ID

**Response** (200):
```json
{
  "label_name": "Label_ID_from_Gmail",
  "another_label": "Another_ID"
}
```

#### GET `/api/users/{user_id}/emails`
Get emails for a user with optional filtering.

**Authentication**: Required

**Path Parameters**:
- `user_id` (integer): User ID

**Query Parameters**:
- `status` (string, optional): Filter by status (pending, drafted, sent, archived, skipped, rework_requested)
- `classification` (string, optional): Filter by classification (needs_response, action_required, payment_request, fyi, waiting)

**Default**: Returns pending emails if no filters specified

**Response** (200):
```json
[
  {
    "id": 1,
    "gmail_thread_id": "18d1234567890abcd",
    "gmail_message_id": "18d1234567890abcd",
    "subject": "Email subject",
    "sender_email": "sender@example.com",
    "sender_name": "Sender Name",
    "snippet": "Email preview text...",
    "classification": "needs_response",
    "status": "pending",
    "confidence": "high",
    "received_at": "2025-01-15T10:30:00",
    "processed_at": "2025-01-15T10:30:05",
    "drafted_at": null,
    "acted_at": null
  }
]
```

### Authentication & Onboarding

#### POST `/api/auth/init`
Bootstrap OAuth and onboard the first user.

**Authentication**: Required

**Query Parameters**:
- `display_name` (string, optional): Display name for the user
- `migrate_v1` (boolean, optional): Import label IDs from config file (default: true)

**Behavior**:
- In personal OAuth mode: Triggers OAuth browser consent flow if no token exists
- Gets user's email from Gmail profile
- Onboards the user (provisions labels, imports settings)

**Response** (200):
```json
{
  "user_id": 1,
  "email": "user@example.com",
  "onboarded": true,
  "migrated_v1": true
}
```

**Error** (400):
```json
{
  "detail": "credentials.json not found at /path/to/credentials.json"
}
```

**Error** (500):
```json
{
  "detail": "Could not get email from Gmail profile"
}
```

### Gmail Watch Management

#### POST `/api/watch`
Register Gmail push notifications.

**Authentication**: Required

**Query Parameters**:
- `user_id` (integer, optional): Register watch for specific user. If omitted, registers for all active users.

**Response** (200) - Single user:
```json
{
  "user_id": 1,
  "email": "user@example.com",
  "watch_registered": true
}
```

**Response** (200) - All users:
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

**Error** (400):
```json
{
  "detail": "No pubsub_topic configured in config section"
}
```

**Error** (404):
```json
{
  "detail": "User 123 not found"
}
```

#### GET `/api/watch/status`
Show watch state for all users.

**Authentication**: Required

**Response** (200):
```json
[
  {
    "user_id": 1,
    "email": "user@example.com",
    "last_history_id": "12345",
    "last_sync_at": "2025-01-15T10:30:00",
    "watch_expiration": "2025-01-15T17:30:00",
    "watch_resource_id": "abcd1234_resource_id"
  }
]
```

### Sync Operations

#### POST `/api/sync`
Enqueue a sync job for a user.

**Authentication**: Required

**Query Parameters**:
- `user_id` (integer, optional): User ID to sync (default: 1)
- `full` (boolean, optional): Clear sync state to force full inbox scan (default: false)

**Response** (200):
```json
{
  "queued": true,
  "user_id": 1,
  "full": false
}
```

**Error** (404):
```json
{
  "detail": "User 123 not found. Run POST /api/auth/init first."
}
```

#### POST `/api/reset`
Reset transient data (clears jobs, emails, events, sync state).

**Authentication**: Required

**Behavior**:
- Preserves user accounts, labels, and settings
- Deletes all data from: jobs, emails, email_events, sync_state tables

**Response** (200):
```json
{
  "deleted": {
    "jobs": 45,
    "emails": 123,
    "email_events": 567,
    "sync_state": 3
  },
  "total": 738
}
```

### Briefing / Dashboard

#### GET `/api/briefing/{user_email}`
Get inbox briefing/summary for a user.

**Authentication**: Required

**Path Parameters**:
- `user_email` (string): User's email address

**Response** (200):
```json
{
  "user": "user@example.com",
  "summary": {
    "needs_response": {
      "total": 15,
      "active": 12,
      "items": [
        {
          "thread_id": "18d1234567890abcd",
          "subject": "Important question",
          "sender": "sender@example.com",
          "status": "pending",
          "confidence": "high"
        }
      ]
    },
    "action_required": {
      "total": 8,
      "active": 5,
      "items": []
    },
    "payment_request": {
      "total": 2,
      "active": 2,
      "items": []
    },
    "fyi": {
      "total": 50,
      "active": 0,
      "items": []
    },
    "waiting": {
      "total": 3,
      "active": 3,
      "items": []
    }
  },
  "pending_drafts": 10,
  "action_items": 17
}
```

**Notes**:
- `items` array limited to 10 entries per classification
- `active` excludes emails with status sent or archived
- `action_items` is sum of active needs_response and action_required

**Error** (404):
```json
{
  "detail": "User not found"
}
```

### Debug / Email Inspection

#### GET `/api/debug/emails`
List emails with search, filter, and per-email debug counts.

**Authentication**: Required

**Query Parameters**:
- `status` (string, optional): Filter by status
- `classification` (string, optional): Filter by classification
- `q` (string, optional): Full-text search across subject, snippet, reasoning, sender, thread ID, body
- `limit` (integer, optional): Max results (default: 50, max: 500)

**Response** (200):
```json
{
  "count": 25,
  "limit": 50,
  "filters": {
    "status": "pending",
    "classification": null,
    "q": "invoice"
  },
  "emails": [
    {
      "id": 123,
      "user_id": 1,
      "user_email": "user@example.com",
      "gmail_thread_id": "18d1234567890abcd",
      "subject": "Invoice #12345",
      "sender_email": "billing@vendor.com",
      "classification": "payment_request",
      "status": "pending",
      "confidence": "high",
      "received_at": "2025-01-15T10:30:00",
      "processed_at": "2025-01-15T10:30:05",
      "event_count": 5,
      "llm_call_count": 2,
      "agent_run_count": 0
    }
  ]
}
```

**Notes**:
- Results ordered by email ID descending (newest first)
- Full-text search uses case-insensitive matching

#### GET `/api/emails/{email_id}/debug`
Get all debug data for a specific email.

**Authentication**: Required

**Path Parameters**:
- `email_id` (integer): Email row ID

**Response** (200):
```json
{
  "email": {
    "id": 123,
    "user_id": 1,
    "gmail_thread_id": "18d1234567890abcd",
    "subject": "Email subject",
    "classification": "needs_response",
    "status": "pending",
    "confidence": "high",
    "reasoning": "Sender is asking a direct question...",
    "draft_id": null,
    "rework_count": 0,
    "received_at": "2025-01-15T10:30:00"
  },
  "events": [...],
  "llm_calls": [...],
  "agent_runs": [...],
  "timeline": [...],
  "summary": {
    "email_id": 123,
    "gmail_thread_id": "18d1234567890abcd",
    "classification": "needs_response",
    "status": "pending",
    "event_count": 1,
    "llm_call_count": 1,
    "agent_run_count": 0,
    "total_tokens": 200,
    "total_latency_ms": 450,
    "error_count": 0,
    "llm_breakdown": {
      "classify": {
        "count": 1,
        "tokens": 200,
        "latency_ms": 450
      }
    },
    "rework_count": 0
  }
}
```

**Error** (404):
```json
{
  "detail": "Email 123 not found"
}
```

#### POST `/api/emails/{email_id}/reclassify`
Force reclassification of an email.

**Authentication**: Required

**Path Parameters**:
- `email_id` (integer): Email row ID

**Behavior**:
- Enqueues a classify job with force flag
- Re-runs the LLM classifier

**Response** (200):
```json
{
  "status": "queued",
  "job_id": 456,
  "email_id": 123,
  "current_classification": "needs_response"
}
```

**Error** (400):
```json
{
  "detail": "Email has no Gmail message ID"
}
```

**Error** (404):
```json
{
  "detail": "Email 123 not found"
}
```

### Webhook / Push Notifications

#### POST `/webhook/gmail`
Receive Gmail Pub/Sub push notifications.

**Authentication**: None required (public endpoint)

**Request Body**:
```json
{
  "message": {
    "data": "base64_encoded_data",
    "messageId": "1234567890",
    "publishTime": "2025-01-15T10:30:00Z"
  },
  "subscription": "projects/project-id/subscriptions/subscription-name"
}
```

**Decoded data field**:
```json
{
  "emailAddress": "user@example.com",
  "historyId": "12345"
}
```

**Behavior**:
- Decodes base64 data
- Looks up user by email address
- Enqueues a sync job with the history ID

**Status Codes**:
- 200: Notification processed successfully
- 400: Invalid notification format
- 500: Internal processing error

## HTML Debug Interface

### GET `/debug/emails`
HTML page listing emails with debug links.

**Authentication**: Required

**Query Parameters**:
- `status` (string, optional): Filter by status
- `classification` (string, optional): Filter by classification
- `q` (string, optional): Search query

**Response**: HTML page with email list, search filters, navigation

### GET `/debug/email/{email_id}`
HTML debug page for a specific email.

**Authentication**: Required

**Path Parameters**:
- `email_id` (integer): Email row ID

**Response**: HTML page showing:
- Email details and metadata
- Chronological timeline of events
- Events table
- LLM calls with expandable prompts/responses
- Agent runs (if applicable)
- Navigation to prev/next email

## Admin UI

### GET `/admin/*`
Database administration interface.

**Authentication**: Required

**Features**:
- Browse/edit all database tables
- View relationships between records
- Read-only mode for safety

**Tables exposed**:
- users, user_labels, user_settings, sync_state
- emails, email_events, llm_calls, jobs

## Status Codes

All endpoints may return:
- 200 OK: Request successful
- 400 Bad Request: Invalid parameters or missing data
- 401 Unauthorized: Missing or invalid credentials
- 404 Not Found: Resource does not exist
- 409 Conflict: Resource already exists
- 500 Internal Server Error: Unexpected server error

## Error Response Format

```json
{
  "detail": "Human-readable error message"
}
```

## Content Types

- **Request**: `application/json` for POST/PUT endpoints
- **Response**:
  - JSON endpoints: `application/json`
  - HTML endpoints: `text/html`
  - Webhook: Empty body or plain text

## Filtering & Search

### Email Filtering
By status: pending, drafted, rework_requested, sent, skipped, archived
By classification: needs_response, action_required, payment_request, fyi, waiting
Full-text search: subject, snippet, reasoning, sender email, thread ID, body content

### Pagination
- Limit-based (default: 50, max: 500)
- No offset or cursor pagination
- Ordered by ID descending (newest first)

## Sorting
- Fixed ordering: ID descending (newest first)
- No custom sorting options

## Missing Features (Potential Enhancements)
- Rate limiting
- CORS configuration
- API versioning
- Bulk operations
- DELETE endpoints
- PATCH endpoints
- Outgoing webhooks
- Cursor-based pagination
