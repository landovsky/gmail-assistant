# CLAUDE.md

## Project Overview

Gmail Assistant v2 is an AI-powered Gmail inbox management system that automatically classifies incoming emails into five categories (needs_response, action_required, payment_request, fyi, waiting), generates draft responses using LLM, and manages email workflows through Gmail labels. It features a two-tier classification system (rule-based + LLM), a rework loop for draft refinement, an agent framework for autonomous email handling, and browser-based debug/admin interfaces.

## Stack

- Ruby 3.4 / Rails 8.1
- SQLite3 with WAL mode (concurrent reads)
- Sidekiq 7 + Redis for background job processing
- RSpec 7 for testing
- Google APIs Gmail v1 gem for Gmail integration
- HTTParty for LiteLLM gateway communication
- Propshaft for assets
- Importmap for JavaScript

## Task Management

This project uses [beads](https://github.com/steveyegge/beads) for task tracking.
- Every task must be tracked: create -> in progress -> done, synced to git at each transition.
- Unrelated issues discovered during work get their own bead for later pickup.

## Git Workflow

- Branch naming: `<type>/<bead-id>-<short-description>` (e.g., `feat/3kd99-basic-auth`, `fix/7xm22-null-avatar`)
- Types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`
- Commit frequently - at minimum after every meaningful change. Use conventional commits.
- Always commit before switching tasks.
- Workers use feature branches. Lead merges after review.

## Code Quality

- Linter: RuboCop with rubocop-rails, rubocop-rspec, rubocop-performance
- Run `bundle exec rubocop` before committing
- Run `bundle exec rspec` before pushing

## Testing

- Framework: RSpec 7
- Factories: FactoryBot
- HTTP mocking: WebMock + VCR
- Database cleanup: DatabaseCleaner
- Strategy: Test orchestration layers (controllers/services), not just leaf nodes
- Run: `bundle exec rspec`

## Common Commands

```bash
# Start dev server
bin/rails server

# Start Sidekiq worker
bundle exec sidekiq

# Run tests
bundle exec rspec

# Run linter
bundle exec rubocop

# Auto-fix lint issues
bundle exec rubocop -a

# Database operations
bin/rails db:migrate
bin/rails db:seed
bin/rails db:reset

# Rails console
bin/rails console

# Generate model
bin/rails generate model ModelName field:type

# Generate controller
bin/rails generate controller ControllerName action1 action2
```

## Architecture

```
app/
  controllers/
    api/           # REST API endpoints (JSON)
    debug/         # Debug HTML interface controllers
    webhook/       # Gmail Pub/Sub webhook handler
  models/          # ActiveRecord models (User, Email, Job, etc.)
  services/        # Business logic services
    gmail/         # Gmail API wrapper services
    classification/ # Two-tier classification engine
    drafting/      # Draft generation and rework
    agents/        # Agent framework (loop, tools, profiles)
    sync/          # Gmail sync engine
  jobs/            # Sidekiq background jobs
  views/
    debug/         # Debug interface HTML templates
    layouts/       # Application layouts
config/
  app.yml          # Application configuration
  prompts/         # LLM prompt templates
  routes.rb        # URL routing
lib/
  tasks/           # Rake tasks (CLI tools)
spec/              # RSpec test suite
```

## Key Domain Concepts

- **Two-tier classification**: Rules engine (Tier 1) catches automated emails, LLM (Tier 2) classifies the rest
- **Email lifecycle**: pending -> drafted -> sent/archived (state machine with Gmail label management)
- **Rework loop**: Users provide feedback via Gmail labels, system regenerates drafts (max 3 iterations)
- **Agent framework**: Tool-use LLM loop for domain-specific email handling (e.g., pharmacy support)
- **Routing**: Rules-based routing decides pipeline vs agent processing per email

## Environment Variables

See `.env.example` for all configurable values. Key ones:
- `GMA_LLM_CLASSIFY_MODEL` - Model for classification (default: gemini/gemini-2.0-flash)
- `GMA_LLM_DRAFT_MODEL` - Model for drafts (default: gemini/gemini-2.5-pro)
- `GMA_AUTH_CREDENTIALS_FILE` - Path to Google OAuth credentials
- `GMA_SERVER_ADMIN_USER` / `GMA_SERVER_ADMIN_PASSWORD` - Basic auth (optional)
- `LITELLM_BASE_URL` - LiteLLM gateway URL
