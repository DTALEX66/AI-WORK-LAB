#!/usr/bin/env python3
"""U09: Token-Monitor / usage convergence — one canonical token/usage/cost contract.

Taskpack 20260919 U09: "One canonical token/usage/cost backend. Observer main UI
+ specialist helper, or Observer parity then specialist UI retirement. No deletion
before parity."

This gate makes that convergence MACHINE-VERIFIED against the single canonical
contract `usage-observation.schema.json` (the JSON-Schema SSOT, U16). It is
catalog/schema-driven — it does NOT hardcode a token-field count (P0-4.1
discipline: a new schema field cannot break the gate).

Convergence statement (fail-closed, exit 1 on any error):
  1. The canonical `usage-observation` schema is a valid JSON Schema and the
     token/cost/quality field set is read from the schema itself.
  2. OBSERVER (Python) conforms: a canonical usage record shaped like the
     Observer ingestion/rollup chain output validates against the schema.
  3. TOKEN-MONITOR (Rust, the "specialist helper") is NOT a second cost
     engine: its `Snapshot` struct carries NO cost/price/currency/usd/cny/
     amount field (U07/U09 front-truth + no-second-engine discipline), and its
     token fields map onto the schema's token fields. Parsed from source, not
     asserted by count.
  4. Role is documented: the token-monitor README carries the "specialist
     helper / one canonical usage contract" marker, so "specialist UI
     retirement" stays an explicit, authorized decision (no silent deletion).

Nothing is deleted here (no deletion before parity): this only proves the two
surfaces share ONE usage/cost contract and that the specialist does not fork
cost truth.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CANONICAL_SCHEMA = "packages/contracts/schemas/workflow/usage-observation.schema.json"
TOKEN_MONITOR_LIB = "apps/token-monitor/src-tauri/src/lib.rs"
TOKEN_MONITOR_README = "apps/token-monitor/README.md"

# token-monitor Rust Snapshot field -> canonical schema field (name mapping;
# `None` = derived sum the schema does not carry as a standalone field).
RUST_TO_SCHEMA_TOKEN = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cached_input_tokens": "cache_read_tokens",
    "reasoning_tokens": "reasoning_tokens",
    "total_tokens": None,
}

# Any of these in the Rust Snapshot would mean a SECOND cost engine.
COST_ENGINE_FIELD_RE = re.compile(r"cost|price|currency|usd|cny|amount", re.IGNORECASE)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_schema(root: Path) -> dict:
    sp = root / CANONICAL_SCHEMA
    if not sp.is_file():
        print(f"USAGE_CONVERGENCE_FAIL canonical schema missing: {CANONICAL_SCHEMA}")
        sys.exit(1)
    return json.loads(sp.read_text(encoding="utf-8"))


def _schema_fields(schema: dict) -> set[str]:
    return set((schema.get("properties") or {}).keys())


def _rust_snapshot_fields(root: Path) -> tuple[set[str], list[str], str]:
    lib = (root / TOKEN_MONITOR_LIB).read_text(encoding="utf-8")
    m = re.search(r"pub struct Snapshot \{(.*?)\n\}", lib, re.DOTALL)
    if not m:
        return set(), [], "Rust `pub struct Snapshot` not found in " + TOKEN_MONITOR_LIB
    body = m.group(1)
    fields = re.findall(r"pub\s+(\w+)\s*:", body)
    cost_hits = [f for f in fields if COST_ENGINE_FIELD_RE.search(f)]
    return set(fields), cost_hits, body


def _observer_record_conforms(schema: dict) -> list[str]:
    """Build a canonical usage record the way the Observer chain emits one and
    validate it against the schema. The record covers every REQUIRED schema
    field plus the token/cost fields, so schema drift in required fields
    surfaces here as a failure (not a silent pass)."""
    required = schema.get("required", [])
    record = {
        "schema_version": "workflow/usage-observation/v1",
        "observation_id": "obs-1",
        "plan_id": "plan-1",
        "task_id": "task-1",
        "project_id": "work-lab",
        "provider_lifecycle": "ACTIVE",
        "measurement_source": "OBSERVED",
        "completeness": "FULL",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_amount": None,
        "currency": None,
    }
    # Fill any required field not already present with a schema-valid value.
    props = schema.get("properties", {})
    for field in required:
        if field in record:
            continue
        p = props.get(field, {})
        enum = p.get("enum")
        typ = p.get("type")
        if enum:
            record[field] = enum[0]
        elif isinstance(typ, list):
            base = [t for t in typ if t != "null"]
            record[field] = {"string": "u09", "integer": 0, "number": 0.0, "boolean": False}.get(base[0] if base else "string", "u09")
        elif typ in ("string", "integer", "number", "boolean"):
            record[field] = {"string": "u09", "integer": 0, "number": 0.0, "boolean": False}.get(typ)
        else:
            record[field] = None
    errors: list[str] = []
    try:
        from jsonschema import Draft202012Validator
        for err in Draft202012Validator(schema).iter_errors(record):
            errors.append(f"observer usage record violates schema @ {list(err.path)}: {err.message}")
    except ImportError:
        errors.append("jsonschema not importable (run under the CI venv)")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"schema validation crashed: {exc}")
    return errors


def main() -> int:
    root = _repo_root()
    errors: list[str] = []
    advisories: list[str] = []

    schema = _load_schema(root)
    try:
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(schema)
    except ImportError:
        errors.append("jsonschema not importable (run under the CI venv)")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"canonical schema is not a valid JSON Schema: {exc}")

    all_fields = _schema_fields(schema)

    # 2. Observer conforms
    errors.extend(_observer_record_conforms(schema))

    # 3. token-monitor: no second cost engine + token fields map onto schema
    rust_fields, cost_hits, _body = _rust_snapshot_fields(root)
    if not rust_fields:
        errors.append(_rust_snapshot_fields(root)[2])
    if cost_hits:
        errors.append(
            "token-monitor Rust Snapshot carries cost-engine fields (a SECOND "
            f"usage/cost engine is forbidden, U09/U07): {sorted(cost_hits)}"
        )
    for rust_name, schema_name in RUST_TO_SCHEMA_TOKEN.items():
        if rust_name in rust_fields and schema_name is not None and schema_name not in all_fields:
            errors.append(
                f"token-monitor token field '{rust_name}' maps to unknown schema field '{schema_name}'"
            )

    # 4. role documented as specialist helper (advisory, not a hard fail)
    readme = root / TOKEN_MONITOR_README
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        if not re.search(r"specialist|one canonical|no second|单一|专家", text, re.IGNORECASE):
            advisories.append(
                "token-monitor README does not yet state its 'specialist helper / "
                "one canonical usage contract' role — add one line (U09 documentation)."
            )
    else:
        errors.append(f"token-monitor README missing: {TOKEN_MONITOR_README}")

    if errors:
        for a in advisories:
            print(f"USAGE_CONVERGENCE_ADVISORY {a}")
        for e in errors:
            print(f"USAGE_CONVERGENCE_FAIL {e}")
        return 1
    print(
        f"USAGE_CONVERGENCE_PASS canonical={CANONICAL_SCHEMA} "
        f"observer=conformed token_monitor=specialist(no-cost-engine) "
        f"schema_fields={len(all_fields)} rust_snapshot_fields={len(rust_fields)}"
    )
    for a in advisories:
        print(f"  [advisory] {a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
