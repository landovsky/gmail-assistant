# Test: Parallelize Email Reading and Classification (Solution 4)

Measure sequential `read_email` latency across multiple emails to quantify the
benefit of parallel processing.
Do NOT modify any data — read-only.

## Context

From `docs/INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md`: Each email is read and classified
sequentially. With 12 emails at 2-5s per read, this takes 24-180s. Parallelizing
could reduce this to the latency of a single read.

## Setup

Database: `data/inbox.db` (query via `sqlite3 data/inbox.db "..."`)

## Test procedure

### T1: Sequential read latency measurement

**Action:** Query the DB for 5 recent emails:
```sql
SELECT gmail_message_id, subject FROM emails
WHERE gmail_message_id IS NOT NULL
ORDER BY processed_at DESC LIMIT 5
```

For each email, record start time (`date +%s`), call `read_email` with the
message ID, record end time. Collect all durations.

**Assert:** Report each read duration. PASS if all reads complete successfully.

### T2: Read independence verification

**Action:** Verify that the 5 reads from T1 have no data dependencies:
- Each uses a different message ID
- No read result is needed as input for another read
- The order of reads doesn't matter

**Assert:** PASS if all reads are independent (they always are for `read_email`
with different message IDs).

### T3: Parallelization savings estimate

**Action:** Calculate:
- `sequential_total`: sum of all read durations from T1
- `parallel_estimate`: max of all read durations (concurrent execution)
- `potential_savings`: sequential_total - parallel_estimate
- `speedup_factor`: sequential_total / parallel_estimate

Scale to full triage run:
- `emails_per_run`: query DB for average recent run size, or use 12 as baseline
- `reads_per_email`: use 1.5 as average (some threads need 2-3 reads)
- `total_reads`: emails_per_run x reads_per_email
- `avg_read_time`: sequential_total / 5
- `sequential_full_run`: total_reads x avg_read_time
- `parallel_full_run`: avg_read_time (all reads concurrent)

**Assert:** PASS if speedup_factor > 1.

### T4: Thread context reads

**Action:** For 2 of the emails from T1, check if they belong to multi-message threads:
```sql
SELECT gmail_thread_id, message_count FROM emails WHERE gmail_message_id = '...'
```

If message_count > 1, this means the current implementation makes additional reads
for thread context (up to 3 messages per thread, per the spec).

**Assert:** Report how many additional context reads are needed per email.
This multiplies the parallelization benefit.

### T5: API rate limit headroom

**Action:** Calculate whether parallel reads would exceed Gmail API limits:
- Gmail read limit: 400 requests per 10 seconds
- Typical triage run: 12-36 reads total
- Concurrent reads: all at once = 12-36 simultaneous

**Assert:** PASS if total concurrent reads < 400 (well within rate limit).
Report the utilization percentage.

## Output format

```
Email | Message ID   | Duration (s) | Subject (truncated)
------|-------------|-------------|--------------------
1     | 18d...abc   | 3           | Re: Project update
2     | 18d...def   | 2           | Invoice #1234
3     | 18d...ghi   | 4           | Meeting tomorrow
4     | 18d...jkl   | 2           | Newsletter
5     | 18d...mno   | 3           | Quick question

Sequential total:    14s (5 reads)
Parallel estimate:    4s (limited by slowest read)
Potential savings:   10s (71%)

Scaled to 12-email run (18 reads avg):
  Sequential: ~50s
  Parallel:   ~4s
  Savings:    ~46s (92%)

API rate limit: 36/400 = 9% utilization (safe)

Test | Result | Details
-----|--------|--------
T1   | PASS   | 5 sequential reads, avg 2.8s each
T2   | PASS   | All reads are independent
T3   | PASS   | 3.5x speedup potential
T4   | PASS   | 2 threads have multi-message context (avg 1.5 reads/email)
T5   | PASS   | 9% rate limit utilization (well within limits)
```
