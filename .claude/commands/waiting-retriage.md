# Waiting Re-triage (Phase A, Step 3)

Process waiting threads to detect new replies and update classification.

## Label IDs

Load from `config/label_ids.yml`:
- waiting: Label_40

## Process

1. **Query local DB** for all threads with `classification='waiting'`:
   ```sql
   SELECT gmail_thread_id, subject, message_count, gmail_message_id
   FROM emails WHERE classification='waiting'
   ```

2. **For each waiting thread:**
   - Read the message using `read_email` with the `gmail_message_id` to get current thread info
   - Search Gmail for messages in this thread using subject: `subject:"<exact subject>"`
   - Count the returned messages to get current message count
   - Store the thread ID to avoid duplicate processing

3. **Detect new messages:**
   - If `current_count > stored_count`:
     - Call `modify_email` with `removeLabelIds: ["Label_40"]` for the message
     - Update DB: `UPDATE emails SET message_count = ?, updated_at = CURRENT_TIMESTAMP WHERE gmail_thread_id = ?`
     - Log event: `INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES (?, 'waiting_retriaged', '...')`
     - Increment `retriaged_count`

4. **Return JSON summary:**
   ```json
   {
     "archived": 0,
     "sent_detected": 0,
     "retriaged": <count of threads where new message was detected>
   }
   ```

## Notes

- Gmail labels are per-message, but we match by thread using the exact subject line
- Only process each thread once per run (track processed_threads)
- Log all events to email_events table for audit trail

