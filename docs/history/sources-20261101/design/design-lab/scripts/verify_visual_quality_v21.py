#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
from __future__ import annotations
import json, sys, os, stat
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
errors=[]
def load(rel):
 p=ROOT/rel
 try:return json.loads(p.read_text(encoding='utf-8'))
 except Exception as e:errors.append(f'{rel}: {e}');return None
lin=load('design-lab/research/style-lineages/STYLE_LINEAGES.json')
styles=load('design-lab/research/style-lineages/STYLE_ANALYSIS_CARDS.json')
masters=load('design-lab/research/master-studies/MASTER_REGISTRY.json')
cards=load('design-lab/research/master-studies/ANCHOR_METHOD_CARDS.json')
sources=load('design-lab/research/visual-quality/SOURCE_REGISTRY_VISUAL_V21.json')
if lin:
 ids=[x['id'] for x in lin.get('lineages',[])]
 if len(ids)!=len(set(ids)):errors.append('duplicate lineage id')
 if any(x.get('influence_cap',1)>0.35 for x in lin['lineages']):errors.append('lineage influence cap > 0.35')
if styles:
 ids=[x['id'] for x in styles.get('cards',[])]
 if styles.get('count')!=len(ids):errors.append('style analysis count mismatch')
 if lin and set(ids)!={x['id'] for x in lin['lineages']}:errors.append('style analysis and lineage id sets differ')
 for x in styles.get('cards',[]):
  if len(x.get('decision_logic',[]))<3:errors.append(f"style {x.get('id')} lacks decision logic")
  if not x.get('failure_modes'):errors.append(f"style {x.get('id')} lacks failure modes")
if masters:
 ids=[x['id'] for x in masters.get('masters',[])]
 if len(ids)!=len(set(ids)):errors.append('duplicate master id')
 if masters.get('count')!=len(ids):errors.append('master count mismatch')
 for x in masters.get('masters',[]):
  if x.get('study_status')=='research-seed-unverified' and x.get('default_lineages'):errors.append(f"unverified seed has default lineage: {x['id']}")
  if x.get('generation_eligibility','').startswith('research-only') and not x.get('evidence_requirement'):errors.append(f"research-only seed lacks evidence gate: {x['id']}")
if cards:
 ids=[x['id'] for x in cards.get('cards',[])]
 if len(ids)!=len(set(ids)):errors.append('duplicate card id')
 if cards.get('count')!=len(ids):errors.append('card count mismatch')
 if any(x.get('card_status')!='curated-local-synthesis-draft' for x in cards.get('cards',[])):errors.append('anchor card status missing')
if sources:
 for e in sources.get('entries',[]):
  if e['integration_mode']=='quarantine' and e['status']=='adopt-now':errors.append(f"quarantine source marked adopt-now: {e['id']}")
atom_ids=set()
for p in (ROOT/'packages'/'capabilities'/'atoms').glob('*/open-design.json'):
 d=load(str(p.relative_to(ROOT)))
 if d and d.get('od',{}).get('kind')=='atom':atom_ids.add(d['name'])
first_party={'research-search','discovery-question-form','direction-picker','todo-write','file-read','file-write','media-image','media-video','media-audio','live-artifact','critique-theater'}
for p in (ROOT/'packages'/'capabilities'/'scenarios').glob('*/open-design.json'):
 d=load(str(p.relative_to(ROOT)))
 if not d:continue
 for stage in d.get('od',{}).get('pipeline',{}).get('stages',[]):
  for a in stage.get('atoms',[]):
   if a not in first_party and a not in atom_ids:errors.append(f"{p.parent.name}: missing atom {a}")
# Runtime/dependency/private data is not a source JSON contract. Prune before
# enumeration, rather than filtering paths after recursively entering them.
EXCLUDED_NAMES = {
 '.git', '.project-local', '.hermes', '.venv', 'venv', 'node_modules',
 '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
 '.codex', '.claude', '.openhuman', 'auth.json', 'credentials.json',
 'tokens.json', 'id_rsa', 'id_ed25519', 'sessions.db', 'session.db',
 'cookies', 'keychain',
}
def excluded(name):
 return name.casefold() in EXCLUDED_NAMES or name.casefold().startswith(('.env', '.hermes'))
def reparse(path):
 info=path.lstat()
 return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
def source_json_files():
 def walk_error(exc):
  errors.append(f'active directory unreadable: {exc}')
 for directory, names, files in os.walk(ROOT, topdown=True, followlinks=False, onerror=walk_error):
  parent=Path(directory)
  keep=[]
  for name in sorted(names):
   if excluded(name):continue
   path=parent/name
   try:
    if reparse(path):
     errors.append(f'{path.relative_to(ROOT)}: active reparse point not scanned')
     continue
   except OSError as exc:
    errors.append(f'{path.relative_to(ROOT)}: unreadable: {exc}')
    continue
   keep.append(name)
  names[:]=keep
  for name in sorted(files):
   if excluded(name) or not name.lower().endswith('.json'):continue
   path=parent/name
   try:
    if reparse(path):
     errors.append(f'{path.relative_to(ROOT)}: active reparse point not scanned')
     continue
   except OSError as exc:
    errors.append(f'{path.relative_to(ROOT)}: unreadable: {exc}')
    continue
   yield path
for p in source_json_files():
 try:json.loads(p.read_text(encoding='utf-8'))
 except Exception as e:errors.append(f'{p.relative_to(ROOT)}: invalid JSON: {e}')
print(f'MASTER_DISCOVERY_ENTRIES={len(masters.get("masters",[])) if masters else 0}')
print(f'CURATED_METHOD_CARDS={len(cards.get("cards",[])) if cards else 0}')
print(f'STYLE_LINEAGES={len(lin.get("lineages",[])) if lin else 0}')
print(f'STYLE_ANALYSIS_CARDS={len(styles.get("cards",[])) if styles else 0}')
print(f'ATOMS={len(atom_ids)}')
print(f"SCENARIOS={len(list((ROOT/'packages'/'capabilities'/'scenarios').glob('*/open-design.json')))}")
print(f"SCHEMAS={len(list((ROOT/'design-lab'/'schemas'/'visual-quality').glob('*.json')))}")
print(f"RUBRICS={len(list((ROOT/'design-lab'/'evals'/'rubrics').glob('*.json')))}")
print(f'ERRORS={len(errors)}')
for e in errors:print('ERROR',e)
print('VERIFY_VISUAL_QUALITY_V21=' + ('OK' if not errors else 'FAIL'))
sys.exit(1 if errors else 0)
