#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Every read of asset_version must declare which ACTIVE row is the current one.

Why this exists: `publish_version` never demotes the bytes it replaced, so an asset
keeps EVERY revision marked ACTIVE -- there is no code path in this repository that
writes `state='SUPERSEDED'`. A query that filters on `state='ACTIVE'` alone therefore
returns a revision history, and four shipped surfaces got that wrong in one session:
the jury review list offered superseded drafts for signature (de9601ed), preflight
certified whichever artifact row SQLite happened to yield first (87524737), the quality
readback called one accepted subject project-wide acceptance (5b8e7d51), and the raster
library listed an asset once per revision while content() demanded exactly one row.

The convention the product actually uses is "current = the highest version_no still
marked ACTIVE for that asset" (native_assets.list, asset_store.current_version). This
gate makes a query say so, in the same statement, or name the version it was pinned to.

It fails on a LIE, not on a count: adding a compliant reader never moves a number.
An empty scan is a failure, because a scan that matched nothing and a clean tree would
otherwise share one verdict.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = REPO / 'src' / 'design_lab'
SELF = Path(__file__).resolve()

ACTIVE = re.compile(r"state\s*=\s*'ACTIVE'")
RULE = re.compile(r'MAX\s*\(\s*\w*\.?version_no\s*\)|ORDER\s+BY\s+\w*\.?version_no\s+DESC', re.I)
PINNED = re.compile(r'version_id\s*=\s*\?')
# A query that names the exact digest it wants (re-publishing identical bytes) never has
# to answer "which revision is current" -- there is at most one row per digest per asset.
PINNED_SHA = re.compile(r'sha256\s*=\s*\?')

# Statements that read asset_version for a reason other than "what is current now".
# Keyed by (file, first 40 chars of the literal) so a stale exemption is detectable:
# an exemption whose statement no longer exists fails the run.
EXEMPT: dict[tuple[str, str], str] = {}


def literals(path: Path) -> list[tuple[int, str]]:
    """Every string constant in a module, with the line it starts on."""
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if 'asset_version' in node.value and ACTIVE.search(node.value):
                found.append((node.lineno, node.value))
    return found


def scan(root: Path) -> list:
    rows = []
    for path in sorted(root.rglob('*.py')):
        if '__pycache__' in path.parts or path.resolve() == SELF:
            continue
        for lineno, text in literals(path):
            collapsed = re.sub(r'\s+', ' ', text).strip()[:40]
            key = (path.name, collapsed)
            state = 'RULED' if RULE.search(text) else (
                'PINNED' if (PINNED.search(text) or PINNED_SHA.search(text)) else 'UNRULED')
            if state == 'UNRULED' and key in EXEMPT:
                state = 'EXEMPT'
            rows.append({'file': path.relative_to(root).as_posix(), 'line': lineno,
                         'key': key, 'state': state, 'statement': collapsed})
    used = {row['key'] for row in rows if row['state'] == 'EXEMPT'}
    stale = [key for key in EXEMPT if key not in used]
    return rows, stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(PRODUCT_ROOT),
                        help='directory to scan (a test may point this at a fixture tree)')
    args = parser.parse_args()
    root = Path(args.root)
    if not root.is_dir():
        print(f'CURRENT_VERSION_RULE=FAIL reason=scan root is not a directory: {root}')
        return 1
    rows, stale = scan(root)
    if not rows:
        print(f'CURRENT_VERSION_RULE=FAIL reason=no statement in {root.name} reads '
              f'asset_version with state=\'ACTIVE\' -- either the scan is broken or the '
              f'convention it defends has been removed; neither is a pass')
        return 1
    bad = [row for row in rows if row['state'] == 'UNRULED']
    for row in rows:
        if row['state'] != 'RULED':
            print(f"  {row['state']}: {row['file']}:{row['line']} {row['statement']}")
    for key in stale:
        print(f'  STALE_EXEMPTION: {key[0]} {key[1]!r} is exempted but no longer matched '
              f'-- the statement is gone or now complies; drop the exemption')
    counts = {state: sum(1 for row in rows if row['state'] == state)
              for state in ('RULED', 'PINNED', 'EXEMPT', 'UNRULED')}
    if bad or stale:
        print(f'CURRENT_VERSION_RULE=FAIL statements={len(rows)} {counts} '
              f'stale_exemptions={len(stale)}')
        print('  every ACTIVE read must contain MAX(<alias>.version_no) or '
              'ORDER BY <alias>.version_no DESC, or pin version_id = ?')
        return 1
    print(f'CURRENT_VERSION_RULE=OK statements={len(rows)} {counts} '
          f'exemptions={len(EXEMPT)} stale=0')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
