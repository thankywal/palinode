"""The supervised fleet.

These agents are deliberately unremarkable. They are ordinary ADK agents doing
ordinary procurement work, and that is the point: Palinode wraps them without
either of them knowing much about the other. Two lines of setup, one call to
supervise, and every tool call they make now goes through the Warden.

Requires google-adk and credentials. The scripted walkthrough in demo.py covers
the same ground with neither.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.tools import FunctionTool  # noqa: E402

from palinode.config import settings  # noqa: E402
from palinode.connectors import base as conn  # noqa: E402
from palinode.warden import AgentCard, get_registry, supervise  # noqa: E402

MODEL = settings.classifier_model


def _tools(*names: str) -> list[FunctionTool]:
    return [FunctionTool(func=conn._TOOLS[name]) for name in names]


INSTRUCTION = """You are part of a procurement fleet.

Every tool call you make that is not a plain database write must include a
_palinode_contract argument describing how to undo it. Shape:

  {"tool": "<reversing tool>", "args": {...}, "verify": "<tool or null>",
   "estimated_exposure_usd": <number>, "affected_parties": ["..."]}

If an action genuinely cannot be undone, set estimated_exposure_usd to the
amount at risk and list who is affected. Do not invent a reversal that does not
exist. An honest empty contract on an irreversible action is correct. A made up
one is worse than nothing, because it will be trusted during an incident."""


def build() -> list[LlmAgent]:
    registry = get_registry()

    registry.register(
        AgentCard(
            name="sourcing",
            owner="procurement",
            description="approves vendors and announces them",
            tools={"db_write", "slack_post", "email_send"},
        )
    )
    registry.register(
        AgentCard(
            name="invoice",
            owner="procurement",
            description="matches invoices to purchase orders",
            tools={"db_write", "github_merge", "email_send"},
        )
    )
    registry.register(
        AgentCard(
            name="payables",
            owner="finance",
            description="settles approved invoices",
            tools={"stripe_charge", "wire_transfer", "email_send"},
            budget_usd_per_hour=5000,
        )
    )

    return [
        supervise(
            LlmAgent(
                name="sourcing",
                model=MODEL,
                instruction=INSTRUCTION,
                tools=_tools("db_write", "slack_post", "email_send"),
            )
        ),
        supervise(
            LlmAgent(
                name="invoice",
                model=MODEL,
                instruction=INSTRUCTION,
                tools=_tools("db_write", "github_merge", "email_send"),
            )
        ),
        supervise(
            LlmAgent(
                name="payables",
                model=MODEL,
                instruction=INSTRUCTION,
                tools=_tools("stripe_charge", "wire_transfer", "email_send"),
            )
        ),
    ]
