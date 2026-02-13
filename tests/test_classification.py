#!/usr/bin/env python3
"""
End-to-end tests for email classification.

Tests various email types in Czech and English, verifying that the classifier
assigns the correct category. Run with:

    python3 -m pytest tests/test_classification.py -v

Or directly:

    python3 tests/test_classification.py
"""

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path
from typing import Tuple

# Import classifier from bin/classify-phase-b (no .py extension)
REPO_ROOT = Path(__file__).parent.parent
_loader = importlib.machinery.SourceFileLoader(
    "classify_phase_b", str(REPO_ROOT / "bin" / "classify-phase-b")
)
_spec = importlib.util.spec_from_loader("classify_phase_b", _loader)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
GmailClassifier = _mod.GmailClassifier
EmailRecord = _mod.EmailRecord


def make_email(subject: str, body: str = "", sender: str = "sender@example.com") -> Tuple[EmailRecord, str]:
    """Helper to create a test email record and body."""
    record = EmailRecord(
        thread_id="test-thread",
        message_id="test-msg",
        sender_email=sender,
        sender_name="",
        subject=subject,
        snippet=body[:100],
        received_at="",
        classification="",
    )
    return record, body


def classify(subject: str, body: str = "", sender: str = "sender@example.com") -> Tuple[str, str]:
    """Classify a test email. Returns (classification, confidence)."""
    classifier = GmailClassifier()
    record, full_body = make_email(subject, body, sender)
    return classifier._classify_email(record, full_body)


# ============================================================================
# ACTION REQUIRED — Meeting requests
# ============================================================================

class TestActionRequired:
    """Emails requiring action outside of email (meetings, approvals, etc.)"""

    # -- Meeting requests (Czech) --

    def test_czech_meeting_request_subject(self):
        """The original bug: Czech meeting request was misclassified as FYI."""
        result, _ = classify(
            "žádost o schůzku",
            "Dobrý den. Mohli bychom se potkat dnes odpoledne v 17:00 v Berlin Hbf na kávu? Díky. Petr Ivan"
        )
        assert result == "action_required", f"Expected action_required, got {result}"

    def test_czech_meeting_short(self):
        result, _ = classify("Schůzka zítra?", "")
        assert result == "action_required"

    def test_czech_potkat_se(self):
        result, _ = classify("", "Můžeme se potkat v pátek?")
        assert result == "action_required"

    def test_czech_sejit_se(self):
        result, _ = classify("", "Mohli bychom se sejít a probrat to?")
        assert result == "action_required"

    def test_czech_setkani(self):
        result, _ = classify("Pozvánka na setkání", "Zveme vás na setkání rodičů.")
        assert result == "action_required"

    def test_czech_sraz(self):
        result, _ = classify("Sraz v 18:00", "Ahoj, sraz je v 18:00 u metra.")
        assert result == "action_required"

    # -- Meeting requests (English) --

    def test_english_lets_meet(self):
        result, _ = classify("Let's meet tomorrow", "Can we get together at 3pm?")
        assert result == "action_required"

    def test_english_meeting_at(self):
        result, _ = classify("Meeting at 2pm", "Please join the meeting at 2pm in room 301.")
        assert result == "action_required"

    def test_english_can_we_meet(self):
        result, _ = classify("", "Can we meet for lunch today?")
        assert result == "action_required"

    def test_english_are_you_free(self):
        result, _ = classify("Quick chat?", "Are you free tomorrow afternoon?")
        assert result == "action_required"

    def test_english_catch_up(self):
        result, _ = classify("", "Could we catch up this week?")
        assert result == "action_required"

    def test_english_appointment(self):
        result, _ = classify("Appointment on Monday", "Your appointment is scheduled for Monday at 10am.")
        assert result == "action_required"

    # -- Approvals and signing --

    def test_please_sign(self):
        result, _ = classify("Contract ready", "Please sign the attached contract.")
        assert result == "action_required"

    def test_please_approve(self):
        result, _ = classify("Budget approval", "Please approve the Q1 budget.")
        assert result == "action_required"

    def test_czech_podepsat(self):
        result, _ = classify("Smlouva k podpisu", "Prosím podepsat přiloženou smlouvu.")
        assert result == "action_required"

    def test_czech_schvalit(self):
        result, _ = classify("Ke schválení", "Prosím schválit rozpočet.")
        assert result == "action_required"

    def test_urgent(self):
        result, _ = classify("URGENT: Server down", "The production server needs immediate attention.")
        assert result == "action_required"


# ============================================================================
# PAYMENT REQUESTS
# ============================================================================

class TestPaymentRequest:
    """Invoices, billing, payment-related emails."""

    def test_invoice_english(self):
        result, _ = classify("Invoice #1234", "Please find attached invoice for $500.")
        assert result == "payment_request"

    def test_faktura_czech(self):
        result, _ = classify("Faktura za služby", "Zasíláme fakturu na 15 000 Kč.")
        assert result == "payment_request"

    def test_payment_due(self):
        result, _ = classify("Payment due", "Your payment of EUR 200 is due on March 1.")
        assert result == "payment_request"

    def test_billing_statement(self):
        result, _ = classify("Billing statement", "Your account balance is $1,200. Amount due: $300.")
        assert result == "payment_request"

    def test_czech_splatnost(self):
        result, _ = classify("", "Splatnost faktury je 14 dní.")
        assert result == "payment_request"

    def test_czk_currency(self):
        result, _ = classify("Objednávka", "Celková částka: 2500 CZK")
        assert result == "payment_request"

    def test_please_pay(self):
        result, _ = classify("Outstanding balance", "Please pay the outstanding amount.")
        assert result == "payment_request"


# ============================================================================
# FYI — Newsletters, notifications, automated
# ============================================================================

class TestFYI:
    """Emails that are informational only, no action needed."""

    def test_newsletter(self):
        result, _ = classify("Weekly Newsletter", "Here's what happened this week...")
        assert result == "fyi"

    def test_noreply_sender(self):
        result, _ = classify("Your order shipped", "Your order has shipped. Do not reply to this email.")
        assert result == "fyi"

    def test_automated_message(self):
        result, _ = classify("", "This is an automated message from the system.")
        assert result == "fyi"

    def test_unsubscribe(self):
        result, _ = classify("New blog post", "Check out our latest post. Unsubscribe here.")
        assert result == "fyi"

    def test_notification(self):
        result, _ = classify("Notification: build passed", "Your CI build passed.")
        assert result == "fyi"

    def test_system_alert(self):
        result, _ = classify("System alert", "CPU usage exceeded 90% threshold.")
        assert result == "fyi"

    def test_reminder(self):
        result, _ = classify("Reminder: subscription", "Your subscription renews tomorrow.")
        assert result == "fyi"

    def test_ambiguous_defaults_to_fyi(self):
        """Completely ambiguous email should default to FYI."""
        result, conf = classify("Ahoj", "Posílám ti ten soubor co jsem slíbil.")
        assert result == "fyi"
        assert conf == "low"


# ============================================================================
# NEEDS RESPONSE — Questions and requests requiring a reply
# ============================================================================

class TestNeedsResponse:
    """Emails that require the user to respond with a message."""

    def test_direct_question(self):
        result, _ = classify("Project update", "What do you think about the new design?")
        assert result == "needs_response"

    def test_can_you(self):
        result, _ = classify("", "Can you send me the report?")
        assert result == "needs_response"

    def test_could_you(self):
        result, _ = classify("", "Could you review this PR?")
        assert result == "needs_response"

    def test_please_review(self):
        result, _ = classify("PR #42", "Please review the attached changes.")
        assert result == "needs_response"

    def test_your_opinion(self):
        result, _ = classify("", "I'd love to hear your thoughts on this.")
        assert result == "needs_response"

    def test_czech_co_si_myslis(self):
        result, _ = classify("", "Co si myslíš o tom návrhu?")
        assert result == "needs_response"

    def test_czech_dej_vedet(self):
        result, _ = classify("", "Dej mi vědět jak to dopadlo.")
        assert result == "needs_response"

    def test_czech_ozvi_se(self):
        result, _ = classify("", "Ozvi se až budeš moct.")
        assert result == "needs_response"

    def test_czech_posli(self):
        result, _ = classify("", "Pošli mi ten dokument prosím.")
        assert result == "needs_response"


# ============================================================================
# BLACKLIST — Should always be FYI
# ============================================================================

class TestBlacklist:
    """Emails from blacklisted senders are forced to FYI."""

    def test_blacklisted_sender_github(self):
        """Even if content looks like needs_response, blacklist forces FYI."""
        classifier = GmailClassifier()
        # Only works if config/contacts.yml has the blacklist entries
        if not classifier.blacklist:
            return  # Skip if no blacklist configured
        matched = classifier._matches_blacklist("bot@noreply.github.com")
        assert matched, "Expected GitHub noreply to match blacklist"

    def test_blacklisted_sender_google(self):
        classifier = GmailClassifier()
        if not classifier.blacklist:
            return
        matched = classifier._matches_blacklist("noreply@notifications.google.com")
        assert matched, "Expected Google notifications to match blacklist"


# ============================================================================
# EDGE CASES — Priority ordering, multilingual, ambiguous
# ============================================================================

class TestEdgeCases:
    """Edge cases and priority ordering tests."""

    def test_payment_beats_action(self):
        """Payment patterns take priority over action patterns."""
        result, _ = classify("Invoice - please approve", "Please approve this invoice for $500.")
        assert result == "payment_request"

    def test_action_beats_needs_response(self):
        """Action required takes priority over needs_response (question mark)."""
        result, _ = classify("Schůzka?", "Můžeme se sejít?")
        assert result == "action_required"

    def test_meeting_with_question_is_action(self):
        """Meeting request phrased as question should be action_required, not needs_response."""
        result, _ = classify(
            "žádost o schůzku",
            "Mohli bychom se potkat dnes odpoledne v 17:00 v Berlin Hbf na kávu?"
        )
        assert result == "action_required"

    def test_fyi_beats_question_mark(self):
        """Automated messages with questions should still be FYI."""
        result, _ = classify(
            "Newsletter: Want more updates?",
            "Unsubscribe from future newsletters. Want to read more?"
        )
        assert result == "fyi"

    def test_english_meeting_invitation(self):
        """Formal meeting invitation."""
        result, _ = classify(
            "You're invited",
            "I'd like to invite you to a meeting next Tuesday at 10am."
        )
        assert result == "action_required"

    def test_czech_time_and_place_meeting(self):
        """Czech email with time and place = meeting request."""
        result, _ = classify(
            "",
            "Ahoj, potkáme se zítra v 15:00 u kavárny?"
        )
        assert result == "action_required"

    def test_pure_question_no_meeting(self):
        """A question that is NOT about a meeting should be needs_response."""
        result, _ = classify("Quick question", "How does the API handle rate limits?")
        assert result == "needs_response"

    def test_czech_confirmation_request(self):
        """Czech email asking for confirmation = action_required."""
        result, _ = classify("Prosba", "Prosím potvrdit účast na workshopu.")
        assert result == "action_required"

    def test_empty_email_defaults_fyi(self):
        """Empty subject and body should default to FYI."""
        result, conf = classify("", "")
        assert result == "fyi"
        assert conf == "low"


# ============================================================================
# COMMUNICATION STYLE RESOLUTION
# ============================================================================

class TestCommunicationStyle:
    """Style resolution for needs_response emails."""

    def test_default_style_is_business(self):
        classifier = GmailClassifier()
        style = classifier._get_communication_style("someone@random.com")
        assert style == "business"

    def test_gov_domain_is_formal(self):
        classifier = GmailClassifier()
        # Only works with config
        if not classifier.domain_overrides:
            return
        style = classifier._get_communication_style("clerk@finance.gov.cz")
        assert style == "formal"

    def test_no_at_sign_returns_business(self):
        classifier = GmailClassifier()
        style = classifier._get_communication_style("invalid-email")
        assert style == "business"


# ============================================================================
# Runner
# ============================================================================

def run_tests():
    """Simple test runner when pytest is not available."""
    test_classes = [
        TestActionRequired,
        TestPaymentRequest,
        TestFYI,
        TestNeedsResponse,
        TestBlacklist,
        TestEdgeCases,
        TestCommunicationStyle,
    ]

    total = 0
    passed = 0
    failed = 0
    failures = []

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        print(f"\n{cls.__name__}:")

        for method_name in sorted(methods):
            total += 1
            method = getattr(instance, method_name)
            try:
                method()
                passed += 1
                print(f"  PASS  {method_name}")
            except AssertionError as e:
                failed += 1
                failures.append((cls.__name__, method_name, str(e)))
                print(f"  FAIL  {method_name}: {e}")
            except Exception as e:
                failed += 1
                failures.append((cls.__name__, method_name, str(e)))
                print(f"  ERROR {method_name}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed, {failed} failed")

    if failures:
        print(f"\nFailures:")
        for cls_name, method, msg in failures:
            print(f"  {cls_name}.{method}: {msg}")

    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    # Try pytest first, fall back to simple runner
    try:
        import pytest
        sys.exit(pytest.main([__file__, "-v"]))
    except ImportError:
        sys.exit(run_tests())
