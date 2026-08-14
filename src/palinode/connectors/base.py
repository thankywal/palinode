"""Connectors.

Each connector owns a tool and the inverse of that tool. Keeping the pair in
one place is deliberate. When they live apart, the inverse rots, and you find
out during an incident.

The implementations below run against an in memory world so the demo works
without credentials. Real connectors replace the body of each function and
nothing else changes, because the Warden only cares about names and contracts.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

log = logging.getLogger("palinode.connectors")

Tool = Callable[..., Awaitable[dict]]
_TOOLS: dict[str, Tool] = {}


def tool(name: str) -> Callable[[Tool], Tool]:
    def register(fn: Tool) -> Tool:
        _TOOLS[name] = fn
        return fn

    return register


async def run_tool(name: str, args: dict[str, Any]) -> dict:
    fn = _TOOLS.get(name)
    if fn is None:
        raise KeyError(f"no connector registered for {name}")
    return await fn(**args)


def registered() -> list[str]:
    return sorted(_TOOLS)


# --------------------------------------------------------------- the world

WORLD: dict[str, dict] = {
    "db": {},
    "outbox": {},
    "slack": {},
    "charges": {},
    "merges": {},
    "wires": {},
}


def reset_world() -> None:
    for bucket in WORLD.values():
        bucket.clear()


# ------------------------------------------------------------------ postgres


@tool("db_write")
async def db_write(table: str, key: str, value: Any, **_: Any) -> dict:
    prior = WORLD["db"].get(f"{table}:{key}")
    WORLD["db"][f"{table}:{key}"] = value
    return {"ok": True, "table": table, "key": key, "prior": prior}


@tool("db_restore")
async def db_restore(table: str, key: str, prior: Any = None, **_: Any) -> dict:
    slot = f"{table}:{key}"
    if prior is None:
        WORLD["db"].pop(slot, None)
    else:
        WORLD["db"][slot] = prior
    return {"ok": True, "restored": slot}


# --------------------------------------------------------------------- email


@tool("email_send")
async def email_send(to: str, subject: str, body: str, **_: Any) -> dict:
    message_id = f"msg_{len(WORLD['outbox']) + 1}"
    WORLD["outbox"][message_id] = {"to": to, "subject": subject, "delivered": True}
    return {"ok": True, "message_id": message_id}


@tool("email_recall")
async def email_recall(message_id: str = "", **_: Any) -> dict:
    """Only works inside the cooling off window, because SMTP has no recall.

    Once a message is delivered it is gone. Pretending otherwise is the single
    easiest way to build a demo that lies, so this returns honestly and the
    caller falls back to a retraction.
    """
    message = WORLD["outbox"].get(message_id)
    if message is None:
        return {"ok": False, "reason": "unknown message"}
    if message.get("delivered"):
        return {"ok": False, "reason": "already delivered, smtp has no recall"}
    WORLD["outbox"].pop(message_id, None)
    return {"ok": True, "recalled": message_id}


@tool("email_retract")
async def email_retract(to: str = "", original_subject: str = "", **_: Any) -> dict:
    retraction_id = f"msg_{len(WORLD['outbox']) + 1}"
    WORLD["outbox"][retraction_id] = {
        "to": to,
        "subject": f"Correction: {original_subject}",
        "delivered": True,
        "is_retraction": True,
    }
    return {"ok": True, "message_id": retraction_id, "compensated": True}


# --------------------------------------------------------------------- slack


@tool("slack_post")
async def slack_post(channel: str, text: str, **_: Any) -> dict:
    ts = f"{len(WORLD['slack']) + 1}.0001"
    WORLD["slack"][ts] = {"channel": channel, "text": text}
    return {"ok": True, "ts": ts, "channel": channel}


@tool("slack_delete")
async def slack_delete(channel: str = "", ts: str = "", **_: Any) -> dict:
    # chat.delete only works on messages our own bot token posted, which is the
    # case here, but it does not unsee the message for anyone already reading.
    existed = WORLD["slack"].pop(ts, None) is not None
    return {"ok": existed, "deleted": ts}


# -------------------------------------------------------------------- stripe


@tool("stripe_charge")
async def stripe_charge(
    customer: str, amount_usd: float, idempotency_key: str = "", **_: Any
) -> dict:
    # The caller names the charge. Stripe works this way for the same reason:
    # if the response is lost you still know what you created. It also means a
    # compensation contract can reference the charge before it exists, so the
    # contract never has to be edited after the fact.
    charge_id = idempotency_key or f"ch_{len(WORLD['charges']) + 1}"
    WORLD["charges"][charge_id] = {
        "customer": customer,
        "amount_usd": amount_usd,
        "refunded": 0.0,
    }
    return {"ok": True, "charge_id": charge_id, "amount_usd": amount_usd}


@tool("stripe_refund")
async def stripe_refund(charge_id: str = "", amount_usd: float = 0.0, **_: Any) -> dict:
    charge = WORLD["charges"].get(charge_id)
    if charge is None:
        return {"ok": False, "reason": "unknown charge"}
    amount = amount_usd or charge["amount_usd"]
    if charge["refunded"] + amount > charge["amount_usd"] + 1e-9:
        return {"ok": False, "reason": "refund exceeds original charge"}
    charge["refunded"] += amount
    return {"ok": True, "charge_id": charge_id, "refunded_usd": amount}


@tool("stripe_confirm_refund")
async def stripe_confirm_refund(charge_id: str = "", **_: Any) -> dict:
    """A refund reported as succeeded is not the same as money that moved."""
    charge = WORLD["charges"].get(charge_id, {})
    return {"confirmed": bool(charge) and charge.get("refunded", 0) > 0}


# -------------------------------------------------------------------- github


@tool("github_merge")
async def github_merge(repo: str, pr: int, **_: Any) -> dict:
    sha = f"sha_{len(WORLD['merges']) + 1}"
    WORLD["merges"][sha] = {"repo": repo, "pr": pr, "reverted": False}
    return {"ok": True, "repo": repo, "pr": pr, "merge_sha": sha}


@tool("github_revert")
async def github_revert(repo: str = "", merge_sha: str = "", **_: Any) -> dict:
    merge = WORLD["merges"].get(merge_sha)
    if merge is None:
        return {"ok": False, "reason": "unknown merge"}
    merge["reverted"] = True
    return {"ok": True, "revert_of": merge_sha}


# ---------------------------------------------------------------------- wire


@tool("wire_transfer")
async def wire_transfer(beneficiary: str, amount_usd: float, **_: Any) -> dict:
    wire_id = f"wire_{len(WORLD['wires']) + 1}"
    WORLD["wires"][wire_id] = {"beneficiary": beneficiary, "amount_usd": amount_usd}
    log.warning("wire sent to %s for $%.2f, this does not come back", beneficiary, amount_usd)
    return {"ok": True, "wire_id": wire_id, "settled": True}
