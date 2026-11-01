# SPDX-License-Identifier: MIT
"""Real CLI processes, loopback requests and persistent project metadata."""
import http.client
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import quote, urlsplit, parse_qsl
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


class ServiceHttpTests(unittest.TestCase):
    def test_native_plan_submission_returns_one_persisted_pending_task(self):
        self.start()
        project=self.request('POST','/api/projects',json.dumps({'name':'Native plan'}))[1]['project']['id']
        route=f'/api/projects/{project}/native-plans'
        value=dict(host='photoshop',rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',
            canvas=dict(width=8,height=6,colorSpace='srgb',background=dict(color='#ffffff',recorded=True)),layers=[]),text_styles={},idempotency_key='plan')
        body=json.dumps(value)
        self.assertEqual(self.request('POST',route,body,{'Authorization':''})[0],401)
        first=self.request('POST',route,body)
        self.assertEqual(first[0],202)
        self.assertEqual(first[1]['task']['attempt']['state'],'PENDING')
        self.assertEqual(self.request('POST',route,body),first)
        value['rir']['canvas']['width']=9
        self.assertEqual(self.request('POST',route,json.dumps(value))[0],409)
        self.assertFalse(list(self.root.rglob('master.psd')))

    def test_default_composed_plan_enqueues_for_both_hosts(self):
        """Batch 22 / D02 + D01 + D04, over the real route.

        The workbench's default plan is a single raster layer. For Illustrator it
        carried ``locked: true``, and the lowering contract refuses a locked node
        unless the caller declares an explicit fallback -- so that host's default plan
        was answered 400 before a job had ever existed, while Photoshop passed only
        because the UI happened to send ``false``. Both hosts must now enqueue; the
        202 must carry the task under ``task`` (the nesting the page reads, not the
        top-level fields it used to read); an identical second POST must replay the
        one attempt; and a locked layer must still be refused, because the fix moves
        the page and not the contract.
        """
        self.start()
        project = self.request('POST', body=json.dumps({'name': 'Default plan'}))[1]['project']['id']
        buffer = io.BytesIO()
        Image.new('RGB', (8, 6), (20, 30, 40)).save(buffer, format='PNG')
        raw = buffer.getvalue()
        # D03: the key is the bytes' own digest, which is what the page now sends.
        status, body = self.request('POST', f'/api/projects/{project}/assets', json.dumps(
            {'content_base64': base64.b64encode(raw).decode(),
             'idempotency_key': hashlib.sha256(raw).hexdigest()}))
        self.assertEqual(status, 201)
        asset = body['asset']['id']
        route = f'/api/projects/{project}/native-plans'
        for host in ('photoshop', 'illustrator'):
            with self.subTest(host=host):
                plan = dict(host=host, text_styles={},
                    idempotency_key=hashlib.sha256((host + asset).encode()).hexdigest(),
                    rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',
                        canvas=dict(width=8, height=6, colorSpace='srgb',
                            background=dict(color='#ffffff', recorded=True)),
                        layers=[dict(id='reference-raster', name='raster', type='raster',
                            opacity=1, bounds=dict(x=0, y=0, width=8, height=6),
                            inferred=False, zOrder=0, visible=True, locked=False,
                            blendMode='normal',
                            raster=dict(path=asset, crop=dict(x=0, y=0, width=8, height=6),
                                alpha=1, sourceMappings=[]))]))
                first = self.request('POST', route, json.dumps(plan))
                self.assertEqual(first[0], 202, first[1])
                job = first[1]['task']['job_id']
                self.assertRegex(job, r'^native-job-[0-9a-f]{64}$')
                self.assertEqual(first[1]['task']['attempt']['state'], 'PENDING')
                listed = self.request('GET', f'/api/projects/{project}/tasks')[1]['tasks']
                self.assertIn(job, [task['job_id'] for task in listed])
                self.assertEqual(self.request('POST', route, json.dumps(plan)), first,
                    'the same intent must replay the one attempt, not queue a second job')
                locked = json.loads(json.dumps(plan))
                locked['rir']['layers'][0]['locked'] = True
                locked['idempotency_key'] = hashlib.sha256(
                    (host + asset + 'locked').encode()).hexdigest()
                refused = self.request('POST', route, json.dumps(locked))
                self.assertEqual(refused[0], 400,
                    'a locked layer is still refused: the contract was not widened')

    def test_native_cancel_request_persists_without_releasing_running_host_guard(self):
        from contextlib import closing
        project,other,_=self.seed_exportable_native()
        from design_lab.service import ProjectService
        from design_lab.native_tasks import NativeTasks
        from design_lab.runtime import job_store as jobs
        service=ProjectService(self.root)
        job='native-job-'+'d'*64
        with closing(NativeTasks(service)._connect()) as conn:
            attempt=jobs.begin_attempt(conn,job,operation_id='native-op-'+'d'*64,
                idempotency_scope='native:'+project+':photoshop',idempotency_key='cancel-fixture',request_hash='d'*64)
            aid=attempt['attempt_id']
            jobs.transition(conn,aid,'RUNNING')
            conn.execute('INSERT INTO native_host_guard_v1 VALUES (?,?,?)',('photoshop',aid,jobs._now()))
            conn.commit()
        self.start()
        route=f'/api/projects/{project}/tasks/{job}/cancel'
        body=json.dumps({'attempt_id':aid})
        for _ in range(2):
            code,data=self.request('POST',route,body)
            self.assertEqual(code,202)
            self.assertEqual(data['task']['attempt']['state'],'CANCEL_REQUESTED')
        with closing(NativeTasks(service)._connect()) as conn:
            self.assertEqual(conn.execute('SELECT attempt_id FROM native_host_guard_v1 WHERE host=?',('photoshop',)).fetchone(),(aid,))
            self.assertEqual(conn.execute('SELECT cancel_acked FROM attempt_resolution WHERE attempt_id=?',(aid,)).fetchone(),(0,))

    def test_native_cancel_is_scoped_and_terminal_tasks_are_not_rewritten(self):
        project,other,job=self.seed_exportable_native();self.start()
        task=self.request(path=f'/api/projects/{project}/tasks/{job}')[1]['task']
        body=json.dumps({'attempt_id':task['attempt']['attempt_id']})
        route=f'/api/projects/{project}/tasks/{job}/cancel'
        self.assertEqual(self.request('POST',route,body,{'Authorization':''})[0],401)
        self.assertEqual(self.request('POST',route.replace(project,other),body)[0],404)
        self.assertEqual(self.request('POST',route,'{}')[0],400)
        self.assertEqual(self.request('POST',route,json.dumps({'attempt_id':'att-'+'0'*32}))[0],409)
        self.assertEqual(self.request('POST',route,body)[0],409)
        current=self.request(path=f'/api/projects/{project}/tasks/{job}')[1]['task']
        self.assertEqual(current['attempt']['state'],'RECEIPTED')

    def test_native_worker_route_rejects_cross_project_and_terminal_attempt(self):
        project,other,job=self.seed_exportable_native();self.start()
        task=self.request(path=f'/api/projects/{project}/tasks/{job}')[1]['task']
        body=json.dumps({'attempt_id':task['attempt']['attempt_id']})
        route=f'/api/projects/{project}/tasks/{job}/run'
        self.assertEqual(self.request('POST',route,body,{'Authorization':''})[0],401)
        self.assertEqual(self.request('POST',route.replace(project,other),body)[0],404)
        self.assertEqual(self.request('POST',route,body)[0],409)
        self.assertEqual(self.request('POST',route,'{}')[0],400)

    def seed_exportable_native(self):
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT/'src'));self.addCleanup(lambda:sys.path.remove(str(ROOT/'src')))
        from design_lab.service import ProjectService
        from design_lab.native_tasks import NativeTasks
        with patch.dict(os.environ):
            os.environ.pop('PROJECT_LOCAL_ROOT',None)
            service=ProjectService(self.root);project=service.create_project('Export fixture')['id']
            other=service.create_project('Other')['id']
            run=service.paths.category_dir('runtime','export-fixture');run.mkdir(parents=True)
            job=dict(schemaVersion='design-lab/photoshop-native-job/v1',jobId='export-fixture',runRoot=str(run),
                     width=8,height=6,assets=[],outputName='native.psd',previewName='preview.png',
                     layers=[dict(id='background',kind='fill',bounds=[0,0,8,6],color=[0,0,0])])
            def native(host,job,**kwargs):
                output={}
                for kind,name in [('psd','native.psd'),('png','preview.png')]:
                    data=('controlled '+kind).encode();(run/name).write_bytes(data)
                    output[kind]=dict(sha256=hashlib.sha256(data).hexdigest(),byte_size=len(data))
                raw=json.dumps(job,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()
                return dict(status='NATIVE_READBACK',job_id=job['jobId'],job_sha256=hashlib.sha256(raw).hexdigest(),
                            host_version='fixture',bridge_sha256='b'*64,inputs={},artifacts=output,documents_before=0,documents_after=0)
            with patch('design_lab.native_tasks._dispatch',side_effect=native):
                result=NativeTasks(service).execute(project,'photoshop',job,idempotency_key='export',approved_root=run,
                    authorization=dict(actor='fixture',scope='project-native-test',receipt='controlled boundary'))
        return project,other,result['attempt']['job_id']

    def test_native_bundle_http_export_and_download_are_owner_scoped(self):
        import zipfile
        project,other,job=self.seed_exportable_native();self.start()
        route='/api/projects/'+project+'/tasks/'+job+'/bundle'
        self.assertEqual(self.request('POST',route,'{}',{'Authorization':''})[0],401)
        self.assertEqual(self.request('POST','/api/projects/'+other+'/tasks/'+job+'/bundle','{}')[0],404)
        self.assertEqual(self.request('POST',route,'{"path":"C:/private"}')[0],400)
        status,data=self.request('POST',route,'{}');self.assertEqual(status,201)
        self.assertNotIn('path',data['bundle'])
        download=data['download_path']
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        try:
            conn.request('GET',download,headers={'Authorization':'Bearer '+self.token})
            response=conn.getresponse();raw=response.read()
            self.assertEqual(response.status,200)
            self.assertEqual(response.getheader('Content-Type'),'application/zip')
            self.assertEqual(hashlib.sha256(raw).hexdigest(),data['bundle']['sha256'])
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                self.assertEqual(archive.read('native.psd'),b'controlled psd')
        finally:conn.close()
        self.assertEqual(self.request(path=download.replace(project,other))[0],404)
        self.assertEqual(self.request(path=download,headers={'Authorization':''})[0],401)
        self.assertEqual(self.request('POST',route,'{}',{'Origin':'https://untrusted.example'})[0],403)
        archives=list(self.root.rglob('delivery.zip'))
        self.assertEqual(len(archives),1)
        archives[0].write_bytes(b'tampered archive')
        self.assertEqual(self.request(path=download)[0],409)

    def test_bundle_list_route_reads_back_project_deliveries(self):
        # The /projects/<id>/bundles route is what makes the Bundles query class
        # reachable from the service and the workbench UI (before it had tests
        # only). Drive a real export first, then read the list back over HTTP.
        project,other,job=self.seed_exportable_native();self.start()
        status,created=self.request('POST','/api/projects/'+project+'/tasks/'+job+'/bundle','{}')
        self.assertEqual(status,201)
        expected_id=created['bundle']['id']
        status,listing=self.request(path='/api/projects/'+project+'/bundles')
        self.assertEqual(status,200)
        self.assertEqual(len(listing['bundles']),1)
        row=listing['bundles'][0]
        self.assertEqual(row['id'],expected_id)
        self.assertEqual(row['kind'],'design-bundle')   # API label, not the stored column value
        self.assertEqual(row['version_id'],created['bundle']['version_id'])
        self.assertEqual(row['byte_size'],created['bundle']['byte_size'])
        # The list carries the prefixed digest while the export reports bare hex --
        # the shape the UI's download hash-check (bundle.sha256) normalizes on.
        self.assertEqual(row['sha256'],'sha256:'+created['bundle']['sha256'])
        self.assertEqual(row['rights'],'NOT_REVIEWED')
        self.assertEqual(row['verification'],'METADATA_ONLY')
        # Cross-project: the same list on the other project must NOT see it.
        status,foreign=self.request(path='/api/projects/'+other+'/bundles')
        self.assertEqual(status,200)
        self.assertEqual(foreign['bundles'],[])

    def test_preflight_route_measures_a_registered_bundle_over_http(self):
        # `POST .../bundles/<id>/preflight` is the only production entry to the preflight
        # checker and the workbench calls it, but until now every preflight test called
        # `pp.preflight_bundle(...)` in-process -- so the route's own defaults, its profile
        # grammar and the shape the page actually receives were unexercised. A verdict that
        # only ever exists in-process is not something the service can be said to emit.
        project,other,job=self.seed_exportable_native();self.start()
        status,created=self.request('POST','/api/projects/'+project+'/tasks/'+job+'/bundle','{}')
        self.assertEqual(status,201)
        bundle=created['bundle']['id']
        route=f'/api/projects/{project}/bundles/{bundle}/preflight'
        status,report=self.request('POST',route,'{}')
        self.assertEqual(status,200)
        # The profile is optional on the route, so this is where the default is pinned.
        self.assertEqual(report['profile'],'digital')
        # The vocabulary is the module's own, not a list copied here: it has four members and
        # `INCOMPLETE` is one of them. This fixture ships a PSD whose transparency flattening
        # this build cannot inspect, so the honest answer is INCOMPLETE -- a PASS arriving over
        # this route would mean the service certified bytes it never opened.
        from design_lab.assurance import production_preflight as pp
        self.assertIn(report['verdict'],pp.VERDICTS)
        unmeasured=[item for item in report['findings'] if item['outcome']=='NOT_MEASURED']
        self.assertTrue(unmeasured,'the fixture was expected to leave something unmeasured')
        self.assertEqual(report['verdict'],'INCOMPLETE')
        # The aggregate must account for every finding it ships, over HTTP as well as in
        # process: a dropped row here would silently upgrade the verdict.
        self.assertEqual(sum(report['counts'].values()),len(report['findings']))
        self.assertTrue(all(item['criterion'] for item in report['findings']),
                        'a finding without its criterion cannot be reviewed by a person')
        # An unregistered bundle is named, not guessed at, and a foreign project cannot
        # reach another project's delivery through this route.
        self.assertEqual(self.request('POST',
            f'/api/projects/{project}/bundles/bundle-{"0"*64}/preflight','{}')[0],404)
        # A foreign project cannot reach another project's delivery through this route. It
        # answers 400 here while the sibling export route answers 404 for the same
        # "not yours / not registered" condition -- the divergence is real and recorded rather
        # than quietly harmonised, because the status code is part of what the workbench
        # branches on and changing it is a contract decision, not a test decision.
        foreign=self.request('POST',f'/api/projects/{other}/bundles/{bundle}/preflight','{}')
        self.assertEqual(foreign[0],400)
        self.assertNotIn('verdict',foreign[1])
        # The profile grammar lives in the route pattern, so an undeclared profile must not
        # reach the checker with the default quietly substituted.
        self.assertEqual(self.request('POST',route+'?profile=bronze','{}')[0],404)

    def receipt_route(self, project, bundle_id, version_id):
        return (f'/api/projects/{project}/bundles/{bundle_id}/versions/{version_id}/receipt')

    def test_delivery_receipt_route_reads_back_the_persisted_document(self):
        """GET .../versions/<v>/receipt -- the CLI's `delivery-receipt` read over HTTP.

        The route answers through NativeDelivery.receipt(), which re-verifies the stored
        document against its own derived digest before anything is sent, so the page gets
        the bytes the delivery wrote or a refusal, never a re-derived approximation. The
        two refusals are the point of this test: a version that was never receipted is a
        different fact (404 DELIVERY_RECEIPT_NOT_FOUND) from a stored receipt whose own
        bytes contradict it (409 DELIVERY_RECEIPT_UNVERIFIED), and collapsing either into
        INVALID_REQUEST would tell the operator to go fix a request that was fine.
        """
        from contextlib import closing
        import sqlite3
        from design_lab.service import ProjectService
        project, other, job = self.seed_exportable_native(); self.start()
        status, created = self.request('POST', '/api/projects/'+project+'/tasks/'+job+'/bundle', '{}')
        self.assertEqual(status, 201, created)
        bundle_id, version_id = created['bundle']['id'], created['bundle']['version_id']
        route = self.receipt_route(project, bundle_id, version_id)

        status, envelope = self.request(path=route)
        self.assertEqual(status, 200, envelope)
        # 2026-10-08: the route answers with the read-back envelope now, and `receipt` inside it
        # must be the stored document with nothing added, removed or re-derived -- the document
        # signs its own bytes with receipt_sha256, so an edited copy would leave the client
        # holding a digest of something it does not have. Every assertion below is on that
        # document, unchanged from before the envelope existed.
        self.assertEqual(envelope['schemaVersion'], 'design-lab/delivery-receipt-readback/v1')
        receipt = envelope['receipt']
        self.assertEqual(receipt, created['bundle']['receipt'])
        self.assertEqual(receipt['schemaVersion'], 'design-lab/delivery-receipt/v2')
        self.assertEqual(receipt['job_id'], job)
        # The new half: each deliverable's rollback reference is looked up, and the answer says
        # what was found instead of repeating the promise back.
        proofs = envelope['rollback_proofs']
        self.assertEqual([proof['deliverable_id'] for proof in proofs],
                         ['native.psd', 'preview.png'])
        self.assertEqual(envelope['rollback_state'], 'ALL_RESOLVED')
        for proof, entry in zip(proofs, receipt['deliverables']):
            self.assertEqual(proof['backup_ref'], entry['rollback']['backup_ref'])
            self.assertEqual(proof['state'], 'RESOLVED')
            self.assertEqual(proof['source_state'], 'ACTIVE')
            self.assertIsInstance(proof['version_no'], int)
            self.assertIn(proof['state'], envelope['rollback_states'])
            self.assertIn(envelope['rollback_state'], envelope['rollback_state_vocabulary'])
        self.assertTrue(envelope['does_not_prove'],
                        'a read-back that reports a resolved restore point without saying that '
                        'no restore was performed is the exact overclaim this envelope avoids')
        # No host opens a delivered artifact in this product, so a real delivery is
        # PARTIAL by construction; a route that reported PASS would be the lie.
        self.assertEqual(receipt['axes'], {'delivery': 'PARTIAL'})
        self.assertEqual([entry['deliverable_id'] for entry in receipt['deliverables']],
                         ['native.psd', 'preview.png'])
        for entry in receipt['deliverables']:
            self.assertIsNone(entry['host_readback'])
            self.assertIsNone(entry['readback_matches_artifact'])
        # A receipt describes bytes; it is not a directory listing. No key of the
        # document or of a deliverable carries a path, and the project root does not
        # appear anywhere in the payload.
        self.assertNotIn('path', set(receipt))
        for entry in receipt['deliverables']:
            self.assertNotIn('path', set(entry))
        self.assertNotIn(str(self.root), json.dumps(receipt))

        # (a) a version with no receipt recorded: 404, and the code says WHICH 404.
        missing = self.receipt_route(project, bundle_id, 'v-' + '0' * 32)
        status, body = self.request(path=missing)
        self.assertEqual(status, 404)
        self.assertEqual(body['error'], 'DELIVERY_RECEIPT_NOT_FOUND')

        # (b) the same route refusing to certify bytes: after the stored document is
        # edited, the hash it carries no longer matches the body it derives from.
        service = ProjectService(self.root)
        database = service.paths.database_path(service.database)
        with closing(sqlite3.connect(database)) as conn:
            stored = conn.execute('SELECT receipt_json FROM delivery_receipt_v1 WHERE version_id=?',
                                  (version_id,)).fetchone()[0]
            tampered = json.loads(stored)
            tampered['deliverables'][0]['byte_size'] += 1
            conn.execute('UPDATE delivery_receipt_v1 SET receipt_json=? WHERE version_id=?',
                         (json.dumps(tampered, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')), version_id))
            conn.commit()
        status, refused = self.request(path=route)
        self.assertEqual(status, 409)
        self.assertEqual(refused['error'], 'DELIVERY_RECEIPT_UNVERIFIED')
        self.assertNotEqual(body['error'], refused['error'],
                            '"no receipt was ever recorded" and "we refuse to certify these '
                            'bytes" must stay two different answers')
        # The refusal is about the document, not the request: the same read that now
        # answers 409 is the read that answered 200 before the bytes moved.

    def test_delivery_receipt_route_keeps_the_project_boundary_and_the_id_shape(self):
        """Ownership first, then shape: nothing here narrows to a guessable id."""
        project, other, job = self.seed_exportable_native(); self.start()
        _, created = self.request('POST', '/api/projects/'+project+'/tasks/'+job+'/bundle', '{}')
        bundle_id, version_id = created['bundle']['id'], created['bundle']['version_id']
        route = self.receipt_route(project, bundle_id, version_id)
        self.assertEqual(self.request(path=route)[0], 200)
        # A foreign project holding the same ids reads nothing -- and it is refused with
        # the receipt's own code, because the asset ledger, not the row's self-declared
        # project_id, decides whose document this is.
        status, body = self.request(path=self.receipt_route(other, bundle_id, version_id))
        self.assertEqual(status, 404)
        self.assertEqual(body['error'], 'DELIVERY_RECEIPT_NOT_FOUND')
        # Unknown-but-well-shaped project: the project check, not the receipt check.
        status, body = self.request(path=self.receipt_route('f' * 32, bundle_id, version_id))
        self.assertEqual(status, 404)
        self.assertEqual(body['error'], 'PROJECT_NOT_FOUND')
        self.assertEqual(self.request(path=route, headers={'Authorization': ''})[0], 401)
        # Malformed ids never reach NativeDelivery (the pattern is a fullmatch on the
        # whole path, as narrow as the /content route beside it).
        for shape in (route.replace(version_id, 'V-' + '0' * 32),
                      route.replace(bundle_id, 'bundle-native-' + '0' * 63),
                      route.replace('/receipt', ''), route + '/extra',
                      route.replace(f'/bundles/{bundle_id}', f'/bundles/{bundle_id}/versions')):
            self.assertEqual(self.request(path=shape)[0], 404, shape)

    def test_bundle_list_route_fails_closed_on_unknown_project_and_auth(self):
        project,other,job=self.seed_exportable_native();self.start()
        # Unknown-but-well-shaped project id: the query class fails closed with the
        # same 404 PROJECT_NOT_FOUND its owner-scoped reads use.
        status,body=self.request(path='/api/projects/'+('f'*32)+'/bundles')
        self.assertEqual(status,404)
        self.assertEqual(body['error'],'PROJECT_NOT_FOUND')
        # Unauthenticated read of a real project list: 401 via guard().
        status,body=self.request(path='/api/projects/'+project+'/bundles',headers={'Authorization':''})
        self.assertEqual(status,401)
        # Malformed id shapes never reach the Bundles class (route regex is
        # fullmatch-strict): they fall through to the generic 404.
        for shape in ('/api/projects/bundles','/api/projects/'+project+'/bundles/extra',
                      '/api/projects/'+project.upper()+'/bundles'):
            self.assertEqual(self.request(path=shape)[0],404)
        # An empty project has NO bundles -- that is a 200 empty list, never 404.
        status,created=self.request('POST','/api/projects',json.dumps({'name':'no deliveries'}))
        self.assertEqual(status,201)
        empty=created['project']['id']
        status,body=self.request(path='/api/projects/'+empty+'/bundles')
        self.assertEqual(status,200)
        self.assertEqual(body['bundles'],[])

    def seed_native(self):
        from contextlib import closing
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT/'src'));self.addCleanup(lambda:sys.path.remove(str(ROOT/'src')))
        from design_lab.service import ProjectService
        from design_lab.runtime import job_store as jobs,asset_store as assets
        with patch.dict(os.environ):
            os.environ.pop('PROJECT_LOCAL_ROOT',None)
            service=ProjectService(self.root);project=service.create_project('Native query fixture')['id']
            other=service.create_project('Other project')['id']
            job='native-job-'+'a'*64;asset='native-'+'b'*64
            data=b'8BPS synthetic query fixture; not native-host evidence'
            path=service.paths.category_dir('projects',project,'assets')/'native.psd';path.parent.mkdir(parents=True);path.write_bytes(data)
            sha=hashlib.sha256(data).hexdigest()
            with closing(assets.connect(service.database,project_root=self.root)) as conn:
                assets.register_asset(conn,project,asset,'psd')
                version=assets.record_version(conn,asset,sha,artifacts=[(str(path),sha,len(data),'deliverable')])
            with closing(jobs.connect(service.database,project_root=self.root)) as conn:
                attempt=jobs.begin_attempt(conn,job,operation_id='native-op-'+'a'*64,idempotency_scope='native:'+project+':photoshop',
                    idempotency_key='PRIVATE_NATIVE_KEY',request_hash='a'*64)
                jobs.transition(conn,attempt['attempt_id'],'RUNNING',note='PRIVATE_NATIVE_NOTE')
                jobs.transition(conn,attempt['attempt_id'],'RECEIPTED',evidence=dict(operation_id='native-op-'+'a'*64,
                    attempt_id=attempt['attempt_id'],artifact_sha256=sha,readback_sha256=sha,private='PRIVATE_NATIVE_RECEIPT'))
        return project,other,job,asset,version,path,sha

    def test_native_tasks_and_asset_readback_are_scoped_and_survive_restart(self):
        project,other,job,asset,version,path,sha=self.seed_native();self.start()
        prefix='/api/projects/'+project
        status,data=self.request(path=prefix+'/tasks');self.assertEqual(status,200)
        self.assertEqual(len(data['tasks']),1,'native task absent from project query')
        self.assertEqual(data['tasks'][0]['kind'],'photoshop-native')
        self.assertEqual(data['tasks'][0]['state'],'SUCCEEDED')
        self.assertEqual(self.request(path=prefix+'/tasks/'+job)[0],200)
        events=self.request(path=prefix+'/tasks/'+job+'/events')[1]['events']
        self.assertEqual([e['to_state'] for e in events],['PENDING','RUNNING','RECEIPTED'])
        status,listing=self.request(path=prefix+'/native-assets');self.assertEqual(status,200)
        record=listing['assets'][0];self.assertEqual(record['id'],asset);self.assertEqual(record['version_id'],version)
        self.assertEqual(record['verification'],'METADATA_ONLY');self.assertNotIn('path',record)
        self.stop();self.start()
        status,checked=self.request(path=prefix+'/native-assets/'+asset+'/verify');self.assertEqual(status,200)
        self.assertEqual(checked['asset']['verification'],'HASH_VERIFIED');self.assertEqual(checked['asset']['sha256'],'sha256:'+sha)
        public=json.dumps([data,listing,checked,events]);self.assertNotIn('PRIVATE_NATIVE',public)
        for suffix in ('/tasks/'+job,'/tasks/'+job+'/events','/native-assets/'+asset+'/verify'):
            self.assertEqual(self.request(path='/api/projects/'+other+suffix)[0],404)
        self.assertEqual(self.request(path=prefix+'/native-assets?after='+asset)[1]['assets'],[])
        self.assertEqual(self.request(path=prefix+'/tasks?after='+job)[1]['tasks'],[])

    def test_native_file_tamper_and_unauthorized_readback_fail_closed(self):
        project,other,job,asset,version,path,sha=self.seed_native();self.start()
        route='/api/projects/'+project+'/native-assets/'+asset+'/verify'
        self.assertEqual(self.request(path=route,headers={'Authorization':''})[0],401)
        path.write_bytes(b'tampered')
        self.assertEqual(self.request(path=route)[0],409)
        self.assertEqual(self.request('POST',path=route,body='{}')[0],404)
        self.assertEqual(self.request(path='/api/projects/'+project+'/native-assets?after=../escape')[0],404)

    def test_task_preflight_http_parses_query_and_maps_errors(self):
        # FA-11 (DL-TP-20260918-UCR-014): real HTTP, not a helper unit test.
        # A fresh root has no task-resources.json -> preflight falls back to the
        # standalone paths.json and reports READY with no declared resources, so a
        # well-formed <TASKPACK>::<TASK_KEY> is deterministic.
        self.start()
        base = '/api/task-preflight'

        # 1) valid task, single param -> 200 READY.
        status, ok = self.request(path=base + '?task=' + quote('TP::T-001'))
        self.assertEqual(status, 200)
        self.assertEqual(ok['task_full_id'], 'TP::T-001')
        self.assertEqual(ok['verdict'], 'READY')
        self.assertEqual(ok['registry_state'], 'NOT_AVAILABLE')

        # 2) the `task` param must be recognised even among other params / after
        #    the correct key (real URL parsing, not string surgery).
        _, other = self.request(path=base + '?x=1&task=' + quote('TP::T-002') + '&y=2')
        self.assertEqual(other['task_full_id'], 'TP::T-002')

        # 3) a literally percent-encoded `::` (TP%3A%3AT-003) must URL-decode back
        #    to the task id.
        _, enc = self.request(path=base + '?task=TP%3A%3AT-003')
        self.assertEqual(enc['task_full_id'], 'TP::T-003')

        # 4) a present query must not 404 (the old bug matched on the raw path
        #    which contained the query string).
        self.assertNotEqual(self.request(path=base + '?task=' + quote('TP::T-001'))[0], 404)

        # 5) missing / empty task -> TASK_REQUIRED, never TASK_PREFLIGHT_REJECTED.
        for path in (base, base + '?', base + '?task=', base + '?x=only'):
            with self.subTest(path=path):
                status, body = self.request(path=path)
                self.assertEqual(status, 400)
                self.assertEqual(body['error'], 'TASK_REQUIRED')

        # 6) malformed task (no `::` separator) -> TASK_PREFLIGHT_REJECTED.
        status, body = self.request(path=base + '?task=' + quote('not-a-valid-task'))
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'TASK_PREFLIGHT_REJECTED')

        # 7) the endpoint is read-only: it never writes project state.
        self.assertFalse((self.root / '.project-local').exists())

    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/service-http-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'AGENTS.md').write_text('# synthetic HTTP test project', encoding='utf-8')
        # The root runner deliberately sets PROJECT_LOCAL_ROOT. Each isolated
        # project owns its own root, including in-process seed/readback calls.
        from unittest.mock import patch
        local_env = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(self.root / '.project-local')})
        local_env.start()
        self.addCleanup(local_env.stop)
        self.token = secrets.token_hex(32)
        self.process = None
        self.addCleanup(self.stop)

    def start(self):
        env = dict(os.environ)
        env.pop('PROJECT_LOCAL_ROOT', None)
        code = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from design_lab.cli import main; sys.exit(main())'
        installed_python = env.pop('DESIGN_LAB_QUALIFICATION_PYTHON', None)
        launcher = ([installed_python, '-I', '-B', '-m', 'design_lab'] if installed_python else
                    [sys.executable, '-B', '-c', code, str(ROOT / 'src')])
        self.process = subprocess.Popen(
            [*launcher, '--project', str(self.root),
             'serve', '--port', '0'], cwd=self.root.parent, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8')
        self.process.stdin.write(self.token + '\n')
        self.process.stdin.flush()
        self.process.stdin.close()
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(self.process.stdout.readline()), daemon=True).start()
        try:
            line = lines.get(timeout=10)
        except queue.Empty:
            self.fail('server did not emit readiness within 10 seconds')
        self.assertTrue(line, 'serve command exited without readiness')
        ready = json.loads(line)
        self.assertEqual(ready['status'], 'LISTENING')
        self.assertEqual(ready['host'], '127.0.0.1')
        self.assertNotIn(self.token, line)
        self.port = ready['port']

    def stop(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
            self.process.wait(timeout=10)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()
            self.process = None

    def raw_get(self, path):
        """The same authenticated request, but the body comes back as the bytes sent.

        `request` json-decodes everything, which is right for the API and wrong for a page:
        an HTML answer is not JSON, and forcing callers to hand-roll HTTPConnection is how
        the page checks below ended up duplicating the transport three times.
        """
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request('GET', path, headers={'Authorization': 'Bearer ' + self.token})
            response = conn.getresponse()
            return response.status, response.read(), response.getheader('Content-Type')
        finally:
            conn.close()

    def request(self, method='GET', path='/api/projects', body=None, headers=None):
        defaults = {'Authorization': 'Bearer ' + self.token}
        if body is not None:
            defaults['Content-Type'] = 'application/json'
        defaults.update(headers or {})
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=defaults)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_http_create_survives_process_restart(self):
        self.start()
        status, body = self.request('POST', body=json.dumps({'name': 'Native editable poster'}))
        self.assertEqual(status, 201)
        record = body['project']
        self.assertEqual(record['name'], 'Native editable poster')
        self.stop()
        self.start()
        status, envelope = self.request()
        self.assertEqual(200, status)
        # The listing is now the roll-up, so a restart test asserts both halves: the record came
        # back, and on a checkout where nothing else was ever opened every unopened surface reads
        # null-and-named rather than 0.
        self.assertEqual('design-lab/project-list/v1', envelope['schemaVersion'])
        self.assertEqual([record], [{key: item[key] for key in ('id', 'name', 'created_at')}
                                     for item in envelope['projects']])
        self.assertEqual(0, envelope['projects'][0]['objects']['assets'])
        self.assertIsNone(envelope['projects'][0]['objects']['promptResults'])
        self.assertIn('promptResults', envelope['projects'][0]['absentSurfaces'])
        self.assertIsNone(envelope['projects'][0]['last_activity_at'])
        self.assertEqual(self.request(path='/api/projects/' + record['id']), (200, {'project': record}))

    def test_health_and_environment_are_read_only(self):
        self.start()
        status, health = self.request(path='/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(health['status'], 'OK')
        self.assertEqual(health['scope'], 'project-metadata')
        self.assertEqual(self.request(path='/api/environment')[0], 200)
        status, listing = self.request()
        self.assertEqual((status, listing['projects']), (200, []))
        self.assertEqual('design-lab/project-list/v1', listing['schemaVersion'])
        self.assertEqual(4, len(listing['does_not_say']),
                         'the empty list still has to say what its nulls mean')
        self.assertFalse((self.root / '.project-local').exists())

    def test_workbench_assets_are_fixed_local_and_do_not_open_api_auth(self):
        self.start()
        for path, mime in (('/workbench', 'text/html'), ('/workbench/main.js', 'text/javascript'),
                           ('/workbench/style.css', 'text/css')):
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
            try:
                conn.request('GET', path)
                response = conn.getresponse()
                payload = response.read()
                self.assertEqual(response.status, 200)
                self.assertTrue(response.getheader('Content-Type').startswith(mime))
                self.assertIn("default-src 'none'", response.getheader('Content-Security-Policy'))
                self.assertGreater(len(payload), 100)
            finally:
                conn.close()
        self.assertEqual(self.request(headers={'Authorization': ''})[0], 401)
        for path in ('/workbench/../../AGENTS.md', '/workbench/main.ts'):
            self.assertEqual(self.request(path=path)[0], 404)
        # This case used to sit in that 404 list as `('/workbench?file=AGENTS.md', 404)`,
        # which pinned the DOT-audit D13 defect as a contract: because the page branch
        # compared `self.path` (which BaseHTTPRequestHandler returns WITH the query) against
        # the route table, any `?palette=ui2026` reload was an unknown path -- 404 for an
        # authenticated client and 401 for a browser navigation, so the theme URL the
        # interface itself writes could not be loaded. The property that has to hold is that
        # a query selects no file, and that is now asserted positively instead of by a 404:
        # the page answers, byte-for-byte the same page, and never the named document.
        plain_status, plain, plain_mime = self.raw_get('/workbench')
        self.assertEqual(plain_status, 200)
        self.assertTrue(plain_mime.startswith('text/html'), plain_mime)
        query_status, payload, payload_mime = self.raw_get('/workbench?file=AGENTS.md')
        self.assertEqual(query_status, 200)
        self.assertTrue(payload_mime.startswith('text/html'), payload_mime)
        self.assertEqual(payload, plain, 'a query string changed which bytes were served')
        self.assertNotIn(b'# AGENTS.md', payload)
        # The reload the interface itself produces must answer, not 401/404.
        for path in ('/workbench?palette=ui2026&scheme=light', '/workbench?dev=1'):
            status, body, _ = self.raw_get(path)
            self.assertEqual(status, 200, path)
            self.assertEqual(body, plain, path)
        self.assertEqual(self.request(path='/workbench', headers={'Host': 'evil.example'})[0], 403)
        self.assertFalse((self.root / '.project-local').exists())

    def test_untrusted_host_origin_and_missing_auth_cannot_write(self):
        self.start()
        for headers in ({'Host': 'evil.example'}, {'Origin': 'https://evil.example'},
                        {'Origin': 'null'}, {'Authorization': ''},
                        {'Authorization': 'Bearer invalid'}, {'Sec-Fetch-Site': 'cross-site'}):
            with self.subTest(headers=list(headers)):
                self.assertIn(self.request('POST', body='{"name":"forbidden"}', headers=headers)[0], (401, 403))
        self.assertFalse((self.root / '.project-local').exists())

    def test_same_origin_json_request_is_accepted(self):
        self.start()
        status, _ = self.request('POST', body='{"name":"allowed"}',
                                 headers={'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 201)

    def test_invalid_payloads_do_not_create_database(self):
        self.start()
        for body in ('{', '[]', '{"name":""}', '{"name":null}', '{"name":"ok","path":"escape"}',
                     '{"name":"one","name":"two"}'):
            with self.subTest(body=body):
                self.assertEqual(self.request('POST', body=body)[0], 400)
        self.assertEqual(self.request('POST', body='{"name":"bad"}',
                                      headers={'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request('POST', body='x' * 17000)[0], 413)
        self.assertFalse((self.root / '.project-local').exists())

    def test_invalid_unicode_name_is_rejected_before_database_creation(self):
        self.start()
        self.assertEqual(self.request('POST', body='{"name":"\\ud800"}')[0], 400)
        self.assertFalse((self.root / '.project-local').exists())

    def test_ambiguous_headers_are_rejected(self):
        self.start()
        for extra, expected in (([('Host', 'evil.example')], 403),
                                ([('Content-Length', '2'), ('Content-Length', '2')], 400),
                                ([('Transfer-Encoding', 'chunked')], 400),
                                ([('Origin', 'null'), ('Origin', f'http://127.0.0.1:{self.port}')], 403)):
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
            try:
                conn.putrequest('POST', '/api/projects')
                conn.putheader('Authorization', 'Bearer ' + self.token)
                conn.putheader('Content-Type', 'application/json')
                for key, value in extra:
                    conn.putheader(key, value)
                conn.endheaders()
                response = conn.getresponse()
                self.assertEqual(response.status, expected)
                response.read()
            finally:
                conn.close()
        self.assertFalse((self.root / '.project-local').exists())

    def test_unknown_routes_and_methods_do_not_write(self):
        self.start()
        for path in ('/api/projects/absent', '/api/projects/../../AGENTS.md', '/api/projects?path=AGENTS.md'):
            self.assertEqual(self.request(path=path)[0], 404)
        self.assertEqual(self.request('DELETE')[0], 405)
        self.assertFalse((self.root / '.project-local').exists())

    def image_body(self, color='red', key='import-one'):
        from PIL import Image
        stream = io.BytesIO()
        Image.new('RGB', (16, 12), color).save(stream, format='PNG')
        data = stream.getvalue()
        return data, json.dumps({'content_base64': base64.b64encode(data).decode('ascii'),
                                 'idempotency_key': key})

    def test_real_image_import_receipt_content_and_restart(self):
        self.start()
        _, project = self.request('POST', body='{"name":"Image project"}')
        endpoint = '/api/projects/' + project['project']['id'] + '/assets'
        data, body = self.image_body()
        status, imported = self.request('POST', endpoint, body)
        self.assertEqual(status, 201)
        asset = imported['asset']
        self.assertEqual(asset['sha256'], 'sha256:' + hashlib.sha256(data).hexdigest())
        self.assertEqual(asset['rights'], 'NOT_REVIEWED')
        self.assertEqual(imported['attempt']['state'], 'RECEIPTED')
        self.assertEqual((asset['width'], asset['height']), (16, 12))
        self.stop()
        self.start()
        self.assertEqual(self.request(path=endpoint), (200, {'assets': [asset]}))
        self.assertEqual(self.request('POST', endpoint, body), (201, imported))
        status, content = self.request(path=endpoint + '/' + asset['id'] + '/content')
        self.assertEqual(status, 200)
        self.assertEqual(base64.b64decode(content['content_base64']), data)

    def test_import_key_conflict_does_not_publish_second_asset(self):
        self.start()
        _, project = self.request('POST', body='{"name":"Conflict project"}')
        endpoint = '/api/projects/' + project['project']['id'] + '/assets'
        _, body = self.image_body('red')
        self.assertEqual(self.request('POST', endpoint, body)[0], 201)
        _, changed = self.image_body('blue')
        self.assertEqual(self.request('POST', endpoint, changed)[0], 409)
        self.assertEqual(len(self.request(path=endpoint)[1]['assets']), 1)

    def test_invalid_image_and_cross_project_read_are_rejected(self):
        self.start()
        _, first = self.request('POST', body='{"name":"First"}')
        _, second = self.request('POST', body='{"name":"Second"}')
        endpoint = '/api/projects/' + first['project']['id'] + '/assets'
        for payload in ({'content_base64': 'not base64', 'idempotency_key': 'a'},
                        {'content_base64': base64.b64encode(b'<svg/>').decode(), 'idempotency_key': 'a'},
                        {'content_base64': '', 'idempotency_key': '../escape'}):
            self.assertEqual(self.request('POST', endpoint, json.dumps(payload))[0], 400)
        self.assertEqual(self.request(path=endpoint), (200, {'assets': []}))
        _, body = self.image_body()
        _, imported = self.request('POST', endpoint, body)
        foreign = '/api/projects/' + second['project']['id'] + '/assets/' + imported['asset']['id'] + '/content'
        self.assertEqual(self.request(path=foreign)[0], 404)

    def test_modified_published_image_cannot_reuse_success_receipt(self):
        self.start()
        _, project = self.request('POST', body='{"name":"Integrity"}')
        endpoint = '/api/projects/' + project['project']['id'] + '/assets'
        _, body = self.image_body()
        _, imported = self.request('POST', endpoint, body)
        files = list((self.root / '.project-local/projects' / project['project']['id']).glob('assets/versions/*/reference.png'))
        self.assertEqual(len(files), 1)
        files[0].write_bytes(b'corrupted synthetic fixture')
        self.assertEqual(self.request('POST', endpoint, body)[0], 409)
        self.assertEqual(self.request(path=endpoint + '/' + imported['asset']['id'] + '/content')[0], 409)

    def test_jpeg_import_preserves_original_encoded_bytes(self):
        from PIL import Image
        self.start()
        _, project = self.request('POST', body='{"name":"JPEG"}')
        endpoint = '/api/projects/' + project['project']['id'] + '/assets'
        stream = io.BytesIO()
        Image.new('RGB', (21, 15), 'blue').save(stream, format='JPEG')
        data = stream.getvalue()
        body = json.dumps({'content_base64': base64.b64encode(data).decode(), 'idempotency_key': 'jpeg'})
        status, imported = self.request('POST', endpoint, body)
        self.assertEqual(status, 201)
        self.assertEqual(imported['asset']['media_type'], 'image/jpeg')
        _, readback = self.request(path=endpoint + '/' + imported['asset']['id'] + '/content')
        self.assertEqual(base64.b64decode(readback['content_base64']), data)

    def _empty_task_list(self, path):
        """A page that holds nothing still has to say so in the same envelope as one that does."""
        status, page = self.request(path=path)
        self.assertEqual(status, 200)
        self.assertEqual(page['schemaVersion'], 'design-lab/task-readback/v1')
        self.assertEqual(page['tasks'], [])
        self.assertEqual(page['count'], 0)
        self.assertFalse(page['truncated'])
        self.assertIsNone(page['next_cursor'])
        return page

    def test_task_history_survives_restart_and_is_project_scoped(self):
        self.start()
        _, first = self.request('POST', body='{"name":"Task owner"}')
        _, second = self.request('POST', body='{"name":"Other owner"}')
        root = '/api/projects/' + first['project']['id']
        other = '/api/projects/' + second['project']['id']
        self._empty_task_list(root + '/tasks')
        _, payload = self.image_body()
        _, imported = self.request('POST', root + '/assets', payload)
        job_id = imported['attempt']['job_id']
        self.stop()
        self.start()
        status, listing = self.request(path=root + '/tasks')
        self.assertEqual(status, 200)
        self.assertEqual(len(listing['tasks']), 1)
        task = listing['tasks'][0]
        self.assertEqual(task['job_id'], job_id)
        self.assertEqual(task['state'], 'SUCCEEDED')
        self.assertEqual(task['attempt']['state'], 'RECEIPTED')
        self.assertEqual(task['kind'], 'image-import')
        self.assertNotIn('note', task['attempt'])
        status, detail = self.request(path=root + '/tasks/' + job_id)
        self.assertEqual(status, 200)
        self.assertEqual(detail['task'], task)
        self.assertEqual(detail['surface'], 'task')
        self.assertEqual(detail['count'], 1)
        status, events = self.request(path=root + '/tasks/' + job_id + '/events')
        self.assertEqual(status, 200)
        self.assertEqual([e['to_state'] for e in events['events']], ['PENDING', 'RUNNING', 'RECEIPTED'])
        self.assertTrue(all('detail' not in e and 'evidence_json' not in e for e in events['events']))
        cursor = events['events'][-1]['event_no']
        status, tail = self.request(path=root + '/tasks/' + job_id + '/events?after=' + str(cursor))
        self.assertEqual(status, 200)
        self.assertEqual(tail['events'], [])
        self.assertFalse(tail['truncated'])
        self.assertIsNone(tail['next_cursor'])
        self.assertEqual(self._empty_task_list(other + '/tasks')['surface'], 'list')
        for tail in ('', '/events'):
            self.assertEqual(self.request(path=other + '/tasks/' + job_id + tail)[0], 404)
        self._empty_task_list(root + '/tasks?after=' + job_id)

    def test_task_reads_cannot_create_state_or_accept_ambiguous_cursors(self):
        self.start()
        root = '/api/projects/' + 'a' * 32 + '/tasks'
        for tail in ('', '/job-' + 'a' * 64, '/job-' + 'a' * 64 + '/events'):
            self.assertEqual(self.request(path=root + tail)[0], 404)
        for query in ('?after=../escape', '?after=x&after=y', '?limit=999999', '?after=%00'):
            self.assertEqual(self.request(path=root + query)[0], 404)
        self.assertFalse((self.root / '.project-local').exists())

    def test_task_pagination_latest_attempt_and_cancellation_are_not_flattened(self):
        from contextlib import closing
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / 'src'))
        self.addCleanup(lambda: sys.path.remove(str(ROOT / 'src')))
        from design_lab.service import ProjectService
        from design_lab.runtime import job_store as jobs
        with patch.dict(os.environ):
            os.environ.pop('PROJECT_LOCAL_ROOT', None)
            service = ProjectService(self.root)
            project = service.create_project('Paginated tasks')['id']
            scope = 'image-import:' + project
            with closing(jobs.connect(service.database, project_root=self.root)) as conn:
                for number in range(102):
                    job_id = 'job-' + f'{number:064x}'
                    jobs.begin_attempt(conn, job_id, operation_id='import-' + f'{number:064x}',
                                       idempotency_scope=scope, idempotency_key=str(number), request_hash='a' * 64)
                first = 'job-' + '0' * 64
                for _ in range(51):
                    attempt = jobs.latest_attempt(conn, first)
                    jobs.transition(conn, attempt['attempt_id'], 'FAILED', note='PRIVATE_TEST_SENTINEL')
                    jobs.retry_attempt(conn, first, previous_attempt_id=attempt['attempt_id'])
                attempt = jobs.latest_attempt(conn, first)
                jobs.transition(conn, attempt['attempt_id'], 'RUNNING')
                jobs.request_cancel(conn, attempt['attempt_id'])
            before = hashlib.sha256(service.database.read_bytes()).hexdigest()
        self.start()
        root = '/api/projects/' + project + '/tasks'
        status, page = self.request(path=root)
        self.assertEqual(status, 200)
        self.assertEqual(len(page['tasks']), 100)
        self.assertEqual(page['next_cursor'], 'job-' + f'{99:064x}')
        self.assertEqual(page['tasks'][0]['state'], 'CANCEL_REQUESTED')
        self.assertEqual(page['tasks'][0]['attempt']['state'], 'CANCEL_REQUESTED')
        self.assertEqual(page['tasks'][0]['attempt']['attempt_no'], 52)
        _, last = self.request(path=root + '?after=' + page['next_cursor'])
        self.assertEqual([t['job_id'] for t in last['tasks']], ['job-' + f'{n:064x}' for n in (100, 101)])
        self.assertIsNone(last['next_cursor'])
        _, events = self.request(path=root + '/' + first + '/events')
        self.assertEqual(len(events['events']), 100)
        self.assertIsNotNone(events['next_cursor'])
        _, tail = self.request(path=root + '/' + first + '/events?after=' + str(events['next_cursor']))
        combined = events['events'] + tail['events']
        self.assertEqual(len(combined), 105)
        self.assertEqual(len({e['event_no'] for e in combined}), 105)
        self.assertEqual(combined[-1]['to_state'], 'CANCEL_REQUESTED')
        self.assertNotIn('PRIVATE_TEST_SENTINEL', json.dumps(combined))
        self.stop()
        self.assertEqual(hashlib.sha256(service.database.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
