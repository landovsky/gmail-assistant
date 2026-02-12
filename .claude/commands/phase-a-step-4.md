# Phase A, Step 4: Manual Label Backfill

Process emails that the user manually labeled with 🤖 AI/Needs Response but aren't yet in the database.

## Process

1. **Search Gmail** for: `label:🤖\ AI/Needs\ Response newer_than:30d`
   Use search_emails with maxResults 50 to get all recent matches.

2. **For each result**, read the full email using read_email to get:
   - Thread ID
   - Message ID  
   - Sender email and name
   - Subject
   - Snippet
   - Received timestamp (parse from headers)

3. **Check database** using Bash/sqlite3:
   ```bash
   sqlite3 data/inbox.db "SELECT 1 FROM emails WHERE gmail_thread_id = '...'"
   ```
   If result exists, skip this thread (already processed).

4. **If new to database**:
   - Load config/contacts.yml
   - Determine resolved_style:
     - Check style_overrides for sender_email (exact match)
     - Check domain_overrides for sender domain (* pattern matching)
     - Default to 'business' if no match
   - Insert record:
     ```sql
     INSERT OR IGNORE INTO emails 
     (gmail_thread_id, gmail_message_id, sender_email, sender_name, subject, snippet, 
      received_at, classification, confidence, reasoning, detected_language, resolved_style, 
      message_count, status, processed_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'needs_response', 'high', 'Manually labeled by user', 'cs', ?, 1, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
     ```
   - Log event:
     ```sql
     INSERT INTO email_events (gmail_thread_id, event_type, detail)
     VALUES (?, 'classified', 'Manual label backfill: user applied 🤖 AI/Needs Response')
     ```

5. **Return** only a single number: count of NEW threads added to database

## Tools Available

Gmail: search_emails, read_email
Local: Bash, Read, Grep

## Notes

- Gmail labels are per-message. A thread may have multiple messages with different labels.
- Only process once - skip if thread already in DB
- Don't process blacklisted senders
- Preserve existing thread records - never overwrite
- All insertions via "INSERT OR IGNORE"
