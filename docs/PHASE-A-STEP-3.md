# Phase A, Step 3: Waiting Re-triage

## Overview

Phase A, Step 3 detects new messages (replies) in threads marked as "🤖 AI/Waiting" and removes the Waiting label if a reply has been received.

## What it Does

For each thread with `classification='waiting'` in the local database:

1. **Query the database** for the stored message count
2. **Search Gmail** for the current message count in that thread (using exact subject match)
3. **Detect new messages:** If `current_count > stored_count`, a reply has arrived
4. **Remove the Waiting label:** Call `modify_email` to remove Label_40
5. **Update the database:** Set the new message count
6. **Log the event:** Record the action in the audit trail

## Database Schema

The implementation uses two tables:

### emails
- `gmail_thread_id` - Unique thread identifier
- `subject` - Email subject line (used to find all messages in thread)
- `message_count` - Number of messages in the thread (to detect new replies)
- `classification` - One of: needs_response, action_required, payment_request, fyi, waiting
- `gmail_message_id` - Message ID for the primary message
- `processed_at` - When the thread was first processed
- `updated_at` - When the thread was last updated

### email_events
- `gmail_thread_id` - Which thread this event is about
- `event_type` - Classification: 'waiting_retriaged'
- `detail` - Human-readable description of what happened
- `created_at` - When the event occurred

## Execution Modes

### Mode 1: Standalone Script
```bash
./bin/phase-a-step-3
```

This runs the step as a standalone Bash script. It queries the database and shows what would happen, but cannot access Gmail MCP tools from bash directly. Returns:
```json
{"archived": 0, "sent_detected": 0, "retriaged": 0}
```

### Mode 2: Full Pipeline with Claude Code
```bash
./bin/process-inbox all
# or
claude -p /cleanup
```

When run through Claude Code with MCP tools available:
- Accesses Gmail MCP tools
- Performs actual message count searches
- Removes labels from threads when new messages detected
- Updates database and logs events
- Returns actual count of retriaged threads

## Configuration

Label IDs are loaded from `config/label_ids.yml`:
```yaml
waiting: Label_40
```

## Example Walkthrough

Given:
- Thread ID: `19c509b5d4d3afd3`
- Subject: `RE: oprava číslování - DOTAZ`
- Stored message count: 1 (you sent the last message)
- User got a reply

Steps:

1. **Query database:**
   ```sql
   SELECT message_count FROM emails WHERE gmail_thread_id='19c509b5d4d3afd3'
   → Returns: 1
   ```

2. **Search Gmail:**
   ```
   search_emails(q='subject:"RE: oprava číslování - DOTAZ"')
   → Returns: 2 messages
   ```

3. **Detect new message:**
   ```
   current_count (2) > stored_count (1) ✓
   → New reply detected!
   ```

4. **Remove label:**
   ```
   modify_email(id='19c509b5d4d3afd3', removeLabelIds=['Label_40'])
   ```

5. **Update database:**
   ```sql
   UPDATE emails SET message_count=2, updated_at=NOW() WHERE gmail_thread_id='...'
   ```

6. **Log event:**
   ```sql
   INSERT INTO email_events VALUES (..., 'waiting_retriaged', 'New reply detected, removed Waiting label (count: 1 → 2)', NOW())
   ```

7. **Result:**
   - Thread no longer has Waiting label
   - Will be re-classified in Phase B
   - Event recorded in audit trail

## Implementation Files

- **`.claude/commands/retriage-waiting.md`** - Claude Code command specification
- **`bin/phase-a-step-3`** - Standalone Bash script
- **`bin/waiting-retriage`** - Python version
- **`bin/waiting-retriage-full`** - Python version with documentation
- **`.claude/commands/waiting-retriage-execute.md`** - Execution guide
- **`.claude/commands/phase-a-step-3.md`** - Detailed specification

## Integration with Pipeline

This step is part of Phase A: "Cleanup & lifecycle transitions" in the Inbox Triage pipeline.

Full pipeline order:
1. **Phase A, Step 1:** Done cleanup
2. **Phase A, Step 2:** Sent draft detection
3. **Phase A, Step 3:** Waiting re-triage ← You are here
4. **Phase B:** Classify new emails
5. Draft response generation

## Output Format

All implementations return JSON:
```json
{
  "archived": 0,
  "sent_detected": 0,
  "retriaged": <number of threads where new messages were detected>
}
```

The `archived` and `sent_detected` counts are always 0 for this step (those are handled by Steps 1 and 2).

## Testing

To test the database update logic without Gmail access:
```bash
# Simulate a new message arriving
sqlite3 data/inbox.db "UPDATE emails SET message_count=2 WHERE gmail_thread_id='19c509b5d4d3afd3'"

# Log the event
sqlite3 data/inbox.db "INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES ('19c509b5d4d3afd3', 'waiting_retriaged', 'Test: New reply detected')"

# Verify
sqlite3 data/inbox.db "SELECT message_count FROM emails WHERE gmail_thread_id='19c509b5d4d3afd3'"
sqlite3 data/inbox.db "SELECT event_type, detail FROM email_events WHERE gmail_thread_id='19c509b5d4d3afd3' AND event_type='waiting_retriaged'"
```

## Notes

- **Subject line matching:** We use exact subject line to find all messages in a thread because Gmail labels are per-message, not per-thread
- **Deduplication:** Each thread is processed only once per run to avoid duplicate work
- **Audit trail:** All actions are logged to email_events for transparency and debugging
- **MCP tools:** Requires Gmail MCP tools (search_emails, modify_email) for full functionality

## See Also

- [Inbox Triage Overview](../README.md#automatic-inbox-triage)
- [Full Pipeline Documentation](./ARCHITECTURE.md)
- [Database Schema](../data/schema.sql)
