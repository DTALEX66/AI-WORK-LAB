# SPDX-License-Identifier: MIT
"""Teeth for design-lab/scripts/verify_route_payload_contracts.py.

Every family in design-lab/scripts/verify_route_payload_contracts.py started as a payload that
named a ``schemaVersion`` no schema file described anywhere. The three paid on 2026-10-20 --
GET /api/models, GET .../model-selection and GET .../knowledge-candidates/<id>/export -- came in
the same move as their schema, their ledger row and their live payloads, which is the only way a
new binding is evidence rather than a claim. They are bound now, and this module is what keeps the
binding honest rather than decorative. One live server is booted for the whole class
(``make_server`` on a real socket, a scratch project root, a real jury verdict and proposal filed
through the write routes, a brief with a revision, an approved knowledge candidate and a recorded
model choice), and every payload compared below is the body that server actually wrote.

Both obligations are tested:

1. the shipped schemas accept the shipped responses -- the control;
2. each failure mode goes RED FOR ITS OWN REASON. The schema and the payload set are injectable
   into ``check_binding``, so a mutation convicts the gate's reasoning without touching a
   shipped file. Cases that must go red: a field the schema requires that the route did not
   send (MISSING_FROM_EMITTER), a field the route sent that a closed schema forbids
   (UNDECLARED_BY_SCHEMA), a one-sided ``schemaVersion`` bump (VERSION_DRIFT), the ledger and
   this file disagreeing in either direction (LEDGER_DISAGREES / UNVALIDATED_BINDING), and every
   shape of NOTHING_TO_COMPARE.

An error whose reason is not the named one does not count, and an ERROR verdict is a harness
fault, not a pass.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_PATH = REPO / 'design-lab' / 'scripts' / 'verify_route_payload_contracts.py'
if str(REPO / 'src') not in sys.path:
    sys.path.insert(0, str(REPO / 'src'))

_spec = importlib.util.spec_from_file_location('route_payload_contracts', GATE_PATH)
GATE = importlib.util.module_from_spec(_spec)
sys.modules[GATE_PATH.stem] = GATE
_spec.loader.exec_module(GATE)


def load_schema(binding):
    return json.loads((REPO / binding['schema']).read_text(encoding='utf-8'))


class RoutePayloadContractTests(unittest.TestCase):
    """One live harness; each case mutates a copy of a schema, never a shipped file."""

    @classmethod
    def setUpClass(cls):
        cls.harness_cm = GATE.Harness()
        cls.harness = cls.harness_cm.__enter__()
        cls.reg, cls.docs = GATE.registry()
        cls.bindings = GATE.build_bindings()
        cls.rows = GATE.ledger_route_rows()
        cls.payloads = {}
        for binding in cls.bindings:
            cls.payloads[binding['name']] = list(binding['cases'](cls.harness))

    @classmethod
    def tearDownClass(cls):
        cls.harness_cm.__exit__(None, None, None)

    def binding(self, name):
        return next(b for b in self.bindings if b['name'] == name)

    def convicting(self, errors, token):
        return [error for error in errors if token in error]

    # --- the control ---------------------------------------------------------------

    def test_the_live_responses_satisfy_the_shipped_schemas(self):
        errors, notes = GATE.run()
        self.assertEqual(errors, [], f'the shipped bindings are red: {errors[:6]}')
        self.assertEqual(len(notes), len(self.bindings))
        for note in notes:
            # A binding that compared zero object locations would report PASS on nothing.
            self.assertGreater(int(note.split('compared=')[-1]), 0, note)
            self.assertGreaterEqual(int(note.split('cases=')[1].split()[0]), 1, note)

    def test_every_family_is_covered_by_its_own_real_cases(self):
        """Not one fixture standing in for several boundaries: each binding must reach the route."""
        expected = {'path-diagnostic': 1, 'capability-library': 1, 'domain-pack-readback': 1,
                    'jury-readback': 2, 'task-resource-preflight': 3, 'model-catalog': 1,
                    # Three states, three real rows: a pick, an explicit declination, and a project
                    # nobody has asked. One payload standing in for all three would let the envelope
                    # collapse them and this file would not notice.
                    'model-selection-readback': 3, 'knowledge-candidate-export': 1,
                    # Both were in the gate before this file started checking the list, and neither
                    # was listed: two boundaries the coverage assertion silently did not cover.
                    'brief-readback': 2, 'evidence-projection': 2,
                    # Cleared, refused by a human, and never filed. The third is the branch an
                    # emitter can turn into a false CLEARED, so it has to be a real read.
                    'rights-readback': 3,
                    # A superseded chain and nothing filed -- `superseded_finding_count` is only
                    # ever nonzero when a real chain exists.
                    'research-readback': 2,
                    # The same route before any native table and after one attempt: the absent /
                    # present split this projection exists to keep apart.
                    'native-runtime-readback': 2,
                    # Accepted, stored-but-unsigned, and never produced. Three review sentences that
                    # a page must not be able to collapse into one empty panel.
                    'prompt-result-readback': 3,
                    # This checkout (tables opened by earlier cases) and a throwaway root where they
                    # were never created: the null-vs-0 branch only the second one can show.
                    'project-list': 2,
                    # One envelope, three surfaces. The list binding reads a project with nothing
                    # recorded and one carrying an acknowledged cancellation -- the two pages where
                    # `truncated`/`next_cursor` and the cancel flags mean different things. The
                    # detail binding reads the same job as a record and as an event page, which is
                    # the only way the `surface` discriminator is compared rather than asserted.
                    'task-readback-list': 2, 'task-readback-detail': 2,
                    # The design-layer family, paid 2026-10-23. Seventeen rows, and every one of
                    # them is compared against two answers rather than one: the shape a reader can
                    # confuse is not a missing field, it is a live tip read as a superseded version,
                    # a project with rows read as an empty one, a choice that was never made read as
                    # a blank panel, or a token list given a cursor it does not have. Each binding
                    # therefore carries both sides of the distinction it exists to keep.
                    'design-layer-rollup': 2,
                    'design-record-brief-detail': 2, 'design-record-direction-detail': 2,
                    'design-collection-directions': 2, 'design-collection-tokens': 2,
                    # The catalog read: one case, because catalog() has no empty branch a fixture
                    # could show.
                    'design-collection-systems': 1,
                    'design-lineage-brief-scoped': 2, 'design-lineage-direction-scoped': 2,
                    'design-lineage-brief-by-id': 2, 'design-lineage-direction-by-id': 2,
                    # Write answers: the append branch and the replay of the same idempotency key,
                    # which is a DIFFERENT code path in the emitter (it returns the stored row) and
                    # the same boundary a caller can be handed.
                    'design-record-brief-create': 2, 'design-record-direction-create': 2,
                    'design-record-direction-choose': 2, 'design-record-direction-bind': 2,
                    'design-record-brief-revise-scoped': 2,
                    'design-record-direction-revise-scoped': 2,
                    'design-record-brief-revise-by-id': 2,
                    'design-record-direction-revise-by-id': 2,
                    # The knowledge library, paid 2026-10-23. The import binding carries two
                    # answers because a replayed import is a different branch from the write
                    # (it returns the stored entry and writes nothing); the search binding
                    # carries the short-word fallback's answer, not one trigram produced.
                    'knowledge-library-search': 1, 'knowledge-entry-write-create': 1,
                    'knowledge-entry-write-revise': 1, 'knowledge-entry-import': 2,
                    'knowledge-entry-readback': 1, 'knowledge-index-rebuild': 1,
                    # DL-KB-05 D5: two judgements of the same entry, both read back as the entry's
                    # own document. One is the recommendation moving BACK to an older revision and
                    # the other is a source marked dead with a stored replacement -- the two facts
                    # the acceptance clause asks the library to be able to say at all.
                    'knowledge-entry-judgement': 2,
                    # The assistance plan, paid 2026-10-24. The readback carries three answers
                    # because its four states are computed per revision: saved-but-unsupplied,
                    # supplied, and chosen-by-a-named-human are three different documents, and a
                    # page that cannot tell them apart is the defect the route exists to prevent.
                    # The list carries an empty project and one with a plan (the two branches the
                    # `truncated` count separates). The two write answers are one case each: the
                    # create always answers the first revision and a revise under a stale
                    # `expected_revision` is a refusal, not a second document shape.
                    'assistance-plan-write-create': 1, 'assistance-plan-write-revise': 1,
                    'assistance-plan-readback': 3, 'assistance-plan-list': 2,
                    # One case: the vocabulary is one closed list with no empty branch (the same
                    # reason design-collection-systems carries one).
                    'assistance-plan-output-types': 1, 'assistance-plan-choose': 1,
                    # DL-KB-12: two cases, one per revision of the harness's two-revision plan. One
                    # answer alone could not distinguish this route from one that ignores the number
                    # it was handed -- the older row is the only payload here whose `document` is not
                    # the readback's `current`, and the newest is the one a named human chose.
                    'assistance-plan-revision': 2,
                    # DL-KB-11: four materials from one plan, all compared. One answer per format
                    # is the minimum that makes "the three exports say the same thing" testable at
                    # all -- and the 分镜 CSV case only exists because this plan carries shot rows,
                    # since the same route refuses to render a storyboard from an empty one.
                    'plan-export': 4,
                    # DL-KB-09. Two cases on detail and two on validate on purpose: the registry's
                    # honest answers are a seeded row whose fields are all UNKNOWN with reasons
                    # (Meshy, four failed fetch attempts recorded in its own row) and a draft
                    # somebody wrote, and validation has to be compared both where the vendor's own
                    # words say "does not support" (FLUX.2 has no negative prompt) and where nobody
                    # reached the entry at all. The list carries one answer because the collection
                    # has no empty branch -- five seeded profiles are always in the tracked config.
                    'target-profile-axes': 1, 'target-profile-list': 1,
                    'target-profile-detail': 2, 'target-profile-create': 1,
                    'target-profile-validate': 2,
                    # DL-KB-16: two cases each. The list is compared while empty AND after two
                    # reports, and the two write answers are the first statement and the correction
                    # -- an append-only history that is only ever compared once could be a mutable
                    # field wearing a list costume.
                    'plan-feedback-list': 2, 'plan-feedback-record': 2}
        self.assertEqual(sorted(expected), sorted(b['name'] for b in self.bindings),
                         'a binding added here without being listed below is a boundary this '
                         'file silently stopped covering')
        for name, count in expected.items():
            cases = self.payloads[name]
            self.assertEqual(len(cases), count, f'{name} captured {len(cases)} payloads')
            for label, payload in cases:
                self.assertIsInstance(payload, dict, f'{name}/{label} is not a mapping')
                self.assertEqual(payload['schemaVersion'], self.binding(name)['version'],
                                 f'{name}/{label} answered under a different version')

    # --- field disagreement in both directions --------------------------------------

    def test_a_required_field_the_route_does_not_send_is_red(self):
        binding = self.binding('path-diagnostic')
        schema = load_schema(binding)
        schema['properties']['auditTrail'] = {'type': 'string'}
        schema['required'].append('auditTrail')
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema, cases=self.payloads[binding['name']])
        convicting = self.convicting(errors, 'MISSING_FROM_EMITTER')
        self.assertEqual(len(convicting), 1, errors)
        self.assertIn('auditTrail', convicting[0])
        self.assertIn('the schema requires fields the route did not send', convicting[0])

    def test_a_field_the_route_sends_that_a_closed_schema_forbids_is_red(self):
        binding = self.binding('path-diagnostic')
        schema = load_schema(binding)
        del schema['properties']['write_trace']
        schema['required'].remove('write_trace')
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema, cases=self.payloads[binding['name']])
        convicting = self.convicting(errors, 'UNDECLARED_BY_SCHEMA')
        self.assertEqual(len(convicting), 1, errors)
        self.assertIn('write_trace', convicting[0])

    def test_a_map_value_and_a_nested_def_are_compared_not_just_the_top_level(self):
        """tools.* is where a state word goes missing. A gate that only looked at `$` would
        have passed a payload whose every tool binding lost the field it is judged on."""
        binding = self.binding('path-diagnostic')
        schema = load_schema(binding)
        schema['$defs']['toolBinding']['required'].append('provenanceReceipt')
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema, cases=self.payloads[binding['name']])
        convicting = self.convicting(errors, 'MISSING_FROM_EMITTER')
        self.assertTrue(convicting, f'the nested map value was never compared: {errors[:4]}')
        self.assertTrue(all('$.tools.*' in error for error in convicting), convicting)
        self.assertTrue(all('provenanceReceipt' in error for error in convicting), convicting)

    def test_the_anyof_branch_a_payload_does_not_satisfy_is_not_convicted(self):
        """A host resource has no resolved_path and must not be reported for it. Only the
        tool branch a real tool record actually matches is compared."""
        binding = self.binding('task-resource-preflight')
        schema = load_schema(binding)
        schema['$defs']['toolResource']['required'].append('probeEvidenceSha256')
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema, cases=self.payloads[binding['name']])
        convicting = self.convicting(errors, 'MISSING_FROM_EMITTER')
        self.assertEqual(len(convicting), 5, f'expected one per tool record in the real cases: '
                                             f'{[e for e in errors if "MISSING" in e][:3]}')
        for error in convicting:
            self.assertIn('#anyOf[0]', error, f'wrong branch convicted: {error}')
            self.assertNotIn('DECLARED_NOT_PROBED', error)

    def test_a_referenced_jury_record_is_compared_against_its_own_contract(self):
        """The readback schema $refs assurance-jury-record-v2 rather than restating it, so a
        record field the referenced contract does not declare is still a finding here."""
        binding = self.binding('jury-readback')
        schema = load_schema(binding)
        # Drop a required field from the ENVELOPE, and separately prove the referenced record
        # is reached: a jury record is one of the compared object locations.
        nodes = GATE.comparisons(schema, self.payloads['jury-readback'][0][1], '$', [],
                                 self.docs, schema, self.reg)
        paths = {node['path'] for node in nodes}
        self.assertTrue(any(p.startswith('$.records[0]') for p in paths),
                        f'the referenced record was never descended into: {sorted(paths)[:8]}')
        self.assertTrue(any(p.startswith('$.current_verdicts.*') for p in paths),
                        'the map of current verdicts was never descended into')
        schema2 = copy.deepcopy(schema)
        del schema2['properties']['accepted_versions']
        schema2['required'].remove('accepted_versions')
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema2,
                                       cases=self.payloads[binding['name']])
        self.assertEqual(len(self.convicting(errors, 'UNDECLARED_BY_SCHEMA')), 2, errors)

    def test_a_selection_document_is_judged_by_the_contract_that_owns_it(self):
        """The three 2026-10-20 bindings $ref their records -- the stored choice, the v2 export
        def, the v1 projection -- rather than restating them. A nested document that was never
        descended into would make that a claim, so each reach is asserted and one envelope field
        is removed to prove the envelope itself is compared too."""
        binding = self.binding('model-selection-readback')
        schema = load_schema(binding)
        nodes = GATE.comparisons(schema, self.payloads[binding['name']][0][1], '$', [],
                                 self.docs, schema, self.reg)
        paths = {node['path'] for node in nodes}
        self.assertTrue(any(p.startswith('$.selection#oneOf') for p in paths),
                        f'the referenced selection document was never descended into: '
                        f'{sorted(paths)}')
        self.assertTrue(any(p.startswith('$.history[0]') for p in paths),
                        'the decision path was never descended into')
        export = self.binding('knowledge-candidate-export')
        export_schema = load_schema(export)
        nodes = GATE.comparisons(export_schema, self.payloads[export['name']][0][1], '$', [],
                                 self.docs, export_schema, self.reg)
        paths = {node['path'] for node in nodes}
        self.assertIn('$.export', paths)
        self.assertIn('$.v1_projection', paths)
        self.assertIn('$.provenance', paths)
        mutated = copy.deepcopy(schema)
        del mutated['properties']['state']
        mutated['required'].remove('state')
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=mutated, cases=self.payloads[binding['name']])
        self.assertEqual(len(self.convicting(errors, 'UNDECLARED_BY_SCHEMA')), 3, errors)

    def test_a_readiness_claim_that_disagrees_with_the_rows_is_red(self):
        """The catalogue's fail-closed numbers are the page's only defence against a green chip
        the registry does not support, so they are bound as invariants. A payload that claims
        QUALIFIED_LOCAL under counts.qualified_local=0 must be convicted by the schema, not by a
        sentence in a reason field."""
        binding = self.binding('model-catalog')
        schema = load_schema(binding)
        label, payload = self.payloads['model-catalog'][0]
        self.assertEqual(0, payload['counts']['qualified_local'],
                         'the registry moved; this case is about the zero-qualified invariant')
        lying = copy.deepcopy(payload)
        lying['models'][0]['radar_state'] = 'QUALIFIED_LOCAL'
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema,
                                       cases=[(f'{label} with one row promoted', lying)])
        convicting = self.convicting(errors, 'SCHEMA_VIOLATION')
        self.assertTrue(convicting, 'the zero-qualified invariant caught nothing')
        self.assertIn('models/0/radar_state', convicting[0])

    # --- the rules each new envelope exists to keep ---------------------------------

    def test_clearing_zero_of_zero_rights_scopes_is_red(self):
        """`rights_clearance` is the one word a reader can be misled by.

        The façade's rule is that CLEARED needs a filed scope and a current APPROVED for every
        filed scope, so an empty ledger reads NOT_REVIEWED. A `all()` over an empty scope set
        returns True and would silently report a gate nobody reviewed as cleared -- this case
        plants exactly that lie on the project that never filed anything, against the shipped
        schema, and requires the schema to convict it.
        """
        binding = self.binding('rights-readback')
        schema = load_schema(binding)
        label, payload = self.payloads['rights-readback'][2]
        self.assertEqual(0, payload['filed_scope_count'],
                         'this case is about the empty ledger; a filed row would make it vacuous')
        self.assertEqual('NOT_REVIEWED', payload['rights_clearance'])
        lying = copy.deepcopy(payload)
        lying['rights_clearance'] = 'CLEARED'
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema,
                                       cases=[(f'{label} reported as cleared', lying)])
        self.assertTrue(self.convicting(errors, 'SCHEMA_VIOLATION'),
                        'the 0-of-0 rule caught nothing: the schema is prose with a $id')

    def test_a_partially_refused_rights_gate_cannot_claim_clearance(self):
        binding = self.binding('rights-readback')
        schema = load_schema(binding)
        label, payload = self.payloads['rights-readback'][1]
        self.assertTrue(payload['unapproved_scopes'],
                        'the refusal branch is what this case plants a lie against')
        self.assertEqual('NOT_REVIEWED', payload['rights_clearance'])
        lying = copy.deepcopy(payload)
        lying['rights_clearance'] = 'CLEARED'
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema,
                                       cases=[(f'{label} with the refusal ignored', lying)])
        self.assertTrue(self.convicting(errors, 'SCHEMA_VIOLATION'),
                        'CLEARED survived a filed DENIED: unapproved_scopes is not bound to it')

    def test_a_research_verdict_word_invented_on_the_readback_is_red(self):
        """Research publishes counts because writing findings down clears no gate.

        `research_verdict: null` is not a missing value waiting to be filled; it is the sentence
        'this surface has no verdict'. A future emitter that starts printing ACCEPTED or CLEARED
        here has to edit this contract first, and the UI may not advertise a verdict the service
        cannot emit.
        """
        binding = self.binding('research-readback')
        schema = load_schema(binding)
        label, payload = self.payloads['research-readback'][0]
        self.assertIsNone(payload['research_verdict'])
        for word in ('ACCEPTED', 'CLEARED', 'PENDING_REVIEW'):
            lying = copy.deepcopy(payload)
            lying['research_verdict'] = word
            errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                           schema_doc=schema,
                                           cases=[(f'{label} claiming {word}', lying)])
            self.assertTrue(self.convicting(errors, 'SCHEMA_VIOLATION'),
                            f'{word} passed as a research verdict')

    def test_an_absent_native_table_collapsed_into_zero_is_red(self):
        """'This service never ran a native attempt' is not 'no attempt holds the host'.

        The projection keeps the two apart with `table: ABSENT` plus null rows and null counts.
        Reporting PRESENT with zero rows -- or a count of 0 where the table is absent -- is the
        collapse this case plants, on the payload read before any native table existed.
        """
        binding = self.binding('native-runtime-readback')
        schema = load_schema(binding)
        label, payload = self.payloads['native-runtime-readback'][0]
        self.assertEqual('ABSENT', payload['host_guard']['table'])
        self.assertIsNone(payload['counts']['hosts_held'])
        collapsed = copy.deepcopy(payload)
        collapsed['counts']['hosts_held'] = 0
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema,
                                       cases=[(f'{label} with a zero count', collapsed)])
        self.assertTrue(self.convicting(errors, 'SCHEMA_VIOLATION'),
                        'a null count and a zero are interchangeable to this schema -- they are '
                        'different sentences to a reader')
        pretend = copy.deepcopy(payload)
        pretend['budget'] = 0
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema,
                                       cases=[(f'{label} with a budget', pretend)])
        self.assertTrue(self.convicting(errors, 'SCHEMA_VIOLATION'),
                        'budget 0 would read as "budget available" on a surface that never '
                        'measured one')

    # --- one-sided version moves ----------------------------------------------------

    def test_a_schema_bumping_its_const_alone_is_red(self):
        binding = self.binding('capability-library')
        schema = load_schema(binding)
        schema['properties']['schemaVersion']['const'] = 'design-lab/capability-library/v2'
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema, cases=self.payloads[binding['name']])
        convicting = self.convicting(errors, 'VERSION_DRIFT')
        self.assertEqual(len(convicting), 1, errors)
        self.assertIn("binds 'design-lab/capability-library/v2'", convicting[0])

    def test_a_schema_that_declares_no_const_cannot_tie_a_payload_to_a_version(self):
        binding = self.binding('domain-pack-readback')
        schema = load_schema(binding)
        del schema['properties']['schemaVersion']['const']
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema, cases=self.payloads[binding['name']])
        self.assertEqual(len(self.convicting(errors, 'VERSION_DRIFT')), 1, errors)

    # --- the ledger and this file must agree ---------------------------------------

    def test_a_row_removed_or_downgraded_in_the_ledger_is_red_here(self):
        """The debt line is not removable: dropping the row, or quietly calling the route
        SCHEMA_LESS again, is convicted from both directions."""
        cases = {
            'row deleted': lambda rows: [r for r in rows
                                         if r['route'] != '/api/environment'],
            'row downgraded to SCHEMA_LESS': lambda rows: [
                dict(r, kind='SCHEMA_LESS') if r['route'] == '/api/environment' else r
                for r in rows],
            'row binds another schema': lambda rows: [
                dict(r, schema='design-lab/schemas/artifact-preflight.schema.json')
                if r['route'] == '/api/environment' else r for r in rows],
            'row names another emitter': lambda rows: [
                dict(r, emitter='src/design_lab/cli.py:1')
                if r['route'] == '/api/environment' else r for r in rows],
        }
        for label, mutate in cases.items():
            rows = mutate(self.rows)
            errors, _ = GATE.check_binding(self.binding('path-diagnostic'), docs=self.docs,
                                           reg=self.reg, rows=rows,
                                           cases=self.payloads['path-diagnostic'])
            convicting = self.convicting(errors, 'LEDGER_DISAGREES')
            self.assertEqual(len(convicting), 1, f'{label}: {errors[:4]}')

    def test_a_bound_row_with_no_payload_binding_is_theatre(self):
        """A ledger may not claim BOUND_SCHEMA for one of these schemas from a route this gate
        never drives -- the claim has to name the response that was actually checked."""
        rows = [dict(row, kind='BOUND_SCHEMA',
                     schema='design-lab/schemas/jury-readback.schema.json',
                     version='design-lab/jury-readback/v1',
                     emitter='src/design_lab/jury_review.py:53')
                for row in self.rows
                if row['route'] == '/api/projects/([0-9a-f]{32})/briefs']
        self.assertEqual(len(rows), 1, 'the fixture row no longer exists to mutate')
        errors = GATE.unvalidated_binding_errors(self.bindings, rows + self.rows)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('/api/projects/([0-9a-f]{32})/briefs', errors[0])
        self.assertIn('jury-readback.schema.json', errors[0])
        # And the same rows, unmutated, must not raise the finding: the check is keyed on the
        # route, not on the schema, so it cannot fire twice for the row that is genuinely bound.
        self.assertEqual(GATE.unvalidated_binding_errors(self.bindings, self.rows), [])

    # --- NOTHING TO_COMPARE is a failure, in every shape ----------------------------

    def test_no_payload_produced_is_red(self):
        binding = self.binding('path-diagnostic')
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=load_schema(binding), cases=[])
        self.assertEqual(len(self.convicting(errors, 'NOTHING_TO_COMPARE')), 1, errors)

    def test_a_payload_that_is_not_a_mapping_is_red(self):
        binding = self.binding('path-diagnostic')
        for label, payload in (('empty', {}), ('list', [{'status': 'PATHS_RESOLVED'}]),
                               ('null', None)):
            errors, _ = GATE.check_binding(
                binding, docs=self.docs, reg=self.reg, rows=self.rows,
                schema_doc=load_schema(binding), cases=[(label, payload)])
            self.assertEqual(len(self.convicting(errors, 'NOTHING_TO_COMPARE')), 1,
                             f'{label}: {errors[:4]}')

    def test_a_schema_that_requires_nothing_is_red(self):
        """An empty `required` set is a schema that accepts any payload: it must not pass."""
        binding = self.binding('path-diagnostic')
        schema = load_schema(binding)
        stripped = GATE.strip_required(schema)
        self.assertNotEqual(stripped, schema, 'the fixture stopped requiring anything')
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=stripped, cases=self.payloads[binding['name']])
        convicting = self.convicting(errors, 'NOTHING_TO_COMPARE')
        self.assertEqual(len(convicting), 1, errors)
        self.assertIn('no schema node requires anything', convicting[0])

    def test_a_schema_binding_no_location_the_payload_reaches_is_red(self):
        """`type: object` with no `properties` binds nothing: the payload would sail through
        every check this gate has, so reaching zero object locations is itself the finding."""
        binding = self.binding('path-diagnostic')
        schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                  '$id': 'https://design-lab.local/schemas/path-diagnostic.schema.json',
                  'type': 'object'}
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       schema_doc=schema, cases=self.payloads[binding['name']])
        convicting = self.convicting(errors, 'NOTHING_TO_COMPARE')
        self.assertEqual(len(convicting), 1, errors)
        self.assertIn('no object location', convicting[0])

    def test_a_route_that_refuses_is_red_not_skipped(self):
        binding = dict(self.binding('path-diagnostic'),
                       cases=lambda h: [('GET /api/not-a-route', h.get('/api/not-a-route'))])
        errors, _ = GATE.check_binding(binding, harness=self.harness, docs=self.docs,
                                       reg=self.reg, rows=self.rows)
        convicting = self.convicting(errors, 'NOTHING_TO_COMPARE')
        self.assertEqual(len(convicting), 1, errors)
        self.assertIn('the route refused', convicting[0])
        self.assertIn('ROUTE_REFUSED', convicting[0])

    def test_a_case_producer_that_misshapes_its_pair_is_red_not_a_crash(self):
        """An ERROR here would be a harness fault, not teeth: a producer that returns a bare
        payload instead of (label, payload) has to be named, not raised through."""
        binding = dict(self.binding('path-diagnostic'),
                       cases=lambda h: [h.get('/api/environment')])
        errors, _ = GATE.check_binding(binding, harness=self.harness, docs=self.docs,
                                       reg=self.reg, rows=self.rows)
        convicting = self.convicting(errors, 'NOTHING_TO_COMPARE')
        self.assertEqual(len(convicting), 1, errors)
        self.assertIn('not a (label, payload) pair', convicting[0])

    def test_a_binding_whose_files_are_missing_is_red(self):
        for field, value in (('schema', 'design-lab/schemas/does-not-exist.schema.json'),
                             ('emitter', 'src/design_lab/does_not_exist.py')):
            binding = dict(self.binding('path-diagnostic'), **{field: value})
            errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg,
                                           rows=self.rows, cases=self.payloads['path-diagnostic'])
            self.assertEqual(len(self.convicting(errors, 'NOTHING_TO_COMPARE')), 1,
                             f'{field}: {errors[:4]}')

    def test_no_bindings_at_all_is_red(self):
        errors, _ = GATE.run(bindings=[])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('NOTHING_TO_COMPARE', errors[0])

    def test_the_verdict_line_is_last_and_names_the_binding_count(self):
        """verify_design_lab.py summarises each gate by scanning its output from the end for a
        line starting with VERIFY_, so the shape and position of this line is part of it."""
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = GATE.main([])
        lines = [line for line in buffer.getvalue().splitlines() if line]
        self.assertEqual(code, 0, f'the shipped bindings exit nonzero: {lines[-6:]}')
        self.assertTrue(lines[-1].startswith('VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS'), lines[-1])
        self.assertIn(f'bindings={len(self.bindings)}', lines[-1])
        self.assertIn('failures=0', lines[-1])

    # --- the design-layer family's own teeth (batch I, 2026-10-23) -------------------------

    def _weakened(self, name, index, mutate):
        """One real payload, mutated in a copy, put back through its own binding."""
        binding = self.binding(name)
        cases = list(self.payloads[name])
        label, payload = cases[index]
        cases[index] = (label, mutate(payload))
        errors, _ = GATE.check_binding(binding, docs=self.docs, reg=self.reg, rows=self.rows,
                                       cases=cases)
        return errors

    def test_a_record_envelope_whose_discriminator_lies_is_red(self):
        """`record_kind` is judged against the key that is present, not trusted because it is there.

        A brief served under `direction` is the mislabelling a page cannot see: the wrapper key it
        indexes is the only other hint, and if the discriminator is decorative the two can disagree
        silently and the panel renders a binding as a direction.
        """
        def lie(payload):
            mutated = dict(payload)
            mutated['record_kind'] = 'direction'
            return mutated

        errors = self._weakened('design-record-brief-detail', 0, lie)
        for token in ('SCHEMA_VIOLATION', 'MISSING_FROM_EMITTER', 'UNDECLARED_BY_SCHEMA'):
            self.assertTrue(self.convicting(errors, token), f'{token}: {errors[:4]}')

    def test_a_chain_that_lost_its_root_is_red(self):
        def strip_root(payload):
            lineage = dict(payload['lineage'])
            lineage.pop('root_id')
            return {**payload, 'lineage': lineage}

        errors = self._weakened('design-lineage-brief-scoped', 0, strip_root)
        self.assertTrue(self.convicting(errors, 'MISSING_FROM_EMITTER'), errors[:4])
        self.assertTrue(self.convicting(errors, 'SCHEMA_VIOLATION'), errors[:4])

    def test_a_collection_that_invents_a_cursor_is_red(self):
        """The token list has no paging, and a `next_cursor` appearing on it is convicted.

        This is the branch a lenient union would let through: one envelope, two shapes, and an
        emitter that grew a cursor would look like a correct answer to a reader that already knows
        the direction list carries one.
        """
        def add_cursor(payload):
            return {**payload, 'next_cursor': None}

        errors = self._weakened('design-collection-tokens', 0, add_cursor)
        self.assertTrue(self.convicting(errors, 'UNDECLARED_BY_SCHEMA'), errors[:4])
        self.assertTrue(self.convicting(errors, 'SCHEMA_VIOLATION'), errors[:4])

    def test_an_empty_object_standing_in_for_a_missing_choice_is_red(self):
        """P0-02: `chosen_direction` is null or a real chosen row -- `{}` is neither.

        An empty dict is the shape an emitter reaches for when it wants to say "nothing chosen"
        without a nullable field, and a page would render it as a choice with blank content.
        """
        def hollow(payload):
            layer = dict(payload['design_layer'])
            layer['chosen_direction'] = {}
            return {**payload, 'design_layer': layer}

        errors = self._weakened('design-layer-rollup', 1, hollow)
        self.assertTrue(self.convicting(errors, 'SCHEMA_VIOLATION'), errors[:4])
        self.assertTrue(self.convicting(errors, 'MISSING_FROM_EMITTER'), errors[:4])

    def test_the_append_and_the_replay_of_a_write_share_one_envelope(self):
        """Both branches of each write route are the same boundary, measured on the real answers.

        The replay is not a second copy of the append: it is the emitter's
        `SELECT ... WHERE operation_id=?` path returning the stored row, and a status that differs
        (201 then 200) is exactly why the key sets have to be compared rather than assumed.
        """
        writes = [name for name in sorted(self.payloads) if name.startswith('design-record-')
                  and any(word in name for word in ('create', 'choose', 'bind', 'revise'))]
        self.assertEqual(len(writes), 8, writes)
        for name in writes:
            cases = self.payloads[name]
            self.assertEqual(len(cases), 2, f'{name} does not carry an append and a replay')
            (first_label, first), (second_label, second) = cases
            self.assertEqual(sorted(first), sorted(second),
                             f'{name}: the replay answer is a different shape from the append')
            self.assertEqual(first['record_kind'], second['record_kind'], name)
            self.assertNotEqual(first_label, second_label, f'{name}: both cases are the same call')


if __name__ == '__main__':
    unittest.main(verbosity=2)
