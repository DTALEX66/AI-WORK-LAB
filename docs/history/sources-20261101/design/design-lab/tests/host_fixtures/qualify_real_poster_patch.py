# SPDX-License-Identifier: MIT
"""One real-poster checkpoint edit through the product durable dispatcher.

Usage: text | path <text-run> | restore. Each execution writes a new version.
Restore reads the immutable original checkpoint, not the changed source file.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.service import ProjectService
from design_lab.native_tasks import NativeTasks


def main():
    mode=sys.argv[1]
    if mode not in ('text','path','restore') or len(sys.argv)!=(3 if mode=='path' else 2):raise ValueError('invalid phase')
    service=ProjectService(ROOT);paths=service.paths
    initial=paths.checked_path(ROOT/'.project-local/task-artifacts/real-poster-20260908/run-3bc50140e7f44caca5393c29002c43f9')
    original=json.loads((initial/'adobe-host-job.json').read_text(encoding='utf-8'))
    proof=json.loads((initial/'native-task-readback.json').read_text(encoding='utf-8'))
    project=proof['project_id'];baseline=copy.deepcopy(original)
    checkpoint=initial/'master.ai';expected_hash=proof['result']['native']['artifacts']['ai']['sha256']
    parent=None
    if mode=='path':
        parent=paths.checked_path(sys.argv[2]);previous=json.loads((parent/'patch-readback.json').read_text(encoding='utf-8'))
        if previous['mode']!='text' or previous['project_id']!=project:raise ValueError('unexpected prior phase')
        baseline=json.loads((parent/'expected-after.json').read_text(encoding='utf-8'))
        checkpoint=parent/'master.ai';expected_hash=previous['result']['native']['artifacts']['ai']['sha256']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=expected_hash:raise ValueError('checkpoint changed')
    run=paths.task_dir('real-poster-patches-20260908',mode+'-'+uuid.uuid4().hex,evidence=True)
    run.mkdir(parents=True,exist_ok=False);shutil.copyfile(checkpoint,run/'checkpoint.ai')
    if baseline['assets']:raise ValueError('this qualification expects embedded vector/text poster only')
    job=copy.deepcopy(baseline);job.update(schemaVersion='design-lab/adobe-patch-job/v1',
        jobId='poster-'+mode+'-'+uuid.uuid4().hex,runRoot=str(run),checkpoint=str(run/'checkpoint.ai'),checkpointSha256=expected_hash,
        targets={k:str(run/name) for k,name in [('ai','master.ai'),('png','illustrator-preview.png'),('svg','master.illustrator.svg')]},
        operations=['openAI','readback','patchObject','saveAI','reopen','readback','exportPNG','exportSVG'])
    def find(identity):
        found=[]
        def visit(item):
            if item['id']==identity:found.append(item)
            for child in item.get('items',item.get('contours',[])):visit(child)
        for layer in job['layers']:
            for item in layer['items']:visit(item)
        if len(found)!=1:raise ValueError('unique object required')
        return found[0]
    if mode in ('text','restore'):
        target=find('ocr-100');text=target['text']
        if mode=='text':
            if text.count('restrykycyjna')!=1:raise ValueError('OCR correction no longer applicable')
            text=text.replace('restrykycyjna','restrykcyjna')
        patch=dict(kind='text',id=target['id'],text=text)
    else:
        target=find('r0-icon2-p1');points=copy.deepcopy(target['points'])
        for point in points:
            for vector in point.values():vector[0]+=4
        patch=dict(kind='path',id=target['id'],points=points)
    job['patch']=patch
    after=copy.deepcopy(job)
    # This expected object graph is used for the next independent full readback.
    def update(items):
        for item in items:
            if item['id']==patch['id']:item['text' if mode!='path' else 'points']=copy.deepcopy(patch['text' if mode!='path' else 'points'])
            update(item.get('items',item.get('contours',[])))
    for layer in after['layers']:update(layer['items'])
    for name,data in [('patch-job.json',job),('expected-after.json',after)]:
        (run/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),mode=mode,checkpoint_sha256=expected_hash)),flush=True)
    tasks=NativeTasks(service)
    auth=dict(actor='user',scope='project-native-test',receipt='active goal authorizes real-reference local edits and checkpoint restoration on copies')
    result=tasks.execute(project,'illustrator',job,idempotency_key=job['jobId'],approved_root=run,authorization=auth)
    replay=NativeTasks(ProjectService(ROOT)).execute(project,'illustrator',job,idempotency_key=job['jobId'],approved_root=run,authorization=auth)
    if result['asset']!=replay['asset'] or result['attempt']!=replay['attempt']:raise ValueError('replay differs')
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=expected_hash:raise ValueError('original checkpoint changed')
    record=dict(mode=mode,project_id=project,parent=str(parent) if parent else str(initial),result=replay,
        restoration_preview_matches_original=(replay['native']['artifacts']['png']['sha256']==proof['result']['native']['artifacts']['png']['sha256']))
    (run/'patch-readback.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    if mode=='restore' and not record['restoration_preview_matches_original']:raise ValueError('restoration differs')
    print(json.dumps(record))


if __name__=='__main__':main()
