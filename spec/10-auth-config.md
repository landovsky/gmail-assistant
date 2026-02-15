# Authentication, Authorization, and Configuration

## Authentication Modes

The system supports two authentication modes for Gmail API access:

### Personal OAuth (Single-User)

**Purpose**: Lite mode for personal use or small teams

**Setup Process**:
1. Create Google Cloud Project
2. Enable Gmail API
3. Create OAuth 2.0 Client ID (Desktop application type)
4. Download credentials JSON file
5. Place file at configured path (default: `config/credentials.json`)
6. On first run: Browser-based consent flow opens
7. User grants permissions
8. Token saved to configured path (default: `config/token.json`)
9. Token auto-refreshes on subsequent runs

**OAuth Flow Details**:
- Authorization server: Google OAuth 2.0
- Flow type: Authorization Code flow for installed apps
- Redirect: Localhost server (http://localhost:port/)
- User consent: One-time (unless revoked)
- Token storage: JSON file on disk
- Refresh: Automatic using refresh token
- Expiration: Access token expires after 1 hour, automatically refreshed

**Required Scope**:
- `https://www.googleapis.com/auth/gmail.modify`
- Permissions: Read, compose, modify labels (does NOT include gmail.send)

**Token Lifecycle**:
1. Check if token file exists
2. Load credentials from token file
3. If expired and refresh token available → auto-refresh
4. If no valid credentials → trigger browser consent flow
5. Save refreshed/new credentials to token file
6. Use credentials for Gmail API calls

**Files**:
- Credentials file: OAuth client ID and secret (from Google Cloud Console)
- Token file: User access token and refresh token (generated after consent)

### Service Account (Multi-User)

**Purpose**: Multi-tenant deployments in Google Workspace environments

**Setup Process**:
1. Create Google Cloud Project
2. Enable Gmail API
3. Create Service Account
4. Download service account key JSON
5. Enable domain-wide delegation
6. Grant service account Gmail API access in Workspace Admin Console
7. Place key file at configured path (default: `config/service-account-key.json`)

**Impersonation**:
- Service account acts on behalf of users
- Uses `credentials.with_subject(user_email)` to impersonate
- No per-user consent required (admin pre-authorizes)

**Scope**:
- Same as personal OAuth: `gmail.modify`

**Current Status**:
- Architecture ready
- Partially implemented
- Designed for future Workspace deployments

**Files**:
- Service account key: Private key for authentication (from Google Cloud Console)

## User Onboarding

### Standard Onboarding Process

**Trigger**: API endpoint `/api/auth/init` or manual Python invocation

**Steps**:

1. **Authenticate with Gmail**:
   - In personal OAuth mode: Trigger browser consent if needed
   - Get user email from Gmail profile API

2. **Create User Record**:
   - Insert into users table
   - Store email, display name (optional)
   - Mark as active

3. **Provision Gmail Labels**:
   - Create parent label: 🤖 AI
   - Create 8 child labels:
     - 🤖 AI/Needs Response
     - 🤖 AI/Outbox
     - 🤖 AI/Rework
     - 🤖 AI/Action Required
     - 🤖 AI/Payment Requests
     - 🤖 AI/FYI
     - 🤖 AI/Waiting
     - 🤖 AI/Done

4. **Store Label IDs**:
   - Save Gmail label IDs to user_labels table
   - Map logical names to Gmail IDs

5. **Initialize Settings**:
   - Import from YAML config files if available
   - Store in user_settings table

6. **Initialize Sync State**:
   - Create sync_state record
   - Fetch current historyId from Gmail
   - Set watch expiration to null (watch not yet registered)

7. **Mark as Onboarded**:
   - Set onboarded_at timestamp
   - User ready for email processing

### V1 Migration Path

**Purpose**: Import existing configuration from v1 deployment

**Trigger**: `migrate_v1=true` parameter on onboarding

**Process**:
- Load existing label IDs from `config/label_ids.yml`
- Skip label creation (assumes labels already exist)
- Import label mappings to database
- Useful for upgrading from v1 to v2

## Per-User Settings

### Storage
- Database table: user_settings (user_id, setting_key, setting_value)
- Format: JSON-serialized values
- Fallback: YAML config files if not in database

### Access Pattern
Database-first, YAML fallback:
1. Check user_settings table for key
2. If not found, check YAML config file
3. If not found, use system default

### Standard Settings

**communication_styles**
- Type: Object with style definitions
- Keys: formal, business, informal
- Values: Greeting patterns, sign-off patterns, tone guidelines, examples
- Source: `config/communication_styles.yml` (fallback)
- Purpose: Draft generation style templates

**contacts**
- Type: Object with email/domain mappings
- Fields:
  - style_overrides: Map email → style name
  - domain_overrides: Map domain → style name
  - language_overrides: Map email/domain → language code
  - blacklist: List of glob patterns for automated senders
- Source: `config/contacts.yml` (fallback)
- Purpose: Style resolution, language detection, automation filtering

**sign_off_name**
- Type: String
- Purpose: Email signature name
- Example: "Jan Novák" or "The Support Team"

**default_language**
- Type: String
- Purpose: Default language for drafts
- Example: "cs" (Czech), "en" (English)

### Setting Management

**Get All Settings**:
- Endpoint: `GET /api/users/{user_id}/settings`
- Returns: Merged view of database + YAML defaults

**Update Setting**:
- Endpoint: `PUT /api/users/{user_id}/settings`
- Body: `{"key": "setting_name", "value": any_value}`
- Action: Upsert to user_settings table

## Authorization Model

### Current Implementation

**Designed for**: Single-user or trusted multi-user environments

**Authentication**:
- HTTP Basic Auth (optional)
- Configured via environment variables
- If not configured → all endpoints public

**Protected Endpoints**:
- All routes except:
  - `/webhook/*` (Gmail Pub/Sub callbacks)
  - `/api/health` (health check)
  - `/admin/statics/*` (CSS/JS assets)

**Authorization Logic**:
- No per-user authentication
- No row-level security enforcement
- Relies on application-level user_id scoping
- Admin UI is read-only for safety

**Credentials**:
- Admin username: Configured via environment variable
- Admin password: Configured via environment variable
- Comparison: Constant-time to prevent timing attacks

### Future Multi-Tenant Enhancements

From multi-tenant design document:
- Row-level security in PostgreSQL
- Per-user OAuth with encrypted token storage
- API keys for programmatic access
- Admin dashboard for Workspace administrators
- Tenant isolation at database level

## Configuration System

### Architecture

**Hierarchy**: YAML base → Environment variable overrides

**Format**:
- Base config: YAML file at `config/app.yml`
- Overrides: Environment variables prefixed with `GMA_`
- Validation: Pydantic Settings classes

### Configuration Sections

**auth** (prefix: GMA_AUTH_):
- mode: personal_oauth | service_account
- credentials_file: Path to OAuth credentials JSON
- token_file: Path to OAuth token JSON
- service_account_file: Path to service account key JSON
- scopes: List of Gmail API scopes

**database** (prefix: GMA_DB_):
- backend: sqlite | postgresql
- sqlite_path: Database file path (default: data/inbox.db)
- postgresql_url: PostgreSQL connection string

**llm** (prefix: GMA_LLM_):
- classify_model: Fast model for classification (default: gemini-2.0-flash)
- draft_model: Quality model for drafts (default: gemini-2.5-pro)
- context_model: Model for context gathering
- max_classify_tokens: Token limit for classification (default: 256)
- max_draft_tokens: Token limit for drafts (default: 2048)

**sync** (prefix: GMA_SYNC_):
- pubsub_topic: Gmail Pub/Sub topic for push notifications
- fallback_interval_minutes: Polling frequency (default: 15)
- full_sync_interval_hours: Full sync frequency (default: 1)
- history_max_results: History API page size (default: 100)

**server** (prefix: GMA_SERVER_):
- host: Bind address (default: 0.0.0.0)
- port: Server port (default: 8000)
- webhook_secret: Webhook verification secret (not currently used)
- log_level: Logging level (default: info)
- worker_concurrency: Background worker count (default: 3)
- admin_user: Basic auth username
- admin_password: Basic auth password

**routing** (prefix: GMA_ROUTING_):
- rules: List of routing rule objects

**agent** (prefix: GMA_AGENT_):
- profiles: Map of agent profile configurations

### Environment Variable Mapping

**Examples**:
- `GMA_DB_BACKEND=postgresql` → database.backend = "postgresql"
- `GMA_LLM_CLASSIFY_MODEL=claude-3-haiku` → llm.classify_model = "claude-3-haiku"
- `GMA_SERVER_PORT=3000` → server.port = 3000
- `GMA_SYNC_PUBSUB_TOPIC=projects/x/topics/y` → sync.pubsub_topic = "projects/x/topics/y"

### Config Loading

**Process**:
1. Load YAML file (if exists)
2. Merge environment variable overrides
3. Validate with Pydantic models
4. Raise validation error if required fields missing
5. Use validated config throughout application

## Required Credentials and API Keys

### Minimum Setup (Personal OAuth)

**Google Cloud**:
1. Google Cloud Project with Gmail API enabled
2. OAuth 2.0 Client ID (Desktop app)
3. Downloaded credentials JSON → `config/credentials.json`
4. First run generates `config/token.json`

**LLM Provider** (at least one):
- ANTHROPIC_API_KEY (for Claude models)
- OPENAI_API_KEY (for GPT models)
- GEMINI_API_KEY (for Gemini models)
- Or any LiteLLM-supported provider key

**Workflow**:
1. Set API key as environment variable
2. Run server
3. Call `/api/auth/init` endpoint
4. Browser consent flow opens
5. Grant permissions
6. Token saved, user onboarded

### Optional Setup (Push Notifications)

**Google Cloud Pub/Sub**:
1. Create Pub/Sub topic
2. Create push subscription pointing to `/webhook/gmail` endpoint
3. Configure subscription to push notifications
4. Set `GMA_SYNC_PUBSUB_TOPIC` environment variable
5. Call `/api/watch` endpoint to register watches

**Without Pub/Sub**:
- System falls back to periodic polling (every 15 min)
- Less real-time but still functional

### Optional Setup (Basic Auth)

**Environment Variables**:
- `GMA_SERVER_ADMIN_USER`: Admin username
- `GMA_SERVER_ADMIN_PASSWORD`: Admin password

**Without Basic Auth**:
- All endpoints public
- Suitable for local development or trusted networks

### Service Account Setup (Multi-User)

**Google Workspace**:
1. Service account with domain-wide delegation
2. Download key JSON → `config/service-account-key.json`
3. Set `GMA_AUTH_MODE=service_account`
4. Grant Gmail API access in Workspace Admin Console

## Security Considerations

### Secrets Management
- Credentials stored in config directory (gitignored)
- No encryption at rest for tokens/credentials
- File system permissions control access
- Production: Consider secret management service (Kubernetes Secrets, etc.)

### Data Isolation
- All database tables include user_id foreign key
- Every query scoped to user
- No row-level security enforcement (relies on application logic)
- Admin UI is read-only

### Gmail Permissions
- Scope: gmail.modify (read, compose, modify labels)
- Does NOT include gmail.send (cannot send email directly)
- Cannot delete emails permanently (only archive via labels)
- Cannot read emails outside of user's mailbox

### Webhook Security
- Gmail webhook endpoint is public (no auth required)
- Pub/Sub provides infrastructure-level authentication
- No webhook signature verification implemented
- Validates user exists before processing

### Files to Protect

**Critical**:
- `config/credentials.json` - OAuth client secret
- `config/token.json` - User access + refresh tokens
- `config/service-account-key.json` - Service account private key

**Important**:
- `data/inbox.db` - Contains email metadata and drafts
- `.env` - API keys and secrets

**Recommendations**:
- .gitignore all credential files
- Restrict file permissions (chmod 600)
- Use environment variables for secrets in production
- Rotate credentials regularly
- Enable audit logging

## Deployment Considerations

### Single-User (Personal)
- Personal OAuth mode
- SQLite database
- Local file storage for credentials
- No authentication required (trusted environment)

### Small Team (Shared)
- Personal OAuth mode
- SQLite or PostgreSQL database
- Shared credentials file
- Basic auth for access control
- Single Gmail account monitored

### Enterprise (Future)
- Service account mode
- PostgreSQL database
- Kubernetes Secrets for credential management
- Per-user OAuth with encrypted storage
- Row-level security
- Admin dashboard
- Audit logging
