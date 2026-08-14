"""Configuration, all of it from the environment.

Nothing here should need editing to run locally. Without GOOGLE_CLOUD_PROJECT
set, the ledger falls back to an in memory store so the demo runs on a laptop.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # Models. The classifier sits inline in front of every tool call in the
    # fleet, so it has a latency budget of roughly 80ms. That budget is the
    # reason it is Flash and not Pro.
    classifier_model: str = field(
        default_factory=lambda: os.getenv("PALINODE_CLASSIFIER_MODEL", "gemini-3.5-flash")
    )
    planner_model: str = field(
        default_factory=lambda: os.getenv("PALINODE_PLANNER_MODEL", "gemini-3.5-flash")
    )
    # Regulated tenants run the classifier inside their own VPC instead.
    sovereign_model: str = field(
        default_factory=lambda: os.getenv("PALINODE_SOVEREIGN_MODEL", "gemma-3-12b-it")
    )
    sovereign_mode: bool = field(default_factory=lambda: _flag("PALINODE_SOVEREIGN_MODE"))

    project: str = field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    location: str = field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"))
    firestore_database: str = field(
        default_factory=lambda: os.getenv("PALINODE_FIRESTORE_DB", "(default)")
    )

    # How long T2 and T3 actions sit in the queue before they reach the world.
    # Anything caught inside this window is a true undo rather than a
    # compensation, which is the difference between a deleted email and an
    # apology for one.
    cooling_off_seconds: int = field(
        default_factory=lambda: int(os.getenv("PALINODE_COOLING_OFF_SECONDS", "30"))
    )

    # An agent may accumulate this much unrecoverable exposure per hour before
    # the Warden drops it to propose only.
    default_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("PALINODE_DEFAULT_BUDGET_USD", "500"))
    )

    # Refuse any action whose author did not say how to take it back.
    require_contract: bool = field(default_factory=lambda: _flag("PALINODE_REQUIRE_CONTRACT", True))

    @property
    def use_firestore(self) -> bool:
        return bool(self.project) and not _flag("PALINODE_FORCE_MEMORY")

    @property
    def classifier(self) -> str:
        return self.sovereign_model if self.sovereign_mode else self.classifier_model


settings = Settings()
