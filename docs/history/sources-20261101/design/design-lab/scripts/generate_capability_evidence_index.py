# SPDX-License-Identifier: MIT
"""DL-TP-R2-014: current capability evidence index generator.

Only explicit capability evidence with bound SHA may yield current E3/E4.
Historical / beta-expired / no-bound evidence cannot produce current E3/E4.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = ROOT / 'integrations' / 'adapter-registry.json'
OUT = ROOT / 'design-lab' / 'config' / 'capability-evidence-current.json'


def main() -> int:
    reg = json.loads(REGISTRY.read_text(encoding='utf-8'))
    adapters = reg.get('adapters', [])
    caps = []
    for a in adapters:
        ev = a.get('evidence', {})
        lvl = ev.get('level', 'E0')
        bound = ev.get('boundSha') or ev.get('bound_sha')
        for c in a.get('capabilities', []):
            # current E3/E4 requires bound SHA; otherwise cap at E1 (no current runtime claim)
            current_level = lvl
            if lvl in ('E3', 'E4') and not bound:
                current_level = 'E1'
            caps.append({
                'capability_id': f"{a.get('adapter_id')}/{c['name']}",
                'evidence_level': current_level,
                'declared_level': lvl,
                'bound_sha': bound,
                'supported_current': bool(c.get('supported')) and current_level in ('E3', 'E4'),
            })
    doc = {
        'schemaVersion': 'design-lab/capability-evidence-current/v1',
        'task': 'DL-TP-R2-014',
        'generatedAt': '2026-09-04T00:00:00Z',
        'capabilities': caps,
    }
    OUT.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    n_e3 = sum(1 for x in caps if x['evidence_level'] == 'E3')
    print(f'CAPABILITY_INDEX=OK capabilities={len(caps)} current_E3={n_e3}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
