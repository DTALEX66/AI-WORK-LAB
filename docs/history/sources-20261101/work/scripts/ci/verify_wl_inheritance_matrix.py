"""Verify the WL inheritance matrix (M-010) exists and covers 30/30 entries with honest statuses."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / ".project/governance" / "generated" / "WL_INHERITANCE_MATRIX.json"


def main() -> int:
    if not MATRIX.exists():
        print("WL_MATRIX_FAIL missing=.project/governance/generated/WL_INHERITANCE_MATRIX.json")
        return 1
    doc = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = doc.get("entries", [])
    if doc.get("declaredCount") != 30 or len(entries) != 30:
        print(f"WL_MATRIX_FAIL declaredCount={doc.get('declaredCount')} actual={len(entries)}")
        return 1
    ids = [e["wlId"] for e in entries]
    if len(set(ids)) != 30:
        print("WL_MATRIX_FAIL duplicate wlId")
        return 1
    valid = {"INHERITED_VERIFIED", "IMPLEMENTED_UNVERIFIED", "PENDING", "BLOCKED", "SUPERSEDED", "REJECTED", "SUPERSEDED_MOVED"}
    for e in entries:
        if e.get("inheritanceStatus") not in valid:
            print(f"WL_MATRIX_FAIL invalid status for {e.get('wlId')}: {e.get('inheritanceStatus')}")
            return 1
    expected_moved = {"WL-600", "WL-610", "WL-620", "WL-630"}
    moved = {e["wlId"] for e in entries if e["inheritanceStatus"] == "SUPERSEDED_MOVED"}
    if moved != expected_moved:
        print(f"WL_MATRIX_FAIL SUPERSEDED_MOVED set mismatch: {sorted(moved)}")
        return 1
    print(f"WL_MATRIX_PASS entries=30 superseded_moved=4 statuses={json.dumps(doc.get('statusCounts', {}))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
