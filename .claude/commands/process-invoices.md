# Process Invoices

Extract structured data from emails labeled `🤖 AI/Invoice`.

## Label IDs

- invoice: Label_38

## Database

SQLite at `data/inbox.db`. Query via Bash: `sqlite3 data/inbox.db "SELECT ..."`

## Steps

1. Query the local DB for unprocessed invoices:
   ```sql
   SELECT gmail_thread_id, gmail_message_id, subject, sender_email
   FROM emails
   WHERE classification = 'invoice' AND invoice_number IS NULL
   ```

2. For each thread:
   a. Read the email content using `read_email`.
   b. Extract:
      - Vendor/sender name
      - Invoice number
      - Amount (with currency)
      - Due date
      - Variable symbol (variabilní symbol) if present
      - Bank account / IBAN if present
   c. Update the local DB:
      ```sql
      UPDATE emails SET
        vendor_name = '...',
        invoice_number = '...',
        invoice_amount = ...,
        invoice_currency = '...',
        invoice_due_date = '...',
        variable_symbol = '...',
        updated_at = CURRENT_TIMESTAMP
      WHERE gmail_thread_id = '...'
      ```

## Output

Print a table:
```
| Vendor | Invoice # | Amount | Due | Variable Symbol |
|--------|-----------|--------|-----|-----------------|
| ...    | ...       | ...    | ... | ...             |
```
