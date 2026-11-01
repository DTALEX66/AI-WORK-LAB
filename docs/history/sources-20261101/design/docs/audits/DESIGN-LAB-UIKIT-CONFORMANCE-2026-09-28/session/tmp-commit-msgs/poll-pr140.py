# SPDX-License-Identifier: MIT
# Poll PR #140 mergeStateStatus until CLEAN, then squash-merge + delete branch +
# sync local main. BEHIND -> re-update-branch; DIRTY/UNSTABLE -> abort.
import subprocess, time, json

CWD = r'D:\All projects\DESIGN-LAB'
def run(*a):
    return subprocess.run(list(a), cwd=CWD, capture_output=True, text=True, encoding='utf-8', errors='replace')

def state():
    r = run('gh','pr','view','140','--json','state,mergeStateStatus')
    try:
        d = json.loads(r.stdout.strip())
        return d.get('state'), d.get('mergeStateStatus')
    except Exception:
        return None, r.stdout.strip()

last=None
for i in range(60):
    st, ms = state()
    sig=f'{st}/{ms}'
    if sig!=last:
        print(f'[{i}] state={st} merge={ms}', flush=True); last=sig
    if st=='MERGED':
        print('PR_MERGED', flush=True); break
    if ms=='BEHIND':
        print('BEHIND -> update-branch', flush=True)
        run('gh','pr','update-branch','140'); time.sleep(45); continue
    if ms in ('DIRTY','UNSTABLE'):
        print(f'ABORT mergeState={ms}', flush=True); break
    if ms=='CLEAN':
        print('CLEAN -> squash merge', flush=True)
        m=run('gh','pr','merge','140','--squash','--delete-branch')
        print('MERGE rc=%d' % m.returncode, flush=True)
        run('git','checkout','main'); run('git','pull'); run('git','remote','prune','origin')
        print('synced main + pruned stale refs', flush=True); break
    time.sleep(60)
print('DONE', flush=True)
