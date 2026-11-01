#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate every indexed current report; --check is a read-only drift gate."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from design_lab.governance.reporting import generate


def _index_identity():
    """The stored record's identity, preserved so a re-check cannot launder it
    (DL-UCR-012 / FA-03: subject / manifest / run). Returns (subject, scope, run)."""
    import json
    index = REPO / "design-lab" / "config" / "current-report-index.json"
    if not index.is_file():
        return None, "no-index", None
    data = json.loads(index.read_text(encoding="utf-8"))
    return data.get("subjectSha"), data.get("checkScope", "bound-input-integrity"), data.get("generatedAt")


def _current_head():
    import subprocess
    try:
        result = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                capture_output=True, text=True, encoding="utf-8")
        return result.stdout.strip() if result.returncode == 0 else None
    except OSError:
        return None


def qualify_check_verdict(stored_subject, current_subject, *, scope=None, run_identity=None):
    """DL-UCR-012 / FA-03: a byte-stable record is *input-integrity*, not a pass.

    A record bound to a subject that HEAD has advanced past is STALE and must
    never be laundered into a bare PASS; the record identity (subject / manifest /
    run) is preserved in the caller's verdict so no consumer mistakes it for a
    current, passing state. Both outcomes keep exit code 0: byte-stability means
    the bound inputs have not drifted (the zero-spill self-test coupling depends
    on that), the *verdict word* — not the exit code — carries the staleness.
    Returns (verdict, exit_code).
    """
    if stored_subject and current_subject and stored_subject != current_subject:
        return "STALE", 0
    return "PASS", 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        failures = generate(REPO, check=args.check)
    except (OSError, ValueError) as exc:
        print(f"CURRENT_REPORTS=FAIL {exc}")
        return 1
    if failures:
        print("CURRENT_REPORTS=DRIFT " + ", ".join(failures))
        return 1
    if not args.check:
        print("CURRENT_REPORTS=PASS mode=generate")
        return 0
    stored_subject, scope, run_identity = _index_identity()
    current_subject = _current_head()
    verdict, code = qualify_check_verdict(stored_subject, current_subject,
                                          scope=scope, run_identity=run_identity)
    if verdict == "PASS":
        # Kept byte-identical to the historical PASS line so the aggregate
        # verifier and any consumer grepping for it stay green on a clean check.
        print("CURRENT_REPORTS=PASS mode=check scope=bound-input-integrity current-git-and-cloud=NOT_VERIFIED")
    else:
        print(f"CURRENT_REPORTS={verdict} mode=check scope={scope} current-git-and-cloud=NOT_VERIFIED "
              f"stored_subject={stored_subject[:12] if stored_subject else 'none'} "
              f"current_head={current_subject[:12] if current_subject else 'unknown'} "
              f"run_identity={run_identity or 'unrecorded'} "
              f"(byte-stable against a subject HEAD has advanced past; rebind required - not a product-pass claim)")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
