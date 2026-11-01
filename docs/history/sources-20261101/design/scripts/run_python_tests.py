#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Root Python test entrypoint for DESIGN-LAB (ODA4-0103).

Discovers and runs every `test_*.py` unittest module under
`design-lab/tests/`. Exits non-zero if any test fails.

Also writes a per-test timing record into this run's project-local directory, because the next
decision about this suite is a sharding decision and it cannot be made from a total. Measured
2026-10-13/14 on the same 3011 tests: 557.124s in one run, 990.101s in an earlier failing run.
A 433s spread with no per-test number behind it is exactly the situation where the tempting move
-- "parallelise it" -- is a guess. This records what actually ran, so the split can be chosen from
data: test id, module, class, wall time, outcome and skip reason.

Unittest stays the executor. Moving to pytest-xdist here would add an unrelated migration to a
batch whose subject is feedback time.

Usage:
    python scripts/run_python_tests.py                     # the whole suite, one process
    python scripts/run_python_tests.py --list-modules      # sorted module names, no run
    python scripts/run_python_tests.py --shard 1/6         # one slice, its own run root
    python scripts/run_python_tests.py --shard 1/6 --plan design-lab/config/python-test-shards.json

Sharding (D04). A shard is a **process**, not a thread: `--shard i/n` imports and runs only the
modules assigned to it, inside its own `project_test_environment` root, and writes its own
`python-tests-timing.json`. Without `--plan` the assignment is `index % n` over the sorted module
list, which is deterministic but not balanced; with `--plan` it comes from the committed shard
plan, which is built from measured per-module time. `scripts/run_python_tests_all.py` is the
orchestrator that runs the shards and proves the union of their test ids equals discovery.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
# Suppress repository bytecode before importing the local environment helper.
if __name__ == '__main__':
    sys.dont_write_bytecode = True
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "design-lab" / "tests"
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.runtime.paths import PathPolicyError
from design_lab.runtime.test_environment import project_test_environment


class _TimingResult(unittest.TextTestResult):
    """Per-test wall time, outcome and skip reason; what the run reports is unchanged.

    Timing is taken in `stopTest`, which runs after the outcome method and after tearDown, so a
    row's `seconds` is setup + call + teardown. That is the coarse figure a sharding decision
    needs; attributing the three phases separately would mean wrapping every TestCase, which is a
    larger change than this batch is for.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records: list[dict[str, object]] = []
        self._started: dict[str, float] = {}
        self._status: dict[str, str] = {}
        self._reason: dict[str, str] = {}

    def startTest(self, test) -> None:  # noqa: N802 (unittest's spelling)
        self._started[test.id()] = time.perf_counter()
        super().startTest(test)

    def _mark(self, test, status: str, reason: str | None = None) -> None:
        self._status[test.id()] = status
        if reason:
            self._reason[test.id()] = reason

    def addSuccess(self, test) -> None:  # noqa: N802
        self._mark(test, 'PASS')
        super().addSuccess(test)

    def addFailure(self, test, err) -> None:  # noqa: N802
        self._mark(test, 'FAIL')
        super().addFailure(test, err)

    def addError(self, test, err) -> None:  # noqa: N802
        self._mark(test, 'ERROR')
        super().addError(test, err)

    def addSkip(self, test, reason) -> None:  # noqa: N802
        # A skipped browser wrapper is not a passed browser check, so the reason travels with the
        # row instead of the row being counted as a pass.
        self._mark(test, 'SKIP', reason)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err) -> None:  # noqa: N802
        self._mark(test, 'EXPECTED_FAILURE')
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test) -> None:  # noqa: N802
        # Kept apart from PASS on purpose: an xfail that starts passing is a result change, and
        # folding it into the pass count is how it stops being visible.
        self._mark(test, 'UNEXPECTED_SUCCESS')
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err) -> None:  # noqa: N802
        if err is not None:
            self._mark(test, 'FAIL', f'subtest failed: {subtest.id()}')
        super().addSubTest(test, subtest, err)

    def stopTest(self, test) -> None:  # noqa: N802
        identifier = test.id()
        started = self._started.pop(identifier, None)
        self.records.append({
            'id': identifier,
            'module': type(test).__module__,
            'class': type(test).__name__,
            'method': getattr(test, '_testMethodName', None),
            'status': self._status.pop(identifier, 'PASS'),
            'seconds': None if started is None else round(time.perf_counter() - started, 6),
            'skip_reason': self._reason.pop(identifier, None),
        })
        super().stopTest(test)


def _timing_document(result: _TimingResult, wall_seconds: float) -> dict:
    by_module: dict[str, dict[str, object]] = {}
    for row in result.records:
        bucket = by_module.setdefault(str(row['module']),
                                      {'tests': 0, 'seconds': 0.0, 'failures': 0, 'skipped': 0})
        bucket['tests'] = int(bucket['tests']) + 1
        bucket['seconds'] = round(float(bucket['seconds']) + float(row['seconds'] or 0.0), 6)
        if row['status'] in ('FAIL', 'ERROR', 'UNEXPECTED_SUCCESS'):
            bucket['failures'] = int(bucket['failures']) + 1
        if row['status'] == 'SKIP':
            bucket['skipped'] = int(bucket['skipped']) + 1
    return {
        'schemaVersion': 'design-lab/python-test-timing/v1',
        'tests': len(result.records),
        'wall_seconds': round(wall_seconds, 6),
        'sum_test_seconds': round(sum(float(r['seconds'] or 0.0) for r in result.records), 6),
        'outcomes': {status: sum(1 for r in result.records if r['status'] == status)
                     for status in sorted({str(r['status']) for r in result.records})},
        'by_module': dict(sorted(by_module.items(),
                                 key=lambda item: float(item[1]['seconds']), reverse=True)),
        'records': sorted(result.records, key=lambda r: float(r['seconds'] or 0.0), reverse=True),
        'meaning': 'per-test wall time for this run on this machine; a sharding decision reads '
                   'by_module, and no row here is a stability claim about another host',
    }


def _write_timing(document: dict) -> Path | None:
    """Write into this run's own project-local directory, the one the environment just made."""
    temp = os.environ.get('TEMP')
    if not temp:
        return None
    try:
        target = Path(temp).parent / 'python-tests-timing.json'
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n',
                          encoding='utf-8', newline='\n')
    except OSError as exc:
        print(f'PYTHON_TESTS_TIMING_UNWRITTEN {type(exc).__name__}: {exc}')
        return None
    return target


def _discover_module_ids() -> dict[str, list[str]]:
    """Every module's test ids, sorted. Imports the modules but runs nothing."""
    loader = unittest.defaultTestLoader
    suite = loader.discover(start_dir=str(TEST_DIR), pattern="test_*.py",
                            top_level_dir=str(TEST_DIR))
    mapping: dict[str, list[str]] = {}
    stack = [suite]
    while stack:
        item = stack.pop()
        if isinstance(item, unittest.TestSuite):
            stack.extend(list(item))
            continue
        mapping.setdefault(type(item).__module__, []).append(item.id())
    return {name: sorted(ids) for name, ids in sorted(mapping.items())}


def _planned_shards(modules: list[str], plan_path: str | None, shard: tuple[int, int] | None
                    ) -> tuple[list[str], str]:
    """The modules this process should run, plus a one-line reason for the record."""
    if plan_path:
        plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
        assignment: dict[str, str] = plan['assignment']
        unknown = [m for m in modules if m not in assignment]
        if unknown:
            # A module nobody assigned would silently stop being run by every shard, which is
            # exactly the "no omissions" property this whole mechanism has to hold.
            raise SystemExit(f'PLAN_INCOMPLETE: {len(unknown)} discovered modules are unassigned, '
                             f'e.g. {unknown[:3]}')
        if shard is None:
            raise SystemExit('--plan requires --shard i/n')
        wanted = f'shard{shard[0]}'
        return [m for m in modules if assignment[m] == wanted], f'plan {plan_path} -> {wanted}'
    if shard is None:
        return modules, 'serial (single process, whole suite)'
    index, count = shard
    return ([m for position, m in enumerate(modules) if position % count == index - 1],
            f'index % {count} == {index - 1}')


def _suite_for(modules: list[str]) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    for name in modules:
        suite.addTests(loader.loadTestsFromName(name))
    return suite


def _run(options: argparse.Namespace) -> int:
    if not TEST_DIR.exists():
        print(f"test dir not found: {TEST_DIR}")
        return 1
    if options.list_modules:
        for name in _discover_module_ids():
            print(name)
        return 0
    shard = None
    if options.shard:
        index, _, count = options.shard.partition('/')
        shard = (int(index), int(count))
        if not (1 <= shard[0] <= shard[1]):
            print(f'BAD_SHARD: {options.shard} is not i/n with 1 <= i <= n')
            return 2
    discovered = _discover_module_ids()
    modules, why = _planned_shards(sorted(discovered), options.plan, shard)
    expected_ids = [tid for name in modules for tid in discovered[name]]
    if not expected_ids:
        print('TEST_SELECTION_EMPTY: no test cases discovered')
        return 2
    suite = _suite_for(modules)
    if suite.countTestCases() == 0:
        print('TEST_SELECTION_EMPTY: the selected modules yield no test cases')
        return 2
    label = f'shard {options.shard}' if options.shard else 'serial'
    print(f'PYTHON_TESTS_SHARD_START {label} modules={len(modules)} '
          f'expected_tests={len(expected_ids)} selection={why}')
    runner = unittest.TextTestRunner(verbosity=1, resultclass=_TimingResult)
    started = time.perf_counter()
    result = runner.run(suite)
    wall = time.perf_counter() - started

    document = _timing_document(result, wall)
    document['shard'] = {'label': label, 'modules': modules, 'selection': why,
                         'expected_tests': len(expected_ids)}
    document['ran_ids'] = [str(row['id']) for row in result.records]
    written = _write_timing(document)
    print(f"PYTHON_TESTS_TIMING={'WROTE ' + str(written) if written else 'NOT_WRITTEN'} "
          f"tests={document['tests']} wall_seconds={document['wall_seconds']} "
          f"outcomes={document['outcomes']}")
    for row in document['records'][:10]:
        print(f"PYTHON_TESTS_SLOW {row['seconds']:>9.3f}s {row['status']:<10} {row['id']}")
    for module, bucket in list(document['by_module'].items())[:10]:
        print(f"PYTHON_TESTS_MODULE {float(bucket['seconds']):>9.3f}s "
              f"tests={bucket['tests']} failures={bucket['failures']} {module}")
    if options.emit_module_timings:
        # Every module, not just the ten slowest: a balanced shard plan needs the whole table, and
        # a plan built from the head of a list is a guess wearing a number.
        for module, bucket in document['by_module'].items():
            print(f"PYTHON_TESTS_MODULE_ALL {float(bucket['seconds']):>9.3f}s "
                  f"tests={bucket['tests']} {module}")
    # The comparison is between what this shard said it would run and what it actually ran: a
    # module that imports but silently yields nothing would otherwise be counted as covered.
    ran = sorted(str(row['id']) for row in result.records)
    if ran != sorted(expected_ids):
        print(f'SHARD_SELECTION_MISMATCH expected={len(expected_ids)} ran={len(ran)}')
        return 2
    print(f'PYTHON_TESTS_SHARD_END {label} ran={len(ran)}')
    return 0 if result.wasSuccessful() else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shard', metavar='I/N', default=None,
                        help='run one slice of the suite as its own process')
    parser.add_argument('--plan', metavar='PATH', default=None,
                        help='committed shard plan; requires --shard')
    parser.add_argument('--list-modules', action='store_true',
                        help='print the sorted module names and exit')
    parser.add_argument('--emit-module-timings', action='store_true',
                        help='print every module\'s time, for building a balanced shard plan')
    options = parser.parse_args()
    namespace = 'python-tests' if not options.shard else f'python-tests-shard-{options.shard[0]}'
    try:
        with project_test_environment(namespace):
            return _run(options)
    except (PathPolicyError, OSError) as exc:
        print(f'TEST_ENVIRONMENT_FAIL: {exc}')
        return 2


if __name__ == "__main__":
    sys.exit(main())
