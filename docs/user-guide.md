# User Guide

Gmail Assistant is a self-hosted, AI-powered email inbox manager. It classifies incoming email, generates draft replies, and surfaces everything through Gmail labels you can act on from your phone.

The system never sends or deletes email. It only reads, labels, and creates drafts.

## Table of contents

- [Use cases](#use-cases)
  - [Automatic inbox triage](#automatic-inbox-triage) — implemented
  - [Review and send an AI draft](#review-and-send-an-ai-draft) — implemented
  - [Revise a draft](#revise-a-draft) — implemented
  - [Manually request a draft](#manually-request-a-draft) — implemented
  - [Mark an email as done](#mark-an-email-as-done) — implemented
  - [Detect payment requests](#detect-payment-requests) — implemented
  - [Agent-based email processing](#agent-based-email-processing) — implemented (stub tools)
  - [Waiting thread re-triage](#waiting-thread-re-triage) — not yet implemented
  - [Get an inbox briefing](#get-an-inbox-briefing) — implemented
  - [Customize communication style](#customize-communication-style) — implemented
- [Gmail labels](#gmail-labels)
- [Safety guarantees](#safety-guarantees)

## Use cases

### Automatic inbox triage
> **Status:** Implemented

When new email arrives (via Gmail push notification, or every 15 minutes as a fallback), the system classifies it into one of five categories:

| Category | Label | Meaning |
|----------|-------|---------|
| Needs Response | `🤖 AI/Needs Response` | Someone is asking you a direct question or expects a reply |
| Action Required | `🤖 AI/Action Required` | You need to do something outside email (sign, approve, attend) |
| Payment Request | `🤖 AI/Payment Request` | Contains a payment request or bill |
| FYI | `🤖 AI/FYI` | Notification, newsletter, no action needed |
| Waiting | `🤖 AI/Waiting` | You sent the last message, awaiting a reply |

Classification uses a two-tier approach: fast rule-based matching first (blacklists, known automated senders, keyword patterns), then LLM for anything ambiguous.

### Review and send an AI draft
> **Status:** Implemented

After classification, the system automatically writes reply drafts for all `Needs Response` emails. Drafts appear in your Gmail drafts folder with the `🤖 AI/Outbox` label.

1. Open a draft in Gmail (mobile or desktop)
2. Review the AI-generated reply
3. Edit if needed, then hit Send

The system detects when a draft disappears from your drafts folder and marks the thread as sent.

### Revise a draft
> **Status:** Implemented

When a draft isn't quite right:

1. Open the draft in Gmail — you'll see a `✂️` marker separating instructions from content
2. Type your feedback **above** the marker (e.g. "make it shorter", "more formal", "mention the Tuesday deadline")
3. Apply the `🤖 AI/Rework` label
4. The system regenerates the draft incorporating your instructions

Up to 3 reworks per thread, then it moves to Action Required for you to handle manually.

### Manually request a draft
> **Status:** Implemented

For emails the system didn't auto-classify as needing a response, or when you want to provide specific instructions upfront:

1. Open the email in Gmail and hit **Reply**
2. Write your notes for the AI (e.g. "politely decline, suggest next month instead")
3. Save the draft
4. Apply the `🤖 AI/Needs Response` label to the thread

The system picks it up, reads your notes, and generates a full draft reply based on your instructions. The flow then continues as a normal [review](#review-and-send-an-ai-draft) or [rework](#revise-a-draft).

### Mark an email as done
> **Status:** Implemented

When you've dealt with an email (sent a reply, completed the action, paid the invoice):

1. Apply the `🤖 AI/Done` label in Gmail
2. The system archives the thread — removes it from Inbox and strips all AI labels except Done

The `🤖 AI/Done` label is kept permanently as an audit trail marker.

### Detect payment requests
> **Status:** Implemented

Emails classified as `Payment Request` are labeled for easy tracking. The classification picks up invoices, bills, payment reminders, and similar.

### Agent-based email processing
> **Status:** Implemented (stub tools — real API integration pending)

Some emails need more than classification and a draft — they need an AI agent that can look up information, take actions, and compose responses autonomously. The agent architecture supports this via config-driven routing rules.

**How it works:**

1. When a new email arrives, the system checks routing rules in `config/app.yml`
2. Emails matching an agent rule (e.g., forwarded from a specific address) are routed to an agent instead of the standard classify→draft pipeline
3. The agent runs a tool-use loop: it reads the email, decides what tools to use (search, reserve, reply, escalate), executes them, and repeats until done
4. All agent actions are logged to the `agent_runs` table for full audit

**Current agent profile:** Pharmacy support (dostupnost-leku.cz)
- Handles drug availability queries forwarded from the Crisp helpdesk
- Tools: `search_drugs`, `manage_reservation`, `web_search`, `send_reply`, `create_draft`, `escalate`
- All tools are currently stubbed with mock responses — real API integration comes later

**Adding a new agent profile:**

1. Create a system prompt in `config/prompts/`
2. Implement tools in `src/agent/tools/`
3. Add a routing rule and agent profile to `config/app.yml`

**Routing rule example** (`config/app.yml`):
```yaml
routing:
  rules:
    - name: pharmacy_support
      match:
        forwarded_from: "info@dostupnost-leku.cz"
      route: agent
      profile: pharmacy
    - name: default
      match:
        all: true
      route: pipeline
```

### Waiting thread re-triage
> **Status:** Not yet implemented

When someone replies to a thread you're waiting on, the system should detect the new message, remove the Waiting label, and re-classify it. The lifecycle handler exists but is not yet wired into the sync pipeline.

### Get an inbox briefing
> **Status:** Implemented

A JSON API endpoint summarizes your inbox state: action queue, pending drafts, and active items per category.

```
GET /api/briefing/{your-email}
```

Returns classification counts, active items per category, and pending draft count.

### Customize communication style
> **Status:** Implemented

The system supports three built-in response styles — **formal**, **business** (default), and **informal**. Each has its own rules, sign-off, and example replies.

Per-sender and per-domain overrides are configured in `config/contacts.yml`:

```yaml
style_overrides:
  "vip@company.com": formal

domain_overrides:
  "*.gov.cz": formal

blacklist:   # Always classified as FYI, never drafted
  - "*@noreply.github.com"
```

## Gmail labels

The system uses these nested labels in Gmail:

```
🤖 AI
🤖 AI/Needs Response
🤖 AI/Outbox
🤖 AI/Rework
🤖 AI/Action Required
🤖 AI/Payment Request
🤖 AI/FYI
🤖 AI/Waiting
🤖 AI/Done
```

Label lifecycle:

- `Needs Response` → draft created → `Outbox` → user sends → detected → archived
- `Outbox` + user adds feedback + `Rework` → regenerated → `Outbox` (max 3 reworks)
- Any label + `Done` → archived, all AI labels stripped except Done

## Safety guarantees

- **Never sends email** — only creates drafts for you to review and send
- **Never deletes email** — only labels and archives (removes from inbox)
- **Old drafts go to Trash** (recoverable 30 days), never permanently deleted
- **Full audit trail** — every classification, draft, and label change logged to the `email_events` table
