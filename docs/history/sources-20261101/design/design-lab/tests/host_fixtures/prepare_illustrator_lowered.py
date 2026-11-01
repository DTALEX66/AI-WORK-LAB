# SPDX-License-Identifier: MIT
"""Prepare a synthetic cross-language native qualification, not a user design.

Default preparation does not launch a host. Explicit --execute-com runs the
product adapter; otherwise generated JSX needs an authorized script entry.
All output stays project-local ignored.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid
import argparse
import subprocess

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'packages/capabilities'))
sys.path.insert(0,str(ROOT/'src'))
from reconstruction.adobe_job import build_adobe_job
from design_lab.runtime.paths import resolve_paths


def prepare():
    paths=resolve_paths(project_root=ROOT)
    run=paths.task_dir('illustrator-lowering-20260908','run-'+uuid.uuid4().hex,evidence=True)
    run.mkdir(parents=True,exist_ok=False)
    source=paths.checked_path(ROOT/'.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/fixture.png')
    shutil.copyfile(source,run/'input.png')
    def node(identity,kind,z,bounds,**extra):
        return dict(id=identity,type=kind,name=identity,opacity=1,bounds=dict(zip(('x','y','width','height'),bounds)),
                    inferred=True,zOrder=z,visible=True,locked=False,blendMode='normal',**extra)
    curve=node('curve','path',1,[40,60,680,320],
        geometry=dict(pathData='M 40 360 C 200 60 500 60 720 300 L 720 380 L 40 380 Z',closed=True),
        style=dict(fill='#146e65'),masks=[])
    image=node('image','raster',2,[300,400,120,130],raster=dict(path=(run/'input.png').relative_to(ROOT).as_posix(),
        crop=dict(x=0,y=0,width=256,height=256),alpha=1,sourceMappings=[]))
    title=node('title','text',3,[340,40,400,60],text=dict(content='DESIGN LAB / LINKED',disposition='live',
        fontCandidates=[dict(family='Arial',weight=400,style='normal',confidence=1)],outlineFallback=dict(available=False,pathData=None)))
    badge=node('badge','primitive',4,[60,430,160,70],primitive=dict(kind='rect',parameters={}),
        style=dict(fill='#eab45d'),masks=[dict(id='badge-mask',pathData='M 60 430 L 220 430 L 200 500 L 80 500 Z',operation='intersect',opacity=1)])
    rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',canvas=dict(width=800,height=600,colorSpace='srgb',
        background=dict(color='#f1f3ef',recorded=True)),layers=[title,image,badge,curve])
    job=build_adobe_job(rir,run,text_styles={'title':dict(font='ArialMT',size=28,color=[23,45,60])}).to_dict()
    for name,data in (('source-rir.json',rir),('adobe-host-job.json',job)):
        (run/name).write_text(json.dumps(data,ensure_ascii=True,sort_keys=True,indent=2),encoding='utf-8')
    # JSON values are serialized as literals, never interpolated as executable user text.
    bridge=(ROOT/'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx').as_posix()
    script='''#target illustrator
(function(){
 var root=ROOT_LITERAL,job=JOB_LITERAL;
 $.evalFile(File(BRIDGE_LITERAL));
 var before=app.documents.length,doc=null;
 var result=File(root+'/result.tsv');
 if(result.exists)throw Error('refusing existing result');
 try {
   doc=runApprovedJob(job,root);
   var title=patchObject(doc,'text','title');
   var curve=patchObject(doc,'path','curve');
   var text='PASS\\thost='+app.version+'\\ttext='+title.contents+'\\tfont='+title.textRange.characterAttributes.textFont.name+'\\tanchor='+curve.pathPoints[0].anchor+'\\tright='+curve.pathPoints[0].rightDirection+'\\trirHash='+job.rirHash;
   doc.close(SaveOptions.DONOTSAVECHANGES);doc=null;
   text+='\\tdocumentsBefore='+before+'\\tdocumentsAfter='+app.documents.length;
   result.encoding='UTF-8';if(!result.open('w'))throw Error('cannot write result');result.write(text);result.close();
 } catch(e) {
   result.encoding='UTF-8';if(result.open('w')){result.write('FAIL\\t'+e+'\\tline='+e.line);result.close();}
   // Retain partial effects for coordinator reconciliation; do not close unrelated docs.
   throw e;
 }
})();
'''.replace('ROOT_LITERAL',json.dumps(run.as_posix())).replace('JOB_LITERAL',json.dumps(job,ensure_ascii=True)).replace('BRIDGE_LITERAL',json.dumps(bridge))
    (run/'run.jsx').write_text(script,encoding='utf-8')
    print(json.dumps(dict(run=str(run),script=str(run/'run.jsx'),rir_hash=job['rirHash'],
        jsx_sha256=hashlib.sha256((run/'run.jsx').read_bytes()).hexdigest())))
    return run,job


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-com',action='store_true',help='Explicitly execute the fixed product COM adapter in Illustrator')
    parser.add_argument('--installed-python',help='Project-local installed interpreter; child runs isolated without source paths')
    args=parser.parse_args()
    run,job=prepare()
    if args.execute_com:
        if args.installed_python:
            executable=resolve_paths(project_root=ROOT).checked_path(args.installed_python)
            code="""import json,sys;from pathlib import Path
import design_lab.adapters.illustrator_com as adapter
job=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
result=adapter.execute(job,project_root=sys.argv[2],approved_root=sys.argv[3])
print(json.dumps(dict(readback=result,qualification=dict(interpreter=sys.executable,module=adapter.__file__))))
"""
            completed=subprocess.run([str(executable),'-I','-B','-c',code,str(run/'adobe-host-job.json'),str(ROOT),str(run)],
                cwd=run,capture_output=True,text=True,encoding='utf-8',timeout=150,check=True)
            proof=json.loads(completed.stdout);result=proof['readback']
            (run/'installed-qualification.json').write_text(json.dumps(proof,sort_keys=True,indent=2),encoding='utf-8')
            print(json.dumps(proof['qualification']))
        else:
            from design_lab.adapters.illustrator_com import execute
            result=execute(job,project_root=ROOT,approved_root=run)
        (run/'com-readback.json').write_text(json.dumps(result,sort_keys=True,indent=2),encoding='utf-8')
        print(json.dumps(result,sort_keys=True))
