# SPDX-License-Identifier: MIT
"""Idempotent object-plan intake; never dispatches a creative host inline."""
from contextlib import closing
import hashlib
import json
import re
import uuid

from .image_assets import ImageAssets, ImageAssetError
from .native_plan import prepare_plan
from .native_tasks import NativeTasks
from .runtime.native_recovery_lock import recovery_lock, RecoveryBusy
from .task_queries import TaskQueries


class NativeSubmissions:
    def __init__(self,service):
        self.service=service

    def submit(self,project_id,host,rir,text_styles,idempotency_key):
        ImageAssets(self.service).require_project(project_id)
        if host not in ('photoshop','illustrator') or not isinstance(text_styles,dict):
            raise ImageAssetError(400,'INVALID_NATIVE_PLAN')
        if not isinstance(idempotency_key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',idempotency_key):
            raise ImageAssetError(400,'INVALID_NATIVE_KEY')
        raw=json.dumps(dict(rir=rir,text_styles=text_styles),sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(raw)>4_000_000:raise ImageAssetError(413,'NATIVE_PLAN_TOO_LARGE')
        digest=hashlib.sha256(raw.encode()).hexdigest()
        identity=hashlib.sha256((project_id+':'+host+':'+idempotency_key).encode()).hexdigest()
        try:
            with recovery_lock(self.service.paths,'submission:'+identity):
                return self._locked(project_id,host,rir,text_styles,idempotency_key,identity,digest)
        except RecoveryBusy:
            raise ImageAssetError(409,'NATIVE_SUBMISSION_BUSY') from None

    def _locked(self,project_id,host,rir,text_styles,key,identity,digest):
        native=NativeTasks(self.service)
        with closing(native._connect()) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS native_submission_v1 ('
                'submission_id TEXT PRIMARY KEY,client_hash TEXT NOT NULL,job_json TEXT NOT NULL)')
            conn.commit()
            row=conn.execute('SELECT client_hash,job_json FROM native_submission_v1 WHERE submission_id=?',(identity,)).fetchone()
            if row and row[0]!=digest:raise ImageAssetError(409,'NATIVE_PLAN_IDEMPOTENCY_CONFLICT')
            if row:
                job=json.loads(row[1])
                root=self.service.paths.checked_path(job['runRoot'])
            else:
                root=self.service.paths.category_dir('projects',project_id,'native-plans',uuid.uuid4().hex)
                root.mkdir(parents=True,exist_ok=False)
                job=prepare_plan(self.service,project_id,host,rir,text_styles,root)
                # A crash before this commit leaves only a retained staging
                # directory, never host effects. Retry uses a fresh directory.
                conn.execute('INSERT INTO native_submission_v1 VALUES (?,?,?)',
                    (identity,digest,json.dumps(job,sort_keys=True,allow_nan=False)))
                conn.commit()
        queued=native.enqueue(project_id,host,job,idempotency_key=key,approved_root=root,
            authorization=dict(actor='authenticated-local-client',scope='project-native-test',
                receipt='Explicit object-plan submission; no rights or quality acceptance'))
        return TaskQueries(self.service).get(project_id,queued['attempt']['job_id'])
