"""Verify capability-matrix.json consistency with adapter-registry.json + workflow-manifest.yaml (WL3-100)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MATRIX = ROOT / "config" / "capability-matrix.json"
REGISTRY = ROOT / "config" / "adapter-registry.json"


def main() -> int:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    reg = {e["id"]: e for e in registry["entries"]}
    errors: list[str] = []
    for client in matrix["clients"]:
        cid = client["id"]
        if cid not in reg:
            errors.append(f"matrix client {cid!r} missing in registry")
            continue
        entry = reg[cid]
        expected_status = entry["provenance"]["status"]
        if client.get("registry_status") != expected_status:
            errors.append(f"{cid}: matrix registry_status={client.get('registry_status')} != registry {expected_status}")
        expected_risk = entry["provenance"]["risk"]
        if client.get("risk") != expected_risk:
            errors.append(f"{cid}: matrix risk={client.get('risk')} != registry {expected_risk}")
        expected_ops = set(entry["operations"])
        matrix_ops = set(client.get("operations") or [])
        if matrix_ops != expected_ops:
            errors.append(f"{cid}: matrix operations={sorted(matrix_ops)} != registry {sorted(expected_ops)}")
        expected_support = entry["support_level"]
        if client.get("support_level") != expected_support:
            errors.append(f"{cid}: matrix support_level={client.get('support_level')} != registry {expected_support}")
        if "kind" in entry:
            if client.get("kind") != entry.get("kind"):
                errors.append(f"{cid}: matrix kind mismatch (registry kind={entry.get('kind')})")
        else:
            if "kind" in client and client.get("kind") != "client":
                errors.append(f"{cid}: non-registry kind field on a client-kind adapter")
    matrix_ids = {c["id"] for c in matrix["clients"]} | {c["id"] for c in matrix["manifest_only_clients"]}
    reg_ids = set(reg)
    if matrix_ids != reg_ids:
        errors.append(f"matrix ids {sorted(matrix_ids - reg_ids)} vs registry-only {sorted(reg_ids - matrix_ids)}")
    if errors:
        print("CAPABILITY_MATRIX_FAIL")
        for e in errors:
            print("  " + e)
        return 1
    print(f"CAPABILITY_MATRIX_PASS clients={len(matrix['clients'])} manifest_only={len(matrix['manifest_only_clients'])} registry={len(reg)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
