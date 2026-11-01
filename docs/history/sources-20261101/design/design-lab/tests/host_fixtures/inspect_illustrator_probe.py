# SPDX-License-Identifier: MIT
"""Read only the known failed diagnostic document; keep its host guard held."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.adapters.illustrator_com import _invoke_com
from design_lab.runtime.paths import resolve_paths

run=resolve_paths(project_root=ROOT).checked_path(ROOT/'.project-local/task-artifacts/text-position-probe-20260908/run-752fbabb7d704289966b0d2685b88b70')
output=run/'readonly-diagnostic.json'
if output.exists():raise ValueError('preserve existing diagnosis')
source=r'''(function(){
 var result=['JSON='+typeof JSON,'STRINGIFY='+(typeof JSON==='undefined'?'absent':typeof JSON.stringify),'DOCUMENTS='+app.documents.length];
 var target=File(__TARGET_LITERAL__),found=0;
 for(var i=0;i<app.documents.length;i++){
  var d=app.documents[i];if(!d.saved || d.fullName.fsName.toLowerCase()!==target.fsName.toLowerCase())continue;
  found++;for(var j=0;j<d.textFrames.length;j++){
   var t=d.textFrames[j];result.push('TEXT='+t.name+'|'+t.position.join(',')+'|'+t.geometricBounds.join(',')+'|'+t.anchor.join(',')+'|'+t.textRange.characterAttributes.size);
  }
 }
 result.push('TARGETS='+found);
 if(typeof _textProbe!=='undefined')for(var k=0;k<_textProbe.length;k++){
  var p=_textProbe[k];result.push('PROBE='+p.phase+'|'+p.id+'|'+p.position.join(',')+'|'+p.bounds.join(',')+'|'+p.anchor.join(',')+'|'+p.size);
 }
 return result.join('\n');
})();'''.replace('__TARGET_LITERAL__',json.dumps(str(run/'master.ai')))
observed=_invoke_com(source,30)
output.write_text(json.dumps(dict(mode='READ_ONLY_GUARD_RETAINED',observed=observed),indent=2),encoding='utf-8')
print(observed)
