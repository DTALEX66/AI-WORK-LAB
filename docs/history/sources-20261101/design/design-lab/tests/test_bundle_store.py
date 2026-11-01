# SPDX-License-Identifier: MIT
from contextlib import closing
import hashlib
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))


class BundleStoreTests(unittest.TestCase):
    def setUp(self):
        from design_lab.service import ProjectService
        from design_lab.runtime import asset_store
        self.assets=asset_store
        parent=ROOT/'.project-local/task-runtime/bundle-tests';parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);(self.root/'AGENTS.md').write_text('# fixture')
        env=patch.dict(os.environ,{'PROJECT_LOCAL_ROOT':str(self.root/'.project-local')});env.start();self.addCleanup(env.stop)
        self.service=ProjectService(self.root);self.project=self.service.create_project('bundle')['id']
        self.inputs=self.service.paths.category_dir('runtime','bundle-input');self.inputs.mkdir(parents=True)
        self.files={}
        for name,data,role in [('native.ai',b'editable fixture','primary'),('preview.png',b'preview fixture','preview')]:
            path=self.inputs/name;path.write_bytes(data)
            self.files[name]={'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'role':role}
        self.conn=asset_store.connect(self.service.database,project_root=self.root);self.addCleanup(self.conn.close)
        from design_lab.runtime import job_store
        with closing(job_store.connect(self.service.database,project_root=self.root)) as jobs:
            self.aid=job_store.begin_attempt(jobs,'bundle-fixture',operation_id='bundle-op',
                idempotency_scope='bundle-test',idempotency_key='one',request_hash='a'*64)['attempt_id']
        asset_store.register_asset(self.conn,self.project,'bundle','other')
        asset_store.acquire_writer(self.conn,'asset:bundle',self.aid)
        self.token=asset_store.writer_token(self.conn,'asset:bundle',self.aid)

    def publish(self):
        from design_lab.runtime.bundle_store import publish_bundle
        return publish_bundle(self.conn,'bundle',self.files,primary='native.ai',metadata={'rights':'NOT_REVIEWED'},
                              store_root=self.service.paths.category_dir('projects',self.project,'assets'),
                              holder_attempt_id=self.aid,generation=self.token,project_root=self.root)

    def test_complete_bundle_is_deterministic_and_one_version(self):
        from design_lab.runtime.bundle_store import verify_bundle
        first=self.publish();second=self.publish()
        self.assertEqual(first,second)
        row=self.conn.execute('SELECT path FROM artifact WHERE version_id=?',(first,)).fetchone()
        manifest=verify_bundle(Path(row[0]))
        self.assertEqual(manifest['primary'],'native.ai')
        self.assertEqual(set(manifest['files']),{'native.ai','preview.png'})
        with zipfile.ZipFile(row[0]) as archive:
            self.assertEqual(archive.read('native.ai'),b'editable fixture')
            self.assertEqual(archive.read('preview.png'),b'preview fixture')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],1)

    def test_secondary_change_produces_distinct_version(self):
        first=self.publish()
        path=Path(self.files['preview.png']['path']);path.write_bytes(b'changed preview')
        self.files['preview.png']['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        second=self.publish()
        self.assertNotEqual(first,second)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],2)

    def test_wrong_hash_or_escaping_name_never_publishes(self):
        self.files['preview.png']['sha256']='0'*64
        with self.assertRaises(ValueError):self.publish()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
        self.files['../escape']=self.files.pop('preview.png')
        with self.assertRaises(ValueError):self.publish()

    def test_case_colliding_names_and_missing_primary_are_rejected(self):
        self.files['PREVIEW.PNG']=dict(self.files['preview.png'])
        with self.assertRaises(ValueError):self.publish()
        del self.files['PREVIEW.PNG'];del self.files['native.ai']
        with self.assertRaises(ValueError):self.publish()

    def test_modified_secondary_member_fails_readback(self):
        from design_lab.runtime.bundle_store import verify_bundle
        version=self.publish()
        path=Path(self.conn.execute('SELECT path FROM artifact WHERE version_id=?',(version,)).fetchone()[0])
        with zipfile.ZipFile(path) as archive:
            members={name:archive.read(name) for name in archive.namelist()}
        members['preview.png']=b'tampered preview'
        altered=self.inputs/'altered.zip'
        with zipfile.ZipFile(altered,'w') as archive:
            for name,data in members.items():archive.writestr(name,data)
        with self.assertRaises(ValueError):verify_bundle(altered,project_root=self.root)

    def test_publication_failure_cannot_commit_partial_bundle(self):
        with patch.object(self.assets,'_after_stage',side_effect=OSError('staged crash')):
            with self.assertRaises(OSError):self.publish()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
        row=self.conn.execute('SELECT state,stage_path FROM asset_publication').fetchone()
        self.assertEqual(row[0],'PREPARED')
        with zipfile.ZipFile(row[1]) as archive:
            self.assertEqual(set(archive.namelist()),{'bundle-manifest.json','native.ai','preview.png'})

    def test_secondary_member_growing_after_validation_fails_during_copy(self):
        """The only window that the "validate everything first" ordering leaves open.

        publish_bundle hashes every member before it stages anything, so a wrong
        hash can never publish (already covered at :67). What that ordering does NOT
        cover is a member that changes after it was measured and while it is being
        copied -- bundle_store.py:114-119 is the guard for that, and nothing else in
        the suite reaches it.
        """
        real=self.assets._file_hash
        target=self.inputs/'preview.png'
        def grow_after_measuring(path,*args,**kwargs):
            digest=real(path,*args,**kwargs)
            if Path(path)==target:
                target.write_bytes(b'preview fixture'+b'x'*8)
            return digest
        with patch.object(self.assets,'_file_hash',side_effect=grow_after_measuring):
            with patch.object(self.assets,'publish_version',side_effect=AssertionError('must not publish')) as invoke:
                with self.assertRaises(ValueError) as caught:
                    self.publish()
        self.assertIn('bundle source grew while copying',str(caught.exception))
        invoke.assert_not_called()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_publication').fetchone()[0],0)

    def test_secondary_member_rewritten_at_same_size_fails_during_copy(self):
        """The other half of the copy window: same byte count, different content.

        The size guard cannot see this and the digest guard cannot see a size change,
        so each branch needs its own case; with the size guard deleted this scenario
        still has to be refused rather than published as a hash-mismatched archive.
        """
        real=self.assets._file_hash
        target=self.inputs/'preview.png'
        def rewrite_after_measuring(path,*args,**kwargs):
            digest=real(path,*args,**kwargs)
            if Path(path)==target:
                original=target.read_bytes()
                target.write_bytes(original[:-1]+bytes([(original[-1]^0x20)]))
            return digest
        with patch.object(self.assets,'_file_hash',side_effect=rewrite_after_measuring):
            with patch.object(self.assets,'publish_version',side_effect=AssertionError('must not publish')) as invoke:
                with self.assertRaises(ValueError) as caught:
                    self.publish()
        self.assertIn('bundle source changed while copying',str(caught.exception))
        invoke.assert_not_called()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_publication').fetchone()[0],0)

    def test_validation_failure_journals_nothing(self):
        """The existing wrong-hash test asserts no version; it does not assert no attempt.

        A PREPARED row with no committed publication is recovery evidence, so it is
        worth knowing which failures create one. Failing before staging should create
        none at all.
        """
        self.files['preview.png']['sha256']='0'*64
        with self.assertRaises(ValueError):self.publish()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_publication').fetchone()[0],0)
        # a retry with the correct hash still succeeds, so the failed call left no lock
        # or journal state that could block the same attempt later
        self.files['preview.png']['sha256']=hashlib.sha256(
            (self.inputs/'preview.png').read_bytes()).hexdigest()
        self.assertTrue(self.publish())
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0],1)


if __name__=='__main__':unittest.main()
