"""Tests for LLM classification (Tier 2) with mocked gateway.

Tests the ClassificationEngine end-to-end: rules + LLM fallback.
Also tests the ClassifyResult parser for robustness, including resolved_style.
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
            "resolved_style": "formal",
        }
        result = ClassifyResult.parse(self._make_response(json.dumps(data)))
        assert result.category == "action_required"
        assert result.confidence == "high"
        assert result.reasoning == "Meeting request"
        assert result.detected_language == "cs"
        assert result.resolved_style == "formal"

    def test_valid_json_with_whitespace(self):
        content = """
        {
            "category": "needs_response",
            "confidence": "medium",
            "reasoning": "Direct question",
            "detected_language": "en",
            "resolved_style": "business"
        }
        """
        result = ClassifyResult.parse(self._make_response(content))
        assert result.category == "needs_response"
        assert result.resolved_style == "business"

    def test_invalid_json_defaults_to_needs_response(self):
        """Parse errors should default to needs_response, not fyi."""
        result = ClassifyResult.parse(self._make_response("This is not JSON"))
        assert result.category == "needs_response"
        assert result.confidence == "low"
        assert "Parse error" in result.reasoning
        assert result.resolved_style == "business"

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

    def test_missing_resolved_style_defaults_to_business(self):
        data = {"category": "needs_response", "confidence": "high", "reasoning": "test"}
        result = ClassifyResult.parse(self._make_response(json.dumps(data)))
        assert result.resolved_style == "business"

    def test_resolved_style_parsed(self):
        data = {
            "category": "needs_response",
            "confidence": "high",
            "reasoning": "test",
            "resolved_style": "informal",
        }
        result = ClassifyResult.parse(self._make_response(json.dumps(data)))
        assert result.resolved_style == "informal"


# ── ClassificationEngine integration tests ───────────────────────────────────


class TestClassificationEngine:
    """Test the full two-tier pipeline with mocked LLM."""

    def _make_engine(
        self, llm_category: str = "needs_response", llm_style: str = "business"
    ) -> ClassificationEngine:
        """Create engine with a mocked LLM gateway."""
        mock_gateway = MagicMock(spec=LLMGateway)
        mock_gateway.classify.return_value = ClassifyResult(
            category=llm_category,
            confidence="high",
            reasoning=f"LLM classified as {llm_category}",
            detected_language="cs",
            resolved_style=llm_style,
        )
        return ClassificationEngine(mock_gateway)

    def test_llm_handles_all_classification(self):
        """LLM handles all classification — content patterns removed from rules."""
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


# ── CR-02: Style resolution priority ────────────────────────────────────────


class TestStyleResolution:
    """CR-02: Style priority: exact email > domain > LLM-determined > fallback."""

    def _make_engine(self, llm_style: str = "business") -> ClassificationEngine:
        mock_gateway = MagicMock(spec=LLMGateway)
        mock_gateway.classify.return_value = ClassifyResult(
            category="needs_response",
            confidence="high",
            reasoning="test",
            detected_language="cs",
            resolved_style=llm_style,
        )
        return ClassificationEngine(mock_gateway)

    def test_exact_email_override_beats_llm(self):
        """Exact email match in contacts overrides LLM-determined style."""
        engine = self._make_engine(llm_style="informal")
        result = engine.classify(
            sender_email="teacher@school.cz",
            sender_name="Teacher",
            subject="Question",
            snippet="",
            body="How are the grades?",
            message_count=1,
            blacklist=[],
            contacts_config={
                "style_overrides": {"teacher@school.cz": "formal"},
                "domain_overrides": {},
            },
        )
        assert result.resolved_style == "formal"

    def test_domain_override_beats_llm(self):
        """Domain match in contacts overrides LLM-determined style."""
        engine = self._make_engine(llm_style="informal")
        result = engine.classify(
            sender_email="official@example.gov.cz",
            sender_name="Official",
            subject="Notice",
            snippet="",
            body="Your case is under review.",
            message_count=1,
            blacklist=[],
            contacts_config={
                "style_overrides": {},
                "domain_overrides": {"*.gov.cz": "formal"},
            },
        )
        assert result.resolved_style == "formal"

    def test_llm_style_used_when_no_override(self):
        """When no config override exists, LLM-determined style is used."""
        engine = self._make_engine(llm_style="informal")
        result = engine.classify(
            sender_email="friend@example.com",
            sender_name="Friend",
            subject="Hey",
            snippet="",
            body="What's up?",
            message_count=1,
            blacklist=[],
            contacts_config={},
        )
        assert result.resolved_style == "informal"

    def test_fallback_to_business(self):
        """When LLM returns no style and no config override, defaults to business."""
        engine = self._make_engine(llm_style="")
        result = engine.classify(
            sender_email="person@example.com",
            sender_name="Person",
            subject="Hi",
            snippet="",
            body="Hello.",
            message_count=1,
            blacklist=[],
            contacts_config={},
        )
        assert result.resolved_style == "business"


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
        """Automated email where LLM returns action_required — safety net only overrides needs_response."""
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
        # LLM says action_required — safety net only overrides needs_response
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
