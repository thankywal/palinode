"""Stripe, for real, in test mode.

The other connectors run against an in memory world. This one talks to Stripe,
so the charge and the refund in the demo are a charge and a refund that exist
in somebody's dashboard.

Three rules this file enforces, in order of how much they matter:

  1. A key that does not begin with `sk_test_` is refused outright. Not warned
     about, refused. The whole demo is about actions that cannot be taken back,
     and running it against a live key would be exactly that mistake, made by
     the tool built to prevent it.

  2. No key means no live mode. The in memory connector stays registered and
     the demo runs as before, so a missing secret degrades the fidelity of the
     demo rather than breaking it.

  3. The caller names the charge. Stripe's idempotency keys exist for the case
     where the response is lost, and Palinode needs the same property for a
     different reason: the compensation contract has to point at the charge
     before the charge exists, or the ledger entry gets edited after it was
     written.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .base import WORLD, _TOOLS

log = logging.getLogger("palinode.stripe")

API = "https://api.stripe.com/v1"
TEST_PREFIX = "sk_test_"


class LiveKeyRefused(RuntimeError):
    """Raised when someone points this at real money."""


def _key() -> Optional[str]:
    raw = (os.getenv("STRIPE_API_KEY") or "").strip()
    if not raw:
        return None
    if not raw.startswith(TEST_PREFIX):
        # Deliberately fatal rather than a fallback. Quietly dropping to the
        # simulator here would mean a demo that looks identical whether or not
        # it is about to move real money.
        raise LiveKeyRefused(
            "STRIPE_API_KEY does not start with sk_test_. This demo issues "
            "charges and refunds and will not run against a live key."
        )
    return raw


def enabled() -> bool:
    try:
        return _key() is not None
    except LiveKeyRefused:
        raise


async def _post(path: str, data: dict[str, Any]) -> dict:
    import httpx

    key = _key()
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{API}/{path}",
            auth=(key, ""),
            data={k: v for k, v in data.items() if v is not None},
        )
    payload = response.json()
    if response.status_code >= 400:
        message = (payload.get("error") or {}).get("message", response.text[:200])
        raise RuntimeError(f"stripe {path} failed: {message}")
    return payload


async def _get(path: str) -> dict:
    import httpx

    key = _key()
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{API}/{path}", auth=(key, ""))
    return response.json()


# Deliberately not decorated. The @tool decorator registers at import time,
# which replaced the in memory tools whether or not a key existed and left the
# tests calling Stripe with no credentials. install() registers these only when
# there is a test key to use.


async def stripe_charge(
    customer: str, amount_usd: float, idempotency_key: str = "", **_: Any
) -> dict:
    """A real test mode PaymentIntent, confirmed against Stripe's test card."""
    intent = await _post(
        "payment_intents",
        {
            "amount": int(round(amount_usd * 100)),
            "currency": "usd",
            "payment_method": "pm_card_visa",
            "confirm": "true",
            "description": f"Palinode demo, {customer}",
            "metadata[palinode_key]": idempotency_key or "",
            "metadata[customer]": customer,
            # Stripe would otherwise try to send the customer to a bank page.
            "automatic_payment_methods[enabled]": "true",
            "automatic_payment_methods[allow_redirects]": "never",
        },
    )

    # Kept so the in memory verifier and the dashboard keep working unchanged.
    WORLD["charges"][intent["id"]] = {
        "customer": customer,
        "amount_usd": amount_usd,
        "refunded": 0.0,
        "live": True,
    }
    log.info("stripe charge %s for $%.2f", intent["id"], amount_usd)
    return {
        "ok": intent.get("status") == "succeeded",
        "charge_id": intent["id"],
        "amount_usd": amount_usd,
        "status": intent.get("status"),
        "live": True,
    }


async def stripe_refund(charge_id: str = "", amount_usd: float = 0.0, **_: Any) -> dict:
    """A real test mode refund. Visible in the Stripe dashboard."""
    if not charge_id:
        return {"ok": False, "reason": "no charge id in the compensation contract"}

    refund = await _post(
        "refunds",
        {
            "payment_intent": charge_id,
            "amount": int(round(amount_usd * 100)) if amount_usd else None,
        },
    )

    record = WORLD["charges"].setdefault(
        charge_id, {"amount_usd": amount_usd, "refunded": 0.0, "live": True}
    )
    record["refunded"] = refund.get("amount", 0) / 100
    log.info("stripe refund %s for $%.2f", charge_id, record["refunded"])
    return {
        "ok": refund.get("status") in ("succeeded", "pending"),
        "charge_id": charge_id,
        "refunded_usd": record["refunded"],
        "refund_id": refund.get("id"),
        "status": refund.get("status"),
        "live": True,
    }


async def stripe_confirm_refund(charge_id: str = "", **_: Any) -> dict:
    """Ask Stripe, rather than believing the refund call.

    This is the reason Verifier exists. A refund API returning 200 means the
    request was accepted, not that the money moved, so the check reads the
    intent back and looks at what Stripe says was actually refunded.
    """
    if not charge_id:
        return {"confirmed": False}

    intent = await _get(f"payment_intents/{charge_id}")
    if "error" in intent:
        return {"confirmed": False, "reason": intent["error"].get("message", "")[:120]}

    charges = (intent.get("charges") or {}).get("data") or []
    refunded = any(c.get("refunded") for c in charges)
    amount_refunded = sum(c.get("amount_refunded", 0) for c in charges) / 100

    if not charges:
        # Newer API versions do not expand charges on the intent. Fall back to
        # listing refunds for it, which is the same question asked differently.
        refunds = await _get(f"refunds?payment_intent={charge_id}&limit=10")
        items = refunds.get("data") or []
        refunded = any(r.get("status") == "succeeded" for r in items)
        amount_refunded = sum(r.get("amount", 0) for r in items) / 100

    return {
        "confirmed": bool(refunded),
        "amount_refunded_usd": amount_refunded,
        "live": True,
    }


def install() -> bool:
    """Swap the in memory Stripe tools for these, when a test key is present."""
    try:
        if not enabled():
            log.info("no STRIPE_API_KEY, staying on the in memory stripe")
            return False
    except LiveKeyRefused as exc:
        log.error("%s", exc)
        raise

    _TOOLS["stripe_charge"] = stripe_charge
    _TOOLS["stripe_refund"] = stripe_refund
    _TOOLS["stripe_confirm_refund"] = stripe_confirm_refund
    log.info("stripe live test mode is on, in memory stripe replaced")
    return True
