# SPDX-License-Identifier: MIT
"""Independent read-only inspection of one known late PSD; guard stays held.

Run only after the original host script is observed quiescent. Never attaches
to an already-open target or turns this receipt into a successful task.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.adapters.photoshop_com import _invoke_com
from design_lab.runtime.paths import resolve_paths


def main():
    if sys.argv[1:]:raise ValueError('fixed inspection accepts no arguments')
    paths=resolve_paths(project_root=ROOT)
    run=paths.checked_path(ROOT/'.project-local/task-artifacts/real-poster-ps-20260908/run-2d83da284b144263ab26ab00028cbd64')
    output=run/'late-readonly-readback.json'
    if output.exists():raise ValueError('immutable readback already exists')
    database=paths.checked_path(paths.runtime_root/'service/state.db')
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as conn:
        row=conn.execute('SELECT request_json FROM native_execution_v1 WHERE attempt_id=? AND host=?',
            ('att-52901594c1684782a99b689538aaebf3','photoshop')).fetchone()
    if row is None:raise ValueError('original execution binding missing')
    request=json.loads(row[0]);job=request['job']
    if job!=json.loads((run/'photoshop-job.json').read_text(encoding='utf-8')):raise ValueError('job changed')
    if paths.checked_path(job['runRoot'])!=run or job['outputName']!='master.psd':raise ValueError('wrong run')
    def digest(p):
        before=p.stat();value=hashlib.sha256(p.read_bytes()).hexdigest();after=p.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('file changing')
        return dict(sha256=value,byte_size=after.st_size)
    artifacts={name:digest(run/name) for name in ('master.psd','photoshop-preview.png')}
    for value,expected in request['inputs'].items():
        p=paths.checked_path(value)
        if not p.is_relative_to(run) or digest(p)!=expected:raise ValueError('input changed')
    bridge=ROOT/'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx'
    source=re.sub(r'^#target.*$','',bridge.read_text(encoding='utf-8'),flags=re.M)
    source+='\n(function(){var job='+json.dumps(job,ensure_ascii=True)+r''';
var before=app.documents.length,previous=before?app.activeDocument:null,doc=null,ids=[],i;
var target=File(job.runRoot+'/'+job.outputName);
for(i=0;i<before;i++){
 var d=app.documents[i];ids.push(d.id);var path=null;
 try{path=d.fullName.fsName;}catch(e){}
 if(path!==null&&psPath(path)===psPath(target.fsName))throw Error('target already open; do not attach');
}
try{doc=app.open(target);psReadback(doc,job);}
finally{if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);if(previous)app.activeDocument=previous;}
if(app.documents.length!==before)throw Error('document count changed');
for(i=0;i<before;i++)if(app.documents[i].id!==ids[i])throw Error('unrelated document changed');
return ['DL_PS_LATE_READONLY',app.version,before,app.documents.length].join('\t');
})();'''
    started=time.monotonic();parts=_invoke_com(source,120).split('\t');elapsed=time.monotonic()-started
    if (len(parts)!=4 or parts[0]!='DL_PS_LATE_READONLY' or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}',parts[1])
        or not parts[2].isdigit() or parts[2]!=parts[3]):raise ValueError('invalid readback receipt')
    if any(digest(run/name)!=expected for name,expected in artifacts.items()):raise ValueError('output changed')
    result=dict(status='LATE_READBACK_ARTIFACT_UNPUBLISHED_GUARD_RETAINED',
        observed_at=datetime.now(timezone.utc).isoformat(),host_version=parts[1],elapsed_seconds=elapsed,
        documents_before=int(parts[2]),documents_after=int(parts[3]),artifacts=artifacts,
        reader_sha256=hashlib.sha256(bridge.read_bytes()).hexdigest(),
        original_attempt='att-52901594c1684782a99b689538aaebf3',
        limits=['not original dispatch receipt','no quality or rights acceptance','no pixel geometry readback',
                'no task publication or guard release','no local edits or restoration verified'])
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()
