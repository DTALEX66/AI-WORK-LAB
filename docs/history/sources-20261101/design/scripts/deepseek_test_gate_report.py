#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-H010 — Full Test Gate report.

Reads the bound-test-suite run records the harness itself wrote and turns the runs
that used the declared critical module set into an artifact. Nothing here is retyped:
every number comes from `.project-local/task-artifacts/test-run/history.jsonl`.

The executed scope is declared rather than implied. The same three orders over the
entire discovered suite (1392 tests) are NOT executed and are recorded as deferred
with the measured reason, because a gate that reports a scope it did not run is worse
than one that names the scope it did.

Writes reports/current/DEEPSEEK-FINAL-TEST-GATE.json.

``--out`` redirects the writer form. The authority chain points it at its own ignored record root:
a verification run that rewrites a tracked projection makes "the chain is check-only" true only on
the machines that happen to have the gitignored history, which is how a green here became a red
assertion on every clean clone (measured 2026-10-13). ``--check`` deliberately ignores ``--out``:
it judges the committed record, and being able to point it elsewhere would let the check and the
record be different files.

`--check` does not re-run anything and does not need this machine's history. Measured on
2026-10-09 in two trees of `d6ba107f`: the old form compared the whole document against a
recompute from `.project-local/task-artifacts/test-run/history.jsonl`, which is gitignored, so a
clean checkout found zero matching runs and reported DRIFT against a committed PASS -- the green
described one disk. What is checkable everywhere is the record's own coherence and the repository:
the declared 16 modules exist as versioned test files, the recorded orders account for the recorded
requirements, the verdict follows from the recorded counts, failures and repetition, and the
full-suite deferral still says what it defers and why. The local history is then reported as
machine state (MATCHES_LOCAL_HISTORY / DIFFERS_FROM_LOCAL_HISTORY / HISTORY_ABSENT), so a machine
whose runs moved is visible without being able to convict a machine that has no runs at all.
Executing the critical set is the authority chain's job (`scripts/verify_authority_gates.py`),
which runs it where history is absent; this script never runs tests.

Usage:
    python scripts/deepseek_test_gate_report.py [--check] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current/DEEPSEEK-FINAL-TEST-GATE.json"
HISTORY = REPO / ".project-local/task-artifacts/test-run/history.jsonl"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-H010"
# The critical set: modules that hold cross-test state, where order dependence and
# state leakage can actually show up.
CRITICAL_MODULES = [
    "test_asset_store", "test_creative_job", "test_creative_ledgers",
    "test_creative_lineage", "test_creative_migration", "test_creative_version_guard",
    "test_creative_f030_f040", "test_creative_session_link", "test_job_store",
    "test_runtime_attempt_safety", "test_runtime_asset_safety",
    "test_runtime_explicit_project", "test_assurance_qa_plane", "test_assurance_jury",
    "test_bundle_store", "test_operation_coordinator",
]
FULL_SUITE_DEFERRED = {
    "scope": "the same three orders over the entire discovered suite (pattern test_*.py)",
    "state": "DEFERRED",
    "measured_reason": "one pass of the full pattern costs roughly 25 minutes or more against "
                       "7.6 seconds for the critical set, so three orders plus repetition is "
                       "75+ minutes of continuous load, and that exact load coincided with the "
                       "host kernel bugcheck 0x4E (PFN_LIST_CORRUPT) at 2026-09-14T01:14:34 that "
                       "this run is still diagnosing with the owner",
    "not_a_claim": "this is a load decision; it is not evidence that the full-suite orders pass",
}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def recorded_runs() -> list:
    if not HISTORY.is_file():
        return []
    runs = []
    for line in HISTORY.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return runs


def choose(runs: list) -> list:
    """The runs that used exactly the declared critical set, newest first."""
    wanted = set(CRITICAL_MODULES)
    matches = [r for r in runs if set(r.get("modules") or []) == wanted]
    return sorted(matches, key=lambda r: r.get("finished_at") or "", reverse=True)


# The critical set is a claim about the repository, so it is checked against the repository:
# every named module must exist as versioned content. This is the machine-independent half of
# the record, and it is the half that rots silently -- a renamed or deleted module would leave
# the declared scope naming something no checkout contains.
TESTS_DIR = "design-lab/tests"
BOUND_SUITE_RUNNER = "scripts/run_bound_test_suite.py"
ORDER_REQUIREMENT_KEYS = {"deterministic_forward": "forward", "reverse": "reverse",
                          "randomized_seeded": "random"}
VOLATILE_FIELDS = ("generated_at", "subject_sha")


def tracked_paths() -> set:
    result = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    return set((result.stdout or "").splitlines())


def record_findings(record: dict) -> list:
    """What the record may claim, judged from the record and the repository alone.

    The runs themselves live in a gitignored history file, so their numbers cannot be
    re-derived on another clone. Everything below can: the declared scope against versioned
    files, and the verdict against the numbers the record itself publishes. A record whose
    verdict does not follow from its own rows is a lie about a measurement, not a measurement.
    """
    findings = []
    tracked = tracked_paths()
    scope = record.get("executed_scope") or {}
    modules = scope.get("modules") or []
    if not modules:
        findings.append("TESTGATE-SCOPE-EMPTY the record declares no module set, so its "
                        "verdict covers nothing")
    untracked = [name for name in modules if f"{TESTS_DIR}/{name}.py" not in tracked]
    if untracked:
        findings.append("TESTGATE-SCOPE-MODULE-UNTRACKED " + ", ".join(untracked) +
                        " -- the declared critical set names a test module that is not in "
                        "the repository, so this record's scope no longer exists")
    if scope.get("module_count") != len(modules):
        findings.append(f"TESTGATE-SCOPE-COUNT module_count={scope.get('module_count')} "
                        f"but {len(modules)} modules are listed")
    if BOUND_SUITE_RUNNER not in tracked:
        findings.append(f"TESTGATE-RUNNER-UNTRACKED {BOUND_SUITE_RUNNER} is named as the "
                        "writer of the source history but is not versioned")

    requirements = record.get("requirements") or {}
    orders = {ORDER_REQUIREMENT_KEYS[key]: value for key, value in requirements.items()
              if key in ORDER_REQUIREMENT_KEYS and isinstance(value, dict)}
    independence = record.get("order_independence") or {}
    recorded = sorted(independence.get("orders_recorded") or [])
    if recorded != sorted(orders):
        findings.append(f"TESTGATE-ORDERS-MISMATCH order_independence names {recorded} "
                        f"while requirements carry {sorted(orders)}")
    counts = {order: row.get("tests") for order, row in orders.items()}
    identical = len(set(counts.values())) <= 1
    zero_failures = all(row.get("failures") == 0 and row.get("errors") == 0
                        for row in orders.values())
    if bool(independence.get("identical_counts")) != identical:
        findings.append(f"TESTGATE-COUNTS-CLAIM identical_counts={independence.get('identical_counts')} "
                        f"but the recorded per-order test counts are {counts}")
    if bool(independence.get("zero_failures_in_every_order")) != zero_failures:
        findings.append("TESTGATE-FAILURE-CLAIM zero_failures_in_every_order="
                        f"{independence.get('zero_failures_in_every_order')} while the recorded "
                        f"rows are " + ", ".join(f"{order}:f{row.get('failures')}/e{row.get('errors')}"
                                                 for order, row in sorted(orders.items())))
    expected_independence = (len(orders) >= 3 and identical and zero_failures)
    expected = {"verdict": "ORDER_INDEPENDENT" if expected_independence else "INSUFFICIENT_EVIDENCE"}
    if independence.get("verdict") != expected["verdict"]:
        findings.append(f"TESTGATE-ORDER-VERDICT record says {independence.get('verdict')!r} but "
                        f"its own rows support {expected['verdict']!r}")

    per_order = scope.get("tests_per_order")
    if counts and any(value != per_order for value in counts.values()):
        findings.append(f"TESTGATE-TESTS-PER-ORDER executed_scope.tests_per_order={per_order} "
                        f"while the recorded orders ran {sorted(set(counts.values()))} -- the "
                        "scope figure was typed rather than taken from the runs")

    repetition = requirements.get("critical_module_repetition")
    verdict = ("PASS" if expected_independence and isinstance(repetition, dict)
               and repetition.get("failures") == 0 and repetition.get("errors") == 0 else "FAIL")
    if record.get("verdict") != verdict:
        findings.append(f"TESTGATE-VERDICT-NOT-DERIVED the record says {record.get('verdict')!r} "
                        f"but its own orders, counts, failures and repetition support {verdict!r}")

    deferred = record.get("deferred") or {}
    if deferred.get("state") != "DEFERRED":
        findings.append(f"TESTGATE-DEFERRAL-LOST state={deferred.get('state')!r}; the 1392-test "
                        "full-suite orders are not evidence and must not read as settled")
    for field in ("scope", "measured_reason", "not_a_claim"):
        if not deferred.get(field):
            findings.append(f"TESTGATE-DEFERRAL-INCOMPLETE deferred.{field} is empty, so the "
                            "deferral no longer says what it covers or why")
    source = str(record.get("source") or "")
    if BOUND_SUITE_RUNNER.split("/")[-1] not in source:
        findings.append(f"TESTGATE-SOURCE-CLAIM source={source!r} does not name the runner that "
                        "writes the history it reports")
    return findings


def history_agreement(stored: dict) -> tuple:
    """Machine state: recompute from this machine's history and say how it relates."""
    if not HISTORY.is_file():
        return "HISTORY_ABSENT", 0
    document = build_document()
    comparable = lambda item: {key: value for key, value in item.items()
                               if key not in VOLATILE_FIELDS}
    if comparable(stored) == comparable(document):
        return "MATCHES_LOCAL_HISTORY", len(choose(recorded_runs()))
    return "DIFFERS_FROM_LOCAL_HISTORY", len(choose(recorded_runs()))


def build_document() -> dict:
    matches = choose(recorded_runs())
    by_order, repetition = {}, None
    for run in matches:
        if (run.get("repeat") or 1) > 1 and repetition is None:
            repetition = run
        elif (run.get("repeat") or 1) == 1 and run["order"] not in by_order:
            by_order[run["order"]] = run
    orders = {order: {"run_id": run["run_id"], "tests": run["tests_run"],
                      "failures": run["failures"], "errors": run["errors"],
                      "skipped": run["skipped"], "duration_seconds": run["duration_seconds"],
                      "seed": run.get("seed"), "result": run.get("result"),
                      "finished_at": run.get("finished_at")}
              for order, run in by_order.items()}
    counts = {key: value["tests"] for key, value in orders.items()}
    order_independent = (len(orders) >= 3 and len(set(counts.values())) == 1
                         and all(v["failures"] == 0 and v["errors"] == 0 for v in orders.values()))
    distinct_counts = sorted(set(counts.values()))
    return {
        "schemaVersion": "design-lab/final-test-gate/v2",
        "task_key": TASK_KEY,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD"),
        "verdict_rule": "the numbers below come from this machine's bound-test history, which is "
                        "gitignored, so --check does not re-derive them here. What --check judges "
                        "is answerable from tracked state and from the record's own rows: the "
                        "declared module set exists as versioned test files, the recorded orders "
                        "account for the requirements, the verdict follows from the recorded "
                        "counts/failures/repetition, and the full-suite deferral is still declared.",
        "source": ".project-local/task-artifacts/test-run/history.jsonl (written by "
                  "scripts/run_bound_test_suite.py, not retyped here)",
        "executed_scope": {
            "kind": "declared critical module set",
            "why": "cross-test state leakage and order dependence can only show up where state "
                   "is held, so the set is the stateful and contract-holding modules",
            "modules": CRITICAL_MODULES,
            "module_count": len(CRITICAL_MODULES),
            # Derived from the runs rather than typed: a hand-copied 220 would keep saying the
            # scope is intact after the set stopped producing that number.
            "tests_per_order": distinct_counts[0] if len(distinct_counts) == 1 else None,
            "tests_per_order_state": "IDENTICAL_ACROSS_ORDERS" if len(distinct_counts) == 1
                                     else "ORDERS_DIFFER",
        },
        "requirements": {
            "deterministic_forward": orders.get("forward"),
            "reverse": orders.get("reverse"),
            "randomized_seeded": orders.get("random"),
            "critical_module_repetition": (
                {"run_id": repetition["run_id"], "tests": repetition["tests_run"],
                 "repeat": repetition["repeat"], "failures": repetition["failures"],
                 "errors": repetition["errors"], "duration_seconds": repetition["duration_seconds"],
                 "result": repetition.get("result"), "finished_at": repetition.get("finished_at")}
                if repetition else None),
        },
        "order_independence": {
            "orders_recorded": sorted(orders),
            "test_counts": counts,
            "identical_counts": len(set(counts.values())) <= 1,
            "zero_failures_in_every_order": all(v["failures"] == 0 and v["errors"] == 0
                                                for v in orders.values()),
            "verdict": "ORDER_INDEPENDENT" if order_independent else "INSUFFICIENT_EVIDENCE",
        },
        "deferred": FULL_SUITE_DEFERRED,
        "verdict": ("PASS" if order_independent
                    and repetition and repetition["failures"] == 0 and repetition["errors"] == 0
                    else "FAIL"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", default=str(OUT),
                        help="writer form only: where to put the record (default "
                             "reports/current/DEEPSEEK-FINAL-TEST-GATE.json)")
    args = parser.parse_args(argv)
    if args.check:
        if args.out != str(OUT):
            parser.error("--check judges the committed record; --out belongs to the writer form")
        if not OUT.is_file():
            print("TEST_GATE=FAIL missing " + OUT.name)
            return 1
        try:
            stored = json.loads(OUT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"TEST_GATE=FAIL unreadable {OUT.name} {type(exc).__name__}")
            return 1
        findings = record_findings(stored)
        state, runs = history_agreement(stored)
        for finding in findings:
            print("TEST_GATE=FINDING " + finding)
        # The local history is reported, never required: it is gitignored, so its absence on a
        # clone says nothing about whether the recorded critical-set runs happened.
        print(f"TEST_GATE={'PASS' if not findings else 'FAIL'} "
              f"modules={len((stored.get('executed_scope') or {}).get('modules') or [])} "
              f"verdict={stored.get('verdict')} findings={len(findings)} "
              f"local_history={state} matching_runs={runs}")
        return 0 if not findings else 1
    document = build_document()
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8", newline="\n")
    orders = document["order_independence"]
    print(f"TEST_GATE={document['verdict']} orders={orders['orders_recorded']} "
          f"tests_per_order={document['executed_scope']['tests_per_order']} "
          f"deferred={FULL_SUITE_DEFERRED['state']} wrote={destination}")
    return 0 if document["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
