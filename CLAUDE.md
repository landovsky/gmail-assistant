# Gmail Assistant v2 - Development Guide

## Project Overview

An AI-powered Gmail inbox management system that automatically classifies incoming emails, generates draft responses, and manages email workflows through Gmail labels. Built with Bun, Hono, Drizzle ORM, and Vercel AI SDK for model-agnostic LLM integration.

## Stack

- **Runtime**: Bun (JavaScript runtime, test runner, package manager)
- **Framework**: Hono (HTTP framework for REST API and webhooks)
- **UI**: Hono JSX (server-rendered debug/admin pages)
- **Database**: Drizzle ORM (SQLite + PostgreSQL support)
- **ORM/Migrations**: Drizzle Kit
- **Database UI**: Drizzle Studio
- **Validation**: Zod (API inputs, config, LLM responses)
- **LLM Integration**: Vercel AI SDK (multi-provider support: Claude, GPT, Gemini)
- **Gmail API**: googleapis (OAuth, Pub/Sub, Gmail operations)
- **Job Queue**: BullMQ (Redis) or SQLite-based (configurable)
- **CLI**: Commander
- **Config**: YAML + environment variables
- **Linter**: ESLint with TypeScript
- **Formatter**: Prettier

## Task Management

This project uses [beads](https://github.com/steveyegge/beads) for task tracking.
- Every task must be tracked: create → in progress → done, synced to git at each transition.
- Unrelated issues discovered during work get their own bead for later pickup.

## Git Workflow

- **Base branch**: main-js (NOT main)
- **Branch naming**: `<type>/<bead-id>-<short-description>` (e.g., `feat/workspace-1-bootstrap`, `fix/workspace-5-auth-bug`)
- **Types**: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`, `ci`
- **Commit frequently** - at minimum after every meaningful change. Use conventional commits.
- Always commit before switching tasks.

## Code Quality

- **Linter**: ESLint with TypeScript plugin
- **Formatter**: Prettier
- **Run before committing**:
  - `bun run lint` - Check for lint errors
  - `bun run format` - Format code
  - `bun test` - Run test suite

## Testing

- **Framework**: Bun's built-in test runner
- **Strategy**: TDD-style - tests alongside features
- **Coverage**: Unit, integration, and E2E tests
- **Run tests**: `bun test`
- **Watch mode**: `bun test --watch`

## Common Commands

```bash
# Development
bun run dev              # Start dev server with hot reload
bun run start            # Start production server

# Testing
bun test                 # Run all tests
bun test --watch         # Watch mode

# Code Quality
bun run lint             # Check linting
bun run format           # Format code
bun run format:check     # Check formatting

# Database
bun run db:generate      # Generate migrations
bun run db:migrate       # Run migrations
bun run db:push          # Push schema changes
bun run db:studio        # Open Drizzle Studio

# Beads (Task Management)
bd ready                 # Show available tasks
bd create --title="..." --type=task --priority=2
bd update <id> --status=in_progress
bd close <id>
bd sync                  # Sync with git
```

## Architecture

```
src/
├── api/           # Hono routes and handlers
├── db/            # Drizzle schema and migrations
├── services/      # Business logic (Gmail, LLM, classification, drafting)
├── jobs/          # Background job workers
├── lib/           # Shared utilities and config
└── cli/           # CLI commands

tests/
├── unit/          # Fast, isolated tests
├── integration/   # Database + service tests
└── e2e/           # Full workflow tests
```

## Environment Variables

Key environment variables (see `.env` for full list):
- `DATABASE_URL` - Database connection string
- `JOB_QUEUE_TYPE` - "sqlite" or "bullmq"
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_AI_API_KEY` - LLM providers
- `GOOGLE_CREDENTIALS_ENCRYPTED` - Encrypted Gmail OAuth credentials
- `PORT` - Server port (default: 3000)

## Artifacts Registry

This project maintains a registry of documentation artifacts at **`artifacts/registry.json`**.

### How to Use the Registry

**ALWAYS check `artifacts/registry.json` when:**
- Starting work on a new feature or bug fix
- Working with unfamiliar parts of the codebase
- Debugging code issues
- Writing or modifying code (frontend, backend, database, tests)
- Making architectural decisions

### Registry Structure

Each artifact entry contains:
```json
{
  "filename": "path/to/artifact.md",
  "description": "Brief description of what the artifact covers",
  "usage": "always" | "decide"
}
```

**Usage field:**
- **`always`** - Must be read before any work (e.g., project overview, core conventions)
- **`decide`** - Read when the artifact is relevant to your current task (e.g., testing conventions when writing tests, API patterns when building endpoints)

## Completeness Rules

**No placeholders.** Every committed handler, controller, or service must contain real logic — not stubs that log and return. If you can't implement something fully, flag it as blocked. Do not ship code that looks done but does nothing.

**When reporting task completion**, always state:
- What is **functional** (wired, tested, works end-to-end).
- What is **stubbed or incomplete** (and why).
- What is **blocked** (and on what).

"Tests pass" alone is not a quality signal. Tests can pass around empty code.

**Test the orchestration layer.** If handlers wire services together, test through the handler — not just the individual services in isolation. Testing leaves without testing the tree proves nothing about whether the system works.

## Team Coordination

- Workers use **feature branches**, not the main branch. Lead merges after review.
- Lead must **read key deliverable files** before merge — not just check test counts.
- Tasks should be **vertically sliced** (one feature end-to-end) rather than horizontally sliced (all handlers in one task, all services in another). Splitting a service from its caller across workers invites placeholders.
- After each merge round, the lead runs a **gap check** against the spec. This is a required step, not an afterthought.
