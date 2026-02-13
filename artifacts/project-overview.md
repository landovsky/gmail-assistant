# Gmail Assistant v2 — Project Overview

## Application Description

Self-hosted, AI-powered email inbox management system. Processes Gmail via direct API, classifies incoming emails using a two-tier engine (fast rules + LLM fallback), generates draft responses, and manages workflows through Gmail labels. Designed for single-user with multi-tenant architecture ready in schema.

The v2 redesign replaced the Claude Code + MCP architecture with a pure Python FastAPI application, achieving ~20x speedup (590s → 15-30s for 12 emails).

## Tech Stack

### Backend
- **FastAPI 0.110+** — Async web framework with lifespan management
- **SQLite** (via aiosqlite) — Default database, PostgreSQL upgrade path available
- **LiteLLM 1.30+** — Model-agnostic LLM gateway (Claude, OpenAI, Gemini, local)
- **google-api-python-client** — Direct Gmail API access (OAuth 2.0)

### Key Libraries
| Library | Purpose |
|---------|---------|
| `litellm` | LLM gateway (classify + draft) |
| `aiosqlite` | Async SQLite access |
| `pydantic` + `pydantic-settings` | Config, validation, env vars |
| `httpx` | Async HTTP client |
| `google-auth-oauthlib` | Gmail OAuth 2.0 flow |
| `pyyaml` | YAML config loading |

### Development
| Tool | Purpose |
|------|---------|
| `pytest` + `pytest-asyncio` | Test framework (118 tests) |
| `ruff` | Linting + formatting |
| Docker + Compose | Containerized deployment |

## Architecture Overview

```
src/
├── main.py                    # FastAPI app, lifespan, worker pool bootstrap
├── config.py                  # Pydantic config (YAML + env vars, prefix GMA_)
├── api/                       # REST API layer
│   ├── webhook.py             # POST /webhook/gmail — Pub/Sub notifications
│   ├── admin.py               # User/email/settings/health endpoints
│   └── briefing.py            # GET /api/briefing/{email} — inbox summary
├── classify/                  # Email classification
│   ├── engine.py              # Two-tier: rules.classify() → llm.classify()
│   ├── rules.py               # Deterministic pattern matching (free, instant)
│   └── prompts.py             # System/user prompts for LLM classification
├── draft/                     # Draft generation
│   ├── engine.py              # generate() + rework() with ✂️ marker parsing
│   └── prompts.py             # System/user prompts for LLM drafting
├── gmail/                     # Gmail API client
│   ├── auth.py                # OAuth 2.0 (desktop app flow)
│   ├── client.py              # Search, get, modify, draft, watch, history
│   └── models.py              # Message, Thread, Draft, HistoryRecord
├── llm/                       # LLM interface
│   ├── gateway.py             # LiteLLM-backed classify() + draft() + agent_completion()
│   └── config.py              # Model selection, token limits
├── sync/                      # Email synchronization
│   ├── engine.py              # Gmail History API incremental sync + routing
│   ├── webhook.py             # Webhook notification → job queue
│   └── watch.py               # Gmail watch setup (Pub/Sub)
├── agent/                     # Agent framework (tool-use loop)
│   ├── loop.py                # LLM → tool calls → results → repeat until done
│   ├── profile.py             # Config-driven agent profiles (model, prompt, tools)
│   └── tools/
│       ├── __init__.py        # Tool + ToolRegistry (OpenAI function-calling format)
│       └── pharmacy.py        # Pharmacy tools (stubbed): search, reserve, reply
├── routing/                   # Config-driven email routing
│   ├── router.py              # Router: match rules → RoutingDecision (pipeline|agent)
│   ├── rules.py               # Rule matching (sender, domain, forwarding, subject)
│   └── preprocessors/
│       ├── crisp.py           # Crisp helpdesk email parser
│       └── default.py         # Pass-through for standard pipeline
├── lifecycle/                 # Email state machine
│   └── manager.py             # Done, Sent, Waiting, Rework transitions (zero LLM)
├── tasks/                     # Job queue
│   ├── workers.py             # Async worker pool (classify, draft, agent_process, etc.)
│   └── scheduler.py           # Recurring tasks (watch renewal, fallback sync)
├── db/                        # Database layer
│   ├── connection.py          # SQLite abstraction (async)
│   ├── models.py              # Repository classes (User, Email, Job, Event, AgentRun)
│   └── migrations/
│       ├── 001_v2_schema.sql  # Core schema (users, emails, jobs, events, etc.)
│       ├── 002_llm_calls.sql  # LLM call logging
│       └── 003_agent_runs.sql # Agent run tracking + llm_calls constraint update
└── users/                     # User management
    ├── onboarding.py          # User setup + Gmail label provisioning
    └── settings.py            # Per-user settings (JSON key-value)
```

## Email Processing Pipeline

```
Gmail Pub/Sub Notification
    → POST /webhook/gmail
    → SyncEngine.process_notification()
    → History API: fetch new messages since last historyId
    → For each new email:
        → Router.route(message_meta) — config-driven routing decision
        → If route == "pipeline": create job(type=classify)       [default]
        → If route == "agent":    create job(type=agent_process)  [config-matched]

Pipeline route (classify → draft):
    Worker picks up classify job:
        → RuleEngine.classify() — pattern matching (sender, subject, keywords)
        → If low confidence: LLMGateway.classify() — Claude Haiku
        → Store classification + create job(type=draft) if needs_response
        → Apply Gmail labels (🤖 AI/Needs Response, etc.)

    Worker picks up draft job:
        → LLMGateway.draft() — Claude Sonnet
        → Create Gmail draft (In-Reply-To headers)
        → Apply 🤖 AI/Outbox label

Agent route (tool-use loop):
    Worker picks up agent_process job:
        → Preprocessor extracts structured data (e.g., Crisp email parser)
        → AgentLoop.run(profile, message) — iterative tool-use loop:
            → LLM decides action → execute tool → feed result back → repeat
            → Until: final answer, max iterations, or error
        → Agent run logged to agent_runs table for audit

Rework loop (user-initiated):
    → User writes instructions above ✂️ marker in draft
    → Labels thread with 🤖 AI/Rework
    → Worker detects rework, re-drafts with instructions (up to 3x)

Lifecycle transitions (deterministic, no LLM):
    → Done: user labels → archives, removes AI labels, keeps Done marker
    → Sent: draft disappears → detects sent, updates status
    → Waiting: reply detected → re-classifies thread
```

## Configuration Hierarchy

1. **Defaults** — Pydantic model defaults in `src/config.py`
2. **YAML** — `config/app.yml` (auth, database, LLM, sync, server)
3. **Environment variables** — `GMA_` prefix overrides everything

Key config classes: `AppConfig` → `AuthConfig`, `DatabaseConfig`, `LLMSettings`, `SyncConfig`, `ServerConfig`, `RoutingConfig`, `AgentConfig`

## Gmail Label System

| Label | Purpose |
|-------|---------|
| 🤖 AI (parent) | Container for all AI labels |
| 🤖 AI/Needs Response | Email classified as needing a reply |
| 🤖 AI/Outbox | Draft ready for review |
| 🤖 AI/Rework | User requested draft revision |
| 🤖 AI/Action Required | Non-email action needed |
| 🤖 AI/Payment Request | Invoice or payment |
| 🤖 AI/FYI | Informational, no action needed |
| 🤖 AI/Waiting | Waiting for external reply |
| 🤖 AI/Done | Permanently archived (audit marker) |

## Key Design Decisions

1. **Direct Gmail API** — No MCP overhead, direct `google-api-python-client` calls
2. **LLM as utility** — Used for classify, draft, and agent tool-use loops
3. **SQLite-first** — Simple default, PostgreSQL upgrade path via asyncpg
4. **Job queue in DB** — No external queue (Redis/RabbitMQ); jobs table with claim-next pattern
5. **Repository pattern** — Type-safe database operations, easier testing
6. **Two-tier classification** — Rules catch obvious cases for free; LLM handles ambiguity
7. **Immutable audit log** — `email_events` table records every transition
8. **Config-driven routing** — YAML rules route emails to pipeline or agent processing
9. **Agent framework** — Tool-use loop with pluggable tools, profiles, and preprocessors

## Coding Conventions

### Python Style
- `from __future__ import annotations` in every file
- Full type hints on all functions and return values
- Async/await for all I/O operations
- Module-level and function-level docstrings
- Ruff linting with `line-length = 100`, target Python 3.11

### Error Handling
- Try/except with logging, graceful fallback (e.g., classify as "fyi" on error)
- Job retry: up to 3 attempts with error message stored in jobs table
- Never send or delete emails automatically — all destructive actions require user labeling

### Commit Messages
Describe what was achieved or fixed (lowercase, no period):
- `add webhook endpoint for Gmail Pub/Sub notifications`
- `fix: classification fallback when LLM returns invalid JSON`
