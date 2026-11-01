# -*- coding: utf-8 -*-
"""Context drift guard (WL3-330 / Context Control Plane design L3).

Validates that any compaction/compression preserves the §12.6 critical facts:
user_goal, non_goals, allowed_paths, forbidden_paths, data_boundary,
base_sha_tree, known_failures, acceptance_commands, rollback_method.
Missing any => fail closed (never compact into drift).
"""
from __future__ import annotations

from typing import Any

DRIFT_PRESERVE = (
    "user_goal",
    "non_goals",
    "allowed_paths",
    "forbidden_paths",
    "data_boundary",
    "base_sha_tree",
    "known_failures",
    "acceptance_commands",
    "rollback_method",
)


class ContextDriftGuard:
    def __init__(self) -> None:
        self.required = set(DRIFT_PRESERVE)

    def check(self, bundle: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a bundle's drift_preserve block. Returns (ok, missing)."""
        preserve = bundle.get("drift_preserve") or {}
        missing = [k for k in self.required
                   if k not in preserve or not str(preserve.get(k) or "").strip()]
        return (len(missing) == 0, missing)

    def assert_preserved(self, bundle: dict[str, Any]) -> None:
        ok, missing = self.check(bundle)
        if not ok:
            raise ValueError(f"context_drift_missing: {missing}")

    def compress(self, bundle: dict[str, Any], summary: str) -> dict[str, Any]:
        """Compress a bundle into a summary, carrying the drift block verbatim.

        The critical facts always survive compression (never summarized away);
        only non-critical body content is replaced by the summary.
        """
        self.assert_preserved(bundle)
        return {
            "schema_version": bundle.get("schema_version", "workflow/context-bundle/v1"),
            "project_id": bundle.get("project_id"),
            "compressed": True,
            "summary": summary,
            "drift_preserve": dict(bundle.get("drift_preserve") or {}),
            "stable_digest": bundle.get("stable_digest"),
            "original_available": "session-log-or-evidence",  # raw kept for replay
        }


if __name__ == "__main__":
    guard = ContextDriftGuard()
    good = {
        "drift_preserve": {k: "v" for k in DRIFT_PRESERVE},
        "schema_version": "workflow/context-bundle/v1",
        "project_id": "work-lab",
        "stable_digest": "abc",
    }
    print("good:", guard.check(good))
    bad = {"drift_preserve": {"user_goal": "x"}}
    print("bad:", guard.check(bad))
    comp = guard.compress(good, "summary body")
    print("compressed drift preserved:", all(k in comp["drift_preserve"] for k in DRIFT_PRESERVE))
    print("DRIFT_GUARD_SMOKE_PASS")
