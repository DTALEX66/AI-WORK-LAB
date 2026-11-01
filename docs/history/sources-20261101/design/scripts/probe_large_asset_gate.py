#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prove the large-asset rule in verify_asset_governance.py both ways.

A budget gate that can only print OK is worthless, so this drives the real gate
against the real index: once clean, once with an undeclared large binary staged,
once with a bundle pushed over its own budget. It always restores the index.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / 'design-lab' / 'scripts' / 'verify_asset_governance.py'
PROBE = REPO / 'docs' / 'golden-cases' / 'zz-large-asset-probe.png'
# Chosen from the index rather than hard-coded: an earlier version of this probe
# copied a 74 KiB screenshot and "proved" the gate worked when the file was
# simply below the 256 KiB threshold and correctly ignored.
DECLARE_ABOVE_KIB = 256


def largest_tracked_png() -> Path:
    best: tuple[int, Path] = (0, Path())
    listed = subprocess.run(['git', 'ls-files', '-s', '*.png'], cwd=REPO, capture_output=True,
                            text=True, encoding='utf-8', errors='replace').stdout
    shas = {}
    for line in listed.splitlines():
        meta, _, path = line.partition('\t')
        parts = meta.split()
        if path and len(parts) >= 2:
            shas[parts[1]] = REPO / path
    if not shas:
        return Path()
    probe = subprocess.run(['git', 'cat-file', '--batch-check=%(objectsize)'],
                           input='\n'.join(shas), cwd=REPO, capture_output=True, text=True,
                           encoding='utf-8', errors='replace').stdout.splitlines()
    for sha, raw in zip(list(shas), probe):
        if raw.isdigit() and int(raw) > best[0]:
            best = (int(raw), shas[sha])
    return best[1]


def run_gate() -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(GATE)], cwd=REPO, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')
    return proc.returncode, proc.stdout


def cleanup() -> None:
    subprocess.run(['git', 'rm', '--cached', '-f', '--', str(PROBE.relative_to(REPO))],
                   cwd=REPO, capture_output=True)
    PROBE.unlink(missing_ok=True)


def main() -> int:
    failures: list[str] = []
    src = largest_tracked_png()
    if not src.is_file():
        print('LARGE_ASSET_PROBE=BLOCKED no tracked png found')
        return 3
    size = src.stat().st_size
    if size < DECLARE_ABOVE_KIB * 1024:
        print('LARGE_ASSET_PROBE=BLOCKED largest tracked png is only %d KiB, below the '
              '%d KiB threshold — a negative test here would prove nothing'
              % (size // 1024, DECLARE_ABOVE_KIB))
        return 3
    print('probe source: %s (%d KiB)' % (src.name, size // 1024))

    code, out = run_gate()
    if code != 0:
        failures.append('baseline gate run did not pass: exit=%s\n%s' % (code, out[-1200:]))
    if 'LARGE_ASSETS' not in out:
        failures.append('baseline printed no LARGE_ASSETS line (gate never reached it)')

    # 1. an undeclared binary outside every declared bundle must FAIL the run.
    try:
        shutil.copyfile(src, PROBE)
        subprocess.run(['git', 'add', '-f', '--', str(PROBE.relative_to(REPO))],
                       cwd=REPO, check=True)
        code, out = run_gate()
        hits = [l for l in out.splitlines()
                if 'outside a declared bundle' in l and PROBE.name in l]
        if code == 0 or not hits:
            failures.append('undeclared large binary did NOT fail the gate (exit=%s)' % code)
        else:
            print('rule 1 fired: %s' % hits[0][:120])
    finally:
        cleanup()

    code, out = run_gate()
    if code != 0:
        failures.append('gate did not recover after cleanup: exit=%s\n%s' % (code, out[-800:]))

    # 2. a declared bundle pushed over its own budget must FAIL the run.
    config = REPO / 'design-lab' / 'config' / 'large-assets.json'
    original = config.read_text(encoding='utf-8')
    try:
        tightened = original.replace('"budgetMib": 8.0', '"budgetMib": 0.1', 1)
        if tightened == original:
            failures.append('could not tighten docs/projects budget; rule 2 untested')
        else:
            config.write_text(tightened, encoding='utf-8')
            code, out = run_gate()
            hits = [l for l in out.splitlines() if 'bundle over budget' in l]
            if code == 0 or not hits:
                failures.append('over-budget bundle did NOT fail the gate (exit=%s)' % code)
            else:
                print('rule 2 fired: %s' % hits[0][:120])
    finally:
        config.write_text(original, encoding='utf-8')

    # 3. the working-tree total must be reported, not silently zero.
    line = next((l for l in out.splitlines() if l.startswith('LARGE_ASSETS')), '')
    if 'working_tree_mib=0.00' in line or not line:
        failures.append('working-tree measurement looks vacuous: %r' % line)

    restored = config.read_text(encoding='utf-8') == original
    print('config restored: %s' % restored)
    if not restored:
        failures.append('large-assets.json was not restored byte-for-byte')

    print('LARGE_ASSET_PROBE failures=%d' % len(failures))
    for f in failures:
        print('  FAIL:', f)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
