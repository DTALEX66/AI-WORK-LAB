# SPDX-License-Identifier: MIT
"""A common RIR must reach Photoshop without hand-authored host jobs."""
import copy
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'packages/capabilities'))


class PhotoshopRirTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.project-local/task-runtime/photoshop-rir-tests';parent.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(temporary.cleanup);self.run=Path(temporary.name)

    def builder(self):
        module=importlib.import_module('reconstruction.adobe_job')
        self.assertTrue(hasattr(module,'build_photoshop_job'),'RIR has no Photoshop producer')
        return module.build_photoshop_job

    def scene(self):
        base=dict(id='panel',name='panel',type='primitive',opacity=1,bounds=dict(x=4,y=5,width=20,height=10),
                  inferred=True,zOrder=0,visible=True,locked=False,blendMode='normal',
                  primitive=dict(kind='rect',parameters={}),style=dict(fill='#123456'),masks=[])
        text={k:copy.deepcopy(v) for k,v in base.items() if k not in ('primitive','style','masks')}
        text.update(id='title',type='text',zOrder=1,text=dict(content='Editable',disposition='live',fontCandidates=[],
                    outlineFallback=dict(available=False,pathData=None)))
        return dict(schemaVersion='design-lab/reconstruction-ir/v1',canvas=dict(width=64,height=48,colorSpace='srgb'),layers=[text,base])

    def test_text_rect_coordinates_and_order_reach_actual_jsx_validator(self):
        build=self.builder();rir=self.scene()
        job=build(rir,self.run,text_styles={'title':dict(font='ArialMT',size=12,color=[0,0,0])})
        self.assertEqual([n['id'] for n in job['layers']],['panel','title'])
        self.assertEqual(job['layers'][0],dict(id='panel',kind='fill',bounds=[4,5,20,10],color=[18,52,86]))
        self.assertEqual(job['layers'][1]['position'],[4,5])
        self.assertEqual(job['layers'][1]['text'],'Editable')
        node=shutil.which('node')
        if not node:self.skipTest('Node needed for actual JSX validation')
        script=r"""const fs=require('fs'),vm=require('vm');const j=JSON.parse(fs.readFileSync(0,'utf8'));
if(!/^[A-Za-z]:/.test(j.runRoot))j.runRoot='D:/fixture';
const c={File:p=>({fsName:p,exists:false}),Folder:p=>({exists:p===j.runRoot}),app:{fonts:{getByName:n=>({name:n})}},payload:JSON.stringify(j)};
vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^#target.*$/m,''),c);
vm.runInContext('var j=JSON.parse(payload);psValidate(j,j.runRoot)',c);console.log('VALID');"""
        result=subprocess.run([node,'-e',script,str(ROOT/'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx')],
                              input=json.dumps(job),capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'VALID')
        self.assertFalse((self.run/'master.psd').exists())

    def test_transparent_raster_and_rectangle_mask_are_independent(self):
        from PIL import Image
        build=self.builder();rir=self.scene();rir['layers']=rir['layers'][1:]
        shape=rir['layers'][0];shape['masks']=[dict(id='clip',pathData='M 4 5 L 24 5 L 24 15 L 4 15 Z',operation='intersect',opacity=1)]
        source=self.run/'source.png';Image.new('RGBA',(8,6),(20,30,40,100)).save(source)
        raster={k:copy.deepcopy(v) for k,v in shape.items() if k not in ('primitive','style','masks')}
        raster.update(id='image',type='raster',zOrder=1,raster=dict(path=source.relative_to(ROOT).as_posix(),crop=dict(x=0,y=0,width=8,height=6),alpha=1,sourceMappings=[]))
        rir['layers'].append(raster);job=build(rir,self.run)
        self.assertEqual(job['layers'][0]['mask'],[4,5,20,10])
        self.assertEqual(job['layers'][0]['children'][0]['kind'],'fill')
        self.assertEqual(job['layers'][1]['position'],[4,5])
        self.assertEqual(job['assets'],[dict(id='asset-image',path=str(source))])

    def test_compound_is_explicitly_rejected_without_writes(self):
        from reconstruction.adobe_job import AdobeJobError
        rir=self.scene();rir['layers']=rir['layers'][1:]
        item=rir['layers'][0];del item['primitive']
        item.update(type='path',geometry=dict(
            pathData='M4 5 L24 5 L24 15 L4 15Z M8 8 L8 12 L20 12 L20 8Z',closed=True))
        with self.assertRaises(AdobeJobError):self.builder()(rir,self.run)
        self.assertEqual(list(self.run.iterdir()),[])

    def test_curve_and_existing_output_are_rejected_without_writes(self):
        from reconstruction.adobe_job import AdobeJobError
        build=self.builder();rir=self.scene();rir['layers']=rir['layers'][1:]
        n=rir['layers'][0];del n['primitive'];n.update(type='path',geometry=dict(pathData='M 4 5 C 8 1 20 1 24 5 L 24 15 L 4 15 Z',closed=True))
        with self.assertRaises(AdobeJobError):build(rir,self.run)
        self.assertEqual(list(self.run.iterdir()),[])
        (self.run/'master.psd').write_bytes(b'preserve')
        with self.assertRaises(AdobeJobError):build(self.scene(),self.run,text_styles={'title':dict(font='ArialMT',size=12,color=[0,0,0])})
        self.assertEqual((self.run/'master.psd').read_bytes(),b'preserve')


if __name__ == '__main__':
    unittest.main()
