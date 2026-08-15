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
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from typing import Iterable, Optional

from ..config import settings
from ..types import ActionRecord, ActionState
from ..identity import GENESIS, entry_hash, verify_chain

log = logging.getLogger("palinode.ledger")

COLLECTION = "palinode_actions"
OUTCOMES = "palinode_outcomes"
CLAIMS = "palinode_claims"


class LedgerStore:
    """Firestore backed when a project is configured, in memory otherwise.

    The in memory path is not a toy. It is what the tests and the local demo
    run against, so it has to behave identically.
    """

    def __init__(self) -> None:
        self._mem: dict[str, ActionRecord] = {}
        self._outcomes: dict[str, dict] = {}
        self._tips: dict[str, str] = {}
        self._claims: dict[str, tuple] = {}
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

    def _demote(self, operation: str, exc: Exception) -> None:
        """Stop using Firestore for the rest of this process.

        A permission or quota failure will not fix itself between one call and
        the next, and a recovery tool that starts throwing 500s during an
        incident is worse than one running on the in memory copy. The write
        already landed in memory, so the ledger stays correct for this process
        and loud in the logs about what it lost.
        """
        log.error(
            "firestore %s failed, continuing in memory only: %s", operation, exc
        )
        self._client = None

    async def append(self, record: ActionRecord) -> ActionRecord:
        async with self._lock:
            # Chain it, unless it is already chained. append is also used to
            # rewrite a record whose contract was completed after execution,
            # and rehashing then would break every entry after it.
            if not record.entry_hash:
                record.prev_hash = self._tips.get(record.run_id, GENESIS)
                record.entry_hash = entry_hash(record, record.prev_hash)
                self._tips[record.run_id] = record.entry_hash
            self._mem[record.id] = record
        if self._client is not None:
            try:
                await self._client.collection(COLLECTION).document(record.id).set(
                    record.model_dump(mode="json")
                )
            except Exception as exc:  # noqa: BLE001
                self._demote("append", exc)
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
            try:
                await self._client.collection(COLLECTION).document(action_id).update(patch)
            except Exception as exc:  # noqa: BLE001
                self._demote("advance", exc)
        return record

    # ---------------------------------------------------------------- reads

    async def get(self, action_id: str) -> Optional[ActionRecord]:
        async with self._lock:
            cached = self._mem.get(action_id)
        if cached is not None or self._client is None:
            return cached

        try:
            snap = await self._client.collection(COLLECTION).document(action_id).get()
        except Exception as exc:  # noqa: BLE001
            self._demote("get", exc)
            return None
        if not snap.exists:
            return None
        record = ActionRecord.model_validate(snap.to_dict())
        async with self._lock:
            self._mem[action_id] = record
        return record

    async def by_run(self, run_id: str) -> list[ActionRecord]:
        if self._client is not None:
            try:
                from google.cloud.firestore_v1.base_query import FieldFilter

                query = self._client.collection(COLLECTION).where(
                    filter=FieldFilter("run_id", "==", run_id)
                )
                records = [
                    ActionRecord.model_validate(d.to_dict()) async for d in query.stream()
                ]
                async with self._lock:
                    for r in records:
                        self._mem.setdefault(r.id, r)
            except Exception as exc:  # noqa: BLE001
                self._demote("by_run", exc)
        async with self._lock:
            records = [r for r in self._mem.values() if r.run_id == run_id]
        return sorted(records, key=lambda r: r.created_at)

    async def open_runs(self, since) -> list[str]:
        """Runs that were never taken back, newest first.

        A run is open if anything in it is still executed or unrecoverable,
        which is to say nobody, and nothing, has undone it. These are what the
        Sweeper reassesses against whatever has been learned since.

        Filtered on state in the query and on date in Python. The pair would
        need a composite index in Firestore, and asking an operator to create
        one before the scheduled job will run is a good way to have a scheduled
        job that silently never runs.
        """
        alive = (ActionState.EXECUTED.value, ActionState.UNRECOVERABLE.value)

        if self._client is not None:
            try:
                from google.cloud.firestore_v1.base_query import FieldFilter

                query = self._client.collection(COLLECTION).where(
                    filter=FieldFilter("state", "in", list(alive))
                )
                records = [
                    ActionRecord.model_validate(d.to_dict()) async for d in query.stream()
                ]
                async with self._lock:
                    for r in records:
                        self._mem.setdefault(r.id, r)
            except Exception as exc:  # noqa: BLE001
                self._demote("open_runs", exc)

        async with self._lock:
            latest: dict[str, object] = {}
            for r in self._mem.values():
                if r.state.value not in alive or r.created_at < since:
                    continue
                if r.run_id not in latest or r.created_at > latest[r.run_id]:
                    latest[r.run_id] = r.created_at

        return [run for run, _ in sorted(latest.items(), key=lambda kv: kv[1], reverse=True)]

    async def claim(self, run_id: str, holder: str, *, ttl_seconds: int = 600) -> bool:
        """Take exclusive charge of reversing a run. False if someone else has it.

        Cloud Scheduler delivers at least once and Cloud Run answers from more
        than one container, so two sweeps can look at the same open run in the
        same second. Both of them found the same three week old fraud, both
        called Regret, and GitHub refused the second revert with 422 because
        the ref had moved underneath it. Stripe would not have refused. It
        would have refunded twice.

        A create that fails when the document already exists is the whole lock.
        Claims go stale so a container that dies mid reversal does not hold a
        run hostage forever.
        """
        now = datetime.now(timezone.utc)
        fresh = now - timedelta(seconds=ttl_seconds)

        if self._client is not None:
            doc = self._client.collection(CLAIMS).document(run_id)
            try:
                await doc.create({"holder": holder, "claimed_at": now.isoformat()})
                return True
            except Exception as exc:  # noqa: BLE001
                # AlreadyExists is the normal, expected answer here. Anything
                # else means Firestore is unwell, and the safe reading of an
                # unavailable lock is that we do not hold it.
                if "already exists" not in str(exc).lower():
                    log.error("claim on %s failed: %s", run_id, exc)
                    return False
                try:
                    snap = await doc.get()
                    held = snap.to_dict() or {}
                    when = datetime.fromisoformat(held.get("claimed_at", now.isoformat()))
                    if when > fresh:
                        log.info("run %s already claimed by %s", run_id, held.get("holder"))
                        return False
                    await doc.set({"holder": holder, "claimed_at": now.isoformat()})
                    log.warning("took over a stale claim on %s", run_id)
                    return True
                except Exception as inner:  # noqa: BLE001
                    log.error("stale claim check on %s failed: %s", run_id, inner)
                    return False

        async with self._lock:
            held = self._claims.get(run_id)
            if held is not None and held[1] > fresh:
                return False
            self._claims[run_id] = (holder, now)
            return True

    async def release(self, run_id: str) -> None:
        """Give the claim back. Best effort: the ttl covers the rest."""
        async with self._lock:
            self._claims.pop(run_id, None)
        if self._client is not None:
            try:
                await self._client.collection(CLAIMS).document(run_id).delete()
            except Exception as exc:  # noqa: BLE001
                log.warning("release of %s failed, ttl will clear it: %s", run_id, exc)

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

    # --------------------------------------------------------- run outcomes

    async def save_outcome(self, run_id: str, outcome: dict) -> None:
        """Persist what a reversal did.

        This lived in a module global until Cloud Run scaled past one instance
        and the dashboard started asking a container that had never heard of
        the reversal. Recovery results are exactly the thing that has to
        outlive the process that produced them.
        """
        async with self._lock:
            self._outcomes[run_id] = outcome
        if self._client is not None:
            try:
                await self._client.collection(OUTCOMES).document(run_id).set(outcome)
            except Exception as exc:  # noqa: BLE001
                self._demote("save_outcome", exc)

    async def get_outcome(self, run_id: str) -> Optional[dict]:
        async with self._lock:
            cached = self._outcomes.get(run_id)
        if cached is not None or self._client is None:
            return cached

        try:
            snap = await self._client.collection(OUTCOMES).document(run_id).get()
        except Exception as exc:  # noqa: BLE001
            self._demote("get_outcome", exc)
            return None
        if not snap.exists:
            return None
        outcome = snap.to_dict()
        async with self._lock:
            self._outcomes[run_id] = outcome
        return outcome

    async def verify(self, run_id: str):
        """Recompute the hash chain for a run and say where it breaks."""
        return verify_chain(await self.by_run(run_id))

    async def clear_run(self, run_id: str) -> int:
        """Delete a run outright. Only the demo reset uses this.

        The ledger is append only for everything that matters, and this is the
        one door out of that, kept narrow on purpose. Without it a second demo
        run reads back ten actions instead of five, because the first run is
        still sitting in Firestore.
        """
        async with self._lock:
            doomed = [rid for rid, r in self._mem.items() if r.run_id == run_id]
            for rid in doomed:
                self._mem.pop(rid, None)
            self._tips.pop(run_id, None)

        if self._client is None:
            return len(doomed)

        try:
            from google.cloud.firestore_v1.base_query import FieldFilter

            query = self._client.collection(COLLECTION).where(
                filter=FieldFilter("run_id", "==", run_id)
            )
            removed = 0
            async for doc in query.stream():
                await doc.reference.delete()
                removed += 1
            return max(removed, len(doomed))
        except Exception as exc:  # noqa: BLE001
            self._demote("clear_run", exc)
            return len(doomed)

    async def clear_outcome(self, run_id: str) -> None:
        async with self._lock:
            self._outcomes.pop(run_id, None)
        if self._client is not None:
            try:
                await self._client.collection(OUTCOMES).document(run_id).delete()
            except Exception as exc:  # noqa: BLE001
                self._demote("clear_outcome", exc)

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
