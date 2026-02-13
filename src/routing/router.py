"""Router — route emails to pipeline (classify→draft) or agent processing."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.config import RoutingConfig
from src.routing.rules import matches_rule

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of routing an email."""

    route_name: str  # "pipeline" or "agent"
    profile_name: str = ""  # agent profile name (empty for pipeline)
    rule_name: str = ""  # name of the matching rule
    metadata: dict[str, Any] = field(default_factory=dict)


class Router:
    """Config-driven email router."""

    def __init__(self, config: RoutingConfig):
        self.config = config

    def route(self, message_meta: dict[str, Any]) -> RoutingDecision:
        """Determine the route for a message.

        Args:
            message_meta: Dict with keys: sender_email, subject, headers, body

        Returns:
            RoutingDecision with route type and profile name
        """
        for rule in self.config.rules:
            if matches_rule(rule, message_meta):
                logger.info(
                    "Routing matched rule %r: route=%s, profile=%s",
                    rule.name,
                    rule.route,
                    rule.profile,
                )
                return RoutingDecision(
                    route_name=rule.route,
                    profile_name=rule.profile,
                    rule_name=rule.name,
                )

        # Default: standard pipeline
        logger.debug("No routing rule matched, using default pipeline")
        return RoutingDecision(route_name="pipeline", rule_name="default_fallback")
