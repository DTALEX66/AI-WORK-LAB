# SPDX-License-Identifier: MIT
# Poll PR #139 mergeStateStatus until CLEAN, then squash-merge + delete branch +
# sync local main. BEHIND -> re-update-branch; DIRTY/UNSTABLE -> abort.
import subprocess, time

CWD = r'D:/All projects/DESIGN-LAB'

def run(*args):
    return subprocess.run(list(args), cwd=CWD, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')

def state():
    r = run('gh','pr','view','139','--json','state,mergeStateStatus')
    out = r.stdout.strip()
    import json
    try:
        d = json.loads(out)
        return d.get('state'), d.get('mergeStateStatus')
    except Exception:
        return None, out

last = None
for i in range(60):
    st, ms = state()
    sig = f'{st}/{ms}'
    if sig != last:
        print(f'[{i}] state={st} merge={ms}', flush=True)
        last = sig
    if st == 'MERGED':
        print('PR_MERGED', flush=True)
        break
    if ms == 'BEHIND':
        print('BEHIND -> update-branch', flush=True)
        run('gh','pr','update-branch','139')
        time.sleep(45)
        continue
    if ms in ('DIRTY','UNSTABLE'):
        print(f'ABORT mergeState={ms}', flush=True)
        break
    if ms == 'CLEAN':
        print('CLEAN -> squash merge', flush=True)
        m = run('gh','pr','merge','139','--squash','--delete-branch')
        print('MERGE rc=%d' % m.returncode, flush=True)
        run('git','checkout','main')
        run('git','pull')
        print('synced main', flush=True)
        break
    time.sleep(60)
print('DONE', flush=True)
