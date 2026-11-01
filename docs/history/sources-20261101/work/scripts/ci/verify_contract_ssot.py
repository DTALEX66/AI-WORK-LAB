#!/usr/bin/env python3
"""U16: Cross-language contract SSOT conformance (catalog-driven, no hardcoded counts).

Single source of truth for cross-language contracts = the JSON Schema set,
referenced by .project/governance/contracts/contract-catalog.json.

This verifier is CATALOG-DRIVEN (P0-4.1: it never hardcodes a contract count,
so adding a contract cannot break the gate just because a number was frozen).

Hard-fail (exit 1) on real SSOT drift:
  1. catalog malformed (missing id/owner/schemaPath, duplicate ids)
  2. a catalog entry points to a schema that does NOT exist on disk
  3. the generated TS projection (packages/client-neutral-core/generated/contracts.ts)
     is missing, or its contract id set != the catalog id set (type drift)

ADVISORY (printed, does NOT fail the gate):
  A. on-disk .schema.json files under the canonical roots that are not in the
     catalog. These are surfaced so a reviewer can decide whether each is a
     cross-language authority (should be cataloged) or a helper schema (fine).
     Not every schema on disk is a cross-language contract authority, so this
     is a report, not a hard gate.

  CORRECTION (2026-10-08): "printed, does not fail" was itself the defect. A gate that can see an
  unexplained schema file and cannot go red is a gate whose output decays into decoration, and the
  count drifted silently (13 -> 12 as this session registered one of them). The set is still allowed
  to be unlisted, but every member must be DECLARED below with the reason measured from the tree, and
  the gate now fails both when a new unlisted schema appears and when a declared one disappears --
  so the boundary between "cross-language contract" and "python-side schema" stays a reviewed decision
  instead of an accident of whoever added a file last.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CANONICAL_SCHEMA_ROOTS = (
    "packages/contracts/schemas",
    ".project/governance/contracts",
    "apps/observer/schemas",
)
GENERATED_TS = "packages/client-neutral-core/generated/contracts.ts"

# Every member is measured, not assumed: `named by verify_core_schemas.py` / a named verifier / a test,
# plus the result of `git grep -F <path>` and a TypeScript-name search for the contract. A member with
# no consumer at all is declared as such rather than quietly tolerated -- that is the point of writing
# the reason down.
DECLARED_HELPER_SCHEMAS: dict[str, str] = {
    ".project/governance/contracts/future-candidate-registry.schema.json":
        "governance-document shape loaded directly by scripts/ci/"
        "verify_future_candidate_registry.py; not a cross-language payload",
    "packages/contracts/schemas/workflow/adapter-registry.schema.json":
        "python-side adapter registry validated by verify_core_schemas.py and read by "
        "run_quality_gate/config-authority-index; no TypeScript consumer found",
    "packages/contracts/schemas/workflow/agent-runtime-adapter.schema.json":
        "DSH adapter contract, python-side (verify_core_schemas.py + "
        "tests/workflow-assistance/test_deepseek_harness_adapter.py); no TypeScript consumer found",
    "packages/contracts/schemas/workflow/canonical-config-intent.schema.json":
        "the FILE is opened by services/policy/config_compiler.py, which takes its version const and "
        "its client/type enums from this schema rather than restating them, and by "
        "packages/client-neutral-core/scripts/backup_restore_drill.py as a backed-up critical file; "
        "tests/ci/test_config_compiler_conforms_to_its_contract.py validates every lifecycle write "
        "against it; python-side, no TypeScript consumer",
    "packages/contracts/schemas/workflow/cloud-event-envelope.schema.json":
        "reached only by the directory census in tests/workflow-assistance/test_core_schemas.py -- no "
        "code path loads it, and the CloudEvents field it exists to pin, specversion, appears nowhere in "
        "the tracked tree except this schema and one frozen release note, so it is an unimplemented "
        "delivery shape rather than a live contract; with additionalProperties:true it would also accept "
        "a key the registry has never named, so it is not yet a guard either",
    "packages/contracts/schemas/workflow/context-capsule.schema.json":
        "assembled by packages/client-neutral-core/scripts/plan_candidate.py and cited by "
        ".project/governance/future-candidate-registry.json; python-side handoff shape",
    "packages/contracts/schemas/workflow/error.schema.json":
        "python-side error envelope validated by verify_core_schemas.py; the Observer renders its own "
        "error state and does not import this shape",
    "packages/contracts/schemas/workflow/model-asset.schema.json":
        "WL3-330 python-side asset metadata, validated by verify_core_schemas.py",
    "packages/contracts/schemas/workflow/model-invocation-plan.schema.json":
        "WL3-330 python-side invocation plan, validated by verify_core_schemas.py",
    "packages/contracts/schemas/workflow/runtime-registry.schema.json":
        "WL3-330 python-side runtime registry, validated by verify_core_schemas.py",
    "packages/contracts/schemas/workflow/task-ledger.schema.json":
        "python-side ledger shape validated by verify_core_schemas.py and "
        "tests/workflow-assistance/test_task_ledger.py; the Observer reads the snapshot, not this",
    "packages/contracts/schemas/workflow/usage-observation.schema.json":
        "WL3-520 python-side usage shape, checked by scripts/ci/verify_usage_convergence.py; "
        "apps/token-monitor documents it in prose but does not import it",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_catalog(root: Path) -> list[dict]:
    p = root / ".project" / "governance" / "contracts" / "contract-catalog.json"
    if not p.is_file():
        print(f"CONTRACT_SSOT_FAIL catalog missing: {p}")
        sys.exit(1)
    data = json.loads(p.read_text(encoding="utf-8"))
    entries = data.get("contracts")
    if not isinstance(entries, list):
        print("CONTRACT_SSOT_FAIL catalog 'contracts' must be an array")
        sys.exit(1)
    return entries


def _disk_schemas(root: Path) -> set[str]:
    found: set[str] = set()
    for rel_root in CANONICAL_SCHEMA_ROOTS:
        base = root / rel_root
        if not base.is_dir():
            continue
        for p in base.rglob("*.schema.json"):
            if "src-tauri" in p.parts or "target" in p.parts:
                continue
            found.add(p.relative_to(root).as_posix())
    return found


def _ts_contract_ids(root: Path) -> set[str] | None:
    p = root / GENERATED_TS
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8")
    return set(re.findall(r"// @contract ([A-Za-z0-9_\-]+)", text))


def unlisted_verdict(unlisted) -> tuple[list[str], list[str]]:
    """Split the on-disk-but-uncatalogued set into (undeclared, stale).

    Exposed as a function so a test can plant both faults without touching the tree: the previous
    version of this rule could not fail at all, which is the thing being fixed.
    """
    un = set(unlisted)
    return (sorted(un - set(DECLARED_HELPER_SCHEMAS)),
            sorted(set(DECLARED_HELPER_SCHEMAS) - un))


def main() -> int:
    root = _repo_root()
    errors: list[str] = []

    entries = _load_catalog(root)
    ids = [e.get("id") for e in entries]
    cat_ids = set(ids)

    # 1. catalog well-formed
    if len(ids) != len(cat_ids):
        dup = sorted({i for i in ids if i and ids.count(i) > 1})
        errors.append(f"duplicate contract ids: {dup}")
    for e in entries:
        for field in ("id", "owner", "schemaPath"):
            if not e.get(field):
                errors.append(f"catalog entry missing '{field}': {e}")

    # 2. every catalog schemaPath exists on disk
    seen: set[str] = set()
    for e in entries:
        sp = e.get("schemaPath", "").replace("\\", "/")
        if not sp:
            continue
        if sp in seen:
            errors.append(f"duplicate schemaPath: {sp}")
        seen.add(sp)
        if not (root / sp).is_file():
            errors.append(f"catalog '{e.get('id')}' -> missing schema {sp}")

    # 3. generated TS projection present + id set == catalog id set
    ts_ids = _ts_contract_ids(root)
    if ts_ids is None:
        errors.append(f"generated TS projection missing: {GENERATED_TS} "
                      f"(run scripts/ci/generate_contract_types.py)")
    else:
        missing = sorted(cat_ids - ts_ids)
        extra = sorted(ts_ids - cat_ids)
        if missing:
            errors.append("generated TS missing contracts: " + ", ".join(missing))
        if extra:
            errors.append("generated TS has unknown contracts: " + ", ".join(extra))

    # unlisted on-disk schemas are allowed only as a DECLARED set (see DECLARED_HELPER_SCHEMAS)
    disk = _disk_schemas(root)
    unlisted = sorted(d for d in disk if d not in seen)
    undeclared = sorted(set(unlisted) - set(DECLARED_HELPER_SCHEMAS))
    stale = sorted(set(DECLARED_HELPER_SCHEMAS) - set(unlisted))
    if undeclared:
        errors.append("unlisted schema without a declared helper reason: " + ", ".join(undeclared))
    if stale:
        errors.append("declared helper is no longer unlisted -- delete the line: " + ", ".join(stale))

    if errors:
        for u in unlisted:
            print(f"CONTRACT_SSOT_ADVISORY unlisted-on-disk-schema {u}")
        for err in errors:
            print(f"CONTRACT_SSOT_FAIL {err}")
        return 1

    print(f"CONTRACT_SSOT_PASS contracts={len(cat_ids)} "
          f"disk_schemas={len(disk)} unlisted_declared={len(unlisted)} "
          f"helper_declarations={len(DECLARED_HELPER_SCHEMAS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
