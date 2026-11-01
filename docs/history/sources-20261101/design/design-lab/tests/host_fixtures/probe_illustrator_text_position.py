# SPDX-License-Identifier: MIT
"""Instrument a fixed source bridge in memory to diagnose text positioning.

This diagnostic derivative is not a production bridge qualification. It uses
the durable native coordinator and only a new project-local test document.
"""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'packages/capabilities')]
from reconstruction.adobe_job import build_adobe_job
from design_lab.runtime.paths import resolve_paths
from design_lab.adapters import illustrator_com


def main():
    paths=resolve_paths(project_root=ROOT)
    run=paths.task_dir('text-position-probe-20260908','run-'+uuid.uuid4().hex,evidence=True)
    run.mkdir(parents=True,exist_ok=False)
    layers=[];styles={}
    for i,size in enumerate((12,24,48)):
        identity='text'+str(i)
        layers.append(dict(id=identity,type='text',name=identity,opacity=1,
            bounds=dict(x=40,y=70+i*100,width=500,height=60),inferred=True,
            zOrder=i,visible=True,locked=False,blendMode='normal',
            text=dict(content='Editable Hg / Polski',disposition='live',fontCandidates=[],
                      outlineFallback=dict(available=False,pathData=None))))
        styles[identity]=dict(font='ArialMT',size=size,color=[0,0,0])
    rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',
        canvas=dict(width=600,height=400,colorSpace='srgb'),layers=layers)
    job=build_adobe_job(rir,run,text_styles=styles).to_dict()
    source=illustrator_com._bridge()
    code=source.decode('utf-8')
    marker='item.contents = spec.text;\n                item.position = spec.position;'
    after='item.textRange.characterAttributes.fillColor = jobRGB(spec.color);'
    if code.count(marker)!=1 or code.count(after)!=1:raise ValueError('probe source changed')
    def snapshot(phase):
        return '_textProbe.push({phase:'+json.dumps(phase)+',id:spec.id,expected:spec.position.slice(0),position:item.position.slice(0),bounds:item.geometricBounds.slice(0),anchor:item.anchor.slice(0),size:item.textRange.characterAttributes.size});'
    code=code.replace(marker,marker+snapshot('before-font-size')).replace(after,after+snapshot('after-font-size'))
    code+='''
var _textProbe=[],_originalRun=runApprovedJob;
runApprovedJob=function(job,root){
 var doc=_originalRun(job,root);
 for(var i=0;i<doc.textFrames.length;i++){
  var t=doc.textFrames[i];
  _textProbe.push({phase:'reopened',id:t.name,position:t.position.slice(0),bounds:t.geometricBounds.slice(0),anchor:t.anchor.slice(0),size:t.textRange.characterAttributes.size});
 }
 var f=jobNewOutput(root+'/text-position-probe.json',root);f.encoding='UTF-8';
 if(!f.open('w'))throw Error('probe cannot write');f.write(JSON.stringify(_textProbe));f.close();
 return doc;
};
'''
    derivative=code.encode('utf-8')
    (run/'probe-source.js').write_bytes(derivative)
    (run/'probe-identity.json').write_text(json.dumps(dict(
        mode='DIAGNOSTIC_DERIVATIVE_NOT_PRODUCTION',base_bridge_sha256=hashlib.sha256(source).hexdigest(),
        derivative_sha256=hashlib.sha256(derivative).hexdigest())),encoding='utf-8')
    path=run/'adobe-host-job.json';path.write_text(json.dumps(job),encoding='utf-8')
    print(str(run),flush=True)
    illustrator_com._bridge=lambda:derivative
    sys.argv=[str(ROOT/'design-lab/tests/host_fixtures/qualify_native_tasks.py'),str(ROOT),'illustrator',str(path)]
    runpy.run_path(sys.argv[0],run_name='__main__')
    print((run/'text-position-probe.json').read_text(encoding='utf-8'))


if __name__=='__main__':main()
