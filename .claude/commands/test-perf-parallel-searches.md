# Test: Parallelize Phase A Searches (Solution 1)

Measure the time each Phase A Gmail search takes individually to quantify the benefit of parallelization.
Report each search's latency and the potential savings from concurrent execution.
Do NOT modify any data — read-only.

## Context

From `docs/INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md`: Phase A runs at least 5 sequential
Gmail searches. These searches are independent and could be parallelized.

## Setup

Database: `data/inbox.db` (query via `sqlite3 data/inbox.db "..."`)

Label IDs: needs_response=Label_34, outbox=Label_35, rework=Label_36,
action_required=Label_37, payment_request=Label_38, fyi=Label_39,
waiting=Label_40, done=Label_41

## Test procedure

For each of the 5 searches below, capture wall-clock time using Bash `date +%s`
before and after the MCP call. Record the elapsed seconds and result count.

### S1: Done label search

**Action:** Record start time. Search Gmail: `label:🤖 AI/Done`.
Record end time and result count.

### S2: Outbox label search

**Action:** Record start time. Search Gmail: `label:🤖 AI/Outbox`.
Record end time and result count.

### S3: Waiting label search

**Action:** Record start time. Search Gmail: `label:🤖 AI/Waiting`.
Record end time and result count.

### S4: Manual Needs Response label search

**Action:** Record start time. Search Gmail: `label:🤖 AI/Needs Response newer_than:30d`.
Record end time and result count.

### S5: Unclassified emails search

**Action:** Record start time. Search Gmail:
`in:inbox newer_than:30d -label:🤖 AI/Needs Response -label:🤖 AI/Outbox -label:🤖 AI/Rework -label:🤖 AI/Action Required -label:🤖 AI/Payment Requests -label:🤖 AI/FYI -label:🤖 AI/Waiting -label:🤖 AI/Done -in:trash -in:spam`
Record end time and result count.

## Assertions

**T1 (Search independence):** PASS if all 5 searches return without error.
Each search uses different label criteria and has no data dependency on the others.

**T2 (Parallelization potential):** Calculate:
- `sequential_total` = sum of all 5 search durations
- `parallel_estimate` = max of all 5 search durations (since they'd run concurrently)
- `potential_savings` = sequential_total - parallel_estimate

PASS if `potential_savings > 0` (parallelization would help).

**T3 (Bottleneck identification):** Report which search is slowest.

## Output format

```
Search | Duration (s) | Results | Notes
-------|-------------|---------|------
S1     | 12          | 3       | Done labels
S2     | 8           | 1       | Outbox labels
S3     | 10          | 2       | Waiting labels
S4     | 15          | 5       | Manual Needs Response
S5     | 20          | 0       | Unclassified inbox

Sequential total:     65s
Parallel estimate:    20s (limited by S5)
Potential savings:    45s (69%)

Test | Result | Details
-----|--------|--------
T1   | PASS   | All 5 searches completed successfully
T2   | PASS   | Parallelization would save ~45s (69%)
T3   | PASS   | Slowest search: S5 (unclassified inbox, 20s)
```
