#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
from __future__ import annotations
import json
from pathlib import Path

REQ_SCHEMAS=['design-brief','reference-dna','design-direction','design-critique','preflight','design-handoff','capability-status','case-record','design-project-state','provenance','source-registry']
REQ_ATOMS=['source-intake-gate','brief-normalizer','reference-dna-analyzer','design-direction-jury','design-quality-jury','commercial-preflight','delivery-packager']
REQ_SCENARIOS=['commercial-design-router','brand-campaign-360']

def main():
    root=Path(__file__).resolve().parents[2]; errors=[]
    for name in REQ_SCHEMAS:
        p=root/f'design-lab/schemas/{name}.schema.json'
        if not p.is_file(): errors.append(f'missing schema {p}')
        else:
            try: json.loads(p.read_text(encoding='utf-8'))
            except Exception as exc: errors.append(f'invalid schema {p}: {exc}')
    for kind,names in [('atoms',REQ_ATOMS),('scenarios',REQ_SCENARIOS)]:
        for name in names:
            base=root/f'packages/capabilities/{kind}/{name}'
            for file in ['SKILL.md','open-design.json','README.md']:
                p=base/file
                if not p.is_file(): errors.append(f'missing {p}')
            mp=base/'open-design.json'
            if mp.is_file():
                m=json.loads(mp.read_text(encoding='utf-8')); od=m.get('od',{})
                if m.get('specVersion')!='1.0.0': errors.append(f'{name}: bad specVersion')
                if not m.get('compat',{}).get('agentSkills'): errors.append(f'{name}: missing compat.agentSkills')
                if kind=='scenarios':
                    stages=od.get('pipeline',{}).get('stages') or []
                    if not stages: errors.append(f'{name}: missing pipeline')
                    stage_map={s.get('id'):set(s.get('atoms') or []) for s in stages if isinstance(s,dict)}
                    for surface in od.get('genui',{}).get('surfaces') or []:
                        trigger=surface.get('trigger') or {}; stage_id=trigger.get('stageId'); atom=trigger.get('atom')
                        if stage_id and stage_id not in stage_map: errors.append(f'{name}: GenUI {surface.get("id")} references missing stage {stage_id}')
                        if stage_id and atom and stage_id in stage_map and atom not in stage_map[stage_id]: errors.append(f'{name}: GenUI {surface.get("id")} atom {atom} is not in stage {stage_id}')
    print(f'ERRORS={len(errors)}')
    for e in errors: print('ERROR:',e)
    print('VERIFY_V2_PROTOCOLS=' + ('OK' if not errors else 'FAIL'))
    return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
