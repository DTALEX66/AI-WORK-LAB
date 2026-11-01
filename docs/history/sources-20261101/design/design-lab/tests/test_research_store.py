# SPDX-License-Identifier: MIT
"""The research-finding store: what may be filed, and what cannot be rewritten.

``design-lab/schemas/research-finding.schema.json`` had been declarable-for-years inert:
``verify_design_kernel.py`` proved only that the FILE exists and
``test_oda4_0204_object_model.py`` proved only the object's id and that its ``schemaRef``
starts with ``schemas/``. No document had ever been validated against it. Every case below
goes through the real append-only store on a real state database, because the properties that
matter are the ones a JSON Schema cannot express: a claim with no source is refused in its
spirit and not in its arithmetic, history cannot be edited, a chain cannot reach into another
project, and an author is never assumed.

Three guards are tested against BOTH sides rather than asserted from a copy: the field list,
the required trio and the confidence enum are read out of the schema file; the table's CHECK
lists are read out of ``design-lab-state-research-v1.sql``; and the declared actor kinds are
read out of ``assurance/human_jury.py``. A restatement that drifts from its source is the
second-authority failure these tests exist to catch.
"""
from __future__ import annotations

import io
import json
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(REPO / 'src'))

from design_lab.assurance import human_jury, research_store                   # noqa: E402
from design_lab.assurance.research_store import ResearchStoreError           # noqa: E402
from design_lab.research_review import readback                              # noqa: E402
from design_lab.runtime.state_resources import state_schema                  # noqa: E402

SCHEMA_FILE = REPO / 'design-lab/schemas/research-finding.schema.json'
STATE_SQL = state_schema('design-lab-state-research-v1.sql')

#: The columns a raw INSERT may set. Written out here because the point of the raw-INSERT
#: cases is to be past the module, and a column list copied from a docstring would test
#: nothing -- it is compared against the shipped schema below.
RAW_COLUMNS = ('finding_id', 'project_id', 'claim', 'confidence', 'source_refs_json',
               'source_ref_count', 'not_design_rule', 'recorded_by', 'actor_kind',
               'document_json')
RAW_INSERT = ('INSERT INTO research_finding (' + ', '.join(RAW_COLUMNS) + ') VALUES ('
              + ', '.join(['?'] * len(RAW_COLUMNS)) + ')')


def finding(finding_id='rf-1', **overrides) -> dict:
    """One complete finding, as a caller who actually looked at something would file it."""
    document = {
        'finding_id': finding_id,
        'claim': 'every competitor puts the price under the fold, so the comparison never '
                 'happens',
        'sourceRefs': ['interview-07', 'bench-competitor-2026-05'],
        'confidence': 'medium',
        'notDesignRule': True,
    }
    document.update(overrides)
    return document


class ResearchStoreTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.db = self.base / 'state.db'
        self.conn = research_store.connect(self.db)
        self.conn.execute('INSERT INTO project VALUES ("p1","Research Probe",'
                          '"2026-10-08T00:00:00Z")')
        self.conn.execute('INSERT INTO project VALUES ("p2","Other Probe",'
                          '"2026-10-08T00:00:00Z")')
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def file(self, *, project_id='p1', recorded_by='dtalex66', actor_kind='HUMAN',
             supersedes=None, **overrides) -> dict:
        return research_store.record(self.conn, project_id=project_id,
                                     document=finding(**overrides), recorded_by=recorded_by,
                                     actor_kind=actor_kind, supersedes=supersedes)

    def refuse(self, call, code) -> ResearchStoreError:
        """Assert the refusal, and assert nothing was written while it was being refused."""
        before = len(research_store.list_findings(self.conn, project_id='p1'))
        with self.assertRaises(ResearchStoreError) as refused:
            call()
        self.assertEqual(refused.exception.code, code, str(refused.exception))
        self.assertEqual(len(research_store.list_findings(self.conn, project_id='p1')), before,
                         'a refused filing must leave no row behind')
        return refused.exception

    # ------------------------------------------------------------- one authority

    def test_the_field_list_and_the_enum_are_loaded_from_the_contract(self):
        """This module states no second copy of either, so the schema file IS the check."""
        declared = json.loads(SCHEMA_FILE.read_text(encoding='utf-8'))
        self.assertEqual(set(research_store.field_names()), set(declared['properties']))
        self.assertEqual(set(research_store.required_field_names()), set(declared['required']))
        self.assertEqual(set(research_store.confidence_vocabulary()),
                         set(declared['properties']['confidence']['enum']))
        self.assertIs(declared['additionalProperties'], False,
                      'a non-closed contract would let a submission smuggle fields through')
        # The contract declares no schemaVersion, which is why this store compares `$id` and
        # why a finding carrying the field the other assurance contracts use is refused.
        self.assertNotIn('schemaVersion', declared['properties'])
        self.assertEqual(declared['$id'], research_store.CONTRACT_ID)

    def test_the_source_field_is_found_by_structure_not_by_name(self):
        """The "no source is a guess" rule has to survive the contract renaming its field."""
        self.assertEqual(research_store.source_ref_field(), 'sourceRefs')
        shifted = json.loads(SCHEMA_FILE.read_text(encoding='utf-8'))
        shifted['required'] = ['finding_id', 'claim', 'sources']
        shifted['properties']['sources'] = shifted['properties'].pop('sourceRefs')
        path = self.base / 'renamed.schema.json'
        path.write_text(json.dumps(shifted), encoding='utf-8')
        saved, cache = research_store.CONTRACT_PATH, research_store.contract
        try:
            from functools import lru_cache
            research_store.CONTRACT_PATH = path
            research_store.contract = lru_cache(maxsize=1)(lambda: json.loads(
                path.read_text(encoding='utf-8')))
            self.assertEqual(research_store.source_ref_field(), 'sources')
        finally:
            research_store.CONTRACT_PATH = saved
            research_store.contract = cache
        self.assertEqual(research_store.source_ref_field(), 'sourceRefs')

    def test_the_table_check_lists_are_their_own_sources(self):
        """Two CHECK lists in the SQL restate vocabularies that live elsewhere; both are
        reconciled here, because a restatement with no reconciliation is how a second
        authority gets born."""
        sql = STATE_SQL.read_text(encoding='utf-8')
        confidence = re.search(r'confidence TEXT\s+CHECK \(confidence IN \((.*?)\)', sql, re.S)
        self.assertIsNotNone(confidence, 'the confidence CHECK list is gone from the schema')
        self.assertEqual(set(re.findall(r"'([a-z_]+)'", confidence.group(1))),
                         set(research_store.confidence_vocabulary()),
                         'the table and the contract disagree about what a confidence can be')
        kinds = re.search(r'actor_kind TEXT CHECK \(actor_kind IS NULL OR actor_kind IN'
                          r'\s*\((.*?)\)\)', sql, re.S)
        self.assertIsNotNone(kinds, 'the actor_kind CHECK list is gone from the schema')
        self.assertEqual(set(re.findall(r"'([A-Z_]+)'", kinds.group(1))),
                         set(human_jury.HUMAN_JUROR_KINDS) | set(human_jury.AGENT_ACTOR_KINDS),
                         'the table may name an actor this repository does not recognise')
        columns = re.search(r'CREATE TABLE IF NOT EXISTS research_finding \((.*?)\n\);', sql,
                            re.S).group(1)
        table_columns = set(re.findall(r'^\s{2}(\w+) ', columns, re.M))
        # `supersedes` is the one column these raw INSERTs never set: a hand-written supersede
        # link would test the chain rules through a door the module owns, and those rules are
        # tested where they live. Everything else the table has must be settable here, or the
        # database-level cases above are writing a different row than the one they name.
        self.assertEqual(table_columns - {'supersedes'}, set(RAW_COLUMNS),
                         'the raw-INSERT column list no longer matches the shipped table')
        self.assertIn('supersedes', table_columns)

    # ------------------------------------------------------------- the happy path

    def test_a_finding_is_filed_and_survives_reopening_the_database(self):
        stored = self.file()
        self.assertEqual(stored['finding_id'], 'rf-1')
        with closing(sqlite3.connect(self.db)) as reopened:
            reopened.row_factory = sqlite3.Row
            findings = research_store.list_findings(reopened, project_id='p1')
            view = readback(reopened, 'p1')
        self.assertEqual([row['finding_id'] for row in findings], ['rf-1'])
        self.assertEqual(view['finding_count'], 1)
        self.assertEqual(list(view['current_findings']), ['rf-1'])
        self.assertEqual(view['sourced_finding_count'], 1)
        self.assertEqual(view['source_ref_total'], 2)
        self.assertEqual(view['confidence_counts']['medium'], 1)
        self.assertEqual(view['confidence_counts']['high'], 0,
                         'a declared category may not go absent just because it is empty')

    def test_the_stored_document_is_the_validated_one_not_the_request(self):
        self.file()
        row = self.conn.execute('SELECT document_json FROM research_finding').fetchone()
        stored = json.loads(row['document_json'])
        self.assertEqual(set(stored) & {'project_id', 'supersedes', 'recorded_by',
                                        'actor_kind', 'schemaVersion'}, set())
        self.assertEqual(stored['confidence'], 'medium')

    def test_an_optional_field_left_out_stays_left_out(self):
        document = finding(confidence=None)
        document.pop('confidence')
        document.pop('notDesignRule')
        stored = research_store.record(self.conn, project_id='p1', document=document,
                                       recorded_by='dtalex66', actor_kind='HUMAN')
        self.assertEqual(set(stored), set(research_store.required_field_names()))
        view = readback(self.conn, 'p1')
        # Absence is reported as absence, never filled in: an unstated confidence is not
        # `low`, and a finding that never disclaimed being a rule is not a disclaimed one.
        self.assertEqual(view['stated_confidence_count'], 0)
        self.assertEqual(view['undeclared_disclaimer'], ['rf-1'])

    def test_a_human_name_that_merely_contains_ai_is_not_refused(self):
        """The positive control: a name check that refused everything would look safest and
        would make the surface unusable, so it has to pass an ordinary human name."""
        stored = self.file(finding_id='rf-daniel', recorded_by='Daniel Aoki')
        self.assertEqual(stored['finding_id'], 'rf-daniel')

    # ------------------------------------------------------------- a source or nothing

    def test_an_empty_source_list_is_refused_as_no_source(self):
        exc = self.refuse(lambda: self.file(finding_id='rf-none', sourceRefs=[]),
                          'RESEARCH_SOURCE_REFS_EMPTY')
        self.assertIn('guess', str(exc))

    def test_a_whitespace_only_source_list_is_refused_though_minitems_passes_it(self):
        """The whole reason the store re-reads the list: `[" "]` satisfies minItems: 1."""
        for value in (['   '], [''], [' ', '\t', '\n'], ['']):
            with self.subTest(value=value):
                self.refuse(lambda: self.file(finding_id='rf-blank', sourceRefs=value),
                            'RESEARCH_SOURCE_REFS_EMPTY')

    def test_a_blank_entry_among_real_ones_is_refused_as_not_a_source(self):
        exc = self.refuse(lambda: self.file(finding_id='rf-half', sourceRefs=['interview-07',
                                                                            '   ']),
                          'RESEARCH_SOURCE_REF_INVALID')
        self.assertIn('blank', str(exc).lower())

    def test_the_same_source_listed_twice_is_refused(self):
        """Otherwise a finding's apparent weight is an artefact of a copy-paste."""
        exc = self.refuse(lambda: self.file(finding_id='rf-twice',
                                            sourceRefs=['bench-x', 'bench-x', ' bench-x ']),
                          'RESEARCH_SOURCE_REF_INVALID')
        self.assertIn('bench-x', str(exc))

    def test_a_source_ref_that_is_not_a_string_is_the_contract_s_refusal(self):
        self.refuse(lambda: self.file(finding_id='rf-types', sourceRefs=[{'a': 1}]),
                    'RESEARCH_FINDING_INVALID')

    def test_the_database_refuses_a_sourceless_row_written_past_the_module(self):
        """The CHECK is the last line, so it must hold for a writer nobody reviewed.

        Written as a raw INSERT because that is the case worth proving: a change above this
        module, or a hand-edited file, still cannot store a guess.
        """
        for values in (  # (source_refs_json, source_ref_count, claim, not_design_rule, kind)
            ('[]', 0, 'a guess', None, None),
            ('["   "]', 0, 'a guess', None, None),
            ('["interview-07"]', 0, 'real', None, None),
            ('["interview-07"]', 1, '   ', None, None),
            ('["interview-07"]', 1, 'real', 0, None),
            ('["interview-07"]', 1, 'real', None, 'ORACLE'),
        ):
            with self.subTest(values=values):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.conn.execute(RAW_INSERT, ('rf-raw', 'p1', values[2], None, values[0],
                                                   values[1], values[3], 'dtalex66', values[4],
                                                   '{}'))
                self.conn.rollback()
        # And the shape a real row has is accepted: one real source, no disclaimer stated,
        # no declared kind (name-checked history), and a machine declared as the author.
        for finding_id, kind in (('rf-raw-ok', None), ('rf-raw-agent', 'AGENT'),
                                 ('rf-raw-human', 'HUMAN')):
            self.conn.execute(RAW_INSERT, (finding_id, 'p1', 'real', None, '["interview-07"]',
                                           1, 1, 'someone', kind,
                                           json.dumps({'finding_id': finding_id,
                                                       'claim': 'real',
                                                       'sourceRefs': ['interview-07']})))
        self.conn.commit()
        self.assertEqual(self.conn.execute(
            'SELECT COUNT(*) FROM research_finding').fetchone()[0], 3)

    # ------------------------------------------------------------- who authored it

    def test_a_human_kind_signed_by_an_automation_name_is_refused_by_name(self):
        for actor in ('review-agent', 'codex', 'qoder-agent', 'MODEL', 'design-lab-pipeline',
                      'OpenAI-GPT-4', 'AI'):
            with self.subTest(actor=actor):
                exc = self.refuse(lambda: self.file(finding_id=f'rf-{actor}',
                                                    recorded_by=actor, actor_kind='HUMAN'),
                                  'RESEARCH_NOT_HUMAN')
                self.assertIn(actor, str(exc), 'the refusal has to name the actor it refused')

    def test_an_agent_may_record_a_finding_and_is_stored_as_what_it_is(self):
        """This is the difference from a human gate, and it has to be a recorded fact.

        AGENTS.md puts no human approval at a working finding, so refusing an agent here
        would only hide who said it. What is refused is the *claim* of human authorship, and
        what is stored is the kind -- so a reader can tell the three cases apart.
        """
        self.file(finding_id='rf-bot', recorded_by='qoder-agent', actor_kind='AGENT')
        view = readback(self.conn, 'p1')
        self.assertEqual(view['actor_kinds'], {'rf-bot': 'AGENT'})
        self.assertEqual(view['unattributed_findings'], [])

    def test_a_declared_kind_in_neither_vocabulary_is_refused(self):
        for kind in ('ORACLE', 'HUMANISH', 'huma', ''):
            with self.subTest(kind=kind):
                self.refuse(lambda: self.file(finding_id=f'rf-kind-{kind}', actor_kind=kind),
                            'RESEARCH_ACTOR_KIND_UNKNOWN' if kind.strip()
                            else 'RESEARCH_ACTOR_MISSING')

    def test_a_kind_declared_with_no_name_is_refused(self):
        """A kind nobody is attributed to establishes nothing, and must not read as authorship."""
        self.refuse(lambda: self.file(finding_id='rf-orphan', recorded_by=None,
                                      actor_kind='HUMAN'), 'RESEARCH_ACTOR_MISSING')

    def test_nothing_stated_about_the_author_is_reported_as_nothing_stated(self):
        self.file(finding_id='rf-blind', recorded_by=None, actor_kind=None)
        view = readback(self.conn, 'p1')
        self.assertEqual(view['unattributed_findings'], ['rf-blind'])
        self.assertEqual(view['actor_kinds'], {'rf-blind': None})

    def test_a_blank_author_name_is_refused_rather_than_assumed(self):
        self.refuse(lambda: self.file(finding_id='rf-nobody', recorded_by='   ',
                                      actor_kind='HUMAN'), 'RESEARCH_ACTOR_MISSING')

    # ------------------------------------------------------------- the contract's teeth

    def test_a_field_the_closed_contract_does_not_declare_is_refused(self):
        smuggled = finding(finding_id='rf-extra')
        smuggled['expires_at'] = '2027-01-01'
        self.refuse(lambda: research_store.record(self.conn, project_id='p1',
                                                  document=smuggled),
                    'RESEARCH_FINDING_INVALID')

    def test_a_schema_version_smuggled_into_a_finding_is_named_not_guessed(self):
        """Callers of the rights and jury routes send `schemaVersion` by habit. This contract
        declares none, and the refusal has to say which field and where it belongs."""
        exc = self.refuse(lambda: self.file(finding_id='rf-version',
                                            schemaVersion='design-lab/research-finding/v1'),
                          'RESEARCH_FINDING_INVALID')
        self.assertIn('schemaVersion', str(exc))
        # Not merely the name -- jsonschema would also name an unexpected property, so the
        # claim being tested is that the caller is told THIS field belongs to another
        # contract, which is the thing they can act on.
        self.assertIn('contract', str(exc).lower())

    def test_a_column_field_cannot_be_smuggled_through_the_document(self):
        """`supersedes`/`recorded_by`/`actor_kind`/`project_id` are columns. A writer that
        could set them inside the document could re-point a stored finding's chain from its
        own bytes, so the closed contract has to refuse the attempt by name."""
        for name in ('supersedes', 'recorded_by', 'actor_kind', 'project_id'):
            with self.subTest(field=name):
                document = finding(finding_id=f'rf-{name}')
                document[name] = 'rf-1'
                exc = self.refuse(
                    lambda document=document: research_store.record(self.conn, project_id='p1',
                                                                    document=document),
                    'RESEARCH_FINDING_INVALID')
                self.assertIn(name, str(exc))
                # The reason, not just the name: an "additional properties" complaint from the
                # validator would name the field too, and would leave the caller guessing
                # whether the contract rejects the word or the store keeps it for itself.
                self.assertIn('column', str(exc).lower())

    def test_a_missing_required_field_is_refused(self):
        for name in sorted(research_store.required_field_names()):
            with self.subTest(field=name):
                document = finding(finding_id=f'rf-no-{name}')
                document.pop(name)
                with self.assertRaises(ResearchStoreError) as refused:
                    research_store.record(self.conn, project_id='p1', document=document)
                self.assertEqual(refused.exception.code, 'RESEARCH_FINDING_INVALID')

    def test_a_whitespace_claim_is_refused_though_minLength_passes_it(self):
        """`minLength: 1` accepts a single space, and a blank claim would be permanent
        append-only history nobody can read."""
        for value in ('   ', ''):
            with self.subTest(value=value):
                self.refuse(lambda: self.file(finding_id='rf-void', claim=value),
                            'RESEARCH_FINDING_INVALID')

    def test_a_confidence_word_the_contract_does_not_allow_is_refused(self):
        for word in ('certain', 'MEDIUM', 'definitely', ''):
            with self.subTest(word=word):
                self.refuse(lambda: self.file(finding_id=f'rf-c-{word}', confidence=word),
                            'RESEARCH_FINDING_INVALID')

    def test_a_finding_that_claims_to_be_a_design_rule_is_refused(self):
        """`notDesignRule` is `const: true`: 研究结论不能直接冒充设计规则. Saying `false` is
        the claim that it may, which no document gets to make here."""
        for value in (False, 'true', 1):
            with self.subTest(value=value):
                self.refuse(lambda: self.file(finding_id=f'rf-rule-{value}',
                                              notDesignRule=value),
                            'RESEARCH_FINDING_INVALID')

    def test_a_non_object_document_is_refused_before_anything_else(self):
        for value in ([], 'claim', None, 7):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ResearchStoreError) as refused:
                    research_store.record(self.conn, project_id='p1', document=value)
                self.assertEqual(refused.exception.code, 'RESEARCH_DOCUMENT_MALFORMED')

    def test_a_contract_that_no_longer_binds_this_identity_is_refused(self):
        """One-sided identity moves are the failure this store was written against."""
        shifted = json.loads(json.dumps(research_store.contract()))
        shifted['$id'] = 'https://dtalex66.local/schemas/something-else.json'
        path = self.base / 'shifted.schema.json'
        path.write_text(json.dumps(shifted), encoding='utf-8')
        saved = research_store.CONTRACT_PATH
        try:
            research_store.CONTRACT_PATH = path
            research_store.contract.cache_clear()
            with self.assertRaises(ResearchStoreError) as refused:
                research_store.field_names()
            self.assertEqual(refused.exception.code, 'RESEARCH_CONTRACT_UNBOUND')
            self.assertIn('something-else.json', str(refused.exception))
        finally:
            research_store.CONTRACT_PATH = saved
            research_store.contract.cache_clear()
        self.assertEqual(research_store.CONTRACT_ID,
                         research_store.contract()['$id'])

    def test_a_contract_that_stopped_closing_its_properties_is_refused(self):
        """`additionalProperties: false` is what makes the route's key set mean anything."""
        opened = json.loads(json.dumps(research_store.contract()))
        opened['additionalProperties'] = True
        path = self.base / 'opened.schema.json'
        path.write_text(json.dumps(opened), encoding='utf-8')
        saved = research_store.CONTRACT_PATH
        try:
            research_store.CONTRACT_PATH = path
            research_store.contract.cache_clear()
            with self.assertRaises(ResearchStoreError) as refused:
                research_store.field_names()
            self.assertEqual(refused.exception.code, 'RESEARCH_CONTRACT_UNBOUND')
        finally:
            research_store.CONTRACT_PATH = saved
            research_store.contract.cache_clear()
        self.assertIs(research_store.contract()['additionalProperties'], False)

    # ------------------------------------------------------------- absence

    def test_a_project_nobody_recorded_for_reads_zero_and_invents_no_verdict(self):
        """The load-bearing rule: a count of findings is not a completion state."""
        self.assertEqual(research_store.current_findings(self.conn, project_id='p1'), {})
        self.assertEqual(research_store.list_findings(self.conn, project_id='p1'), [])
        view = readback(self.conn, 'p1')
        self.assertEqual(view['finding_count'], 0)
        self.assertEqual(view['sourced_finding_count'], 0)
        self.assertEqual(view['unsourced_finding_count'], 0)
        self.assertIsNone(view['research_verdict'])
        self.assertFalse(view['proves_design_quality'])
        self.assertFalse(view['is_knowledge_export'])
        self.assertTrue(view['research_verdict_note'])
        serialized = json.dumps(view)
        for word in ('CLEARED', 'RESEARCH_COMPLETE', 'PENDING_REVIEW', 'ACCEPTED',
                     'NOT_REVIEWED'):
            self.assertNotIn(word, serialized,
                             f'the read-back emits {word!r}, which is a gate word this '
                             'surface has no business producing')

    def test_an_unknown_project_is_refused_before_anything_is_written(self):
        with self.assertRaises(ResearchStoreError) as refused:
            self.file(project_id='nope')
        self.assertEqual(refused.exception.code, 'RESEARCH_PROJECT_NOT_RECORDED')
        with self.assertRaises(ResearchStoreError) as refused:
            readback(self.conn, 'nope')
        self.assertEqual(refused.exception.code, 'RESEARCH_PROJECT_NOT_RECORDED')
        self.assertEqual(self.conn.execute(
            'SELECT COUNT(*) FROM research_finding').fetchone()[0], 0)

    # ------------------------------------------------------------- append-only history

    def test_a_filed_finding_cannot_be_edited_or_deleted(self):
        self.file()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE research_finding SET claim='rewritten' WHERE"
                              " finding_id='rf-1'")
        self.conn.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute('DELETE FROM research_finding WHERE finding_id=rf-1'.replace(
                'rf-1', "'rf-1'"))
        self.conn.rollback()
        self.assertEqual(len(research_store.list_findings(self.conn, project_id='p1')), 1)
        self.assertEqual(research_store.current_findings(self.conn, project_id='p1')
                         ['rf-1']['claim'][:5], 'every')

    def test_a_correction_is_a_new_finding_that_supersedes_the_old_one(self):
        self.file()
        self.file(finding_id='rf-2', claim='a second interview reversed it',
                  sourceRefs=['interview-09'], supersedes='rf-1')
        current = research_store.current_findings(self.conn, project_id='p1')
        self.assertEqual(list(current), ['rf-2'])
        self.assertEqual([row['finding_id'] for row in
                          research_store.list_findings(self.conn, project_id='p1')],
                         ['rf-1', 'rf-2'], 'correcting a finding must not erase the record')
        view = readback(self.conn, 'p1')
        self.assertEqual((view['finding_count'], view['current_finding_count'],
                          view['superseded_finding_count']), (2, 1, 1))

    def test_one_finding_cannot_be_superseded_twice(self):
        self.file()
        self.file(finding_id='rf-2', supersedes='rf-1')
        self.refuse(lambda: self.file(finding_id='rf-3', supersedes='rf-1'),
                    'RESEARCH_ALREADY_SUPERSEDED')

    def test_a_finding_cannot_supersede_itself(self):
        self.refuse(lambda: self.file(finding_id='rf-self', supersedes='rf-self'),
                    'RESEARCH_SUPERSEDES_UNKNOWN')

    def test_superseding_requires_a_finding_of_this_project(self):
        self.file()
        exc = self.refuse(lambda: self.file(finding_id='rf-ghost', supersedes='rf-nope'),
                          'RESEARCH_SUPERSEDES_UNKNOWN')
        self.assertIn('rf-nope', str(exc))

    def test_a_supersede_may_not_reach_into_another_project(self):
        """A chain that leaves the project would leave that project with a current finding its
        own read-back never filed, and this one with a link to bytes it does not own."""
        self.file(finding_id='rf-p1')
        self.file(finding_id='rf-p2', project_id='p2')
        exc = self.refuse(lambda: self.file(finding_id='rf-3', supersedes='rf-p2'),
                          'RESEARCH_SUPERSEDES_FOREIGN_PROJECT')
        self.assertIn('p2', str(exc))
        self.assertIn('rf-p2', str(exc))
        # and the other direction is the same fact, not a different one
        with self.assertRaises(ResearchStoreError) as refused:
            research_store.record(self.conn, project_id='p2', document=finding(finding_id='x'),
                                  recorded_by='dtalex66', actor_kind='HUMAN',
                                  supersedes='rf-p1')
        self.assertEqual(refused.exception.code, 'RESEARCH_SUPERSEDES_FOREIGN_PROJECT')

    def test_filing_against_a_project_that_does_not_exist_needs_no_chain_to_refuse(self):
        """The project check runs first, so an unknown project is never told about a link."""
        self.file(finding_id='rf-p1')
        with self.assertRaises(ResearchStoreError) as refused:
            research_store.record(self.conn, project_id='nope',
                                  document=finding(finding_id='x'), recorded_by='dtalex66',
                                  actor_kind='HUMAN', supersedes='rf-p1')
        self.assertEqual(refused.exception.code, 'RESEARCH_PROJECT_NOT_RECORDED')

    # ------------------------------------------------------------- reading back

    def test_a_stored_row_that_no_longer_satisfies_its_contract_is_reported(self):
        """Re-validation on read is the tamper signal, not a courtesy.

        Reached the way tampering would be reached -- past the module, straight at the row,
        with the immutability guard dropped first.
        """
        self.file()
        self.conn.executescript('DROP TRIGGER research_finding_no_update;'
                                " UPDATE research_finding SET document_json ="
                                " replace(document_json, '\"medium\"', '\"certain\"')"
                                " WHERE finding_id='rf-1';")
        self.conn.commit()
        with self.assertRaises(ResearchStoreError) as refused:
            research_store.list_findings(self.conn, project_id='p1')
        self.assertEqual(refused.exception.code, 'RESEARCH_STORED_RECORD_INVALID')
        self.assertIn('rf-1', str(refused.exception))
        with self.assertRaises(ResearchStoreError) as refused:
            readback(self.conn, 'p1')
        self.assertEqual(refused.exception.code, 'RESEARCH_STORED_RECORD_INVALID')

    def test_a_stored_row_whose_source_bytes_disagree_with_its_count_is_reported(self):
        """The count column exists so a query can count sources without parsing documents.

        That is only honest while the column and the bytes are the same number -- a read-back
        that published one of them would be publishing a claim nobody could trace.
        """
        self.file()
        self.conn.executescript('DROP TRIGGER research_finding_no_update;'
                                " UPDATE research_finding SET source_ref_count = 99"
                                " WHERE finding_id='rf-1';")
        self.conn.commit()
        exc = None
        try:
            research_store.list_findings(self.conn, project_id='p1')
        except ResearchStoreError as raised:
            exc = raised
        self.assertIsNotNone(exc, 'a disagreeing row was served as if it were trusted')
        self.assertEqual(exc.code, 'RESEARCH_STORED_RECORD_INVALID')
        self.assertIn('99', str(exc))
        self.assertIn('source_ref_count', str(exc))

    def test_the_readback_publishes_what_no_finding_proves(self):
        view = readback(self.conn, 'p1')
        self.assertTrue(view['does_not_prove'])
        joined = ' '.join(view['does_not_prove']).lower()
        self.assertIn('archeaxis', joined, 'the long-term-knowledge boundary is the reason '
                                           'this table is working state, and a reader not '
                                           'told that will treat the table as the truth')
        self.assertIn('knowledgecandidate', joined)
        self.assertIn('quality', joined)
        self.assertIn('source', joined)
        self.assertEqual(view['schemaVersion'], 'design-lab/research-readback/v1')
        self.assertIn('RESEARCH_SOURCE_REFS_EMPTY', research_store.REFUSAL_CODES)

    def test_every_refusal_code_is_documented_and_reachable_from_one_vocabulary(self):
        """An undocumented code is a bug in the store, so it raises AssertionError."""
        with self.assertRaises(AssertionError):
            ResearchStoreError('invented', code='RESEARCH_NOT_IN_THE_LIST')
        self.assertEqual(research_store.REFUSAL_CODES, frozenset({
            'RESEARCH_PROJECT_NOT_RECORDED', 'RESEARCH_DOCUMENT_MALFORMED',
            'RESEARCH_CONTRACT_UNREADABLE', 'RESEARCH_CONTRACT_UNBOUND',
            'RESEARCH_FINDING_INVALID', 'RESEARCH_SOURCE_REFS_EMPTY',
            'RESEARCH_SOURCE_REF_INVALID', 'RESEARCH_ACTOR_MISSING',
            'RESEARCH_ACTOR_KIND_UNKNOWN', 'RESEARCH_NOT_HUMAN',
            'RESEARCH_SUPERSEDES_UNKNOWN', 'RESEARCH_SUPERSEDES_FOREIGN_PROJECT',
            'RESEARCH_ALREADY_SUPERSEDED', 'RESEARCH_FINDING_ID_TAKEN',
            'RESEARCH_DATABASE_REFUSED', 'RESEARCH_STORED_RECORD_INVALID'}))
        # and every code the store can raise is reachable from the façade's status map
        from design_lab.research_review import ResearchReview
        for code in research_store.REFUSAL_CODES:
            mapped = ResearchReview._map(ResearchStoreError('x', code=code))
            self.assertEqual(mapped.code, code, f'{code} loses its identity at the boundary')

    def test_the_state_resource_is_registered_and_resolves(self):
        """A schema nothing can name is a file, not a resource: `state_schema` is the gate."""
        from design_lab.runtime.state_resources import _NAMES
        self.assertIn('design-lab-state-research-v1.sql', _NAMES)
        self.assertTrue(STATE_SQL.is_file())
        self.assertEqual(STATE_SQL.name, 'design-lab-state-research-v1.sql')


class ResearchCliTests(unittest.TestCase):
    """The `research` verb: the same rules, reached from a terminal.

    A verb no test runs is the declared-but-unread shape this whole chain exists to close, so
    the refusals an operator has to be able to tell apart are asserted here against the real
    argparse parser and a real project root -- not read off the source. This is also the only
    place the out-of-document author (`--recorded-by` / `--actor-kind`) can be reached: the
    closed contract gives an HTTP submission no field to state one in.
    """

    def setUp(self):
        from design_lab import cli
        from design_lab.service import ProjectService
        self.cli = cli
        root = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime')) / 'project'
        root.mkdir()
        (root / 'AGENTS.md').write_text('# research cli fixture', encoding='utf-8')
        self.root = root
        self.service = ProjectService(root)
        self.project_id = self.service.create_project('CLI Probe')['id']

    def run_verb(self, *argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.cli.main(['--project', str(self.root), 'research', *argv])
        printed = buffer.getvalue().strip()
        try:
            return code, json.loads(printed)
        except ValueError:
            raise AssertionError(f'the verb answered in prose, not JSON: {printed[:200]}') from None

    def read_back(self):
        code, body = self.run_verb('--project-id', self.project_id)
        self.assertEqual(code, 0, body)
        self.assertEqual(body['status'], 'RESEARCH_READBACK')
        return body

    def file(self, finding_id, **flags):
        argv = ['--record', '--project-id', self.project_id, '--finding-id', finding_id,
                '--claim', flags.get('claim', 'a claim'), '--source',
                flags.get('source', 'interview-07')]
        for name in ('confidence', 'recorded-by', 'actor-kind'):
            if flags.get(name.replace('-', '_')):
                argv += ['--' + name, flags[name.replace('-', '_')]]
        if flags.get('not_design_rule'):
            argv.append('--not-design-rule')
        return self.run_verb(*argv)

    def test_no_project_id_is_refused_rather_than_guessed(self):
        code, body = self.run_verb()
        self.assertEqual(code, 2, body)
        self.assertEqual(body['error'], 'RESEARCH_PROJECT_REQUIRED')

    def test_an_unknown_project_is_refused_before_the_database_is_opened(self):
        code, body = self.run_verb('--project-id', '0' * 32)
        self.assertEqual(code, 2, body)
        self.assertEqual(body['error'], 'RESEARCH_PROJECT_UNKNOWN')
        with closing(research_store.connect(self.service.database,
                                           project_root=self.service.paths.project_root)
                     ) as conn:
            self.assertEqual(research_store.list_findings(conn, project_id=self.project_id), [])

    def test_recording_without_a_claim_or_a_source_names_the_missing_flag(self):
        code, body = self.run_verb('--record', '--project-id', self.project_id)
        self.assertEqual(code, 2, body)
        self.assertEqual(body['error'], 'RESEARCH_RECORD_INPUTS_REQUIRED')
        self.assertIn('--claim', body['detail'])
        self.assertIn('--source', body['detail'])
        code, body = self.run_verb('--record', '--project-id', self.project_id,
                                   '--claim', 'a claim with nothing behind it')
        self.assertEqual(code, 2, body)
        self.assertIn('--source', body['detail'])
        self.assertNotIn('--claim', body['detail'],
                         'a flag that was stated must not be reported as missing')

    def test_a_finding_is_recorded_and_a_repeat_is_refused_as_taken(self):
        """The CLI never replays: an explicit id is what makes the second call visible."""
        code, body = self.file('rf-cli-1', claim='the price card outranks the comparison',
                               source='bench-x', recorded_by='dtalex66', actor_kind='HUMAN',
                               not_design_rule=True)
        self.assertEqual(code, 0, body)
        self.assertEqual(body['status'], 'RESEARCH_RECORDED')
        self.assertEqual(body['sourced_finding_count'], 1)
        self.assertIs(body['is_knowledge_export'], False)
        self.assertTrue(body['does_not_prove'])
        code, again = self.file('rf-cli-1', claim='the price card outranks the comparison',
                                source='bench-x', recorded_by='dtalex66', actor_kind='HUMAN',
                                not_design_rule=True)
        self.assertEqual(code, 2, again)
        self.assertEqual(again['error'], 'RESEARCH_FINDING_ID_TAKEN')
        self.assertEqual(self.read_back()['finding_count'], 1,
                         'a retry may not become a second finding of one claim')

    def test_a_confidence_word_outside_the_contract_is_refused_by_the_verb_too(self):
        code, body = self.file('rf-cli-bad', confidence='certain')
        self.assertEqual(code, 2, body)
        self.assertEqual(body['error'], 'RESEARCH_FINDING_INVALID')
        self.assertEqual(self.read_back()['finding_count'], 0)

    def test_an_agent_may_record_one_but_may_not_claim_a_human_authorship(self):
        """The difference between this surface and a human gate, reached from a terminal."""
        code, body = self.file('rf-cli-bot', claim='compiled from the session log',
                               source='transcript-03', recorded_by='qoder-agent',
                               actor_kind='AGENT')
        self.assertEqual(code, 0, body)
        view = self.read_back()
        self.assertEqual(view['actor_kinds']['rf-cli-bot'], 'AGENT')
        self.assertEqual(view['unattributed_findings'], [],
                         'a stated author may not be reported as none')
        code, refused = self.file('rf-cli-lie', claim='a machine signing as a person',
                                  source='transcript-03', recorded_by='codex',
                                  actor_kind='HUMAN')
        self.assertEqual(code, 2, refused)
        self.assertEqual(refused['error'], 'RESEARCH_NOT_HUMAN')
        self.assertEqual(self.read_back()['finding_count'], 1,
                         'the refused claim left no finding behind')

    def test_the_empty_surface_reads_zero_and_emits_no_verdict_word(self):
        view = self.read_back()
        self.assertEqual(view['finding_count'], 0)
        self.assertIsNone(view['research_verdict'])
        self.assertFalse(view['proves_design_quality'])
        self.assertEqual(view['source_ref_field'], 'sourceRefs')


class MethodCardCollisionTests(unittest.TestCase):
    """The sibling object in the same `object-model.json`, deliberately NOT bound.

    `design-lab/config/object-model.json` names two objects side by side -- ResearchFinding and
    MethodCard -- and this chain gave the first one a store, a route, a verb and this suite. The
    second one is a live naming collision, not an unread schema, and the decision recorded here
    is to leave it unresolved rather than pick a winner in somebody else's inventory:

    * `design-lab/schemas/method-card.schema.json` requires method_id/name/steps/attribution;
    * `design-lab/research/master-studies/ANCHOR_METHOD_CARDS.json` -- which the object model's
      `schemaRef` does NOT point at -- carries id/name/thesis/transferable_methods/
      shallow_mimicry_risks, is enforced field-by-field by
      `design-lab/scripts/verify_style_master_method.py`, and is counted as
      `"method_cards": 77` in `design-lab/config/asset-counts.json`.

    Both are called "method card" today. Nothing was renamed, reshaped or absorbed here, and
    these numbers are measured from the shipped bytes on every run, so the collision stays a
    finding instead of becoming a quiet assumption: if one side is ever conformed to the other
    without this decision being made, the counts below stop being true and this suite says so.
    """

    CORPUS = REPO / 'design-lab/research/master-studies/ANCHOR_METHOD_CARDS.json'
    OTHER_GATE = REPO / 'design-lab/scripts/verify_style_master_method.py'
    COUNTS = REPO / 'design-lab/config/asset-counts.json'

    def test_the_two_method_card_shapes_are_still_incompatible(self):
        import jsonschema

        schema = json.loads((REPO / 'design-lab/schemas/method-card.schema.json')
                            .read_text(encoding='utf-8'))
        cards = json.loads(self.CORPUS.read_text(encoding='utf-8'))['cards']
        validator = jsonschema.Draft202012Validator(schema)
        failing = [card['id'] for card in cards if list(validator.iter_errors(card))]
        self.assertEqual(len(cards), 77, 'the anchor corpus count moved -- re-check which '
                                         'shape this repository means by "method card"')
        self.assertEqual(len(failing), len(cards),
                         'some anchor cards now satisfy schemas/method-card.schema.json, so the '
                         'two shapes have quietly started to merge and this non-decision has to '
                         'be revisited')
        # The claim is not "different labels": a required field is absent outright.
        self.assertFalse({'method_id', 'steps', 'attribution'} <= set(cards[0]),
                         'the anchor corpus grew the schema\'s required fields, so the '
                         'collision may now be resolvable by binding rather than renaming')

    def test_the_other_shape_is_the_one_two_gates_enforce(self):
        """Recorded so a reader can see why binding THIS schema was not a free choice."""
        gate = self.OTHER_GATE.read_text(encoding='utf-8')
        for field in ('id', 'name', 'thesis', 'transferable_methods', 'shallow_mimicry_risks'):
            self.assertIn(f'"{field}"', gate,
                          f'verify_style_master_method.py no longer names {field}, so the '
                          'enforced shape may have moved and this record is stale')
        counts = json.loads(self.COUNTS.read_text(encoding='utf-8'))
        self.assertEqual(counts['method_cards'], 77)
        self.assertEqual(len(json.loads(self.CORPUS.read_text(encoding='utf-8'))['cards']),
                         counts['method_cards'],
                         'the counted inventory and the counted corpus disagree')

    def test_nothing_in_src_binds_method_card_schema(self):
        """The non-decision is that this schema stays inert, so that must remain checkable.

        Asserted from the tree rather than from memory: if a future store loads it, this case
        is the one that says the decision was actually made and this record has to go.
        """
        sources = [path for path in (REPO / 'src').rglob('*.py') if '__pycache__' not in path.parts]
        loaders = [path.relative_to(REPO).as_posix() for path in sources
                   if 'schemas/method-card.schema.json' in path.read_text(encoding='utf-8')]
        self.assertEqual(loaders, [],
                         'something in src/ loads the method-card contract now: the collision '
                         'has been resolved in practice and this record must be replaced by a '
                         'real binding row in design-lab/config/contract-bindings.json')


if __name__ == '__main__':
    unittest.main()
