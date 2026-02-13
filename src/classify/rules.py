"""Rule-based pre-classifier — instant, free, no LLM needed.

Ported from bin/classify-phase-b with the same patterns and logic.
"""

from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    category: str
    confidence: str  # 'high', 'medium', 'low'
    reasoning: str
    matched: bool  # True if a rule matched (skip LLM)


# Payment request indicators
PAYMENT_PATTERNS = [
    r"invoice", r"faktura", r"faktúra",
    r"payment", r"platba", r"zaplatit",
    r"billing", r"account.*due", r"amount due",
    r"total.*due", r"please pay", r"kč|czk|eur|usd|\$",
    r"splatnost", r"due date",
]

# Action required indicators
ACTION_PATTERNS = [
    r"please sign", r"please approve", r"approval required",
    r"signature required", r"please confirm",
    r"action required", r"urgent", r"asap",
    r"podepsat|schválit|potvrdit|vyžaduje (akci|vašu akci)",
]

# Automated/FYI indicators
FYI_PATTERNS = [
    r"newsletter", r"automated", r"noreply", r"no-reply",
    r"notification", r"alert", r"reminder", r"report",
    r"unsubscribe", r"this is an automated message",
    r"do not reply", r"system message", r"mailer-daemon",
]

# Needs response indicators
RESPONSE_PATTERNS = [
    r"\?",  # Question mark
    r"can you\s", r"could you\s", r"would you\s", r"will you\s",
    r"please\s+(let|send|provide|check|review)",
    r"what.*think|your (opinion|thoughts|feedback)",
    r"can i.*you", r"do you.*think",
    r"co si myslíš", r"tvůj názor", r"co se ti jeví",
]


def classify_by_rules(
    sender_email: str,
    subject: str,
    snippet: str,
    body: str,
    blacklist: list[str],
) -> RuleResult:
    """
    Tier 1: Deterministic rule-based classification.

    Returns a result with matched=True if confident enough to skip LLM.
    Returns matched=False if the email should go to LLM for classification.
    """
    # Step 1: Blacklist check
    if _matches_blacklist(sender_email, blacklist):
        return RuleResult(
            category="fyi",
            confidence="high",
            reasoning=f"Sender {sender_email} matched blacklist",
            matched=True,
        )

    # Step 2: No-reply / automated sender check
    sender_lower = sender_email.lower()
    if any(pattern in sender_lower for pattern in ["noreply", "no-reply", "mailer-daemon", "notifications"]):
        return RuleResult(
            category="fyi",
            confidence="high",
            reasoning=f"Automated sender: {sender_email}",
            matched=True,
        )

    # Step 3: Content-based patterns
    content = f"{subject or ''} {snippet or ''} {body or ''}".lower()

    # Payment patterns (high confidence)
    for pattern in PAYMENT_PATTERNS:
        if re.search(pattern, content):
            return RuleResult(
                category="payment_request",
                confidence="high",
                reasoning=f"Payment pattern matched: {pattern}",
                matched=True,
            )

    # Action patterns (high confidence)
    for pattern in ACTION_PATTERNS:
        if re.search(pattern, content):
            return RuleResult(
                category="action_required",
                confidence="high",
                reasoning=f"Action pattern matched: {pattern}",
                matched=True,
            )

    # FYI patterns (high confidence)
    for pattern in FYI_PATTERNS:
        if re.search(pattern, content):
            return RuleResult(
                category="fyi",
                confidence="high",
                reasoning=f"FYI pattern matched: {pattern}",
                matched=True,
            )

    # Response patterns — medium confidence, still pass to LLM for nuance
    for pattern in RESPONSE_PATTERNS:
        if re.search(pattern, content):
            return RuleResult(
                category="needs_response",
                confidence="medium",
                reasoning=f"Response pattern matched: {pattern}",
                matched=False,  # Let LLM confirm
            )

    # No rule matched → LLM decides
    return RuleResult(
        category="fyi",
        confidence="low",
        reasoning="No rule matched",
        matched=False,
    )


def _matches_blacklist(sender_email: str, blacklist: list[str]) -> bool:
    """Check if sender matches any blacklist glob pattern."""
    sender_lower = sender_email.lower()
    for pattern in blacklist:
        if fnmatch.fnmatch(sender_lower, pattern.lower()):
            return True
    return False


def resolve_communication_style(
    sender_email: str,
    contacts_config: dict[str, Any],
) -> str:
    """Determine communication style for a sender based on contacts config.

    Priority: style_overrides (exact email) > domain_overrides > default (business).
    """
    if not contacts_config:
        return "business"

    # Exact email match
    style_overrides = contacts_config.get("style_overrides", {})
    if sender_email in style_overrides:
        return style_overrides[sender_email]

    # Domain pattern match
    domain_overrides = contacts_config.get("domain_overrides", {})
    if "@" in sender_email:
        domain = sender_email.split("@", 1)[1].lower()
        for pattern, style in domain_overrides.items():
            if fnmatch.fnmatch(domain, pattern.lower()):
                return style

    return "business"
