# Parallel Email Reads Implementation

**Issue:** `gmail-assistant-9o7`
**Date:** 2026-02-12
**Implemented by:** Claude (Sonnet 4.5)

## Summary

Implemented parallel email reading and batch label application in Phase B classification to reduce inbox triage time from ~590s to potentially <200s for typical 12-email runs.

## Changes Made

### 1. Updated `inbox-triage.md` Command (Phase B)

**File:** `.claude/commands/inbox-triage.md`

**Key Changes:**

- **Step 6:** Changed from sequential `read_email` calls to parallel batch reads
  - Added instruction: "Make a single message with parallel `read_email` tool calls"
  - Added explicit warning: "Do NOT read emails sequentially"
  - Performance gain: ~83s → ~6s for 12 emails (93% reduction)

- **Step 6b:** Added blacklist filtering step after parallel reads
  - Moved from per-email check to batch filtering after all reads complete
  - More efficient than checking during sequential reads

- **Step 7:** Updated classification to be in-memory batch operation
  - Group results by classification type for batch label application

- **Step 8:** Changed from individual `modify_email` to `batch_modify_emails`
  - One API call per classification group instead of one per email
  - Performance gain: ~24s → ~10s for 12 emails (58% reduction)
  - Uses existing `batch_modify_emails` tool from GMAIL_WRITE toolset

### 2. Updated `phase-b-classify.md` Command

**File:** `.claude/commands/phase-b-classify.md`

**Key Changes:**

- Restructured processing steps to emphasize parallel execution
- Added performance optimization notes at the top
- Split into 7 clear steps with parallel processing highlighted
- Added critical warnings about using parallel tool calls vs sequential

### 3. Configuration

**File:** `.beads/config.yaml`

- Added `issue-prefix: "gmail-assistant"` to fix beads CLI issues

## Performance Impact

Based on testing documented in `docs/INBOX-TRIAGE-PERF-TEST-RESULTS.md`:

| Operation | Before | After | Savings |
|-----------|--------|-------|---------|
| Email reads (12 emails) | ~83s sequential | ~6s parallel | ~77s (93%) |
| Label applications (12 emails) | ~24s individual | ~10s batched | ~14s (58%) |
| **Total Phase B improvement** | ~590s | **~200s** | **~390s (66%)** |

Note: The 590s baseline includes ~400s of LLM overhead (reasoning time), which is not addressed by this optimization. The parallel reads optimization primarily addresses API latency.

## How It Works

### Before (Sequential)

```
For each email in results:
  1. read_email(message_id) → 6s
  2. classify(content) → 3s
  3. modify_email(message_id, label) → 2s
  4. store_in_db() → 0.01s
  # Total: ~11s per email × 12 = ~132s
  # Plus LLM overhead: ~38s per iteration × 12 = ~456s
  # Grand total: ~588s
```

### After (Parallel)

```
# Step 1: Parallel reads (one message, multiple tool calls)
results = parallel_read_emails([msg1, msg2, ..., msg12]) → ~6s

# Step 2: Batch classify in memory
classifications = classify_batch(results) → ~36s (one LLM call)

# Step 3: Batch apply labels (one call per group)
batch_modify_emails(needs_response_ids, Label_34) → ~2s
batch_modify_emails(fyi_ids, Label_39) → ~2s
batch_modify_emails(action_required_ids, Label_37) → ~2s
... (total ~10s for 5 groups)

# Step 4: Store in DB
store_all_in_db(classifications) → ~0.2s

# Total: ~52s (92% faster than 588s)
```

Note: This optimistic calculation assumes batch classification works perfectly. In practice, Claude Code may still need multiple LLM turns, so real savings may be ~390s (66%) rather than ~536s (92%).

## Implementation Notes

### Critical Requirements

1. **Parallel Tool Calls**
   - Claude Code must make parallel `read_email` calls in a SINGLE message
   - Syntax: Multiple `<invoke name="mcp__gmail__read_email">` blocks in one response
   - Do NOT loop with sequential tool calls

2. **Batch Label Application**
   - Must use `batch_modify_emails` tool (already in GMAIL_WRITE toolset)
   - Group message IDs by classification before applying labels
   - Do NOT call `modify_email` individually for each email

3. **Memory-Based Classification**
   - Store all read results in memory before classifying
   - Do NOT make API calls during classification (use in-memory pattern matching)
   - Blacklist filtering happens after reads, before classification

### Tool Availability

These tools are already configured in `bin/common.sh`:

```bash
GMAIL_READ="mcp__gmail__search_emails mcp__gmail__read_email mcp__gmail__list_email_labels"
GMAIL_WRITE="mcp__gmail__modify_email mcp__gmail__batch_modify_emails"
```

### API Rate Limits

Gmail API limits: 400 requests per 10 seconds

- Typical run: 12 emails → ~14 parallel reads
- Utilization: 14/400 = 3.5% (well within limits)
- Safe to parallelize even for 50+ emails

## Testing

### Test Command

Use the existing test command to validate parallel read performance:

```bash
/test-perf-parallel-reads
```

This measures:
- Sequential read latency (5 samples)
- Parallelization potential
- API rate limit headroom
- Expected savings for full inbox triage run

### Manual Testing

To test the full implementation:

1. Run inbox triage with the updated commands:
   ```bash
   /inbox-triage
   ```

2. Monitor the execution:
   - Verify parallel `read_email` calls happen in one message
   - Verify `batch_modify_emails` is used instead of individual `modify_email` calls
   - Measure total Phase B duration

3. Compare with baseline (from `INBOX-TRIAGE-PERF-TEST-RESULTS.md`):
   - Baseline: ~590s for 12 emails
   - Target: <250s for 12 emails (58% improvement)

## Future Optimizations

This implementation addresses Solutions #4 and #3 from the performance analysis:

- ✅ **Solution 4:** Parallelize email reads
- ✅ **Solution 3:** Batch label applications

Remaining high-impact optimizations:

- **Solution 7:** Incremental processing (use `after:` filter based on last run)
  - Issue: `gmail-assistant-7ii`
  - Potential: 77% fewer emails to process
  - Compounds with parallel reads

- **Solution 2:** Eliminate subject-based thread lookups (Phase A Done cleanup)
  - Potential: Eliminates 95% overhead on recurring subjects
  - Use Thread ID from initial `read_email` instead of searching by subject

## Related Files

- Command definitions:
  - `.claude/commands/inbox-triage.md`
  - `.claude/commands/phase-b-classify.md`

- Performance analysis:
  - `docs/INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md`
  - `docs/INBOX-TRIAGE-PERF-TEST-RESULTS.md`

- Test commands:
  - `.claude/commands/test-perf-parallel-reads.md`
  - `.claude/commands/test-perf-batch-labels.md`

- Database schema:
  - `data/schema.sql`

- Configuration:
  - `config/label_ids.yml` (Gmail label mappings)
  - `config/contacts.yml` (blacklist and style overrides)

## Backward Compatibility

The Python script at `bin/classify-phase-b` is now DEPRECATED. It was an incomplete prototype that doesn't actually integrate with MCP tools.

Use these commands instead:
- `/inbox-triage` - Full inbox triage (includes Phase A, B, C)
- `/phase-b-classify` - Phase B only (classify new emails)

Both commands now use the parallel processing implementation.
