# Gmail Assistant v2

An AI-powered Gmail inbox management system that automatically classifies emails, generates draft responses, and manages email workflows through Gmail labels.

## Features

- **Intelligent Email Classification** - Automatically categorizes emails (needs_response, action_required, payment_request, fyi, waiting)
- **AI Draft Generation** - Creates contextual draft responses using Claude/GPT/Gemini
- **Workflow Automation** - Manages complete email lifecycle from classification → draft → sent
- **Gmail Label Management** - Organizes emails with smart labels visible in Gmail
- **Rework Support** - Regenerate drafts with user feedback (up to 3 times)
- **Multi-Language** - Detects language and generates responses in matching language
- **Communication Styles** - Adapts tone (formal/business/informal) based on sender
- **Background Jobs** - Reliable job queue with retry logic
- **Debug UI** - Web interface for monitoring email processing

## Tech Stack

- **Bun** — runtime, test runner, package manager
- **Hono** — HTTP framework, REST API, webhooks
- **Hono JSX** — server-rendered debug/admin pages
- **Drizzle ORM** — type-safe queries (SQLite + PostgreSQL)
- **Vercel AI SDK** — LLM integration (Claude/GPT/Gemini)
- **googleapis** — Gmail API client, OAuth, Pub/Sub
- **BullMQ/SQLite** — job queue with retries
- **Zod** — validation for API inputs, config, LLM responses

## Quick Start

### Prerequisites

- [Bun](https://bun.sh) >= 1.0.0
- Gmail account with API access
- LLM API key (Anthropic Claude, OpenAI GPT, or Google Gemini)

### Installation

```bash
# Clone and install
git clone https://github.com/landovsky/gmail-assistant.git
cd gmail-assistant
bun install

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Setup Gmail OAuth credentials
# 1. Go to Google Cloud Console
# 2. Enable Gmail API
# 3. Create OAuth 2.0 credentials (Desktop app)
# 4. Download as config/credentials.json

# Initialize database
bun run db:push

# Authenticate with Gmail
bun run cli auth init

# Start server
bun run dev
```

Visit `http://localhost:3000/debug/emails`

## Usage

### CLI Commands

```bash
# Authentication
bun run cli auth init         # First-time OAuth setup
bun run cli auth status       # Check authentication

# Sync Operations
bun run cli sync              # Incremental sync
bun run cli sync --full       # Full inbox scan

# Job Queue
bun run cli jobs start        # Start background worker
bun run cli jobs list         # List pending jobs

# Labels
bun run cli labels provision  # Create Gmail labels
```

### Rework Workflow

1. Find draft in Gmail Outbox label
2. Edit draft, add instructions above ✂️ marker:
   ```
   Make this shorter and more formal
   ✂️
   [existing draft text...]
   ```
3. Apply "Rework" label in Gmail
4. System regenerates draft (max 3 times)

## Architecture

```
Gmail Inbox
    ↓
Gmail Pub/Sub Push Notification
    ↓
Sync Engine (History API)
    ↓
Classification (Rule-based + LLM)
    ↓
Draft Generation (Context-aware AI)
    ↓
Gmail Draft Created
```

**Email Lifecycle States:**
- `pending` → Email classified as needs_response
- `drafted` → AI draft created in Gmail
- `rework_requested` → User requested changes
- `sent` → User sent the email
- `archived` → User marked as Done
- `skipped` → No response needed (fyi, action_required, etc.)

## Development

```bash
# Run tests
bun test
bun run test:e2e

# Code quality
bun run lint
bun run format

# Database
bun run db:studio      # Open Drizzle Studio
bun run db:generate    # Generate migrations
bun run db:push        # Push schema changes
```

### Project Structure

```
src/
├── api/                  # HTTP routes
├── jobs/handlers/        # classify, draft, rework, cleanup
├── services/
│   ├── gmail/            # Gmail API, sync, auth
│   ├── llm/              # LLM integration
│   ├── classification/   # Email classification
│   └── drafting/         # Draft generation
├── workflows/            # Email lifecycle state machine
└── db/                   # Drizzle schema

tests/
├── e2e/                  # End-to-end workflow tests
├── integration/          # Integration tests
└── helpers/              # Mock clients, fixtures
```

## Configuration

Edit `config/config.yml`:

```yaml
database:
  type: sqlite
  url: data/gmail-assistant.db

llm:
  defaultProvider: anthropic
  models:
    classify: claude-3-haiku-20240307
    draft: claude-3-5-sonnet-20241022

gmail:
  syncIntervalMs: 900000  # 15 minutes

jobQueue:
  type: sqlite  # or 'bullmq'
  concurrency: 5
```

## API Endpoints

```bash
# Sync
POST /api/sync?user_id=1              # Trigger sync
POST /api/sync?full=true              # Full sync

# Emails
GET /api/users/{id}/emails            # List emails
GET /api/emails/{id}                  # Get email details
POST /api/emails/{id}/reclassify      # Reclassify email

# Webhooks
POST /webhook/gmail                   # Gmail Pub/Sub webhook

# Debug UI
GET /debug/emails                     # Email list view
GET /debug/jobs                       # Job queue view
```

## Troubleshooting

**Gmail authentication fails:**
```bash
bun run cli auth init  # Re-authenticate
```

**Drafts not created - check job queue:**
```bash
bun run cli jobs list
```

**Reset database:**
```bash
rm data/gmail-assistant.db
bun run db:push
bun run cli auth init
```

**Check LLM API connectivity:**
```bash
# View recent LLM calls
sqlite3 data/gmail-assistant.db "SELECT * FROM llm_calls ORDER BY created_at DESC LIMIT 10;"
```

## Deployment

### Environment Variables

```env
# LLM Provider (choose one)
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GOOGLE_AI_API_KEY=...

# Database
DATABASE_URL=data/gmail-assistant.db

# Job Queue
JOB_QUEUE_TYPE=sqlite  # or 'bullmq'

# Optional: Redis (if using BullMQ)
# REDIS_HOST=localhost
# REDIS_PORT=6379
```

### Production Checklist

- [ ] Configure LLM API keys
- [ ] Set up Gmail OAuth credentials
- [ ] Configure production database
- [ ] Set up job queue (BullMQ recommended)
- [ ] Configure Gmail Pub/Sub webhooks
- [ ] Set up monitoring/logging
- [ ] Configure SSL/TLS
- [ ] Set up backup strategy

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feat/amazing-feature`)
3. Commit changes using conventional commits
4. Open Pull Request

**Conventional Commits:**
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code refactoring

## License

MIT - see LICENSE file

## Links

- [Issues](https://github.com/landovsky/gmail-assistant/issues)
- [Discussions](https://github.com/landovsky/gmail-assistant/discussions)