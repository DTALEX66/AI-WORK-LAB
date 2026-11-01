\
#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OVERLAY=ROOT/'overlay'

def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def git_root(target):
    try:
        out=subprocess.check_output(['git','-C',str(target),'rev-parse','--show-toplevel'], text=True, stderr=subprocess.STDOUT).strip()
        return Path(out).resolve()
    except Exception as e: raise SystemExit(f'BLOCKED: target is not a readable Git repo: {e}')

def main():
    ap=argparse.ArgumentParser(description='Plan or safely apply the unified additive overlay.')
    ap.add_argument('target')
    ap.add_argument('--plan', action='store_true', help='Explicit plan mode (default).')
    ap.add_argument('--apply', action='store_true', help='Actually create non-conflicting files.')
    ap.add_argument('--overwrite', action='store_true', help='Replace conflicts after backing them up; requires --apply.')
    a=ap.parse_args()
    if a.apply and a.plan: raise SystemExit('choose --plan or --apply')
    if a.overwrite and not a.apply: raise SystemExit('--overwrite requires --apply')
    target=Path(a.target).resolve()
    if target.drive.upper().startswith('E:') or str(target).upper().startswith('E:\\'):
        raise SystemExit('BLOCKED: E drive is forbidden')
    root=git_root(target)
    if root != target: raise SystemExit(f'BLOCKED: target must be Git root; resolved {root}')
    if target.name.lower()!='open-design-assistance':
        raise SystemExit(f'BLOCKED: unexpected repository name {target.name}')
    mode='apply' if a.apply else 'plan'
    ts=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    artifact=target/'.hermes'/'task-artifacts'/'open-design-v3'
    backup=artifact/'backups'/ts
    actions=[]
    for src in sorted(p for p in OVERLAY.rglob('*') if p.is_file()):
        rel=src.relative_to(OVERLAY)
        dst=target/rel
        if dst.is_file():
            if h(src)==h(dst): status='same'
            else: status='overwrite' if a.overwrite else 'conflict-skip'
        elif dst.exists(): status='blocked-nonfile'
        else: status='create'
        actions.append({'path':rel.as_posix(),'status':status,'source_sha256':h(src)})
        if a.apply:
            if status=='create':
                dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src,dst)
            elif status=='overwrite':
                b=backup/rel; b.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(dst,b); shutil.copy2(src,dst)
            elif status=='blocked-nonfile':
                raise SystemExit(f'BLOCKED non-file target: {rel}')
    report={'mode':mode,'target':str(target),'timestamp':ts,'counts':{},'actions':actions}
    for x in actions: report['counts'][x['status']]=report['counts'].get(x['status'],0)+1
    if a.apply:
        artifact.mkdir(parents=True, exist_ok=True)
        rp=artifact/f'overlay-{mode}-{ts}.json'; rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(rp)
    print(json.dumps(report['counts'],ensure_ascii=False,indent=2))
    if any(x['status'].startswith('blocked') for x in actions): return 2
    if any(x['status']=='conflict-skip' for x in actions): return 3
    return 0
if __name__=='__main__': raise SystemExit(main())
