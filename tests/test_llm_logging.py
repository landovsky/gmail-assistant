"""Tests for LLM call logging functionality."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from src.config import AppConfig
from src.db.connection import Database
from src.db.models import LLMCallRepository
from src.llm.config import LLMConfig
from src.llm.gateway import LLMGateway


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    from src.db.models import UserRepository

    config = AppConfig.from_yaml()
    config.database.sqlite_path = str(tmp_path / "test.db")
    db = Database(config)
    db.initialize_schema()

    # Create a test user for foreign key constraints
    user_repo = UserRepository(db)
    user_repo.create("test@example.com", "Test User")

    return db


@pytest.fixture
def call_repo(db):
    """Create an LLM call repository."""
    return LLMCallRepository(db)


@pytest.fixture
def llm_gateway(call_repo):
    """Create an LLM gateway with call logging."""
    config = LLMConfig(
        classify_model="anthropic/claude-haiku-4",
        draft_model="anthropic/claude-sonnet-4",
        context_model="anthropic/claude-haiku-4",
    )
    return LLMGateway(config, call_repo=call_repo)


def test_llm_call_repository_log(call_repo):
    """Test that LLM calls can be logged."""
    call_id = call_repo.log(
        call_type="classify",
        model="anthropic/claude-haiku-4",
        user_id=1,
        gmail_thread_id="thread_123",
        system_prompt="You are a classifier.",
        user_message="Classify this email.",
        response_text='{"category": "fyi"}',
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=500,
    )

    assert call_id > 0

    # Verify we can retrieve it
    calls = call_repo.get_by_thread("thread_123")
    assert len(calls) == 1
    assert calls[0]["call_type"] == "classify"
    assert calls[0]["model"] == "anthropic/claude-haiku-4"
    assert calls[0]["total_tokens"] == 150
    assert calls[0]["latency_ms"] == 500


def test_llm_call_repository_get_stats(call_repo):
    """Test token usage statistics."""
    # Log multiple calls
    call_repo.log(
        call_type="classify",
        model="anthropic/claude-haiku-4",
        user_id=1,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=500,
    )
    call_repo.log(
        call_type="draft",
        model="anthropic/claude-sonnet-4",
        user_id=1,
        prompt_tokens=200,
        completion_tokens=100,
        total_tokens=300,
        latency_ms=1000,
    )

    stats = call_repo.get_stats(user_id=1)
    assert stats["call_count"] == 2
    assert stats["total_tokens"] == 450
    assert stats["total_prompt_tokens"] == 300
    assert stats["total_completion_tokens"] == 150


@patch("litellm.completion")
def test_llm_gateway_classify_logs_call(mock_completion, llm_gateway, call_repo):
    """Test that classify method logs the LLM call."""
    # Mock the LiteLLM response
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content='{"category": "fyi", "confidence": "high", "reasoning": "Test"}'))
    ]
    mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    mock_completion.return_value = mock_response

    # Call classify with context
    result = llm_gateway.classify(
        system="You are a classifier.",
        user_message="Classify this email.",
        user_id=1,
        gmail_thread_id="thread_123",
    )

    # Verify result
    assert result.category == "fyi"

    # Verify the call was logged
    calls = call_repo.get_by_thread("thread_123")
    assert len(calls) == 1
    assert calls[0]["call_type"] == "classify"
    assert calls[0]["user_id"] == 1
    assert calls[0]["gmail_thread_id"] == "thread_123"
    assert calls[0]["total_tokens"] == 150
    assert calls[0]["latency_ms"] >= 0


@patch("litellm.completion")
def test_llm_gateway_draft_logs_call(mock_completion, llm_gateway, call_repo):
    """Test that draft method logs the LLM call."""
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="This is a draft response."))]
    mock_response.usage = Mock(prompt_tokens=200, completion_tokens=100, total_tokens=300)
    mock_completion.return_value = mock_response

    result = llm_gateway.draft(
        system="You are a drafter.",
        user_message="Draft a response.",
        user_id=1,
        gmail_thread_id="thread_456",
    )

    assert result == "This is a draft response."

    calls = call_repo.get_by_thread("thread_456")
    assert len(calls) == 1
    assert calls[0]["call_type"] == "draft"
    assert calls[0]["total_tokens"] == 300


@patch("litellm.completion")
def test_llm_gateway_rework_logs_as_rework(mock_completion, llm_gateway, call_repo):
    """Test that rework calls are logged with call_type='rework'."""
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="This is a reworked draft."))]
    mock_response.usage = Mock(prompt_tokens=250, completion_tokens=120, total_tokens=370)
    mock_completion.return_value = mock_response

    result = llm_gateway.draft(
        system="You are a drafter.",
        user_message="Rework this draft.",
        user_id=1,
        gmail_thread_id="thread_789",
        is_rework=True,
    )

    assert result == "This is a reworked draft."

    calls = call_repo.get_by_thread("thread_789")
    assert len(calls) == 1
    assert calls[0]["call_type"] == "rework"
    assert calls[0]["total_tokens"] == 370


@patch("litellm.completion")
def test_llm_gateway_logs_errors(mock_completion, llm_gateway, call_repo):
    """Test that failed LLM calls are logged with error details."""
    mock_completion.side_effect = Exception("API timeout")

    result = llm_gateway.classify(
        system="You are a classifier.",
        user_message="Classify this.",
        user_id=1,
        gmail_thread_id="thread_error",
    )

    # Should return error result
    assert result.category == "needs_response"
    assert "API timeout" in result.reasoning

    # Error should be logged
    calls = call_repo.get_by_thread("thread_error")
    assert len(calls) == 1
    assert calls[0]["error"] is not None
    assert "API timeout" in calls[0]["error"]
