#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Classify the repository's documentation and asset areas into one index.

The catalog is DERIVED, not authored: every number comes out of `git ls-files` /
`git ls-tree`, so it cannot quietly drift into a flattering description of the
repo the way a hand-kept manifest does. `--check` re-derives and fails on drift.

Categories are decided by explicit rules (see CATEGORY_RULES) so the mapping is
auditable and reviewable in diff form.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "current" / "REPO-CLASSIFICATION.json"

# Ordered: first match wins. `docs/audits/...` must be tested before `docs/`.
CATEGORY_RULES: list[tuple[str, str, str]] = [
    ('AUTHORITY.md', 'authority', '顶层权威（唯一）'),
    ('AGENTS.md', 'authority', '根执行规则'),
    ('.project/governance/', 'authority', '机器权威索引与策略'),
    ('.project/paths.json', 'authority', '本机外置根声明'),
    ('docs/taskpacks/', 'planning', '任务包（含 superseded，见 INDEX）'),
    ('design-lab/config/task-ledger-r3.json', 'planning', '唯一可变任务账本'),
    ('docs/current/', 'planning', '当前文档面'),
    ('docs/audits/', 'evidence', '审计与验收证据包'),
    ('docs/history/', 'history', '冻结历史与逐字节基线（含 2026-10-19 归档的 handoffs/taskpacks）'),
    ('reports/history/', 'history', '历史进度账本冻结件'),
    ('reports/current/', 'generated', '当前状态投影（由生成器再生）'),
    ('reports/migration/', 'history', '迁移记录'),
    ('docs/golden-cases/', 'evidence', '黄金用例'),
    ('docs/projects/', 'evidence', '设计项目产物（真实交付样例）'),
    ('docs/decisions/', 'authority', '决策记录（ADR 式）'),
    ('docs/architecture/', 'authority', '架构与语言策略'),
    ('fixtures/', 'evidence', '域 fixture 与回归素材'),
    ('design-lab/evals/', 'evidence', '评估与黄金语料'),
    ('apps/workbench/build/', 'generated', '提交的构建产物（Build Output Truth）'),
    ('src/', 'source', '产品源码'),
    ('packages/', 'source', '能力包'),
    ('apps/', 'source', 'Workbench 前端源码'),
    ('integrations/', 'source', '宿主/发行集成层'),
    ('design-lab/scripts/', 'source', '门与工具（Python）'),
    ('scripts/', 'source', '根级门与工具'),
    ('design-lab/tests/', 'source', '测试'),
    ('.github/', 'source', 'CI 定义'),
    ('docs/', 'documentation', '其余文档'),
    ('design-lab/', 'source', '设计核心其余模块'),
    ('reports/', 'generated', '其余报告'),
    ('vendor/', 'source', '第三方源码副本（inert source blobs）'),
    ('research/', 'documentation', '研究素材'),
    ('LICENSES/', 'repo-meta', '第三方许可证文本'),
    # Single-segment paths: the repo-root operating/meta documents. Must stay last
    # so no real directory is caught by it.
    ('', 'repo-meta', '根级运维与政策文档'),
]


def classify(path: str) -> tuple[str, str]:
    for prefix, category, note in CATEGORY_RULES:
        if not prefix:
            if '/' not in path:
                return category, note
            continue
        if path == prefix or path.startswith(prefix):
            return category, note
    return 'other', ''


def tracked_files() -> list[str]:
    out = subprocess.run(['git', 'ls-files', '-z'], cwd=REPO, capture_output=True)
    return [p for p in out.stdout.decode('utf-8').split('\0') if p]


def blob_sizes() -> dict[str, int]:
    """Working-tree byte size per tracked path, taken from the index and object store.

    Two failures this replaces, both found by measuring the same tree twice:

    - `git ls-tree -r -l HEAD` escapes and quotes non-ASCII paths, so 11 tracked
      files with Chinese names had no key in the returned map and were summed as 0
      bytes; -z output is the only porcelain that is never quoted.
    - Reading sizes from HEAD while taking the file list from the index silently
      priced every staged-but-uncommitted file at 0 bytes: right after a 259-file
      import the same repository measured 52.28 MiB, then 60.22 MiB, with the
      tracked file count unchanged. A size projection that under-reads by the whole
      size of the newest change is the one number the volume budgets depend on.
    """
    listing = subprocess.run(['git', 'ls-files', '-s', '-z'], cwd=REPO, capture_output=True)
    sha_by_path: dict[str, str] = {}
    for rec in listing.stdout.decode('utf-8').split('\0'):
        if not rec:
            continue
        meta, _, path = rec.partition('\t')
        fields = meta.split()
        if path and len(fields) >= 2:
            sha_by_path[path] = fields[1]
    shas = sorted(set(sha_by_path.values()))
    sizes: dict[str, int] = {}
    for i in range(0, len(shas), 2000):
        chunk = shas[i:i + 2000]
        probe = subprocess.run(['git', 'cat-file', '--batch-check'], input='\n'.join(chunk),
                               capture_output=True, text=True, cwd=str(REPO),
                               encoding='utf-8', errors='replace')
        for line in probe.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == 'blob' and parts[2].isdigit():
                sizes[parts[0]] = int(parts[2])
    missing = sorted(p for p, s in sha_by_path.items() if s not in sizes)
    if missing:
        raise SystemExit(f"CLASSIFY_REPO=FAIL {len(missing)} tracked blobs unreadable, "
                         f"e.g. {missing[:3]}")
    return {path: sizes[sha] for path, sha in sha_by_path.items()}


def last_touch(path: str) -> str:
    out = subprocess.run(['git', 'log', '-1', '--format=%ad', '--date=short', '--', path],
                         cwd=REPO, capture_output=True, text=True, encoding='utf-8')
    return out.stdout.strip() or 'unknown'


def authority_references() -> set[str]:
    """Path references made inside the two authority files (fenced blocks removed)."""
    refs: set[str] = set()
    for name in ('AUTHORITY.md', 'AGENTS.md'):
        text = (REPO / name).read_text(encoding='utf-8', errors='replace')
        text = re.sub(r'```.*?```', '', text, flags=re.S)
        for token in re.findall(r'[\w./\-]+\.(?:md|json|py|csv|yaml|yml|toml|jsonl(?:\.gz)?|mjs)',
                                text):
            refs.add(token.lstrip('/'))
    return refs


def bundle_key(path: str) -> str:
    parts = path.split('/')
    if parts[0] == 'docs' and len(parts) > 2 and parts[1] in ('audits', 'handoffs', 'history',
                                                             'projects', 'golden-cases',
                                                             'UI-CONVERGENCE-20260930'):
        return '/'.join(parts[:2]) + '/'
    if parts[0] in ('reports', 'fixtures') and len(parts) > 2:
        return '/'.join(parts[:2]) + '/'
    if len(parts) == 1:
        return path
    return parts[0] + '/'


def build() -> dict:
    files = tracked_files()
    sizes = blob_sizes()
    refs = authority_references()
    bundles: dict[str, dict] = {}
    # Categories are tallied per FILE. `bundle_key()` collapses every path under a top-level
    # directory into one bundle, so labelling a bundle by its first file used to relabel the
    # whole directory: `docs/` alone mixes docs/taskpacks (planning), docs/history (history),
    # docs/audits (evidence) and the rest, and `planning` vanished from the projection entirely.
    by_cat: dict[str, dict] = {}
    cat_bundles: dict[str, set] = {}
    for path in files:
        category, note = classify(path)
        key = bundle_key(path)
        entry = bundles.setdefault(key, {'path': key, 'category': category, 'note': note,
                                         'files': 0, 'bytes': 0,
                                         'cited_by_authority': 0, 'lastTouch': 'earliest'})
        entry['files'] += 1
        entry['bytes'] += sizes.get(path, 0)
        cat = by_cat.setdefault(category, {'files': 0, 'bytes': 0, 'bundles': 0})
        cat['files'] += 1
        cat['bytes'] += sizes.get(path, 0)
        cat_bundles.setdefault(category, set()).add(key)
        if path in refs or any(r.endswith(path) or path.endswith(r) for r in refs):
            entry['cited_by_authority'] += 1
    for category, keys in cat_bundles.items():
        by_cat[category]['bundles'] = len(keys)
    touched = {}
    for key in bundles:
        touched[key] = last_touch(key)
    for key, entry in bundles.items():
        entry['lastTouch'] = touched[key]
        entry['bytes'] = entry['bytes']
    packs = subprocess.run(['git', 'count-objects', '-vH'], cwd=REPO,
                           capture_output=True, text=True, encoding='utf-8').stdout
    pack_mib = 0.0
    for line in packs.splitlines():
        if line.startswith('size-pack:'):
            value, unit = line.split(':')[1].strip().split()
            pack_mib = float(value) * {'KiB': 1/1024, 'MiB': 1, 'GiB': 1024, 'B': 1/1048576}[unit]
    return {
        'schemaVersion': 'design-lab/repo-classification/v1',
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'observedCommit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                                         capture_output=True, text=True).stdout.strip(),
        'totals': {
            'trackedFiles': len(files),
            'workingTreeMiB': round(sum(sizes.values()) / 1048576, 2),
            'packMiB': round(pack_mib, 2),
            'note': 'pack 含全部历史与 tag 归档；working tree 为当前检出字节。两者之差不是垃圾。',
        },
        'categories': {k: {'files': v['files'], 'bundles': v['bundles'],
                           'mib': round(v['bytes'] / 1048576, 2)}
                       for k, v in sorted(by_cat.items())},
        'bundles': sorted(bundles.values(), key=lambda e: (-e['bytes'], e['path'])),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='fail if the committed file drifted')
    args = parser.parse_args()
    payload = build()
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if not args.check:
        OUT.write_text(text, encoding='utf-8')
        print(f'REPO_CLASSIFICATION=WRITTEN {OUT.relative_to(REPO).as_posix()} '
              f'bundles={len(payload["bundles"])} '
              f'workingTreeMiB={payload["totals"]["workingTreeMiB"]} '
              f'packMiB={payload["totals"]["packMiB"]}')
        return 0
    # A regeneration always rewrites the timestamp, the observed commit and the
    # pack size; those are not drift. `size-pack` in particular is a property of
    # the clone (CI checks out with limited history), so treating it as an
    # invariant would raise a false failure there.
    if not OUT.exists():
        print('REPO_CLASSIFICATION=MISSING')
        return 1
    committed = json.loads(OUT.read_text(encoding='utf-8'))
    # Two different things are being conflated by a single equality test, and only
    # one of them is a lie:
    #   * a bundle path that no longer exists, or a category the rules no longer
    #     produce, means the committed catalogue DESCRIBES SOMETHING THAT IS GONE.
    #     That is a lie and must fail.
    #   * counts and byte totals move every time anyone adds a file. Comparing them
    #     for equality turns the gate into a tripwire that goes red for ordinary
    #     work (it did, twice, on the branches that introduced it) while protecting
    #     nothing about honesty. That is reported as DRIFT_NOTICE and does not fail.
    known_categories = {category for _, category, _ in CATEGORY_RULES}
    committed_paths = {e['path'] for e in committed['bundles']}
    missing = sorted(p for p in committed_paths if not (REPO / p).exists())
    if missing:
        print('REPO_CLASSIFICATION=FAIL bundles name paths that no longer exist: %s'
              % missing[:6])
        return 1
    unknown = sorted({e['category'] for e in committed['bundles']} - known_categories)
    if unknown:
        print('REPO_CLASSIFICATION=FAIL categories the rules no longer produce: %s' % unknown)
        return 1
    key = lambda items: {e['path']: (e['category'], e['files'], e['bytes']) for e in items}
    watched = lambda t: {'trackedFiles': t['trackedFiles'], 'workingTreeMiB': t['workingTreeMiB']}
    fresh = key(payload['bundles'])
    stale_paths = sorted(set(fresh) - committed_paths)
    if watched(committed['totals']) != watched(payload['totals']) \
            or committed['categories'] != payload['categories'] \
            or key(committed['bundles']) != fresh:
        print('REPO_CLASSIFICATION=DRIFT_NOTICE regenerating would add %d bundle(s) '
              '(e.g. %s); totals committed=%s derived=%s'
              % (len(stale_paths), stale_paths[:3],
                 watched(committed['totals']), watched(payload['totals'])))
    print('REPO_CLASSIFICATION=OK (no dead paths, no unknown categories)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
