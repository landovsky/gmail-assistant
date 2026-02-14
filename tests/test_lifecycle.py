"""Tests for lifecycle manager and draft prompts."""

from src.draft.prompts import (
    build_rework_user_message,
    extract_rework_instruction,
    wrap_draft_with_marker,
)


class TestReworkMarker:
    def test_wrap_draft(self):
        body = "Hello, here is my reply."
        result = wrap_draft_with_marker(body)
        assert "✂️" in result
        assert result.endswith("Hello, here is my reply.")

    def test_extract_instruction_with_marker(self):
        draft = "Please make it shorter\n\n✂️\n\nDobrý den, here is the draft."
        instruction, below = extract_rework_instruction(draft)
        assert instruction == "Please make it shorter"
        assert "Dobrý den" in below

    def test_extract_no_marker(self):
        draft = "Just a plain draft."
        instruction, below = extract_rework_instruction(draft)
        assert instruction == ""
        assert below == "Just a plain draft."

    def test_extract_empty_instruction(self):
        draft = "\n\n✂️\n\nThe actual draft."
        instruction, below = extract_rework_instruction(draft)
        assert instruction == ""
        assert "The actual draft." in below

    def test_extract_multiline_instruction(self):
        draft = "Line 1\nLine 2\nLine 3\n\n✂️\n\nDraft content."
        instruction, below = extract_rework_instruction(draft)
        assert "Line 1" in instruction
        assert "Line 3" in instruction
        assert "Draft content." in below


class TestReworkUserMessage:
    """CR-03: Rework prompt now includes related context."""

    def test_rework_message_without_context(self):
        msg = build_rework_user_message(
            sender_email="alice@example.com",
            sender_name="Alice",
            subject="Project update",
            thread_body="Hi, how's the project?",
            current_draft="Dobrý den, here is my reply.",
            rework_instruction="Make it shorter",
            rework_count=0,
        )
        assert "alice@example.com" in msg
        assert "Project update" in msg
        assert "Make it shorter" in msg
        assert "Related emails" not in msg

    def test_rework_message_with_context(self):
        context = "--- Related emails from your mailbox ---\n1. From: Bob | Subject: Old thread\n   Previous discussion about the project\n--- End related emails ---"
        msg = build_rework_user_message(
            sender_email="alice@example.com",
            sender_name="Alice",
            subject="Project update",
            thread_body="Hi, how's the project?",
            current_draft="Dobrý den, here is my reply.",
            rework_instruction="Make it shorter",
            rework_count=0,
            related_context=context,
        )
        assert "--- Related emails from your mailbox ---" in msg
        assert "Previous discussion about the project" in msg
        assert "--- End related emails ---" in msg
        # Context should appear between thread and current draft
        thread_pos = msg.index("Hi, how's the project?")
        context_pos = msg.index("Related emails")
        draft_pos = msg.index("Current draft:")
        assert thread_pos < context_pos < draft_pos

    def test_rework_message_context_none_is_same_as_no_context(self):
        msg_without = build_rework_user_message(
            sender_email="a@b.com",
            sender_name="",
            subject="S",
            thread_body="B",
            current_draft="D",
            rework_instruction="I",
            rework_count=0,
        )
        msg_with_none = build_rework_user_message(
            sender_email="a@b.com",
            sender_name="",
            subject="S",
            thread_body="B",
            current_draft="D",
            rework_instruction="I",
            rework_count=0,
            related_context=None,
        )
        assert msg_without == msg_with_none
