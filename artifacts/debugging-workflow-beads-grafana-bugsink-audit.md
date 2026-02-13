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

### Admin UI (SQLAdmin)

**Location:** `http://localhost:8000/admin`

The Admin UI provides a read-only web interface for debugging all system data, with special focus on LLM decisions and email processing.

#### Key Features

**Email View** - Primary debugging interface
- Shows: subject, sender, classification, style, status, confidence
- Searchable by: subject, sender, thread_id
- Detail view includes: full reasoning, all timestamps, rework history
- Related data: links to all events and LLM calls for the thread

**LLM Call View** - Debug AI decisions
- Shows: call_type, model, tokens, latency, error
- Searchable by: thread_id, call_type, model
- Detail view includes: full system prompt, user message, complete response
- Call types: `classify`, `draft`, `rework`, `context`

**Email Event View** - Audit trail
- Shows: thread_id, event_type, detail, timestamp
- Searchable by: thread_id, event_type
- Chronological timeline of all state transitions

**Other Views**
- Users, Labels, Settings, Sync State, Jobs

#### Common Workflows

**Debug Classification Decision**
1. Navigate to Emails, search for subject/sender
2. Click email to see classification + reasoning
3. Click "LLM Calls" tab to see full classify prompt and response
4. Review Events tab for state transition history

**Debug Draft Quality**
1. Find email in Emails view
2. Check Events for draft_created timestamp
3. View LLM Calls filtered by thread_id
4. Find `draft` or `rework` call type
5. Inspect full system prompt (includes style config)
6. Review user message (includes context if gathered)
7. Compare response_text with Gmail draft

**Track Token Usage**
1. Navigate to LLM Calls view
2. Sort by total_tokens descending
3. Filter by date range using created_at
4. Identify expensive operations
5. Review prompts for optimization opportunities

**Investigate Failures**
1. Filter LLM Calls by non-null error
2. Review error messages and latency
3. Check if retries succeeded
4. Correlate with Events for impact

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

### LLM Call Logging (llm_calls table)

The `llm_calls` table tracks every LLM API call with full context for debugging AI decisions and monitoring costs.

```python
# Query LLM calls for a thread
calls = await call_repo.get_by_thread(thread_id="thread123")
# Each call: {call_type, model, system_prompt, user_message, response_text,
#            prompt_tokens, completion_tokens, total_tokens, latency_ms, error}

# Get token usage statistics
stats = await call_repo.get_stats(user_id=1)
# Returns: {call_count, total_prompt_tokens, total_completion_tokens,
#          total_tokens, avg_latency_ms}
```

**Call types**: `classify`, `draft`, `rework`, `context`

```sql
-- Direct SQL for investigation

-- All LLM calls for a thread (with full prompts)
SELECT call_type, model, prompt_tokens, completion_tokens, latency_ms,
       system_prompt, user_message, response_text, error, created_at
FROM llm_calls
WHERE gmail_thread_id = 'thread123'
ORDER BY created_at;

-- Recent expensive calls (token-heavy)
SELECT call_type, model, gmail_thread_id, total_tokens, latency_ms, created_at
FROM llm_calls
WHERE total_tokens > 5000
ORDER BY created_at DESC
LIMIT 20;

-- Failed LLM calls
SELECT call_type, model, gmail_thread_id, error, latency_ms, created_at
FROM llm_calls
WHERE error IS NOT NULL
ORDER BY created_at DESC;

-- Average tokens per call type
SELECT call_type,
       COUNT(*) as call_count,
       AVG(total_tokens) as avg_tokens,
       AVG(latency_ms) as avg_latency_ms
FROM llm_calls
WHERE created_at > datetime('now', '-7 days')
GROUP BY call_type;

-- Token usage by user (last 30 days)
SELECT user_id,
       COUNT(*) as total_calls,
       SUM(total_tokens) as total_tokens,
       SUM(prompt_tokens) as prompt_tokens,
       SUM(completion_tokens) as completion_tokens
FROM llm_calls
WHERE created_at > datetime('now', '-30 days')
GROUP BY user_id
ORDER BY total_tokens DESC;

-- Slow LLM calls (potential issues)
SELECT call_type, model, gmail_thread_id, latency_ms,
       total_tokens, error, created_at
FROM llm_calls
WHERE latency_ms > 10000  -- > 10 seconds
ORDER BY latency_ms DESC;
```

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
- **Check Admin UI** (`http://localhost:8000/admin`) - fastest way to see email/LLM/events
- Check application logs (local or Grafana)
- Query email_events and llm_calls tables for affected threads
- Analyze Stacktrace
- Identify Root Cause
- Create Beads Issue

### Quick Admin UI Debugging

For most issues, start with the Admin UI:

**Email not classified correctly?**
1. Admin → Emails → search subject
2. View classification + reasoning
3. Click to LLM Calls, find `classify` call
4. Review system prompt and user message
5. Check if reasoning explains the decision

**Draft quality issues?**
1. Admin → Emails → find thread
2. Check Events for draft creation
3. Go to LLM Calls, filter by thread_id
4. Find `draft` or `rework` call
5. Inspect full prompt (includes style + context)
6. Compare response with actual draft

**Performance investigation?**
1. Admin → LLM Calls → sort by latency_ms
2. Identify slow calls
3. Check token counts (correlates with latency)
4. Review prompts for optimization

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
