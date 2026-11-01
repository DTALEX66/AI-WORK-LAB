# SPDX-License-Identifier: MIT
"""The ledger contract gate must catch the defects that froze the projections.

`main` carried two contract violations for six days (an evidence record with no
retained artefact, and completion states with no reassessment) while every CI
job stayed green, because nothing validated the ledger itself. These tests pin
both rules so the new gate cannot degrade into a no-op.

Both mutation fixtures edit `tasks` or `evidence` -- which are also the two fields
`current_execution.validate` compares against the frozen predecessor snapshot, and that
guard runs first inside `r5_contract.validate`. With `currentExecution` present the guard
fires, `assertRaisesRegex` never sees the rule it names, and the test is a no-op that looks
like a pass. The fixtures drop that partition, which removes only the guard scoped to it;
`test_the_frozen_partition_guard_still_fires_first` pins the other half so the drop cannot
quietly become a way of avoiding a real rejection.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab.governance import reporting
from design_lab.governance.reporting import LEDGER, Reader, validate_ledger_contract


class TaskLedgerContractGateTests(unittest.TestCase):
    def test_repo_ledger_satisfies_its_own_contract(self):
        validate_ledger_contract(REPO)

    def test_the_frozen_partition_guard_still_fires_first(self):
        """Positive control for the two fixtures below: the dropped guard is live.

        Measured 2026-10-13: with `currentExecution` present, mutating either field raises
        `ValueError: frozen predecessor partition changed: tasks|evidence` before any R5 rule.
        If this ever stops raising, the fixtures below are no longer proving what they say.
        """
        reader = Reader(REPO)
        for field, mutate in (('tasks', lambda l: l['tasks'][0].__setitem__('title', 'rewritten')),
                              ('evidence', lambda l: l['evidence'][-1].__setitem__('artifacts', []))):
            ledger = copy.deepcopy(reader.json(LEDGER))
            self.assertIn('currentExecution', ledger, 'the shipped ledger lost its partition')
            mutate(ledger)
            with self.assertRaisesRegex(Exception,
                                        f'frozen predecessor partition changed: {field}'):
                reporting._validate(reader, ledger)

    def test_evidence_record_without_retained_artefact_is_rejected(self):
        reader = Reader(REPO)
        ledger = copy.deepcopy(reader.json(LEDGER))
        ledger.pop('currentExecution', None)   # see the module docstring: the guard above owns this partition
        ledger['evidence'][-1]['artifacts'] = []
        with self.assertRaisesRegex(Exception, 'artifacts'):
            reporting._validate(reader, ledger)

    def test_completion_state_without_reassessment_is_rejected(self):
        reader = Reader(REPO)
        ledger = copy.deepcopy(reader.json(LEDGER))
        ledger.pop('currentExecution', None)   # see the module docstring: the guard above owns this partition
        for task in ledger['tasks']:
            if any(axis['state'] in {'PASS', 'IMPLEMENTED_LOCAL'}
                   for axis in task['axes'].values()):
                task['reassessment'] = 'PENDING_EVIDENCE_REVIEW'
                break
        else:
            self.fail('no task carries a completion state to test')
        with self.assertRaisesRegex(Exception, 'reassessment'):
            reporting._validate(reader, ledger)


if __name__ == '__main__':
    unittest.main()
