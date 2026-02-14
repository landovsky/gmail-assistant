"""Debug routes — unified email debugging view."""

from __future__ import annotations

import html
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from src.db.connection import get_db
from src.db.models import AgentRunRepository, EventRepository, JobRepository, LLMCallRepository

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_email_debug_data(email_id: int) -> dict:
    """Collect all debug data for an email by its row ID."""
    db = get_db()

    # Fetch the email record
    email = db.execute_one("SELECT * FROM emails WHERE id = ?", (email_id,))
    if not email:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")

    user_id = email["user_id"]
    thread_id = email["gmail_thread_id"]

    # Fetch related data
    events = EventRepository(db).get_thread_events(user_id, thread_id)
    llm_calls = LLMCallRepository(db).get_by_thread(thread_id)
    agent_runs = AgentRunRepository(db).get_by_thread(user_id, thread_id)

    return {
        "email": dict(email),
        "events": [dict(e) for e in events],
        "llm_calls": [dict(c) for c in llm_calls],
        "agent_runs": [dict(r) for r in agent_runs],
    }


def _build_timeline(events: list[dict], llm_calls: list[dict], agent_runs: list[dict]) -> list:
    """Merge events, LLM calls, and agent runs into a single chronological timeline."""
    items = []
    for ev in events:
        items.append(
            {
                "time": ev.get("created_at"),
                "type": "event",
                "event_type": ev.get("event_type"),
                "detail": ev.get("detail"),
                "label_id": ev.get("label_id"),
                "draft_id": ev.get("draft_id"),
                "source_id": ev.get("id"),
            }
        )
    for lc in llm_calls:
        items.append(
            {
                "time": lc.get("created_at"),
                "type": "llm_call",
                "call_type": lc.get("call_type"),
                "model": lc.get("model"),
                "total_tokens": lc.get("total_tokens", 0),
                "latency_ms": lc.get("latency_ms", 0),
                "error": lc.get("error"),
                "source_id": lc.get("id"),
            }
        )
    for ar in agent_runs:
        items.append(
            {
                "time": ar.get("created_at"),
                "type": "agent_run",
                "profile": ar.get("profile"),
                "status": ar.get("status"),
                "iterations": ar.get("iterations", 0),
                "error": ar.get("error"),
                "completed_at": ar.get("completed_at"),
                "source_id": ar.get("id"),
            }
        )
    items.sort(key=lambda x: x.get("time") or "")
    return items


def _build_summary(
    email: dict, events: list[dict], llm_calls: list[dict], agent_runs: list[dict]
) -> dict:
    """Pre-compute summary statistics for AI consumption."""
    total_tokens = sum(c.get("total_tokens", 0) for c in llm_calls)
    total_latency = sum(c.get("latency_ms", 0) for c in llm_calls)
    errors = [e for e in events if e.get("event_type") == "error"]
    llm_errors = [c for c in llm_calls if c.get("error")]
    agent_errors = [r for r in agent_runs if r.get("status") == "error"]

    call_types: dict = {}
    for c in llm_calls:
        ct = c.get("call_type", "unknown")
        if ct not in call_types:
            call_types[ct] = {"count": 0, "tokens": 0, "latency_ms": 0}
        call_types[ct]["count"] += 1
        call_types[ct]["tokens"] += c.get("total_tokens", 0)
        call_types[ct]["latency_ms"] += c.get("latency_ms", 0)

    return {
        "email_id": email.get("id"),
        "gmail_thread_id": email.get("gmail_thread_id"),
        "classification": email.get("classification"),
        "status": email.get("status"),
        "event_count": len(events),
        "llm_call_count": len(llm_calls),
        "agent_run_count": len(agent_runs),
        "total_tokens": total_tokens,
        "total_latency_ms": total_latency,
        "error_count": len(errors) + len(llm_errors) + len(agent_errors),
        "errors": {
            "events": [{"id": e.get("id"), "detail": e.get("detail")} for e in errors],
            "llm_calls": [
                {"id": c.get("id"), "call_type": c.get("call_type"), "error": c.get("error")}
                for c in llm_errors
            ],
            "agent_runs": [
                {"id": r.get("id"), "profile": r.get("profile"), "error": r.get("error")}
                for r in agent_errors
            ],
        },
        "llm_breakdown": call_types,
        "rework_count": email.get("rework_count", 0),
    }


def _build_email_list_filters(
    status: str | None, classification: str | None, q: str | None
) -> tuple[list[str], list]:
    """Build WHERE conditions and params for the email list query."""
    conditions: list[str] = []
    params: list = []

    if status:
        conditions.append("e.status = ?")
        params.append(status)
    if classification:
        conditions.append("e.classification = ?")
        params.append(classification)
    if q:
        # Full-text search across subject, snippet, reasoning, sender,
        # thread ID, and LLM call content (which contains email body)
        conditions.append(
            """(e.subject LIKE ? COLLATE NOCASE
                OR e.snippet LIKE ? COLLATE NOCASE
                OR e.reasoning LIKE ? COLLATE NOCASE
                OR e.sender_email LIKE ? COLLATE NOCASE
                OR e.gmail_thread_id LIKE ?
                OR EXISTS (
                    SELECT 1 FROM llm_calls lc
                    WHERE lc.gmail_thread_id = e.gmail_thread_id
                      AND lc.user_message LIKE ? COLLATE NOCASE
                ))"""
        )
        like = f"%{q}%"
        params.extend([like, like, like, like, like, like])

    return conditions, params


# ---------------------------------------------------------------------------
# JSON API endpoints
# ---------------------------------------------------------------------------


@router.get("/api/emails/{email_id}/debug")
async def email_debug_api(email_id: int) -> dict:
    """JSON API: all debug data for an email.

    Returns the email record, related events, LLM calls, agent runs,
    a merged chronological timeline, and pre-computed summary statistics.
    Designed for programmatic / AI-assisted debugging.
    """
    data = _get_email_debug_data(email_id)
    data["timeline"] = _build_timeline(data["events"], data["llm_calls"], data["agent_runs"])
    data["summary"] = _build_summary(
        data["email"], data["events"], data["llm_calls"], data["agent_runs"]
    )
    return data


@router.get("/api/debug/emails")
async def email_list_api(
    status: str | None = None,
    classification: str | None = None,
    q: str | None = None,
    limit: int = 50,
) -> dict:
    """JSON API: list emails with search, filter, and per-email debug counts.

    Query params:
        status: Filter by email status (pending, drafted, sent, etc.)
        classification: Filter by classification (needs_response, fyi, etc.)
        q: Full-text search across subject, snippet, reasoning, sender,
           thread ID, and email body content (via LLM call user_message)
        limit: Max results (default 50, max 500)
    """
    db = get_db()
    limit = min(max(limit, 1), 500)

    conditions, params = _build_email_list_filters(status, classification, q)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    emails = db.execute(
        f"""SELECT e.*, u.email as user_email,
                   (SELECT COUNT(*) FROM email_events ev
                    WHERE ev.gmail_thread_id = e.gmail_thread_id
                      AND ev.user_id = e.user_id) as event_count,
                   (SELECT COUNT(*) FROM llm_calls lc
                    WHERE lc.gmail_thread_id = e.gmail_thread_id) as llm_call_count,
                   (SELECT COUNT(*) FROM agent_runs ar
                    WHERE ar.gmail_thread_id = e.gmail_thread_id
                      AND ar.user_id = e.user_id) as agent_run_count
            FROM emails e
            LEFT JOIN users u ON u.id = e.user_id
            {where}
            ORDER BY e.id DESC
            LIMIT ?""",
        (*params, limit),
    )

    return {
        "count": len(emails),
        "limit": limit,
        "filters": {
            "status": status,
            "classification": classification,
            "q": q,
        },
        "emails": [dict(em) for em in emails],
    }


@router.post("/api/emails/{email_id}/reclassify")
async def reclassify_email(email_id: int) -> dict:
    """Force reclassification of an email by enqueuing a classify job with force=True."""
    db = get_db()
    email = db.execute_one("SELECT * FROM emails WHERE id = ?", (email_id,))
    if not email:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")

    message_id = email["gmail_message_id"]
    if not message_id:
        raise HTTPException(status_code=400, detail="Email has no Gmail message ID")

    jobs = JobRepository(db)
    job_id = jobs.enqueue(
        "classify",
        email["user_id"],
        {"message_id": message_id, "force": True},
    )

    logger.info("Enqueued reclassify job %d for email %d (thread %s)",
                job_id, email_id, email["gmail_thread_id"])

    return {
        "status": "queued",
        "job_id": job_id,
        "email_id": email_id,
        "current_classification": email["classification"],
    }


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------


@router.get("/debug/emails", response_class=HTMLResponse)
async def email_list_page(
    status: str | None = None,
    classification: str | None = None,
    q: str | None = None,
) -> HTMLResponse:
    """Email list page with links to debug views."""
    db = get_db()

    conditions, params = _build_email_list_filters(status, classification, q)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    emails = db.execute(
        f"""SELECT e.*, u.email as user_email,
                   (SELECT COUNT(*) FROM email_events ev
                    WHERE ev.gmail_thread_id = e.gmail_thread_id
                      AND ev.user_id = e.user_id) as event_count,
                   (SELECT COUNT(*) FROM llm_calls lc
                    WHERE lc.gmail_thread_id = e.gmail_thread_id) as llm_call_count
            FROM emails e
            LEFT JOIN users u ON u.id = e.user_id
            {where}
            ORDER BY e.id DESC
            LIMIT 200""",
        tuple(params),
    )

    return HTMLResponse(_render_email_list(emails, status, classification, q))


@router.get("/debug/email/{email_id}", response_class=HTMLResponse)
async def email_debug_page(email_id: int) -> HTMLResponse:
    """Unified email debug page — all related data on one screen."""
    data = _get_email_debug_data(email_id)
    return HTMLResponse(_render_debug_page(data))


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

_CSS = """\
:root {
  --bg: #0f1117; --surface: #1a1d27; --surface2: #242833;
  --border: #2e3341; --text: #e1e4ed; --text2: #8b90a0;
  --accent: #6c8cff; --green: #4ade80; --yellow: #facc15;
  --red: #f87171; --orange: #fb923c; --purple: #a78bfa;
  --cyan: #22d3ee;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
       background:var(--bg); color:var(--text); font-size:13px; line-height:1.5; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }

.container { max-width:1400px; margin:0 auto; padding:16px 24px; }

/* Top nav */
.topnav { background:var(--surface); border-bottom:1px solid var(--border);
           padding:10px 24px; display:flex; align-items:center; gap:16px;
           position:sticky; top:0; z-index:100; }
.topnav h1 { font-size:15px; font-weight:600; color:var(--accent); }
.topnav a { color:var(--text2); font-size:12px; }
.topnav a:hover { color:var(--text); }
.topnav button { background:var(--accent); color:#fff; border:none;
  padding:4px 10px; border-radius:4px; cursor:pointer; font-size:11px;
  font-family:inherit; }
.topnav button:hover { opacity:0.9; }

/* Header card */
.email-header { background:var(--surface); border:1px solid var(--border);
                 border-radius:8px; padding:20px; margin-bottom:16px; }
.email-header h2 { font-size:16px; margin-bottom:8px; font-weight:600; }
.meta-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));
             gap:8px 16px; margin-top:12px; }
.meta-item { display:flex; flex-direction:column; }
.meta-label { font-size:11px; color:var(--text2); text-transform:uppercase;
              letter-spacing:0.5px; }
.meta-value { font-size:13px; color:var(--text); word-break:break-all; }

/* Badges */
.badge { display:inline-block; padding:2px 8px; border-radius:4px;
         font-size:11px; font-weight:600; text-transform:uppercase; }
.badge-needs_response { background:#1e3a5f; color:#60a5fa; }
.badge-action_required { background:#3b1f1f; color:var(--orange); }
.badge-payment_request { background:#3b2f1f; color:var(--yellow); }
.badge-fyi { background:#1a2e1a; color:var(--green); }
.badge-waiting { background:#2d1f3b; color:var(--purple); }
.badge-pending { background:#2d2d1f; color:var(--yellow); }
.badge-drafted { background:#1e3a5f; color:#60a5fa; }
.badge-sent { background:#1a2e1a; color:var(--green); }
.badge-archived { background:#1f1f2d; color:var(--text2); }
.badge-skipped { background:#1f1f2d; color:var(--text2); }
.badge-rework_requested { background:#3b2f1f; color:var(--orange); }
.badge-high { background:#1a2e1a; color:var(--green); }
.badge-medium { background:#2d2d1f; color:var(--yellow); }
.badge-low { background:#3b1f1f; color:var(--red); }
.badge-error { background:#3b1f1f; color:var(--red); }
.badge-completed { background:#1a2e1a; color:var(--green); }
.badge-running { background:#1e3a5f; color:#60a5fa; }
.badge-classify { background:#2d1f3b; color:var(--purple); }
.badge-draft { background:#1e3a5f; color:#60a5fa; }
.badge-rework { background:#3b2f1f; color:var(--orange); }
.badge-context { background:#1f2d2d; color:var(--cyan); }
.badge-agent { background:#2d1f3b; color:var(--purple); }

/* Section panels */
.section { background:var(--surface); border:1px solid var(--border);
           border-radius:8px; margin-bottom:16px; overflow:hidden; }
.section-header { padding:12px 16px; border-bottom:1px solid var(--border);
                  display:flex; align-items:center; justify-content:space-between;
                  cursor:default; }
.section-header h3 { font-size:13px; font-weight:600; }
.section-count { font-size:11px; color:var(--text2); background:var(--surface2);
                 padding:2px 8px; border-radius:10px; }

/* Timeline */
.timeline { padding:0 16px 16px; }
.tl-item { display:grid; grid-template-columns:90px 28px 1fr; gap:0;
           min-height:48px; }
.tl-time { font-size:11px; color:var(--text2); padding-top:14px; text-align:right;
           padding-right:12px; }
.tl-line { position:relative; display:flex; justify-content:center; }
.tl-line::before { content:''; position:absolute; top:0; bottom:0;
                   width:2px; background:var(--border); }
.tl-dot { width:10px; height:10px; border-radius:50%; background:var(--accent);
          position:relative; top:16px; z-index:1; }
.tl-dot.event { background:var(--green); }
.tl-dot.llm { background:var(--purple); }
.tl-dot.agent { background:var(--cyan); }
.tl-dot.error { background:var(--red); }
.tl-body { padding:8px 0 8px 12px; }
.tl-title { font-size:12px; font-weight:600; }
.tl-detail { font-size:11px; color:var(--text2); margin-top:2px; }

/* Tables */
table { width:100%; border-collapse:collapse; }
th { text-align:left; font-size:11px; color:var(--text2); text-transform:uppercase;
     letter-spacing:0.5px; padding:8px 12px; border-bottom:1px solid var(--border);
     background:var(--surface2); }
td { padding:8px 12px; border-bottom:1px solid var(--border); font-size:12px;
     vertical-align:top; }
tr:last-child td { border-bottom:none; }
tr:hover td { background:var(--surface2); }

/* Expandable text */
.expandable { position:relative; }
.expand-toggle { color:var(--accent); cursor:pointer; font-size:11px;
                 user-select:none; }
.expand-content { display:none; margin-top:6px; background:var(--bg);
                  border:1px solid var(--border); border-radius:4px;
                  padding:8px 10px; white-space:pre-wrap; word-break:break-word;
                  font-size:11px; max-height:400px; overflow-y:auto; }
.expand-content.open { display:block; }

/* Email list */
.filter-bar { display:flex; gap:8px; align-items:center; flex-wrap:wrap;
              margin-bottom:16px; }
.filter-bar input, .filter-bar select { background:var(--surface); border:1px solid var(--border);
  color:var(--text); padding:6px 10px; border-radius:4px; font-size:12px;
  font-family:inherit; }
.filter-bar input { min-width:250px; }
.filter-bar select { min-width:140px; }
.filter-bar button { background:var(--accent); color:#fff; border:none;
  padding:6px 14px; border-radius:4px; cursor:pointer; font-size:12px;
  font-family:inherit; }
.filter-bar button:hover { opacity:0.9; }
.filter-bar .reset { background:transparent; color:var(--text2); border:1px solid var(--border); }

/* Reasoning box */
.reasoning-box { background:var(--bg); border:1px solid var(--border);
                 border-radius:4px; padding:10px 12px; margin-top:8px;
                 font-size:12px; white-space:pre-wrap; line-height:1.6; }

/* Two-column layout for detail page */
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media (max-width: 900px) { .two-col { grid-template-columns:1fr; } }

/* Empty state */
.empty { padding:24px; text-align:center; color:var(--text2); font-size:12px; }
"""

_JS = """\
function toggle(id) {
  var el = document.getElementById(id);
  el.classList.toggle('open');
  var btn = el.previousElementSibling;
  if (btn) {
    var label = btn.textContent.replace(/^[▸▾]\\s/, '');
    btn.textContent = el.classList.contains('open') ? '▾ ' + label : '▸ ' + label;
  }
}
function toggleAll(rowId, expand) {
  var row = document.getElementById(rowId);
  if (!row) return;
  var contents = row.querySelectorAll('.expand-content');
  var toggles = row.querySelectorAll('.expand-toggle');
  contents.forEach(function(el) {
    if (expand) el.classList.add('open');
    else el.classList.remove('open');
  });
  toggles.forEach(function(btn) {
    var label = btn.textContent.replace(/^[▸▾]\\s/, '');
    btn.textContent = expand ? '▾ ' + label : '▸ ' + label;
  });
}
function applyFilters() {
  var q = document.getElementById('q').value;
  var s = document.getElementById('status-filter').value;
  var c = document.getElementById('class-filter').value;
  var params = new URLSearchParams();
  if (q) params.set('q', q);
  if (s) params.set('status', s);
  if (c) params.set('classification', c);
  var qs = params.toString();
  window.location.href = '/debug/emails' + (qs ? '?' + qs : '');
}
function resetFilters() { window.location.href = '/debug/emails'; }
async function triggerFullSync() {
  if (!confirm('Trigger a full sync? This will clear sync state and scan the entire inbox.')) return;
  try {
    var res = await fetch('/api/sync?full=true&user_id=1', {method: 'POST'});
    var data = await res.json();
    alert('Full sync queued successfully!');
  } catch (err) {
    alert('Failed to trigger sync: ' + err.message);
  }
}
async function reclassifyEmail(emailId) {
  if (!confirm('Force reclassification of this email? This will re-run the LLM classifier.')) return;
  var btn = document.getElementById('reclassify-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Queued…'; }
  try {
    var res = await fetch('/api/emails/' + emailId + '/reclassify', {method: 'POST'});
    var data = await res.json();
    if (res.ok) {
      alert('Reclassify job queued (job #' + data.job_id + '). Refresh the page to see results.');
    } else {
      alert('Failed: ' + (data.detail || 'unknown error'));
      if (btn) { btn.disabled = false; btn.textContent = 'Reclassify'; }
    }
  } catch (err) {
    alert('Failed to trigger reclassification: ' + err.message);
    if (btn) { btn.disabled = false; btn.textContent = 'Reclassify'; }
  }
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && document.activeElement.id === 'q') applyFilters();
});
"""


def _e(text: str | None) -> str:
    """HTML-escape."""
    if text is None:
        return '<span style="color:var(--text2)">—</span>'
    return html.escape(str(text))


def _badge(value: str | None) -> str:
    if not value:
        return "—"
    cls = value.lower().replace(" ", "_")
    return f'<span class="badge badge-{_e(cls)}">{_e(value)}</span>'


def _time_short(ts: str | None) -> str:
    """Format timestamp for timeline display."""
    if not ts:
        return "—"
    # Already a string from SQLite — show time portion
    s = str(ts)
    if "T" in s:
        return s.split("T")[1][:8]
    if " " in s:
        return s.split(" ")[1][:8]
    return s[:8]


def _truncate(text: str | None, length: int = 80) -> str:
    if not text:
        return ""
    s = str(text)
    if len(s) <= length:
        return _e(s)
    return _e(s[:length]) + "…"


def _render_email_list(
    emails: list[dict], status: str | None, classification: str | None, q: str | None
) -> str:
    rows = ""
    for em in emails:
        eid = em["id"]
        rows += f"""<tr>
          <td><a href="/debug/email/{eid}">#{eid}</a></td>
          <td>{_e(em.get("user_email", ""))}</td>
          <td><a href="/debug/email/{eid}">{_truncate(em.get("subject"), 60)}</a></td>
          <td>{_e(em.get("sender_email", ""))}</td>
          <td>{_badge(em.get("classification"))}</td>
          <td>{_badge(em.get("status"))}</td>
          <td>{_badge(em.get("confidence"))}</td>
          <td style="text-align:center">{em.get("event_count", 0)}</td>
          <td style="text-align:center">{em.get("llm_call_count", 0)}</td>
          <td>{_e(em.get("received_at"))}</td>
        </tr>"""

    if not emails:
        rows = '<tr><td colspan="10" class="empty">No emails found.</td></tr>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Email Debug</title>
<style>{_CSS}</style></head><body>
<div class="topnav">
  <h1>Email Debug</h1>
  <a href="/debug/emails">All Emails</a>
  <a href="/admin">SQLAdmin</a>
  <button onclick="triggerFullSync()">Full Sync</button>
</div>
<div class="container">
  <div class="filter-bar">
    <input id="q" type="text" placeholder="Search subject, body, sender, thread ID…"
           value="{_e(q or "")}">
    <select id="status-filter">
      <option value="">All draft statuses</option>
      {
        "".join(
            f'<option value="{s}"{" selected" if status == s else ""}>{s}</option>'
            for s in ["pending", "drafted", "rework_requested", "sent", "skipped", "archived"]
        )
    }
    </select>
    <select id="class-filter">
      <option value="">All classifications</option>
      {
        "".join(
            f'<option value="{c}"{" selected" if classification == c else ""}>{c}</option>'
            for c in ["needs_response", "action_required", "payment_request", "fyi", "waiting"]
        )
    }
    </select>
    <button onclick="applyFilters()">Filter</button>
    <button class="reset" onclick="resetFilters()">Reset</button>
  </div>
  <div class="section">
    <table>
      <thead><tr>
        <th>ID</th><th>User</th><th>Subject</th><th>Sender</th>
        <th>Classification</th><th>Draft Status</th><th>Confidence</th>
        <th>Events</th><th>LLM</th><th>Received</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>
<script>{_JS}</script>
</body></html>"""


def _render_debug_page(data: dict) -> str:
    email = data["email"]
    events = data["events"]
    llm_calls = data["llm_calls"]
    agent_runs = data["agent_runs"]
    eid = email["id"]

    # --- Build timeline ---
    timeline_items = []
    for ev in events:
        dot_cls = "error" if ev.get("event_type") == "error" else "event"
        timeline_items.append(
            {
                "time": ev.get("created_at", ""),
                "dot_cls": dot_cls,
                "title": f"Event: {ev.get('event_type', '')}",
                "detail": ev.get("detail") or "",
                "type": "event",
            }
        )
    for lc in llm_calls:
        timeline_items.append(
            {
                "time": lc.get("created_at", ""),
                "dot_cls": "error" if lc.get("error") else "llm",
                "title": f"LLM: {lc.get('call_type', '')} ({lc.get('model', '')})",
                "detail": f"{lc.get('total_tokens', 0)} tokens, {lc.get('latency_ms', 0)}ms"
                + (f" — error: {lc.get('error')}" if lc.get("error") else ""),
                "type": "llm",
            }
        )
    for ar in agent_runs:
        timeline_items.append(
            {
                "time": ar.get("created_at", ""),
                "dot_cls": "error" if ar.get("status") == "error" else "agent",
                "title": f"Agent: {ar.get('profile', '')}",
                "detail": f"{ar.get('iterations', 0)} iterations, status={ar.get('status', '')}",
                "type": "agent",
            }
        )

    timeline_items.sort(key=lambda x: x["time"] or "", reverse=True)

    tl_html = ""
    for item in timeline_items:
        tl_html += f"""<div class="tl-item">
          <div class="tl-time">{_time_short(item["time"])}</div>
          <div class="tl-line"><div class="tl-dot {item["dot_cls"]}"></div></div>
          <div class="tl-body">
            <div class="tl-title">{_e(item["title"])}</div>
            <div class="tl-detail">{_e(item["detail"])}</div>
          </div>
        </div>"""

    if not timeline_items:
        tl_html = '<div class="empty">No timeline entries.</div>'

    # --- Events table ---
    ev_rows = ""
    for ev in events:
        ev_rows += f"""<tr>
          <td>{ev.get("id", "")}</td>
          <td>{_badge(ev.get("event_type"))}</td>
          <td>{_e(ev.get("detail"))}</td>
          <td>{_e(ev.get("label_id"))}</td>
          <td>{_e(ev.get("draft_id"))}</td>
          <td>{_e(ev.get("created_at"))}</td>
        </tr>"""
    if not events:
        ev_rows = '<tr><td colspan="6" class="empty">No events recorded.</td></tr>'

    # --- LLM calls table ---
    llm_rows = ""
    for i, lc in enumerate(llm_calls):
        exp_id = f"llm-{lc.get('id', i)}"
        row_id = f"llm-row-{lc.get('id', i)}"
        error_cell = (
            f'<span style="color:var(--red)">{_e(lc.get("error"))}</span>'
            if lc.get("error")
            else "—"
        )
        llm_rows += f"""<tr id="{row_id}">
          <td>{lc.get("id", "")}</td>
          <td>{_badge(lc.get("call_type"))}</td>
          <td>{_e(lc.get("model"))}</td>
          <td>{lc.get("prompt_tokens", 0)}</td>
          <td>{lc.get("completion_tokens", 0)}</td>
          <td>{lc.get("total_tokens", 0)}</td>
          <td>{lc.get("latency_ms", 0)}ms</td>
          <td>{error_cell}</td>
          <td>{_e(lc.get("created_at"))}</td>
          <td class="expandable">
            <div style="margin-bottom:6px;">
              <button onclick="toggleAll('{row_id}', true)" style="background:var(--surface2); color:var(--text2); border:1px solid var(--border); padding:2px 6px; border-radius:3px; cursor:pointer; font-size:10px; margin-right:4px;">expand all</button>
              <button onclick="toggleAll('{row_id}', false)" style="background:var(--surface2); color:var(--text2); border:1px solid var(--border); padding:2px 6px; border-radius:3px; cursor:pointer; font-size:10px;">collapse all</button>
            </div>
            <span class="expand-toggle" onclick="toggle('{exp_id}-sys')">▸ system</span>
            <div id="{exp_id}-sys" class="expand-content">{_e(lc.get("system_prompt"))}</div>
            <span class="expand-toggle" onclick="toggle('{exp_id}-usr')">▸ user</span>
            <div id="{exp_id}-usr" class="expand-content">{_e(lc.get("user_message"))}</div>
            <span class="expand-toggle" onclick="toggle('{exp_id}-res')">▸ response</span>
            <div id="{exp_id}-res" class="expand-content">{_e(lc.get("response_text"))}</div>
          </td>
        </tr>"""
    if not llm_calls:
        llm_rows = '<tr><td colspan="10" class="empty">No LLM calls recorded.</td></tr>'

    # --- Agent runs table ---
    agent_rows = ""
    for i, ar in enumerate(agent_runs):
        exp_id = f"agent-{ar.get('id', i)}"
        tool_log = ar.get("tool_calls_log", "[]")
        try:
            tool_log_pretty = json.dumps(json.loads(tool_log), indent=2)
        except (json.JSONDecodeError, TypeError):
            tool_log_pretty = str(tool_log)

        agent_rows += f"""<tr>
          <td>{ar.get("id", "")}</td>
          <td>{_e(ar.get("profile"))}</td>
          <td>{_badge(ar.get("status"))}</td>
          <td>{ar.get("iterations", 0)}</td>
          <td>{_e(ar.get("error"))}</td>
          <td>{_e(ar.get("created_at"))}</td>
          <td>{_e(ar.get("completed_at"))}</td>
          <td class="expandable">
            <span class="expand-toggle" onclick="toggle('{exp_id}-tools')">▸ tool calls</span>
            <div id="{exp_id}-tools" class="expand-content">{_e(tool_log_pretty)}</div>
            <span class="expand-toggle" onclick="toggle('{exp_id}-msg')">▸ final message</span>
            <div id="{exp_id}-msg" class="expand-content">{_e(ar.get("final_message"))}</div>
          </td>
        </tr>"""
    if not agent_runs:
        agent_rows = '<tr><td colspan="8" class="empty">No agent runs recorded.</td></tr>'

    # --- Reasoning ---
    reasoning_html = ""
    if email.get("reasoning"):
        reasoning_html = f'<div class="reasoning-box">{_e(email["reasoning"])}</div>'

    # --- Navigation: prev/next ---
    db = get_db()
    prev_email = db.execute_one(
        "SELECT id FROM emails WHERE id < ? ORDER BY id DESC LIMIT 1", (eid,)
    )
    next_email = db.execute_one(
        "SELECT id FROM emails WHERE id > ? ORDER BY id ASC LIMIT 1", (eid,)
    )
    prev_link = f'<a href="/debug/email/{prev_email["id"]}">← prev</a>' if prev_email else ""
    next_link = f'<a href="/debug/email/{next_email["id"]}">next →</a>' if next_email else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Debug #{eid} — {_e(email.get("subject", ""))}</title>
<style>{_CSS}</style></head><body>
<div class="topnav">
  <h1>Email Debug</h1>
  <a href="/debug/emails">← All Emails</a>
  <a href="/admin">SQLAdmin</a>
  <button onclick="triggerFullSync()">Full Sync</button>
  <button id="reclassify-btn" onclick="reclassifyEmail({eid})"
    style="background:var(--purple)">Reclassify</button>
  <span style="margin-left:auto; display:flex; gap:12px">{prev_link} {next_link}</span>
</div>
<div class="container">

  <!-- Email header -->
  <div class="email-header">
    <h2>{_e(email.get("subject", "(no subject)"))}</h2>
    <div style="color:var(--text2); font-size:12px; margin-bottom:8px;">
      {_e(email.get("sender_name", ""))} &lt;{_e(email.get("sender_email", ""))}&gt;
      · Thread: <code>{_e(email.get("gmail_thread_id"))}</code>
      · Message: <code>{_e(email.get("gmail_message_id"))}</code>
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
      {_badge(email.get("classification"))}
      {_badge(email.get("status"))}
      {_badge(email.get("confidence"))}
      <span class="badge" style="background:var(--surface2); color:var(--text2);">
        {email.get("message_count", 1)} msg(s)
      </span>
      <span class="badge" style="background:var(--surface2); color:var(--text2);">
        style: {_e(email.get("resolved_style"))}
      </span>
      <span class="badge" style="background:var(--surface2); color:var(--text2);">
        lang: {_e(email.get("detected_language"))}
      </span>
    </div>
    <div class="meta-grid">
      <div class="meta-item"><span class="meta-label">Received</span>
        <span class="meta-value">{_e(email.get("received_at"))}</span></div>
      <div class="meta-item"><span class="meta-label">Processed</span>
        <span class="meta-value">{_e(email.get("processed_at"))}</span></div>
      <div class="meta-item"><span class="meta-label">Drafted</span>
        <span class="meta-value">{_e(email.get("drafted_at"))}</span></div>
      <div class="meta-item"><span class="meta-label">Acted</span>
        <span class="meta-value">{_e(email.get("acted_at"))}</span></div>
      <div class="meta-item"><span class="meta-label">Draft ID</span>
        <span class="meta-value">{_e(email.get("draft_id"))}</span></div>
      <div class="meta-item"><span class="meta-label">Rework Count</span>
        <span class="meta-value">{email.get("rework_count", 0)}</span></div>
      <div class="meta-item"><span class="meta-label">Vendor</span>
        <span class="meta-value">{_e(email.get("vendor_name"))}</span></div>
      <div class="meta-item"><span class="meta-label">DB ID</span>
        <span class="meta-value">{eid}</span></div>
    </div>
    {reasoning_html}
    {"<div style='margin-top:8px'><span class='meta-label'>Last Rework Instruction</span><div class='reasoning-box'>" + _e(email.get("last_rework_instruction")) + "</div></div>" if email.get("last_rework_instruction") else ""}
    {"<div style='margin-top:8px'><span class='meta-label'>Snippet</span><div class='reasoning-box'>" + _e(email.get("snippet")) + "</div></div>" if email.get("snippet") else ""}
  </div>

  <!-- Timeline -->
  <div class="section">
    <div class="section-header">
      <h3>Timeline</h3>
      <span class="section-count">{len(timeline_items)} entries</span>
    </div>
    <div class="timeline">{tl_html}</div>
  </div>

  <!-- Events -->
  <div class="section">
    <div class="section-header">
      <h3>Events</h3>
      <span class="section-count">{len(events)}</span>
    </div>
    <table>
      <thead><tr><th>ID</th><th>Type</th><th>Detail</th><th>Label</th>
        <th>Draft</th><th>Time</th></tr></thead>
      <tbody>{ev_rows}</tbody>
    </table>
  </div>

  <!-- LLM Calls -->
  <div class="section">
    <div class="section-header">
      <h3>LLM Calls</h3>
      <span class="section-count">{len(llm_calls)}</span>
    </div>
    <div style="overflow-x:auto;">
    <table>
      <thead><tr><th>ID</th><th>Type</th><th>Model</th><th>Prompt</th>
        <th>Compl.</th><th>Total</th><th>Latency</th><th>Error</th>
        <th>Time</th><th>Prompts / Response</th></tr></thead>
      <tbody>{llm_rows}</tbody>
    </table>
    </div>
  </div>

  <!-- Agent Runs -->
  <div class="section">
    <div class="section-header">
      <h3>Agent Runs</h3>
      <span class="section-count">{len(agent_runs)}</span>
    </div>
    <table>
      <thead><tr><th>ID</th><th>Profile</th><th>Status</th><th>Iterations</th>
        <th>Error</th><th>Started</th><th>Completed</th><th>Details</th></tr></thead>
      <tbody>{agent_rows}</tbody>
    </table>
  </div>

</div>
<script>{_JS}</script>
</body></html>"""
