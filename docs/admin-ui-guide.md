# Admin UI & LLM Logging Guide

Complete guide to using the Admin UI for debugging, monitoring, and understanding AI decisions in Gmail Assistant v2.

## Quick Start

**Access:** `http://localhost:8000/admin`

**Prerequisites:**
- Server running: `uv run uvicorn src.main:app --reload`
- Dependencies installed: `uv sync --all-extras`

**Features:**
- ✅ Read-only interface (safe for production)
- ✅ Full LLM call history with prompts/responses
- ✅ Email classification reasoning
- ✅ Audit trail of all state transitions
- ✅ Token usage and cost monitoring
- ✅ Performance analysis (latency tracking)

---

## Views Overview

### 📧 Emails

**Purpose:** Primary debugging interface for email processing

**List Columns:**
- ID, User ID, Subject, Sender Email
- Classification (needs_response, action_required, payment_request, fyi, waiting)
- Resolved Style (business, casual, friendly)
- Status (pending, drafted, rework_requested, sent, skipped, archived)
- Confidence (high, medium, low)
- Received At

**Detail View Shows:**
- All email metadata (thread_id, message_id, sender info)
- Full classification reasoning (why the LLM chose this category)
- Language detection
- Message count (for threads)
- Draft tracking (draft_id, rework_count, last instruction)
- Payment request fields (vendor_name for invoices)
- All timestamps (received, processed, drafted, acted)

**Search:**
- By subject, sender email, or Gmail thread ID

**Use Cases:**
- "Why was this email classified as FYI instead of needs_response?"
- "What reasoning did the AI use for this classification?"
- "Which emails are stuck in rework status?"

---

### 🧠 LLM Calls

**Purpose:** Debug AI decisions and monitor LLM usage

**List Columns:**
- ID, User ID, Gmail Thread ID
- Call Type (classify, draft, rework, context)
- Model (e.g., anthropic/claude-haiku-4)
- Total Tokens (prompt + completion)
- Latency (milliseconds)
- Error (if failed)
- Created At

**Detail View Shows:**
- **System Prompt:** Full system instructions sent to the LLM
- **User Message:** Complete user prompt (email content, context, etc.)
- **Response Text:** Full LLM response
- **Token Breakdown:** Prompt tokens, completion tokens, total
- **Latency:** Request duration in milliseconds
- **Error Details:** If the call failed

**Search:**
- By Gmail thread ID, call type, or model

**Use Cases:**
- "What exact prompt was sent to classify this email?"
- "Why did the draft include/exclude certain information?"
- "How much did this classification cost in tokens?"
- "Why is drafting taking so long for this thread?"

---

### 📋 Email Events

**Purpose:** Audit trail of all email state transitions

**List Columns:**
- ID, User ID, Gmail Thread ID
- Event Type (classified, label_added, draft_created, etc.)
- Detail (human-readable description)
- Created At

**Event Types:**
- `classified` - Email was classified
- `label_added` - Gmail label applied
- `label_removed` - Gmail label removed
- `draft_created` - AI draft generated
- `draft_trashed` - Old draft deleted
- `draft_reworked` - User requested changes
- `sent_detected` - Email was sent
- `archived` - Email archived
- `rework_limit_reached` - Max rework attempts hit
- `waiting_retriaged` - Waiting email re-evaluated
- `error` - Processing error occurred

**Search:**
- By Gmail thread ID or event type

**Use Cases:**
- "What happened to this email after classification?"
- "When was the draft created?"
- "Did the label get applied successfully?"
- "What errors occurred during processing?"

---

### 👤 Users

**Purpose:** View user accounts and status

**Shows:** Email, display name, active status, onboarding date

---

### 🏷️ User Labels

**Purpose:** View Gmail label mappings

**Shows:** User ID, label key (e.g., "needs_response"), Gmail label ID, Gmail label name

---

### ⚙️ User Settings

**Purpose:** View per-user configuration

**Shows:** User ID, setting key, created date (values are JSON, visible in detail view)

---

### 🔄 Sync State

**Purpose:** Monitor Gmail sync status

**Shows:** User ID, last history ID, last sync timestamp, watch expiration

---

### 📝 Jobs

**Purpose:** View background job queue

**Shows:** Job type, user ID, status (pending/running/completed/failed), attempts, error message, timestamps

---

## Common Workflows

### 🔍 Investigate Classification Issue

**Scenario:** Email was classified incorrectly

1. Navigate to **Emails** view
2. Search for the email (by subject, sender, or thread ID)
3. Click the email row to open detail view
4. Review:
   - Classification (what it was labeled as)
   - Confidence (LLM's certainty)
   - Reasoning (why this category was chosen)
   - Detected Language
5. Click **LLM Calls** in the navigation
6. Search for the Gmail thread ID
7. Find the `classify` call
8. In detail view, examine:
   - System prompt (classification instructions)
   - User message (email content sent to LLM)
   - Response text (raw LLM output)
9. Check **Email Events** for the thread to see if labels were applied

**What to Look For:**
- Is the reasoning sound? Or did the LLM misunderstand?
- Does the email content match what was sent to the LLM?
- Was there an error in the LLM call?
- Did automated header detection override the LLM decision?

---

### ✍️ Debug Draft Quality

**Scenario:** Generated draft is inappropriate or missing context

1. Navigate to **Emails**, find the thread
2. Check the email's:
   - Classification (should be `needs_response`)
   - Status (should be `drafted`)
   - Resolved Style (business/casual/friendly)
   - Draft ID (Gmail draft ID)
3. Go to **LLM Calls**
4. Search by Gmail thread ID
5. Find the `draft` call (or `rework` if user requested changes)
6. In detail view, inspect:
   - **System Prompt:**
     - Contains the communication style config
     - Instructions for tone, length, format
   - **User Message:**
     - Sender info and subject
     - Thread history
     - User instructions (if manual draft)
     - Related context (if context gathering enabled)
   - **Response Text:**
     - The actual draft content before the ✂️ marker
7. Compare with the actual Gmail draft
8. Check **Email Events** for:
   - `draft_created` - when it was generated
   - `draft_trashed` - if old drafts were removed
   - `draft_reworked` - if user requested changes

**What to Look For:**
- Is the style config correct for this sender?
- Was context gathered? (check for `context` call type)
- Did user instructions get included properly?
- Is the LLM response different from the Gmail draft? (indicates post-processing issue)

---

### 📊 Monitor Token Usage

**Scenario:** Track LLM costs and identify optimization opportunities

1. Navigate to **LLM Calls**
2. Sort by **Total Tokens** (descending)
3. Identify high-token calls
4. For each expensive call:
   - Click to view detail
   - Check prompt length (system + user)
   - Review if all context is necessary
   - Note the call type and model

**Optimization Tips:**
- `classify` calls should be cheap (using Haiku)
- `draft` calls are more expensive (using Sonnet) but should still be reasonable
- `context` calls can be expensive if gathering too much
- Check if prompts include unnecessary information

**SQL Queries for Analysis:**

```sql
-- Total tokens by call type (last 7 days)
SELECT call_type,
       COUNT(*) as calls,
       SUM(total_tokens) as tokens,
       AVG(total_tokens) as avg_tokens
FROM llm_calls
WHERE created_at > datetime('now', '-7 days')
GROUP BY call_type;

-- Most expensive threads
SELECT gmail_thread_id,
       COUNT(*) as llm_calls,
       SUM(total_tokens) as total_tokens
FROM llm_calls
WHERE gmail_thread_id IS NOT NULL
GROUP BY gmail_thread_id
ORDER BY total_tokens DESC
LIMIT 20;

-- Daily token usage trend
SELECT DATE(created_at) as date,
       COUNT(*) as calls,
       SUM(total_tokens) as tokens
FROM llm_calls
WHERE created_at > datetime('now', '-30 days')
GROUP BY DATE(created_at)
ORDER BY date;
```

---

### ⚡ Investigate Performance Issues

**Scenario:** LLM calls are taking too long

1. Navigate to **LLM Calls**
2. Sort by **Latency** (descending)
3. Identify slow calls (> 5-10 seconds is concerning)
4. For each slow call:
   - Note the call type and model
   - Check total tokens (more tokens = longer processing)
   - Review timestamp (when did it occur?)
   - Check error field (did it fail?)

**Common Causes:**
- Large prompts (high token count)
- API rate limiting or throttling
- Network issues
- LLM provider performance

**SQL Queries:**

```sql
-- Slowest calls
SELECT call_type, model, gmail_thread_id,
       total_tokens, latency_ms, created_at
FROM llm_calls
WHERE latency_ms > 5000  -- > 5 seconds
ORDER BY latency_ms DESC;

-- Average latency by call type
SELECT call_type,
       COUNT(*) as calls,
       AVG(latency_ms) as avg_latency,
       MAX(latency_ms) as max_latency
FROM llm_calls
GROUP BY call_type;

-- Correlation: tokens vs latency
SELECT
    CASE
        WHEN total_tokens < 1000 THEN '< 1K'
        WHEN total_tokens < 5000 THEN '1K-5K'
        WHEN total_tokens < 10000 THEN '5K-10K'
        ELSE '> 10K'
    END as token_range,
    COUNT(*) as calls,
    AVG(latency_ms) as avg_latency
FROM llm_calls
GROUP BY token_range;
```

---

### ❌ Track LLM Failures

**Scenario:** Some LLM calls are failing

1. Navigate to **LLM Calls**
2. Click on the **Error** column header to show non-null first
3. Review failed calls:
   - Error message (what went wrong?)
   - Call type (which operation failed?)
   - Timestamp (when did it fail?)
   - User ID / Thread ID (affected email)

**Check:**
- Email Events for the same thread (was it retried?)
- Application logs for more context
- Pattern: Is it always the same call type or model?

---

## Database Schema Reference

### llm_calls Table

```sql
CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    gmail_thread_id TEXT,
    call_type TEXT NOT NULL,  -- classify, draft, rework, context
    model TEXT NOT NULL,
    system_prompt TEXT,
    user_message TEXT,
    response_text TEXT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_llm_calls_thread` on `gmail_thread_id`
- `idx_llm_calls_type` on `call_type`
- `idx_llm_calls_user` on `user_id`
- `idx_llm_calls_created` on `created_at`

### emails Table (Key Fields)

```sql
CREATE TABLE emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    gmail_thread_id TEXT UNIQUE NOT NULL,
    gmail_message_id TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    subject TEXT,
    classification TEXT NOT NULL,  -- needs_response, action_required, etc.
    confidence TEXT DEFAULT 'medium',
    reasoning TEXT,  -- LLM explanation
    detected_language TEXT DEFAULT 'cs',
    resolved_style TEXT DEFAULT 'business',
    status TEXT DEFAULT 'pending',
    draft_id TEXT,
    rework_count INTEGER DEFAULT 0,
    -- ... timestamps
);
```

### email_events Table

```sql
CREATE TABLE email_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    gmail_thread_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT,
    label_id TEXT,
    draft_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Programmatic Access

### Python API (Repository Pattern)

```python
from src.db.models import LLMCallRepository, EmailRepository, EventRepository
from src.db.connection import get_db

db = get_db()

# LLM Calls
call_repo = LLMCallRepository(db)
calls = call_repo.get_by_thread("thread_123")
stats = call_repo.get_stats(user_id=1)

# Emails
email_repo = EmailRepository(db)
email = email_repo.get_by_thread(user_id=1, thread_id="thread_123")
pending = email_repo.get_pending_drafts(user_id=1)

# Events
event_repo = EventRepository(db)
events = event_repo.get_thread_events(user_id=1, thread_id="thread_123")
```

### Direct SQL (Read-Only Connection)

```python
import sqlite3

conn = sqlite3.connect('data/gmail_assistant.db', check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.execute("SELECT * FROM llm_calls WHERE gmail_thread_id = ?", ("thread_123",))
calls = [dict(row) for row in cursor.fetchall()]
```

---

## Tips & Best Practices

### 🎯 Efficient Debugging

1. **Start with Admin UI** - Fastest way to see the full picture
2. **Use Thread ID** - Correlates emails, events, and LLM calls
3. **Check timestamps** - Understand the sequence of events
4. **Read reasoning** - LLM often explains its decision clearly

### 🔍 Advanced Queries

Combine SQL queries across tables:

```sql
-- Find emails where classification took a long time
SELECT e.gmail_thread_id, e.subject, e.classification,
       l.latency_ms, l.total_tokens
FROM emails e
JOIN llm_calls l ON e.gmail_thread_id = l.gmail_thread_id
WHERE l.call_type = 'classify' AND l.latency_ms > 3000;

-- Draft quality: check if context was gathered
SELECT e.gmail_thread_id, e.subject,
       COUNT(CASE WHEN l.call_type = 'context' THEN 1 END) as context_calls,
       COUNT(CASE WHEN l.call_type = 'draft' THEN 1 END) as draft_calls
FROM emails e
LEFT JOIN llm_calls l ON e.gmail_thread_id = l.gmail_thread_id
WHERE e.status = 'drafted'
GROUP BY e.gmail_thread_id;
```

### 🚫 What NOT to Do

- ❌ Don't modify data through the Admin UI (read-only by design)
- ❌ Don't rely solely on logs - use the Admin UI for structured data
- ❌ Don't ignore the reasoning field - it often explains unexpected classifications

---

## Troubleshooting

### Admin UI Not Loading

**Check:**
1. Server is running: `curl http://localhost:8000/health`
2. Dependencies installed: `uv sync --all-extras`
3. Migration applied: Check `data/gmail_assistant.db` for `llm_calls` table

**Solution:**
```bash
# Reinstall dependencies
uv sync --all-extras

# Restart server
uv run uvicorn src.main:app --reload
```

### No LLM Calls Showing

**Reasons:**
1. No emails processed yet
2. LLM gateway not configured with call_repo
3. Database migration not applied

**Check:**
```sql
SELECT COUNT(*) FROM llm_calls;  -- Should return > 0 if calls logged
```

### Slow Admin UI

**Common Cause:** Large dataset without indexes

**Solution:**
```sql
-- Verify indexes exist
SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='llm_calls';

-- Should show:
-- idx_llm_calls_thread
-- idx_llm_calls_type
-- idx_llm_calls_user
-- idx_llm_calls_created
```

---

## Next Steps

- 📖 [Debugging Workflow](../artifacts/debugging-workflow-beads-grafana-bugsink-audit.md) - Complete debugging guide
- 🏗️ [Architecture Overview](../artifacts/project-overview.md) - System design
- 🧪 [Testing Conventions](../artifacts/testing-conventions.md) - Test guidelines
- 📊 [Database Conventions](../artifacts/database-conventions.md) - Schema patterns
