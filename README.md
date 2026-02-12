# Gmail Assistant

A self-hosted, AI-powered email inbox manager built on [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Gmail MCP](https://www.npmjs.com/package/@gongrzhe/server-gmail-autoauth-mcp). It classifies incoming email, generates draft replies, extracts invoice data, and surfaces everything through Gmail labels you can act on from your phone.

```
New email → Triage (Haiku) → Draft reply (Sonnet) → You review on mobile → Done
```

The system never sends or deletes email. It only reads, labels, and creates drafts.

## How it works

Every 30 minutes (or on demand), a pipeline runs three steps:

| Step | Model | What it does |
|------|-------|-------------|
| **Triage** | Haiku | Classifies unread email into 5 categories |
| **Draft** | Sonnet | Writes reply drafts for emails that need a response |
| **Invoices** | Haiku | Extracts vendor, amount, due date from invoices |

Emails are tagged with nested Gmail labels under `🤖 AI/`:

| Label | Meaning |
|-------|---------|
| Needs Response | Someone is waiting for your reply |
| Action Required | You need to do something outside email |
| Invoice | Contains a payment request or bill |
| FYI | Notification, newsletter, no action needed |
| Waiting | You sent the last message, awaiting reply |
| Outbox | Draft is ready for your review |
| Rework | You asked for a draft revision |
| Done | You've handled it (permanent audit marker) |

### The rework loop

When you see a draft you don't like:

1. Open the draft in Gmail — you'll see a `✂️` marker
2. Type your feedback above the marker (e.g. "make it shorter", "add the deadline")
3. Apply the `🤖 AI/Rework` label
4. Next pipeline run regenerates the draft with your instructions

Up to 3 reworks per thread, then it moves to Action Required for you to handle manually.

## Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) with an Anthropic API key
- A Google Cloud project with Gmail API enabled and OAuth credentials
- Node.js (for npx / Gmail MCP server)
- SQLite3 (pre-installed on macOS)
- macOS recommended (uses launchd for scheduling; adaptable to cron/systemd)

## Setup

### 1. Clone and configure

```bash
git clone <repo-url> gmail-assistant
cd gmail-assistant

# Create config files from examples
cp config/label_ids.example.yml config/label_ids.yml
cp config/contacts.example.yml config/contacts.yml
cp config/communication_styles.example.yml config/communication_styles.yml
```

### 2. Set up Gmail OAuth

Follow the [Gmail MCP docs](https://www.npmjs.com/package/@gongrzhe/server-gmail-autoauth-mcp) to create OAuth credentials. Place them at:

```
~/.gmail-mcp/gcp-oauth.keys.json   # OAuth client ID/secret from Google Cloud
~/.gmail-mcp/credentials.json       # Generated on first auth (auto-created)
```

### 3. Create Gmail labels

Create these nested labels in Gmail (Settings → Labels → Create new):

```
🤖 AI
🤖 AI/Needs Response
🤖 AI/Outbox
🤖 AI/Rework
🤖 AI/Action Required
🤖 AI/Invoice
🤖 AI/FYI
🤖 AI/Waiting
🤖 AI/Done
```

Then find each label's ID (run `claude -p "list all gmail labels"` with the MCP configured) and put them in `config/label_ids.yml`.

### 4. Initialize the database

```bash
sqlite3 data/inbox.db < data/schema.sql
```

### 5. Test it

```bash
# Run just the triage step
bin/process-inbox triage

# Run the full pipeline
bin/process-inbox all
```

### 6. (Optional) Automate with launchd

```bash
# Edit the plist to match your paths
cp config/com.gmail-assistant.process-inbox.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gmail-assistant.process-inbox.plist
```

This runs the pipeline every 30 minutes. Logs go to `logs/`.

## Configuration

### `config/label_ids.yml`

Maps label names to Gmail label IDs. Required for the system to apply and read labels.

### `config/contacts.yml`

Per-sender overrides for communication style, language, and a blacklist:

```yaml
style_overrides:
  "vip-client@company.com": formal

domain_overrides:
  "*.gov.cz": formal

language_overrides:
  "english-speaker@abroad.com": en

blacklist:   # Always classified as FYI, never drafted
  - "*@noreply.github.com"
```

### `config/communication_styles.yml`

Defines three response styles — **formal**, **business** (default), **informal** — each with rules, sign-off, and examples. You can refine these from your own sent email history:

```bash
claude -p /update-style
```

## Commands

Run standalone or as part of the pipeline:

| Command | Script | Purpose |
|---------|--------|---------|
| `/inbox-triage` | `bin/process-inbox triage` | Classify new emails |
| `/draft-response` | `bin/process-inbox draft` | Generate reply drafts |
| `/process-invoices` | `bin/process-inbox invoices` | Extract invoice data |
| `/cleanup` | `bin/cleanup` | Archive Done threads, detect sent drafts |
| `/rework-draft` | `bin/rework` | Process draft feedback |
| `/morning-briefing` | — | Generate HTML dashboard summary |
| `/update-style` | — | Learn communication patterns from sent mail |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                 Background Processor                  │
│             (Claude Code custom commands)             │
│                                                      │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │  Triage   │→│   Draft     │→│ Invoice Processing│ │
│  │  (Haiku)  │ │  (Sonnet)   │ │     (Haiku)       │ │
│  └──────────┘  └────────────┘  └──────────────────┘ │
│       │              │                  │             │
│       ▼              ▼                  ▼             │
│  ┌──────────────────────────────────────────────────┐│
│  │             Local SQLite Database                 ││
│  └──────────────────────────────────────────────────┘│
│       │              │                               │
│       ▼              ▼                               │
│  ┌──────────┐  ┌────────────┐                       │
│  │  Gmail    │  │   Gmail     │                       │
│  │  Labels   │  │   Drafts    │                       │
│  └──────────┘  └────────────┘                       │
└──────────────────────────────────────────────────────┘
        │                │
        ▼                ▼
  ┌──────────┐    ┌──────────────┐
  │  Mobile   │    │   Desktop    │
  │  Gmail    │    │  Dashboard   │
  │ (labels)  │    │  (HTML file) │
  └──────────┘    └──────────────┘
```

Every action is logged to an `email_events` audit table. The `🤖 AI/Done` label is kept permanently as a processing marker and never removed.

## Safety guarantees

- **Never sends email** — only creates drafts for you to review and send
- **Never deletes email** — only labels and archives (removes from inbox)
- **Old drafts go to Trash** (recoverable 30 days), never permanently deleted
- **Full audit trail** in `email_events` table — every classification, draft, label change logged
- **Tool allowlisting** — each pipeline step runs with minimum required permissions

## License

MIT
