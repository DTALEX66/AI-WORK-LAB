# SPDX-License-Identifier: MIT
import copy
import hashlib
from pathlib import Path
import unittest
import test_native_plan as fixtures


class PhotoshopPatchPlanTests(unittest.TestCase):
    setUp=fixtures.NativePlanTests.setUp

    def baseline(self):
        source=self.root/'.project-local/task-artifacts/source';source.mkdir(parents=True)
        self.checkpoint=source/'checkpoint.psd'
        self.checkpoint.write_bytes(b'8BPS\x00\x01'+b'\0'*6+b'\x00\x03'+(6).to_bytes(4,'big')+(8).to_bytes(4,'big')+b'\x00\x08\x00\x03')
        self.checksum=hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
        return dict(schemaVersion='design-lab/photoshop-native-job/v1',jobId='base',runRoot=str(source),
            width=8,height=6,assets=[],outputName='output.psd',previewName='output.png',
            layers=[dict(id='group',kind='group',mask=None,children=[
                dict(id='title',kind='text',text='Before',font='ArialMT',size=2,position=[1,2],color=[0,0,0]),
                dict(id='box',kind='fill',bounds=[1,1,2,2],color=[0,0,0])])])

    def prepare(self,baseline,patch):
        from design_lab.native_patch_plan import prepare_patch
        return prepare_patch(self.service,self.project,baseline,self.checkpoint,self.checksum,{},patch,self.run)

    def test_psd_text_plan_preserves_checkpoint_and_source_graph(self):
        baseline=self.baseline();original=copy.deepcopy(baseline)
        result=self.prepare(baseline,dict(kind='text',id='title',text='After'))
        self.assertEqual(result['schemaVersion'],'design-lab/photoshop-patch-job/v1')
        self.assertEqual(Path(result['checkpoint']).read_bytes(),self.checkpoint.read_bytes())
        self.assertEqual(result['layers'][0]['children'][0]['text'],'Before')
        self.assertEqual(result['patch']['text'],'After');self.assertEqual(baseline,original)

    def test_second_patch_inherits_previous_text_result(self):
        baseline=self.baseline();baseline.update(schemaVersion='design-lab/photoshop-patch-job/v1',patch=dict(kind='text',id='title',text='After'))
        result=self.prepare(baseline,dict(kind='move',id='box',delta=[1,1]))
        self.assertEqual(result['layers'][0]['children'][0]['text'],'After')
        self.assertEqual(result['patch']['delta'],[1,1])

    def test_previous_move_updates_only_target_geometry(self):
        baseline=self.baseline();baseline.update(schemaVersion='design-lab/photoshop-patch-job/v1',patch=dict(kind='move',id='box',delta=[1,1]))
        result=self.prepare(baseline,dict(kind='text',id='title',text='Next'))
        self.assertEqual(result['layers'][0]['children'][1]['bounds'],[2,2,2,2])
        self.assertEqual(result['layers'][0]['children'][0]['position'],[1,2])

    def test_invalid_psd_patch_or_changed_checkpoint_does_not_stage(self):
        baseline=self.baseline()
        for patch in [dict(kind='move',id='group',delta=[1,1]),dict(kind='move',id='box',delta=[True,0]),
                      dict(kind='move',id='box',delta=[float('inf'),0]),dict(kind='move',id='box',delta=[9,0]),
                      dict(kind='text',id='box',text='No'),dict(kind='text',id='title',text='')]:
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):self.prepare(baseline,patch)
                self.assertEqual(list(self.run.iterdir()),[])
        self.checkpoint.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.prepare(baseline,dict(kind='text',id='title',text='After'))
        self.assertEqual(list(self.run.iterdir()),[])


if __name__ == '__main__':
    unittest.main()
