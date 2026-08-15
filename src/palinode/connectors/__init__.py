import logging as _logging
import os as _os

from .base import WORLD, registered, reset_world, run_tool, tool

_log = _logging.getLogger("palinode.connectors")

# Whether this process is allowed to touch anything real.
#
# The hosted demo is public, because judges have to be able to use it, and for
# a while that meant an anonymous request to /undo or /demo/seed could move
# money in a Stripe account, push a commit and post in a Slack channel. Rate
# limiting is not authorisation. A reviewer put it plainly: do not let the
# judge facing URL be the one wired to the real systems.
#
# So the deployment carries PALINODE_PUBLIC_DEMO=1 and the live connectors are
# not installed at all. Everything still works, end to end, against the in
# memory world. The evidence that the real integration exists lives where it
# should: in the recorded film, in the console captures, and in the Stripe,
# GitHub and Slack histories those captures came from.
#
# Unset the flag to run against the real systems, which is what the capture
# session does.
PUBLIC_DEMO = _os.getenv("PALINODE_PUBLIC_DEMO", "").strip().lower() in {"1", "true", "yes"}

_LIVE = []
_CANDIDATES = () if PUBLIC_DEMO else ("stripe_live", "github_live", "slack_live")
if PUBLIC_DEMO:
    _log.warning(
        "public demo mode: live connectors are not installed, nothing real can be touched"
    )

for _name in _CANDIDATES:
    try:
        _module = __import__(f"palinode.connectors.{_name}", fromlist=[_name])
        if _module.install():
            _LIVE.append(_name.replace("_live", ""))
    except Exception as exc:  # noqa: BLE001
        _log.error("%s not installed: %s", _name, exc)


def live_connectors() -> list[str]:
    """Which systems of record are real in this process."""
    return list(_LIVE)


__all__ = [
    "PUBLIC_DEMO",
    "WORLD",
    "registered",
    "reset_world",
    "run_tool",
    "tool",
    "live_connectors",
]
