# Test: Use SQLite Transactions (Solution 5)

Compare individual INSERT performance vs batched transactions in SQLite.
Uses a temporary test table to avoid modifying production data.

## Context

From `docs/INBOX-TRIAGE-PERFORMANCE-ANALYSIS.md`: Each classified email triggers
2 SQLite writes (emails + email_events). With 12 emails, that's 24 individual
writes at ~0.5-1s each. Wrapping in a transaction could reduce this to 3-5s total.

## Setup

Database: `data/inbox.db` (query via `sqlite3 data/inbox.db "..."`)

## Test procedure

### T1: Current write pattern measurement

**Action:** Create a temporary test table, then measure individual INSERT performance:

```bash
# Create temp table
sqlite3 data/inbox.db "CREATE TABLE IF NOT EXISTS _perf_test (id INTEGER PRIMARY KEY, val TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP);"

# Time 10 individual inserts
START=$(date +%s%N)
for i in $(seq 1 10); do
  sqlite3 data/inbox.db "INSERT INTO _perf_test (val) VALUES ('test_$i');"
done
END=$(date +%s%N)
echo "Individual: $(( (END - START) / 1000000 ))ms for 10 inserts"
```

**Assert:** Record the total time for 10 individual inserts.

### T2: Transaction-batched write measurement

**Action:** Measure the same 10 inserts wrapped in a single transaction:

```bash
START=$(date +%s%N)
sqlite3 data/inbox.db "BEGIN; $(for i in $(seq 11 20); do echo "INSERT INTO _perf_test (val) VALUES ('test_$i');"; done) COMMIT;"
END=$(date +%s%N)
echo "Transaction: $(( (END - START) / 1000000 ))ms for 10 inserts"
```

**Assert:** Record the total time for 10 transactional inserts.

### T3: Speedup calculation

**Action:** Calculate:
- `individual_time`: from T1
- `transaction_time`: from T2
- `speedup`: individual_time / transaction_time
- Scaled to real workload: 24 writes (12 emails x 2 tables)

**Assert:** PASS if speedup > 1 (transactions are faster).

### T4: Current DB write volume

**Action:** Query the DB to understand the actual write volume per triage run:
```sql
SELECT date(created_at) as day, COUNT(*) as events
FROM email_events
WHERE created_at >= date('now', '-7 days')
GROUP BY date(created_at)
ORDER BY day DESC
```

Also count emails table writes:
```sql
SELECT date(processed_at) as day, COUNT(*) as emails_processed
FROM emails
WHERE processed_at >= date('now', '-7 days')
GROUP BY date(processed_at)
ORDER BY day DESC
```

**Assert:** Report daily write volumes. This validates the performance analysis
estimate of ~24 writes per run.

### T5: Cleanup

**Action:** Drop the temporary test table:
```bash
sqlite3 data/inbox.db "DROP TABLE IF EXISTS _perf_test;"
```

**Assert:** PASS if cleanup succeeds.

## Output format

```
Metric                     | Value
---------------------------|------
Individual inserts (10x)   | 120ms
Transaction inserts (10x)  | 15ms
Speedup                    | 8.0x
Per-insert (individual)    | 12ms
Per-insert (transaction)   | 1.5ms

Scaled to real workload (24 writes/run):
  Current estimate:  24 x 12ms  = 288ms
  Optimized:         24 x 1.5ms =  36ms (in one transaction)
  Savings:           252ms

Recent DB write volume:
  Date       | Events | Emails
  2026-02-12 | 15     | 12
  2026-02-11 | 20     | 18

Test | Result | Details
-----|--------|--------
T1   | PASS   | 10 individual inserts: 120ms
T2   | PASS   | 10 transaction inserts: 15ms
T3   | PASS   | 8.0x speedup with transactions
T4   | PASS   | ~24 writes per run confirmed
T5   | PASS   | Temp table cleaned up
```
