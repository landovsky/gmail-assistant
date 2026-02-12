# Execute Waiting Re-triage (Phase A, Step 3)

Execute the Waiting re-triage step to detect new messages in threads marked as "Waiting" and remove the waiting label if a reply has arrived.

## Process

### Step 1: Load Configuration
- Load Label IDs from `config/label_ids.yml`
  - waiting: Label_40

### Step 2: Query Database
Get all threads currently marked as "waiting" from local DB:
```sql
SELECT gmail_thread_id, subject, message_count, gmail_message_id
FROM emails
WHERE classification='waiting'
ORDER BY processed_at DESC
```

### Step 3: For Each Waiting Thread

1. Read the thread's base message using `read_email`:
   - Input: gmail_message_id
   - Get: thread ID, subject, snippet
   - Skip to next if read fails

2. Search Gmail for all messages in this thread:
   - Query: `subject:"<exact subject from DB>"`
   - Count the returned messages
   - This gives us the current message count

3. Detect New Messages:
   - If current_count > stored_count:
     - A new message arrived (the user got a reply!)
     - Call `modify_email` to remove Label_40 from the message
       - Input: gmail_message_id, removeLabelIds: ["Label_40"]
     - Update local DB:
       ```sql
       UPDATE emails
       SET message_count = <current_count>,
           updated_at = CURRENT_TIMESTAMP
       WHERE gmail_thread_id = '<thread_id>'
       ```
     - Log the event:
       ```sql
       INSERT INTO email_events (gmail_thread_id, event_type, detail, created_at)
       VALUES ('<thread_id>', 'waiting_retriaged',
               'New reply detected, removed Waiting label (count: <stored> -> <current>)',
               CURRENT_TIMESTAMP)
       ```
     - Increment retriaged_count

4. Track Processed Threads:
   - Keep a set of thread IDs already processed in this run
   - Skip any duplicate entries

### Step 4: Output Summary

Return a JSON object:
```json
{
  "archived": 0,
  "sent_detected": 0,
  "retriaged": <number of threads where new message was detected>
}
```

## Implementation Notes

- Use Bash tool for all sqlite3 database queries
- Use read_email to fetch thread info when needed
- Use search_emails to count current messages in thread
- Use modify_email to remove Label_40 when new message detected
- All Gmail label operations use the label IDs from config/label_ids.yml
- Log all state changes to email_events table for audit trail

## Tools Required

- `Bash` - for sqlite3 queries
- `Read` - for reading configuration files
- `mcp__gmail__read_email` - to read thread message
- `mcp__gmail__search_emails` - to count messages in thread
- `mcp__gmail__modify_email` - to remove Waiting label
