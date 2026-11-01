# SPDX-License-Identifier: MIT
"""Prepare a fresh RIR-derived Photoshop qualification job, never dispatch.

Synthetic geometry plus a staged fixture image. This is producer/consumer
qualification, not automatic reference decomposition or a complex-design E3.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[3]
INSTALLED='--installed' in sys.argv[1:]
if not INSTALLED:
    sys.path.insert(0,str(ROOT/'src'))
    sys.path.insert(0,str(ROOT/'packages/capabilities'))
from design_lab.runtime.paths import resolve_paths
if INSTALLED:
    import design_lab.reconstruction.adobe_job as producer
else:
    import reconstruction.adobe_job as producer


def prepare():
    paths=resolve_paths(project_root=ROOT)
    run=paths.task_dir('photoshop-rir-20260908','run-'+uuid.uuid4().hex,evidence=True)
    run.mkdir(parents=True,exist_ok=False)
    source=paths.checked_path(ROOT/'.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/fixture.png')
    shutil.copyfile(source,run/'input.png')
    from PIL import Image
    with Image.open(run/'input.png') as image:iw,ih=image.size
    def node(identity,kind,x,y,w,h,z,**extra):
        return dict(id=identity,name=identity,type=kind,opacity=1,bounds=dict(x=x,y=y,width=w,height=h),
                    inferred=True,zOrder=z,visible=True,locked=False,blendMode='normal',**extra)
    rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',canvas=dict(width=800,height=600,colorSpace='srgb'),layers=[
        node('background','primitive',0,0,800,600,0,primitive=dict(kind='rect',parameters={}),style=dict(fill='#F1F3EF'),masks=[]),
        node('title','text',45,80,710,45,2,text=dict(content='RIR TO PHOTOSHOP',disposition='live',fontCandidates=[],outlineFallback=dict(available=False,pathData=None))),
        node('panel','primitive',45,130,710,365,1,primitive=dict(kind='rect',parameters={}),style=dict(fill='#146E65'),
             masks=[dict(id='panel-mask',pathData='M 45 130 L 755 130 L 755 495 L 45 495 Z',operation='intersect',opacity=1)]),
        node('image','raster',300,175,210,210,3,raster=dict(path=(run/'input.png').relative_to(ROOT).as_posix(),crop=dict(x=0,y=0,width=iw,height=ih),alpha=1,sourceMappings=[]))])
    styles={'title':dict(font='ArialMT',size=32,color=[23,45,60])}
    job=producer.build_photoshop_job(rir,run,text_styles=styles,project_root=ROOT)
    for name,data in [('rir.json',rir),('text-styles.json',styles),('job.json',job)]:
        (run/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
    proof=dict(rir_sha256=producer.canonical_rir_hash(rir,project_root=ROOT),job_sha256=hashlib.sha256((run/'job.json').read_bytes()).hexdigest(),
               input_sha256=hashlib.sha256((run/'input.png').read_bytes()).hexdigest(),
               producer_sha256=hashlib.sha256(Path(producer.__file__).read_bytes()).hexdigest(),
               producer_module=producer.__file__,installed=INSTALLED,
               qualification='synthetic RIR; no inferred source-layer or Human Jury claim')
    (run/'producer-binding.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),job=str(run/'job.json'))))


if __name__=='__main__':prepare()
