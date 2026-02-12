# Phase B: Classify New Emails

Classify unprocessed emails from the past 30 days into actionable categories.

## Overview

Searches Gmail for emails without AI labels and assigns each to one of five categories:
- `needs_response`: Direct question or request requiring reply
- `action_required`: Task outside email (sign, approve, attend meeting)
- `payment_request`: Invoice, billing, or payment request
- `fyi`: Notification, newsletter, automated, or CC'd
- `waiting`: You sent last message, awaiting reply

## Implementation Script

```bash
python3 bin/classify-phase-b
```

Or with custom time window:
```bash
GMAIL_NEWER_THAN="7d" python3 bin/classify-phase-b
```

## Gmail Search Query

Search for emails without any AI labels:

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

Use Gmail MCP tool `search_emails` with `maxResults: 20`.

## Processing Steps

For each unclassified email/thread:

1. **Read email** with `read_email` MCP tool
   - Get thread ID, message ID, sender, subject, snippet, body
   - If thread has multiple messages, read up to 3 most recent for context

2. **Check blacklist** from `config/contacts.yml`
   - If sender email matches any glob pattern in `blacklist` section
   - Force classify as `fyi` (no drafts for these senders)
   - Skip to step 4

3. **Classify based on content**
   - Analyze subject, snippet, and full body
   - Apply classification signals (see below)
   - Determine confidence level

4. **Determine communication style** (for needs_response only)
   - Check `config/contacts.yml` domain_overrides
   - Match sender's email domain against patterns
   - Default to `business`

5. **Apply Gmail label** via `modify_email`
   - Add appropriate label from table below

6. **Store in database**
   - INSERT OR REPLACE into `emails` table with classification

7. **Log event**
   - INSERT into `email_events` table for audit trail

## Classification Signals

Match signals in order of specificity:

### payment_request (high confidence)
- "invoice", "faktura", "payment", "billing", "due date"
- "amount due", "total", "please pay"
- Currency: CZK, EUR, USD, amount with currency symbol
- Any receipt or financial document

### action_required (high confidence)
- "please sign", "signature required", "please approve"
- "approval required", "please confirm"
- "action required", "needs your approval"
- Explicit request for action outside email

### fyi (high confidence)
- "newsletter", "automated message", "notification"
- "no-reply", "noreply", "unsubscribe"
- "system message", "alert", "reminder"
- No expectation of response

### needs_response (medium confidence)
- Direct question: "?" in content
- "can you", "could you", "would you"
- "what do you think", "your opinion"
- "please let me know", "please send"
- "check this", "review", "feedback"

### waiting (low confidence, requires context)
- Requires checking if you sent the last message
- Not automatically detected from content alone
- Usually set manually when sending your reply

### Default: fyi (when uncertain)
- Classify ambiguous emails as FYI
- Can be reclassified later by user

## Label IDs

Applied via `modify_email` with `addLabelIds`:

| Classification | Label ID |
|---|---|
| needs_response | Label_34 |
| action_required | Label_37 |
| payment_request | Label_38 |
| fyi | Label_39 |
| waiting | Label_40 |

## Database Storage

INSERT OR REPLACE into `emails`:

```sql
INSERT OR REPLACE INTO emails (
    gmail_thread_id,      -- Gmail thread ID
    gmail_message_id,     -- Gmail message ID
    sender_email,         -- Sender email address
    sender_name,          -- Sender display name
    subject,              -- Email subject
    snippet,              -- Email preview (first 100 chars)
    received_at,          -- Email date
    classification,       -- 'needs_response' | 'action_required' | 'payment_request' | 'fyi' | 'waiting'
    confidence,           -- 'high' | 'medium' | 'low'
    reasoning,            -- Description of why classified this way
    detected_language,    -- 'cs' or 'en' (auto-detected)
    resolved_style,       -- 'business' | 'formal' | 'informal'
    message_count,        -- Number of messages in thread
    status,               -- 'pending'
    processed_at,         -- CURRENT_TIMESTAMP
    updated_at            -- CURRENT_TIMESTAMP
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
```

## Audit Logging

Log each classification event:

```sql
INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES
    (?, 'classified', 'Phase B: <classification> (confidence=<level>)')
```

## Configuration

**Blacklist** (`config/contacts.yml`):
```yaml
blacklist:
  - "visitor*.messages@email.dostupnost-leku.cz"
  - "*@noreply.github.com"
  - "*@notifications.google.com"
```

**Domain styles** (`config/contacts.yml`):
```yaml
domain_overrides:
  "*.gov.cz": formal
  "*.mfcr.cz": formal
  "*.edu.cz": formal
```

## Output

Return JSON summary:

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

## Usage Examples

### Run as part of full pipeline
```bash
./bin/process-inbox all
```

### Run Phase B standalone
```bash
python3 bin/classify-phase-b
```

### Via Claude Code command
```bash
claude -p /phase-b-classify
```

## Related Documentation

- Full guide: `docs/PHASE-B-CLASSIFY.md`
- Inbox Triage spec: `.claude/commands/inbox-triage.md`
- Phase A (cleanup): `.claude/commands/cleanup.md`
- Phase C (drafting): `.claude/commands/draft-response.md`
