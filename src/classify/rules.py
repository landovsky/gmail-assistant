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
    is_automated: bool = False  # True if detected as automated/machine-sent


# Payment request indicators
PAYMENT_PATTERNS = [
    r"invoice",
    r"faktura",
    r"faktúra",
    r"payment",
    r"platba",
    r"zaplatit",
    r"billing",
    r"account.*due",
    r"amount due",
    r"total.*due",
    r"please pay",
    r"kč|czk|eur|usd|\$",
    r"splatnost",
    r"due date",
]

# Action required indicators
ACTION_PATTERNS = [
    r"please sign",
    r"please approve",
    r"approval required",
    r"signature required",
    r"please confirm",
    r"action required",
    r"urgent",
    r"asap",
    r"podep(sat|is|sán)|schvál(it|en)|potvrdi[tť]|vyžaduje (akci|vašu akci)",
    # Meeting/appointment requests (EN + CS + DE)
    r"meeting request",
    r"calendar invite",
    r"attend.*meeting",
    r"schůzk[auyáě]",
    r"setkání",
    r"sejít se",
    r"potkat se",
    r"žádost o schůzku",
    r"termin",
    r"treffen",  # DE: appointment, meet
]

# Automated/FYI indicators
FYI_PATTERNS = [
    r"newsletter",
    r"automated",
    r"noreply",
    r"no-reply",
    r"notification",
    r"alert",
    r"unsubscribe",
    r"this is an automated message",
    r"do not reply",
    r"system message",
    r"mailer-daemon",
    # "report" and "reminder" removed — too generic, cause false positives
    # on legitimate emails like "can you send me the report?"
]

# Sender address patterns indicating automated/machine-generated email
AUTOMATED_SENDER_PATTERNS = [
    "noreply",
    "no-reply",
    "do-not-reply",
    "donotreply",
    "mailer-daemon",
    "postmaster",
    "notifications",
    "notification",
    "bounce",
    "bounces",
]

# Headers that reliably indicate automated/machine-sent email.
# Presence of any of these (with qualifying values) → automated.
AUTOMATED_HEADERS = {
    # RFC 3834: auto-generated or auto-replied (value != "no" means automated)
    "Auto-Submitted": lambda v: v.lower() != "no",
    # Bulk/list/auto-reply precedence
    "Precedence": lambda v: v.lower() in ("bulk", "list", "auto_reply", "junk"),
    # Mailing list identifier (RFC 2919)
    "List-Id": lambda _: True,
    # Bulk mail unsubscribe header (RFC 2369)
    "List-Unsubscribe": lambda _: True,
    # Microsoft auto-response suppression
    "X-Auto-Response-Suppress": lambda _: True,
    # Google bulk sender tracking
    "Feedback-ID": lambda _: True,
    # Common in automated transactional email
    "X-Autoreply": lambda _: True,
    "X-Autorespond": lambda _: True,
}

# Needs response indicators
RESPONSE_PATTERNS = [
    r"\?",  # Question mark
    r"can you\s",
    r"could you\s",
    r"would you\s",
    r"will you\s",
    r"please\s+(let|send|provide|check|review)",
    r"what.*think|your (opinion|thoughts|feedback)",
    r"can i.*you",
    r"do you.*think",
    # Czech: question/request patterns
    r"co si myslíš",
    r"tvůj názor",
    r"co se ti jeví",
    r"mohl[ai]?\s+bys",
    r"mohli\s+bychom",
    r"můžeš",
    r"můžete",
    r"dej\s+mi\s+vědět",
    r"ozvi\s+se",
    r"napiš\s+mi",
]


def classify_by_rules(
    sender_email: str,
    subject: str,
    snippet: str,
    body: str,
    blacklist: list[str],
    headers: dict[str, str] | None = None,
) -> RuleResult:
    """
    Tier 1: Deterministic rule-based classification.

    Returns a result with matched=True if confident enough to skip LLM.
    Returns matched=False if the email should go to LLM for classification.

    Automated emails (detected via sender patterns or email headers) are never
    classified as needs_response — they skip draft generation.  They can still
    be action_required or payment_request since those categories don't produce
    drafts but do surface useful labels.
    """
    # Step 1: Blacklist check
    if _matches_blacklist(sender_email, blacklist):
        return RuleResult(
            category="fyi",
            confidence="high",
            reasoning=f"Sender {sender_email} matched blacklist",
            matched=True,
            is_automated=True,
        )

    # Step 2: No-reply / automated sender check
    sender_lower = sender_email.lower()
    automated_sender = any(p in sender_lower for p in AUTOMATED_SENDER_PATTERNS)
    if automated_sender:
        return RuleResult(
            category="fyi",
            confidence="high",
            reasoning=f"Automated sender: {sender_email}",
            matched=True,
            is_automated=True,
        )

    # Step 3: Header-based automation detection
    automated_by_headers, header_reason = _detect_automated_headers(headers or {})

    # Step 4: Content-based patterns
    content = f"{subject or ''} {snippet or ''} {body or ''}".lower()

    # Payment patterns (high confidence) — still applies to automated emails
    for pattern in PAYMENT_PATTERNS:
        if re.search(pattern, content):
            return RuleResult(
                category="payment_request",
                confidence="high",
                reasoning=f"Payment pattern matched: {pattern}",
                matched=True,
                is_automated=automated_by_headers,
            )

    # Action patterns (high confidence) — still applies to automated emails
    for pattern in ACTION_PATTERNS:
        if re.search(pattern, content):
            return RuleResult(
                category="action_required",
                confidence="high",
                reasoning=f"Action pattern matched: {pattern}",
                matched=True,
                is_automated=automated_by_headers,
            )

    # FYI patterns (high confidence)
    for pattern in FYI_PATTERNS:
        if re.search(pattern, content):
            return RuleResult(
                category="fyi",
                confidence="high",
                reasoning=f"FYI pattern matched: {pattern}",
                matched=True,
                is_automated=automated_by_headers,
            )

    # Automated email detected via headers — no action/payment pattern matched,
    # so classify as fyi to prevent draft generation.
    if automated_by_headers:
        return RuleResult(
            category="fyi",
            confidence="high",
            reasoning=f"Automated email: {header_reason}",
            matched=True,
            is_automated=True,
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


def _detect_automated_headers(headers: dict[str, str]) -> tuple[bool, str]:
    """Check email headers for signals that the message is automated.

    Returns (is_automated, reason_string).
    """
    for header_name, check_fn in AUTOMATED_HEADERS.items():
        value = headers.get(header_name)
        if value is not None and check_fn(value):
            return True, f"header {header_name}: {value[:80]}"
    return False, ""


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
