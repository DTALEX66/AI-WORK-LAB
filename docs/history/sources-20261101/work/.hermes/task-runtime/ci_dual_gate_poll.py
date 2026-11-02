#!/usr/bin/env python3
import json, os, subprocess, time
R = 'D:/All projects/WORK-LAB'
OUT = os.path.join(R, '.hermes', 'task-runtime', 'ci_dual_gate_result_u20u21.json')
BR = 'u17/global-agent-policy-20260918'
HEAD = subprocess.run(['git', '-C', R, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()[:7]
def runs(wf):
    r = subprocess.run(['gh', 'run', 'list', '--workflow', wf, '--branch', BR,
                        '--limit', '5', '--json', 'databaseId,status,conclusion,headSha,event'],
                       capture_output=True, text=True, cwd=R)
    try:
        return json.loads(r.stdout or '[]')
    except Exception:
        return []
def concl(runs):
    for x in runs:
        if str(x.get('headSha', '')).startswith(HEAD) and x.get('status') == 'completed':
            return x.get('conclusion')
    return None
deadline = time.time() + 25 * 60
while True:
    g = runs('work-lab-gate'); w = runs('wlr-060-production-gates')
    gc, wc = concl(g), concl(w)
    state = {'ts': time.strftime('%H:%M:%S'), 'head': HEAD, 'gate_conclusion': gc, 'wlr_conclusion': wc,
             'final': gc is not None and wc is not None, 'gate': g, 'wlr': w}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=1)
    if state['final'] or time.time() >= deadline:
        break
    time.sleep(60)
