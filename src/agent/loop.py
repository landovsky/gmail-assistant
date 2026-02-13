"""Agent execution loop — call LLM with tools, execute tool calls, repeat."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from src.agent.profile import AgentProfile
from src.agent.tools import ToolRegistry
from src.llm.gateway import LLMGateway

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRecord:
    """Record of a single tool call within an agent run."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    iteration: int


@dataclass
class AgentResult:
    """Result of an agent run."""

    status: str  # "completed", "max_iterations", "error"
    final_message: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iterations: int = 0
    error: str | None = None


class AgentLoop:
    """Tool-use loop: call Claude -> execute tool calls -> feed results back -> repeat."""

    def __init__(
        self,
        llm: LLMGateway,
        tool_registry: ToolRegistry,
    ):
        self.llm = llm
        self.tool_registry = tool_registry

    def run(
        self,
        profile: AgentProfile,
        user_message: str,
        *,
        user_id: int | None = None,
        gmail_thread_id: str | None = None,
    ) -> AgentResult:
        """Execute the agent loop until completion or max iterations.

        Args:
            profile: Agent profile with system prompt, tools, and model config
            user_message: The initial user message (email content)
            user_id: For logging
            gmail_thread_id: For logging
        """
        messages: list[dict[str, Any]] = []
        if profile.system_prompt:
            messages.append({"role": "system", "content": profile.system_prompt})
        messages.append({"role": "user", "content": user_message})

        tool_specs = self.tool_registry.get_specs(profile.tool_names or None)
        tool_call_records: list[ToolCallRecord] = []

        for iteration in range(1, profile.max_iterations + 1):
            try:
                response = self.llm.agent_completion(
                    messages=messages,
                    tools=tool_specs,
                    model=profile.model,
                    max_tokens=profile.max_tokens,
                    temperature=profile.temperature,
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                )
            except Exception as e:
                logger.error("Agent loop LLM call failed at iteration %d: %s", iteration, e)
                return AgentResult(
                    status="error",
                    tool_calls=tool_call_records,
                    iterations=iteration,
                    error=str(e),
                )

            message = response.choices[0].message

            # Append assistant message to conversation
            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if message.content:
                assistant_msg["content"] = message.content
            if hasattr(message, "tool_calls") and message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            messages.append(assistant_msg)

            # If no tool calls, the agent is done
            if not hasattr(message, "tool_calls") or not message.tool_calls:
                return AgentResult(
                    status="completed",
                    final_message=message.content or "",
                    tool_calls=tool_call_records,
                    iterations=iteration,
                )

            # Execute each tool call and feed results back
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                logger.info("Agent executing tool %s (iteration %d)", tool_name, iteration)

                result = self.tool_registry.execute(tool_name, arguments)

                record = ToolCallRecord(
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result,
                    iteration=iteration,
                )
                tool_call_records.append(record)

                # Add tool result to conversation
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    }
                )

        # Exhausted max iterations
        final_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                final_content = msg["content"]
                break

        return AgentResult(
            status="max_iterations",
            final_message=final_content,
            tool_calls=tool_call_records,
            iterations=profile.max_iterations,
        )
