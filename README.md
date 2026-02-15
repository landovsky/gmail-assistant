# Gmail Assistant v2

An AI-powered Gmail inbox management system that automatically classifies your emails, generates draft responses, and helps you stay on top of your inbox.

## What It Does

Gmail Assistant monitors your inbox and automatically:

- **Classifies emails** into five categories:
  - 📝 **Needs Response** - Requires a reply (AI drafts one for you)
  - ⚡ **Action Required** - You need to do something (no draft needed)
  - 💰 **Payment Request** - Invoices and bills
  - 📄 **FYI** - Just informational, no action needed
  - ⏳ **Waiting** - You're waiting for someone else to respond

- **Generates draft replies** for emails that need responses, matching your communication style

- **Manages Gmail labels** to surface email state and guide your workflow

- **Learns from your feedback** with a rework loop - mark a draft for revision and the AI will regenerate it

- **Handles domain-specific emails** with the agent framework (e.g., pharmacy support, customer service)

## Prerequisites

- **Ruby 3.4+** and **Rails 8.1+**
- **Redis** (for background job processing)
- **LiteLLM gateway** running (for AI model access)
- **Google Cloud project** with Gmail API enabled
- **Gmail account** you want to manage

## Quick Start

### 1. Install Dependencies

```bash
# Install Ruby dependencies
bundle install

# Install and start Redis
# macOS:
brew install redis
brew services start redis

# Linux (Ubuntu/Debian):
sudo apt install redis-server
sudo systemctl start redis
```

### 2. Set Up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Gmail API**
4. Create OAuth 2.0 credentials:
   - Application type: **Desktop app**
   - Download the credentials JSON file
5. Save as `config/credentials.json`

### 3. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and set:
# - LITELLM_BASE_URL (your LiteLLM gateway URL)
# - GMA_AUTH_CREDENTIALS_FILE (path to credentials.json)
# - Model preferences (optional, defaults to Gemini)
```

### 4. Set Up Database

```bash
bin/rails db:migrate
```

### 5. Start the Application

Open two terminal windows:

```bash
# Terminal 1: Start the web server
bin/rails server

# Terminal 2: Start background workers
bundle exec sidekiq
```

### 6. Initialize Your Account

1. Open your browser to `http://localhost:3000`
2. You'll be redirected to Google OAuth consent screen
3. Authorize the application
4. The system will automatically:
   - Create your user account
   - Set up Gmail labels
   - Start syncing your inbox

## How to Use

### First Sync

After initialization, trigger your first inbox sync:

```bash
# Via API
curl -X POST http://localhost:3000/api/sync

# Or via rake task
bundle exec rake sync:full
```

### View Your Emails

**Debug Interface** (recommended for exploring):
- Visit `http://localhost:3000/debug/emails`
- Search, filter by status/classification
- View detailed debug info for each email

**REST API**:
```bash
# Get pending emails
curl http://localhost:3000/api/users/1/emails?status=pending

# Get inbox briefing
curl http://localhost:3000/api/briefing/your-email@gmail.com
```

### Managing Drafts

The AI creates drafts in your Gmail account. To manage them:

1. **Review drafts** in Gmail (look for emails with drafts)
2. **Send as-is** or **edit before sending**
3. **Request rework**: Add the "Rework" label in Gmail, the AI will regenerate (up to 3 times)
4. **Mark done**: Add the "Done" label to archive

### Communication Styles

Configure how the AI writes in your voice:

```bash
# Set your default style
curl -X PUT http://localhost:3000/api/users/1/settings \
  -H "Content-Type: application/json" \
  -d '{"key": "default_language", "value": "en"}'

# Configure styles per contact
curl -X PUT http://localhost:3000/api/users/1/settings \
  -H "Content-Type: application/json" \
  -d '{
    "key": "contacts",
    "value": {
      "boss@company.com": {"style": "formal"},
      "friend@example.com": {"style": "informal"}
    }
  }'
```

### Gmail Labels

The system creates and manages these labels automatically:

- **Needs Response** - Emails requiring a reply
- **Action Required** - Tasks you need to do
- **Payment Request** - Bills and invoices
- **FYI** - Informational only
- **Waiting** - Awaiting responses
- **Outbox** - Drafts ready to review
- **Rework** - Request draft regeneration
- **Done** - Processed/archived

## Advanced Features

### Agent Framework

For domain-specific automation (e.g., pharmacy support, customer service):

1. Configure routing rules in `config/app.yml`:

```yaml
routing:
  rules:
    - name: pharmacy_support
      match:
        forwarded_from: "info@pharmacy-system.com"
      route: agent
      profile: pharmacy

    - name: default
      match:
        all: true
      route: pipeline
```

2. Agents can use tools to:
   - Search external databases
   - Create reservations
   - Auto-send responses (for straightforward queries)
   - Escalate complex issues

### Push Notifications (Optional)

For real-time inbox monitoring:

1. Set up Google Cloud Pub/Sub
2. Configure webhook URL and topic in `.env`
3. Register watch:

```bash
curl -X POST http://localhost:3000/api/watch
```

## Useful Commands

```bash
# Sync inbox
bundle exec rake sync:full

# View statistics
bundle exec rake db_management:stats

# Test classification
bundle exec rake classification:test

# Reset and start fresh
bundle exec rake db_management:reset

# View debug info
bundle exec rake classification:debug[<email_id>]
```

## Monitoring & Debugging

### Check Job Status

```bash
# View Sidekiq dashboard
# Add 'sidekiq-web' to Gemfile and mount in routes.rb
```

### View Logs

```bash
# Application logs
tail -f log/development.log

# Check email processing
bin/rails console
> Email.last
> Email.find(123).email_events
> Email.find(123).llm_calls
```

### Debug Interface

Visit `http://localhost:3000/debug/emails` to:
- Search emails by content, sender, classification
- View full event timeline for each email
- See LLM prompts and responses
- Track token usage and costs

### Database Admin

Visit `http://localhost:3000/admin` to browse all database tables.

## Configuration Reference

All settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LITELLM_BASE_URL` | `http://localhost:4000` | LiteLLM gateway URL |
| `GMA_LLM_CLASSIFY_MODEL` | `gemini/gemini-2.0-flash` | Model for classification |
| `GMA_LLM_DRAFT_MODEL` | `gemini/gemini-2.5-pro` | Model for drafting |
| `GMA_AUTH_CREDENTIALS_FILE` | `config/credentials.json` | Google OAuth credentials |
| `GMA_SERVER_ADMIN_USER` | - | Basic auth username (optional) |
| `GMA_SERVER_ADMIN_PASSWORD` | - | Basic auth password (optional) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |

See `.env.example` for complete list.

## API Reference

Full REST API documentation: See `artifacts/specification/02-rest-api.md`

Quick examples:

```bash
# Health check
curl http://localhost:3000/api/health

# List users
curl http://localhost:3000/api/users

# Get emails
curl http://localhost:3000/api/users/1/emails?status=pending

# Trigger sync
curl -X POST http://localhost:3000/api/sync?user_id=1

# Reclassify email
curl -X POST http://localhost:3000/api/emails/123/reclassify

# Get inbox briefing
curl http://localhost:3000/api/briefing/your-email@gmail.com
```

## Troubleshooting

### Gmail OAuth Issues

**Problem**: "Error: credentials.json not found"
- **Solution**: Download credentials from Google Cloud Console and save to `config/credentials.json`

**Problem**: "Invalid grant" or "Token expired"
- **Solution**: Delete `config/token.json` and restart the server to re-authorize

### Sync Not Working

**Problem**: Inbox isn't syncing
- **Solution**: Check Sidekiq is running, verify Redis is up, check logs for errors

**Problem**: Jobs stuck in pending
- **Solution**: Restart Sidekiq, check for failed jobs in logs

### AI Not Generating Drafts

**Problem**: Classification works but no drafts
- **Solution**: Check LiteLLM is running, verify model is accessible, check `llm_calls` table for errors

**Problem**: Drafts are low quality
- **Solution**: Configure communication styles, provide examples via user settings

## Testing

```bash
# Run full test suite (350 tests)
bundle exec rspec

# Run specific tests
bundle exec rspec spec/models
bundle exec rspec spec/integration
bundle exec rspec spec/services

# Check code quality
bundle exec rubocop
```

## Architecture

For developers, see `CLAUDE.md` for:
- Project structure
- Code organization
- Testing strategy
- Development workflow

For system documentation, see `artifacts/specification/`:
- Data model and relationships
- Classification logic
- Draft generation
- Agent framework
- Background jobs
- Email lifecycle

## Security & Privacy

- **OAuth scope**: The app requests `gmail.modify` to read emails, create drafts, and manage labels
- **No email sending**: The system only creates drafts (you review and send manually)
- **Local storage**: All data stored locally in SQLite
- **Audit logging**: Every AI call and email action is logged
- **Basic auth**: Optional HTTP Basic Authentication for web interface

## Cost Considerations

LLM usage per email:
- **Classification**: ~100-200 tokens (< $0.001)
- **Draft generation**: ~500-1500 tokens (~$0.005-$0.015)
- **Rework**: Additional ~500-1500 tokens per iteration

Estimate: ~$0.02-$0.05 per email with drafting

## Support & Contributing

- **Issues**: Create beads for bugs/features: `bd create --title="..." --type=bug`
- **Documentation**: See `artifacts/specification/` for complete specs
- **Testing**: All contributions require tests (RSpec)

## License

[Your License Here]

## Credits

Built with:
- Rails 8.1
- Google Gmail API
- LiteLLM (unified LLM gateway)
- Sidekiq (background jobs)
- RSpec (testing)
