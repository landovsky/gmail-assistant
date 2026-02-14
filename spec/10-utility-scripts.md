# 10 — Utility Scripts & Commands

## Overview

The project includes shell scripts (`bin/`) for operational tasks and Claude Code commands (`.claude/commands/`) for AI-assisted workflows. Scripts that touch production require explicit `--env=production` flags and interactive confirmation prompts. Gmail-connected scripts share the same OAuth credentials from `config/`.

---

## Shell Scripts (bin/)

### Gmail Maintenance

#### cleanup-drafts

Remove AI-generated Gmail drafts containing the `✂️` rework marker.

- **Default behavior:** Dry run — lists matching drafts without deleting
- **Flag:** `--delete` to actually trash drafts
- **Connects to:** Gmail API (drafts endpoint)
- **Safety:** Only targets drafts containing the `✂️` marker. Paginates through all drafts. Progress reported every 10 drafts.

#### cleanup-labels

Remove all `🤖 AI/*` labels from inbox messages.

- **Default behavior:** Dry run — shows a sample of affected messages
- **Flag:** `--delete` to actually strip labels
- **Connects to:** Gmail API (messages, labels)
- **Safety:** Does not delete messages, only removes labels. Batch modification (50 messages per batch). Shows first 10 affected messages in preview.

---

### Classification Debugging

#### debug-classify

Run a single email through the classification pipeline with detailed step-by-step output.

- **Input modes:** `--sender`, `--subject`, `--body` flags; `--file PATH` for bulk; `--thread-id ID` to replay from DB; interactive prompt if no args
- **Flag:** `--llm` to include LLM classification (requires API key); `--verbose` for full pattern matching trace
- **Connects to:** Local DB (read-only), LLM API (optional)
- **Output:** Color-coded results showing both rule tier and LLM tier decisions, confidence, reasoning, detected style

#### debug-context

Test context gathering by generating Gmail search queries and fetching related threads.

- **Input modes:** `--sender`, `--subject`, `--body`; `--thread-id ID` to load from DB
- **Flag:** `--live` to execute actual Gmail searches (requires OAuth)
- **Connects to:** LLM API (query generation), Gmail API (search, optional)
- **Safety:** Read-only. Query generation by default, live search opt-in. Max 5 related threads. Deduplicates by thread ID.

#### test-classification

Run predefined test cases through the ClassificationEngine and report accuracy.

- **Flags:** `--rules-only` (no LLM, no API key needed); `--llm-only` (skip rule-matched cases); `--verbose`; `--filter CATEGORY`; `--id CASE_ID`; `--cases PATH` (custom fixture file, default `tests/fixtures/classification_cases.yaml`)
- **Connects to:** LLM API (unless `--rules-only`), test fixtures
- **Output:** Per-case pass/fail, accuracy percentage, confusion matrix on failures, tier counts (rules vs LLM)

---

### Server & Database Operations

#### dev

Start the FastAPI development server via `uvicorn` with reload enabled. No arguments.

#### full-sync

Trigger a full inbox sync (classifies all untagged emails).

- **Flag:** `--env=production|dev` (default: dev); `--reset` to also wipe transient DB data
- **Connects to:** Server API (local `localhost:8000` or production `gmail.kopernici.cz`)
- **Safety:** Production requires Basic Auth (env vars `GMA_SERVER_ADMIN_USER`, `GMA_SERVER_ADMIN_PASSWORD`). Production reset requires interactive confirmation (`Type 'yes' to confirm`). Health check before proceeding.

#### reset-db

Clear all transient data from the database (jobs, emails, events, sync_state). Preserves users, labels, settings.

- **Flag:** `--env=production|dev` (required)
- **Connects to:** Server API
- **Safety:** Same production safeguards as `full-sync`. Displays deleted row counts per table.

#### pip-install

Wrapper that runs `uv sync` against the project virtualenv (`.venv`).

---

### Deployment

#### k8s-update-secrets

Update Kubernetes secrets for production deployment.

- **Required env vars:** `GEMINI_API_KEY`, `GMA_SERVER_ADMIN_USER`, `GMA_SERVER_ADMIN_PASSWORD`
- **Optional env vars:** `ANTHROPIC_API_KEY`
- **Required files:** `config/credentials.json`, `config/token.json`
- **Behavior:** Deletes existing `gmail-assistant-secrets` then recreates with all API keys and OAuth credential files
- **Note:** Manual pod restart required after (`kubectl rollout restart deployment`)

---

### Session Debugging

These scripts operate on local Claude Code session logs (`~/.claude/projects/.../*.jsonl`). Read-only, development only.

#### list-sessions

List all Claude Code sessions for this project with metadata (turn counts, file sizes, timestamps). Sorted by total turns.

- **Flags:** `--min-turns N`; `--dev-only` (skip sessions < 7 turns); `--json`

#### extract-session-messages

Extract user messages and error-indicator assistant messages from a specific session.

- **Args:** `session_id` (full or partial UUID)
- **Flags:** `--all` (include all assistant messages); `--user-only`; `--max-len N` (default 500)

---

### Testing

#### send-test-email

Send realistic test emails (in Czech) to exercise the classification pipeline.

- **Flags:** `--kind=<category>` (needs_response, action_required, payment_request, fyi, waiting); `--style=<tone>` (formal, casual, terse, etc.); `--recipient=EMAIL` (default: project owner); `--count=N`; `--delay-between=M` (minutes)
- **Connects to:** Claude CLI with Gmail MCP for sending
- **Safety:** Random selection if kind/style omitted. Delay between multiple sends.

---

## Claude Code Commands (.claude/commands/)

### /dev-env

Manage the local development environment: Pub/Sub emulator + server + Gmail watch.

- **Subcommands:** `start`, `stop`, `status`, `update-endpoint`
- **Connects to:** GCP Pub/Sub (`gmail-push-dev` topic/subscription), local server, admin API
- **Behavior:** `start` accepts an optional ngrok URL for webhook forwarding. `stop` tears down background processes. `status` checks all components. `update-endpoint` changes the Pub/Sub push endpoint.

### /prod-env

Manage the production environment: Pub/Sub + K3s cluster + Gmail watch.

- **Subcommands:** `start`, `stop`, `status`, `update-endpoint`, `logs`, `restart`
- **Connects to:** GCP Pub/Sub (`gmail-push-prod` topic/subscription), K3s cluster, production server API (`gmail.kopernici.cz`)
- **Safety:** Basic Auth required for admin API. Interactive confirmation for `restart`. Health checks before/after actions. Rollout monitoring with 120s timeout. `stop` only clears the push endpoint (server stays running).

### /reset-db

Reset the local dev database via the server API (`POST /api/reset`). Checks server health first. Displays deleted row counts.

### /send-test-email

Generate and send a realistic test email in Czech to exercise classification. Same parameters as `bin/send-test-email`. Includes kind-specific guidance for the LLM generating the email content (e.g., payment requests include invoice numbers and bank details).

### /update-style

Learn communication patterns from real sent emails and update style configuration.

- **Argument:** Style name to update (e.g., `business`, `casual`)
- **Connects to:** Gmail API (sent emails search, read-only), config YAML files
- **Behavior:** Searches sent emails (60 days, layered strategy: explicit contacts → domains → broad fallback). Reads up to 20 emails. Analyzes language patterns, tone, structure. Updates `config/communication_styles.yml`.
- **Safety:** Anonymizes examples in config (changes names, companies, amounts, dates). Only updates the target style. Warns on small sample (< 5 emails).

### /code-review

Full codebase review for anti-patterns, non-Pythonic idioms, and architectural issues.

- **Argument:** Optional focus area (`db`, `async`, `workers`, `api`, etc.)
- **Behavior:** Reads all Python files in scope. Cross-references previous review artifact to avoid duplication. Triages findings by severity (P0–P3). Commits updated artifact.
- **Safety:** Read-only analysis. Requires concrete file/line references. Excludes intentional trade-offs documented elsewhere.

---

## Safety Patterns

| Pattern | Scripts |
|---------|---------|
| **Dry-run default** | cleanup-drafts, cleanup-labels |
| **Production confirmation** | full-sync, reset-db, /prod-env restart |
| **Basic Auth for production** | full-sync, reset-db, /prod-env |
| **Health check before action** | full-sync, reset-db, /reset-db, /dev-env, /prod-env |
| **Read-only** | debug-classify, debug-context, test-classification, list-sessions, extract-session-messages, /code-review |
