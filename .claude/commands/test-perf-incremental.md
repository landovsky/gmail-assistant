# Test: Caching / Incremental Processing (Solution 7)

Measure how much redundant work could be avoided by tracking the last-processed
timestamp and only scanning new emails.
Do NOT modify any data — read-only.

## Context

From `docs/INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md`: The current search scans
`newer_than:30d` every run. If the system tracks the last-processed timestamp,
it could use `after:<last_run_date>` to scan only new emails, reducing the result
set size and overall processing time.

## Setup

Database: `data/inbox.db` (query via `sqlite3 data/inbox.db "..."`)

## Test procedure

### T1: Last processing timestamp

**Action:** Query the DB for the most recent processing timestamp:
```sql
SELECT MAX(processed_at) as last_run FROM emails
```

Also check the most recent event:
```sql
SELECT MAX(created_at) as last_event FROM email_events
```

**Assert:** Report both timestamps. PASS if at least one timestamp exists.

### T2: Full scan result count

**Action:** Record start time (`date +%s`). Search Gmail with the current broad query:

`in:inbox newer_than:30d -label:🤖 AI/Needs Response -label:🤖 AI/Outbox -label:🤖 AI/Rework -label:🤖 AI/Action Required -label:🤖 AI/Payment Requests -label:🤖 AI/FYI -label:🤖 AI/Waiting -label:🤖 AI/Done -in:trash -in:spam`

Record end time and result count.

### T3: Incremental scan result count

**Action:** Using the last_run timestamp from T1, construct an incremental query.
Convert the timestamp to a Gmail-compatible date format (YYYY/MM/DD):

`in:inbox after:<last_run_date> -label:🤖 AI/Needs Response -label:🤖 AI/Outbox -label:🤖 AI/Rework -label:🤖 AI/Action Required -label:🤖 AI/Payment Requests -label:🤖 AI/FYI -label:🤖 AI/Waiting -label:🤖 AI/Done -in:trash -in:spam`

Record start time, run search, record end time and result count.

### T4: Reduction measurement

**Action:** Calculate:
- `full_scan_results`: from T2
- `incremental_results`: from T3
- `reduction_pct`: (1 - incremental_results / full_scan_results) x 100
- `full_scan_time`: from T2
- `incremental_scan_time`: from T3
- `time_savings`: full_scan_time - incremental_scan_time

**Assert:** PASS if incremental_results <= full_scan_results.
Report the reduction percentage.

### T5: Already-processed email overlap

**Action:** Count how many emails from the past 30 days are already in the DB:
```sql
SELECT COUNT(*) as already_processed
FROM emails
WHERE processed_at >= date('now', '-30 days')
```

Compare with the full scan result count from T2.

**Assert:** Report the overlap. If already_processed >> full_scan_results,
the label exclusions are doing most of the filtering. If already_processed is close
to full_scan_results, incremental processing would add less value (labels already filter).

### T6: Phase A applicability

**Action:** Check if Phase A searches (Done, Outbox, Waiting) could also benefit
from incremental processing. Query the DB:
```sql
SELECT event_type, COUNT(*) as cnt, MAX(created_at) as latest
FROM email_events
WHERE event_type IN ('archived', 'sent_detected', 'waiting_retriaged')
  AND created_at >= date('now', '-7 days')
GROUP BY event_type
```

**Assert:** Report Phase A event frequency. If events are rare (< 5/day),
incremental processing for Phase A has less impact but still avoids empty searches.

## Output format

```
Metric                          | Value
--------------------------------|------
Last processed at               | 2026-02-12 17:05:00
Full scan (newer_than:30d)      | 3 results in 15s
Incremental scan (after:02/12)  | 0 results in 8s
Result reduction                | 100% (3 → 0)
Time reduction                  | 47% (15s → 8s)

Already processed (30d):        127 emails
Full scan unclassified:         3 emails
Label exclusion filtering:      97.7% already filtered by labels

Phase A events (7d):
  archived:          5
  sent_detected:     2
  waiting_retriaged: 1

Test | Result | Details
-----|--------|--------
T1   | PASS   | Last run: 2026-02-12 17:05:00
T2   | PASS   | Full scan: 3 results, 15s
T3   | PASS   | Incremental: 0 results, 8s
T4   | PASS   | 47% time reduction (even with 0 results, search still takes time)
T5   | INFO   | Labels already filter 97.7%; incremental adds marginal benefit
T6   | INFO   | Phase A has ~1 event/day; incremental would skip empty searches
```
