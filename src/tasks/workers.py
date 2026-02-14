"""Async workers — process jobs from the queue.

Runs N concurrent worker coroutines. All blocking I/O (Gmail API, LLM,
SQLite) is pushed to threads via asyncio.to_thread so the FastAPI event
loop stays responsive.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from src.classify.engine import ClassificationEngine
from src.classify.rules import resolve_communication_style
from src.config import AppConfig
from src.context.gatherer import ContextGatherer
from src.db.connection import Database
from src.db.models import (
    AgentRunRepository,
    EmailRecord,
    EmailRepository,
    EventRepository,
    JobRepository,
    LabelRepository,
    UserRepository,
)
from src.draft.engine import DraftEngine
from src.draft.prompts import extract_rework_instruction
from src.gmail.client import GmailService, UserGmailClient
from src.lifecycle.manager import LifecycleManager
from src.sync.engine import SyncEngine
from src.users.settings import UserSettings

if TYPE_CHECKING:
    from src.agent.loop import AgentLoop
    from src.agent.profile import AgentProfile
    from src.routing.router import Router

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
        agent_loop: AgentLoop | None = None,
        agent_profiles: dict[str, AgentProfile] | None = None,
        router: Router | None = None,
    ):
        self.db = db
        self.gmail_service = gmail_service
        self.classification_engine = classification_engine
        self.draft_engine = draft_engine
        self.context_gatherer = context_gatherer
        self.agent_loop = agent_loop
        self.agent_profiles = agent_profiles or {}
        self.config = config
        self.jobs = JobRepository(db)
        self.users = UserRepository(db)
        self.emails = EmailRepository(db)
        self.events = EventRepository(db)
        self.labels_repo = LabelRepository(db)
        self.agent_runs = AgentRunRepository(db)
        self.sync_engine = SyncEngine(db, config.sync, router=router)
        self.lifecycle = LifecycleManager(db, draft_engine, context_gatherer)
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
            elif job.job_type == "manual_draft":
                await self._handle_manual_draft(job, gmail_client)
            elif job.job_type == "agent_process":
                await self._handle_agent_process(job, gmail_client)
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
            headers=msg.headers,
            style_config=settings.communication_styles,
            user_id=job.user_id,
            gmail_thread_id=msg.thread_id,
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
                user_id=job.user_id,
                gmail_thread_id=thread_id,
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
            user_id=job.user_id,
            gmail_thread_id=thread_id,
        )

        # Trash any stale drafts from previous attempts
        await asyncio.to_thread(gmail_client.trash_thread_drafts, thread_id)

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

    async def _handle_manual_draft(self, job: Any, gmail_client: UserGmailClient) -> None:
        """Handle user manually applying Needs Response label.

        Finds user's notes draft, extracts instructions, creates/updates the DB
        record, generates an AI draft, and moves to Outbox.
        """
        message_id = job.payload.get("message_id", "")
        if not message_id:
            return

        # Get the message to find thread_id and sender info
        msg = await asyncio.to_thread(gmail_client.get_message, message_id)
        if not msg:
            return

        thread_id = msg.thread_id

        # Check if already drafted — avoid duplicate work
        existing = await asyncio.to_thread(self.emails.get_by_thread, job.user_id, thread_id)
        if existing and existing["status"] == "drafted":
            return

        # Get thread for context
        thread = await asyncio.to_thread(gmail_client.get_thread, thread_id)
        if not thread or not thread.latest_message:
            return

        # Look for user's notes draft in this thread
        user_draft = await asyncio.to_thread(gmail_client.get_thread_draft, thread_id)
        user_instructions: str | None = None
        if user_draft and user_draft.message:
            draft_body = user_draft.message.body
            # Try extracting instructions above ✂️ marker first
            instruction, _ = extract_rework_instruction(draft_body)
            # If no marker, treat entire body as instructions
            user_instructions = instruction if instruction else draft_body.strip()
            if not user_instructions:
                user_instructions = None

        settings = await asyncio.to_thread(UserSettings, self.db, job.user_id)

        # Ensure DB record exists with needs_response classification
        if not existing:
            # Create a new record from the Gmail message
            resolved_style = resolve_communication_style(msg.sender_email, settings.contacts)
            record = EmailRecord(
                user_id=job.user_id,
                gmail_thread_id=thread_id,
                gmail_message_id=msg.id,
                sender_email=msg.sender_email,
                sender_name=msg.sender_name,
                subject=msg.subject,
                snippet=msg.snippet,
                received_at=msg.internal_date,
                classification="needs_response",
                confidence="high",
                reasoning="Manually requested by user",
                detected_language="auto",
                resolved_style=resolved_style,
                message_count=thread.message_count,
            )
            await asyncio.to_thread(self.emails.upsert, record)
        else:
            # Reclassify existing record to needs_response + pending
            resolved_style = existing.get("resolved_style", "business")
            record = EmailRecord(
                user_id=job.user_id,
                gmail_thread_id=thread_id,
                gmail_message_id=existing["gmail_message_id"],
                sender_email=existing["sender_email"],
                sender_name=existing.get("sender_name"),
                subject=existing.get("subject"),
                snippet=existing.get("snippet"),
                received_at=existing.get("received_at"),
                classification="needs_response",
                confidence="high",
                reasoning="Reclassified: manually requested by user",
                detected_language=existing.get("detected_language", "auto"),
                resolved_style=resolved_style,
                message_count=thread.message_count,
            )
            await asyncio.to_thread(self.emails.upsert, record)

        # Re-fetch email record after upsert
        email = await asyncio.to_thread(self.emails.get_by_thread, job.user_id, thread_id)

        thread_body = "\n---\n".join(m.body[:1000] for m in thread.messages)

        # Gather related context
        related_context: str | None = None
        if self.context_gatherer:
            ctx = await asyncio.to_thread(
                self.context_gatherer.gather,
                gmail_client,
                thread_id,
                msg.sender_email,
                msg.subject,
                thread_body,
                user_id=job.user_id,
                gmail_thread_id=thread_id,
            )
            if not ctx.is_empty:
                related_context = ctx.format_for_prompt()

        # Generate AI draft with user instructions
        draft_body = await asyncio.to_thread(
            self.draft_engine.generate_draft,
            sender_email=email["sender_email"],
            sender_name=email.get("sender_name", ""),
            subject=email.get("subject", ""),
            thread_body=thread_body,
            resolved_style=email.get("resolved_style", "business"),
            user_instructions=user_instructions,
            style_config=settings.communication_styles,
            related_context=related_context,
            user_id=job.user_id,
            gmail_thread_id=thread_id,
        )

        # Trash user's notes draft and any stale AI drafts from previous attempts
        await asyncio.to_thread(gmail_client.trash_thread_drafts, thread_id)

        # Create the AI draft
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

        detail = "Manual draft created"
        if user_instructions:
            detail += f" with instructions: {user_instructions[:100]}"
        await asyncio.to_thread(
            self.events.log,
            job.user_id,
            thread_id,
            "draft_created",
            detail,
            draft_id=draft_id,
        )

        logger.info("Created manual draft for thread %s", thread_id)

    async def _handle_agent_process(self, job: Any, gmail_client: UserGmailClient) -> None:
        """Handle agent-routed email processing.

        Runs the agent loop with the configured profile and tools,
        then logs the result to agent_runs for audit.
        """
        message_id = job.payload.get("message_id")
        thread_id = job.payload.get("thread_id", "")
        profile_name = job.payload.get("profile", "")

        if not message_id:
            return

        if not self.agent_loop:
            logger.error("Agent loop not configured, cannot process agent job %d", job.id)
            return

        profile = self.agent_profiles.get(profile_name)
        if not profile:
            logger.error("Unknown agent profile %r for job %d", profile_name, job.id)
            return

        # Get message content
        msg = await asyncio.to_thread(gmail_client.get_message, message_id)
        if not msg:
            return

        thread_id = thread_id or msg.thread_id

        # Get thread for full context
        thread = await asyncio.to_thread(gmail_client.get_thread, thread_id)
        thread_body = ""
        if thread and thread.messages:
            thread_body = "\n---\n".join(m.body[:2000] for m in thread.messages)

        # Preprocess based on profile (import here to avoid circular imports)
        from src.routing.preprocessors.crisp import format_for_agent, parse_crisp_email

        crisp_msg = parse_crisp_email(
            sender_email=msg.sender_email,
            subject=msg.subject,
            body=thread_body or msg.body,
            headers=msg.headers,
        )
        user_message = format_for_agent(crisp_msg, msg.subject)

        # Create agent run record
        run_id = await asyncio.to_thread(
            self.agent_runs.create,
            job.user_id,
            thread_id,
            profile_name,
        )

        # Run agent loop (blocking LLM calls pushed to thread)
        result = await asyncio.to_thread(
            self.agent_loop.run,
            profile,
            user_message,
            user_id=job.user_id,
            gmail_thread_id=thread_id,
        )

        # Serialize tool calls for audit
        tool_calls_json = json.dumps([
            {
                "tool": tc.tool_name,
                "arguments": tc.arguments,
                "result": tc.result,
                "iteration": tc.iteration,
            }
            for tc in result.tool_calls
        ], ensure_ascii=False, default=str)

        # Update agent run record
        await asyncio.to_thread(
            self.agent_runs.complete,
            run_id,
            status=result.status,
            tool_calls_log=tool_calls_json,
            final_message=result.final_message[:5000] if result.final_message else "",
            iterations=result.iterations,
            error=result.error,
        )

        # Log event
        detail = f"Agent {profile_name}: {result.status} ({result.iterations} iterations, {len(result.tool_calls)} tool calls)"
        await asyncio.to_thread(
            self.events.log,
            job.user_id,
            thread_id,
            "classified",
            detail,
        )

        logger.info(
            "Agent processed thread %s: %s (%d iterations, %d tool calls)",
            thread_id, result.status, result.iterations, len(result.tool_calls),
        )
