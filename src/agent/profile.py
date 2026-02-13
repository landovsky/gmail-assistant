"""Agent profiles — system prompt, tools, model config per agent type."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.config import AgentProfileConfig, REPO_ROOT

logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    """Runtime agent profile with resolved system prompt and tool list."""

    name: str
    model: str = "gemini/gemini-2.5-pro"
    max_tokens: int = 4096
    temperature: float = 0.3
    max_iterations: int = 10
    system_prompt: str = ""
    tool_names: list[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: AgentProfileConfig) -> AgentProfile:
        """Build a profile from config, resolving the system prompt file."""
        system_prompt = ""
        if config.system_prompt_file:
            prompt_path = REPO_ROOT / config.system_prompt_file
            if prompt_path.exists():
                system_prompt = prompt_path.read_text().strip()
            else:
                logger.warning("System prompt file not found: %s", prompt_path)

        return cls(
            name=config.name,
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            max_iterations=config.max_iterations,
            system_prompt=system_prompt,
            tool_names=list(config.tools),
        )
