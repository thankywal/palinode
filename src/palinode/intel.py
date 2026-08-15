"""What we found out afterwards.

Sentinel reads the shape of a run at the moment it happens, and at that moment
the only alarming shape is an irreversible action where there should not be
one. That catches the poisoned invoice. It cannot catch the other case, which
is more common and slower: every action was ordinary, nothing was irreversible,
and three weeks later the vendor turns out to be fraudulent.

Nothing about the run changed. What changed is what we know.

So this is the store for facts that arrive late. A counterparty lands here when
a bank, a deny list or a person marks it, and from then on every run that ever
paid it is suspect, whatever it looked like at the time. The Sweeper reads this
on a schedule and reassesses history against it.

Firestore backed for the same reason the ledger is: an intelligence store that
does not outlive the process cannot answer a question about three weeks ago.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .config import settings

log = logging.getLogger("palinode.intel")

COLLECTION = "palinode_intel"


class Intel:
    """Counterparties later found to be bad, and when we found out."""

    def __init__(self) -> None:
        self._mem: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._client = None
        self._loaded = False

        if settings.use_firestore:
            try:
                from google.cloud import firestore  # imported lazily on purpose

                self._client = firestore.AsyncClient(
                    project=settings.project,
                    database=settings.firestore_database,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("firestore unavailable for intel: %s", exc)
                self._client = None

    async def _load(self) -> None:
        """Pull the whole store once per process. It is a small set."""
        if self._loaded or self._client is None:
            self._loaded = True
            return
        try:
            async for doc in self._client.collection(COLLECTION).stream():
                self._mem.setdefault(doc.id, doc.to_dict())
        except Exception as exc:  # noqa: BLE001
            # Same rule as the ledger. A recovery tool that throws during an
            # incident is worse than one working from what it already has.
            log.error("intel unavailable, continuing without it: %s", exc)
            self._client = None
        self._loaded = True

    async def flag(self, party: str, source: str, note: str = "") -> dict:
        """Record that a counterparty is now known to be bad."""
        entry = {
            "party": party,
            "source": source,
            "note": note,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
        }
        async with self._lock:
            self._mem[party] = entry
        if self._client is not None:
            try:
                await self._client.collection(COLLECTION).document(party).set(entry)
            except Exception as exc:  # noqa: BLE001
                log.error("intel write failed for %s: %s", party, exc)
        log.warning("counterparty flagged: %s via %s", party, source)
        return entry

    async def get(self, party: str) -> Optional[dict]:
        await self._load()
        async with self._lock:
            return self._mem.get(party)

    async def all(self) -> list[dict]:
        await self._load()
        async with self._lock:
            return sorted(self._mem.values(), key=lambda e: e["flagged_at"])

    async def clear(self, party: str) -> None:
        async with self._lock:
            self._mem.pop(party, None)
        if self._client is not None:
            try:
                await self._client.collection(COLLECTION).document(party).delete()
            except Exception as exc:  # noqa: BLE001
                log.error("intel delete failed for %s: %s", party, exc)


_intel: Optional[Intel] = None


def get_intel() -> Intel:
    global _intel
    if _intel is None:
        _intel = Intel()
    return _intel


def reset_intel() -> None:
    """Tests and the demo reset. Drops the process copy, not Firestore."""
    global _intel
    _intel = None
