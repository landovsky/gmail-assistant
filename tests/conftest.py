"""Shared fixtures for end-to-end tests that call real LLM APIs."""

from __future__ import annotations

import os

import pytest
import yaml

from src.llm.config import LLMConfig
from src.llm.gateway import LLMGateway


def _has_llm_api_key() -> bool:
    """Check whether at least one LLM API key is configured."""
    return bool(
        os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    )


def _llm_config() -> LLMConfig:
    """Build an LLMConfig from env vars (GMA_LLM_* override defaults)."""
    return LLMConfig(
        classify_model=os.getenv("GMA_LLM_CLASSIFY_MODEL", LLMConfig.classify_model),
        draft_model=os.getenv("GMA_LLM_DRAFT_MODEL", LLMConfig.draft_model),
        context_model=os.getenv("GMA_LLM_CONTEXT_MODEL", LLMConfig.context_model),
    )


# ── skip marker ──────────────────────────────────────────────────────────────

skip_without_api_key = pytest.mark.skipif(
    not _has_llm_api_key(),
    reason="No LLM API key set (need ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY)",
)


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def llm_config() -> LLMConfig:
    """Session-scoped LLM config resolved from env."""
    return _llm_config()


@pytest.fixture(scope="session")
def llm_gateway(llm_config: LLMConfig) -> LLMGateway:
    """Session-scoped LLM gateway backed by a real API."""
    return LLMGateway(llm_config)


@pytest.fixture(scope="session")
def classification_cases() -> list[dict]:
    """Load classification test cases from the YAML fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "classification_cases.yaml")
    with open(fixture_path) as f:
        data = yaml.safe_load(f)
    return data["cases"]


@pytest.fixture(scope="session")
def classification_defaults() -> dict:
    """Load defaults from the YAML fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "classification_cases.yaml")
    with open(fixture_path) as f:
        data = yaml.safe_load(f)
    return data.get("defaults", {})


@pytest.fixture(scope="session")
def style_config() -> dict:
    """Load communication styles for draft tests."""
    example_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "communication_styles.example.yml"
    )
    if os.path.exists(example_path):
        with open(example_path) as f:
            return yaml.safe_load(f)
    # Minimal fallback
    return {
        "default": "business",
        "styles": {
            "business": {
                "language": "auto",
                "rules": ["Professional but concise"],
                "sign_off": "Best regards",
            },
        },
    }
