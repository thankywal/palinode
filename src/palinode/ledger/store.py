"""The causality ledger.

This is a graph, not a log. A log tells you what happened. A graph tells you
what else has to be undone before the thing you actually care about can be.

Append only by construction: records are written once and then only their state
field is advanced. Nothing is ever deleted, including failed reversals, because
the audit trail of a botched recovery matters more than a clean one.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from typing import Iterable, Optional

from ..config import settings
from ..types import ActionRecord, ActionState

log = logging.getLogger("palinode.ledger")

COLLECTION = "palinode_actions"


class LedgerStore:
    """Firestore backed when a project is configured, in memory otherwise.

    The in memory path is not a toy. It is what the tests and the local demo
    run against, so it has to behave identically.
    """

    def __init__(self) -> None:
        self._mem: dict[str, ActionRecord] = {}
        self._lock = asyncio.Lock()
        self._client = None

        if settings.use_firestore:
            try:
                from google.cloud import firestore  # imported lazily on purpose

                self._client = firestore.AsyncClient(
                    project=settings.project,
                    database=settings.firestore_database,
                )
                log.info("ledger backed by firestore project=%s", settings.project)
            except Exception as exc:  # noqa: BLE001
                log.warning("firestore unavailable, falling back to memory: %s", exc)
                self._client = None
        else:
            log.info("ledger running in memory, set GOOGLE_CLOUD_PROJECT to persist")

    # ---------------------------------------------------------------- writes

    async def append(self, record: ActionRecord) -> ActionRecord:
        async with self._lock:
            self._mem[record.id] = record
        if self._client is not None:
            await self._client.collection(COLLECTION).document(record.id).set(
                record.model_dump(mode="json")
            )
        return record

    async def advance(
        self,
        action_id: str,
        state: ActionState,
        *,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> Optional[ActionRecord]:
        """Move an action to a new state. The only mutation this store allows."""
        async with self._lock:
            record = self._mem.get(action_id)
            if record is None:
                return None
            record.state = state
            if result is not None:
                record.result = result
            if error is not None:
                record.error = error

        if self._client is not None:
            patch = {"state": state.value}
            if result is not None:
                patch["result"] = result
            if error is not None:
                patch["error"] = error
            await self._client.collection(COLLECTION).document(action_id).update(patch)
        return record

    # ---------------------------------------------------------------- reads

    async def get(self, action_id: str) -> Optional[ActionRecord]:
        async with self._lock:
            cached = self._mem.get(action_id)
        if cached is not None or self._client is None:
            return cached

        snap = await self._client.collection(COLLECTION).document(action_id).get()
        if not snap.exists:
            return None
        record = ActionRecord.model_validate(snap.to_dict())
        async with self._lock:
            self._mem[action_id] = record
        return record

    async def by_run(self, run_id: str) -> list[ActionRecord]:
        if self._client is not None:
            query = self._client.collection(COLLECTION).where("run_id", "==", run_id)
            records = [ActionRecord.model_validate(d.to_dict()) async for d in query.stream()]
            async with self._lock:
                for r in records:
                    self._mem.setdefault(r.id, r)
        async with self._lock:
            records = [r for r in self._mem.values() if r.run_id == run_id]
        return sorted(records, key=lambda r: r.created_at)

    async def spend_since(self, agent: str, cutoff) -> float:
        """Unrecoverable exposure an agent has run up since a point in time."""
        async with self._lock:
            return sum(
                r.cost()
                for r in self._mem.values()
                if r.agent == agent
                and r.created_at >= cutoff
                and r.state
                in (ActionState.EXECUTED, ActionState.UNRECOVERABLE, ActionState.COMPENSATED)
            )

    # ------------------------------------------------------------ the graph

    async def blast_radius(self, action_id: str) -> list[ActionRecord]:
        """Everything downstream of an action, including the action itself.

        An email goes out, someone replies, the reply updates the CRM, the CRM
        raises an invoice. Undoing the email means undoing four things. This
        walks that closure so Regret never reverses half a story.
        """
        record = await self.get(action_id)
        if record is None:
            return []

        run = await self.by_run(record.run_id)
        children: dict[str, list[ActionRecord]] = defaultdict(list)
        for candidate in run:
            for parent in candidate.caused_by:
                children[parent].append(candidate)

        seen: set[str] = {action_id}
        ordered: list[ActionRecord] = [record]
        queue: deque[str] = deque([action_id])

        while queue:
            for child in children.get(queue.popleft(), []):
                if child.id in seen:
                    continue
                seen.add(child.id)
                ordered.append(child)
                queue.append(child.id)

        return ordered

    async def reverse_order(self, actions: Iterable[ActionRecord]) -> list[ActionRecord]:
        """Newest effects first, so nothing is undone before its consequences.

        Falls back to execution time where the declared graph is incomplete,
        which it will be until causal inference stops being on the roadmap.
        """
        return sorted(
            actions,
            key=lambda r: (r.executed_at or r.created_at),
            reverse=True,
        )


_store: Optional[LedgerStore] = None


def get_ledger() -> LedgerStore:
    global _store
    if _store is None:
        _store = LedgerStore()
    return _store
