"""Database model helpers — query builders for the v2 schema."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.db.connection import Database

logger = logging.getLogger(__name__)


@dataclass
class User:
    id: int
    email: str
    display_name: str | None = None
    is_active: bool = True
    onboarded_at: datetime | None = None
    created_at: datetime | None = None


@dataclass
class EmailRecord:
    id: int | None = None
    user_id: int = 0
    gmail_thread_id: str = ""
    gmail_message_id: str = ""
    sender_email: str = ""
    sender_name: str | None = None
    subject: str | None = None
    snippet: str | None = None
    received_at: str | None = None
    classification: str = "fyi"
    confidence: str = "medium"
    reasoning: str | None = None
    detected_language: str = "cs"
    resolved_style: str = "business"
    message_count: int = 1
    status: str = "pending"
    draft_id: str | None = None
    rework_count: int = 0
    last_rework_instruction: str | None = None
    vendor_name: str | None = None
    processed_at: str | None = None
    drafted_at: str | None = None
    acted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Job:
    id: int | None = None
    job_type: str = ""
    user_id: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 3
    error_message: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class UserRepository:
    """Database operations for users."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, email: str, display_name: str | None = None) -> int:
        return self.db.execute_write(
            "INSERT INTO users (email, display_name) VALUES (?, ?)",
            (email, display_name),
        )

    def get_by_email(self, email: str) -> User | None:
        row = self.db.execute_one("SELECT * FROM users WHERE email = ?", (email,))
        if row:
            return User(
                **{
                    k: row[k]
                    for k in (
                        "id",
                        "email",
                        "display_name",
                        "is_active",
                        "onboarded_at",
                        "created_at",
                    )
                }
            )
        return None

    def get_by_id(self, user_id: int) -> User | None:
        row = self.db.execute_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if row:
            return User(
                **{
                    k: row[k]
                    for k in (
                        "id",
                        "email",
                        "display_name",
                        "is_active",
                        "onboarded_at",
                        "created_at",
                    )
                }
            )
        return None

    def get_active_users(self) -> list[User]:
        rows = self.db.execute("SELECT * FROM users WHERE is_active = 1")
        return [
            User(
                **{
                    k: r[k]
                    for k in (
                        "id",
                        "email",
                        "display_name",
                        "is_active",
                        "onboarded_at",
                        "created_at",
                    )
                }
            )
            for r in rows
        ]

    def mark_onboarded(self, user_id: int) -> None:
        self.db.execute_write(
            "UPDATE users SET onboarded_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,),
        )


class LabelRepository:
    """Database operations for user label mappings."""

    def __init__(self, db: Database):
        self.db = db

    def set_label(
        self, user_id: int, label_key: str, gmail_label_id: str, gmail_label_name: str
    ) -> None:
        self.db.execute_write(
            """INSERT OR REPLACE INTO user_labels (user_id, label_key, gmail_label_id, gmail_label_name)
               VALUES (?, ?, ?, ?)""",
            (user_id, label_key, gmail_label_id, gmail_label_name),
        )

    def get_labels(self, user_id: int) -> dict[str, str]:
        """Return {label_key: gmail_label_id} mapping."""
        rows = self.db.execute(
            "SELECT label_key, gmail_label_id FROM user_labels WHERE user_id = ?",
            (user_id,),
        )
        return {r["label_key"]: r["gmail_label_id"] for r in rows}

    def get_label_names(self, user_id: int) -> dict[str, str]:
        """Return {label_key: gmail_label_name} mapping."""
        rows = self.db.execute(
            "SELECT label_key, gmail_label_name FROM user_labels WHERE user_id = ?",
            (user_id,),
        )
        return {r["label_key"]: r["gmail_label_name"] for r in rows}


class SettingsRepository:
    """Database operations for per-user settings."""

    def __init__(self, db: Database):
        self.db = db

    def get(self, user_id: int, key: str) -> Any:
        row = self.db.execute_one(
            "SELECT setting_value FROM user_settings WHERE user_id = ? AND setting_key = ?",
            (user_id, key),
        )
        if row:
            return json.loads(row["setting_value"])
        return None

    def set(self, user_id: int, key: str, value: Any) -> None:
        self.db.execute_write(
            """INSERT OR REPLACE INTO user_settings (user_id, setting_key, setting_value)
               VALUES (?, ?, ?)""",
            (user_id, key, json.dumps(value)),
        )

    def get_all(self, user_id: int) -> dict[str, Any]:
        rows = self.db.execute(
            "SELECT setting_key, setting_value FROM user_settings WHERE user_id = ?",
            (user_id,),
        )
        return {r["setting_key"]: json.loads(r["setting_value"]) for r in rows}


class SyncStateRepository:
    """Database operations for sync state."""

    def __init__(self, db: Database):
        self.db = db

    def get(self, user_id: int) -> dict[str, Any] | None:
        return self.db.execute_one("SELECT * FROM sync_state WHERE user_id = ?", (user_id,))

    def upsert(self, user_id: int, history_id: str) -> None:
        self.db.execute_write(
            """INSERT INTO sync_state (user_id, last_history_id, last_sync_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   last_history_id = excluded.last_history_id,
                   last_sync_at = CURRENT_TIMESTAMP""",
            (user_id, history_id),
        )

    def set_watch(self, user_id: int, resource_id: str, expiration: str) -> None:
        self.db.execute_write(
            """UPDATE sync_state SET watch_resource_id = ?, watch_expiration = ?
               WHERE user_id = ?""",
            (resource_id, expiration, user_id),
        )

    def delete(self, user_id: int) -> None:
        self.db.execute_write("DELETE FROM sync_state WHERE user_id = ?", (user_id,))


class EmailRepository:
    """Database operations for emails."""

    def __init__(self, db: Database):
        self.db = db

    def upsert(self, record: EmailRecord) -> int:
        return self.db.execute_write(
            """INSERT INTO emails (
                user_id, gmail_thread_id, gmail_message_id, sender_email, sender_name,
                subject, snippet, received_at, classification, confidence, reasoning,
                detected_language, resolved_style, message_count, status,
                processed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, gmail_thread_id) DO UPDATE SET
                gmail_message_id = excluded.gmail_message_id,
                classification = excluded.classification,
                confidence = excluded.confidence,
                reasoning = excluded.reasoning,
                detected_language = excluded.detected_language,
                resolved_style = excluded.resolved_style,
                message_count = excluded.message_count,
                updated_at = CURRENT_TIMESTAMP""",
            (
                record.user_id,
                record.gmail_thread_id,
                record.gmail_message_id,
                record.sender_email,
                record.sender_name,
                record.subject,
                record.snippet,
                record.received_at,
                record.classification,
                record.confidence,
                record.reasoning,
                record.detected_language,
                record.resolved_style,
                record.message_count,
            ),
        )

    def get_by_thread(self, user_id: int, thread_id: str) -> dict[str, Any] | None:
        return self.db.execute_one(
            "SELECT * FROM emails WHERE user_id = ? AND gmail_thread_id = ?",
            (user_id, thread_id),
        )

    def get_by_message(self, user_id: int, message_id: str) -> dict[str, Any] | None:
        return self.db.execute_one(
            "SELECT * FROM emails WHERE user_id = ? AND gmail_message_id = ?",
            (user_id, message_id),
        )

    def get_pending_drafts(self, user_id: int) -> list[dict[str, Any]]:
        return self.db.execute(
            """SELECT * FROM emails
               WHERE user_id = ? AND classification = 'needs_response' AND status = 'pending'""",
            (user_id,),
        )

    def get_by_status(self, user_id: int, status: str) -> list[dict[str, Any]]:
        return self.db.execute(
            "SELECT * FROM emails WHERE user_id = ? AND status = ?",
            (user_id, status),
        )

    def get_by_classification(self, user_id: int, classification: str) -> list[dict[str, Any]]:
        return self.db.execute(
            "SELECT * FROM emails WHERE user_id = ? AND classification = ?",
            (user_id, classification),
        )

    def update_status(self, user_id: int, thread_id: str, status: str, **kwargs: Any) -> None:
        sets = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = [status]
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            params.append(v)
        params.extend([user_id, thread_id])
        self.db.execute_write(
            f"UPDATE emails SET {', '.join(sets)} WHERE user_id = ? AND gmail_thread_id = ?",
            tuple(params),
        )

    def update_draft(self, user_id: int, thread_id: str, draft_id: str) -> None:
        self.db.execute_write(
            """UPDATE emails SET status = 'drafted', draft_id = ?,
               drafted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND gmail_thread_id = ?""",
            (draft_id, user_id, thread_id),
        )

    def increment_rework(
        self, user_id: int, thread_id: str, draft_id: str, instruction: str
    ) -> None:
        self.db.execute_write(
            """UPDATE emails SET rework_count = rework_count + 1,
               draft_id = ?, last_rework_instruction = ?,
               status = 'drafted', updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND gmail_thread_id = ?""",
            (draft_id, instruction, user_id, thread_id),
        )


class EventRepository:
    """Database operations for the audit log."""

    def __init__(self, db: Database):
        self.db = db

    def log(
        self,
        user_id: int,
        thread_id: str,
        event_type: str,
        detail: str | None = None,
        label_id: str | None = None,
        draft_id: str | None = None,
    ) -> int:
        return self.db.execute_write(
            """INSERT INTO email_events (user_id, gmail_thread_id, event_type, detail, label_id, draft_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, thread_id, event_type, detail, label_id, draft_id),
        )

    def get_thread_events(self, user_id: int, thread_id: str) -> list[dict[str, Any]]:
        return self.db.execute(
            """SELECT * FROM email_events
               WHERE user_id = ? AND gmail_thread_id = ?
               ORDER BY created_at""",
            (user_id, thread_id),
        )


class LLMCallRepository:
    """Database operations for LLM call logging."""

    def __init__(self, db: Database):
        self.db = db

    def log(
        self,
        call_type: str,
        model: str,
        user_id: int | None = None,
        gmail_thread_id: str | None = None,
        system_prompt: str | None = None,
        user_message: str | None = None,
        response_text: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int = 0,
        error: str | None = None,
    ) -> int:
        """Log an LLM API call with all metadata."""
        return self.db.execute_write(
            """INSERT INTO llm_calls (
                user_id, gmail_thread_id, call_type, model,
                system_prompt, user_message, response_text,
                prompt_tokens, completion_tokens, total_tokens,
                latency_ms, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                gmail_thread_id,
                call_type,
                model,
                system_prompt,
                user_message,
                response_text,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                error,
            ),
        )

    def get_by_thread(self, thread_id: str) -> list[dict[str, Any]]:
        """Get all LLM calls for a specific Gmail thread."""
        return self.db.execute(
            """SELECT * FROM llm_calls
               WHERE gmail_thread_id = ?
               ORDER BY created_at""",
            (thread_id,),
        )

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent LLM calls (for debugging/monitoring)."""
        return self.db.execute(
            "SELECT * FROM llm_calls ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def get_stats(self, user_id: int | None = None) -> dict[str, Any]:
        """Get token usage statistics."""
        where = "WHERE user_id = ?" if user_id else ""
        params = (user_id,) if user_id else ()
        result = self.db.execute_one(
            f"""SELECT
                COUNT(*) as call_count,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(latency_ms) as avg_latency_ms
               FROM llm_calls {where}""",
            params,
        )
        return result or {}


class AgentRunRepository:
    """Database operations for agent run tracking."""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        user_id: int,
        gmail_thread_id: str,
        profile: str,
    ) -> int:
        """Create a new agent run record. Returns the run ID."""
        return self.db.execute_write(
            """INSERT INTO agent_runs (user_id, gmail_thread_id, profile, status)
               VALUES (?, ?, ?, 'running')""",
            (user_id, gmail_thread_id, profile),
        )

    def complete(
        self,
        run_id: int,
        status: str,
        tool_calls_log: str,
        final_message: str = "",
        iterations: int = 0,
        error: str | None = None,
    ) -> None:
        """Mark an agent run as completed (or errored)."""
        self.db.execute_write(
            """UPDATE agent_runs
               SET status = ?, tool_calls_log = ?, final_message = ?,
                   iterations = ?, error = ?, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, tool_calls_log, final_message, iterations, error, run_id),
        )

    def get_by_thread(self, user_id: int, thread_id: str) -> list[dict[str, Any]]:
        """Get all agent runs for a thread."""
        return self.db.execute(
            """SELECT * FROM agent_runs
               WHERE user_id = ? AND gmail_thread_id = ?
               ORDER BY created_at""",
            (user_id, thread_id),
        )

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent agent runs for monitoring."""
        return self.db.execute(
            "SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )


class JobRepository:
    """Database operations for the job queue."""

    def __init__(self, db: Database):
        self.db = db

    def enqueue(self, job_type: str, user_id: int, payload: dict | None = None) -> int:
        return self.db.execute_write(
            "INSERT INTO jobs (job_type, user_id, payload) VALUES (?, ?, ?)",
            (job_type, user_id, json.dumps(payload or {})),
        )

    def claim_next(self, job_type: str | None = None) -> Job | None:
        """Atomically claim the next pending job.

        Uses UPDATE ... RETURNING (SQLite 3.35+) to avoid race conditions
        when multiple workers call claim_next concurrently.
        """
        type_filter = "AND job_type = ?" if job_type else ""
        params: list[Any] = []
        if job_type:
            params.append(job_type)

        sql = f"""
            UPDATE jobs
            SET status = 'running',
                attempts = attempts + 1,
                started_at = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'pending' AND attempts < max_attempts
                {type_filter}
                ORDER BY created_at
                LIMIT 1
            )
            RETURNING *
        """

        row = self.db.execute_one(sql, tuple(params))
        if not row:
            return None

        return Job(
            id=row["id"],
            job_type=row["job_type"],
            user_id=row["user_id"],
            payload=json.loads(row["payload"]),
            status="running",
            attempts=row["attempts"],
        )

    def complete(self, job_id: int) -> None:
        self.db.execute_write(
            "UPDATE jobs SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (job_id,),
        )

    def fail(self, job_id: int, error: str) -> None:
        self.db.execute_write(
            "UPDATE jobs SET status = 'failed', error_message = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (error, job_id),
        )

    def retry(self, job_id: int, error: str) -> None:
        """Mark job for retry (back to pending)."""
        self.db.execute_write(
            "UPDATE jobs SET status = 'pending', error_message = ? WHERE id = ?",
            (error, job_id),
        )

    def cleanup_old(self, days: int = 7) -> int:
        """Remove completed/failed jobs older than N days."""
        return self.db.execute_write(
            "DELETE FROM jobs WHERE status IN ('completed', 'failed') AND completed_at < datetime('now', ?)",
            (f"-{days} days",),
        )
