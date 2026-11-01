# SPDX-License-Identifier: MIT
import copy
import hashlib
import importlib.util
import unittest
import test_native_plan as fixtures


class NativePatchPlanTests(unittest.TestCase):
    setUp = fixtures.NativePlanTests.setUp

    def prepare(self, baseline, patch, root=None):
        self.assertIsNotNone(importlib.util.find_spec('design_lab.native_patch_plan'), 'patch plan preparation missing')
        from design_lab.native_patch_plan import prepare_patch
        return prepare_patch(self.service, self.project, baseline, self.checkpoint,
                             self.checksum, {}, patch, root or self.run)

    def baseline(self):
        source = self.root / '.project-local/task-artifacts/source'
        source.mkdir(parents=True)
        self.checkpoint = source / 'checkpoint.ai'
        self.checkpoint.write_bytes(b'%PDF- controlled fake checkpoint; no host invoked')
        self.checksum = hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
        return dict(schemaVersion='design-lab/adobe-host-job/v1', jobId='base', rirHash='a'*64,
                    runRoot=str(self.checkpoint.parent), artboard=dict(width=8,height=6), assets=[],
                    targets={}, operations=[], authorization=dict(required=True,scope='single-session'),
                    layers=[dict(id='layer',items=[dict(kind='text',id='title',text='Before')])])

    def test_text_patch_stages_verified_copy_and_preserves_source(self):
        baseline=self.baseline(); before=copy.deepcopy(baseline)
        job=self.prepare(baseline,dict(kind='text',id='title',text='After'))
        from pathlib import Path
        self.assertEqual(Path(job['checkpoint']).read_bytes(),self.checkpoint.read_bytes())
        self.assertEqual(job['patch']['text'],'After')
        self.assertEqual(job['layers'][0]['items'][0]['text'],'Before')
        self.assertEqual(baseline,before)
        self.assertFalse(Path(job['targets']['ai']).exists())

    def test_second_patch_uses_prior_post_patch_graph(self):
        baseline=self.baseline(); baseline.update(schemaVersion='design-lab/adobe-patch-job/v1',patch=dict(kind='text',id='title',text='After'))
        job=self.prepare(baseline,dict(kind='text',id='title',text='Second'))
        self.assertEqual(job['layers'][0]['items'][0]['text'],'After')
        self.assertEqual(job['patch']['text'],'Second')

    def test_invalid_patch_and_changed_checkpoint_leave_no_staged_files(self):
        baseline=self.baseline()
        for change in (dict(kind='text',id='absent',text='After'),dict(kind='text',id='title',text=''),
                       dict(kind='text',id='title',text='After',command='anything'),dict(kind='path',id='title',points=[])):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):self.prepare(baseline,change)
                self.assertEqual(list(self.run.iterdir()),[])
        self.checkpoint.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.prepare(baseline,dict(kind='text',id='title',text='After'))
        self.assertEqual(list(self.run.iterdir()),[])

    def test_path_topology_and_nonfinite_coordinates_rejected(self):
        baseline=self.baseline(); points=[dict(anchor=[0,0],left=[0,0],right=[0,0]),dict(anchor=[1,1],left=[1,1],right=[1,1])]
        baseline['layers'][0]['items']=[dict(kind='path',id='curve',points=points)]
        for bad in (points[:1],[points[0],dict(anchor=[float('nan'),0],left=[0,0],right=[0,0])]):
            with self.assertRaises(ValueError):self.prepare(baseline,dict(kind='path',id='curve',points=bad))
        good=copy.deepcopy(points);good[0]['anchor']=[2,2]
        job=self.prepare(baseline,dict(kind='path',id='curve',points=good))
        self.assertEqual(job['patch']['points'][0]['anchor'],[2,2])

    def test_linked_asset_copy_requires_matching_receipt(self):
        baseline=self.baseline(); image=self.checkpoint.parent/'linked.png'
        image.write_bytes(b'controlled input bytes; format checked by adapter')
        baseline['assets']=[dict(id='linked',path=str(image))]
        from design_lab.native_patch_plan import prepare_patch
        patch=dict(kind='text',id='title',text='After')
        with self.assertRaises(ValueError):self.prepare(baseline,patch)
        self.assertEqual(list(self.run.iterdir()),[])
        digest=dict(sha256=hashlib.sha256(image.read_bytes()).hexdigest(),byte_size=image.stat().st_size)
        job=prepare_patch(self.service,self.project,baseline,self.checkpoint,self.checksum,{str(image):digest},patch,self.run)
        from pathlib import Path
        self.assertEqual(Path(job['assets'][0]['path']).read_bytes(),image.read_bytes())
        self.assertTrue(Path(job['assets'][0]['path']).is_relative_to(self.run))
        self.assertEqual(baseline['assets'][0]['path'],str(image))

    def test_other_project_root_and_existing_files_not_overwritten(self):
        baseline=self.baseline();other=self.service.create_project('Other')['id']
        root=self.service.paths.category_dir('projects',other,'native-plans','fixture');root.mkdir(parents=True)
        with self.assertRaises(ValueError):self.prepare(baseline,dict(kind='text',id='title',text='After'),root)
        self.assertEqual(list(root.iterdir()),[])
        sentinel=self.run/'checkpoint.ai';sentinel.write_bytes(b'preserve')
        with self.assertRaises(ValueError):self.prepare(baseline,dict(kind='text',id='title',text='After'))
        self.assertEqual(sentinel.read_bytes(),b'preserve')


if __name__=='__main__':unittest.main()
