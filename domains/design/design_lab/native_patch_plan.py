# SPDX-License-Identifier: MIT
"""Internal patch staging from a caller-verified native receipt, never public paths.

The caller must bind baseline/checkpoint/input hashes to a project-owned RECEIPTED
attempt. This helper rechecks bytes and stages copies; it does not authorize or
dispatch a host. Each host's closed bridge remains the native validator.
"""
import hashlib
import json
import math
import os
import re
import uuid


def _target(layers, patch):
    if not isinstance(patch,dict) or patch.get('kind') not in ('text','path'):
        raise ValueError('unsupported patch')
    field='text' if patch['kind']=='text' else 'points'
    if set(patch)!={'kind','id',field} or not isinstance(patch['id'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}',patch['id']):
        raise ValueError('invalid patch fields')
    found=[]
    def walk(items):
        for item in items:
            if item['id']==patch['id']:found.append(item)
            walk(item.get('items',item.get('contours',[])))
    for layer in layers:walk(layer['items'])
    if len(found)!=1 or found[0]['kind']!=patch['kind']:raise ValueError('patch target absent or ambiguous')
    value=patch[field]
    if field=='text':
        if not isinstance(value,str) or not 1<=len(value)<=10000:raise ValueError('invalid text')
    else:
        if not isinstance(value,list) or not 2<=len(value)<=10000 or len(value)!=len(found[0]['points']):
            raise ValueError('path topology change unsupported')
        for point in value:
            if not isinstance(point,dict) or set(point)!={'anchor','left','right'}:raise ValueError('invalid point')
            for vector in point.values():
                if not isinstance(vector,list) or len(vector)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or not -16383<=v<=16383 for v in vector):
                    raise ValueError('invalid coordinate')
    return found[0],field


def _photoshop_patch(job,patch,*,apply=False):
    if not isinstance(patch,dict) or patch.get('kind') not in ('text','move'):
        raise ValueError('unsupported Photoshop patch')
    field='text' if patch['kind']=='text' else 'delta'
    if set(patch)!={'kind','id',field} or not isinstance(patch['id'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}',patch['id']):
        raise ValueError('invalid Photoshop patch fields')
    pending=list(job['layers']);found=[]
    while pending:
        item=pending.pop()
        if item['id']==patch['id']:found.append(item)
        pending.extend(item.get('children',[]))
    if len(found)!=1:raise ValueError('Photoshop target absent or ambiguous')
    target=found[0]
    if field=='text':
        if target['kind']!='text' or not isinstance(patch[field],str) or not 1<=len(patch[field])<=10000:
            raise ValueError('invalid Photoshop text patch')
        if apply:target['text']=patch['text']
    else:
        delta=patch['delta']
        if target['kind'] not in ('text','raster','fill') or not isinstance(delta,list) or len(delta)!=2 or any(
            type(v) not in (int,float) or not math.isfinite(v) or not -16383<=v<=16383 for v in delta):
            raise ValueError('invalid Photoshop leaf movement')
        key='bounds' if target['kind']=='fill' else 'position'
        moved=list(target[key]);moved[:2]=[moved[i]+delta[i] for i in range(2)]
        if any(not 0<=v<=16383 for v in moved[:2]):raise ValueError('movement outside supported coordinates')
        if target['kind']=='fill' and (moved[0]+moved[2]>job['width'] or moved[1]+moved[3]>job['height']):
            raise ValueError('fill outside canvas')
        if apply:target[key]=moved


def prepare_patch(service,project_id,baseline,checkpoint,checkpoint_sha256,input_hashes,patch,run_root):
    if service.get_project(project_id) is None:raise ValueError('unknown project')
    paths=service.paths;root=paths.checked_path(run_root)
    allowed=paths.category_dir('projects',project_id,'native-plans')
    if root==allowed or not root.is_relative_to(allowed) or not root.is_dir() or any(root.iterdir()):
        raise ValueError('new project-owned run directory required')
    payload=json.dumps(dict(job=baseline,patch=patch),allow_nan=False)
    if len(payload)>4_000_000:raise ValueError('oversized patch plan')
    sealed=json.loads(payload);job=sealed['job'];patch=sealed['patch']
    photoshop=job['schemaVersion'] in ('design-lab/photoshop-native-job/v1','design-lab/photoshop-patch-job/v1')
    if photoshop:
        if job['schemaVersion']=='design-lab/photoshop-patch-job/v1':_photoshop_patch(job,job['patch'],apply=True)
        _photoshop_patch(job,patch)
    else:
        if job['schemaVersion'] not in ('design-lab/adobe-host-job/v1','design-lab/adobe-patch-job/v1'):
            raise ValueError('supported native baseline required')
        if job['schemaVersion']=='design-lab/adobe-patch-job/v1':
            prior,field=_target(job['layers'],job['patch']);prior[field]=job['patch'][field]
        _target(job['layers'],patch)
    source_root=paths.checked_path(job['runRoot'])
    def read_verified(raw,expected,limit):
        source=paths.checked_path(raw)
        if source==source_root or not source.is_relative_to(source_root):raise ValueError('input outside source run')
        before=source.stat()
        if not source.is_file() or before.st_nlink!=1 or not 0<before.st_size<=limit:raise ValueError('invalid source')
        data=source.read_bytes();after=source.stat()
        if (before.st_ino,before.st_mtime_ns,before.st_size)!=(after.st_ino,after.st_mtime_ns,after.st_size) or hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError('source hash changed')
        return data
    native=read_verified(checkpoint,checkpoint_sha256,256*1024*1024)
    if photoshop:
        if (len(native)<26 or native[:6]!=b'8BPS\x00\x01' or int.from_bytes(native[14:18],'big')!=job['height']
            or int.from_bytes(native[18:22],'big')!=job['width']):raise ValueError('matching PSD required')
    elif not native.startswith(b'%PDF-'):raise ValueError('PDF-compatible AI required')
    checkpoint_name='checkpoint.psd' if photoshop else 'checkpoint.ai'
    staged=[(root/checkpoint_name,native)];total=len(native)
    for index,asset in enumerate(job['assets']):
        source=paths.checked_path(asset['path']);digest=input_hashes.get(str(source))
        if not isinstance(digest,dict):raise ValueError('asset receipt missing')
        data=read_verified(source,digest['sha256'],32*1024*1024)
        if len(data)!=digest['byte_size']:raise ValueError('asset size changed')
        total+=len(data)
        if total>256*1024*1024:raise ValueError('patch inputs too large')
        suffix=source.suffix.lower()
        if suffix not in ('.png','.jpg','.jpeg'):raise ValueError('unsupported linked image')
        target=root/(f'input-{index:04d}'+suffix);staged.append((target,data));asset['path']=str(target)
    if photoshop:
        job.update(schemaVersion='design-lab/photoshop-patch-job/v1',jobId='patch-'+uuid.uuid4().hex,
                   runRoot=str(root),checkpoint=str(root/checkpoint_name),checkpointSha256=checkpoint_sha256,
                   patch=patch,outputName='master.psd',previewName='master.png')
    else:job.update(schemaVersion='design-lab/adobe-patch-job/v1',jobId='patch-'+uuid.uuid4().hex,
               runRoot=str(root),checkpoint=str(root/'checkpoint.ai'),checkpointSha256=checkpoint_sha256,
               patch=patch,targets={kind:str(root/('master.'+kind)) for kind in ('ai','png','svg')},
               operations=['openAI','readback','patchObject','saveAI','reopen','readback','exportPNG','exportSVG'])
    for path,data in staged:
        with path.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    return job
