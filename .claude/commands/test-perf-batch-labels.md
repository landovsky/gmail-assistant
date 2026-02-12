# Test: Batch Label Applications (Solution 3)

Measure the overhead of individual `modify_email` calls and quantify the benefit
of grouping them into `batch_modify_emails` calls.
Do NOT modify any data — read-only.

## Context

From `docs/INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md`: Each classified email gets
labels applied individually via `modify_email`. Batching by label type using
`batch_modify_emails` could reduce 12 API calls to 5 (one per label type).

## Setup

Database: `data/inbox.db` (query via `sqlite3 data/inbox.db "..."`)

## Test procedure

### T1: Current label distribution

**Action:** Query the DB for the most recent triage run's classification distribution:
```sql
SELECT classification, COUNT(*) as cnt
FROM emails
WHERE processed_at >= date('now', '-7 days')
GROUP BY classification
ORDER BY cnt DESC
```

**Assert:** Report the distribution. Each classification maps to exactly one label,
so this shows how many `modify_email` calls are made (one per email) and how many
`batch_modify_emails` calls would be needed (one per classification group).

### T2: Batching potential

**Action:** Calculate:
- `individual_calls`: total number of emails classified in the last 7 days
- `batched_calls`: number of distinct classification groups (at most 5)
- `call_reduction`: individual_calls - batched_calls

**Assert:** PASS if call_reduction > 0.

### T3: Single modify_email timing

**Action:** Pick one email from the DB that currently has a label. Search Gmail to
confirm the label is present (use `read_email` on the message, check labels).
Record the `read_email` call time as a proxy for per-call API overhead
(since we can't call modify_email in a read-only test).

Measure the `read_email` time with `date +%s` before and after.

**Assert:** Report the per-call overhead. This is a lower bound for `modify_email`
(writes are typically slower than reads).

### T4: Estimated savings calculation

**Action:** Using the per-call overhead from T3 and the call reduction from T2,
calculate:
- `current_time_estimate`: individual_calls x per_call_overhead
- `batched_time_estimate`: batched_calls x per_call_overhead
- `estimated_savings`: current_time_estimate - batched_time_estimate

**Assert:** PASS if estimated_savings > 0. Report with both seconds and percentage.

### T5: batch_modify_emails availability

**Action:** Verify that the `batch_modify_emails` MCP tool is available by checking
that it's listed in the allowed tools. Read `bin/common.sh` and confirm
`mcp__gmail__batch_modify_emails` is in `GMAIL_WRITE`.

**Assert:** PASS if `batch_modify_emails` is available in the toolset.

## Output format

```
Classification     | Count | Individual calls | Batch calls
-------------------|-------|-----------------|------------
fyi                | 8     | 8               | 1
action_required    | 2     | 2               | 1
needs_response     | 1     | 1               | 1
payment_request    | 1     | 1               | 1
Total              | 12    | 12              | 4

Per-call overhead (read_email proxy): ~2s
Current estimate:  12 calls x 2s = 24s
Batched estimate:  4 calls x 2s  = 8s
Estimated savings: 16s (67%)

Test | Result | Details
-----|--------|--------
T1   | PASS   | 4 classification groups, 12 emails
T2   | PASS   | Call reduction: 12 → 4 (67% fewer API calls)
T3   | PASS   | Per-call overhead: ~2s
T4   | PASS   | Estimated savings: ~16s (67%)
T5   | PASS   | batch_modify_emails available in GMAIL_WRITE
```
