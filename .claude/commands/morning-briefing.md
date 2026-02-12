# Morning Briefing

Generate a local HTML dashboard summarizing the inbox state.

## Database

SQLite at `data/inbox.db`. Query via Bash: `sqlite3 data/inbox.db "SELECT ..."`

## Steps

1. Query the local DB for all active (non-archived, non-sent) items:
   ```sql
   SELECT * FROM emails WHERE status NOT IN ('archived', 'sent') ORDER BY processed_at DESC
   ```

2. Generate an HTML file at `data/dashboard.html` with:

### Summary section
- Counts by category (needs_response, drafted/outbox, rework_requested, action_required, payment_request, fyi, waiting)
- Total active items

### Action queue
For each item with status `drafted` or classification `action_required`, show a card with:
- Subject, sender, date
- Classification + one-line reasoning
- Direct link to Gmail thread: `https://mail.google.com/mail/u/0/#inbox/<gmail_message_id>`

### Payment requests
Table of emails classified as `payment_request`: Subject, Sender, Date, Status

### Waiting for
List of threads with classification `waiting`, showing days elapsed since processed_at.

### Design
- Clean, minimal HTML with inline CSS
- Mobile-responsive
- No JavaScript dependencies
- Light color scheme, clear typography

## Output

Write the HTML file and print the path.
