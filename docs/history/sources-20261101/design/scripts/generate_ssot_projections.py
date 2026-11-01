#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-B040 / DLDS-H030 — regenerate the CAPABILITY_INDEX and EVIDENCE_INDEX projections.

These two files were produced by a throwaway script that lived under
``.project-local/`` (git-ignored), which made the projections unreproducible from
the tree: a projection whose generator is not in the repository cannot be
verified, refreshed or audited. This is that generator, promoted into
``scripts/`` unchanged in behaviour.

Both files are **projections**: their authoring sources stay
``design-lab/config/capability-{index,status}.json`` and
``design-lab/config/capability-evidence-{index,current}.json``. Nothing here may
edit capability state, and historical evidence bound to another tree never
auto-promotes a capability.

Usage:
    python scripts/generate_ssot_projections.py [--check]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RC = REPO / "reports" / "current"
TASK_KEYS = ["DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-B040",
             "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-H030"]
ORIGIN = "promoted from .project-local/task-runtime/r5-ssot-indexes-20260913/build_indexes.py"


def head() -> str:
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def load(rel: str) -> dict:
    return json.loads((REPO / rel).read_bytes().decode("utf-8"))


def build(observed_at: str) -> dict:
    sha = head()
    status = load("design-lab/config/capability-status.json")
    cindex = load("design-lab/config/capability-index.json")
    evindex = load("design-lab/config/capability-evidence-index.json")
    evcurrent = load("design-lab/config/capability-evidence-current.json")

    product_rows = []
    for capability in cindex.get("capabilities", []):
        cid = capability.get("id") or capability.get("capability_id") or capability.get("name")
        product_rows.append({
            "capability_id": cid,
            "declared": {k: v for k, v in capability.items() if k not in ("id",)},
            "state_record": status.get("capabilityRecords", {}).get(cid),
        })
    known = {row["capability_id"] for row in product_rows}
    for cid, record in status.get("capabilityRecords", {}).items():
        if cid not in known:
            product_rows.append({"capability_id": cid, "declared": None, "state_record": record})

    capability_payload = {
        "schemaVersion": "design-lab/capability-index-projection/v1",
        "task_keys": TASK_KEYS,
        "origin": ORIGIN,
        "observed_at": observed_at,
        "subject_sha": sha,
        "source_of_truth": ["design-lab/config/capability-index.json",
                            "design-lab/config/capability-status.json"],
        "rule": "state/evidenceLevel are projections of the SSOT; historical evidence never "
                "auto-promotes a capability",
        "capability_count": len(product_rows),
        "capabilities": product_rows,
        "notes": {
            "adapter_level_capabilities": "50 adapter capabilities tracked separately in "
                                          "capability-evidence-current.json",
            "no_status_edited": True,
        },
    }

    last_tree = evindex.get("lastVerifiedTree")
    rows = []
    for record in evindex.get("records", []):
        bound = record.get("tree_sha")
        rows.append({
            "capability_id": record.get("capability_id"),
            "evidence_level": record.get("evidence_level"),
            "artifacts": record.get("artifacts"),
            "bound_tree": bound,
            "runtime_id": record.get("runtime_id"),
            "task_id": record.get("task_id"),
            "binding_vs_current": (
                "HISTORICAL_VALID (bound tree != current HEAD; requires requalification)"
                if bound and bound != sha else
                ("NO_TREE_BINDING" if not bound else "CURRENT_EXACT")
            ),
        })
    adapter_rows = [
        {"capability_id": c.get("capability_id"), "evidence_level": c.get("evidence_level"),
         "declared_level": c.get("declared_level"), "bound_sha": c.get("bound_sha"),
         "supported_current": c.get("supported_current")}
        for c in evcurrent.get("capabilities", [])
    ]
    evidence_payload = {
        "schemaVersion": "design-lab/evidence-index-projection/v1",
        "task_keys": TASK_KEYS,
        "origin": ORIGIN,
        "observed_at": observed_at,
        "subject_sha": sha,
        "source_of_truth": ["design-lab/config/capability-evidence-index.json",
                            "design-lab/config/capability-evidence-current.json"],
        "lastVerifiedTree": last_tree,
        "lastVerifiedTree_vs_head": ("HISTORICAL_VALID" if last_tree and last_tree != sha
                                     else "CURRENT_EXACT"),
        "product_evidence_records": rows,
        "adapter_evidence_records": adapter_rows,
        "counts": {"product_records": len(rows), "adapter_records": len(adapter_rows),
                   "adapter_supported_current": sum(1 for r in adapter_rows if r.get("supported_current"))},
        "notes": {
            "generation_time_is_not_test_time": True,
            "historical_e3_not_current": "creative-toolchain E3 remains bound to a prior tree; "
                                          "requalification required",
        },
    }
    return {"CAPABILITY_INDEX.json": capability_payload, "EVIDENCE_INDEX.json": evidence_payload}


def render(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="compare regenerated content with the committed projections")
    args = parser.parse_args(argv)
    payloads = build(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if args.check:
        drift = []
        for name, payload in payloads.items():
            path = RC / name
            if not path.is_file():
                drift.append(f"{name}: missing")
                continue
            current = json.loads(path.read_text(encoding="utf-8"))
            volatile = {"observed_at"}
            same = {k: v for k, v in current.items() if k not in volatile} == \
                   {k: v for k, v in payload.items() if k not in volatile}
            if not same:
                drift.append(f"{name}: content differs from the authoring sources")
        print("SSOT_PROJECTIONS=" + ("PASS" if not drift else "DRIFT " + "; ".join(drift)))
        return 0 if not drift else 1
    for name, payload in payloads.items():
        (RC / name).write_text(render(payload), encoding="utf-8", newline="\n")
        print(f"wrote reports/current/{name}")
    print("capabilities:", payloads["CAPABILITY_INDEX.json"]["capability_count"],
          "| product evidence:", payloads["EVIDENCE_INDEX.json"]["counts"]["product_records"],
          "| adapter evidence:", payloads["EVIDENCE_INDEX.json"]["counts"]["adapter_records"])
    print("lastVerifiedTree vs HEAD:",
          payloads["EVIDENCE_INDEX.json"]["lastVerifiedTree_vs_head"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
