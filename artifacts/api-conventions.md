# API Conventions

## Framework
FastAPI with async handlers, Pydantic request/response models, and dependency injection via `app.state`.

## Endpoints

### Webhook
```
POST /webhook/gmail
```
Receives Gmail Pub/Sub push notifications. Decodes base64 `message.data`, extracts `historyId` and `emailAddress`, creates a sync job.

### Admin — User Management
```
GET    /api/health                              # Health check (DB + LLM)
GET    /api/users                               # List active users
POST   /api/users                               # Create user (triggers onboarding)
GET    /api/users/{user_id}/settings             # Get user settings
PUT    /api/users/{user_id}/settings             # Update setting (key-value)
GET    /api/users/{user_id}/labels               # Get Gmail label mappings
GET    /api/users/{user_id}/emails               # List emails (filter: status, classification)
```

### Briefing
```
GET    /api/briefing/{user_email}               # Inbox summary grouped by classification
```

### Debug — Email Investigation (JSON API)
```
GET    /api/debug/emails                         # List emails with search/filter + debug counts
GET    /api/emails/{email_id}/debug              # Full debug data for a single email
```

**`GET /api/debug/emails`** — List emails with per-email event/LLM/agent counts.
- `?status=pending` — filter by status
- `?classification=needs_response` — filter by classification
- `?q=search+term` — full-text search across subject, snippet, reasoning, sender, thread ID, and email body (via LLM call content)
- `?limit=50` — max results (1–500, default 50)

**`GET /api/emails/{email_id}/debug`** — All debug data for one email:
- `email` — full email record
- `events` — all audit events for the thread
- `llm_calls` — all LLM API calls (classify, draft, rework, agent) with full prompts/responses
- `agent_runs` — agent execution records with tool call logs
- `timeline` — merged chronological view of events + LLM calls + agent runs
- `summary` — pre-computed stats (token totals, latency, error count, LLM breakdown by call type)

### Debug — Email Investigation (HTML UI)
```
GET    /debug/emails                             # Searchable email list (links to debug pages)
GET    /debug/email/{email_id}                   # Unified single-email debug page
```

## Route Organization

```python
# src/api/webhook.py
from fastapi import APIRouter, Request
router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.post("/gmail")
async def gmail_webhook(request: Request):
    ...

# src/api/admin.py
router = APIRouter(prefix="/api", tags=["admin"])

@router.get("/health")
async def health_check(request: Request):
    ...
```

Routes registered in `src/main.py`:
```python
app.include_router(webhook_router)
app.include_router(admin_router)
app.include_router(briefing_router)
app.include_router(debug_router)
```

## Patterns

### Accessing App State
```python
@router.get("/api/users")
async def list_users(request: Request):
    db = request.app.state.db
    config = request.app.state.config
    repo = UserRepository(db)
    users = await repo.list_active()
    return {"users": users}
```

### Error Handling
- Return appropriate HTTP status codes (400, 404, 500)
- Log errors with `logger.error()` before returning error responses
- Webhook endpoint returns 200 even on processing errors (Gmail retries otherwise)

### Query Parameters
```python
@router.get("/api/users/{user_id}/emails")
async def list_emails(
    request: Request,
    user_id: int,
    status: str | None = None,
    classification: str | None = None,
):
    ...
```

## Configuration
- Host/port: `GMA_SERVER_HOST` / `GMA_SERVER_PORT` (default: 0.0.0.0:8000)
- Log level: `GMA_SERVER_LOG_LEVEL` (default: info)
- Webhook secret: `GMA_SERVER_WEBHOOK_SECRET` (optional, for Pub/Sub verification)
