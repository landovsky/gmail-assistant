"""Config-driven matching rules for email routing."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.config import RoutingRuleConfig

logger = logging.getLogger(__name__)


def matches_rule(rule: RoutingRuleConfig, message_meta: dict[str, Any]) -> bool:
    """Check if a message matches a routing rule.

    Supported match keys:
        - all: true — matches everything (default/fallback rule)
        - forwarded_from: str — matches if the original sender (via forwarding headers
          or body) matches this address
        - sender_domain: str — matches if the sender email domain matches
        - sender_email: str — exact match on sender email
        - subject_contains: str — case-insensitive substring match on subject
        - header_match: dict — matches specific header values (key: regex pattern)

    Args:
        rule: A routing rule config
        message_meta: Dict with keys: sender_email, subject, headers, body
    """
    match = rule.match

    if not match:
        return False

    if match.get("all") is True:
        return True

    sender_email = message_meta.get("sender_email", "")
    subject = message_meta.get("subject", "")
    headers = message_meta.get("headers", {})
    body = message_meta.get("body", "")

    # forwarded_from: check X-Forwarded-From header, From header in forwarded body,
    # or the Crisp forwarding pattern
    if "forwarded_from" in match:
        target = match["forwarded_from"].lower()
        # Check headers
        fwd_header = headers.get("X-Forwarded-From", "").lower()
        if target in fwd_header:
            return True
        # Check if sender matches directly
        if target == sender_email.lower():
            return True
        # Check Reply-To header
        reply_to = headers.get("Reply-To", "").lower()
        if target in reply_to:
            return True
        # Check body for forwarded-from pattern
        if target in body.lower():
            return True
        return False

    # sender_domain: match domain part of sender email
    if "sender_domain" in match:
        target_domain = match["sender_domain"].lower()
        if "@" in sender_email:
            domain = sender_email.split("@")[1].lower()
            if domain != target_domain:
                return False
        else:
            return False

    # sender_email: exact match
    if "sender_email" in match:
        if sender_email.lower() != match["sender_email"].lower():
            return False

    # subject_contains: case-insensitive substring
    if "subject_contains" in match:
        if match["subject_contains"].lower() not in subject.lower():
            return False

    # header_match: dict of header_name -> regex pattern
    if "header_match" in match:
        for header_name, pattern in match["header_match"].items():
            header_value = headers.get(header_name, "")
            if not re.search(pattern, header_value, re.IGNORECASE):
                return False

    return True
