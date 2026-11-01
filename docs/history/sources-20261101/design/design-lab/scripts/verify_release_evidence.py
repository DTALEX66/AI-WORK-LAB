#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Release evidence SHA readback + validation (ODA4-0107).

Validates a release-evidence record: local branch/HEAD/tree, remote SHA
readback, and CI binding. Rejects claims where the recorded CI/head differs
from the actual current tree (a prior green CI on another SHA is NOT evidence).

Usage:
    python design-lab/scripts/verify_release_evidence.py [evidence.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "schemas" / "release-evidence.schema.json"


def git(args: list[str]) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def validate_contract(ev: object) -> list[str]:
    """Validate the machine-readable contract before checking live Git facts."""
    try:
        import jsonschema
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(ev),
            key=lambda error: list(error.path),
        )
    except ImportError as exc:
        return [f"schema validation unavailable: jsonschema is required ({exc})"]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"release-evidence schema unreadable: {exc}"]

    failures = [f"schema: {error.message}" for error in errors]
    if failures:
        return failures
    record = ev if isinstance(ev, dict) else {}
    if record.get("state") != "PASS":
        failures.append(f"release evidence state must be PASS, got {record.get('state')!r}")
    if record.get("worktree") != "clean":
        failures.append(f"release evidence worktree must be clean, got {record.get('worktree')!r}")
    ci = record.get("ci") if isinstance(record.get("ci"), dict) else {}
    if ci.get("conclusion") != "success":
        failures.append(f"CI conclusion must be success, got {ci.get('conclusion')!r}")
    read_back = record.get("read_back") if isinstance(record.get("read_back"), dict) else {}
    if read_back.get("verified") is not True:
        failures.append("remote readback must be explicitly verified=true")
    return failures


REQUALIFICATION_FAILURE = (
    "requalified capability cannot certify {level} on the current tree "
    "(effective floor E1); requiresRequalification=true in capability-evidence-index"
)


def load_effective_evidence_module():
    """Load the sibling effective_evidence.py (scripts/ is not a package)."""
    import importlib.util

    path = Path(__file__).resolve().parent / "effective_evidence.py"
    spec = importlib.util.spec_from_file_location("effective_evidence", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load effective_evidence from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def requalification_failures(ev: object, index: object, module) -> list[str]:
    """P1-B: a requalified capability cannot certify above its effective floor.

    ``requiresRequalification=true`` in capability-evidence-index.json means the
    capability's runtime evidence is bound to another tree, so on the current tree
    it keeps only its structural ceiling (E1). A release claim at E2-E5 for that
    capability is therefore not evidence for this checkout.
    """
    if not isinstance(ev, dict):
        return []
    level = ev.get("evidence_level")
    if ev.get("capability_id") not in module.requalified(index):
        return []
    if module.LEVEL.get(level, -1) > module.LEVEL["E1"]:
        return [REQUALIFICATION_FAILURE.format(level=level)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", nargs="?", help="release-evidence JSON file; omit to print schema usage")
    args = parser.parse_args()

    if not args.evidence:
        print("USAGE: verify_release_evidence.py <release-evidence.json>")
        print("Recorded head/tree must match the live checkout; remote readback is required.")
        print("RELEASE_EVIDENCE=FAIL")
        return 2

    try:
        ev = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"RELEASE_EVIDENCE=FAIL\n - evidence unreadable: {exc}")
        return 1

    contract_failures = validate_contract(ev)
    if contract_failures:
        print("RELEASE_EVIDENCE=FAIL")
        for failure in contract_failures:
            print(" -", failure)
        return 1

    # Local facts
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    head = git(["rev-parse", "HEAD"])
    tree = git(["rev-parse", "HEAD^{tree}"])
    worktree = git(["status", "--porcelain"])

    print(f"local branch={branch}")
    print(f"local head={head}")
    print(f"local tree={tree}")
    print(f"worktree={'clean' if not worktree else 'dirty'}")

    failures = []
    if ev.get("branch") != branch:
        failures.append(f"branch mismatch: recorded {ev.get('branch')} != live {branch}")
    if ev.get("head_sha") != head:
        failures.append(f"head mismatch: recorded {ev.get('head_sha')} != live {head}")
    if ev.get("tree_sha") != tree:
        failures.append(f"tree mismatch: recorded {ev.get('tree_sha')} != live {tree}")
    if ev.get("worktree") != ("clean" if not worktree else "dirty"):
        failures.append("worktree status mismatch")

    # CI binding: a green CI recorded against a DIFFERENT head is not evidence.
    ci_head = ((ev.get("ci") or {}).get("head_sha") or "").lower()
    if ci_head and ci_head != ev.get("head_sha", "").lower():
        failures.append("CI head_sha != evidence head_sha (prior green CI reused illegally)")

    # P1-B: historical evidence for a requalified capability never certifies the
    # current tree above its effective floor (E1).
    try:
        effective_module = load_effective_evidence_module()
        evidence_index = effective_module.load_index(REPO.parent)
    except (ImportError, OSError, UnicodeError, ValueError) as exc:
        failures.append(f"capability evidence index unreadable for requalification check: {exc}")
    else:
        failures.extend(requalification_failures(ev, evidence_index, effective_module))

    # Remote readback
    remote = (ev.get("read_back") or {}).get("remote_sha")
    if remote:
        try:
            origin_head = git(["rev-parse", f"origin/{ev.get('read_back', {}).get('remote_branch', 'main')}"])
            print(f"remote {ev.get('read_back', {}).get('remote_branch')}={origin_head}")
            if origin_head != remote:
                failures.append(f"remote readback mismatch: recorded {remote} != origin {origin_head}")
            else:
                print("remote readback verified")
        except RuntimeError as e:
            failures.append(f"remote readback unavailable: {e}")
    else:
        failures.append("no remote readback provided (cannot verify release)")

    if failures:
        print("\nRELEASE_EVIDENCE=FAIL")
        for f in failures:
            print(" -", f)
        return 1

    print("\nRELEASE_EVIDENCE=OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
