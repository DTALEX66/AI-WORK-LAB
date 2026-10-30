# SPDX-License-Identifier: MIT
"""Project-scoped patch intake from verified persisted native attempts."""
from contextlib import closing
import hashlib
import json
import re
import uuid

from .image_assets import ImageAssetError
from .native_patch_plan import prepare_patch
from .native_tasks import NativeTasks, NativeTaskError
from .runtime import job_store as jobs
from .runtime.attempt_contract import request_hash
from .runtime.native_recovery_lock import recovery_lock, RecoveryBusy
from .task_queries import TaskQueries


class NativePatchSubmissions:
    def __init__(self,service):
        self.service=service

    def submit(self,project_id,job_id,source_attempt_id,patch,idempotency_key):
        task=TaskQueries(self.service).get(project_id,job_id)['task']
        if task['kind'] not in ('illustrator-native','photoshop-native') or task['attempt']['attempt_id']!=source_attempt_id or task['attempt']['state']!='RECEIPTED':
            raise ImageAssetError(409,'PATCH_SOURCE_NOT_READY')
        if not isinstance(idempotency_key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',idempotency_key):
            raise ImageAssetError(400,'INVALID_NATIVE_KEY')
        raw=json.dumps(dict(source_attempt_id=source_attempt_id,patch=patch),sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(raw)>1_000_000:raise ImageAssetError(413,'PATCH_TOO_LARGE')
        digest=hashlib.sha256(raw.encode()).hexdigest()
        identity=hashlib.sha256(('patch:'+project_id+':'+idempotency_key).encode()).hexdigest()
        try:
            with recovery_lock(self.service.paths,'patch-submission:'+identity), recovery_lock(self.service.paths,source_attempt_id):
                return self._locked(project_id,source_attempt_id,patch,identity,digest)
        except RecoveryBusy:
            raise ImageAssetError(409,'PATCH_SOURCE_BUSY') from None

    def _locked(self,project_id,source_attempt_id,patch,identity,digest):
        native=NativeTasks(self.service)
        with closing(native._connect()) as conn:
            try:
                attempt,_=jobs._current(conn,source_attempt_id)
                row=conn.execute('SELECT n.project_id,n.host,n.request_json,n.receipt_json,i.request_hash '
                    'FROM native_execution_v1 n JOIN attempt_state a ON a.attempt_id=n.attempt_id '
                    'JOIN job j ON j.job_id=a.job_id JOIN operation_intent i ON i.operation_id=j.operation_id '
                    'WHERE n.attempt_id=?',(source_attempt_id,)).fetchone()
                if not row or row[0]!=project_id or row[1] not in ('illustrator','photoshop') or attempt['state']!='RECEIPTED' or not row[3]:
                    raise ValueError('source not ready')
                request=json.loads(row[2]);receipt=json.loads(row[3]);baseline=request['job']
                host=row[1];primary='psd' if host=='photoshop' else 'ai'
                if request_hash(request)!=row[4] or request['project_id']!=project_id or request['host']!=host:
                    raise ValueError('source request mismatch')
                source_root=self.service.paths.checked_path(baseline['runRoot'])
                raw_outputs=({'psd':source_root/baseline['outputName'],'png':source_root/baseline['previewName']}
                             if host=='photoshop' else baseline['targets'])
                outputs={kind:native._inside(path,source_root) for kind,path in raw_outputs.items()}
                native._verify_receipt(receipt,baseline,request,outputs)
                result=native._existing(conn,attempt,project_id)
                if result['asset']['sha256']!=receipt['artifacts'][primary]['sha256']:
                    raise ValueError('published source mismatch')
            except (ValueError,KeyError,TypeError,OSError,NativeTaskError,jobs.AttemptError):
                raise ImageAssetError(409,'PATCH_SOURCE_UNVERIFIED') from None
            parent=dict(attempt_id=source_attempt_id,asset_id=result['asset']['id'],version_id=result['asset']['version_id'])
            conn.execute('CREATE TABLE IF NOT EXISTS native_patch_submission_v1 ('
                'submission_id TEXT PRIMARY KEY,client_hash TEXT NOT NULL,parent_json TEXT NOT NULL,job_json TEXT NOT NULL,job_hash TEXT NOT NULL)')
            conn.commit()
            prior=conn.execute('SELECT client_hash,parent_json,job_json,job_hash FROM native_patch_submission_v1 WHERE submission_id=?',(identity,)).fetchone()
            if prior:
                if prior[0]!=digest or json.loads(prior[1])!=parent:
                    raise ImageAssetError(409,'PATCH_IDEMPOTENCY_CONFLICT')
                if hashlib.sha256(prior[2].encode()).hexdigest()!=prior[3]:
                    raise ImageAssetError(409,'PATCH_STAGING_UNVERIFIED')
                job=json.loads(prior[2]);root=self.service.paths.checked_path(job['runRoot'])
            else:
                root=self.service.paths.category_dir('projects',project_id,'native-plans',uuid.uuid4().hex)
                root.mkdir(parents=True,exist_ok=False)
                job=prepare_patch(self.service,project_id,baseline,outputs[primary],receipt['artifacts'][primary]['sha256'],request['inputs'],patch,root)
                job_raw=json.dumps(job,sort_keys=True,allow_nan=False)
                conn.execute('INSERT INTO native_patch_submission_v1 VALUES (?,?,?,?,?)',
                    (identity,digest,json.dumps(parent,sort_keys=True),job_raw,hashlib.sha256(job_raw.encode()).hexdigest()))
                conn.commit()
        queued=native.enqueue(project_id,host,job,idempotency_key=identity,approved_root=root,
            authorization=dict(actor='authenticated-local-client',scope='project-native-test',
                               receipt='Explicit project-scoped object patch; no rights or quality acceptance'))
        return dict(TaskQueries(self.service).get(project_id,queued['attempt']['job_id']),parent=parent)
