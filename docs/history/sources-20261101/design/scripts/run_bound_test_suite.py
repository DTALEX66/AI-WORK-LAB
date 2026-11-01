#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-H000 — run a test suite and bind the result to an exact subject.

"1351 OK" is not evidence unless the reader can tell *what* was tested. This
runner records, for every run:

* the subject: commit sha, worktree digest, worktree clean flag;
* what ran: order, seed, pattern, selected modules, repeat count;
* the result: tests run, failures, errors, skipped (with the identity and stated
  reason of each skipped case, not just a count), exit code, duration;
* the environment fingerprint.

It writes `.project-local/task-artifacts/test-run/last-run.json`, which is exactly
the record `design_lab.governance.reporting.test_run_binding()` reads, so a
regenerated projection can carry the run id instead of a null.

The order and seed replicate `design-lab/scripts/run_test_isolation.py` so an
isolation gate and a bound run describe the same work.

Usage:
    python scripts/run_bound_test_suite.py --order forward
    python scripts/run_bound_test_suite.py --order reverse
    python scripts/run_bound_test_suite.py --order random --seed 42
    python scripts/run_bound_test_suite.py --modules test_asset_store --repeat 20
    python scripts/run_bound_test_suite.py --pattern 'test_creative_*.py'
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "design-lab/tests"
RECORD_DIR = REPO / ".project-local/task-artifacts/test-run"
RECORD = RECORD_DIR / "last-run.json"
HISTORY = RECORD_DIR / "history.jsonl"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-H000"
sys.path.insert(0, str(REPO / "src"))


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def worktree_digest() -> str:
    # Unified content-bound digest (DL-AUDIT-20260914-01): bind every change to
    # its SHA-256 content rather than the porcelain status string alone.
    from design_lab.governance.worktree_digest import worktree_digest as unified
    return unified(REPO)


def discover(pattern: str):
    return unittest.defaultTestLoader.discover(start_dir=str(TESTS), pattern=pattern,
                                               top_level_dir=str(TESTS))


def flatten(suite) -> list:
    tests = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            tests.extend(flatten(item))
        else:
            tests.append(item)
    return tests


def order_tests(tests: list, order: str, seed: int) -> list:
    if order == "forward":
        return tests
    if order == "reverse":
        return list(reversed(tests))
    shuffled = list(tests)
    random.Random(seed).shuffle(shuffled)
    return shuffled


def skip_details(result, limit: int = 40) -> tuple:
    """Which cases did not run, plus the reason the case itself stated.

    A bare `skipped=4` is a measurement of this runner's scope, not of the world: it
    cannot distinguish "four host probes found no host" from "four real checks stopped
    being collected". The reason comes from the test's own skip decorator, so the record
    never states a cause the code does not know, and a list longer than `limit` reports
    that it was cut instead of letting the cut read as the whole truth.
    """
    entries = [{"case": str(case), "case_id": case.id(), "reason": str(reason)}
               for case, reason in result.skipped]
    return entries[:limit], len(entries) > limit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order", choices=("forward", "reverse", "random"), default="forward")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--modules", action="append", nargs="+", default=None,
                        metavar="MODULE",
                        help="critical test module(s); repeat the flag or list several names "
                             "after one flag; both forms are equivalent")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--label")
    args = parser.parse_args(argv)
    # --modules is append + nargs="+": the parsed value is a list of lists.
    # Flatten to a single list of module names so downstream consumers (the
    # "modules" history field and the critical-set comparison in the gate
    # report) always see a flat list.
    if args.modules is not None:
        flat: list = []
        for group in args.modules:
            if isinstance(group, list):
                flat.extend(group)
            else:  # defensive: a bare string if the flag form changes
                flat.append(group)
        args.modules = flat

    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    tests = flatten(discover(args.pattern))
    if args.modules:
        wanted = set(args.modules)
        tests = [t for t in tests if any(name in type(t).__module__ for name in wanted)
                 or any(name in str(t) for name in wanted)]
    if not tests:
        print("BOUND_TEST_RUN=FAIL no tests selected")
        return 2
    selected = []
    for _ in range(max(1, args.repeat)):
        selected.extend(order_tests(tests, args.order, args.seed))

    suite = unittest.TestSuite(selected)
    # DL-AUDIT-20260914-07: bind the exact test *list* the run covers. The
    # manifest hash is the SHA-256 of the ordered test IDs (module::class::name),
    # so a run proves exactly which cases, in which order, on which platform and
    # seed — reordering, adding or removing a case changes the hash, and a Linux
    # result can never be read as a Windows host result because the platform is
    # recorded alongside it.
    manifest = []
    for index, item in enumerate(selected):
        identifier = item.id()
        if args.repeat > 1:
            identifier = f"{index % len(tests)}::{identifier}"
        manifest.append(identifier)
    manifest_hash = "sha256:" + hashlib.sha256("\n".join(manifest).encode("utf-8")).hexdigest()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    skips, skips_truncated = skip_details(result)
    duration = round(time.monotonic() - clock, 3)
    run_id = (f"testrun-{started.strftime('%Y%m%dT%H%M%SZ')}-{args.order}"
              f"{'' if not args.modules else '-repeat'}-{worktree_digest()[7:19]}")
    record = {
        "schemaVersion": "design-lab/bound-test-run/v1",
        "task_key": TASK_KEY,
        "run_id": run_id,
        "command": " ".join(["python", "scripts/run_bound_test_suite.py", *sys.argv[1:]]),
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_seconds": duration,
        "result": "OK" if result.wasSuccessful() else "FAILED",
        "exit_code": 0 if result.wasSuccessful() else 1,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "order": args.order,
        "seed": args.seed if args.order == "random" else None,
        "pattern": args.pattern,
        "modules": args.modules,
        "repeat": args.repeat,
        "selected_cases": len(selected),
        "test_manifest_sha256": manifest_hash,
        "test_manifest_scope": "ordered test IDs (module::class::name), one hash covers the exact "
                               "cases and their order; a different list, order or repeat count "
                               "produces a different hash",
        "platform_binding": "the environment_fingerprint records the platform that produced this "
                            "run; a result recorded on another platform is a different record and "
                            "never substitutes for this one",
        "subject": {"commit_sha": git("rev-parse", "HEAD"),
                    "worktree_digest": worktree_digest(),
                    "worktree_clean": git("status", "--porcelain=v1") == "",
                    "branch": git("rev-parse", "--abbrev-ref", "HEAD")},
        "environment_fingerprint": {"python": platform.python_version(),
                                    "platform": platform.platform(),
                                    "machine": platform.machine()},
        "what_this_proves": "the named cases, in this exact order, passed on this platform "
                            "(see platform_binding) on this exact subject; it proves nothing about "
                            "a different commit, a dirty tree that has moved on, or a different "
                            "platform — a Linux record never stands in for a Windows host result",
        "failures_detail": [str(test) for test, _ in result.failures][:20],
        "errors_detail": [str(test) for test, _ in result.errors][:20],
        "skipped_detail": skips,
        "skipped_detail_truncated": skips_truncated,
    }
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
    with HISTORY.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({k: record[k] for k in
                                 ("run_id", "result", "tests_run", "failures", "errors", "skipped",
                                  "order", "seed", "pattern", "modules", "repeat", "duration_seconds",
                                  "finished_at")}, ensure_ascii=False) + "\n")
    print(f"BOUND_TEST_RUN={record['result']} run_id={run_id} tests={result.testsRun} "
          f"failures={record['failures']} errors={record['errors']} skipped={record['skipped']} "
          f"order={args.order} subject={record['subject']['commit_sha'][:12]} "
          f"clean={record['subject']['worktree_clean']} in {duration}s")
    for entry in skips:
        print(f"SKIP {entry['case_id']} :: {entry['reason']}")
    if record["skipped"] and not skips:
        # The count was recorded but no case was. That is this runner failing to read
        # its own input, and a green suite must not be allowed to hide it.
        print("BOUND_SKIP_IDENTITY=DEFECT skipped>0 was recorded but no case identity "
              "came out of the result; the count alone is not evidence")
        return 3
    if skips_truncated:
        print(f"SKIP_DETAIL_TRUNCATED identities shown={len(skips)} of skipped={record['skipped']}")
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
