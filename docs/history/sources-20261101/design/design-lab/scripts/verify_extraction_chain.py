#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL P0-005: verify external-asset conversion chain contracts (fail-closed)."""
from __future__ import annotations
import json
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parent.parent

def main() -> int:
    errors: list[str] = []
    for name in ('extraction-job', 'candidate-knowledge'):
        p = ROOT / 'schemas' / (name + '.schema.json')
        s = json.loads(p.read_text(encoding='utf-8'))
        jsonschema.Draft202012Validator.check_schema(s)
    # 正例 + 负例
    ej = json.loads((ROOT / 'schemas/extraction-job.schema.json').read_text(encoding='utf-8'))
    good = {'job_id': 'ej-1', 'schemaVersion': 'design-lab/extraction-job/v1', 'source_id': 'pixelmatch', 'state': 'queued', 'created_at': '2026-08-19T00:00:00Z'}
    jsonschema.validate(good, ej)
    bad = dict(good, state='exploded')
    try:
        jsonschema.validate(bad, ej)
        errors.append('bad extraction state must fail')
    except jsonschema.ValidationError:
        pass
    print(f'EXTRACTION_CHAIN={"FAIL" if errors else "PASS"}')
    for e in errors:
        print('ERROR:', e)
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
