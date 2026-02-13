"""LLM configuration — model selection, defaults."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import AppConfig


@dataclass
class LLMConfig:
    classify_model: str = "gemini/gemini-2.0-flash"
    draft_model: str = "gemini/gemini-2.5-pro"
    context_model: str = "gemini/gemini-2.0-flash"
    max_classify_tokens: int = 256
    max_draft_tokens: int = 2048
    max_context_tokens: int = 256

    @classmethod
    def from_app_config(cls, config: AppConfig) -> LLMConfig:
        return cls(
            classify_model=config.llm.classify_model,
            draft_model=config.llm.draft_model,
            context_model=config.llm.context_model,
            max_classify_tokens=config.llm.max_classify_tokens,
            max_draft_tokens=config.llm.max_draft_tokens,
            max_context_tokens=config.llm.max_context_tokens,
        )
