"""Context gathering prompts — LLM generates Gmail search queries."""

from __future__ import annotations


CONTEXT_SYSTEM_PROMPT = """You generate Gmail search queries to find related emails for context.

Given an email thread (sender, subject, body), output a JSON array of 2-3 Gmail search queries
that would find related correspondence in the user's mailbox.

Rules:
- Output ONLY a JSON array of strings, nothing else.
- One query MUST be sender-based: from:sender@example.com
- Other queries should be topic-based: keywords, project names, reference numbers, company names.
- Do NOT use date operators (newer_than:, after:, before:). Let Gmail return by relevance.
- Keep queries concise — 2-4 terms each.
- Extract specific identifiers when present (invoice numbers, project codes, ticket IDs).

Example output:
["from:petr@acme.com", "acme project alpha", "invoice INV-2024-003"]"""


def build_context_user_message(
    sender: str,
    subject: str,
    body: str,
) -> str:
    """Build the user message for context query generation."""
    return f"""Sender: {sender}
Subject: {subject}

Body:
{body[:1500]}"""
