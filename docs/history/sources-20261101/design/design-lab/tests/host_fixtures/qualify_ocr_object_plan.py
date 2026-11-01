# SPDX-License-Identifier: MIT
"""Replay measured OCR observations through the production object-plan seam."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from design_lab.analysis.decomposition import Plan
from PIL import Image
import jsonschema


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    base=ROOT/'.project-local/task-artifacts/ocr-qualification'
    receipt=base/'onnx-20260907T193520352697Z/live-20260907T194844712383Z/results.json'
    assert sha(receipt)=='c015ad6dc300122413cc76944d5d5d9510ce1c0556a6b10e6370e120f0fc298a'
    result=json.loads(receipt.read_text(encoding='utf-8'))
    assert result['status']=='CONTROLLED_OCR_PASS'
    fixture_root=base/'paddle-20260906T202022263722Z/live-20260906T202626725459Z'
    schema_path=ROOT/'design-lab/schemas/contracts/planar-decomposition.schema.json'
    schema=json.loads(schema_path.read_text(encoding='utf-8'))
    out=base/('object-plan-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(exist_ok=False)
    evidence=dict(status='RUNNING',scope='measured synthetic OCR to object plan; no new inference or host mapping',
                  receipt_sha256=sha(receipt),script_sha256=sha(Path(__file__)),
                  producer_sha256=sha(ROOT/'src/design_lab/analysis/decomposition.py'),
                  schema_sha256=sha(schema_path),cases=[])
    for case in result['cases']:
        assert case['id'] in ('english','chinese','commerce','inverted','blank')
        source=fixture_root/(case['id']+'.png')
        assert sha(source)==case['sha256']
        with Image.open(source) as image:canvas=image.size
        detections=[dict(text=p['text'], confidence=p['score'], polygon=p['polygon']) for p in case['predictions']]
        plan=Plan.from_ocr(decomposition_id='observed-'+case['id'],
                          source_ref=source.relative_to(ROOT).as_posix(), source_sha256='sha256:'+sha(source),
                          canvas=canvas, module='pp-ocrv6-medium-onnx', detections=detections)
        payload=plan.to_contract();jsonschema.validate(payload,schema)
        assert all(o.host_object_id is None for o in plan.objects)
        assert sum(o.kind=='text' for o in plan.objects)==len(case['predictions'])
        assert plan.objects[-1].mapping_state=='unrecovered'
        target=out/(case['id']+'.json');target.write_text(plan.to_json(),encoding='utf-8')
        evidence['cases'].append(dict(id=case['id'],text_objects=len(detections),
                                     plan_sha256=sha(target),unrecovered_content=True))
    evidence['status']='OBSERVED_OCR_OBJECT_PLAN_PASS'
    (out/'readback.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(out),**evidence)))


if __name__=='__main__':main()
