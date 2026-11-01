# SPDX-License-Identifier: MIT
"""Independent unregistered full-canvas PSD preview diagnostic, not acceptance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.runtime.paths import resolve_paths


def main():
    paths=resolve_paths(project_root=ROOT)
    run=paths.checked_path(sys.argv[1])
    source=paths.checked_path(ROOT/'.project-local/task-artifacts/reference-qualification/behance-5783221/publisher-3000.png')
    candidate=run/'photoshop-preview.png'
    proof=json.loads((run/'native-task-readback.json').read_text(encoding='utf-8'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(source)!='5e53676d6c62826d374e81b23958444250c3c7bd57015ff913e98c93b4307e43':raise ValueError('source changed')
    if sha(candidate)!=proof['result']['native']['artifacts']['png']['sha256']:raise ValueError('preview changed')
    with Image.open(candidate) as im:
        alpha_extrema=im.convert('RGBA').getchannel('A').getextrema()
        if alpha_extrema!=(255,255):raise ValueError('full preview unexpectedly transparent')
        actual=np.asarray(im.convert('RGB')).astype(float)
    with Image.open(source) as im:expected=np.asarray(im.convert('RGB')).astype(float)
    if actual.shape!=expected.shape:raise ValueError('no resize or registration allowed')
    a=actual.mean(2)<128;b=expected.mean(2)<128
    record=dict(status='MEASURED_NOT_ACCEPTED',observed_at=datetime.now(timezone.utc).isoformat(),
        source_sha256=sha(source),preview_sha256=sha(candidate),
        mae_0_255=float(np.abs(actual-expected).mean()),foreground_iou=float((a&b).sum()/max(1,(a|b).sum())),
        limits=['inferred white matte','substituted fonts and uncorrected OCR','pixel fills are not vector shapes',
                'no local edits or restoration tested for this PSD','no Human Jury or rights acceptance'])
    with (run/'pixel-metrics.json').open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2)
    print(json.dumps(record))


if __name__=='__main__':main()
