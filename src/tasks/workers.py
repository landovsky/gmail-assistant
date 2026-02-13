"""Async workers — process jobs from the queue.

Runs N concurrent worker coroutines. All blocking I/O (Gmail API, LLM,
SQLite) is pushed to threads via asyncio.to_thread so the FastAPI event
loop stays responsive.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.classify.engine import ClassificationEngine
from src.config import AppConfig
from src.context.gatherer import ContextGatherer
from src.db.connection import Database
from src.db.models import (
    EmailRecord,
    EmailRepository,
    EventRepository,
    JobRepository,
    LabelRepository,
    UserRepository,
)
from src.draft.engine import DraftEngine
from src.gmail.client import GmailService, UserGmailClient
from src.lifecycle.manager import LifecycleManager
from src.sync.engine import SyncEngine
from src.users.settings import UserSettings

logger = logging.getLogger(__name__)


class WorkerPool:
    """Manages async workers that process jobs from the queue."""

    def __init__(
        self,
        db: Database,
        gmail_service: GmailService,
        classification_engine: ClassificationEngine,
        draft_engine: DraftEngine,
        config: AppConfig,
        context_gatherer: ContextGatherer | None = None,
    ):
        self.db = db
        self.gmail_service = gmail_service
        self.classification_engine = classification_engine
        self.draft_engine = draft_engine
        self.context_gatherer = context_gatherer
        self.config = config
        self.jobs = JobRepository(db)
        self.users = UserRepository(db)
        self.emails = EmailRepository(db)
        self.events = EventRepository(db)
        self.labels_repo = LabelRepository(db)
        self.sync_engine = SyncEngine(db, config.sync)
        self.lifecycle = LifecycleManager(db, draft_engine)
        self._running = False
        self._concurrency = config.server.worker_concurrency

    async def start(self, poll_interval: float = 1.0) -> None:
        """Start N concurrent worker loops."""
        self._running = True
        logger.info("Worker pool started (%d workers)", self._concurrency)
        tasks = [
            asyncio.create_task(self._worker_loop(i, poll_interval))
            for i in range(self._concurrency)
        ]
        await asyncio.gather(*tasks)

    def stop(self) -> None:
        """Stop all worker loops."""
        self._running = False
        logger.info("Worker pool stopping")

    async def _worker_loop(self, worker_id: int, poll_interval: float) -> None:
        """Single worker loop — claim and process jobs."""
        while self._running:
            job = await asyncio.to_thread(self.jobs.claim_next)
            if job:
                await self._process_job(job, worker_id)
            else:
                await asyncio.sleep(poll_interval)

    async def _process_job(self, job: Any, worker_id: int = 0) -> None:
        """Dispatch a job to the appropriate handler."""
        try:
            logger.info(
                "Worker %d processing job %d: %s (user=%d)",
                worker_id,
                job.id,
                job.job_type,
                job.user_id,
            )

            user = await asyncio.to_thread(self.users.get_by_id, job.user_id)
            if not user:
                await asyncio.to_thread(self.jobs.fail, job.id, f"User {job.user_id} not found")
                return

            gmail_client = self.gmail_service.for_user(user.email)

            if job.job_type == "sync":
                await self._handle_sync(job, gmail_client)
            elif job.job_type == "classify":
                await self._handle_classify(job, gmail_client)
            elif job.job_type == "draft":
                await self._handle_draft(job, gmail_client)
            elif job.job_type == "cleanup":
                await self._handle_cleanup(job, gmail_client)
            elif job.job_type == "rework":
                await self._handle_rework(job, gmail_client)
            else:
                await asyncio.to_thread(self.jobs.fail, job.id, f"Unknown job type: {job.job_type}")
                return

            await asyncio.to_thread(self.jobs.complete, job.id)

        except Exception as e:
            logger.error("Job %d failed: %s", job.id, e, exc_info=True)
            if job.attempts < job.max_attempts:
                await asyncio.to_thread(self.jobs.retry, job.id, str(e))
            else:
                await asyncio.to_thread(self.jobs.fail, job.id, str(e))

    async def _handle_sync(self, job: Any, gmail_client: UserGmailClient) -> None:
        history_id = job.payload.get("history_id")
        await asyncio.to_thread(self.sync_engine.sync_user, job.user_id, gmail_client, history_id)

    async def _handle_classify(self, job: Any, gmail_client: UserGmailClient) -> None:
        message_id = job.payload.get("message_id")

        if not message_id:
            return

        # Get message content
        msg = await asyncio.to_thread(gmail_client.get_message, message_id)
        if not msg:
            return

        # Check if already classified
        existing = await asyncio.to_thread(self.emails.get_by_thread, job.user_id, msg.thread_id)
        if existing:
            return

        # Get user settings
        settings = await asyncio.to_thread(UserSettings, self.db, job.user_id)
        contacts = settings.contacts

        # Classify (LLM call — most expensive)
        result = await asyncio.to_thread(
            self.classification_engine.classify,
            sender_email=msg.sender_email,
            sender_name=msg.sender_name,
            subject=msg.subject,
            snippet=msg.snippet,
            body=msg.body,
            message_count=1,
            blacklist=settings.blacklist,
            contacts_config=contacts,
        )

        # Apply Gmail label
        label_ids = await asyncio.to_thread(self.labels_repo.get_labels, job.user_id)
        label_id = label_ids.get(result.category)
        if label_id:
            await asyncio.to_thread(gmail_client.modify_labels, message_id, add=[label_id])

        # Store in DB
        record = EmailRecord(
            user_id=job.user_id,
            gmail_thread_id=msg.thread_id,
            gmail_message_id=msg.id,
            sender_email=msg.sender_email,
            sender_name=msg.sender_name,
            subject=msg.subject,
            snippet=msg.snippet,
            received_at=msg.internal_date,
            classification=result.category,
            confidence=result.confidence,
            reasoning=result.reasoning,
            detected_language=result.detected_language,
            resolved_style=result.resolved_style,
        )
        await asyncio.to_thread(self.emails.upsert, record)

        # Log event
        await asyncio.to_thread(
            self.events.log,
            job.user_id,
            msg.thread_id,
            "classified",
            f"{result.category} ({result.confidence}, source={result.source})",
        )

        # Queue draft if needs_response
        if result.category == "needs_response":
            await asyncio.to_thread(
                self.jobs.enqueue,
                "draft",
                job.user_id,
                {
                    "thread_id": msg.thread_id,
                    "message_id": msg.id,
                },
            )

        logger.info(
            "Classified %s → %s (%s, %s)",
            msg.thread_id,
            result.category,
            result.confidence,
            result.source,
        )

    async def _handle_draft(self, job: Any, gmail_client: UserGmailClient) -> None:
        thread_id = job.payload.get("thread_id")
        if not thread_id:
            return

        email = await asyncio.to_thread(self.emails.get_by_thread, job.user_id, thread_id)
        if not email or email["status"] != "pending":
            return

        # Get thread for context
        thread = await asyncio.to_thread(gmail_client.get_thread, thread_id)
        if not thread or not thread.latest_message:
            return

        settings = await asyncio.to_thread(UserSettings, self.db, job.user_id)
        thread_body = "\n---\n".join(m.body[:1000] for m in thread.messages)

        # Gather related context (fail-safe — empty on error)
        related_context: str | None = None
        if self.context_gatherer:
            ctx = await asyncio.to_thread(
                self.context_gatherer.gather,
                gmail_client,
                thread_id,
                email["sender_email"],
                email.get("subject", ""),
                thread_body,
            )
            if not ctx.is_empty:
                related_context = ctx.format_for_prompt()

        # Generate draft (LLM call)
        draft_body = await asyncio.to_thread(
            self.draft_engine.generate_draft,
            sender_email=email["sender_email"],
            sender_name=email.get("sender_name", ""),
            subject=email.get("subject", ""),
            thread_body=thread_body,
            resolved_style=email.get("resolved_style", "business"),
            style_config=settings.communication_styles,
            related_context=related_context,
        )

        # Create Gmail draft
        latest = thread.latest_message
        draft_id = await asyncio.to_thread(
            gmail_client.create_draft,
            thread_id=thread_id,
            to=email["sender_email"],
            subject=email.get("subject", ""),
            body=draft_body,
            in_reply_to=latest.headers.get("Message-ID"),
        )

        if not draft_id:
            raise RuntimeError(f"Failed to create draft for thread {thread_id}")

        # Move label: Needs Response → Outbox
        label_ids = await asyncio.to_thread(self.labels_repo.get_labels, job.user_id)
        needs_resp = label_ids.get("needs_response")
        outbox = label_ids.get("outbox")
        if needs_resp and outbox:
            msg_ids = [m.id for m in thread.messages]
            await asyncio.to_thread(
                gmail_client.batch_modify_labels, msg_ids, add=[outbox], remove=[needs_resp]
            )

        # Update DB
        await asyncio.to_thread(self.emails.update_draft, job.user_id, thread_id, draft_id)
        await asyncio.to_thread(
            self.events.log,
            job.user_id,
            thread_id,
            "draft_created",
            f"Draft created with style: {email.get('resolved_style', 'business')}",
            draft_id=draft_id,
        )

        logger.info("Created draft for thread %s", thread_id)

    async def _handle_cleanup(self, job: Any, gmail_client: UserGmailClient) -> None:
        action = job.payload.get("action", "")
        thread_id = job.payload.get("thread_id", "")

        if action == "done" and thread_id:
            await asyncio.to_thread(
                self.lifecycle.handle_done, job.user_id, thread_id, gmail_client
            )
        elif action == "check_sent" and thread_id:
            await asyncio.to_thread(
                self.lifecycle.handle_sent_detection, job.user_id, thread_id, gmail_client
            )

    async def _handle_rework(self, job: Any, gmail_client: UserGmailClient) -> None:
        message_id = job.payload.get("message_id", "")

        # Need to find the thread_id from the message
        msg = await asyncio.to_thread(gmail_client.get_message, message_id) if message_id else None
        if not msg:
            return

        settings = await asyncio.to_thread(UserSettings, self.db, job.user_id)
        await asyncio.to_thread(
            self.lifecycle.handle_rework,
            job.user_id,
            msg.thread_id,
            gmail_client,
            style_config=settings.communication_styles,
        )
