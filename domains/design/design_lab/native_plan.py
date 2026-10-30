# SPDX-License-Identifier: MIT
"""Lower client object plans using owned asset IDs, never client filesystem paths."""
import base64
import json
import os
import re

from .image_assets import ImageAssets, ImageAssetError
from .reconstruction.contracts import validate_rir
from .reconstruction.adobe_job import build_adobe_job, build_photoshop_job


def prepare_plan(service,project_id,host,rir,text_styles,run_root):
    """Internal staging step; caller owns the new empty project run directory.

    Raster.path in the client plan is an imported img-ID. The returned job is
    internal only. This does not dispatch a host or approve quality/rights.
    Failed staging is retained for caller reconciliation, never reported ready.
    """
    images=ImageAssets(service);images.require_project(project_id)
    if host not in ('photoshop','illustrator'):raise ValueError('unsupported host')
    owner=service.paths.project_root
    root=service.paths.checked_path(run_root)
    allowed=service.paths.category_dir('projects',project_id,'native-plans')
    if root==allowed or not root.is_relative_to(allowed) or not root.is_dir() or any(root.iterdir()):
        raise ValueError('new project-owned run directory required')
    raw=json.dumps(rir,allow_nan=False)
    if len(raw)>4_000_000:raise ValueError('plan too large')
    plan=json.loads(raw);validate_rir(plan,project_root=owner)
    staged={};total=0
    def walk(nodes):
        nonlocal total
        for node in nodes:
            if node['type']=='group':walk(node['children'])
            if node['type']!='raster':continue
            identity=node['raster']['path']
            if not re.fullmatch(r'img-[0-9a-f]{64}',identity):
                raise ImageAssetError(400,'PLAN_REQUIRES_ASSET_ID')
            if identity not in staged:
                item=images.content(project_id,identity)
                data=base64.b64decode(item['content_base64'],validate=True)
                total+=len(data)
                if total>256*1024*1024:raise ValueError('plan inputs too large')
                suffix='.png' if item['asset']['media_type']=='image/png' else '.jpg'
                path=service.paths.checked_path(root/(f'input-{len(staged):04d}'+suffix))
                staged[identity]=(path,data)
            node['raster']['path']=staged[identity][0].relative_to(owner).as_posix()
    walk(plan['layers'])
    for path,data in staged.values():
        with path.open('xb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
    if host=='photoshop':return build_photoshop_job(plan,root,text_styles=text_styles,project_root=owner)
    return build_adobe_job(plan,root,text_styles=text_styles,project_root=owner).to_dict()
