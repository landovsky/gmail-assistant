# Gmail Assistant

A self-hosted, AI-powered email inbox manager built on [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Gmail MCP](https://www.npmjs.com/package/@gongrzhe/server-gmail-autoauth-mcp). It classifies incoming email, generates draft replies, and surfaces everything through Gmail labels you can act on from your phone.

The system never sends or deletes email. It only reads, labels, and creates drafts.

## Table of contents

- [Use cases](#use-cases)
  - [Automatic inbox triage](#automatic-inbox-triage) — implemented
  - [Review and send an AI draft](#review-and-send-an-ai-draft) — implemented
  - [Revise a draft](#revise-a-draft) — implemented
  - [Manually request a draft](#manually-request-a-draft) — implemented
  - [Mark an email as done](#mark-an-email-as-done) — implemented
  - [Detect payment requests](#detect-payment-requests) — implemented
  - [Get a morning briefing](#get-a-morning-briefing) — planned
  - [Customize communication style](#customize-communication-style) — implemented
- [Setup](#setup)
- [Configuration](#configuration)
- [Commands reference](#commands-reference)
- [Architecture](#architecture)
- [Safety guarantees](#safety-guarantees)

## Use cases

### Automatic inbox triage
> **Status:** Implemented

Every 30 minutes (or on demand), the pipeline scans your inbox and classifies each email into one of five categories:

| Category | Label | Meaning |
|----------|-------|---------|
| Needs Response | `🤖 AI/Needs Response` | Someone is asking you a direct question or expects a reply |
| Action Required | `🤖 AI/Action Required` | You need to do something outside email (sign, approve, attend) |
| Payment Request | `🤖 AI/Payment Requests` | Contains a payment request or bill |
| FYI | `🤖 AI/FYI` | Notification, newsletter, no action needed |
| Waiting | `🤖 AI/Waiting` | You sent the last message, awaiting a reply |

When someone replies to a Waiting thread, the system detects the new message and re-triages it automatically.

```bash
bin/process-inbox triage    # run manually
bin/process-inbox all       # full pipeline (triage + draft)
```

### Review and send an AI draft
> **Status:** Implemented

After triage, the pipeline automatically writes reply drafts for all `Needs Response` emails. Drafts appear in your Gmail drafts folder with the `🤖 AI/Outbox` label.

1. Open a draft in Gmail (mobile or desktop)
2. Review the AI-generated reply
3. Edit if needed, then hit Send

The system detects when a draft disappears from your drafts folder and marks it as sent.

### Revise a draft
> **Status:** Implemented

When a draft isn't quite right:

1. Open the draft in Gmail — you'll see a `✂️` marker separating instructions from content
2. Type your feedback **above** the marker (e.g. "make it shorter", "more formal", "mention the Tuesday deadline")
3. Apply the `🤖 AI/Rework` label
4. Next run regenerates the draft incorporating your instructions

Up to 3 reworks per thread, then it moves to Action Required for you to handle manually.

```bash
bin/rework    # process pending rework requests
```

### Manually request a draft
> **Status:** Implemented

For emails the system didn't auto-classify as needing a response, or when you want to provide specific instructions upfront:

1. Open the email in Gmail and hit **Reply**
2. Write your notes for the AI (e.g. "politely decline, suggest next month instead")
3. Save the draft
4. Apply the `🤖 AI/Needs Response` label to the thread

The next pipeline run picks it up, reads your notes, and generates a full draft reply based on your instructions. The flow then continues as a normal [review](#review-and-send-an-ai-draft) or [rework](#revise-a-draft).

### Mark an email as done
> **Status:** Implemented

When you've dealt with an email (sent a reply, completed the action, paid the invoice):

1. Apply the `🤖 AI/Done` label in Gmail
2. Next cleanup run archives the thread — removes it from Inbox and strips all AI labels except Done

The `🤖 AI/Done` label is kept permanently as an audit trail marker.

```bash
bin/cleanup    # run cleanup manually
```

### Detect payment requests
> **Status:** Implemented

Emails containing payment requests, invoices, or billing statements are automatically detected during triage and labeled `🤖 AI/Payment Requests`. No further processing is done — the label surfaces them for your attention.

### Get a morning briefing
> **Status:** Planned

Create a summary of your inbox state: action queue, pending drafts, payment requests, and waiting threads.

### Customize communication style
> **Status:** Implemented

The system supports three built-in response styles — **formal**, **business** (default), and **informal**. Each has its own rules, sign-off, and example replies. Per-sender and per-domain overrides are configured in `config/contacts.yml`.

To refine styles from your own 60-day sent email history:

```bash
claude -p /update-style
```

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

Create these nested labels in Gmail (Settings > Labels > Create new):

```
🤖 AI
🤖 AI/Needs Response
🤖 AI/Outbox
🤖 AI/Rework
🤖 AI/Action Required
🤖 AI/Payment Requests
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
bin/process-inbox triage    # classify your inbox
bin/process-inbox all       # full pipeline
```

### 6. (Optional) Automate with launchd

```bash
# Edit the plist to match your paths
cp config/com.gmail-assistant.process-inbox.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gmail-assistant.process-inbox.plist
```

Runs the pipeline every 30 minutes. Logs go to `logs/`.

### Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) with an Anthropic API key
- A Google Cloud project with Gmail API enabled and OAuth credentials
- Node.js (for npx / Gmail MCP server)
- SQLite3 (pre-installed on macOS)
- macOS recommended (uses launchd for scheduling; adaptable to cron/systemd)

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

Defines three response styles — **formal**, **business** (default), **informal** — each with rules, sign-off, and examples.

## Commands reference

| Command | Script | Purpose |
|---------|--------|---------|
| `/inbox-triage` | `bin/process-inbox triage` | Classify new emails |
| `/draft-response` | `bin/process-inbox draft` | Generate reply drafts |
| `/cleanup` | `bin/cleanup` | Archive Done threads, detect sent drafts |
| `/rework-draft` | `bin/rework` | Process draft feedback |
| `/morning-briefing` | — | Generate HTML dashboard summary |
| `/update-style` | — | Learn communication patterns from sent mail |

### Logging

All scripts log to both stdout and `logs/<script-name>.log`. Set log verbosity with:

```bash
GMA_LOG_LEVEL=debug bin/process-inbox all    # debug, info (default), warn, error
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                 Background Processor                  │
│             (Claude Code custom commands)             │
│                                                      │
│  ┌──────────────────┐  ┌────────────────────────┐   │
│  │  Triage           │→│   Draft Responses       │   │
│  │  (Haiku)          │ │   (Sonnet)              │   │
│  └──────────────────┘  └────────────────────────┘   │
│       │                       │                      │
│       ▼                       ▼                      │
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
