# SPDX-License-Identifier: MIT
import base64
from contextlib import closing
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.service import ProjectService
from design_lab.image_assets import ImageAssets, ImageAssetError


class NativePlanTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.project-local/task-runtime/native-plan-tests';parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);(self.root/'AGENTS.md').write_text('# fixture',encoding='utf-8')
        env=patch.dict('os.environ',{'PROJECT_LOCAL_ROOT':str(self.root/'.project-local')});env.start();self.addCleanup(env.stop)
        self.service=ProjectService(self.root);self.project=self.service.create_project('Plan')['id']
        self.run=self.service.paths.category_dir('projects',self.project,'native-plans','fixture');self.run.mkdir(parents=True)
        buf=io.BytesIO();Image.new('RGBA',(8,6),(20,30,40,100)).save(buf,format='PNG');self.raw=buf.getvalue()
        self.asset=ImageAssets(self.service).import_image(self.project,base64.b64encode(self.raw).decode(),'fixture')['asset']
        self.rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',canvas=dict(width=8,height=6,colorSpace='srgb'),layers=[
            dict(id='image',name='image',type='raster',opacity=1,bounds=dict(x=0,y=0,width=8,height=6),inferred=True,
                 zOrder=0,visible=True,locked=False,blendMode='normal',raster=dict(path=self.asset['id'],
                 crop=dict(x=0,y=0,width=8,height=6),alpha=1,sourceMappings=[]))])

    def test_raster_id_is_resolved_to_verified_owned_input(self):
        from design_lab.native_plan import prepare_plan
        job=prepare_plan(self.service,self.project,'photoshop',self.rir,{},self.run)
        self.assertEqual(len(job['assets']),1)
        path=Path(job['assets'][0]['path'])
        self.assertTrue(path.is_relative_to(self.run))
        self.assertEqual(path.read_bytes(),self.raw)
        self.assertEqual(job['layers'][0]['kind'],'raster')
        self.assertEqual(self.rir['layers'][0]['raster']['path'],self.asset['id'])
        self.assertFalse((self.run/'master.psd').exists())

    def test_arbitrary_paths_and_other_project_assets_are_rejected(self):
        from design_lab.native_plan import prepare_plan
        other=self.service.create_project('Other')['id']
        for value in ('C:/private.png','../private.png','img-'+'0'*64):
            self.rir['layers'][0]['raster']['path']=value
            with self.assertRaises((ImageAssetError,ValueError)):
                prepare_plan(self.service,self.project,'photoshop',self.rir,{},self.run)
        self.rir['layers'][0]['raster']['path']=self.asset['id']
        with self.assertRaises((ImageAssetError,ValueError)):
            prepare_plan(self.service,other,'photoshop',self.rir,{},self.run)
        self.assertEqual(list(self.run.iterdir()),[])

    def test_illustrator_uses_same_owned_input_and_server_targets(self):
        from design_lab.native_plan import prepare_plan
        job=prepare_plan(self.service,self.project,'illustrator',self.rir,{},self.run)
        self.assertEqual(set(job['targets']),{'ai','png','svg'})
        self.assertTrue(all(Path(p).parent==self.run for p in job['targets'].values()))
        self.assertEqual(Path(job['assets'][0]['path']).read_bytes(),self.raw)
        self.assertEqual(job['layers'][0]['items'][0]['kind'],'raster')

    def test_modified_asset_bytes_are_rejected_without_staging(self):
        from design_lab.native_plan import prepare_plan
        import sqlite3
        with closing(sqlite3.connect(self.service.database)) as conn:
            path=conn.execute('SELECT f.path FROM artifact f JOIN asset_version v ON f.version_id=v.version_id WHERE v.asset_id=?',(self.asset['id'],)).fetchone()[0]
        Path(path).write_bytes(b'changed')
        with self.assertRaises(ImageAssetError):
            prepare_plan(self.service,self.project,'photoshop',self.rir,{},self.run)
        self.assertEqual(list(self.run.iterdir()),[])

    def test_nonempty_run_is_not_overwritten(self):
        from design_lab.native_plan import prepare_plan
        prior=self.run/'master.psd';prior.write_bytes(b'preserve existing project')
        with self.assertRaises(ValueError):
            prepare_plan(self.service,self.project,'photoshop',self.rir,{},self.run)
        self.assertEqual(prior.read_bytes(),b'preserve existing project')
        self.assertEqual(list(self.run.iterdir()),[prior])


if __name__ == '__main__':
    unittest.main()
