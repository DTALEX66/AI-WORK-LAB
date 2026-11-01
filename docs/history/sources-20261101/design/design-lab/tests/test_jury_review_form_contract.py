# SPDX-License-Identifier: MIT
"""The Workbench's jury form must be fillable by the contract it posts to.

`JURY_CRITERIA` and the document skeleton live in TypeScript, while
`assurance/human_jury.py` is the gatekeeper. Without this check the page could
offer five axes whose weights sum to 0.9, or omit a field the schema requires, and
every submission would come back 400 with the user blaming their own judgement.

The test reads the declaration out of shell.ts and drives it through
`record_verdict` unchanged -- the same code path the endpoint runs.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / 'apps/workbench' / 'shell.ts'
import sys
sys.path.insert(0, str(REPO / 'src'))

from design_lab.assurance import human_jury  # noqa: E402


def declared_criteria():
    text = SHELL.read_text(encoding='utf-8')
    block = re.search(r"export const JURY_CRITERIA = \[(.*?)\] as const", text, re.S)
    assert block, 'JURY_CRITERIA is no longer declared in shell.ts'
    rows = re.findall(r"\{ criterion_id: '([^']+)', weight: ([0-9.]+) \}", block.group(1))
    assert rows, 'JURY_CRITERIA declared no axes'
    return [(name, float(weight)) for name, weight in rows]


class JuryFormContractTests(unittest.TestCase):
    def test_declared_weights_sum_to_one(self):
        total = round(sum(weight for _, weight in declared_criteria()), 10)
        self.assertEqual(total, 1.0,
                         'human_jury refuses any other weight sum, so the form could '
                         'never be submitted successfully')

    def test_declared_criteria_are_unique(self):
        names = [name for name, _ in declared_criteria()]
        self.assertEqual(len(names), len(set(names)), f'duplicate criterion_id in {names}')

    def test_the_form_document_is_accepted_by_the_contract(self):
        criteria = [{'criterion_id': name, 'weight': weight, 'score': 4.0,
                     'note': 'reviewed at 100%'} for name, weight in declared_criteria()]
        document = {
            'schemaVersion': human_jury.REVIEW_VERSION,
            'kind': human_jury.KIND_VERDICT,
            'jury_record_id': 'jury-form-contract-1',
            'subject_ref': 'version:v1',
            'artifact_sha256': 'sha256:' + 'a' * 64,
            'juror': {'juror_id': 'dtalex66', 'kind': 'HUMAN', 'members': [],
                      'attestation': 'reviewed the exported poster at 100%'},
            'criteria': criteria,
            'verdict': 'APPROVE',
            'decided_at': '2026-10-08T00:00:00Z',
            'supersedes': None,
            'evidence_refs': [],
        }
        accepted = human_jury.record_verdict(document)
        self.assertEqual(accepted['jury_record_id'], 'jury-form-contract-1')

    def test_a_rejection_from_the_form_still_needs_evidence(self):
        """The UI keeps the REJECT field visible for a reason the contract enforces."""
        criteria = [{'criterion_id': name, 'weight': weight, 'score': 2.0,
                     'note': 'see notes'} for name, weight in declared_criteria()]
        document = {
            'schemaVersion': human_jury.REVIEW_VERSION, 'kind': human_jury.KIND_VERDICT,
            'jury_record_id': 'jury-form-contract-2', 'subject_ref': 'version:v1',
            'artifact_sha256': 'sha256:' + 'b' * 64,
            'juror': {'juror_id': 'dtalex66', 'kind': 'HUMAN', 'members': [],
                      'attestation': 'reviewed at 100%'},
            'criteria': criteria, 'verdict': 'REJECT',
            'decided_at': '2026-10-08T00:00:00Z', 'supersedes': None, 'evidence_refs': [],
        }
        with self.assertRaises(human_jury.AssuranceError) as caught:
            human_jury.record_verdict(document)
        self.assertIn('evidence_ref', str(caught.exception))
        text = SHELL.read_text(encoding='utf-8')
        self.assertIn('拒绝时必填', text, 'the form must say the rejection evidence is required')


if __name__ == '__main__':
    unittest.main()
