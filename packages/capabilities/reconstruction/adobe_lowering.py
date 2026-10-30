# SPDX-License-Identifier: MIT
"""Explicit RIR -> native Illustrator lowering, with no silent style loss.

Absolute/relative M/L/C/Z contours, closed nonzero compound paths, groups, full
staged rasters and explicitly styled live text are currently representable.
Unsupported appearance requires a separately approved raster/vector fallback.
This module does not dispatch, grant rights, infer typography, or copy assets.
"""
import copy
import math
import re
from pathlib import Path
from PIL import Image

from .adobe_job import AdobeJobError, _inside


def require(ok, message):
    if not ok:
        raise AdobeJobError(message)


def fields(value, keys):
    require(isinstance(value,dict) and set(value)==set(keys.split()),'unexpected native object fields')


def number(value, low, high):
    require(type(value) in (int,float) and math.isfinite(value) and low<=value<=high,'native number out of range')


def vector(value, size, low=-16383, high=16383):
    require(isinstance(value,list) and len(value)==size,'invalid native vector')
    for v in value:number(v,low,high)


def color(value):
    require(isinstance(value,str) and re.fullmatch(r'#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}',value),'solid RGB hex fill required')
    value=value[1:]
    if len(value)==3:value=''.join(c*2 for c in value)
    return [int(value[i:i+2],16) for i in (0,2,4)]


def path_contours(data,height):
    require(isinstance(data,str) and 0<len(data)<=2_000_000,'invalid path data size')
    number(height,1,16383)
    token=re.compile(r'[MLCZmlcz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
    matches=list(token.finditer(data)); end=0; values=[]
    for match in matches:
        require(not data[end:match.start()].strip(' ,\t\r\n'),'unsupported path syntax')
        values.append(match.group());end=match.end()
    require(not data[end:].strip(' ,\t\r\n'),'unsupported path syntax')
    require(values and values[0] in ('M','m'),'path must start with moveto')
    points=[];contours=[];i=0;command=None;current=[0.,0.];start=None;total=0
    def coordinate(x,y):
        p=[float(x),height-float(y)];vector(p,2);return p
    def add(p):points.append(dict(anchor=p,left=p[:],right=p[:]))
    def finish(closed):
        require(len(points)>=2,'path needs two anchors')
        if closed and points[-1]['anchor']==points[0]['anchor']:
            points[0]['left']=points.pop()['left']
        require(len(points)>=2,'degenerate closed path')
        contours.append((points[:],closed));points.clear()
        require(len(contours)<=256,'contour complexity limit')
    while i<len(values):
        if values[i] in ('M','L','C','Z','m','l','c','z'):
            command=values[i];i+=1
            if command.upper()=='Z':
                require(bool(points),'close without active contour')
                finish(True);current=start[:];command=None;continue
        require(command is not None and command.upper() in ('M','L','C'),'missing path command')
        size=6 if command.upper()=='C' else 2
        require(i+size<=len(values) and all(v not in 'MLCZmlcz' for v in values[i:i+size]),'incomplete path command')
        v=[float(x) for x in values[i:i+size]];i+=size
        if command.islower():v=[x+current[j%2] for j,x in enumerate(v)]
        if command.upper()=='M':
            if points:finish(False)
            add(coordinate(*v));start=v[:];command='l' if command.islower() else 'L'
        elif command.upper()=='L':
            require(bool(points),'line without contour');add(coordinate(*v))
        else:
            require(bool(points),'curve without anchor')
            points[-1]['right']=coordinate(*v[:2]);add(coordinate(*v[4:]));points[-1]['left']=coordinate(*v[2:4])
        current=v[-2:];total+=1
        require(total<=10000,'path complexity limit')
    if points:finish(False)
    return contours


def path_points(data,height):
    contours=path_contours(data,height)
    require(len(contours)==1,'single contour required')
    return contours[0]


def lower_layers(rir,root,text_styles,*,project_root=None):
    height=rir['canvas']['height'];assets=[];used_styles=set()
    require(isinstance(text_styles,dict),'text styles must be explicit map')
    def contour(identity,data,fill,declared=None):
        contours=path_contours(data,height)
        if len(contours)>1:
            require(all(closed and len(points)>=3 for points,closed in contours),'compound contours must be closed with at least three anchors')
            require(declared is not False,'path closure metadata mismatch')
            return dict(id=identity,kind='compound',color=fill,contours=[
                dict(id=f'{identity}-c{i}',kind='path',points=points,closed=True,color=fill[:])
                for i,(points,closed) in enumerate(contours)])
        points,closed=contours[0]
        require(declared is None or declared==closed,'path closure metadata mismatch')
        return dict(id=identity,kind='path',points=points,closed=closed,color=fill)
    def rect(identity,b,fill):
        x,y,w,h=(b[k] for k in ('x','y','width','height'))
        require(w>0 and h>0,'empty rectangle')
        return contour(identity,f'M {x} {y} L {x+w} {y} L {x+w} {y+h} L {x} {y+h} Z',fill)
    def ordered(nodes):
        require(len({n['zOrder'] for n in nodes})==len(nodes),'ambiguous sibling zOrder')
        return sorted(nodes,key=lambda n:n['zOrder'])
    def lower(n,depth=0):
        require(depth<=8,'group depth limit')
        require(n['opacity']==1 and n['visible'] and not n['locked'] and n['blendMode']=='normal',
                'unsupported opacity/visibility/lock/blend; explicit fallback required')
        identity=n['id'];b=n['bounds'];kind=n['type']
        if kind=='group':
            return dict(id=identity,kind='group',items=[lower(c,depth+1) for c in ordered(n['children'])],mask=None)
        if kind=='text':
            require(n['text']['disposition']=='live','outlined/hybrid text requires explicit separate fallback')
            style=text_styles.get(identity)
            fields(style,'font size color');used_styles.add(identity)
            return dict(id=identity,kind='text',text=n['text']['content'],position=[b['x'],height-b['y']],**copy.deepcopy(style))
        if kind=='raster':
            r=n['raster'];require(r['alpha']==1 and not r['sourceMappings'],'raster remapping/alpha requires explicit preprocessed asset')
            owner=Path(project_root) if project_root is not None else Path(__file__).resolve().parents[3]
            source=_inside(owner/r['path'],root)
            require(source.is_file() and source.suffix.lower() in ('.png','.jpg','.jpeg'),'raster must be staged inside run root')
            require(source.stat().st_size<=32*1024*1024 and source.stat().st_nlink==1,'invalid raster size/link')
            with Image.open(source) as image:
                require(image.format in ('PNG','JPEG') and image.width*image.height<=25_000_000 and getattr(image,'n_frames',1)==1,'unsupported raster')
                require(r['crop']==dict(x=0,y=0,width=image.width,height=image.height),'crop must be materialized before host job')
                image.verify()
            asset_id='asset-'+identity;assets.append(dict(id=asset_id,path=str(source)))
            return dict(id=identity,kind='raster',assetId=asset_id,position=[b['x'],height-b['y']],width=b['width'],height=b['height'])
        style=n['style']
        require(style.get('stroke') in (None,'none') and style.get('strokeWidth',0)==0 and style.get('fillRule','nonzero')=='nonzero','stroke/fill-rule unsupported')
        fill=color(style.get('fill'))
        if kind=='path':item=contour(identity,n['geometry']['pathData'],fill,n['geometry'].get('closed'))
        else:
            p=n['primitive'];params=p['parameters']
            if p['kind']=='rect':
                require(not params,'rounded or parameterized rect unsupported');item=rect(identity,b,fill)
            elif p['kind']=='polygon':
                require(set(params)=={'points'} and len(params['points'])>=3,'polygon requires points')
                data=' '.join(('M' if i==0 else 'L')+f" {v['x']} {v['y']}" for i,v in enumerate(params['points']))+' Z'
                item=contour(identity,data,fill)
            else:raise AdobeJobError('primitive needs explicit path conversion')
        masks=n.get('masks',[])
        require(len(masks)<=1,'multiple masks unsupported')
        if masks:
            mask=masks[0];require(mask['operation']=='intersect' and mask['opacity']==1,'only opaque intersect mask supported')
            item=dict(id='masked-'+identity,kind='group',items=[item],mask=contour(mask['id'],mask['pathData'],[0,0,0],True))
        return item
    layers=[]
    if 'background' in rir['canvas']:
        layers.append(dict(id='canvas-background-layer',items=[rect('canvas-background',dict(x=0,y=0,width=rir['canvas']['width'],height=height),color(rir['canvas']['background']['color']))]))
    for index,n in enumerate(ordered(rir['layers'])):
        layers.append(dict(id='layer-'+str(index),items=[lower(n)]))
    require(set(text_styles)==used_styles,'unused text style binding')
    return layers,assets


def validate_objects(job,root):
    seen=set();asset_ids=set();count=0
    def identity(v):
        require(isinstance(v,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}',v) and v not in seen,'invalid/duplicate native ID')
        seen.add(v)
    require(isinstance(job['assets'],list) and len(job['assets'])<=500,'invalid assets')
    for asset in job['assets']:
        fields(asset,'id path');identity(asset['id']);asset_ids.add(asset['id'])
        require(isinstance(asset['path'],str),'invalid asset path');p=_inside(Path(asset['path']),root)
        require(p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg'),'missing raster')
    def item(n,depth):
        nonlocal count
        count+=1;require(depth<=8 and count<=10000,'object complexity limit')
        require(isinstance(n,dict),'object required');kind=n.get('kind')
        if kind=='path':
            fields(n,'id kind points closed color');require(type(n['closed']) is bool,'closed boolean required');vector(n['color'],3,0,255)
            require(isinstance(n['points'],list) and 2<=len(n['points'])<=10000,'invalid path size')
            for p in n['points']:
                fields(p,'anchor left right')
                for v in p.values():vector(v,2)
        elif kind=='text':
            fields(n,'id kind text position font size color');vector(n['position'],2);vector(n['color'],3,0,255);number(n['size'],1,1296)
            require(isinstance(n['text'],str) and 0<len(n['text'])<=10000 and isinstance(n['font'],str) and bool(n['font']),'invalid live text')
        elif kind=='compound':
            fields(n,'id kind contours color');vector(n['color'],3,0,255)
            require(isinstance(n['contours'],list) and 2<=len(n['contours'])<=256,'invalid compound size')
            for c in n['contours']:
                require(isinstance(c,dict) and c.get('kind')=='path' and c.get('closed') is True and c.get('color')==n['color'],'invalid compound contour')
                item(c,depth+1)
                require(len(c['points'])>=3,'compound contour needs three anchors')
            require(sum(len(c['points']) for c in n['contours'])<=10000,'compound point limit')
        elif kind=='raster':
            fields(n,'id kind assetId position width height');require(n['assetId'] in asset_ids,'unknown raster');vector(n['position'],2)
            number(n['width'],.01,16383);number(n['height'],.01,16383)
        elif kind=='group':
            fields(n,'id kind items mask');items(n['items'],depth+1)
            if n['mask'] is not None:
                require(isinstance(n['mask'],dict) and n['mask'].get('kind')=='path' and n['mask'].get('closed') is True,'closed path mask required');item(n['mask'],depth+1)
        else:raise AdobeJobError('unknown native kind')
        identity(n['id'])
    def items(values,depth):
        require(isinstance(values,list) and 1<=len(values)<=1000,'invalid native item count')
        for n in values:item(n,depth)
    require(isinstance(job['layers'],list) and 1<=len(job['layers'])<=100,'invalid layers')
    for layer in job['layers']:
        fields(layer,'id items');identity(layer['id']);items(layer['items'],0)
