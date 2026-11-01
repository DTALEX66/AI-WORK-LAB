#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the Python suite as shards and prove the shards together are the suite.

D04 (2026-10-14). The measured spread on the same 3011 tests -- 557.124s, 990.101s, 788.813s --
means the total was never the interesting number; the per-module table is. This orchestrator
exists to make sharding safe before it is made fast: it runs each shard as **its own process**
(`--shard i/n`), each with its own project-local run root, then compares the union of the test ids
the shards actually ran against the ids discovery produces. A shard split that is quick but drops
a module is worse than a slow suite, so "no omissions, no duplicates" is checked here rather than
assumed.

Order is sequential by default. The document this implements says the recovery / archive / port /
environment tests must be isolated rather than parallelised, and that shards should start small:
`--jobs` exists but stays 1 unless asked, and any shard the plan marks isolated runs alone even
then.

Usage:
    python scripts/run_python_tests_all.py                      # shards from the plan, sequential
    python scripts/run_python_tests_all.py --shards 6 --jobs 1
    python scripts/run_python_tests_all.py --shards 6 --dry-run  # print the assignment and stop
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_python_tests.py"
PLAN = ROOT / "design-lab" / "config" / "python-test-shards.json"
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from design_lab.runtime.paths import PathPolicyError
from design_lab.runtime.test_environment import project_test_environment
import run_python_tests as runner_module

_TIMING_LINE = re.compile(r'PYTHON_TESTS_TIMING=WROTE (?P<path>.+?) '
                          r'tests=(?P<tests>\d+) wall_seconds=(?P<wall>[\d.]+)')


def _expected_ids() -> dict[str, list[str]]:
    return runner_module._discover_module_ids()


def _run_shard(index: int, count: int, plan: str | None) -> dict:
    argv = [sys.executable, str(RUNNER), '--shard', f'{index}/{count}']
    if plan:
        argv += ['--plan', plan]
    started = time.perf_counter()
    done = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    wall = time.perf_counter() - started
    out = (done.stdout or '') + (done.stderr or '')
    match = _TIMING_LINE.search(out)
    record = {
        'shard': index,
        'exit_code': done.returncode,
        'wall_seconds': round(wall, 3),
        'timing_path': match.group('path').strip() if match else None,
        'reported_tests': int(match.group('tests')) if match else None,
        'ran_ids': [],
        'outcomes': {},
        'failed_ids': [],
        'notes': [line for line in out.splitlines()
                  if line.startswith(('PYTHON_TESTS_SHARD_', 'SHARD_SELECTION_MISMATCH',
                                      'TEST_SELECTION_EMPTY', 'TEST_ENVIRONMENT_FAIL',
                                      'PLAN_INCOMPLETE', 'BAD_SHARD'))],
    }
    if match:
        try:
            document = json.loads(Path(record['timing_path']).read_text(encoding='utf-8'))
            record['ran_ids'] = document.get('ran_ids', [])
            record['outcomes'] = document.get('outcomes', {})
            record['by_module'] = document.get('by_module', {})
            # The shard document already carries every test id with its status. Naming the
            # failures here is what turns `FAIL: 3` into something a reader can act on: without
            # it, CI publishes a count, the log has no names, and the only way to learn which
            # three are red is to re-run the shard locally for twenty minutes.
            record['failed_ids'] = sorted(
                str(row.get('id')) for row in document.get('records', [])
                if str(row.get('status')) in ('FAIL', 'ERROR', 'UNEXPECTED_SUCCESS'))
        except (OSError, ValueError) as exc:
            record['notes'].append(f'TIMING_UNREADABLE {type(exc).__name__}: {exc}')
    # A shard that died before its timing file was written still has to be reported as a shard
    # that ran nothing -- not quietly as a shard that had nothing to run.
    return record


def _aggregate(expected: dict[str, list[str]], shards: list[dict]) -> dict:
    expected_ids = sorted(tid for ids in expected.values() for tid in ids)
    ran: list[str] = []
    for record in shards:
        ran.extend(record['ran_ids'])
    expected_counts = collections.Counter(expected_ids)
    ran_counts = collections.Counter(ran)
    # The invariant is multiset equality: the shards together reproduce exactly what discovery
    # produced, including any duplication discovery itself carries. The split is not allowed to
    # add a second copy of anything, and it is not allowed to drop one either.
    duplicates = sorted(tid for tid, n in ran_counts.items() if n > expected_counts[tid])
    missing = sorted(tid for tid, n in expected_counts.items() if ran_counts[tid] < n)
    unexpected = sorted(tid for tid in ran_counts if tid not in expected_counts)
    # Reported separately so a pre-existing double registration is visible as its own finding
    # rather than folding into the split's verdict.
    discovery_duplicates = sorted(tid for tid, n in expected_counts.items() if n > 1)
    outcomes: dict[str, int] = {}
    by_module: dict[str, dict[str, object]] = {}
    for record in shards:
        for status, count in (record['outcomes'] or {}).items():
            outcomes[status] = outcomes.get(status, 0) + int(count)
        for module, bucket in (record.get('by_module') or {}).items():
            merged = by_module.setdefault(module, {'tests': 0, 'seconds': 0.0, 'failures': 0,
                                                   'skipped': 0})
            merged['tests'] = int(merged['tests']) + int(bucket['tests'])
            merged['seconds'] = round(float(merged['seconds']) + float(bucket['seconds']), 6)
            merged['failures'] = int(merged['failures']) + int(bucket['failures'])
            merged['skipped'] = int(merged['skipped']) + int(bucket['skipped'])
    return {
        'schemaVersion': 'design-lab/python-test-shards/v1',
        'expected_tests': len(expected_ids),
        'expected_distinct_tests': len(expected_counts),
        'discovery_duplicates': discovery_duplicates,
        'ran_tests': len(ran),
        'shards': len(shards),
        'duplicates': duplicates,
        'missing': missing,
        'unexpected': unexpected,
        'outcomes': outcomes,
        # The merged per-module table is the input a balanced plan is built from; keeping it in
        # the document means the plan can be regenerated from a run rather than retyped.
        'by_module': dict(sorted(by_module.items(),
                                 key=lambda item: float(item[1]['seconds']), reverse=True)),
        'shard_records': shards,
        'union_exact': ran_counts == expected_counts,
        'meaning': 'the shards together must be the suite, as a multiset: the union reproduces '
                   'discovery exactly, counting every id as many times as discovery does',
    }


def _write(document: dict) -> Path | None:
    temp = os.environ.get('TEMP')
    if not temp:
        return None
    try:
        target = Path(temp).parent / 'python-tests-shards.json'
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n',
                          encoding='utf-8', newline='\n')
    except OSError as exc:
        print(f'SHARDS_JSON_UNWRITTEN {type(exc).__name__}: {exc}')
        return None
    return target


def _main(options: argparse.Namespace) -> int:
    plan_path = str(PLAN) if (PLAN.is_file() and not options.no_plan) else None
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8')) if plan_path else None
    count = options.shards or (plan['shardCount'] if plan else 6)
    isolated = set(plan.get('isolatedModules', [])) if plan else set()
    if options.dry_run:
        expected = _expected_ids()
        for index in range(1, count + 1):
            modules = runner_module._planned_shards(sorted(expected), plan_path, (index, count))[0]
            mark = ' [ISOLATED]' if isolated & set(modules) else ''
            print(f'shard{index}: {len(modules)} modules{mark}')
        return 0

    expected = _expected_ids()
    print(f'PYTHON_TESTS_SHARDS_START shards={count} expected_tests='
          f'{sum(len(v) for v in expected.values())} plan={plan_path or "none (index %% n)"}')
    shards: list[dict] = []
    for index in range(1, count + 1):
        record = _run_shard(index, count, plan_path)
        shards.append(record)
        print(f"PYTHON_TESTS_SHARD_RESULT shard={index}/{count} exit={record['exit_code']} "
              f"tests={record['reported_tests']} wall_seconds={record['wall_seconds']} "
              f"outcomes={record['outcomes']}")
        if record['failed_ids']:
            print(f"PYTHON_TESTS_SHARD_FAILURES shard={index}/{count} "
                  f"n={len(record['failed_ids'])} ids={', '.join(record['failed_ids'])}")
    document = _aggregate(expected, shards)
    written = _write(document)
    print(f"PYTHON_TESTS_UNION={'OK' if document['union_exact'] else 'BROKEN'} "
          f"expected={document['expected_tests']} "
          f"distinct={document['expected_distinct_tests']} ran={document['ran_tests']} "
          f"duplicates={len(document['duplicates'])} missing={len(document['missing'])} "
          f"unexpected={len(document['unexpected'])}")
    if document['discovery_duplicates']:
        # The suite registering one id twice is its own defect and is reported as such: it makes
        # the suite run that test twice, and it is not something the split caused or can fix.
        print(f"PYTHON_TESTS_DISCOVERY_DUPLICATES={len(document['discovery_duplicates'])} "
              f"first={document['discovery_duplicates'][:3]}")
    for tid in document['duplicates'][:5]:
        print(f'PYTHON_TESTS_DUPLICATE {tid}')
    for tid in document['missing'][:5]:
        print(f'PYTHON_TESTS_MISSING {tid}')
    print(f"PYTHON_TESTS_SHARDS_JSON={'WROTE ' + str(written) if written else 'NOT_WRITTEN'} "
          f"outcomes={document['outcomes']}")
    for module, bucket in list(document['by_module'].items())[:10]:
        print(f"PYTHON_TESTS_MODULE {float(bucket['seconds']):>9.3f}s "
              f"tests={bucket['tests']} {module}")
    if options.emit_module_timings:
        for module, bucket in document['by_module'].items():
            print(f"PYTHON_TESTS_MODULE_ALL {float(bucket['seconds']):>9.3f}s "
                  f"tests={bucket['tests']} {module}")
    if not document['union_exact']:
        # A split that loses a test is a failure even when every shard it did run passed.
        return 2
    return 0 if all(record['exit_code'] == 0 for record in shards) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shards', type=int, default=None, help='how many shards to run')
    parser.add_argument('--jobs', type=int, default=1, help='reserved; shards run sequentially')
    parser.add_argument('--plan', dest='no_plan', action='store_true',
                        help='ignore the committed plan and use index %% n')
    parser.add_argument('--dry-run', action='store_true', help='print the assignment and stop')
    parser.add_argument('--emit-module-timings', action='store_true',
                        help='print every module\'s merged time, to build a balanced plan')
    options = parser.parse_args()
    try:
        with project_test_environment('python-tests-all'):
            return _main(options)
    except (PathPolicyError, OSError) as exc:
        print(f'TEST_ENVIRONMENT_FAIL: {exc}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
