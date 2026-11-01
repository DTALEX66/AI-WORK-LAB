#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""P1-3 — library index 4-file consistency guard (cross-file invariants).

DESIGN-LAB carries its library / model / asset roots in four files that are
maintained independently and therefore drift unless cross-checked:

  * ``.project/paths.json``                         — shared_inputs roots (the single source of truth)
  * ``design-lab/config/external-assets-index.json``  — shared_roots + asset ids
  * ``design-lab/readiness/model-radar.json``        — asset_index_ids -> index ids
  * ``design-lab/config/task-resources.json``        — external/model resource refs -> roots

This guard enforces the cross-file invariants plus the "every shared root is
declared on the local ``D:`` drive" red line (E: is protected, C: is not the
declared library drive). It is pure-stdlib, read-only and fail-closed.

It deliberately does NOT probe whether the external roots exist on disk: they
live outside the repository and differ per machine, so existence is the
local-inventory job (the same stance as ``verify_external_assets_index.py``,
which checks schema + root *declaration*, never root *existence*).

``task-resources.json`` is legal to be absent (its own ``note`` says so): the
guard skips the resource-reference checks when it is missing but still
validates the other three. The other three files are required; a missing one
is a fail-closed error.

Run:
    python design-lab/scripts/verify_library_index_consistency.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DESIGN_LAB = Path(__file__).resolve().parents[1]  # design-lab/
REPO_ROOT = DESIGN_LAB.parent                      # DESIGN-LAB/

PATHS_FILE = REPO_ROOT / ".project" / "paths.json"
ASSETS_FILE = DESIGN_LAB / "config" / "external-assets-index.json"
RADAR_FILE = DESIGN_LAB / "readiness" / "model-radar.json"
TASKS_FILE = DESIGN_LAB / "config" / "task-resources.json"

# Red line: declared shared roots must sit on the local D: drive (string-level
# invariant, so it holds on a CI runner that has no D: drive at all).
REQUIRED_DRIVE = "D:"

# The external/model resource entries in task-resources.json carry a *provenance
# string* like "declared in .project/paths.json shared_inputs.model-library"
# rather than a literal path; extract the referenced shared_inputs key.
_SHARED_REF_RE = re.compile(r"shared_inputs\.([a-z][a-z0-9-]*)")


def _norm(path: str) -> str:
    """Normalise a declared root so ``D:\\a\\b`` and ``D:/a/b`` compare equal."""
    return path.replace("\\", "/")


def _on_drive(path: str, drive: str = REQUIRED_DRIVE) -> bool:
    return _norm(path).upper().startswith(drive.upper())


def check(
    paths: dict,
    assets: dict,
    radar: dict,
    tasks: dict | None = None,
) -> list[str]:
    """Cross-check the four library/index documents.

    Returns a list of human-readable errors; an empty list means the invariants
    hold. ``tasks`` may be ``None`` (legal absence of task-resources.json).
    """
    errors: list[str] = []

    shared_inputs = paths.get("shared_inputs", {})
    index_roots = assets.get("shared_roots", {})

    # (1) every shared_inputs root is declared on the D: drive.
    for name, root in shared_inputs.items():
        if not _on_drive(str(root)):
            errors.append(f"paths.json shared_inputs.{name} = {root!r} is not on the {REQUIRED_DRIVE} drive")

    # (2) external-assets shared_roots: key must be a declared shared_inputs
    #     entry, value on the D: drive, and value must AGREE with paths.json
    #     (single source of truth — a disagreement is exactly the drift this
    #     guard exists to catch).
    for name, root in index_roots.items():
        if name not in shared_inputs:
            errors.append(f"external-assets shared_roots.{name} is not declared in paths.json shared_inputs")
        if not _on_drive(str(root)):
            errors.append(f"external-assets shared_roots.{name} = {root!r} is not on the {REQUIRED_DRIVE} drive")
        elif name in shared_inputs and _norm(str(root)) != _norm(str(shared_inputs[name])):
            errors.append(
                f"external-assets shared_roots.{name} = {_norm(str(root))!r} disagrees with "
                f"paths.json shared_inputs.{name} = {_norm(str(shared_inputs[name]))!r}")

    # (3) every asset's shared_root must be a declared shared_roots key.
    asset_ids: set[str] = set()
    for a in assets.get("assets", []):
        asset_ids.add(a.get("id"))
        if a.get("shared_root") not in index_roots:
            errors.append(f"asset {a.get('id')!r}: shared_root {a.get('shared_root')!r} not in shared_roots")

    # (4) every radar entry's asset_index_ids must point at existing index ids
    #     (an empty list is legal; a dangling id is drift).
    for entry in radar.get("entries", []):
        for ref in entry.get("asset_index_ids", []):
            if ref not in asset_ids:
                errors.append(
                    f"model-radar {entry.get('model_id')!r}: asset_index_ids references unknown index id {ref!r}")

    # (5) task-resources external/model refs must name a declared shared_inputs
    #     key, and each task's resource refs must be declared resources.
    if tasks is not None:
        resources = tasks.get("resources", {})
        for rname, r in resources.items():
            if r.get("kind") in {"external", "model"}:
                for ref in _SHARED_REF_RE.findall(str(r.get("path", ""))):
                    if ref not in shared_inputs:
                        errors.append(
                            f"task-resources resources.{rname} references shared_inputs.{ref} "
                            f"which is not declared in paths.json")
        declared = set(resources)
        for tkey, trefs in (tasks.get("tasks") or {}).items():
            for rref in trefs:
                if rref not in declared:
                    errors.append(f"task-resources tasks.{tkey}: references undeclared resource {rref!r}")

    return errors


def _load(path: Path, required: bool, errors: list[str]) -> dict | None:
    if not path.exists():
        if required:
            errors.append(f"missing required file: {path.name}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # fail closed on any parse error
        errors.append(f"parse error in {path.name}: {exc}")
        return None


def main() -> int:
    errors: list[str] = []
    paths = _load(PATHS_FILE, True, errors)
    assets = _load(ASSETS_FILE, True, errors)
    radar = _load(RADAR_FILE, True, errors)
    tasks = _load(TASKS_FILE, False, errors)  # absence is legal

    # A missing/undecodable required file already recorded an error: fail
    # closed and report what we know so far.
    if paths is not None and assets is not None and radar is not None:
        errors.extend(check(paths, assets, radar, tasks))

    for e in errors:
        print("ERROR", e)
    verdict = "PASS" if not errors else "FAIL"
    print(
        f"LIBRARY_INDEX_CONSISTENCY={verdict} "
        f"shared_inputs={len((paths or {}).get('shared_inputs', {}))} "
        f"shared_roots={len((assets or {}).get('shared_roots', {}))} "
        f"assets={len((assets or {}).get('assets', []))} "
        f"radar_entries={len((radar or {}).get('entries', []))} "
        f"task_resources={'present' if tasks is not None else 'absent(legal)'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
