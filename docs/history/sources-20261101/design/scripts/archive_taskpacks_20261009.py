# SPDX-License-Identifier: MIT
"""Archive the two explicitly supplied inputs without executing their contents.

Default is readback only. --apply performs the owner-authorized local archive.
Large originals stay in the ignored project-local evidence root (Git pack budget).
Every ZIP member has a hash and a local landing; text/code copies are versionable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = 'docs/history/taskpacks/20261009-inputs'
LOCAL = '.project-local/task-artifacts/taskpacks-20261009'
SOURCES = [
    ('final', Path('D:/All projects/Record/DESIGN-LAB_最终任务包_20261009.zip')),
    ('ui', Path('D:/All projects/Record/DESIGN-LAB_UI前端任务包_20261009.zip')),
]
TEXT = {'.md', '.txt', '.json', '.html', '.css', '.js', '.mjs', '.py', '.svg', '.cmd'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe(relative):
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or '\\' in relative or ':' in relative:
        raise ValueError('escaping archive member')
    target = ROOT.joinpath(*rel.parts)
    if not target.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('archive destination escaped project')
    for p in (target, *target.parents):
        if p == ROOT:
            break
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('archive destination traverses link')
    return target


def put(relative, raw):
    target = safe(relative)
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError('refusing to overwrite different archive bytes: ' + relative)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def apply():
    packages = []
    for kind, source in SOURCES:
        raw = source.read_bytes()
        zip_rel = f'{LOCAL}/originals/{source.name}'
        put(zip_rel, raw)
        rows = []
        with zipfile.ZipFile(source) as z:
            bad = z.testzip()
            if bad:
                raise ValueError('ZIP CRC failure: ' + bad)
            for info in z.infolist():
                if info.is_dir():
                    continue
                member = PurePosixPath(info.filename)
                if member.is_absolute() or '..' in member.parts:
                    raise ValueError('escaping input member')
                relative = '/'.join(member.parts[1:])
                data = z.read(info)
                local = f'{LOCAL}/extracted/{kind}/{relative}'
                put(local, data)
                tracked = None
                if member.suffix.lower() in TEXT:
                    tracked = f'{ARCHIVE}/{kind}/{relative}'
                    put(tracked, data)
                rows.append({'member': info.filename, 'bytes': len(data),
                             'sha256': digest(data), 'crc32': f'{info.CRC:08x}',
                             'repository_text': tracked, 'local_copy': local,
                             'state': 'FROZEN_INPUT_NOT_DISPATCH'})
        packages.append({'kind': kind, 'source': str(source), 'bytes': len(raw),
                         'sha256': digest(raw), 'local_original': zip_rel,
                         'members': rows})
    manifest = {'schemaVersion': 'design-lab/taskpack-input-archive/v1',
                'date': '2026-10-09', 'owner_intent': '新发任务包梳理归档到本项目；UI优先；手机端延后或冻结',
                'originals_git_tracked': False,
                'reason': '242.71 MiB observed Git pack, 256 MiB hard budget; full local originals preserved',
                'packages': packages}
    put(f'{ARCHIVE}/ARCHIVE-MANIFEST.json',
        (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode())


def verify():
    manifest = json.loads(safe(f'{ARCHIVE}/ARCHIVE-MANIFEST.json').read_text(encoding='utf-8'))
    n = 0
    local_missing = []
    for package in manifest['packages']:
        for field in ('source', 'local_original'):
            p = Path(package[field]) if field == 'source' else safe(package[field])
            if p.exists():
                if digest(p.read_bytes()) != package['sha256']:
                    raise ValueError('original hash mismatch: ' + str(p))
            else:
                local_missing.append(str(p))
        for row in package['members']:
            for field in ('repository_text', 'local_copy'):
                if not row[field]:
                    continue
                p = safe(row[field])
                if not p.exists():
                    if field == 'repository_text':
                        raise ValueError('versionable input missing: ' + row[field])
                    local_missing.append(row[field])
                    continue
                data = p.read_bytes()
                if len(data) != row['bytes'] or digest(data) != row['sha256']:
                    raise ValueError('member hash mismatch: ' + row[field])
            n += 1
    print(f'TASKPACK_ARCHIVE={"PARTIAL_LOCAL_MEDIA_ABSENT" if local_missing else "PASS"} '
          f'packages={len(manifest["packages"])} members={n} local_missing={len(local_missing)}')
    return 1 if local_missing else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        apply()
    raise SystemExit(verify())
