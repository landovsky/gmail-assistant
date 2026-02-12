# Rework Draft

Process user feedback on drafts labeled `🤖 AI/Rework`.

## Label IDs

- rework: Label_36
- outbox: Label_35
- action_required: Label_37

## Database

SQLite at `data/inbox.db`. Query via Bash: `sqlite3 data/inbox.db "SELECT ..."`

**Audit logging:** Every action must be logged to the `email_events` table:
```sql
INSERT INTO email_events (gmail_thread_id, event_type, detail, label_id, draft_id) VALUES (?, ?, ?, ?, ?);
```

## Steps

1. Search Gmail for threads with the `🤖 AI/Rework` label (Label_36).

2. For each thread:
   a. Query the local DB for the thread's rework_count and draft_id:
      ```sql
      SELECT gmail_thread_id, gmail_message_id, draft_id, rework_count, resolved_style
      FROM emails WHERE gmail_thread_id = '...'
      ```
   b. If rework_count >= 3, this thread exceeded the rework limit:
      - Move label to `🤖 AI/Action Required`: modify_email with addLabelIds ["Label_37"], removeLabelIds ["Label_36"]
      - Update DB: `UPDATE emails SET status='skipped', updated_at=CURRENT_TIMESTAMP WHERE gmail_thread_id='...'`
      - Log: `INSERT INTO email_events (gmail_thread_id, event_type, detail) VALUES ('...', 'rework_limit_reached', 'Rework limit (3) exceeded, moved to Action Required')`
      - Skip to next thread.
   c. Find the current draft: search Gmail `in:draft` in the thread to locate
      it (the stored draft_id is a resource ID, not a message ID — cannot use
      `read_email` on it directly). Read the draft content once you find it.
   d. Extract user instructions: everything ABOVE the `✂️` marker line in the draft body.
   e. Parse instructions for:
      - Style overrides ("informal tone", "formal please")
      - Context references ("the April email", "our last conversation")
      - Content directives ("say no", "add Tuesday meeting", "shorter")
      - Language switches ("in English", "česky")
   f. If context is referenced, search Gmail for matching threads
      (same sender, referenced time period, keywords) and include relevant excerpts.
   g. Load the appropriate communication style from `config/communication_styles.yml`.
   h. Regenerate the draft with the user's instructions + any additional context.
   i. Move the old draft to Trash via `modify_email` with `addLabelIds: ["TRASH"]` (recoverable for 30 days, no permanent deletion).
      Log: `INSERT INTO email_events (gmail_thread_id, event_type, detail, draft_id) VALUES ('...', 'draft_trashed', 'Old draft trashed for rework', '...')`
   j. Create a new draft via `draft_email` on the same thread:
      - Preserve threadId and inReplyTo from the original
      - Include the rework marker in the new draft
   k. If rework_count will become 3 (this is the last allowed rework), prepend a warning above the marker:
      `⚠️ This is the last automatic rework. Further changes must be made manually.`
      And move label to `🤖 AI/Action Required` (Label_37) instead of `🤖 AI/Outbox`.
   l. Otherwise, move label from `🤖 AI/Rework` to `🤖 AI/Outbox`:
      modify_email with addLabelIds ["Label_35"], removeLabelIds ["Label_36"]
   m. Update DB:
      ```sql
      UPDATE emails SET rework_count = rework_count + 1, draft_id = '...', last_rework_instruction = '...', status = 'drafted', updated_at = CURRENT_TIMESTAMP
      WHERE gmail_thread_id = '...'
      ```
   n. Log: `INSERT INTO email_events (gmail_thread_id, event_type, detail, draft_id) VALUES ('...', 'draft_reworked', 'Rework #N: <instruction summary>', '...')`

## Important

- Preserve any factual content the user added to the draft.
- If the instruction is ambiguous, err on the side of minimal changes.
- If referenced context can't be found, note it: [TODO: couldn't find the referenced email — please verify].

## Output

Print a summary of reworked drafts with the instruction processed and current rework count.
