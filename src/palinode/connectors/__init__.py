from .base import WORLD, registered, reset_world, run_tool, tool

# Registered last on purpose. Each of these replaces the in memory tools of the
# same name when its credentials are present, and leaves them alone when they
# are not. Nothing else in the system is told which one it is talking to.
_LIVE = []
for _name in ("stripe_live", "github_live", "slack_live"):
    try:
        _module = __import__(f"palinode.connectors.{_name}", fromlist=[_name])
        if _module.install():
            _LIVE.append(_name.replace("_live", ""))
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger("palinode.connectors").error("%s not installed: %s", _name, exc)


def live_connectors() -> list[str]:
    """Which systems of record are real in this process."""
    return list(_LIVE)


__all__ = [
    "WORLD",
    "registered",
    "reset_world",
    "run_tool",
    "tool",
    "live_connectors",
]
