# Inbox Triage Performance Test Results

**Issue:** `gmail-assistant-3mn`
**Date:** 2026-02-12
**Tested by:** Claude (Opus 4.6)

## Summary

Seven performance tests were run against the live Gmail inbox and local SQLite database to validate the optimization opportunities identified in the [initial analysis](INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md). The results reveal that **the original analysis significantly overestimated search overhead** and identified the true bottleneck: the per-email read+classify+label+DB loop.

| Solution | Verdict | Estimated Impact | Notes |
|----------|---------|-----------------|-------|
| 1. Parallelize Phase A searches | Low | ~27s saved (5% of 590s) | Searches are fast; loop is the bottleneck |
| 2. Eliminate subject-based lookups | **High** | ~60+ wasted API calls eliminated | 95% overhead on recurring subjects |
| 3. Batch label applications | Medium | 12 calls → 5 calls (~14s saved) | Easy win, already have `batch_modify_emails` |
| 4. Parallelize email reads | **High** | ~77s saved (93% of read time) | Biggest single optimization |
| 5. SQLite transactions | Negligible | 93ms → 1ms | DB is not the bottleneck |
| 6. Optimize search queries | **None** | 0s | Parent-label exclusion is incorrect |
| 7. Incremental processing | **High** | 77% fewer emails to process | Compounds with #4 |

**Revised bottleneck:** The 590s inbox triage is dominated by the **sequential per-email processing loop** (~49s/email × 12 emails ≈ 590s), not by searches (~36s total). Each iteration includes: read_email (~6s) + LLM classification (~3s) + modify_email (~2s) + sqlite (~0.01s) + LLM overhead (~38s).

---

## Test 1: Parallelize Phase A Searches

**Goal:** Measure individual search latency to quantify parallelization benefit.

```
Search | Duration (s) | Results | Notes
-------|-------------|---------|------
S1     | 8           | 7       | label:🤖 AI/Done
S2     | 6           | 1       | label:🤖 AI/Outbox
S3     | 6           | 0       | label:🤖 AI/Waiting
S4     | 7           | 1       | label:🤖 AI/Needs Response (30d)
S5     | 9           | 49      | Unclassified inbox (30d, 8 exclusions)

Sequential total:     36s
Parallel estimate:     9s (limited by S5)
Potential savings:    27s (75% of search time, but only 5% of total 590s)
```

**Verdict: LOW IMPACT.** Searches total only 36s — not the 250-500s originally estimated. The original analysis overestimated because it attributed the full step duration to searches, when most time is actually spent in the per-email processing loop that follows.

**Caveat:** Durations include LLM round-trip overhead (~3-5s per measurement). Raw Gmail API latency is likely 1-3s per search.

---

## Test 2: Eliminate Subject-Based Thread Lookups

**Goal:** Verify Thread ID is available from `read_email` and quantify subject-search waste.

```
Test | Result | Details
-----|--------|--------
T1   | PASS   | Thread ID field present: '19c41ee291ca8dd4'
T2   | PASS   | Subject "ADMIN: chybí denní importy": 20 results, 1 matched target thread
T3   | PASS   | Thread IDs consistent within threads (verified on 3 threads)
T4   | PASS   | 19 of 20 reads wasted (95% overhead) for recurring subjects
T5   | PASS   | Savings: 1 search + 19 read_email calls per recurring-subject thread
```

**Key finding:** The "ADMIN: chybí denní importy" subject returned **20 results across 20 different Thread IDs**. Only 1 matched the target — 19 reads (95%) were completely wasted. For unique subjects the waste is 0%, but automated/recurring emails create severe overhead.

**Verdict: HIGH IMPACT.** Thread ID is already available from the initial `read_email` call, making subject search entirely redundant. Eliminates 1 search + N wasted reads per thread during Done cleanup.

---

## Test 3: Batch Label Applications

**Goal:** Quantify the benefit of grouping `modify_email` calls into `batch_modify_emails`.

```
Classification     | Count | Individual calls | Batch calls
-------------------|-------|-----------------|------------
fyi                | 92    | 92              | 1
action_required    | 29    | 29              | 1
needs_response     | 4     | 4               | 1
invoice            | 1     | 1               | 1
waiting            | 1     | 1               | 1
Total (7d)         | 127   | 127             | 5
```

For the 12-email run specifically: 12 individual calls → ~5 batch calls (one per classification group). At ~2s per API call, this saves ~14s.

**Tool availability:** `batch_modify_emails` is already in `GMAIL_WRITE` toolset (`bin/common.sh` line 8). No infrastructure changes needed.

**Verdict: MEDIUM IMPACT.** Easy win — just collect classifications first, then batch-apply labels by group. Saves ~14s per 12-email run.

---

## Test 4: Parallelize Email Reading and Classification

**Goal:** Measure per-read latency and quantify parallelization potential.

```
Email | Duration (s) | Subject (truncated)
------|-------------|--------------------------------------------
1     | 6.66        | Duplicitní čísla zakázek v DUB
2     | 6.18        | Nezmeškej únorové slevy!
3     | 5.47        | MŠ Zprávičky
4     | 5.68        | StandardError: User marek.novak@...
5     | 5.77        | Let's meet in person in Prague

Sequential total:    29.8s (5 reads)
Parallel estimate:    6.7s (limited by slowest)
Potential savings:   23.1s (78%)

Scaled to 12-email run (14 reads, avg 1.2/email):
  Sequential: ~83s
  Parallel:   ~6s
  Savings:    ~77s (93%)

API rate limit: 14/400 = 4% (safe)
```

**Verdict: HIGH IMPACT.** This is the largest single optimization. Reading 12 emails sequentially takes ~83s; reading them all in parallel takes ~6s. The 5.95s average per read includes LLM tool-dispatch overhead.

**Constraint:** Classification must happen after reading, but reads are fully independent. A two-phase approach (parallel reads → parallel classifications) could work.

---

## Test 5: SQLite Transactions

**Goal:** Measure individual vs. batched write performance.

```
Method                  | 10 inserts | Per insert
------------------------|-----------|----------
Individual sqlite3 calls | 93ms      | 9.3ms
Single transaction       | 1ms       | 0.1ms
Speedup                 | 93x       | —

Write volumes (7d): 335 events, 127 emails processed
```

**Verdict: NEGLIGIBLE.** Even individual inserts are <10ms each. The 93x speedup (93ms → 1ms for 10 inserts) is impressive in isolation but irrelevant in a pipeline where Gmail API calls take 6,000ms each. Total DB time per 12-email run: ~240ms individual, ~2.4ms batched. Savings: 0.24s.

Transactions are still worth using for **atomicity** (mutation + audit log in one commit), but not for performance.

---

## Test 6: Optimize Search Query Construction

**Goal:** Test whether simpler queries (parent label, narrower time window) perform faster.

```
Query Variant                | Duration (s) | Results | Correct?
-----------------------------|-------------|---------|----------
Current (8 child exclusions) | 8.05        | 90      | YES (baseline)
Parent label only            | 8.87        | 100+    | NO (extra results!)
7-day window                 | 9.25        | 90      | YES (today)
```

**Critical finding:** `-label:🤖 AI` does **NOT** exclude child labels. Emails labeled `🤖 AI/Done` or `🤖 AI/FYI` but without the parent label itself are NOT excluded. The simplified query returns **extra results** (already-triaged emails), making it **incorrect**.

**Verdict: NO BENEFIT.** The current 8-exclusion query is both correct and performs identically to simpler alternatives (~8-9s, within API jitter). Query complexity has zero measurable impact on Gmail search latency.

---

## Test 7: Caching / Incremental Processing

**Goal:** Measure how much work is avoided by scanning only new emails since last run.

```
Metric                          | Value
--------------------------------|------
Last processed at               | 2026-02-12 16:02:37
Full scan (newer_than:30d)      | 96 results in ~9s
Incremental scan (after:02/12)  | 22 results in ~10s
Result reduction                | 77% (96 → 22)

Already processed (30d):        127 emails
Label exclusion filtering:      57% of inbox filtered by existing AI labels

Phase A events (7d):
  archived:           13 (~1.9/day)
  sent_detected:       3 (~0.4/day)
  waiting_retriaged:   1 (~0.1/day)
```

**Key insight:** The search itself isn't faster (Gmail API latency floor: ~8-9s regardless of result count). The savings come from **processing fewer results downstream**: 74 fewer emails × ~49s/email = potentially **~60 minutes saved** if all 74 would have been classified.

**Caveat:** Gmail `after:` has day-level granularity only (not hour-level). First run of the day still scans everything from that day. Most benefit is across multi-day gaps.

**Verdict: HIGH IMPACT** when combined with Solution 4 (parallel reads). Fewer emails to read+classify = proportionally less time.

---

## Revised Performance Model

The original analysis estimated search overhead at 250-500s. Actual measurements show searches take only ~36s. The revised model:

| Operation | Count | Unit Time | Total | % of 590s |
|-----------|-------|-----------|-------|-----------|
| Gmail searches (Phase A) | 5 | ~7s | ~36s | 6% |
| Per-email processing loop | 12 | ~45s | ~540s | 91% |
| — read_email | 12-14 | ~6s | ~80s | 14% |
| — LLM classification | 12 | ~3s | ~36s | 6% |
| — modify_email (labels) | 12 | ~2s | ~24s | 4% |
| — DB writes | 24 | ~0.01s | ~0.2s | 0% |
| — LLM overhead (reasoning, tool dispatch) | 12 | ~33s | ~400s | 68% |
| Misc overhead | — | — | ~14s | 2% |
| **Total** | — | — | **~590s** | **100%** |

**The dominant cost is LLM overhead** — the time Claude spends reasoning about each email, deciding tool calls, and generating text between API operations. This is ~400s (68%) of the total and is largely invisible in per-operation timing.

---

## Recommended Optimization Priority

### Tier 1: Highest Impact (implement first)

1. **Parallelize email reads** (Solution 4)
   - Savings: ~77s (read time), potentially more from batched classification
   - Approach: Read all emails in parallel, then classify in batch

2. **Incremental processing** (Solution 7)
   - Savings: 77% fewer emails to process
   - Approach: Track last-processed timestamp, use `after:` filter

3. **Eliminate subject-based lookups** (Solution 2)
   - Savings: eliminates wasted API calls in Done cleanup
   - Approach: Use Thread ID from `read_email` directly

### Tier 2: Easy Wins

4. **Batch label applications** (Solution 3)
   - Savings: ~14s
   - Approach: Collect results, one `batch_modify_emails` per label type

### Tier 3: Architectural (addresses root cause)

5. **Reduce LLM overhead** (not in original 7 solutions)
   - The biggest cost (68%) is LLM reasoning time between tool calls
   - Possible approaches:
     - Move to a script-based pipeline (Python/Node) instead of LLM orchestration
     - Pre-format email data to minimize LLM reasoning per email
     - Batch-classify multiple emails in a single LLM call
     - Use structured output to reduce generation time

### Not Recommended

6. ~~Optimize search queries~~ (Solution 6) — No benefit, current query is optimal
7. ~~SQLite transactions~~ (Solution 5) — Negligible performance impact (use for atomicity only)
8. ~~Parallelize searches~~ (Solution 1) — Only 5% of total time; not worth the complexity

---

## Key Takeaway

**The original analysis was wrong about the bottleneck.** Gmail searches are fast (~7s each). The real cost is the sequential per-email loop where the LLM reads, reasons about, classifies, labels, and logs each email one at a time. The LLM overhead alone (~33s/email) dwarfs all API latency combined.

The highest-ROI optimization is **batch processing**: read all emails in parallel, present them to the LLM in a single batch for classification, then apply labels and DB writes in bulk. This attacks both the API latency (parallel reads) and the LLM overhead (one reasoning pass instead of twelve).
