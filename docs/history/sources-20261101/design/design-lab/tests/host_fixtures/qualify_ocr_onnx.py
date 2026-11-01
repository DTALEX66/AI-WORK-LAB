# SPDX-License-Identifier: MIT
"""Offline PP-OCRv6 medium ONNX qualification on predeclared image fixtures."""
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
models=ROOT/'.project-local/task-artifacts/ocr-qualification/onnx-20260907T193520352697Z'
out=models/('live-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir(exist_ok=False)
for key in ('TEMP','TMP','TMPDIR','XDG_CACHE_HOME','MPLCONFIGDIR','HF_HOME'):
    folder=out/key;folder.mkdir();os.environ[key]=str(folder)
os.environ.update(HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',PYTHONDONTWRITEBYTECODE='1')
import tempfile
tempfile.tempdir=str(out/'TEMP')
denied=[];writes=[];base=Path(sys.base_prefix).resolve()
def audit(event,args):
    if event in ('socket.connect','socket.getaddrinfo','subprocess.Popen'):
        denied.append(event);raise PermissionError('offline qualification denies network/child processes')
    targets=[]
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        raw=os.fsdecode(args[0])
        if raw.replace('\\','/').upper() in ('NUL','//./NUL'):return
        path=Path(raw).resolve()
        if path.drive.lower()=='e:' or (path.is_relative_to(Path('C:/Users/ALEX')) and not path.is_relative_to(base)):
            denied.append('protected-read');raise PermissionError('protected read denied')
        if isinstance(args[2],int) and args[2]&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_APPEND|os.O_TRUNC):targets=[path]
    elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.utime') and isinstance(args[0],(str,bytes,os.PathLike)):
        targets=[Path(os.fsdecode(args[0])).resolve()]
    elif event in ('os.rename','os.link','os.symlink'):targets=[Path(os.fsdecode(p)).resolve() for p in args[:2]]
    for path in targets:
        if not path.is_relative_to(out):denied.append('outside-write');raise PermissionError('outside write denied')
        writes.append(str(path.relative_to(out)))
sys.addaudithook(audit)
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def normalized(value):return ''.join(c.casefold() for c in value if c.isalnum() or c in '¥.')
def cer(a,b):
    a,b=normalized(a),normalized(b);prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]/max(1,len(a))
def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return inter/max(1,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)
record=dict(status='RUNNING',scope='synthetic CPU ONNX det+rec only; not production qualification',cases=[],
            thresholds={'minimum_bbox_iou':.35,'maximum_normalized_cer':.1,'no_extra_text':True},reference_text_supplied_to_model=False)
print(str(out),flush=True)
try:
    prep=json.loads((models/'preparation.json').read_text());assert prep['status']=='WEIGHTS_COMPLETE_NOT_LOADED'
    before={str(models/m['role']/f['path']):f['sha256'] for m in prep['models'] for f in m['files']}
    assert all(sha(Path(p))==h for p,h in before.items())
    protocol=ROOT/'.project-local/task-artifacts/ocr-qualification/paddle-20260906T202022263722Z/live-20260906T202626725459Z/protocol.json'
    fixtures=json.loads(protocol.read_text(encoding='utf-8'))['fixtures']
    record.update(protocol_sha256=sha(protocol),script_sha256=sha(Path(__file__)),models=prep['models'],
                  versions={p:importlib.metadata.version(p) for p in ('rapidocr','onnxruntime','numpy','opencv-python')})
    import yaml
    import numpy as np
    import cv2
    import onnxruntime as ort
    ort.disable_telemetry_events()
    import rapidocr
    from rapidocr.utils.parse_parameters import ParseParams
    from rapidocr.ch_ppocr_det import TextDetector
    from rapidocr.ch_ppocr_rec import TextRecognizer,TextRecInput
    from rapidocr.utils.process_img import get_rotate_crop_image
    cfg=yaml.safe_load((Path(rapidocr.__file__).parent/'config.yaml').read_text(encoding='utf-8'))
    dictionary=yaml.safe_load((models/'rec/inference.yml').read_text(encoding='utf-8'))['PostProcess']['character_dict']
    (out/'dictionary.txt').write_text('\n'.join(dictionary)+'\n',encoding='utf-8')
    cfg['EngineConfig']['onnxruntime'].update(intra_op_num_threads=2,inter_op_num_threads=1,use_cuda=False,use_dml=False)
    for role in ('Det','Rec'):
        cfg[role].update(model_type='medium',model_path=str(models/role.lower()/'inference.onnx'),model_root_dir=str(out))
    cfg['Det'].update(mean=[.485,.456,.406],std=[.229,.224,.225],thresh=.2,box_thresh=.45,unclip_ratio=1.4,max_candidates=3000,use_dilation=False)
    cfg['Rec'].update(rec_keys_path=str(out/'dictionary.txt'),rec_batch_num=2,font_path='C:/Windows/Fonts/msyh.ttc')
    (out/'config.yaml').write_text(yaml.safe_dump(cfg),encoding='utf-8');cfg=ParseParams.load(out/'config.yaml')
    for role in ('Det','Rec'):cfg[role].engine_cfg=cfg.EngineConfig.onnxruntime
    started=time.monotonic();det=TextDetector(cfg.Det);rec=TextRecognizer(cfg.Rec)
    record['load_seconds']=round(time.monotonic()-started,3)
    for fixture in fixtures:
        path=Path(fixture['path']);assert path.is_relative_to(ROOT/'.project-local') and sha(path)==fixture['sha256']
        image=cv2.imdecode(np.frombuffer(path.read_bytes(),np.uint8),cv2.IMREAD_COLOR)
        started=time.monotonic();detected=det(image);boxes=[] if detected.boxes is None else detected.boxes
        result=rec(TextRecInput([get_rotate_crop_image(image,b.copy()) for b in boxes])) if len(boxes) else None
        predictions=[]
        if result is not None:
            for box,text,score in zip(boxes,result.txts,result.scores):
                predictions.append(dict(text=text,score=float(score),polygon=box.tolist(),bbox=[float(box[:,0].min()),float(box[:,1].min()),float(box[:,0].max()),float(box[:,1].max())]))
        expected=fixture['lines'];checks=[];remaining=list(predictions)
        for truth in expected:
            best=max(remaining,key=lambda p:iou(truth['bbox'],p['bbox'])) if remaining else None
            if best is None:checks.append(dict(passed=False));continue
            remaining.remove(best);overlap=iou(truth['bbox'],best['bbox']);error=cer(truth['text'],best['text'])
            checks.append(dict(iou=overlap,cer=error,passed=overlap>=.35 and error<=.1))
        passed=all(c['passed'] for c in checks) and not remaining and len(predictions)==len(expected)
        record['cases'].append(dict(id=fixture['id'],sha256=fixture['sha256'],seconds=round(time.monotonic()-started,3),predictions=predictions,checks=checks,passed=passed))
        print(fixture['id']+' '+str(passed),flush=True)
    assert all(sha(Path(p))==h for p,h in before.items())
    record['status']='CONTROLLED_OCR_PASS' if all(c['passed'] for c in record['cases']) and not denied else 'PARTIAL'
except Exception as exc:
    record.update(status='FAIL',error=type(exc).__name__+': '+str(exc));raise
finally:
    record.update(denied_events=denied,write_paths=writes)
    (out/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
