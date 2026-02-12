# Phase B: Classify New Emails

Classification of unprocessed emails from the past 30 days into actionable categories.

## Purpose

Phase B processes all unclassified emails in your inbox (emails without any `🤖 AI/*` labels) and assigns them to one of five categories:

- **needs_response**: Direct question or request that requires your reply
- **action_required**: Task outside email (sign, approve, attend meeting, etc.)
- **payment_request**: Invoice, billing statement, or payment request
- **fyi**: Notification, newsletter, automated message, or CC where not directly addressed
- **waiting**: Thread where you sent the last message and are awaiting a reply

## How It Works

### 1. Search

Searches Gmail for unclassified emails from the past 30 days:

```
in:inbox newer_than:30d \
  -label:🤖\ AI/Needs\ Response \
  -label:🤖\ AI/Outbox \
  -label:🤖\ AI/Rework \
  -label:🤖\ AI/Action\ Required \
  -label:🤖\ AI/Payment\ Requests \
  -label:🤖\ AI/FYI \
  -label:🤖\ AI/Waiting \
  -label:🤖\ AI/Done \
  -in:trash -in:spam
```

### 2. Read & Analyze

For each email:
- Read the full email content
- If thread has multiple messages, read up to 3 most recent for context
- Check sender against blacklist patterns

### 3. Classify

Classification is determined by content analysis:

| Signal | Category |
|--------|----------|
| Question mark `?`, "can you", "could you" | **needs_response** |
| "please sign/approve/confirm", "signature required" | **action_required** |
| "invoice", "faktura", "payment", "due date", currency symbols | **payment_request** |
| "newsletter", "automated", "no-reply", "notification" | **fyi** |
| You sent last message, awaiting reply | **waiting** |
| Sender matches blacklist pattern | **fyi** (forced) |

### 4. Store & Label

For each classified email:
1. Store classification in local database (`data/inbox.db`)
2. Apply corresponding Gmail label:
   - `🤖 AI/Needs Response` (Label_34)
   - `🤖 AI/Action Required` (Label_37)
   - `🤖 AI/Payment Requests` (Label_38)
   - `🤖 AI/FYI` (Label_39)
   - `🤖 AI/Waiting` (Label_40)
3. Log event to audit trail

### 5. Style Determination

For `needs_response` emails, determines communication style based on:

**Domain overrides** (from `config/contacts.yml`):
```yaml
domain_overrides:
  "*.gov.cz": formal
  "*.edu.cz": formal
```

**Default**: `business`

## Usage

### Run with Full Pipeline

```bash
./bin/process-inbox all
```

Runs all phases:
1. Phase A: Cleanup & Lifecycle
2. Phase B: Classify New Emails
3. Draft Responses

### Run Phase B Only

```bash
./bin/classify-phase-b
```

Or via Claude Code:

```bash
claude -p /phase-b-classify
```

### Customize Search

Override the default 30-day window:

```bash
# Last 7 days only
GMAIL_NEWER_THAN="7d" ./bin/classify-phase-b

# All emails (no time limit)
GMAIL_NEWER_THAN="1970-01-01" ./bin/classify-phase-b
```

## Database Schema

Emails are stored in `data/inbox.db`:

```sql
CREATE TABLE emails (
    id INTEGER PRIMARY KEY,
    gmail_thread_id TEXT UNIQUE,
    gmail_message_id TEXT,
    sender_email TEXT,
    sender_name TEXT,
    subject TEXT,
    snippet TEXT,
    received_at DATETIME,
    classification TEXT,  -- 'needs_response' | 'action_required' | 'payment_request' | 'fyi' | 'waiting'
    confidence TEXT,      -- 'high' | 'medium' | 'low'
    reasoning TEXT,
    detected_language TEXT,
    resolved_style TEXT,  -- 'business' | 'formal' | 'informal'
    message_count INTEGER,
    status TEXT,          -- 'pending' | 'drafted' | 'sent' | 'archived'
    processed_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE email_events (
    id INTEGER PRIMARY KEY,
    gmail_thread_id TEXT,
    event_type TEXT,  -- 'classified' | 'label_added' | 'label_removed' | 'draft_created' | 'sent_detected' | 'archived'
    detail TEXT,
    created_at DATETIME
);
```

## Blacklist

Emails from blacklisted senders are automatically classified as FYI and never get a response.

**Configuration** (`config/contacts.yml`):

```yaml
blacklist:
  - "visitor*.messages@email.dostupnost-leku.cz"
  - "*@noreply.github.com"
  - "*@notifications.google.com"
```

Patterns support glob syntax:
- `*` matches any characters
- `?` matches single character
- Matching is case-insensitive

## Classification Examples

### needs_response

```
From: alice@company.com
Subject: Question about project timeline
Body: Hi, can you confirm the project deadline for next week?
      What's your availability?
```

→ Classified as **needs_response** (questions, "can you")

### action_required

```
From: legal@company.com
Subject: Document requires your signature
Body: Please sign the attached contract and return by Friday.
```

→ Classified as **action_required** ("please sign")

### payment_request

```
From: vendor@supplier.com
Subject: Invoice #12345
Body: Amount due: 50,000 CZK
      Due date: 2026-02-28
```

→ Classified as **payment_request** (invoice, amount, due date)

### fyi

```
From: noreply@github.com
Subject: Your workflow completed
Body: Automated message: workflow build-tests completed successfully
```

→ Classified as **fyi** (automated, no-reply)

### waiting

```
From: boss@company.com
Subject: RE: Project Status
Body: (This is your email - you sent the last message)
```

→ Classified as **waiting** (you sent last message)

## Confidence Levels

- **high**: Clear signals, high certainty
- **medium**: Some ambiguity but reasonable classification
- **low**: Uncertain classification, defaulted to safe option (FYI)

## Performance

- **Speed**: ~1-2 seconds per email (with Gmail MCP tools)
- **Batch**: Processes up to 20 emails per run
- **Timeout**: 5 minutes per batch

## Troubleshooting

### "No unclassified emails found"

This is normal if:
1. All emails in the past 30 days already have labels
2. Inbox is empty
3. Time window is too small

To verify: `sqlite3 data/inbox.db "SELECT COUNT(*) FROM emails WHERE classification IS NOT NULL;"`

### Misclassifications

If an email is classified incorrectly:

1. **Open** the email in Gmail
2. **Apply correct label** manually (e.g., drag to "🤖 AI/Needs Response")
3. **Phase B skips** emails that already have labels

The classification rules can be improved by:
- Adding patterns to `config/contacts.yml` blacklist
- Modifying domain_overrides for sender styles
- Updating classification logic in `bin/classify-phase-b`

### Gmail Search Issues

If Gmail search isn't working:

```bash
# Check MCP configuration
cat .mcp.json

# Verify Gmail credentials
ls ~/.gmail-mcp/

# Check Gmail API access
claude --model haiku -p /test
```

## Integration with Other Phases

**Phase B depends on:**
- Phase A completion (cleanup, sent detection, waiting re-triage)
- `config/contacts.yml` (blacklist, style overrides)
- `data/inbox.db` schema (for storage)

**Phase B enables:**
- Phase C: Draft Responses (needs classified emails to draft)

## Notes

- **Blacklist**: Once blacklisted, future emails from sender always get FYI (no drafts)
- **Labels**: Gmail labels are per-message, not per-thread. Phase B labels the specific message
- **Database**: Classification is stored permanently in local DB for audit and analysis
- **Re-running**: Emails already in DB aren't re-processed (checked by `gmail_thread_id`)

## Return Value

Returns JSON summary:

```json
{
  "processed": 12,
  "needs_response": 3,
  "action_required": 2,
  "payment_request": 1,
  "fyi": 6,
  "waiting": 0
}
```
