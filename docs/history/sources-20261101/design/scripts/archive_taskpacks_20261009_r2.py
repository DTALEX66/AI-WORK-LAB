#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Archive the 20261009 **R2** UI package into this repository.

Same rules the 20261009 R1 adoption used, restated because the owner's standing instruction
is that new material must arrive with its source, hash, version/final state, aliases and
canonical location registered -- not just copied:

  * the original ZIP is kept byte-for-byte under `.project-local/` (never committed: the
    observed Git pack is already past the warn line, and a 19 MiB binary would make it worse);
  * text/code members are copied into the repository so a clone can read the contract
    without the ZIP;
  * binary members (screens, art, fonts) land in `.project-local/` and are addressed by
    hash, so a cross-machine handoff must carry the ZIP;
  * a member whose bytes already exist in the R1 archive is **not duplicated**: the record
    points at the existing canonical path (`reuse_of`), because two copies of one input is
    how they start to disagree.

Read-only re-verification: `--check`, which re-hashes the members already in the repository
against the stored manifest and needs neither the ZIP nor `.project-local` -- a clone can run
it. Writing: `--apply`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/All projects/Record/DESIGN-LAB_UI_R2_成熟方案与前端任务包_20261009.zip')
# Declared, not discovered: a different byte stream is a different package, and silently
# archiving one would make every downstream hash meaningless.
SOURCE_SHA256 = '99921131982a7fe4acf9869edf9608f13254539f790ecb8707b5346afff59fbf'
PREFIX = 'DESIGN-LAB_UI_R2_20261009/'
TRACKED_DIR = Path('docs/history/taskpacks/20261009-r2-inputs/ui-r2')
LOCAL_DIR = Path('.project-local/task-artifacts/taskpacks-20261009-r2')
MANIFEST = TRACKED_DIR / 'ARCHIVE-MANIFEST.json'
# R1's archive is the dedup source of truth: same bytes, same object, one canonical path.
R1_MANIFEST = Path('docs/history/taskpacks/20261009-inputs/ARCHIVE-MANIFEST.json')
TEXT_SUFFIXES = {'.md', '.json', '.txt', '.html', '.htm', '.css', '.js', '.mjs',
                 '.py', '.csv', '.cmd', '.svg', '.yml', '.yaml'}


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _r1_index() -> dict:
    if not R1_MANIFEST.is_file():
        return {}
    doc = json.loads(R1_MANIFEST.read_text(encoding='utf-8'))
    index = {}
    for package in doc.get('packages', []):
        for member in package.get('members', []):
            digest = member.get('sha256')
            canonical = member.get('repository_text') or member.get('local_copy')
            if digest and canonical and digest not in index:
                index[digest] = {'path': canonical, 'bytes': member.get('bytes')}
    return index


def build(apply: bool) -> tuple[dict, list[str]]:
    problems: list[str] = []
    if not SOURCE.is_file():
        return {'error': f'source zip missing: {SOURCE}'}, [f'SOURCE_MISSING {SOURCE}']
    raw = SOURCE.read_bytes()
    digest = sha256_of(raw)
    if digest != SOURCE_SHA256:
        return {}, [f'SOURCE_HASH_DIFFERS expected={SOURCE_SHA256[:16]}… observed={digest[:16]}…']

    r1 = _r1_index()
    members = []
    with zipfile.ZipFile(SOURCE) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not name.startswith(PREFIX):
                problems.append(f'OUTSIDE_PREFIX {name}')
                continue
            rel = name[len(PREFIX):]
            data = archive.read(info)
            member_sha = sha256_of(data)
            suffix = Path(rel).suffix.lower()
            record = {
                'member': name,
                'path': rel,
                'bytes': info.file_size,
                'sha256': member_sha,
                'crc32': format(info.CRC & 0xFFFFFFFF, '08x'),
                'state': 'FROZEN_INPUT_NOT_DISPATCH',
            }
            reuse = r1.get(member_sha)
            if reuse:
                record['reuse_of'] = reuse['path']
                record['disposition'] = 'REUSED_FROM_R1_ARCHIVE_BY_HASH'
            elif suffix in TEXT_SUFFIXES:
                record['repository_text'] = str(TRACKED_DIR / rel).replace('\\', '/')
                record['disposition'] = 'TRACKED_TEXT'
            else:
                record['local_copy'] = str(LOCAL_DIR / 'extracted' / rel).replace('\\', '/')
                record['disposition'] = 'LOCAL_BINARY_NOT_IN_GIT'
            members.append(record)

            if not apply:
                continue
            if 'repository_text' in record:
                target = REPO / record['repository_text']
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_file() and sha256_of(target.read_bytes()) != member_sha:
                    problems.append(f'TRACKED_DRIFT {record["repository_text"]}')
                    continue
                target.write_bytes(data)
            elif 'local_copy' in record:
                target = REPO / record['local_copy']
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.is_file() or sha256_of(target.read_bytes()) != member_sha:
                    target.write_bytes(data)

    original_copy = LOCAL_DIR / 'originals' / SOURCE.name
    if apply:
        original_copy.parent.mkdir(parents=True, exist_ok=True)
        if not original_copy.is_file() or sha256_of(original_copy.read_bytes()) != digest:
            shutil.copyfile(SOURCE, original_copy)

    counts: dict[str, int] = {}
    for record in members:
        counts[record['disposition']] = counts.get(record['disposition'], 0) + 1
    doc = {
        'schemaVersion': 'design-lab/taskpack-input-archive/v2',
        'date': '2026-10-09',
        'owner_intent': '分析有用的加入到UI任务里，并做好项目仓库归档（R2 成熟方案与前端任务包）',
        'originals_git_tracked': False,
        'reason': '原 ZIP 与位图/字体留在 .project-local/，不提交：仓库 pack 已越过 220 MiB 警戒线；'
                  '文本/代码/SVG 逐字节入仓，跨机器交接须另附原 ZIP',
        'supersedes': {
            'for_information_architecture': 'UI-20261009-r1',
            'kept_from_r1': '交互细节、文案与验收语义仍在 specs/r1/ 的既有归档里',
            'crosswalk': 'docs/history/archive-2026-10-19/taskpacks/20261009-r2-ui/CROSSWALK.md',
        },
        'packages': [{
            'kind': 'ui-r2',
            'source': str(SOURCE).replace('\\', '/'),
            'bytes': len(raw),
            'sha256': digest,
            'local_original': str(original_copy).replace('\\', '/'),
            'member_count': len(members),
            'disposition_counts': counts,
            'members': members,
        }],
    }
    return doc, problems


def verify(doc: dict) -> list[str]:
    """--check: every tracked text member must still match the hash recorded for it."""
    bad = []
    for record in doc['packages'][0]['members']:
        path = record.get('repository_text')
        if path and (REPO / path).is_file():
            if sha256_of((REPO / path).read_bytes()) != record['sha256']:
                bad.append(f'TRACKED_DRIFT {path}')
        elif path:
            bad.append(f'TRACKED_MISSING {path}')
    return bad


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='写入仓内/本地副本与原 ZIP 归档')
    parser.add_argument('--check', action='store_true',
                        help='只读复验已入仓文本成员的哈希；不读源 ZIP，也不写任何文件')
    args = parser.parse_args(argv)

    if args.check:
        # The subject of `--check` is the stored record plus the bytes already in the repository;
        # neither needs the source ZIP, which is never committed (see the module docstring).
        # Building first put a writer-path prerequisite in front of the read-only form, so the
        # check was unreachable on every checkout that does not carry the ZIP: measured
        # 2026-10-13, exit 2 `ARCHIVE_BLOCKED: source zip missing` on CI, exit 0 on a machine
        # that happens to have D:/All projects/Record. A check that answers differently per
        # machine is not a repository property and cannot be required; this one now can be.
        if not MANIFEST.is_file():
            print(f'ARCHIVE_CHECK=FAIL missing {MANIFEST.relative_to(REPO).as_posix()}')
            return 1
        stored = json.loads(MANIFEST.read_text(encoding='utf-8'))
        problems = verify(stored)
        counts = stored['packages'][0]['disposition_counts']
        print(f"R2_ARCHIVE mode=check members={stored['packages'][0]['member_count']} "
              f"tracked={counts.get('TRACKED_TEXT', 0)} local={counts.get('LOCAL_BINARY_NOT_IN_GIT', 0)} "
              f"reused_from_r1={counts.get('REUSED_FROM_R1_ARCHIVE_BY_HASH', 0)} "
              f"problems={len(problems)}")
        for problem in problems[:12]:
            print(f'  {problem}')
        return 1 if problems else 0

    doc, problems = build(apply=args.apply)
    if 'error' in doc:
        print(f'ARCHIVE_BLOCKED: {doc["error"]}')
        return 2
    if args.apply:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n',
                            encoding='utf-8', newline='\n')
    counts = doc['packages'][0]['disposition_counts']
    print(f"R2_ARCHIVE mode={'apply' if args.apply else 'dry-run'} "
          f"members={doc['packages'][0]['member_count']} "
          f"tracked={counts.get('TRACKED_TEXT', 0)} local={counts.get('LOCAL_BINARY_NOT_IN_GIT', 0)} "
          f"reused_from_r1={counts.get('REUSED_FROM_R1_ARCHIVE_BY_HASH', 0)} "
          f"problems={len(problems)}")
    for problem in problems[:12]:
        print(f'  {problem}')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
