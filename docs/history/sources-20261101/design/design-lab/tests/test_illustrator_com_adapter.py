# SPDX-License-Identifier: MIT
"""Adapter decisions with COM boundary doubled; native qualification is separate."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))


class IllustratorComAdapterTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.project-local/task-runtime/illustrator-com-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'AGENTS.md').write_text('# synthetic owner',encoding='utf-8')
        # Each synthetic checkout owns its runtime root, even under CI's outer override.
        environment=patch.dict(os.environ,{'PROJECT_LOCAL_ROOT':str(self.root/'.project-local')})
        environment.start();self.addCleanup(environment.stop)
        self.run=self.root/'.project-local/task-artifacts/run';self.run.mkdir(parents=True)
        self.job=dict(schemaVersion='design-lab/adobe-host-job/v1',jobId='com-test',rirHash='a'*64,
            runRoot=str(self.run),artboard=dict(width=8,height=6),layers=[dict(id='layer',items=[dict(id='box',kind='path',
                points=[dict(anchor=[0,0],left=[0,0],right=[0,0]),dict(anchor=[8,6],left=[8,6],right=[8,6])],closed=False,color=[255,0,0])])],assets=[],
            targets={k:str(self.run/('output.'+k)) for k in ('ai','png','svg')},
            operations=['createDocument','createLayer','placePath','placeText','placeRaster','applyMask',
                'saveAI','exportSVG','reopen','readback','exportPNG'],authorization=dict(required=True,scope='single-session'))

    def adapter(self):
        import design_lab.adapters.illustrator_com as module
        return module

    def outputs(self,script,timeout):
        # Only external COM boundary is doubled; filesystem sealing is real.
        (self.run/'output.ai').write_bytes(b'%PDF-1.5\nsynthetic test, not native proof')
        (self.run/'output.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>',encoding='utf-8')
        Image.new('RGB',(8,6),'red').save(self.run/'output.png')
        return 'DL_NATIVE_V1\t29.5.1\tcom-test\t'+'a'*64+'\t0\t0'

    def test_adapter_available_and_seals_real_outputs(self):
        """Missing adapter or accepting an unbound acknowledgement must fail."""
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('design_lab.adapters.illustrator_com'))
        module=self.adapter()
        with patch.object(module,'_invoke_com',side_effect=self.outputs):
            result=module.execute(self.job,project_root=self.root,approved_root=self.run)
        self.assertEqual(result['status'],'NATIVE_READBACK')
        self.assertEqual(result['host_version'],'29.5.1')
        self.assertEqual(result['artifacts']['ai']['sha256'],hashlib.sha256((self.run/'output.ai').read_bytes()).hexdigest())
        self.assertEqual(result['job_sha256'],hashlib.sha256(json.dumps(self.job,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest())

    def patch_job(self):
        checkpoint=self.run/'checkpoint.ai';checkpoint.write_bytes(b'%PDF-1.5\ncontrolled checkpoint')
        self.job.update(schemaVersion='design-lab/adobe-patch-job/v1',checkpoint=str(checkpoint),
            checkpointSha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            patch=dict(kind='path',id='box',points=[dict(anchor=[1,0],left=[1,0],right=[1,0]),
                dict(anchor=[8,6],left=[8,6],right=[8,6])]),
            operations=['openAI','readback','patchObject','saveAI','reopen','readback','exportPNG','exportSVG'])
        return checkpoint

    def test_patch_checkpoint_is_hash_bound_and_not_overwritten(self):
        checkpoint=self.patch_job();before=checkpoint.read_bytes();module=self.adapter()
        with patch.object(module,'_invoke_com',side_effect=self.outputs):
            result=module.execute(self.job,project_root=self.root,approved_root=self.run)
        self.assertEqual(checkpoint.read_bytes(),before)
        self.assertEqual(result['inputs'][str(checkpoint)]['sha256'],self.job['checkpointSha256'])

    def test_changed_patch_checkpoint_fails_before_dispatch(self):
        checkpoint=self.patch_job();checkpoint.write_bytes(b'changed');module=self.adapter()
        with patch.object(module,'_invoke_com') as call:
            with self.assertRaises(module.IllustratorDispatchError) as caught:
                module.execute(self.job,project_root=self.root,approved_root=self.run)
            self.assertFalse(caught.exception.outcome_unknown);call.assert_not_called()

    def test_escape_or_existing_output_never_dispatches(self):
        module=self.adapter()
        for target in (self.root/'outside.ai',self.run/'..'/'escape.ai'):
            self.job['targets']['ai']=str(target)
            with patch.object(module,'_invoke_com') as invoke:
                with self.assertRaises(module.IllustratorDispatchError):module.execute(self.job,project_root=self.root,approved_root=self.run)
                invoke.assert_not_called()
        self.job['targets']['ai']=str(self.run/'output.ai');(self.run/'output.ai').write_bytes(b'preserve')
        with patch.object(module,'_invoke_com') as invoke:
            with self.assertRaises(module.IllustratorDispatchError):module.execute(self.job,project_root=self.root,approved_root=self.run)
            invoke.assert_not_called()
        self.assertEqual((self.run/'output.ai').read_bytes(),b'preserve')

    def test_timeout_and_wrong_receipt_do_not_report_success(self):
        module=self.adapter()
        for outcome in (TimeoutError('COM did not return'),'DL_NATIVE_V1\t29.5.1\tanother-job\t'+'a'*64+'\t0\t0'):
            with patch.object(module,'_invoke_com',**({'side_effect':outcome} if isinstance(outcome,Exception) else {'return_value':outcome})):
                with self.assertRaises(module.IllustratorDispatchError) as caught:
                    module.execute(self.job,project_root=self.root,approved_root=self.run)
                self.assertTrue(caught.exception.outcome_unknown)

    def test_missing_output_and_changed_input_are_unknown(self):
        module=self.adapter()
        with patch.object(module,'_invoke_com',return_value='DL_NATIVE_V1\t29.5.1\tcom-test\t'+'a'*64+'\t0\t0'):
            with self.assertRaises(module.IllustratorDispatchError) as caught:
                module.execute(self.job,project_root=self.root,approved_root=self.run)
            self.assertTrue(caught.exception.outcome_unknown)
        Image.new('RGB',(8,6),'blue').save(self.run/'input.png')
        self.job['assets']=[dict(id='image',path=str(self.run/'input.png'))]
        def changed(script,timeout):
            result=self.outputs(script,timeout);(self.run/'input.png').write_bytes(b'changed');return result
        with patch.object(module,'_invoke_com',side_effect=changed):
            with self.assertRaises(module.IllustratorDispatchError) as caught:
                module.execute(self.job,project_root=self.root,approved_root=self.run)
            self.assertTrue(caught.exception.outcome_unknown)

    def test_malformed_job_fails_before_com_and_retains_existing_files(self):
        module=self.adapter()
        self.job['rirHash']='0'*64
        with patch.object(module,'_invoke_com') as invoke:
            with self.assertRaises(module.IllustratorDispatchError) as caught:
                module.execute(self.job,project_root=self.root,approved_root=self.run)
            self.assertFalse(caught.exception.outcome_unknown)
            invoke.assert_not_called()

    def test_the_shipped_fixture_conforms_to_the_contract_it_declares(self):
        """The closed job this suite dispatches is judged by the contract file, and passes it.

        Without this the next test only proves a refusal happened somewhere.
        """
        module=self.adapter()
        self.assertEqual(module._contract_problems(self.job),[])
        checkpoint=self.patch_job()
        self.assertEqual(module._contract_problems(self.job),[])
        self.assertTrue(checkpoint.is_file())

    def test_fields_the_hand_key_sets_never_typed_are_refused_by_the_contract(self):
        """B2b (2026-10-22): `set(job)==required` says which keys exist, not what they hold.

        These three shapes passed every hand check in execute() and were handed to the host
        anyway; the contract file is what stops them now, before any COM call.
        """
        module=self.adapter()
        for field,unshaped in (('authorization',None),('layers',{'id':'layer'}),('artboard','8x6')):
            job=dict(self.job);job[field]=unshaped
            with self.subTest(field=field):
                problems=module._contract_problems(job)
                self.assertTrue(problems,f'{field}={unshaped!r} passed the contract check')
                with patch.object(module,'_invoke_com') as invoke:
                    with self.assertRaises(module.IllustratorDispatchError) as caught:
                        module.execute(job,project_root=self.root,approved_root=self.run)
                    self.assertFalse(caught.exception.outcome_unknown)
                    invoke.assert_not_called()

    def test_every_version_the_adapter_compares_has_a_contract_file_on_disk(self):
        """A version added to the hand check without a contract row is caught here, not in production."""
        module=self.adapter()
        for version,relative in module.JOB_CONTRACTS.items():
            with self.subTest(version=version):
                self.assertTrue((ROOT/relative).is_file(),f'{version} maps to absent {relative}')
                document=json.loads((ROOT/relative).read_text(encoding='utf-8'))
                self.assertEqual(document['properties']['schemaVersion']['const'],version,
                                 f'{relative} binds {document["properties"]["schemaVersion"]["const"]!r}, '
                                 f'not the {version!r} the adapter selects it by')


if __name__ == '__main__':
    unittest.main()
