"""Slack, for real.

This is the T2 connector, and T2 is the tier the whole project argues about.

`chat.delete` works. The message disappears. But the people in the channel
already read it, and deleting it does not unsend the notification that went to
their phone. So a Slack post is not reversible, it is compensable: delete the
original and post a correction that says what happened.

Palinode does both, and records the outcome as compensated rather than
reversed, because those are different things and the difference is the point.

Needs a bot token with chat:write and a channel it has been invited to.
Without one the in memory connector stays.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .base import WORLD, _TOOLS

log = logging.getLogger("palinode.slack")

API = "https://slack.com/api"


def _token() -> Optional[str]:
    raw = (os.getenv("SLACK_BOT_TOKEN") or "").strip()
    return raw or None


def _channel(fallback: str = "") -> str:
    return (os.getenv("SLACK_DEMO_CHANNEL") or fallback or "").strip()


def enabled() -> bool:
    return bool(_token() and _channel())


async def _call(method: str, payload: dict) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{API}/{method}",
            headers={"Authorization": f"Bearer {_token()}"},
            json=payload,
        )
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"slack {method} failed: {body.get('error', 'unknown')}")
    return body


async def slack_post(channel: str = "", text: str = "", **_: Any) -> dict:
    target = _channel(channel)
    body = await _call("chat.postMessage", {"channel": target, "text": text})

    WORLD["slack"][body["ts"]] = {"channel": target, "text": text, "live": True}
    log.info("slack post %s in %s", body["ts"], target)
    return {"ok": True, "ts": body["ts"], "channel": target, "live": True}


async def slack_delete(channel: str = "", ts: str = "", **_: Any) -> dict:
    """Delete the message, then say why it was deleted.

    Deleting alone would leave everyone who read it believing something that is
    no longer true, which is the failure mode this tier exists to name.
    """
    target = _channel(channel)
    if not ts:
        return {"ok": False, "reason": "no message ts in the compensation contract"}

    await _call("chat.delete", {"channel": target, "ts": ts})

    correction = await _call(
        "chat.postMessage",
        {
            "channel": target,
            "text": (
                ":warning: The previous message in this channel was posted by an "
                "automated agent acting on a manipulated invoice and has been "
                "removed. No approval from this channel was valid. Palinode "
                "reversed the run."
            ),
        },
    )

    WORLD["slack"].pop(ts, None)
    log.info("slack deleted %s and posted a correction in %s", ts, target)
    return {
        "ok": True,
        "deleted": ts,
        "correction_ts": correction["ts"],
        "compensated": True,
        "live": True,
    }


async def channels() -> dict:
    """Which channels can this bot actually post to?

    Setup diagnostic. Installing a Slack app and inviting the bot to a channel
    are two different steps and the second is easy to skip, at which point
    every post fails with not_in_channel and nothing says why.
    """
    if not _token():
        return {"ok": False, "reason": "no SLACK_BOT_TOKEN"}

    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{API}/conversations.list",
            headers={"Authorization": f"Bearer {_token()}"},
            params={"types": "public_channel,private_channel", "limit": 200},
        )
    body = response.json()
    if not body.get("ok"):
        return {"ok": False, "reason": body.get("error", "unknown")}

    joined = [
        {"name": f"#{c['name']}", "id": c["id"]}
        for c in body.get("channels", [])
        if c.get("is_member")
    ]
    return {
        "ok": True,
        "bot_is_in": joined,
        "configured": _channel() or None,
        "hint": (
            "Invite the bot with /invite @palinode in the channel you want"
            if not joined
            else "Set SLACK_DEMO_CHANNEL to one of these"
        ),
    }


def install() -> bool:
    if not enabled():
        log.info("no SLACK_BOT_TOKEN and SLACK_DEMO_CHANNEL, staying on the in memory slack")
        return False

    _TOOLS["slack_post"] = slack_post
    _TOOLS["slack_delete"] = slack_delete
    log.info("slack live is on for %s", _channel())
    return True
