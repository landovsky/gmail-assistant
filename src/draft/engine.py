"""Draft engine — generates email reply drafts via LLM gateway."""

from __future__ import annotations

import logging

from src.config import load_communication_styles
from src.draft.prompts import (
    build_draft_system_prompt,
    build_draft_user_message,
    build_rework_user_message,
    extract_rework_instruction,
    wrap_draft_with_marker,
)
from src.gmail.client import UserGmailClient
from src.llm.gateway import LLMGateway

logger = logging.getLogger(__name__)


class DraftEngine:
    """Generates email drafts using LLM gateway."""

    def __init__(self, llm_gateway: LLMGateway):
        self.llm = llm_gateway

    def generate_draft(
        self,
        sender_email: str,
        sender_name: str,
        subject: str,
        thread_body: str,
        resolved_style: str,
        user_instructions: str | None = None,
        style_config: dict | None = None,
        related_context: str | None = None,
    ) -> str:
        """Generate a draft reply. Returns the full draft body with rework marker."""
        if style_config is None:
            style_config = load_communication_styles()

        system_prompt = build_draft_system_prompt(style_config, resolved_style)
        user_message = build_draft_user_message(
            sender_email,
            sender_name,
            subject,
            thread_body,
            user_instructions,
            related_context,
        )

        raw_draft = self.llm.draft(system_prompt, user_message)
        return wrap_draft_with_marker(raw_draft)

    def rework_draft(
        self,
        sender_email: str,
        sender_name: str,
        subject: str,
        thread_body: str,
        current_draft_body: str,
        rework_count: int,
        resolved_style: str,
        style_config: dict | None = None,
    ) -> tuple[str, str]:
        """Rework an existing draft based on user instructions.

        Returns (new_draft_body_with_marker, extracted_instruction).
        """
        if style_config is None:
            style_config = load_communication_styles()

        # Extract instruction from above the marker
        instruction, old_draft = extract_rework_instruction(current_draft_body)
        if not instruction:
            instruction = "(no specific instruction provided)"

        system_prompt = build_draft_system_prompt(style_config, resolved_style)
        user_message = build_rework_user_message(
            sender_email,
            sender_name,
            subject,
            thread_body,
            old_draft,
            instruction,
            rework_count,
        )

        raw_draft = self.llm.draft(system_prompt, user_message)

        # If this is the last allowed rework (count will become 3), add warning
        if rework_count + 1 >= 3:
            raw_draft = (
                "⚠️ This is the last automatic rework. "
                "Further changes must be made manually.\n\n" + raw_draft
            )

        return wrap_draft_with_marker(raw_draft), instruction

    def create_gmail_draft(
        self,
        gmail_client: UserGmailClient,
        thread_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> str | None:
        """Create the draft in Gmail and return draft_id."""
        return gmail_client.create_draft(thread_id, to, subject, body, in_reply_to)
