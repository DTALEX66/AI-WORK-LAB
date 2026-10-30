# SPDX-License-Identifier: MIT
"""V06: unified knowledge/solution retrieval — 1-char and 2-char Chinese short
queries, no-result queries, the STALE-revision refusal (one writer reads the number
another writer already committed), index rebuild without data loss, restart readback.

Not covered here, whatever this docstring used to say: real simultaneous writers.
The revision conflict below is serial, not raced. The race lives in
`tests/legacy/design/test_knowledge_library.py::KnowledgeLibraryTests::test_two_simultaneous_revisers_cannot_both_land`
(two `revise(expected_revision=N)` calls released by one Barrier) and, on the unified
envelope, in `tests/unified/test_v03_work_loop.py::test_concurrent_attempt_update_refuses_the_loser`.
"Restart readback" here also only reopens stores over the same files inside this
process; the real second process is `tests/unified/test_v17_process_restart.py`.
"""
from __future__ import annotations

from design_lab.knowledge_library import KnowledgeLibrary

SOURCE = {'sourceId': 'owner-note', 'origin': 'UNKNOWN', 'author': 'owner',
          'license': 'UNKNOWN', 'licenseStatus': 'unknown', 'allowedUsage': 'UNKNOWN',
          'citationScope': 'UNKNOWN', 'version': '1', 'observedAt': '2026-10-30T00:00:00Z',
          'contentHash': 'UNKNOWN', 'verification': 'UNVERIFIED'}


def _entry(**overrides):
    body = {
        'entry_type': 'METHOD',
        'title': '分镜拆解三步法',
        'summary': '把一段脚本拆成镜头表：先定节拍，再定景别，最后定转场。',
        'domain_tags': ['film'],
        'task_tags': ['storyboard'],
        'target_tools': ['storyboarder'],
        'body': '第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场。',
        'applicability': '适合 30-90 秒短片的分镜前置。',
        'limits': '不适用于需要精确口型对位的动画。',
        'source': dict(SOURCE),
        'related_capability_ids': [],
        'recommended': True,
        'created_by': 'owner',
        'supersedes': None,
    }
    body.update(overrides)
    return body


def _library(server):
    return KnowledgeLibrary(server.design_service)


def test_create_search_short_queries_and_no_result(server):
    library = _library(server)
    created = library.create(_entry())
    entry_id = created['entry']['knowledge_entry_id']

    # 2-char Chinese word: the trigram index alone cannot match it; the mandatory
    # LIKE fallback is what finds it
    found = library.search(query='分镜')
    assert any(row['knowledge_entry_id'] == entry_id for row in found['entries'])

    # 1-char query still routes through the fallback and answers
    single = library.search(query='镜')
    assert isinstance(single['entries'], list)

    # no result is legal data, not an error
    empty = library.search(query='量子色动力学urrence')
    assert empty['entries'] == []

    # browse (no query) lists entries
    browse = library.search()
    assert any(row['knowledge_entry_id'] == entry_id for row in browse['entries'])


def test_revision_conflict_and_index_rebuild(server):
    library = _library(server)
    created = library.create(_entry(title='修复方案：缓存穿透', summary='用布隆过滤器挡住穿透。'))
    entry_id = created['entry']['knowledge_entry_id']
    revision = created['entry']['revision']

    # a revise against a stale revision is refused, not silently applied
    try:
        library.revise(entry_id, _entry(title='并发写作者乙', expected_revision=revision + 5))
        raise AssertionError("stale revise should be refused")
    except ValueError as error:
        assert getattr(error, 'code', '') == 'KNOWLEDGE_ENTRY_REVISION_CONFLICT'

    # the honest writer wins: revise against the revision it actually saw
    revised = library.revise(entry_id, _entry(title='修复方案：缓存穿透（修订）',
                                              expected_revision=revision))
    assert revised['entry']['revision'] == revision + 1
    assert revised['entry']['title'] == '修复方案：缓存穿透（修订）'

    # the index is derived: dropping and rebuilding it loses nothing
    library.rebuild_index()
    after = library.search(query='节拍')
    assert any(row['knowledge_entry_id'] == entry_id for row in after['entries'])

    # restart readback: a fresh library instance over the same store
    reopened = _library(server)
    detail = reopened.detail(entry_id)
    assert detail['current']['revision'] == revision + 1
    assert detail['current']['title'] == '修复方案：缓存穿透（修订）'


def test_unified_search_endpoint_merges_both_libraries(server):
    library = _library(server)
    created = library.create(_entry())
    status, unified = server.client.get('/api/v1/knowledge/search?q=%E5%88%86%E9%95%9C')
    assert status == 200
    assert any(row['knowledge_entry_id'] == created['entry']['knowledge_entry_id']
               for row in unified['knowledge']['entries'])
    assert 'solutions' in unified
    assert 'content_types' in unified
