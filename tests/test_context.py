"""Tests for context gathering — query generation, search, deduplication."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.context.gatherer import ContextGatherer, GatheredContext
from src.context.prompts import CONTEXT_SYSTEM_PROMPT, build_context_user_message
from src.draft.prompts import build_draft_user_message
from src.gmail.models import Message


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_message(
    msg_id: str,
    thread_id: str,
    sender_email: str = "sender@example.com",
    sender_name: str = "",
    subject: str = "Test Subject",
    snippet: str = "Test snippet",
) -> Message:
    return Message(
        id=msg_id,
        thread_id=thread_id,
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        snippet=snippet,
    )


def _mock_gateway(raw_response: str = '["from:test@example.com", "project alpha"]'):
    gw = MagicMock()
    gw.generate_context_queries.return_value = raw_response
    return gw


def _mock_gmail_client(messages_per_query: list[list[Message]] | None = None):
    client = MagicMock()
    if messages_per_query is not None:
        client.search_metadata.side_effect = messages_per_query
    else:
        client.search_metadata.return_value = []
    return client


# ── Query parsing tests ──────────────────────────────────────────────────────


class TestQueryParsing:
    def test_valid_json_returns_list(self):
        gw = _mock_gateway('["from:test@example.com", "project alpha", "invoice 123"]')
        gatherer = ContextGatherer(gw)
        queries = gatherer._generate_queries("test@example.com", "Subject", "Body")
        assert queries == ["from:test@example.com", "project alpha", "invoice 123"]

    def test_malformed_json_returns_empty(self):
        gw = _mock_gateway("this is not json")
        gatherer = ContextGatherer(gw)
        queries = gatherer._generate_queries("test@example.com", "Subject", "Body")
        assert queries == []

    def test_more_than_3_queries_capped(self):
        gw = _mock_gateway('["q1", "q2", "q3", "q4", "q5"]')
        gatherer = ContextGatherer(gw)
        queries = gatherer._generate_queries("test@example.com", "Subject", "Body")
        assert len(queries) == 3
        assert queries == ["q1", "q2", "q3"]

    def test_non_array_returns_empty(self):
        gw = _mock_gateway('{"query": "from:test@example.com"}')
        gatherer = ContextGatherer(gw)
        queries = gatherer._generate_queries("test@example.com", "Subject", "Body")
        assert queries == []

    def test_empty_array_returns_empty(self):
        gw = _mock_gateway("[]")
        gatherer = ContextGatherer(gw)
        queries = gatherer._generate_queries("test@example.com", "Subject", "Body")
        assert queries == []


# ── Search and dedup tests ───────────────────────────────────────────────────


class TestSearchAndDeduplicate:
    def test_current_thread_excluded(self):
        gw = _mock_gateway()
        gatherer = ContextGatherer(gw)

        messages = [
            _make_message("m1", "current_thread"),
            _make_message("m2", "other_thread"),
        ]
        client = _mock_gmail_client([[messages[0], messages[1]]])

        results = gatherer._search_and_deduplicate(
            client, ["from:test@example.com"], exclude_thread_id="current_thread"
        )
        assert len(results) == 1
        assert results[0]["thread_id"] == "other_thread"

    def test_duplicates_across_queries_deduped(self):
        gw = _mock_gateway()
        gatherer = ContextGatherer(gw)

        msg = _make_message("m1", "thread_a", subject="Same Thread")
        client = _mock_gmail_client([[msg], [msg]])

        results = gatherer._search_and_deduplicate(
            client, ["query1", "query2"], exclude_thread_id="none"
        )
        assert len(results) == 1

    def test_capped_at_5_results(self):
        gw = _mock_gateway()
        gatherer = ContextGatherer(gw)

        messages = [_make_message(f"m{i}", f"thread_{i}") for i in range(10)]
        client = _mock_gmail_client([messages])

        results = gatherer._search_and_deduplicate(client, ["query1"], exclude_thread_id="none")
        assert len(results) == 5

    def test_search_failure_skips_query(self):
        gw = _mock_gateway()
        gatherer = ContextGatherer(gw)

        msg = _make_message("m1", "thread_a")
        client = MagicMock()
        client.search_metadata.side_effect = [Exception("API error"), [msg]]

        results = gatherer._search_and_deduplicate(
            client, ["bad_query", "good_query"], exclude_thread_id="none"
        )
        assert len(results) == 1


# ── GatheredContext tests ────────────────────────────────────────────────────


class TestGatheredContext:
    def test_is_empty_when_no_threads(self):
        ctx = GatheredContext()
        assert ctx.is_empty is True

    def test_is_empty_false_when_threads_present(self):
        ctx = GatheredContext(
            related_threads=[{"thread_id": "t1", "sender": "a", "subject": "b", "snippet": "c"}]
        )
        assert ctx.is_empty is False

    def test_format_for_prompt_empty(self):
        ctx = GatheredContext()
        assert ctx.format_for_prompt() == ""

    def test_format_for_prompt_structure(self):
        ctx = GatheredContext(
            related_threads=[
                {
                    "thread_id": "t1",
                    "sender": "Alice <alice@example.com>",
                    "subject": "Project update",
                    "snippet": "Here is the latest...",
                },
                {
                    "thread_id": "t2",
                    "sender": "bob@example.com",
                    "subject": "Invoice",
                    "snippet": "Please pay",
                },
            ]
        )
        result = ctx.format_for_prompt()
        assert "--- Related emails from your mailbox ---" in result
        assert "--- End related emails ---" in result
        assert "1. From: Alice <alice@example.com>" in result
        assert "Subject: Project update" in result
        assert "2. From: bob@example.com" in result
        assert "Here is the latest..." in result

    def test_format_for_prompt_truncates_snippet(self):
        long_snippet = "x" * 500
        ctx = GatheredContext(
            related_threads=[
                {"thread_id": "t1", "sender": "a", "subject": "b", "snippet": long_snippet},
            ]
        )
        result = ctx.format_for_prompt()
        # Snippet should be capped at 200 chars
        assert "x" * 200 in result
        assert "x" * 201 not in result

    def test_error_preserved(self):
        ctx = GatheredContext(error="LLM timeout")
        assert ctx.error == "LLM timeout"
        assert ctx.is_empty is True


# ── End-to-end gather tests ──────────────────────────────────────────────────


class TestGather:
    def test_happy_path(self):
        gw = _mock_gateway('["from:alice@example.com", "project alpha"]')
        gatherer = ContextGatherer(gw)

        messages_q1 = [
            _make_message("m1", "thread_1", sender_email="alice@example.com", subject="Old thread")
        ]
        messages_q2 = [_make_message("m2", "thread_2", subject="Alpha update")]
        client = _mock_gmail_client([messages_q1, messages_q2])

        ctx = gatherer.gather(client, "current_thread", "alice@example.com", "Re: Alpha", "body")
        assert not ctx.is_empty
        assert len(ctx.related_threads) == 2
        assert ctx.queries_used == ["from:alice@example.com", "project alpha"]
        assert ctx.error is None

    def test_llm_failure_returns_empty(self):
        gw = MagicMock()
        gw.generate_context_queries.side_effect = Exception("LLM down")
        gatherer = ContextGatherer(gw)

        client = _mock_gmail_client()
        ctx = gatherer.gather(client, "thread_1", "a@b.com", "Sub", "Body")
        assert ctx.is_empty

    def test_search_failure_returns_graceful(self):
        gw = _mock_gateway('["from:test@example.com"]')
        gatherer = ContextGatherer(gw)

        client = MagicMock()
        client.search_metadata.side_effect = Exception("Gmail API error")

        ctx = gatherer.gather(client, "thread_1", "test@example.com", "Sub", "Body")
        # Should return empty context (no results), not raise
        assert ctx.is_empty or ctx.error is None  # either no results or graceful

    def test_empty_queries_returns_empty_context(self):
        gw = _mock_gateway("[]")
        gatherer = ContextGatherer(gw)

        client = _mock_gmail_client()
        ctx = gatherer.gather(client, "thread_1", "a@b.com", "Sub", "Body")
        assert ctx.is_empty


# ── Prompt integration tests ─────────────────────────────────────────────────


class TestPromptIntegration:
    def test_build_draft_user_message_without_context(self):
        msg = build_draft_user_message(
            sender_email="test@example.com",
            sender_name="Test",
            subject="Hello",
            thread_body="How are you?",
        )
        assert "Related emails" not in msg
        assert "test@example.com" in msg
        assert "How are you?" in msg

    def test_build_draft_user_message_with_context(self):
        context = "--- Related emails from your mailbox ---\n1. From: a | Subject: b\n--- End related emails ---"
        msg = build_draft_user_message(
            sender_email="test@example.com",
            sender_name="Test",
            subject="Hello",
            thread_body="How are you?",
            related_context=context,
        )
        assert "--- Related emails from your mailbox ---" in msg
        assert "--- End related emails ---" in msg
        # Context should appear after thread body
        thread_pos = msg.index("How are you?")
        context_pos = msg.index("Related emails")
        assert context_pos > thread_pos

    def test_build_draft_user_message_context_before_instructions(self):
        context = "--- Related emails from your mailbox ---\n1. From: a | Subject: b\n--- End related emails ---"
        msg = build_draft_user_message(
            sender_email="test@example.com",
            sender_name="Test",
            subject="Hello",
            thread_body="How are you?",
            user_instructions="Be brief",
            related_context=context,
        )
        context_pos = msg.index("Related emails")
        instructions_pos = msg.index("User instructions")
        assert context_pos < instructions_pos


# ── Prompt content tests ─────────────────────────────────────────────────────


class TestContextPrompts:
    def test_system_prompt_mentions_json(self):
        assert "JSON" in CONTEXT_SYSTEM_PROMPT or "json" in CONTEXT_SYSTEM_PROMPT

    def test_system_prompt_mentions_sender(self):
        assert "from:" in CONTEXT_SYSTEM_PROMPT

    def test_build_context_user_message(self):
        msg = build_context_user_message("alice@example.com", "Project update", "Latest status")
        assert "alice@example.com" in msg
        assert "Project update" in msg
        assert "Latest status" in msg

    def test_build_context_user_message_truncates_body(self):
        long_body = "x" * 3000
        msg = build_context_user_message("a@b.com", "Sub", long_body)
        # Body should be truncated to 1500 chars
        assert len(msg) < 3000
