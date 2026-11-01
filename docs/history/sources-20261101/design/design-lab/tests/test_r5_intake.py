# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_r5_intake import validate


class R5IntakeTests(unittest.TestCase):
    def setUp(self):
        self.source=json.loads((ROOT/'docs/history/taskpacks/r5-20260908/tasks.json').read_text(encoding='utf-8'))

    def test_all_tasks_are_ordered_after_dependencies(self):
        order=validate(self.source)
        self.assertEqual(len(order),28)
        for task in self.source['tasks']:
            for dep in task['depends_on']:self.assertLess(order.index(dep),order.index(task['id']))

    def test_missing_duplicate_or_unknown_ids_are_rejected(self):
        for change in (lambda d:d['tasks'].pop(),lambda d:d['tasks'].append(copy.deepcopy(d['tasks'][0])),
                       lambda d:d['tasks'][0].update(id='DL-R5-999')):
            value=copy.deepcopy(self.source);change(value)
            with self.assertRaises(ValueError):validate(value)

    def test_missing_acceptance_and_false_completed_axes_are_rejected(self):
        for field in ('acceptance','rollback','evidence_required','axes'):
            value=copy.deepcopy(self.source);del value['tasks'][0][field]
            with self.assertRaises(ValueError):validate(value)
        value=copy.deepcopy(self.source);value['tasks'][0]['axes']['host_live']='PASS'
        with self.assertRaises(ValueError):validate(value)

    def test_unknown_dependencies_and_cycles_are_rejected(self):
        for deps in (['DL-R5-999'],['DL-R5-002']):
            value=copy.deepcopy(self.source);value['tasks'][0]['depends_on']=deps
            with self.assertRaises(ValueError):validate(value)

    def test_optional_generators_cannot_become_m1_prerequisites(self):
        for dependency in ('DL-R5-008','DL-R5-018','DL-R5-024'):
            value=copy.deepcopy(self.source)
            next(t for t in value['tasks'] if t['id']=='DL-R5-009')['depends_on'].append(dependency)
            with self.assertRaises(ValueError):validate(value)

    def test_conditional_media_dependencies_cannot_be_dropped_or_retargeted(self):
        for replacement in ({},{'TTS_required':'DL-R5-008','generated_music_required':'DL-R5-017'}):
            value=copy.deepcopy(self.source)
            next(t for t in value['tasks'] if t['id']=='DL-R5-019')['conditional_dependencies']=replacement
            with self.assertRaises(ValueError):validate(value)


if __name__=='__main__':unittest.main()
