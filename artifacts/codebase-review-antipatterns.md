# Codebase Review: Anti-patterns, Non-Pythonic Code, and Architectural Cracks

**Date:** 2026-02-13
**Scope:** Full `src/` tree, schema, tests

---

## Triage Legend

| Severity | Meaning |
|----------|---------|
| **P0 — fix now** | Will cause bugs or data loss under normal operation |
| **P1 — fix soon** | Correctness risk under concurrency or growth; tech debt that compounds |
| **P2 — plan for** | Design friction that slows future work; non-Pythonic idioms |
| **P3 — consider** | Minor style or ergonomic nits |

---

## P0 — Fix Now

### 1. Synchronous DB inside an async application

**Files:** `src/db/connection.py`, `src/tasks/workers.py`, `src/api/admin.py`

The `Database` class uses synchronous `sqlite3` connections. The worker pool compensates by wrapping every call in `asyncio.to_thread()`, but the API layer does not — every route in `admin.py` and `webhook.py` calls `get_db()` and executes blocking SQL directly on the event loop:

```python
# src/api/admin.py:34 — blocks the event loop
@router.get("/users")
async def list_users() -> list[dict]:
    db = get_db()
    repo = UserRepository(db)
    users = repo.get_active_users()   # ← synchronous sqlite3 call
```

Every `admin.py` endpoint (lines 33–230) and `webhook.py:32` do this. Under any concurrent load the event loop stalls.

**Fix:** Either wrap all route-level DB calls in `await asyncio.to_thread(...)` consistently, or switch to an async DB driver (`aiosqlite`) and make the repository methods async.

### 2. Dead code / logic bug in `sync/engine.py:154`

```python
msg = gmail_client_not_available = None  # need thread_id
```

This line assigns `None` to two variables as a workaround for not having the thread_id in a label-added history record. The `cleanup` job is then enqueued with `message_id` but the `_handle_cleanup` handler in `workers.py:302-313` dispatches on `action` and `thread_id` — the cleanup job for "done" will never have a `thread_id` in its payload because it only receives `message_id`. The handler checks `if action == "done" and thread_id:` which will be falsy (empty string), so **"Done" label events from incremental sync are silently dropped**.

**Fix:** The cleanup job needs to resolve message_id → thread_id (via a Gmail API get_message call) before dispatching, or the sync engine should populate thread_id from the history record.

### 3. `execute_write` returns ambiguous value

**File:** `src/db/connection.py:65-69`

```python
def execute_write(self, sql: str, params: tuple = ()) -> int:
    cursor = conn.execute(sql, params)
    return cursor.lastrowid or cursor.rowcount
```

`lastrowid` is 0 for UPDATE/DELETE statements, and `rowcount` is 0 for INSERT on some edge cases. The `or` operator means an INSERT that returns `lastrowid=0` (possible with `WITHOUT ROWID` tables or `AUTOINCREMENT` edge cases) silently falls through to `rowcount`. Callers like `UserRepository.create()` use the return value as the user ID — if it ever returned `rowcount` instead, the wrong value would propagate as a user ID.

**Fix:** Return a named result or separate `insert()` / `update()` methods, or at minimum use the cursor's `lastrowid` unconditionally for INSERT and `rowcount` unconditionally for UPDATE/DELETE.

---

## P1 — Fix Soon

### 4. New connection per query — no connection reuse

**File:** `src/db/connection.py:29-47`

Every `execute()` / `execute_write()` call opens a new `sqlite3.connect()`, sets PRAGMAs, does work, commits, and closes. This means:

- `PRAGMA journal_mode=WAL` is re-sent on every query (it's persistent, so it's harmless but wasteful).
- `PRAGMA foreign_keys=ON` is per-connection and correct, but opening 5-10 connections per job is expensive.
- No connection pooling or reuse across a request lifecycle.

For SQLite this works but is wasteful. It will break when migrating to PostgreSQL — you can't afford a new TCP connection per query.

**Fix:** Use a connection pool (or at minimum a thread-local connection). For async, `aiosqlite` or `databases` library handles this.

### 5. `asyncio.to_thread` wrapping is pervasive and mechanical

**File:** `src/tasks/workers.py` (throughout)

Every DB and Gmail call in the worker is individually wrapped:

```python
user = await asyncio.to_thread(self.users.get_by_id, job.user_id)
# ...
settings = await asyncio.to_thread(UserSettings, self.db, job.user_id)
# ...
result = await asyncio.to_thread(self.classification_engine.classify, ...)
```

The `_handle_classify` method alone has ~10 `asyncio.to_thread` calls. This is noisy, easy to forget (as the API routes prove — see P0 #1), and means every tiny DB read spawns a thread from the pool.

**Fix:** Make the underlying layer natively async. Short of that, at minimum batch related synchronous work into a single `to_thread` call per logical step, or introduce a helper `async def run_sync(fn, *args)` to reduce noise and make omissions easier to catch in review.

### 6. String-typed enums everywhere — no validation at boundaries

**Files:** `src/db/models.py`, `src/classify/engine.py`, `src/lifecycle/manager.py`

Job types (`"sync"`, `"classify"`, `"draft"`, `"cleanup"`, `"rework"`, `"manual_draft"`), email statuses (`"pending"`, `"drafted"`, `"sent"`, etc.), classification categories, and confidence levels are all bare strings. The dispatcher in `workers.py:107-121` is a long if/elif chain matching string literals.

The schema has CHECK constraints, but Python code freely constructs strings like `"drafted"` or `"rework"` with no compile-time or runtime validation. A typo (e.g., `"rework_requested"` in the schema vs `"rework"` in Python) will pass silently until it hits the DB constraint.

**Actual inconsistency found:** The schema defines status values including `'rework_requested'` but the Python code in `lifecycle/manager.py` never uses that status — it uses `'drafted'` after rework and `'skipped'` at the limit. The `workers.py` code sets statuses without going through the status enum. This divergence will cause confusion.

**Fix:** Define `StrEnum` classes for `JobType`, `EmailStatus`, `Classification`, `Confidence` and use them in code + match statements.

### 7. Repository methods return raw `dict` instead of dataclasses

**File:** `src/db/models.py`

`EmailRecord` exists as a dataclass but is only used for *inserts*. All reads return `dict[str, Any]`:

```python
def get_by_thread(self, user_id: int, thread_id: str) -> dict[str, Any] | None:
```

Consumers then do `email["sender_email"]`, `email.get("subject", "")`, etc. — untyped string key access scattered across `workers.py`, `lifecycle/manager.py`, `briefing.py`. This is a rich source of KeyError bugs and makes refactoring the schema dangerous (no IDE support for renames).

**Fix:** Have read methods return dataclass instances (e.g., `EmailRecord`). Map `sqlite3.Row` → dataclass in the repository, not in every caller.

### 8. `UserSettings.__init__` is called via `asyncio.to_thread` as if it were I/O

**File:** `src/tasks/workers.py:153,236,323,371`

```python
settings = await asyncio.to_thread(UserSettings, self.db, job.user_id)
```

`UserSettings.__init__` just stores two attributes — it does no I/O. The expensive calls happen later in `.contacts`, `.communication_styles`, etc. Wrapping the constructor in `to_thread` is misleading and the actual property accesses that do I/O are then called synchronously on those lines.

### 9. Regex patterns are recompiled on every email

**File:** `src/classify/rules.py:106-144`

```python
for pattern in PAYMENT_PATTERNS:
    if re.search(pattern, content):
```

~36 regex patterns are compiled from strings on every `classify_by_rules()` call. With `re.search(string_pattern, ...)`, Python does cache recently used patterns via an internal LRU, but it's better practice and more explicit to pre-compile:

```python
PAYMENT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [...]]
```

This also avoids the subtle bug that the patterns are not compiled with `re.IGNORECASE` — the code lowercases `content` instead, which doesn't work correctly for all Unicode case folding (relevant since the patterns include Czech diacritics).

### 10. The webhook has no authentication

**File:** `src/api/webhook.py`, `src/sync/webhook.py`

The Gmail Pub/Sub webhook endpoint accepts any POST body with no verification. The `ServerConfig` has a `webhook_secret` field but it's never checked. Anyone who discovers the webhook URL can inject fake sync jobs.

**Fix:** Validate the Pub/Sub push token or use the `webhook_secret` to verify the request origin.

---

## P2 — Plan For

### 11. Module-level singleton with `global` for DB

**File:** `src/db/connection.py:94-111`

```python
_db: Database | None = None

def get_db() -> Database:
    global _db
    if _db is None:
        raise RuntimeError(...)
    return _db
```

Similarly in `src/main.py:29-31`:

```python
_worker_pool: WorkerPool | None = None
_scheduler: Scheduler | None = None
_bg_tasks: list[asyncio.Task] = []
```

Module-level mutable globals with `global` are a Python anti-pattern. They make testing hard (must monkeypatch module state), prevent running multiple app instances, and create import-order coupling.

**Fix:** Use FastAPI's dependency injection (`Depends`) and `app.state` consistently. The DB is already on `app.state.db` in main.py — the routes should use `request.app.state.db` instead of `get_db()`.

### 12. Massive `WorkerPool` class — 493 lines, 8 responsibilities

**File:** `src/tasks/workers.py`

`WorkerPool` handles: job dispatch, sync, classification (with label application and DB writes), draft generation (with context gathering, Gmail draft creation, label moves), cleanup, rework, and manual drafting. This is a God Object.

Each handler has its own mix of Gmail + DB + LLM calls, duplicated patterns (label lookup, thread fetching, event logging), and different error handling. `_handle_draft` and `_handle_manual_draft` share ~80% of their logic but are separate 70-line methods with copy-pasted code (lines 222-300 vs 332-492).

**Fix:** Extract each handler into its own class or function module (e.g., `tasks/handlers/classify.py`). Use a registry pattern for dispatch. Factor shared patterns (label lookup + move, draft creation + DB update + event log) into composable helpers.

### 13. Two nearly-identical config systems

**Files:** `src/config.py`, `src/users/settings.py`

App-level config uses Pydantic Settings with YAML + env vars. Per-user settings use a separate `UserSettings` class backed by `SettingsRepository` with its own YAML fallback. Both load the same YAML files (`communication_styles.yml`, `contacts.yml`), but through different paths and with different caching behavior (none).

`load_communication_styles()` reads from disk on every call — in a classification + draft flow this happens multiple times per email.

**Fix:** Cache YAML reads at startup or at least per-request. Long term, unify the config surface so per-user overrides layer cleanly on top of app defaults.

### 14. No MIME handling for HTML-only emails

**File:** `src/gmail/models.py:53-77`

`Message._extract_body()` only looks for `text/plain` parts. Emails that are HTML-only (no plain text alternative) will have an empty `body`. This is common with marketing emails but also with some corporate mail clients.

The classifier then receives an empty body and must rely solely on subject + snippet (which is plain-text but truncated by Gmail).

**Fix:** Fall back to stripping HTML from `text/html` parts when no `text/plain` is available (using `html.parser` or `beautifulsoup4`).

### 15. `_extract_body` only recurses 2 levels deep

**File:** `src/gmail/models.py:65-75`

```python
for part in payload.get("parts", []):
    if part.get("mimeType") == "text/plain":
        ...
    for sub in part.get("parts", []):
        if sub.get("mimeType") == "text/plain":
```

MIME payloads can be nested arbitrarily deep (e.g., `multipart/mixed` → `multipart/alternative` → `multipart/related` → `text/plain`). The current code only handles 2 levels. Deeply nested emails will return empty bodies.

**Fix:** Use a recursive helper or a `while` loop with a stack.

### 16. `Email.from` address parsing is fragile

**File:** `src/gmail/models.py:30-34`

```python
if "<" in sender and ">" in sender:
    sender_name = sender.split("<")[0].strip().strip('"')
    sender_email = sender.split("<")[1].rstrip(">")
```

This breaks on edge cases like:
- `"Last, First" <email@x.com>` — works but leaves quotes
- `Name <email@x.com>, Other <other@x.com>` — takes wrong part
- Display names containing `<` or `>`

Python's `email.utils.parseaddr` or `email.headerregistry` handles all RFC 5322 cases correctly.

### 17. `handle_done` passes literal string as timestamp

**File:** `src/lifecycle/manager.py:61`

```python
self.emails.update_status(user_id, thread_id, "archived", acted_at="CURRENT_TIMESTAMP")
```

The `update_status` method builds `SET acted_at = ?` with the **string** `"CURRENT_TIMESTAMP"` as a parameter value. This stores the literal string `"CURRENT_TIMESTAMP"` in the `acted_at` column, not the actual timestamp. Same bug on line 96.

**Fix:** Use `datetime.now(timezone.utc).isoformat()` or restructure `update_status` to handle SQL expressions differently from parameter values.

### 18. Pub/Sub webhook returns 400 on invalid data — risks retry storm

**File:** `src/api/webhook.py:38`

Google Pub/Sub retries on non-2xx responses with exponential backoff. Returning 400 for invalid/duplicate notifications will cause Pub/Sub to retry them forever (until the ack deadline). This can create a retry storm for permanently invalid messages.

**Fix:** Return 200 for all well-formed notifications (even if the user is unknown or data is stale). Only return 4xx/5xx for truly transient errors you want retried.

---

## P3 — Consider

### 19. `from typing import Any` used after class that needs it

**File:** `src/llm/gateway.py:26,57`

```python
@classmethod
def parse(cls, response: Any) -> ClassifyResult:  # ← Any used at line 26
    ...

from typing import Any  # ← imported at line 57
```

The `Any` type hint on `ClassifyResult.parse()` at line 26 is used before the import at line 57. This only works because of `from __future__ import annotations` (PEP 563 — annotations are strings, not evaluated). It's legal but confusing and will break if someone removes the future import.

**Fix:** Move the import to the top of the file with the other imports.

### 20. `Enum` import unused in `auth.py`

**File:** `src/gmail/auth.py:6`

```python
from enum import Enum  # never used
```

### 21. Mutable default in `connection.py`

**File:** `src/db/connection.py:51,60`

```python
def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
```

The default `params: tuple = ()` is fine (tuples are immutable), but `execute_many`'s `params_list: list[tuple]` with no default is correctly handled. However, the type annotation `params: tuple` should be `params: tuple[Any, ...] | Sequence[Any]` for precision — callers sometimes pass lists.

### 22. `format` shadows builtin in `gmail/client.py:69`

```python
def get_message(self, message_id: str, format: str = "full") -> Message | None:
```

The parameter name `format` shadows the Python builtin. Harmless but flagged by linters. Consider `fmt` or `message_format`.

### 23. `import base64` inside `_extract_body` staticmethod

**File:** `src/gmail/models.py:57`

```python
@staticmethod
def _extract_body(payload: dict) -> str:
    import base64
```

Local imports in frequently-called methods add per-call overhead (Python checks `sys.modules` each time). `base64` is already imported at module level in `client.py` but not in `models.py`. Move to top-level.

### 24. `json` imported but unused in `users/settings.py:5`

The import of `json` at line 5 of `settings.py` is never used directly — JSON serialization is handled by `SettingsRepository`.

---

## Architectural Cracks — Summary

### The async/sync boundary is the biggest structural problem

The codebase is split between an async FastAPI application and synchronous database + Gmail code. The `asyncio.to_thread()` bridging works but is applied inconsistently (workers: yes, API routes: no) and creates a massive amount of boilerplate. This needs a clear decision: either go fully async with `aiosqlite` + `httpx`/`aiogoogle`, or acknowledge the app is sync-with-async-wrapper and adopt a pattern that enforces the wrapping uniformly.

### The worker pool is a monolith trying to be a microservice

`WorkerPool` at 493 lines is doing the work of 6-8 separate handlers with significant code duplication between `_handle_draft` and `_handle_manual_draft`. As new job types are added, this file will grow unboundedly. The if/elif dispatch, mixed concerns (Gmail + DB + LLM + label management in every handler), and lack of a common handler interface make it the most likely source of future bugs.

### String typing creates invisible coupling

Job types, statuses, classifications, and label keys are all string-typed with no central enum definition. The schema CHECK constraints are the only validation, and they're already out of sync with the Python code (`'rework_requested'` in schema vs `'rework'` never used). Adding a new status or job type requires updating 3-5 files with no compiler help.

### Config is read from disk repeatedly with no caching

`load_communication_styles()` and `load_contacts_config()` hit the filesystem on every call. In a classify-then-draft flow, styles are loaded at least twice. For a multi-user system under load, this becomes a bottleneck.

### The DB layer is structured for SQLite but promised for PostgreSQL

The `Database` class has `NotImplementedError` for PostgreSQL, but the SQL uses SQLite-specific syntax (`INSERT OR REPLACE`, `PRAGMA`, `datetime('now', ?)`, `executescript`). A PostgreSQL migration would require rewriting most of `models.py` and `connection.py`. If PostgreSQL support is planned, consider an ORM or query builder now rather than maintaining two SQL dialects later.
