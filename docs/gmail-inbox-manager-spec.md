# Gmail Inbox Management System — Specification

## Overview

A self-hosted system that processes Gmail via MCP, classifies emails, generates draft responses, and surfaces actions through two interfaces: **Gmail labels** (mobile) and a **local HTML dashboard** (desktop). The processing pipeline runs as Claude Code custom commands using cost-appropriate models.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Background Processor                   │
│              (Claude Code custom commands)                │
│                                                          │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐ │
│  │  Triage   │→│   Draft     │→│   Invoice Processing  │ │
│  │  (Haiku)  │ │  (Sonnet)   │ │       (Haiku)         │ │
│  └──────────┘  └────────────┘  └──────────────────────┘ │
│       │              │                    │               │
│       ▼              ▼                    ▼               │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Local SQLite Database                   │ │
│  └─────────────────────────────────────────────────────┘ │
│       │              │                    │               │
│       ▼              ▼                    ▼               │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐ │
│  │  Gmail    │  │   Gmail     │  │    Fakturoid MCP     │ │
│  │  Labels   │  │   Drafts    │  │    (optional)        │ │
│  │  (MCP)    │  │   (MCP)     │  │                      │ │
│  └──────────┘  └────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────┘
        │                │
        ▼                ▼
  ┌──────────┐    ┌──────────────┐
  │  Mobile   │    │   Desktop    │
  │  Gmail    │    │  Dashboard   │
  │  (labels) │    │  (HTML file) │
  └──────────┘    └──────────────┘
```

---

## 1. Gmail Label System

All system-managed labels are nested under a `🤖 AI` parent label in Gmail's sidebar, using the `🤖 AI/` prefix to distinguish them from manual labels.

### Labels

| Label | Applied by | Meaning | User action |
|---|---|---|---|
| `🤖 AI/Needs Response` | Processor | Email requires a reply | Wait for draft, or rework |
| `🤖 AI/Outbox` | Processor | Draft reply is ready in the thread | Review draft, edit, send |
| `🤖 AI/Rework` | **User** | Draft needs revision (user added instructions) | Wait for regenerated draft |
| `🤖 AI/Action Required` | Processor | Non-email action needed (sign, pay, attend…) | Do the thing, then apply `🤖 AI/Done` |
| `🤖 AI/Invoice` | Processor | Unpaid invoice detected | Pay or forward to accountant |
| `🤖 AI/FYI` | Processor | Informational, no action needed | Skim or archive at will |
| `🤖 AI/Waiting` | Processor | Awaiting someone else's reply | System re-triages when reply arrives |
| `🤖 AI/Done` | **User** | Signals "I'm finished with this thread" | System archives, removes other `🤖 AI/*` labels, keeps Done as audit marker |

### Label Lifecycle

```
New email arrives
    │
    ▼
inbox-triage classifies
    │
    ├─→ 🤖 AI/FYI                          (terminal — user archives when ready)
    ├─→ 🤖 AI/Action Required              → user acts → 🤖 AI/Done → archived
    ├─→ 🤖 AI/Invoice                      → user pays → 🤖 AI/Done → archived
    ├─→ 🤖 AI/Waiting                      → reply arrives → reclassified
    └─→ 🤖 AI/Needs Response
            │
            ▼
        draft-response generates draft
            │
            ▼
        🤖 AI/Outbox
            │
            ├─→ User sends draft         → cleanup detects sent, removes label, DB → sent
            ├─→ User adds note, relabels → 🤖 AI/Rework → rework-draft
            │                                  │
            │                                  ▼
            │                              Regenerated draft → 🤖 AI/Outbox
            │                              (max 3 reworks, then → 🤖 AI/Action Required)
            └─→ User removes label        → interpreted as "skip, don't redraft"

🤖 AI/Done (user-applied on any thread)
    │
    ▼
Cleanup: remove all 🤖 AI/* labels EXCEPT Done, archive from INBOX, DB → archived
```

---

## 2. Rework Feedback Loop

### How it works

1. User sees a draft in `🤖 AI/Outbox` on mobile
2. User opens the draft and types instructions **at the top** of the draft body, above a `---✂---` marker line
3. User saves the draft and changes the label from `🤖 AI/Outbox` → `🤖 AI/Rework`
4. Next processor run picks up `🤖 AI/Rework` threads:
   - Reads the user's note (everything above the `---✂---` marker)
   - If the note references other emails (e.g. "see the April email"), searches Gmail via MCP for matching threads with that contact around the referenced time
   - Feeds the note + any retrieved context into `rework-draft` command
   - Deletes the old draft and creates a new one on the same thread (Gmail MCP has no draft update — delete + recreate is the pattern)
   - Moves label back to `🤖 AI/Outbox`
   - If this is the 3rd rework (max), adds a warning to the draft and moves to `🤖 AI/Action Required` instead

### Draft format

When the processor creates a draft, it inserts the marker:

```
---✂--- Your instructions above this line / Draft below ---✂---

Dobrý den paní Nováková,

děkuji za Vaši zprávu...
```

The user types above the marker on mobile:

```
We agreed on Thursday in the April email. Reference that.
---✂--- Your instructions above this line / Draft below ---✂---

Dobrý den paní Nováková,

děkuji za Vaši zprávu...
```

### Rework instruction examples

- `"softer tone, she's a friend"` → switches to informal style
- `"we discussed this in the April thread, reference that agreement"` → fetches April context
- `"say no politely, I don't have time"` → rewrites as a decline
- `"add that we can meet next Tuesday at 3pm"` → incorporates specific detail
- `"in English please"` → switches language

---

## 3. Communication Styles

### Style definitions

Styles live in a YAML config file within the project repository.

**File: `config/communication_styles.yml`**

```yaml
default: business

styles:
  formal:
    description: "Official correspondence — teachers, government, doctors, institutions"
    language: cs  # default to Czech unless incoming email is in another language
    rules:
      - Use formal address (vykání in Czech, standard formal English)
      - Full salutations and sign-offs
      - No contractions, no slang, no emoji
      - Reference specific documents, dates, or case numbers when available
      - Err on the side of politeness and completeness
    sign_off: "S pozdravem, Tomáš"
    examples:
      - context: "Responding to a teacher about a parent-teacher meeting"
        input: "Dobrý den, ráda bych s Vámi probrala prospěch Vašeho syna. Hodil by se Vám čtvrtek v 16:00?"
        draft: |
          Dobrý den paní Nováková,

          děkuji za Vaši zprávu. Termín schůzky ve čtvrtek 15. května v 16:00 mi vyhovuje.

          Těším se na setkání.

          S pozdravem,
          Tomáš
      - context: "Writing to a government office about a permit"
        input: "Vaše žádost č. 2025/1234 vyžaduje doplnění dokumentace."
        draft: |
          Dobrý den,

          děkuji za informaci k žádosti č. 2025/1234. Mohl byste prosím upřesnit, které dokumenty je potřeba doložit?

          Předem děkuji za odpověď.

          S pozdravem,
          Tomáš

  business:
    description: "Clients, partners, vendors, contractors, invoicing"
    language: auto  # match the language of the incoming email
    rules:
      - Professional but not stiff
      - Get to the point quickly
      - Use tykání if the other party initiated it, otherwise vykání
      - Include specific next steps, deadlines, or asks
      - Keep it concise — busy people appreciate brevity
    sign_off: "Díky, Tomáš"
    examples:
      - context: "Following up on an unpaid invoice"
        input: "(system-generated: invoice #2025-042, due 2025-02-10, amount 15,000 CZK, recipient: Petr)"
        draft: |
          Ahoj Petře,

          posílám připomínku k faktuře č. 2025-042 se splatností 10. 2. na 15 000 Kč.

          Dáš vědět, jestli je vše v pořádku?

          Díky,
          Tomáš
      - context: "Confirming a project deliverable"
        input: "Hi Tom, we've finished the first round of designs. Can you review by Friday?"
        draft: |
          Hi,

          Thanks, I'll review by Friday and send feedback over the weekend at the latest.

          Tom

  informal:
    description: "Friends, family, casual acquaintances"
    language: auto
    rules:
      - Casual, warm tone
      - Tykání always in Czech, first names in English
      - Short is fine — don't over-explain
      - Emoji OK if the sender uses them
      - Match the energy/length of the incoming message
    sign_off: "T."
    examples:
      - context: "Friend asking about weekend plans"
        input: "Čau, co děláš v sobotu? Nechceš vyrazit na kolo?"
        draft: |
          Čau, jasně, sobota funguje. Dej vědět kam a kdy.

          T.
      - context: "Family member sharing photos"
        input: "Koukni na fotky z dovolené! Bylo to super."
        draft: |
          Ty jo, to vypadá parádně! Kam přesně jste jeli?

          T.
```

### Style selection logic

The processor selects a style using the following priority (first match wins):

```
1. Rework instruction override
   └─ User explicitly wrote "use informal tone" in rework note

2. Contact-level override
   └─ Sender email matches an entry in config/contacts.yml

3. Domain-level override
   └─ Sender domain matches a pattern in config/contacts.yml

4. Thread history analysis
   └─ If previous messages in the thread use vykání → formal
   └─ If previous messages use tykání → business or informal

5. Default
   └─ Falls back to the `default` value in communication_styles.yml (business)
```

### Contact and domain overrides

**File: `config/contacts.yml`**

```yaml
# Specific email addresses
style_overrides:
  "novakova@zsskola.cz": formal
  "petr@hristehrou.cz": business
  "kamarad@gmail.com": informal
  "ucetni@firma.cz": business

# Domain patterns
domain_overrides:
  "*.gov.cz": formal
  "*.mfcr.cz": formal
  "*.edu.cz": formal
  "*.justice.cz": formal

# Language overrides (when auto-detection isn't enough)
language_overrides:
  "english-client@abroad.com": en
```

---

## 4. Processing Pipeline — Claude Code Commands

### Command structure

```
.claude/commands/
├── inbox-triage.md
├── draft-response.md
├── rework-draft.md
├── process-invoices.md
└── morning-briefing.md
```

### Model routing

| Command | Model | Estimated cost per run | Rationale |
|---|---|---|---|
| `inbox-triage` | Haiku | Very low | Classification is pattern-matching |
| `draft-response` | Sonnet | Low–moderate | Needs good writing quality |
| `rework-draft` | Sonnet | Low–moderate | Must understand nuanced feedback |
| `process-invoices` | Haiku | Very low | Structured data extraction |
| `morning-briefing` | Haiku | Very low | Summarization from structured data |

### Command: `inbox-triage.md`

```markdown
# Inbox Triage

Classify unprocessed emails, handle lifecycle transitions, and apply Gmail labels.

## Steps

### Phase A: Cleanup & lifecycle transitions

1. **🤖 AI/Done cleanup.** Search for threads with `🤖 AI/Done` label.
   For each: remove all `🤖 AI/*` labels EXCEPT `🤖 AI/Done` (keep it
   as a permanent audit marker), remove from INBOX (archive),
   update local DB status to `archived`. Log to `email_events`.

2. **Sent draft detection.** For threads with `🤖 AI/Outbox` label,
   check if the stored `draft_id` in the local DB still exists as a
   draft. If the draft was sent (no longer exists as draft, but a sent
   message exists in the thread), remove `🤖 AI/Outbox` label and update
   DB status to `sent`.

3. **🤖 AI/Waiting re-triage.** Search for threads with `🤖 AI/Waiting` label.
   For each, check if new inbound messages (not from me) have arrived
   since the label was applied. If yes, remove `🤖 AI/Waiting` and
   re-classify the thread in Phase B below.

### Phase B: Classify new emails

4. Use Gmail MCP to fetch emails that have no `🤖 AI/*` labels and are
   not in Trash or Spam. Include threads surfaced by Phase A step 3.
5. For each email thread, read the full thread content via Gmail MCP.
   (Note: `read_email` reads one message at a time — search for all
   messages in the thread and read each.)
6. Classify into exactly ONE category:

   - **needs_response** — Someone is asking me a direct question, requesting
     something, or the social context requires a reply
   - **action_required** — I need to do something outside of email
     (sign a document, attend a meeting, approve something)
   - **invoice** — Contains a payment request, invoice, or billing statement
   - **fyi** — Newsletter, notification, automated message, CC'd thread
     where I'm not directly addressed
   - **waiting** — I sent the last message in this thread and am awaiting a reply

7. Apply the corresponding `🤖 AI/*` label via Gmail MCP.
8. Store the classification in the local SQLite database at `data/inbox.db`:
   - gmail_thread_id, gmail_message_id, sender, subject
   - classification, confidence (high/medium/low), reasoning (one line)
   - detected_language, processed_at
9. For `needs_response` emails, also store:
   - resolved_style (using the style selection logic from config files)
   - Contact name and email for the draft-response command to pick up

## Classification signals

- Direct question addressed to me → needs_response
- "Please confirm / approve / sign" → action_required
- Attachment named *faktura*, *invoice*, amount + due date → invoice
- Automated sender, no-reply address, marketing → fyi
- I sent the last message, no new reply from others → waiting
- When uncertain between needs_response and fyi, prefer needs_response

## Output

Print a JSON summary:
{
  "processed": 12,
  "needs_response": 3,
  "action_required": 1,
  "invoice": 2,
  "fyi": 5,
  "waiting": 1,
  "archived": 2,
  "sent_detected": 1,
  "waiting_retriaged": 0
}
```

### Command: `draft-response.md`

```markdown
# Draft Response

Generate email reply drafts for threads labeled `🤖 AI/Needs Response`.

## Steps

1. Query the local SQLite database for emails with classification
   `needs_response` and status `pending` (no draft yet created).
2. For each email:
   a. Load the full thread from Gmail MCP.
   b. Determine communication style:
      - Check config/contacts.yml for sender override
      - Check domain overrides
      - Analyze thread history for formality signals
      - Fall back to default style
   c. Load the matching style from config/communication_styles.yml
      (rules, examples, sign_off, language).
   d. Generate a draft reply following the style rules.
   e. Prepend the rework marker to the draft body:
      `---✂--- Your instructions above this line / Draft below ---✂---`
   f. Create the draft as a reply to the thread via Gmail MCP.
   g. Move the label from `🤖 AI/Needs Response` to `🤖 AI/Outbox`.
   h. Update the local DB: set status to `drafted`, store draft_id.

## Draft quality guidelines

- Match the language of the incoming email unless the style config
  specifies otherwise.
- Keep drafts concise — match the length and energy of the sender.
- Include specific details from the original email (dates, names, numbers).
- Never fabricate information. If context is missing, flag it in the draft
  with [TODO: ...].
- Use the sign_off from the style config.

## Output

Print a summary of drafts created with thread subjects and styles used.
```

### Command: `rework-draft.md`

```markdown
# Rework Draft

Process user feedback on drafts labeled `🤖 AI/Rework`.

## Steps

1. Use Gmail MCP to find threads with the `🤖 AI/Rework` label.
2. For each thread:
   a. Check rework_count in local DB. If rework_count >= 3, this
      thread has exceeded the rework limit — move label to
      `🤖 AI/Action Required`, update DB status, and skip to next thread.
   b. Fetch the current draft from the thread.
   c. Extract user instructions: everything ABOVE the
      `---✂---` marker line in the draft body.
   d. Parse the instructions for:
      - Style overrides ("informal tone", "formal please")
      - Context references ("the April email", "our last conversation")
      - Content directives ("say no", "add Tuesday meeting", "shorter")
      - Language switches ("in English", "česky")
   e. If context is referenced:
      - Search Gmail MCP for matching threads
        (same sender, referenced time period, keywords)
      - Include relevant excerpts as context for regeneration
   f. If a style override is requested, load that style config.
      Otherwise, use the original style.
   g. Regenerate the draft with the user's instructions + any
      additional context.
   h. Delete the old draft via Gmail MCP, then create a new draft
      as a reply on the same thread (Gmail MCP has no draft update
      — delete + recreate is the pattern). Preserve the thread_id
      and in_reply_to from the original draft.
   i. If this is the 3rd rework (rework_count will become 3), prepend
      a warning to the draft body above the marker:
      `⚠️ This is the last automatic rework. Further changes must be made manually.`
      And move the label to `🤖 AI/Action Required` instead of `🤖 AI/Outbox`.
   j. Otherwise, move the label from `🤖 AI/Rework` back to `🤖 AI/Outbox`.
   k. Update the local DB: increment rework_count, log the instruction,
      store the new draft_id.

## Important

- Preserve any factual content the user added to the draft.
- If the instruction is ambiguous, err on the side of minimal changes.
- If referenced context can't be found, note it:
  [TODO: couldn't find the April email — please verify the reference].

## Output

Print a summary of reworked drafts with the instruction that was processed
and current rework count.
```

### Command: `process-invoices.md`

```markdown
# Process Invoices

Extract structured data from emails labeled `🤖 AI/Invoice`.

## Steps

1. Query Gmail MCP for threads with `🤖 AI/Invoice` label
   that haven't been processed yet (check local DB).
2. For each thread:
   a. Extract:
      - Vendor/sender name
      - Invoice number
      - Amount (with currency)
      - Due date
      - Variable symbol (variabilní symbol) if present
      - Bank account / IBAN if present
   b. Store in local DB: invoice_amount, invoice_currency,
      invoice_due_date, invoice_number, vendor_name, variable_symbol
   c. (Optional) Search Fakturoid MCP for matching expense:
      - Match by variable symbol or vendor name + amount
      - If found, store fakturoid_expense_id
      - If not found, flag as "unmatched"

## Output

Print a table:
| Vendor | Invoice # | Amount | Due | Fakturoid match |
```

### Command: `morning-briefing.md`

```markdown
# Morning Briefing

Generate a local HTML dashboard summarizing the inbox state.

## Steps

1. Read the local SQLite database for all active (non-archived) items.
2. Generate an HTML file at `~/inbox-dashboard/index.html` with:

### Summary section
- Counts by category (needs response, outbox, rework, action required,
  invoices, FYI, waiting)
- Total unprocessed

### Action queue
For each `🤖 AI/Outbox` and `🤖 AI/Action Required` item, a card showing:
- Subject, sender, date
- Classification + one-line reasoning
- Draft preview (first 3 lines) for Outbox items
- Direct link to Gmail thread:
  `https://mail.google.com/mail/u/0/#inbox/{message_id}`

### Invoice tracker
Table with columns: Vendor, Amount, Due date, Status, Fakturoid link

### Waiting for
List of threads where I'm waiting, with days elapsed since last message.

### Design
- Clean, minimal HTML with inline CSS
- Mobile-responsive (in case I open it on my phone too)
- No JavaScript dependencies
- Light color scheme, clear typography
- Cards for action items, table for invoices

## Output

Write the file and print the path.
```

---

## 5. Orchestration

### Full pipeline run

A wrapper script or command that runs the pipeline in sequence:

```bash
#!/bin/bash
# bin/process-inbox
# Model routing: pass --model explicitly because command-level
# model frontmatter has a known bug (anthropics/claude-code#13535).

echo "=== Inbox Triage ==="
claude --model haiku --command inbox-triage

echo "=== Draft Responses ==="
claude --model sonnet --command draft-response

echo "=== Rework Drafts ==="
claude --model sonnet --command rework-draft

echo "=== Process Invoices ==="
claude --model haiku --command process-invoices

echo "=== Generate Dashboard ==="
claude --model haiku --command morning-briefing

echo "=== Done ==="
```

### Scheduling

Use macOS `launchd` to run the pipeline every 30 minutes:

**File: `~/Library/LaunchAgents/com.tom.inbox-processor.plist`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tom.inbox-processor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/project/bin/process-inbox</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>StandardOutPath</key>
    <string>/tmp/inbox-processor.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/inbox-processor-error.log</string>
</dict>
</plist>
```

Load with: `launchctl load ~/Library/LaunchAgents/com.tom.inbox-processor.plist`

### Manual trigger

For on-demand processing:

```bash
# Run everything
bin/process-inbox

# Run just triage + dashboard (quick check)
claude --model haiku --command inbox-triage && claude --model haiku --command morning-briefing

# Rework only (after adding feedback on mobile)
claude --model sonnet --command rework-draft
```

---

## 6. Local Database Schema

**File: `data/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_thread_id TEXT UNIQUE NOT NULL,
    gmail_message_id TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    sender_name TEXT,
    subject TEXT,
    snippet TEXT,
    received_at DATETIME,

    -- Classification
    classification TEXT NOT NULL
        CHECK (classification IN (
            'needs_response', 'action_required',
            'invoice', 'fyi', 'waiting'
        )),
    confidence TEXT DEFAULT 'medium'
        CHECK (confidence IN ('high', 'medium', 'low')),
    reasoning TEXT,
    detected_language TEXT DEFAULT 'cs',
    resolved_style TEXT DEFAULT 'business',

    -- Thread tracking
    message_count INTEGER DEFAULT 1,  -- track message count to detect new replies in 🤖 AI/Waiting threads

    -- Draft tracking
    status TEXT DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'drafted', 'rework_requested',
            'sent', 'skipped', 'archived'
        )),
    draft_id TEXT,
    rework_count INTEGER DEFAULT 0,
    last_rework_instruction TEXT,

    -- Invoice fields (nullable, only for classification=invoice)
    invoice_number TEXT,
    invoice_amount REAL,
    invoice_currency TEXT DEFAULT 'CZK',
    invoice_due_date DATE,
    variable_symbol TEXT,
    vendor_name TEXT,
    fakturoid_expense_id INTEGER,

    -- Timestamps
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    drafted_at DATETIME,
    acted_at DATETIME,

    -- Indexes
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_emails_classification ON emails(classification);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(gmail_thread_id);

-- Audit log: every action the system takes on an email
CREATE TABLE IF NOT EXISTS email_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_thread_id TEXT NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'classified', 'label_added', 'label_removed',
            'draft_created', 'draft_deleted', 'draft_reworked',
            'sent_detected', 'archived', 'rework_limit_reached',
            'waiting_retriaged', 'error'
        )),
    detail TEXT,              -- human-readable description of what happened
    label_id TEXT,            -- which label was added/removed (if applicable)
    draft_id TEXT,            -- which draft was created/deleted (if applicable)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_thread ON email_events(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON email_events(event_type);
```

---

## 7. Project File Structure

```
gmail-inbox-manager/
├── .claude/
│   └── commands/
│       ├── inbox-triage.md
│       ├── draft-response.md
│       ├── rework-draft.md
│       ├── process-invoices.md
│       └── morning-briefing.md
├── config/
│   ├── communication_styles.yml
│   └── contacts.yml
├── data/
│   ├── schema.sql
│   └── inbox.db              (created at first run)
├── bin/
│   └── process-inbox          (orchestration script)
├── ~/inbox-dashboard/
│   └── index.html             (generated by morning-briefing)
└── README.md
```

---

## 8. Idempotency and Safety

### Critical invariants

- **No duplicate drafts.** Before creating a draft, check the local DB for an existing `draft_id` on that thread. If one exists, skip.
- **No duplicate labels.** Check existing labels on a thread before applying new ones.
- **Thread-level keying.** All processing is keyed on `gmail_thread_id`, not individual message IDs. A thread is one unit of work.
- **No automatic sending.** The system NEVER sends an email. It only creates drafts and applies labels. The user always sends manually.
- **No destructive actions.** The system never deletes emails or removes user-applied labels. It only adds/moves `🤖 AI/*` labels and creates/updates drafts. Draft deletion only occurs as part of the delete+recreate pattern during rework (the new draft replaces the old one on the same thread).
- **Rework is bounded.** After 3 rework cycles on the same thread, the system adds a warning to the final draft and moves it to `🤖 AI/Action Required` for manual handling. The `rework_count` is tracked in the local DB.

### Error handling

- If Gmail MCP is unreachable, the processor logs the error and retries on next scheduled run.
- If a draft creation fails, the email stays in `🤖 AI/Needs Response` for the next run.
- If classification confidence is `low`, apply `🤖 AI/FYI` as a safe default (user can manually reclassify).

---

## 9. Implementation Phases

### Phase 1 — Core loop (first weekend)

- [ ] Create Gmail labels manually
- [ ] Set up project structure and SQLite schema
- [ ] Implement `inbox-triage` command
- [ ] Implement `draft-response` command (business style only)
- [ ] Test: receive email → see label → see draft → send from mobile
- [ ] Set up `bin/process-inbox` script

### Phase 2 — Feedback and styles (second weekend)

- [ ] Implement `rework-draft` command
- [ ] Create `communication_styles.yml` with all three styles
- [ ] Create `contacts.yml` with initial overrides
- [ ] Implement style selection logic in `draft-response`
- [ ] Test: rework flow on mobile

### Phase 3 — Dashboard and invoices (third weekend)

- [ ] Implement `morning-briefing` command (HTML generation)
- [ ] Implement `process-invoices` command
- [ ] Add Fakturoid MCP matching
- [ ] Set up `launchd` scheduling

### Phase 4 — Polish (ongoing)

- [ ] Tune classification prompts based on real-world accuracy
- [ ] Expand style examples based on actual sent emails
- [ ] Add nudge/reminder logic for `🤖 AI/Waiting` threads
- [ ] Consider upgrading dashboard to a live Rails app if the static
      HTML feels limiting
