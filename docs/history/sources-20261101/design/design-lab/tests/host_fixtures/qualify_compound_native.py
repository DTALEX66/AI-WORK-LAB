# SPDX-License-Identifier: MIT
"""Explicit source-tree native compound qualification; never a full-reference claim."""
import json
from pathlib import Path
import runpy
import sys
import uuid
import hashlib
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'packages/capabilities')]
from reconstruction.adobe_job import build_adobe_job
from design_lab.runtime.paths import resolve_paths


def main():
    paths=resolve_paths(project_root=ROOT)
    run=paths.task_dir('compound-native-20260908','run-'+uuid.uuid4().hex,evidence=True)
    run.mkdir(parents=True,exist_ok=False)
    def node(identity,z,geometry,color):
        return dict(id=identity,type='path',name=identity,opacity=1,
            bounds=dict(x=0,y=0,width=100,height=100),inferred=True,zOrder=z,
            visible=True,locked=False,blendMode='normal',masks=[],
            style=dict(fill=color),geometry=dict(pathData=geometry,closed=True))
    rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',
        canvas=dict(width=100,height=100,colorSpace='srgb'),layers=[
            node('backdrop',0,'M0 0 L100 0 L100 100 L0 100Z','#e05030'),
            node('ring',1,'M10 10 l80 0 0 80 -80 0z m20 20 l0 40 40 0 0 -40z','#123456')])
    traced = sys.argv[1:] == ['--real-trace']
    if sys.argv[1:] and not traced:raise ValueError('only --real-trace is supported')
    if traced:
        source=paths.checked_path(ROOT/'.project-local/task-artifacts/reference-qualification/behance-5783221/copy-icon-traced.svg')
        content=source.read_bytes()
        if hashlib.sha256(content).hexdigest()!='c23ed50452d78f74cabe971d55945b689c6e8e80e92399fe51543fae8b9aa4e8':
            raise ValueError('fixed diagnostic trace changed')
        document=ET.fromstring(content)
        rir['canvas'].update(width=210,height=200)
        rir['layers']=[node('backdrop',0,'M0 0 L210 0 L210 200 L0 200Z','#ffffff')]
        for i,element in enumerate(document):
            if element.tag!='{http://www.w3.org/2000/svg}path' or set(element.attrib)!={'d','fill'}:
                raise ValueError('unsupported trace element')
            rir['layers'].append(node('trace'+str(i),i+1,element.attrib['d'],element.attrib['fill']))
        for item in rir['layers']:item['bounds'].update(width=210,height=200)
        (run/'source-trace.svg').write_bytes(content)
    job=build_adobe_job(rir,run).to_dict()
    for name,value in [('source-rir.json',rir),('adobe-host-job.json',job)]:
        (run/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),mode='SOURCE_TREE_CONTROLLED_FIXTURE')),flush=True)
    sys.argv=[str(ROOT/'design-lab/tests/host_fixtures/qualify_native_tasks.py'),str(ROOT),
              'illustrator',str(run/'adobe-host-job.json')]
    runpy.run_path(sys.argv[0],run_name='__main__')
    if traced:
        print(json.dumps(dict(status='REAL_TRACE_NATIVE_READBACK',quality='NOT_ACCEPTED_EDGE_CLIPPED_DIAGNOSTIC')))
        return
    from PIL import Image
    with Image.open(job['targets']['png']) as image:
        pixels=image.convert('RGB')
        observed={name:pixels.getpixel(point) for name,point in
                  [('outside',(5,5)),('ring',(20,20)),('hole',(50,50))]}
    assert observed==dict(outside=(224,80,48),ring=(18,52,86),hole=(224,80,48)),observed
    (run/'hole-pixel-readback.json').write_text(json.dumps(observed),encoding='utf-8')
    print(json.dumps(dict(status='NONZERO_HOLE_PIXEL_PASS',observed=observed)))


if __name__=='__main__':main()
