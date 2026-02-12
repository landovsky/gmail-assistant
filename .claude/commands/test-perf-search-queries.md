# Test: Optimize Search Query Construction (Solution 6)

Compare different Gmail search query formulations for the Phase B unclassified
email search. Test whether query structure affects performance.
Do NOT modify any data — read-only.

## Context

From `docs/INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md`: The current Phase B search uses
8 separate `-label:` exclusions. Using Gmail search operators more efficiently
(e.g., grouping with OR or using the parent label) might reduce search time.

## Setup

Database: `data/inbox.db` (query via `sqlite3 data/inbox.db "..."`)

Label IDs: needs_response=Label_34, outbox=Label_35, rework=Label_36,
action_required=Label_37, payment_request=Label_38, fyi=Label_39,
waiting=Label_40, done=Label_41

## Test procedure

### T1: Current query timing

**Action:** Record start time (`date +%s`). Run the current Phase B search:

`in:inbox newer_than:30d -label:🤖 AI/Needs Response -label:🤖 AI/Outbox -label:🤖 AI/Rework -label:🤖 AI/Action Required -label:🤖 AI/Payment Requests -label:🤖 AI/FYI -label:🤖 AI/Waiting -label:🤖 AI/Done -in:trash -in:spam`

Record end time and result count.

### T2: Parent label exclusion query

**Action:** Record start time. Test if excluding the parent label covers all children:

`in:inbox newer_than:30d -label:🤖 AI -in:trash -in:spam`

Record end time and result count.

**Note:** This may not work the same way — Gmail parent labels may not automatically
include children in exclusion. Report whether result count matches T1.

### T3: Narrower time window query

**Action:** Record start time. Test with a tighter time window:

`in:inbox newer_than:7d -label:🤖 AI/Needs Response -label:🤖 AI/Outbox -label:🤖 AI/Rework -label:🤖 AI/Action Required -label:🤖 AI/Payment Requests -label:🤖 AI/FYI -label:🤖 AI/Waiting -label:🤖 AI/Done -in:trash -in:spam`

Record end time and result count.

### T4: Result set comparison

**Action:** Compare the result sets:
- `T1_results`: message IDs from the current query
- `T2_results`: message IDs from the parent label query
- `T3_results`: message IDs from the narrower time window

Check:
- Are T2_results a superset/subset of T1_results? (parent label behavior)
- Are T3_results a subset of T1_results? (narrower window should return fewer)

**Assert:**
- If T2 matches T1: parent label exclusion works — simpler query, same results
- If T2 differs: parent label doesn't cover children — keep current approach
- T3 should be a subset of T1 (PASS) or equal if no old unclassified emails exist

### T5: Query complexity impact

**Action:** Summarize timing:
- `current_query_time`: from T1
- `parent_label_time`: from T2
- `narrow_window_time`: from T3
- `fastest_equivalent`: whichever query returns the same results fastest

**Assert:** Report which query formulation is fastest while maintaining correctness.

## Output format

```
Query Variant           | Duration (s) | Results | Correct?
------------------------|-------------|---------|--------
T1: Current (8 exclusions) | 15       | 3       | baseline
T2: Parent label           | 8        | 5       | NO (2 extra)
T3: 7-day window           | 10       | 1       | subset (OK)

Test | Result | Details
-----|--------|--------
T1   | PASS   | Current query: 15s, 3 results
T2   | INFO   | Parent label returns more results (not equivalent)
T3   | PASS   | Narrower window is faster but returns fewer results
T4   | PASS   | T3 is strict subset of T1
T5   | INFO   | No equivalent faster query found; current approach is correct
             | Narrower time window trades completeness for speed
```
