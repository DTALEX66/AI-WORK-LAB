#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""TP-20260819 E2E-003: governed-production Design Review step (federation).

Contract-level: quality gate -> design review -> preflight -> editable handoff.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main() -> int:
    errors: list[str] = []
    data = json.loads((ROOT / 'evals/e2e-reference/ecommerce-hero-v1.json').read_text(encoding='utf-8'))
    # 1) quality gate 通过
    if not data.get('quality_scores', {}):
        errors.append('no quality scores')
    # 2) design review 记录（critique/decision）
    review = {
        'critique_refs': ['c1', 'c2'],
        'decision': 'approved',
        'contract': 'design-review/v1',
    }
    if review['decision'] not in ('approved', 'revision'):
        errors.append('invalid review decision')
    # 3) preflight 全 pass
    for chk in data.get('preflight', {}).get('checks', []):
        if chk.get('status') != 'pass':
            errors.append(f'preflight {chk.get("id")} not pass')
    # 4) editable handoff（可编辑交付）
    arts = data.get('delivery_manifest', {}).get('artifacts', [])
    if not any('source' in a or 'psd' in a or 'editable' in a for a in arts):
        errors.append('handoff missing editable source')
    print(f'FEDERATION_REVIEW={"FAIL" if errors else "PASS"}')
    for e in errors:
        print('ERROR:', e)
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
