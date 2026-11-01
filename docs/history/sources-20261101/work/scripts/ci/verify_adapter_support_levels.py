#!/usr/bin/env python3
"""W09 (2026-10-17): a client's support level may not promise more than its evidence proves.

Why
---
`config/adapter-registry.json` already distinguishes `deep` / `experimental` / `manifest-only`, records
`operations`, `detection.mode`, `provenance.source_kind`/`version` and a `policy_projection` of
`*_supported` flags. Every one of those statements is true today by inspection -- and nothing enforced them.
The failure mode W09 names is exactly the quiet promotion: a client that is merely *installed*, or merely
*has a manifest*, being recorded as an integration, so that a later reader plans against capabilities that
were never verified. Nothing in the tree would have said so.

What it enforces (each rule is true of the registry as it stands; each catches a named promotion)
-----------------------------------------------------------------------------------------------
A. `support_level == "manifest-only"`  -> no write operation and no apply/readback/rollback flag.
   A manifest is not an interface. (`workbuddy`, `cursor`, `claude-code` are the live cases.)
B. `detection.mode == "static"`        -> `apply_supported` false.
   Static detection cannot prove a live write interface exists.
C. `apply_supported` true              -> the reviewed adapter exists as `integrations/executors/<id>/` in the
   repository AND the provenance version is not UNVERIFIED. A write claim needs both.
   (`hermes`, `codex` are the live cases; `github` claims only `plan_supported`, so it needs neither.)
D. `provenance.version == "UNVERIFIED"` -> `support_level` is `manifest-only`.
   An unverified version may not be promoted above the tier that says "we have only seen a manifest".

Deliberately NOT enforced: how many clients exist, which ones are managed, and whether `qoder` should be
registered at all. Those are owner decisions (`Qoder/WorkBuddy 先 native-only/observe`); this checker only
refuses to let a *recorded* claim outrun its evidence.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "adapter-registry.json"
WRITE_OPERATIONS = {"plan", "apply", "invoke", "rollback"}
WRITE_FLAGS = ("apply_supported", "readback_supported", "rollback_supported")


def tracked_files(root: Path) -> set[str]:
    result = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def audit(registry: dict[str, Any], tracked: set[str]) -> list[str]:
    problems: list[str] = []
    entries = registry.get("entries") or []
    if not entries:
        return ["registry declares no entries; a checker that sees nothing reports nothing"]
    for entry in entries:
        cid = str(entry.get("id") or "?")
        level = str(entry.get("support_level") or "")
        operations = set(entry.get("operations") or [])
        detection = entry.get("detection") or {}
        provenance = entry.get("provenance") or {}
        projection = entry.get("policy_projection") or {}
        version = str(provenance.get("version") or "")
        mode = str(detection.get("mode") or "")

        if not detection.get("evidence_state"):
            problems.append(f"{cid}: detection carries no evidence_state; the basis of the level is unstated")

        write_ops = sorted(operations & WRITE_OPERATIONS)
        write_flags = [flag for flag in WRITE_FLAGS if projection.get(flag)]

        if level == "manifest-only" and (write_ops or write_flags):
            problems.append(f"{cid}: manifest-only but claims write capability "
                            f"(operations={write_ops} flags={write_flags}); a manifest is not an interface")

        if mode == "static" and projection.get("apply_supported"):
            problems.append(f"{cid}: detection.mode=static but apply_supported is true; static detection "
                            f"cannot prove a live write interface")

        if projection.get("apply_supported"):
            adapter = f"integrations/executors/{cid}/"
            if not any(path.startswith(adapter) for path in tracked):
                problems.append(f"{cid}: claims apply_supported with no reviewed adapter directory "
                                f"({adapter} is not tracked)")
            if version == "UNVERIFIED":
                problems.append(f"{cid}: claims apply_supported while provenance.version is UNVERIFIED")

        if version == "UNVERIFIED" and level not in ("manifest-only", ""):
            problems.append(f"{cid}: version UNVERIFIED but support_level={level!r}; an unverified version "
                            f"may not be promoted above manifest-only")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    if not REGISTRY.is_file():
        print(f"ADAPTER_SUPPORT_LEVELS_FAIL {REGISTRY} is missing; nothing to check")
        return 1
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    problems = audit(registry, tracked_files(args.root))
    entries = registry.get("entries") or []
    by_level: dict[str, int] = {}
    for entry in entries:
        by_level[str(entry.get("support_level"))] = by_level.get(str(entry.get("support_level")), 0) + 1
    print(f"ADAPTER_SUPPORT_LEVELS entries={len(entries)} levels={dict(sorted(by_level.items()))}")
    for problem in problems:
        print(f"  {problem}")
    if problems:
        print(f"ADAPTER_SUPPORT_LEVELS_FAIL problems={len(problems)}")
        return 1
    print("ADAPTER_SUPPORT_LEVELS_PASS no recorded capability outruns its evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
