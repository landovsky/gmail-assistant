# 08 — Auth, Admin & Configuration

## Authentication & Authorization

### API Authentication

**Current state:** No authentication is implemented on any API endpoint. All endpoints are open. The system is designed to run on a trusted network or behind an authenticating reverse proxy.

### Authorization Model

There is no role-based access control. All API operations are available to any caller. The admin dashboard is read-only by design but has no access restrictions.

### Google Authentication

See spec 05 for OAuth and service account details.

---

## Admin Dashboard

### Capabilities

The admin dashboard provides read-only visibility into all system state:

| Entity | List View | Search | Detail View |
|--------|-----------|--------|-------------|
| Users | id, email, display_name, is_active, onboarded_at, created_at | email, display_name | All fields |
| User Labels | user_id, label_key, gmail_label_id, gmail_label_name | label_key, gmail_label_name | All fields |
| User Settings | user_id, setting_key, setting_value | setting_key | All fields |
| Sync State | user_id, last_history_id, last_sync_at, watch_expiration | — | All fields |
| Emails | id, user_id, subject, sender_email, classification, resolved_style, status, confidence, received_at | subject, sender_email, gmail_thread_id | All fields including reasoning, rework details |
| Email Events | id, user_id, gmail_thread_id, event_type, detail, created_at | gmail_thread_id, event_type, detail | All fields |
| LLM Calls | id, user_id, gmail_thread_id, call_type, model, total_tokens, latency_ms, error, created_at | gmail_thread_id, call_type, model | Full prompts, responses, token counts |
| Jobs | id, user_id, job_type, status, attempts, error_message, created_at | job_type, status | All fields |

All views default to descending sort by primary key or created_at.

**Operations NOT supported:** create, edit, delete. The admin UI is strictly for observation and debugging.

---

## Configuration

### Configuration Hierarchy

Configuration follows a layered approach:
1. **YAML file** — Base configuration from `config/app.yml`
2. **Environment variables** — Override YAML values (prefix: `GMA_`)
3. **Code defaults** — Fallback values if neither YAML nor env var is set

### Configuration Structure

```yaml
# Authentication
auth:
  mode: personal_oauth          # or "service_account"
  credentials_file: config/credentials.json
  token_file: config/token.json
  service_account_file: config/service-account-key.json
  scopes:
    - https://www.googleapis.com/auth/gmail.modify

# Database
database:
  backend: sqlite               # or "postgresql"
  sqlite_path: data/inbox.db
  postgresql_url: ""            # connection string for PostgreSQL

# LLM Models
llm:
  classify_model: gemini/gemini-2.0-flash    # fast, cheap model
  draft_model: gemini/gemini-2.5-pro         # higher quality model
  context_model: gemini/gemini-2.0-flash     # for context query generation
  max_classify_tokens: 256
  max_draft_tokens: 2048
  max_context_tokens: 256

# Gmail Sync
sync:
  pubsub_topic: ""              # e.g., projects/myproject/topics/gmail-push
  fallback_interval_minutes: 15 # polling interval as safety net
  history_max_results: 100      # max history records per API call
  full_sync_days: 10            # lookback for full sync

# Server
server:
  host: 0.0.0.0
  port: 8000
  webhook_secret: ""            # [UNCLEAR: not currently used for validation]
  log_level: info
  worker_concurrency: 3         # number of concurrent job workers

# Email Routing
routing:
  rules:
    - name: pharmacy_support
      match:
        forwarded_from: "info@dostupnost-leku.cz"
      route: agent
      profile: pharmacy
    - name: default
      match:
        all: true
      route: pipeline

# Agent Framework
agent:
  profiles:
    pharmacy:
      model: gemini/gemini-2.5-pro
      max_tokens: 4096
      temperature: 0.3
      max_iterations: 10
      system_prompt_file: config/prompts/pharmacy.txt
      tools:
        - search_drugs
        - manage_reservation
        - web_search
        - send_reply
        - create_draft
        - escalate

# Environment
environment: development        # or "production"
sentry_dsn: ""                  # error tracking (disabled in development)
```

### Environment Variables

All environment variables use the prefix `GMA_`. Nested config sections use additional prefixes:

| Variable | Config Path | Example |
|----------|-------------|---------|
| `GMA_AUTH_MODE` | auth.mode | `personal_oauth` |
| `GMA_DB_BACKEND` | database.backend | `sqlite` |
| `GMA_DB_SQLITE_PATH` | database.sqlite_path | `data/inbox.db` |
| `GMA_LLM_CLASSIFY_MODEL` | llm.classify_model | `gemini/gemini-2.0-flash` |
| `GMA_LLM_DRAFT_MODEL` | llm.draft_model | `gemini/gemini-2.5-pro` |
| `GMA_SERVER_HOST` | server.host | `0.0.0.0` |
| `GMA_SERVER_PORT` | server.port | `8000` |
| `GMA_SERVER_LOG_LEVEL` | server.log_level | `info` |
| `GMA_SERVER_WORKER_CONCURRENCY` | server.worker_concurrency | `3` |
| `GMA_SYNC_PUBSUB_TOPIC` | sync.pubsub_topic | `projects/x/topics/y` |
| `GMA_ENVIRONMENT` | environment | `development` |
| `GMA_SENTRY_DSN` | sentry_dsn | `https://...@sentry.io/...` |
| `ANTHROPIC_API_KEY` | — | LLM API key (used by LiteLLM) |

### Per-User Configuration Files

In addition to the main `app.yml`, user-specific behavior is configured through:

- **contacts.yml** — Style overrides per sender email, domain overrides, blacklist patterns
- **communication_styles.yml** — Draft style definitions (rules, sign-off, language, examples)
- **label_ids.yml** — Legacy v1 label ID mapping (used during migration)

These are loaded at startup and stored in the `user_settings` table during onboarding.

### Communication Styles Configuration

```yaml
styles:
  business:
    rules:
      - "Keep the tone professional and courteous"
      - "Use formal address"
    sign_off: "Best regards,\nJohn"
    language: auto
    examples:
      - context: "Supplier inquiry about delivery"
        input: "When can we expect the shipment?"
        draft: "Thank you for your message. The shipment is scheduled for..."

  casual:
    rules:
      - "Keep it relaxed and friendly"
      - "Use first names"
    sign_off: "Cheers,\nJohn"
    language: auto
```

### Contacts Configuration

```yaml
style_overrides:
  friend@example.com: casual
  boss@company.com: business

domain_overrides:
  "*.gov.cz": business
  "gmail.com": casual

blacklist:
  - "*@marketing.spam.com"
  - "noreply@*"
```

---

## External Services

### Required

| Service | Purpose | Configuration |
|---------|---------|---------------|
| **LLM Provider** | Classification, draft generation, context queries, agent | API key via env var (e.g., `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) |
| **Gmail API** | Email access, label management, draft creation | OAuth credentials or service account key |

### Optional

| Service | Purpose | Configuration |
|---------|---------|---------------|
| **Google Cloud Pub/Sub** | Real-time Gmail push notifications | Topic name in `sync.pubsub_topic`. Requires topic creation and IAM setup. |
| **Sentry** | Error tracking and monitoring | DSN in `sentry_dsn`. Disabled in development environment. |
| **PostgreSQL** | Alternative to SQLite for production | Connection URL in `database.postgresql_url`. [UNCLEAR: PostgreSQL backend is defined in config but raises NotImplementedError at runtime.] |

### Sentry Configuration

Sentry is initialized only when:
- `sentry_dsn` is non-empty AND
- `environment` is not `development`

Settings:
- `send_default_pii: true` — Include user info in error reports
- `max_request_body_size: "always"` — Include request bodies
- `traces_sample_rate: 0` — No performance tracing
- No session tracking, no client reports

---

## Startup Sequence

1. Load configuration from YAML + environment variables
2. Initialize Sentry (if configured and not development)
3. Configure logging (level from config)
4. Create database instance, ensure directories exist
5. Run all database migrations (idempotent)
6. Register API routers (webhook, admin, briefing)
7. Mount admin dashboard
8. **On lifespan start:**
   a. Create Gmail service (auth handler)
   b. Create LLM gateway with call logging
   c. Create classification engine
   d. Create draft engine
   e. Create context gatherer
   f. Create router from routing config
   g. Build tool registry, register tools
   h. Build agent profiles from config
   i. Create agent loop (if profiles exist)
   j. Start worker pool (N async workers)
   k. Start scheduler (watch renewal + fallback sync)

9. **On lifespan shutdown:**
   a. Signal worker pool to stop
   b. Signal scheduler to stop
   c. Cancel background tasks
   d. Wait for cancellation

---

## Logging

The system uses Python's standard logging module:

- **Level:** Configurable via `server.log_level` (default: `info`)
- **Format:** `%(asctime)s %(levelname)s %(name)s: %(message)s`
- **Per-module loggers:** Each module has its own named logger

Key log events:
- Worker job processing (job id, type, user_id)
- Classification results (thread_id, category, confidence, source)
- Draft creation (thread_id)
- Sync results (new messages, label changes, deletions, jobs queued)
- Watch renewal success/failure per user
- LLM call failures
- Gmail API errors (with retry info)
