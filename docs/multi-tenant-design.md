# Multi-Tenant Architecture: Google Workspace Deployment

What would need to change to deploy this Gmail assistant to an organisation with Google Workspace.

## 1. Authentication — the biggest shift

**Current**: Single OAuth token in a flat file, one MCP server process.

**Multi-tenant options**:

- **Google Workspace domain-wide delegation** — A service account authorized by the Workspace admin can impersonate any user in the org. No per-user OAuth consent flow needed. You'd call Gmail API with `subject=user@org.com` for each user.
- **Per-user OAuth with consent** — Each user goes through an OAuth flow once. Tokens stored in a database (encrypted), refreshed automatically. More flexible but requires a consent UI.

Domain-wide delegation is the natural fit for "deploy to an org" since the admin authorizes once.

## 2. Data model — tenant scoping everywhere

**Current**: No `user_id` column anywhere. Single SQLite file.

**Changes**:
- Add `user_email` (or `user_id`) column to both `emails` and `email_events` tables
- **Every query** gets a `WHERE user_email = ?` clause — this is non-negotiable for data isolation
- Move from SQLite to PostgreSQL (or similar) — SQLite doesn't handle concurrent writes from multiple users well
- Consider row-level security in Postgres for defense-in-depth

## 3. Configuration — per-user vs org-wide

Three tiers of config emerge:

| Tier | Example | Storage |
|------|---------|---------|
| **Org-wide** | Label naming scheme, enabled features | Single config / env vars |
| **Per-user customizable** | Communication styles, sign-off name, contacts | DB table `user_settings` |
| **Per-user generated** | Gmail label IDs (differ per account) | DB table `user_labels` |

**Current hardcoded items that become per-user**:
- `config/label_ids.yml` — label IDs are unique per Gmail account, must be created and stored per user (via `get_or_create_label` on first run)
- `config/communication_styles.yml` — sign-off name becomes a user setting
- `config/contacts.yml` — personal contacts/overrides, per-user

## 4. Execution model — from CLI to service

**Current**: Claude Code commands run interactively, one user at a time.

**Multi-tenant**: You need a **service** that processes users in a loop/queue:

- **Scheduler** (cron / Cloud Scheduler) triggers processing
- **Worker** iterates over active users, impersonating each via the service account
- Each user's processing is isolated — their own label IDs, styles, DB rows
- The Gmail MCP server abstraction goes away — you'd call the Gmail API directly (via a Python/Node SDK) since MCP is designed for single-user interactive use

This is the most fundamental architectural change: **MCP is a single-user, interactive protocol**. Multi-tenant means switching to direct API calls.

## 5. The AI layer

**Current**: Claude Code commands with model routing (Haiku for triage, Sonnet for drafts).

**Multi-tenant**: The classification and drafting logic becomes API calls to Claude:

- Extract the prompt templates from `.claude/commands/*.md` into application code
- Call the Anthropic API directly with the appropriate model
- Per-user context (style, contacts, language) injected into prompts at runtime
- Consider batching — triage many users' emails in parallel with async API calls

## 6. Label management

**Current**: Labels created once manually, IDs stored in YAML.

**Multi-tenant**: On user onboarding:
1. Use Gmail API (as impersonated user) to `get_or_create_label` for each AI label
2. Store the resulting label IDs in `user_labels` table
3. Reference these IDs whenever processing that user's mail

## 7. Security & isolation

New concerns:
- **Token storage**: Encrypted at rest, scoped access
- **Data isolation**: Users must never see each other's emails (row-level security, query scoping)
- **Rate limiting**: Gmail API quotas are per-user but also per-project — need to respect both
- **Audit**: The `email_events` table already exists, just needs user scoping
- **Admin console**: Workspace admin needs visibility into what the system is doing across users

## 8. Deployment topology

```
┌─────────────────────────────────────────────┐
│  Google Workspace Admin                      │
│  (authorizes domain-wide delegation)         │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  Gmail Assistant Service                     │
│  ┌────────────┐  ┌────────────────────────┐ │
│  │ Scheduler   │  │ User Registry          │ │
│  │ (cron/queue)│  │ (settings, labels,     │ │
│  └─────┬──────┘  │  tokens, contacts)      │ │
│        │         └────────────────────────┘ │
│  ┌─────▼──────────────────────────────────┐ │
│  │ Worker Pool                             │ │
│  │  ├─ For each user:                      │ │
│  │  │   1. Impersonate via service account │ │
│  │  │   2. Triage (Claude API - Haiku)     │ │
│  │  │   3. Draft  (Claude API - Sonnet)    │ │
│  │  │   4. Store results in Postgres       │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │ PostgreSQL                              │ │
│  │  emails (user_email, ...)               │ │
│  │  email_events (user_email, ...)         │ │
│  │  user_settings (styles, contacts)       │ │
│  │  user_labels (gmail label IDs)          │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## 9. Summary of effort

| Area | Effort | Why |
|------|--------|-----|
| Auth (service account + impersonation) | High | Completely new auth model |
| Replace MCP with direct Gmail API | High | Core integration rewrite |
| Replace Claude Code commands with API calls | High | Extract prompts, build orchestration |
| DB schema + migration to Postgres | Medium | Add user scoping, switch engine |
| Per-user config/settings | Medium | New tables, onboarding flow |
| Label provisioning | Low | Already have `get_or_create_label` pattern |
| Audit trail | Low | Already exists, just add user column |

## Core insight

The current system is a personal CLI tool that leverages Claude Code + MCP as its runtime. Multi-tenant means building an actual **application** — the prompt logic and workflow design carry over nicely, but the execution substrate changes completely from "Claude Code commands" to "a service calling Gmail API + Claude API directly."
