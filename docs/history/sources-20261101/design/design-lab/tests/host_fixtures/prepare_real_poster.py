# SPDX-License-Identifier: MIT
"""Fixed raster-only Behance poster reconstruction candidate, not acceptance.

No source PDF text/vector extraction. Graphics are individually traced;
OCR lines remain live text with explicitly substituted fonts. Default only
prepares a closed job; --execute runs the durable source-tree native adapter.
"""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'packages/capabilities')]
from PIL import Image, ImageFont
import numpy as np
from reconstruction.adobe_job import build_adobe_job
from reconstruction.adobe_lowering import path_contours
from design_lab.runtime.paths import resolve_paths


def bands(values):
    return [(int(v[0]),int(v[-1])+1) for v in
            np.split(values,np.flatnonzero(np.diff(values)>1)+1) if len(v)]


def main():
    if sys.argv[1:] not in ([],['--execute']):raise ValueError('unsupported arguments')
    execute=bool(sys.argv[1:])
    paths=resolve_paths(project_root=ROOT)
    source=paths.checked_path(ROOT/'.project-local/task-artifacts/reference-qualification/behance-5783221')
    raster=source/'publisher-3000.png'
    assert hashlib.sha256(raster.read_bytes()).hexdigest()=='5e53676d6c62826d374e81b23958444250c3c7bd57015ff913e98c93b4307e43'
    tracer=Path('D:/All projects/Design External Configuration/toolchains/vtracer/1.0.0-alpha.3/vtracer.exe')
    expected='83d9df564119f1d21719f358c02b77372dd40e34373cc7a47b9dcc3014e7c587'
    if hashlib.sha256(tracer.read_bytes()).hexdigest()!=expected:raise ValueError('tracer changed')
    run=paths.task_dir('real-poster-20260908','run-'+uuid.uuid4().hex,evidence=True)
    run.mkdir(parents=True,exist_ok=False)
    image=Image.open(raster).convert('RGB');a=np.asarray(image.convert('L'))
    horizontal=bands(np.flatnonzero((a<80).sum(axis=1)>1100))
    if len(horizontal)!=18:raise ValueError('fixed six-row grid not detected')
    layers=[];styles={};regions=[];audit=[]
    def node(identity,kind,bounds,**extra):
        value=dict(id=identity,type=kind,name=identity,opacity=1,
            bounds=dict(zip(('x','y','width','height'),bounds)),inferred=True,
            zOrder=len(layers),visible=True,locked=False,blendMode='normal',**extra)
        layers.append(value);return value
    def rect(identity,x,y,w,h):
        node(identity,'primitive',[x,y,w,h],primitive=dict(kind='rect',parameters={}),
             style=dict(fill='#000000'),masks=[])
    for row in range(6):
        top,middle,bottom=horizontal[row*3:row*3+3]
        vertical=bands(np.flatnonzero((a[top[0]:middle[0]]<80).mean(axis=0)>.97))
        if len(vertical)<8:raise ValueError('grid columns missing')
        for i,(x,right) in enumerate(vertical):rect(f'r{row}-v{i}',x,top[0],right-x,bottom[1]-top[0])
        for i,(y,end) in enumerate((top,middle,bottom)):
            for j,(x,right) in enumerate([(vertical[0][0],vertical[1][1]),(vertical[2][0],vertical[-1][1])]):
                rect(f'r{row}-h{i}-{j}',x,y,right-x,end-y)
        regions.append((f'r{row}-license',vertical[0][1]+2,top[1]+2,vertical[1][0]-2,top[0]+160))
        for col in range(2,len(vertical)-1):
            regions.append((f'r{row}-icon{col}',vertical[col][1],top[1],vertical[col+1][0],middle[0]))
    # Three brand graphics are explicitly vector logos, not editable body text.
    regions.extend([('brand-header',170,169,883,291),('brand-footer',1538,2748,1753,2808),
                    ('brand-centre',1884,2690,1981,2764)])
    for identity,x,y,right,bottom in regions:
        crop=run/(identity+'.png');svg=run/(identity+'.svg')
        image.crop((x,y,right,bottom)).save(crop)
        result=subprocess.run([str(tracer),'--input',str(crop),'--output',str(svg),
            '--preset','bw','--mode','spline','--filter-speckle','2','--path-precision','3'],
            capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=60)
        if result.returncode:raise RuntimeError('tracer failed: '+identity)
        elements=ET.fromstring(svg.read_bytes())
        count=0
        for index,element in enumerate(elements):
            if element.tag!='{http://www.w3.org/2000/svg}path' or set(element.attrib)!={'d','fill'}:
                raise ValueError('unsupported traced SVG object')
            contours=path_contours(element.attrib['d'],bottom-y);parts=[]
            def xy(p):return f'{p[0]+x:.4f} {bottom-p[1]:.4f}'
            for points,closed in contours:
                if not closed:raise ValueError('unexpected open trace')
                parts.append('M'+xy(points[0]['anchor']))
                for previous,current in zip(points,points[1:]+points[:1]):
                    parts.append('C'+xy(previous['right'])+' '+xy(current['left'])+' '+xy(current['anchor']))
                parts.append('Z')
            node(identity+'-p'+str(index),'path',[x,y,right-x,bottom-y],
                 geometry=dict(pathData=' '.join(parts),closed=True),
                 style=dict(fill=element.attrib['fill']),masks=[])
            count+=1
        audit.append(dict(id=identity,box=[x,y,right,bottom],path_count=count,
            input_sha256=hashlib.sha256(crop.read_bytes()).hexdigest(),
            trace_sha256=hashlib.sha256(svg.read_bytes()).hexdigest()))
    ocr_path=source/'highres-20260907T200935782054Z/results.json'
    predictions=json.loads(ocr_path.read_text(encoding='utf-8'))['predictions']
    excluded=[]
    for i,prediction in enumerate(predictions):
        poly=np.array(prediction['polygon']);x,y=poly.min(axis=0);right,bottom=poly.max(axis=0)
        cx,cy=(x+right)/2,(y+bottom)/2
        region=next((r[0] for r in regions if r[1]<=cx<=r[3] and r[2]<=cy<=r[4]),None)
        if region:excluded.append(dict(index=i,region=region,text=prediction['text']));continue
        identity='ocr-'+str(i)
        is_label=any(top[0]<cy<end[1] for top,mid,end in [horizontal[j:j+3] for j in range(0,18,3)])
        font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if is_label else 'C:/Windows/Fonts/arial.ttf',100)
        size=max(8,min((bottom-y)*1.15,(right-x)*100/max(1,font.getlength(prediction['text']))))
        node(identity,'text',[float(x),float(y),float(right-x),float(bottom-y)],
            text=dict(content=prediction['text'],disposition='live',fontCandidates=[],
                      outlineFallback=dict(available=False,pathData=None)))
        styles[identity]=dict(font='Arial-BoldMT' if is_label else 'ArialMT',size=float(size),color=[0,0,0])
    object_count=len(layers)
    content=dict(id='poster-objects',name='Poster objects',type='group',opacity=1,
        bounds=dict(x=0,y=0,width=2155,height=3000),inferred=True,zOrder=0,
        visible=True,locked=False,blendMode='normal',children=layers)
    rir=dict(schemaVersion='design-lab/reconstruction-ir/v1',canvas=dict(width=2155,height=3000,
        colorSpace='srgb',background=dict(color='#ffffff',recorded=True)),layers=[content])
    # Preserve preparation evidence even if the host contract rejects a contour.
    for name,value in [('source-rir.json',rir),('text-styles.json',styles),('segmentation.json',audit),
                       ('excluded-ocr.json',excluded)]:
        (run/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),objects=object_count,live_text=len(styles),
        graphics_regions=len(regions),quality='UNVERIFIED_OCR_AND_SUBSTITUTED_FONTS')),flush=True)
    job=build_adobe_job(rir,run,text_styles=styles).to_dict()
    job_path=run/'adobe-host-job.json';job_path.write_text(json.dumps(job,indent=2),encoding='utf-8')
    if execute:
        sys.argv=[str(ROOT/'design-lab/tests/host_fixtures/qualify_native_tasks.py'),str(ROOT),'illustrator',str(job_path)]
        runpy.run_path(sys.argv[0],run_name='__main__')


if __name__=='__main__':main()
