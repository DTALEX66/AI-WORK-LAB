# SPDX-License-Identifier: MIT
"""Independent pixel locality and immutable checkpoint recovery checks."""
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.runtime.paths import resolve_paths


def main():
    paths=resolve_paths(project_root=ROOT)
    original=paths.checked_path(ROOT/'.project-local/task-artifacts/real-poster-20260908/run-3bc50140e7f44caca5393c29002c43f9')
    text_run,path_run,restore_run=[paths.checked_path(v) for v in sys.argv[1:]]
    def pixels(folder,initial=False):
        if initial:proof=json.loads((folder/'native-task-readback.json').read_text())['result']
        else:proof=json.loads((folder/'patch-readback.json').read_text())['result']
        path=folder/'illustrator-preview.png'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=proof['native']['artifacts']['png']['sha256']:raise ValueError('preview changed')
        if hashlib.sha256((folder/'master.ai').read_bytes()).hexdigest()!=proof['native']['artifacts']['ai']['sha256']:raise ValueError('native changed')
        with Image.open(path) as image:return np.asarray(image.convert('RGBA')).copy()
    baseline=pixels(original,True);edited_text=pixels(text_run);edited_path=pixels(path_run);restored=pixels(restore_run)
    def check(before,after,box):
        if before.shape!=after.shape:raise ValueError('canvas changed')
        difference=np.any(before!=after,axis=2);ys,xs=np.where(difference)
        if not len(xs):raise ValueError('local edit had no visible effect')
        actual=[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]
        contained=actual[0]>=box[0] and actual[1]>=box[1] and actual[2]<=box[2] and actual[3]<=box[3]
        return dict(changed_pixels=int(len(xs)),changed_bbox=actual,allowed_bbox=box,outside_unchanged=contained)
    rir=json.loads((original/'source-rir.json').read_text())
    text=next(n for n in rir['layers'][0]['children'] if n['id']=='ocr-100')['bounds']
    text_box=[int(text['x']),int(text['y']),int(text['x']+text['width'])+1,int(text['y']+text['height'])+1]
    icon=next(v for v in json.loads((original/'segmentation.json').read_text()) if v['id']=='r0-icon2')['box']
    result=dict(text=check(baseline,edited_text,text_box),path=check(edited_text,edited_path,icon),
        restoration_pixel_exact=bool(np.array_equal(baseline,restored)))
    passed=result['text']['outside_unchanged'] and result['path']['outside_unchanged'] and result['restoration_pixel_exact']
    result['status']='LOCALITY_AND_CHECKPOINT_RESTORE_VERIFIED' if passed else 'FAILED_LOCALITY_OR_RESTORE'
    output=restore_run/'independent-edit-verification.json'
    if output.exists():raise ValueError('preserve existing receipt')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
