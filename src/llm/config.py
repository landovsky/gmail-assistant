"""LLM configuration — model selection, defaults."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import AppConfig


@dataclass
class LLMConfig:
    classify_model: str = "claude-haiku-4-5-20251001"
    draft_model: str = "claude-sonnet-4-5-20250929"
    max_classify_tokens: int = 256
    max_draft_tokens: int = 2048

    @classmethod
    def from_app_config(cls, config: AppConfig) -> LLMConfig:
        return cls(
            classify_model=config.llm.classify_model,
            draft_model=config.llm.draft_model,
            max_classify_tokens=config.llm.max_classify_tokens,
            max_draft_tokens=config.llm.max_draft_tokens,
        )
