# Draft Response

Generate email reply drafts for threads labeled `🤖 AI/Needs Response`.

## Label IDs

- needs_response: Label_34
- outbox: Label_35

## Database

SQLite at `data/inbox.db`. Query via Bash: `sqlite3 data/inbox.db "SELECT ..."`

**Audit logging:** Every action must be logged to the `email_events` table:
```sql
INSERT INTO email_events (gmail_thread_id, event_type, detail, label_id, draft_id) VALUES (?, ?, ?, ?, ?);
```

## Steps

1. Query the local DB for emails needing drafts:
   ```sql
   SELECT gmail_thread_id, gmail_message_id, sender_email, sender_name, subject, detected_language, resolved_style
   FROM emails
   WHERE classification = 'needs_response' AND status = 'pending'
   ```

2. For each email:
   a. Read the full thread from Gmail MCP using `read_email` with the gmail_message_id.
   b. Load the communication style config from `config/communication_styles.yml`.
      Use the `resolved_style` from the DB (already determined by inbox-triage).
      For Phase 1, this will typically be `business`.
   c. Load style rules, examples, sign_off, and language setting.
   d. Generate a draft reply following the style rules.
   e. Prepend the rework marker to the draft body. Format:
      two blank lines, then `✂️` on its own line, then blank line,
      then the draft. This gives the user space to tap and type above the marker.
      ```


      ✂️

      [draft content here]
      ```
   f. Create the draft as a reply to the thread via Gmail MCP `draft_email`:
      - Set `to` to the sender's email
      - Set `subject` to "Re: [original subject]" (if not already prefixed)
      - Set `body` to the draft content with marker
      - Set `threadId` to the gmail_thread_id
      - Set `inReplyTo` to the gmail_message_id
   g. Move the label: use `modify_email` on the message with
      `addLabelIds: ["Label_35"]` and `removeLabelIds: ["Label_34"]`
   h. Update the local DB:
      ```sql
      UPDATE emails SET status='drafted', draft_id='...', drafted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
      WHERE gmail_thread_id='...'
      ```
   i. Log to audit table:
      ```sql
      INSERT INTO email_events (gmail_thread_id, event_type, detail, draft_id)
      VALUES ('...', 'draft_created', 'Draft created with style: ...', '...')
      ```

## Draft quality guidelines

- Match the language of the incoming email unless the style config specifies otherwise.
- Keep drafts concise — match the length and energy of the sender.
- Include specific details from the original email (dates, names, numbers).
- Never fabricate information. If context is missing, flag it with [TODO: ...].
- Use the sign_off from the style config.
- Do NOT include the subject line in the body.

## Output

Print a summary of drafts created:
```
Drafted 3 responses:
- "Re: Project deadline" (business style, cs)
- "Re: Meeting next week" (business style, en)
- "Re: Faktura za služby" (business style, cs)
```
