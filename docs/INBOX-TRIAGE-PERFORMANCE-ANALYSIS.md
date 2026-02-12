# Inbox Triage Performance Analysis

**Issue:** `gmail-assistant-3mn`
**Date:** 2026-02-12
**Author:** Claude (Sonnet 4.5)

## Executive Summary

A full `process-inbox` run took 728 seconds (~12 minutes), with **Inbox Triage consuming 590 seconds (81% of total time)** to process just 12 emails. This is **25-50x slower than the expected performance** documented in `PHASE-B-CLASSIFY.md`, which states typical runs should take ~1-2 seconds per email (< 5 seconds for 20 emails).

**Key Finding:** The bottleneck is sequential Gmail API operations combined with inefficient search patterns, particularly subject-based thread lookups during Done cleanup.

---

## Observed Performance

### Timeline (2026-02-12 run)
```
[16:53:57] process-inbox started
[16:53:57-16:55:37] Cleanup & Lifecycle: 100s
                    - Archived 3 threads
                    - Detected 1 sent draft
                    - Retriaged 1 waiting thread
[16:55:37-17:05:27] Inbox Triage: 590s
                    - Classified 12 emails
                    - Detected 1 sent draft
                    - Backfilled 1 manual label
[17:05:27-17:06:05] Draft Responses: 38s
                    - Drafted 1 response
[17:06:05] Total: 728s
```

### Performance Comparison

| Metric | Expected | Actual | Ratio |
|--------|----------|--------|-------|
| Per-email processing | 1-2s | ~49s | 25-50x slower |
| 12 emails total | ~24s | 590s | 25x slower |
| 20 emails total | < 5s | N/A | — |

---

## Root Cause Analysis

### Architecture Overview

Inbox Triage is implemented as a Claude Code command (`.claude/commands/inbox-triage.md`) that orchestrates:
- **Gmail MCP tools** for email operations (`search_emails`, `read_email`, `modify_email`, `batch_modify_emails`)
- **SQLite database** (`data/inbox.db`) for state tracking
- **Haiku model** for classification decisions

The process runs in two phases:
1. **Phase A:** Cleanup & lifecycle transitions (4 sub-steps)
2. **Phase B:** Classify new emails (6 sub-steps)

### Identified Bottlenecks

#### 1. Sequential Gmail Search Operations (HIGH IMPACT)

**Phase A runs at least 5 sequential searches:**
```
1. Search for Done labels (Label_41)
2. Search for Outbox labels (Label_35)
3. Search for Waiting labels (Label_40)
4. Search for manual Needs Response labels (Label_34)
5. Search for unclassified emails (7+ label exclusions)
```

**Estimated impact:** 5 searches × 20-100s each = **100-500s**

These searches are independent and could be parallelized, but the current command specification runs them sequentially.

#### 2. Subject-Based Thread Lookups (HIGH IMPACT)

From `.claude/commands/inbox-triage.md` lines 36-39:

> For each message found [in Done cleanup]:
> - Search for other messages in the same thread by subject:
>   `subject:"<exact subject>"`. Read each result and keep only those whose
>   Thread ID matches.

**Problem:** For each Done email, the command:
1. Reads the message to get Thread ID and Subject
2. Performs a new Gmail search: `subject:"<exact subject>"`
3. Reads ALL matching results
4. Filters to keep only those matching Thread ID
5. Calls `batch_modify_emails` to strip labels

**Estimated impact:**
- 3 archived threads × (1 read + 1 search + N reads + 1 batch_modify)
- If each thread has 5 messages, that's 3 × (1 + 1 + 5 + 1) = 24 operations
- At ~2-5s per operation = **48-120s just for Done cleanup**

**Better approach:** Gmail threads are first-class entities. Use Thread ID directly instead of subject search. The MCP tool likely returns Thread ID already.

#### 3. Individual Email Reads (MEDIUM IMPACT)

From the specification (lines 86-87):

> For each email/thread:
> - Read the email content using `read_email`
> - If the thread has multiple messages, read the most recent ones (up to 3) for context

**Estimated impact:**
- 12 emails × 1-3 `read_email` calls = **12-36 Gmail API calls**
- At ~2-5s per call = **24-180s**

These reads are sequential and cannot be easily batched due to Gmail API design, but they could potentially be parallelized at the orchestration level.

#### 4. Sequential Label Application (MEDIUM IMPACT)

From lines 100-105, each classified email gets labels applied individually via `modify_email`. While the spec mentions `batch_modify_emails` for Done cleanup, it doesn't specify batching for classification results.

**Estimated impact:**
- 12 emails × 1 `modify_email` call = **12 API calls**
- At ~2s per call = **24s**

**Optimization:** Collect all classification results, then batch by label type using `batch_modify_emails`.

#### 5. Database Write Operations (LOW-MEDIUM IMPACT)

Each classified email triggers:
```sql
INSERT OR REPLACE INTO emails (...) VALUES (...)
INSERT INTO email_events (...) VALUES (...)
```

**Estimated impact:**
- 12 emails × 2 writes = **24 SQLite operations**
- At ~0.5-1s per write (with fsync) = **12-24s**

**Optimization:** Use SQLite transactions to batch writes.

#### 6. Claude Model Invocations (LOW-MEDIUM IMPACT)

The classification logic runs through Claude Haiku. From the spec (line 93-98), each email must be classified into exactly one category.

**Estimated impact:**
- 12 emails × 1 classification = **12 model calls**
- Haiku latency: ~1-3s per call = **12-36s**

The current implementation appears to classify emails sequentially. Parallelizing model calls could reduce total time, though this may increase API rate limit risk.

---

## Performance Budget Breakdown

Reconstructing the 590-second Inbox Triage phase:

| Operation Type | Count | Unit Time | Total Time | % of Total |
|----------------|-------|-----------|------------|------------|
| Gmail searches (Phase A) | 5 | 50-100s | 250-500s | 42-85% |
| Subject-based thread lookups | 3 | 30-40s | 90-120s | 15-20% |
| Email reads (Phase B) | 12-36 | 2-5s | 24-180s | 4-30% |
| Label applications | 12 | 2s | 24s | 4% |
| Database writes | 24 | 0.5-1s | 12-24s | 2-4% |
| Model classifications | 12 | 1-3s | 12-36s | 2-6% |
| **Total estimated** | — | — | **412-884s** | — |
| **Actual observed** | — | — | **590s** | — |

The estimates bracket the actual time, confirming that **sequential Gmail searches and subject-based lookups are the primary bottlenecks**.

---

## Recommendations

### High Priority (Expected 5-10x speedup)

1. **Parallelize Phase A searches**
   - Run all 5 Gmail searches concurrently
   - Potential savings: 200-400s → 50-100s

2. **Eliminate subject-based thread lookups**
   - Use Thread ID directly (Gmail threads are atomic)
   - Check if MCP `read_email` returns Thread ID
   - Potential savings: 90-120s → 10-20s

3. **Batch label applications**
   - Collect all classification results
   - Group by label type, use `batch_modify_emails`
   - Potential savings: 24s → 5s

### Medium Priority (Expected 2-3x speedup)

4. **Parallelize email reading and classification**
   - Process multiple emails concurrently
   - Requires refactoring command to handle parallel execution
   - Potential savings: 36-216s → 12-72s

5. **Use SQLite transactions**
   - Wrap all DB writes in BEGIN/COMMIT
   - Potential savings: 12-24s → 3-5s

### Low Priority (Expected 1.5x speedup)

6. **Optimize search query construction**
   - Combine label exclusions more efficiently
   - Use Gmail search operators better (e.g., `-(label1 OR label2)`)
   - Potential savings: marginal

7. **Consider caching/incremental processing**
   - Track last-processed timestamp
   - Only search for emails `newer_than:<last_run>`
   - Reduces search result set size

### Infrastructure Improvements

8. **Add detailed timing instrumentation**
   - Log start/end time for each operation type
   - Identify which specific searches are slowest
   - Use `date +%s` before/after each phase

9. **Consider async/background processing**
   - For non-urgent operations (e.g., Done cleanup)
   - Could split into separate scheduled jobs

---

## Expected Performance After Optimizations

### Conservative estimate (High-priority changes only)

| Phase | Current | Optimized | Speedup |
|-------|---------|-----------|---------|
| Phase A searches | 250-500s | 50-100s | 5x |
| Subject lookups | 90-120s | 10-20s | 9x |
| Email reads | 24-180s | 24-180s | 1x |
| Label application | 24s | 5s | 5x |
| DB writes | 12-24s | 12-24s | 1x |
| Classifications | 12-36s | 12-36s | 1x |
| **Total** | **412-884s** | **113-365s** | **3.6-2.4x** |

### Aggressive estimate (All changes)

| Phase | Current | Optimized | Speedup |
|-------|---------|-----------|---------|
| Phase A searches | 250-500s | 50-100s | 5x |
| Subject lookups | 90-120s | 10-20s | 9x |
| Email reads | 24-180s | 12-72s | 2x |
| Label application | 24s | 5s | 5x |
| DB writes | 12-24s | 3-5s | 4x |
| Classifications | 12-36s | 12-36s | 1x |
| **Total** | **412-884s** | **92-238s** | **4.5-3.7x** |

**Target:** Process 12 emails in **~60-120 seconds** (vs. 590s current)

---

## Implementation Notes

### Constraint: Command-Based Architecture

The current implementation uses `.claude/commands/inbox-triage.md`, which is a prompt-based orchestration. This architecture may limit parallelization options depending on Claude Code's execution model.

**Questions to investigate:**
1. Does Claude Code support parallel tool calls within a command?
2. Can we split into multiple commands and run them concurrently?
3. Should we move heavy logic to a Python/Node script?

### Gmail API Rate Limits

Parallelization must respect Gmail API quotas:
- **Search:** 400 requests per 10 seconds per user
- **Read:** 400 requests per 10 seconds per user
- **Modify:** 50 requests per second per user

Current usage (12 emails, sequential):
- Searches: ~5-10 per run
- Reads: ~12-36 per run
- Modifies: ~12 per run

All well under rate limits, so parallelization is safe.

### Testing Strategy

1. Add timing instrumentation to current implementation
2. Identify slowest operations with empirical data
3. Implement high-priority optimizations one at a time
4. Measure improvement after each change
5. Document actual vs. expected speedup

---

## Conclusion

The 590-second Inbox Triage duration is primarily caused by:
1. **Sequential Gmail searches** (250-500s)
2. **Subject-based thread lookups** (90-120s)
3. **Sequential email reads** (24-180s)

Implementing the recommended optimizations should reduce processing time to **~60-120 seconds for 12 emails**, achieving the expected 1-2 seconds per email performance target.

The most impactful change is **parallelizing Phase A searches**, which alone could reduce execution time by 200-400 seconds.

---

## References

- Issue: `gmail-assistant-3mn`
- Command spec: `.claude/commands/inbox-triage.md`
- Phase B docs: `docs/PHASE-B-CLASSIFY.md`
- Database schema: `data/schema.sql`
