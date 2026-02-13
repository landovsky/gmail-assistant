# Gmail Assistant v2

A self-hosted, AI-powered email inbox manager that classifies incoming email, generates draft replies, and surfaces everything through Gmail labels you can act on from your phone.

**v2** replaces the Claude Code + MCP runtime with a Python application that talks directly to the Gmail API. Claude (or any LLM) is called only for classification and draft generation — everything else is fast, deterministic code.

## What changed from v1

| | v1 | v2 |
|---|---|---|
| Gmail access | Gmail MCP (through Claude) | `google-api-python-client` direct |
| Orchestration | Bash scripts + Claude Code | Python async application (FastAPI) |
| LLM usage | Claude as runtime (does everything) | LLM called only for classify + draft |
| Speed | 590s for 12 emails | ~15-30s for 12 emails |
| Database | SQLite, single user | SQLite (default) or PostgreSQL |
| Deployment | macOS CLI tool | Docker Compose, any server |
| Models | Locked to Claude | Any model via LiteLLM (Claude, GPT, Gemini, local) |

**What stays the same:** the 8 Gmail labels, 5 classification categories, communication styles, rework loop, safety guarantees (never sends, never deletes).

---

## Quick start

### Prerequisites

- Python 3.11+
- A Google Cloud project with the Gmail API enabled
- An LLM API key (Anthropic, OpenAI, or any LiteLLM-supported provider)

### 1. Install

```bash
cd gmail-assistant
pip install -e .
```

### 2. Set up Google OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** (Desktop application)
3. Download the JSON and save it as:

```
config/credentials.json
```

### 3. Create config files

```bash
cp config/app.example.yml config/app.yml
cp config/contacts.example.yml config/contacts.yml
cp config/communication_styles.example.yml config/communication_styles.yml
```

### 4. Set your LLM API key

```bash
# For Claude (default):
export ANTHROPIC_API_KEY="sk-ant-..."

# Or for OpenAI:
# export OPENAI_API_KEY="sk-..."
# Then edit config/app.yml to use gpt-4o-mini / gpt-4o
```

### 5. Start the server

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

On first run, a browser window opens for Google OAuth consent. After authorizing, the token is saved to `config/token.json` for future runs.

The server:
- Initializes the SQLite database (`data/inbox.db`) automatically
- Starts background workers that process jobs from the queue
- Listens for Gmail Pub/Sub webhook notifications (if configured)
- Exposes REST API endpoints

### 6. Onboard yourself

The first time, you need to create your user and provision Gmail labels. Use the API or a Python shell:

```python
from src.config import AppConfig
from src.db.connection import init_db
from src.gmail.client import GmailService
from src.users.onboarding import OnboardingService

config = AppConfig.from_yaml()
db = init_db(config)
gmail = GmailService(config)
client = gmail.for_user()  # uses your personal OAuth

onboarding = OnboardingService(db)
user_id = onboarding.onboard_user("you@gmail.com", client, display_name="Your Name")
```

This creates the 9 Gmail labels (`🤖 AI/*`), stores their IDs in the database, and imports your config files as user settings.

**Migrating from v1?** If you already have the labels and `config/label_ids.yml`:

```python
user_id = onboarding.onboard_from_existing_config("you@gmail.com", client)
```

---

## Docker deployment

```bash
# Set your API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Build and start
docker compose up -d
```

The container mounts `./data`, `./config`, and `./logs` as volumes, so your database and config persist across restarts.

To customize models or port:

```bash
GMA_LLM_CLASSIFY_MODEL=gpt-4o-mini \
GMA_LLM_DRAFT_MODEL=gpt-4o \
GMA_SERVER_PORT=9000 \
docker compose up -d
```

---

## Configuration

All configuration lives in `config/app.yml` (see `config/app.example.yml`). Every setting can also be overridden with environment variables prefixed `GMA_`.

### `config/app.yml`

```yaml
auth:
  mode: personal_oauth        # or "service_account" for multi-user
  credentials_file: config/credentials.json
  token_file: config/token.json

database:
  backend: sqlite              # or "postgresql"
  sqlite_path: data/inbox.db

llm:
  classify_model: "claude-haiku-4-5-20251001"    # fast, cheap
  draft_model: "claude-sonnet-4-5-20250929"      # high quality

sync:
  fallback_interval_minutes: 15

server:
  host: "0.0.0.0"
  port: 8000
  log_level: info
```

### Switching LLM providers

Change the model names in `config/app.yml` to any [LiteLLM-supported model](https://docs.litellm.ai/docs/providers):

```yaml
llm:
  # OpenAI
  classify_model: "gpt-4o-mini"
  draft_model: "gpt-4o"

  # Google
  # classify_model: "gemini/gemini-2.0-flash"
  # draft_model: "gemini/gemini-2.0-pro"

  # Local (Ollama)
  # classify_model: "ollama/llama3"
  # draft_model: "ollama/llama3"
```

Set the corresponding API key as an environment variable (`OPENAI_API_KEY`, `GEMINI_API_KEY`, etc.).

### `config/contacts.yml`

Per-sender overrides for communication style, language, and a blacklist of senders that are always classified as FYI:

```yaml
style_overrides:
  "vip@company.com": formal

domain_overrides:
  "*.gov.cz": formal

blacklist:
  - "*@noreply.github.com"
  - "*@notifications.google.com"
```

### `config/communication_styles.yml`

Three response styles — **formal**, **business** (default), **informal** — each with rules, sign-off, and example replies. See `config/communication_styles.example.yml`.

---

## API reference

The server exposes a REST API at `http://localhost:8000`. Interactive docs at `/docs` (Swagger UI).

### Health

```
GET /api/health
```

### Webhook (Gmail Pub/Sub)

```
POST /webhook/gmail
```

Receives push notifications from Google Pub/Sub when a mailbox changes. Automatically queues sync jobs.

### Users

```
GET  /api/users                          # List active users
POST /api/users                          # Create user {"email": "...", "display_name": "..."}
GET  /api/users/{id}/settings            # Get user settings
PUT  /api/users/{id}/settings            # Update setting {"key": "...", "value": ...}
GET  /api/users/{id}/labels              # Get label ID mappings
GET  /api/users/{id}/emails              # List emails (?status=pending&classification=needs_response)
```

### Briefing

```
GET /api/briefing/{email}                # Inbox summary for a user
```

Returns classification counts, active items per category, and pending draft count.

---

## How it works

### Processing pipeline

```
New email arrives
  │
  ▼
Sync engine: history.list()              ← ~200ms (1 API call)
  │
  ▼
For each new message (parallel):
  ├─ Rule-based classify                 ← ~1ms   (local, no API)
  ├─ LLM classify (if ambiguous)         ← ~500ms (1 API call)
  ├─ Apply Gmail label                   ← ~100ms (1 API call)
  └─ Store in DB                         ← ~5ms   (local)
  │
  ▼
For needs_response emails (parallel):
  ├─ Generate draft (LLM)               ← ~3-5s  (1 API call)
  ├─ Create Gmail draft                  ← ~100ms (1 API call)
  └─ Move label: Needs Response → Outbox ← ~100ms (1 API call)
```

### Two-tier classification

1. **Rules** (instant, free): blacklist matching, automated sender detection, payment/action/FYI keyword patterns
2. **LLM** (via gateway): called only when rules are not confident enough — nuanced classification with structured JSON output

### Label lifecycle

Same as v1 — the 8 labels and their transitions are unchanged:

- `Needs Response` → draft created → `Outbox` → user sends → detected → `sent`
- `Outbox` → user adds feedback + `Rework` label → regenerate → `Outbox` (max 3 reworks)
- Any label + `Done` → cleanup archives thread, strips labels, keeps Done

### Job queue

Jobs (sync, classify, draft, cleanup, rework) are stored in a `jobs` table and processed by async workers. In SQLite mode this is a simple polling loop; PostgreSQL mode uses `SKIP LOCKED` for concurrent processing.

---

## Project structure

```
src/
├── main.py                    # FastAPI app entry point
├── config.py                  # Configuration (env vars + YAML)
│
├── gmail/
│   ├── auth.py                # Personal OAuth + service account
│   ├── client.py              # GmailService + UserGmailClient
│   └── models.py              # Message, Thread, Draft dataclasses
│
├── llm/
│   ├── gateway.py             # LLMGateway (LiteLLM-backed)
│   └── config.py              # Model selection
│
├── classify/
│   ├── engine.py              # Two-tier classification engine
│   ├── rules.py               # Rule-based pre-classifier
│   └── prompts.py             # LLM prompt templates
│
├── draft/
│   ├── engine.py              # Draft generation + rework
│   └── prompts.py             # Draft prompt templates
│
├── lifecycle/
│   └── manager.py             # Done/Sent/Waiting/Rework handlers
│
├── sync/
│   ├── engine.py              # Incremental sync (history.list)
│   ├── webhook.py             # Pub/Sub notification handler
│   └── watch.py               # Watch renewal scheduler
│
├── users/
│   ├── onboarding.py          # Label provisioning, settings init
│   └── settings.py            # Per-user config management
│
├── db/
│   ├── connection.py          # SQLite / PostgreSQL connection
│   ├── models.py              # Repository classes
│   └── migrations/
│       └── 001_v2_schema.sql  # Database schema
│
├── api/
│   ├── webhook.py             # POST /webhook/gmail
│   ├── admin.py               # User management endpoints
│   └── briefing.py            # Inbox summary endpoint
│
└── tasks/
    └── workers.py             # Async job workers
```

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

49 tests covering: rule-based classification, prompt building, database repositories, Gmail model parsing, rework marker logic.

---

## Environment variables

All settings can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GMA_AUTH_MODE` | `personal_oauth` | `personal_oauth` or `service_account` |
| `GMA_DB_BACKEND` | `sqlite` | `sqlite` or `postgresql` |
| `GMA_DB_SQLITE_PATH` | `data/inbox.db` | SQLite database path |
| `GMA_LLM_CLASSIFY_MODEL` | `claude-haiku-4-5-20251001` | Classification model |
| `GMA_LLM_DRAFT_MODEL` | `claude-sonnet-4-5-20250929` | Draft generation model |
| `GMA_SYNC_PUBSUB_TOPIC` | _(empty)_ | Pub/Sub topic for push notifications |
| `GMA_SYNC_FALLBACK_INTERVAL_MINUTES` | `15` | Polling interval when push is not available |
| `GMA_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `GMA_SERVER_PORT` | `8000` | Server port |
| `GMA_SERVER_LOG_LEVEL` | `info` | Log level (`debug`, `info`, `warning`, `error`) |
| `ANTHROPIC_API_KEY` | — | Required for Claude models |

---

## Safety guarantees

Same as v1:

- **Never sends email** — only creates drafts for you to review and send
- **Never deletes email** — only labels and archives (removes from inbox)
- **Old drafts go to Trash** (recoverable 30 days), never permanently deleted
- **Full audit trail** — every classification, draft, and label change logged to `email_events`
