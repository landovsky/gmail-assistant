Send a test email to exercise the Gmail Assistant classification pipeline.

Usage: /send-test-email $ARGUMENTS

$ARGUMENTS may contain `--kind=<kind>`, `--style=<style>`, and/or `--recipient=<email>`.

## Parameters

- **kind**: Which classification label to target. One of: `needs_response`, `action_required`, `payment_request`, `fyi`, `waiting`. If omitted, pick one at random.
- **style**: Tone/format of the email. One of: `formal`, `casual`, `terse`, `verbose`, `passive_aggressive`, `friendly`. If omitted, pick one at random.
- **recipient**: Email address to send to. Defaults to `tomas@kopernici.cz`.

## Instructions

1. Parse $ARGUMENTS for `--kind`, `--style`, and `--recipient` values. For any missing parameter, select randomly from the options above.
2. Generate a realistic email **in Czech** with:
   - A subject line and body that would naturally trigger the chosen **kind** classification
   - Written in the chosen **style**
   - Vary length randomly (2–8 sentences for terse/casual, 5–15 for verbose/formal)
   - Use a plausible fictional sender name and context (business partner, colleague, vendor, newsletter, etc.)
   - Do NOT mention the classification label or that this is a test
3. Use the Gmail MCP `send_email` tool to send the email:
   - **to**: the recipient address
   - **subject**: the generated subject
   - **body**: the generated body
4. After sending, report:
   - The kind and style used (especially if randomly chosen)
   - The subject line
   - A brief summary of the email content

### Kind-specific guidance

- **needs_response**: Ask a direct question, request information, or ask for an opinion. Use question marks. Examples: scheduling a meeting time, asking for feedback on a document, requesting a phone number.
- **action_required**: Require the recipient to DO something outside email — sign a document, attend a meeting, approve a request, complete a task with a deadline. Don't just ask a question.
- **payment_request**: Include an invoice, billing reference, amount due, bank account details, or payment deadline. Use words like "faktura", "platba", "splatnost", currency amounts in CZK.
- **fyi**: Write as a newsletter, automated notification, system alert, or informational update with no action needed. Can include "noreply" style language or unsubscribe notes.
- **waiting**: Write as a follow-up to a previous conversation where the sender is checking in on something they asked about before. Reference a prior email or request.
