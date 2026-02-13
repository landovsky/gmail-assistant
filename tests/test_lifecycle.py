"""Tests for lifecycle manager and draft prompts."""

import pytest

from src.draft.prompts import extract_rework_instruction, wrap_draft_with_marker


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
