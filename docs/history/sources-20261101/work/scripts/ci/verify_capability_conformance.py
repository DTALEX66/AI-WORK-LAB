#!/usr/bin/env python3
"""Verify static ACP/Skills/MCP conformance without live client access."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config/capability-conformance.json"
SCHEMA = ROOT / ".project/governance/contracts/capability-conformance.schema.json"
ADAPTERS = ROOT / "config/adapter-registry.json"
SKILLS = ROOT / "config/skill-provenance.yaml"
FORBIDDEN = {"write", "execute", "network"}


def verify_document(document: dict[str, Any], root: Path = ROOT) -> dict[str, int]:
    schema = json.loads((root / SCHEMA.relative_to(ROOT)).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda error: list(error.path))
    if errors:
        raise ValueError("; ".join(error.message for error in errors[:5]))
    if document["scope"] != ["workflow-assistance", "work-lab-observer"]:
        raise ValueError("capability scope drift")
    total = 0
    for protocol_name in ("acp", "skills", "mcp"):
        protocol = document[protocol_name]
        for entry in protocol["entries"]:
            total += 1
            if FORBIDDEN.intersection(entry["permissions"]):
                raise ValueError(f"{protocol_name}/{entry['id']}: write/execute/network permissions require explicit approval")
            if any(token in json.dumps(entry).lower() for token in ("opendesign-assistance", "open-design-assistance")):
                raise ValueError(f"{protocol_name}/{entry['id']}: retired Open Design migration alias capability")
    adapter_entries = json.loads((root / ADAPTERS.relative_to(ROOT)).read_text(encoding="utf-8"))["entries"]
    adapter_by_id = {entry["id"]: entry for entry in adapter_entries}
    for client_id in ("open-design", "openhuman"):
        entry = adapter_by_id.get(client_id)
        if entry is None:
            raise ValueError(f"adapter registry missing client adapter: {client_id}")
        if entry.get("support_level") != "experimental":
            raise ValueError(f"{client_id} adapter must be experimental until a reviewed official interface exists")
        operations = set(entry.get("operations", []))
        if not operations.issubset({"detect", "capabilities", "observe"}):
            raise ValueError(f"{client_id} adapter must be read-only (detect/capabilities/observe)")
    if not (root / SKILLS.relative_to(ROOT)).is_file():
        raise ValueError("skill provenance manifest missing")
    return {"protocols": 3, "entries": total, "mcp_unverified": 1}


def main() -> int:
    try:
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        result = verify_document(document)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"CAPABILITY_CONFORMANCE_FAIL {exc}")
        return 1
    print(f"CAPABILITY_CONFORMANCE_PASS protocols={result['protocols']} entries={result['entries']} mcp_unverified={result['mcp_unverified']} malicious_permissions=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
