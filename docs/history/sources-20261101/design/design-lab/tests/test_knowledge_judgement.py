# SPDX-License-Identifier: MIT
"""DL-KB-05 acceptance D5: a later judgement about a knowledge entry.

D5 asks two things and nothing in the store could say either of them before this file:

* **回退推荐版本后旧方案仍可读.** The recommendation must be able to move BACK to an older
  revision, while every revision -- including the one an older plan pinned -- keeps the exact bytes
  it was written with. That is only possible if the recommendation is a separate recorded fact: the
  revision rows are append-only by trigger, so `recommended` on a revision can never be rewritten.
* **失效来源可标记并替换.** Marking a source INVALID has to name what replaces it, and it has to be
  somebody's recorded decision, not a computed state.

So a judgement is its own append-only row (design-lab/schemas/state/
design-lab-state-knowledge-judgement-v1.sql). What this suite pins down:

  - the newest judgement of a kind is the answer, and the rows under it are the history;
  - content digests do not move when a recommendation does (the "old plan still reads it" half);
  - an agent cannot record one, a judgement without a reason cannot be recorded, and a judgement
    cannot recommend bytes that were never stored;
  - INVALID without a replacement is refused, a replacement that is not a stored entry is refused
    by the writer AND by the table's own foreign key, and an entry cannot replace itself;
    an absent source_state says "nobody has said", not "the source is fine";
  - the same judgement sent twice is one judgement;
  - UPDATE and DELETE on the table are refused by trigger, so the trail cannot be edited.

Nothing here proves a person agreed the content is good: it proves the store can record who said
what about it, in order, without rewriting anything.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from design_lab.knowledge_library import KnowledgeLibrary, KnowledgeLibraryError  # noqa: E402
from design_lab.service import ProjectService  # noqa: E402
from test_knowledge_library import entry  # noqa: E402  (a payload factory, not a TestCase)


class KnowledgeJudgementTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# knowledge judgement fixture', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.service.create_project('Knowledge Judgements')
        self.library = KnowledgeLibrary(self.service)
        created = self.library.create(entry())['entry']
        self.entry_id = created['knowledge_entry_id']
        # The entry a dead source is replaced BY. A replacement has to be something the reader can
        # actually open, so the store only accepts a real entry id.
        self.replacement_id = self.library.create(
            entry(title='分镜拆解（再来源）', recommended=False))['entry']['knowledge_entry_id']
        # r2 carries new bytes and is NOT recommended, so latest and recommended differ from the
        # written flags alone -- the starting point a rollback has to be measured against.
        self.library.revise(self.entry_id, dict(
            entry(title='分镜拆解四步法', body='第一步切节拍。第二步选景别。第三步标转场。'
                 + '第四步只在对位处补口型。'),
            created_by='owner', expected_revision=1, recommended=False))

    def digests(self):
        detail = self.library.detail(self.entry_id)
        return {row['revision']: row['content_sha256'] for row in detail['revisions']}

    # ---- the rollback half ---------------------------------------------------------------
    def test_a_recorded_judgement_moves_the_recommendation_back(self):
        before = self.library.detail(self.entry_id)
        self.assertEqual(before['latest_revision'], 2)
        self.assertEqual(before['recommended_revision'], 1)
        self.assertEqual(before['recommendation_basis'], 'written-flag')

        after = self.library.record_judgement(self.entry_id, {
            'kind': 'RECOMMENDATION', 'revision': 2, 'value': None, 'replaced_by': None,
            'reason': '第二步的景别表在真人测试里更好用，退回 r2。',
            'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(after['recommended_revision'], 2)
        self.assertEqual(after['recommendation_basis'], 'recorded-judgement')
        self.assertEqual(after['recommendation_judgement']['recorded_by'], '张工')
        self.assertEqual(len(after['judgements']), 1)

    def test_moving_the_recommendation_rewrites_no_stored_bytes(self):
        before = self.digests()
        self.library.record_judgement(self.entry_id, {
            'kind': 'RECOMMENDATION', 'revision': 2, 'value': None, 'replaced_by': None,
            'reason': '推荐前进到 r2。', 'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        moved = self.library.record_judgement(self.entry_id, {
            'kind': 'RECOMMENDATION', 'revision': 1, 'value': None, 'replaced_by': None,
            'reason': '再退回 r1：r2 的第四步在纯短片场景里是多余的一层。',
            'recorded_by': '李工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(moved['recommended_revision'], 1)
        self.assertEqual(moved['latest_revision'], 2)
        # The claim D5 makes: whatever a plan pinned, it still reads the same document.
        self.assertEqual(self.digests(), before)
        self.assertEqual([j['revision'] for j in moved['judgements']], [2, 1])

    def test_the_newest_judgement_of_a_kind_is_the_answer_and_the_rest_is_history(self):
        for revision, who in ((2, '张工'), (1, '李工'), (2, '张工')):
            self.library.record_judgement(self.entry_id, {
                'kind': 'RECOMMENDATION', 'revision': revision, 'value': None, 'replaced_by': None,
                'reason': '按真人反馈调整推荐。', 'recorded_by': who, 'recorded_by_kind': 'HUMAN'})
        detail = self.library.detail(self.entry_id)
        self.assertEqual(detail['recommended_revision'], 2)
        self.assertEqual(len(detail['judgements']), 3)

    # ---- the source half -----------------------------------------------------------------
    def test_an_invalid_source_must_name_its_replacement(self):
        with self.assertRaises(KnowledgeLibraryError) as refused:
            self.library.record_judgement(self.entry_id, {
                'kind': 'SOURCE_STATE', 'revision': None, 'value': 'INVALID',
                'replaced_by': None, 'reason': '原稿下架了。',
                'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(refused.exception.code, 'KNOWLEDGE_SOURCE_REPLACEMENT_REQUIRED')
        self.assertIsNone(self.library.detail(self.entry_id)['source_state'])

        with self.assertRaises(KnowledgeLibraryError) as dangling:
            self.library.record_judgement(self.entry_id, {
                'kind': 'SOURCE_STATE', 'revision': None, 'value': 'INVALID',
                'replaced_by': 'kentry-' + '0' * 32, 'reason': '指向了一个不存在的替代条目。',
                'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(dangling.exception.code, 'KNOWLEDGE_SOURCE_REPLACEMENT_UNKNOWN')

        replaced = self.library.record_judgement(self.entry_id, {
            'kind': 'SOURCE_STATE', 'revision': None, 'value': 'INVALID',
            'replaced_by': self.replacement_id, 'reason': '原稿下架，改引替代条目。',
            'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        state = replaced['source_state']
        self.assertEqual(state['value'], 'INVALID')
        self.assertEqual(state['replaced_by'], self.replacement_id)
        self.assertEqual(state['recorded_by'], '张工')
        # Marking it valid again is a later judgement, not an edit of the first one.
        restored = self.library.record_judgement(self.entry_id, {
            'kind': 'SOURCE_STATE', 'revision': None, 'value': 'ACTIVE', 'replaced_by': None,
            'reason': '出版社恢复了原链接。', 'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(restored['source_state']['value'], 'ACTIVE')
        self.assertEqual(len(restored['judgements']), 2)

    # ---- who may say, and about what ------------------------------------------------------
    def test_an_agent_may_not_record_a_judgement(self):
        with self.assertRaises(KnowledgeLibraryError) as refused:
            self.library.record_judgement(self.entry_id, {
                'kind': 'RECOMMENDATION', 'revision': 1, 'value': None, 'replaced_by': None,
                'reason': '自动排序觉得 r1 更好。', 'recorded_by': 'agent',
                'recorded_by_kind': 'AGENT'})
        self.assertEqual(refused.exception.code, 'KNOWLEDGE_HUMAN_JUDGEMENT_REQUIRED')

    def test_a_judgement_without_a_reason_is_refused(self):
        for reason in ('', '   '):
            with self.assertRaises(KnowledgeLibraryError) as refused:
                self.library.record_judgement(self.entry_id, {
                    'kind': 'RECOMMENDATION', 'revision': 1, 'value': None, 'replaced_by': None,
                    'reason': reason, 'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
            self.assertEqual(refused.exception.code, 'REASON_REQUIRED')

    def test_a_recommendation_cannot_name_a_revision_that_was_never_stored(self):
        with self.assertRaises(KnowledgeLibraryError) as refused:
            self.library.record_judgement(self.entry_id, {
                'kind': 'RECOMMENDATION', 'revision': 7, 'value': None, 'replaced_by': None,
                'reason': '推荐一个不存在的修订。', 'recorded_by': '张工',
                'recorded_by_kind': 'HUMAN'})
        self.assertEqual(refused.exception.code, 'KNOWLEDGE_REVISION_NOT_FOUND')

    def test_the_wrong_field_for_the_kind_is_named_not_ignored(self):
        with self.assertRaises(KnowledgeLibraryError) as first:
            self.library.record_judgement(self.entry_id, {
                'kind': 'RECOMMENDATION', 'revision': 1, 'value': None,
                'replaced_by': 'owner-note-v2', 'reason': '带错了字段。',
                'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(first.exception.code, 'KNOWLEDGE_JUDGEMENT_FIELD_NOT_APPLICABLE')
        with self.assertRaises(KnowledgeLibraryError) as second:
            self.library.record_judgement(self.entry_id, {
                'kind': 'SOURCE_STATE', 'revision': 1, 'value': 'ACTIVE', 'replaced_by': None,
                'reason': '带错了字段。', 'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(second.exception.code, 'KNOWLEDGE_JUDGEMENT_FIELD_NOT_APPLICABLE')
        with self.assertRaises(KnowledgeLibraryError) as third:
            self.library.record_judgement(self.entry_id, {
                'kind': 'RANKING', 'revision': None, 'value': 'ACTIVE', 'replaced_by': None,
                'reason': '没有这种判定。', 'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(third.exception.code, 'KNOWLEDGE_JUDGEMENT_KIND_INVALID')

    def test_the_same_judgement_sent_twice_is_one_judgement(self):
        body = {'kind': 'RECOMMENDATION', 'revision': 2, 'value': None, 'replaced_by': None,
                'reason': '真人反馈更好用。', 'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'}
        first = self.library.record_judgement(self.entry_id, body)
        again = self.library.record_judgement(self.entry_id, dict(body))
        self.assertEqual(len(first['judgements']), 1)
        self.assertEqual(len(again['judgements']), 1)

    # ---- the table itself keeps its own shape --------------------------------------------
    def test_a_source_cannot_be_replaced_by_the_entry_it_marks_dead(self):
        with self.assertRaises(KnowledgeLibraryError) as refused:
            self.library.record_judgement(self.entry_id, {
                'kind': 'SOURCE_STATE', 'revision': None, 'value': 'INVALID',
                'replaced_by': self.entry_id, 'reason': '用它自己替代它自己。',
                'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(refused.exception.code, 'KNOWLEDGE_SOURCE_REPLACEMENT_SELF')
        self.assertEqual(self.library.detail(self.entry_id)['judgements'], [])

    def test_the_table_refuses_a_replacement_that_is_not_an_entry(self):
        # The writer checks this too. This one is about the DDL not being decoration: a row inserted
        # past the store still cannot point at an entry the library does not hold.
        connection = self.library._connect()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    'INSERT INTO knowledge_judgement (judgement_id, entry_id, kind, revision,'
                    " value, replaced_by, reason, recorded_by, recorded_at) VALUES "
                    "('kjudge-' || printf('%032x', 1), ?, 'SOURCE_STATE', NULL, 'INVALID', ?, "
                    "'绕过写入面', '张工', '2026-10-24T00:00:00Z')",
                    (self.entry_id, 'kentry-' + '0' * 32))
        finally:
            connection.close()

    def test_the_judgement_table_is_append_only(self):
        self.library.record_judgement(self.entry_id, {
            'kind': 'RECOMMENDATION', 'revision': 2, 'value': None, 'replaced_by': None,
            'reason': '为了验证这张表不能改。', 'recorded_by': '张工',
            'recorded_by_kind': 'HUMAN'})
        connection = self.library._connect()
        try:
            # A trigger's RAISE(ABORT) surfaces as IntegrityError, not OperationalError.
            with self.assertRaises(sqlite3.IntegrityError) as update:
                connection.execute("UPDATE knowledge_judgement SET reason='改了'")
            self.assertIn('append-only', str(update.exception))
            with self.assertRaises(sqlite3.IntegrityError) as delete:
                connection.execute('DELETE FROM knowledge_judgement')
            self.assertIn('append-only', str(delete.exception))
            rows = connection.execute(
                'SELECT judgement_id, reason FROM knowledge_judgement').fetchall()
            self.assertEqual([row['reason'] for row in rows], ['为了验证这张表不能改。'])
        finally:
            connection.close()

    def test_a_judgement_survives_a_restart_and_still_outranks_the_written_flag(self):
        self.library.record_judgement(self.entry_id, {
            'kind': 'RECOMMENDATION', 'revision': 2, 'value': None, 'replaced_by': None,
            'reason': '重启后还要拿得回来。', 'recorded_by': '张工',
            'recorded_by_kind': 'HUMAN'})
        reopened = KnowledgeLibrary(ProjectService(self.project))
        detail = reopened.detail(self.entry_id)
        self.assertEqual(detail['recommended_revision'], 2)
        self.assertEqual(detail['recommendation_basis'], 'recorded-judgement')
        self.assertEqual(len(detail['judgements']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
