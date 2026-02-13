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
    ) -> Classification:
        """Classify an email: rules first, then LLM if needed."""

        # Tier 1: Rule-based (instant, free)
        rule_result = classify_by_rules(sender_email, subject, snippet, body, blacklist)

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

        style = resolve_communication_style(sender_email, contacts_config)

        return Classification(
            category=llm_result.category,
            confidence=llm_result.confidence,
            reasoning=llm_result.reasoning,
            detected_language=llm_result.detected_language,
            resolved_style=style,
            source="llm",
        )
