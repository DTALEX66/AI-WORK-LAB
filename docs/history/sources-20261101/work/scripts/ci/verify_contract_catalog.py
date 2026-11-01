#!/usr/bin/env python3
"""Fail-closed verification for the root contract catalog and owned schemas."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, SchemaError

EXPECTED = {
    "module-profile": "root-governance",
    "source-ledger": "root-governance",
    "capability-conformance": "root-governance",
    "task-card": "workflow",
    "runtime-lock": "workflow",

    "domain-pack": "external-design-lab",
    "evidence-envelope": "root-governance",
    "workflow-evidence-envelope": "workflow",
    "release-manifest": "root-governance",
    "adapter-capability": "workflow",
    "action-plan": "workflow",
    # The repair-pack envelope (后端2, 2026-10-22): a prepared handoff for an executor a human
    # named, never an auto-dispatch. Registered rather than left loose because this file is the review gate
    # that makes a new contract an explicit decision -- and the interface it generates is what proves the
    # envelope's refusal fields (sent/dispatched const false) survive into the TypeScript side.
    "repair-pack": "workflow",
    # CL-06 (2026-10-23): the reusable solution revision. Its producer is `solution_library.py` and its
    # reader is the sidecar's `/api/v1/solutions`; registering it here is the review gate for a new
    # cross-language document, and it is what generates the TypeScript interface the Observer consumes.
    "solution": "workflow",
    "task-ledger-event": "workflow",
    # P1-06 (2026-10-08): the Control Surface pair. Registering a contract here is the review gate that
    # makes a new cross-language write boundary an explicit decision instead of a file that appeared.
    "control-operation": "workflow",
    "control-operation-result": "workflow",
    # OD05 (2026-10-08): Quick Entry finally gets a field and permission spec. Blueprint coverage recorded
    # the mode as having "no field or permission spec anywhere in the source ... must not be presented as
    # implemented"; registering the contract here is the review gate, and the consumer is
    # packages/client-neutral-core/scripts/quick_entry.py.
    "quick-entry-request": "workflow",
    # ERR-173 precedent: the packages/.../workflow copy of an observer-event name is a DIFFERENT
    # document from apps/observer/schemas/observer-event.schema.json (snake_case projection-event shape,
    # $id work-lab/observer-event/v1, validated by verify_core_schemas.py). Registered additively under
    # its own id so one filename no longer hides two contracts in the SSOT.
    "workflow-observer-event": "workflow",
    "rule-asset": "workflow",
    "skill-package": "workflow",
    "growth-candidate": "workflow",
    "observer-event": "observer",
    "observer-pricing": "observer",
    "data-quality": "observer",
    "dashboard-projection": "observer",

    "archive-manifest": "root-governance",
    "project-profile": "workflow",
    "gate-registry": "workflow",
    "gate-plan": "workflow",
    "blocker": "workflow",
    "ci-observation": "workflow",
    "evidence-manifest": "workflow",
    "model-policy": "workflow",
    "memory-record": "workflow",
    "rule-drift": "workflow",
    "config-ownership": "workflow",
    "platform-identity": "workflow",
    "global-agent-policy": "workflow",
    "policy-projection-contract": "workflow",
    "policy-projection-loss-report": "workflow",
    "software-installation-identity": "workflow",
    "software-update-preflight": "workflow",
    "execution-parallel-dispatch": "workflow",
    "software-update-postflight": "workflow",
    # WUI-15 (2026-10-10): the read-only Observer snapshot finally joins the SSOT. It was the one
    # cross-language payload the front and the producer both depend on and that lived only as Python
    # validation code plus a hand-maintained types.ts, which is how ERR-225 happened — the producer emitted
    # entryProbe/versionDrift the front model never declared, so those facts could not render and nothing
    # went red. Registering it here is the review gate this file exists for.
    "workflow-snapshot-v3": "workflow",
    # WUI-21 read models. Registered here rather than left as loose schema files because the whole
    # point of this registry is that a field the producer cannot answer has to be visible as a gap:
    # both contracts carry a producer_gaps list, and the state enum refuses SUBMITTING, which no
    # module in this repository produces.
    "workflow-operation-progress-v1": "workflow",
    "workflow-isolated-trial-v1": "workflow",
}
CANONICAL_SCHEMA_PREFIXES = {
    "module-profile": (".project/governance/",),
    "source-ledger": (".project/governance/",),
    "capability-conformance": (".project/governance/",),
    "task-card": ("packages/contracts/",),
    "runtime-lock": (".project/governance/",),

    "domain-pack": ("packages/contracts/",),
    "evidence-envelope": (".project/governance/",),
    "workflow-evidence-envelope": ("packages/contracts/",),
    "release-manifest": (".project/governance/",),
    "adapter-capability": ("packages/contracts/",),
    "action-plan": ("packages/contracts/",),
    "repair-pack": ("packages/contracts/",),
    "solution": ("packages/contracts/",),
    "task-ledger-event": ("packages/contracts/",),
    "control-operation": ("packages/contracts/",),
    "control-operation-result": ("packages/contracts/",),
    "quick-entry-request": ("packages/contracts/",),
    "workflow-observer-event": ("packages/contracts/",),
    "rule-asset": ("packages/contracts/",),
    "skill-package": ("packages/contracts/",),
    "growth-candidate": ("packages/contracts/",),
    "observer-event": ("apps/observer/",),
    "observer-pricing": ("apps/observer/",),
    "data-quality": ("apps/observer/",),
    "dashboard-projection": ("apps/observer/",),

    "archive-manifest": (".project/governance/",),
    "project-profile": ("packages/contracts/",),
    "gate-registry": ("packages/contracts/",),
    "gate-plan": ("packages/contracts/",),
    "blocker": ("packages/contracts/",),
    "ci-observation": ("packages/contracts/",),
    "evidence-manifest": ("packages/contracts/",),
    "model-policy": ("packages/contracts/",),
    "memory-record": ("packages/contracts/",),
    "rule-drift": ("packages/contracts/",),
    "config-ownership": ("packages/contracts/",),
    "platform-identity": ("packages/contracts/",),
    "global-agent-policy": ("packages/contracts/",),
    "policy-projection-contract": ("packages/contracts/",),
    "policy-projection-loss-report": ("packages/contracts/",),
    "software-installation-identity": ("packages/contracts/",),
    "software-update-preflight": ("packages/contracts/",),
    "execution-parallel-dispatch": ("packages/contracts/",),
    "software-update-postflight": ("packages/contracts/",),
    "workflow-snapshot-v3": ("packages/contracts/",),
    "workflow-operation-progress-v1": ("packages/contracts/",),
    "workflow-isolated-trial-v1": ("packages/contracts/",),
}


def verify_catalog(root: Path) -> list[str]:
    errors: list[str] = []
    catalog_path = root / ".project/governance" / "contracts" / "contract-catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"catalog unreadable: {exc}"]

    entries = catalog.get("contracts")
    if not isinstance(entries, list):
        return ["catalog contracts must be an array"]

    by_id: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            errors.append("catalog entry missing string id")
            continue
        contract_id = entry["id"]
        if contract_id in by_id:
            errors.append(f"duplicate contract id: {contract_id}")
        by_id[contract_id] = entry

    if set(by_id) != set(EXPECTED):
        errors.append(f"catalog ids must equal {sorted(EXPECTED)}; got {sorted(by_id)}")

    seen_paths: set[str] = set()
    for contract_id, owner in EXPECTED.items():
        entry = by_id.get(contract_id)
        if entry is None:
            continue
        if entry.get("owner") != owner:
            errors.append(f"{contract_id}: owner must be {owner}")
        schema_path = entry.get("schemaPath")
        if not isinstance(schema_path, str) or not schema_path:
            errors.append(f"{contract_id}: schemaPath is required")
            continue
        normalized = schema_path.replace("\\", "/")
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
            errors.append(f"{contract_id}: schemaPath escapes repository: {schema_path}")
            continue
        if normalized in seen_paths:
            errors.append(f"duplicate schemaPath: {normalized}")
        seen_paths.add(normalized)
        canonical_prefixes = CANONICAL_SCHEMA_PREFIXES.get(contract_id)
        if canonical_prefixes is None:
            # A new id added to EXPECTED without a canonical boundary used to raise KeyError here, which
            # destroys the whole verdict the same way a crashed gate always does. Name the missing entry
            # instead: this gate has to be able to report its own bookkeeping gap.
            errors.append(f"{contract_id}: declared in EXPECTED but has no entry in "
                          "CANONICAL_SCHEMA_PREFIXES -- state which module boundary its schema lives behind")
        elif not normalized.startswith(canonical_prefixes):
            errors.append(f"{contract_id}: schemaPath is outside its canonical module boundary: {schema_path}")
        path = root / Path(normalized)
        if not path.is_file():
            errors.append(f"{contract_id}: missing schema {normalized}")
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
            errors.append(f"{contract_id}: invalid JSON Schema: {exc}")
            continue
        if not isinstance(schema.get("$id"), str) or not schema["$id"]:
            errors.append(f"{contract_id}: schema $id is required")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    errors = verify_catalog(root)
    if errors:
        for error in errors:
            print(f"CONTRACT_CATALOG_FAIL {error}")
        return 1
    print(f"CONTRACT_CATALOG_PASS contracts={len(EXPECTED)} schemas={len(EXPECTED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
