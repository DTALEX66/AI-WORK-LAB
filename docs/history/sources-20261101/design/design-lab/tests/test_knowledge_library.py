# SPDX-License-Identifier: MIT
"""DL-KB-02/04: the knowledge library's store, its revisions, its search and its derived index.

What this suite is for. The library is the first place in this repository where a person can write
knowledge down -- a rule, a method, a prompt pattern, a note about a model. The ways that goes wrong
are not exotic:

* **a field the person did not fill disappears.** The taskpack asks for a complete minimum record
  with UNKNOWN where a value is missing, so "absent" must be visible in the bytes a reader gets,
  not indistinguishable from "empty".
* **a link is read as verification.** Writing a source with a URL must not upgrade it; the stored
  `verification` stays UNVERIFIED and a caller that claims otherwise is refused, because no fetch
  was made and no person reviewed it.
* **a correction overwrites its parent.** Revisions are append-only; "current" is MAX(revision) at
  read time, and a write prepared against a stale revision is refused with the actual number.
* **a two-character Chinese word stops working.** The trigram index cannot answer `分镜` or `粒子`,
  which is most of what a Chinese prompt library is searched with. Half of this file exists to keep
  the fallback from being quietly deleted: the index-alone miss is asserted first, so the fallback
  has a failing control rather than a comment.
* **the index becomes a second truth source.** It is derived; the rebuild test corrupts it and
  requires the canonical rows to restore it.
* **an empty search fills itself with near-matches.** An empty answer must explain why it is empty
  and must not recommend entries the query never matched.
* **A5 is a mood rather than a measurement.** "Writing, searching, editing and copying still work
  with no model service" is only worth anything if something checks it: the library's imports are
  scanned for anything model-, provider- or network-facing (and the scanner is proven on a planted
  import), the model-selection store is asserted empty, and the four acts are then performed. The
  copy leg's bytes are compared against what the route answered -- in Chromium for a granted
  clipboard, and against the refused-clipboard fallback in the DOM harness.

Nothing here proves a model ran, a source was fetched or a person reviewed anything: counts are
records in a local store. The published performance claim (1,000 entries, p95 <= 300 ms) is measured
here against the same constant the docs quote.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab import knowledge_library                        # noqa: E402
from design_lab.knowledge_library import (                      # noqa: E402
    KnowledgeLibrary, KnowledgeLibraryError, UNKNOWN)
from design_lab import model_selection                            # noqa: E402
from design_lab.service import ProjectService                    # noqa: E402

SOURCE = {'sourceId': 'owner-note', 'origin': 'UNKNOWN', 'author': 'owner',
          'license': 'UNKNOWN', 'licenseStatus': 'unknown', 'allowedUsage': 'UNKNOWN',
          'citationScope': 'UNKNOWN', 'version': '1', 'observedAt': '2026-10-23T00:00:00Z',
          'contentHash': 'UNKNOWN', 'verification': 'UNVERIFIED'}


def entry(**overrides):
    """A complete create request. Overrides are how each case states what it is about."""
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


class KnowledgeLibraryTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# knowledge library fixture', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.service.create_project('Knowledge Library')
        self.library = KnowledgeLibrary(self.service)

    # -- one authoritative writer, complete records --------------------------------
    def test_every_minimum_field_is_stored_and_a_silent_field_is_unknown(self):
        silent = self.library.create(entry(
            applicability=None, limits=None,
            source={'sourceId': 'owner-note'}, related_capability_ids=[]))['entry']
        for key in (' applicability'.strip(), 'limits'):
            self.assertEqual(UNKNOWN, silent[key],
                             f'{key} was left out, so the stored bytes must say UNKNOWN instead of '
                             'omitting the key')
        self.assertEqual('UNKNOWN', silent['source']['origin'])
        self.assertEqual('unknown', silent['source']['licenseStatus'],
                         'an UNKNOWN license must be filed as unknown, never as reviewed')
        self.assertEqual('UNVERIFIED', silent['source']['verification'])
        self.assertEqual(silent['content_sha256'],
                         knowledge_library._content_digest(silent),
                         'the stored digest does not cover the bytes it claims to')
        self.assertEqual(1, silent['revision'])
        self.assertIsNone(silent['supersedes'])

    def test_the_three_content_fields_cannot_be_unknown(self):
        for key in ('title', 'summary', 'body'):
            with self.assertRaises(KnowledgeLibraryError) as caught:
                self.library.create(entry(**{key: None}))
            self.assertEqual('KNOWLEDGE_CONTENT_MISSING', caught.exception.code, key)

    def test_a_source_claim_of_verification_is_refused(self):
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.create(entry(source=dict(SOURCE, verification='VERIFIED')))
        self.assertEqual('KNOWLEDGE_SOURCE_VERIFICATION_UNSUPPORTED', caught.exception.code)

    def test_a_source_field_the_contract_does_not_declare_is_refused(self):
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.create(entry(source=dict(SOURCE, url='https://example.invalid/doc')))
        self.assertEqual('KNOWLEDGE_SOURCE_UNKNOWN_FIELD', caught.exception.code,
                         'a link smuggled in under a new key must not be stored as if it counted')

    # -- revisions -------------------------------------------------------------------
    def test_a_revision_appends_and_a_stale_revision_is_refused(self):
        created = self.library.create(entry())['entry']
        entry_id = created['knowledge_entry_id']
        revised = self.library.revise(entry_id, entry(
            title='分镜拆解三步法（修订）', expected_revision=1, recommended=False,
            supersedes='ignored-in-revision-fields'))
        self.assertEqual(2, revised['revision'])
        detail = self.library.detail(entry_id)
        self.assertEqual([1, 2], [row['revision'] for row in detail['revisions']],
                         'the revision replaced its parent instead of appending to it')
        self.assertEqual(created['content_sha256'], detail['revisions'][0]['content_sha256'],
                         'the parent bytes moved when a revision was appended')
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.revise(entry_id, entry(expected_revision=1))
        self.assertEqual(409, caught.exception.status)
        self.assertEqual('KNOWLEDGE_ENTRY_REVISION_CONFLICT', caught.exception.code)
        self.assertIn('2', str(caught.exception), 'the refusal must name the revision that exists')

    def test_the_recommended_revision_can_lag_the_latest_one(self):
        created = self.library.create(entry())['entry']
        entry_id = created['knowledge_entry_id']
        self.library.revise(entry_id, entry(title='较新的草稿', expected_revision=1,
                                            recommended=False))
        detail = self.library.detail(entry_id)
        self.assertEqual(2, detail['latest_revision'])
        self.assertEqual(1, detail['recommended_revision'],
                         'recommended:false on revision 2 must not move the recommendation')
        self.assertEqual('分镜拆解三步法', detail['recommended']['title'])
        self.assertEqual('较新的草稿', detail['current']['title'],
                         'the newest bytes and the recommended document are two different rows')

    # -- search ------------------------------------------------------------------------
    def test_the_trigram_index_alone_misses_a_two_character_chinese_word(self):
        """The failing control for the fallback. If this ever passes on the index alone the
        fallback is no longer needed -- and the assertion below about the public search would
        stop proving anything."""
        self.library.create(entry())
        with closing(self.library._connect()) as conn:
            self.assertEqual([], knowledge_library._fts_matches(conn, '分镜'))
            self.assertEqual([], knowledge_library._fts_matches(conn, '粒子'))
            self.assertNotEqual([], knowledge_library._fts_matches(conn, 'storyboarder'),
                                'the control must also show what the index can answer')

    def test_a_two_character_word_finds_its_entry_through_the_fallback(self):
        self.library.create(entry())
        self.library.create(entry(entry_type='RECIPE', title='粒子转场配方',
                                  summary='粒子在转场里只做遮挡，不做主体。',
                                  domain_tags=['motion'], task_tags=['transition'],
                                  target_tools=['ae'],
                                  body='先低分辨率试转场长度，再上粒子层。'))
        storyboard = self.library.search(query='分镜')
        self.assertEqual(1, storyboard['total'])
        self.assertEqual('分镜拆解三步法', storyboard['entries'][0]['title'])
        self.assertEqual('SHORT_FALLBACK', storyboard['strategy'],
                         'a two-character query must be answered by the fallback, not the index')
        particle = self.library.search(query='粒子')
        self.assertEqual(1, particle['total'])
        self.assertEqual('粒子转场配方', particle['entries'][0]['title'])
        self.assertIn('title', particle['entries'][0]['matched_fields'],
                      'the answer must say which field matched')
        self.assertEqual(['粒子'], particle['entries'][0]['matched_terms'])

    def test_the_search_answer_carries_the_six_type_names(self):
        """DL-KB-03's type filter reads one table. The service's TYPE_LABELS travels with the
        answer, so the screen never keeps a hand-typed second vocabulary that could drift."""
        answer = self.library.search()
        self.assertEqual(list(knowledge_library.ENTRY_TYPES),
                         [item['value'] for item in answer['entryTypes']])
        self.assertEqual(['规范', '方法', '提示词', '模型指南', '配方', '案例'],
                         [item['label'] for item in answer['entryTypes']])
        self.assertEqual(list(knowledge_library.LICENSE_STATES), answer['licenseStates'])

    def test_a_three_character_term_goes_through_the_index_and_survives_a_lost_index(self):
        """Measured on this host: a contiguous three-character CJK run is itself an indexed
        trigram, so `分镜头` is answered by the index -- the sentence "shorter than three
        characters" alone would describe the wrong boundary. The second half deletes the derived
        index rows, which is the only state in which the fallback's >=3-character branch runs;
        without it a lost index row would hide every match for that term."""
        self.library.create(entry(title='分镜头脚本写法', body='先写分镜头脚本，再画镜头。'))
        with closing(self.library._connect()) as conn:
            self.assertNotEqual([], knowledge_library._fts_matches(conn, '分镜头'),
                                'a contiguous three-character run must be an indexed trigram')
        healthy = self.library.search(query='分镜头')
        self.assertEqual(1, healthy['total'])
        self.assertEqual('TRIGRAM', healthy['strategy'],
                         'the index answered, so the row must have been selected through it')
        with closing(self.library._connect()) as conn:
            conn.execute('DELETE FROM knowledge_entry_fts')
            conn.commit()
        degraded = self.library.search(query='分镜头')
        self.assertEqual(1, degraded['total'],
                         'with the derived index missing this term the substring fallback must '
                         'still answer; otherwise one lost index row hides the entry')
        self.assertEqual('MIXED', degraded['strategy'],
                         'the index was asked and could not answer, so the fallback ran')

    def test_english_matching_does_not_mean_chinese_search_is_usable(self):
        """Two cases, one verdict. `brand` is answered by the index and `品牌` only by the
        fallback; a suite that only ever searched an ASCII word would report the library usable
        while every Chinese query returned nothing."""
        self.library.create(entry(title='品牌系统命名规范', summary='色板按角色命名。',
                                  entry_type='STANDARD', domain_tags=['brand'],
                                  task_tags=['design-system'], target_tools=['figma'],
                                  body='角色命名能让暗色模式复用同一套 token。'))
        english = self.library.search(query='brand')
        chinese = self.library.search(query='品牌')
        self.assertEqual(1, english['total'])
        self.assertEqual(1, chinese['total'])
        self.assertEqual('TRIGRAM', english['strategy'])
        self.assertEqual('SHORT_FALLBACK', chinese['strategy'])
        self.assertNotEqual(english['strategy'], chinese['strategy'],
                            'if both queries take the same path this test stops proving the '
                            'Chinese path exists')

    def test_an_empty_search_explains_and_recommends_nothing(self):
        self.library.create(entry())
        answer = self.library.search(query='不存在的主题')
        self.assertEqual(0, answer['total'])
        self.assertEqual([], answer['entries'],
                         'an empty search must not fill itself with unrelated entries')
        self.assertIn('不存在的主题', answer['explanation'])
        self.assertIn('不推荐', answer['explanation'],
                      'the answer must say it is not recommending near-matches, not just be empty')

    def test_filters_are_exact_and_a_bad_type_is_a_refusal_not_an_empty_page(self):
        self.library.create(entry(domain_tags=['film'], task_tags=['storyboard']))
        self.library.create(entry(entry_type='STANDARD', title='品牌系统命名规范',
                                  domain_tags=['brand'], task_tags=['design-system'],
                                  target_tools=['figma']))
        self.assertEqual(1, self.library.search(domain='brand')['total'])
        self.assertEqual(1, self.library.search(task='storyboard')['total'])
        self.assertEqual(1, self.library.search(target='storyboarder')['total'])
        self.assertEqual(1, self.library.search(target='figma')['total'])
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.search(entry_type='NOPE')
        self.assertEqual('KNOWLEDGE_TYPE_INVALID', caught.exception.code)

    def test_the_promised_search_refusals_are_the_words_the_contract_names(self):
        """`contract-bindings.json` promises five 400 codes on the search route. Three of them
        (KNOWLEDGE_OFFSET_INVALID, KNOWLEDGE_LIMIT_INVALID, KNOWLEDGE_QUERY_TOO_LONG) had no
        test anywhere in the repository, so the row was advertising refusals nothing proved --
        the same class of gap as a bound declared and never read. A word a client cannot rely
        on is not a contract: this asserts each code, and asserts the declared maximum itself
        still answers, because a bound that also refuses its own limit is a wall, not a bound.
        """
        from design_lab.knowledge_library import MAX_LIMIT, MAX_QUERY

        for offset in (-1, '0', True):
            with self.assertRaises(KnowledgeLibraryError) as caught:
                self.library.search(offset=offset)
            self.assertEqual('KNOWLEDGE_OFFSET_INVALID', caught.exception.code,
                             f'offset {offset!r} must be refused with the promised word')
        for limit in (0, MAX_LIMIT + 1, True):
            with self.assertRaises(KnowledgeLibraryError) as caught:
                self.library.search(limit=limit)
            self.assertEqual('KNOWLEDGE_LIMIT_INVALID', caught.exception.code,
                             f'limit {limit!r} must be refused with the promised word')
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.search(query='品' * (MAX_QUERY + 1))
        self.assertEqual('KNOWLEDGE_QUERY_TOO_LONG', caught.exception.code)
        self.assertIn(str(MAX_QUERY), caught.exception.detail,
                      'the refusal must name the bound it applied, not just say too long')
        self.assertEqual(0, self.library.search(query='品' * MAX_QUERY)['total'],
                         'a query of exactly the declared maximum is legal and answers')

    # -- the index is derived ------------------------------------------------------------
    def test_a_rebuild_restores_a_corrupted_index(self):
        self.library.create(entry())
        with closing(self.library._connect()) as conn:
            conn.execute('DELETE FROM knowledge_entry_fts')
            conn.commit()
            self.assertEqual([], knowledge_library._fts_matches(conn, 'storyboard'))
        degraded = self.library.search(query='storyboard')
        self.assertEqual(1, degraded['total'],
                         'the canonical rows still answer while the derived index is empty -- '
                         'otherwise this test could not tell a rebuild from a no-op')
        self.assertEqual('MIXED', degraded['strategy'],
                         'the index was asked and could not answer, so the fallback ran')
        rebuilt = self.library.rebuild_index()
        self.assertEqual(1, rebuilt['indexed'])
        self.assertEqual(1, rebuilt['index']['rows'])
        with closing(self.library._connect()) as conn:
            self.assertNotEqual([], knowledge_library._fts_matches(conn, 'storyboard'),
                                'the rebuild did not repopulate the trigram index')
        restored = self.library.search(query='storyboard')
        self.assertEqual(1, restored['total'])
        self.assertEqual('TRIGRAM', restored['strategy'],
                         'after the rebuild the row must be selected through the index again')

    # -- import identity -------------------------------------------------------------------
    def test_import_identity_is_the_source_and_its_version(self):
        body = {key: value for key, value in entry().items()
                if key not in ('created_by',)}
        body['imported_by'] = 'owner'
        first = self.library.import_entry(dict(body))
        self.assertEqual('CREATED', first['outcome'])
        again = self.library.import_entry(dict(body))
        self.assertEqual('DUPLICATE', again['outcome'])
        self.assertEqual(first['knowledge_entry_id'], again['knowledge_entry_id'])
        self.assertEqual(1, len(self.library.search(query='分镜')['entries']),
                         'a re-import wrote a second row for the same source and version')
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.import_entry(dict(body, title='同一版本的不同内容'))
        self.assertEqual(409, caught.exception.status)
        self.assertEqual('KNOWLEDGE_IMPORT_VERSION_CONFLICT', caught.exception.code)
        newer = dict(body)
        newer['source'] = dict(SOURCE, version='2')
        versioned = self.library.import_entry(newer)
        self.assertEqual('VERSIONED', versioned['outcome'])
        self.assertIn(first['knowledge_entry_id'], versioned['related_entries'],
                      'a new version must point at the entries from the same source')

    def test_an_import_without_a_source_version_is_refused(self):
        body = {key: value for key, value in entry().items() if key != 'created_by'}
        body['imported_by'] = 'owner'
        body['source'] = {'sourceId': 'owner-note'}
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.import_entry(body)
        self.assertEqual('KNOWLEDGE_IMPORT_SOURCE_INCOMPLETE', caught.exception.code)

    # -- the published performance claim ----------------------------------------------------
    def test_search_answers_within_the_published_budget_at_a_thousand_entries(self):
        """The docs publish "1,000 records, p95 <= 300 ms". This seeds exactly 1,000 through the
        same writer the routes use, times the public search, and compares against the constant the
        docs quote -- so the sentence and the measurement cannot drift apart."""
        with closing(self.library._connect()) as conn:
            for index in range(1000):
                document = knowledge_library._document(
                    'kentry-' + format(index, '032x'), 1,
                    knowledge_library._fields(entry(
                        title=f'批量条目 {index}', summary=f'第 {index} 条检索语料',
                        body='批量语料用于检索性能预算的测量。'), for_revision=False),
                    created_at='2026-10-23T00:00:00Z', created_by='owner', supersedes=None)
                conn.execute(
                    'INSERT INTO knowledge_entry (entry_id, supersedes, created_at, created_by)'
                    ' VALUES (?,?,?,?)',
                    (document['knowledge_entry_id'], None, '2026-10-23T00:00:00Z', 'owner'))
                self.library._write_revision(
                    conn, document['knowledge_entry_id'], 1,
                    knowledge_library._fields(entry(
                        title=f'批量条目 {index}', summary=f'第 {index} 条检索语料',
                        body='批量语料用于检索性能预算的测量。'), for_revision=False),
                    created_by='owner', supersedes=None)
            conn.commit()
            self.assertEqual(1000, knowledge_library._index_state(conn)['rows'])
        queries = ['分镜', '粒子', '品牌', '批量条目 7', '检索语料'] * 6
        samples = []
        for query in queries:
            started = time.perf_counter()
            self.library.search(query=query, limit=50)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        p95 = samples[max(0, int(len(samples) * 0.95) - 1)]
        # Printed, not just asserted: the product plan publishes a 300 ms budget, and a budget
        # without the measured number beside it cannot be checked later. CI keeps the line.
        print(f'KNOWLEDGE_SEARCH_P95_MS={p95:.1f} budget={knowledge_library.SEARCH_P95_BUDGET_MS} '
              f'entries=1000 samples={len(samples)}')
        self.assertLessEqual(
            p95, knowledge_library.SEARCH_P95_BUDGET_MS,
            f'p95 {p95:.1f} ms over {len(samples)} searches at 1,000 entries exceeds the '
            f'published budget of {knowledge_library.SEARCH_P95_BUDGET_MS} ms')


    # -- A5: no model service stands between a designer and these four acts ---------------

    #: What would put a model, a provider or a network hop between the library and its answer.
    #: A deny-list, because the claim A5 makes is a negative one: "this path reaches no model".
    #: Anything on this list appearing in the module's imports makes the claim false, and the
    #: false-import test below proves the scanner is not decoration.
    MODEL_FACING = frozenset({
        'model_selection', 'model_catalog', 'providers', 'provider', 'http_service',
        'http', 'http.client', 'urllib', 'urllib.request', 'socket', 'requests', 'httpx',
        'openai', 'anthropic'})

    @staticmethod
    def _reached_names(source: str) -> set:
        """Every module this source imports, however deeply nested the import statement is."""
        import ast
        names = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
                names.update(node.module + '.' + alias.name for alias in node.names)
        return names

    @classmethod
    def _model_facing_hits(cls, names):
        """Which imported names reach a model, a provider or the network.

        Matched on dotted parts, so ``from design_lab.model_selection import X``,
        ``import design_lab.providers`` and ``from http import client`` all land -- a bare
        ``name in deny_list`` would let the dotted forms walk straight past it.
        """
        return sorted(name for name in names
                      if name in cls.MODEL_FACING
                      or set(name.split('.')) & cls.MODEL_FACING)

    def test_the_library_reaches_no_model_layer_and_no_network_at_all(self):
        source = (REPO / 'src/design_lab/knowledge_library.py').read_text(encoding='utf-8')
        hits = self._model_facing_hits(self._reached_names(source))
        self.assertEqual(hits, [],
                         'the knowledge library now imports something model- or network-facing: '
                         + str(hits))
        for call in ('urlopen(', 'HTTPConnection(', 'socket.', 'requests.'):
            self.assertNotIn(call, source, f'the library calls {call}; A5 says it must not')

    def test_the_offline_scanner_notices_a_model_import(self):
        # The guard above is only worth what its falsification is worth: a planted import must be
        # caught by the same function, or the pass above would also pass on a wired-up library.
        planted = chr(10).join(['from design_lab import model_selection',
                                'import http.client', ''])
        self.assertEqual(self._model_facing_hits(self._reached_names(planted)),
                         ['design_lab.model_selection', 'http.client'],
                         'the scanner missed a planted model or network import: '
                         + str(self._reached_names(planted)))
        # And it must not flag an ordinary package import for being nearby in the namespace.
        self.assertEqual(self._model_facing_hits({'design_lab', 'design_lab.knowledge_library'}),
                         [], 'the scanner flagged a plain package import as model-facing')

    def test_writing_searching_editing_and_copying_answer_with_no_model_configured(self):
        """A5 measured, not assumed: the model store is empty, and all four acts still answer."""
        with closing(model_selection.connect(
                self.service.database,
                project_root=self.service.paths.project_root)) as conn:
            self.assertEqual(
                0, conn.execute('SELECT COUNT(*) FROM model_selection').fetchone()[0],
                'a recorded model selection leaked into this fixture; the run would then prove '
                'nothing about a machine with no model service')
        created = self.library.create(entry())['entry']
        entry_id = created['knowledge_entry_id']
        found = self.library.search(query='分镜')
        self.assertIn(entry_id, [row['knowledge_entry_id'] for row in found['entries']],
                      'with no model configured, the search a designer can actually run stopped '
                      'answering')
        revised = self.library.revise(entry_id, entry(
            body='第一步切节拍。第二步选景别。第三步只在对位处补口型。',
            created_by='owner', expected_revision=1, recommended=False))['entry']
        detail = self.library.detail(entry_id)
        # The copy button puts `current.body` on the clipboard byte for byte, so the bytes the
        # route answers are the copyable ones -- no model, no rewrite, no composition.
        self.assertEqual(revised['body'], detail['current']['body'])
        self.assertEqual(revised['content_sha256'], detail['current']['content_sha256'])
        self.assertLessEqual(1, len(detail['revisions']))


class SupersessionForkIsRefused(unittest.TestCase):
    """One entry may have at most one successor, and the route that wrote the fork is the point.

    `create` had refused a second successor for as long as the feature existed. `import_entry`
    validated that `supersedes` was well-formed and that the entry existed, then inserted without
    asking whether something already replaced it -- so the exact fork the UI blocked was one
    import away, and the read side picked one of the two rows with `dict.setdefault` over an
    unordered scan. Owner audit 2026-10-26, finding 2. The acceptance is that both routes refuse
    in the same words, that the refusal survives a restart, that a concurrent writer cannot slip
    between the check and the insert, and that the database itself -- not only the Python -- holds
    the rule.
    """

    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# supersession fixture', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.service.create_project('Supersession')
        self.library = KnowledgeLibrary(self.service)

    def import_body(self, **overrides):
        body = {key: value for key, value in entry().items() if key != 'created_by'}
        body['imported_by'] = 'owner'
        body.update(overrides)
        return body

    def successors_of(self, conn, entry_id):
        return [row['entry_id'] for row in conn.execute(
            'SELECT entry_id FROM knowledge_entry WHERE supersedes=?', (entry_id,))]

    def test_the_import_route_refuses_the_fork_the_create_route_already_refused(self):
        first = self.library.create(entry())['entry']['knowledge_entry_id']
        self.library.create(entry(supersedes=first))['entry']['knowledge_entry_id']
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.import_entry(self.import_body(
                source=dict(SOURCE, sourceId='other-note', version='1'), supersedes=first))
        self.assertEqual(409, caught.exception.status,
                         'the import answered a different status than the create would have')
        self.assertEqual('KNOWLEDGE_SUPERSESSION_CONFLICT', caught.exception.code,
                         'the two routes refused with different words for the same rule, so a '
                         'caller cannot tell a fork from any other import failure')
        self.assertIn(first, caught.exception.detail,
                      'the refusal does not name the entry that is already replaced')

    def test_the_refusal_names_the_existing_successor_not_just_the_conflict(self):
        first = self.library.create(entry())['entry']['knowledge_entry_id']
        successor = self.library.create(entry(supersedes=first))['entry']['knowledge_entry_id']
        with self.assertRaises(KnowledgeLibraryError) as caught:
            self.library.create(entry(supersedes=first))
        self.assertIn(successor, caught.exception.detail,
                      'the operator is told that a successor exists but not which one, so the '
                      'only way to find it is to guess')

    def test_the_fork_is_still_one_row_after_the_store_is_reopened(self):
        """Restart read-back: the refusal must not have half-written anything."""
        first = self.library.create(entry())['entry']['knowledge_entry_id']
        kept = self.library.create(entry(supersedes=first))['entry']['knowledge_entry_id']
        with self.assertRaises(KnowledgeLibraryError):
            self.library.import_entry(self.import_body(
                source=dict(SOURCE, sourceId='late-note', version='1'), supersedes=first))
        reopened = KnowledgeLibrary(self.service)
        conn = reopened._connect()
        try:
            self.assertEqual([kept], self.successors_of(conn, first),
                             'the refused import left a second successor row behind')
            revision_rows = conn.execute(
                'SELECT COUNT(*) FROM knowledge_entry_revision WHERE entry_id IN'
                ' (SELECT entry_id FROM knowledge_entry WHERE supersedes=?)', (first,)).fetchone()[0]
            self.assertEqual(1, revision_rows,
                             'the refused transaction left revision bytes behind, so the library '
                             'holds content for an entry row that was never accepted')
        finally:
            conn.close()
        detail = reopened.detail(first)
        self.assertEqual(kept, detail['superseded_by'],
                         'the read side is still choosing between two rows')

    def test_the_database_itself_refuses_a_writer_that_skips_the_application_check(self):
        """The rule lives in the schema, not only in the two routes I remembered to fix.

        A future route that inserts straight into `knowledge_entry` gets the trigger, so "both
        callers now share the guard" is not the whole guarantee.
        """
        first = self.library.create(entry())['entry']['knowledge_entry_id']
        self.library.create(entry(supersedes=first))
        conn = self.library._connect()
        try:
            with self.assertRaises(sqlite3.IntegrityError) as caught:
                conn.execute('INSERT INTO knowledge_entry (entry_id, supersedes, created_at,'
                             ' created_by) VALUES (?,?,?,?)',
                             ('kentry' + '0' * 40, first, '2026-10-26T00:00:00Z', 'raw writer'))
            self.assertIn('at most one successor', str(caught.exception))
        finally:
            conn.close()

    def test_two_writers_cannot_both_become_the_successor(self):
        """Concurrency: the guard reads, then the insert writes -- the window is the defect.

        Both attempts use different routes and different sources, so a fix that only closed the
        import path (or only ran the check outside the lock) cannot pass this.
        """
        first = self.library.create(entry())['entry']['knowledge_entry_id']
        barrier = threading.Barrier(2)

        def via_create():
            barrier.wait()
            try:
                self.library.create(entry(supersedes=first))
                return 'wrote'
            except KnowledgeLibraryError as exc:
                return exc.code

        def via_import():
            barrier.wait()
            try:
                self.library.import_entry(self.import_body(
                    source=dict(SOURCE, sourceId='racer', version='1'), supersedes=first))
                return 'wrote'
            except KnowledgeLibraryError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(f.result() for f in
                              (pool.submit(via_create), pool.submit(via_import)))
        self.assertEqual(['KNOWLEDGE_SUPERSESSION_CONFLICT', 'wrote'], outcomes,
                         'both writers got through, or the loser was refused for the wrong reason:'
                         ' %s' % outcomes)
        conn = self.library._connect()
        try:
            self.assertEqual(1, len(self.successors_of(conn, first)))
        finally:
            conn.close()


    def test_the_trigger_fallback_refusal_names_the_successor_too(self):
        """A writer that reaches the database trigger is refused in the same words, with the id.

        The guard is the polite door; the trigger is the wall behind it. The wall's message used to
        be vaguer than the door's -- "already superseded by another entry" without saying which -- so
        the one caller who most needed the id (a race, where the operator already thinks they are the
        first) got the least. The guard is silenced here on purpose: that is the only way to arrive
        at the fallback deliberately instead of by losing a race.
        """
        first = self.library.create(entry())['entry']['knowledge_entry_id']
        successor = self.library.create(entry(supersedes=first))['entry']['knowledge_entry_id']
        real_guard = knowledge_library._supersedes_guard
        knowledge_library._supersedes_guard = lambda conn, supersedes: None
        try:
            with self.assertRaises(KnowledgeLibraryError) as caught:
                self.library.create(entry(supersedes=first))
        finally:
            knowledge_library._supersedes_guard = real_guard
        self.assertEqual(409, caught.exception.status)
        self.assertEqual('KNOWLEDGE_SUPERSESSION_CONFLICT', caught.exception.code)
        self.assertIn(successor, caught.exception.detail,
                      'the fallback refusal does not name the entry that holds the claim: %s'
                      % caught.exception.detail)
        conn = self.library._connect()
        try:
            self.assertEqual([successor], sorted(self.successors_of(conn, first)),
                             'the refused fallback write forked the chain anyway')
        finally:
            conn.close()
        # And the two refusals agree, which is why they share one formatter.
        with self.assertRaises(KnowledgeLibraryError) as via_guard:
            self.library.create(entry(supersedes=first))
        self.assertEqual(via_guard.exception.detail, caught.exception.detail,
                         'the guard and the trigger fallback describe the same refusal differently')


if __name__ == '__main__':
    unittest.main()
