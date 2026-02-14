"""Rule-based automation detector — identifies machine-generated emails.

CR-01: The rule tier only performs automation detection (blacklist, automated
sender patterns, header inspection). All content-based classification is
delegated to the LLM.
"""

from __future__ import annotations

import fnmatch
import logging
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


def classify_by_rules(
    sender_email: str,
    subject: str,
    snippet: str,
    body: str,
    blacklist: list[str],
    headers: dict[str, str] | None = None,
) -> RuleResult:
    """
    Tier 1: Automation detection only.

    Identifies machine-generated emails via blacklist, sender patterns, and
    RFC headers. Returns is_automated=True for the safety net.

    All content-based classification (payment, action, FYI, response patterns)
    is delegated entirely to the LLM.
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
    if automated_by_headers:
        return RuleResult(
            category="fyi",
            confidence="high",
            reasoning=f"Automated email: {header_reason}",
            matched=True,
            is_automated=True,
        )

    # No automation detected → LLM decides everything
    return RuleResult(
        category="needs_response",
        confidence="low",
        reasoning="No automation detected, passing to LLM",
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
