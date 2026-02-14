"""Tests for rule-based automation detection and style resolution.

CR-01: Rules only detect automation. Content pattern tests removed.
"""

from src.classify.rules import classify_by_rules, resolve_communication_style


class TestBlacklistMatching:
    def test_exact_match(self):
        result = classify_by_rules(
            sender_email="bot@noreply.github.com",
            subject="New PR",
            snippet="",
            body="",
            blacklist=["*@noreply.github.com"],
        )
        assert result.category == "fyi"
        assert result.confidence == "high"
        assert result.matched is True
        assert result.is_automated is True

    def test_no_match(self):
        result = classify_by_rules(
            sender_email="person@example.com",
            subject="Hello",
            snippet="",
            body="",
            blacklist=["*@noreply.github.com"],
        )
        assert result.matched is False

    def test_empty_blacklist_normal_sender(self):
        result = classify_by_rules(
            sender_email="colleague@company.com",
            subject="Hello",
            snippet="Quick update",
            body="",
            blacklist=[],
        )
        assert result.matched is False


class TestAutomatedSender:
    def test_noreply(self):
        result = classify_by_rules(
            sender_email="noreply@company.com",
            subject="Your order",
            snippet="",
            body="",
            blacklist=[],
        )
        assert result.category == "fyi"
        assert result.matched is True
        assert result.is_automated is True

    def test_notifications(self):
        result = classify_by_rules(
            sender_email="notifications@service.com",
            subject="Update",
            snippet="",
            body="",
            blacklist=[],
        )
        assert result.category == "fyi"
        assert result.matched is True
        assert result.is_automated is True


class TestHeaderDetection:
    def test_auto_submitted(self):
        result = classify_by_rules(
            sender_email="system@company.com",
            subject="Report",
            snippet="",
            body="",
            blacklist=[],
            headers={"Auto-Submitted": "auto-generated"},
        )
        assert result.category == "fyi"
        assert result.matched is True
        assert result.is_automated is True

    def test_list_unsubscribe(self):
        result = classify_by_rules(
            sender_email="promo@shop.com",
            subject="Sale",
            snippet="",
            body="",
            blacklist=[],
            headers={"List-Unsubscribe": "<mailto:unsub@shop.com>"},
        )
        assert result.category == "fyi"
        assert result.matched is True
        assert result.is_automated is True


class TestContentPassesToLLM:
    """Content-based emails are no longer classified by rules."""

    def test_invoice_passes_through(self):
        result = classify_by_rules(
            sender_email="vendor@company.com",
            subject="Invoice #12345",
            snippet="",
            body="",
            blacklist=[],
        )
        assert result.matched is False

    def test_action_passes_through(self):
        result = classify_by_rules(
            sender_email="hr@company.com",
            subject="Contract",
            snippet="Please sign the attached document",
            body="",
            blacklist=[],
        )
        assert result.matched is False

    def test_question_passes_through(self):
        result = classify_by_rules(
            sender_email="colleague@company.com",
            subject="Meeting",
            snippet="",
            body="Are you free tomorrow?",
            blacklist=[],
        )
        assert result.matched is False

    def test_ambiguous_passes_through(self):
        result = classify_by_rules(
            sender_email="person@company.com",
            subject="Update",
            snippet="Here's the latest version",
            body="",
            blacklist=[],
        )
        assert result.matched is False
        assert result.confidence == "low"


class TestCommunicationStyle:
    def test_exact_email_override(self):
        config = {
            "style_overrides": {"teacher@school.cz": "formal"},
            "domain_overrides": {},
        }
        assert resolve_communication_style("teacher@school.cz", config) == "formal"

    def test_domain_override(self):
        config = {
            "style_overrides": {},
            "domain_overrides": {"*.gov.cz": "formal"},
        }
        assert resolve_communication_style("official@example.gov.cz", config) == "formal"

    def test_default_business(self):
        assert resolve_communication_style("anyone@example.com", {}) == "business"

    def test_empty_config(self):
        assert resolve_communication_style("anyone@example.com", None) == "business"
