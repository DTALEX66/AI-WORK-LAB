# SPDX-License-Identifier: MIT
"""Fixed real-reference PSD candidate; inferred alpha, not source-layer recovery."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys
import uuid

import numpy as np
from PIL import Image, ImageFont

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'packages/capabilities')]
from reconstruction.adobe_job import build_photoshop_job
from design_lab.runtime.paths import resolve_paths


def white_to_alpha(image):
    """Infer maximal white removal in encoded RGB; preserve white composite.

    This is a chosen matte, not recovered physical foreground/alpha truth.
    Pure white becomes transparent, including intentional white inside icons.
    """
    rgb=np.asarray(image.convert('RGB')).astype(float)
    base=rgb.min(axis=2,keepdims=True)
    alpha=255-base
    foreground=np.divide((rgb-base)*255,alpha,out=np.zeros_like(rgb),where=alpha!=0)
    return Image.fromarray(np.concatenate([np.rint(foreground),alpha],axis=2).astype('uint8'))


def main():
    if sys.argv[1:] not in ([],['--execute']):raise ValueError('unsupported arguments')
    execute=bool(sys.argv[1:])
    paths=resolve_paths(project_root=ROOT)
    source=paths.checked_path(ROOT/'.project-local/task-artifacts/real-poster-20260908/run-3bc50140e7f44caca5393c29002c43f9')
    rir=json.loads((source/'source-rir.json').read_text(encoding='utf-8'))
    styles=json.loads((source/'text-styles.json').read_text(encoding='utf-8'))
    regions=json.loads((source/'segmentation.json').read_text(encoding='utf-8'))
    run=paths.task_dir('real-poster-ps-20260908','run-'+uuid.uuid4().hex,evidence=True)
    run.mkdir(parents=True,exist_ok=False)
    children=[copy.deepcopy(n) for n in rir['layers'][0]['children'] if n['type']!='path']
    assert len(children)==188 and len(styles)==99 and len(regions)==44
    # PS point text uses baseline. This substituted-font estimate is explicit,
    # never a claim of verified host glyph bounds or exact source typography.
    offsets=[]
    for n in children:
        if n['type']!='text':continue
        style=styles[n['id']]
        font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if style['font']=='Arial-BoldMT' else 'C:/Windows/Fonts/arial.ttf',1000)
        ink=font.getbbox(n['text']['content'],anchor='ls')
        offset=-ink[1]*style['size']/1000
        n['bounds']['y']+=offset
        offsets.append(dict(id=n['id'],baseline_offset=offset,method='PIL substituted-font ink estimate'))
    evidence=[]
    for region in regions:
        src=source/(region['id']+'.png')
        if hashlib.sha256(src.read_bytes()).hexdigest()!=region['input_sha256']:raise ValueError('source crop changed')
        with Image.open(src) as image:
            rgb=image.convert('RGB');alpha=white_to_alpha(rgb)
        composite=Image.alpha_composite(Image.new('RGBA',rgb.size,'white'),alpha).convert('RGB')
        error=int(np.abs(np.asarray(composite).astype(int)-np.asarray(rgb)).max())
        if error>1:raise ValueError('white composite changed')
        dest=run/(region['id']+'-alpha.png');alpha.save(dest)
        x,y,right,bottom=region['box']
        children.append(dict(id=region['id'],name=region['id'],type='raster',opacity=1,
            bounds=dict(x=x,y=y,width=right-x,height=bottom-y),inferred=True,zOrder=len(children),
            visible=True,locked=False,blendMode='normal',
            raster=dict(path=dest.relative_to(ROOT).as_posix(),alpha=1,sourceMappings=[],
                        crop=dict(x=0,y=0,width=rgb.width,height=rgb.height))))
        evidence.append(dict(id=region['id'],source_sha256=region['input_sha256'],
            alpha_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),white_composite_max_error=error,
            alpha_extrema=alpha.getchannel('A').getextrema()))
    for i,n in enumerate(children):n['zOrder']=i
    rir['layers'][0]['children']=children
    job=build_photoshop_job(rir,run,text_styles=styles,project_root=ROOT)
    for name,data in [('source-rir.json',rir),('text-styles.json',styles),('alpha-evidence.json',evidence),
                      ('baseline-estimates.json',offsets),('photoshop-job.json',job)]:
        (run/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),live_text=99,independent_rasters=44,rectangular_pixel_fills=89,
        quality='UNVERIFIED_OCR_SUBSTITUTED_FONTS_INFERRED_ALPHA')),flush=True)
    if execute:
        sys.argv=[str(ROOT/'design-lab/tests/host_fixtures/qualify_native_tasks.py'),str(ROOT),'photoshop',str(run/'photoshop-job.json')]
        runpy.run_path(sys.argv[0],run_name='__main__')


if __name__=='__main__':main()
