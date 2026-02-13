"""LLM Gateway — model-agnostic interface backed by LiteLLM."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import litellm

from src.llm.config import LLMConfig

if TYPE_CHECKING:
    from src.db.models import LLMCallRepository

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) that some models wrap around JSON."""
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else text


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
        content = strip_code_fences(response.choices[0].message.content.strip())
        try:
            data = json.loads(content)
            category = data.get("category", "needs_response")
            if category not in cls.VALID_CATEGORIES:
                logger.warning(
                    "LLM returned unknown category %r, defaulting to needs_response", category
                )
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

    def __init__(self, config: LLMConfig, call_repo: LLMCallRepository | None = None):
        self.config = config
        self.call_repo = call_repo
        # Suppress litellm verbose logging
        litellm.set_verbose = False

    def classify(self, system: str, user_message: str, **kwargs: Any) -> ClassifyResult:
        """Call the classification model (fast, cheap model).

        Args:
            system: System prompt
            user_message: User message
            **kwargs: Optional user_id and gmail_thread_id for logging
        """
        user_id = kwargs.get("user_id")
        gmail_thread_id = kwargs.get("gmail_thread_id")
        start_time = time.monotonic()
        error_msg = None

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
            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Extract token usage
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            total_tokens = getattr(usage, "total_tokens", 0) if usage else 0

            response_text = response.choices[0].message.content

            # Log the call
            if self.call_repo:
                self.call_repo.log(
                    call_type="classify",
                    model=self.config.classify_model,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    system_prompt=system,
                    user_message=user_message,
                    response_text=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                )

            return ClassifyResult.parse(response)
        except Exception as e:
            logger.error("LLM classify call failed: %s", e)
            error_msg = str(e)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Log the failed call
            if self.call_repo:
                self.call_repo.log(
                    call_type="classify",
                    model=self.config.classify_model,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    system_prompt=system,
                    user_message=user_message,
                    latency_ms=latency_ms,
                    error=error_msg,
                )

            return ClassifyResult(
                category="needs_response",
                confidence="low",
                reasoning=f"LLM error: {e}",
            )

    def draft(self, system: str, user_message: str, **kwargs: Any) -> str:
        """Call the draft generation model (higher quality model).

        Args:
            system: System prompt
            user_message: User message
            **kwargs: Optional user_id and gmail_thread_id for logging
        """
        user_id = kwargs.get("user_id")
        gmail_thread_id = kwargs.get("gmail_thread_id")
        # Determine if this is a rework call based on kwargs
        is_rework = kwargs.get("is_rework", False)
        call_type = "rework" if is_rework else "draft"
        start_time = time.monotonic()
        error_msg = None

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
            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Extract token usage
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            total_tokens = getattr(usage, "total_tokens", 0) if usage else 0

            response_text = response.choices[0].message.content

            # Log the call
            if self.call_repo:
                self.call_repo.log(
                    call_type=call_type,
                    model=self.config.draft_model,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    system_prompt=system,
                    user_message=user_message,
                    response_text=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                )

            return response_text
        except Exception as e:
            logger.error("LLM draft call failed: %s", e)
            error_msg = str(e)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Log the failed call
            if self.call_repo:
                self.call_repo.log(
                    call_type=call_type,
                    model=self.config.draft_model,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    system_prompt=system,
                    user_message=user_message,
                    latency_ms=latency_ms,
                    error=error_msg,
                )

            return f"[ERROR: Draft generation failed — {e}]"

    def generate_context_queries(self, system: str, user_message: str, **kwargs: Any) -> str:
        """Call context model to generate Gmail search queries. Returns raw JSON string.

        Args:
            system: System prompt
            user_message: User message
            **kwargs: Optional user_id and gmail_thread_id for logging
        """
        user_id = kwargs.get("user_id")
        gmail_thread_id = kwargs.get("gmail_thread_id")
        start_time = time.monotonic()
        error_msg = None

        try:
            response = litellm.completion(
                model=self.config.context_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=self.config.max_context_tokens,
                temperature=0.0,
            )
            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Extract token usage
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            total_tokens = getattr(usage, "total_tokens", 0) if usage else 0

            response_text = response.choices[0].message.content.strip()

            # Log the call
            if self.call_repo:
                self.call_repo.log(
                    call_type="context",
                    model=self.config.context_model,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    system_prompt=system,
                    user_message=user_message,
                    response_text=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                )

            return response_text
        except Exception as e:
            logger.error("LLM context query generation failed: %s", e)
            error_msg = str(e)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Log the failed call
            if self.call_repo:
                self.call_repo.log(
                    call_type="context",
                    model=self.config.context_model,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    system_prompt=system,
                    user_message=user_message,
                    latency_ms=latency_ms,
                    error=error_msg,
                )

            return "[]"

    def agent_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> Any:
        """Call LLM with tool-use support for the agent loop.

        Args:
            messages: Full conversation history (system + user + assistant + tool results)
            tools: Tool definitions in OpenAI function-calling format
            model: Model to use (defaults to draft model)
            max_tokens: Max tokens for response
            temperature: Sampling temperature
            **kwargs: Optional user_id and gmail_thread_id for logging
        """
        user_id = kwargs.get("user_id")
        gmail_thread_id = kwargs.get("gmail_thread_id")
        used_model = model or self.config.draft_model
        start_time = time.monotonic()

        try:
            completion_kwargs: dict[str, Any] = {
                "model": used_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if tools:
                completion_kwargs["tools"] = tools

            response = litellm.completion(**completion_kwargs)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            total_tokens = getattr(usage, "total_tokens", 0) if usage else 0

            response_text = ""
            message = response.choices[0].message
            if message.content:
                response_text = message.content

            if self.call_repo:
                self.call_repo.log(
                    call_type="agent",
                    model=used_model,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    system_prompt=messages[0]["content"] if messages else None,
                    user_message=str(len(messages)) + " messages",
                    response_text=response_text[:2000] if response_text else None,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                )

            return response
        except Exception as e:
            logger.error("LLM agent completion failed: %s", e)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if self.call_repo:
                self.call_repo.log(
                    call_type="agent",
                    model=used_model,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    system_prompt=messages[0]["content"] if messages else None,
                    user_message=str(len(messages)) + " messages",
                    latency_ms=latency_ms,
                    error=str(e),
                )
            raise

    def health_check(self) -> dict[str, bool]:
        """Check if LLM models are reachable."""
        results = {}
        for name, model in [
            ("classify", self.config.classify_model),
            ("draft", self.config.draft_model),
            ("context", self.config.context_model),
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
