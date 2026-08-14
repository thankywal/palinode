"""The Warden.

Wires into ADK through before_tool_callback and after_tool_callback. Returning
a dict from before_tool_callback stops ADK from running the tool and hands that
dict back to the model as the result, which is exactly the shape a policy gate
needs, so no monkey patching is required anywhere in this file.

Order of checks matters. Registry first because an unknown agent should never
reach a model call. Classification next because everything downstream keys off
the tier. Contract after that. Budget last, since it is the only check that
needs to know what the action costs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..config import settings
from ..ledger.store import get_ledger
from ..types import (
    ActionRecord,
    ActionState,
    CompensationContract,
    Decision,
    Tier,
    Verdict,
)
from .classifier import get_classifier
from .registry import get_registry

log = logging.getLogger("palinode.warden")

# Key used to pass the compensation contract alongside the tool arguments.
CONTRACT_ARG = "_palinode_contract"
# Set by the interceptor so the next action in the same turn knows its parent.
LAST_ACTION_KEY = "palinode:last_action"
RUN_KEY = "palinode:run_id"


class Warden:
    def __init__(self) -> None:
        self.ledger = get_ledger()
        self.registry = get_registry()
        self.classifier = get_classifier()

    # ------------------------------------------------------------- decision

    async def evaluate(
        self,
        *,
        agent: str,
        tool: str,
        args: dict[str, Any],
        contract: Optional[CompensationContract],
    ) -> tuple[Decision, Optional[ActionRecord]]:
        card = self.registry.get(agent)
        if card is None:
            return (
                Decision(
                    verdict=Verdict.BLOCK,
                    tier=Tier.T3_UNRECOVERABLE,
                    reason=f"agent {agent} is not in the registry",
                ),
                None,
            )

        if not card.may_use(tool):
            return (
                Decision(
                    verdict=Verdict.BLOCK,
                    tier=Tier.T3_UNRECOVERABLE,
                    reason=f"{agent} has no grant for {tool}",
                ),
                None,
            )

        tier, reason = await self.classifier.classify(tool, args)

        if not card.acting():
            return (
                Decision(
                    verdict=Verdict.ESCALATE,
                    tier=tier,
                    reason=f"{agent} is in {card.mode.value} mode",
                ),
                None,
            )

        # T0 is cheap to reverse and we hold the snapshot ourselves, so it does
        # not need the agent to spell out a contract. Everything else does.
        if settings.require_contract and contract is None and tier is not Tier.T0_REVERSIBLE:
            return (
                Decision(
                    verdict=Verdict.ESCALATE,
                    tier=tier,
                    reason="no compensation contract supplied for a non trivial action",
                ),
                None,
            )

        exposure = contract.estimated_exposure_usd if contract else 0.0
        if tier is Tier.T3_UNRECOVERABLE and exposure > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            spent = await self.ledger.spend_since(agent, cutoff)
            if spent + exposure > card.budget_usd_per_hour:
                self.registry.downgrade(
                    agent,
                    f"blast radius budget exhausted at ${spent:,.2f}",
                )
                return (
                    Decision(
                        verdict=Verdict.ESCALATE,
                        tier=tier,
                        reason=(
                            f"would put {agent} at ${spent + exposure:,.2f} of unrecoverable "
                            f"exposure against a ${card.budget_usd_per_hour:,.2f} budget"
                        ),
                    ),
                    None,
                )

        hold = settings.cooling_off_seconds if tier.needs_cooling_off else 0
        record = ActionRecord(
            run_id="",  # filled in by the caller, which knows the invocation
            agent=agent,
            tool=tool,
            args=args,
            tier=tier,
            tier_reason=reason,
            contract=contract,
            state=ActionState.HELD if hold else ActionState.PENDING,
        )
        if hold:
            record.release_at = datetime.now(timezone.utc) + timedelta(seconds=hold)

        return (
            Decision(
                verdict=Verdict.HOLD if hold else Verdict.ALLOW,
                tier=tier,
                reason=reason,
                hold_seconds=hold,
            ),
            record,
        )

    # -------------------------------------------------------- adk callbacks

    async def before_tool(self, tool, args: dict[str, Any], tool_context) -> Optional[dict]:
        """ADK before_tool_callback. A dict return stops the tool running."""
        raw = args.pop(CONTRACT_ARG, None)
        contract = CompensationContract.model_validate(raw) if raw else None

        agent = tool_context.agent_name
        decision, record = await self.evaluate(
            agent=agent, tool=tool.name, args=args, contract=contract
        )

        if not decision.allowed:
            log.warning("blocked %s.%s: %s", agent, tool.name, decision.reason)
            return {
                "palinode": "blocked",
                "verdict": decision.verdict.value,
                "tier": decision.tier.value,
                "reason": decision.reason,
            }

        assert record is not None
        record.run_id = tool_context.state.get(RUN_KEY) or tool_context.invocation_id
        parent = tool_context.state.get(LAST_ACTION_KEY)
        if parent:
            # Declared lineage. Inferring this automatically is the next thing
            # to build, but a declaration that is right beats an inference that
            # is nearly right when the output is a refund.
            record.caused_by = [parent]

        await self.ledger.append(record)
        tool_context.state[LAST_ACTION_KEY] = record.id
        tool_context.state[RUN_KEY] = record.run_id
        tool_context.state["palinode:pending"] = record.id
        return None

    async def after_tool(
        self, tool, args: dict[str, Any], tool_context, tool_response: dict
    ) -> Optional[dict]:
        """ADK after_tool_callback. Records the outcome, never alters it."""
        action_id = tool_context.state.get("palinode:pending")
        if not action_id:
            return None

        record = await self.ledger.get(action_id)
        if record is None:
            return None

        failed = isinstance(tool_response, dict) and "error" in tool_response
        if failed:
            state = ActionState.FAILED
        elif record.tier is Tier.T3_UNRECOVERABLE:
            state = ActionState.UNRECOVERABLE
        else:
            state = ActionState.EXECUTED

        record.executed_at = datetime.now(timezone.utc)
        await self.ledger.advance(
            action_id,
            state,
            result=tool_response if isinstance(tool_response, dict) else {"value": tool_response},
        )
        return None


_warden: Optional[Warden] = None


def get_warden() -> Warden:
    global _warden
    if _warden is None:
        _warden = Warden()
    return _warden


def supervise(agent):
    """Attach the Warden to an ADK LlmAgent.

    Usage:
        agent = supervise(LlmAgent(name="payables", model=..., tools=[...]))
    """
    warden = get_warden()
    agent.before_tool_callback = warden.before_tool
    agent.after_tool_callback = warden.after_tool
    return agent
