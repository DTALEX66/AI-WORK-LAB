# SPDX-License-Identifier: MIT
"""Explicit native Photoshop qualification; synthetic fixture, not product E3.

Creates new project-local files only. --execute-com authorizes this fixed test
sequence, not arbitrary host scripts. Failed/timeout effects are retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from design_lab.runtime.paths import resolve_paths


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    paths = resolve_paths(project_root=ROOT)
    run = paths.task_dir('photoshop-native-20260908', 'run-'+uuid.uuid4().hex, evidence=True)
    run.mkdir(parents=True, exist_ok=False)
    source = paths.checked_path(ROOT/'.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/fixture.png')
    shutil.copyfile(source, run/'input.png')
    job = dict(schemaVersion='design-lab/photoshop-native-job/v1', jobId='ps-native',
        runRoot=run.as_posix(), width=800, height=600, outputName='baseline.psd', previewName='baseline.png',
        assets=[dict(id='input', path=(run/'input.png').as_posix())], layers=[
            dict(id='background', kind='fill', bounds=[0,0,800,600], color=[241,243,239]),
            dict(id='title', kind='text', text='DESIGN LAB / NATIVE', font='ArialMT', size=32,
                 position=[45,80], color=[23,45,60]),
            dict(id='panel', kind='fill', bounds=[45,130,710,365], color=[20,110,101]),
            dict(id='image-group', kind='group', mask=[300,175,175,210], children=[
                dict(id='image', kind='raster', assetId='input', position=[280,160], width=256, height=256)]),
            dict(id='footer', kind='text', text='LIVE TEXT + IMAGE + GROUP MASK', font='ArialMT', size=18,
                 position=[45,550], color=[23,45,60])])
    bridge = ROOT/'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx'
    script = re.sub(r'^#target.*$', '', bridge.read_text(encoding='utf-8'), flags=re.M)
    script += '\n(function(){var root='+json.dumps(run.as_posix())+',job='+json.dumps(job)+r''';
var stage='preflight',before=app.documents.length,doc=null;
try{
 if(before!==0)throw Error('qualification requires no open documents');
 stage='baseline';doc=psRunJob(job,root);
 stage='text-patch';doc=psPatch(doc,root+'/baseline.psd',{kind:'text',id:'title',text:'DESIGN LAB / EDITED'},root+'/text-edit.psd',root);
 psExportPNG(doc,root+'/text-edit.png',root);
 stage='image-patch';doc=psPatch(doc,root+'/text-edit.psd',{kind:'move',id:'image',delta:[24,12]},root+'/image-edit.psd',root);
 psExportPNG(doc,root+'/image-edit.png',root);
 if(!psHasMask(psFind(doc,'image-group')))throw Error('mask lost after patches');
 doc.close(SaveOptions.DONOTSAVECHANGES);doc=null;
 stage='restore';doc=app.open(File(root+'/baseline.psd'));psReadback(doc,job);
 psExportPNG(doc,root+'/restored.png',root);doc.close(SaveOptions.DONOTSAVECHANGES);doc=null;
 return ['PASS',app.version,before,app.documents.length,'text-edit','image-move','baseline-restored'].join('\t');
}catch(e){return ['FAIL',stage,String(e),e.line,before,app.documents.length].join('\t');}
})();'''
    (run/'job.json').write_text(json.dumps(job, indent=2), encoding='utf-8')
    (run/'run.jsx').write_text(script, encoding='utf-8')
    print(json.dumps(dict(run=str(run))), flush=True)
    return run, script, bridge


def execute(run, script, bridge):
    command = """$ErrorActionPreference='Stop';
[Console]::InputEncoding=New-Object System.Text.UTF8Encoding($false);
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false);
$source=[Console]::In.ReadToEnd();
$photoshop=New-Object -ComObject Photoshop.Application;
$result=$photoshop.DoJavaScript($source);
[Console]::Out.Write([string]$result);
"""
    proof = dict(started=datetime.now(timezone.utc).isoformat(), os=platform.platform(),
        repo_sha=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        bridge_sha256=digest(bridge), script_sha256=digest(run/'run.jsx'), job_sha256=digest(run/'job.json'),
        input_sha256=digest(run/'input.png'), authorization='active user goal: native software tests; new project-local files only',
        fixture='synthetic; not a complex reference or Human Jury acceptance', status='OUTCOME_UNKNOWN')
    (run/'invocation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    result = subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',command],
        input=script,capture_output=True,text=True,encoding='utf-8',timeout=180,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    proof.update(exit_code=result.returncode, receipt=result.stdout.strip(), stderr=result.stderr,
                 ended=datetime.now(timezone.utc).isoformat())
    (run/'result.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(dict(exit_code=result.returncode,receipt=result.stdout.strip())),flush=True)
    if result.returncode or not result.stdout.startswith('PASS\t'):
        raise RuntimeError('native qualification failed; retain partial effects, do not auto-repeat')
    parts=result.stdout.strip().split('\t')
    if len(parts)!=7 or parts[2:4]!=['0','0']:raise AssertionError('document count receipt mismatch')
    proof['artifacts']={p.name:dict(sha256=digest(p),bytes=p.stat().st_size) for p in run.iterdir() if p.suffix in ('.psd','.png')}
    for name in ('baseline.psd','text-edit.psd','image-edit.psd'):
        with (run/name).open('rb') as stream:
            if stream.read(6)!=b'8BPS\x00\x01':raise AssertionError('not a native PSD')
    images=[]
    for name in ('baseline.png','text-edit.png','image-edit.png','restored.png'):
        with Image.open(run/name) as image:
            if image.format!='PNG' or image.size!=(800,600):raise AssertionError('wrong preview')
            images.append(image.convert('RGB'))
    boxes=[ImageChops.difference(images[a],images[b]).getbbox() for a,b in ((0,1),(1,2),(0,3))]
    if not boxes[0] or boxes[0][3]>120:raise AssertionError('text edit absent or nonlocal')
    if not boxes[1] or boxes[1][0]<300 or boxes[1][1]<175 or boxes[1][2]>475 or boxes[1][3]>385:
        raise AssertionError('image edit absent or escaped group mask')
    if boxes[2] is not None:raise AssertionError('baseline restoration differs')
    if digest(run/'input.png')!=proof['input_sha256']:raise AssertionError('input modified')
    proof.update(status='NATIVE_ROUNDTRIP_VERIFIED',pixel_change_boxes=boxes)
    (run/'result.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=proof['status'],pixel_change_boxes=boxes)),flush=True)


def execute_adapter(run, installed_python):
    """Qualify the installed product adapter, not this fixture's own COM helper."""
    executable=resolve_paths(project_root=ROOT).checked_path(installed_python)
    code="""import json,sys;from pathlib import Path
import design_lab.adapters.photoshop_com as adapter
job=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
result=adapter.execute(job,project_root=sys.argv[2],approved_root=sys.argv[3])
print(json.dumps(dict(readback=result,interpreter=sys.executable,module=adapter.__file__)))
"""
    result=subprocess.run([str(executable),'-I','-B','-c',code,str(run/'job.json'),str(ROOT),str(run)],
        cwd=run,capture_output=True,text=True,encoding='utf-8',timeout=150)
    if result.returncode:
        (run/'adapter-failure.json').write_text(json.dumps(dict(status='OUTCOME_UNKNOWN',exit_code=result.returncode,
            stdout=result.stdout,stderr=result.stderr),indent=2),encoding='utf-8')
        raise RuntimeError('installed adapter failed; retain partial effects')
    proof=json.loads(result.stdout)
    if proof['readback']['status']!='NATIVE_READBACK':raise AssertionError('native readback missing')
    proof.update(repo_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        observed_at=datetime.now(timezone.utc).isoformat(),os=platform.platform(),
        adapter_source_sha256=digest(ROOT/'src/design_lab/adapters/photoshop_com.py'))
    (run/'installed-readback.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(proof),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--execute-com',action='store_true')
    mode.add_argument('--installed-python',help='Execute the product adapter with an isolated installed interpreter')
    args=parser.parse_args()
    run,script,bridge=prepare()
    if args.execute_com:execute(run,script,bridge)
    elif args.installed_python:execute_adapter(run,args.installed_python)
