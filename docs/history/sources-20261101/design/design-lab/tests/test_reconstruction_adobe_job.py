# SPDX-License-Identifier: MIT
"""Behavioral contracts for closed Adobe reconstruction host jobs."""
from __future__ import annotations

import shutil
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))
RUNTIME_ROOT = PROJECT_ROOT / ".project-local" / "task-runtime" / "adobe-job-tests"


class AdobeHostJobTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
        RUNTIME_ROOT.mkdir(parents=True)
        self.rir = {
            "schemaVersion": "design-lab/reconstruction-ir/v1",
            "canvas": {"width": 64, "height": 48, "colorSpace": "srgb"},
            "layers": [dict(id='base',type='primitive',name='base',opacity=1,
                bounds=dict(x=0,y=0,width=64,height=48),inferred=True,zOrder=0,
                visible=True,locked=False,blendMode='normal',
                primitive=dict(kind='rect',parameters={}),style=dict(fill='#ffffff'),masks=[])],
        }

    def tearDown(self) -> None:
        shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)

    def test_job_targets_are_run_relative_and_hash_bound(self) -> None:
        """Changing the RIR or escaping the run root must invalidate the immutable host job."""
        from reconstruction.adobe_job import build_adobe_job, canonical_rir_hash

        job = build_adobe_job(self.rir, RUNTIME_ROOT)

        self.assertEqual(job.rir_hash, canonical_rir_hash(self.rir))
        self.assertTrue(all(path.is_relative_to(RUNTIME_ROOT) for path in job.target_paths()))
        self.assertEqual(job.artboard, {"width": 64, "height": 48})

    def test_unknown_host_operation_is_rejected(self) -> None:
        """No job may invoke menu commands, shell execution, or an unlisted host action."""
        from reconstruction.adobe_job import AdobeJobError, build_adobe_job, validate_adobe_job

        job = build_adobe_job(self.rir, RUNTIME_ROOT).to_dict()
        job["operations"] = ["createDocument", "runMenuCommand"]

        with self.assertRaises(AdobeJobError):
            validate_adobe_job(job)

    def scene(self):
        rir = copy.deepcopy(self.rir)
        base = dict(name='fixture', opacity=1, bounds=dict(x=4,y=5,width=20,height=10),
                    inferred=True,zOrder=0,visible=True,locked=False,blendMode='normal')
        rir['layers'] = [dict(base, id='curve',type='path',
            geometry=dict(pathData='M 4 5 C 8 1 20 1 24 5 L 24 15 L 4 15 Z',closed=True),
            style=dict(fill='#123456'),masks=[])]
        return rir

    def test_python_payload_passes_actual_jsx_validation(self):
        """Catch producer/consumer drift, not separately handwritten valid jobs."""
        from reconstruction.adobe_job import build_adobe_job
        node = shutil.which('node')
        if not node:
            self.skipTest('Node required for JSX cross-runtime test')
        job = build_adobe_job(self.scene(), RUNTIME_ROOT).to_dict()
        script = r'''
const fs=require('fs'),vm=require('vm');
const generated=JSON.parse(fs.readFileSync(0,'utf8'));
// On POSIX CI, map only filesystem paths to a synthetic Windows mount.
// Windows qualification uses the unmodified producer paths and actual files.
if(!/^[A-Za-z]:/.test(generated.runRoot)){
 generated.runRoot='D:/cross-platform-qualification';
 for(const kind of Object.keys(generated.targets))generated.targets[kind]=generated.runRoot+'/output.'+kind;
}
const payload=JSON.stringify(generated),root=generated.runRoot;
const context={File:p=>({fsName:p,exists:fs.existsSync(p)}),
 Folder:p=>({fsName:p,exists:p===root}),app:{textFonts:{getByName:n=>({name:n})}},payload,root};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),context);
vm.runInContext('validateJob(JSON.parse(payload),root)',context);
console.log('PYTHON_TO_JSX=PASS');
'''
        result = subprocess.run([node,'-e',script,str(PROJECT_ROOT/'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx')],
                                input=json.dumps(job),capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        points=job['layers'][0]['items'][0]['points']
        self.assertEqual(points[0],dict(anchor=[4,43],left=[4,43],right=[8,47]))
        self.assertEqual(points[1],dict(anchor=[24,43],left=[20,47],right=[24,43]))
        self.assertEqual(job['layers'][0]['items'][0]['color'],[18,52,86])

    def test_unsupported_appearance_is_not_silently_dropped(self):
        from reconstruction.adobe_job import AdobeJobError, build_adobe_job
        for change in (lambda n:n.update(opacity=.5),lambda n:n.update(visible=False),
                       lambda n:n.update(locked=True),lambda n:n.update(blendMode='multiply'),
                       lambda n:n['style'].update(stroke='#000',strokeWidth=2),
                       lambda n:n['style'].update(fill='url(#gradient)'),
                       lambda n:n['geometry'].update(pathData='M 1 1 A 3 3 0 0 0 5 5 Z'),
                       lambda n:n['geometry'].update(pathData='M 1 1 L 5 5 Z M 8 8 L 9 9 Z')):
            rir=self.scene();change(rir['layers'][0])
            with self.subTest(node=rir['layers'][0]):
                with self.assertRaises(AdobeJobError):build_adobe_job(rir,RUNTIME_ROOT)

    def test_nested_rect_and_explicit_live_text_keep_z_order(self):
        from reconstruction.adobe_job import AdobeJobError, build_adobe_job
        rir=self.scene(); text=copy.deepcopy(rir['layers'][0])
        for key in ('geometry','style','masks'):del text[key]
        text.update(id='title',type='text',zOrder=2,text=dict(content='Editable',disposition='live',
            fontCandidates=[],outlineFallback=dict(available=False,pathData=None)))
        rect=copy.deepcopy(rir['layers'][0]);del rect['geometry']
        rect.update(id='box',type='primitive',zOrder=1,primitive=dict(kind='rect',parameters={}))
        rir['layers']=[text,rect,rir['layers'][0]]
        with self.assertRaises(AdobeJobError):build_adobe_job(rir,RUNTIME_ROOT)
        job=build_adobe_job(rir,RUNTIME_ROOT,text_styles={'title':dict(font='ArialMT',size=12,color=[0,0,0])}).to_dict()
        self.assertEqual([v['items'][0]['id'] for v in job['layers']],['curve','box','title'])
        self.assertEqual(job['layers'][2]['items'][0]['position'],[4,43])
        self.assertEqual(job['layers'][2]['items'][0]['font'],'ArialMT')

    def test_job_does_not_alias_input_and_rejects_tampered_payload(self):
        from reconstruction.adobe_job import AdobeJobError,build_adobe_job,validate_adobe_job
        rir=self.scene();job=build_adobe_job(rir,RUNTIME_ROOT)
        rir['layers'][0]['geometry']['pathData']='M 0 0 L 1 1'
        self.assertEqual(job.to_dict()['layers'][0]['items'][0]['points'][0]['anchor'],[4,43])
        for change in (lambda j:j.update(rirHash='0'*64),lambda j:j['artboard'].update(colorSpace='RGB'),
                       lambda j:j['targets'].update(ai=str(RUNTIME_ROOT/'..'/'escape.ai')),
                       lambda j:j['layers'][0]['items'][0].update(command='run'),
                       lambda j:j['authorization'].update(required=1)):
            data=job.to_dict();change(data)
            with self.assertRaises(AdobeJobError):validate_adobe_job(data)

    def test_group_mask_and_staged_transparent_raster_are_lowered(self):
        from PIL import Image
        from reconstruction.adobe_job import AdobeJobError,build_adobe_job
        source=RUNTIME_ROOT/'input.png';Image.new('RGBA',(8,6),(255,0,0,120)).save(source)
        rir=self.scene();shape=rir['layers'][0]
        shape['masks']=[dict(id='clip',pathData='M 4 5 L 24 5 L 24 15 L 4 15 Z',operation='intersect',opacity=1)]
        raster={k:copy.deepcopy(v) for k,v in shape.items() if k not in ('geometry','style','masks')}
        raster.update(id='image',type='raster',zOrder=1,raster=dict(path=source.relative_to(PROJECT_ROOT).as_posix(),
            crop=dict(x=0,y=0,width=8,height=6),alpha=1,sourceMappings=[]))
        group={k:copy.deepcopy(v) for k,v in shape.items() if k not in ('geometry','style','masks')}
        group.update(id='group',type='group',children=[shape,raster]);rir['layers']=[group]
        job=build_adobe_job(rir,RUNTIME_ROOT).to_dict()
        items=job['layers'][0]['items'][0]['items']
        self.assertEqual(items[0]['mask']['points'][0]['anchor'],[4,43])
        self.assertEqual(items[1]['assetId'],'asset-image')
        self.assertEqual(job['assets'],[dict(id='asset-image',path=str(source))])
        raster['raster']['crop']['width']=4
        with self.assertRaises(AdobeJobError):build_adobe_job(rir,RUNTIME_ROOT)

    def test_empty_duplicate_order_and_existing_output_fail_closed(self):
        from reconstruction.adobe_job import AdobeJobError,build_adobe_job
        rir=self.scene();rir['layers']=[]
        with self.assertRaises(AdobeJobError):build_adobe_job(rir,RUNTIME_ROOT)
        rir=self.scene();other=copy.deepcopy(rir['layers'][0]);other['id']='second';rir['layers'].append(other)
        with self.assertRaises(AdobeJobError):build_adobe_job(rir,RUNTIME_ROOT)
        (RUNTIME_ROOT/'master.ai').write_bytes(b'preserve')
        with self.assertRaises(AdobeJobError):build_adobe_job(self.scene(),RUNTIME_ROOT)
        self.assertEqual((RUNTIME_ROOT/'master.ai').read_bytes(),b'preserve')


if __name__ == "__main__":
    unittest.main()
