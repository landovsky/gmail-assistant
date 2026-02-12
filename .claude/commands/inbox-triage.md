# Inbox Triage

Classify unprocessed emails, handle lifecycle transitions, and apply Gmail labels.

## Label IDs

Load label IDs from `config/label_ids.yml`:
- needs_response: Label_34
- outbox: Label_35
- rework: Label_36
- action_required: Label_37
- invoice: Label_38
- fyi: Label_39
- waiting: Label_40
- done: Label_41

## Database

Use the SQLite database at `data/inbox.db` (schema in `data/schema.sql`).
Run queries via Bash: `sqlite3 data/inbox.db "SELECT ..."`

**Audit logging:** Every action must be logged to the `email_events` table:
```sql
INSERT INTO email_events (gmail_thread_id, event_type, detail, label_id, draft_id) VALUES (?, ?, ?, ?, ?);
```

## Steps

### Phase A: Cleanup & lifecycle transitions

1. **Done cleanup.** Search Gmail for threads with label `🤖 AI/Done` (Label_41).
   For each thread found:
   - Remove all `🤖 AI/*` labels EXCEPT `🤖 AI/Done` (Label_34 through Label_40) using `modify_email` with `removeLabelIds`. Keep Label_41 as permanent audit marker.
   - Also remove the INBOX label to archive the thread
   - Update local DB: `UPDATE emails SET status='archived', acted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE gmail_thread_id='...'`
   - Log: `INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES (?, 'archived', 'Done cleanup: archived thread, kept 🤖 AI/Done label')`

2. **Sent draft detection.** Search Gmail for threads with label `🤖 AI/Outbox` (Label_35).
   For each thread, query the local DB for the stored `draft_id`.
   If a draft_id exists, try to read it via `read_email`. If it fails (draft no longer exists),
   the user likely sent it. Remove `🤖 AI/Outbox` label and update DB status to `sent`.

3. **Waiting re-triage.** Search Gmail for threads with label `🤖 AI/Waiting` (Label_40).
   For each thread, query the local DB for stored `message_count`.
   Search Gmail for messages in that thread (use `rfc822msgid` or `in:thread` search).
   If the current message count is higher than stored, a new message arrived.
   Remove `🤖 AI/Waiting` label and include this thread in Phase B classification.
   Update the message_count in DB.

### Phase B: Classify new emails

4. Search Gmail for emails matching: `in:inbox -label:🤖 AI/Needs Response -label:🤖 AI/Outbox -label:🤖 AI/Rework -label:🤖 AI/Action Required -label:🤖 AI/Invoice -label:🤖 AI/FYI -label:🤖 AI/Waiting -label:🤖 AI/Done -in:trash -in:spam`
   Use `search_emails` with maxResults of 20.
   Also include any threads surfaced by Phase A step 3.

5. For each email/thread:
   - Read the email content using `read_email`
   - If the thread has multiple messages, read the most recent ones (up to 3) for context

6. Classify each thread into exactly ONE category:
   - **needs_response** — Someone is asking me a direct question, requesting something, or the social context requires a reply
   - **action_required** — I need to do something outside of email (sign a document, attend a meeting, approve something)
   - **invoice** — Contains a payment request, invoice, or billing statement
   - **fyi** — Newsletter, notification, automated message, CC'd thread where I'm not directly addressed
   - **waiting** — I sent the last message in this thread and am awaiting a reply

7. For each classified thread, apply the corresponding label via `modify_email`:
   - needs_response → addLabelIds: ["Label_34"]
   - action_required → addLabelIds: ["Label_37"]
   - invoice → addLabelIds: ["Label_38"]
   - fyi → addLabelIds: ["Label_39"]
   - waiting → addLabelIds: ["Label_40"]

8. Store in local DB via sqlite3:
   ```
   INSERT OR REPLACE INTO emails (gmail_thread_id, gmail_message_id, sender_email, sender_name, subject, snippet, received_at, classification, confidence, reasoning, detected_language, resolved_style, message_count, status, processed_at, updated_at)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
   ```

9. For `needs_response` emails, determine the communication style:
   - Read `config/contacts.yml` and check if sender_email has an override
   - Check domain_overrides for sender domain
   - Default to `business`
   - Store resolved_style in the DB

## Classification signals

- Direct question addressed to me → needs_response
- "Please confirm / approve / sign" → action_required
- Attachment named *faktura*, *invoice*, amount + due date → invoice
- Automated sender, no-reply address, marketing, newsletter → fyi
- I sent the last message, no new reply from others → waiting
- When uncertain between needs_response and fyi, prefer needs_response
- Low confidence → default to fyi as safe fallback

## Output

After processing all emails, print a JSON summary:
```json
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
