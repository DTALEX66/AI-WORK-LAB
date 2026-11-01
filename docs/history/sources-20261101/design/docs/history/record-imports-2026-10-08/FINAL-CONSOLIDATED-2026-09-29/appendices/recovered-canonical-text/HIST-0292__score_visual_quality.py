#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('report');p.add_argument('--rubric',required=True);a=p.parse_args()
 report=json.loads(Path(a.report).read_text(encoding='utf-8'));rubric=json.loads(Path(a.rubric).read_text(encoding='utf-8'))
 axes=report.get('axes',{});total=weight=0.0;missing=[]
 for spec in rubric['axes']:
  item=axes.get(spec['id'])
  if not item:missing.append(spec['id']);continue
  w=float(spec.get('weight',1));total+=float(item['score'])*w;weight+=w
 score=round(total/weight,2) if weight else 0
 failed=[g['id'] for g in report.get('hard_gates',[]) if not g.get('pass')]
 decision='reject' if failed or score<rubric['acceptance']['reject_below'] else ('revise' if score<rubric['acceptance']['accept'] else 'accept')
 print(json.dumps({'score':score,'decision':decision,'failed_gates':failed,'missing_axes':missing},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
