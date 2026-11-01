# SPDX-License-Identifier: MIT
"""Quiescence frees the host, never declares unknown outputs accepted."""
from contextlib import closing
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.service import ProjectService
from design_lab.native_tasks import NativeTasks,NativeTaskError
from design_lab.adapters.illustrator_com import IllustratorDispatchError
from design_lab.runtime import job_store as jobs


class QuiescenceTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.project-local/task-runtime/quiescence-tests';parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);(self.root/'AGENTS.md').write_text('# fixture')
        env=patch.dict(os.environ,{'PROJECT_LOCAL_ROOT':str(self.root/'.project-local')});env.start();self.addCleanup(env.stop)
        self.service=ProjectService(self.root);self.project=self.service.create_project('test')['id']
        self.run=self.service.paths.runtime_root/'qualification';self.run.mkdir(parents=True)
        self.job=dict(jobId='test',runRoot=str(self.run),assets=[],targets={k:str(self.run/('master.'+k)) for k in ('ai','png','svg')})
        self.auth=dict(actor='user',scope='project-native-test',receipt='controlled synthetic test')
        self.tasks=NativeTasks(self.service)
        with patch('design_lab.native_tasks._dispatch',side_effect=IllustratorDispatchError('failed',outcome_unknown=True)):
            with self.assertRaises(NativeTaskError) as caught:
                self.tasks.execute(self.project,'illustrator',self.job,idempotency_key='one',approved_root=self.run,authorization=self.auth)
        self.aid=caught.exception.attempt['attempt_id']

    def test_verified_quiescence_pauses_without_accepting_or_publishing(self):
        self.assertTrue(hasattr(self.tasks,'quiesce_illustrator'),'guard reconciliation missing')
        with patch('design_lab.adapters.illustrator_com.quiesce',return_value=dict(
                status='HOST_QUIESCENT_ARTIFACTS_UNACCEPTED',job_id='test',closed_documents=1,
                documents_before=1,documents_after=0,artifacts={})):
            result=self.tasks.quiesce_illustrator(self.aid,authorization=self.auth)
        self.assertEqual(result['attempt']['state'],'RECONCILING')
        with closing(self.tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM artifact').fetchone()[0],0)
            _,op=jobs._current(conn,self.aid)
            self.assertEqual(jobs.operation_status(conn,op)['state'],'PAUSED_NEEDS_USER')

    def test_failed_quiescence_keeps_guard_and_prevents_second_dispatch(self):
        self.assertTrue(hasattr(self.tasks,'quiesce_illustrator'),'guard reconciliation missing')
        with patch('design_lab.adapters.illustrator_com.quiesce',side_effect=RuntimeError('host uncertain')):
            with self.assertRaises(NativeTaskError):self.tasks.quiesce_illustrator(self.aid,authorization=self.auth)
        with closing(self.tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)
        with patch('design_lab.adapters.illustrator_com.quiesce') as call:
            with self.assertRaises(NativeTaskError):self.tasks.quiesce_illustrator(self.aid,authorization=self.auth)
            call.assert_not_called()

    def test_negative_document_counts_do_not_release_guard(self):
        with patch('design_lab.adapters.illustrator_com.quiesce',return_value=dict(
                status='HOST_QUIESCENT_ARTIFACTS_UNACCEPTED',job_id='test',closed_documents=0,
                documents_before=-1,documents_after=-1,artifacts={})):
            with self.assertRaises(NativeTaskError):self.tasks.quiesce_illustrator(self.aid,authorization=self.auth)
        with closing(self.tasks._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],1)


if __name__=='__main__':unittest.main()
