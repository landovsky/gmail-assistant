# Gmail Assistant v2

AI-powered Gmail inbox management system that automatically classifies incoming emails, generates draft responses, and manages email workflows through Gmail labels.

## Features

- **AI Classification**: Automatically categorizes emails (needs_response, action_required, payment_request, fyi, waiting)
- **Draft Generation**: Creates contextual draft responses using LLM
- **Gmail Integration**: OAuth 2.0 authentication, label management, Pub/Sub webhooks
- **Agent System**: Specialized agents for handling specific email types (pharmacy, reservations, etc.)
- **Debug UI**: Visual email inspection with timeline, LLM calls, and agent runs
- **Admin Interface**: Read-only database browser for all system data
- **Background Jobs**: Async processing with SQLite or Redis-based queues
- **CLI Tools**: Command-line utilities for debugging and administration

## Tech Stack

- **Runtime**: Bun
- **Framework**: Hono (HTTP)
- **Database**: Drizzle ORM (SQLite/PostgreSQL)
- **LLM**: Vercel AI SDK (multi-provider: Claude, GPT, Gemini)
- **Gmail**: googleapis (OAuth, Pub/Sub, History API)
- **Job Queue**: BullMQ (Redis) or SQLite-based

## Quick Start

### 1. Install Dependencies

```bash
bun install
```

### 2. Configure Gmail OAuth

Create `config/credentials.json` with your Google Cloud OAuth 2.0 credentials:

```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID",
    "project_id": "your-project",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["http://localhost"]
  }
}
```

**How to get credentials:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download JSON and save as `config/credentials.json`

### 3. Set Environment Variables

Create `.env` file:

```bash
# Database
DATABASE_URL=./data/gmail-assistant.db

# LLM Provider (choose one or more)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_AI_API_KEY=...

# Default LLM model
LLM_MODEL=claude-3-5-sonnet-20241022

# Job Queue
JOB_QUEUE_TYPE=sqlite  # or "bullmq" for Redis

# Server
PORT=3000
NODE_ENV=development

# Basic Auth (optional)
# BASIC_AUTH_USERNAME=admin
# BASIC_AUTH_PASSWORD=secret
```

### 4. Initialize Database

```bash
bun run db:push
```

### 5. Start Server

```bash
bun run dev
```

The server will start on `http://localhost:3000`

### 6. Onboard Your Gmail Account

Visit `http://localhost:3000/api/auth/init` in your browser. This will:
- Trigger Gmail OAuth flow (browser popup)
- Save OAuth tokens to `config/token.json`
- Create your user account in the database
- Initialize sync state

**Note**: First-time OAuth requires manual browser interaction.

### 7. Access Debug UI

Navigate to `http://localhost:3000/debug/emails` to view:
- Email list with filtering and search
- Email detail pages with timeline
- LLM call inspection
- Agent run details

## CLI Tools

The system includes 5 CLI tools for debugging and administration. Access via `bun run cli`:

### 1. Classification Debugger

Debug why an email was classified a certain way:

```bash
# Interactive debugging
bun run cli classify-debug \
  --sender "user@example.com" \
  --subject "Meeting request" \
  --body "Can we meet tomorrow at 2pm?" \
  --live

# Debug from database
bun run cli classify-debug --thread-id "thread-abc123" --live
```

**Options:**
- `--sender, -s` - Sender email address
- `--sender-name, -n` - Sender display name
- `--subject` - Email subject line
- `--body, -b` - Email body text
- `--thread-id, -t` - Load from database by thread ID
- `--live` - Make actual LLM call (requires API key)

**Output:** Step-by-step classification pipeline, rule engine evaluation, LLM result

### 2. Full Sync Trigger

Trigger a complete inbox scan:

```bash
# Basic sync
bun run cli full-sync

# Reset database first, then sync
bun run cli full-sync --reset

# With authentication
bun run cli full-sync --user admin --password secret
```

**Options:**
- `--reset` - Clear database before syncing
- `--url` - API URL (default: http://localhost:3000)
- `--user` - Basic auth username
- `--password` - Basic auth password

### 3. Database Reset

Clear all transient data (preserves users and settings):

```bash
# Interactive confirmation
bun run cli db-reset

# Skip confirmation
bun run cli db-reset --confirm
```

**Deletes:** Jobs, emails, events, sync state
**Preserves:** Users, labels, settings

### 4. Gmail Label Cleanup

Remove AI workflow labels from Gmail messages:

```bash
# Dry run (preview only)
bun run cli label-cleanup

# Actually remove labels
bun run cli label-cleanup --delete

# Limit number of messages
bun run cli label-cleanup --delete --limit 500
```

**Options:**
- `--dry-run` - Preview mode (default)
- `--delete` - Actually remove labels
- `--limit` - Max messages to process (default: 100)

### 5. Classification Test Suite

Run classification tests against fixture file:

```bash
# Run all tests
bun run cli classify-test

# Test specific category
bun run cli classify-test --category needs_response

# Rules engine only (no LLM calls)
bun run cli classify-test --rules-only

# Custom fixture file
bun run cli classify-test --fixture ./tests/my-tests.yml
```

**Fixture format** (`tests/fixtures/classification.yml`):

```yaml
tests:
  - id: test-1
    from: sender@example.com
    sender_name: John Doe
    subject: Meeting request
    body: Can we schedule a meeting for next week?
    expected_category: needs_response

  - id: test-2
    from: billing@service.com
    subject: Invoice #1234
    body: Your invoice is attached
    expected_category: payment_request
```

**Output:** Pass/fail per test, accuracy percentage, confusion matrix

## Debug UI

### Email List (`/debug/emails`)

Browse and filter all processed emails with debug metadata.

**Features:**
- Search across subject, body, sender, thread ID
- Filter by status (pending, drafted, sent, etc.)
- Filter by classification (needs_response, action_required, etc.)
- View event counts and LLM call counts
- Click ID or subject to view details

**Columns:**
- ID, User, Subject, Sender
- Classification, Status, Confidence
- Events, LLM calls, Received timestamp

### Email Detail (`/debug/email/:id`)

Deep inspection of a single email with complete processing history.

**Features:**
- Complete email metadata (8-field grid)
- Timeline visualization merging events, LLM calls, agent runs
- Expandable LLM prompts and responses
- Agent run details with tool calls
- Reclassify button to re-run classification
- Prev/next navigation between emails

**Sections:**
1. **Metadata** - Subject, sender, thread/message IDs, badges
2. **Timeline** - Chronological events with color-coded dots (green=event, purple=LLM, cyan=agent)
3. **Events** - All lifecycle events for the thread
4. **LLM Calls** - Prompts, responses, tokens, latency with expand/collapse
5. **Agent Runs** - Profile, status, iterations, tool calls, final message

### Admin Database Browser (`/admin`)

Read-only interface for browsing all database tables.

**Features:**
- Browse 9 tables: users, user_labels, user_settings, sync_state, emails, email_events, llm_calls, jobs, agent_runs
- Search within tables
- Pagination (25/50/100 per page)
- Record detail views
- Debug link from emails table to `/debug/email/:id`
- Full Sync button in navigation

## API Endpoints

### Health & Admin

- `GET /api/health` - Health check (returns `{status: "ok"}`)
- `POST /api/auth/init` - Bootstrap OAuth & onboard user
- `POST /api/reset` - Clear transient data (jobs, emails, events)

### User Management

- `GET /api/users` - List all active users
- `POST /api/users` - Create new user
- `GET /api/users/:id/settings` - Get user settings as key-value map
- `PUT /api/users/:id/settings` - Update single setting (upsert)
- `GET /api/users/:id/labels` - Get Gmail label mappings
- `GET /api/users/:id/emails` - List user's emails with filtering

### Email Operations

- `GET /api/debug/emails` - Search and filter emails (JSON API)
- `GET /api/emails/:id/debug` - Complete email debug data (JSON)
- `POST /api/emails/:id/reclassify` - Force re-classification
- `GET /api/briefing/:email` - Inbox briefing by classification

### Sync & Watch

- `POST /api/sync` - Trigger sync job (`?full=true` for complete scan)
- `POST /api/watch` - Register Gmail Pub/Sub watch
- `GET /api/watch/status` - Show watch status and expiration
- `POST /webhook/gmail` - Gmail Pub/Sub webhook (public endpoint)

### HTML UI

- `GET /` - Redirects to `/debug/emails`
- `GET /debug/emails` - Email list with search/filter UI
- `GET /debug/email/:id` - Email detail with timeline
- `GET /admin` - Database browser landing page
- `GET /admin/table/:tableName` - Browse specific database table

## Configuration

### Application Config

Create `config/app.yml` for application settings:

```yaml
server:
  host: localhost
  port: 3000

gmail:
  credentials_path: config/credentials.json
  token_path: config/token.json

llm:
  default_model: claude-3-5-sonnet-20241022
  temperature: 0.3
  max_tokens: 2000

classification:
  default_language: en
  default_style: business

jobs:
  concurrency: 3
  retry_attempts: 3
  retry_delay_ms: 5000
```

### Gmail Labels

The system creates these labels in your Gmail account:
- **Needs Response** - Emails requiring a reply
- **Action Required** - Urgent action items
- **Waiting** - Emails awaiting external response
- **FYI** - Informational emails
- **Outbox** - Drafted emails ready for review

Labels are created automatically during onboarding.

## Development

### Running Tests

```bash
# All tests
bun test

# Watch mode
bun test:watch

# E2E tests only
bun test:e2e
```

### Code Quality

```bash
# Lint
bun run lint

# Format
bun run format

# Check formatting
bun run format:check
```

### Database Management

```bash
# Generate migrations
bun run db:generate

# Run migrations
bun run db:migrate

# Push schema changes
bun run db:push

# Open Drizzle Studio
bun run db:studio
```

## Architecture

```
┌──────────────────────────────────────────┐
│           Gmail Account                   │
│  (OAuth, Pub/Sub, Labels, Drafts)        │
└──────────────────┬───────────────────────┘
                   │
                   ↓
┌──────────────────────────────────────────┐
│          Gmail Assistant Server           │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │   REST API (Hono)                  │  │
│  │   - User management                │  │
│  │   - Email operations               │  │
│  │   - Sync triggering                │  │
│  │   - Debug endpoints                │  │
│  └────────────────────────────────────┘  │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │   HTML UI (Hono JSX)               │  │
│  │   - Email list                     │  │
│  │   - Email detail + timeline        │  │
│  │   - Admin database browser         │  │
│  └────────────────────────────────────┘  │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │   Background Jobs                  │  │
│  │   - classify, draft, rework        │  │
│  │   - sync, cleanup                  │  │
│  │   - manual_draft, agent_process    │  │
│  └────────────────────────────────────┘  │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │   LLM Services                     │  │
│  │   - Classification                 │  │
│  │   - Draft generation               │  │
│  │   - Context gathering              │  │
│  │   - Agent execution                │  │
│  └────────────────────────────────────┘  │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │   Database (Drizzle ORM)           │  │
│  │   - SQLite or PostgreSQL           │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**Email Lifecycle States:**
- `pending` → Email classified as needs_response
- `drafted` → AI draft created in Gmail
- `rework_requested` → User requested changes
- `sent` → User sent the email
- `archived` → User marked as done
- `skipped` → No response needed

## Troubleshooting

### OAuth Issues

**Problem:** "Error: invalid_grant" or "Token has been expired"

**Solution:**
```bash
# Delete token file and re-authenticate
rm config/token.json
# Visit /api/auth/init again in browser
```

### Classification Not Working

**Problem:** Emails not being classified

**Solution:**
```bash
# Debug a specific email
bun run cli classify-debug --thread-id "thread-abc123" --live

# Check LLM API key is set
echo $ANTHROPIC_API_KEY

# Check server logs for errors
```

### Database Errors

**Problem:** "Table not found" or migration errors

**Solution:**
```bash
# Push latest schema
bun run db:push

# Or reset and reinitialize
bun run cli db-reset --confirm
bun run db:push
```

### Gmail API Quota

**Problem:** "User rate limit exceeded"

**Solution:**
- Gmail API has quota limits (default: 250 quota units/user/second)
- Reduce job concurrency in `config/app.yml`
- Exponential backoff is built-in
- Request quota increase in Google Cloud Console

### Background Jobs Not Running

**Problem:** Jobs stuck in "pending" status

**Solution:**
```bash
# Check worker pool is running
# Look for log line: "Worker pool started"

# Check job queue type
echo $JOB_QUEUE_TYPE

# If using BullMQ, ensure Redis is running
redis-cli ping
```

## Deployment

### Production Checklist

- [ ] Set `NODE_ENV=production`
- [ ] Configure PostgreSQL (recommended over SQLite)
- [ ] Use BullMQ with Redis for job queue
- [ ] Enable basic auth for API (`BASIC_AUTH_USERNAME`, `BASIC_AUTH_PASSWORD`)
- [ ] Set up Gmail Pub/Sub watch
- [ ] Configure proper logging
- [ ] Set up SSL/TLS
- [ ] Configure backup strategy

### Docker Deployment

```dockerfile
FROM oven/bun:1

WORKDIR /app

COPY package.json bun.lockb ./
RUN bun install --production

COPY . .

EXPOSE 3000

CMD ["bun", "run", "start"]
```

## Contributing

1. Create a new branch: `git checkout -b feat/your-feature`
2. Make changes and test: `bun test`
3. Format code: `bun run format`
4. Commit using conventional commits: `git commit -m "feat: your feature"`
5. Push and create PR

**Conventional Commits:**
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code refactoring

## License

MIT

## Support

For issues and questions:
- GitHub Issues: [https://github.com/landovsky/gmail-assistant/issues](https://github.com/landovsky/gmail-assistant/issues)

---

**Built with** ❤️ **using Bun, Hono, and Vercel AI SDK**
