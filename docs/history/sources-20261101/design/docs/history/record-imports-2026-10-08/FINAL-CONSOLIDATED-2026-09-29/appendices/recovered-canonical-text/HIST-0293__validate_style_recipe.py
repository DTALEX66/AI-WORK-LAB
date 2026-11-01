#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('recipe');a=ap.parse_args();d=json.loads(Path(a.recipe).read_text(encoding='utf-8'))
 errs=[]
 if d['project_dna']['weight']<0.5:errs.append('project_dna weight must be >= 0.5')
 lw=sum(float(x['weight']) for x in d.get('lineage_weights',[]))
 mw=sum(float(x['weight']) for x in d.get('master_method_refs',[]))
 if lw>0.45:errs.append('combined lineage weight must be <= 0.45')
 if mw>0.35:errs.append('combined master-method weight must be <= 0.35')
 prompt=d.get('originality_guard',{}).get('name_free_generation_prompt','')
 names=[x['id'].replace('-',' ') for x in d.get('master_method_refs',[])]
 if any(n.lower() in prompt.lower() for n in names if len(n)>3):errs.append('generation prompt appears to contain a master name')
 print(json.dumps({'valid':not errs,'errors':errs,'weights':{'project':d['project_dna']['weight'],'lineages':lw,'masters':mw}},ensure_ascii=False,indent=2))
 raise SystemExit(1 if errs else 0)
if __name__=='__main__':main()
