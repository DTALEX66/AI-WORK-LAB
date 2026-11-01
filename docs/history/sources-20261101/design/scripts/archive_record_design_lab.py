# SPDX-License-Identifier: MIT
"""Owner-authorized local Record archive with hash deduplication and searchable aliases.

No source deletion, no executable imports, no cloud writes. --apply builds an
immutable dated archive; default verifies it; --find searches the registered names.
All runtime data stays in this project's .project-local/. Shared containers remain
inert context, not a grant or a current TaskPack.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile
import zlib

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/All projects/Record')
META = 'docs/history/record-archive-2026-10-09'
LOCAL = '.project-local/task-artifacts/record-archive-2026-10-09'
MANIFEST = META + '/ARCHIVE-MANIFEST.json'
MARKER = re.compile(r'DESIGN[\s_-]?LAB|设计实验室|DL-(?:TP|R5|AUTHORITY)-|Open[ -]Design[ -]Assistance', re.I)
TEXT = {'.md', '.txt', '.json', '.csv', '.html', '.htm', '.yaml', '.yml', '.js', '.ts', '.css'}
OFFICE = {'.docx', '.xlsx', '.pptx'}
SENSITIVE = re.compile(r'(^|/)(?:\.env(?:\..*)?|credentials(?:\..*)?|auth\.json|id_rsa|id_ed25519|cookies?\.sqlite)$', re.I)


def disk(path):
    path = Path(path).absolute()
    return Path('\\\\?\\' + str(path)) if os.name == 'nt' else path


def sha(path):
    h = hashlib.sha256()
    with disk(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe(relative):
    parts = PurePosixPath(relative.replace('\\', '/'))
    if parts.is_absolute() or '..' in parts.parts or any(':' in p for p in parts.parts):
        raise ValueError('unsafe archive path: ' + relative)
    target = REPO.joinpath(*parts.parts)
    if not target.resolve().is_relative_to(REPO.resolve()):
        raise ValueError('archive target escapes project')
    cursor = REPO
    for part in parts.parts:
        cursor /= part
        if cursor.exists() and (cursor.is_symlink() or cursor.is_junction()):
            raise ValueError('archive target traverses a link')
    return target


def write(relative, data, replace=False):
    p = disk(safe(relative))
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.read_bytes() != data and not replace:
        raise ValueError('refuse to overwrite differing archive bytes: ' + relative)
    if not p.exists() or p.read_bytes() != data:
        p.write_bytes(data)


def text_hits(data):
    return len(MARKER.findall(data.decode('utf-8', errors='replace')))


def _evidence(path):
    """Minimal classification evidence, never print document bodies."""
    suffix = path.suffix.lower()
    if suffix in TEXT and path.stat().st_size <= 8 * 1024 * 1024:
        return {'text_hits': text_hits(path.read_bytes())}
    if suffix in OFFICE:
        with zipfile.ZipFile(path) as z:
            count = sum(text_hits(z.read(i)) for i in z.infolist()
                        if i.filename.endswith('.xml') and i.file_size <= 2 * 1024 * 1024)
        return {'office_xml_hits': count}
    if suffix == '.zip':
        with zipfile.ZipFile(path) as z:
            names = sum(bool(MARKER.search(i.filename)) for i in z.infolist())
            hits = 0
            # Huge archives of another project are inventoried, not inflated.
            if path.stat().st_size <= 160 * 1024 * 1024:
                for i in z.infolist():
                    if PurePosixPath(i.filename).suffix.lower() in TEXT and i.file_size <= 2 * 1024 * 1024:
                        hits += text_hits(z.read(i))
            return {'zip_member_name_hits': names, 'zip_text_hits': hits,
                    'zip_members': sum(not i.is_dir() for i in z.infolist()),
                    'large_body_scan': 'SKIPPED_OTHER_PROJECT' if path.stat().st_size > 160 * 1024 * 1024 else 'SMALL_TEXT_ONLY'}
    return {}


def evidence(path):
    try:
        return _evidence(path)
    except (zipfile.BadZipFile, OSError) as exc:
        return {'container_inspection_error': type(exc).__name__,
                'inspection_state': 'UNREADABLE_INPUT_NOT_SILENTLY_DROPPED'}


def source_inventory():
    old = json.loads((REPO / 'docs/history/record-imports-2026-10-08/RECORD-IMPORT-MANIFEST.json').read_text(encoding='utf-8'))
    known = {e['source_container'].split('::')[0] for e in old['entries']}
    top, files = [], []
    for item in sorted(SOURCE.iterdir(), key=lambda p: p.name.casefold()):
        if item.is_symlink() or item.is_junction():
            raise ValueError('source link not followed: ' + item.name)
        children = sorted(item.rglob('*')) if item.is_dir() else [item]
        rows = []
        for p in children:
            if p.is_symlink() or p.is_junction():
                raise ValueError('source link not followed: ' + str(p))
            if not p.is_file():
                continue
            rel = p.relative_to(SOURCE).as_posix()
            if SENSITIVE.search(rel):
                raise ValueError('sensitive source name requires separate handling: ' + rel)
            ev = evidence(p)
            relevant = bool(MARKER.search(rel)) or any(ev.get(k, 0) for k in
                ('text_hits', 'office_xml_hits', 'zip_member_name_hits', 'zip_text_hits'))
            if item.name in known or item.name.startswith('Three_Project_Logos_'):
                relevant = True
            rows.append({'source_relative': rel, 'bytes': p.stat().st_size,
                         'mtime_ns': p.stat().st_mtime_ns, 'classification_evidence': ev,
                         'relevant': relevant})
        # A loose runnable visual-reference folder needs its companion resources.
        if item.is_dir() and any(r['relevant'] for r in rows):
            for r in rows:
                r['relevant'] = True
                r['shared_folder_companion'] = True
        for r in rows:
            direct = bool(MARKER.search(r['source_relative']))
            r['disposition'] = ('ARCHIVED_PROJECT_ORIGINAL' if direct else 'ARCHIVED_SHARED_REFERENCE') if r.pop('relevant') else 'OTHER_PROJECT_OR_SYSTEM_NOT_IMPORTED'
            r['reason'] = ('原件完整保留，输入指令惰性、旧包不派工' if direct else
                           '跨项目相关内容/共享视觉依赖，完整源容器惰性保存，不提升产品证据') if r['disposition'].startswith('ARCHIVED') else '项目归属/内容标记无DESIGN-LAB命中；不因同卷存在而混入'
            if 'container_inspection_error' in r['classification_evidence'] and not r['disposition'].startswith('ARCHIVED'):
                r['reason'] = '文件名归属其他项目；容器不可读，内容相关性UNVERIFIED，未假称零命中'
        top.append({'name': item.name, 'kind': 'directory' if item.is_dir() else 'file',
                    'files': len(rows), 'bytes': sum(r['bytes'] for r in rows),
                    'relevant_files': sum(r['disposition'].startswith('ARCHIVED') for r in rows)})
        files.extend(rows)
    return top, files


def seed_pool():
    pool = {}
    old = json.loads((REPO / 'docs/history/record-imports-2026-10-08/RECORD-IMPORT-MANIFEST.json').read_text(encoding='utf-8'))
    for e in old['entries']:
        if e.get('action') == 'LANDED' and e.get('target'):
            p = REPO / e['target']
            digest = e['sha256'].removeprefix('sha256:')
            if p.exists() and sha(p) == digest:
                pool.setdefault(digest, e['target'])
    inputs = json.loads((REPO / 'docs/history/taskpacks/20261009-inputs/ARCHIVE-MANIFEST.json').read_text(encoding='utf-8'))
    for p in inputs['packages']:
        candidates = [(p['local_original'], p['sha256'])]
        candidates += [(m['repository_text'] or m['local_copy'], m['sha256']) for m in p['members']]
        for rel, digest in candidates:
            if safe(rel).exists() and sha(safe(rel)) == digest:
                pool.setdefault(digest, rel)
    return pool


def apply():
    if (REPO / MANIFEST).exists():
        raise ValueError('dated archive exists; verify or make an explicit new dated snapshot')
    top, sources = source_inventory()
    pool, rows = seed_pool(), []
    seeded = set(pool)
    def store(data, name):
        digest = hashlib.sha256(data).hexdigest()
        if digest not in pool:
            basename = PurePosixPath(name.replace('\\', '/')).name
            if not basename or SENSITIVE.search(basename):
                raise ValueError('unsafe/sensitive member name')
            basename = basename[:110] + PurePosixPath(basename).suffix if len(basename) > 150 else basename
            relative = f'{LOCAL}/objects/{digest[:2]}/{digest}/{basename}'
            write(relative, data)
            pool[digest] = relative
        return digest, pool[digest]
    def unpack(data, origin, depth=0):
        if depth > 8:
            raise ValueError('nested archive depth exceeded')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set()
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace('\\', '/')
                parts = PurePosixPath(name)
                if (parts.is_absolute() or '..' in parts.parts or any(':' in p for p in parts.parts)
                        or SENSITIVE.search(name) or stat.S_ISLNK(info.external_attr >> 16)):
                    raise ValueError('unsafe/sensitive ZIP member: ' + origin + '::' + name)
                if name in names:
                    raise ValueError('duplicate archive member identity')
                names.add(name)
                member = z.read(info)  # ZIP CRC verification happens here.
                digest, target = store(member, name)
                logical = origin + '::' + name
                rows.append({'origin': logical, 'bytes': len(member), 'sha256': digest,
                             'crc32': f'{zlib.crc32(member) & 0xffffffff:08x}',
                             'canonical': target, 'kind': 'ZIP_MEMBER', 'depth': depth})
                if name.lower().endswith('.zip'):
                    unpack(member, logical, depth + 1)
    for source in sources:
        if not source['disposition'].startswith('ARCHIVED'):
            continue
        p = SOURCE / source['source_relative']
        data = p.read_bytes()
        digest, target = store(data, p.name)
        source.update(sha256=digest, canonical=target)
        rows.append({'origin': source['source_relative'], 'bytes': len(data),
                     'sha256': digest, 'canonical': target, 'kind': 'SOURCE_ORIGINAL'})
        if p.suffix.lower() == '.zip':
            if zipfile.is_zipfile(io.BytesIO(data)):
                unpack(data, source['source_relative'])
                source['unpack_state'] = 'ALL_MEMBERS_INDEXED_RECURSIVELY'
            else:
                source['unpack_state'] = 'UNREADABLE_ORIGINAL_PRESERVED'
    aliases = Counter(r['sha256'] for r in rows)
    unique = {r['sha256']: r for r in rows}
    payload = {'schemaVersion': 'design-lab/complete-record-archive/v1', 'date': '2026-10-09',
               'source_root': str(SOURCE), 'observed_head': subprocess.check_output(
                   ['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
               'state': 'INERT_HISTORICAL_INPUT_NOT_AUTHORITY', 'git_large_objects': False,
               'top_level': top, 'source_files': sources, 'aliases': rows,
               'summary': {'top_level_entries': len(top), 'source_files': len(sources),
                           'archived_source_files': sum('canonical' in s for s in sources),
                           'logical_records': len(rows), 'unique_contents': len(unique),
                           'duplicate_aliases': len(rows) - len(unique),
                           'logical_bytes': sum(r['bytes'] for r in rows),
                           'unique_content_bytes': sum(r['bytes'] for r in unique.values()),
                           'new_object_bytes': sum(r['bytes'] for k, r in unique.items() if k not in seeded)},
               'deduplication': [{'sha256': h, 'canonical': unique[h]['canonical'], 'aliases': n}
                                  for h, n in sorted(aliases.items()) if n > 1],
               'limitations': ['相同hash只新增一个实体，原路径全部索引；不删除既有权威/冻结证据',
                               '完整大包/素材在项目本地ignored档案；Git单独克隆不带大对象',
                               '同名不同内容分别保留；跨项目参考不作为当前派工或许可批准']}
    write(MANIFEST, (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode())
    render(payload)


def render(m):
    summary = m['summary']
    lines = ['# Record 资料固定入口与完整归档索引', '',
             '这是资料定位索引，非Authority、非第二任务状态账本。当前派工仍为20261009桌面UI优先统一包。', '',
             '查找顺序：先本索引 → 文件名/成员别名 → canonical项目内路径。无需反复回Record寻找。',
             '原任务包/Agent提示词全部惰性保存；不据其授权安装、写宿主或升级旧任务状态。', '',
             f'统计：扫描{summary["top_level_entries"]}个顶层条目、{summary["source_files"]}个源文件；完整归档{summary["archived_source_files"]}个相关源文件。',
             f'包含递归ZIP成员的{summary["logical_records"]}条来源记录对应{summary["unique_contents"]}份唯一内容；{summary["duplicate_aliases"]}条重复来源复用实体。',
             f'新增对象{summary["new_object_bytes"]:,}字节；既有副本按hash复用。原卷未删改，旧固定路径未删除。', '',
             '原始ZIP＋逐成员内容均已登记；JPEG/PNG/字体、B01–B10旧UI图包以及混合作品集的相关内容完整保留。',
             '全量对象位于本项目.project-local/task-artifacts/record-archive-2026-10-09/或登记的既有本项目副本；不是EXTERNAL-ONLY指针。',
             '大对象未进入Git：换机器须连同索引所引用的本地档案/原ZIP迁移，不能声称仅clone即完整。', '',
             '只读复验：`.venv/Scripts/python.exe scripts/archive_record_design_lab.py`',
             '与原Record比对：加`--source-check`；默认复验只读项目内档案，不依赖Record仍在线。',
             '按名称查找：`.venv/Scripts/python.exe scripts/archive_record_design_lab.py --find "关键词"`', '',
             f'机器清单：`{MANIFEST}`；成员索引：`{META}/MEMBER-INDEX.md`。', '',
             '## 已归档源文件', '', '|原文件名/源相对路径|归属|唯一实体位置|', '|---|---|---|']
    for s in m['source_files']:
        if 'canonical' in s:
            absolute = (REPO / s['canonical']).as_posix()
            lines.append(f'|{s["source_relative"]}|{s["disposition"]}|[打开](<{absolute}>) · `{s["canonical"]}`|')
    lines += ['', '## 全卷登记与未混入项', '', '|条目|文件数|相关归档数|字节|', '|---|---|---|---|']
    lines += [f'|{t["name"]}|{t["files"]}|{t["relevant_files"]}|{t["bytes"]}|' for t in m['top_level']]
    lines += ['', '未混入项的逐文件分类证据在机器清单source_files；其它项目专有大档案未按全卷整复制。',
              '项目边界：AAOS属于独立项目。AAOS自身任务及文件读取异常不计入DESIGN-LAB待办、阻塞或未完成项；全卷登记中的相关元数据仅供来源定位，跨项目归档仅作合同/历史参考。',
              '本轮范围的完整性定义：相关原件/共享容器及其全部递归ZIP成员均保留并复验；归档不等于rights准入或产品实现。']
    write('docs/RECORD-ARCHIVE-INDEX.md', ('\n'.join(lines) + '\n').encode(), replace=True)
    members = ['# 文件与ZIP成员别名索引', '', '每条原身份对应唯一内容；同hash同canonical，同名异hash保留。', '',
               '|来源身份（::表示ZIP层级）|字节|SHA-256|唯一存放位置|', '|---|---|---|---|']
    for r in m['aliases']:
        absolute = (REPO / r['canonical']).as_posix()
        members.append(f'|{r["origin"].replace("|", "&#124;")}|{r["bytes"]}|{r["sha256"]}|[打开](<{absolute}>) · `{r["canonical"]}`|')
    write(META + '/MEMBER-INDEX.md', ('\n'.join(members) + '\n').encode(), replace=True)


def verify(m, check_source=False):
    origins = {r['origin']: r for r in m['aliases']}
    if len(origins) != len(m['aliases']):
        raise ValueError('duplicate logical origin')
    mapping = {}
    for r in m['aliases']:
        if mapping.setdefault(r['sha256'], r['canonical']) != r['canonical']:
            raise ValueError('same content has multiple archive canonical locations')
    for digest, relative in mapping.items():
        if sha(safe(relative)) != digest:
            raise ValueError('canonical bytes changed/missing: ' + relative)
    def members(data, origin):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            expected = [i for i in z.infolist() if not i.is_dir()]
            registered = [r for r in m['aliases'] if r['kind'] == 'ZIP_MEMBER' and r['origin'].rsplit('::', 1)[0] == origin]
            if len(expected) != len(registered):
                raise ValueError('member inventory differs: ' + origin)
            for i in expected:
                raw = z.read(i)
                identity = origin + '::' + i.filename.replace('\\', '/')
                r = origins[identity]
                if len(raw) != r['bytes'] or hashlib.sha256(raw).hexdigest() != r['sha256']:
                    raise ValueError('member bytes differ: ' + identity)
                if i.filename.lower().endswith('.zip'):
                    members(raw, identity)
    if check_source:
        current_files = set()
        for item in SOURCE.iterdir():
            if item.is_symlink() or item.is_junction():
                raise ValueError('source link not followed')
            for p in item.rglob('*') if item.is_dir() else [item]:
                if p.is_symlink() or p.is_junction():
                    raise ValueError('source link not followed')
                if p.is_file():
                    current_files.add(p.relative_to(SOURCE).as_posix())
        if current_files != {s['source_relative'] for s in m['source_files']}:
            raise ValueError('Record source inventory changed; archive needs a new dated reconciliation')
    for s in m['source_files']:
        if check_source:
            p = SOURCE / s['source_relative']
            if p.stat().st_size != s['bytes'] or p.stat().st_mtime_ns != s['mtime_ns']:
                raise ValueError('source size/time changed: ' + str(p))
        if 'canonical' not in s:
            continue
        if check_source and sha(p) != s['sha256']:
            raise ValueError('source hash changed: ' + str(p))
        if s['source_relative'].lower().endswith('.zip'):
            data = disk(safe(s['canonical'])).read_bytes()
            if zipfile.is_zipfile(io.BytesIO(data)):
                members(data, s['source_relative'])
            elif s.get('unpack_state') != 'UNREADABLE_ORIGINAL_PRESERVED':
                raise ValueError('unregistered unreadable container')
    print('RECORD_ARCHIVE=PASS ' + ' '.join(f'{k}={v}' for k, v in m['summary'].items()))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--find')
    ap.add_argument('--source-check', action='store_true', help='also compare the original Record source; default archive verification is project-local')
    ap.add_argument('--refresh-index', action='store_true', help='rebuild only the derived human indexes from the manifest')
    args = ap.parse_args()
    if args.apply:
        apply()
    manifest = json.loads((REPO / MANIFEST).read_text(encoding='utf-8'))
    if args.refresh_index:
        render(manifest)
    if args.find:
        found = [r for r in manifest['aliases'] if args.find.casefold() in r['origin'].casefold()]
        print(json.dumps(found, ensure_ascii=False, indent=2))
    else:
        verify(manifest, check_source=args.source_check or args.apply)
