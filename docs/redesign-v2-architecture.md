# Gmail Assistant v2 — Architecture Redesign

## Problem Statement

The current system uses **Claude Code + Gmail MCP** as its runtime. Every Gmail operation — searching, reading, labeling, drafting — flows through Claude's context window via MCP tool calls. This is:

1. **Slow**: 590s to triage 12 emails (49s/email vs expected 1-2s). Every Gmail search is a full LLM round-trip.
2. **Expensive**: Each MCP tool invocation burns input/output tokens on operations that need zero intelligence (fetching, labeling, DB writes).
3. **Not parallelizable**: Claude processes MCP calls sequentially. No batching.
4. **Single-user only**: MCP is an interactive single-session protocol. One OAuth token, one user.
5. **Polling-based**: Runs every 30 minutes via launchd. Emails can wait up to 30 min for classification.

### Core Insight

Claude is being used as both the **runtime** (orchestration, I/O, state management) and the **brain** (classification, draft writing). The redesign separates these concerns:

> **Code does mechanics. Claude does intelligence.**

---

## Design Principles

1. **Gmail API direct** — All email operations via `google-api-python-client`, not MCP
2. **Push, not poll** — Gmail Pub/Sub notifications for near real-time processing
3. **LLM only for intelligence** — LLM called only for classification and draft generation
4. **Model-agnostic** — LLM gateway for flexible model choice (not locked to one provider)
5. **Multi-user from day one** — Service account with domain-wide delegation
6. **Single-user lite mode** — Personal OAuth path for non-Workspace individual users
7. **Preserve tagging logic** — The 8-label system, 5 categories, communication styles, rework loop all carry over unchanged

---

## What Stays, What Changes

### Stays (unchanged)

- 8 Gmail labels (`🤖 AI/Needs Response`, `Outbox`, `Rework`, `Action Required`, `Payment Requests`, `FYI`, `Waiting`, `Done`)
- 5 classification categories (`needs_response`, `action_required`, `payment_request`, `fyi`, `waiting`)
- Label lifecycle state machine (same flows, same transitions)
- Communication styles (formal / business / informal) with same selection priority
- Rework feedback loop with `✂️` marker (max 3 reworks)
- Safety invariants: never send, never delete, always log, always require human review
- Draft quality guidelines and style rules
- Audit trail via `email_events`

### Changes

| Aspect | Current (v1) | Redesign (v2) |
|--------|-------------|---------------|
| Gmail access | Gmail MCP server | `google-api-python-client` direct |
| Orchestration | Claude Code commands + bash scripts | Python async application |
| LLM usage | Claude as runtime (does everything) | LLM gateway (model-agnostic) for classification + drafting only |
| Sync model | Poll every 30 min (launchd) | Gmail Pub/Sub push (near real-time) |
| Users | Single user, single OAuth token | Multi-user, service account impersonation |
| Database | SQLite, no user scoping | PostgreSQL, all tables user-scoped |
| Configuration | YAML files on disk | DB-stored per-user settings + org defaults |
| Deployment | macOS CLI tool | Self-hosted, containerized (Docker Compose) |
| Label management | Manual setup, IDs in YAML | Auto-provisioned on user onboarding |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Google Workspace Admin                         │
│            (authorizes domain-wide delegation once)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   Gmail Assistant v2 Service                     │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────┐ │
│  │  Webhook      │   │  Scheduler   │   │  Admin API          │ │
│  │  /webhook/    │   │  (watch      │   │  /api/users/        │ │
│  │  gmail        │   │   renewal,   │   │  /api/settings/     │ │
│  │              │   │   fallback   │   │  /api/briefing/     │ │
│  └──────┬───────┘   │   sync)      │   └─────────────────────┘ │
│         │           └──────┬───────┘                            │
│         │                  │                                     │
│  ┌──────▼──────────────────▼────────────────────────────────┐   │
│  │              Job Queue (PostgreSQL table)                  │   │
│  │  sync:{user}  classify:{user}  draft:{user}  cleanup:{u} │   │
│  └──────┬───────────────┬──────────────┬──────────┬─────────┘   │
│         │               │              │          │              │
│  ┌──────▼───────┐ ┌─────▼──────┐ ┌────▼────┐ ┌──▼──────────┐  │
│  │ Sync Engine  │ │ Classifier │ │ Drafter │ │ Lifecycle   │  │
│  │              │ │            │ │         │ │ Manager     │  │
│  │ history.list │ │ Rules +    │ │ LLM     │ │             │  │
│  │ incremental  │ │ LLM        │ │ Gateway │ │ Done/Sent/  │  │
│  │ sync         │ │ Gateway    │ │         │ │ Waiting     │  │
│  └──────┬───────┘ └─────┬──────┘ └────┬────┘ └──┬──────────┘  │
│         │               │              │          │              │
│  ┌──────▼───────────────▼──────────────▼──────────▼──────────┐  │
│  │                  Gmail Service Layer                        │  │
│  │  google-api-python-client + service account impersonation  │  │
│  │  search | get_thread | modify_labels | create_draft | batch│  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                     PostgreSQL                              │  │
│  │  users | emails | email_events | user_settings |            │  │
│  │  user_labels | sync_state                                   │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
         │                                        ▲
         ▼                                        │
┌─────────────────┐                    ┌──────────┴──────────┐
│  Gmail API       │                    │  Google Cloud       │
│  (per-user       │                    │  Pub/Sub            │
│   impersonation) │                    │  (push topic)       │
└─────────────────┘                    └─────────────────────┘
         │                                        ▲
         ▼                                        │
┌─────────────────────────────────────────────────┘
│  Gmail Mailboxes (all users in Workspace org)
└──────────────────────────────────────────────────
```

---

## Gmail Push Notifications (Real-Time Sync)

Gmail supports real-time push via Google Cloud Pub/Sub. This replaces the 30-minute polling loop.

### How it works

1. **Setup** (once per user): Call `users.watch()` with a Pub/Sub topic and optional label filter
2. **Renewal**: `watch()` expires after 7 days — a scheduled job renews daily for all active users
3. **Notification**: When a mailbox changes, Gmail publishes a message to the Pub/Sub topic containing `{emailAddress, historyId}`
4. **Processing**: Our webhook receives the notification, queues a sync job for that user
5. **Incremental sync**: `history.list(startHistoryId=lastKnown)` returns only what changed since last sync
6. **History events** tell us: messages added, messages deleted, labels added/removed

### Latency improvement

| | v1 (polling) | v2 (push) |
|---|---|---|
| New email → classified | Up to 30 min | ~5-15 seconds |
| Classified → draft ready | +38s (sequential) | +3-5s (async) |
| User marks Done → cleaned up | Up to 30 min | ~5-15 seconds |
| User marks Rework → new draft | Up to 30 min | ~10-20 seconds |

### Push notification flow

```
User receives email in Gmail
    │
    ▼
Gmail publishes to Pub/Sub topic
    │  {emailAddress: "user@org.com", historyId: 12345}
    ▼
Pub/Sub pushes to POST /webhook/gmail
    │
    ▼
Webhook handler:
    1. Decode & validate message
    2. Look up user by emailAddress
    3. Queue sync job: sync:{user_id}
    │
    ▼
Sync worker:
    1. Load user's lastHistoryId from DB
    2. Call history.list(startHistoryId=lastHistoryId)
    3. Process each history record:
       │
       ├─ messagesAdded (new email) → queue classify:{user_id, message_id}
       ├─ labelsAdded "🤖 AI/Done" → queue cleanup:{user_id, thread_id}
       ├─ labelsAdded "🤖 AI/Rework" → queue rework:{user_id, thread_id}
       ├─ labelsRemoved (draft deleted = sent?) → check & update status
       └─ messagesDeleted → check if draft (sent detection)
    │
    4. Update lastHistoryId in DB
```

### Fallback: scheduled full sync

Push notifications can occasionally be missed (Pub/Sub delivery is at-least-once, not exactly-once, and watch() can lapse). A scheduled job runs every 15-30 minutes as a safety net:

- For each user: compare DB state against Gmail label state
- Classify any emails that were missed
- This is lightweight since most work is already done by push

---

## Component Design

### 1. Gmail Service Layer

Wraps `google-api-python-client` with service account impersonation.

```python
class GmailService:
    """Direct Gmail API client with per-user impersonation."""

    def __init__(self, service_account_creds: str):
        self.base_creds = service_account.Credentials.from_service_account_file(
            service_account_creds,
            scopes=['https://www.googleapis.com/auth/gmail.modify'],
        )

    def for_user(self, user_email: str) -> 'UserGmailClient':
        """Create an impersonated client for a specific user."""
        delegated = self.base_creds.with_subject(user_email)
        service = build('gmail', 'v1', credentials=delegated)
        return UserGmailClient(service, user_email)


class UserGmailClient:
    """Gmail operations for a single user."""

    def search(self, query: str, max_results: int = 50) -> list[Message]: ...
    def get_thread(self, thread_id: str) -> Thread: ...
    def get_message(self, message_id: str) -> Message: ...
    def modify_labels(self, message_id: str, add: list[str], remove: list[str]): ...
    def batch_modify_labels(self, message_ids: list[str], add: list[str], remove: list[str]): ...
    def create_draft(self, thread_id: str, to: str, subject: str, body: str) -> str: ...
    def trash_draft(self, draft_id: str): ...
    def get_draft(self, draft_id: str) -> Draft | None: ...
    def list_history(self, start_history_id: str, label_id: str = None) -> list[History]: ...
    def watch(self, topic_name: str, label_ids: list[str] = None) -> WatchResponse: ...
    def stop_watch(self): ...
    def get_or_create_label(self, name: str, **kwargs) -> str: ...
```

**Key differences from MCP approach:**
- Direct API calls — no LLM round-trip per operation
- Batch API support — modify 50 messages in one HTTP call
- Async support — multiple users processed concurrently
- Thread-level operations — get full thread in one call (not message-by-message)
- Proper error handling with retries and exponential backoff

### 2. Sync Engine

Manages incremental sync via `history.list()`.

```python
class SyncEngine:
    """Incremental mailbox sync using Gmail History API."""

    def sync_user(self, user_id: int, history_id: str) -> SyncResult:
        """Process all changes since last known historyId."""
        # 1. Fetch history records
        # 2. Categorize changes (new messages, label changes, deletions)
        # 3. Dispatch to appropriate handlers
        # 4. Update stored historyId

    def full_sync(self, user_id: int) -> SyncResult:
        """Full sync fallback — scan inbox for unclassified emails."""
        # Used on first run or when history gap is too large
```

**Sync state** stored per user:

```sql
CREATE TABLE sync_state (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    last_history_id TEXT NOT NULL,
    last_sync_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    watch_expiration TIMESTAMPTZ,
    watch_resource_id TEXT
);
```

### 3. Classification Engine

Two-tier classification: fast rule-based pre-filter, then LLM for ambiguous cases.

```python
class ClassificationEngine:
    """Classifies emails using rules + LLM gateway."""

    def __init__(self, llm_gateway: LLMGateway):
        self.llm = llm_gateway

    def classify(self, email: Email, user_settings: UserSettings) -> Classification:
        # Tier 1: Rule-based (instant, free)
        result = self._rule_based_classify(email, user_settings)
        if result.confidence == 'high':
            return result

        # Tier 2: LLM-based (via gateway — model configurable)
        return self._llm_classify(email, user_settings)

    def _rule_based_classify(self, email, settings) -> Classification:
        """Deterministic rules — blacklist, payment patterns, FYI signals."""
        # Blacklist match → fyi (high confidence)
        # Payment keywords → payment_request (high)
        # No-reply/automated sender → fyi (high)
        # Action keywords → action_required (high)
        # Everything else → pass to LLM

    def _llm_classify(self, email, settings) -> Classification:
        """Call LLM for nuanced classification."""
        # Single API call with email content + classification prompt
        # Returns: category, confidence, reasoning, detected_language
```

### LLM Gateway

All LLM calls go through a gateway abstraction that decouples the application from any specific provider. This enables swapping models (Claude, GPT, Gemini, local models) without changing application code.

```python
class LLMGateway:
    """Model-agnostic LLM interface. Backed by LiteLLM or similar router."""

    def __init__(self, config: LLMConfig):
        self.classify_model = config.classify_model   # e.g. "claude-haiku-4-5-20251001"
        self.draft_model = config.draft_model         # e.g. "claude-sonnet-4-5-20250929"
        # LiteLLM supports 100+ models via unified interface:
        # "gpt-4o-mini", "gemini/gemini-2.0-flash", "claude-sonnet-4-5-20250929", etc.

    def classify(self, system: str, user_message: str) -> ClassifyResult:
        """Call the classification model (fast, cheap model)."""
        response = litellm.completion(
            model=self.classify_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            max_tokens=256,
            response_format={"type": "json_object"},  # structured output
        )
        return ClassifyResult.parse(response)

    def draft(self, system: str, user_message: str) -> str:
        """Call the draft generation model (higher quality model)."""
        response = litellm.completion(
            model=self.draft_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            max_tokens=2048,
        )
        return response.choices[0].message.content
```

**Configuration** — model choice is a simple config change:

```yaml
# config/llm.yml (or env vars)
llm:
  classify_model: "claude-haiku-4-5-20251001"   # fast, cheap
  draft_model: "claude-sonnet-4-5-20250929"     # high quality
  # Alternative configurations:
  # classify_model: "gpt-4o-mini"
  # draft_model: "gpt-4o"
  # classify_model: "gemini/gemini-2.0-flash"
  # draft_model: "gemini/gemini-2.0-pro"
```

**LLM call structure** — replaces the current approach where Claude reads the prompt from `.claude/commands/inbox-triage.md`, invokes MCP tools, thinks about it, etc. Instead:

```python
result = llm_gateway.classify(
    system="You are an email classifier. Classify into exactly ONE category...",
    user_message=f"Subject: {email.subject}\nFrom: {email.sender}\n\n{email.body[:2000]}",
)
```

**Batching opportunity**: For the scheduled full-sync fallback, batch 5-10 emails into a single LLM call with structured output per email.

### 4. Draft Engine

Generates reply drafts via LLM gateway (defaults to a high-quality model).

```python
class DraftEngine:
    """Generates email drafts using LLM gateway."""

    def __init__(self, llm_gateway: LLMGateway):
        self.llm = llm_gateway

    def generate_draft(self, email: Email, style: CommunicationStyle,
                       user_settings: UserSettings,
                       rework_instruction: str = None) -> str:
        """Generate a draft reply."""
        # Build prompt with:
        # - Email thread context
        # - Communication style rules + examples
        # - User's sign-off
        # - Rework instruction (if rework)
        # - Language preference
        #
        # Call llm_gateway.draft()
        # Return formatted draft body with ✂️ marker

    def create_gmail_draft(self, user_client: UserGmailClient,
                           thread_id: str, draft_body: str) -> str:
        """Create the draft in Gmail and return draft_id."""
```

### 5. Lifecycle Manager

Handles label state machine transitions — previously done by Claude reading cleanup.md.

```python
class LifecycleManager:
    """Manages email lifecycle transitions."""

    def handle_done(self, user_id: int, thread_id: str):
        """User marked thread as Done → strip AI labels, archive."""
        # 1. Get all messages in thread
        # 2. Remove all 🤖 AI/* labels except Done
        # 3. Remove INBOX label (archive)
        # 4. Update DB status → 'archived'
        # 5. Log event

    def handle_sent_detection(self, user_id: int, thread_id: str, draft_id: str):
        """Draft disappeared → check if sent."""
        # 1. Try to fetch draft by ID
        # 2. If gone, check for sent message in thread
        # 3. If sent: remove Outbox label, update DB status → 'sent'
        # 4. Log event

    def handle_waiting_retriage(self, user_id: int, thread_id: str):
        """New reply arrived on a Waiting thread → reclassify."""
        # 1. Remove Waiting label
        # 2. Queue for classification
        # 3. Log event

    def handle_rework(self, user_id: int, thread_id: str):
        """User marked Rework → extract instructions, regenerate draft."""
        # 1. Check rework_count (max 3)
        # 2. Fetch current draft
        # 3. Extract instructions above ✂️ marker
        # 4. Call DraftEngine with rework_instruction
        # 5. Trash old draft, create new one
        # 6. Move label: Rework → Outbox (or Action Required if 3rd rework)
        # 7. Update DB
```

**Key improvement**: These are all deterministic operations that never needed Claude's reasoning. They were only routed through Claude because MCP was the only way to access Gmail. Now they're fast, reliable Python code.

---

## Multi-User Data Model

### Database: PostgreSQL

```sql
-- Users table (new)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,           -- user@org.com
    display_name TEXT,
    is_active BOOLEAN DEFAULT true,
    onboarded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-user Gmail label IDs (replaces config/label_ids.yml)
CREATE TABLE user_labels (
    user_id INTEGER REFERENCES users(id),
    label_key TEXT NOT NULL,              -- 'needs_response', 'outbox', etc.
    gmail_label_id TEXT NOT NULL,         -- 'Label_34' (unique per Gmail account)
    gmail_label_name TEXT NOT NULL,       -- '🤖 AI/Needs Response'
    PRIMARY KEY (user_id, label_key)
);

-- Per-user settings (replaces config/*.yml)
CREATE TABLE user_settings (
    user_id INTEGER REFERENCES users(id),
    setting_key TEXT NOT NULL,
    setting_value JSONB NOT NULL,
    PRIMARY KEY (user_id, setting_key)
);
-- setting_key examples:
--   'communication_styles' → full styles config as JSON
--   'contacts' → style overrides, domain overrides, blacklist
--   'sign_off_name' → "Tomáš"
--   'default_language' → "cs"

-- Sync state per user (new)
CREATE TABLE sync_state (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    last_history_id TEXT NOT NULL,
    last_sync_at TIMESTAMPTZ DEFAULT NOW(),
    watch_expiration TIMESTAMPTZ,
    watch_resource_id TEXT
);

-- Emails table (+ user_id column)
CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    gmail_thread_id TEXT NOT NULL,
    gmail_message_id TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    sender_name TEXT,
    subject TEXT,
    snippet TEXT,
    received_at TIMESTAMPTZ,

    classification TEXT NOT NULL CHECK (classification IN (
        'needs_response', 'action_required', 'payment_request', 'fyi', 'waiting'
    )),
    confidence TEXT DEFAULT 'medium' CHECK (confidence IN ('high', 'medium', 'low')),
    reasoning TEXT,
    detected_language TEXT DEFAULT 'cs',
    resolved_style TEXT DEFAULT 'business',
    message_count INTEGER DEFAULT 1,

    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'drafted', 'rework_requested', 'sent', 'skipped', 'archived'
    )),
    draft_id TEXT,
    rework_count INTEGER DEFAULT 0,
    last_rework_instruction TEXT,

    processed_at TIMESTAMPTZ DEFAULT NOW(),
    drafted_at TIMESTAMPTZ,
    acted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, gmail_thread_id)
);

CREATE INDEX idx_emails_user_classification ON emails(user_id, classification);
CREATE INDEX idx_emails_user_status ON emails(user_id, status);

-- Audit log (+ user_id column)
CREATE TABLE email_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    gmail_thread_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'classified', 'label_added', 'label_removed',
        'draft_created', 'draft_trashed', 'draft_reworked',
        'sent_detected', 'archived', 'rework_limit_reached',
        'waiting_retriaged', 'error'
    )),
    detail TEXT,
    label_id TEXT,
    draft_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_user_thread ON email_events(user_id, gmail_thread_id);
```

---

## Authentication: Domain-Wide Delegation

### Setup (org admin does this once)

1. Create a GCP project with Gmail API enabled
2. Create a **service account** (no user interaction needed)
3. In Google Workspace Admin Console → Security → API Controls → Domain-wide Delegation:
   - Add the service account's Client ID
   - Grant scopes: `https://www.googleapis.com/auth/gmail.modify`
4. Configure the service account key in the Gmail Assistant service

### How impersonation works

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    'service-account-key.json',
    scopes=['https://www.googleapis.com/auth/gmail.modify'],
)

# Impersonate user@org.com
delegated_creds = creds.with_subject('user@org.com')
gmail = build('gmail', 'v1', credentials=delegated_creds)

# Now all API calls act as user@org.com
messages = gmail.users().messages().list(userId='me', q='in:inbox').execute()
```

No per-user OAuth flow. No token storage. The service account credential is the only secret.

### Single-User Lite Mode (Personal OAuth)

For individual users who are **not** part of a Google Workspace org (personal Gmail, small teams without admin access), the system supports a "lite" mode using standard OAuth 2.0:

```python
class AuthMode(Enum):
    SERVICE_ACCOUNT = "service_account"   # Multi-user, domain-wide delegation
    PERSONAL_OAUTH = "personal_oauth"     # Single-user, personal Gmail

class GmailAuth:
    """Unified auth that supports both modes."""

    def __init__(self, config: AuthConfig):
        self.mode = config.auth_mode

    def get_credentials(self, user_email: str = None) -> Credentials:
        if self.mode == AuthMode.SERVICE_ACCOUNT:
            return self._service_account_creds(user_email)
        else:
            return self._personal_oauth_creds()

    def _personal_oauth_creds(self) -> Credentials:
        """Load or refresh personal OAuth token."""
        # Standard OAuth 2.0 flow:
        # 1. First run: browser-based consent → stores refresh token
        # 2. Subsequent runs: refresh token → access token
        # Token stored in config/token.json (same as v1)
```

**Lite mode differences**:
- Single user, no `users` table needed (or single row)
- Settings stored in YAML files on disk (like v1) or DB — configurable
- SQLite instead of PostgreSQL (optional — PostgreSQL still works)
- No Pub/Sub push (requires GCP project with billing) — falls back to scheduled polling
- Still gets all the speed benefits of direct Gmail API + LLM gateway

**Configuration**:
```yaml
# config/app.yml
auth:
  mode: personal_oauth            # or "service_account"
  credentials_file: config/credentials.json
  token_file: config/token.json

database:
  backend: sqlite                 # or "postgresql"
  sqlite_path: data/inbox.db     # lite mode
  # postgresql_url: postgresql://...  # multi-user mode
```

---

## User Onboarding Flow

When a new user is added (by admin or self-service):

1. **Create user record** in `users` table
2. **Provision labels**: For each of the 8 AI labels, call `gmail.users().labels().create()` as the impersonated user. Store resulting label IDs in `user_labels`
3. **Initialize settings**: Copy org defaults into `user_settings` (styles, default language, sign-off)
4. **Set up watch**: Call `users.watch()` for the user's mailbox → stores `watch_resource_id` and `watch_expiration`
5. **Initial sync**: Run a full sync to classify existing inbox emails
6. Mark `onboarded_at`

---

## Project Structure

```
gmail-assistant/
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # App configuration (env vars, defaults)
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── gateway.py             # LLMGateway (LiteLLM-backed, model-agnostic)
│   │   └── config.py              # Model selection config
│   │
│   ├── gmail/
│   │   ├── __init__.py
│   │   ├── client.py              # GmailService + UserGmailClient
│   │   ├── auth.py                # Service account + personal OAuth (dual mode)
│   │   └── models.py              # Message, Thread, Draft dataclasses
│   │
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── engine.py              # SyncEngine (incremental + full sync)
│   │   ├── webhook.py             # Pub/Sub webhook handler
│   │   └── watch.py               # Watch renewal scheduler
│   │
│   ├── classify/
│   │   ├── __init__.py
│   │   ├── engine.py              # ClassificationEngine (rules + LLM)
│   │   ├── rules.py               # Rule-based pre-classifier
│   │   └── prompts.py             # LLM prompt templates
│   │
│   ├── draft/
│   │   ├── __init__.py
│   │   ├── engine.py              # DraftEngine (Claude Sonnet)
│   │   └── prompts.py             # Draft generation prompt templates
│   │
│   ├── lifecycle/
│   │   ├── __init__.py
│   │   └── manager.py             # Done/Sent/Waiting/Rework handlers
│   │
│   ├── users/
│   │   ├── __init__.py
│   │   ├── onboarding.py          # Label provisioning, settings init
│   │   └── settings.py            # Per-user config management
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py          # DB connection (PostgreSQL or SQLite)
│   │   ├── models.py              # SQLAlchemy models (or raw queries)
│   │   ├── jobs.py                # PostgreSQL job queue (SKIP LOCKED)
│   │   └── migrations/            # Alembic migrations
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhook.py             # POST /webhook/gmail
│   │   ├── admin.py               # User management endpoints
│   │   └── briefing.py            # GET /api/briefing/{user_email}
│   │
│   └── tasks/
│       ├── __init__.py
│       └── workers.py             # Asyncio workers (sync, classify, draft, cleanup)
│
├── config/
│   ├── communication_styles.yml   # Org-wide default styles (template)
│   └── contacts.example.yml       # Example contacts config
│
├── tests/
│   ├── test_classify.py
│   ├── test_lifecycle.py
│   ├── test_sync.py
│   └── test_draft.py
│
├── docker-compose.yml             # App + PostgreSQL (self-hosted)
├── Dockerfile
├── requirements.txt
├── alembic.ini
└── README.md
```

---

## Processing Pipeline Comparison

### v1: 12 emails, 728 seconds

```
bin/process-inbox (bash)
  └─ claude --model sonnet -p /cleanup     ← 100s  (Claude reads prompt, calls MCP 5+ times)
  └─ claude --model haiku -p /inbox-triage ← 590s  (Claude reads prompt, calls MCP 24+ times)
  └─ claude --model sonnet -p /draft       ← 38s   (Claude reads prompt, calls MCP 6+ times)
                                             ─────
                                             728s total, ~35+ MCP round-trips
```

### v2: 12 emails, estimated 15-30 seconds

```
Pub/Sub notification arrives
  └─ Sync engine: history.list()                  ← ~200ms  (1 API call)
  └─ For each new message (parallel):
      ├─ Rule-based classify                      ← ~1ms    (local, no API)
      ├─ LLM classify (if needed, via gateway)    ← ~500ms  (1 API call)
      ├─ Apply label                              ← ~100ms  (1 API call, or batched)
      └─ Store in DB                              ← ~5ms    (local)
  └─ For needs_response emails (parallel):
      ├─ Generate draft (via gateway)             ← ~3-5s   (1 API call)
      ├─ Create Gmail draft                       ← ~100ms  (1 API call)
      └─ Move label                               ← ~100ms  (1 API call)
                                                    ─────
                                                    ~5-10s for classification
                                                    ~10-20s total with drafts
```

**Speed improvement**: ~50x for classification, ~35x end-to-end.

**Cost improvement**: Only 2 Claude API calls per email (classify + draft) instead of 35+ MCP round-trips through Claude's context window.

---

## Implementation Phases

### Phase 1: Gmail API Foundation (replace MCP)

- [ ] `src/gmail/auth.py` — Personal OAuth (lite mode first, service account later)
- [ ] `src/gmail/client.py` — GmailService + UserGmailClient (search, get, modify, draft, batch)
- [ ] `src/db/` — SQLite schema (evolve from existing `data/inbox.db`), migrations
- [ ] `src/llm/gateway.py` — LLM gateway with LiteLLM
- [ ] `src/users/onboarding.py` — Auto-provision labels, store IDs
- [ ] Tests: Gmail client against a test account

**Milestone**: Can search, read, label, and draft via direct API. Single user, SQLite, personal OAuth.

### Phase 2: Classification + Lifecycle (replace Claude commands)

- [ ] `src/classify/rules.py` — Rule-based pre-classifier (port from `bin/classify-phase-b`)
- [ ] `src/classify/engine.py` — LLM classifier via gateway
- [ ] `src/classify/prompts.py` — Extract classification prompt from `inbox-triage.md`
- [ ] `src/lifecycle/manager.py` — Done/Sent/Waiting handlers (port from `cleanup.md`)
- [ ] Tests: Classification accuracy against labeled test set

**Milestone**: Full triage + lifecycle runs as Python code, Claude only called for ambiguous classification.

### Phase 3: Draft Generation (replace draft-response command)

- [ ] `src/draft/engine.py` — Draft generation via LLM gateway
- [ ] `src/draft/prompts.py` — Extract draft prompt from `draft-response.md` and `rework-draft.md`
- [ ] `src/users/settings.py` — Per-user styles, contacts, language
- [ ] Rework loop implementation
- [ ] Tests: Draft quality review

**Milestone**: Full pipeline runs without Claude Code or MCP.

### Phase 4: Push Notifications (replace polling)

- [ ] `src/sync/webhook.py` — Pub/Sub webhook endpoint
- [ ] `src/sync/engine.py` — Incremental sync via history.list()
- [ ] `src/sync/watch.py` — Watch renewal scheduler
- [ ] `src/api/webhook.py` — FastAPI route for POST /webhook/gmail
- [ ] GCP Pub/Sub topic + push subscription setup
- [ ] Fallback scheduled sync

**Milestone**: Near real-time email processing via push notifications.

### Phase 5: Multi-User + Admin (upgrade from lite → multi-user)

- [ ] PostgreSQL backend (add as alternative to SQLite)
- [ ] Service account auth + domain-wide delegation
- [ ] `src/api/admin.py` — User management (add, remove, configure)
- [ ] `src/api/briefing.py` — Per-user briefing/dashboard endpoint
- [ ] Asyncio job queue with PostgreSQL job table for concurrent per-user processing
- [ ] Rate limiting (respect Gmail API quotas: 250 units/user/second)
- [ ] Docker Compose for self-hosted deployment (app + PostgreSQL)
- [ ] Monitoring, logging, health checks

**Milestone**: Production-ready multi-user service. SQLite lite mode already works from Phases 1-4.

---

## Rate Limits & Quotas

Gmail API quotas to respect:

| Quota | Limit | Strategy |
|-------|-------|----------|
| Per-user rate limit | 250 quota units/second | Throttle per-user workers |
| Daily usage limit | 1,000,000,000 units/day | More than enough |
| messages.list | 5 units | Batch where possible |
| messages.get | 5 units | Get thread (1 call) vs individual messages |
| messages.modify | 5 units | Use batch_modify for multiple |
| drafts.create | 10 units | One per draft |
| history.list | 2 units | Very cheap, ideal for incremental sync |

LLM API (via gateway — model-agnostic):
- Classification model: fast + cheap (default: Claude Haiku, alternatives: GPT-4o-mini, Gemini Flash)
- Draft model: high quality (default: Claude Sonnet, alternatives: GPT-4o, Gemini Pro)
- Provider batch APIs available for non-urgent processing (e.g. Anthropic Batch API: 50% cost reduction)

---

## Migration Path

The v1 system can continue running during development. Migration is incremental:

### Single-user migration (v1 → v2 lite)
1. Evolve existing `data/inbox.db` schema in place (add new columns, tables)
2. Import `config/label_ids.yml` into `user_labels` table
3. Import `config/contacts.yml` and `config/communication_styles.yml` into `user_settings`
4. Reuse existing OAuth credentials (`config/token.json`)
5. Set up Pub/Sub watch() for the user
6. Disable launchd scheduler
7. Verify push-driven processing works

### Multi-user upgrade (v2 lite → v2 full)
1. Export SQLite data into PostgreSQL (with user_id scoping)
2. Switch auth mode to service account + domain-wide delegation
3. Onboard additional users
4. Switch config to PostgreSQL backend

---

## Resolved Decisions

1. **Task queue**: Simple asyncio + PostgreSQL job table. No Redis/Celery. A `jobs` table with `SKIP LOCKED` polling is sufficient for <100 users and keeps the stack minimal.

2. **Single-user lite mode**: YES. Personal OAuth + SQLite + polling fallback for individual users not in a Workspace org. Same codebase, different config.

3. **Deployment**: Self-hosted via Docker Compose (app + PostgreSQL). No cloud vendor lock-in. Pub/Sub webhook works from any publicly reachable endpoint (or via ngrok/Cloudflare tunnel for dev). Production can run on any VPS.

4. **LLM provider**: LLM gateway (LiteLLM or similar) for model-agnostic operation. Default to Claude Haiku for classification + Claude Sonnet for drafts, but configurable to any provider (OpenAI, Google, local models). Single config change to swap models.

5. **Admin UI**: API + CLI first. Web UI is a future nice-to-have, not a v2 blocker.

6. **Public endpoint**: Not a problem for self-hosted. Pub/Sub push webhook works directly.

7. **Database**: Start with SQLite. Build the single-user path first, add PostgreSQL as the multi-user backend later. SQLite is the default; PostgreSQL is an upgrade path when scaling to multi-user.
