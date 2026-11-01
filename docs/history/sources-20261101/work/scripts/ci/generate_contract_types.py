#!/usr/bin/env python3
"""U16: generate the TypeScript projection of the JSON-Schema contract SSOT.

Reads the catalog (NOT a hardcoded list) and emits
packages/client-neutral-core/generated/contracts.ts with one exported
interface per catalogued contract + a `ContractId` union. The frontend/Rust
consume these generated types instead of hand-forking contract shapes
(AUDIT-CONVERGENCE U16 / language-architecture ADR).

Each contract block is tagged `// @contract <id>` so the SSOT verifier can
prove the generated set == the catalog set. This is generated output; do not
hand-edit (a schema change -> re-run this generator).

Practical depth: nested objects are projected up to MAX_DEPTH levels; deeper objects
and $ref fields collapse to Record<string, unknown> / unknown (documented
limitation, not a second authority).
"""
from __future__ import annotations

import json
from pathlib import Path

GEN_PATH = "packages/client-neutral-core/generated/contracts.ts"
CATALOG = ".project/governance/contracts/contract-catalog.json"
MAX_DEPTH = 5


def _pascal(name: str) -> str:
    return "".join(part.capitalize() for part in name.replace("-", "_").split("_") if part)


def _ts_type(prop: dict, depth: int) -> str:
    """Project one JSON-Schema property to a TS type expression."""
    if "$ref" in prop:
        return "unknown"
    typ = prop.get("type")
    if isinstance(typ, list):
        # e.g. ["string","null"] -> string | null ; ["object","null"] -> ...
        parts = [_ts_type({**prop, "type": t}, depth) for t in typ if t != "null"]
        parts = [p for p in parts if p]
        if "null" in typ:
            parts.append("null")
        # Deduplicated: a schema that allows null in its type *and* lists null among its enum values produced
        # `"A" | "B" | null | null` -- harmless to a compiler, but it makes the union string differ from the
        # hand-written model it is supposed to be compared against.
        unique: list[str] = []
        for part in parts:
            if part not in unique:
                unique.append(part)
        return " | ".join(unique) or "unknown"
    if "const" in prop:
        # A const is the narrowest enum there is; rendering it as `unknown` threw the fact away.
        return json.dumps(prop["const"])
    if "enum" in prop:
        # A union of literals. The previous rendering, `["A", "B"]`, is a tuple type in TypeScript, so every
        # enum field in the file demanded an array where the schema promises a single value.
        lits = " | ".join(json.dumps(v) for v in prop["enum"])
        base = lits if lits else "unknown"
        if isinstance(typ, list) and "null" in typ:
            return base + " | null"
        return base
    t = typ
    if t == "string":
        return "string"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "array":
        items = prop.get("items", {})
        if not items:
            return "unknown[]"
        if "$ref" in items:
            return "unknown[]"
        inner = _ts_type(items, depth + 1)
        # Parenthesised:  parses as , so an array whose members are an enum or a
        # union would silently accept a bare "A" -- the shape reads fine and says the wrong thing.
        return f"({inner})[]" if " | " in inner else f"{inner}[]"
    if t == "object":
        if depth >= MAX_DEPTH:
            return "Record<string, unknown>"
        props = prop.get("properties")
        if not props:
            if prop.get("additionalProperties"):
                return "Record<string, unknown>"
            return "Record<string, unknown>"
        req = set(prop.get("required", []))
        lines = []
        for k, v in props.items():
            ks = k if k.isidentifier() else json.dumps(k)
            opt = "" if k in req else "?"
            lines.append(f"    {ks}{opt}: {_ts_type(v, depth + 1)}")
        return "{\n" + ",\n".join(lines) + "\n  }"
    return "unknown"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    catalog = json.loads((root / CATALOG).read_text(encoding="utf-8"))
    entries = catalog.get("contracts", [])

    out: list[str] = []
    out.append("// GENERATED FILE — do not edit by hand.")
    out.append("// Source of truth: JSON Schema contracts referenced by the catalog")
    out.append("// (.project/governance/contracts/contract-catalog.json).")
    out.append("// Regenerate: python scripts/ci/generate_contract_types.py")
    out.append("// Each `// @contract <id>` marker is consumed by")
    out.append("// scripts/ci/verify_contract_ssot.py to prove generated == catalog.")
    out.append("")

    # ContractId union (every catalogued id)
    union = " | ".join(json.dumps(e.get("id")) for e in entries)
    out.append("export type ContractId =\n  " + ("\n  | ".join(
        json.dumps(e.get("id")) for e in entries)) + ";")
    out.append("")

    for e in entries:
        cid = e.get("id", "")
        spath = e.get("schemaPath", "").replace("\\", "/")
        sp = root / spath
        if not sp.is_file():
            # verifier will hard-fail on missing schema; emit a stub so this
            # generator never crashes the build — it just produces a placeholder.
            out.append(f"// @contract {cid}")
            out.append(f"// (schema missing at {spath}; stub pending verifier gate)")
            out.append(f"export type {_pascal(cid)} = unknown;")
            out.append("")
            continue
        schema = json.loads(sp.read_text(encoding="utf-8"))
        out.append(f"// @contract {cid}")
        out.append(f"// schema: {spath}")
        tname = _pascal(cid)
        body = _ts_type(schema, 0)
        # _ts_type on the root object gives the full interface body
        out.append(f"export type {tname} = {body};")
        out.append("")

    # Index union already emitted; per-contract types above are the projection.
    # (No runtime `CONTRACT_TYPES` map: a map of `undefined as T` casts is
    #  meaningless under strict TS; the type-level projection is the value.)
    out.append("")

    gen_dir = root / GEN_PATH
    gen_dir.parent.mkdir(parents=True, exist_ok=True)
    gen_dir.write_text("\n".join(out), encoding="utf-8")
    print(f"GENERATED_CONTRACT_TYPES contracts={len(entries)} -> {GEN_PATH}")


if __name__ == "__main__":
    main()
