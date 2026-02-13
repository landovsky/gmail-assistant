"""LLM Gateway — model-agnostic interface backed by LiteLLM."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import litellm

from src.llm.config import LLMConfig

logger = logging.getLogger(__name__)


@dataclass
class ClassifyResult:
    category: str
    confidence: str
    reasoning: str
    detected_language: str = "cs"

    VALID_CATEGORIES = {"needs_response", "action_required", "payment_request", "fyi", "waiting"}

    @classmethod
    def parse(cls, response: Any) -> ClassifyResult:
        """Parse LLM classification response (expects JSON).

        On parse failure, defaults to needs_response (safer to over-triage
        than silently drop an email into FYI).
        """
        content = response.choices[0].message.content.strip()
        try:
            data = json.loads(content)
            category = data.get("category", "needs_response")
            if category not in cls.VALID_CATEGORIES:
                logger.warning("LLM returned unknown category %r, defaulting to needs_response", category)
                category = "needs_response"
            return cls(
                category=category,
                confidence=data.get("confidence", "medium"),
                reasoning=data.get("reasoning", ""),
                detected_language=data.get("detected_language", "cs"),
            )
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %s", content[:200])
            return cls(
                category="needs_response",
                confidence="low",
                reasoning=f"Parse error; raw: {content[:200]}",
            )


# Need to use Any for litellm response type
from typing import Any


class LLMGateway:
    """Model-agnostic LLM interface. Backed by LiteLLM for 100+ model support."""

    def __init__(self, config: LLMConfig):
        self.config = config
        # Suppress litellm verbose logging
        litellm.set_verbose = False

    def classify(self, system: str, user_message: str) -> ClassifyResult:
        """Call the classification model (fast, cheap model)."""
        try:
            response = litellm.completion(
                model=self.config.classify_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=self.config.max_classify_tokens,
                temperature=0.0,
            )
            return ClassifyResult.parse(response)
        except Exception as e:
            logger.error("LLM classify call failed: %s", e)
            return ClassifyResult(
                category="needs_response",
                confidence="low",
                reasoning=f"LLM error: {e}",
            )

    def draft(self, system: str, user_message: str) -> str:
        """Call the draft generation model (higher quality model)."""
        try:
            response = litellm.completion(
                model=self.config.draft_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=self.config.max_draft_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("LLM draft call failed: %s", e)
            return f"[ERROR: Draft generation failed — {e}]"

    def health_check(self) -> dict[str, bool]:
        """Check if LLM models are reachable."""
        results = {}
        for name, model in [
            ("classify", self.config.classify_model),
            ("draft", self.config.draft_model),
        ]:
            try:
                litellm.completion(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=5,
                )
                results[name] = True
            except Exception:
                results[name] = False
        return results
