# SPDX-License-Identifier: MIT
"""The RIGHTS gate's decision store: what may be filed, and what cannot be rewritten.

The gate had a contract and no table for it, so nothing here was ever driven against
stored bytes before. Every case below goes through the real append-only store on a real
state database, because the properties that matter are the ones a schema cannot express:
a decision that names automation is refused by name, history cannot be edited, and a scope
nobody filed has no entry at all -- it is never defaulted to a word that claims somebody
was asked.

Two guards are tested against BOTH sides rather than asserted from a copy: the decision
vocabulary is read out of ``contracts/rights-decision.schema.json``, and the table's CHECK
list is read out of ``design-lab-state-rights-v1.sql``. A restatement that drifts from the
contract is the second-authority failure these tests exist to catch.
"""
from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(REPO / 'src'))

from design_lab.assurance import rights_ledger                       # noqa: E402
from design_lab.assurance.rights_ledger import RightsLedgerError     # noqa: E402
from design_lab.rights_review import CLEARANCE_STATES, readback      # noqa: E402
from design_lab.runtime.state_resources import state_schema          # noqa: E402

SCHEMA_FILE = REPO / 'design-lab/schemas/contracts/rights-decision.schema.json'
STATE_SQL = state_schema('design-lab-state-rights-v1.sql')


def contract_document(**overrides) -> dict:
    """One complete decision, written the way a human signs one."""
    document = {
        'schemaVersion': 'design-lab/rights-decision/v1',
        'decision_id': 'rd-1',
        'use_scope': 'commercial-print',
        'decision': 'APPROVED',
        'decided_by': 'dtalex66',
        'decided_at': '2026-10-08T00:00:00Z',
        'territory': 'worldwide',
        'license_ref': 'OFL-1.1',
        'note': 'read the licence text of the shipped font revision',
    }
    document.update(overrides)
    return document


class RightsLedgerTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.db = self.base / 'state.db'
        self.conn = rights_ledger.connect(self.db)
        self.conn.execute('INSERT INTO project VALUES ("p1","Rights Probe",'
                          '"2026-10-08T00:00:00Z")')
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def file(self, *, project_id='p1', actor_kind='HUMAN', supersedes=None,
             **overrides) -> dict:
        return rights_ledger.record(self.conn, project_id=project_id,
                                    document=contract_document(**overrides),
                                    actor_kind=actor_kind, supersedes=supersedes)

    # ------------------------------------------------------------- one authority

    def test_the_field_list_and_the_enum_are_loaded_from_the_contract(self):
        """This module states no second copy of either, so the schema file IS the check."""
        declared = json.loads(SCHEMA_FILE.read_text(encoding='utf-8'))
        self.assertEqual(set(rights_ledger.field_names()), set(declared['properties']))
        self.assertEqual(set(rights_ledger.required_field_names()), set(declared['required']))
        self.assertEqual(set(rights_ledger.decision_vocabulary()),
                         set(declared['properties']['decision']['enum']))
        self.assertIs(declared['additionalProperties'], False,
                      'a non-closed contract would let a submission smuggle fields through')

    def test_the_table_enum_is_the_contract_enum(self):
        """The SQL CHECK list is a restatement a database needs; it is reconciled here.

        Without this, the table could keep accepting a word the contract retired (or refuse
        one it added) and every Python-side check would still look green.
        """
        sql = STATE_SQL.read_text(encoding='utf-8')
        match = re.search(r'decision TEXT NOT NULL\s+CHECK \(decision IN \((.*?)\)\)', sql, re.S)
        self.assertIsNotNone(match, 'the decision CHECK list is gone from the state schema')
        stored = set(re.findall(r"'([A-Z_]+)'", match.group(1)))
        self.assertEqual(stored, set(rights_ledger.decision_vocabulary()),
                         'the table and the contract disagree about what a decision can be')

    # ------------------------------------------------------------- the happy path

    def test_a_human_decision_is_filed_and_survives_reopening_the_database(self):
        stored = self.file()
        self.assertEqual(stored['decision_id'], 'rd-1')
        with closing(sqlite3.connect(self.db)) as reopened:
            reopened.row_factory = sqlite3.Row
            decisions = rights_ledger.list_decisions(reopened, project_id='p1')
            current = rights_ledger.current_decisions(reopened, project_id='p1')
            view = readback(reopened, 'p1')
        self.assertEqual([row['decision_id'] for row in decisions], ['rd-1'])
        self.assertEqual(list(current), ['commercial-print'])
        self.assertEqual(current['commercial-print']['decision'], 'APPROVED')
        self.assertEqual(view['rights_clearance'], 'CLEARED')
        self.assertEqual(view['approved_scope_count'], 1)
        self.assertEqual(view['filed_scope_count'], 1)

    def test_the_stored_document_is_the_validated_one_not_the_request(self):
        self.file()
        row = self.conn.execute('SELECT document_json FROM rights_decision').fetchone()
        stored = json.loads(row['document_json'])
        self.assertEqual(stored['schemaVersion'], 'design-lab/rights-decision/v1')
        # project_id and supersedes are columns, never document fields: the contract closes
        # its properties, and copying a storage fact in would make a valid decision fail
        # validation for a reason that has nothing to do with the rights gate.
        self.assertNotIn('project_id', stored)
        self.assertNotIn('supersedes', stored)

    def test_an_optional_field_left_out_stays_left_out(self):
        document = contract_document(decision_id='rd-opt')
        for name in ('territory', 'license_ref', 'note'):
            document.pop(name)
        stored = rights_ledger.record(self.conn, project_id='p1', document=document,
                                      actor_kind='HUMAN')
        self.assertEqual(set(stored), set(rights_ledger.required_field_names()))

    # ------------------------------------------------------------- who may sign it

    def test_an_actor_that_names_automation_is_refused_by_name(self):
        for actor in ('review-agent', 'codex', 'qoder-agent', 'MODEL', 'design-lab-pipeline',
                      'OpenAI-GPT-4', 'AI'):
            with self.subTest(actor=actor):
                before = len(rights_ledger.list_decisions(self.conn, project_id='p1'))
                with self.assertRaises(RightsLedgerError) as refused:
                    self.file(decision_id=f'rd-{actor}', decided_by=actor)
                self.assertEqual(refused.exception.code, 'RIGHTS_NOT_HUMAN')
                self.assertIn(actor, str(refused.exception),
                              'the refusal has to name the actor it refused')
                self.assertIn('human', str(refused.exception).lower())
                self.assertEqual(
                    len(rights_ledger.list_decisions(self.conn, project_id='p1')), before,
                    'a refused signature must leave no row behind')

    def test_a_human_name_that_merely_contains_ai_is_not_refused(self):
        """The positive control: a name check that refused everything would look safest and
        would make the gate unusable, so it has to pass an ordinary human name."""
        stored = self.file(decision_id='rd-daniel', decided_by='Daniel Aoki')
        self.assertEqual(stored['decided_by'], 'Daniel Aoki')

    def test_a_declared_automated_actor_kind_is_refused(self):
        for kind in ('AGENT', 'MODEL', 'SYSTEM', 'CODEX'):
            with self.subTest(kind=kind):
                with self.assertRaises(RightsLedgerError) as refused:
                    self.file(decision_id=f'rd-kind-{kind}', actor_kind=kind)
                self.assertEqual(refused.exception.code, 'RIGHTS_NOT_HUMAN')

    def test_a_declared_actor_kind_is_recorded_and_read_back(self):
        """The declared kind has to be a stored fact, not a parameter nobody reads.

        `actor_kind` is the only thing that separates "this person stated they are human"
        from "this name looked human to a name check", so a filing that discarded it would
        make every row report the weaker claim -- or, worse, the stronger one.
        """
        self.file(decision_id='rd-panel', actor_kind='PANEL',
                  use_scope='client-delivery', decided_by='brand-review-board')
        rows = {row['decision_id']: row['actor_kind'] for row in self.conn.execute(
            'SELECT decision_id, actor_kind FROM rights_decision')}
        self.assertEqual(rows['rd-panel'], 'PANEL')
        self.assertEqual(rights_ledger.name_checked_only(self.conn, project_id='p1'), [])
        self.assertEqual(readback(self.conn, 'p1')['name_checked_only'], [])

    def test_a_decision_that_declares_no_actor_is_refused_rather_than_assumed(self):
        with self.assertRaises(RightsLedgerError) as refused:
            self.file(decision_id='rd-nobody', decided_by='   ')
        self.assertEqual(refused.exception.code, 'RIGHTS_ACTOR_MISSING')

    def test_a_jury_record_dressed_as_a_rights_decision_is_refused_by_name(self):
        """Relabelling cannot launder an agent-authored record into a rights gate."""
        smuggled = contract_document(decision_id='rd-jury')
        smuggled['juror'] = {'juror_id': 'codex', 'kind': 'CODEX', 'attestation': 'auto'}
        with self.assertRaises(RightsLedgerError) as refused:
            rights_ledger.record(self.conn, project_id='p1', document=smuggled)
        self.assertEqual(refused.exception.code, 'RIGHTS_DECISION_INVALID')
        self.assertIn('juror', str(refused.exception))

    def test_the_database_itself_refuses_an_automation_signing_kind(self):
        """A guard the module cannot be talked out of: the column's CHECK is the last line.

        Written as a raw INSERT past every Python check, because that is the case worth
        proving -- a writer above this module that was changed, or hand-edited rows. The
        contract closes its properties and has no actor-kind field, so this column is the
        only place the distinction is recorded, and it cannot record automation.
        """
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                'INSERT INTO rights_decision (decision_id, project_id, use_scope, decision,'
                " decided_by, actor_kind, document_json, decided_at) VALUES ("
                "'rd-raw','p1','commercial-print','APPROVED','codex','AGENT','{}',"
                "'2026-10-08T00:00:00Z')")
        self.conn.rollback()
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM rights_decision WHERE actor_kind = 'AGENT'").fetchone()[0], 0)
        # A declared human kind and a NULL (name-checked, nothing declared) are both legal.
        self.conn.execute(
            'INSERT INTO rights_decision (decision_id, project_id, use_scope, decision,'
            " decided_by, actor_kind, document_json, decided_at) VALUES ("
            "'rd-null','p1','client-delivery','APPROVED','dtalex66',NULL,'{}',"
            "'2026-10-08T00:00:00Z')")
        self.conn.commit()
        self.assertEqual(self.conn.execute(
            "SELECT actor_kind FROM rights_decision WHERE decision_id='rd-null'"
        ).fetchone()[0], None)

    def test_name_checked_only_rows_are_reported_as_such(self):
        self.file(decision_id='rd-declared')
        rights_ledger.record(self.conn, project_id='p1',
                             document=contract_document(decision_id='rd-blind',
                                                        use_scope='client-delivery',
                                                        decision='PENDING_REVIEW'),
                             actor_kind=None)
        self.assertEqual(rights_ledger.name_checked_only(self.conn, project_id='p1'),
                         ['client-delivery'])
        view = readback(self.conn, 'p1')
        self.assertEqual(view['name_checked_only'], ['client-delivery'])
        self.assertEqual(view['rights_clearance'], 'NOT_REVIEWED',
                         'one approved scope does not clear a project with two')
        self.assertEqual((view['approved_scope_count'], view['filed_scope_count']), (1, 2))

    # ------------------------------------------------------------- the contract's teeth

    def test_a_decision_word_the_contract_does_not_allow_is_refused(self):
        for word in ('MAYBE', 'approve', 'CLEARED', '', 'NOT_REVIEWED'):
            with self.subTest(word=word):
                before = len(rights_ledger.list_decisions(self.conn, project_id='p1'))
                with self.assertRaises(RightsLedgerError) as refused:
                    self.file(decision_id=f'rd-word-{word}', decision=word)
                self.assertEqual(refused.exception.code, 'RIGHTS_DECISION_INVALID')
                self.assertEqual(
                    len(rights_ledger.list_decisions(self.conn, project_id='p1')), before)

    def test_a_field_the_closed_contract_does_not_declare_is_refused(self):
        smuggled = contract_document(decision_id='rd-extra')
        smuggled['expires_at'] = '2027-01-01T00:00:00Z'
        with self.assertRaises(RightsLedgerError) as refused:
            rights_ledger.record(self.conn, project_id='p1', document=smuggled)
        self.assertEqual(refused.exception.code, 'RIGHTS_DECISION_INVALID')

    def test_supersedes_is_not_a_document_field(self):
        """The contract never declared it, so a submission cannot carry one: the link is a
        column, and a writer cannot re-point a stored decision from inside its document."""
        document = contract_document(decision_id='rd-smuggle')
        document['supersedes'] = 'rd-1'
        with self.assertRaises(RightsLedgerError) as refused:
            rights_ledger.record(self.conn, project_id='p1', document=document)
        self.assertEqual(refused.exception.code, 'RIGHTS_DECISION_INVALID')
        self.assertIn('supersedes', str(refused.exception))
        self.assertEqual(rights_ledger.list_decisions(self.conn, project_id='p1'), [])

    def test_a_missing_required_field_is_refused(self):
        for name in sorted(rights_ledger.required_field_names()):
            with self.subTest(field=name):
                document = contract_document(decision_id=f'rd-no-{name}')
                document.pop(name)
                before = len(rights_ledger.list_decisions(self.conn, project_id='p1'))
                with self.assertRaises(RightsLedgerError) as refused:
                    rights_ledger.record(self.conn, project_id='p1', document=document)
                # A document that states no actor is refused for that fact, by name, before
                # the generic contract message; every other gap is the contract's own finding.
                self.assertEqual(refused.exception.code, 'RIGHTS_ACTOR_MISSING'
                                 if name == 'decided_by' else 'RIGHTS_DECISION_INVALID')
                self.assertEqual(
                    len(rights_ledger.list_decisions(self.conn, project_id='p1')), before)

    def test_a_timestamp_that_is_not_rfc_3339_is_refused(self):
        """The contract says `format: date-time`; the installed validator does not check
        formats, so the store has to. "last tuesday" would otherwise be permanent history."""
        for value in ('last tuesday', '2026-10-08', '2026-10-08T00:00:00', ''):
            with self.subTest(value=value):
                with self.assertRaises(RightsLedgerError) as refused:
                    self.file(decision_id=f'rd-time-{len(value)}', decided_at=value)
                self.assertEqual(refused.exception.code, 'RIGHTS_TIMESTAMP_INVALID')

    def test_a_contract_that_no_longer_binds_this_version_is_refused(self):
        """One-sided version moves are the failure this store was written against.

        The schema file is the authority and this module names the version it is written
        for; if the file's const moves, validating against it would silently be validating
        a different contract, so the load itself refuses.
        """
        shifted = json.loads(json.dumps(rights_ledger.contract()))
        shifted['properties']['schemaVersion']['const'] = 'design-lab/rights-decision/v2'
        path = self.base / 'shifted.schema.json'
        path.write_text(json.dumps(shifted), encoding='utf-8')
        saved = rights_ledger.CONTRACT_PATH
        try:
            rights_ledger.CONTRACT_PATH = path
            rights_ledger.contract.cache_clear()
            with self.assertRaises(RightsLedgerError) as refused:
                rights_ledger.decision_vocabulary()
            self.assertEqual(refused.exception.code, 'RIGHTS_CONTRACT_UNBOUND')
            self.assertIn('design-lab/rights-decision/v2', str(refused.exception))
        finally:
            rights_ledger.CONTRACT_PATH = saved
            rights_ledger.contract.cache_clear()
        # The real contract is readable again, or the case above proved nothing but a swap.
        self.assertEqual(rights_ledger.CONTRACT_VERSION,
                         rights_ledger.contract()['properties']['schemaVersion']['const'])

    # ------------------------------------------------------------- absence

    def test_a_project_nobody_filed_for_reads_NOT_REVIEWED_and_never_pending_review(self):
        """The load-bearing rule this store exists to keep.

        Absence is not a review in progress: a scope with no row has no entry, the project
        word is NOT_REVIEWED, and PENDING_REVIEW -- which claims somebody was asked and owes
        an answer -- is only ever a word a human filed. The facade cannot produce it.
        """
        self.assertEqual(rights_ledger.current_decisions(self.conn, project_id='p1'), {})
        self.assertEqual(rights_ledger.list_decisions(self.conn, project_id='p1'), [])
        self.assertEqual(rights_ledger.filed_scopes(self.conn, project_id='p1'), [])
        view = readback(self.conn, 'p1')
        self.assertEqual(view['rights_clearance'], 'NOT_REVIEWED')
        self.assertEqual(view['decision_count'], 0)
        self.assertEqual(view['filed_scope_count'], 0)
        self.assertEqual(view['approved_scope_count'], 0)
        # 0 of 0 may not read as cleared, and the empty case is distinguishable from a
        # project that has decisions: the counts are published next to the word.
        self.assertEqual(set(CLEARANCE_STATES), {'CLEARED', 'NOT_REVIEWED'})
        self.assertNotIn('PENDING_REVIEW', CLEARANCE_STATES,
                         'the facade has no word that claims a request was made')
        self.assertEqual(view['decision_states']['PENDING_REVIEW'], 0)
        self.assertNotIn('PENDING_REVIEW', json.dumps(view['current_decisions']))

    def test_only_a_human_filed_pending_review_shows_up_as_pending(self):
        self.file(decision_id='rd-pending', decision='PENDING_REVIEW',
                  note='referred to counsel; the licence text is ambiguous')
        current = rights_ledger.current_decisions(self.conn, project_id='p1')
        self.assertEqual(current['commercial-print']['decision'], 'PENDING_REVIEW')
        view = readback(self.conn, 'p1')
        self.assertEqual(view['decision_states']['PENDING_REVIEW'], 1)
        self.assertEqual(view['rights_clearance'], 'NOT_REVIEWED')
        self.assertEqual([row['use_scope'] for row in view['unapproved_scopes']],
                         ['commercial-print'])

    def test_a_denied_decision_leaves_the_scope_visible_and_uncleared(self):
        self.file(decision_id='rd-denied', decision='DENIED',
                  note='the stock image licence forbids redistribution')
        view = readback(self.conn, 'p1')
        self.assertEqual(view['rights_clearance'], 'NOT_REVIEWED')
        self.assertEqual(view['filed_scope_count'], 1)
        self.assertEqual(view['approved_scope_count'], 0)

    def test_an_unknown_project_is_refused_before_anything_is_written(self):
        with self.assertRaises(RightsLedgerError) as refused:
            self.file(project_id='nope')
        self.assertEqual(refused.exception.code, 'RIGHTS_PROJECT_NOT_RECORDED')
        with self.assertRaises(RightsLedgerError) as refused:
            readback(self.conn, 'nope')
        self.assertEqual(refused.exception.code, 'RIGHTS_PROJECT_NOT_RECORDED')

    # ------------------------------------------------------------- append-only history

    def test_a_filed_decision_cannot_be_edited_or_deleted(self):
        self.file()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE rights_decision SET decision='DENIED'"
                              " WHERE decision_id='rd-1'")
        self.conn.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM rights_decision WHERE decision_id='rd-1'")
        self.conn.rollback()
        self.assertEqual(
            rights_ledger.current_decisions(self.conn, project_id='p1')
            ['commercial-print']['decision'], 'APPROVED')
        self.assertEqual(len(rights_ledger.list_decisions(self.conn, project_id='p1')), 1)

    def test_a_correction_is_a_new_decision_that_supersedes_the_old_one(self):
        self.file()
        self.file(decision_id='rd-2', decision='DENIED',
                  note='a second reading found a redistribution clause', supersedes='rd-1')
        current = rights_ledger.current_decisions(self.conn, project_id='p1')
        self.assertEqual(current['commercial-print']['decision_id'], 'rd-2')
        self.assertEqual([row['decision_id'] for row in
                          rights_ledger.list_decisions(self.conn, project_id='p1')],
                         ['rd-1', 'rd-2'], 'withdrawal must not erase the record it replaces')
        view = readback(self.conn, 'p1')
        self.assertEqual(view['rights_clearance'], 'NOT_REVIEWED',
                         'a withdrawn approval cannot keep the project cleared')
        self.assertEqual(view['ever_filed_scopes'], ['commercial-print'])

    def test_one_decision_cannot_be_superseded_twice(self):
        self.file()
        self.file(decision_id='rd-2', supersedes='rd-1')
        with self.assertRaises(RightsLedgerError) as refused:
            self.file(decision_id='rd-3', supersedes='rd-1')
        self.assertEqual(refused.exception.code, 'RIGHTS_ALREADY_SUPERSEDED')

    def test_superseding_requires_a_real_decision_of_this_project(self):
        self.file()
        with self.assertRaises(RightsLedgerError) as refused:
            self.file(decision_id='rd-ghost', supersedes='rd-nope')
        self.assertEqual(refused.exception.code, 'RIGHTS_SUPERSEDES_UNKNOWN')
        self.assertIn('rd-nope', str(refused.exception))
        # Another project's id is not a link either, and an unknown project is refused before
        # anything about the link is even looked at.
        with self.assertRaises(RightsLedgerError) as refused:
            rights_ledger.record(self.conn, project_id='p2',
                                 document=contract_document(decision_id='rd-p2'),
                                 supersedes='rd-1')
        self.assertEqual(refused.exception.code, 'RIGHTS_PROJECT_NOT_RECORDED')

    def test_a_decision_cannot_supersede_a_different_use_scope(self):
        """Otherwise a filing about one scope could hide an unfavourable decision about
        another, and the clearance would count fewer scopes than were ever adjudicated."""
        self.file(decision_id='rd-font', use_scope='font-embedding')
        with self.assertRaises(RightsLedgerError) as refused:
            self.file(decision_id='rd-other', use_scope='commercial-print',
                      supersedes='rd-font')
        self.assertEqual(refused.exception.code, 'RIGHTS_SUPERSEDES_SCOPE_MISMATCH')

    def test_two_live_decisions_for_one_scope_are_published_as_a_conflict(self):
        """`current_decisions` keeps the newest word; that tie-break may not be silent."""
        self.file(decision_id='rd-a', decided_at='2026-10-08T00:00:00Z')
        self.file(decision_id='rd-b', decision='DENIED', decided_at='2026-10-08T01:00:00Z')
        current = rights_ledger.current_decisions(self.conn, project_id='p1')
        self.assertEqual(current['commercial-print']['decision_id'], 'rd-b')
        conflicts = rights_ledger.unlinked_scope_conflicts(self.conn, project_id='p1')
        self.assertEqual([row['use_scope'] for row in conflicts], ['commercial-print'])
        self.assertEqual(conflicts[0]['decision_ids'], ['rd-a', 'rd-b'])
        self.assertEqual(readback(self.conn, 'p1')['scope_conflicts'], conflicts)

    def test_a_stored_row_that_no_longer_satisfies_its_contract_is_reported(self):
        """Re-validation on read is the tamper signal, not a courtesy.

        The triggers make this unreachable in normal operation, so it is reached here the
        way an attacker would: past the module, straight at the file, with the immutability
        guard dropped first. A row that cannot be trusted must not be served as a clearance.
        """
        self.file()
        self.conn.executescript('DROP TRIGGER rights_decision_no_update;'
                                " UPDATE rights_decision SET document_json ="
                                " replace(document_json, '\"APPROVED\"', '\"MAYBE\"')"
                                " WHERE decision_id='rd-1';")
        self.conn.commit()
        with self.assertRaises(RightsLedgerError) as refused:
            rights_ledger.list_decisions(self.conn, project_id='p1')
        self.assertEqual(refused.exception.code, 'RIGHTS_STORED_RECORD_INVALID')
        with self.assertRaises(RightsLedgerError) as refused:
            readback(self.conn, 'p1')
        self.assertEqual(refused.exception.code, 'RIGHTS_STORED_RECORD_INVALID')

    def test_the_declared_vocabulary_is_what_the_emitters_actually_produce(self):
        """The rights words in state-vocabularies.json are checked against their sources.

        A vocabulary block that nothing reads back is the decoration this repo's own gate
        exists to refuse, so the declaration is re-derived here from the facade source and
        the contract file, and the shipped gate is run over the real tree.
        """
        import importlib.util
        import io
        from contextlib import redirect_stdout

        gate_path = REPO / 'design-lab/scripts/verify_state_vocabularies.py'
        spec = importlib.util.spec_from_file_location('vocabulary_gate_for_rights', gate_path)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        clearance, decisions, notes = gate.py_rights()
        self.assertEqual(notes, [], f'the rights emitters could not be read: {notes}')
        contract = json.loads((REPO / 'design-lab/config/state-vocabularies.json')
                              .read_text(encoding='utf-8'))
        self.assertEqual(set(contract['rights']['clearance']), clearance)
        self.assertEqual(set(contract['rights']['decisions']), decisions)
        self.assertEqual(set(CLEARANCE_STATES), clearance)
        self.assertEqual(set(rights_ledger.decision_vocabulary()), decisions)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = gate.main()
        self.assertEqual(code, 0, buffer.getvalue())

    def test_the_readback_publishes_what_no_decision_proves(self):
        view = readback(self.conn, 'p1')
        self.assertTrue(view['does_not_prove'])
        self.assertTrue(any('registry' in line for line in view['does_not_prove']),
                        'the ledger does not read rights-registry.json, and a reader who is '
                        'not told that will assume the 74 subjects were adjudicated')
        self.assertEqual(view['schemaVersion'], 'design-lab/rights-readback/v1')
        self.assertIn('RIGHTS_NOT_HUMAN', rights_ledger.REFUSAL_CODES)

    def test_every_refusal_code_is_documented_and_reachable_from_one_vocabulary(self):
        """An undocumented code is a bug in the store, so it raises AssertionError."""
        with self.assertRaises(AssertionError):
            RightsLedgerError('invented', code='RIGHTS_NOT_IN_THE_LIST')
        self.assertEqual(rights_ledger.REFUSAL_CODES, frozenset({
            'RIGHTS_PROJECT_NOT_RECORDED', 'RIGHTS_DOCUMENT_MALFORMED',
            'RIGHTS_CONTRACT_UNREADABLE', 'RIGHTS_CONTRACT_UNBOUND',
            'RIGHTS_DECISION_INVALID', 'RIGHTS_ACTOR_MISSING', 'RIGHTS_NOT_HUMAN',
            'RIGHTS_TIMESTAMP_INVALID', 'RIGHTS_SUPERSEDES_UNKNOWN',
            'RIGHTS_ALREADY_SUPERSEDED', 'RIGHTS_SUPERSEDES_SCOPE_MISMATCH',
            'RIGHTS_DECISION_ID_TAKEN', 'RIGHTS_DATABASE_REFUSED',
            'RIGHTS_STORED_RECORD_INVALID'}))


if __name__ == '__main__':
    unittest.main()
