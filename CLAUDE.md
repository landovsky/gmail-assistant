# Gmail Assistant v2

AI-powered Gmail inbox management — classifies emails, generates draft responses, manages workflows through Gmail labels.

# Quick Reference

## Task Management

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

### Workflow

1. Check `bd ready` for available issues (no blockers)
2. Claim with `bd update <id> --status in_progress`
3. Complete work and commit changes
4. Close with `bd close <id> --reason="description"`
5. Run `bd sync` before ending session

## Tech Stack
- **Python 3.11+** / **FastAPI** / **SQLite** (PostgreSQL-ready) / **LiteLLM**
- **Gmail**: Direct `google-api-python-client` (not MCP)
- **LLM**: LiteLLM gateway — Haiku for classification, Sonnet for drafts
- **Config**: Pydantic Settings + YAML (`config/app.yml`)
- **Key libs**: aiosqlite, httpx, pydantic, google-auth-oauthlib

## Commands
```bash
pytest                         # Run all tests (118 tests)
pytest tests/test_classify.py  # Run specific test file
ruff check src/ tests/         # Lint
ruff format src/ tests/        # Format
uvicorn src.main:app --reload  # Dev server (port 8000)
docker compose up --build      # Run via Docker
gmail-assistant                # CLI entry point (if pip installed)
```

## Architecture
- `src/main.py` — FastAPI app entry point, lifespan, worker pool
- `src/api/` — REST routes (webhook, admin, briefing)
- `src/classify/` — Two-tier classification (rules → LLM)
- `src/draft/` — Draft generation + rework loop
- `src/gmail/` — Direct Gmail API client, OAuth, models
- `src/llm/` — LiteLLM gateway (model-agnostic, includes agent_completion)
- `src/sync/` — Gmail History API sync, Pub/Sub webhook, routing integration
- `src/lifecycle/` — Email state machine (done, sent, waiting, rework)
- `src/tasks/` — Async worker pool (claim-next job queue, agent_process handler)
- `src/db/` — SQLite connection, repository pattern, migrations (3 migrations)
- `src/users/` — Onboarding, per-user settings
- `src/config.py` — Pydantic config (env vars override YAML)
- `src/agent/` — Agent framework: tool-use loop, tool registry, agent profiles
- `src/routing/` — Config-driven email routing (rules, preprocessors)

### Email Processing Flow
Incoming email → Sync Engine → **Router** decides:
- **Pipeline route** (default): classify → draft (existing flow)
- **Agent route** (config-matched): preprocessor → agent loop (LLM + tools)

## Documentation
Document important changes to keep them up to date.

Check `artifacts/registry.json` for detailed docs on:
- Project overview and architecture
- Testing conventions, API patterns, database conventions
- Classification and drafting domain logic
- Debugging workflow

## Conventions
- `from __future__ import annotations` in all files
- Full type hints throughout
- Async/await for all I/O (database, HTTP, Gmail)
- Repository pattern for database access
- Pydantic models for configuration and validation
- Ruff for linting and formatting (line-length 100)
- `email_events` audit table logs all state transitions
- Commit messages: describe what was achieved/fixed (lowercase, no period)
- when running as a remote agent, commit and push regularly to avoid data loss

## Environment Variables (prefix: `GMA_`)
- `ANTHROPIC_API_KEY` — LLM access
- `GMA_AUTH_MODE` — `personal_oauth` or `service_account`
- `GMA_DB_BACKEND` — `sqlite` (default) or `postgresql`
- `GMA_LLM_CLASSIFY_MODEL` / `GMA_LLM_DRAFT_MODEL` — model overrides
- `GMA_SERVER_LOG_LEVEL` — logging level (default: info)
- `GMA_SYNC_PUBSUB_TOPIC` — Gmail Pub/Sub topic
