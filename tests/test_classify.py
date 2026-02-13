"""Tests for classification prompts and engine wiring."""

import pytest

from src.classify.prompts import CLASSIFY_SYSTEM_PROMPT, build_classify_user_message


class TestClassifyPrompts:
    def test_system_prompt_has_categories(self):
        assert "needs_response" in CLASSIFY_SYSTEM_PROMPT
        assert "action_required" in CLASSIFY_SYSTEM_PROMPT
        assert "payment_request" in CLASSIFY_SYSTEM_PROMPT
        assert "fyi" in CLASSIFY_SYSTEM_PROMPT
        assert "waiting" in CLASSIFY_SYSTEM_PROMPT

    def test_system_prompt_requires_json(self):
        assert "JSON" in CLASSIFY_SYSTEM_PROMPT or "json" in CLASSIFY_SYSTEM_PROMPT

    def test_build_user_message(self):
        msg = build_classify_user_message(
            sender_email="test@example.com",
            sender_name="Test User",
            subject="Hello World",
            snippet="This is a test",
            body="Full body of the email.",
            message_count=2,
        )
        assert "test@example.com" in msg
        assert "Test User" in msg
        assert "Hello World" in msg
        assert "Full body of the email." in msg
        assert "2" in msg  # message count

    def test_build_user_message_truncates_body(self):
        long_body = "x" * 5000
        msg = build_classify_user_message(
            sender_email="test@example.com",
            sender_name="",
            subject="Test",
            snippet="",
            body=long_body,
        )
        # Body should be truncated to 2000 chars
        assert len(msg) < 5000

    def test_build_user_message_no_name(self):
        msg = build_classify_user_message(
            sender_email="test@example.com",
            sender_name="",
            subject="Test",
            snippet="Snippet",
            body="",
        )
        assert "From: test@example.com" in msg
