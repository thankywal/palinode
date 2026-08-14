"""A rate limit on the endpoints that cost money.

The service is public because judges have to be able to use it, and a public
endpoint that calls Gemini and Model Armor on every request is a way to donate
an inference budget to whoever finds it first.

This is deliberately small. Not a quota system, not Redis, not per user. One
counter per caller per minute, in the process, on the handful of routes that
reach a paid API. Cloud Run runs at most three containers here, so the true
ceiling is three times this, which is the right order of magnitude for a demo
and cheap enough to be worth having.

Reads stay unlimited. The dashboard polls several times a second and none of
those calls costs anything.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("palinode.limits")

WINDOW_SECONDS = 60
MAX_PER_WINDOW = 20

# Routes that reach Gemini, Model Armor or Stripe. Everything else is free to
# call as often as anyone likes.
COSTLY = (
    "/demo/screen",
    "/demo/seed",
    "/demo/cold-case",
    "/undo",
    "/sentinel",
)

_hits: dict[str, deque[float]] = defaultdict(deque)


def _caller(request: Request) -> str:
    # Cloud Run puts the real client first in X-Forwarded-For. Falling back to
    # the socket address would otherwise bucket every caller behind the load
    # balancer into one, which is worse than no limit at all.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_costly(path: str, method: str) -> bool:
    if method == "GET":
        return False
    return any(path.startswith(prefix) for prefix in COSTLY)


async def throttle(request: Request, call_next):
    if not _is_costly(request.url.path, request.method):
        return await call_next(request)

    caller = _caller(request)
    now = time.monotonic()
    seen = _hits[caller]

    while seen and now - seen[0] > WINDOW_SECONDS:
        seen.popleft()

    if len(seen) >= MAX_PER_WINDOW:
        retry_in = int(WINDOW_SECONDS - (now - seen[0])) + 1
        log.warning("throttled %s on %s", caller, request.url.path)
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_in)},
            content={
                "detail": (
                    "This endpoint calls a paid model on every request, so it "
                    f"is limited to {MAX_PER_WINDOW} calls a minute."
                ),
                "retry_after_seconds": retry_in,
            },
        )

    seen.append(now)

    # Unbounded growth is the obvious way for a rate limiter to become the
    # outage. Anything with no hits left in the window is dropped.
    if len(_hits) > 2000:
        for key in [k for k, v in _hits.items() if not v]:
            del _hits[key]

    return await call_next(request)
