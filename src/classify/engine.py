"""Classification engine — two-tier: automation rules, then LLM for all content decisions."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.classify.prompts import build_classify_system_prompt, build_classify_user_message
from src.classify.rules import classify_by_rules, resolve_communication_style
from src.llm.gateway import LLMGateway

logger = logging.getLogger(__name__)


@dataclass
class Classification:
    category: str
    confidence: str
    reasoning: str
    detected_language: str
    resolved_style: str
    source: str  # 'rules' or 'llm'


class ClassificationEngine:
    """Classifies emails using rules + LLM gateway."""

    def __init__(self, llm_gateway: LLMGateway):
        self.llm = llm_gateway

    def classify(
        self,
        sender_email: str,
        sender_name: str,
        subject: str,
        snippet: str,
        body: str,
        message_count: int,
        blacklist: list[str],
        contacts_config: dict,
        headers: dict[str, str] | None = None,
        style_config: dict | None = None,
        **llm_kwargs,
    ) -> Classification:
        """Classify an email: rules first, then LLM if needed.

        When ``headers`` are provided, the rule engine can detect automated
        emails via standard RFC headers (List-Unsubscribe, Auto-Submitted,
        Precedence, etc.) and prevent unnecessary draft generation.
        """

        # Tier 1: Rule-based automation detection (instant, free)
        rule_result = classify_by_rules(
            sender_email,
            subject,
            snippet,
            body,
            blacklist,
            headers=headers,
        )

        # Tier 2: LLM-based classification (via gateway)
        system_prompt = build_classify_system_prompt(style_config)
        llm_result = self.llm.classify(
            system=system_prompt,
            user_message=build_classify_user_message(
                sender_email, sender_name, subject, snippet, body, message_count
            ),
            **llm_kwargs,
        )

        category = llm_result.category
        reasoning = llm_result.reasoning

        # Safety net: if the rule engine detected automation signals,
        # prevent the LLM from classifying as needs_response.
        if rule_result.is_automated and category == "needs_response":
            logger.info(
                "LLM classified automated email as needs_response — overriding to fyi "
                "(rule reason: %s)",
                rule_result.reasoning,
            )
            category = "fyi"
            reasoning = f"Automated email overridden from needs_response: {reasoning}"

        # CR-02: Style resolution priority:
        # 1. Exact email match in contacts.style_overrides
        # 2. Domain pattern match in contacts.domain_overrides
        # 3. LLM-determined style from classification response
        # 4. Fallback: "business"
        config_style = resolve_communication_style(sender_email, contacts_config)
        if config_style != "business":
            # Config override found (exact email or domain match)
            style = config_style
        else:
            # No config override — use LLM-determined style, fall back to "business"
            style = llm_result.resolved_style or "business"

        return Classification(
            category=category,
            confidence=llm_result.confidence,
            reasoning=reasoning,
            detected_language=llm_result.detected_language,
            resolved_style=style,
            source="llm",
        )
