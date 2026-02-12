# Inbox Triage

Classify unprocessed emails, handle lifecycle transitions, and apply Gmail labels.

## Label IDs

Load label IDs from `config/label_ids.yml`:
- needs_response: Label_34
- outbox: Label_35
- rework: Label_36
- action_required: Label_37
- payment_request: Label_38
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

1. **Done cleanup.** Search Gmail for messages with label `🤖 AI/Done` (Label_41).
   **IMPORTANT:** Gmail labels are per-message, not per-thread. A thread may have
   multiple messages each carrying different `🤖 AI/*` labels. You must strip labels
   from ALL messages in the thread, not just the one returned by the search.
   For each message found:
   - Call `read_email` to get its Thread ID and Subject. Skip if this thread was already processed.
   - Search for other messages in the same thread by subject:
     `subject:"<exact subject>"`. Read each result and keep only those whose
     Thread ID matches.
   - Call `batch_modify_emails` with ALL message IDs from the thread, with
     `removeLabelIds: ["Label_34", "Label_35", "Label_36", "Label_37", "Label_38", "Label_39", "Label_40", "INBOX"]`.
     Keep Label_41 (Done) as permanent audit marker.
   - Update local DB: `UPDATE emails SET status='archived', acted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE gmail_thread_id='...'`
   - Log: `INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES (?, 'archived', 'Done cleanup: archived thread, kept 🤖 AI/Done label')`

2. **Sent draft detection.** Search Gmail for threads with label `🤖 AI/Outbox` (Label_35).
   For each thread, query the local DB for the stored `draft_id` and `subject`.
   To check if the draft still exists, search Gmail: `in:draft subject:"<subject>"`.
   If the draft is gone (no results or the draft_id no longer matches), the user
   likely sent it. Remove `🤖 AI/Outbox` label, update DB status to `sent`,
   and log: `INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES (?, 'sent_detected', 'Draft no longer exists, marking as sent')`
   **Note:** `draft_email` returns a draft resource ID (e.g. `r-7936...`), NOT a
   message ID — you cannot use `read_email` on it. Use search instead.

3. **Waiting re-triage.** Search Gmail for threads with label `🤖 AI/Waiting` (Label_40).
   For each thread, query the local DB for stored `message_count`.
   Search Gmail for messages in that thread (use `rfc822msgid` or `in:thread` search).
   If the current message count is higher than stored, a new message arrived.
   Remove `🤖 AI/Waiting` label and include this thread in Phase B classification.
   Update the message_count in DB.

4. **Manual label backfill.** Search Gmail for `label:🤖 AI/Needs Response newer_than:30d`.
   For each result:
   - Call `read_email` to get the Thread ID, sender, subject, etc.
   - Check the local DB: `SELECT 1 FROM emails WHERE gmail_thread_id = '...'`
   - If the thread already exists in DB, skip it.
   - If NOT in DB: determine `resolved_style` from `config/contacts.yml` (same logic as step 10),
     then insert a new record:
     ```sql
     INSERT OR IGNORE INTO emails (gmail_thread_id, gmail_message_id, sender_email, sender_name, subject, snippet, received_at, classification, confidence, reasoning, detected_language, resolved_style, message_count, status, processed_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'needs_response', 'high', 'Manually labeled by user', ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
     ```
   - Log: `INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES (?, 'classified', 'Manual label backfill: user applied 🤖 AI/Needs Response')`

### Phase B: Classify new emails

5. Search Gmail for emails matching: `in:inbox newer_than:30d -label:🤖 AI/Needs Response -label:🤖 AI/Outbox -label:🤖 AI/Rework -label:🤖 AI/Action Required -label:🤖 AI/Payment Requests -label:🤖 AI/FYI -label:🤖 AI/Waiting -label:🤖 AI/Done -in:trash -in:spam`
   Use `search_emails` with maxResults of 20.
   Also include any threads surfaced by Phase A step 3.

   **Time window:** The default `newer_than:30d` keeps the initial scan manageable.
   The user may override this in conversation (e.g. "triage emails from the past 7 days"
   or "triage all emails with no date limit"). Adjust the search query accordingly.

6. For each email/thread:
   - Read the email content using `read_email`
   - If the thread has multiple messages, read the most recent ones (up to 3) for context
   - **Blacklist check:** Read `config/contacts.yml` and check the `blacklist` list.
     If the sender email matches any blacklist pattern (glob-style, `*` matches
     any characters), force-classify as `fyi` and skip to step 8. Do not run
     the classification logic below.

7. Classify each thread into exactly ONE category:
   - **needs_response** — Someone is asking me a direct question, requesting something, or the social context requires a reply
   - **action_required** — I need to do something outside of email (sign a document, attend a meeting, approve something)
   - **payment_request** — Contains a payment request, invoice, or billing statement
   - **fyi** — Newsletter, notification, automated message, CC'd thread where I'm not directly addressed
   - **waiting** — I sent the last message in this thread and am awaiting a reply

8. For each classified thread, apply the corresponding label via `modify_email`:
   - needs_response → addLabelIds: ["Label_34"]
   - action_required → addLabelIds: ["Label_37"]
   - payment_request → addLabelIds: ["Label_38"]
   - fyi → addLabelIds: ["Label_39"]
   - waiting → addLabelIds: ["Label_40"]

9. Store in local DB via sqlite3:
   ```
   INSERT OR REPLACE INTO emails (gmail_thread_id, gmail_message_id, sender_email, sender_name, subject, snippet, received_at, classification, confidence, reasoning, detected_language, resolved_style, message_count, status, processed_at, updated_at)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
   ```

10. For `needs_response` emails, determine the communication style:
   - Read `config/contacts.yml` and check if sender_email has an override
   - Check domain_overrides for sender domain
   - Default to `business`
   - Store resolved_style in the DB

## Classification signals

- Direct question addressed to me → needs_response
- "Please confirm / approve / sign" → action_required
- Attachment named *faktura*, *invoice*, amount + due date → payment_request
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
  "payment_request": 2,
  "fyi": 5,
  "waiting": 1,
  "archived": 2,
  "sent_detected": 1,
  "waiting_retriaged": 0
}
```
