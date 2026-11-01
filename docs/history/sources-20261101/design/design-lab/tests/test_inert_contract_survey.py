# SPDX-License-Identifier: MIT
"""The INERT contract survey must be computed, falsifiable, and pinned to the ledger.

`design-lab/scripts/inert_contract_survey.py` turns thirty prose claims into a table an owner can
decide from. That only helps if the table cannot drift from the repository it describes, so these
tests check the survey against the ledger in both directions, re-derive every classification from
the sources it names, and prove the checks fail when the facts they read are planted.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'design-lab/scripts/inert_contract_survey.py'
DOC = ROOT / 'docs/audits/INERT-CONTRACT-SURVEY-2026-10-08.md'
LEDGER = ROOT / 'design-lab/config/contract-bindings.json'

spec = importlib.util.spec_from_file_location('inert_contract_survey', SCRIPT)
survey = importlib.util.module_from_spec(spec)
sys.modules['inert_contract_survey'] = survey
spec.loader.exec_module(survey)


def ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding='utf-8'))


def document() -> dict:
    return json.loads(re.search(r'```json\n(.*?)\n```', DOC.read_text(encoding='utf-8'), re.S).group(1))


class LedgerPinning(unittest.TestCase):
    def test_the_survey_covers_exactly_the_inert_rows(self):
        doc = document()
        inert = sorted(Path(row['schema']).name
                       for row in ledger()['contracts'] if row.get('status') == 'INERT')
        surveyed = sorted(Path(row['schema']).name for row in doc['rows'])
        self.assertEqual(inert, surveyed,
                         'a new INERT row that nobody surveyed, or a surveyed row that stopped being '
                         'INERT, is a decision that silently disappears from the sheet')
        self.assertEqual(doc['inertRows'], len(inert))
        self.assertEqual(sum(doc['stateCounts'].values()), len(inert),
                         'the state counts must add up to the rows, not to a number kept by hand')

    def test_no_binding_row_leaks_into_the_survey(self):
        binding = {row['schema'] for row in ledger()['contracts'] if row.get('status') == 'BINDING'}
        self.assertTrue(binding, 'the ledger has no BINDING rows at all; this check is vacuous')
        self.assertEqual([], [row for row in document()['rows'] if row['schema'] in binding])

    def test_the_committed_document_is_what_the_code_computes(self):
        computed = survey.render(survey.build())
        self.assertEqual(computed, DOC.read_text(encoding='utf-8'),
                         'the sheet drifted from the repository it describes; re-run the survey')

    def test_a_single_changed_number_in_the_document_is_stale(self):
        """Control for the assertion above: it fails when the bytes disagree, and says so."""
        text = DOC.read_text(encoding='utf-8')
        tampered = text.replace('"inertRows": 30', '"inertRows": 29', 1)
        self.assertNotEqual(text, tampered, 'the fixture no longer contains the field it tampers with')
        block = json.loads(re.search(r'```json\n(.*?)\n```', tampered, re.S).group(1))
        self.assertNotEqual(block['inertRows'], survey.build()['inertRows'])


class ClassificationIsNotFabricated(unittest.TestCase):
    def setUp(self):
        self.tables = survey.sql_tables()
        self.corpus = survey.product_corpus(ROOT)
        self.writers, self.readers = survey.table_users(self.corpus)

    def row_for(self, schema_rel: str) -> dict:
        return next(row for row in ledger()['contracts'] if row['schema'] == schema_rel)

    def test_every_claimed_column_really_is_a_column_of_the_named_table(self):
        for entry in document()['rows']:
            if not entry['best_table']:
                self.assertEqual([], entry['matched_fields'])
                self.assertEqual(0.0, entry['overlap'])
                continue
            columns = self.tables[entry['best_table']]
            for field in entry['matched_fields']:
                self.assertIn(field, columns,
                              f"{entry['schema']} claims {field} is a column of "
                              f"{entry['best_table']}, and the SQL says it is not")

    def test_overlap_is_the_reported_fraction_of_the_reported_fields(self):
        for entry in document()['rows']:
            if not entry['fields']:
                continue
            expected = round(len(entry['matched_fields']) / entry['fields'], 3)
            self.assertEqual(expected, entry['overlap'], entry['schema'])

    def test_a_reported_writer_really_holds_a_write_statement_for_that_table(self):
        checked = 0
        for entry in document()['rows']:
            for rel in entry['table_writers']:
                text = self.corpus[rel]
                pattern = re.compile(rf'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+{entry["best_table"]}\b',
                                     re.I)
                self.assertTrue(pattern.search(text),
                                f'{rel} is reported as writing {entry["best_table"]} and does not')
                checked += 1
        self.assertGreater(checked, 5, 'almost no writer evidence was checked at all')

    def test_a_table_being_written_is_what_makes_it_a_duplicate_claim(self):
        """The classification is a function of the evidence, so changing it changes the verdict."""
        target = self.row_for('design-lab/schemas/contracts/operation-intent.schema.json')
        entry = survey.classify(target, self.tables, self.writers, self.readers, self.corpus,
                                ledger())
        self.assertEqual('TABLE_WRITES_THIS_ACTIVITY', entry['state'])
        self.assertGreaterEqual(entry['overlap'], survey.OVERLAP_FLOOR)
        nobody = {name: [] for name in self.writers}
        quiet = survey.classify(target, self.tables, nobody, self.readers, self.corpus, ledger())
        self.assertEqual('TABLE_EXISTS_UNWRITTEN', quiet['state'],
                         'with the writers erased it must stop claiming somebody implements this')

    def test_overlap_is_exactly_the_reported_fraction(self):
        row = self.row_for('design-lab/schemas/contracts/run-event.schema.json')
        declared = survey.schema_fields(ROOT / row['schema'])
        book = ledger()
        for width in (1, 2, 3):
            probe = {'probe_table': declared[:width]}
            entry = survey.classify(row, probe, {}, {}, self.corpus, book)
            self.assertEqual(round(width / entry['fields'], 3), entry['overlap'], entry)
            self.assertEqual([], entry['table_writers'])

    def test_a_wide_schema_is_not_called_a_duplicate_by_one_shared_column(self):
        row = self.row_for('design-lab/schemas/contracts/run-event.schema.json')
        declared = survey.schema_fields(ROOT / row['schema'])
        self.assertGreaterEqual(len(declared), 4,
                                'the fixture needs a schema wide enough to prove the floor bites')
        entry = survey.classify(row, {'probe_table': declared[:1]}, {}, {},
                                self.corpus, ledger())
        self.assertLess(entry['overlap'], survey.OVERLAP_FLOOR)
        self.assertEqual('NO_STATE_COUNTERPART', entry['state'])

    def test_a_narrow_schema_flags_its_single_column_match_as_thin(self):
        """Two-property schemas reach a one-third floor on ONE shared column. The sheet has to say
        so rather than let the classification word carry more weight than the evidence."""
        row = self.row_for('design-lab/schemas/contracts/retry-policy.schema.json')
        declared = survey.schema_fields(ROOT / row['schema'])
        self.assertLessEqual(len(declared), 3)
        entry = survey.classify(row, {'probe_table': declared[:1]}, {}, {},
                                self.corpus, ledger())
        self.assertGreaterEqual(entry['overlap'], survey.OVERLAP_FLOOR)
        self.assertTrue(entry['thin_match'], 'a one-column match on a narrow schema must be marked')


class RetireCoherence(unittest.TestCase):
    def test_a_route_that_claims_an_inert_schema_makes_retirement_incoherent(self):
        """The flag is only worth reading if planting a reference flips it."""
        tables, corpus = survey.sql_tables(), survey.product_corpus(ROOT)
        writers, readers = survey.table_users(corpus)
        pristine = ledger()
        original = next(row for row in pristine['contracts'] if row.get('status') == 'INERT')
        before = survey.classify(original, tables, writers, readers, corpus, pristine)
        self.assertTrue(before['retire_coherent'], 'the fixture row has to start coherent')
        mutated = copy.deepcopy(pristine)
        target = next(row for row in mutated['contracts'] if row['schema'] == original['schema'])
        mutated['routes'].append({'route': '/api/probe', 'method': 'GET', 'kind': 'BOUND_SCHEMA',
                                  'handler': 'probe', 'schema': target['schema'],
                                  'version': target['version'],
                                  'emitter': 'src/design_lab/http_service.py:1', 'reason': 'probe'})
        after = survey.classify(target, tables, writers, readers, corpus, mutated)
        self.assertFalse(after['retire_coherent'])
        self.assertEqual(['/api/probe'], after['route_references'])

    def test_a_schema_declared_twice_in_the_ledger_is_not_retirable_in_one_move(self):
        tables, corpus = survey.sql_tables(), survey.product_corpus(ROOT)
        writers, readers = survey.table_users(corpus)
        book = ledger()
        first = next(row for row in book['contracts'] if row.get('status') == 'INERT')
        book['contracts'].append(dict(first))
        entry = survey.classify(first, tables, writers, readers, corpus, book)
        self.assertFalse(entry['retire_coherent'],
                         'two rows naming one contract: retiring one leaves a claim pointing at a '
                         'file that is gone')

    def test_a_missing_schema_file_is_reported_not_silently_retirable(self):
        tables, corpus = survey.sql_tables(), survey.product_corpus(ROOT)
        writers, readers = survey.table_users(corpus)
        book = ledger()
        target = next(row for row in book['contracts'] if row.get('status') == 'INERT')
        ghost = dict(target, schema='design-lab/schemas/contracts/not-a-real-contract.schema.json')
        entry = survey.classify(ghost, tables, writers, readers, corpus, book)
        self.assertEqual('SCHEMA_FILE_ABSENT', entry['state'],
                         'a ledger row whose file is gone is a finding, not a traceback')
        self.assertFalse(entry['retire_coherent'])
        self.assertEqual([], entry['matched_fields'])

    def test_the_real_sheet_reports_its_own_coherence_count(self):
        doc = document()
        coherent = [row['schema'] for row in doc['rows'] if row['retire_coherent']]
        self.assertEqual(len(doc['rows']), len(coherent),
                         'some INERT row is now referenced elsewhere; the sheet has to say which')


class ToolHygiene(unittest.TestCase):
    def test_the_document_is_utf8_and_has_no_placeholder_left(self):
        raw = DOC.read_bytes()
        self.assertNotIn(b'{json_block}', raw)
        self.assertNotIn(b'{table_rows}', raw)
        text = raw.decode('utf-8')
        self.assertIn('INERT 合同普查', text)
        self.assertLess(text.count('\ufffd'), 1)

    def test_check_passes_on_the_committed_sheet_and_names_a_stale_one(self):
        self.assertEqual(0, survey.main(['--check']))
        scratch = Path(tempfile.mkdtemp(dir=ROOT / '.project-local/task-runtime'))
        try:
            moved = scratch / 'survey-copy.md'
            original = DOC.read_text(encoding='utf-8')
            committed = json.loads(re.search(r'```json\n(.*?)\n```', original, re.S).group(1))
            current = committed['stateCounts']['NO_STATE_COUNTERPART']
            # Derived from the sheet, not pinned: the control has to bite the counts this
            # document actually carries, or a regenerated sheet silently disarms it.
            tampered = original.replace(f'"NO_STATE_COUNTERPART": {current}',
                                         f'"NO_STATE_COUNTERPART": {current - 1}')
            self.assertNotEqual(original, tampered, 'the control no longer bites the sheet')
            moved.write_text(tampered, encoding='utf-8')
            stale = json.loads(re.search(r'```json\n(.*?)\n```',
                                         moved.read_text(encoding='utf-8'), re.S).group(1))
            self.assertNotEqual(stale['stateCounts'], survey.build()['stateCounts'])
        finally:
            import shutil
            shutil.rmtree(scratch, ignore_errors=True)

    def test_sql_parsing_covers_the_state_directory_it_claims(self):
        tables = survey.sql_tables()
        self.assertGreaterEqual(len(tables), 12)
        for name in ('operation_intent', 'attempt_state', 'jury_record', 'rights_decision'):
            self.assertIn(name, tables, f'{name} is a real state table and the parser lost it')
            self.assertTrue(tables[name], f'{name} parsed with no columns')


if __name__ == '__main__':
    unittest.main()
