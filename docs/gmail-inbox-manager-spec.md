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

All system-managed labels are prefixed with `🤖/` to visually group them in Gmail's sidebar and distinguish them from manual labels.

### Labels

| Label | Applied by | Meaning | User action |
|---|---|---|---|
| `🤖/Needs Response` | Processor | Email requires a reply | Wait for draft, or rework |
| `🤖/Outbox` | Processor | Draft reply is ready in the thread | Review draft, edit, send |
| `🤖/Rework` | **User** | Draft needs revision (user added instructions) | Wait for regenerated draft |
| `🤖/Action Required` | Processor | Non-email action needed (sign, pay, attend…) | Do the thing, then apply `🤖/Done` |
| `🤖/Invoice` | Processor | Unpaid invoice detected | Pay or forward to accountant |
| `🤖/FYI` | Processor | Informational, no action needed | Skim or archive at will |
| `🤖/Waiting` | Processor | Awaiting someone else's reply | System sends periodic nudge reminders |
| `🤖/Done` | **User** | Signals "I'm finished with this thread" | System archives, stops processing |

### Label Lifecycle

```
New email arrives
    │
    ▼
inbox-triage classifies
    │
    ├─→ 🤖/FYI                          (terminal — user archives when ready)
    ├─→ 🤖/Action Required              → user acts → 🤖/Done → archived
    ├─→ 🤖/Invoice                      → user pays → 🤖/Done → archived
    ├─→ 🤖/Waiting                      → reply arrives → reclassified
    └─→ 🤖/Needs Response
            │
            ▼
        draft-response generates draft
            │
            ▼
        🤖/Outbox
            │
            ├─→ User sends draft         → label removed, thread done
            ├─→ User adds note, relabels → 🤖/Rework → rework-draft
            │                                  │
            │                                  ▼
            │                              Regenerated draft → 🤖/Outbox
            └─→ User removes label        → interpreted as "skip, don't redraft"
```

---

## 2. Rework Feedback Loop

### How it works

1. User sees a draft in `🤖/Outbox` on mobile
2. User opens the draft and types instructions **at the top** of the draft body, above a `---✂---` marker line
3. User saves the draft and changes the label from `🤖/Outbox` → `🤖/Rework`
4. Next processor run picks up `🤖/Rework` threads:
   - Reads the user's note (everything above the `---✂---` marker)
   - If the note references other emails (e.g. "see the April email"), searches Gmail via MCP for matching threads with that contact around the referenced time
   - Feeds the note + any retrieved context into `rework-draft` command
   - Regenerates the draft
   - Moves label back to `🤖/Outbox`

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

Classify unprocessed emails and apply Gmail labels.

## Steps

1. Use Gmail MCP to fetch emails that have no `🤖/*` labels and are not in Trash or Spam.
2. For each email thread, read the full thread content.
3. Classify into exactly ONE category:

   - **needs_response** — Someone is asking me a direct question, requesting
     something, or the social context requires a reply
   - **action_required** — I need to do something outside of email
     (sign a document, attend a meeting, approve something)
   - **invoice** — Contains a payment request, invoice, or billing statement
   - **fyi** — Newsletter, notification, automated message, CC'd thread
     where I'm not directly addressed
   - **waiting** — I sent the last message in this thread and am awaiting a reply

4. Apply the corresponding `🤖/*` label via Gmail MCP.
5. Store the classification in the local SQLite database at `data/inbox.db`:
   - gmail_thread_id, gmail_message_id, sender, subject
   - classification, confidence (high/medium/low), reasoning (one line)
   - detected_language, processed_at
6. For `needs_response` emails, also store:
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
  "waiting": 1
}
```

### Command: `draft-response.md`

```markdown
# Draft Response

Generate email reply drafts for threads labeled `🤖/Needs Response`.

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
   g. Move the label from `🤖/Needs Response` to `🤖/Outbox`.
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

Process user feedback on drafts labeled `🤖/Rework`.

## Steps

1. Use Gmail MCP to find threads with the `🤖/Rework` label.
2. For each thread:
   a. Fetch the current draft from the thread.
   b. Extract user instructions: everything ABOVE the
      `---✂---` marker line in the draft body.
   c. Parse the instructions for:
      - Style overrides ("informal tone", "formal please")
      - Context references ("the April email", "our last conversation")
      - Content directives ("say no", "add Tuesday meeting", "shorter")
      - Language switches ("in English", "česky")
   d. If context is referenced:
      - Search Gmail MCP for matching threads
        (same sender, referenced time period, keywords)
      - Include relevant excerpts as context for regeneration
   e. If a style override is requested, load that style config.
      Otherwise, use the original style.
   f. Regenerate the draft with the user's instructions + any
      additional context.
   g. Replace the draft body (keep the marker format).
   h. Move the label from `🤖/Rework` back to `🤖/Outbox`.
   i. Update the local DB: increment rework_count, log the instruction.

## Important

- Preserve any factual content the user added to the draft.
- If the instruction is ambiguous, err on the side of minimal changes.
- If referenced context can't be found, note it:
  [TODO: couldn't find the April email — please verify the reference].

## Output

Print a summary of reworked drafts with the instruction that was processed.
```

### Command: `process-invoices.md`

```markdown
# Process Invoices

Extract structured data from emails labeled `🤖/Invoice`.

## Steps

1. Query Gmail MCP for threads with `🤖/Invoice` label
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
For each `🤖/Outbox` and `🤖/Action Required` item, a card showing:
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

echo "=== Inbox Triage ==="
claude --command inbox-triage

echo "=== Draft Responses ==="
claude --command draft-response

echo "=== Rework Drafts ==="
claude --command rework-draft

echo "=== Process Invoices ==="
claude --command process-invoices

echo "=== Generate Dashboard ==="
claude --command morning-briefing

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
claude --command inbox-triage && claude --command morning-briefing

# Rework only (after adding feedback on mobile)
claude --command rework-draft
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
- **No destructive actions.** The system never deletes emails or removes user-applied labels. It only adds/moves `🤖/*` labels and creates/updates drafts.
- **Rework is bounded.** After 3 rework cycles on the same thread, the system flags it for manual handling instead of regenerating.

### Error handling

- If Gmail MCP is unreachable, the processor logs the error and retries on next scheduled run.
- If a draft creation fails, the email stays in `🤖/Needs Response` for the next run.
- If classification confidence is `low`, apply `🤖/FYI` as a safe default (user can manually reclassify).

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
- [ ] Add nudge/reminder logic for `🤖/Waiting` threads
- [ ] Consider upgrading dashboard to a live Rails app if the static
      HTML feels limiting
