"""Default preprocessor — pass-through for the standard pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DefaultMessage:
    """Pass-through message for the standard pipeline."""

    sender_email: str = ""
    subject: str = ""
    body: str = ""
    metadata: dict[str, Any] | None = None


def preprocess_default(
    sender_email: str,
    subject: str,
    body: str,
    headers: dict[str, str] | None = None,
) -> DefaultMessage:
    """Pass-through preprocessor — returns the message as-is."""
    return DefaultMessage(
        sender_email=sender_email,
        subject=subject,
        body=body,
    )
