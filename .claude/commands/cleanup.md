# Cleanup & Lifecycle Transitions

Handle Done cleanup, sent draft detection, and Waiting re-triage.
This is Phase A of inbox-triage, run standalone.

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

1. **Done cleanup.** Search Gmail for threads with label `🤖 AI/Done` (Label_41).
   For each thread found:
   - Remove all `🤖 AI/*` labels EXCEPT `🤖 AI/Done` (Label_34 through Label_40) using `modify_email` with `removeLabelIds`. Keep Label_41 as permanent audit marker.
   - Also remove the INBOX label to archive the thread
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
   Remove `🤖 AI/Waiting` label and log:
   `INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES (?, 'waiting_retriaged', 'New reply detected, removed Waiting label')`

## Output

Print a JSON summary:
```json
{
  "archived": 2,
  "sent_detected": 1,
  "waiting_retriaged": 0
}
```
