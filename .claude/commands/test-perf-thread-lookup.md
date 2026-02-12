# Test: Eliminate Subject-Based Thread Lookups (Solution 2)

Verify that Thread ID is available from `read_email` and that using it directly
avoids the expensive subject-based search pattern.
Do NOT modify any data — read-only.

## Context

From `docs/INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md`: Done cleanup currently searches
by `subject:"<exact subject>"` to find all messages in a thread, then filters by
Thread ID. This is redundant because Gmail threads are first-class entities and
`read_email` already returns the Thread ID.

## Setup

Database: `data/inbox.db` (query via `sqlite3 data/inbox.db "..."`)

Label IDs: done=Label_41

## Test procedure

### T1: Thread ID availability

**Action:** Search Gmail for `label:🤖 AI/Done` (or if no Done labels exist, use
any labeled email: `label:🤖 AI/Needs Response newer_than:30d`).

For the first result, call `read_email` on the message ID.

**Assert:** The response includes a Thread ID field (threadId or similar).
PASS if Thread ID is present in the read_email response.
Report the field name and value.

### T2: Subject search overhead

**Action:** Using the email from T1, take its subject and run:
`subject:"<exact subject>"`

Record start time (`date +%s`) before and end time after the search.
Count the results returned.

**Assert:** Report the duration and result count. For each result, call `read_email`
and check if its Thread ID matches the original. Report how many matched vs total.

### T3: Thread ID consistency

**Action:** From the subject search results in T2, read each message and collect
its Thread ID.

**Assert:** All messages that belong to the same conversation share the same
Thread ID. PASS if Thread IDs are consistent within the thread.

### T4: Unnecessary reads quantified

**Action:** Count from T2:
- `total_subject_results`: number of messages returned by subject search
- `matching_thread_results`: number that actually belong to the target thread
- `wasted_reads`: total_subject_results - matching_thread_results

**Assert:** Report the waste ratio. If `wasted_reads > 0`, this confirms the
subject-search approach reads unnecessary messages.

### T5: Time comparison

**Action:** Calculate:
- `current_approach_time`: time for subject search + time to read all results + filter
- `proposed_approach_time`: 0s (Thread ID already available from T1, no extra search needed)
- `savings_per_thread`: current_approach_time - proposed_approach_time

Query the DB for the total number of archived threads:
```sql
SELECT COUNT(*) FROM emails WHERE status = 'archived'
```

Multiply `savings_per_thread` by typical Done cleanup volume (use 3 threads as baseline
from the performance analysis) to estimate total savings.

**Assert:** PASS if savings_per_thread > 0.

## Output format

```
Test | Result | Details
-----|--------|--------
T1   | PASS   | Thread ID field 'threadId' found: '18d...'
T2   | PASS   | Subject search: 8 results in 12s, 3 matched thread
T3   | PASS   | All 3 matching messages share threadId '18d...'
T4   | PASS   | 5 of 8 reads were wasted (62% overhead)
T5   | PASS   | Savings: ~12s per thread, ~36s for 3 threads

Summary: Subject-based lookups add ~12s overhead per thread with 62%
wasted reads. Using Thread ID directly eliminates this entirely.
```
