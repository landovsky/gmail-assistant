# Database Conventions

## Backend
- **Default**: SQLite via `aiosqlite` (async)
- **Upgrade path**: PostgreSQL via `asyncpg` (schema-compatible, not yet fully wired)
- **Location**: `data/inbox.db` (configurable via `GMA_DB_SQLITE_PATH`)

## Schema (10 Tables)

Defined in `src/db/migrations/001_v2_schema.sql`.

### Core Tables

**`users`** — User accounts
```sql
id INTEGER PRIMARY KEY, email TEXT UNIQUE, display_name TEXT,
is_active BOOLEAN, onboarded_at DATETIME, created_at DATETIME
```

**`emails`** — Central email tracking (one row per thread per user)
```sql
id, user_id (FK), gmail_thread_id, gmail_message_id,
sender_email, sender_name, subject, snippet, received_at,
classification ('needs_response'|'action_required'|'payment_request'|'fyi'|'waiting'),
confidence ('high'|'medium'|'low'), reasoning, detected_language, resolved_style,
status ('pending'|'drafted'|'rework_requested'|'sent'|'skipped'|'archived'),
draft_id, rework_count (0-3), last_rework_instruction,
vendor_name, message_count, processed_at, drafted_at, acted_at
UNIQUE(user_id, gmail_thread_id)
```

**`jobs`** — Work queue
```sql
id, job_type ('sync'|'classify'|'draft'|'cleanup'|'rework'),
user_id (FK), payload (JSON), status ('pending'|'running'|'completed'|'failed'),
attempts (0-3), max_attempts, error_message, created_at, started_at, completed_at
```

**`email_events`** — Immutable audit log
```sql
id, user_id, gmail_thread_id,
event_type ('classified'|'label_added'|'label_removed'|'draft_created'|...),
detail, label_id, draft_id, created_at
```

**`user_labels`** — Per-user Gmail label ID mapping
```sql
user_id + label_key (PK), gmail_label_id, gmail_label_name
```

**`user_settings`** — JSON key-value store per user
```sql
user_id + setting_key (PK), setting_value (JSON)
```

**`sync_state`** — Per-user sync progress
```sql
user_id (PK), last_history_id, last_sync_at, watch_resource_id, watch_expiration
```

## Repository Pattern

All database access goes through repository classes in `src/db/models.py`:

```python
class EmailRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create(self, user_id: int, gmail_thread_id: str, ...) -> int:
        ...

    async def get_by_thread_id(self, user_id: int, thread_id: str) -> dict | None:
        ...

    async def update_classification(self, email_id: int, classification: str, ...) -> None:
        ...
```

### Available Repositories
- `UserRepository` — CRUD for users, list_active, get_by_email
- `EmailRepository` — Email CRUD, filter by status/classification, update classification/draft
- `JobRepository` — Job queue: create, claim_next, complete, fail, retry
- `SyncStateRepository` — Per-user sync state (historyId, watch)
- `EventRepository` — Append-only audit log
- `LabelRepository` — Per-user Gmail label mappings
- `SettingsRepository` — Per-user JSON settings

## Conventions

### Async All the Way
```python
async with db.connection() as conn:
    await conn.execute("INSERT INTO ...", params)
    rows = await conn.fetchall("SELECT ...")
```

### Parameterized Queries
Always use parameter binding — never string interpolation:
```python
await conn.execute(
    "SELECT * FROM emails WHERE user_id = ? AND classification = ?",
    (user_id, classification),
)
```

### Audit Logging
Every significant state transition logs to `email_events`:
```python
await event_repo.log(
    user_id=1,
    gmail_thread_id="thread123",
    event_type="classified",
    detail="needs_response (high confidence)",
)
```

### Migrations
- SQL files in `src/db/migrations/` run at startup
- Schema is forward-compatible with PostgreSQL
- Use `IF NOT EXISTS` for idempotent migrations
