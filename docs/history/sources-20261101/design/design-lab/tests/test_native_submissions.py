# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch
import test_native_plan as fixtures


class NativeSubmissionTests(unittest.TestCase):
    setUp = fixtures.NativePlanTests.setUp
    def test_submit_is_durable_idempotent_and_rejects_changed_plan(self):
        from design_lab.native_submissions import NativeSubmissions
        from design_lab.image_assets import ImageAssetError
        submissions=NativeSubmissions(self.service)
        first=submissions.submit(self.project,'photoshop',self.rir,{},'same-key')
        second=NativeSubmissions(self.service).submit(self.project,'photoshop',self.rir,{},'same-key')
        self.assertEqual(first['task']['attempt']['state'],'PENDING')
        self.assertEqual(first['task']['attempt']['attempt_id'],second['task']['attempt']['attempt_id'])
        self.rir['canvas']['width']=9
        with self.assertRaises(ImageAssetError) as caught:
            submissions.submit(self.project,'photoshop',self.rir,{},'same-key')
        self.assertEqual(caught.exception.status,409)
        self.assertFalse(list(self.root.rglob('master.psd')))

    def test_retry_after_lost_enqueue_response_reuses_persisted_attempt(self):
        from design_lab.native_submissions import NativeSubmissions
        from design_lab.native_tasks import NativeTasks
        from design_lab.task_queries import TaskQueries
        original=NativeTasks.enqueue
        def interrupted(native,*args,**kwargs):
            original(native,*args,**kwargs)
            raise RuntimeError('controlled lost response')
        with patch.object(NativeTasks,'enqueue',interrupted):
            with self.assertRaisesRegex(RuntimeError,'controlled lost response'):
                NativeSubmissions(self.service).submit(self.project,'photoshop',self.rir,{},'interrupted')
        before=TaskQueries(self.service).list(self.project)['tasks']
        self.assertEqual(len(before),2)  # one image import and one native task
        native=[task for task in before if task['kind']=='photoshop-native'][0]
        result=NativeSubmissions(self.service).submit(self.project,'photoshop',self.rir,{},'interrupted')
        self.assertEqual(result['task']['attempt']['attempt_id'],native['attempt']['attempt_id'])
        self.assertEqual(len(TaskQueries(self.service).list(self.project)['tasks']),2)
        self.assertFalse(list(self.root.rglob('master.psd')))


if __name__ == '__main__':
    unittest.main()
