"""Context gatherer — finds related threads to enrich draft prompts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from src.context.prompts import CONTEXT_SYSTEM_PROMPT, build_context_user_message
from src.gmail.client import UserGmailClient
from src.llm.gateway import LLMGateway

logger = logging.getLogger(__name__)


@dataclass
class GatheredContext:
    """Result of context gathering — related threads for draft enrichment."""

    related_threads: list[dict[str, str]] = field(default_factory=list)
    queries_used: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def is_empty(self) -> bool:
        return len(self.related_threads) == 0

    def format_for_prompt(self) -> str:
        """Format gathered context as a block for the draft prompt."""
        if self.is_empty:
            return ""

        lines = ["--- Related emails from your mailbox ---"]
        for i, thread in enumerate(self.related_threads, 1):
            lines.append(
                f"{i}. From: {thread.get('sender', '?')} | Subject: {thread.get('subject', '?')}"
            )
            snippet = thread.get("snippet", "")
            if snippet:
                lines.append(f"   {snippet[:200]}")
        lines.append("--- End related emails ---")
        return "\n".join(lines)


class ContextGatherer:
    """Gathers related email context to enrich draft generation."""

    def __init__(self, llm_gateway: LLMGateway):
        self.llm = llm_gateway

    def gather(
        self,
        gmail_client: UserGmailClient,
        thread_id: str,
        sender: str,
        subject: str,
        body: str,
        **llm_kwargs,
    ) -> GatheredContext:
        """Gather related context from the mailbox. Never raises."""
        try:
            queries = self._generate_queries(sender, subject, body, **llm_kwargs)
            if not queries:
                return GatheredContext()

            results = self._search_and_deduplicate(
                gmail_client, queries, exclude_thread_id=thread_id
            )
            return GatheredContext(related_threads=results, queries_used=queries)

        except Exception as e:
            logger.warning("Context gathering failed (non-fatal): %s", e)
            return GatheredContext(error=str(e))

    def _generate_queries(self, sender: str, subject: str, body: str, **llm_kwargs) -> list[str]:
        """Use LLM to generate Gmail search queries."""
        user_message = build_context_user_message(sender, subject, body)
        raw = self.llm.generate_context_queries(CONTEXT_SYSTEM_PROMPT, user_message, **llm_kwargs)

        try:
            from src.llm.gateway import strip_code_fences

            queries = json.loads(strip_code_fences(raw))
            if not isinstance(queries, list):
                logger.warning("Context queries not a list: %s", raw[:200])
                return []
            # Cap at 3 queries
            return [str(q) for q in queries[:3]]
        except json.JSONDecodeError:
            logger.warning("Failed to parse context queries as JSON: %s", raw[:200])
            return []

    def _search_and_deduplicate(
        self,
        gmail_client: UserGmailClient,
        queries: list[str],
        exclude_thread_id: str,
        max_results: int = 5,
    ) -> list[dict[str, str]]:
        """Run queries, deduplicate by thread_id, exclude current thread."""
        seen_threads: set[str] = set()
        results: list[dict[str, str]] = []

        for query in queries:
            try:
                messages = gmail_client.search_metadata(query, max_results=10)
            except Exception as e:
                logger.warning("Search failed for query %r: %s", query, e)
                continue

            for msg in messages:
                if msg.thread_id == exclude_thread_id:
                    continue
                if msg.thread_id in seen_threads:
                    continue

                seen_threads.add(msg.thread_id)
                results.append(
                    {
                        "thread_id": msg.thread_id,
                        "sender": (
                            f"{msg.sender_name} <{msg.sender_email}>"
                            if msg.sender_name
                            else msg.sender_email
                        ),
                        "subject": msg.subject,
                        "snippet": msg.snippet,
                    }
                )

                if len(results) >= max_results:
                    return results

        return results
