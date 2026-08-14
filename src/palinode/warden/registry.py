"""Agent cataloging.

Every agent the Warden supervises registers here first. An unregistered agent
gets nothing, which is the point: the registry is the list of things allowed to
touch the world, and it is checked on every call rather than at startup.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

from ..config import settings
from ..identity import workload_id


class RuntimeMode(str, enum.Enum):
    AUTONOMOUS = "autonomous"
    PROPOSE_ONLY = "propose_only"  # may plan, may not act
    SUSPENDED = "suspended"


@dataclass
class AgentCard:
    name: str
    owner: str
    description: str = ""
    tools: set[str] = field(default_factory=set)
    budget_usd_per_hour: float = field(default_factory=lambda: settings.default_budget_usd)
    mode: RuntimeMode = RuntimeMode.AUTONOMOUS
    # Bumped on every re-registration with different grants. The track asks for
    # publishing, versioning and discovery, and without this the catalog cannot
    # answer which version of an agent took an action three weeks ago.
    version: int = 1

    @property
    def identity(self) -> str:
        return workload_id(settings.project, self.owner, self.name)

    def may_use(self, tool: str) -> bool:
        # An empty grant list means nothing is granted. Defaulting to open here
        # would make the registry decorative.
        return tool in self.tools

    def acting(self) -> bool:
        return self.mode is RuntimeMode.AUTONOMOUS


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentCard] = {}
        self._history: dict[str, list[AgentCard]] = {}

    def register(self, card: AgentCard) -> AgentCard:
        existing = self._agents.get(card.name)
        if existing is not None:
            # Same grants means the same agent, not a new version. Bumping on
            # every restart would make the version number meaningless.
            changed = (
                existing.tools != card.tools
                or existing.budget_usd_per_hour != card.budget_usd_per_hour
            )
            card.version = existing.version + 1 if changed else existing.version
            self._history.setdefault(card.name, []).append(existing)
        self._agents[card.name] = card
        return card

    def history(self, name: str) -> list[AgentCard]:
        """Every previous version of an agent, oldest first."""
        return list(self._history.get(name, []))

    def get(self, name: str) -> Optional[AgentCard]:
        return self._agents.get(name)

    def all(self) -> list[AgentCard]:
        return sorted(self._agents.values(), key=lambda c: c.name)

    def downgrade(self, name: str, reason: str = "") -> Optional[AgentCard]:
        """Drop an agent to propose only. Called when its budget runs out.

        Deliberately not reversible from inside the system. Putting an agent
        back into autonomous mode is a human decision.
        """
        card = self._agents.get(name)
        if card is not None and card.mode is RuntimeMode.AUTONOMOUS:
            card.mode = RuntimeMode.PROPOSE_ONLY
            card.description = f"{card.description} [downgraded: {reason}]".strip()
        return card


_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
