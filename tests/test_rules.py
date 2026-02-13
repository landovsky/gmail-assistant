"""Tests for rule-based classification engine."""

import pytest

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
        # Normal sender with no blacklist — not matched by blacklist
        assert result.reasoning != "Sender colleague@company.com matched blacklist"


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


class TestPaymentPatterns:
    def test_invoice_in_subject(self):
        result = classify_by_rules(
            sender_email="vendor@company.com",
            subject="Invoice #12345",
            snippet="",
            body="",
            blacklist=[],
        )
        assert result.category == "payment_request"
        assert result.confidence == "high"

    def test_faktura_czech(self):
        result = classify_by_rules(
            sender_email="vendor@firma.cz",
            subject="Faktura za služby",
            snippet="",
            body="",
            blacklist=[],
        )
        assert result.category == "payment_request"

    def test_amount_in_body(self):
        result = classify_by_rules(
            sender_email="vendor@company.com",
            subject="Services",
            snippet="",
            body="Please pay 5000 CZK by end of month",
            blacklist=[],
        )
        assert result.category == "payment_request"


class TestActionPatterns:
    def test_please_sign(self):
        result = classify_by_rules(
            sender_email="hr@company.com",
            subject="Contract",
            snippet="Please sign the attached document",
            body="",
            blacklist=[],
        )
        assert result.category == "action_required"

    def test_approval_required(self):
        result = classify_by_rules(
            sender_email="system@company.com",
            subject="Approval required",
            snippet="",
            body="",
            blacklist=[],
        )
        assert result.category == "action_required"


class TestFYIPatterns:
    def test_newsletter(self):
        result = classify_by_rules(
            sender_email="editor@news.com",
            subject="Weekly Newsletter",
            snippet="",
            body="Click to unsubscribe",
            blacklist=[],
        )
        assert result.category == "fyi"

    def test_automated_message(self):
        result = classify_by_rules(
            sender_email="system@company.com",
            subject="Report",
            snippet="This is an automated message",
            body="",
            blacklist=[],
        )
        assert result.category == "fyi"


class TestResponsePatterns:
    def test_question_mark(self):
        result = classify_by_rules(
            sender_email="colleague@company.com",
            subject="Meeting",
            snippet="",
            body="Are you free tomorrow?",
            blacklist=[],
        )
        # Question marks trigger needs_response but with matched=False (pass to LLM)
        assert result.category == "needs_response"

    def test_can_you(self):
        result = classify_by_rules(
            sender_email="boss@company.com",
            subject="Task",
            snippet="Can you review this document",
            body="",
            blacklist=[],
        )
        assert result.category == "needs_response"


class TestNoMatch:
    def test_ambiguous_email(self):
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
