# SPDX-License-Identifier: MIT
"""The task read-back envelope: what it promises, and what it refuses to let a page invent.

Backend D (2026-10-22) gave ``GET …/tasks``, ``GET …/tasks/<job>`` and ``GET …/tasks/<job>/events``
one shared version, because Stitch screen D08 needs three facts no caller could previously get from
the payload alone: which state words this service can emit at all, whether the page it received is
the whole answer, and what ``cancel.acknowledged`` asserts. These tests pin those three, the cap the
reads put on themselves, and the two refusals (a payload that contradicts its own envelope, a
vocabulary file that cannot be read).

Seeded through the product's own writers (``job_store``), never by hand-written rows: a fixture that
typed its own state words could satisfy a schema the state machine no longer produces.
"""
from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from design_lab import task_queries
from design_lab.runtime import job_store
from design_lab.service import ProjectService
from design_lab.task_queries import TaskQueries, TaskReadbackError

JOB_STORE = ROOT / 'src' / 'design_lab' / 'runtime' / 'job_store.py'
VOCABULARY = ROOT / 'design-lab' / 'config' / 'state-vocabularies.json'
# Spelled out again on purpose: the payload announces where its words came from, and this test
# compares that announcement against the repository's own spelling rather than reading the module
# constant that produced it.
VOCABULARY_RELATIVE = 'design-lab/config/state-vocabularies.json'
OPERATION_WORDS = re.compile(r'_op\(conn, op, "([A-Z_]+)"\)')


class EnvelopeFixture(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/task-envelope-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'AGENTS.md').write_text('# synthetic owner', encoding='utf-8')
        env = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(self.root / '.project-local')})
        env.start()
        self.addCleanup(env.stop)
        self.service = ProjectService(self.root)
        self.project = self.service.create_project('Envelope owner')['id']
        self.queries = TaskQueries(self.service)

    def seed(self, count=1, *, start_at=0, transitions=()):
        """Create ``count`` attempts on this project, walking each through ``transitions``."""
        ids = []
        with closing(job_store.connect(self.service.database,
                                       project_root=self.service.paths.project_root)) as conn:
            for index in range(start_at, start_at + count):
                job_id = f'job-{index:064x}'
                attempt = job_store.begin_attempt(
                    conn, job_id, operation_id=f'op-{index:064x}',
                    idempotency_scope=f'native:{self.project}:photoshop',
                    idempotency_key=f'envelope-{index}', request_hash='c' * 64)
                for state in transitions:
                    job_store.transition(conn, attempt['attempt_id'], state)
                ids.append(job_id)
            conn.commit()
        return ids

    def cancelled(self, *, acknowledge, tag):
        """One attempt whose cancellation was requested, and optionally acknowledged."""
        job_id = f'job-{tag:064x}'
        with closing(job_store.connect(self.service.database,
                                       project_root=self.service.paths.project_root)) as conn:
            attempt = job_store.begin_attempt(
                conn, job_id, operation_id=f'op-{tag:064x}',
                idempotency_scope=f'native:{self.project}:photoshop',
                idempotency_key=f'envelope-cancel-{tag}', request_hash='a' * 64)
            job_store.transition(conn, attempt['attempt_id'], 'RUNNING')
            job_store.request_cancel(conn, attempt['attempt_id'])
            if acknowledge:
                job_store.acknowledge_cancel(conn, attempt['attempt_id'])
            conn.commit()
        return job_id


class EnvelopeShapeTests(EnvelopeFixture):
    def test_an_empty_page_still_carries_the_vocabulary(self):
        page = self.queries.list(self.project)
        self.assertEqual(page['schemaVersion'], 'design-lab/task-readback/v1')
        self.assertEqual(page['surface'], 'list')
        self.assertEqual(page['tasks'], [])
        self.assertEqual(page['count'], 0)
        self.assertFalse(page['truncated'])
        self.assertIsNone(page['next_cursor'])
        self.assertEqual(page['limit'], 100)
        # Read from the file here rather than through state_vocabulary(): comparing the payload with
        # the same function that built it would be an echo, not a check.
        declared = json.loads(VOCABULARY.read_text(encoding='utf-8'))['attemptStates']
        self.assertEqual(page['stateVocabulary']['attemptStates']['all'], declared['all'])
        self.assertEqual(page['stateVocabulary']['vocabularyFile'], VOCABULARY_RELATIVE)

    def test_the_three_surfaces_differ_only_in_the_payload_key(self):
        job_id = self.seed()[0]
        pages = {'list': self.queries.list(self.project),
                 'task': self.queries.get(self.project, job_id),
                 'events': self.queries.events(self.project, job_id)}
        payload_key = {'list': 'tasks', 'task': 'task', 'events': 'events'}
        for name, page in pages.items():
            self.assertEqual(page['surface'], name)
            self.assertEqual(page['schemaVersion'], 'design-lab/task-readback/v1')
            self.assertEqual(page['limit'], 100)
            self.assertIn(payload_key[name], page)
            for other in set(pages) - {name}:
                self.assertNotIn(payload_key[other], page,
                                 f'the {name} surface shipped the {other} surface\'s payload key')

    def test_observed_states_are_the_states_this_page_returned(self):
        self.seed(3, transitions=('RUNNING',))
        page = self.queries.list(self.project)
        emitted = sorted({task['state'] for task in page['tasks']})
        self.assertEqual(page['stateVocabulary']['operationStates']['observedInThisPage'], emitted)
        # The words must come from the file that writes them, not from this projection: the envelope
        # announces job_store as the owner because no named set of operation-level states exists.
        written = set(OPERATION_WORDS.findall(JOB_STORE.read_text(encoding='utf-8')))
        self.assertTrue(written, 'no operation-level state literal found in job_store')
        self.assertTrue(set(emitted) <= written,
                        f'the page reported states the writer cannot emit: {emitted}')
        self.assertEqual(page['stateVocabulary']['operationStates']['owner'],
                         'src/design_lab/runtime/job_store.py')
        vocabulary = page['stateVocabulary']['attemptStates']['all']
        for task in page['tasks']:
            self.assertIn(task['attempt']['state'], vocabulary)

    def test_a_cancellation_is_two_facts_and_neither_claims_the_host_stopped(self):
        requested = self.queries.get(self.project, self.cancelled(acknowledge=False, tag=1))
        self.assertEqual(requested['task']['cancel'], {'requested': True, 'acknowledged': False})
        self.assertEqual(requested['task']['attempt']['state'], 'CANCEL_REQUESTED')

        acked = self.queries.get(self.project, self.cancelled(acknowledge=True, tag=2))
        self.assertEqual(acked['task']['cancel'], {'requested': True, 'acknowledged': True})
        # Acknowledged is the adapter's confirmation, never a claim that the host halted: the state
        # it leaves behind is RECONCILING, and the read says so on every page.
        self.assertEqual(acked['task']['state'], 'RECONCILING')
        self.assertEqual(acked['task']['attempt']['state'], 'RECONCILING')
        sentence = [line for line in acked['does_not_say'] if 'cancel.acknowledged' in line]
        self.assertEqual(len(sentence), 1, 'the cancel meaning must travel with every page')
        self.assertIn('也不说产物已核对', sentence[0])
        self.assertIn('readback still required', sentence[0])


class TruncationTests(EnvelopeFixture):
    def test_a_full_page_hands_back_a_cursor_and_refuses_to_claim_the_end(self):
        self.seed(task_queries.PAGE_LIMIT + 1)
        page = self.queries.list(self.project)
        self.assertEqual(page['count'], task_queries.PAGE_LIMIT)
        self.assertEqual(len(page['tasks']), task_queries.PAGE_LIMIT)
        self.assertTrue(page['truncated'])
        self.assertEqual(page['next_cursor'], page['tasks'][-1]['job_id'])
        rest = self.queries.list(self.project, after=page['next_cursor'])
        self.assertEqual(rest['count'], 1)
        self.assertFalse(rest['truncated'])
        self.assertIsNone(rest['next_cursor'],
                          'the last page must not hand back a cursor a page would keep paging on')

    def test_an_event_page_cursors_on_the_event_number(self):
        job_id = self.seed(transitions=('RUNNING', 'FAILED'))[0]
        page = self.queries.events(self.project, job_id)
        self.assertEqual([event['to_state'] for event in page['events']],
                         ['PENDING', 'RUNNING', 'FAILED'])
        self.assertFalse(page['truncated'])
        self.assertIsNone(page['next_cursor'])
        after = self.queries.events(self.project, job_id, after=page['events'][-1]['event_no'])
        self.assertEqual(after['events'], [])
        self.assertEqual(after['count'], 0)
        self.assertFalse(after['truncated'])


class RefusalTests(EnvelopeFixture):
    def envelope(self, **overrides):
        vocabulary = json.loads(json.dumps(task_queries.state_vocabulary()))
        vocabulary['operationStates']['observedInThisPage'] = []
        envelope = {'schemaVersion': task_queries.TASK_READBACK_VERSION, 'surface': 'list',
                    'limit': 100, 'truncated': False, 'next_cursor': None, 'count': 0,
                    'stateVocabulary': vocabulary, 'tasks': [],
                    'does_not_say': list(task_queries.DOES_NOT_SAY)}
        envelope.update(overrides)
        return envelope

    def test_a_payload_that_lies_about_its_own_cursor_is_refused(self):
        convictions = [
            ({'truncated': True, 'count': 1}, 'truncated with no cursor to page on'),
            ({'surface': 'task'}, 'the list surface carrying a task payload key'),
            ({'truncated': True, 'next_cursor': 'x'},
             'an empty page claiming there is more'),
            ({'limit': 50}, 'a limit the contract does not declare'),
            ({'tasks': [{'job_id': 'job-1'}]}, 'a task record missing its cancel flags'),
        ]
        for plant, reason in convictions:
            with self.subTest(case=reason):
                with self.assertRaises(TaskReadbackError) as refused:
                    task_queries._guard(self.envelope(**plant))
                self.assertEqual(refused.exception.status, 500)
                self.assertEqual(refused.exception.code, 'TASK_READBACK_CONTRACT_VIOLATION')
                self.assertTrue(str(refused.exception), 'a refusal must name what disagreed')

    def test_the_honest_pair_is_not_convicted(self):
        # Without this control the plant test above could pass while the guard refused everything.
        page = task_queries._guard(self.envelope(count=1, truncated=True,
                                                 next_cursor='job-' + '1' * 64,
                                                 tasks=[self.task_row()]))
        self.assertTrue(page['truncated'])
        self.assertEqual(page['next_cursor'], 'job-' + '1' * 64)

    def task_row(self):
        return {'job_id': 'job-' + '1' * 64, 'operation_id': 'op-' + '2' * 64,
                'kind': 'photoshop-native', 'state': 'RECONCILING',
                'updated_at': '2026-10-22T00:00:00Z',
                'cancel': {'requested': True, 'acknowledged': True},
                'attempt': {'attempt_id': 'att-1', 'attempt_no': 1, 'state': 'RECONCILING',
                            'started_at': '2026-10-22T00:00:00Z', 'ended_at': None}}

    def test_an_unreadable_vocabulary_is_a_refusal_not_an_absent_list(self):
        task_queries.state_vocabulary.cache_clear()
        self.addCleanup(task_queries.state_vocabulary.cache_clear)
        with patch.object(task_queries, 'repo_resource',
                          side_effect=FileNotFoundError('packaged repository resource missing')):
            with self.assertRaises(TaskReadbackError) as refused:
                self.queries.list(self.project)
        self.assertEqual(refused.exception.status, 503)
        self.assertEqual(refused.exception.code, 'TASK_VOCABULARY_UNREADABLE')
        self.assertIn('state-vocabularies.json', str(refused.exception))

    def test_a_vocabulary_without_its_state_list_is_refused(self):
        task_queries.state_vocabulary.cache_clear()
        self.addCleanup(task_queries.state_vocabulary.cache_clear)
        with patch.object(task_queries, 'repo_resource',
                          return_value=FakeFile('{"attemptStates": {"terminal": []}}')):
            with self.assertRaises(TaskReadbackError) as refused:
                task_queries.state_vocabulary()
        self.assertEqual(refused.exception.code, 'TASK_VOCABULARY_INCOMPLETE')


class FakeFile:
    def __init__(self, text):
        self._text = text

    def read_text(self, encoding=None):
        return self._text


if __name__ == '__main__':
    unittest.main()
