# SPDX-License-Identifier: MIT
"""Real preflight/filesystem with only native COM dispatch doubled."""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))


class PhotoshopComAdapterTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.project-local/task-runtime/photoshop-com-tests';parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);(self.root/'AGENTS.md').write_text('# synthetic owner',encoding='utf-8')
        environment=patch.dict(os.environ,{'PROJECT_LOCAL_ROOT':str(self.root/'.project-local')})
        environment.start();self.addCleanup(environment.stop)
        self.run=self.root/'.project-local/task-artifacts/run';self.run.mkdir(parents=True)
        Image.new('RGB',(8,6),'blue').save(self.run/'input.png')
        self.job=dict(schemaVersion='design-lab/photoshop-native-job/v1',jobId='ps-test',runRoot=str(self.run),
            width=8,height=6,outputName='output.psd',previewName='output.png',
            assets=[dict(id='input',path=str(self.run/'input.png'))],
            layers=[dict(id='image',kind='raster',assetId='input',position=[0,0],width=8,height=6)])

    def adapter(self):
        self.assertIsNotNone(importlib.util.find_spec('design_lab.adapters.photoshop_com'),'product adapter missing')
        return importlib.import_module('design_lab.adapters.photoshop_com')

    def receipt(self):
        sha=hashlib.sha256(json.dumps(self.job,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        return 'DL_PS_NATIVE_V1\t26.7.0\tps-test\t'+sha+'\t0\t0'

    def test_quiescence_binds_acknowledgement_and_preserves_existing_files(self):
        module=self.adapter()
        self.assertTrue(hasattr(module,'quiesce'))
        (self.run/'output.psd').write_bytes(b'preserved unknown output')
        with patch.object(module,'_invoke_com',return_value='DL_PS_QUIESCENT_V1|ps-test|2|1|1'):
            result=module.quiesce(self.job,project_root=self.root,approved_root=self.run)
        self.assertEqual(result['closed_documents'],1)
        self.assertEqual(result['status'],'HOST_QUIESCENT_ARTIFACTS_UNACCEPTED')
        self.assertEqual((self.run/'output.psd').read_bytes(),b'preserved unknown output')
        for reply in ['DL_PS_QUIESCENT_V1|other|0|0|0','DL_PS_QUIESCENT_V1|ps-test|2|0|2','DL_PS_QUIESCENT_V1|ps-test|-1|-1|0']:
            with self.subTest(reply=reply),patch.object(module,'_invoke_com',return_value=reply):
                with self.assertRaises(ValueError):module.quiesce(self.job,project_root=self.root,approved_root=self.run)
        def mutate(script,timeout):
            (self.run/'output.psd').write_bytes(b'changed')
            return 'DL_PS_QUIESCENT_V1|ps-test|0|0|0'
        with patch.object(module,'_invoke_com',side_effect=mutate):
            with self.assertRaises(ValueError):module.quiesce(self.job,project_root=self.root,approved_root=self.run)

    def test_quiescence_script_preserves_unrelated_unsaved_and_unknown_documents(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        module=self.adapter()
        runner=r'''
const vm=require('vm'),fs=require('fs');const input=JSON.parse(fs.readFileSync(0,'utf8'));
const closed=[],documents=[];
for(const spec of input.docs){const d={saved:spec.saved,close(){closed.push(spec.path);documents.splice(documents.indexOf(d),1)}};
Object.defineProperty(d,'fullName',{get(){if(spec.unknown)throw Error('unsaved location');return {fsName:spec.path}}});documents.push(d);}
const context={app:{documents},File:p=>({fsName:p}),SaveOptions:{DONOTSAVECHANGES:2}};
let reply=null,error=null;try{reply=vm.runInNewContext(input.script,context)}catch(e){error=e.message}
console.log(JSON.stringify({reply,error,closed,remaining:documents.length}));
'''
        target=str(self.run/'output.psd');other=str(self.run/'user.psd')
        scenarios=[
            ([dict(path=other,saved=False),dict(path=target,saved=True)],[target],False),
            ([dict(path=target,saved=False)],[],True),
            ([dict(path=other,saved=True,unknown=True)],[],True),
            ([dict(path=target,saved=True),dict(path=target,saved=True)],[],True),
            ([dict(path=other,saved=False)],[],False),
            ([],[],False)]
        for docs,closed,reject in scenarios:
            with self.subTest(docs=docs):
                observed={}
                def invoke(script,timeout):
                    result=subprocess.run([node,'-e',runner],input=json.dumps(dict(script=script,docs=docs)),capture_output=True,text=True,encoding='utf-8',timeout=10)
                    self.assertEqual(result.returncode,0,result.stderr)
                    observed.update(json.loads(result.stdout))
                    if observed['error']:raise RuntimeError(observed['error'])
                    return observed['reply']
                with patch.object(module,'_invoke_com',side_effect=invoke):
                    if reject:
                        with self.assertRaises(RuntimeError):module.quiesce(self.job,project_root=self.root,approved_root=self.run)
                    else:module.quiesce(self.job,project_root=self.root,approved_root=self.run)
                self.assertEqual(observed['closed'],closed)
                self.assertEqual(observed['remaining'],len(docs)-len(closed))

    def test_stage_observer_writes_bound_events_and_rejects_unknown_stage(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        module=self.adapter();self.assertTrue(hasattr(module,'_stage_observer'))
        source=module._stage_observer(str(self.run/'stages.log'),'a'*64)
        runner=r'''
const vm=require('vm'),fs=require('fs'),writes=[];let closed=0;
const c={File:path=>({open:mode=>mode==='a',writeln:line=>{writes.push({path,line});return true},close:()=>{closed++;return true}})};
const observe=vm.runInNewContext(fs.readFileSync(0,'utf8'),c);
observe('validated');observe('build-start');let rejected=false;try{observe('arbitrary')}catch(e){rejected=true}
console.log(JSON.stringify({writes,closed,rejected}));
'''
        result=subprocess.run([node,'-e',runner],input=source,capture_output=True,text=True,encoding='utf-8',timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout);self.assertEqual(data['closed'],2);self.assertTrue(data['rejected'])
        for event,stage in zip(data['writes'],['validated','build-start']):
            self.assertEqual(event['path'],str(self.run/'stages.log'))
            fields=event['line'].split('|');self.assertEqual(fields[:2],['a'*64,stage]);self.assertGreaterEqual(int(fields[2]),0)

    def test_existing_stage_evidence_is_never_overwritten_or_dispatched(self):
        module=self.adapter();trace=self.run/'photoshop-stages.log';trace.write_bytes(b'preserve')
        with patch.object(module,'_invoke_com') as invoke:
            with self.assertRaises(module.PhotoshopDispatchError):module.execute(self.job,project_root=self.root,approved_root=self.run)
            self.assertEqual(invoke.call_count,0)
        self.assertEqual(trace.read_bytes(),b'preserve')

    def outputs(self,script,timeout):
        (self.run/'output.psd').write_bytes(b'8BPS\x00\x01'+b'\0'*6+b'\x00\x03'+(6).to_bytes(4,'big')+(8).to_bytes(4,'big')+b'\x00\x08\x00\x03')
        Image.new('RGB',(8,6),'red').save(self.run/'output.png')
        return self.receipt()

    def test_dispatch_wrapper_persists_job_bound_stage_events(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        module=self.adapter()
        bridge=b"function psRunJob(job,root,observe){observe('validated');observe('build-start');return {close:function(){}};}"
        runner=r'''
const vm=require('vm'),fs=require('fs');
const c={app:{documents:[],version:'26.7.0'},SaveOptions:{DONOTSAVECHANGES:2},
File:path=>({open:mode=>mode==='a',writeln:line=>{fs.appendFileSync(path,line+'\n');return true},close:()=>true})};
process.stdout.write(vm.runInNewContext(fs.readFileSync(0,'utf8'),c));
'''
        def invoke(script,timeout):
            self.assertEqual((self.run/'photoshop-stages.log').read_bytes(),b'')
            result=subprocess.run([node,'-e',runner],input=script,capture_output=True,text=True,encoding='utf-8',timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.outputs(script,timeout)
            return result.stdout
        with patch.object(module,'_bridge',return_value=bridge),patch.object(module,'_invoke_com',side_effect=invoke):
            result=module.execute(self.job,project_root=self.root,approved_root=self.run)
        events=[line.split('|') for line in (self.run/'photoshop-stages.log').read_text().splitlines()]
        self.assertEqual([event[1] for event in events],['validated','build-start'])
        self.assertTrue(all(event[0]==result['job_sha256'] for event in events))
        self.assertEqual((self.run/'photoshop-completion.receipt').read_text().strip(),self.receipt())

    def test_existing_completion_receipt_prevents_dispatch_and_is_preserved(self):
        module=self.adapter();receipt=self.run/'photoshop-completion.receipt'
        receipt.write_bytes(b'original completion')
        with patch.object(module,'_invoke_com') as invoke:
            with self.assertRaises(module.PhotoshopDispatchError) as caught:
                module.execute(self.job,project_root=self.root,approved_root=self.run)
            self.assertFalse(caught.exception.outcome_unknown)
            self.assertEqual(invoke.call_count,0)
        self.assertEqual(receipt.read_bytes(),b'original completion')

    def test_native_close_failure_leaves_completion_receipt_empty(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        module=self.adapter()
        bridge=b"function psRunJob(){return {close:function(){throw Error('close failed');}};}"
        runner=r'''
const vm=require('vm'),fs=require('fs');
const c={app:{documents:[],version:'26.7.0'},SaveOptions:{DONOTSAVECHANGES:2},
File:path=>({open:()=>true,writeln:line=>{fs.appendFileSync(path,line+'\n');return true},close:()=>true})};
try{vm.runInNewContext(fs.readFileSync(0,'utf8'),c)}catch(e){process.stdout.write(e.message);process.exitCode=1}
'''
        def invoke(script,timeout):
            result=subprocess.run([node,'-e',runner],input=script,capture_output=True,text=True,encoding='utf-8',timeout=10)
            self.assertEqual(result.returncode,1);self.assertEqual(result.stdout,'close failed')
            raise RuntimeError('controlled host close failure')
        with patch.object(module,'_bridge',return_value=bridge),patch.object(module,'_invoke_com',side_effect=invoke):
            with self.assertRaises(module.PhotoshopDispatchError) as caught:
                module.execute(self.job,project_root=self.root,approved_root=self.run)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual((self.run/'photoshop-completion.receipt').read_bytes(),b'')

    def test_seals_bound_native_receipt_and_real_file_hashes(self):
        module=self.adapter()
        with patch.object(module,'_invoke_com',side_effect=self.outputs):
            result=module.execute(self.job,project_root=self.root,approved_root=self.run)
        self.assertEqual(result['status'],'NATIVE_READBACK')
        self.assertEqual(result['host_version'],'26.7.0')
        self.assertEqual(result['artifacts']['psd']['sha256'],hashlib.sha256((self.run/'output.psd').read_bytes()).hexdigest())
        self.assertEqual(result['job_sha256'],self.receipt().split('\t')[3])

    def test_patch_dispatch_binds_psd_checkpoint_and_rejects_changed_source(self):
        module=self.adapter();checkpoint=self.run/'checkpoint.psd'
        self.outputs('',1);checkpoint.write_bytes((self.run/'output.psd').read_bytes())
        (self.run/'output.psd').unlink();(self.run/'output.png').unlink()
        checksum=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        self.job.update(schemaVersion='design-lab/photoshop-patch-job/v1',checkpoint=str(checkpoint),
            checkpointSha256=checksum,patch=dict(kind='move',id='image',delta=[1,0]))
        with patch.object(module,'_invoke_com',side_effect=self.outputs):
            result=module.execute(self.job,project_root=self.root,approved_root=self.run)
        self.assertEqual(result['inputs'][str(checkpoint)]['sha256'],checksum)
        self.assertEqual(checkpoint.read_bytes()[:6],b'8BPS\x00\x01')
        for name in ('output.psd','output.png','photoshop-stages.log','photoshop-completion.receipt'):
            (self.run/name).unlink(missing_ok=True)
        checkpoint.write_bytes(b'changed')
        with patch.object(module,'_invoke_com') as invoke:
            with self.assertRaises(module.PhotoshopDispatchError) as caught:
                module.execute(self.job,project_root=self.root,approved_root=self.run)
            self.assertFalse(caught.exception.outcome_unknown);self.assertEqual(invoke.call_count,0)

    def test_measured_143_second_workflow_fits_default_bounded_dispatch_budget(self):
        module=self.adapter()
        def measured_host(script,timeout):
            if timeout<143:raise TimeoutError('measured complex workflow needs 143 seconds')
            self.assertLessEqual(timeout,600)
            return self.outputs(script,timeout)
        with patch.object(module,'_invoke_com',side_effect=measured_host):
            result=module.execute(self.job,project_root=self.root,approved_root=self.run)
        self.assertEqual(result['status'],'NATIVE_READBACK')

    def test_bad_paths_existing_outputs_and_invalid_dimensions_never_dispatch(self):
        module=self.adapter()
        for key,value in [('outputName','../escape.psd'),('previewName','x.psd'),('width',True),('width',0),('height',float('nan')),
                          ('width',16384),('runRoot',str(self.root))]:
            bad=dict(self.job);bad[key]=value
            with self.subTest(key=key,value=value),patch.object(module,'_invoke_com') as invoke:
                with self.assertRaises(module.PhotoshopDispatchError) as caught:module.execute(bad,project_root=self.root,approved_root=self.run)
                self.assertFalse(caught.exception.outcome_unknown);invoke.assert_not_called()
        (self.run/'output.psd').write_bytes(b'preserve')
        with patch.object(module,'_invoke_com') as invoke:
            with self.assertRaises(module.PhotoshopDispatchError):module.execute(self.job,project_root=self.root,approved_root=self.run)
            invoke.assert_not_called()
        self.assertEqual((self.run/'output.psd').read_bytes(),b'preserve')

    def test_nonimage_and_outside_assets_never_dispatch(self):
        module=self.adapter();(self.run/'input.png').write_bytes(b'not an image')
        for path in (str(self.run/'input.png'),str(self.root/'private.png')):
            self.job['assets'][0]['path']=path
            with patch.object(module,'_invoke_com') as invoke:
                with self.assertRaises(module.PhotoshopDispatchError) as caught:module.execute(self.job,project_root=self.root,approved_root=self.run)
                self.assertFalse(caught.exception.outcome_unknown);invoke.assert_not_called()

    def test_timeout_wrong_binding_and_missing_artifacts_are_unknown(self):
        module=self.adapter()
        for reply in (TimeoutError('test'),self.receipt().replace('ps-test','other'),self.receipt()):
            (self.run/'photoshop-stages.log').unlink(missing_ok=True)
            (self.run/'photoshop-completion.receipt').unlink(missing_ok=True)
            with patch.object(module,'_invoke_com',**({'side_effect':reply} if isinstance(reply,Exception) else {'return_value':reply})):
                with self.assertRaises(module.PhotoshopDispatchError) as caught:module.execute(self.job,project_root=self.root,approved_root=self.run)
                self.assertTrue(caught.exception.outcome_unknown)

    def test_modified_input_cannot_be_sealed_as_success(self):
        module=self.adapter()
        def changed(script,timeout):
            reply=self.outputs(script,timeout);(self.run/'input.png').write_bytes(b'mutated');return reply
        with patch.object(module,'_invoke_com',side_effect=changed):
            with self.assertRaises(module.PhotoshopDispatchError) as caught:module.execute(self.job,project_root=self.root,approved_root=self.run)
            self.assertTrue(caught.exception.outcome_unknown)

    def test_wrong_native_header_or_preview_dimensions_are_unknown(self):
        module=self.adapter()
        for kind in ('psd','png'):
            for name in ('output.psd','output.png','photoshop-stages.log','photoshop-completion.receipt'):
                path=self.run/name
                if path.exists():path.unlink()
            def corrupted(script,timeout):
                reply=self.outputs(script,timeout)
                if kind=='psd':(self.run/'output.psd').write_bytes(b'not psd')
                else:Image.new('RGB',(7,6),'red').save(self.run/'output.png')
                return reply
            with patch.object(module,'_invoke_com',side_effect=corrupted):
                with self.assertRaises(module.PhotoshopDispatchError) as caught:module.execute(self.job,project_root=self.root,approved_root=self.run)
                self.assertTrue(caught.exception.outcome_unknown)

    def patch_job(self):
        """The same closed job plus one staged checkpoint and one leaf move."""
        checkpoint=self.run/'checkpoint.psd'
        header=bytearray(b'8BPS\x00\x01'+b'\x00'*8)
        header+=int(6).to_bytes(4,'big')+int(8).to_bytes(4,'big')      # height, width
        header+=b'\x00'*4
        checkpoint.write_bytes(bytes(header[:26])+b'synthetic, not a real PSD')
        job=dict(self.job)
        job.update(schemaVersion='design-lab/photoshop-patch-job/v1',checkpoint=str(checkpoint),
            checkpointSha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            patch=dict(kind='move',id='image',delta=[1,1]))
        return job

    def test_the_shipped_jobs_conform_to_the_contracts_they_declare(self):
        """Both closed shapes pass their own contract file, so a refusal below is a real refusal."""
        module=self.adapter()
        self.assertEqual(module._contract_problems(self.job),[])
        self.assertEqual(module._contract_problems(self.patch_job()),[])

    def test_a_layer_tree_that_is_not_a_list_is_refused_by_the_contract(self):
        """B2b (2026-10-22): `set(job)==required` judged the keys, never the value of `layers`.

        These shapes passed every hand check that a native job's `layers` gets -- execute()
        reads no field of it -- and were handed to Photoshop anyway. The contract file refuses
        them before the first COM call; the list-of-lists case is judged on the patch shape,
        whose own file says a layer is an object because native_patch_plan._photoshop_patch
        indexes every item.
        """
        module=self.adapter()
        cases=[(self.job,{'id':'image'}),(self.job,'image'),(self.patch_job(),[['id','image']])]
        for job,unshaped in cases:
            probe=dict(job);probe['layers']=unshaped
            with self.subTest(layers=unshaped,version=probe['schemaVersion']):
                self.assertTrue(module._contract_problems(probe),
                                f'layers={unshaped!r} passed the contract check')
                with patch.object(module,'_invoke_com') as invoke:
                    with self.assertRaises(module.PhotoshopDispatchError) as caught:
                        module.execute(probe,project_root=self.root,approved_root=self.run)
                    self.assertFalse(caught.exception.outcome_unknown)
                    invoke.assert_not_called()

    def test_every_version_the_adapter_compares_has_a_contract_file_on_disk(self):
        """A version added to the hand check without a contract file is caught here, not on a host."""
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
