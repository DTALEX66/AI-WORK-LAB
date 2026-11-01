# SPDX-License-Identifier: MIT
"""Durable native execution: real SQLite, files and threads; COM boundary only doubled."""
from contextlib import closing
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import secrets
import sys
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.service import ProjectService
from design_lab.runtime import job_store
from design_lab.adapters.photoshop_com import PhotoshopDispatchError


def native_receipt(run,job):
    """The bytes and the receipt a real host would leave behind.

    Shared with the crash children below, so a persisted receipt in these tests
    is the same artifact the parent process would have verified, not a shortcut.
    """
    primary=run/job['outputName'];preview=run/job['previewName']
    primary.write_bytes(b'8BPS\x00\x01 controlled fake COM boundary')
    Image.new('RGB',(8,6),'red').save(preview)
    def digest(p):return dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),byte_size=p.stat().st_size)
    return dict(status='NATIVE_READBACK',job_id=job['jobId'],host_version='26.7.0',bridge_sha256='b'*64,
        job_sha256=hashlib.sha256(json.dumps(job,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest(),
        inputs={str(run/'input.png'):digest(run/'input.png')},artifacts={'psd':digest(primary),'png':digest(preview)},
        documents_before=0,documents_after=0)


def quiescence_receipt(job):
    """A fixed host cleanup: the host is idle, the outputs are explicitly not accepted."""
    return dict(status='HOST_QUIESCENT_ARTIFACTS_UNACCEPTED',job_id=job['jobId'],
        documents_before=0,documents_after=0,closed_documents=0,artifacts={})


class NativeFixture:
    """One real project directory, real SQLite, only the COM/host call doubled."""

    def setUp(self):
        parent=ROOT/'.project-local/task-runtime/native-task-tests';parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);(self.root/'AGENTS.md').write_text('# synthetic owner',encoding='utf-8')
        env=patch.dict(os.environ,{'PROJECT_LOCAL_ROOT':str(self.root/'.project-local')});env.start();self.addCleanup(env.stop)
        self.service=ProjectService(self.root);self.project=self.service.create_project('Native test')['id']
        self.run=self.root/'.project-local/task-artifacts/run';self.run.mkdir(parents=True)
        Image.new('RGB',(8,6),'blue').save(self.run/'input.png')
        self.job=dict(schemaVersion='design-lab/photoshop-native-job/v1',jobId='native-test',runRoot=str(self.run),width=8,height=6,
            outputName='output.psd',previewName='output.png',assets=[dict(id='input',path=str(self.run/'input.png'))],
            layers=[dict(id='image',kind='raster',assetId='input',position=[0,0],width=8,height=6)])
        self.authorization=dict(actor='test-owner',scope='project-native-test',receipt='synthetic test authorization')

    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('design_lab.native_tasks'),'durable native executor missing')
        return importlib.import_module('design_lab.native_tasks')

    def execute(self,key='key',job=None):
        return self.module().NativeTasks(self.service).execute(self.project,'photoshop',job or self.job,
            idempotency_key=key,approved_root=self.run,authorization=self.authorization)

    def native(self,host,job,**kwargs):
        return native_receipt(self.run,job)


class NativeTaskTests(NativeFixture,unittest.TestCase):
    def test_restart_reuses_one_native_execution_and_published_version(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native) as invoke:
            first=self.execute();self.service=ProjectService(self.root);second=self.execute()
        self.assertEqual(invoke.call_count,1)
        self.assertEqual(first['asset'],second['asset'])
        self.assertEqual(second['attempt']['state'],'RECEIPTED')
        published=Path(second['asset']['path']);self.assertTrue(published.is_relative_to(self.service.paths.projects_root))
        self.assertEqual(published.read_bytes(),(self.run/'output.psd').read_bytes())

    def test_photoshop_patch_enqueue_binds_checkpoint_and_rejects_changed_bytes(self):
        module=self.module();tasks=module.NativeTasks(self.service)
        checkpoint=self.run/'checkpoint.psd';checkpoint.write_bytes(b'controlled checkpoint')
        checksum=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        job=dict(self.job,schemaVersion='design-lab/photoshop-patch-job/v1',checkpoint=str(checkpoint),
                 checkpointSha256=checksum,patch=dict(kind='move',id='image',delta=[1,0]))
        result=tasks.enqueue(self.project,'photoshop',job,idempotency_key='patch',approved_root=self.run,authorization=self.authorization)
        with closing(tasks._connect()) as conn:
            raw=json.loads(conn.execute('SELECT request_json FROM native_execution_v1 WHERE attempt_id=?',
                (result['attempt']['attempt_id'],)).fetchone()[0])
        self.assertEqual(raw['inputs'].get(str(checkpoint)),dict(sha256=checksum,byte_size=21))
        checkpoint.write_bytes(b'changed')
        with self.assertRaises(module.NativeTaskError):
            tasks.enqueue(self.project,'photoshop',job,idempotency_key='different',approved_root=self.run,authorization=self.authorization)

    def test_photoshop_quiescence_pauses_unknown_without_publishing(self):
        module=self.module();tasks=module.NativeTasks(self.service)
        self.assertTrue(hasattr(tasks,'quiesce_photoshop'))
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('unknown',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        aid=caught.exception.attempt['attempt_id']
        with patch.object(module.photoshop_com,'quiesce',return_value=dict(
            status='HOST_QUIESCENT_ARTIFACTS_UNACCEPTED',job_id='native-test',
            documents_before=0,documents_after=0,closed_documents=0,artifacts={})):
            result=tasks.quiesce_photoshop(aid,authorization=self.authorization)
        self.assertEqual(result['attempt']['state'],'RECONCILING')
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM artifact').fetchone()[0],0)
            _,op=job_store._current(conn,aid)
            self.assertEqual(job_store.operation_status(conn,op)['state'],'PAUSED_NEEDS_USER')

    def test_photoshop_quiescence_rejects_changed_request_before_dispatch(self):
        module=self.module();tasks=module.NativeTasks(self.service)
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('unknown',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        aid=caught.exception.attempt['attempt_id']
        with closing(tasks._connect()) as conn:
            raw=json.loads(conn.execute('SELECT request_json FROM native_execution_v1 WHERE attempt_id=?',(aid,)).fetchone()[0])
            raw['job']['outputName']='different.psd'
            conn.execute('UPDATE native_execution_v1 SET request_json=? WHERE attempt_id=?',(json.dumps(raw),aid));conn.commit()
        with patch.object(module.photoshop_com,'quiesce') as invoke:
            with self.assertRaises(module.NativeTaskError):tasks.quiesce_photoshop(aid,authorization=self.authorization)
            invoke.assert_not_called()
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_quiescence_v1').fetchone()[0],0)

    def test_failed_photoshop_quiescence_keeps_guard_and_never_retries(self):
        module=self.module();tasks=module.NativeTasks(self.service)
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('unknown',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        aid=caught.exception.attempt['attempt_id']
        with patch.object(module.photoshop_com,'quiesce',side_effect=TimeoutError('still unknown')) as invoke:
            for _ in range(2):
                with self.assertRaises(module.NativeTaskError):tasks.quiesce_photoshop(aid,authorization=self.authorization)
            self.assertEqual(invoke.call_count,1)
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM artifact').fetchone()[0],0)

    def test_enqueue_survives_restart_and_execute_uses_same_attempt(self):
        module=self.module()
        queued=module.NativeTasks(self.service).enqueue(self.project,'photoshop',self.job,
            idempotency_key='key',approved_root=self.run,authorization=self.authorization)
        self.assertEqual(queued['attempt']['state'],'PENDING')
        self.assertFalse((self.run/'output.psd').exists())
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],0)
        self.service=ProjectService(self.root)
        with patch.object(module,'_dispatch',side_effect=self.native):
            result=module.NativeTasks(self.service).execute_queued(queued['attempt']['attempt_id'])
        self.assertEqual(result['attempt']['attempt_id'],queued['attempt']['attempt_id'])
        self.assertEqual(result['attempt']['state'],'RECEIPTED')

    def test_cancel_queued_native_task_never_dispatches(self):
        module=self.module()
        queued=module.NativeTasks(self.service).enqueue(self.project,'photoshop',self.job,
            idempotency_key='key',approved_root=self.run,authorization=self.authorization)
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            job_store.request_cancel(conn,queued['attempt']['attempt_id'])
        result=module.NativeTasks(self.service).execute_queued(queued['attempt']['attempt_id'])
        self.assertEqual(result['attempt']['state'],'CANCELLED')
        self.assertFalse((self.run/'output.psd').exists())

    def test_cancel_requested_while_the_host_works_stays_visible_after_receipt(self):
        # No adapter event can acknowledge a stop, so a cancel asked mid-flight ends one of
        # two ways: the host fails (CANCELLED) or it delivers (RECEIPTED with the cancel
        # unacknowledged). The second used to be indistinguishable from an uncontested
        # completion on every surface, which is how a refused operation reads as accepted.
        from design_lab.task_queries import TaskQueries
        module=self.module()
        queued=module.NativeTasks(self.service).enqueue(self.project,'photoshop',self.job,
            idempotency_key='key',approved_root=self.run,authorization=self.authorization)
        aid=queued['attempt']['attempt_id']
        def dispatch_with_cancel(host,job,**kwargs):
            with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
                job_store.request_cancel(conn,aid)
            return self.native(host,job,**kwargs)
        with patch.object(module,'_dispatch',side_effect=dispatch_with_cancel):
            result=module.NativeTasks(self.service).execute_queued(aid)
        self.assertEqual(result['attempt']['state'],'RECEIPTED')
        self.assertIn('cancel',result['attempt']['note'])
        self.assertIn('never acknowledged',result['attempt']['note'])
        task=TaskQueries(self.service).get(self.project,result['attempt']['job_id'])['task']
        self.assertEqual(task['cancel'],{'requested':True,'acknowledged':False})
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            row=conn.execute('SELECT cancel_requested,cancel_acked FROM attempt_resolution'
                             ' WHERE attempt_id=?',(aid,)).fetchone()
        self.assertEqual((row[0],row[1]),(1,0),'an unacknowledged cancel must not be recorded as one')

    def test_an_ordinary_receipt_reports_no_cancel_at_all(self):
        """Falsification for the new readback field: `requested` must not default to true,
        and a plain completion must say so rather than leaving the reader to guess."""
        from design_lab.task_queries import TaskQueries
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native):
            result=self.execute()
        task=TaskQueries(self.service).get(self.project,result['attempt']['job_id'])['task']
        self.assertEqual(task['cancel'],{'requested':False,'acknowledged':False})
        self.assertNotIn('cancel',result['attempt']['note'])

    def test_queued_input_change_is_rejected_before_host_claim(self):
        module=self.module()
        queued=module.NativeTasks(self.service).enqueue(self.project,'photoshop',self.job,
            idempotency_key='key',approved_root=self.run,authorization=self.authorization)
        Image.new('RGB',(8,6),'green').save(self.run/'input.png')
        with self.assertRaisesRegex(module.NativeTaskError,'NATIVE_IDEMPOTENCY_CONFLICT'):
            module.NativeTasks(self.service).execute_queued(queued['attempt']['attempt_id'])
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],0)
        self.assertFalse((self.run/'output.psd').exists())

    def test_queue_worker_rejects_modified_persisted_request(self):
        module=self.module()
        queued=module.NativeTasks(self.service).enqueue(self.project,'photoshop',self.job,
            idempotency_key='key',approved_root=self.run,authorization=self.authorization)
        aid=queued['attempt']['attempt_id']
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            raw=json.loads(conn.execute('SELECT request_json FROM native_execution_v1 WHERE attempt_id=?',(aid,)).fetchone()[0])
            raw['job']['width']=99
            conn.execute('UPDATE native_execution_v1 SET request_json=? WHERE attempt_id=?',(json.dumps(raw),aid));conn.commit()
        with self.assertRaisesRegex(module.NativeTaskError,'NATIVE_QUEUE_BINDING_INVALID'):
            module.NativeTasks(self.service).execute_queued(aid)
        self.assertFalse((self.run/'output.psd').exists())

    def test_cli_worker_reads_cancelled_attempt_without_host_dispatch(self):
        queued=self.module().NativeTasks(self.service).enqueue(self.project,'photoshop',self.job,
            idempotency_key='key',approved_root=self.run,authorization=self.authorization)
        aid=queued['attempt']['attempt_id']
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            job_store.request_cancel(conn,aid)
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1')
        child=subprocess.run([sys.executable,'-B','-X','utf8','-m','design_lab','--project',str(self.root),
            'native-worker','--attempt',aid],cwd=self.root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(child.returncode,0,child.stderr)
        data=json.loads(child.stdout)
        self.assertEqual(data,{'attempt_id':aid,'state':'CANCELLED'})
        self.assertFalse((self.run/'output.psd').exists())
        missing=subprocess.run([sys.executable,'-B','-X','utf8','-m','design_lab','--project',str(self.root),
            'native-worker','--attempt','att-'+'0'*32],cwd=self.root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(missing.returncode,2)
        self.assertEqual(json.loads(missing.stdout),{'status':'ERROR','error':'NATIVE_REQUEST_MISSING'})
        self.assertEqual(missing.stderr,'')

    def test_background_worker_records_real_predispatch_rejection(self):
        from design_lab.native_workers import NativeWorkers
        invalid=dict(self.job,width=0)
        queued=self.module().NativeTasks(self.service).enqueue(self.project,'photoshop',invalid,
            idempotency_key='invalid-worker',approved_root=self.run,authorization=self.authorization)
        task=queued['attempt'];workers=NativeWorkers(self.service)
        result=workers.start(self.project,task['job_id'],task['attempt_id'])
        self.assertEqual(result['worker'],'STARTED')
        process=workers._processes[task['attempt_id']]
        self.assertEqual(process.wait(timeout=30),2)
        from design_lab.task_queries import TaskQueries
        current=TaskQueries(self.service).get(self.project,task['job_id'])
        self.assertEqual(current['task']['attempt']['state'],'FAILED')
        self.assertFalse((self.run/'output.psd').exists())

    def test_different_request_same_key_rejected_without_dispatch(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native) as invoke:
            self.execute();changed=dict(self.job);changed['width']=9
            with self.assertRaises(module.NativeTaskError):self.execute(job=changed)
        self.assertEqual(invoke.call_count,1)

    def test_timeout_persists_host_guard_across_restart_and_projects(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('timeout',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        self.assertEqual(caught.exception.attempt['state'],'OUTCOME_UNKNOWN')
        self.service=ProjectService(self.root);self.project=self.service.create_project('Other')['id']
        with patch.object(module,'_dispatch') as invoke:
            with self.assertRaisesRegex(module.NativeTaskError,'HOST_BUSY'):self.execute('other-key')
            invoke.assert_not_called()

    def test_preflight_rejection_releases_host_without_auto_retry(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('invalid')):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        self.assertEqual(caught.exception.attempt['state'],'FAILED')
        with patch.object(module,'_dispatch',side_effect=self.native) as invoke:
            unchanged=self.execute();good=self.execute('new-key')
        self.assertEqual(unchanged['attempt']['state'],'FAILED')
        self.assertEqual(good['attempt']['state'],'RECEIPTED');self.assertEqual(invoke.call_count,1)

    def test_concurrent_workers_do_not_double_dispatch(self):
        module=self.module();entered=threading.Event();release=threading.Event();results=[]
        def slow(*args,**kwargs):
            entered.set()
            if not release.wait(10):raise RuntimeError('test release timeout')
            return self.native(*args,**kwargs)
        def worker():
            try:results.append(self.execute())
            except BaseException as e:results.append(e)
        with patch.object(module,'_dispatch',side_effect=slow) as invoke:
            thread=threading.Thread(target=worker);thread.start()
            try:
                self.assertTrue(entered.wait(10));second=self.execute()
                self.assertEqual(second['attempt']['state'],'RUNNING')
                with self.assertRaisesRegex(module.NativeTaskError,'HOST_BUSY'):self.execute('second-key')
            finally:release.set();thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(invoke.call_count,1)
        self.assertEqual(results[0]['attempt']['state'],'RECEIPTED')

    def test_bad_receipt_retains_unresolved_guard(self):
        module=self.module()
        def wrong(*args,**kwargs):
            receipt=self.native(*args,**kwargs);receipt['job_sha256']='0'*64;return receipt
        with patch.object(module,'_dispatch',side_effect=wrong):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        self.assertEqual(caught.exception.attempt['state'],'OUTCOME_UNKNOWN')
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
        with patch.object(module,'_dispatch') as invoke:
            self.assertEqual(self.execute()['attempt']['state'],'OUTCOME_UNKNOWN');invoke.assert_not_called()

    def test_publication_failure_does_not_redispatch_or_release_guard(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native),patch.object(module.assets,'publish_version',side_effect=OSError('test disk failure')):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        self.assertEqual(caught.exception.attempt['state'],'OUTCOME_UNKNOWN')
        self.assertTrue((self.run/'output.psd').exists())
        with patch.object(module,'_dispatch') as invoke:
            with self.assertRaisesRegex(module.NativeTaskError,'HOST_BUSY'):self.execute('other')
            invoke.assert_not_called()

    def test_reconcile_persisted_receipt_publishes_without_host_redispatch(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native),patch.object(module.assets,'publish_version',side_effect=OSError('disk failure')):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        self.service=ProjectService(self.root)
        tasks=module.NativeTasks(self.service)
        self.assertTrue(hasattr(tasks,'reconcile_receipted'),'persisted receipt recovery missing')
        with patch.object(module,'_dispatch',side_effect=AssertionError('must not redispatch')):
            result=tasks.reconcile_receipted(caught.exception.attempt['attempt_id'],authorization=self.authorization)
            replay=tasks.reconcile_receipted(caught.exception.attempt['attempt_id'],authorization=self.authorization)
        self.assertEqual(result['asset'],replay['asset'])
        self.assertEqual(result['attempt']['state'],'RECEIPTED')
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],0)

    def test_reconcile_after_publication_reuses_committed_version(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native),patch.object(module.NativeTasks,'_finish',side_effect=OSError('finish interrupted')):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        tasks=module.NativeTasks(self.service)
        self.assertTrue(hasattr(tasks,'reconcile_receipted'),'persisted receipt recovery missing')
        with closing(tasks._connect()) as conn:
            version=conn.execute('SELECT version_id FROM asset_version').fetchone()[0]
        result=tasks.reconcile_receipted(caught.exception.attempt['attempt_id'],authorization=self.authorization)
        self.assertEqual(result['asset']['version_id'],version)

    def test_reconcile_unknown_host_without_receipt_keeps_guard(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('timeout',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        tasks=module.NativeTasks(self.service)
        self.assertTrue(hasattr(tasks,'reconcile_receipted'),'persisted receipt recovery missing')
        with self.assertRaises(module.NativeTaskError):
            tasks.reconcile_receipted(caught.exception.attempt['attempt_id'],authorization=self.authorization)
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)

    def test_reconcile_changed_input_cannot_publish_or_release_guard(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native),patch.object(module.assets,'publish_version',side_effect=OSError('disk failure')):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        (self.run/'input.png').write_bytes(b'changed')
        tasks=module.NativeTasks(self.service)
        self.assertTrue(hasattr(tasks,'reconcile_receipted'),'persisted receipt recovery missing')
        with self.assertRaises(module.NativeTaskError):
            tasks.reconcile_receipted(caught.exception.attempt['attempt_id'],authorization=self.authorization)
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)

    def test_legacy_reconciliation_claim_cannot_be_inferred_stopped(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native),patch.object(module.assets,'publish_version',side_effect=OSError('disk failure')):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        aid=caught.exception.attempt['attempt_id'];tasks=module.NativeTasks(self.service)
        with self.assertRaisesRegex(module.NativeTaskError,'AUTHORIZATION'):
            tasks.reconcile_receipted(aid,authorization={})
        with patch.object(module.assets,'publish_version',side_effect=OSError('still unavailable')):
            with self.assertRaises(module.NativeTaskError):tasks.reconcile_receipted(aid,authorization=self.authorization)
        # Model the previous implementation: a claim with no OS-lock protocol.
        with closing(tasks._connect()) as conn:
            conn.execute('DELETE FROM native_recovery_protocol_v2 WHERE attempt_id=?',(aid,))
            conn.commit()
        with patch.object(module.assets,'publish_version',side_effect=AssertionError('must not steal')) as publish:
            with self.assertRaisesRegex(module.NativeTaskError,'NOT_ELIGIBLE'):
                module.NativeTasks(ProjectService(self.root)).reconcile_receipted(aid,authorization=self.authorization)
            publish.assert_not_called()
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_reconciliation_v1').fetchone()[0],1)

    def test_recovery_can_resume_after_os_locked_worker_returns(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native),patch.object(module.assets,'publish_version',side_effect=OSError('disk failure')):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        aid=caught.exception.attempt['attempt_id'];tasks=module.NativeTasks(self.service)
        with patch.object(module.assets,'publish_version',side_effect=OSError('recovery failure')):
            with self.assertRaises(module.NativeTaskError):tasks.reconcile_receipted(aid,authorization=self.authorization)
        from design_lab.runtime.native_recovery_lock import recovery_lock
        with recovery_lock(tasks.paths,aid):
            with self.assertRaisesRegex(module.NativeTaskError,'WORKER_ACTIVE'):
                tasks.reconcile_receipted(aid,authorization=self.authorization)
        with patch.object(module,'_dispatch',side_effect=AssertionError('no host dispatch')):
            result=module.NativeTasks(ProjectService(self.root)).reconcile_receipted(aid,authorization=self.authorization)
        self.assertEqual(result['attempt']['state'],'RECEIPTED')
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],1)

    def test_recovery_process_crash_after_publish_resumes_same_version(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native),patch.object(module.assets,'publish_version',side_effect=OSError('disk failure')):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        aid=caught.exception.attempt['attempt_id']
        code=(
            'import sys,os; sys.path.insert(0,sys.argv[1]); '
            'from design_lab.service import ProjectService; '
            'from design_lab.native_tasks import NativeTasks; '
            't=NativeTasks(ProjectService(sys.argv[2])); '
            't._finish=lambda *a,**k: os._exit(43); '
            't.reconcile_receipted(sys.argv[3],authorization=dict(actor="test",scope="project-native-test",receipt="crash fixture"))'
        )
        child=subprocess.run([sys.executable,'-B','-X','utf8','-c',code,str(ROOT/'src'),str(self.root),aid],
                             capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=20)
        self.assertEqual(child.returncode,43,child.stderr)
        tasks=module.NativeTasks(ProjectService(self.root))
        with closing(tasks._connect()) as conn:
            version=conn.execute('SELECT version_id FROM asset_version').fetchone()[0]
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)
        result=tasks.reconcile_receipted(aid,authorization=self.authorization)
        self.assertEqual(result['attempt']['state'],'RECEIPTED')
        self.assertEqual(result['asset']['version_id'],version)
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],1)

    def test_recovery_crash_during_stage_or_rename_preserves_uncommitted_bytes(self):
        module=self.module()
        for seam in ('_after_stage','_after_rename'):
            with self.subTest(window=seam):
                with patch.object(module,'_dispatch',side_effect=self.native),patch.object(module.assets,'publish_version',side_effect=OSError('disk failure')):
                    with self.assertRaises(module.NativeTaskError) as caught:self.execute(key=seam)
                aid=caught.exception.attempt['attempt_id']
                code=(
                    'import sys,os; sys.path.insert(0,sys.argv[1]); '
                    'from design_lab.service import ProjectService; '
                    'from design_lab.native_tasks import NativeTasks; '
                    'from design_lab.runtime import asset_store; '
                    'setattr(asset_store,sys.argv[4],lambda *a: os._exit(43)); '
                    'NativeTasks(ProjectService(sys.argv[2])).reconcile_receipted(sys.argv[3],'
                    'authorization=dict(actor="test",scope="project-native-test",receipt="crash fixture"))'
                )
                child=subprocess.run([sys.executable,'-B','-X','utf8','-c',code,str(ROOT/'src'),str(self.root),aid,seam],
                                     capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=20)
                self.assertEqual(child.returncode,43,child.stderr)
                tasks=module.NativeTasks(ProjectService(self.root))
                result=tasks.reconcile_receipted(aid,authorization=self.authorization)
                self.assertEqual(result['attempt']['state'],'RECEIPTED')
                with closing(tasks._connect()) as conn:
                    rows=conn.execute('SELECT state,quarantine_path FROM asset_publication WHERE holder_attempt_id=?',(aid,)).fetchall()
                    self.assertEqual(sorted(r[0] for r in rows),['COMMITTED','QUARANTINED'])
                    quarantine=Path(next(r[1] for r in rows if r[0]=='QUARANTINED'))
                    self.assertEqual(quarantine.read_bytes(),(self.run/'output.psd').read_bytes())

    def test_pre_dispatch_cancel_is_not_sent_to_host(self):
        module=self.module()
        # First unresolved job occupies host; second remains PENDING.
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('timeout',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError):self.execute()
        with self.assertRaises(module.NativeTaskError) as busy:self.execute('pending')
        aid=busy.exception.attempt['attempt_id']
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:job_store.request_cancel(conn,aid)
        with patch.object(module,'_dispatch') as invoke:
            self.assertEqual(self.execute('pending')['attempt']['state'],'CANCELLED');invoke.assert_not_called()

    def test_proven_preflight_failure_allows_explicit_next_attempt(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('preflight')):
            with self.assertRaises(module.NativeTaskError) as failure:self.execute()
        old=failure.exception.attempt
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            job_store.retry_attempt(conn,old['job_id'],previous_attempt_id=old['attempt_id'])
        with patch.object(module,'_dispatch',side_effect=self.native):result=self.execute()
        self.assertEqual(result['attempt']['attempt_no'],2);self.assertEqual(result['attempt']['state'],'RECEIPTED')

    def test_changed_input_same_key_is_conflict_even_when_path_unchanged(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native):self.execute()
        Image.new('RGB',(8,6),'green').save(self.run/'input.png')
        with patch.object(module,'_dispatch') as invoke:
            with self.assertRaisesRegex(module.NativeTaskError,'IDEMPOTENCY_CONFLICT'):self.execute()
            invoke.assert_not_called()

    def test_missing_scoped_authorization_never_dispatches(self):
        module=self.module();self.authorization={}
        with patch.object(module,'_dispatch') as invoke:
            with self.assertRaisesRegex(module.NativeTaskError,'REQUEST_REJECTED'):self.execute()
            invoke.assert_not_called()

    def test_native_bundle_export_preserves_outputs_inputs_and_primary_contract(self):
        import zipfile
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native):result=self.execute()
        tasks=module.NativeTasks(self.service)
        self.assertTrue(hasattr(tasks,'export_bundle'),'native bundle export missing')
        aid=result['attempt']['attempt_id']
        with patch.object(module,'_dispatch',side_effect=AssertionError('export must not dispatch')):
            bundle=tasks.export_bundle(aid,authorization=self.authorization)
            again=tasks.export_bundle(aid,authorization=self.authorization)
        self.assertEqual(bundle,again)
        with zipfile.ZipFile(bundle['path']) as archive:
            self.assertEqual(set(archive.namelist()),{'bundle-manifest.json','native.psd','preview.png','inputs/0000.png'})
            self.assertEqual(archive.read('native.psd'),Path(result['asset']['path']).read_bytes())
            self.assertEqual(archive.read('inputs/0000.png'),(self.run/'input.png').read_bytes())
            manifest=json.loads(archive.read('bundle-manifest.json'))
            self.assertEqual(manifest['metadata']['rights'],'NOT_REVIEWED')
            self.assertEqual(manifest['metadata']['link_relocation'],'NOT_VERIFIED')
        self.assertEqual(self.execute()['asset'],result['asset'])

    def test_bundle_records_requested_fonts_without_claiming_license_or_observation(self):
        import zipfile
        module=self.module()
        self.job['layers'].extend([
            dict(id='title',kind='text',font='ArialMT',text='Title',size=12,position=[0,0],color=[0,0,0]),
            dict(id='subtitle',kind='text',font='ArialMT',text='Subtitle',size=10,position=[0,2],color=[0,0,0])])
        with patch.object(module,'_dispatch',side_effect=self.native):result=self.execute()
        bundle=module.NativeTasks(self.service).export_bundle(result['attempt']['attempt_id'],authorization=self.authorization)
        with zipfile.ZipFile(bundle['path']) as archive:
            metadata=json.loads(archive.read('bundle-manifest.json'))['metadata']
        self.assertEqual(metadata.get('requested_fonts'),[{'postscript_name':'ArialMT','object_ids':['subtitle','title']}])
        self.assertEqual(metadata.get('font_inventory'),'REQUESTED_ONLY')
        self.assertEqual(metadata.get('font_rights'),'NOT_REVIEWED')
        self.assertEqual(metadata.get('font_observation'),'NOT_COLLECTED')
        self.assertEqual(metadata.get('native_receipt_binding'),{
            'attempt_id':result['attempt']['attempt_id'],
            'bridge_sha256':result['native']['bridge_sha256'],
            'job_sha256':result['native']['job_sha256']})

    def test_requested_font_inventory_traverses_nested_items_and_ignores_shapes(self):
        from design_lab.native_bundles import _requested_fonts
        job={'layers':[{'items':[{'id':'group','kind':'group','items':[
            {'id':'a','kind':'text','font':'Font-B'},
            {'id':'inner','kind':'group','items':[{'id':'b','kind':'text','font':'Font-A'}]},
            {'id':'shape','kind':'path','font':'not-a-text-font'}]}]}]}
        self.assertEqual(_requested_fonts(job),[
            {'postscript_name':'Font-A','object_ids':['b']},
            {'postscript_name':'Font-B','object_ids':['a']}])
        self.assertEqual(_requested_fonts({'layers':[{'kind':'raster','id':'image'}]}),[])
        with self.assertRaises(ValueError):
            _requested_fonts({'layers':[{'kind':'text','id':'bad','font':''}]})

    def test_requested_font_inventory_includes_photoshop_nested_group_children(self):
        from design_lab.native_bundles import _requested_fonts
        job={'layers':[{'id':'outer','kind':'group','children':[
            {'id':'inner','kind':'group','children':[{'id':'title','kind':'text','font':'ArialMT'}]}]}]}
        self.assertEqual(_requested_fonts(job),[{'postscript_name':'ArialMT','object_ids':['title']}])

    def test_native_bundle_export_rejects_changed_preview(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native):result=self.execute()
        (self.run/'output.png').write_bytes(b'changed preview')
        tasks=module.NativeTasks(self.service)
        self.assertTrue(hasattr(tasks,'export_bundle'),'native bundle export missing')
        with self.assertRaises(module.NativeTaskError):
            tasks.export_bundle(result['attempt']['attempt_id'],authorization=self.authorization)
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],1)

    def test_unknown_native_attempt_cannot_export_a_completed_bundle(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('timeout',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError) as caught:self.execute()
        tasks=module.NativeTasks(self.service)
        self.assertTrue(hasattr(tasks,'export_bundle'),'native bundle export missing')
        with self.assertRaises(module.NativeTaskError):
            tasks.export_bundle(caught.exception.attempt['attempt_id'],authorization=self.authorization)

    def test_published_bytes_tampered_replay_does_not_return_success(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=self.native):result=self.execute()
        Path(result['asset']['path']).write_bytes(b'tampered')
        with patch.object(module,'_dispatch') as invoke:
            with self.assertRaises(module.NativeTaskError):self.execute()
            invoke.assert_not_called()


class StartUpRecoveryDecisions(NativeFixture,unittest.TestCase):
    """A project that died mid-host-run must be reachable from the product, not only from tests.

    reconcile_receipted and quiesce_* existed and were unit tested, but nothing in
    production could call them, so an attempt left at OUTCOME_UNKNOWN was a
    permanent dead end. These drive the start-up readback and the explicit operator
    decision through the real service, the real CLI and a real child process that
    dies during the host call; only the COM boundary is doubled.
    """

    def crash_child(self,*,persist_receipt,key='crash'):
        """Die in a real child process mid-run, leaving the attempt RUNNING with its guard.

        persist_receipt=False is a process killed inside COM; True is one killed
        after its receipt row committed but before publication. Both are what a
        crash actually leaves behind: no verdict, no artifact, host held.
        """
        module=self.module()
        queued=module.NativeTasks(self.service).enqueue(self.project,'photoshop',self.job,
            idempotency_key=key,approved_root=self.run,authorization=self.authorization)
        aid=queued['attempt']['attempt_id']
        crash=('nt.NativeTasks._publish=lambda *a,**k: os._exit(43); ' if persist_receipt
               else 'nt._dispatch=lambda host,j,**k: os._exit(43); ')
        code=('import sys,os,json; sys.path.insert(0,sys.argv[1]); sys.path.insert(0,sys.argv[5]); '
              'from pathlib import Path; import test_native_tasks as T; '
              'from design_lab.service import ProjectService; from design_lab import native_tasks as nt; '
              'run=Path(sys.argv[4]); job=json.loads(sys.argv[6]); '
              'nt._dispatch=lambda host,j,**k: T.native_receipt(run,j); '+crash+
              'nt.NativeTasks(ProjectService(sys.argv[2])).execute(sys.argv[3],"photoshop",job,'
              'idempotency_key=sys.argv[7],approved_root=str(run),authorization=json.loads(sys.argv[8]))')
        child=subprocess.run([sys.executable,'-B','-X','utf8','-c',code,str(ROOT/'src'),str(self.root),
            self.project,str(self.run),str(Path(__file__).resolve().parent),json.dumps(self.job),key,
            json.dumps(self.authorization)],cwd=str(self.root),capture_output=True,text=True,
            encoding='utf-8',errors='replace',timeout=60)
        self.assertEqual(child.returncode,43,child.stderr)
        identity=hashlib.sha256((self.project+':photoshop:'+key).encode()).hexdigest()
        with closing(job_store.connect(self.service.database,project_root=self.root)) as conn:
            self.assertEqual(job_store.latest_attempt(conn,'native-job-'+identity)['state'],'RUNNING')
        with closing(module.NativeTasks(self.service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1,
                             'the crashed run must still own its host guard')
            self.assertEqual(conn.execute('SELECT receipt_json IS NOT NULL FROM native_execution_v1 '
                'WHERE attempt_id=?',(aid,)).fetchone()[0],1 if persist_receipt else 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
        return aid

    def decision(self,attempt_id):
        found=[d for d in self.service.recovery_readback()['decisions'] if d['attempt_id']==attempt_id]
        self.assertEqual(len(found),1,'the unresolved attempt must be listed exactly once')
        return found[0]

    def cli(self,*argv):
        from design_lab import cli
        out=io.StringIO()
        with patch('sys.stdout',new=out):
            code=cli.main(['--project',str(self.root),*argv])
        return code,json.loads(out.getvalue()),out.getvalue()

    def test_a_crashed_host_run_is_listed_as_needing_a_decision(self):
        module=self.module();aid=self.crash_child(persist_receipt=False)
        self.assertEqual(self.service.recovery_readback()['pending'],1)
        crashed=self.decision(aid)
        self.assertEqual(crashed['state'],'RUNNING')
        self.assertIsNone(crashed['action'],'a crash may not be decided before it is labelled')
        self.assertEqual(crashed['reason'],'RUNNING_ATTEMPT_AWAITS_START_UP_RELABELLING')
        self.assertFalse(crashed['worker_active'],'the crashed holder must be provably gone')
        # A readback is a read: nothing is decided, released or published by looking.
        self.assertEqual(self.decision(aid),crashed)
        self.assertEqual(self.service.reconcile_interrupted_attempts(),[aid])
        listed=self.decision(aid)
        self.assertEqual((listed['state'],listed['operation'],listed['host_guard'],
            listed['receipt_persisted'],listed['action']),
            ('OUTCOME_UNKNOWN','OUTCOME_UNKNOWN','self',False,'quiesce'))
        with closing(module.NativeTasks(self.service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM artifact').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_quiescence_v1').fetchone()[0],0)

    def test_boot_decision_reconciles_the_persisted_receipt_and_never_redispatches(self):
        module=self.module();aid=self.crash_child(persist_receipt=True)
        self.assertEqual(self.service.reconcile_interrupted_attempts(),[aid])
        listed=self.decision(aid)
        self.assertEqual((listed['action'],listed['receipt_persisted'],listed['host_guard']),
                         ('reconcile',True,'self'))
        with closing(module.NativeTasks(self.service)._connect()) as conn:
            persisted=conn.execute('SELECT receipt_json FROM native_execution_v1 WHERE attempt_id=?',
                                   (aid,)).fetchone()[0]
        self.assertTrue(persisted,'the crashed run committed its receipt before dying')
        with patch.object(module,'_dispatch',side_effect=AssertionError('recovery must not dispatch')) as invoke,\
             patch.object(module.photoshop_com,'execute') as adapter:
            decided=self.service.decide_native_recovery(aid,authorization=self.authorization)
        invoke.assert_not_called();adapter.assert_not_called()
        self.assertEqual(decided['result']['attempt']['state'],'RECEIPTED')
        published=Path(decided['result']['asset']['path'])
        self.assertTrue(published.is_relative_to(self.service.paths.projects_root))
        self.assertEqual(published.read_bytes(),(self.run/'output.psd').read_bytes())
        with closing(module.NativeTasks(self.service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT receipt_json FROM native_execution_v1 WHERE attempt_id=?',
                (aid,)).fetchone()[0],persisted,'it used the persisted receipt, not new host evidence')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],1)
            proof,evidence=conn.execute('SELECT proof,evidence_json FROM attempt_resolution WHERE attempt_id=?',
                                        (aid,)).fetchone()
        self.assertEqual(proof,'effect_verified')
        bound=json.loads(evidence)
        # The success is bound to bytes that exist, so it is not a claimed verdict.
        self.assertEqual(bound['artifact_sha256'],
                         'sha256:'+hashlib.sha256((self.run/'output.psd').read_bytes()).hexdigest())
        self.assertEqual(bound['attempt_id'],aid)
        self.assertEqual(self.service.recovery_readback()['pending'],0,'decided work stops being pending')

    def test_a_live_run_lease_refuses_the_decision_and_leaves_the_attempt_untouched(self):
        module=self.module();aid=self.crash_child(persist_receipt=True)
        self.assertEqual(self.service.reconcile_interrupted_attempts(),[aid])
        self.assertEqual(self.decision(aid)['action'],'reconcile')
        from design_lab.runtime.native_recovery_lock import recovery_lock
        tasks=module.NativeTasks(self.service)
        with recovery_lock(tasks.paths,aid):
            live=self.decision(aid)
            self.assertTrue(live['worker_active'])
            self.assertEqual(live['reason'],'NATIVE_RUN_LIVE')
            self.assertIsNone(live['action'])
            with patch.object(module,'_dispatch',side_effect=AssertionError('no host')) as invoke,\
                 patch.object(module.assets,'publish_version') as publish:
                with self.assertRaises(module.NativeTaskError) as caught:
                    self.service.decide_native_recovery(aid,authorization=self.authorization)
            self.assertEqual(str(caught.exception),'RECOVERY_DECISION_WORKER_ACTIVE')
            invoke.assert_not_called();publish.assert_not_called()
        after=self.decision(aid)
        self.assertEqual((after['state'],after['host_guard'],after['receipt_persisted'],after['action']),
                         ('OUTCOME_UNKNOWN','self',True,'reconcile'))
        with closing(tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT attempt_id FROM native_host_guard_v1').fetchone(),(aid,),
                             'a refused decision may not release the guard')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)

    def test_an_attempt_whose_host_belongs_to_another_run_is_refused(self):
        module=self.module()
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('unknown',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError) as first:self.execute(key='one')
        a=first.exception.attempt['attempt_id']
        with patch.object(module.photoshop_com,'quiesce',return_value=quiescence_receipt(self.job)):
            self.service.decide_native_recovery(a,authorization=self.authorization)
        self.assertEqual(self.decision(a)['reason'],'HOST_QUIESCENT_OUTPUTS_UNACCEPTED_NEEDS_USER')
        self.assertIsNone(self.decision(a)['action'])
        with patch.object(module,'_dispatch',side_effect=PhotoshopDispatchError('unknown',outcome_unknown=True)):
            with self.assertRaises(module.NativeTaskError) as second:self.execute(key='two')
        b=second.exception.attempt['attempt_id']
        blocked=self.decision(a)
        self.assertEqual((blocked['host_guard'],blocked['action'],blocked['reason'],
                          blocked['blocking_attempt_id']),
                         ('other',None,'HOST_GUARD_HELD_BY_ANOTHER_ATTEMPT',b))
        self.assertEqual(self.decision(b)['action'],'quiesce','the current holder is still decidable')
        with patch.object(module,'_dispatch',side_effect=AssertionError('no host')) as invoke,\
             patch.object(module.photoshop_com,'quiesce') as cleanup:
            with self.assertRaises(module.NativeTaskError) as refused:
                self.service.decide_native_recovery(a,authorization=self.authorization)
            invoke.assert_not_called();cleanup.assert_not_called()
        self.assertEqual(str(refused.exception),'RECOVERY_DECISION_INDETERMINATE')
        self.assertEqual(refused.exception.attempt['reason'],'HOST_GUARD_HELD_BY_ANOTHER_ATTEMPT')
        with closing(module.NativeTasks(self.service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT attempt_id FROM native_host_guard_v1').fetchall(),[(b,)],
                             'refusing must not disturb the run that owns the host')

    def test_no_verdict_without_operator_authorization_and_no_pass_without_evidence(self):
        module=self.module();aid=self.crash_child(persist_receipt=False)
        self.assertEqual(self.service.reconcile_interrupted_attempts(),[aid])
        self.assertEqual(self.decision(aid)['action'],'quiesce')
        unsigned=({},dict(self.authorization,actor='  '),dict(self.authorization,scope='any-other-scope'),
                  dict(self.authorization,receipt=''),dict(self.authorization,extra='x'))
        with patch.object(module,'_dispatch',side_effect=AssertionError('no host')) as invoke,\
             patch.object(module.photoshop_com,'quiesce') as cleanup:
            for bad in unsigned:
                with self.assertRaises(module.NativeTaskError) as caught:
                    self.service.decide_native_recovery(aid,authorization=bad)
                self.assertEqual(str(caught.exception),'RECOVERY_DECISION_AUTHORIZATION_REQUIRED')
            cleanup.assert_not_called()
            self.assertEqual(self.decision(aid)['action'],'quiesce','a refusal decides nothing')
            with patch.object(module.photoshop_com,'quiesce',
                              return_value=quiescence_receipt(self.job)) as done:
                decided=self.service.decide_native_recovery(aid,authorization=self.authorization)
            invoke.assert_not_called()
            self.assertEqual(done.call_count,1)
        attempt=decided['result']['attempt']
        self.assertEqual(attempt['state'],'RECONCILING')
        self.assertNotIn(attempt['state'],job_store.TERMINAL)
        self.assertEqual(decided['result']['quiescence']['status'],'HOST_QUIESCENT_ARTIFACTS_UNACCEPTED')
        with closing(module.NativeTasks(self.service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM artifact').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],0)
            _,op=job_store._current(conn,aid)
            self.assertEqual(job_store.operation_status(conn,op)['state'],'PAUSED_NEEDS_USER')
        self.assertEqual(self.service.recovery_readback()['actionable'],0,
                         'a paused host is pending a human judgement, never an action')
        self.assertTrue(self.decision(aid)['quiescence_recorded'])

    def test_an_unbound_persisted_request_offers_no_action_and_stays_unknown(self):
        module=self.module();aid=self.crash_child(persist_receipt=False)
        self.assertEqual(self.service.reconcile_interrupted_attempts(),[aid])
        self.assertEqual(self.decision(aid)['action'],'quiesce')
        with closing(module.NativeTasks(self.service)._connect()) as conn:
            raw=json.loads(conn.execute('SELECT request_json FROM native_execution_v1 WHERE attempt_id=?',
                                        (aid,)).fetchone()[0])
            raw['job']['outputName']='different.psd'
            conn.execute('UPDATE native_execution_v1 SET request_json=? WHERE attempt_id=?',
                         (json.dumps(raw),aid));conn.commit()
        tampered=self.decision(aid)
        self.assertFalse(tampered['request_bound'])
        self.assertIsNone(tampered['action'])
        self.assertEqual(tampered['reason'],'NATIVE_REQUEST_UNBOUND')
        with patch.object(module,'_dispatch') as invoke,\
             patch.object(module.photoshop_com,'quiesce') as cleanup:
            with self.assertRaises(module.NativeTaskError) as caught:
                self.service.decide_native_recovery(aid,authorization=self.authorization)
            invoke.assert_not_called();cleanup.assert_not_called()
        self.assertEqual(str(caught.exception),'RECOVERY_DECISION_INDETERMINATE')
        self.assertEqual(caught.exception.attempt['state'],'OUTCOME_UNKNOWN')
        with closing(module.NativeTasks(self.service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_quiescence_v1').fetchone()[0],0)

    def test_the_cli_lists_and_decides_only_for_a_signed_operator(self):
        module=self.module();aid=self.crash_child(persist_receipt=True)
        self.assertEqual(self.service.reconcile_interrupted_attempts(),[aid])
        with patch.object(module,'_dispatch',side_effect=AssertionError('the host stays untouched')) as invoke:
            code,listing,printed=self.cli('native-recovery')
            self.assertEqual((code,listing['status'],listing['recovery']['status'],
                              listing['recovery']['pending'],listing['recovery']['actionable']),
                             (0,'RECOVERY_READBACK','OK',1,1))
            self.assertEqual(listing['recovery']['needsDecision'][0]['action'],'reconcile')
            self.assertNotIn(str(self.run),printed,'the readback must not carry the run root')
            self.assertNotIn(self.authorization['receipt'],printed)
            code,refused,_=self.cli('native-recovery','--attempt',aid)
            self.assertEqual((code,refused['error']),(2,'RECOVERY_DECISION_AUTHORIZATION_REQUIRED'))
            self.assertEqual(self.decision(aid)['action'],'reconcile','the refusal decided nothing')
            code,decided,_=self.cli('native-recovery','--attempt',aid,'--actor','recovery-operator',
                '--receipt','operator authorized publication-only recovery after the crash')
            self.assertEqual(code,0)
            self.assertEqual((decided['status'],decided['action'],decided['state'],
                              decided['artifacts_accepted']),('RECOVERY_DECIDED','reconcile','RECEIPTED',True))
            invoke.assert_not_called()
            code,after,after_text=self.cli('native-recovery')
            self.assertEqual((code,after['recovery']['pending'],after['recovery']['actionable']),(0,0,0))
            self.assertNotIn(str(self.run),after_text)

    def test_the_server_boot_announces_what_needs_a_decision_and_takes_no_action(self):
        aid=self.crash_child(persist_receipt=True)
        code='import sys; sys.path.insert(0, sys.argv.pop(1)); from design_lab.cli import main; sys.exit(main())'
        child=subprocess.Popen([sys.executable,'-B','-X','utf8','-c',code,str(ROOT/'src'),
            '--project',str(self.root),'serve','--port','0'],cwd=str(self.root),env=dict(os.environ),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        self.addCleanup(self.stop_server,child)
        child.stdin.write(secrets.token_hex(32)+'\n');child.stdin.flush();child.stdin.close()
        lines=queue.Queue()
        threading.Thread(target=lambda:lines.put(child.stdout.readline()),daemon=True).start()
        try:line=lines.get(timeout=30)
        except queue.Empty:self.fail('the server never announced readiness')
        self.stop_server(child)
        ready=json.loads(line)
        self.assertEqual(ready['status'],'LISTENING')
        self.assertEqual(ready['reconciled_attempts'],1,'start-up still converts the crash')
        self.assertEqual([(d['attempt_id'],d['state'],d['action']) for d in ready['recovery']['needsDecision']],
                         [(aid,'OUTCOME_UNKNOWN','reconcile')])
        self.assertEqual(ready['recovery']['status'],'OK')
        self.assertEqual(ready['recovery']['actionable'],1,'it reports the action, it does not take it')
        self.assertNotIn(str(self.run),line)
        self.assertEqual(self.decision(aid)['state'],'OUTCOME_UNKNOWN','boot announces but never decides')

    def stop_server(self,child):
        if child.poll() is None:child.terminate()
        child.wait(timeout=20)
        for stream in (child.stdin,child.stdout,child.stderr):
            stream.close()

    def test_no_native_history_and_no_state_file_are_both_reported_as_nothing_pending(self):
        readback=self.service.recovery_readback()
        self.assertEqual((readback['status'],readback['pending'],readback['actionable'],
                          readback['truncated']),('OK',0,0,False))
        self.service.database.unlink()
        self.assertFalse(self.service.database.exists())
        self.assertEqual(self.service.recovery_readback()['pending'],0)
        self.assertEqual(self.service.native_recovery_decisions(),[])


if __name__ == '__main__':
    unittest.main()
