# SPDX-License-Identifier: MIT
"""Read-only pixel comparison, writing a new project-local metrics receipt.

Geometry-aligned diagnostic only; no rights, typography or human acceptance.
No image resampling, cropping, registration or white-background score masking.
"""
from datetime import datetime,timezone
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
    run=paths.checked_path(sys.argv[1])
    source=paths.checked_path(ROOT/'.project-local/task-artifacts/reference-qualification/behance-5783221/publisher-3000.png')
    candidate=paths.checked_path(run/'illustrator-preview.png')
    receipt=run/'pixel-metrics.json'
    if receipt.exists():raise ValueError('immutable metrics already exist')
    proof=json.loads((run/'native-task-readback.json').read_text(encoding='utf-8'))
    candidate_hash=hashlib.sha256(candidate.read_bytes()).hexdigest()
    if candidate_hash!=proof['result']['native']['artifacts']['png']['sha256']:raise ValueError('preview changed')
    with Image.open(source) as image:s=np.asarray(image.convert('RGB')).astype(np.float32)
    with Image.open(candidate) as image:t=np.asarray(image.convert('RGB')).astype(np.float32)
    if s.shape!=t.shape:raise ValueError('canvas mismatch; no automatic registration')
    def metrics(a,b):
        ink_a=a.mean(2)<128;ink_b=b.mean(2)<128
        return dict(mae_0_255=float(np.abs(a-b).mean()),
            foreground_iou=float((ink_a&ink_b).sum()/max(1,(ink_a|ink_b).sum())),
            exact_rgb_fraction=float((a==b).all(2).mean()))
    regions=json.loads((run/'segmentation.json').read_text(encoding='utf-8'))
    result=dict(observed_at=datetime.now(timezone.utc).isoformat(),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),candidate_sha256=candidate_hash,
        full_canvas=metrics(s,t),graphics=[],status='MEASURED_NOT_ACCEPTED',
        limits=['fixed 128 ink threshold','no ground-truth text or font score','no Human Jury receipt',
                'exact RGB includes white background; not an acceptance percentage'])
    for region in regions:
        x,y,right,bottom=region['box']
        result['graphics'].append(dict(id=region['id'],**metrics(s[y:bottom,x:right],t[y:bottom,x:right])))
    receipt.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),full_canvas=result['full_canvas'],status=result['status'])))


if __name__=='__main__':main()
