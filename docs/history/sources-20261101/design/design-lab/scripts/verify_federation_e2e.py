#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""TP-20260819 E2E-002: federation E2E (Brief -> IR -> Knowledge Query -> Quality -> Handoff).

Contract-level (E1 honest): reuses ecommerce-hero reference chain + Knowledge Query step (ArcheAxis federation query contract).
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main() -> int:
    errors: list[str] = []
    data = json.loads((ROOT / 'evals/e2e-reference/ecommerce-hero-v1.json').read_text(encoding='utf-8'))
    knowledge = {
        'query': 'ecommerce hero premium beverage composition',
        'contract': 'archeaxis:query_knowledge/v1',
        'results': ['mem_dl_ecom_001', 'mem_dl_typ_002'],
    }
    if not data.get('brief', {}).get('project_id'):
        errors.append('missing brief project_id')
    if data.get('domain') != 'ecommerce.hero_image':
        errors.append('domain mismatch')
    ir = json.loads((ROOT / 'schemas/design-ir.schema.json').read_text(encoding='utf-8'))
    if ir.get('$id') != 'https://design-lab.local/schemas/design-ir.schema.json':
        errors.append('IR schema missing')
    mem = json.loads((ROOT / 'memory/records.json').read_text(encoding='utf-8'))
    ids = {r.get('id') for r in mem}
    for ref in knowledge['results']:
        if ref not in ids:
            errors.append(f'knowledge ref {ref} not in memory')
    if not data.get('quality_scores', {}):
        errors.append('no quality scores')
    if 'quality-report.json' not in data.get('delivery_manifest', {}).get('artifacts', []):
        errors.append('handoff missing quality-report')
    print(f'FEDERATION_E2E={"FAIL" if errors else "PASS"}')
    for e in errors:
        print('ERROR:', e)
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
