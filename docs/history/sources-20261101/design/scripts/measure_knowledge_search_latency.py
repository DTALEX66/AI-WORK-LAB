#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure local knowledge-search latency over 1,000 real-structure samples (DL-KB-13).

The card asks for 1,000 条真实结构样例的本地搜索 p95 与普通操作反馈目标分别测量, and forbids
「感觉变快了」. So this file measures one thing and says what it does not:

* samples are built through the same store a person writes through, so the FTS5 trigram index and
  the short-term fallback see data shaped like production, not a hand-made fixture;
* percentiles are computed from the measured list, never estimated from a mean;
* it reports no inference or model latency. Analysis latency is a separate number on a separate
  surface and mixing the two is how a UI budget ends up being judged by a GPU;
* the database path is created here and asserted absent first: a store constructor that silently
  opens an existing file would report timings about somebody's leftover corpus.

    python scripts/measure_knowledge_search_latency.py [--samples 1000] [--repeat 30]
"""
from __future__ import annotations

import argparse
import math
import platform
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))

from design_lab.knowledge_library import KnowledgeLibrary, UNKNOWN  # noqa: E402
from design_lab.service import ProjectService  # noqa: E402

TITLES = ('分镜拆解三步法', '粒子转场配方', '品牌色板收敛', '海报留白比例', '镜头目的说明',
          '油墨限制与印刷', '短视频开场节奏', '配音情绪对照', '3D 材质说明', 'UI 状态穷举')
BODIES = ('第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场。',
          '主体、材质、风格、技术约束四段各写一句，不靠加长提示词。',
          '两种油墨，一个专色，暗部不压死；参考只作风格不作复制对象。')
QUERIES = ('分镜', '粒子', '品牌', '转场', '油墨', '景别', '材质', '配音', 'poster', 'storyboard')


def percentile(values: list[float], point: float) -> float:
    """Nearest-rank percentile. An estimate dressed as a measurement is worse than no number.

    The rank is `ceil(point/100 * n)`, 1-based. An earlier draft computed it with floor division on
    a negated value, which returned the maximum for every point -- so p50, p95 and max printed
    identical numbers and the whole table was an artifact of the instrument, not of the machine.
    """
    if not values:
        raise SystemExit('MEASURE_NO_SAMPLES nothing was timed -- the loop never ran')
    if not 0 < point <= 100:
        raise SystemExit(f'MEASURE_BAD_PERCENTILE {point} is not between 0 and 100')
    ordered = sorted(values)
    rank = math.ceil(point / 100 * len(ordered))
    return ordered[min(max(rank, 1), len(ordered)) - 1]


def seed(store, project: str, samples: int) -> int:
    for index in range(samples):
        title = f'{TITLES[index % len(TITLES)]} · 变体 {index + 1:04d}'
        body = BODIES[index % len(BODIES)] + f' 第 {index + 1} 条样例，用于稳定语料规模。'
        store.create({
            'entry_type': 'METHOD', 'title': title, 'summary': body[:120],
            'domain_tags': ['film', 'brand'], 'task_tags': ['storyboard'],
            'target_tools': ['storyboarder'], 'body': body,
            'applicability': '测量用样例，不作为正式知识', 'limits': '不代表任何项目结论',
            'source': {'sourceId': f'measure-{index % 40}', 'origin': UNKNOWN, 'author': 'measure',
                       'license': UNKNOWN, 'licenseStatus': 'unknown', 'allowedUsage': UNKNOWN,
                       'citationScope': UNKNOWN, 'version': str(index % 7 + 1),
                       'observedAt': '2026-10-24T00:00:00Z', 'contentHash': UNKNOWN,
                       'verification': 'UNVERIFIED'},
            'related_capability_ids': [], 'recommended': True, 'created_by': 'measure',
            'supersedes': None,
        })
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=1000)
    parser.add_argument('--repeat', type=int, default=30)
    args = parser.parse_args()
    if args.samples < 1 or args.repeat < 1:
        raise SystemExit('MEASURE_ARGS samples and repeat must both be positive')

    runtime = REPO / '.project-local' / 'task-runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    root = runtime / f'latency-{int(time.time())}-{time.perf_counter_ns() % 1000:03d}'
    if root.exists():
        raise SystemExit(f'MEASURE_PATH_COLLIDES {root} already exists; refusing to reuse a corpus')
    (root / 'project').mkdir(parents=True)
    (root / 'project' / 'AGENTS.md').write_text('# latency measurement corpus', encoding='utf-8')
    try:
        service = ProjectService(root / 'project')
        project = service.create_project('Latency Measure')['id']
        store = KnowledgeLibrary(service)
        built = seed(store, project, args.samples)
        # Warm the index the same way a first real query does, then measure steady state.
        store.search(query=QUERIES[0])
        timings: list[float] = []
        hits_total = 0
        for attempt in range(args.repeat):
            query = QUERIES[attempt % len(QUERIES)]
            started = time.perf_counter()
            answer = store.search(query=query, limit=50)
            timings.append((time.perf_counter() - started) * 1000.0)
            hits_total += answer['total']
        writes: list[float] = []
        for extra in range(20):
            started = time.perf_counter()
            store.create({
                'entry_type': 'CASE', 'title': f'写入计时 {extra}',
                'summary': '普通操作反馈的写入侧读数', 'domain_tags': ['film'],
                'task_tags': ['storyboard'], 'target_tools': [], 'body': '正文',
                'applicability': '测量', 'limits': '测量',
                'source': {'sourceId': 'measure', 'origin': UNKNOWN, 'author': 'measure',
                           'license': UNKNOWN, 'licenseStatus': 'unknown', 'allowedUsage': UNKNOWN,
                           'citationScope': UNKNOWN, 'version': '1',
                           'observedAt': '2026-10-24T00:00:00Z', 'contentHash': UNKNOWN,
                           'verification': 'UNVERIFIED'},
                'related_capability_ids': [], 'recommended': True, 'created_by': 'measure',
                'supersedes': None})
            writes.append((time.perf_counter() - started) * 1000.0)
        detail: list[float] = []
        listed = store.search(limit=50)   # unfiltered browse, the same path a list uses
        for row in listed['entries'][:12]:
            started = time.perf_counter()
            store.detail(row['knowledge_entry_id'])
            detail.append((time.perf_counter() - started) * 1000.0)
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)

    host = f'{platform.system()} {platform.release()} / {platform.machine()} / ' \
           f'{platform.python_version()}'
    print(f'LATENCY host={host}')
    print(f'LATENCY corpus samples={built} queries={args.repeat} '
          f'total_hits={hits_total} avg_hits={hits_total / args.repeat:.1f}')
    for label, values in (('search', timings), ('create', writes), ('detail', detail)):
        if not values:
            raise SystemExit(f'MEASURE_NO_SAMPLES {label} produced no timings')
        print(f'LATENCY {label} n={len(values)} p50={percentile(values, 50):.2f}ms '
              f'p95={percentile(values, 95):.2f}ms max={max(values):.2f}ms '
              f'mean={statistics.fmean(values):.2f}ms')
    print('LATENCY NOTE 这是本机冷磁盘单进程读数，不含网络、不含推理；推理延迟单独报，'
          '不与界面指标混合。数据库目录已随测量删除，语料是测量生成的，不是 owner 的条目。')
    print(f'LATENCY=MEASURED search_p95={percentile(timings, 95):.2f}ms')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
