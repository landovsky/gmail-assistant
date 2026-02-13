"""Crisp email preprocessor — parse Crisp forwarding format.

Crisp forwards customer support emails from the helpdesk to Gmail.
This preprocessor extracts structured data (patient name, original message,
contact info) from the forwarded email body.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Common Crisp forwarding patterns
_NAME_RE = re.compile(r"(?:From|Od|Name|Jméno):\s*(.+?)(?:\n|$)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_SEPARATOR_RE = re.compile(r"-{3,}|={3,}|_{3,}|—{3,}")


@dataclass
class CrispMessage:
    """Parsed Crisp forwarded message."""

    patient_name: str = ""
    patient_email: str = ""
    original_message: str = ""
    raw_body: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_crisp_email(
    sender_email: str,
    subject: str,
    body: str,
    headers: dict[str, str] | None = None,
) -> CrispMessage:
    """Parse a Crisp-forwarded email into structured data.

    This is a best-effort parser. The exact Crisp format may vary,
    so we extract what we can and pass the rest through.
    """
    headers = headers or {}
    result = CrispMessage(raw_body=body)

    # Try to extract patient name from body
    name_match = _NAME_RE.search(body)
    if name_match:
        result.patient_name = name_match.group(1).strip()

    # Try to extract patient email from body or Reply-To header
    reply_to = headers.get("Reply-To", "")
    if reply_to:
        email_match = _EMAIL_RE.search(reply_to)
        if email_match:
            result.patient_email = email_match.group()

    if not result.patient_email:
        # Look for email addresses in body that aren't the forwarding address
        emails = _EMAIL_RE.findall(body)
        for email in emails:
            if "dostupnost-leku" not in email.lower() and email != sender_email:
                result.patient_email = email
                break

    # Extract the original message — look for content after separators
    # or take the body without the header metadata
    parts = _SEPARATOR_RE.split(body, maxsplit=1)
    if len(parts) > 1:
        # Message is after the separator
        result.original_message = parts[1].strip()
    else:
        # No separator — use the whole body, stripping any metadata lines at the top
        lines = body.strip().split("\n")
        message_lines = []
        past_headers = False
        for line in lines:
            if past_headers:
                message_lines.append(line)
            elif _NAME_RE.match(line) or _EMAIL_RE.match(line):
                continue  # Skip metadata-like lines at the top
            else:
                past_headers = True
                message_lines.append(line)
        result.original_message = "\n".join(message_lines).strip()

    if not result.original_message:
        result.original_message = body.strip()

    return result


def format_for_agent(crisp_msg: CrispMessage, subject: str) -> str:
    """Format a parsed Crisp message as structured input for the agent."""
    parts = [f"Subject: {subject}"]
    if crisp_msg.patient_name:
        parts.append(f"Patient name: {crisp_msg.patient_name}")
    if crisp_msg.patient_email:
        parts.append(f"Patient email: {crisp_msg.patient_email}")
    parts.append("")
    parts.append("Message:")
    parts.append(crisp_msg.original_message)
    return "\n".join(parts)
