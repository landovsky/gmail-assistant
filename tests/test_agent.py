"""Tests for agent framework — loop, tools, profiles, routing, preprocessors."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.agent.loop import AgentLoop
from src.agent.profile import AgentProfile
from src.agent.tools import Tool, ToolRegistry
from src.agent.tools.pharmacy import (
    PHARMACY_TOOLS,
    create_draft,
    escalate,
    manage_reservation,
    register_pharmacy_tools,
    search_drugs,
    send_reply,
    web_search,
)
from src.config import (
    AgentConfig,
    AgentProfileConfig,
    AppConfig,
    DatabaseBackend,
    DatabaseConfig,
    RoutingConfig,
    RoutingRuleConfig,
)
from src.db.connection import Database
from src.db.models import AgentRunRepository, UserRepository
from src.routing.preprocessors.crisp import CrispMessage, format_for_agent, parse_crisp_email
from src.routing.router import Router
from src.routing.rules import matches_rule


# ── Tool Registry Tests ──────────────────────────────────────────────────────


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            handler=lambda: {"ok": True},
        )
        registry.register(tool)
        assert registry.get("test_tool") is tool
        assert registry.get("nonexistent") is None

    def test_get_specs(self):
        registry = ToolRegistry()
        tool = Tool(
            name="my_tool",
            description="Does stuff",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=lambda x: x,
        )
        registry.register(tool)
        specs = registry.get_specs()
        assert len(specs) == 1
        assert specs[0]["type"] == "function"
        assert specs[0]["function"]["name"] == "my_tool"

    def test_get_specs_filtered(self):
        registry = ToolRegistry()
        for name in ["a", "b", "c"]:
            registry.register(
                Tool(
                    name=name,
                    description=name,
                    parameters={},
                    handler=lambda: None,
                )
            )
        specs = registry.get_specs(["a", "c"])
        assert len(specs) == 2
        names = [s["function"]["name"] for s in specs]
        assert "a" in names
        assert "c" in names
        assert "b" not in names

    def test_execute(self):
        registry = ToolRegistry()
        registry.register(
            Tool(
                name="adder",
                description="Add two numbers",
                parameters={},
                handler=lambda a, b: {"sum": a + b},
            )
        )
        result = registry.execute("adder", {"a": 2, "b": 3})
        assert result == {"sum": 5}

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent", {})
        assert "error" in result

    def test_execute_handler_error(self):
        def bad_handler():
            raise ValueError("boom")

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="bad",
                description="",
                parameters={},
                handler=bad_handler,
            )
        )
        result = registry.execute("bad", {})
        assert "error" in result

    def test_names(self):
        registry = ToolRegistry()
        registry.register(Tool(name="x", description="", parameters={}, handler=lambda: None))
        registry.register(Tool(name="y", description="", parameters={}, handler=lambda: None))
        assert set(registry.names) == {"x", "y"}


# ── Pharmacy Tools Tests ─────────────────────────────────────────────────────


class TestPharmacyTools:
    def test_search_drugs(self):
        result = search_drugs("Ibuprofen")
        assert "results" in result
        assert len(result["results"]) > 0
        assert "Ibuprofen" in result["results"][0]["name"]

    def test_manage_reservation_create(self):
        result = manage_reservation(action="create", drug_name="Aspirin")
        assert result["status"] == "created"
        assert "reservation_id" in result

    def test_manage_reservation_check(self):
        result = manage_reservation(action="check", drug_name="Aspirin", reservation_id="RES-001")
        assert result["status"] == "active"

    def test_manage_reservation_cancel(self):
        result = manage_reservation(action="cancel", drug_name="Aspirin", reservation_id="RES-001")
        assert result["status"] == "cancelled"

    def test_manage_reservation_unknown_action(self):
        result = manage_reservation(action="unknown", drug_name="test")
        assert "error" in result

    def test_web_search(self):
        result = web_search("Ibuprofen side effects")
        assert "results" in result
        assert len(result["results"]) > 0

    def test_send_reply(self):
        result = send_reply(to="test@example.com", subject="Re: Test", body="Hello")
        assert result["status"] == "sent"

    def test_create_draft(self):
        result = create_draft(to="test@example.com", subject="Re: Test", body="Hello")
        assert result["status"] == "draft_created"

    def test_escalate(self):
        result = escalate(reason="Medical advice request")
        assert result["status"] == "escalated"

    def test_register_pharmacy_tools(self):
        registry = ToolRegistry()
        register_pharmacy_tools(registry)
        assert len(registry.names) == len(PHARMACY_TOOLS)
        assert "search_drugs" in registry.names
        assert "send_reply" in registry.names


# ── Routing Rules Tests ──────────────────────────────────────────────────────


class TestRoutingRules:
    def test_match_all(self):
        rule = RoutingRuleConfig(name="default", match={"all": True}, route="pipeline")
        assert matches_rule(rule, {"sender_email": "any@example.com"}) is True

    def test_match_forwarded_from_sender(self):
        rule = RoutingRuleConfig(
            name="pharmacy",
            match={"forwarded_from": "info@dostupnost-leku.cz"},
            route="agent",
        )
        meta = {"sender_email": "info@dostupnost-leku.cz", "subject": "", "headers": {}, "body": ""}
        assert matches_rule(rule, meta) is True

    def test_match_forwarded_from_header(self):
        rule = RoutingRuleConfig(
            name="pharmacy",
            match={"forwarded_from": "info@dostupnost-leku.cz"},
            route="agent",
        )
        meta = {
            "sender_email": "noreply@crisp.chat",
            "subject": "New message",
            "headers": {"X-Forwarded-From": "info@dostupnost-leku.cz"},
            "body": "",
        }
        assert matches_rule(rule, meta) is True

    def test_match_forwarded_from_body(self):
        rule = RoutingRuleConfig(
            name="pharmacy",
            match={"forwarded_from": "info@dostupnost-leku.cz"},
            route="agent",
        )
        meta = {
            "sender_email": "noreply@crisp.chat",
            "subject": "",
            "headers": {},
            "body": "Forwarded from info@dostupnost-leku.cz\n\nHello...",
        }
        assert matches_rule(rule, meta) is True

    def test_no_match_forwarded_from(self):
        rule = RoutingRuleConfig(
            name="pharmacy",
            match={"forwarded_from": "info@dostupnost-leku.cz"},
            route="agent",
        )
        meta = {
            "sender_email": "random@example.com",
            "subject": "Hello",
            "headers": {},
            "body": "Just a regular email",
        }
        assert matches_rule(rule, meta) is False

    def test_match_sender_domain(self):
        rule = RoutingRuleConfig(
            name="corp",
            match={"sender_domain": "company.com"},
            route="pipeline",
        )
        meta = {"sender_email": "user@company.com", "subject": "", "headers": {}, "body": ""}
        assert matches_rule(rule, meta) is True

    def test_no_match_sender_domain(self):
        rule = RoutingRuleConfig(
            name="corp",
            match={"sender_domain": "company.com"},
            route="pipeline",
        )
        meta = {"sender_email": "user@other.com", "subject": "", "headers": {}, "body": ""}
        assert matches_rule(rule, meta) is False

    def test_match_subject_contains(self):
        rule = RoutingRuleConfig(
            name="urgent",
            match={"subject_contains": "URGENT"},
            route="pipeline",
        )
        meta = {"sender_email": "", "subject": "Re: URGENT request", "headers": {}, "body": ""}
        assert matches_rule(rule, meta) is True

    def test_no_match_subject_contains(self):
        rule = RoutingRuleConfig(
            name="urgent",
            match={"subject_contains": "URGENT"},
            route="pipeline",
        )
        meta = {"sender_email": "", "subject": "Normal email", "headers": {}, "body": ""}
        assert matches_rule(rule, meta) is False

    def test_match_sender_email(self):
        rule = RoutingRuleConfig(
            name="specific",
            match={"sender_email": "vip@example.com"},
            route="pipeline",
        )
        meta = {"sender_email": "VIP@example.com", "subject": "", "headers": {}, "body": ""}
        assert matches_rule(rule, meta) is True

    def test_empty_match_returns_false(self):
        rule = RoutingRuleConfig(name="empty", match={}, route="pipeline")
        assert matches_rule(rule, {}) is False


# ── Router Tests ─────────────────────────────────────────────────────────────


class TestRouter:
    def test_route_to_agent(self):
        config = RoutingConfig(
            rules=[
                RoutingRuleConfig(
                    name="pharmacy",
                    match={"forwarded_from": "info@dostupnost-leku.cz"},
                    route="agent",
                    profile="pharmacy",
                ),
                RoutingRuleConfig(name="default", match={"all": True}, route="pipeline"),
            ]
        )
        router = Router(config)
        decision = router.route(
            {
                "sender_email": "info@dostupnost-leku.cz",
                "subject": "Drug inquiry",
                "headers": {},
                "body": "",
            }
        )
        assert decision.route_name == "agent"
        assert decision.profile_name == "pharmacy"
        assert decision.rule_name == "pharmacy"

    def test_route_default_pipeline(self):
        config = RoutingConfig(
            rules=[
                RoutingRuleConfig(
                    name="pharmacy",
                    match={"forwarded_from": "info@dostupnost-leku.cz"},
                    route="agent",
                    profile="pharmacy",
                ),
                RoutingRuleConfig(name="default", match={"all": True}, route="pipeline"),
            ]
        )
        router = Router(config)
        decision = router.route(
            {
                "sender_email": "friend@gmail.com",
                "subject": "Hello",
                "headers": {},
                "body": "",
            }
        )
        assert decision.route_name == "pipeline"
        assert decision.rule_name == "default"

    def test_route_no_rules_fallback(self):
        config = RoutingConfig(rules=[])
        router = Router(config)
        decision = router.route({"sender_email": "any@example.com"})
        assert decision.route_name == "pipeline"
        assert decision.rule_name == "default_fallback"


# ── Crisp Preprocessor Tests ─────────────────────────────────────────────────


class TestCrispPreprocessor:
    def test_parse_basic(self):
        body = "From: Jan Novák\nEmail: jan@example.com\n---\nDobrý den, mám dotaz na Ibuprofen."
        result = parse_crisp_email(
            sender_email="info@dostupnost-leku.cz",
            subject="Dotaz na lék",
            body=body,
        )
        assert result.patient_name == "Jan Novák"
        assert result.patient_email == "jan@example.com"
        assert "Ibuprofen" in result.original_message

    def test_parse_reply_to_header(self):
        result = parse_crisp_email(
            sender_email="noreply@crisp.chat",
            subject="New message",
            body="Hello, I need help with my medication.",
            headers={"Reply-To": "patient@example.com"},
        )
        assert result.patient_email == "patient@example.com"

    def test_parse_no_separator(self):
        body = "Dobrý den, potřebuji informaci o léku Paralen."
        result = parse_crisp_email(
            sender_email="info@dostupnost-leku.cz",
            subject="Dotaz",
            body=body,
        )
        assert "Paralen" in result.original_message

    def test_format_for_agent(self):
        msg = CrispMessage(
            patient_name="Jan Novák",
            patient_email="jan@example.com",
            original_message="Dobrý den, hledám Ibuprofen 400mg.",
        )
        formatted = format_for_agent(msg, "Dotaz na lék")
        assert "Subject: Dotaz na lék" in formatted
        assert "Patient name: Jan Novák" in formatted
        assert "Patient email: jan@example.com" in formatted
        assert "Ibuprofen 400mg" in formatted

    def test_format_for_agent_minimal(self):
        msg = CrispMessage(original_message="Potřebuji pomoc.")
        formatted = format_for_agent(msg, "Help")
        assert "Subject: Help" in formatted
        assert "Patient name" not in formatted
        assert "Potřebuji pomoc" in formatted


# ── Agent Profile Tests ──────────────────────────────────────────────────────


class TestAgentProfile:
    def test_from_config_with_prompt_file(self, tmp_path):
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("You are a helpful assistant.")

        config = AgentProfileConfig(
            name="test",
            model="test-model",
            max_tokens=1024,
            temperature=0.5,
            max_iterations=5,
            system_prompt_file=str(prompt_file),
            tools=["tool_a", "tool_b"],
        )

        with patch("src.agent.profile.REPO_ROOT", tmp_path):
            # Since from_config uses REPO_ROOT / system_prompt_file,
            # we need to set the file relative to REPO_ROOT
            config.system_prompt_file = "test_prompt.txt"
            profile = AgentProfile.from_config(config)

        assert profile.name == "test"
        assert profile.model == "test-model"
        assert profile.system_prompt == "You are a helpful assistant."
        assert profile.tool_names == ["tool_a", "tool_b"]

    def test_from_config_missing_prompt_file(self):
        config = AgentProfileConfig(
            name="test",
            system_prompt_file="nonexistent.txt",
        )
        profile = AgentProfile.from_config(config)
        assert profile.system_prompt == ""


# ── Agent Loop Tests ─────────────────────────────────────────────────────────


class TestAgentLoop:
    def _make_mock_response(self, content="Done!", tool_calls=None, finish_reason="stop"):
        """Create a mock LLM response."""
        message = MagicMock()
        message.content = content
        message.tool_calls = tool_calls
        if tool_calls is None:
            # Make hasattr(message, 'tool_calls') return True but tool_calls falsy
            message.tool_calls = None

        choice = MagicMock()
        choice.message = message
        choice.finish_reason = finish_reason

        response = MagicMock()
        response.choices = [choice]
        return response

    def _make_tool_call(self, tool_id, name, arguments):
        """Create a mock tool call."""
        tc = MagicMock()
        tc.id = tool_id
        tc.function.name = name
        tc.function.arguments = json.dumps(arguments)
        return tc

    def test_simple_completion_no_tools(self):
        """Agent responds directly without using tools."""
        mock_llm = MagicMock()
        mock_llm.agent_completion.return_value = self._make_mock_response(
            content="The answer is 42."
        )

        registry = ToolRegistry()
        loop = AgentLoop(mock_llm, registry)
        profile = AgentProfile(name="test", system_prompt="Be helpful.")

        result = loop.run(profile, "What is the meaning of life?")

        assert result.status == "completed"
        assert result.final_message == "The answer is 42."
        assert result.iterations == 1
        assert len(result.tool_calls) == 0

    def test_tool_use_then_completion(self):
        """Agent uses a tool, then gives final answer."""
        mock_llm = MagicMock()

        # First call: agent wants to use a tool
        tool_call = self._make_tool_call("tc_1", "search_drugs", {"query": "Ibuprofen"})
        first_response = self._make_mock_response(
            content=None, tool_calls=[tool_call], finish_reason="tool_calls"
        )

        # Second call: agent gives final answer
        second_response = self._make_mock_response(content="Ibuprofen is available.")

        mock_llm.agent_completion.side_effect = [first_response, second_response]

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="search_drugs",
                description="Search drugs",
                parameters={},
                handler=lambda query: {
                    "results": [{"name": "Ibuprofen", "availability": "available"}]
                },
            )
        )

        loop = AgentLoop(mock_llm, registry)
        profile = AgentProfile(name="test", max_iterations=5)

        result = loop.run(profile, "Is Ibuprofen available?")

        assert result.status == "completed"
        assert result.final_message == "Ibuprofen is available."
        assert result.iterations == 2
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "search_drugs"

    def test_max_iterations_reached(self):
        """Agent keeps calling tools until max iterations."""
        mock_llm = MagicMock()

        tool_call = self._make_tool_call("tc_1", "search", {"query": "test"})
        response = self._make_mock_response(
            content="Thinking...", tool_calls=[tool_call], finish_reason="tool_calls"
        )
        mock_llm.agent_completion.return_value = response

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="search",
                description="",
                parameters={},
                handler=lambda query: {"results": []},
            )
        )

        loop = AgentLoop(mock_llm, registry)
        profile = AgentProfile(name="test", max_iterations=3)

        result = loop.run(profile, "Search forever")

        assert result.status == "max_iterations"
        assert result.iterations == 3
        assert len(result.tool_calls) == 3

    def test_llm_error(self):
        """Agent handles LLM errors gracefully."""
        mock_llm = MagicMock()
        mock_llm.agent_completion.side_effect = RuntimeError("LLM down")

        loop = AgentLoop(mock_llm, ToolRegistry())
        profile = AgentProfile(name="test")

        result = loop.run(profile, "Hello")

        assert result.status == "error"
        assert "LLM down" in result.error


# ── Agent Run Repository Tests ───────────────────────────────────────────────


class TestAgentRunRepository:
    @pytest.fixture
    def db(self, tmp_path):
        config = AppConfig()
        config.database = DatabaseConfig(
            backend=DatabaseBackend.SQLITE,
            sqlite_path=tmp_path / "test.db",
        )
        database = Database(config)
        database.initialize_schema()
        return database

    def test_create_and_complete(self, db):
        UserRepository(db).create("test@example.com")
        repo = AgentRunRepository(db)

        run_id = repo.create(1, "thread_123", "pharmacy")
        assert run_id > 0

        repo.complete(
            run_id,
            status="completed",
            tool_calls_log='[{"tool": "search_drugs"}]',
            final_message="Done",
            iterations=3,
        )

        runs = repo.get_by_thread(1, "thread_123")
        assert len(runs) == 1
        assert runs[0]["status"] == "completed"
        assert runs[0]["iterations"] == 3

    def test_get_recent(self, db):
        UserRepository(db).create("test@example.com")
        repo = AgentRunRepository(db)

        repo.create(1, "thread_1", "pharmacy")
        repo.create(1, "thread_2", "pharmacy")

        recent = repo.get_recent(limit=10)
        assert len(recent) == 2


# ── Config Tests ─────────────────────────────────────────────────────────────


class TestRoutingConfig:
    def test_default_config(self):
        config = RoutingConfig()
        assert config.rules == []

    def test_with_rules(self):
        config = RoutingConfig(
            rules=[
                RoutingRuleConfig(
                    name="pharmacy",
                    match={"forwarded_from": "info@example.com"},
                    route="agent",
                    profile="pharmacy",
                ),
            ]
        )
        assert len(config.rules) == 1
        assert config.rules[0].name == "pharmacy"


class TestAgentConfig:
    def test_default_config(self):
        config = AgentConfig()
        assert config.profiles == {}

    def test_with_profiles(self):
        config = AgentConfig(
            profiles={
                "pharmacy": AgentProfileConfig(
                    name="pharmacy",
                    model="test-model",
                    tools=["search_drugs"],
                ),
            }
        )
        assert "pharmacy" in config.profiles
        assert config.profiles["pharmacy"].tools == ["search_drugs"]
