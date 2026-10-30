# SPDX-License-Identifier: MIT
"""Durable internal native execution using the service's existing state stores.

Host guards deliberately never expire. An unresolved COM call may still write;
only a verified completion or a proven pre-dispatch rejection releases a guard.
This is not a public arbitrary-job endpoint or a rights/quality approval engine.
"""
from contextlib import closing
import hashlib
import json
import re
import sqlite3

from .adapters import illustrator_com, photoshop_com
from .runtime import asset_store as assets, job_store as jobs
from .runtime.attempt_contract import request_hash
from .runtime.native_recovery_lock import recovery_lock, RecoveryBusy


class NativeTaskError(RuntimeError):
    def __init__(self,code,*,attempt=None):
        super().__init__(code);self.attempt=attempt


def _dispatch(host,job,**kwargs):
    return {'illustrator':illustrator_com,'photoshop':photoshop_com}[host].execute(job,**kwargs)


def _authorization_valid(authorization):
    """The exact scoped authorization the verified recovery entries already demand."""
    return (isinstance(authorization,dict) and set(authorization)=={'actor','scope','receipt'}
        and authorization['scope']=='project-native-test'
        and all(isinstance(v,str) and v.strip() and len(v)<=2000 for v in authorization.values()))


def _json(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False)


def _digest(path):
    before=path.stat()
    if not path.is_file() or not 0<before.st_size<=256*1024*1024 or before.st_nlink!=1:raise ValueError('invalid file')
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('file changed')
    return dict(sha256=h.hexdigest(),byte_size=before.st_size)


class NativeTasks:
    def __init__(self,service):
        self.service=service;self.paths=service.paths;self.owner=self.paths.project_root

    def _connect(self):
        conn=jobs.connect(self.service.database,project_root=self.owner)
        try:
            conn.executescript('''
CREATE TABLE IF NOT EXISTS native_execution_v1 (
 attempt_id TEXT PRIMARY KEY REFERENCES attempt_state(attempt_id),
 project_id TEXT NOT NULL REFERENCES project(project_id), host TEXT NOT NULL,
 request_json TEXT NOT NULL, receipt_json TEXT, result_json TEXT
);
CREATE TABLE IF NOT EXISTS native_host_guard_v1 (
 host TEXT PRIMARY KEY CHECK(host IN ('illustrator','photoshop')),
 attempt_id TEXT NOT NULL UNIQUE REFERENCES attempt_state(attempt_id), acquired_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS native_quiescence_v1 (
 attempt_id TEXT PRIMARY KEY REFERENCES attempt_state(attempt_id),
 authorization_json TEXT NOT NULL, started_at TEXT NOT NULL, receipt_json TEXT
);
CREATE TABLE IF NOT EXISTS native_reconciliation_v1 (
 attempt_id TEXT PRIMARY KEY REFERENCES attempt_state(attempt_id),
 authorization_json TEXT NOT NULL, started_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS native_recovery_protocol_v2 (
 attempt_id TEXT PRIMARY KEY REFERENCES native_reconciliation_v1(attempt_id),
 protocol TEXT NOT NULL CHECK(protocol='os-lock-v1')
);
''')
            return conn
        except BaseException:conn.close();raise

    def _inside(self,value,root):
        path=self.paths.checked_path(value)
        if path==root or not path.is_relative_to(root):raise ValueError('outside approved root')
        return path

    def _prepare(self,project_id,host,job,key,root,authorization):
        if host not in ('photoshop','illustrator'):raise ValueError('unsupported host')
        if not isinstance(project_id,str) or not re.fullmatch(r'[0-9a-f]{32}',project_id) or self.service.get_project(project_id) is None:raise ValueError('unknown project')
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',key):raise ValueError('invalid key')
        if (not isinstance(authorization,dict) or set(authorization)!={'actor','scope','receipt'}
            or authorization['scope']!='project-native-test'
            or any(not isinstance(v,str) or not v.strip() or len(v)>2000 for v in authorization.values())):raise ValueError('scoped caller authorization required')
        payload=_json(job)
        if len(payload)>4_000_000:raise ValueError('oversized job')
        job=json.loads(payload);root=self.paths.checked_path(root)
        if not root.is_dir() or self.paths.checked_path(job['runRoot'])!=root:raise ValueError('unapproved root')
        inputs={}
        for asset in job['assets']:
            path=self._inside(asset['path'],root);inputs[str(path)]=_digest(path)
        if ((host=='illustrator' and job.get('schemaVersion')=='design-lab/adobe-patch-job/v1') or
            (host=='photoshop' and job.get('schemaVersion')=='design-lab/photoshop-patch-job/v1')):
            path=self._inside(job['checkpoint'],root);inputs[str(path)]=_digest(path)
            if inputs[str(path)]['sha256']!=job['checkpointSha256']:raise ValueError('checkpoint hash mismatch')
        if host=='photoshop':
            outputs={'psd':root/job['outputName'],'png':root/job['previewName']}
        else:outputs=job['targets']
        outputs={kind:self._inside(path,root) for kind,path in outputs.items()}
        primary='psd' if host=='photoshop' else 'ai'
        if set(outputs)!=({'psd','png'} if primary=='psd' else {'ai','png','svg'}):raise ValueError('invalid output set')
        identity=hashlib.sha256((project_id+':'+host+':'+key).encode()).hexdigest()
        request=dict(project_id=project_id,host=host,job=job,inputs=inputs,authorization=dict(authorization))
        return job,root,outputs,primary,identity,request

    def _claim(self,conn,attempt,host):
        with jobs._transaction(conn):
            current,op=jobs._current(conn,attempt['attempt_id'])
            if current['state']!='PENDING':return False
            if conn.execute('SELECT 1 FROM native_host_guard_v1 WHERE host=?',(host,)).fetchone():
                raise NativeTaskError('HOST_BUSY_UNRESOLVED',attempt=current)
            conn.execute('INSERT INTO native_host_guard_v1 VALUES (?,?,?)',(host,current['attempt_id'],jobs._now()))
            jobs._change(conn,current,'RUNNING','native host claimed; non-expiring guard')
            jobs._op(conn,op,'DISPATCHING')
            return True

    def _verify_result(self,result,project_id):
        asset=result['asset'];path=self._inside(asset['path'],self.paths.category_dir('projects',project_id))
        actual=_digest(path)
        if actual!={'sha256':asset['sha256'],'byte_size':asset['byte_size']}:raise NativeTaskError('PUBLISHED_ARTIFACT_CHANGED')
        return result

    def _existing(self,conn,attempt,project_id):
        row=conn.execute('SELECT result_json FROM native_execution_v1 WHERE attempt_id=?',(attempt['attempt_id'],)).fetchone()
        if attempt['state']=='RECEIPTED':
            if not row or not row[0]:raise NativeTaskError('NATIVE_RESULT_MISSING',attempt=attempt)
            return self._verify_result(json.loads(row[0]),project_id)
        return {'attempt':attempt}

    def export_bundle(self,attempt_id,*,authorization):
        from .native_bundles import export_bundle
        return export_bundle(self,attempt_id,authorization)

    def _verify_receipt(self,receipt,job,request,outputs):
        if (receipt.get('status')!='NATIVE_READBACK' or receipt.get('job_id')!=job['jobId']
            or receipt.get('job_sha256')!=hashlib.sha256(_json(job).encode()).hexdigest()
            or receipt.get('documents_before')!=receipt.get('documents_after')
            or type(receipt.get('documents_before')) is not int
            or receipt.get('inputs')!=request['inputs']):raise ValueError('native receipt mismatch')
        for path,digest in request['inputs'].items():
            if _digest(self.paths.checked_path(path))!=digest:raise ValueError('input changed')
        if set(receipt.get('artifacts',{}))!=set(outputs):raise ValueError('artifact set mismatch')
        for kind,path in outputs.items():
            if _digest(self.paths.checked_path(path))!=receipt['artifacts'][kind]:raise ValueError('output mismatch')

    def _publish(self,project_id,asset_id,primary,source,receipt,aid,*,recovering=False):
        with closing(assets.connect(self.service.database,project_root=self.owner)) as conn:
            assets.register_asset(conn,project_id,asset_id,primary)
            resource='asset:'+asset_id
            if not assets.acquire_writer(conn,resource,aid):
                if not recovering:raise NativeTaskError('ASSET_WRITER_BUSY')
                # Caller owns the OS recovery lock; only this same attempt's
                # prior lease may be fenced out, never a different writer.
                assets.takeover_writer(conn,resource,aid,expected_holder=aid)
            generation=assets.writer_token(conn,resource,aid)
            try:
                if recovering:
                    assets.recover_publications(conn,store_root=self.paths.category_dir('projects',project_id,'assets'),
                        project_root=self.owner,asset_id=asset_id,holder_attempt_id=aid,generation=generation)
                version=assets.publish_version(conn,asset_id,source,
                    store_root=self.paths.category_dir('projects',project_id,'assets'),artifact_name='native.'+primary,
                    expected_sha256=receipt['artifacts'][primary]['sha256'],holder_attempt_id=aid,
                    generation=generation,project_root=self.owner)
                row=conn.execute('SELECT path,sha256,byte_size FROM artifact WHERE version_id=?',(version,)).fetchone()
                result=dict(id=asset_id,version_id=version,path=row[0],sha256=row[1].removeprefix('sha256:'),
                            byte_size=row[2],kind=primary,rights='NOT_REVIEWED')
                self._verify_result({'asset':result},project_id)
                return result
            finally:assets.release_writer(conn,resource,aid,generation=generation)

    def _finish(self,conn,aid,host,result):
        with jobs._transaction(conn):
            current,op=jobs._current(conn,aid)
            guard=conn.execute('SELECT attempt_id FROM native_host_guard_v1 WHERE host=?',(host,)).fetchone()
            if current['state'] not in ('RUNNING','CANCEL_REQUESTED','RECONCILING') or guard!=(aid,):raise NativeTaskError('NATIVE_FINISH_CONFLICT')
            digest=result['asset']['sha256']
            evidence=jobs._evidence(dict(operation_id=op,attempt_id=aid,artifact_sha256=digest,readback_sha256=digest,
                kind='native-host-published',native=result['native'],version_id=result['asset']['version_id'],rights='NOT_REVIEWED'),op,aid)
            jobs._resolution(conn,aid,'effect_verified',evidence);jobs._op(conn,op,'SUCCEEDED')
            # A cancel the adapter never acknowledged must not vanish into a success.
            # RECEIPTED is the truthful state -- the bytes really were published and
            # read back -- but the record has to say the operator asked and the host
            # delivered anyway, or the ledger reads as an uncontested completion.
            jobs._change(conn,current,'RECEIPTED',
                         'native readback and published bytes verified after a cancel '
                         'request the adapter never acknowledged'
                         if current['state']=='CANCEL_REQUESTED'
                         else 'native readback and published bytes verified')
            result['attempt']=jobs._record(conn,aid)
            conn.execute('UPDATE native_execution_v1 SET result_json=? WHERE attempt_id=?',(_json(result),aid))
            conn.execute('DELETE FROM native_host_guard_v1 WHERE host=? AND attempt_id=?',(host,aid))
        return result

    def _failed(self,conn,aid,host,not_started):
        with jobs._transaction(conn):
            current,op=jobs._current(conn,aid)
            if current['state'] in ('RUNNING','CANCEL_REQUESTED'):
                if not_started:
                    cancelling=current['state']=='CANCEL_REQUESTED'
                    jobs._resolution(conn,aid,'effect_not_started');jobs._op(conn,op,'CANCELLED' if cancelling else 'RETRYABLE')
                    if cancelling:conn.execute('UPDATE attempt_resolution SET cancel_acked=1 WHERE attempt_id=?',(aid,))
                    jobs._change(conn,current,'CANCELLED' if cancelling else 'FAILED','adapter rejected before dispatch')
                    conn.execute('DELETE FROM native_host_guard_v1 WHERE host=? AND attempt_id=?',(host,aid))
                elif current['state']=='RUNNING':
                    jobs._change(conn,current,'OUTCOME_UNKNOWN','native effects/publication require reconciliation')
                    jobs._op(conn,op,'OUTCOME_UNKNOWN')
            return jobs._record(conn,aid)

    def reconcile_receipted(self,attempt_id,*,authorization):
        """Resume publication from a persisted verified host receipt, never dispatch.

        Missing receipts cannot prove host completion. Explicit recovery holds
        an OS-owned lock throughout; only a subsequent holder may resume a
        protocol-tagged claim. Legacy claims are never inferred stopped.
        """
        if (not isinstance(authorization,dict) or set(authorization)!={'actor','scope','receipt'}
            or authorization['scope']!='project-native-test'
            or any(not isinstance(v,str) or not v.strip() or len(v)>2000 for v in authorization.values())):
            raise NativeTaskError('RECONCILIATION_AUTHORIZATION_REQUIRED')
        try:
            with recovery_lock(self.paths,attempt_id):
                return self._reconcile_receipted_locked(attempt_id,authorization)
        except RecoveryBusy as exc:
            raise NativeTaskError('RECONCILIATION_WORKER_ACTIVE') from exc

    def _reconcile_receipted_locked(self,attempt_id,authorization):
        with closing(self._connect()) as conn:
            with jobs._transaction(conn):
                current,op=jobs._current(conn,attempt_id)
                row=conn.execute('SELECT host,project_id,request_json,receipt_json FROM native_execution_v1 WHERE attempt_id=?',(attempt_id,)).fetchone()
                if not row:raise NativeTaskError('RECONCILIATION_NOT_ELIGIBLE')
                host,project_id,raw_request,raw_receipt=row
                if current['state']=='RECEIPTED':return self._existing(conn,current,project_id)
                guard=conn.execute('SELECT attempt_id FROM native_host_guard_v1 WHERE host=?',(host,)).fetchone()
                claim=conn.execute('SELECT 1 FROM native_reconciliation_v1 WHERE attempt_id=?',(attempt_id,)).fetchone()
                protocol=conn.execute('SELECT protocol FROM native_recovery_protocol_v2 WHERE attempt_id=?',(attempt_id,)).fetchone()
                eligible=(current['state']=='OUTCOME_UNKNOWN' and not claim) or (
                    current['state']=='RECONCILING' and claim and protocol==('os-lock-v1',))
                if (not eligible or guard!=(attempt_id,) or not raw_receipt
                    or conn.execute('SELECT 1 FROM native_quiescence_v1 WHERE attempt_id=?',(attempt_id,)).fetchone()):
                    raise NativeTaskError('RECONCILIATION_NOT_ELIGIBLE')
                if not claim:
                    conn.execute('INSERT INTO native_reconciliation_v1 VALUES (?,?,?)',(attempt_id,_json(authorization),jobs._now()))
                    conn.execute("INSERT INTO native_recovery_protocol_v2 VALUES (?,'os-lock-v1')",(attempt_id,))
                    jobs._change(conn,current,'RECONCILING','persisted native receipt; publication-only recovery')
                else:
                    jobs._event(conn,attempt_id,'RECONCILING','RECONCILING','OS lock reacquired; explicit publication recovery')
                jobs._op(conn,op,'RECONCILING')
            try:
                request=json.loads(raw_request);job=request['job'];receipt=json.loads(raw_receipt)
                root=self.paths.checked_path(job['runRoot'])
                raw_outputs=({'psd':root/job['outputName'],'png':root/job['previewName']}
                             if host=='photoshop' else job['targets'])
                outputs={kind:self._inside(path,root) for kind,path in raw_outputs.items()}
                primary='psd' if host=='photoshop' else 'ai'
                self._verify_receipt(receipt,job,request,outputs)
                # Asset identity is already bound to the persisted operation, not
                # reconstructed using a new idempotency key or caller input.
                if not op.startswith('native-op-'):raise ValueError('invalid operation identity')
                asset_id='native-'+op.removeprefix('native-op-')
                asset=self._publish(project_id,asset_id,primary,outputs[primary],receipt,attempt_id,recovering=True)
                return self._finish(conn,attempt_id,host,dict(asset=asset,native=receipt))
            except Exception as exc:
                raise NativeTaskError('RECONCILIATION_UNRESOLVED_GUARD_RETAINED') from exc

    def quiesce_illustrator(self,attempt_id,*,authorization):
        return self._quiesce_host(attempt_id,'illustrator',authorization)

    def quiesce_photoshop(self,attempt_id,*,authorization):
        return self._quiesce_host(attempt_id,'photoshop',authorization)

    def _quiesce_host(self,attempt_id,host,authorization):
        """Pause an unknown attempt after fixed host cleanup, never accept it.

        Internal recovery entry, not an HTTP action. A failed recovery keeps
        both the original guard and a non-expiring recovery claim; no retries.
        """
        if (not isinstance(authorization,dict) or set(authorization)!={'actor','scope','receipt'}
            or authorization['scope']!='project-native-test'
            or any(not isinstance(v,str) or not v.strip() or len(v)>2000 for v in authorization.values())):
            raise NativeTaskError('QUIESCENCE_AUTHORIZATION_REQUIRED')
        with closing(self._connect()) as conn:
            with jobs._transaction(conn):
                current,op=jobs._current(conn,attempt_id)
                row=conn.execute('SELECT n.host,n.request_json,i.request_hash,n.project_id '
                    'FROM native_execution_v1 n JOIN attempt_state a ON a.attempt_id=n.attempt_id '
                    'JOIN job j ON j.job_id=a.job_id JOIN operation_intent i ON i.operation_id=j.operation_id '
                    'WHERE n.attempt_id=?',(attempt_id,)).fetchone()
                guard=conn.execute('SELECT attempt_id FROM native_host_guard_v1 WHERE host=?',(host,)).fetchone()
                if (not row or row[0]!=host or guard!=(attempt_id,) or current['state']!='OUTCOME_UNKNOWN'
                    or conn.execute('SELECT 1 FROM native_quiescence_v1 WHERE attempt_id=?',(attempt_id,)).fetchone()):
                    raise NativeTaskError('QUIESCENCE_NOT_ELIGIBLE')
                try:
                    request=json.loads(row[1]);job=request['job']
                    if request_hash(request)!=row[2] or request['host']!=host or request['project_id']!=row[3]:
                        raise ValueError('recovery request changed')
                except (ValueError,KeyError,TypeError) as exc:
                    raise NativeTaskError('QUIESCENCE_REQUEST_UNVERIFIED') from exc
                conn.execute('INSERT INTO native_quiescence_v1 VALUES (?,?,?,NULL)',(attempt_id,_json(authorization),jobs._now()))
            try:
                adapter={'illustrator':illustrator_com,'photoshop':photoshop_com}[host]
                receipt=adapter.quiesce(job,project_root=self.owner,approved_root=job['runRoot'])
                if (receipt.get('status')!='HOST_QUIESCENT_ARTIFACTS_UNACCEPTED'
                    or receipt.get('job_id')!=job['jobId'] or type(receipt.get('closed_documents')) is not int
                    or receipt['closed_documents'] not in (0,1)
                    or type(receipt.get('documents_before')) is not int or type(receipt.get('documents_after')) is not int
                    or receipt['documents_before']<0 or receipt['documents_after']<0
                    or receipt['documents_before']-receipt['documents_after']!=receipt['closed_documents']):
                    raise ValueError('invalid quiescence receipt')
                with jobs._transaction(conn):
                    current,op=jobs._current(conn,attempt_id)
                    guard=conn.execute('SELECT attempt_id FROM native_host_guard_v1 WHERE host=?',(host,)).fetchone()
                    if current['state']!='OUTCOME_UNKNOWN' or guard!=(attempt_id,):raise ValueError('recovery state changed')
                    jobs._change(conn,current,'RECONCILING','host quiescent; outputs preserved, not accepted')
                    jobs._resolution(conn,attempt_id,'needs_user');jobs._op(conn,op,'PAUSED_NEEDS_USER')
                    conn.execute('UPDATE native_quiescence_v1 SET receipt_json=? WHERE attempt_id=?',(_json(receipt),attempt_id))
                    conn.execute('DELETE FROM native_host_guard_v1 WHERE host=? AND attempt_id=?',(host,attempt_id))
                    return dict(attempt=jobs._record(conn,attempt_id),quiescence=receipt)
            except Exception as exc:raise NativeTaskError('QUIESCENCE_OUTCOME_UNKNOWN_GUARD_RETAINED') from exc

    def _worker_active(self,attempt_id):
        """True only while a process still holds this attempt's execution lock.

        "Free" means there is no holder, never "the holder looks old"; it is the
        same probe the start-up relabelling uses, and it is the only thing that
        lets recovery tell a crashed run from a run that is still writing.
        """
        try:
            with recovery_lock(self.paths,attempt_id):
                return False
        except RecoveryBusy:
            return True

    def _request_bound(self,conn,attempt_id,raw_request):
        """Whether the persisted request still hashes to its own operation intent."""
        row=conn.execute('SELECT i.request_hash FROM job j JOIN operation_intent i ON i.operation_id=j.operation_id '
            'WHERE j.job_id=(SELECT job_id FROM attempt_state WHERE attempt_id=?)',(attempt_id,)).fetchone()
        if not row:return False
        try:
            return request_hash(json.loads(raw_request))==row[0]
        except (ValueError,TypeError,json.JSONDecodeError):
            return False

    def _decision(self,conn,attempt_id,host,project_id,state,has_receipt,raw_request):
        """One unresolved native attempt: what can decide it, and why if nothing can.

        Read-only. Every field is a persisted ledger fact or a live lock probe;
        an action is named only when the existing verified entry would accept
        this exact state. Anything else stays UNKNOWN and says so.
        """
        decision=dict(attempt_id=attempt_id,project_id=project_id,host=host,state=state,
            operation=None,receipt_persisted=bool(has_receipt),host_guard=None,
            worker_active=False,request_bound=self._request_bound(conn,attempt_id,raw_request),
            quiescence_recorded=False,action=None,reason=None)
        guard=conn.execute('SELECT attempt_id FROM native_host_guard_v1 WHERE host=?',(host,)).fetchone()
        decision['host_guard']=(None if not guard else ('self' if guard[0]==attempt_id else 'other'))
        try:
            current,op=jobs._current(conn,attempt_id)
        except jobs.AttemptError:
            decision['reason']='ATTEMPT_NOT_CURRENT_OR_OPERATION_AMBIGUOUS';return decision
        status=jobs.operation_status(conn,op)
        decision['operation']=status['state'] if status else None
        if current['state']=='RUNNING':
            # Still claimed: either a run that is alive (untouchable) or a crash the
            # start-up relabelling has not converted yet. Neither may be decided here.
            decision['worker_active']=self._worker_active(attempt_id)
            decision['reason']=('NATIVE_RUN_LIVE' if decision['worker_active']
                                else 'RUNNING_ATTEMPT_AWAITS_START_UP_RELABELLING')
            return decision
        if current['state'] not in ('OUTCOME_UNKNOWN','RECONCILING'):
            decision['reason']='NATIVE_ATTEMPT_ALREADY_DECIDED';return decision
        if current['state']!=state:
            decision['reason']='RECOVERY_STATE_CHANGED';return decision
        quiesced=conn.execute('SELECT receipt_json FROM native_quiescence_v1 WHERE attempt_id=?',(attempt_id,)).fetchone()
        decision['quiescence_recorded']=bool(quiesced and quiesced[0] is not None)
        claim=conn.execute('SELECT 1 FROM native_reconciliation_v1 WHERE attempt_id=?',(attempt_id,)).fetchone()
        protocol=conn.execute('SELECT protocol FROM native_recovery_protocol_v2 WHERE attempt_id=?',(attempt_id,)).fetchone()
        decision['worker_active']=self._worker_active(attempt_id)
        if decision['worker_active']:
            decision['reason']='NATIVE_RUN_LIVE';return decision
        # Both verified entries demand that this attempt owns its host's guard, so
        # another attempt holding it is a real run ahead of this decision, not noise.
        if decision['host_guard']=='other':
            decision['reason']='HOST_GUARD_HELD_BY_ANOTHER_ATTEMPT'
            decision['blocking_attempt_id']=guard[0];return decision
        if quiesced:
            decision['reason']=('HOST_QUIESCENT_OUTPUTS_UNACCEPTED_NEEDS_USER' if decision['quiescence_recorded']
                                else 'QUIESCENCE_CLAIM_RETAINED')
            return decision
        if decision['host_guard'] is None:
            decision['reason']='HOST_GUARD_ABSENT';return decision
        if current['state']=='OUTCOME_UNKNOWN':
            if claim:decision['reason']='RECONCILIATION_CLAIM_RETAINED';return decision
            if has_receipt:decision['action']='reconcile';return decision
            # No receipt cannot prove the host finished; only fixed cleanup is
            # available, and it accepts nothing.
            if not decision['request_bound']:
                decision['reason']='NATIVE_REQUEST_UNBOUND';return decision
            decision['action']='quiesce';return decision
        if has_receipt and claim and protocol==('os-lock-v1',):
            decision['action']='reconcile';return decision
        decision['reason']='RECONCILING_NOT_RESUMABLE';return decision

    def _read_only(self):
        """Read the ledger without migrating it.

        `_connect` creates the native tables, and creating them rewrites the
        database file. "Just telling me what needs a decision" may not be a write:
        the HTTP/start-up read-only guarantee is asserted on this file's bytes.
        A ledger with no native tables has no native attempts, which is reported
        as an empty list, while any other read failure is raised, not swallowed.
        """
        database=self.paths.database_path(self.service.database)
        conn=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def _unresolved_rows(self,conn):
        try:
            return conn.execute('SELECT n.attempt_id,n.host,n.project_id,a.state,n.receipt_json,'
                'n.request_json FROM native_execution_v1 n JOIN attempt_state a ON a.attempt_id=n.attempt_id '
                'JOIN job j ON j.job_id=a.job_id WHERE a.state IN '
                "('OUTCOME_UNKNOWN','RECONCILING','RUNNING') ORDER BY a.started_at,n.attempt_id").fetchall()
        except sqlite3.OperationalError as exc:
            if 'no such table' in str(exc).lower():return []
            raise

    def _persisted_attempt(self,conn,attempt_id):
        """The persisted native binding for one attempt, or None if there is none."""
        try:
            return conn.execute('SELECT n.host,n.project_id,a.state,n.receipt_json,n.request_json '
                'FROM native_execution_v1 n JOIN attempt_state a ON a.attempt_id=n.attempt_id '
                'WHERE n.attempt_id=?',(attempt_id,)).fetchone()
        except sqlite3.OperationalError as exc:
            if 'no such table' in str(exc).lower():return None
            raise

    def recovery_decisions(self):
        """List the persisted native attempts whose outcome the machine cannot decide.

        This is a readback, not an action: it changes no state, releases no host
        guard, publishes nothing and infers no verdict. Attempts still RUNNING are
        listed too, always without an action, because the only honest reading of
        "running with a dead holder" is a crash that start-up relabelling must
        convert into OUTCOME_UNKNOWN before any verified entry applies.
        """
        with closing(self._read_only()) as conn:
            return [self._decision(conn,*row) for row in self._unresolved_rows(conn)]

    def decide_recovery(self,attempt_id,*,authorization):
        """Route one unresolved native attempt to the verified entry that fits it.

        Explicit operator command, never a start-up action: the entries this can
        reach all require a scoped human authorization, and a process that
        supplies one for itself would be manufacturing the approval it claims to
        resume. The action is re-derived here, not replayed from an earlier
        listing, and a state with no verified entry stays UNKNOWN and says so.
        """
        if not _authorization_valid(authorization):
            raise NativeTaskError('RECOVERY_DECISION_AUTHORIZATION_REQUIRED')
        if not isinstance(attempt_id,str) or not re.fullmatch(r'att-[0-9a-f]{32}',attempt_id):
            raise NativeTaskError('INVALID_NATIVE_ATTEMPT')
        with closing(self._read_only()) as conn:
            row=self._persisted_attempt(conn,attempt_id)
            if not row:raise NativeTaskError('RECOVERY_DECISION_NOT_PENDING')
            decision=self._decision(conn,attempt_id,row[0],row[1],row[2],row[3],row[4])
        if decision['state'] in jobs.TERMINAL:
            raise NativeTaskError('RECOVERY_DECISION_NOT_PENDING',attempt=decision)
        if decision['worker_active']:
            # A live holder means the run may still be writing. Refuse untouched.
            raise NativeTaskError('RECOVERY_DECISION_WORKER_ACTIVE',attempt=decision)
        action=decision['action']
        if action is None:
            raise NativeTaskError('RECOVERY_DECISION_INDETERMINATE',attempt=decision)
        if action=='reconcile':
            # reconcile_receipted owns the attempt lock itself; taking it here
            # would deadlock against it, so the probe above is the gate.
            return dict(decision=decision,result=self.reconcile_receipted(
                attempt_id,authorization=authorization))
        try:
            # Hold the lock across cleanup so no dispatch can start underneath it:
            # a host run takes this same lock for its whole life, and quiesce
            # re-checks state and guard inside its own transaction.
            with recovery_lock(self.paths,attempt_id):
                quiesce={'photoshop':self.quiesce_photoshop,'illustrator':self.quiesce_illustrator}[decision['host']]
                return dict(decision=decision,result=quiesce(
                    attempt_id,authorization=authorization))
        except RecoveryBusy as exc:
            raise NativeTaskError('RECOVERY_DECISION_WORKER_ACTIVE') from exc

    def _enqueue_prepared(self,conn,project_id,host,identity,request,idempotency_key):
        try:
            attempt=jobs.begin_attempt(conn,'native-job-'+identity,operation_id='native-op-'+identity,
                idempotency_scope='native:'+project_id+':'+host,idempotency_key=idempotency_key,request_hash=request_hash(request))
        except jobs.AttemptError as exc:raise NativeTaskError('NATIVE_IDEMPOTENCY_CONFLICT') from exc
        with jobs._transaction(conn):
            conn.execute('INSERT OR IGNORE INTO native_execution_v1(attempt_id,project_id,host,request_json) VALUES (?,?,?,?)',
                         (attempt['attempt_id'],project_id,host,_json(request)))
        return attempt

    def enqueue(self,project_id,host,job,*,idempotency_key,approved_root,authorization):
        """Persist an internal approved request without claiming or dispatching.

        This is not a public arbitrary-job API. Execution revalidates the same
        request and input hashes before acquiring the native host guard.
        """
        try:
            _,_,_,_,identity,request=self._prepare(project_id,host,job,idempotency_key,approved_root,authorization)
        except Exception as exc:raise NativeTaskError('NATIVE_REQUEST_REJECTED') from exc
        with closing(self._connect()) as conn:
            attempt=self._enqueue_prepared(conn,project_id,host,identity,request,idempotency_key)
            return self._existing(conn,attempt,project_id)

    def execute_queued(self,attempt_id):
        """Internal worker entry; load only the exact persisted approved request."""
        if not isinstance(attempt_id,str) or not re.fullmatch(r'att-[0-9a-f]{32}',attempt_id):
            raise NativeTaskError('INVALID_NATIVE_ATTEMPT')
        with closing(self._connect()) as conn:
            row=conn.execute('SELECT n.project_id,n.host,n.request_json,i.idempotency_key,i.request_hash '
                'FROM native_execution_v1 n JOIN attempt_state a ON a.attempt_id=n.attempt_id '
                'JOIN job j ON j.job_id=a.job_id JOIN operation_intent i ON i.operation_id=j.operation_id '
                'WHERE n.attempt_id=?',(attempt_id,)).fetchone()
            if not row:raise NativeTaskError('NATIVE_REQUEST_MISSING')
            try:
                request=json.loads(row[2])
                if (request_hash(request)!=row[4] or request['project_id']!=row[0] or request['host']!=row[1]):
                    raise ValueError('request binding mismatch')
                current,_=jobs._current(conn,attempt_id)
            except (ValueError,KeyError,TypeError,jobs.AttemptError) as exc:
                raise NativeTaskError('NATIVE_QUEUE_BINDING_INVALID') from exc
            if current['state']!='PENDING':return self._existing(conn,current,row[0])
        return self.execute(row[0],row[1],request['job'],idempotency_key=row[3],
            approved_root=request['job']['runRoot'],authorization=request['authorization'],
            _expected_attempt_id=attempt_id)

    def execute(self,project_id,host,job,*,idempotency_key,approved_root,authorization,_expected_attempt_id=None):
        try:job,root,outputs,primary,identity,request=self._prepare(project_id,host,job,idempotency_key,approved_root,authorization)
        except Exception as exc:raise NativeTaskError('NATIVE_REQUEST_REJECTED') from exc
        with closing(self._connect()) as conn:
            attempt=self._enqueue_prepared(conn,project_id,host,identity,request,idempotency_key)
            aid=attempt['attempt_id']
            if _expected_attempt_id is not None and aid!=_expected_attempt_id:
                raise NativeTaskError('NATIVE_QUEUE_ATTEMPT_CHANGED')
            # Holding the attempt's OS lock for the whole execution is what makes
            # "the lock is free" mean "no process is running this attempt". Without
            # it, start-up reconciliation cannot tell a crashed attempt from an
            # in-flight one, and relabelling an in-flight one is forbidden.
            # A busy lock is not an error here: this is the same idempotency key, so
            # the holder is executing the attempt this caller asked about and the
            # answer is its current state. Contending for a *different* attempt on
            # the same host still fails closed with HOST_BUSY from _claim.
            try:
                attempt_lock=recovery_lock(self.paths,aid)
                attempt_lock.__enter__()
            except RecoveryBusy:
                return self._existing(conn,jobs.latest_attempt(conn,attempt['job_id']),project_id)
            try:
                if not self._claim(conn,attempt,host):return self._existing(conn,jobs.latest_attempt(conn,attempt['job_id']),project_id)
                adapter_returned=False
                try:
                    receipt=_dispatch(host,job,project_root=self.owner,approved_root=root)
                    adapter_returned=True
                    self._verify_receipt(receipt,job,request,outputs)
                    with jobs._transaction(conn):
                        conn.execute('UPDATE native_execution_v1 SET receipt_json=? WHERE attempt_id=?',(_json(receipt),aid))
                    asset=self._publish(project_id,'native-'+identity,primary,outputs[primary],receipt,aid)
                    return self._finish(conn,aid,host,dict(asset=asset,native=receipt))
                except Exception as exc:
                    no_effect=(not adapter_returned and isinstance(exc,(photoshop_com.PhotoshopDispatchError,illustrator_com.IllustratorDispatchError)) and not exc.outcome_unknown)
                    current=self._failed(conn,aid,host,no_effect)
                    raise NativeTaskError('NATIVE_NOT_STARTED' if no_effect else 'NATIVE_OUTCOME_UNKNOWN',attempt=current) from exc
            finally:
                attempt_lock.__exit__(None,None,None)
