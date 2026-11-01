import json,hashlib,zipfile,re,shutil
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent
checks=[]
def check(name,ok):
    checks.append({'name':name,'pass':bool(ok)})
    if not ok:raise ValueError(name)
def load(name):return json.loads((ROOT/name).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for p in ROOT.rglob('*.json'):json.loads(p.read_text())
check('All JSON parses',True)
screen_map=load('specs/screen_map.json')
check('21 screen configurations present',len(screen_map)==21)
for s in screen_map:
    for key in ['desktop','retina','full_page']:
        if s.get(key):check(f'{s["id"]} {key} exists',(ROOT/s[key]).is_file())
    if not s.get('mobile'):
        with Image.open(ROOT/s['retina']) as im:check(s['id']+' 4K viewport dimensions',im.size==(3840,2160))
    else:
        with Image.open(ROOT/s['retina']) as im:check(s['id']+' mobile viewport dimensions',im.size==(780,1688))
for p in (ROOT/'screens').rglob('*.png'):
    with Image.open(p) as im:im.verify()
check('All screen images decode',True)
render=load('evidence/render_report.json')
check('No browser page errors',not render['errors'])
check('All desktop media loaded',all(im['ok'] for m in render['measurements'] for im in m.get('images',[])))
check('No page-wide overflow in rendered configurations',all(m['scrollWidth']<=m['viewport'][0] for m in render['measurements']))
interaction=load('evidence/interaction_report.json')
check('31 local UI behavior checks passed',len(interaction['checks'])==31 and all(c['pass'] for c in interaction['checks']))
manifest=load('specs/asset_manifest.json')
check('10 SVG and 10 high-res PNG assets',len([a for a in manifest['assets'] if a.get('source')=='NATIVE_SVG_CREATED_FOR_THIS_UI_TASK'])==20)
for a in manifest['assets']:
    p=ROOT/a['path'];check(a['id']+' hash matches',p.exists() and sha(p)==a['sha256'])
    if p.suffix=='.png' and a.get('width'):
        with Image.open(p) as im:check(a['id']+' actual dimensions',im.size==(a['width'],a['height']))
tasks=load('specs/page_tasks.json')['work_items'];ids={t['id'] for t in tasks};done=set()
check('Work item dependencies resolve',all(d in ids for t in tasks for d in t['depends_on']))
while len(done)<len(tasks):
    progress=[t['id'] for t in tasks if t['id'] not in done and set(t['depends_on'])<=done]
    check('Dependency graph can advance',bool(progress));done.update(progress)
check('12 implementation work items',len(tasks)==12)
for html in ['gallery.html','overview.html']:
    s=(ROOT/html).read_text()
    refs=re.findall(r'(?:href|src)="([^"]+)"',s)
    check(html+' local references resolve',all((ROOT/r.split('#')[0]).exists() for r in refs if not r.startswith(('http','data:','#'))))
files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
check('No zero-byte deliverables',all(p.stat().st_size>0 for p in files))
report={'kind':'LOCAL_ARTIFACT_PACKAGE_VERIFICATION','scope':'UI reference only. No production repository, real hosts, Human Jury, AAOS, WORK-LAB or actual learning tests.','checks':checks,'screen_configurations':len(screen_map),'screenshot_png_count':len(list((ROOT/'screens').rglob('*.png'))),'independent_artwork_sets':10,'implementation_work_items':12,'production_status':'NOT_STARTED','real_host':'NOT_RUN','three_project_integration':'NOT_TESTED'}
(ROOT/'evidence/package_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
files=[p for p in ROOT.rglob('*') if p.is_file() and p.name!='MANIFEST.json' and '__pycache__' not in p.parts]
(ROOT/'MANIFEST.json').write_text(json.dumps({'version':'UI-20261009-r1','kind':'DELIVERY_CHECKSUMS_NOT_REPO_AUTHORITY','files':[{'path':p.relative_to(ROOT).as_posix(),'size_bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]},ensure_ascii=False,indent=2)+'\n')
zip_path=OUT/'DESIGN-LAB_UI前端任务包_20261009.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(zip_path) as z:check('Archive CRC integrity',z.testzip() is None)
overview=OUT/'DESIGN-LAB_UI_界面总览_20261009.png';shutil.copyfile(ROOT/'DESIGN-LAB_UI_总览_20261009.png',overview)
prompt=OUT/'DESIGN-LAB_UI_Agent执行提示词_20261009.md';shutil.copyfile(ROOT/'01_AGENT_EXECUTION.md',prompt)
print(json.dumps({'zip':str(zip_path),'size_bytes':zip_path.stat().st_size,'overview':str(overview),'prompt':str(prompt),'checks':len(checks),'screenshot_files':report['screenshot_png_count']},ensure_ascii=False))
