# SPDX-License-Identifier: MIT
"""DL-TP-R0-005: test isolation runner (forward / reverse / random order).

Discovers design-lab/tests, flattens the suite, orders test cases by module in
forward / reverse / random (seeded) order, runs once, and reports a machine-
readable summary. Used to evidence R0-005 DoD ("Python suite green in fixed,
reverse, and random order"). Pollution-sensitive modules can be repeated N times
via --repeat for the same-module contamination check.

Usage:
  python design-lab/scripts/run_test_isolation.py --order forward
  python design-lab/scripts/run_test_isolation.py --order reverse
  python design-lab/scripts/run_test_isolation.py --order random --seed 42
  python design-lab/scripts/run_test_isolation.py --modules design_lab.runtime.asset_store --repeat 20
"""
from __future__ import annotations

import sys
if __name__ == '__main__':
    sys.dont_write_bytecode = True
import argparse
import json
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # design-lab/
TEST_DIR = ROOT / "tests"
sys.path.insert(0, str(ROOT.parent / 'src'))
from design_lab.runtime.paths import PathPolicyError
from design_lab.runtime.test_environment import project_test_environment


def discover() -> unittest.TestSuite:
    return unittest.defaultTestLoader.discover(
        start_dir=str(TEST_DIR), pattern="test_*.py", top_level_dir=str(TEST_DIR)
    )


def flatten(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    tests: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            tests.extend(flatten(item))
        else:
            tests.append(item)
    return tests


def module_key(test: unittest.TestCase) -> str:
    return test.__class__.__module__


def file_key(test: unittest.TestCase) -> str:
    """Test module name (test_xxx) derived from the test method module."""
    return test.__class__.__module__.rsplit(".", 1)[-1]


def build(ordered: list[unittest.TestCase]) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    suite.addTests(ordered)
    return suite


def run(order: str, seed: int, repeat: int, modules: list[str] | None) -> int:
    base = flatten(discover())
    if modules:
        wanted = set(modules)
        base = [t for t in base if file_key(t) in wanted or module_key(t) in wanted]
    if not base:
        print('R0-005 ' + json.dumps({'ok': False, 'ran': 0,
                                     'reason': 'TEST_SELECTION_EMPTY'}, sort_keys=True))
        return 2
    if order == "reverse":
        base = list(reversed(base))
    elif order == "random":
        rng = random.Random(seed)
        rng.shuffle(base)

    for iteration in range(max(1, repeat)):
        runner = unittest.TextTestRunner(verbosity=1)
        result = runner.run(build(base))
        summary = {
            "order": order,
            "seed": seed,
            "iteration": iteration + 1,
            "repeat": max(1, repeat),
            "ran": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "ok": result.wasSuccessful(),
        }
        print("R0-005 " + json.dumps(summary, sort_keys=True))
        if not result.wasSuccessful():
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", choices=["forward", "reverse", "random"], default="forward")
    parser.add_argument("--seed", type=int, default=20260905)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--modules", nargs="*", default=None, help="filter to module names")
    args = parser.parse_args()
    try:
        with project_test_environment('test-isolation'):
            return run(args.order, args.seed, args.repeat, args.modules)
    except (PathPolicyError, OSError) as exc:
        print('R0-005 ' + json.dumps({'ok': False, 'ran': 0,
                                     'reason': 'TEST_ENVIRONMENT_FAIL', 'detail': str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
