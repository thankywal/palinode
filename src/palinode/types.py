"""Core types shared by every component.

The one idea worth understanding here is CompensationContract. It is written at
the moment an action is authorised, never reconstructed after an incident. By
the time you know you need to undo something, the context that told you how is
already gone.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Tier(str, enum.Enum):
    """How recoverable an action is, decided before the action runs."""

    T0_REVERSIBLE = "T0"      # exact inverse exists, e.g. a database write
    T1_COMPENSABLE = "T1"     # money or state can be returned, e.g. a refund
    T2_SOCIAL = "T2"          # a human saw it, e.g. a sent email or Slack post
    T3_UNRECOVERABLE = "T3"   # nothing brings this back, e.g. a wire transfer

    @property
    def is_recoverable(self) -> bool:
        return self is not Tier.T3_UNRECOVERABLE

    @property
    def needs_cooling_off(self) -> bool:
        """T2 and T3 get held briefly so there is a window to catch them."""
        return self in (Tier.T2_SOCIAL, Tier.T3_UNRECOVERABLE)


class Verdict(str, enum.Enum):
    ALLOW = "allow"
    HOLD = "hold"        # parked in the cooling off window
    ESCALATE = "escalate"  # needs a human
    BLOCK = "block"


class ActionState(str, enum.Enum):
    PENDING = "pending"
    HELD = "held"
    EXECUTED = "executed"
    REVERSED = "reversed"
    COMPENSATED = "compensated"
    UNRECOVERABLE = "unrecoverable"
    FAILED = "failed"


class CompensationContract(BaseModel):
    """How to take an action back, written before the action is taken.

    An action without one of these does not get to run. That rule is the whole
    reason this system works, so it is enforced in the Warden and not left to
    the good intentions of whoever wrote the agent.
    """

    tool: str = Field(description="tool to call to reverse the original action")
    args: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="prior state needed to restore, captured before execution",
    )
    verify: Optional[str] = Field(
        default=None,
        description="tool that confirms the reversal actually landed",
    )
    notes: Optional[str] = None

    # For T3 there is no reversal, only disclosure. Herald reads these.
    disclosure_required: bool = False
    affected_parties: list[str] = Field(default_factory=list)
    estimated_exposure_usd: float = 0.0


class ActionRecord(BaseModel):
    """One node in the causality graph."""

    id: str = Field(default_factory=lambda: _new_id("act"))
    run_id: str
    agent: str
    # SPIFFE shaped principal for the agent that acted. A display name is not
    # an identity, and an audit trail that only has one cannot answer "who".
    actor: str = ""
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)

    tier: Tier
    tier_reason: str = ""
    state: ActionState = ActionState.PENDING

    # The edge that makes this a graph rather than a log. Undoing one action is
    # never one action, and this is how Regret finds the rest of them.
    caused_by: list[str] = Field(default_factory=list)

    contract: Optional[CompensationContract] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    created_at: datetime = Field(default_factory=_now)
    executed_at: Optional[datetime] = None
    release_at: Optional[datetime] = None  # set while held in cooling off

    # Hash chain over the run. Each entry commits to the one before it, so an
    # action cannot be edited or removed after the fact without every hash
    # after it failing to recompute.
    prev_hash: str = ""
    entry_hash: str = ""

    def cost(self) -> float:
        return self.contract.estimated_exposure_usd if self.contract else 0.0


class Decision(BaseModel):
    """What the Warden decided about a single tool call."""

    verdict: Verdict
    tier: Tier
    reason: str
    hold_seconds: int = 0

    @property
    def allowed(self) -> bool:
        return self.verdict in (Verdict.ALLOW, Verdict.HOLD)


class ReversalStep(BaseModel):
    action_id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    verify: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)


class ReversalPlan(BaseModel):
    """What Regret intends to do, in the order it intends to do it."""

    run_id: str
    steps: list[ReversalStep] = Field(default_factory=list)
    unrecoverable: list[str] = Field(default_factory=list)
    exposure_usd: float = 0.0

    def summary(self) -> str:
        return (
            f"{len(self.steps)} reversible, "
            f"{len(self.unrecoverable)} unrecoverable, "
            f"${self.exposure_usd:,.2f} exposure"
        )
