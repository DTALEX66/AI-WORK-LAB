# SPDX-License-Identifier: MIT
"""The evidence readback must answer with what the projection can actually support.

`design-lab/schemas/evidence-projection.schema.json` binds the payload of
`GET /api/evidence-projection`, which is the only place a person can ask "is any of this evidence
verified" and get a computed answer. These tests drive the real emitter over the real ledger and
inject each lie the contract is meant to refuse.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from design_lab.governance import evidence_readback as er  # noqa: E402
from design_lab.governance import reporting  # noqa: E402
from design_lab import http_service  # noqa: E402

LEDGER_REL = reporting.LEDGER


class LiveProjectionTests(unittest.TestCase):
    """What the route actually answers, from the ledger and the object database."""

    @classmethod
    def setUpClass(cls):
        cls.payload = er.projection()

    def test_the_live_payload_satisfies_its_own_contract(self):
        """No refusal raised, and the guard hands back the same bytes it was given."""
        clone = copy.deepcopy(self.payload)
        self.assertEqual(clone, er._check(clone))

    def test_the_version_is_one_value_on_both_sides(self):
        schema = json.loads(er.SCHEMA_PATH.read_text(encoding='utf-8'))
        self.assertEqual(schema['properties']['schemaVersion']['const'],
                         er.EVIDENCE_PROJECTION_SCHEMA_VERSION)
        self.assertEqual(self.payload['schemaVersion'], er.EVIDENCE_PROJECTION_SCHEMA_VERSION)

    def test_totals_are_arithmetic_on_the_same_receipts_the_page_renders(self):
        totals = self.payload['totals']
        receipts = self.payload['receipts']
        self.assertEqual(totals['records'], len(receipts))
        self.assertEqual(totals['verified'] + totals['unverified'], totals['records'])
        self.assertLessEqual(totals['current'], totals['verified'],
                             'a receipt cannot be current about bytes it cannot reproduce')
        self.assertEqual(totals['outcomePass'],
                         sum(1 for r in receipts if r['outcome'] == 'PASS'))

    def test_reason_counts_use_the_bare_vocabulary_not_the_pathed_form(self):
        counts = self.payload['reasonCounts']
        for group in ('integrity', 'currency'):
            for token in counts[group]:
                self.assertNotIn(':', token, f'{group} counts must key on the reason, not a path')
        recomputed = {}
        for receipt in self.payload['receipts']:
            for reason in receipt['integrityReasons']:
                recomputed[er._token(reason)] = recomputed.get(er._token(reason), 0) + 1
        self.assertEqual(recomputed, counts['integrity'])

    def test_a_record_never_leaks_its_note_or_its_byte_lists_into_the_readback(self):
        """The projection carries a paragraph of prose and per-file digests per record.

        None of that belongs on this surface: the answer is about whether bytes reproduce, and a note
        field would let a record's own description of itself reach a reader unjudged.
        """
        for receipt in self.payload['receipts']:
            self.assertEqual(sorted(receipt), sorted([
                'binding', 'current', 'currencyReasons', 'id', 'integrityReasons', 'kind',
                'observedAt', 'outcome', 'subjectSha', 'taskIds', 'verified']))

    def test_verified_and_current_are_not_the_same_word(self):
        """The whole point of splitting them: an intact record about moved bytes is not evidence today."""
        states = {(r['verified'], r['current']) for r in self.payload['receipts']}
        self.assertIn((False, False), states, 'no unverified receipt? the ledger would have to be perfect')
        self.assertIn((True, False), states,
                      'nothing is intact-but-moved, which only happens if currency is not measured')
        for receipt in self.payload['receipts']:
            if not receipt['verified']:
                self.assertFalse(receipt['current'],
                                 'a receipt that cannot reproduce its bytes cannot be current')

    def test_the_subject_is_a_real_commit_and_no_receipt_is_asked_to_be_current_about_another(self):
        sha = self.payload['subjectSha']
        self.assertRegex(sha, '^[0-9a-f]{40}$')
        self.assertTrue(reporting._CommitReader(ROOT).has_commit(sha))


class RefusalTests(unittest.TestCase):
    """Every way this readback can fail must be named, and none of them answers an empty list."""

    def test_a_missing_ledger_is_refused_rather_than_answered_as_zero_records(self):
        scratch = Path(tempfile.mkdtemp(dir=ROOT / '.project-local/task-runtime'))
        try:
            with self.assertRaises(er.EvidenceReadbackError) as caught:
                er.projection(root=scratch, subject_sha='a' * 40)
            self.assertEqual('EVIDENCE_LEDGER_ABSENT', caught.exception.code)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_a_ledger_that_will_not_project_is_refused_with_the_reason(self):
        scratch = Path(tempfile.mkdtemp(dir=ROOT / '.project-local/task-runtime'))
        try:
            target = scratch / LEDGER_REL
            target.parent.mkdir(parents=True)
            broken = json.loads((ROOT / LEDGER_REL).read_text(encoding='utf-8'))
            broken['evidence'].append(dict(broken['evidence'][0]))  # duplicate id
            target.write_text(json.dumps(broken), encoding='utf-8', newline='\n')
            with self.assertRaises(er.EvidenceReadbackError) as caught:
                er.projection(root=scratch, subject_sha='a' * 40)
            self.assertEqual('EVIDENCE_LEDGER_REJECTED', caught.exception.code)
            self.assertTrue(caught.exception.details, 'a refusal with no reason is a dead end')
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_a_record_set_beyond_the_contract_bound_is_refused_not_truncated(self):
        original = er.MAX_RECEIPTS
        try:
            er.MAX_RECEIPTS = 1
            with self.assertRaises(er.EvidenceReadbackError) as caught:
                er.projection(subject_sha='a' * 40)
            self.assertEqual('EVIDENCE_PROJECTION_OVERFLOW', caught.exception.code)
        finally:
            er.MAX_RECEIPTS = original

    def test_a_missing_schema_file_is_refused_as_absent_not_validated_as_unbounded(self):
        original = er.SCHEMA_PATH
        try:
            er.SCHEMA_PATH = ROOT / 'design-lab/schemas/not-the-evidence-contract.schema.json'
            er._SCHEMA_CACHE.clear()
            with self.assertRaises(er.EvidenceReadbackError) as caught:
                er._check({'schemaVersion': er.EVIDENCE_PROJECTION_SCHEMA_VERSION})
            self.assertEqual('EVIDENCE_CONTRACT_ABSENT', caught.exception.code)
        finally:
            er.SCHEMA_PATH = original
            er._SCHEMA_CACHE.clear()

    def test_an_unregistered_reason_token_is_refused(self):
        """A new reason in the code that nobody registered in the schema cannot reach a reader."""
        payload = er.projection(subject_sha='a' * 40)
        payload['receipts'][0]['integrityReasons'] = ['BRAND_NEW_REASON:some/file.py']
        with self.assertRaises(er.EvidenceReadbackError) as caught:
            er._check(payload)
        self.assertEqual('EVIDENCE_CONTRACT_VIOLATION', caught.exception.code)
        self.assertTrue(any('integrityReasons' in problem for problem in caught.exception.details))

    def test_a_renamed_field_is_refused_rather_than_served_short(self):
        payload = er.projection(subject_sha='a' * 40)
        payload['totals']['verifed'] = payload['totals'].pop('verified')  # one letter, silently wrong
        with self.assertRaises(er.EvidenceReadbackError) as caught:
            er._check(payload)
        self.assertEqual('EVIDENCE_CONTRACT_VIOLATION', caught.exception.code)


class RouteSurfaceTests(unittest.TestCase):
    """The dispatch and the refusal vocabulary have to stay in step with each other."""

    def test_every_refusal_code_maps_to_a_status(self):
        """Collected from the emitter's own AST, so adding a refusal without a status is red.

        The generic fallback in http_service would otherwise answer 500 for a condition the operator
        could only fix by looking at the checkout, and a reader cannot tell a missing ledger from a
        broken contract.
        """
        tree = ast.parse((ROOT / 'src/design_lab/governance/evidence_readback.py')
                         .read_text(encoding='utf-8'))
        codes = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == 'EvidenceReadbackError'
                    and node.args and isinstance(node.args[0], ast.Constant)):
                codes.add(node.args[0].value)
        self.assertGreaterEqual(len(codes), 5, f'found only {sorted(codes)}')
        unmapped = sorted(codes - set(http_service.EVIDENCE_READBACK_STATUS))
        self.assertEqual([], unmapped, 'a refusal the route cannot answer with a status')
        invented = sorted(set(http_service.EVIDENCE_READBACK_STATUS) - codes)
        self.assertEqual([], invented, 'a status mapping for a code nothing raises is dead vocabulary')

    def test_the_route_is_dispatched_and_binds_the_contract(self):
        source = (ROOT / 'src/design_lab/http_service.py').read_text(encoding='utf-8')
        self.assertIn("/api/evidence-projection", source)
        self.assertIn('evidence_projection()', source)
        ledger = json.loads((ROOT / 'design-lab/config/contract-bindings.json')
                            .read_text(encoding='utf-8'))
        row = next(r for r in ledger['routes'] if r['route'] == '/api/evidence-projection')
        self.assertEqual('BOUND_SCHEMA', row['kind'])
        self.assertEqual('design-lab/schemas/evidence-projection.schema.json', row['schema'])
        self.assertEqual(er.EVIDENCE_PROJECTION_SCHEMA_VERSION, row['version'])


class ObjectReadCostTests(unittest.TestCase):
    """A readback nobody waits for is not a surface; the cost is part of the capability.

    Measured 2026-10-08 before batching: 10.0s cold and 10.3s warm for 75 receipts over 502 byte
    claims, because every claim took its own `git show`. That was not a slow page -- it was a
    question nobody could ask. Batched per commit, the same answers cost 1.0s.

    The assertion counts git processes by shape rather than timing anything, because a wall-clock
    budget would fail on a loaded runner and pass on an idle one while the real regression -- back to
    one spawn per claim -- stays invisible in both.
    """

    def _count(self, call):
        seen = []
        real = reporting.subprocess.run

        def counting(args, **kwargs):
            seen.append([str(item) for item in args])
            return real(args, **kwargs)

        reporting.subprocess.run = counting
        try:
            call()
        finally:
            reporting.subprocess.run = real
        return seen

    def test_no_claim_is_read_by_its_own_git_process(self):
        ledger = json.loads((ROOT / reporting.LEDGER).read_text(encoding='utf-8'))
        subjects = {entry['subject_sha'] for entry in ledger['evidence']}
        calls = self._count(lambda: er.projection(subject_sha='a' * 40))
        per_claim = [args for args in calls if 'show' in args]
        self.assertEqual([], per_claim,
                         f'{len(per_claim)} claims fell back to `git show`; the batch never ran')
        batched = [args for args in calls if '--batch' in args]
        # one batch per commit the projection reads (the ledger's subjects plus the projection's own)
        self.assertLessEqual(len(batched), len(subjects) + 2,
                             'the batch count grew past the commits, so claims are being re-read')
        self.assertLessEqual(len(calls), 3 * (len(subjects) + 2) + 4,
                             f'{len(calls)} git processes for {len(subjects)} commits -- the '
                             'readback is back to per-claim cost')

    def test_the_batched_read_returns_the_same_bytes_as_a_single_claim_read(self):
        """Speed that changes the verdict is not an optimisation, it is a different program."""
        ledger = json.loads((ROOT / reporting.LEDGER).read_text(encoding='utf-8'))
        sample = [entry for entry in ledger['evidence']
                  if entry.get('binding') == 'COMMIT'][:10]
        slow = reporting._CommitReader(ROOT)
        batched = reporting._CommitReader(ROOT)
        missing = 0
        for entry in sample:
            claimed = reporting.claims(entry)[0]
            batched.prefetch(entry['subject_sha'], claimed)
            for path in claimed:
                one = slow.blob(entry['subject_sha'], path)
                if one is None:
                    missing += 1
                self.assertEqual(one, batched.blob(entry['subject_sha'], path),
                                 f'{path} came back differently through the batch')
        self.assertGreater(missing, 0,
                           'no claim was absent in the sample, so the missing-blob path is untested')


if __name__ == '__main__':
    unittest.main()
