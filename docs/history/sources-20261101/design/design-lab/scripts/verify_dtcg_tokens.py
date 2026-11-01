#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL E: verify DTCG token alignment (fail-closed)."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEMS = ROOT / 'design-systems'

def main() -> int:
    errors: list[str] = []
    for name in ('anomaly-monitor-dark', 'uiux-commercial-light'):
        src = json.loads((SYSTEMS / name / 'design-tokens.json').read_text(encoding='utf-8'))
        dtcg = json.loads((SYSTEMS / name / 'design-tokens.dtcg.json').read_text(encoding='utf-8'))
        for sec in ('colors', 'radius', 'spacing', 'font'):
            if sec in src and sec in dtcg:
                src_keys = set(src[sec].keys())
                dtcg_keys = set(dtcg[sec].keys())
                if src_keys != dtcg_keys:
                    errors.append(f'{name}/{sec}: key mismatch {sorted(src_keys - dtcg_keys)}')
                for k in src_keys & dtcg_keys:
                    tok = dtcg[sec][k]
                    if '$type' not in tok or '$value' not in tok:
                        errors.append(f'{name}/{sec}/{k}: missing $type/$value')
    print(f'DTCG_TOKENS={"FAIL" if errors else "PASS"}')
    for e in errors:
        print('ERROR:', e)
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
