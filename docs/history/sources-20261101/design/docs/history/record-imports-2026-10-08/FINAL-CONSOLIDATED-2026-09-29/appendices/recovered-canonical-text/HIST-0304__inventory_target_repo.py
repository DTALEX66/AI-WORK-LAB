\
#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

ap=argparse.ArgumentParser(); ap.add_argument('target'); ap.add_argument('--output')
a=ap.parse_args(); root=Path(a.target).resolve()
def cmd(*args): return subprocess.check_output(args,text=True,cwd=root,stderr=subprocess.STDOUT).strip()
if root.drive.upper().startswith('E:'): raise SystemExit('E drive forbidden')
if Path(cmd('git','rev-parse','--show-toplevel')).resolve()!=root: raise SystemExit('target is not Git root')
files=[]
for p in root.rglob('*'):
    if not p.is_file(): continue
    rel=p.relative_to(root)
    if rel.parts and rel.parts[0] in {'.git','.hermes','node_modules'}: continue
    files.append({'path':rel.as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
data={'generated_at':datetime.now(timezone.utc).isoformat(),'root':str(root),'branch':cmd('git','branch','--show-current'),'head':cmd('git','rev-parse','HEAD'),'tree':cmd('git','rev-parse','HEAD^{tree}'),'status':cmd('git','status','--short','--branch'),'files':files}
out=Path(a.output) if a.output else root/'.hermes'/'task-artifacts'/'open-design-v3'/'baseline-inventory.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(out)
