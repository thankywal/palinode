"""Who acted, and proof that the record of it has not been edited since.

Google's Agent Identity assigns every agent a cryptographic id on the SPIFFE
standard and describes the result as non-repudiable auditing of every agent
action. That product is the right place for this to come from, and when it is
reachable Palinode should take the id from there rather than mint its own.

Until then this issues ids in the same SPIFFE URI shape, so the ledger records
a principal rather than a display name, and swapping the issuer later does not
change the schema.

The second half is the part that makes the first half worth anything. An id on
a record only means something if the record cannot be quietly edited after the
fact, so entries are hash chained per run. Each entry commits to the one before
it. Changing an old action, or removing one, breaks every hash after it and
`verify_chain` says exactly where.

Lives at the package root rather than under warden/ because the ledger needs
it too, and a module both of them import cannot sit inside either.

This is not a blockchain and does not pretend to be. It is a Merkle style chain
that makes tampering detectable by anyone holding the ledger, which is what an
auditor asking "was this edited after the incident" actually needs.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

log = logging.getLogger("palinode.identity")

TRUST_DOMAIN = "palinode"
GENESIS = "0" * 64


def workload_id(project: str, owner: str, name: str) -> str:
    """A SPIFFE shaped id for an agent.

    spiffe://palinode/<project>/<owner>/<agent>

    Same shape Agent Identity issues, so the ledger schema does not change when
    the issuer does.
    """
    parts = [p.strip("/") for p in (project or "local", owner or "unowned", name) if p]
    return f"spiffe://{TRUST_DOMAIN}/" + "/".join(parts)


def _canonical(payload: dict) -> bytes:
    """Stable bytes for hashing.

    Sorted keys and no whitespace, so the same record hashes the same way on
    any machine and in any Python version. A hash chain that depends on dict
    ordering is a hash chain that fails the first time it matters.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


def entry_hash(record, prev_hash: str) -> str:
    """Commit to the parts of an action that must not change after the fact.

    Deliberately not the whole record. State advances legitimately as an action
    is executed and then reversed, and chaining over a mutable field would mean
    every normal state change looked like tampering. What is committed to is
    what the action was and what it promised about undoing itself.
    """
    payload = {
        "id": record.id,
        "run_id": record.run_id,
        "actor": getattr(record, "actor", "") or "",
        "agent": record.agent,
        "tool": record.tool,
        "args": record.args,
        "tier": record.tier.value,
        "caused_by": record.caused_by,
        "contract": record.contract.model_dump(mode="json") if record.contract else None,
        "created_at": record.created_at.isoformat(),
        "prev": prev_hash,
    }
    return hashlib.sha256(_canonical(payload)).hexdigest()


@dataclass
class ChainReport:
    intact: bool
    length: int
    broken_at: Optional[str] = None
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "intact": self.intact,
            "length": self.length,
            "broken_at": self.broken_at,
            "reason": self.reason,
        }


def verify_chain(records: Iterable) -> ChainReport:
    """Recompute the chain and report the first entry that does not match."""
    ordered = sorted(records, key=lambda r: r.created_at)
    prev = GENESIS
    count = 0

    for record in ordered:
        count += 1
        recorded = getattr(record, "entry_hash", "") or ""
        if not recorded:
            return ChainReport(
                intact=False,
                length=count,
                broken_at=record.id,
                reason="entry was never hashed, so nothing commits to it",
            )

        if getattr(record, "prev_hash", "") != prev:
            return ChainReport(
                intact=False,
                length=count,
                broken_at=record.id,
                reason="entry does not follow the one before it, an action was removed or reordered",
            )

        expected = entry_hash(record, prev)
        if expected != recorded:
            return ChainReport(
                intact=False,
                length=count,
                broken_at=record.id,
                reason="entry contents changed after it was written",
            )

        prev = recorded

    return ChainReport(intact=True, length=count, reason="every entry commits to the one before it")
