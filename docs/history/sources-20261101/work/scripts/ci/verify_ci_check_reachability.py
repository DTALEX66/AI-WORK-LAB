#!/usr/bin/env python3
"""No rule may exist only in CI: every check a workflow runs must be reachable from a local run, or be
declared with the reason it cannot be.

Why this exists, measured rather than asserted: `scripts/ci/verify_blueprint_coverage.py` ran in the
integration job and in no local gate, so the branch was red at two pushed heads while the canonical
local gate printed PASS on the same tree. The writer had no way to know, because the check they broke
was a check they could not run. That is a structural gap, not a one-off: anything a workflow invokes
and no local route reaches will eventually be broken by an honest edit.

Reachability is decided from repository text, never from a machine's state:
  NAMED_GATE   -- the runner lists it in a gate body (services/orchestration/run_quality_gate.py)
  TEST_ROUTE   -- some test module names it (the root batch and the workflow batch are discovered
                  dynamically, so a test wrapper counts as a local route)
  SELF_RUN     -- the operand is itself a discovered test module
  DECLARED     -- an infrastructure step with a stated reason, re-checked so a declaration cannot
                  quietly outlive its excuse
Exit 0 prints CI_CHECK_REACHABILITY_PASS; anything else names what a local writer cannot see.
"""
from __future__ import annotations

import argparse
import posixpath
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"

# Paths a workflow invokes that are the CI harness or a host-bound readback, not a rule a writer could
# run: each entry is re-tested for reachability, so a stale exemption (the script is now wired locally)
# is reported instead of hiding behind the list. The three infrastructure steps first drafted here --
# aggregate_gate, emit_gate_plan, failfast_group -- turned out to be reachable already, and the
# staleness rule is what said so; they are not declared.
#
# `apps/observer/scripts/write_artifact_receipt.py` was declared here and the staleness rule removed it on
# 2026-10-08: widening the canonical compile step to every tracked .py made the gate name that file, so by
# this tool's definition it has a local route now. The route is syntactic only -- its behaviour is still
# exercised by CI's receipt gates -- and that limit belongs in the record, not in a frozen exemption list.
#
# `apps/observer/scripts/u19_webview_e2e.py` was declared here for the same syntactic reason and the
# staleness rule removed it on 2026-10-26, when `tests/ci/test_native_surface_skip_is_granted_by_the_probe.py`
# began running its verdict rule locally. The limit stays on the record, because it is real: the harness
# still drives a built Tauri bundle through WebView2 on a Windows runner (the step carries
# `working-directory: apps/observer`), there is no cargo/rustc or drawable surface in a local run, and the
# only thing a writer can reproduce here is the decision -- the render itself stays CI's evidence.
DECLARED_CI_ONLY: dict[str, str] = {}

OPERAND = re.compile(r"(?:scripts|packages|services|apps|tests|integrations)/[\w./-]+\.py")


def tracked_python(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "--", "*.py"], cwd=root, capture_output=True,
                         check=True).stdout
    return [line.decode("utf-8", "replace").strip() for line in out.splitlines() if line.strip()]


def workflow_operands(root: Path) -> dict[str, set[str]]:
    """Every python operand named in a workflow, resolved to the repo path the step really runs.

    A step can carry `working-directory:`, and CI then names the script relative to that directory:
    `python scripts/u19_webview_e2e.py` under `apps/observer` is a different file from the same words at
    the repo root. Judging the literal string would call the reachable one unreachable and vice versa,
    so the candidate that exists as a tracked path wins, and an operand that matches nothing is kept as
    written so it is still reported.
    """
    found: dict[str, set[str]] = {}
    tracked = set(tracked_python(root)) | {p for p in _tracked_all(root) if p.endswith(".py")}
    for wf in sorted((root / ".github" / "workflows").glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="replace")
        cwd = ""
        for line in text.splitlines():
            directory = re.search(r"working-directory:\s*([^\s]+)", line)
            if directory:
                cwd = directory.group(1).strip("'\"")
                if cwd == ".":
                    cwd = ""
                continue
            for match in OPERAND.findall(line):
                joined = posixpath.normpath(posixpath.join(cwd, match)) if cwd else match
                operand = joined if joined in tracked else (match if match in tracked else joined)
                found.setdefault(operand, set()).add(wf.name)
    return found


def _tracked_all(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, check=True).stdout
    return [line.decode("utf-8", "replace").strip() for line in out.splitlines() if line.strip()]


def local_corpus(root: Path, tracked: list[str]) -> dict[str, str]:
    """Repo-relative path -> text, for the files that can constitute a local route."""
    corpus: dict[str, str] = {}
    runner = root / "services/orchestration/run_quality_gate.py"
    if runner.is_file():
        corpus[runner.relative_to(root).as_posix()] = runner.read_text(encoding="utf-8",
                                                                        errors="replace")
    for rel in tracked:
        if rel.startswith("tests/") and "/test_" in rel:
            corpus[rel] = (root / rel).read_text(encoding="utf-8", errors="replace")
    return corpus


def classify(operand: str, corpus: dict[str, str]) -> tuple[str, str]:
    stem = Path(operand).name
    if operand in corpus:
        return "SELF_RUN", "it is itself a discovered test module"
    if any(stem in text or operand in text for text in corpus.values()):
        where = next(p for p, text in corpus.items() if stem in text or operand in text)
        if where.endswith("run_quality_gate.py"):
            return "NAMED_GATE", where
        return "TEST_ROUTE", where
    return "UNREACHABLE", ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-unreachable", action="store_true",
                        help="print every unreachable operand even when the gate passes")
    args = parser.parse_args(argv)

    tracked = tracked_python(REPO)
    if not tracked:
        print("CI_CHECK_REACHABILITY_FAIL git ls-files returned no python files; nothing can be "
              "judged reachable against an empty corpus")
        return 1
    corpus = local_corpus(REPO, tracked)
    operands = workflow_operands(REPO)
    if not operands:
        print(f"CI_CHECK_REACHABILITY_FAIL no python operands found in {WORKFLOWS}; the extractor "
              "matched nothing, which is a broken checker rather than a clean CI")
        return 1

    counts = {"NAMED_GATE": 0, "TEST_ROUTE": 0, "SELF_RUN": 0, "DECLARED": 0, "UNREACHABLE": 0}
    offenders: list[tuple[str, str]] = []
    stale: list[tuple[str, str]] = []
    for operand, where in sorted(operands.items()):
        verdict, evidence = classify(operand, corpus)
        if operand in DECLARED_CI_ONLY:
            if verdict != "UNREACHABLE":
                stale.append((operand, f"{verdict} via {evidence}"))
            else:
                counts["DECLARED"] += 1
        if verdict == "UNREACHABLE" and operand not in DECLARED_CI_ONLY:
            counts["UNREACHABLE"] += 1
            offenders.append((operand, ",".join(sorted(where))))
        elif operand not in DECLARED_CI_ONLY:
            counts[verdict] += 1

    print(f"CI_CHECK_REACHABILITY_OPERANDS workflows={len(list((REPO / '.github/workflows').glob('*.yml')))} "
          f"operands={len(operands)} corpus_files={len(corpus)}")
    for name, count in counts.items():
        print(f"  {name}={count}")
    for operand, where in offenders:
        print(f"  CI-ONLY {operand}  [{'/'.join(sorted(operands[operand]))}]")
    for operand, why in stale:
        print(f"  DECLARED_BUT_REACHABLE {operand} -- {why}; drop the declaration")
    if args.list_unreachable:
        for operand in sorted(operands):
            print(f"    {operand}: {classify(operand, corpus)[0]}")
    if offenders or stale:
        print("CI_CHECK_REACHABILITY_FAIL "
              f"ci_only={len(offenders)} stale_declarations={len(stale)} -- a writer cannot see a rule "
              "that only the runner enforces")
        return 1
    print(f"CI_CHECK_REACHABILITY_PASS operands={len(operands)} "
          f"declared={counts['DECLARED']} ci_only=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
