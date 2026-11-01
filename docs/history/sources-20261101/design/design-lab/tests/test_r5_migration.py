# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))
import prepare_r5_ledger as migration


class R5MigrationTests(unittest.TestCase):
    def setUp(self):
        self.previous = (ROOT / 'docs/history/taskpacks/r3-ledger-pre-r5-20260909.json').read_bytes()
        self.active_before = (ROOT / 'design-lab/config/task-ledger-r3.json').read_bytes()
        self.source = (ROOT / 'docs/history/taskpacks/r5-20260908/tasks.json').read_bytes()

    def build(self, previous=None, source=None):
        return migration.prepare(ROOT, self.previous if previous is None else previous,
                                 self.source if source is None else source,
                                 updated_at='2026-09-09T00:00:00Z')

    def test_preserves_entire_predecessor_without_mutating_active_file(self):
        candidate = self.build()
        self.assertEqual(candidate['predecessor']['ledger'], json.loads(self.previous))
        self.assertEqual(candidate['predecessor']['sha256'], hashlib.sha256(self.previous).hexdigest())
        self.assertEqual((ROOT / 'design-lab/config/task-ledger-r3.json').read_bytes(), self.active_before)
        self.assertEqual(self.build(), candidate)

    def test_all_definitions_and_conditions_survive_without_pass_transfer(self):
        candidate = self.build()
        self.assertEqual(len(candidate['tasks']), 28)
        self.assertEqual(candidate['evidence'], [])
        for original, task in zip(json.loads(self.source)['tasks'], candidate['tasks']):
            self.assertEqual(task['definition'], original)
            self.assertEqual(task['id'], original['id'])
            self.assertEqual(task['depends_on'], original['depends_on'])
            for axis in task['axes'].values():
                self.assertEqual(axis, {'state': 'PARTIAL', 'evidence': []})

    def test_mapping_covers_all_old_tasks_without_erasing_split_work(self):
        tasks = {t['id']: t for t in self.build()['tasks']}
        mapped = {old for task in tasks.values() for old in task['predecessor_task_ids']}
        self.assertEqual(mapped, {f'R3-{i:02d}' for i in range(1, 25)})
        self.assertEqual(tasks['DL-R5-001']['predecessor_task_ids'], ['R3-01', 'R3-03'])
        self.assertEqual(tasks['DL-R5-025']['predecessor_task_ids'], ['R3-16', 'R3-20'])
        self.assertEqual(tasks['DL-R5-028']['predecessor_task_ids'], [])

    def test_modified_source_and_invalid_predecessor_are_rejected(self):
        with self.assertRaises(ValueError):
            self.build(source=self.source + b' ')
        previous = json.loads(self.previous)
        previous['tasks'].pop()
        with self.assertRaises(ValueError):
            self.build(previous=json.dumps(previous).encode())

    def test_candidate_projects_all_tasks_without_qualifying_history(self):
        from design_lab.governance.reporting import project_ledger
        result = project_ledger(ROOT, self.build(), 'a' * 40)
        self.assertEqual(result['taskpack'], 'DL-TP-20260908-R5')
        self.assertEqual(result['schemaVersion'], 'design-lab/task-progress/r5-v1')
        self.assertEqual(len(result['tasks']), 28)
        self.assertEqual(result['counts'], {'PARTIAL': 28})
        self.assertEqual(result['evidence'], [])

    def test_candidate_rejects_definition_and_history_tampering(self):
        from design_lab.governance.reporting import project_ledger
        for change in (
            lambda d: d['tasks'][0]['definition'].update(acceptance=['weakened']),
            lambda d: d['predecessor']['ledger']['evidence'].clear(),
            lambda d: d['tasks'][0].update(depends_on=[] ,title='wrong'),
            lambda d: d['tasks'][0].update(predecessor_task_ids=[]),
        ):
            candidate = self.build()
            change(candidate)
            with self.assertRaises(ValueError):
                project_ledger(ROOT, candidate, 'a' * 40)

    def test_r5_local_receipt_does_not_qualify_host_or_delivery(self):
        from design_lab.governance.reporting import project_ledger
        candidate = self.build()
        candidate['evidence'] = [{
            'id': 'controlled-test', 'task_ids': ['DL-R5-015'], 'kind': 'local_test',
            'outcome': 'PASS', 'subject_sha': 'a' * 40, 'binding': 'WORKTREE_FILES',
            'observed_at': '2026-09-09T00:00:00Z', 'software': {'fixture': 'controlled'},
            'subject_files': {'docs/history/taskpacks/r5-20260908/tasks.json': hashlib.sha256(self.source).hexdigest()},
            'artifacts': [{'path': 'docs/history/taskpacks/r5-20260908/tasks.json', 'sha256': hashlib.sha256(self.source).hexdigest()}],
            'note': 'Controlled unit evidence only, not a live acceptance record.',
        }]
        task = next(t for t in candidate['tasks'] if t['id'] == 'DL-R5-015')
        task['reassessment'] = 'REVIEWED'
        for axis in task['axes'].values():
            axis.update(state='PASS', evidence=['controlled-test'])
        row = next(t for t in project_ledger(ROOT, candidate, 'a' * 40)['tasks'] if t['id'] == 'DL-R5-015')
        self.assertEqual(row['axes']['unit']['state'], 'PASS')
        self.assertEqual(row['axes']['host_live']['state'], 'UNVERIFIED')
        self.assertEqual(row['axes']['delivery']['state'], 'UNVERIFIED')
        self.assertEqual(row['status'], 'PARTIAL')
        self.assertTrue(row['unmet_dependencies'])

    def test_r5_cannot_waive_required_axes_or_skip_reassessment(self):
        from design_lab.governance.reporting import project_ledger
        for change in (
            lambda d: d['tasks'][14].update(required_axes=['implementation', 'unit']),
            lambda d: d['tasks'][14]['axes']['host_live'].update(state='NOT_REQUIRED'),
            lambda d: d['tasks'][0]['axes']['implementation'].update(state='PASS'),
            lambda d: d.update(updated_at='invalid'),
        ):
            candidate = self.build()
            change(candidate)
            with self.assertRaises(ValueError):
                project_ledger(ROOT, candidate, 'a' * 40)

    def test_conditional_audio_is_explicit_and_required_audio_blocks(self):
        from design_lab.governance.reporting import project_ledger
        candidate = self.build()
        def row():
            return next(t for t in project_ledger(ROOT, candidate, 'a' * 40)['tasks'] if t['id'] == 'DL-R5-019')
        self.assertEqual(row()['unresolved_conditions'], ['TTS_required', 'generated_music_required'])
        task = next(t for t in candidate['tasks'] if t['id'] == 'DL-R5-019')
        task['condition_decisions'] = {
            'TTS_required': {'required': True, 'reason': 'Case uses generated narration'},
            'generated_music_required': {'required': False, 'reason': 'Case uses licensed existing music'},
        }
        self.assertEqual(row()['unresolved_conditions'], [])
        self.assertIn('DL-R5-016', row()['unmet_dependencies'])
        self.assertNotIn('DL-R5-017', row()['unmet_dependencies'])
        task['condition_decisions']['generated_music_required']['reason'] = ''
        with self.assertRaises(ValueError):
            row()

    def test_duplicate_predecessor_keys_and_bad_timestamp_are_rejected(self):
        with self.assertRaises(ValueError):
            self.build(previous=b'{"tasks":[],"tasks":[]}')
        for invalid in ('not-a-date', '2026-09-09T00:00:00', '2026-02-30T00:00:00Z'):
            with self.subTest(timestamp=invalid), self.assertRaises(ValueError):
                migration.prepare(ROOT, self.previous, self.source, updated_at=invalid)


if __name__ == '__main__':
    unittest.main()
