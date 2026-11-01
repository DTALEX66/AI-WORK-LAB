#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('critique'); ap.add_argument('--threshold',type=float,default=8.0); a=ap.parse_args()
    d=json.loads(Path(a.critique).read_text(encoding='utf-8')); scores=d.get('scores',[])
    total=sum(float(x['score'])*float(x.get('weight',1)) for x in scores); weight=sum(float(x.get('weight',1)) for x in scores)
    result=total/weight if weight else 0
    blockers=[x for x in d.get('automated_checks',[]) if x.get('result')=='fail' and x.get('severity','blocker')=='blocker']
    print(f'WEIGHTED_SCORE={result:.2f}'); print(f'BLOCKERS={len(blockers)}'); print('ACCEPT=' + ('YES' if result>=a.threshold and not blockers else 'NO'))
    return 0 if result>=a.threshold and not blockers else 1
if __name__=='__main__': raise SystemExit(main())
