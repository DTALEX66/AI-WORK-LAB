#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('before');p.add_argument('after');a=p.parse_args()
b=json.loads(Path(a.before).read_text(encoding='utf-8'));c=json.loads(Path(a.after).read_text(encoding='utf-8'))
axes=sorted(set(b.get('axes',{}))|set(c.get('axes',{})))
deltas={x:round(c.get('axes',{}).get(x,{}).get('score',0)-b.get('axes',{}).get(x,{}).get('score',0),2) for x in axes}
print(json.dumps({'overall_delta':round(c.get('overall',0)-b.get('overall',0),2),'axis_deltas':deltas,'regressions':[k for k,v in deltas.items() if v<0]},ensure_ascii=False,indent=2))
