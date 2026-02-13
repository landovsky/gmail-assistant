"""End-to-end tests with real LLM API calls.

These tests call the actual LLM API (Gemini, Anthropic, or OpenAI) via LiteLLM
and verify that classification and draft generation produce sensible results.

Run locally:
    GEMINI_API_KEY=... pytest tests/test_e2e_llm.py -v
    ANTHROPIC_API_KEY=... GMA_LLM_CLASSIFY_MODEL=anthropic/claude-haiku pytest tests/test_e2e_llm.py -v

Skipped automatically when no API key is set.
"""

from __future__ import annotations

import pytest

from src.classify.engine import ClassificationEngine
from src.classify.prompts import CLASSIFY_SYSTEM_PROMPT, build_classify_user_message
from src.draft.engine import DraftEngine
from src.llm.gateway import ClassifyResult, LLMGateway
from tests.conftest import skip_without_api_key

pytestmark = [pytest.mark.e2e, skip_without_api_key]


# ── Helpers ──────────────────────────────────────────────────────────────────

VALID_CATEGORIES = {"needs_response", "action_required", "payment_request", "fyi", "waiting"}
VALID_CONFIDENCES = {"high", "medium", "low"}


def _classify_via_engine(
    gateway: LLMGateway,
    *,
    sender_email: str = "person@example.com",
    sender_name: str = "",
    subject: str = "",
    body: str = "",
    snippet: str = "",
    message_count: int = 1,
    blacklist: list[str] | None = None,
    contacts_config: dict | None = None,
    headers: dict[str, str] | None = None,
):
    """Convenience wrapper around ClassificationEngine.classify."""
    engine = ClassificationEngine(gateway)
    return engine.classify(
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        snippet=snippet,
        body=body,
        message_count=message_count,
        blacklist=blacklist or [],
        contacts_config=contacts_config or {},
        headers=headers,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. LLM Gateway: raw classify / draft calls
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMGatewayClassify:
    """Verify the gateway returns well-formed ClassifyResult from a real LLM."""

    def test_returns_valid_json_category(self, llm_gateway: LLMGateway):
        """LLM should return valid JSON with a recognised category."""
        user_msg = build_classify_user_message(
            sender_email="alice@company.com",
            sender_name="Alice",
            subject="Quick question about the report",
            snippet="Can you send me the latest numbers?",
            body="Hi, can you send me the latest numbers for the Q3 report? Thanks!",
            message_count=1,
        )
        result = llm_gateway.classify(CLASSIFY_SYSTEM_PROMPT, user_msg)
        assert isinstance(result, ClassifyResult)
        assert result.category in VALID_CATEGORIES
        assert result.confidence in VALID_CONFIDENCES
        assert len(result.reasoning) > 0

    def test_fyi_newsletter(self, llm_gateway: LLMGateway):
        """A clear newsletter should be classified as fyi."""
        user_msg = build_classify_user_message(
            sender_email="news@techdigest.io",
            sender_name="Tech Digest",
            subject="This Week in Tech — Issue #247",
            snippet="Top stories this week in AI, cloud computing, and open source...",
            body=(
                "Top stories this week:\n"
                "1. New GPT model released\n"
                "2. Kubernetes 1.30 features\n"
                "3. Open-source LLM roundup\n\n"
                "You are receiving this because you subscribed. "
                "To unsubscribe, click here."
            ),
            message_count=1,
        )
        result = llm_gateway.classify(CLASSIFY_SYSTEM_PROMPT, user_msg)
        assert result.category == "fyi"

    def test_payment_request_invoice(self, llm_gateway: LLMGateway):
        """A clear invoice email should be classified as payment_request."""
        user_msg = build_classify_user_message(
            sender_email="billing@vendor.com",
            sender_name="Billing Department",
            subject="Invoice #2024-0567 — December services",
            snippet="Please find attached your invoice for December.",
            body=(
                "Dear Customer,\n\n"
                "Please find attached your invoice for December consulting services.\n"
                "Amount due: $8,500.00\n"
                "Payment terms: Net 30\n"
                "Due date: January 15, 2025\n\n"
                "Please remit payment at your earliest convenience.\n\n"
                "Best regards,\nBilling Department"
            ),
            message_count=1,
        )
        result = llm_gateway.classify(CLASSIFY_SYSTEM_PROMPT, user_msg)
        assert result.category == "payment_request"


class TestLLMGatewayDraft:
    """Verify the gateway generates non-empty draft text."""

    def test_generates_nonempty_draft(self, llm_gateway: LLMGateway):
        """Draft generation should return non-empty text."""
        system = (
            "You are an email draft generator. Write a concise, professional reply. "
            "Language: English. Sign-off: Best regards"
        )
        user_msg = (
            "From: Alice <alice@company.com>\n"
            "Subject: Meeting tomorrow\n\n"
            "Thread:\n"
            "Hi, are you available for a 30-minute call tomorrow at 2pm to discuss "
            "the project timeline?\n\n"
            "Best,\nAlice"
        )
        draft = llm_gateway.draft(system, user_msg)
        assert isinstance(draft, str)
        assert len(draft.strip()) > 10, "Draft should be a substantive reply"

    def test_draft_in_czech(self, llm_gateway: LLMGateway):
        """Draft should match the language of the incoming email."""
        system = (
            "You are an email draft generator. Match the language of the incoming email. "
            "Sign-off: Tomáš"
        )
        user_msg = (
            "From: Jana Nová <jana@firma.cz>\n"
            "Subject: Schůzka v pondělí\n\n"
            "Thread:\n"
            "Ahoj, hodí se ti pondělí v 10:00 na krátkou schůzku? "
            "Potřebuju probrat rozpočet na Q1.\n\nDíky, Jana"
        )
        draft = llm_gateway.draft(system, user_msg)
        assert len(draft.strip()) > 10


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Classification Engine: full two-tier pipeline with real LLM
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassifyEngineE2E:
    """Test the ClassificationEngine with real LLM calls."""

    def test_needs_response_direct_question(self, llm_gateway: LLMGateway):
        """A direct question from a colleague should be needs_response."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="jan.novak@firma.cz",
            sender_name="Jan Novák",
            subject="Soubor k projektu",
            body="Ahoj, můžeš mi poslat ten soubor k projektu Alfa? Díky!",
        )
        assert result.category == "needs_response"
        assert result.source == "llm"

    def test_needs_response_english_feedback(self, llm_gateway: LLMGateway):
        """English request for feedback should be needs_response."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="sarah.jones@partner.com",
            sender_name="Sarah Jones",
            subject="Q3 proposal",
            body="I'd appreciate your thoughts on the proposal we discussed last week.",
        )
        assert result.category == "needs_response"
        assert result.source == "llm"

    def test_action_required_meeting_czech(self, llm_gateway: LLMGateway):
        """Czech meeting request should be action_required."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="petra.kralova@firma.cz",
            sender_name="Petra Králová",
            subject="Žádost o schůzku na pondělí",
            body="Ráda bych s tebou probrala výsledky auditu. Hodí se ti pondělí odpoledne?",
        )
        assert result.category == "action_required"

    def test_action_required_sign_contract(self, llm_gateway: LLMGateway):
        """Contract signing request should be action_required."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="legal@partner.com",
            sender_name="Legal Department",
            subject="Contract for signature",
            body="Please sign the attached NDA and return it by Friday.",
        )
        assert result.category == "action_required"

    def test_payment_request_czech_invoice(self, llm_gateway: LLMGateway):
        """Czech invoice email should be payment_request."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="ucetni@dodavatel.cz",
            sender_name="Účetní oddělení",
            subject="Faktura č. 2024-0892",
            body="V příloze zasíláme fakturu za dodané služby v měsíci říjnu.",
        )
        assert result.category == "payment_request"

    def test_payment_request_english_invoice(self, llm_gateway: LLMGateway):
        """English invoice with amount should be payment_request."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="billing@saas-vendor.com",
            sender_name="Billing",
            subject="Invoice for November",
            body="Your invoice for consulting services is ready. Amount: $4,500.",
        )
        assert result.category == "payment_request"

    def test_fyi_newsletter(self, llm_gateway: LLMGateway):
        """Newsletter with unsubscribe should be fyi."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="news@techblog.io",
            sender_name="",
            subject="This Week in AI",
            body="Top stories this week... To unsubscribe, click here.",
        )
        assert result.category == "fyi"

    def test_fyi_noreply_sender(self, llm_gateway: LLMGateway):
        """Noreply sender should be fyi (rule engine detects, safety net enforces)."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="noreply@github.com",
            sender_name="GitHub",
            subject="New comment on issue #42",
            body="User xyz commented on your pull request.",
        )
        assert result.category == "fyi"

    def test_fyi_promo_with_prices(self, llm_gateway: LLMGateway):
        """Promotional email with CZK prices should be fyi, not payment_request."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="newsletter@shop.cz",
            sender_name="Shop",
            subject="Slevy až 40 %",
            body=(
                "Využijte naše sezónní slevy! Produkt A za 299 Kč, Produkt B za 599 Kč. "
                "Odhlásit odběr newsletteru"
            ),
        )
        assert result.category == "fyi"

    def test_waiting_sent_proposal(self, llm_gateway: LLMGateway):
        """Email where I sent the last message should be waiting."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="me@firma.cz",
            sender_name="",
            subject="Re: Nabídka služeb",
            body="Poslal jsem nabídku klientovi minulý týden, zatím bez odpovědi.",
        )
        assert result.category == "waiting"

    def test_automated_header_overrides_to_fyi(self, llm_gateway: LLMGateway):
        """Email with List-Unsubscribe header: safety net overrides needs_response to fyi."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="updates@service.com",
            sender_name="Service Updates",
            subject="Quick update for you",
            body="Here's your weekly activity summary. You had 5 new messages this week.",
            headers={"List-Unsubscribe": "<mailto:unsub@service.com>"},
        )
        # Even if LLM says needs_response, the safety net overrides to fyi
        assert result.category == "fyi"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Classification from YAML fixture cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassifyFromFixtures:
    """Run classification against the YAML fixture cases with a real LLM."""

    def test_fixture_cases(
        self,
        llm_gateway: LLMGateway,
        classification_cases: list[dict],
        classification_defaults: dict,
    ):
        """Each YAML fixture case should classify to its expected category."""
        failures = []

        for case in classification_cases:
            case_id = case["id"]
            expected = case["expected_category"]

            result = _classify_via_engine(
                llm_gateway,
                sender_email=case.get("sender_email", "test@example.com"),
                sender_name=case.get("sender_name", classification_defaults.get("sender_name", "")),
                subject=case.get("subject", ""),
                body=case.get("body", ""),
                snippet=case.get("snippet", classification_defaults.get("snippet", "")),
                message_count=case.get(
                    "message_count", classification_defaults.get("message_count", 1)
                ),
                blacklist=case.get("blacklist", classification_defaults.get("blacklist", [])),
                contacts_config=case.get(
                    "contacts_config", classification_defaults.get("contacts_config", {})
                ),
            )

            if result.category != expected:
                failures.append(
                    f"  {case_id}: expected={expected}, got={result.category} "
                    f"(confidence={result.confidence}, reason={result.reasoning[:80]})"
                )

        if failures:
            # Report all failures at once for easy debugging
            msg = f"{len(failures)}/{len(classification_cases)} fixture cases misclassified:\n"
            msg += "\n".join(failures)
            pytest.fail(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Draft Engine: real LLM draft generation
# ═══════════════════════════════════════════════════════════════════════════════


class TestDraftEngineE2E:
    """Test DraftEngine with a real LLM for draft generation."""

    def test_generates_reply_english(self, llm_gateway: LLMGateway, style_config: dict):
        """Draft engine should generate a valid English reply."""
        engine = DraftEngine(llm_gateway)
        draft = engine.generate_draft(
            sender_email="alice@company.com",
            sender_name="Alice",
            subject="Meeting tomorrow",
            thread_body=(
                "Hi, are you available for a 30-minute call tomorrow at 2pm "
                "to discuss the project timeline?\n\nBest,\nAlice"
            ),
            resolved_style="business",
            style_config=style_config,
        )
        assert len(draft.strip()) > 20
        # Should contain the rework marker
        assert "✂️" in draft

    def test_generates_reply_czech(self, llm_gateway: LLMGateway, style_config: dict):
        """Draft engine should generate a Czech reply when the input is Czech."""
        engine = DraftEngine(llm_gateway)
        draft = engine.generate_draft(
            sender_email="jana@firma.cz",
            sender_name="Jana Nová",
            subject="Rozpočet Q1",
            thread_body=(
                "Ahoj, mohli bychom probrat rozpočet na Q1? "
                "Mám pár dotazů k novým položkám. Díky, Jana"
            ),
            resolved_style="business",
            style_config=style_config,
        )
        assert len(draft.strip()) > 20
        assert "✂️" in draft

    def test_generates_reply_with_instructions(self, llm_gateway: LLMGateway, style_config: dict):
        """Draft engine should incorporate user instructions into the reply."""
        engine = DraftEngine(llm_gateway)
        draft = engine.generate_draft(
            sender_email="bob@partner.com",
            sender_name="Bob",
            subject="Project deadline",
            thread_body=(
                "Hi, can we push the deadline to next Friday? "
                "We're running behind on the design phase."
            ),
            resolved_style="business",
            user_instructions="Agree to the extension but ask for a status update by Wednesday",
            style_config=style_config,
        )
        assert len(draft.strip()) > 20
        assert "✂️" in draft

    def test_rework_draft(self, llm_gateway: LLMGateway, style_config: dict):
        """Rework should modify an existing draft based on instructions."""
        engine = DraftEngine(llm_gateway)

        # Generate initial draft
        initial = engine.generate_draft(
            sender_email="client@corp.com",
            sender_name="Client",
            subject="Proposal review",
            thread_body="Could you review the proposal and send feedback?",
            resolved_style="business",
            style_config=style_config,
        )

        # Rework with instructions
        reworked_body = f"Make it shorter and more direct\n\n{initial}"
        new_draft, instruction = engine.rework_draft(
            sender_email="client@corp.com",
            sender_name="Client",
            subject="Proposal review",
            thread_body="Could you review the proposal and send feedback?",
            current_draft_body=reworked_body,
            rework_count=0,
            resolved_style="business",
            style_config=style_config,
        )
        assert len(new_draft.strip()) > 10
        assert "✂️" in new_draft
        assert instruction == "Make it shorter and more direct"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Full pipeline: classify → draft
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullPipelineE2E:
    """Test the full classify → draft pipeline with real LLM calls."""

    def test_needs_response_generates_draft(self, llm_gateway: LLMGateway, style_config: dict):
        """When an email is classified as needs_response, a draft should be generated."""
        # Step 1: Classify
        result = _classify_via_engine(
            llm_gateway,
            sender_email="colleague@company.com",
            sender_name="Colleague",
            subject="Quick question",
            body="Hey, could you review my PR #123 when you get a chance? No rush.",
        )
        assert result.category == "needs_response"

        # Step 2: Generate draft
        draft_engine = DraftEngine(llm_gateway)
        draft = draft_engine.generate_draft(
            sender_email="colleague@company.com",
            sender_name="Colleague",
            subject="Quick question",
            thread_body="Hey, could you review my PR #123 when you get a chance? No rush.",
            resolved_style=result.resolved_style,
            style_config=style_config,
        )
        assert len(draft.strip()) > 20
        assert "✂️" in draft

    def test_fyi_skips_draft(self, llm_gateway: LLMGateway):
        """FYI emails should not need draft generation — verify classification only."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="noreply@notifications.service.com",
            sender_name="",
            subject="Your weekly digest",
            body="Here is your weekly activity summary. 5 new updates this week.",
        )
        assert result.category == "fyi"
        # In production, no draft is generated for fyi emails

    def test_payment_request_no_draft(self, llm_gateway: LLMGateway):
        """Payment requests get labelled but don't generate drafts."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="invoices@supplier.com",
            sender_name="Supplier Billing",
            subject="Invoice INV-2024-1234",
            body=(
                "Please find attached your invoice.\n"
                "Amount: EUR 2,350.00\n"
                "Due: 30 days net\n\n"
                "Thank you for your business."
            ),
        )
        assert result.category == "payment_request"

    def test_czech_full_pipeline(self, llm_gateway: LLMGateway, style_config: dict):
        """Full pipeline in Czech: classify as needs_response then generate Czech draft."""
        result = _classify_via_engine(
            llm_gateway,
            sender_email="karel@firma.cz",
            sender_name="Karel Dvořák",
            subject="Návrh spolupráce",
            body=(
                "Dobrý den,\n\n"
                "rád bych Vám nabídl spolupráci na projektu digitalizace. "
                "Mohli bychom se sejít příští týden a probrat detaily?\n\n"
                "S pozdravem,\nKarel Dvořák"
            ),
        )
        # Could be action_required (meeting) or needs_response (question)
        assert result.category in ("action_required", "needs_response")

        draft_engine = DraftEngine(llm_gateway)
        draft = draft_engine.generate_draft(
            sender_email="karel@firma.cz",
            sender_name="Karel Dvořák",
            subject="Návrh spolupráce",
            thread_body=(
                "Dobrý den,\n\n"
                "rád bych Vám nabídl spolupráci na projektu digitalizace. "
                "Mohli bychom se sejít příští týden a probrat detaily?\n\n"
                "S pozdravem,\nKarel Dvořák"
            ),
            resolved_style=result.resolved_style,
            style_config=style_config,
        )
        assert len(draft.strip()) > 20


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Context query generation
# ═══════════════════════════════════════════════════════════════════════════════


class TestContextQueriesE2E:
    """Test LLM-generated Gmail search queries for context gathering."""

    def test_generates_search_queries(self, llm_gateway: LLMGateway):
        """LLM should generate valid Gmail search queries as a JSON list."""
        from src.context.prompts import CONTEXT_SYSTEM_PROMPT, build_context_user_message

        user_msg = build_context_user_message(
            sender="alice@company.com",
            subject="Follow up on Q3 budget",
            body="Can you check the budget numbers we discussed last month?",
        )
        raw = llm_gateway.generate_context_queries(CONTEXT_SYSTEM_PROMPT, user_msg)

        import json

        from src.llm.gateway import strip_code_fences

        queries = json.loads(strip_code_fences(raw))
        assert isinstance(queries, list)
        assert len(queries) >= 1
        assert all(isinstance(q, str) for q in queries)
