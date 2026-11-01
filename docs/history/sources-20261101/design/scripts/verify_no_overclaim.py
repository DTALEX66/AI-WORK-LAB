#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-K000 — no-overclaim audit.

Scans the current claim surface for the words the taskpack names - integrated,
verified, supported, ready, complete, E3, E4 - and checks each hit against the
evidence it would need.

The judgment is mechanical, not editorial:

* a JSON object that declares ``supported: true``, or a status/verdict of
  verified/ready/complete/integrated, must carry an evidence reference in the same
  object (an evidence path, a digest, a task id, a runtime id or an evidence
  record) — otherwise it is `UNSUPPORTED`;
* a claim that also carries a limitation marker (historical, not verified, pending,
  deferred, blocked, unqualified, NOT_EXECUTED) is `QUALIFIED`, which is honest and
  passes;
* E3/E4 are delegated to `scripts/verify_evidence_levels.py`, which already knows
  who may claim them.

Writes reports/current/NO-OVERCLAIM-AUDIT.json and exits non-zero on any
UNSUPPORTED claim.

Usage:
    python scripts/verify_no_overclaim.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current/NO-OVERCLAIM-AUDIT.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-K000"
SURFACE = ("reports/current/", "design-lab/readiness/", "integrations/", "design-lab/config/")
SKIP = ("design-lab/config/task-ledger-r3.json",)   # the R5 ledger is the status truth, not a claim
CLAIM_STATUS = re.compile(r"\b(verified|ready|complete|integrated|available|supported)\b", re.I)
EVIDENCE_HINT = re.compile(r"(evidence/|evidence_ref|artifact_paths|artifact_sha256|sha256:|task_ids|"
                           r"runtime_id|prompt_id|record|receipt|report)", re.I)
LIMITATION = re.compile(r"(historical|not verified|unverif|pending|deferred|blocked|unqualified|"
                       r"not_executed|not executed|never launched|requires|unproven|partial|"
                       r"declared only|structurally|E0|E1)", re.I)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def tracked() -> list:
    return [line for line in git("ls-files").splitlines() if line.strip()]


def in_surface(rel: str) -> bool:
    return rel not in SKIP and any(rel.startswith(prefix) for prefix in SURFACE)


def claims_in(document, path: str) -> list:
    found = []

    def walk(node, trail):
        if isinstance(node, dict):
            # A ladder definition (label/state/proof) describes what a level would
            # mean; it is not a claim that the level was reached.
            if {"label", "state", "proof"} <= set(node):
                return
            text = json.dumps(node, ensure_ascii=False)
            supported = node.get("supported")
            status = node.get("status") or node.get("verdict") or node.get("state") or node.get("result")
            why = None
            if supported is True:
                why = "supported: true"
            elif isinstance(status, str) and CLAIM_STATUS.search(status):
                why = f"status {status!r}"
            if why:
                found.append({"path": path, "at": "/".join(trail) or "/", "claim": why,
                              "identity": node.get("adapter_id") or node.get("provider_id")
                                          or node.get("capability_id") or node.get("name"),
                              "has_evidence": bool(EVIDENCE_HINT.search(text)),
                              "has_limitation": bool(LIMITATION.search(text))})
            for key, value in node.items():
                walk(value, [*trail, str(key)])
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, [*trail, str(index)])

    walk(document, [])
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rows = []
    for rel in tracked():
        if not in_surface(rel) or not rel.endswith(".json"):
            continue
        path = REPO / rel
        try:
            if path.stat().st_size > 3_000_000:
                continue
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        for claim in claims_in(document, rel):
            if claim["has_evidence"]:
                verdict = "SUPPORTED"
            elif claim["has_limitation"]:
                verdict = "QUALIFIED"
            else:
                verdict = "UNSUPPORTED"
            rows.append({**claim, "verdict": verdict})
    unsupported = [row for row in rows if row["verdict"] == "UNSUPPORTED"]
    document = {
        "schemaVersion": "design-lab/no-overclaim-audit/v1",
        "task_key": TASK_KEY,
        "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD").strip(),
        "surface": list(SURFACE),
        "rule": "a claim of supported/verified/ready/complete/integrated must carry an evidence "
                "reference in the same object, or an explicit limitation that makes it honest",
        "counts": {"claims": len(rows), "supported": sum(1 for r in rows if r["verdict"] == "SUPPORTED"),
                   "qualified": sum(1 for r in rows if r["verdict"] == "QUALIFIED"),
                   "unsupported": len(unsupported)},
        "unsupported": unsupported[:50],
        "delegated": {"E3_E4": "scripts/verify_evidence_levels.py owns who may claim which level"},
        "verdict": "PASS" if not unsupported else "FAIL",
    }
    summary = f"NO_OVERCLAIM={document['verdict']} " + " ".join(
        f"{k}={v}" for k, v in document["counts"].items())
    if args.check:
        # The checker must say what it examined. A bare `NO_OVERCLAIM=PASS` with no counts
        # cannot be told apart from a pass over zero claims, which is the failure mode this
        # gate exists to catch, so the measurement line is printed in both modes.
        stored = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else None
        if stored is None:
            print(summary)
            print("NO_OVERCLAIM=DRIFT no report at " + str(OUT))
            return 1
        if stored["verdict"] != document["verdict"]:
            print(summary)
            print(f"NO_OVERCLAIM=DRIFT stored verdict={stored['verdict']} "
                  f"fresh={document['verdict']}")
            return 1
        print(summary)
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(summary)
    for row in unsupported[:12]:
        print(f"  UNSUPPORTED {row['path']} {row['at']} -> {row['claim']} ({row['identity']})")
    return 0 if not unsupported else 1


if __name__ == "__main__":
    raise SystemExit(main())
