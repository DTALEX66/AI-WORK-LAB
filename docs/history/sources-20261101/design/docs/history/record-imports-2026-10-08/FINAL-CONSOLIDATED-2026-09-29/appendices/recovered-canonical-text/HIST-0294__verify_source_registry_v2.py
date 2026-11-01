#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

ALLOWED_MODES={'vendor-adapt','adapter','derive','reference','quarantine'}
ALLOWED_STATUS={'adopt-now','adapter-next','reference-now','review-required'}

def main():
    root=Path(__file__).resolve().parents[2]
    path=root/'opendesign-assistance/research/global-absorption/SOURCE_REGISTRY.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    errors=[]; ids=set()
    for i,e in enumerate(data.get('entries',[])):
        prefix=f'entry[{i}] {e.get("id")}'
        if e.get('id') in ids: errors.append(prefix+': duplicate id')
        ids.add(e.get('id'))
        if e.get('integration_mode') not in ALLOWED_MODES: errors.append(prefix+': invalid integration_mode')
        if e.get('status') not in ALLOWED_STATUS: errors.append(prefix+': invalid status')
        if e.get('integration_mode')=='vendor-adapt' and not e.get('license_verified'): errors.append(prefix+': vendor-adapt requires verified license')
        if e.get('license') in ('UNVERIFIED','REFERENCE-ONLY') and e.get('integration_mode') not in ('reference','quarantine','derive'): errors.append(prefix+': unclear license cannot be vendored')
        if not str(e.get('url','')).startswith('https://'): errors.append(prefix+': canonical https URL required')
    print(f'SOURCES={len(data.get("entries",[]))}')
    print(f'ERRORS={len(errors)}')
    for err in errors: print('ERROR:',err)
    print('VERIFY_SOURCE_REGISTRY=' + ('OK' if not errors else 'FAIL'))
    return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
