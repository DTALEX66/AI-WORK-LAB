# SPDX-License-Identifier: MIT
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_native_plan as fixtures


class NativePatchSubmissionTests(unittest.TestCase):
    def setUp(self):
        fixtures.NativePlanTests.setUp(self)
        from design_lab.native_tasks import NativeTasks
        self.job=dict(schemaVersion='design-lab/adobe-host-job/v1',jobId='base',rirHash='a'*64,
            runRoot=str(self.run),artboard=dict(width=8,height=6),assets=[],
            targets={kind:str(self.run/('master.'+kind)) for kind in ('ai','png','svg')},
            operations=[],authorization=dict(required=True,scope='single-session'),
            layers=[dict(id='layer',items=[dict(kind='text',id='title',text='Before')])])
        def dispatch(host,job,**kwargs):
            outputs={kind:Path(value) for kind,value in job['targets'].items()}
            for kind,path in outputs.items():path.write_bytes(b'%PDF- fixture' if kind=='ai' else b'controlled '+kind.encode())
            return dict(status='NATIVE_READBACK',job_id=job['jobId'],host_version='29.5.1',
                job_sha256=hashlib.sha256(json.dumps(job,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest(),
                inputs={},artifacts={kind:dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),byte_size=p.stat().st_size) for kind,p in outputs.items()},
                documents_before=0,documents_after=0)
        with patch('design_lab.native_tasks._dispatch',side_effect=dispatch):
            self.base=NativeTasks(self.service).execute(self.project,'illustrator',self.job,idempotency_key='base',approved_root=self.run,
                authorization=dict(actor='test',scope='project-native-test',receipt='controlled test'))
        self.change=dict(kind='text',id='title',text='After')

    def submit(self,project=None,change=None):
        self.assertIsNotNone(importlib.util.find_spec('design_lab.native_patch_submissions'),'patch intake missing')
        from design_lab.native_patch_submissions import NativePatchSubmissions
        return NativePatchSubmissions(self.service).submit(project or self.project,self.base['attempt']['job_id'],
            self.base['attempt']['attempt_id'],change or self.change,'click-once')

    def test_repeat_submission_preserves_parent_and_one_queued_attempt(self):
        first=self.submit();second=self.submit()
        self.assertEqual(first,second)
        self.assertEqual(first['task']['attempt']['state'],'PENDING')
        self.assertEqual(first['parent']['attempt_id'],self.base['attempt']['attempt_id'])
        self.assertEqual(first['parent']['version_id'],self.base['asset']['version_id'])
        self.assertNotIn('path',json.dumps(first))
        from design_lab.native_tasks import NativeTasks
        with closing(NativeTasks(self.service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_execution_v1').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_host_guard_v1').fetchone()[0],0)
        from design_lab.image_assets import ImageAssetError
        with self.assertRaises(ImageAssetError):self.submit(change=dict(kind='text',id='title',text='Different'))

    def test_photoshop_submission_queues_same_host_and_preserves_parent(self):
        from design_lab.native_tasks import NativeTasks
        root=self.run/'photoshop';root.mkdir()
        job=dict(schemaVersion='design-lab/photoshop-native-job/v1',jobId='ps-base',runRoot=str(root),
            width=8,height=6,assets=[],outputName='master.psd',previewName='master.png',
            layers=[dict(id='title',kind='text',text='Before',font='ArialMT',size=2,position=[1,2],color=[0,0,0])])
        def native(host,current,**kwargs):
            outputs={'psd':root/'master.psd','png':root/'master.png'}
            outputs['psd'].write_bytes(b'8BPS\x00\x01'+b'\0'*6+b'\x00\x03'+(6).to_bytes(4,'big')+(8).to_bytes(4,'big')+b'\x00\x08\x00\x03')
            outputs['png'].write_bytes(b'controlled preview')
            return dict(status='NATIVE_READBACK',job_id=current['jobId'],host_version='26.7.0',
                job_sha256=hashlib.sha256(json.dumps(current,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest(),
                inputs={},artifacts={kind:dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),byte_size=p.stat().st_size) for kind,p in outputs.items()},
                documents_before=0,documents_after=0)
        with patch('design_lab.native_tasks._dispatch',side_effect=native):
            self.base=NativeTasks(self.service).execute(self.project,'photoshop',job,idempotency_key='ps-base',approved_root=root,
                authorization=dict(actor='test',scope='project-native-test',receipt='controlled test'))
        result=self.submit();self.assertEqual(self.submit(),result)
        self.assertEqual(result['task']['kind'],'photoshop-native')
        self.assertEqual(result['parent']['version_id'],self.base['asset']['version_id'])
        with closing(NativeTasks(self.service)._connect()) as conn:
            stored=json.loads(conn.execute('SELECT request_json FROM native_execution_v1 WHERE attempt_id=?',
                (result['task']['attempt']['attempt_id'],)).fetchone()[0])
        self.assertEqual(stored['job']['schemaVersion'],'design-lab/photoshop-patch-job/v1')
        self.assertIn(stored['job']['checkpoint'],stored['inputs'])
        from design_lab.image_assets import ImageAssetError
        (root/'master.psd').write_bytes(b'changed')
        with self.assertRaises(ImageAssetError):self.submit()

    def test_cross_project_and_changed_original_are_rejected(self):
        from design_lab.image_assets import ImageAssetError
        other=self.service.create_project('Other')['id']
        with self.assertRaises(ImageAssetError):self.submit(project=other)
        Path(self.job['targets']['ai']).write_bytes(b'changed')
        with self.assertRaises(ImageAssetError):self.submit()

    def test_lost_enqueue_response_retries_same_attempt(self):
        from design_lab.native_tasks import NativeTasks
        original=NativeTasks.enqueue
        def lost(native,*args,**kwargs):
            original(native,*args,**kwargs)
            raise RuntimeError('lost response')
        with patch.object(NativeTasks,'enqueue',side_effect=lost,autospec=True):
            with self.assertRaisesRegex(RuntimeError,'lost response'):self.submit()
        recovered=self.submit()
        self.assertEqual(recovered['task']['attempt']['state'],'PENDING')
        with closing(NativeTasks(self.service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM native_execution_v1').fetchone()[0],2)

    def test_changed_published_asset_and_request_binding_rejected(self):
        from design_lab.image_assets import ImageAssetError
        from design_lab.native_tasks import NativeTasks
        path=Path(self.base['asset']['path']);before=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaises(ImageAssetError):self.submit()
        path.write_bytes(before)
        with closing(NativeTasks(self.service)._connect()) as conn:
            raw=json.loads(conn.execute('SELECT request_json FROM native_execution_v1 WHERE attempt_id=?',(self.base['attempt']['attempt_id'],)).fetchone()[0])
            raw['job']['layers'][0]['items'][0]['text']='forged'
            conn.execute('UPDATE native_execution_v1 SET request_json=? WHERE attempt_id=?',(json.dumps(raw),self.base['attempt']['attempt_id']));conn.commit()
        with self.assertRaises(ImageAssetError):self.submit()

    def test_http_patch_route_scoped_fields_and_idempotency(self):
        from design_lab.http_service import make_server
        import http.client
        import threading
        access='a'*64
        server=make_server(self.service,access)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(body,project=None,auth=True):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
            headers={'Content-Type':'application/json'}
            if auth:headers['Authorization']='Bearer '+access
            try:
                conn.request('POST',f"/api/projects/{project or self.project}/tasks/{self.base['attempt']['job_id']}/patch",json.dumps(body),headers)
                reply=conn.getresponse();return reply.status,json.loads(reply.read())
            finally:conn.close()
        try:
            body=dict(source_attempt_id=self.base['attempt']['attempt_id'],patch=self.change,idempotency_key='http-key')
            status,first=request(body);self.assertEqual(status,202,first)
            self.assertEqual(request(body),(202,first))
            self.assertEqual(request(dict(body,checkpoint='C:/private.ai'))[0],400)
            self.assertEqual(request(body,auth=False)[0],401)
            other=self.service.create_project('Other')['id']
            self.assertEqual(request(body,other)[0],404)
        finally:server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':unittest.main()
