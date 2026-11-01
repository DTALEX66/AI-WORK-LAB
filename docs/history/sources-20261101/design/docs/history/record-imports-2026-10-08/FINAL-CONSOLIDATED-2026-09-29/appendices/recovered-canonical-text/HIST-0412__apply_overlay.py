#!/usr/bin/env python3
from __future__ import annotations
import argparse,shutil,hashlib,json
from pathlib import Path

def sha(p):
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()
def main():
 ap=argparse.ArgumentParser(description='Safely apply the additive V2.1 visual-quality overlay.')
 ap.add_argument('repo');ap.add_argument('--overwrite',action='store_true');a=ap.parse_args()
 src=Path(__file__).resolve().parent/'overlay';dst=Path(a.repo).resolve()
 if not (dst/'opendesign-assistance').is_dir():raise SystemExit('Target does not look like OPEN-DESIGN-Assistance')
 changes=[]
 for p in sorted(src.rglob('*')):
  if not p.is_file():continue
  rel=p.relative_to(src);out=dst/rel;out.parent.mkdir(parents=True,exist_ok=True)
  if out.exists() and sha(out)!=sha(p):
   if not a.overwrite:changes.append({'path':str(rel),'status':'conflict-skipped'});continue
   backup=out.with_suffix(out.suffix+'.v20-backup');shutil.copy2(out,backup);changes.append({'path':str(rel),'status':'updated','backup':str(backup.relative_to(dst))})
  elif out.exists():changes.append({'path':str(rel),'status':'unchanged'});continue
  else:changes.append({'path':str(rel),'status':'created'})
  shutil.copy2(p,out)
 report=dst/'V21_VISUAL_QUALITY_APPLY_REPORT.json';report.write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(report);print('created',sum(x['status']=='created' for x in changes),'updated',sum(x['status']=='updated' for x in changes),'conflicts',sum(x['status']=='conflict-skipped' for x in changes))
if __name__=='__main__':main()
