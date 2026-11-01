# SPDX-License-Identifier: MIT
"""Read-only host preflight: return before app.open, preserve pending guard."""
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.adapters.illustrator_com import _bridge,_invoke_com
from design_lab.runtime.paths import resolve_paths
paths=resolve_paths(project_root=ROOT);run=paths.checked_path(sys.argv[1])
job=json.loads((run/'patch-job.json').read_text(encoding='utf-8'))
code=re.sub(r'^#target.*$','',_bridge().decode('utf-8'),flags=re.M)
marker='var doc=app.open(input);'
if code.count(marker)!=1:raise ValueError('read-only probe insertion changed')
code=code.replace(marker,"return 'PREFLIGHT_OK';")
if len(sys.argv)>2 and sys.argv[2]=='--explicit-branches':
    code=code.replace('var children=n.kind==="group"?n.items:n.kind==="compound"?n.contours:[];',
        'var children=[];if(n.kind==="group")children=n.items;else if(n.kind==="compound")children=n.contours;')
code=code.replace('for(var j=0;j<children.length;j++)visit(children[j]);',
    'try{for(var j=0;j<children.length;j++)visit(children[j]);}catch(probeError){throw Error("visit="+n.id+" kind="+n.kind+" group="+(n.kind==="group")+" items="+typeof n.items+" children="+typeof children+" index="+j+" cause="+probeError);}')
code+='\n(function(){try{return runApprovedPatchJob('+json.dumps(job,ensure_ascii=True)+','+json.dumps(str(run))+');}catch(e){return String(e)+" line="+e.line;}})();'
print(_invoke_com(code,30))
