# SPDX-License-Identifier: MIT
"""The new dispatch must not revive old tasks or qualify unexecuted UI."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.governance.current_execution import projection, validate
from design_lab.governance.reporting import Reader


class CurrentExecutionTests(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((ROOT / 'design-lab/config/task-ledger-r3.json').read_text(encoding='utf-8'))
        # Controlled not-started branch, independent of future product progress.
        self.ledger['currentExecution']['evidence'] = []
        for task in self.ledger['currentExecution']['tasks']:
            task.update(state='NOT_STARTED', evidence=[])

    def test_old_receipts_never_qualify_new_ui(self):
        p = projection(Reader(ROOT), self.ledger)
        # The inventory size is read from the ledger this projection is about to replace, not typed
        # here: the shipped set grew from 34 to 50 when owner 2026-10-23 added the desktop-UI segment,
        # and a literal would have made this test the thing that had to be edited every round.
        self.assertEqual(p['counts'], {'NOT_STARTED': len(self.ledger['currentExecution']['tasks'])})
        self.assertEqual(p['ledger_partition'], 'currentExecution')
        self.assertEqual(p['mobile'], 'FROZEN_DEFERRED')
        self.assertTrue(all(t['evidence_level'] == 'NO_EVIDENCE' for t in p['tasks']))

    def test_done_without_independent_axes_is_rejected(self):
        self.ledger['currentExecution']['tasks'][0]['state'] = 'DONE'
        with self.assertRaisesRegex(ValueError, 'lacks required'):
            validate(Reader(ROOT), self.ledger)

    def test_historical_axis_cannot_be_edited_in_current_work(self):
        self.ledger['tasks'][0]['axes']['implementation']['state'] = 'NOT_EXECUTED'
        with self.assertRaisesRegex(ValueError, 'frozen predecessor'):
            validate(Reader(ROOT), self.ledger)

    def test_dependency_cycle_is_rejected_even_with_a_matching_source_hash(self):
        execution = self.ledger['currentExecution']
        definitions = json.loads((ROOT / execution['source']['path']).read_text(encoding='utf-8'))
        definitions['tasks'][0]['implementation_depends_on'] = [definitions['tasks'][0]['id']]
        raw = json.dumps(definitions).encode()
        execution['source']['sha256'] = hashlib.sha256(raw).hexdigest()
        original = Reader(ROOT)
        class ChangedReader:
            def read(self, path):
                return raw if path == execution['source']['path'] else original.read(path)
        with self.assertRaisesRegex(ValueError, 'cyclic current'):
            validate(ChangedReader(), self.ledger)

    def test_missing_subtask_cannot_hide_behind_parent_inventory(self):
        self.ledger['currentExecution']['tasks'].pop()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            validate(Reader(ROOT), self.ledger)


if __name__ == '__main__':
    unittest.main()
