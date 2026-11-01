\
#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors=[]

def err(msg): errors.append(msg)

def load(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e: err(f'JSON {path.relative_to(ROOT)}: {e}'); return None

for p in ROOT.rglob('*.json'): load(p)

tasks_doc=load(ROOT/'tasks/task-cards.json') or {}
tasks=tasks_doc.get('tasks',[])
ids=[t.get('id') for t in tasks]
if len(ids)!=len(set(ids)): err('duplicate task ids')
idset=set(ids)
for t in tasks:
    for d in t.get('dependencies',[]):
        if d not in idset: err(f"{t.get('id')} missing dependency {d}")
    if not t.get('acceptance'): err(f"{t.get('id')} has no acceptance")

# Overlay is expected to be V2(77) + V2.1(122) with no collisions.
overlay=[p for p in (ROOT/'overlay').rglob('*') if p.is_file()]
if len(overlay)!=199: err(f'overlay file count expected 199, got {len(overlay)}')

manifest=load(ROOT/'PACK_MANIFEST.json') or {}
for item in manifest.get('files',[]):
    p=ROOT/item['path']
    if not p.is_file(): err(f"missing {item['path']}"); continue
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    if h!=item['sha256']: err(f"hash mismatch {item['path']}")

print(f'TASKS={len(tasks)}')
print(f'OVERLAY_FILES={len(overlay)}')
print(f'ERRORS={len(errors)}')
for e in errors: print('ERROR:',e)
print('VERIFY_COMPLETE_TASKPACK=' + ('OK' if not errors else 'FAIL'))
sys.exit(1 if errors else 0)
