"""Classification engine — two-tier: fast rules, then LLM for ambiguous cases."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.classify.prompts import CLASSIFY_SYSTEM_PROMPT, build_classify_user_message
from src.classify.rules import RuleResult, classify_by_rules, resolve_communication_style
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
    ) -> Classification:
        """Classify an email: rules first, then LLM if needed.

        When ``headers`` are provided, the rule engine can detect automated
        emails via standard RFC headers (List-Unsubscribe, Auto-Submitted,
        Precedence, etc.) and prevent unnecessary draft generation.
        """

        # Tier 1: Rule-based (instant, free)
        rule_result = classify_by_rules(
            sender_email,
            subject,
            snippet,
            body,
            blacklist,
            headers=headers,
        )

        if rule_result.matched and rule_result.confidence == "high":
            style = resolve_communication_style(sender_email, contacts_config)
            return Classification(
                category=rule_result.category,
                confidence=rule_result.confidence,
                reasoning=rule_result.reasoning,
                detected_language="cs",
                resolved_style=style,
                source="rules",
            )

        # Tier 2: LLM-based (via gateway)
        llm_result = self.llm.classify(
            system=CLASSIFY_SYSTEM_PROMPT,
            user_message=build_classify_user_message(
                sender_email, sender_name, subject, snippet, body, message_count
            ),
        )

        category = llm_result.category
        reasoning = llm_result.reasoning

        # Safety net: if the rule engine detected automation signals but didn't
        # match high-confidence (e.g. action/payment patterns weren't present),
        # prevent the LLM from overriding to needs_response.
        if rule_result.is_automated and category == "needs_response":
            logger.info(
                "LLM classified automated email as needs_response — overriding to fyi "
                "(rule reason: %s)",
                rule_result.reasoning,
            )
            category = "fyi"
            reasoning = f"Automated email overridden from needs_response: {reasoning}"

        style = resolve_communication_style(sender_email, contacts_config)

        return Classification(
            category=category,
            confidence=llm_result.confidence,
            reasoning=reasoning,
            detected_language=llm_result.detected_language,
            resolved_style=style,
            source="llm",
        )
