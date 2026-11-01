import collections
import hashlib
import json
import pathlib
import re
import shutil
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADMIN = ROOT / '_归档管理'
PROJECTS = ['AAOS项目','WORKLAB项目','DESIGNLAB项目','AIWORKLAB项目']

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(4194304),b''): h.update(chunk)
    return h.hexdigest()

def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
def checked(path):
    # Resolve and reject every link/reparse component before any mutation.
    path=path.absolute()
    if not path.is_relative_to(ROOT): raise ValueError('Outside task root')
    for part in [path]+list(path.parents):
        if part==ROOT.parent: break
        if part.exists() and (part.is_symlink() or part.is_junction()): raise ValueError('Reparse path refused')
    if not path.resolve().is_relative_to(ROOT): raise ValueError('Resolved outside task root')
    return path

def render(path,record,entry):
    lines=[f'# {record.get("title", "无标题")}', '',f'来源：{entry["source"]}，序号 {entry["source_index"]}；唯一键 {entry["key"]}',
           '项目归属：'+'、'.join(entry['projects']), '归类依据：'+entry['reason'],'',
           '以下保留全部消息节点（含分支）；完整原始结构见同名 JSON。','']
    nodes=sorted(record.get('mapping',{}).items(),key=lambda kv:(kv[1].get('message') or {}).get('create_time') or 0)
    for node_id,node in nodes:
        m=node.get('message')
        if not m:continue
        lines.extend([f'## {(m.get("author") or {}).get("role", "unknown")} · {node_id}','',f'父节点：{node.get("parent")}；时间戳：{m.get("create_time")}',''])
        content=m.get('content') or {};parts=content.get('parts')
        if isinstance(parts,list):
            for part in parts:lines.extend([part if isinstance(part,str) else json.dumps(part,ensure_ascii=False,indent=2),''])
        else:lines.extend([json.dumps(content,ensure_ascii=False,indent=2),''])
    lines.extend(['## 本地关联附件',''])
    lines.extend(f'- [{name}](../附件/{name})' for name in entry['assets'])
    path.write_text('\n'.join(lines),encoding='utf-8',newline='\n')

def verify_retained():
    receipt=load(ADMIN/'保留文件校验清单.json')
    for item in receipt:
        p=checked(ROOT/item['path'])
        if not p.is_file() or digest(p)!=item['sha256']:raise ValueError('Retained file hash mismatch: '+item['path'])
    summary=load(ADMIN/'清理结果.json')
    print(json.dumps({'status':'PASS','retained_files_verified':len(receipt),'projects':summary['projects']},ensure_ascii=False,indent=2))

def prepare():
    baseline=load(ADMIN/'原始文件校验.json')
    for item in baseline:
        p=checked(ROOT/item['path'])
        if not p.is_file() or digest(p)!=item['sha256']:raise ValueError('Source changed: '+item['path'])
    print('All 3809 original files reverified before cleanup.',flush=True)
    original={}
    for path in sorted(ROOT.glob('conversations-*.json')):
        for i,r in enumerate(load(path)):original[f'{path.stem[-3:]}:{i:03}']=(path.name,i,r)
    manifests=[load(ROOT/g/'分类清单.json') for g in PROJECTS]
    additions={}
    def add(shard,indices,groups):
        for i in indices:additions[f'{shard}:{i:03}']=groups
    add('000',[0,8,10,19,22,23,24,26,27,29,31,32,38,42,49,51],[0])
    add('000',[76,85],[0,1])
    add('001',[3,46,61],[1])
    add('001',[10,19,24,36,54,92,95,98],[0,1,2])
    add('001',[11],[2])
    add('001',[47],[1,2])
    add('001',[56],[0,1])
    add('002',[0,2,3,7,23,24,39,41],[0,1,2])
    add('002',[47],[3])
    source_assets={x.name:x for x in ROOT.glob('*.dat')}
    for key,groups in additions.items():
        source,index,r=original[key];title=r.get('title') or '无标题'
        text=json.dumps(r,ensure_ascii=False);refs=set(re.findall(r'file[_-][0-9a-fA-F]{20,40}',text))
        assets=sorted(ref+'.dat' for ref in refs if ref+'.dat' in source_assets)
        stem=key.replace(':','-')+'_'+(re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title).strip(' .')[:65] or '无标题')
        for g in groups:
            if any(e['key']==key for e in manifests[g]):continue
            folder=ROOT/PROJECTS[g];jp=folder/'对话'/(stem+'.json');mp=jp.with_suffix('.md')
            entry={'key':key,'source':source,'source_index':index,'id':r.get('id'),'title':title,
                   'projects':[PROJECTS[k] for k in groups], 'reason':'删除前补充复核：项目历史前身、架构、研究或品牌展示资料；混合对话完整保留',
                   'cross_project':len(groups)>1,'json_path':jp.relative_to(ROOT).as_posix(),
                   'markdown_path':mp.relative_to(ROOT).as_posix(),'assets':assets,'referenced_file_ids':sorted(refs)}
            save(checked(jp),r);render(checked(mp),r,entry)
            for asset in assets:
                dest=checked(folder/'附件'/asset)
                if not dest.exists():shutil.copy2(source_assets[asset],dest)
            manifests[g].append(entry)
    library=load(ROOT/'library_files.json');stats={};unique_keys=set();record_bindings=[]
    for g,entries in enumerate(manifests):
        folder=ROOT/PROJECTS[g];entries.sort(key=lambda e:e['key'])
        # Normalize memberships across copies and verify every complete record against original.
        for e in entries:
            e['projects']=[PROJECTS[k] for k,es in enumerate(manifests) if any(x['key']==e['key'] for x in es)]
            e['cross_project']=len(e['projects'])>1
            r=original[e['key']][2]
            if load(ROOT/e['json_path'])!=r:raise ValueError('Full record differs: '+e['key'])
            with (ROOT/e['markdown_path']).open(encoding='utf-8',newline='') as f:md=f.read()
            for node_id,node in r.get('mapping',{}).items():
                m=node.get('message')
                if not m:continue
                if ' · '+node_id not in md:raise ValueError('Message node absent')
                for part in (m.get('content') or {}).get('parts',[]):
                    if isinstance(part,str) and part not in md:raise ValueError('Message text absent')
            for name in e['assets']:
                if not (folder/'附件'/name).is_file():raise ValueError('Missing linked attachment')
            unique_keys.add(e['key'])
            canonical=json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
            record_bindings.append({'project':PROJECTS[g],'key':e['key'],'original_record_sha256':hashlib.sha256(canonical).hexdigest()})
        asset_list=list((folder/'附件').glob('*'))
        for path in asset_list:
            if digest(path)!=digest(source_assets[path.name]):raise ValueError('Attachment differs: '+path.name)
        save(folder/'分类清单.json',entries)
        fids={ref for e in entries for ref in e['referenced_file_ids']}
        fids|={x.stem for x in asset_list}
        selected=load(folder/'附件元数据.json')
        known={json.dumps(r,sort_keys=True) for r in selected}
        for r in library:
            if r.get('file_id') in fids and json.dumps(r,sort_keys=True) not in known:
                selected.append(r);known.add(json.dumps(r,sort_keys=True))
        save(folder/'附件元数据.json',selected)
        lines=[f'# {PROJECTS[g]}','','完整原始 JSON 与全部分支消息均保留；混合对话按完整记录保留。','']
        if g==0:lines+=['AAOS = ArcheAxis-Knowledge-OS。包含 ArcheAxis、Cognitive-Loop-OS、元枢系统历史资料及已复核的早期组件演变记录。','']
        for e in entries:
            name=pathlib.PurePosixPath(e['markdown_path']).name
            label=e['title'].strip().replace('[','\\[').replace(']','\\]')
            lines.append(f'- [{label}](对话/{urllib.parse.quote(name)})'+('（跨项目）' if e['cross_project'] else ''))
        (folder/'阅读入口.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
        stats[PROJECTS[g]]={'conversations':len(entries),'assets':len(asset_list)}
    # Bind all retained files before removing any source. New receipt excludes unrelated content.
    keep=[]
    for group in PROJECTS:
        for p in sorted((ROOT/group).rglob('*')):
            if p.is_file():keep.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)})
    save(ADMIN/'保留文件校验清单.json',keep)
    save(ADMIN/'保留对话来源校验.json',record_bindings)
    result={'status':'PREPARED','root':str(ROOT),'AAOS_identity':'ArcheAxis-Knowledge-OS',
            'source_files_verified_before_deletion':len(baseline),'source_conversation_count':len(original),
            'retained_unique_conversations':len(unique_keys),'excluded_conversation_count':len(original)-len(unique_keys),
            'projects':stats,'original_export_files_to_remove':len(baseline),
            'integrity':'完整JSON逐条与原记录相等；全部消息节点和文本保留；所有项目附件逐个SHA256相等',
            'note':'跨项目及包含项目资料的混合对话保留全文。原始导出未提供的附件二进制无法补回。'}
    save(ADMIN/'清理结果.json',result)
    save(ADMIN/'删除计划.json',{'root':str(ROOT),'source_files':baseline,'admin_files':[p.name for p in ADMIN.iterdir() if p.is_file() and p.name not in ['retain_projects.py','保留文件校验清单.json','保留对话来源校验.json','清理结果.json','删除计划.json','原始导出缺件说明.json']]})
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

def remove_sources():
    plan=load(ADMIN/'删除计划.json')
    if pathlib.Path(plan['root'])!=ROOT:raise ValueError('Root mismatch')
    verify_retained()
    targets=[]
    for item in plan['source_files']:
        p=checked(ROOT/item['path'])
        if p.is_file() and digest(p)!=item['sha256']:raise ValueError('Deletion target changed')
        if p.exists():targets.append(p)
    for name in plan['admin_files']:
        p=checked(ADMIN/name)
        if p.parent!=ADMIN:raise ValueError('Invalid admin target')
        if p.is_file():targets.append(p)
    print(f'Deleting {len(targets)} verified targets within {ROOT}',flush=True)
    for p in targets:p.unlink()
    for name in ['pages','sites']:
        base=checked(ROOT/name)
        if base.exists():
            for p in sorted(base.rglob('*'),key=lambda p:len(p.parts),reverse=True):
                if p.is_dir():checked(p).rmdir()
            base.rmdir()
    result=load(ADMIN/'清理结果.json');result['status']='PASS';result['deleted_files']=len(targets)
    save(ADMIN/'清理结果.json',result)
    (ROOT/'归档阅读入口.md').write_text('# 四项目归档\n\nAAOS = ArcheAxis-Knowledge-OS。项目历史名称、早期组件演变及含项目资料的混合对话已保留。\n\n'+
        '\n'.join(f'- [{g}]({g}/阅读入口.md)' for g in PROJECTS)+
        '\n\n无关对话、附件及包含无关内容的原始合并导出已删除。\n\n[清理结果](_归档管理/清理结果.json) · [保留文件校验清单](_归档管理/保留文件校验清单.json)\n\n'+
        '部分附件二进制在原始导出中就不存在，缺件说明见管理目录；不能视为本次删除造成。\n',encoding='utf-8',newline='\n')
    # Delete the plan itself: it contains names/hashes of the excluded sources.
    checked(ADMIN/'删除计划.json').unlink()
    verify_retained()
    print('Cleanup finished; no source conversation shards or unrelated full-record copies remain.',flush=True)

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else '--verify'
    if mode=='--prepare':prepare()
    elif mode=='--delete':remove_sources()
    elif mode=='--verify':verify_retained()
    else:raise ValueError('Unknown mode')
