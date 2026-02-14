"""Lifecycle manager — handles label state machine transitions.

Replaces the cleanup.md and rework-draft.md Claude commands with
deterministic Python code. These operations need zero LLM intelligence.
"""

from __future__ import annotations

import logging
from typing import Any

from src.context.gatherer import ContextGatherer
from src.db.models import EmailRepository, EventRepository, LabelRepository
from src.db.connection import Database
from src.draft.engine import DraftEngine
from src.gmail.client import UserGmailClient

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manages email lifecycle transitions — Done, Sent, Waiting, Rework."""

    def __init__(
        self,
        db: Database,
        draft_engine: DraftEngine | None = None,
        context_gatherer: ContextGatherer | None = None,
    ):
        self.db = db
        self.emails = EmailRepository(db)
        self.events = EventRepository(db)
        self.labels = LabelRepository(db)
        self.draft_engine = draft_engine
        self.context_gatherer = context_gatherer

    def handle_done(
        self,
        user_id: int,
        thread_id: str,
        gmail_client: UserGmailClient,
    ) -> bool:
        """User marked thread as Done → strip AI labels, archive."""
        label_ids = self.labels.get_labels(user_id)
        ai_label_ids = [
            v for k, v in label_ids.items()
            if k in ("needs_response", "outbox", "rework", "action_required",
                      "payment_request", "fyi", "waiting")
        ]

        # Get all messages in thread
        thread = gmail_client.get_thread(thread_id)
        if not thread:
            logger.error("Thread %s not found", thread_id)
            return False

        message_ids = [m.id for m in thread.messages]

        # Remove all AI labels + INBOX, keep Done label
        remove_labels = ai_label_ids + ["INBOX"]
        gmail_client.batch_modify_labels(message_ids, remove=remove_labels)

        # Update DB
        self.emails.update_status(user_id, thread_id, "archived", acted_at="CURRENT_TIMESTAMP")
        self.events.log(user_id, thread_id, "archived", "Done cleanup: archived thread, kept Done label")

        logger.info("Archived thread %s for user %d", thread_id, user_id)
        return True

    def handle_sent_detection(
        self,
        user_id: int,
        thread_id: str,
        gmail_client: UserGmailClient,
    ) -> bool:
        """Draft disappeared → check if sent."""
        email = self.emails.get_by_thread(user_id, thread_id)
        if not email or not email.get("draft_id"):
            return False

        draft_id = email["draft_id"]

        # Check if draft still exists
        draft = gmail_client.get_draft(draft_id)
        if draft is not None:
            return False  # Draft still exists, not sent

        # Draft is gone → likely sent
        label_ids = self.labels.get_labels(user_id)
        outbox_label = label_ids.get("outbox")

        if outbox_label:
            # Find messages in thread and remove Outbox label
            thread = gmail_client.get_thread(thread_id)
            if thread:
                msg_ids = [m.id for m in thread.messages]
                gmail_client.batch_modify_labels(msg_ids, remove=[outbox_label])

        self.emails.update_status(user_id, thread_id, "sent", acted_at="CURRENT_TIMESTAMP")
        self.events.log(user_id, thread_id, "sent_detected", "Draft no longer exists, marking as sent")

        logger.info("Detected sent draft for thread %s", thread_id)
        return True

    def handle_waiting_retriage(
        self,
        user_id: int,
        thread_id: str,
        gmail_client: UserGmailClient,
    ) -> bool:
        """New reply on a Waiting thread → remove Waiting label for reclassification."""
        email = self.emails.get_by_thread(user_id, thread_id)
        if not email:
            return False

        stored_count = email.get("message_count", 0)

        # Check current message count
        thread = gmail_client.get_thread(thread_id)
        if not thread or thread.message_count <= stored_count:
            return False  # No new messages

        # New messages arrived — remove Waiting label
        label_ids = self.labels.get_labels(user_id)
        waiting_label = label_ids.get("waiting")

        if waiting_label:
            msg_ids = [m.id for m in thread.messages]
            gmail_client.batch_modify_labels(msg_ids, remove=[waiting_label])

        self.events.log(
            user_id, thread_id, "waiting_retriaged",
            f"New reply detected ({thread.message_count} vs stored {stored_count}), removed Waiting label",
        )

        logger.info("Retriaged waiting thread %s (new messages)", thread_id)
        return True

    def handle_rework(
        self,
        user_id: int,
        thread_id: str,
        gmail_client: UserGmailClient,
        style_config: dict | None = None,
    ) -> bool:
        """User marked Rework → extract instructions, regenerate draft."""
        if not self.draft_engine:
            logger.error("Draft engine not configured for rework")
            return False

        email = self.emails.get_by_thread(user_id, thread_id)
        if not email:
            return False

        rework_count = email.get("rework_count", 0)
        label_ids = self.labels.get_labels(user_id)

        # Check rework limit
        if rework_count >= 3:
            # Move to Action Required
            rework_label = label_ids.get("rework")
            action_label = label_ids.get("action_required")
            if rework_label and action_label:
                thread = gmail_client.get_thread(thread_id)
                if thread:
                    msg_ids = [m.id for m in thread.messages]
                    gmail_client.batch_modify_labels(
                        msg_ids, add=[action_label], remove=[rework_label]
                    )

            self.emails.update_status(user_id, thread_id, "skipped")
            self.events.log(
                user_id, thread_id, "rework_limit_reached",
                "Rework limit (3) exceeded, moved to Action Required",
            )
            return True

        # Get current draft content
        draft_id = email.get("draft_id")
        current_draft_body = ""
        if draft_id:
            draft = gmail_client.get_draft(draft_id)
            if draft and draft.message:
                current_draft_body = draft.message.body

        # Get thread for context
        thread = gmail_client.get_thread(thread_id)
        if not thread or not thread.latest_message:
            return False

        latest = thread.latest_message
        thread_body = "\n---\n".join(m.body[:1000] for m in thread.messages)

        # CR-03: Gather related context (same as initial draft flow)
        related_context: str | None = None
        if self.context_gatherer:
            ctx = self.context_gatherer.gather(
                gmail_client,
                thread_id,
                email["sender_email"],
                email.get("subject", ""),
                thread_body,
                user_id=user_id,
                gmail_thread_id=thread_id,
            )
            if not ctx.is_empty:
                related_context = ctx.format_for_prompt()

        # Generate reworked draft
        new_draft_body, instruction = self.draft_engine.rework_draft(
            sender_email=email["sender_email"],
            sender_name=email.get("sender_name", ""),
            subject=email.get("subject", ""),
            thread_body=thread_body,
            current_draft_body=current_draft_body,
            rework_count=rework_count,
            resolved_style=email.get("resolved_style", "business"),
            style_config=style_config,
            related_context=related_context,
            user_id=user_id,
            gmail_thread_id=thread_id,
        )

        # Trash old draft
        if draft_id:
            gmail_client.trash_draft(draft_id)
            self.events.log(
                user_id, thread_id, "draft_trashed",
                "Old draft trashed for rework", draft_id=draft_id,
            )

        # Create new draft
        new_draft_id = gmail_client.create_draft(
            thread_id=thread_id,
            to=email["sender_email"],
            subject=email.get("subject", ""),
            body=new_draft_body,
            in_reply_to=email.get("gmail_message_id"),
        )

        if not new_draft_id:
            return False

        # Move label: Rework → Outbox (or Action Required if last rework)
        rework_label = label_ids.get("rework")
        msg_ids = [m.id for m in thread.messages]

        if rework_count + 1 >= 3:
            target_label = label_ids.get("action_required")
        else:
            target_label = label_ids.get("outbox")

        if rework_label and target_label:
            gmail_client.batch_modify_labels(
                msg_ids, add=[target_label], remove=[rework_label]
            )

        # Update DB
        self.emails.increment_rework(user_id, thread_id, new_draft_id, instruction)
        self.events.log(
            user_id, thread_id, "draft_reworked",
            f"Rework #{rework_count + 1}: {instruction[:100]}",
            draft_id=new_draft_id,
        )

        logger.info("Reworked draft for thread %s (rework #%d)", thread_id, rework_count + 1)
        return True
