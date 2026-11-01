# SPDX-License-Identifier: MIT
"""RIR lowering must use the caller's project, never the package location."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]


class ExplicitReconstructionOwnerTests(unittest.TestCase):
    def test_other_project_raster_builds_both_hosts_and_rejects_escape(self):
        parent=ROOT/'.project-local/task-runtime/rir-owner-tests';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            owner=Path(directory);(owner/'AGENTS.md').write_text('# test owner',encoding='utf-8')
            run=owner/'.project-local/run';run.mkdir(parents=True)
            code=r'''
import copy,json,sys
from pathlib import Path
from PIL import Image
if sys.argv[4]=='installed':
 from design_lab.reconstruction.adobe_job import build_adobe_job,build_photoshop_job
 assert sys.argv[1] not in sys.path and sys.argv[2] not in sys.path
 try:build_photoshop_job({},Path(sys.argv[3]))
 except ValueError:pass
 else:raise AssertionError('implicit installed project root accepted')
else:
 sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2])
 from reconstruction.adobe_job import build_adobe_job,build_photoshop_job
owner=Path(sys.argv[3]);run=owner/'.project-local/run';Image.new('RGBA',(8,6),(2,3,4,100)).save(run/'input.png')
rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',canvas=dict(width=64,height=48,colorSpace='srgb'),layers=[
dict(id='image',type='raster',name='image',opacity=1,bounds=dict(x=4,y=5,width=20,height=10),inferred=True,zOrder=0,
visible=True,locked=False,blendMode='normal',raster=dict(path='.project-local/run/input.png',crop=dict(x=0,y=0,width=8,height=6),alpha=1,sourceMappings=[]))])
ai=build_adobe_job(rir,run,project_root=owner).to_dict();ps=build_photoshop_job(rir,run,project_root=owner)
assert ai['assets'][0]['path']==ps['assets'][0]['path']==str(run/'input.png')
assert ai['layers'][0]['items'][0]['position']==[4,43] and ps['layers'][0]['position']==[4,5]
for bad in ('../outside.png','https://example.invalid/x.png','C:/outside.png'):
 value=copy.deepcopy(rir);value['layers'][0]['raster']['path']=bad
 try:build_photoshop_job(value,run,project_root=owner)
 except ValueError:pass
 else:raise AssertionError('escaped input accepted')
try:build_photoshop_job(rir,owner,project_root=owner)
except ValueError:pass
else:raise AssertionError('run outside project-local accepted')
print(json.dumps({'status':'OWNER_BOUND','outputs':sorted(p.name for p in run.iterdir())}))
'''
            env=dict(os.environ);env.pop('PROJECT_LOCAL_ROOT',None)
            mode='installed' if os.environ.get('DL_TEST_INSTALLED_RIR')=='1' else 'source'
            result=subprocess.run([sys.executable,'-I','-B','-c',code,str(ROOT/'src'),str(ROOT/'packages/capabilities'),str(owner),mode],
                                  cwd=owner,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),{'status':'OWNER_BOUND','outputs':['input.png']})


if __name__ == '__main__':
    unittest.main()
