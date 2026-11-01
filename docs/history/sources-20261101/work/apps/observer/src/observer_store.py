from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from observer_runtime import ObserverInputError


class ObserverStore:
    """Strictly read-only facade over Workflow-owned canonical SQLite."""

    def __init__(self, canonical_path: Path, *, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()
        if not (self.project_root / ".git").exists():
            raise ValueError("Observer store project root must be a Git project")
        self.path = Path(canonical_path).resolve()
        expected = (
            self.project_root / ".hermes" / "task-runtime" / "workflow" / "canonical.sqlite"
        ).resolve()
        if self.path != expected:
            raise ValueError("Observer must read the Workflow-owned canonical SQLite path")
        if not self.path.is_file():
            raise FileNotFoundError(f"canonical store missing: {self.path}")

    def rebuild_projection(self) -> dict[str, Any]:
        # R2 third batch: rebuild the v3 snapshot projection; the legacy v2
        # to_dashboard path is retired. Governance is enriched from the REAL
        # repo inventory so the projection never shows an empty pane.
        from canonical_store import CanonicalStore
        from composition_root import build_v3_snapshot, load_approved_index
        from observer_runtime import load_governance

        store = CanonicalStore(self.path, readonly=True)
        try:
            index = load_approved_index(store)
            projection = build_v3_snapshot(
                store,
                index,
                revision=store.seed_revision(),
                events_url=None,
                transport_state="UNKNOWN",
            )
            skills_dim, adapters_dim, rules_count = load_governance(self.project_root)
            projection["governance"] = {
                "rules": {"current": rules_count, "drift": None, "quarantined": None, "conflicts": None, "stale": None},
                "skills": skills_dim,
                "adapters": adapters_dim,
                "memoryContext": {"current": None, "drift": None, "quarantined": None, "conflicts": None, "stale": None},
            }
            return projection
        finally:
            store.close()

    def read_events(self) -> list[dict[str, Any]]:
        """Legacy event access is retired; canonical projections replace it."""
        return []

    def append(self, incoming: Iterable[dict[str, Any]]) -> int:
        raise ObserverInputError(
            "Observer is read-only: canonical writes belong to Workflow Assistance"
        )

    def close(self) -> None:
        """No persistent reader is held; nothing to close (canonical store is
        opened transiently by rebuild_projection)."""
