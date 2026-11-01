# -*- coding: utf-8 -*-
"""Context Control Plane orchestration (WL3-330 / Context Control Plane design).

Given a task, produce: canonical stable prefix + cache-hit expectation +
compaction decision + per-client adaptation suggestion. Consumes the upgraded
ContextBundle (L1) and model_usage_mapper (L2) truth values; never writes
prompt/response bodies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from context_bundle import ContextBundle, DRIFT_PRESERVE
from model_usage_mapper import map_usage

SCHEMA_VERSION = "workflow/context-control-plane/v1"

# Client adaptation surface (§design L4). CC Switch/GitHub/OpenHuman/Open
# Design have no context mechanism -> OBSERVE only.
CLIENT_ADAPTATION = {
    "dsh": {"mechanism": "compaction-basic + tool-result-pruner", "action": "tune thresholdRatio/retainRatio"},
    "hermes": {"mechanism": "context_compressor + protect_first_n", "action": "set protect_first_n"},
    "codex": {"mechanism": "auto-compact + prompt caching", "action": "align static prefix"},
    "cc-switch": {"mechanism": "none", "action": "observe-only"},
    "github": {"mechanism": "none", "action": "observe-only"},
    "openhuman": {"mechanism": "none", "action": "observe-only"},
    "open-design": {"mechanism": "none", "action": "observe-only"},
}


class ContextControlPlane:
    def __init__(self, project_id: str, rules_revision: str,
                 global_rules_revision: str = "global-1") -> None:
        self.bundle = ContextBundle(project_id, rules_revision, global_rules_revision)

    def assemble(self, task: dict[str, Any], blocks: dict[str, str],
                 preserve: dict[str, str], base_tree: str | None = None,
                 data_classification: str = "public") -> dict[str, Any]:
        """Build canonical bundle + decision for one task."""
        boundary = task.get("boundary", "")
        acceptance = task.get("acceptance", "")
        bundle = self.bundle.build(
            blocks, boundary, acceptance,
            base_tree=base_tree,
            evidence_selectors=task.get("evidence_selectors"),
            data_classification=data_classification,
            preserve=preserve,
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "task_id": task.get("task_id", "unknown"),
            "bundle": bundle,
            "decision": self._decision(bundle),
            "client_adaptation": self._client_adaptation(task.get("clients", ["dsh"])),
        }

    def _decision(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Compaction decision: full history vs summarized vs pruned."""
        # Token estimate unavailable -> conservative "full-until-pressure".
        return {
            "mode": "stable-prefix-full",
            "token_estimate_source": bundle.get("token_estimate_source", "unavailable"),
            "cache_strategy": "static-prefix-first",
            "compaction": "deferred-until-pressure",
            "drift_guard": "all-preserved",
        }

    def _client_adaptation(self, clients: list[str]) -> dict[str, Any]:
        return {c: CLIENT_ADAPTATION.get(c, {"mechanism": "unknown", "action": "observe-only"})
                for c in clients}

    def cache_truth(self, provider: str, observation: dict[str, Any]) -> dict[str, Any]:
        """L2: cache hit/miss truth from model_usage_mapper (never fabricate)."""
        return map_usage({"provider": provider, **observation})


def build_from_task(plane: ContextControlPlane, task: dict[str, Any],
                    root: Path, selectors: list[str]) -> dict[str, Any]:
    """Assemble from a task + directory evidence selectors. Read-only."""
    preserve = {k: str(task.get(k, "")) for k in DRIFT_PRESERVE}
    return plane.assemble(task, {"evidence": _read_evidence(root, selectors)},
                          preserve, base_tree=task.get("base_tree"))


def _read_evidence(root: Path, selectors: list[str]) -> str:
    parts = []
    for sel in selectors:
        p = (root / sel).resolve()
        try:
            p.relative_to(root.resolve())
        except ValueError:
            raise ValueError(f"path escape rejected: {sel}")
        if p.is_file():
            parts.append(f"{sel}: {p.read_text(encoding='utf-8', errors='replace')[:2000]}")
    return "\n".join(parts)


if __name__ == "__main__":
    plane = ContextControlPlane("work-lab", "rev-1")
    task = {
        "task_id": "t1",
        "boundary": "project root only",
        "acceptance": "tests pass",
        "base_tree": "abc123",
        "user_goal": "reduce token waste",
        "non_goals": "drop nothing",
        "allowed_paths": ".hermes",
        "forbidden_paths": "E:/",
        "data_boundary": "project only",
        "known_failures": "none",
        "acceptance_commands": "run_quality_gate",
        "rollback_method": "restore backup",
    }
    result = plane.assemble(task, {"system_boundary": "proj", "evidence": "e1"}, task)
    print(json.dumps({k: v for k, v in result.items() if k != "bundle"}, ensure_ascii=False, indent=2))
    print("bundle valid:", ContextBundle.validate(result["bundle"]))
    print("cache truth:", json.dumps(plane.cache_truth("deepseek", {"cache_hit_tokens": 10, "cache_miss_tokens": 5}), ensure_ascii=False))
