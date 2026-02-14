"""Sync engine — incremental mailbox sync via Gmail History API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.config import SyncConfig
from src.db.connection import Database
from src.db.models import (
    EmailRepository,
    EventRepository,
    JobRepository,
    LabelRepository,
    SyncStateRepository,
)
from src.gmail.client import UserGmailClient
from src.gmail.models import HistoryRecord

if TYPE_CHECKING:
    from src.routing.router import Router

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    new_messages: int = 0
    label_changes: int = 0
    deletions: int = 0
    jobs_queued: int = 0
    errors: list[str] = field(default_factory=list)


class SyncEngine:
    """Incremental mailbox sync using Gmail History API."""

    def __init__(
        self,
        db: Database,
        sync_config: SyncConfig | None = None,
        router: Router | None = None,
    ):
        self.db = db
        self.sync_config = sync_config or SyncConfig()
        self.sync_state = SyncStateRepository(db)
        self.emails = EmailRepository(db)
        self.events = EventRepository(db)
        self.labels_repo = LabelRepository(db)
        self.jobs = JobRepository(db)
        self.router = router

    def sync_user(
        self,
        user_id: int,
        gmail_client: UserGmailClient,
        notified_history_id: str | None = None,
        force_full: bool = False,
    ) -> SyncResult:
        """Process all changes since last known historyId."""
        result = SyncResult()

        if force_full:
            logger.info("Forced full sync for user %d", user_id)
            return self.full_sync(user_id, gmail_client)

        state = self.sync_state.get(user_id)
        if not state:
            logger.warning("No sync state for user %d, need full sync", user_id)
            return self.full_sync(user_id, gmail_client)

        last_history_id = state["last_history_id"]
        label_ids = self.labels_repo.get_labels(user_id)

        # Fetch history records
        records = gmail_client.list_history(last_history_id)

        if not records:
            logger.info("No history changes for user %d since %s", user_id, last_history_id)
            self.sync_state.upsert(user_id, notified_history_id or last_history_id)
            return result

        # Process each history record (track seen jobs to deduplicate per-thread)
        seen_jobs: set[tuple[str, str]] = set()
        for record in records:
            self._process_history_record(user_id, record, label_ids, result, seen_jobs)

        # Update stored historyId
        new_history_id = notified_history_id or records[-1].id
        self.sync_state.upsert(user_id, new_history_id)

        logger.info(
            "Synced user %d: %d new, %d label changes, %d deletions, %d jobs",
            user_id, result.new_messages, result.label_changes,
            result.deletions, result.jobs_queued,
        )
        return result

    def full_sync(
        self,
        user_id: int,
        gmail_client: UserGmailClient,
    ) -> SyncResult:
        """Full sync fallback — scan inbox for unclassified emails."""
        result = SyncResult()
        label_ids = self.labels_repo.get_labels(user_id)

        # Build exclusion query
        label_names = self.labels_repo.get_label_names(user_id)
        exclusions = " ".join(
            f'-label:"{name}"'
            for key, name in label_names.items()
            if key in ("needs_response", "outbox", "rework", "action_required",
                        "payment_request", "fyi", "waiting", "done")
        )

        days = self.sync_config.full_sync_days
        query = f"in:inbox newer_than:{days}d {exclusions} -in:trash -in:spam"
        messages = gmail_client.search(query, max_results=50)

        for msg in messages:
            # Skip if already classified or job already queued
            # (avoids duplicate jobs across overlapping full syncs)
            if self.emails.get_by_thread(user_id, msg.thread_id):
                continue
            if self.jobs.has_pending_for_thread("classify", user_id, msg.thread_id):
                continue

            self.jobs.enqueue("classify", user_id, {
                "message_id": msg.id,
                "thread_id": msg.thread_id,
            })
            result.new_messages += 1
            result.jobs_queued += 1

        # Update sync state from profile
        profile = gmail_client.get_profile()
        new_history_id = profile.get("historyId", "0")
        self.sync_state.upsert(user_id, str(new_history_id))

        logger.info("Full sync for user %d: %d unclassified emails found", user_id, result.new_messages)
        return result

    def _process_history_record(
        self,
        user_id: int,
        record: HistoryRecord,
        label_ids: dict[str, str],
        result: SyncResult,
        seen_jobs: set[tuple[str, str]],
    ) -> None:
        """Process a single history record — dispatch to appropriate handlers."""
        done_label = label_ids.get("done")
        rework_label = label_ids.get("rework")
        waiting_label = label_ids.get("waiting")
        needs_response_label = label_ids.get("needs_response")

        # New messages → route to classify or agent_process
        for msg in record.messages_added:
            if "INBOX" in msg.label_ids:
                # Check routing rules if router is available
                job_type = "classify"
                payload: dict[str, Any] = {
                    "message_id": msg.id,
                    "thread_id": msg.thread_id,
                }

                if self.router:
                    message_meta = {
                        "sender_email": msg.sender_email,
                        "subject": msg.subject,
                        "headers": msg.headers,
                        "body": msg.body,
                    }
                    decision = self.router.route(message_meta)
                    if decision.route_name == "agent":
                        job_type = "agent_process"
                        payload["profile"] = decision.profile_name
                        payload["route_rule"] = decision.rule_name

                key = (job_type, msg.thread_id)
                if key in seen_jobs:
                    continue
                seen_jobs.add(key)
                self.jobs.enqueue(job_type, user_id, payload)
                result.new_messages += 1
                result.jobs_queued += 1

        # Label additions — deduplicate per thread to avoid duplicate jobs
        # (Gmail reports one label change per message in a thread)
        for item in record.labels_added:
            added_labels = item.get("label_ids", [])
            msg_id = item.get("message_id", "")
            thread_id = item.get("thread_id", msg_id)

            if done_label and done_label in added_labels:
                key = ("cleanup_done", thread_id)
                if key in seen_jobs:
                    continue
                seen_jobs.add(key)
                self.jobs.enqueue(
                    "cleanup", user_id,
                    {"message_id": msg_id, "thread_id": thread_id, "action": "done"},
                )
                result.label_changes += 1
                result.jobs_queued += 1

            if rework_label and rework_label in added_labels:
                key = ("rework", thread_id)
                if key in seen_jobs:
                    continue
                seen_jobs.add(key)
                self.jobs.enqueue("rework", user_id, {"message_id": msg_id})
                result.label_changes += 1
                result.jobs_queued += 1

            if needs_response_label and needs_response_label in added_labels:
                key = ("manual_draft", thread_id)
                if key in seen_jobs:
                    continue
                seen_jobs.add(key)
                self.jobs.enqueue("manual_draft", user_id, {"message_id": msg_id})
                result.label_changes += 1
                result.jobs_queued += 1

        # Deletions (potential sent detection)
        for msg_id in record.messages_deleted:
            self.jobs.enqueue("cleanup", user_id, {"message_id": msg_id, "action": "check_sent"})
            result.deletions += 1
            result.jobs_queued += 1
