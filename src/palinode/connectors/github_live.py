"""GitHub, for real.

The demo merges a pull request and then reverts it. Both are ordinary git
operations with an obvious inverse, which makes this the cleanest possible
example of a T1 action: the effect is undoable through an API, and the undo
leaves a record rather than pretending nothing happened.

That last part matters and is the reason a revert is T1 and not T0. Reverting a
merge does not remove it from history. It adds a commit that undoes it. Anyone
reading the log can see both, which is the correct outcome and also the honest
one.

Needs a fine grained token scoped to one throwaway repository. Without one the
in memory connector stays and the demo runs as before.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .base import WORLD, _TOOLS

log = logging.getLogger("palinode.github")

API = "https://api.github.com"


def _token() -> Optional[str]:
    return (os.getenv("GITHUB_TOKEN") or "").strip() or None


def _repo() -> str:
    return (os.getenv("GITHUB_DEMO_REPO") or "").strip()


def enabled() -> bool:
    return bool(_token() and _repo())


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _request(method: str, path: str, **kwargs) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.request(
            method, f"{API}{path}", headers=_headers(), **kwargs
        )
    if response.status_code == 204:
        return {}
    payload = response.json()
    if response.status_code >= 400:
        raise RuntimeError(
            f"github {method} {path} failed: "
            f"{payload.get('message', response.text[:160])}"
        )
    return payload


async def github_merge(repo: str = "", pr: int = 0, **_: Any) -> dict:
    """Commit straight to the demo branch, which is the merge we then revert.

    Opening a pull request first would be more faithful and would also mean the
    demo depends on a branch existing in a particular state. The thing being
    demonstrated is the reversal, not the review flow.
    """
    target = _repo()
    branch = os.getenv("GITHUB_DEMO_BRANCH", "main")

    ref = await _request("GET", f"/repos/{target}/git/ref/heads/{branch}")
    parent = ref["object"]["sha"]

    base = await _request("GET", f"/repos/{target}/git/commits/{parent}")
    blob = await _request(
        "POST",
        f"/repos/{target}/git/blobs",
        json={"content": f"vendor v-8842 approved by palinode, pr {pr}\n", "encoding": "utf-8"},
    )
    tree = await _request(
        "POST",
        f"/repos/{target}/git/trees",
        json={
            "base_tree": base["tree"]["sha"],
            "tree": [
                {"path": "vendors.txt", "mode": "100644", "type": "blob", "sha": blob["sha"]}
            ],
        },
    )
    commit = await _request(
        "POST",
        f"/repos/{target}/git/commits",
        json={
            "message": f"approve vendor config, pr {pr}",
            "tree": tree["sha"],
            "parents": [parent],
        },
    )
    await _request(
        "PATCH",
        f"/repos/{target}/git/refs/heads/{branch}",
        json={"sha": commit["sha"]},
    )

    WORLD["merges"][commit["sha"]] = {
        "repo": target,
        "pr": pr,
        "reverted": False,
        "parent": parent,
        "live": True,
    }
    log.info("github commit %s on %s", commit["sha"][:12], target)
    return {
        "ok": True,
        "repo": target,
        "pr": pr,
        "merge_sha": commit["sha"],
        "url": f"https://github.com/{target}/commit/{commit['sha']}",
        "live": True,
    }


async def github_revert(repo: str = "", merge_sha: str = "", **_: Any) -> dict:
    """Add a commit that undoes the last one. History keeps both."""
    target = _repo()
    branch = os.getenv("GITHUB_DEMO_BRANCH", "main")

    if not merge_sha:
        return {"ok": False, "reason": "no merge sha in the compensation contract"}

    known = WORLD["merges"].get(merge_sha, {})
    parent = known.get("parent")

    if not parent:
        commit = await _request("GET", f"/repos/{target}/git/commits/{merge_sha}")
        parents = commit.get("parents") or []
        if not parents:
            return {"ok": False, "reason": "commit has no parent to restore"}
        parent = parents[0]["sha"]

    # A new commit whose tree is the state before, rather than moving the
    # branch back. Rewriting the branch would erase the evidence that any of
    # this happened, and an append only ledger sitting on top of a rewritten
    # history would be worth nothing.
    before = await _request("GET", f"/repos/{target}/git/commits/{parent}")
    head = await _request("GET", f"/repos/{target}/git/ref/heads/{branch}")
    revert = await _request(
        "POST",
        f"/repos/{target}/git/commits",
        json={
            "message": f"revert {merge_sha[:12]}, reversed by palinode",
            "tree": before["tree"]["sha"],
            "parents": [head["object"]["sha"]],
        },
    )
    await _request(
        "PATCH",
        f"/repos/{target}/git/refs/heads/{branch}",
        json={"sha": revert["sha"]},
    )

    WORLD["merges"].setdefault(merge_sha, {})["reverted"] = True
    log.info("github revert %s on %s", revert["sha"][:12], target)
    return {
        "ok": True,
        "revert_of": merge_sha,
        "revert_sha": revert["sha"],
        "url": f"https://github.com/{target}/commit/{revert['sha']}",
        "live": True,
    }


def install() -> bool:
    if not enabled():
        log.info("no GITHUB_TOKEN and GITHUB_DEMO_REPO, staying on the in memory github")
        return False

    _TOOLS["github_merge"] = github_merge
    _TOOLS["github_revert"] = github_revert
    log.info("github live is on for %s", _repo())
    return True
