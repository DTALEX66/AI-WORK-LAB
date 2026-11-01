#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL E: convert design tokens to W3C DTCG format (interop with Tokens Studio/Penpot)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

TYPE_MAP = {
    'colors': 'color',
    'radius': 'dimension',
    'spacing': 'dimension',
    'fontSize': 'dimension',
    'fontWeight': 'fontWeight',
    'fontFamily': 'fontFamily',
    'font': 'fontFamily',
}

def convert(src: dict) -> dict:
    out = {'$schema': 'https://design-tokens.bit.dev/schema.json', 'theme': {'$type': 'string', '$value': src.get('theme', '')}}
    for section, values in src.items():
        if section == 'theme' or not isinstance(values, dict):
            continue
        t = TYPE_MAP.get(section, 'string')
        out[section] = {}
        for k, v in values.items():
            if isinstance(v, dict):
                out[section][k] = v  # already typed
            else:
                out[section][k] = {'$type': t, '$value': str(v) + ('px' if t == 'dimension' and not str(v).endswith('px') else '')}
    return out

def main() -> int:
    src_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    src = json.loads(src_path.read_text(encoding='utf-8'))
    out = convert(src)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print('DTCG_OK tokens=' + str(len([k for k in out if k not in ('$schema', 'theme')])))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
