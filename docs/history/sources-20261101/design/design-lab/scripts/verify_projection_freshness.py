#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Every tracked projection that can be re-checked must agree with its own record, on a clone.

Why this gate exists. Each generator that writes a tracked projection also has a read-only
``--check`` form, and nothing ran all of them together. Two defects came out of that in
2026-10-09: ``deepseek_language_inventory.py --check`` compared the committed per-language file
counts against the live tree, so it had been red for weeks and nobody saw it (no workflow step, no
aggregate entry, no test, and its name matches no reachability pattern -- a permanently failing gate
that is also an orphan), and three further checks pass on the machine that generated their record
and fail on a clean checkout, which means their green proves nothing about the repository.

So this gate runs each entry's own read-only form and reports the verdict lines, and the entry list
is exactly the set measured to pass in **both** trees. All three of those machine-dependent checks
have been fixed and moved into ENTRIES: RECOVERY-SAFETY by archiving its destructive-operation
receipts from their single tracked copy in the preserved evidence bundle so the verdict reads versioned bytes
instead of this machine's gitignored ``.project-local``; DEEPSEEK-FINAL-TEST-GATE by judging the
record against versioned test files and its own rows instead of re-deriving runs from a gitignored
bound-test history; and SPILL-CENSUS by judging the record against the path rules, git and its own
arithmetic while reporting the live census as machine state. EXCLUDED is therefore empty and is
kept as a named register rather than deleted: it is the place an unverifiable projection has to go
and say why, and ``test_projection_freshness.py`` pins that it holds nothing. (Dated correction: the
first version of this docstring said "four excluded entries" while the table held three -- a number
written from a remembered list rather than from the bytes, which is the same class of defect the
gate exists to catch.)

Read-only by construction: only the ``--check``/``--self-test`` argv appears in ENTRIES, and
``test_projection_freshness.py`` refuses an entry whose argument list is empty (that is the writer
form -- the defect fixed one commit before this gate existed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# (record, generator, argv). The argv must be a read-only form; see the module docstring.
ENTRIES = [
    ("reports/current/FOUNDATION-AUDIT.json", "scripts/deepseek_foundation_audit.py", ["--check"]),
    ("reports/current/LANGUAGE-INVENTORY.json", "scripts/deepseek_language_inventory.py",
     ["--check"]),
    ("reports/current/DEEPSEEK-REGISTRY-SSOT.json", "scripts/deepseek_registry_ssot.py",
     ["--check"]),
    ("design-lab/config/rights-registry.json", "scripts/generate_rights_registry.py", ["--check"]),
    ("reports/current/REPO-CLASSIFICATION.json", "scripts/classify_repo.py", ["--check"]),
    ("reports/current/CONTRACT-GRAPH.json", "scripts/verify_contract_graph.py", ["--check"]),
    ("reports/current/EVIDENCE-LEVEL-AUDIT.json", "scripts/verify_evidence_levels.py",
     ["--check"]),
    ("reports/current/LANGUAGE-BOUNDARY-SCAN.json", "scripts/verify_language_boundary.py",
     ["--check"]),
    ("reports/current/NO-OVERCLAIM-AUDIT.json", "scripts/verify_no_overclaim.py", ["--check"]),
    ("reports/current/SUPPLY-CHAIN-REPORT.json", "scripts/verify_supply_chain.py", ["--check"]),
    ("reports/current/MACHINE_INVENTORY.json", "scripts/generate_machine_inventory.py",
     ["--check"]),
    # Left the register below on 2026-10-09: the three destructive-operation receipts it audits
    # are read from their single tracked copy under docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/session, so the verdict no longer
    # depends on this machine's gitignored .project-local copies.
    ("reports/current/RECOVERY-SAFETY.json", "scripts/verify_recovery_safety.py", ["--check"]),
    # Also left the register on 2026-10-09: --check now judges the record against the repository
    # (the declared module set as versioned test files) and against its own rows, instead of
    # re-deriving the runs from this machine's gitignored bound-test history.
    ("reports/current/DEEPSEEK-FINAL-TEST-GATE.json", "scripts/deepseek_test_gate_report.py",
     ["--check"]),
    # The last of the three. Its --check used to sum .hermes bytes off this disk; it now judges
    # the record against the path rules that produced it, against git, and against its own
    # arithmetic, and reports the live census as machine state.
    ("reports/current/SPILL-CENSUS.json", "scripts/deepseek_spill_census.py", ["--check"]),
]

# Excluded, each with the measured reason. These stay visible here precisely so that "the gate is
# green" never reads as "every projection was verified". The set only shrinks by fixing a check;
# test_projection_freshness.py names the members, so one cannot join silently.
# Closed on 2026-10-09: all three machine-dependent checks now answer from tracked state. An
# exclusion may only come back by naming its measured cause here and in that test.
EXCLUDED: dict = {}

READ_ONLY_FLAGS = ("--check", "--self-test", "--verify")

# Read-only forms that audit versioned records rather than re-deriving a projection: the same
# discipline, a different subject. `deepseek_hermes_migration.py --verify` is here because it had
# been FAILING for weeks in both trees and nothing invoked it -- its complaint was half real (the
# archive is intact) and half stale (one archived object is deleted in a tracked prune record).
# Wiring it here means a regression in either record is seen instead of accumulated.
RECEIPT_CHECKS = [
    ("scripts/deepseek_hermes_migration.py", ["--verify"]),
    # Reached today only as a bare name in the aggregate's SCRIPTS, i.e. whatever its default mode
    # happens to be. Naming --check here gives it the same per-child write guard as every other
    # read-only form, instead of trusting that the default is still the checker.
    ("design-lab/scripts/verify_vendor_manifests.py", ["--check"]),
    # Measured 2026-10-09 in a clean tree: 0-1s, PASS, reads tracked text only.
    ("scripts/design_debt_baseline.py", ["--check"]),
    ("design-lab/scripts/inert_contract_survey.py", ["--check"]),
    # Left the register on 2026-10-09 (task #24): its --check used to compare one derived count
    # over every tracked file, which moves each commit, so it had been red for weeks while naming
    # nothing wrong. It now fails on contract, verdict, provenance and the two registers the
    # record itself calls defects, and reports count movement. 245 ms measured.
    ("scripts/deepseek_content_audit.py", ["--check"]),
    # Measured 2026-10-13 in both this tree and a clean clone at 7799fbe6, porcelain empty
    # before and after: rc=0, `members=97 tracked=23 local=26 reused_from_r1=48 problems=0`.
    # It re-verifies the hashes of the members already in the repository; the machine-local
    # members are counted and reported, never required, which is why it holds on a clone.
    ("scripts/archive_taskpacks_20261009_r2.py", ["--check"]),
    # Measured 2026-10-13 in both trees: rc=0, `DECLARE-EVOLUTION=OK nothing-to-declare`. This is
    # the tool the record-evolution declaration is made with; it was added without a caller, which
    # is exactly the "declared read-only form that nothing invokes" shape this table closes. Its
    # --check takes no paths, so wiring it here cannot re-declare anything.
    ("scripts/declare_record_evolution.py", ["--check"]),
]



def porcelain() -> str:
    """The tracked working-tree state, kept for the aggregate's summary line only."""
    result = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO), capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    return result.stdout


def protected_state() -> tuple:
    """path -> status + content digest for everything the tree differs on. Returns (map, error).

    The first version of this detector compared the `git status --porcelain` *string* and reported
    the paths that appeared after minus before. Measured against three plants, it caught exactly one
    of the three cases it existed for: an already-dirty record rewritten with different bytes keeps
    the same status string (missed), and a check that restores a dirty file to clean makes the set
    smaller, which a difference of `after - before` cannot see (missed). It also read an empty stdout
    as "nothing changed", so a failing git call -- a locked index, an unreadable long path -- silently
    certified the run. `-z` keeps non-ASCII paths unquoted (line-splitting a quoted Chinese path loses
    it), and a git error is now a finding rather than an empty snapshot.

    History-versus-present stays a separate question: this function only says whether the check moved
    bytes. Whether the record still agrees with the repository is the child's own verdict, and nothing
    here rewrites a report to close a missing `subject_sha` -- that is the debt register's job.
    """
    try:
        result = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                                cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
                                errors="replace")
    except OSError as exc:
        # A REPO that is not a directory, or a git that cannot start, is a detector failure -- and
        # an empty snapshot from a broken detector reads exactly like "nothing was written".
        return {}, f"git could not run: {type(exc).__name__}: {exc}"
    if result.returncode != 0:
        return {}, f"git status exited {result.returncode}: {(result.stderr or '').strip()[:200]}"
    snapshot = {}
    for record in (item for item in (result.stdout or "").split("\0") if item):
        status, path = record[:2], record[3:].replace("\\", "/")
        target = REPO / path
        try:
            if not target.is_file():
                digest = "ABSENT"
            elif target.stat().st_size > 32 * 1024 * 1024:
                digest = f"SIZE:{target.stat().st_size}"
            else:
                digest = "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError as exc:
            digest = f"UNREADABLE:{type(exc).__name__}"
        snapshot[path] = f"{status} {digest}"
    return snapshot, ""


def run_entry(generator: str, argv: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run([sys.executable, "-B", str(REPO / generator), *argv],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                cwd=str(REPO), timeout=1800)
    except OSError as exc:
        # A gate that crashes instead of printing a verdict is the gate's defect: this surfaced as a
        # traceback with no finding code, indistinguishable from a child that failed.
        return 127, f"child could not start ({type(exc).__name__}): {generator} {' '.join(argv)}"
    lines = [line for line in (result.stdout or "").strip().splitlines() if line.strip()]
    tail = lines[-1] if lines else (result.stderr or "").strip()[-160:]
    return result.returncode, tail



def run_entry_read_only(generator: str, argv: list[str]) -> tuple[int, str, list[str], str]:
    """Run an entry's check and report which paths it moved, by content, not by status string.

    A check that writes is worse than no check: it can never disagree with the record, because it
    just rewrote it. So the claim is tested per child instead of trusted, and it now fails closed
    when the detector itself cannot run.
    """
    before, before_error = protected_state()
    code, tail = run_entry(generator, argv)
    after, after_error = protected_state()
    if before_error or after_error:
        return code, tail, [], (before_error or after_error)
    moved = sorted({path for path in set(before) | set(after) if before.get(path) != after.get(path)})
    if not moved:
        return code, tail, [], ""
    detail = []
    for path in moved:
        # was/now rather than a guessed verb: "a path entered the dirty set" can mean a new write,
        # a deletion or a restore, and the reader needs the transition, not a label.
        detail.append(f"{path} [was={before.get(path, 'CLEAN')} now={after.get(path, 'CLEAN')}]")
    return code, tail, detail, ""


def guard_read_only(generator: str, argv: list[str], subject: str, drift_code: str,
                    meaning: str) -> tuple:
    """One owner for the two loops' reporting, so ENTRIES and RECEIPT_CHECKS cannot drift apart."""
    code, tail, moved, scan_error = run_entry_read_only(generator, argv)
    failures = []
    if scan_error:
        failures.append(f"FRESHNESS-PROTECTED-SCAN-FAILED {generator} {' '.join(argv)} -- the "
                        f"write detector itself failed ({scan_error}); an unusable detector must "
                        "not read as 'nothing was written'")
    for path in moved:
        failures.append(f"FRESHNESS-CHECK-WROTE {generator} {' '.join(argv)} modified "
                        f"{path}, so {meaning} -- it rewrote the thing it was comparing against")
    if code != 0:
        failures.append(f"{drift_code} {subject} -- {generator} {' '.join(argv)} exited "
                        f"{code}: {tail}")
    return code, tail, moved, scan_error, failures


def check() -> tuple[list[str], list[str], list[str], int]:
    """Return (failures, excluded reasons, checked records, records missing on disk)."""
    failures: list[str] = []
    missing: list[str] = []
    checked: list[str] = []
    for record, generator, argv in ENTRIES:
        # `argv and ...` was the first version of this line, and it let the writer form through:
        # an empty argument list short-circuits the test to false, so the one case this guard
        # exists for was the case it never checked. My own planted-entry test caught it.
        if not argv or argv[0] not in READ_ONLY_FLAGS:
            failures.append(f"FRESHNESS-WRITER-INVOKED {generator} would be run with {argv}, "
                            "which is not a read-only form")
            continue
        if not (REPO / record).is_file():
            missing.append(record)
            failures.append(f"FRESHNESS-RECORD-MISSING {record} is declared checked but the "
                            "tracked projection is not in this checkout")
            continue
        _code, _tail, _moved, _scan_error, failures_local = guard_read_only(
            generator, argv, record, "FRESHNESS-DRIFT",
            "its agreement with the record proves nothing")
        failures.extend(failures_local)
        checked.append(record)
    for generator, argv in RECEIPT_CHECKS:
        if not argv or argv[0] not in READ_ONLY_FLAGS:
            failures.append(f"FRESHNESS-WRITER-INVOKED {generator} would be run with {argv}, "
                            "which is not a read-only form")
            continue
        _code, _tail, _moved, _err, failures_local = guard_read_only(
            generator, argv, generator, "FRESHNESS-RECEIPT-DRIFT",
            "its verdict describes bytes it just rewrote")
        failures.extend(failures_local)
        checked.append(generator)
    return failures, [f"{key}: {value}" for key, value in sorted(EXCLUDED.items())], checked, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="print the entries and exclusions")
    args = parser.parse_args(argv)
    failures, exclusions, checked, _missing = check()
    for failure in failures:
        print("VERIFY_PROJECTION_FRESHNESS=FAIL " + failure)
    for line in exclusions:
        print("VERIFY_PROJECTION_FRESHNESS=NOTICE excluded " + line)
    if args.list:
        for record, generator, gate_args in ENTRIES:
            print(f"  ENTRY {record} <- {generator} {' '.join(gate_args)}")
        for generator, gate_args in RECEIPT_CHECKS:
            print(f"  RECEIPT {generator} {' '.join(gate_args)}")
    print(f"VERIFY_PROJECTION_FRESHNESS={'OK' if not failures else 'FAIL'} "
          f"records={len(ENTRIES)} verified={len(checked)} receipts={len(RECEIPT_CHECKS)} "
          f"excluded={len(EXCLUDED)} findings={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
