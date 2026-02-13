"""Tests for LLM classification (Tier 2) with mocked gateway.

Tests the ClassificationEngine end-to-end: rules + LLM fallback.
Also tests the ClassifyResult parser for robustness.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.classify.engine import Classification, ClassificationEngine
from src.llm.gateway import ClassifyResult, LLMGateway


# ── ClassifyResult parser tests ──────────────────────────────────────────────


class TestClassifyResultParser:
    """Test JSON parsing robustness of LLM responses."""

    def _make_response(self, content: str) -> MagicMock:
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = content
        return response

    def test_valid_json(self):
        data = {
            "category": "action_required",
            "confidence": "high",
            "reasoning": "Meeting request",
            "detected_language": "cs",
        }
        result = ClassifyResult.parse(self._make_response(json.dumps(data)))
        assert result.category == "action_required"
        assert result.confidence == "high"
        assert result.reasoning == "Meeting request"
        assert result.detected_language == "cs"

    def test_valid_json_with_whitespace(self):
        content = """
        {
            "category": "needs_response",
            "confidence": "medium",
            "reasoning": "Direct question",
            "detected_language": "en"
        }
        """
        result = ClassifyResult.parse(self._make_response(content))
        assert result.category == "needs_response"

    def test_invalid_json_defaults_to_needs_response(self):
        """Parse errors should default to needs_response, not fyi."""
        result = ClassifyResult.parse(self._make_response("This is not JSON"))
        assert result.category == "needs_response"
        assert result.confidence == "low"
        assert "Parse error" in result.reasoning

    def test_empty_response(self):
        result = ClassifyResult.parse(self._make_response(""))
        assert result.category == "needs_response"
        assert result.confidence == "low"

    def test_unknown_category_defaults_to_needs_response(self):
        """Unknown categories should fall back to needs_response."""
        data = {"category": "spam", "confidence": "high", "reasoning": "test"}
        result = ClassifyResult.parse(self._make_response(json.dumps(data)))
        assert result.category == "needs_response"

    def test_missing_category_defaults_to_needs_response(self):
        data = {"confidence": "high", "reasoning": "test"}
        result = ClassifyResult.parse(self._make_response(json.dumps(data)))
        assert result.category == "needs_response"

    def test_missing_confidence_defaults_to_medium(self):
        data = {"category": "fyi", "reasoning": "Newsletter"}
        result = ClassifyResult.parse(self._make_response(json.dumps(data)))
        assert result.confidence == "medium"

    def test_all_valid_categories_accepted(self):
        for cat in ["needs_response", "action_required", "payment_request", "fyi", "waiting"]:
            data = {"category": cat, "confidence": "high", "reasoning": "test"}
            result = ClassifyResult.parse(self._make_response(json.dumps(data)))
            assert result.category == cat


# ── ClassificationEngine integration tests ───────────────────────────────────


class TestClassificationEngine:
    """Test the full two-tier pipeline with mocked LLM."""

    def _make_engine(self, llm_category: str = "needs_response") -> ClassificationEngine:
        """Create engine with a mocked LLM gateway."""
        mock_gateway = MagicMock(spec=LLMGateway)
        mock_gateway.classify.return_value = ClassifyResult(
            category=llm_category,
            confidence="high",
            reasoning=f"LLM classified as {llm_category}",
            detected_language="cs",
        )
        return ClassificationEngine(mock_gateway)

    def test_rule_match_still_calls_llm(self):
        """Rule-based shortcut is disabled — LLM handles all classification."""
        engine = self._make_engine(llm_category="payment_request")
        result = engine.classify(
            sender_email="person@example.com",
            sender_name="Person",
            subject="Faktura za služby",
            snippet="",
            body="Přiložena faktura",
            message_count=1,
            blacklist=[],
            contacts_config={},
        )
        assert result.category == "payment_request"
        assert result.source == "llm"
        engine.llm.classify.assert_called_once()

    def test_no_rule_match_calls_llm(self):
        """When rules don't match, LLM is consulted."""
        engine = self._make_engine(llm_category="needs_response")
        result = engine.classify(
            sender_email="person@example.com",
            sender_name="Person",
            subject="Hey",
            snippet="",
            body="Just wanted to check in.",
            message_count=1,
            blacklist=[],
            contacts_config={},
        )
        assert result.category == "needs_response"
        assert result.source == "llm"
        engine.llm.classify.assert_called_once()

    def test_medium_confidence_rule_calls_llm(self):
        """Response patterns (medium confidence, matched=False) still call LLM."""
        engine = self._make_engine(llm_category="action_required")
        result = engine.classify(
            sender_email="person@example.com",
            sender_name="Person",
            subject="Quick question",
            snippet="",
            body="Are you available tomorrow?",
            message_count=1,
            blacklist=[],
            contacts_config={},
        )
        # The rule engine sees "?" and returns needs_response/medium/matched=False
        # So LLM is called, and LLM says action_required
        assert result.category == "action_required"
        assert result.source == "llm"

    def test_blacklist_overrides_llm_to_fyi(self):
        """Blacklisted sender: LLM still runs but automated safety net forces fyi."""
        engine = self._make_engine(llm_category="needs_response")
        result = engine.classify(
            sender_email="bot@noreply.github.com",
            sender_name="GitHub Bot",
            subject="PR review requested",
            snippet="",
            body="Please review PR #42",
            message_count=1,
            blacklist=["*@noreply.github.com"],
            contacts_config={},
        )
        assert result.category == "fyi"
        assert result.source == "llm"

    def test_czech_meeting_request_classified_by_llm(self):
        """Meeting request — LLM handles all classification now."""
        engine = self._make_engine(llm_category="action_required")
        result = engine.classify(
            sender_email="petr.ivan@example.com",
            sender_name="Petr Ivan",
            subject="žádost o schůzku",
            snippet="Mohli bychom se potkat",
            body="Dobrý den. Mohli bychom se potkat dnes odpoledne v 17:00 "
            "v Berlin Hbf na kávu? Díky. Petr Ivan",
            message_count=1,
            blacklist=[],
            contacts_config={},
        )
        assert result.category == "action_required"
        assert result.source == "llm"
        engine.llm.classify.assert_called_once()

    def test_style_resolution_for_needs_response(self):
        engine = self._make_engine(llm_category="needs_response")
        result = engine.classify(
            sender_email="teacher@school.cz",
            sender_name="Teacher",
            subject="Question",
            snippet="",
            body="How are the grades looking this semester?",
            message_count=1,
            blacklist=[],
            contacts_config={
                "style_overrides": {"teacher@school.cz": "formal"},
                "domain_overrides": {},
            },
        )
        assert result.resolved_style == "formal"

    def test_llm_error_defaults_to_needs_response(self):
        """If LLM fails entirely, should default to needs_response not fyi."""
        mock_gateway = MagicMock(spec=LLMGateway)
        mock_gateway.classify.return_value = ClassifyResult(
            category="needs_response",
            confidence="low",
            reasoning="LLM error: connection refused",
        )
        engine = ClassificationEngine(mock_gateway)
        result = engine.classify(
            sender_email="person@example.com",
            sender_name="Person",
            subject="Important",
            snippet="",
            body="Unstructured content here.",
            message_count=1,
            blacklist=[],
            contacts_config={},
        )
        assert result.category == "needs_response"


# ── Automated header safety net in engine ─────────────────────────────────


class TestAutomatedHeaderOverride:
    """When headers indicate automation, LLM needs_response is overridden to fyi."""

    def _make_engine(self, llm_category: str = "needs_response") -> ClassificationEngine:
        mock_gateway = MagicMock(spec=LLMGateway)
        mock_gateway.classify.return_value = ClassifyResult(
            category=llm_category,
            confidence="high",
            reasoning=f"LLM classified as {llm_category}",
            detected_language="en",
        )
        return ClassificationEngine(mock_gateway)

    def test_automated_header_overrides_llm_needs_response(self):
        """If LLM says needs_response but email has List-Unsubscribe → safety net overrides to fyi."""
        engine = self._make_engine(llm_category="needs_response")
        result = engine.classify(
            sender_email="team@saas.com",
            sender_name="SaaS Team",
            subject="Quick question for you",
            snippet="",
            body="Just checking in on the project.",
            message_count=1,
            blacklist=[],
            contacts_config={},
            headers={"List-Unsubscribe": "<mailto:unsub@saas.com>"},
        )
        # LLM runs but safety net detects automation header → overrides to fyi
        assert result.category == "fyi"
        assert result.source == "llm"

    def test_automated_header_allows_llm_action_required(self):
        """Automated email where LLM returns action_required — safety net overrides to fyi."""
        engine = self._make_engine(llm_category="action_required")
        result = engine.classify(
            sender_email="ci@builds.com",
            sender_name="CI Bot",
            subject="Build succeeded",
            snippet="",
            body="Your build passed all tests.",
            message_count=1,
            blacklist=[],
            contacts_config={},
            headers={"Auto-Submitted": "auto-generated"},
        )
        # LLM says action_required but safety net only overrides needs_response
        assert result.category == "action_required"
        assert result.source == "llm"

    def test_no_headers_llm_needs_response_preserved(self):
        """Without automation headers, LLM needs_response is kept."""
        engine = self._make_engine(llm_category="needs_response")
        result = engine.classify(
            sender_email="person@company.com",
            sender_name="Person",
            subject="Follow up",
            snippet="",
            body="Just following up on our conversation.",
            message_count=1,
            blacklist=[],
            contacts_config={},
        )
        assert result.category == "needs_response"
        assert result.source == "llm"
