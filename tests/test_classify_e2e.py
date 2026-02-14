"""End-to-end rule engine tests — automation detection only.

CR-01: The rule tier only performs automation detection (blacklist, automated
sender patterns, header inspection). All content-based classification is
delegated to the LLM. These tests verify the rule tier correctly identifies
automated emails and passes everything else to the LLM.
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
) -> tuple[str, str, bool, bool]:
    """Run classification and return (category, confidence, matched, is_automated)."""
    result = classify_by_rules(sender, subject, snippet, body, blacklist or [], headers=headers)
    return result.category, result.confidence, result.matched, result.is_automated


# ── Blacklisted senders → fyi ───────────────────────────────────────────────


class TestBlacklist:
    def test_blacklisted_sender(self):
        cat, conf, matched, automated = classify(
            sender="bot@noreply.github.com",
            subject="Important question?",
            body="Can you review this PR?",
            blacklist=["*@noreply.github.com"],
        )
        assert cat == "fyi"
        assert matched is True
        assert automated is True

    def test_blacklist_overrides_everything(self):
        cat, _, matched, automated = classify(
            sender="bot@spam.com",
            subject="Urgent invoice - please sign",
            body="Pay immediately. Please approve.",
            blacklist=["*@spam.com"],
        )
        assert cat == "fyi"
        assert matched is True
        assert automated is True


# ── Automated sender patterns → fyi ─────────────────────────────────────────


class TestAutomatedSenders:
    def test_noreply_sender(self):
        cat, _, matched, automated = classify(
            sender="noreply@company.com",
            subject="Your order has shipped",
        )
        assert cat == "fyi"
        assert matched is True
        assert automated is True

    def test_notifications_sender(self):
        cat, _, matched, automated = classify(
            sender="notifications@github.com",
            subject="New comment on PR #123",
        )
        assert cat == "fyi"
        assert matched is True
        assert automated is True

    def test_mailer_daemon(self):
        cat, _, matched, automated = classify(
            sender="mailer-daemon@google.com",
            subject="Delivery failed",
        )
        assert cat == "fyi"
        assert matched is True
        assert automated is True

    def test_do_not_reply(self):
        cat, _, matched, _ = classify(sender="do-not-reply@company.com")
        assert cat == "fyi"
        assert matched is True

    def test_donotreply(self):
        cat, _, matched, _ = classify(sender="donotreply@company.com")
        assert cat == "fyi"
        assert matched is True

    def test_postmaster(self):
        cat, _, matched, _ = classify(sender="postmaster@mail.company.com")
        assert cat == "fyi"
        assert matched is True

    def test_bounce(self):
        cat, _, matched, _ = classify(sender="bounce@mail.company.com")
        assert cat == "fyi"
        assert matched is True

    def test_notification_singular(self):
        cat, _, matched, _ = classify(sender="notification@app.com")
        assert cat == "fyi"
        assert matched is True


# ── Automated header detection → fyi ────────────────────────────────────────


class TestAutomatedHeaders:
    def test_list_unsubscribe_header(self):
        cat, conf, matched, automated = classify(
            sender="promo@shop.com",
            subject="50% off sale!",
            body="Check out our latest deals.",
            headers={"List-Unsubscribe": "<mailto:unsub@shop.com>"},
        )
        assert cat == "fyi"
        assert conf == "high"
        assert matched is True
        assert automated is True

    def test_auto_submitted_header(self):
        cat, _, matched, automated = classify(
            sender="system@company.com",
            subject="Your report is ready",
            body="Hi, can you review the attached report?",
            headers={"Auto-Submitted": "auto-generated"},
        )
        assert cat == "fyi"
        assert matched is True
        assert automated is True

    def test_auto_submitted_auto_replied(self):
        cat, _, matched, _ = classify(
            sender="colleague@company.com",
            subject="Re: Project update",
            body="I am currently out of office.",
            headers={"Auto-Submitted": "auto-replied"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_auto_submitted_no_is_human(self):
        """Auto-Submitted: no means human-sent — should NOT be treated as automated."""
        cat, _, matched, automated = classify(
            sender="colleague@company.com",
            subject="Quick question",
            body="Can you send me the report?",
            headers={"Auto-Submitted": "no"},
        )
        assert matched is False
        assert automated is False

    def test_precedence_bulk(self):
        cat, _, matched, _ = classify(
            sender="updates@service.com",
            subject="Weekly digest",
            headers={"Precedence": "bulk"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_precedence_list(self):
        cat, _, matched, _ = classify(
            sender="user@mailinglist.org",
            subject="Re: Discussion topic",
            headers={"Precedence": "list"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_list_id_header(self):
        cat, _, matched, _ = classify(
            sender="dev@lists.project.org",
            subject="RFC: New API design",
            headers={"List-Id": "<dev.lists.project.org>"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_feedback_id_header(self):
        cat, _, matched, _ = classify(
            sender="hello@startup.com",
            subject="We'd love your feedback",
            headers={"Feedback-ID": "123:campaign:startup"},
        )
        assert cat == "fyi"
        assert matched is True

    def test_x_auto_response_suppress(self):
        cat, _, matched, _ = classify(
            sender="calendar@company.com",
            subject="Your schedule for today",
            headers={"X-Auto-Response-Suppress": "All"},
        )
        assert cat == "fyi"
        assert matched is True


# ── Content-based emails pass through to LLM ────────────────────────────────


class TestPassToLLM:
    """All content-based classification is delegated to the LLM.

    The rule tier should return matched=False for all non-automated emails.
    """

    def test_invoice_passes_to_llm(self):
        """Payment emails are no longer matched by rules — LLM handles them."""
        _, _, matched, _ = classify(
            subject="Invoice #2024-0045",
            body="Please find attached invoice for services rendered.",
        )
        assert matched is False

    def test_meeting_request_passes_to_llm(self):
        """Meeting requests are no longer matched by rules — LLM handles them."""
        _, _, matched, _ = classify(
            sender="petr.ivan@example.com",
            subject="žádost o schůzku",
            body="Dobrý den. Mohli bychom se potkat?",
        )
        assert matched is False

    def test_action_required_passes_to_llm(self):
        _, _, matched, _ = classify(
            body="Please sign the attached contract.",
        )
        assert matched is False

    def test_question_passes_to_llm(self):
        _, _, matched, _ = classify(
            body="Are you free tomorrow afternoon?",
        )
        assert matched is False

    def test_newsletter_content_passes_to_llm(self):
        """Content mentioning 'newsletter' no longer matched by rules — LLM handles."""
        _, _, matched, _ = classify(
            sender="editor@news.com",
            subject="Weekly Newsletter: Top Stories",
            body="Here are this week's top stories.",
        )
        assert matched is False

    def test_generic_update_passes_to_llm(self):
        _, _, matched, _ = classify(
            subject="Project update",
            body="Here is the latest version of the document.",
        )
        assert matched is False

    def test_empty_email_passes_to_llm(self):
        _, _, matched, _ = classify(sender="x@x.com")
        assert matched is False

    def test_no_headers_no_automation(self):
        _, _, matched, automated = classify(
            sender="colleague@company.com",
            body="Can you help me with this?",
        )
        assert matched is False
        assert automated is False

    def test_empty_headers_no_automation(self):
        _, _, matched, automated = classify(
            sender="colleague@company.com",
            body="Can you help me with this?",
            headers={},
        )
        assert matched is False
        assert automated is False
