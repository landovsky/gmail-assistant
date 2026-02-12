# Phase A, Step 3: Waiting Re-triage

## Overview

This step processes threads marked as "🤖 AI/Waiting" to detect if new messages (replies) have arrived. If a reply is detected:
1. The "Waiting" label is removed
2. The thread is re-classified in Phase B
3. The database is updated
4. The event is logged

## Implementation

### Configuration

Label IDs from `config/label_ids.yml`:
- waiting: Label_40

### Step 1: Query Database

Get all waiting threads:
```bash
sqlite3 data/inbox.db "SELECT gmail_thread_id, subject, message_count, gmail_message_id FROM emails WHERE classification='waiting' ORDER BY processed_at DESC"
```

Expected output: pipe-separated values with one row per waiting thread

### Step 2: Initialize Counters
- `retriaged_count = 0`
- `processed_threads = []` (to avoid duplicate processing)

### Step 3: Process Each Waiting Thread

For each row from Step 1:

1. **Parse the row:**
   - `thread_id` = gmail_thread_id
   - `subject` = subject
   - `stored_count` = message_count
   - `message_id` = gmail_message_id

2. **Skip duplicates:**
   - If thread_id is already in processed_threads, skip to next row
   - Add thread_id to processed_threads

3. **Search Gmail for current message count:**
   ```
   Call search_emails with q = 'subject:"' + subject + '"'
   Count the number of messages in the response
   current_count = length of messages list
   ```

4. **Detect new messages:**
   - If `current_count > stored_count`:
     - A new message has arrived!
     - The user received a reply to their waiting message

5. **Remove Waiting label:**
   ```
   Call modify_email with:
     - id = message_id
     - removeLabelIds = ["Label_40"]
   ```

6. **Update database:**
   ```bash
   sqlite3 data/inbox.db "UPDATE emails SET message_count = $current_count, updated_at = CURRENT_TIMESTAMP WHERE gmail_thread_id = '$thread_id'"
   ```

7. **Log the event:**
   ```bash
   sqlite3 data/inbox.db "INSERT INTO email_events (gmail_thread_id, event_type, detail, created_at) VALUES ('$thread_id', 'waiting_retriaged', 'New reply detected, removed Waiting label (count: $stored_count → $current_count)', CURRENT_TIMESTAMP)"
   ```

8. **Increment counter:**
   - `retriaged_count += 1`

### Step 4: Output Result

After processing all waiting threads, output:
```json
{
  "archived": 0,
  "sent_detected": 0,
  "retriaged": <retriaged_count>
}
```

## Important Notes

- **Gmail label operations:** Labels are per-message in Gmail, but we identify the thread using the exact subject line
- **Thread deduplication:** Only process each thread once per run to avoid redundant work
- **Audit trail:** Every state change is logged to email_events for audit purposes
- **Database consistency:** Always update the local database when removing labels from Gmail
- **Edge case:** If a subject line contains special characters, it may need escaping for the search query

## Tools Required

- `Bash` - for database operations and orchestration
- `Read` - for reading configuration files
- `mcp__gmail__search_emails` - to find current message count
- `mcp__gmail__modify_email` - to remove Waiting label
- `mcp__gmail__read_email` - to verify thread info if needed

## Expected Behavior

- If no waiting threads: returns `{"archived": 0, "sent_detected": 0, "retriaged": 0}`
- If waiting threads exist but no new messages: returns count with retriaged=0
- If new messages detected: removes labels, updates DB, increments retriaged count
