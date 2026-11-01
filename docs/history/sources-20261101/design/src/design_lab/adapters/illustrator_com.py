# SPDX-License-Identifier: MIT
"""Fixed native Illustrator COM dispatch and file readback sealing.

Internal adapter, not an arbitrary script endpoint. Caller owns rights, job
qualification, operation/attempt and the host writer lease. A dispatch timeout
cannot prove Adobe stopped; never kill the host or automatically repeat it.
"""
from importlib.resources import files
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image
from ..interop import InteropError, load_schema, schema_errors
from ..runtime.paths import PROJECT_ROOT, resolve_paths


class IllustratorDispatchError(RuntimeError):
    def __init__(self, code, *, outcome_unknown=False):
        super().__init__(code)
        self.outcome_unknown = outcome_unknown


def _bridge():
    packaged=files('design_lab').joinpath('resources','adobe','reconstruction-assemble.jsx')
    if packaged.is_file():return packaged.read_bytes()
    root=Path(__file__).resolve().parents[3]
    source=root/'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx'
    if source.is_file():return source.read_bytes()
    raise IllustratorDispatchError('ILLUSTRATOR_BRIDGE_MISSING')


def _invoke_com(script,timeout):
    executable=shutil.which('powershell.exe') if os.name=='nt' else None
    if not executable:raise IllustratorDispatchError('WINDOWS_COM_UNAVAILABLE')
    # Constant command, no profile, no policy override, no script/request in argv.
    command="""$ErrorActionPreference='Stop';
[Console]::InputEncoding=New-Object System.Text.UTF8Encoding($false);
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false);
$source=[Console]::In.ReadToEnd();
$illustrator=New-Object -ComObject Illustrator.Application;
$result=$illustrator.DoJavaScript($source);
[Console]::Out.Write([string]$result);
"""
    result=subprocess.run([executable,'-NoLogo','-NoProfile','-NonInteractive','-Command',command],
        input=script,capture_output=True,text=True,encoding='utf-8',timeout=timeout,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise IllustratorDispatchError('COM_EXECUTION_FAILED',outcome_unknown=True)
    return result.stdout.strip()


def _digest(path,limit):
    before=path.stat()
    if not path.is_file() or before.st_size==0 or before.st_size>limit or before.st_nlink!=1:
        raise ValueError('invalid artifact size/link')
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('artifact changed while hashing')
    return dict(sha256=h.hexdigest(),byte_size=after.st_size)


def quiesce(job,*,project_root,approved_root,timeout=60):
    """Close only the saved task-native document; preserve all output bytes.

    Caller holds the original non-expiring host guard and owns reconciliation.
    A synchronous host acknowledgement releases no guard by itself and does
    not prove output correctness. Never close unsaved or unrelated documents.
    """
    paths=resolve_paths(project_root=project_root)
    root=paths.checked_path(approved_root)
    if paths.checked_path(job['runRoot'])!=root or not root.is_dir():raise ValueError('unapproved root')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}',job['jobId']):raise ValueError('invalid identity')
    if set(job['targets'])!={'ai','png','svg'}:raise ValueError('invalid targets')
    targets={kind:paths.checked_path(value) for kind,value in job['targets'].items()}
    for kind,path in targets.items():
        if not path.is_relative_to(root) or path==root or path.suffix.lower()!='.'+kind:raise ValueError('target outside root')
    def snapshot():
        return {kind:_digest(path,256*1024*1024) for kind,path in targets.items() if path.exists()}
    before_files=snapshot()
    script=r'''(function(){
var target=File(__TARGET__),before=app.documents.length,match=null,count=0;
for(var i=0;i<app.documents.length;i++){
 var d=app.documents[i],name=null;
 try{name=d.fullName.fsName;}catch(e){continue;}
 if(name.toLowerCase()===target.fsName.toLowerCase()){
  if(d.saved!==true)throw Error('task has unsaved changes; preserve');
  match=d;count++;
 }
}
if(count>1)throw Error('ambiguous task document');
if(match)match.close(SaveOptions.DONOTSAVECHANGES);
if(app.documents.length!==before-count)throw Error('document count changed');
return ['DL_QUIESCENT_V1',__JOB__,before,app.documents.length,count].join('|');
})();'''.replace('__TARGET__',json.dumps(str(targets['ai']))).replace('__JOB__',json.dumps(job['jobId']))
    reply=_invoke_com(script,timeout).split('|')
    if len(reply)!=5 or reply[:2]!=['DL_QUIESCENT_V1',job['jobId']] or not all(v.isdigit() for v in reply[2:]):
        raise ValueError('quiescence acknowledgement invalid')
    before,after,closed=map(int,reply[2:])
    if closed not in (0,1) or before-after!=closed or snapshot()!=before_files:raise ValueError('quiescence mismatch')
    return dict(status='HOST_QUIESCENT_ARTIFACTS_UNACCEPTED',job_id=job['jobId'],
        documents_before=before,documents_after=after,closed_documents=closed,artifacts=before_files,
        recovery_script_sha256=hashlib.sha256(script.encode('utf-8')).hexdigest())


#: Each closed shape this adapter accepts, with the contract file that states it. Keyed by
#: version on purpose: an unmapped schemaVersion is a refusal, not a guess about which file
#: was meant.
JOB_CONTRACTS={
    'design-lab/adobe-host-job/v1':'design-lab/schemas/reconstruction/adobe-host-job.schema.json',
    'design-lab/adobe-patch-job/v1':'design-lab/schemas/reconstruction/adobe-patch-job.schema.json',
}


def _contract_problems(job):
    """Judge a job against its own contract before anything reaches the host."""
    version=job.get('schemaVersion')
    relative=JOB_CONTRACTS.get(version)
    if relative is None:return [f'no contract is mapped for schemaVersion {version!r}']
    try:return schema_errors(load_schema(PROJECT_ROOT/relative),job,limit=3)
    except InteropError as exc:return [f'{relative} cannot be read: {exc}']


def execute(job,*,project_root,approved_root,timeout=120):
    """Execute one already qualified closed job; return actual bound readback.

    preflight errors have outcome_unknown=False, errors after entering COM True.
    No database state is changed here: the coordinator must persist those states.
    """
    try:
        if type(timeout) not in (int,float) or not 1<=timeout<=600:raise ValueError('invalid timeout')
        paths=resolve_paths(project_root=project_root)
        root=paths.checked_path(approved_root)
        if not root.is_dir():raise ValueError('run root absent')
        required={'schemaVersion','jobId','rirHash','runRoot','artboard','layers','assets','targets','operations','authorization'}
        is_patch=isinstance(job,dict) and job.get('schemaVersion')=='design-lab/adobe-patch-job/v1'
        if is_patch:required|={'checkpoint','checkpointSha256','patch'}
        if not isinstance(job,dict) or set(job)!=required:raise ValueError('invalid job fields')
        payload=json.dumps(job,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(payload)>4_000_000:raise ValueError('job too large')
        job=json.loads(payload)  # Seal caller-owned mutable structures before dispatch.
        if (job['schemaVersion'] not in ('design-lab/adobe-host-job/v1','design-lab/adobe-patch-job/v1')
            or not isinstance(job['jobId'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}',job['jobId'])
            or not isinstance(job['rirHash'],str) or not re.fullmatch(r'[0-9a-f]{64}',job['rirHash'])
            or job['rirHash']=='0'*64):raise ValueError('job binding invalid')
        if paths.checked_path(job['runRoot'])!=root:raise ValueError('run root mismatch')
        def inside(value):
            path=paths.checked_path(value)
            if not path.is_relative_to(root) or path==root:raise ValueError('path outside trusted run root')
            return path
        if not isinstance(job['targets'],dict) or set(job['targets'])!={'ai','png','svg'}:raise ValueError('targets invalid')
        targets={kind:inside(value) for kind,value in job['targets'].items()}
        for kind,path in targets.items():
            if path.exists() or path.suffix.lower()!='.'+kind or not path.parent.is_dir():raise ValueError('output unavailable')
        inputs={}
        if is_patch:
            checkpoint=inside(job['checkpoint'])
            if checkpoint.suffix.lower()!='.ai':raise ValueError('native AI checkpoint required')
            inputs[str(checkpoint)]=_digest(checkpoint,256*1024*1024)
            if inputs[str(checkpoint)]['sha256']!=job['checkpointSha256']:raise ValueError('checkpoint changed')
            with checkpoint.open('rb') as stream:
                if stream.read(5)!=b'%PDF-':raise ValueError('PDF-compatible native checkpoint required')
            patch=job['patch']
            if not isinstance(patch,dict) or patch.get('kind') not in ('text','path'):raise ValueError('unsupported patch')
            if set(patch)!=({'kind','id','text'} if patch['kind']=='text' else {'kind','id','points'}):raise ValueError('patch fields invalid')
            if not isinstance(patch['id'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}',patch['id']):raise ValueError('patch identity invalid')
            if job['operations']!=['openAI','readback','patchObject','saveAI','reopen','readback','exportPNG','exportSVG']:raise ValueError('patch operations invalid')
        problems=_contract_problems(job)
        if problems:raise ValueError('job contract invalid: '+problems[0])
        if not isinstance(job['assets'],list) or len(job['assets'])>500:raise ValueError('assets invalid')
        for asset in job['assets']:
            if not isinstance(asset,dict) or set(asset)!={'id','path'}:raise ValueError('asset fields invalid')
            path=inside(asset['path']);inputs[str(path)]=_digest(path,32*1024*1024)
            with Image.open(path) as image:
                if image.format not in ('PNG','JPEG') or getattr(image,'n_frames',1)!=1 or image.width*image.height>25_000_000:
                    raise ValueError('input image invalid')
                image.verify()
        bridge=_bridge();source=re.sub(r'^#target.*$','',bridge.decode('utf-8'),flags=re.M)
        entry='runApprovedPatchJob' if is_patch else 'runApprovedJob'
        source+='\n(function(){var job='+payload+',root='+json.dumps(str(root))+''';
var before=app.documents.length;
var doc='''+entry+'''(job,root);
var version=app.version;
doc.close(SaveOptions.DONOTSAVECHANGES);
return ['DL_NATIVE_V1',version,job.jobId,job.rirHash,before,app.documents.length].join('\\t');
})();'''
    except Exception as exc:
        raise IllustratorDispatchError('ILLUSTRATOR_PREFLIGHT_REJECTED') from exc
    try:
        reply=_invoke_com(source,timeout)
        parts=reply.split('\t')
        if (len(parts)!=6 or parts[0]!='DL_NATIVE_V1' or parts[2:4]!=[job['jobId'],job['rirHash']]
            or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}',parts[1])
            or not parts[4].isdigit() or parts[4]!=parts[5]):raise ValueError('native receipt binding mismatch')
        for path,expected in inputs.items():
            if _digest(inside(path),32*1024*1024)!=expected:raise ValueError('input changed during dispatch')
        artifacts={kind:_digest(inside(str(path)),256*1024*1024) for kind,path in targets.items()}
        with targets['ai'].open('rb') as stream:
            if not stream.read(5).startswith(b'%PDF'):raise ValueError('native PDF-compatible AI absent')
        with Image.open(targets['png']) as image:
            if image.format!='PNG' or image.size!=(job['artboard']['width'],job['artboard']['height']):
                raise ValueError('native preview dimensions mismatch')
            image.verify()
        return dict(status='NATIVE_READBACK',host_version=parts[1],job_id=job['jobId'],rir_hash=job['rirHash'],
            job_sha256=hashlib.sha256(payload.encode('utf-8')).hexdigest(),bridge_sha256=hashlib.sha256(bridge).hexdigest(),
            inputs=inputs,artifacts=artifacts,documents_before=int(parts[4]),documents_after=int(parts[5]))
    except Exception as exc:
        raise IllustratorDispatchError('ILLUSTRATOR_OUTCOME_UNKNOWN',outcome_unknown=True) from exc
