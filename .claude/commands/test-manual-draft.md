# Test: Manually Request a Draft

Run assertions against live Gmail and DB state to verify the manual-draft flow.
Report each test as PASS/FAIL with details. Do NOT modify any data — read-only.

## Setup

Database: `data/inbox.db` (query via `sqlite3 data/inbox.db "..."`)

Label IDs: needs_response=Label_34, outbox=Label_35, done=Label_41

## Test cases

### T1: Manual backfill search finds labeled emails

**Action:** Search Gmail for `label:🤖 AI/Needs Response newer_than:30d`.

**Assert:** The search returns results (at least 1 email).

### T2: Backfill correctly identifies missing DB records

**Action:** For each result from T1, check the DB:
```sql
SELECT gmail_thread_id, classification, status FROM emails WHERE gmail_thread_id = '<thread_id>'
```

**Assert for each thread:** Either:
- (a) Thread exists in DB — backfill would skip it (expected for previously triaged emails), OR
- (b) Thread is missing from DB — backfill would insert it (this is the gap the feature fills)

**Report:** List each thread with its status: `IN_DB` or `MISSING — would be backfilled`.

### T3: Phase B search excludes already-labeled emails

**Action:** Run the Phase B search query:
`in:inbox newer_than:30d -label:🤖 AI/Needs Response -label:🤖 AI/Outbox -label:🤖 AI/Rework -label:🤖 AI/Action Required -label:🤖 AI/Payment Requests -label:🤖 AI/FYI -label:🤖 AI/Waiting -label:🤖 AI/Done -in:trash -in:spam`

**Assert:** None of the thread IDs from T1 appear in this result set.
If any do, it means the label exclusion is broken → FAIL.

### T4: Draft detection finds user drafts in labeled threads

**Action:** For each `needs_response` + `pending` email in DB (or threads from T2 that would be backfilled), search:
`in:draft subject:"<subject>"`

**Assert for each:** Report whether a user draft exists and whether it contains the `✂️` marker.
Possible outcomes:
- `NO_DRAFT` — no draft found (normal auto-draft path)
- `DRAFT_WITH_MARKER` — user instructions detected (manual-draft path with instructions)
- `DRAFT_NO_MARKER` — user draft exists but no marker (user wrote a reply manually, not instructions for AI)

### T5: Drafted emails excluded from next draft run

**Action:** Query the DB:
```sql
SELECT gmail_thread_id, subject, status FROM emails
WHERE classification = 'needs_response' AND status = 'drafted'
LIMIT 5
```

**Assert:** These threads would NOT be picked up by the draft-response query
(`WHERE classification = 'needs_response' AND status = 'pending'`).
Verify by confirming `status = 'drafted'` ≠ `'pending'`.

### T6: DB status values are consistent

**Action:** Run:
```sql
SELECT status, COUNT(*) FROM emails GROUP BY status ORDER BY COUNT(*) DESC
```

**Assert:** All status values are valid per schema: `pending`, `drafted`, `rework_requested`, `sent`, `skipped`, `archived`.

## Output format

Print results as a table:

```
Test | Result | Details
-----|--------|--------
T1   | PASS   | 3 labeled emails found
T2   | PASS   | 2 in DB, 1 missing (would be backfilled)
T3   | PASS   | No overlap with Phase B results
T4   | PASS   | 1 NO_DRAFT, 1 DRAFT_NO_MARKER, 1 DRAFT_WITH_MARKER
T5   | PASS   | 3 drafted emails correctly excluded
T6   | PASS   | All status values valid
```

If any test FAILs, explain what went wrong and what the expected vs actual result was.
