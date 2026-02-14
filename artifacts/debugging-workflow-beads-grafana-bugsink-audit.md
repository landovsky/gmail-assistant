# Production Debugging Workflow

A systematic approach to debugging production issues using BugSink error tracking, Beads task management, and application logs.

## Core Principles

1. **Use Beads for ALL bug tracking** - Never use TaskCreate, TodoWrite, or markdown files
2. **Always create a beads issue BEFORE writing code** - Establish tracking first
3. **Link BugSink URLs in issue descriptions** - Maintain traceability
4. **Commit with good context** - Include root cause, fix, and BugSink URL
5. **Test before closing** - Verify the fix handles the edge case

---

## Tools

### Audit Log (email_events table)

The `email_events` table serves as an immutable audit log for all email state transitions.

```python
# Query audit events for a thread
events = await event_repo.get_by_thread(user_id=1, thread_id="thread123")
# Each event: {event_type, detail, label_id, draft_id, created_at}
```

**Event types**: `classified`, `label_added`, `label_removed`, `draft_created`, `draft_trashed`, `rework_requested`, `status_changed`, `error`

```sql
-- Direct SQL for investigation
SELECT * FROM email_events
WHERE gmail_thread_id = 'thread123'
ORDER BY created_at DESC;

-- Recent errors
SELECT * FROM email_events
WHERE event_type = 'error'
ORDER BY created_at DESC
LIMIT 20;

-- Classification history for a user
SELECT gmail_thread_id, detail, created_at
FROM email_events
WHERE user_id = 1 AND event_type = 'classified'
ORDER BY created_at DESC;
```

### Debug API (JSON — for AI/programmatic debugging)

The debug API provides structured JSON access to all email-related data, designed for AI-assisted and programmatic debugging.

```bash
# List emails with search/filter — returns event/LLM/agent counts per email
curl "http://localhost:8000/api/debug/emails?q=invoice&status=pending&limit=20"

# Full debug dump for a specific email — includes timeline and summary
curl "http://localhost:8000/api/emails/42/debug"
```

**`GET /api/debug/emails`** query params: `?status=`, `?classification=`, `?q=` (full-text), `?limit=` (1–500)

**`GET /api/emails/{id}/debug`** response structure:
- `email` — full email record (all columns)
- `events` — audit events for the thread (chronological)
- `llm_calls` — all LLM API calls with full prompts, responses, token counts
- `agent_runs` — agent execution logs with tool call history
- `timeline` — merged chronological view of all three data sources
- `summary` — pre-computed: total tokens, total latency, error count, LLM breakdown by call type

**Typical AI debugging workflow:**
1. `GET /api/debug/emails?q=<search>` to find the email
2. `GET /api/emails/{id}/debug` to get the full debug dump
3. Inspect `summary.errors` for quick error overview
4. Walk `timeline` for chronological processing sequence
5. Drill into `llm_calls[].system_prompt` / `user_message` / `response_text` for LLM decision inspection

### Debug UI (HTML)

Browser-based debug views at `/debug/emails` (list) and `/debug/email/{id}` (detail).
The email list in SQLAdmin (`/admin`) also links to debug pages via the ID column.

### BugSink Error Tracking CLI

**Note:** Issues and Events are READ-ONLY via the API. Write operations (marking as resolved) must be done manually in the web UI.

**Location:** `bugsink`

#### Getting Issue Details

```bash
# Get issue summary
bugsink issues get <issue-uuid> --json

# Output includes:
# - calculated_type (error class)
# - calculated_value (error message + snippet)
# - transaction (handler name)
# - digested_event_count (occurrence frequency)
# - first_seen / last_seen (dates)
```

#### Accessing Events and Stacktraces

```bash
# List all events for an issue
bugsink events list --issue=<issue-uuid> --json

# Get specific event details (includes full stacktrace)
bugsink events get <event-uuid> --json

# Extract stacktrace frames (application code only)
bugsink events get <event-uuid> --json | \
  jq '.data.exception.values[0].stacktrace.frames[] |
      select(.in_app == true) |
      {filename, function, lineno, context_line}'
```

#### Known API Issues

**Problem:** `bugsink events stacktrace <uuid>` returns 500 error

**Workaround:** Use `bugsink events get <uuid> --json` and extract with `jq`:
```bash
bugsink events get <uuid> --json | \
  jq '.data.exception.values[0].stacktrace.frames[]'
```

---

## Application Logs

### Log Format
```
%(asctime)s %(levelname)s %(name)s: %(message)s
```

### Log Locations
- **Local**: `logs/` directory
- **Docker**: `docker compose logs -f app`
- **Log level**: Configurable via `GMA_SERVER_LOG_LEVEL` (default: info)

### Common Log Searches
```bash
# Recent errors
grep "ERROR" logs/*.log | tail -20

# Classification failures
grep "classify.*error\|classify.*failed" logs/*.log

# Draft generation issues
grep "draft.*error\|draft.*failed" logs/*.log

# Worker job failures
grep "Job.*failed\|retry" logs/*.log
```

---

## Grafana Logs

### Querying Logs via HTTP API

Use grafana-curl command that wraps bash -c and checks for relevant env variables.

```bash
grafana-curl --help

# Basic query
grafana-curl --query '{app="${GRAFANA_APP_NAME}"} |= "error"' \
  --start "$(date -u -v-1H +%s)000000000" \
  --end "$(date -u +%s)000000000"

# Query with JQ filter
grafana-curl --query '{app="${GRAFANA_APP_NAME}"} |= "Processing"' \
  --start "1707123000000000000" \
  --end "1707126600000000000" \
  --limit 5000 \
  --jq '.data.result[].values[] | .[1]'
```

### Time Ranges
```bash
--start "$(date -u -v-1H +%s)000000000"   # Last hour
--start "$(date -u -v-6H +%s)000000000"   # Last 6 hours
--start "$(date -u -v-24H +%s)000000000"  # Last 24 hours
```

## Systematic Debugging Process

Use common sense and best practices.

Common methodology (override if justifiable):

- Fetch Error Details
- Use Debug API (`/api/emails/{id}/debug`) to get full context for an email — this is the fastest way to see the complete processing history, LLM decisions, and errors in one place
- Check application logs (local or Grafana)
- Query email_events audit table for affected threads (or use Debug API timeline)
- Analyze Stacktrace
- Identify Root Cause
- Create Beads Issue

**Stop here and report if**
- you don't have high confidence in root cause analysis
- if bug suggests bad architecture

## Implementing Fix

1. Run full test suite (assume something was already broken)

2. If issue is in code, write a test that confirms the issue.

3. Implement fix

4. Run the test to verify if the issue is gone.

If test fails, review your hypothesis and repeat.

Ensure test suite runs successfully (with exception of already present bugs), BUT watch out for regression.

## Finalizing

- Commit with Context
- Close Issue and Push unless instructed otherwise or if you have reservations about the root cause or bug fix approaches
