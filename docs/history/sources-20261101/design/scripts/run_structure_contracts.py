#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Early structural contracts: the cheap checks that must fail before the suite finishes.

D03 (2026-10-14). The failing sample behind this file ran 3011 tests for 990.101s and then
reported `AssertionError: 52 != 50` -- a list-container inventory that a static read of one file
can settle in milliseconds. Paying sixteen minutes for a fact that a cheap check already holds is
not a testing problem, it is an ordering problem.

This step runs first in `python-gate` and covers the contracts whose subject is source structure
rather than behaviour: the list inventory (the 52/50 case), the stage-nav anchors, and the gate
reachability register. They are enumerated by explicit module name, never by a pattern, and the
step fails if the selection is empty -- "ran zero tests and printed nothing" must not read as a
pass, which is the failure mode a pattern-based selection has.

**Not covered here**: the workflow files themselves. A YAML syntax error or a duplicated mapping
key in `.github/workflows/*.yml` is rejected by GitHub before any job is created, and the only
symptom is a run with zero jobs and `conclusion=failure`, which reads like an infrastructure
flake. This batch hit exactly that. A workflow-syntax step belongs in this family and is not in
it yet; until it is, validate edited workflows with a linter before pushing.

Usage:
    python scripts/run_structure_contracts.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "design-lab" / "tests"
sys.path.insert(0, str(ROOT / 'src'))
# `design-lab/tests` has no `__init__.py` (it is a PEP 420 namespace package), and the
# directory name contains a hyphen so it can never be imported as `design-lab.tests`.
# Adding its parent to the path is what lets these load as `tests.<module>`.
sys.path.insert(0, str(TESTS.parent))

# Explicit, and each one is named with what it protects. A glob would have to be re-read every
# time a module is renamed, and a rename that silently stopped matching is exactly how a step
# starts passing for lack of tests rather than for lack of defects.
MODULES = (
    # Source-structure contracts over apps/workbench/shell.ts: the ul.list inventory (52/50),
    # single-definition CSS, and the list-member convention.
    "tests.test_workbench_css_single_definition",
    # Every IMPLEMENTED stage chip must point at a panel that is actually rendered.
    "tests.test_workbench_stage_nav_reachability",
    # Every gate script is either invoked by something or declared, with the reason it cannot be.
    "tests.test_gate_reachability",
)


def main() -> int:
    missing = [name for name in MODULES
               if not (TESTS / (name.rsplit('.', 1)[1] + '.py')).is_file()]
    if missing:
        print('STRUCTURE_CONTRACTS_MISSING ' + ' '.join(missing))
        return 2
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    for name in MODULES:
        loaded = loader.loadTestsFromName(name)
        if loaded.countTestCases() == 0:
            # A module that imports but yields no cases would otherwise be counted as satisfied.
            print(f'STRUCTURE_CONTRACTS_EMPTY {name}')
            return 2
        suite.addTests(loaded)
    total = suite.countTestCases()
    print(f'STRUCTURE_CONTRACTS_RAN modules={len(MODULES)} tests={total}')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f'STRUCTURE_CONTRACTS={"PASS" if result.wasSuccessful() else "FAIL"} tests={total} '
          f'failures={len(result.failures)} errors={len(result.errors)}')
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
