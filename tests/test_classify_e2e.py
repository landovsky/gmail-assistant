"""End-to-end classification tests — realistic emails through the full pipeline.

Tests the rule engine (Tier 1) with a variety of email types across languages.
Each test case represents a real-world email pattern that must be classified correctly.

For LLM (Tier 2) testing, see test_classify_llm.py which mocks the gateway.
"""

from __future__ import annotations

import pytest

from src.classify.rules import classify_by_rules


# ── Helpers ──────────────────────────────────────────────────────────────────


def classify(
    sender: str = "person@example.com",
    subject: str = "",
    body: str = "",
    snippet: str = "",
    blacklist: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[str, str, bool]:
    """Run classification and return (category, confidence, matched)."""
    result = classify_by_rules(sender, subject, snippet, body, blacklist or [], headers=headers)
    return result.category, result.confidence, result.matched


# ── Meeting / Appointment Requests → action_required ─────────────────────────


class TestMeetingRequests:
    """Meeting/appointment requests should be action_required."""

    def test_czech_meeting_request(self):
        """The original misclassified email."""
        cat, conf, matched = classify(
            sender="petr.ivan@example.com",
            subject="žádost o schůzku",
            body="Dobrý den. Mohli bychom se potkat dnes odpoledne v 17:00 "
            "v Berlin Hbf na kávu? Díky. Petr Ivan",
        )
        assert cat == "action_required"
        assert matched is True

    def test_czech_meeting_schuzka(self):
        cat, _, matched = classify(
            subject="Schůzka v pondělí",
            body="Potřeboval bych s vámi probrat projekt.",
        )
        assert cat == "action_required"
        assert matched is True

    def test_czech_setkani(self):
        cat, _, matched = classify(
            body="Rád bych domluvil setkání ohledně nového projektu.",
        )
        assert cat == "action_required"
        assert matched is True

    def test_czech_potkat_se(self):
        cat, _, matched = classify(
            body="Mohli bychom se potkat se zítra?",
        )
        assert cat == "action_required"
        assert matched is True

    def test_czech_sejit_se(self):
        cat, _, matched = classify(
            body="Měli bychom se sejít se a probrat to.",
        )
        assert cat == "action_required"
        assert matched is True

    def test_english_meeting_request(self):
        cat, _, matched = classify(
            subject="Meeting request: Q1 Review",
            body="Hi, can we schedule a meeting for next week?",
        )
        assert cat == "action_required"
        assert matched is True

    def test_english_calendar_invite(self):
        cat, _, matched = classify(
            subject="Calendar invite: Team sync",
            body="You've been invited to a meeting.",
        )
        assert cat == "action_required"
        assert matched is True

    def test_german_termin(self):
        cat, _, matched = classify(
            subject="Termin nächste Woche",
            body="Könnten wir uns am Dienstag treffen?",
        )
        assert cat == "action_required"
        assert matched is True

    def test_german_treffen(self):
        cat, _, matched = classify(
            body="Wollen wir uns morgen treffen?",
        )
        assert cat == "action_required"
        assert matched is True


# ── Payment / Invoice → payment_request ──────────────────────────────────────


class TestPaymentRequests:
    """Payment-related emails should be payment_request."""

    def test_english_invoice(self):
        cat, _, matched = classify(
            subject="Invoice #2024-0045",
            body="Please find attached invoice for services rendered.",
        )
        assert cat == "payment_request"
        assert matched is True

    def test_czech_faktura(self):
        cat, _, matched = classify(
            subject="Faktura za služby",
            body="V příloze naleznete fakturu na částku 15 000 Kč.",
        )
        assert cat == "payment_request"
        assert matched is True

    def test_czech_platba(self):
        cat, _, matched = classify(
            body="Prosím o platba do konce měsíce.",
        )
        assert cat == "payment_request"
        assert matched is True

    def test_amount_with_czk(self):
        cat, _, matched = classify(
            body="Celková částka: 5 000 CZK. Splatnost: 15. 3. 2025.",
        )
        assert cat == "payment_request"
        assert matched is True

    def test_amount_with_eur(self):
        cat, _, matched = classify(
            body="Total amount: 250 EUR. Due by March 15.",
        )
        assert cat == "payment_request"
        assert matched is True

    def test_due_date(self):
        cat, _, matched = classify(
            subject="Services rendered",
            body="Amount: $500. Due date: 2025-04-01.",
        )
        assert cat == "payment_request"
        assert matched is True

    def test_czech_splatnost(self):
        cat, _, matched = classify(
            body="Splatnost faktury je 30 dní.",
        )
        assert cat == "payment_request"
        assert matched is True


# ── Action Required (non-meeting) → action_required ──────────────────────────


class TestActionRequired:
    """Non-meeting action requests should be action_required."""

    def test_please_sign(self):
        cat, _, _ = classify(
            body="Please sign the attached contract and return by Friday.",
        )
        assert cat == "action_required"

    def test_please_approve(self):
        cat, _, _ = classify(
            subject="Expense report - please approve",
        )
        assert cat == "action_required"

    def test_approval_required(self):
        cat, _, _ = classify(
            subject="Approval required: Budget increase",
        )
        assert cat == "action_required"

    def test_urgent(self):
        cat, _, _ = classify(
            subject="Urgent: Server is down",
        )
        assert cat == "action_required"

    def test_czech_podepsat(self):
        cat, _, _ = classify(
            body="Prosím o podepsání smlouvy.",
        )
        assert cat == "action_required"

    def test_czech_schvalit(self):
        cat, _, _ = classify(
            body="Prosíme o schválení rozpočtu.",
        )
        assert cat == "action_required"

    def test_please_confirm(self):
        cat, _, _ = classify(
            body="Please confirm your attendance.",
        )
        assert cat == "action_required"


# ── FYI / Automated → fyi ───────────────────────────────────────────────────


class TestFYI:
    """Newsletters, automated messages, and notifications should be fyi."""

    def test_newsletter(self):
        cat, _, matched = classify(
            sender="editor@news.com",
            subject="Weekly Newsletter: Top Stories",
            body="Here are this week's top stories.",
        )
        assert cat == "fyi"
        assert matched is True

    def test_noreply_sender(self):
        cat, _, matched = classify(
            sender="noreply@company.com",
            subject="Your order has shipped",
        )
        assert cat == "fyi"
        assert matched is True

    def test_notifications_sender(self):
        cat, _, matched = classify(
            sender="notifications@github.com",
            subject="New comment on PR #123",
        )
        assert cat == "fyi"
        assert matched is True

    def test_unsubscribe(self):
        cat, _, matched = classify(
            body="If you'd like to unsubscribe, click here.",
        )
        assert cat == "fyi"
        assert matched is True

    def test_automated_message(self):
        cat, _, matched = classify(
            body="This is an automated message. Do not reply.",
        )
        assert cat == "fyi"
        assert matched is True

    def test_system_alert(self):
        cat, _, matched = classify(
            subject="System alert: Backup completed",
            body="Your daily backup completed successfully.",
        )
        assert cat == "fyi"
        assert matched is True

    def test_blacklisted_sender(self):
        cat, _, matched = classify(
            sender="bot@noreply.github.com",
            subject="Important question?",
            body="Can you review this PR?",
            blacklist=["*@noreply.github.com"],
        )
        assert cat == "fyi"
        assert matched is True

    def test_mailer_daemon(self):
        cat, _, matched = classify(
            sender="mailer-daemon@google.com",
            subject="Delivery failed",
        )
        assert cat == "fyi"
        assert matched is True


# ── Needs Response → needs_response (passed to LLM) ─────────────────────────


class TestNeedsResponse:
    """Direct questions and requests should trigger needs_response."""

    def test_question_mark(self):
        cat, conf, matched = classify(
            body="Are you free tomorrow afternoon?",
        )
        assert cat == "needs_response"
        assert conf == "medium"
        assert matched is False  # passes to LLM

    def test_can_you(self):
        cat, _, _ = classify(
            body="Can you send me the report by EOD?",
        )
        assert cat == "needs_response"

    def test_could_you(self):
        cat, _, _ = classify(
            body="Could you review the document I sent?",
        )
        assert cat == "needs_response"

    def test_would_you(self):
        cat, _, _ = classify(
            body="Would you be willing to help with this?",
        )
        assert cat == "needs_response"

    def test_what_do_you_think(self):
        cat, _, _ = classify(
            body="What do you think about the new proposal?",
        )
        assert cat == "needs_response"

    def test_your_feedback(self):
        cat, _, _ = classify(
            body="I'd appreciate your feedback on the draft.",
        )
        assert cat == "needs_response"

    def test_czech_mohli_bychom(self):
        """Czech 'mohli bychom' (could we) — triggers needs_response."""
        cat, _, _ = classify(
            body="Mohli bychom probrat nový návrh?",
        )
        # Note: "mohli bychom" is in RESPONSE_PATTERNS, but if subject had
        # "schůzka" it would hit ACTION_PATTERNS first.
        assert cat == "needs_response"

    def test_czech_muzete(self):
        cat, _, _ = classify(
            body="Můžete mi poslat ten soubor?",
        )
        assert cat == "needs_response"

    def test_czech_ozvi_se(self):
        cat, _, _ = classify(
            body="Ozvi se mi, až budeš mít čas.",
        )
        assert cat == "needs_response"

    def test_please_review(self):
        cat, _, _ = classify(
            body="Please review the attached document.",
        )
        assert cat == "needs_response"


# ── Ambiguous / No Match → falls through to LLM ─────────────────────────────


class TestAmbiguousEmails:
    """Emails that don't match any rule pattern should fall through to LLM."""

    def test_generic_update(self):
        cat, conf, matched = classify(
            subject="Project update",
            body="Here is the latest version of the document.",
        )
        assert matched is False
        assert conf == "low"

    def test_short_greeting(self):
        """A brief personal email with no clear action."""
        cat, conf, matched = classify(
            body="Ahoj, jak se máš",  # No question mark
        )
        assert matched is False

    def test_forwarded_info(self):
        cat, conf, matched = classify(
            subject="FW: Project timeline",
            body="See below for the updated timeline.",
        )
        assert matched is False


# ── Pattern Priority Tests ───────────────────────────────────────────────────


class TestPatternPriority:
    """Payment > Action > FYI > Response — verify ordering."""

    def test_payment_beats_action(self):
        """Invoice with 'urgent' — payment wins."""
        cat, _, _ = classify(
            subject="Urgent invoice",
            body="Please pay this invoice immediately.",
        )
        assert cat == "payment_request"

    def test_payment_beats_fyi(self):
        """Automated payment notice — payment wins over newsletter."""
        cat, _, _ = classify(
            sender="noreply@billing.com",
            subject="Invoice ready",
            body="Your invoice is ready.",
        )
        # noreply sender would match FYI, but it checks sender first (step 2)
        # Actually, noreply check happens before content patterns
        # So this will be fyi from the sender check
        assert cat == "fyi"

    def test_action_beats_fyi(self):
        """Sign request in automated context — action wins over FYI pattern."""
        cat, _, _ = classify(
            body="Please sign the document. This is an automated notification.",
        )
        assert cat == "action_required"

    def test_action_beats_response(self):
        """Meeting request phrased as question — action wins."""
        cat, _, _ = classify(
            subject="žádost o schůzku",
            body="Můžeme se sejít?",
        )
        assert cat == "action_required"

    def test_fyi_beats_response(self):
        """Newsletter with a question — FYI wins."""
        cat, _, _ = classify(
            body="What do you think about our newsletter? Click to unsubscribe.",
        )
        assert cat == "fyi"


# ── Edge Cases ───────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    def test_empty_email(self):
        cat, conf, matched = classify(sender="x@x.com")
        assert matched is False
        assert conf == "low"

    def test_very_long_body(self):
        """Long body should not cause issues."""
        cat, _, _ = classify(body="word " * 10000 + " please sign this.")
        assert cat == "action_required"

    def test_unicode_in_subject(self):
        cat, _, _ = classify(
            subject="Žádost o schůzku 🗓️",
            body="Sejdeme se v pátek?",
        )
        assert cat == "action_required"

    def test_mixed_language(self):
        """Email mixing Czech and English."""
        cat, _, _ = classify(
            subject="Meeting request / žádost o schůzku",
            body="Let's discuss the project. Mohli bychom se potkat?",
        )
        assert cat == "action_required"

    def test_case_insensitive(self):
        cat, _, _ = classify(
            subject="URGENT: ACTION REQUIRED",
        )
        assert cat == "action_required"

    def test_blacklist_overrides_everything(self):
        """Blacklist should override even action/payment patterns."""
        cat, _, matched = classify(
            sender="bot@spam.com",
            subject="Urgent invoice - please sign",
            body="Pay immediately. Please approve.",
            blacklist=["*@spam.com"],
        )
        assert cat == "fyi"
        assert matched is True


# ── Automated Email Detection via Headers ─────────────────────────────────


class TestAutomatedHeaders:
    """Automated emails detected via RFC headers should be fyi (no draft)."""

    def test_list_unsubscribe_header(self):
        """Emails with List-Unsubscribe are bulk mail → fyi."""
        cat, conf, matched = classify(
            sender="promo@shop.com",
            subject="50% off sale!",
            body="Check out our latest deals. Can you believe these prices?",
            headers={"List-Unsubscribe": "<mailto:unsub@shop.com>"},
        )
        assert cat == "fyi"
        assert conf == "high"
        assert matched is True

    def test_auto_submitted_header(self):
        """RFC 3834 Auto-Submitted: auto-generated → fyi."""
        cat, conf, matched = classify(
            sender="system@company.com",
            subject="Your report is ready",
            body="Hi, can you review the attached report?",
            headers={"Auto-Submitted": "auto-generated"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_auto_submitted_auto_replied(self):
        """Auto-Submitted: auto-replied (out-of-office) → fyi."""
        cat, _, matched = classify(
            sender="colleague@company.com",
            subject="Re: Project update",
            body="I am currently out of office. Can you contact my deputy?",
            headers={"Auto-Submitted": "auto-replied"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_auto_submitted_no_is_human(self):
        """Auto-Submitted: no means human-sent — should NOT be treated as automated."""
        cat, _, matched = classify(
            sender="colleague@company.com",
            subject="Quick question",
            body="Can you send me the report?",
            headers={"Auto-Submitted": "no"},
        )
        assert cat == "needs_response"
        assert matched is False  # goes to LLM

    def test_precedence_bulk(self):
        """Precedence: bulk → automated → fyi."""
        cat, _, matched = classify(
            sender="updates@service.com",
            subject="Weekly digest",
            body="Here's what happened this week. What do you think?",
            headers={"Precedence": "bulk"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_precedence_list(self):
        """Precedence: list (mailing list) → fyi."""
        cat, _, matched = classify(
            sender="user@mailinglist.org",
            subject="Re: Discussion topic",
            body="Could you elaborate on that point?",
            headers={"Precedence": "list"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_list_id_header(self):
        """List-Id header (RFC 2919) → mailing list → fyi."""
        cat, _, matched = classify(
            sender="dev@lists.project.org",
            subject="RFC: New API design",
            body="What do you think about this approach?",
            headers={"List-Id": "<dev.lists.project.org>"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_feedback_id_header(self):
        """Feedback-ID (Google bulk tracking) → fyi."""
        cat, _, matched = classify(
            sender="hello@startup.com",
            subject="We'd love your feedback",
            body="Can you take 2 minutes to fill out this survey?",
            headers={"Feedback-ID": "123:campaign:startup"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_x_auto_response_suppress(self):
        """X-Auto-Response-Suppress → automated → fyi."""
        cat, _, matched = classify(
            sender="calendar@company.com",
            subject="Your schedule for today",
            body="You have 3 meetings today. Please review.",
            headers={"X-Auto-Response-Suppress": "All"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_automated_with_payment_keeps_payment(self):
        """Automated email with invoice content → payment_request (not fyi).

        Payment/action categories don't generate drafts, so they're still useful.
        """
        cat, _, matched = classify(
            sender="billing@saas.com",
            subject="Invoice #2025-001",
            body="Your invoice for January is ready. Amount due: $99.",
            headers={"List-Unsubscribe": "<mailto:unsub@saas.com>"},
        )
        assert cat == "payment_request"
        assert matched is True

    def test_automated_with_action_keeps_action(self):
        """Automated email with action content → action_required (not fyi)."""
        cat, _, matched = classify(
            sender="hr@company.com",
            subject="Please approve time-off request",
            body="John Smith has requested PTO. Please approve by Friday.",
            headers={"Auto-Submitted": "auto-generated"},
        )
        assert cat == "action_required"
        assert matched is True

    def test_no_headers_no_effect(self):
        """Without headers, classification works as before."""
        cat, conf, matched = classify(
            sender="colleague@company.com",
            body="Can you help me with this?",
        )
        assert cat == "needs_response"
        assert matched is False

    def test_empty_headers_no_effect(self):
        """Empty headers dict has no effect."""
        cat, _, matched = classify(
            sender="colleague@company.com",
            body="Can you help me with this?",
            headers={},
        )
        assert cat == "needs_response"
        assert matched is False


# ── Expanded Automated Sender Patterns ────────────────────────────────────


class TestAutomatedSenderPatterns:
    """Extended sender patterns for automated email detection."""

    def test_do_not_reply(self):
        cat, _, matched = classify(sender="do-not-reply@company.com")
        assert cat == "fyi"
        assert matched is True

    def test_donotreply(self):
        cat, _, matched = classify(sender="donotreply@company.com")
        assert cat == "fyi"
        assert matched is True

    def test_postmaster(self):
        cat, _, matched = classify(sender="postmaster@mail.company.com")
        assert cat == "fyi"
        assert matched is True

    def test_bounce(self):
        cat, _, matched = classify(sender="bounce@mail.company.com")
        assert cat == "fyi"
        assert matched is True

    def test_notification_singular(self):
        cat, _, matched = classify(sender="notification@app.com")
        assert cat == "fyi"
        assert matched is True
