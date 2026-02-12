# Retriage Waiting Threads

Execute Phase A, Step 3: Detect new messages in waiting threads and remove the Waiting label.

## Overview

For each thread marked as "🤖 AI/Waiting" (Label_40):
1. Query the local database for stored message count
2. Search Gmail for actual current message count
3. If current > stored: new reply detected!
   - Remove the Waiting label
   - Update the database
   - Log the event

## Steps

### 1. Query Database for Waiting Threads

Use Bash to query:
```bash
sqlite3 data/inbox.db "SELECT gmail_thread_id, subject, message_count, gmail_message_id FROM emails WHERE classification='waiting' ORDER BY processed_at DESC"
```

This returns pipe-separated rows: `thread_id|subject|stored_count|message_id`

### 2. Initialize Tracking

- `retriaged_count = 0`
- `processed_threads = {}` (set of thread IDs already processed)

### 3. For Each Waiting Thread

Repeat the following for each row:

**a) Parse the row:**
```
thread_id, subject, stored_count, message_id = parse_row(row)
```

**b) Skip duplicates:**
```
if thread_id in processed_threads:
    continue
processed_threads.add(thread_id)
```

**c) Search Gmail for current message count:**
```
Use search_emails with:
  q = 'subject:"<exact subject>"'

Count the messages in the response: current_count
```

**d) Detect new message:**
```
if current_count > stored_count:
    # New message has arrived!
    # User got a reply to their waiting message
```

**e) Remove Waiting label:**
```
Call modify_email with:
  id = message_id
  removeLabelIds = ["Label_40"]
```

**f) Update database:**
```bash
sqlite3 data/inbox.db "UPDATE emails SET message_count = $current_count, updated_at = CURRENT_TIMESTAMP WHERE gmail_thread_id = '$thread_id'"
```

**g) Log the event:**
```bash
sqlite3 data/inbox.db "INSERT INTO email_events (gmail_thread_id, event_type, detail, created_at) VALUES ('$thread_id', 'waiting_retriaged', 'New reply detected, removed Waiting label (count: $stored_count → $current_count)', CURRENT_TIMESTAMP)"
```

**h) Increment counter:**
```
retriaged_count += 1
```

### 4. Return Result

Output JSON:
```json
{
  "archived": 0,
  "sent_detected": 0,
  "retriaged": <retriaged_count>
}
```

## Configuration

Load from `config/label_ids.yml`:
```yaml
waiting: Label_40
```

## Database

SQLite database at `data/inbox.db` with schema in `data/schema.sql`.

Required tables:
- `emails` - thread records with classification, message_count
- `email_events` - audit log of all actions

## Implementation Notes

- **Subject matching:** Gmail searches use exact subject line to find thread messages
- **Per-message labels:** Gmail labels are per-message, so we match by subject to find all messages in a thread
- **Deduplication:** Process each thread only once per run
- **Audit trail:** Log all state changes to email_events
- **Edge case handling:** Special characters in subjects may need escaping for the search query

## Tools Required

- `Bash` - for sqlite3 database queries
- `mcp__gmail__search_emails` - to count messages in thread
- `mcp__gmail__modify_email` - to remove Waiting label

## Expected Output Examples

**No waiting threads:**
```json
{
  "archived": 0,
  "sent_detected": 0,
  "retriaged": 0
}
```

**One waiting thread with no new messages:**
```json
{
  "archived": 0,
  "sent_detected": 0,
  "retriaged": 0
}
```

**Two waiting threads, one with new message:**
```json
{
  "archived": 0,
  "sent_detected": 0,
  "retriaged": 1
}
```
