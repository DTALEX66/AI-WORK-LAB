# SPDX-License-Identifier: MIT
"""The rollback classifier, case by case.

`native_delivery._resolve_rollback` is the function that decides whether a receipt's promise still
has a target, so every branch of it is worth a named assertion. These run against a stub
connection rather than a live delivery on purpose: the product path (a real published archive read
back through the route) is covered in test_delivery_receipt_wiring.py, and what is exercised here
is the classification -- including the two branches a happy-path integration test can never
reach, because a real delivery only ever produces RESOLVED.

The rules under test are the ones that make the answer trustworthy:
* a reference the resolver cannot parse is reported as unparsed, with NULL identifiers, and is
  never quietly matched to a plausible row;
* a version that exists under another project is not a restore point for this one;
* a version row that is not ACTIVE is not a restore point either;
* the aggregate word distinguishes "nothing to check" from "all checked", because collapsing
  those two is exactly how an empty ledger reads as a clean one.
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab import native_delivery as nd  # noqa: E402

ASSET = 'native-' + 'a' * 64
VERSION = 'v-' + 'b' * 64
PROJECT = 'c' * 32
OTHER = 'd' * 32


class StubConnection:
    """Answers the one query the resolver asks, from a table of rows the test declares."""

    def __init__(self, rows):
        self.rows = rows
        self.asks = []

    def execute(self, sql, parameters=()):
        self.asks.append((sql, tuple(parameters)))
        assert sql == nd.ROLLBACK_LOOKUP, 'the resolver asked a query this stub does not model'
        return self

    def fetchone(self):
        return self.rows


def entry(reference, deliverable_id='native.psd'):
    return {'deliverable_id': deliverable_id,
            'rollback': None if reference == '__none__' else {'backup_ref': reference,
                                                              'procedure': 'drop the appended'}}


class ResolvedTests(unittest.TestCase):
    def test_an_active_version_of_this_projects_asset_resolves(self):
        proof = nd._resolve_rollback(StubConnection(('ACTIVE', 4, PROJECT)), PROJECT,
                                      entry(f'asset:{ASSET}/version:{VERSION}'))
        self.assertEqual(proof['state'], 'RESOLVED')
        self.assertEqual(proof['version_no'], 4)
        self.assertEqual(proof['source_state'], 'ACTIVE')
        self.assertEqual(proof['asset_id'], ASSET)
        self.assertIn('ACTIVE', proof['reason'])

    def test_the_lookup_is_one_query_with_the_parsed_identifiers(self):
        conn = StubConnection(('ACTIVE', 1, PROJECT))
        nd._resolve_rollback(conn, PROJECT, entry(f'asset:{ASSET}/version:{VERSION}'))
        self.assertEqual(len(conn.asks), 1)
        self.assertEqual(conn.asks[0][1], (ASSET, VERSION))


class UnparsedTests(unittest.TestCase):
    def test_a_reference_without_a_version_is_reported_not_matched(self):
        """The dangerous mistake available here is to look up the asset half and call it good."""
        conn = StubConnection(('ACTIVE', 7, PROJECT))
        proof = nd._resolve_rollback(conn, PROJECT, entry(f'asset:{ASSET}'))
        self.assertEqual(proof['state'], 'REF_UNPARSED')
        self.assertEqual(conn.asks, [], 'an unparsable reference must not reach the ledger')
        self.assertIsNone(proof['version_no'])
        self.assertIsNone(proof['asset_id'])
        self.assertIn('not in the asset:', proof['reason'])

    def test_other_shapes_are_all_unparsed(self):
        # ``asset:<id>`` with no version is listed here as well as in the test above: this list is
        # the inventory of references that must never parse, and the mutation that makes the
        # version optional is only convicted here if the versionless shape is really listed. The
        # test above adds the separate promise that nothing is looked up.
        for reference in ('backup-1', 'backup://job-7', 'asset:/version:', 'ASSET:x/version:y',
                          'asset:x/version:y/extra', f'asset:{ASSET}', ''):
            with self.subTest(reference=reference):
                proof = nd._resolve_rollback(StubConnection(None), PROJECT, entry(reference))
                self.assertEqual(proof['state'], 'REF_UNPARSED', reference)

    def test_a_missing_reference_is_not_the_same_as_an_unrecognised_one(self):
        proof = nd._resolve_rollback(StubConnection(None), PROJECT, entry('__none__'))
        self.assertEqual(proof['state'], 'REF_UNPARSED')
        self.assertIsNone(proof['backup_ref'])
        self.assertIn('no backup_ref', proof['reason'])


class MissingAndForeignTests(unittest.TestCase):
    def test_a_version_that_is_not_recorded_at_all_is_missing(self):
        proof = nd._resolve_rollback(StubConnection(None), PROJECT,
                                      entry(f'asset:{ASSET}/version:{VERSION}'))
        self.assertEqual(proof['state'], 'SOURCE_MISSING')
        self.assertIsNone(proof['version_no'])
        self.assertIn('no version', proof['reason'])

    def test_another_projects_version_is_not_a_restore_point_for_this_one(self):
        proof = nd._resolve_rollback(StubConnection(('ACTIVE', 2, OTHER),), PROJECT,
                                     entry(f'asset:{ASSET}/version:{VERSION}'))
        self.assertEqual(proof['state'], 'OTHER_PROJECT')
        # The identifiers came out of the operator's own receipt, so what the ledger said is
        # reported rather than withheld: "exists, but is not yours" is a different instruction from
        # "not found", and hiding the number would blur those two into one.
        self.assertEqual(proof['version_no'], 2)
        self.assertEqual(proof['source_state'], 'ACTIVE')
        self.assertIn('another project', proof['reason'])

    def test_a_superseded_row_is_not_active_and_says_which_state_it_is(self):
        proof = nd._resolve_rollback(StubConnection(('SUPERSEDED', 3, PROJECT),), PROJECT,
                                     entry(f'asset:{ASSET}/version:{VERSION}'))
        self.assertEqual(proof['state'], 'SOURCE_NOT_ACTIVE')
        self.assertEqual(proof['source_state'], 'SUPERSEDED')
        self.assertIn('SUPERSEDED', proof['reason'])


class SummaryTests(unittest.TestCase):
    """The aggregate word, driven through the real classifier with a sequenced stub.

    Each deliverable in the document names a parseable reference, so the answer the stub gives at
    position i is what decides proof i -- which means the sequence below is the sequence the
    resolver actually saw, not a list this test asserts about itself.
    """

    class Sequenced:
        def __init__(self, states):
            self.states = states
            self.index = -1

        def execute(self, sql, parameters=()):
            assert sql == nd.ROLLBACK_LOOKUP
            self.index += 1
            return self

        def fetchone(self):
            state = self.states[self.index]
            if state == 'RESOLVED':
                return ('ACTIVE', 1, PROJECT)
            if state == 'SOURCE_MISSING':
                return None
            if state == 'OTHER_PROJECT':
                return ('ACTIVE', 1, OTHER)
            if state == 'SOURCE_NOT_ACTIVE':
                return ('SUPERSEDED', 1, PROJECT)
            raise AssertionError(f'{state} cannot come from a lookup; classify it with '
                             'nd._resolve_rollback on a stub that returns a row instead')

    def resolve(self, states):
        document = {'deliverables': [{'deliverable_id': f'd{i}',
                                      'rollback': {'backup_ref':
                                                   f'asset:{ASSET}/version:{VERSION}',
                                                   'procedure': 'p'}}
                                     for i in range(len(states))]}
        return nd.rollback_proofs(self.Sequenced(states), document, PROJECT)

    def test_all_resolved(self):
        summary, proofs = self.resolve(['RESOLVED', 'RESOLVED'])
        self.assertEqual(summary, 'ALL_RESOLVED')
        self.assertEqual([proof['state'] for proof in proofs], ['RESOLVED', 'RESOLVED'])

    def test_one_of_two_failing_is_partly_not_all(self):
        summary, proofs = self.resolve(['RESOLVED', 'SOURCE_MISSING'])
        self.assertEqual(summary, 'PARTLY_UNRESOLVED')
        self.assertEqual([proof['state'] for proof in proofs], ['RESOLVED', 'SOURCE_MISSING'])

    def test_none_resolved(self):
        summary, _proofs = self.resolve(['SOURCE_MISSING', 'SOURCE_NOT_ACTIVE'])
        self.assertEqual(summary, 'NONE_RESOLVED')

    def test_an_empty_document_is_not_reported_as_all_resolved(self):
        summary, proofs = nd.rollback_proofs(StubConnection(None), {'deliverables': []}, PROJECT)
        self.assertEqual(summary, 'NOTHING_TO_CHECK')
        self.assertEqual(proofs, [])
        self.assertNotEqual(summary, 'ALL_RESOLVED')

    def test_a_document_with_no_deliverables_key_at_all_is_also_nothing_to_check(self):
        self.assertEqual(nd.rollback_proofs(StubConnection(None), {}, PROJECT)[0],
                         'NOTHING_TO_CHECK')


class LedgerUnreadableTests(unittest.TestCase):
    """The difference between "nothing to look at" and "the ledger would not answer".

    `rollback_proofs` itself never invents this word -- `_rollback_or_unreadable` catches the query
    error around it, because a receipt whose ledger could not be read must not be reported under
    NOTHING_TO_CHECK, which is a statement about the document.
    """

    class Raising:
        def execute(self, sql, parameters=()):
            raise sqlite3.OperationalError('no such table: asset_version')

    def test_a_ledger_that_raises_is_its_own_word_not_nothing_to_check(self):
        document = {'deliverables': [{'deliverable_id': 'native.psd',
                                      'rollback': {'backup_ref':
                                                   f'asset:{ASSET}/version:{VERSION}',
                                                   'procedure': 'p'}}]}
        summary, proofs = nd._rollback_or_unreadable(self.Raising(), document, PROJECT)
        self.assertEqual(summary, 'LEDGER_UNREADABLE')
        self.assertEqual(proofs, [])
        self.assertNotEqual(summary, 'NOTHING_TO_CHECK',
                            'a failure to look cannot arrive as "there was nothing to look at"')

    def test_a_ledger_that_answers_still_reports_what_it_said(self):
        summary, proofs = nd._rollback_or_unreadable(
            StubConnection(('ACTIVE', 2, PROJECT)),
            {'deliverables': [{'deliverable_id': 'native.psd',
                               'rollback': {'backup_ref': f'asset:{ASSET}/version:{VERSION}'}}]},
            PROJECT)
        self.assertEqual(summary, 'ALL_RESOLVED')
        self.assertEqual(len(proofs), 1)


class VocabularyTests(unittest.TestCase):
    def test_every_state_word_ships_with_its_meaning(self):
        self.assertEqual(set(nd.ROLLBACK_STATE_MEANING),
                         set(nd.ROLLBACK_STATES) | set(nd.ROLLBACK_SUMMARIES),
                         'every state word needs a meaning, and no meaning may be orphaned')

    def test_the_two_aggregate_words_for_nothing_checked_are_not_one_word(self):
        # NOTHING_TO_CHECK says the document names no deliverable; LEDGER_UNREADABLE says the
        # lookup itself failed. They share an empty proof list and must not share a vocabulary slot.
        self.assertIn('NOTHING_TO_CHECK', nd.ROLLBACK_SUMMARIES)
        self.assertIn('LEDGER_UNREADABLE', nd.ROLLBACK_SUMMARIES)
        self.assertEqual(len(nd.ROLLBACK_SUMMARIES), len(set(nd.ROLLBACK_SUMMARIES)))
        joined = (nd.ROLLBACK_STATE_MEANING['LEDGER_UNREADABLE']
                  + nd.ROLLBACK_STATE_MEANING['NOTHING_TO_CHECK']).lower()
        self.assertIn('could not be asked', joined)
        self.assertIn('no deliverables', joined)

    def test_the_per_deliverable_and_aggregate_vocabularies_are_disjoint(self):
        self.assertFalse(set(nd.ROLLBACK_STATES) & set(nd.ROLLBACK_SUMMARIES),
                         'a reader cannot tell a state from a summary if one word is both')

    def test_resolution_refuses_nothing_and_proves_no_restore(self):
        joined = ' '.join(nd.ROLLBACK_DOES_NOT_PROVE).lower()
        self.assertIn('restore', joined)
        self.assertIn('none has been', joined)
        self.assertGreaterEqual(len(nd.ROLLBACK_DOES_NOT_PROVE), 3)


if __name__ == '__main__':
    unittest.main()
