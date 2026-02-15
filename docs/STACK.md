# Technology Stack

## Web Framework
**Choice:** Ruby on Rails 8.1
**Reasoning:** Rails provides a mature, full-stack framework with excellent conventions for this type of system: REST API, background jobs via ActiveJob/Sidekiq, database migrations, model validations, and a built-in view layer for the debug/admin interfaces. The convention-over-configuration approach accelerates development of the 15+ API endpoints and 8 database tables. Rails generators reduce boilerplate for models, controllers, and migrations.
**Alternatives considered:** NestJS (good async but heavier setup for server-rendered views), Django (strong but less idiomatic for the real-time job processing pattern), Express (too minimal, would require assembling many pieces).

## Database
**Choice:** SQLite3 with WAL mode
**Reasoning:** The spec explicitly calls for SQLite as the default. WAL mode enables concurrent reads while maintaining write serialization, which is sufficient for a single-user or small-team system. Foreign keys are enforced at the database level. The simplicity of SQLite (no separate server process) fits the local development focus.
**Alternatives considered:** PostgreSQL (better for multi-tenant but overkill for local dev, spec says SQLite default).

## Background Jobs
**Choice:** Sidekiq 7 + Redis
**Reasoning:** The system has 7 job types requiring reliable async processing with retry logic. Sidekiq provides battle-tested job processing with configurable retry, concurrency control, and a built-in web dashboard. It integrates natively with Rails via ActiveJob. The spec requires atomic job claiming and concurrent worker pools - Sidekiq handles both via Redis-based queue primitives.
**Alternatives considered:** GoodJob (SQLite-compatible but less mature), Solid Queue (Rails 8 default but less feature-rich for complex retry patterns).

## Testing
**Choice:** RSpec 7 + FactoryBot + WebMock
**Reasoning:** RSpec provides expressive test syntax ideal for the complex business logic (classification rules, state machine transitions, agent tool loops). FactoryBot enables clean test data setup for the 8-table data model. WebMock stubs external API calls (Gmail API, LiteLLM) for deterministic tests. The spec requires testing at the orchestration layer - RSpec's shared contexts and let blocks support this well.
**Alternatives considered:** Minitest (simpler but less expressive for complex domain testing).

## Gmail Integration
**Choice:** google-apis-gmail_v1 gem + googleauth
**Reasoning:** Official Google-maintained Ruby gems for Gmail API access. Handles OAuth token refresh, request retry, and all Gmail API operations (messages, labels, drafts, history, watch). Directly maps to the spec's Gmail integration requirements.
**Alternatives considered:** Raw HTTP (would require reimplementing OAuth flow, pagination, retry logic).

## LLM Integration
**Choice:** HTTParty + LiteLLM gateway
**Reasoning:** The spec uses LiteLLM as a unified gateway to 100+ LLM providers. HTTParty provides a clean HTTP client for making API calls to the LiteLLM server. This keeps the Rails app decoupled from any specific LLM provider - model switching is a configuration change, not a code change.
**Alternatives considered:** ruby-openai gem (ties to OpenAI-specific API format, less flexible).

## Linting
**Choice:** RuboCop with rubocop-rails, rubocop-rspec, rubocop-performance
**Reasoning:** Standard Ruby/Rails linting tool. The Rails-specific rules catch common mistakes (N+1 queries, skipped validations). RSpec rules enforce consistent test patterns. Performance rules catch common bottlenecks.
**Alternatives considered:** Standard (less configurable, no Rails-specific rules).

## Asset Pipeline
**Choice:** Propshaft + Importmap
**Reasoning:** Rails 8 defaults. Propshaft is simpler than Sprockets for serving CSS/JS. Importmap eliminates the need for a JavaScript build step (webpack/esbuild), which is appropriate since the debug UI uses minimal JS (expand/collapse, API calls). No complex frontend framework needed.
**Alternatives considered:** esbuild (overkill for the simple JS requirements of the debug interface).

## Configuration
**Choice:** dotenv-rails + YAML config files
**Reasoning:** The spec requires YAML base config with environment variable overrides (GMA_* prefix). dotenv-rails loads .env files in development, and Rails' built-in YAML loading handles the config files. This matches the spec's configuration hierarchy exactly.
**Alternatives considered:** Rails credentials (encrypted, harder to work with for development).
