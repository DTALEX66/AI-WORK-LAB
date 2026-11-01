#!/usr/bin/env python3
"""Verify the WORK-LAB cross-module source index (NX-100).

Guarantees:
- Every historical Open Design adopt-now source is recorded honestly:
  a decision status (external-optional / reference) is NOT presented as an
  implementation status (local-verified) when no WORK-LAB target path exists.
- An entry may claim implementation only when its declared target/test paths
  actually exist in the current tree.
- No Open Design source is registered as an active WORK-LAB absorbed module.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / ".project/governance" / "cross-module-source-index.json"
SOURCE_LEDGER = ROOT / ".project/governance" / "source-ledger.json"
FORBIDDEN_DESIGN_PREFIXES = (
    "scenarios/", "adapters/", "schemas/design-tokens/",
    "knowledge/", "evals/", "opendesign-assistance/", "20-design/open-design/",
)


def _git_head(root: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, encoding="utf-8", errors="replace",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _validate_shape(index: dict[str, Any]) -> None:
    if index.get("schemaVersion") != "work-lab/cross-module-source-index/v1":
        raise ValueError("cross-module index schema identity mismatch")
    if index.get("scope") != ["workflow-assistance", "work-lab-observer"]:
        raise ValueError("index scope must be only Workflow + Observer")
    entries = index.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("index entries must be a non-empty list")


def verify(root: Path = ROOT, index_path: Path | None = None) -> dict[str, Any]:
    if index_path is None:
        index_path = root / INDEX.relative_to(ROOT)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    _validate_shape(index)
    entries = index["entries"]
    errors: list[str] = []

    # Open Design entries must NOT claim WORK-LAB implementation.
    open_design_entries = [
        e for e in entries
        if str(e.get("ownerModule", "")).lower() in {"open-design", "open-design-assistance", "od"}
    ]
    for entry in open_design_entries:
        impl = entry.get("implementationStatus")
        if impl in {"local-verified", "adapter-implemented", "fixture-verified"}:
            errors.append(
                f"{entry['id']}: Open Design-owned source must not claim WORK-LAB implementation ({impl})"
            )
        decision = entry.get("decisionStatus")
        if decision in {"derive", "adapter", "vendor-adapt"}:
            errors.append(
                f"{entry['id']}: Open Design-owned source must use external-optional/reference, not {decision}"
            )

    # Honest implementation claim: local-verified requires real target paths.
    for entry in entries:
        impl = entry.get("implementationStatus")
        targets = entry.get("targetPaths") or []
        if impl in {"local-verified", "adapter-implemented", "fixture-verified"}:
            if not targets:
                errors.append(f"{entry['id']}: claims {impl} but has no target paths")
            for t in targets:
                if not (root / t).exists():
                    errors.append(f"{entry['id']}: claims {impl} but target {t} does not exist")
                    break

    # No Open Design target prefixes in a WORK-LAB-absorbed entry.
    for entry in entries:
        if entry.get("implementationStatus") in {"local-verified", "adapter-implemented", "fixture-verified"}:
            serialized = json.dumps(entry, ensure_ascii=False, sort_keys=True).lower()
            if any(p in serialized for p in FORBIDDEN_DESIGN_PREFIXES):
                errors.append(f"{entry['id']}: WORK-LAB-absorbed entry must not contain Open Design paths")

    # Integrity: adopt-now totals must reconcile.
    # Every entry whose sourceId came from the Open Design SOURCE_REGISTRY adopt-now set
    # is flagged as an Open Design-owned source (external-optional). Count all entries
    # carrying ownerModule = OPEN-DESIGN-Assistance (legacy) or DESIGN-LAB (current name,
    # after the 2026-08-14 rename; P1-4 — pointer-only, never re-absorbs design capability).
    OWNER_MODULES = {"open-design-assistance", "design-lab"}
    adopt = [e for e in entries if str(e.get("ownerModule", "")).lower() in OWNER_MODULES]
    complete = index.get("adopt_now_complete_in_worklab", -1)
    partial = index.get("adopt_now_partial_in_worklab", -1)
    none = index.get("adopt_now_no_worklab_targets", -1)
    total = index.get("adopt_now_total", -1)
    if complete + partial + none != total:
        errors.append("adopt-now accounting mismatch: complete+partial+none != total")
    if len(adopt) != total:
        errors.append(f"adopt-now entry count {len(adopt)} != declared {total}")

    if errors:
        raise ValueError("; ".join(errors))
    return {"entries": len(entries), "adopt_now": total,
            "complete": complete, "partial": partial, "none": none, "head": _git_head(root)}


def main() -> int:
    try:
        result = verify()
    except (OSError, json.JSONDecodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"CROSS_MODULE_SOURCE_INDEX_FAIL {exc}")
        return 1
    print(
        f"CROSS_MODULE_SOURCE_INDEX_PASS entries={result['entries']} "
        f"adopt_now={result['adopt_now']} complete={result['complete']} "
        f"partial={result['partial']} none={result['none']} "
        f"honest=true scope=workflow,observer"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
