# SPDX-License-Identifier: MIT
"""The task ledger must have the schema its own version names, in both directions.

Background: on 2026-09-09 the live ledger's ``schemaVersion`` moved to
``design-lab/task-ledger/r5-v1`` and no r5-v1 schema file was written. The r3 schema stayed
behind, correct for the r3 file it was written for, while the ledger that nothing could
validate kept being edited -- six days of contract violations later, the projections froze.
These tests are the anti-recurrence machine:

* the real ledger validates against the schema its version selects, and the frozen r3
  predecessor still validates against the r3 schema, so the pairing holds in both directions
  and the r3 file keeps a job instead of being tidied away as "stale";
* a version with no schema behind it is a hard failure -- proven against a mutated copy;
* schema and data are accountable both ways: a ledger field no schema declares fails by path,
  and a schema property the ledger never uses is reported unless a dated register explains it
  -- and a register entry the ledger has outgrown fails too;
* the r5 schema is not weaker than the r3 contract or the rules already written in
  ``r5_contract.py``: shared enums, required lists, id patterns and pinned provenance values
  are compared, not assumed.

Every red case runs against a MUTATED COPY in a temp directory. The live ledger, the frozen
predecessor and the SHA-pinned r3 schema are only ever read.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'design-lab' / 'scripts' / 'verify_ledger_schema_pairing.py'
SCHEMA_R5 = ROOT / 'design-lab' / 'schemas' / 'task-ledger-r5-v1.schema.json'
SCHEMA_R3 = ROOT / 'design-lab' / 'schemas' / 'task-ledger-r3.schema.json'
R5_CONTRACT = ROOT / 'src' / 'design_lab' / 'governance' / 'r5_contract.py'
R5_SOURCE = ROOT / 'docs' / 'history' / 'taskpacks' / 'r5-20260908' / 'tasks.json'

spec = importlib.util.spec_from_file_location('ledger_schema_pairing', SCRIPT)
gate = importlib.util.module_from_spec(spec)
sys.modules['ledger_schema_pairing'] = gate
spec.loader.exec_module(gate)

R3_UNUSED_IN_R5 = '/tasks[]/condition_decisions'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def ledger_document():
    return copy.deepcopy(gate.load(gate.LEDGER))


def run_on(ledger, schema_dir=None):
    """Run the whole gate against a mutated copy, never against the tree's own ledger."""
    with tempfile.TemporaryDirectory(prefix='dl-schema-') as tmp:
        path = Path(tmp) / 'ledger.json'
        path.write_text(json.dumps(ledger, ensure_ascii=False), encoding='utf-8')
        return gate.run(path, gate.PREDECESSOR, schema_dir or gate.SCHEMA_DIR)


def temp_schemas(**edits):
    """A schema directory of copies: the real design-lab/schemas/ is never written."""
    directory = Path(tempfile.mkdtemp(prefix='dl-schemas-'))
    (directory / SCHEMA_R3.name).write_bytes(SCHEMA_R3.read_bytes())
    schema = read_json(SCHEMA_R5)
    for name, value in edits.items():
        if name == 'r5_mutate':
            value(schema)
            continue
        raise AssertionError(f'unknown edit {name}')
    (directory / SCHEMA_R5.name).write_text(json.dumps(schema, ensure_ascii=False),
                                           encoding='utf-8')
    return directory


def contract_rule(pattern):
    """Read a rule out of r5_contract.py without importing it: that module's package is
    being edited by another owner right now, and parsing is the read-only edge."""
    text = R5_CONTRACT.read_text(encoding='utf-8')
    match = re.search(pattern, text)
    assert match, f'r5_contract.py no longer states {pattern}'
    return ast.literal_eval(match.group(1))


def contract_names():
    named, strings = {}, set()
    tree = ast.parse(R5_CONTRACT.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(
                node.targets[0], ast.Name):
            try:
                named[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                pass
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.add(node.value)
    return named, strings


class RealPairing(unittest.TestCase):
    def test_the_live_ledger_validates_against_the_schema_its_version_names(self):
        ledger = ledger_document()
        path = gate.schema_path_for(ledger['schemaVersion'])
        self.assertEqual(path.name, 'task-ledger-r5-v1.schema.json')
        schema = read_json(path)
        self.assertEqual(schema['properties']['schemaVersion']['const'], ledger['schemaVersion'])
        self.assertEqual(gate.validate_against(schema, ledger), [])

    def test_the_frozen_r3_predecessor_still_validates_against_the_r3_schema(self):
        predecessor = read_json(gate.PREDECESSOR)
        path = gate.schema_path_for(predecessor['schemaVersion'])
        self.assertEqual(path.name, 'task-ledger-r3.schema.json')
        self.assertEqual(gate.validate_against(read_json(path), predecessor), [])

    def test_the_predecessor_binding_in_the_live_ledger_is_the_file(self):
        carried = ledger_document()['predecessor']
        raw = gate.PREDECESSOR.read_bytes()
        self.assertEqual(carried['sha256'], sha256(raw).hexdigest())
        self.assertEqual(carried['ledger'], json.loads(raw.decode('utf-8')))

    def test_the_whole_gate_passes_on_the_real_tree_as_a_subprocess(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT)], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('VERIFY_LEDGER_SCHEMA_PAIRING=OK', result.stdout)

    def test_the_ok_line_reports_a_population_that_is_actually_there(self):
        """An OK that checked nothing would be the worst outcome of all: green, and wrong."""
        result = run_on(ledger_document())
        self.assertEqual(result['failures'], [])
        self.assertEqual([item['label'] for item in result['stats']],
                         ['live ledger', 'frozen r3 predecessor'])
        live, r3 = result['stats']
        self.assertEqual(live['version'], 'design-lab/task-ledger/r5-v1')
        self.assertEqual(live['schema_errors'], 0)
        self.assertEqual(live['undeclared'], 0)
        self.assertEqual(live['unused'], 0)
        self.assertGreaterEqual(live['declared_paths'], 60,
                                'the audit stopped walking the schema, so it would catch nothing')
        # declared-but-observed: the registered condition_decisions subtree, and nothing else.
        self.assertEqual(live['declared_paths'] - live['observed_paths'], 3)
        self.assertEqual(live['sanctioned_unused'], 1)
        self.assertEqual(r3['version'], 'design-lab/task-ledger/r3-v1')
        self.assertEqual(r3['schema_errors'], 0)
        self.assertEqual(r3['undeclared'], 0)
        self.assertEqual(r3['sanctioned_undeclared'], 7)
        self.assertGreaterEqual(r3['observed_paths'], 40)

    def test_both_schemas_are_valid_2020_12_documents(self):
        import jsonschema
        for path in (SCHEMA_R5, SCHEMA_R3):
            with self.subTest(schema=path.name):
                jsonschema.Draft202012Validator.check_schema(read_json(path))

    def test_every_local_ref_in_the_r5_schema_resolves_and_is_used(self):
        schema = read_json(SCHEMA_R5)
        found = []

        def walk(node):
            if isinstance(node, dict):
                ref = node.get('$ref')
                if isinstance(ref, str) and ref.startswith('#/'):
                    found.append(ref)
                    gate._pointer(schema, ref)      # raises when it points at nothing
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(schema)
        self.assertGreaterEqual(len(found), 20, 'the r5 schema stopped using $defs at all')
        named, _wildcards = gate.declared_paths(gate.resolve(schema, schema))
        self.assertGreaterEqual(len(named), 60)

    def test_the_embedded_predecessor_is_delegated_not_duplicated(self):
        """One contract, one file. The r5 schema must reference the r3 schema rather than
        copy it -- copying is what let the r3 schema and the r5 ledger disagree."""
        schema = read_json(SCHEMA_R5)
        ledger_node = schema['properties']['predecessor']['properties']['ledger']
        self.assertEqual(ledger_node[gate.DELEGATED], SCHEMA_R3.relative_to(ROOT).as_posix())
        self.assertNotIn('properties', ledger_node)
        _named, wildcards, observed = gate.path_sets(schema, ledger_document())
        self.assertNotIn('/predecessor/ledger/tasks[]/acceptance', observed)


class VersionSelection(unittest.TestCase):
    """The root cause: a version string with no schema behind it."""

    def test_a_version_with_no_schema_file_is_a_hard_failure(self):
        ledger = ledger_document()
        ledger['schemaVersion'] = 'design-lab/task-ledger/r9-v9'
        joined = '\n'.join(run_on(ledger)['failures'])
        self.assertIn(gate.MISSING_SCHEMA, joined)
        self.assertIn('selects no schema file', joined)
        self.assertIn('design-lab/task-ledger/r9-v9', joined)

    def test_a_mapped_version_whose_file_has_disappeared_is_a_hard_failure(self):
        directory = Path(tempfile.mkdtemp(prefix='dl-schemas-'))
        (directory / SCHEMA_R3.name).write_bytes(SCHEMA_R3.read_bytes())
        joined = '\n'.join(run_on(ledger_document(), schema_dir=directory)['failures'])
        self.assertIn('missing_schema', joined)
        self.assertIn('task-ledger-r5-v1.schema.json, which does not exist', joined)
        self.assertIn(gate.MISSING_SCHEMA, joined)

    def test_a_schema_that_claims_a_different_version_is_rejected(self):
        def lie(schema):
            schema['properties']['schemaVersion']['const'] = 'design-lab/task-ledger/r3-v1'

        directory = temp_schemas(r5_mutate=lie)
        joined = '\n'.join(run_on(ledger_document(), schema_dir=directory)['failures'])
        self.assertIn('version_mismatch', joined)

    def test_a_schema_file_no_version_selects_is_reported_as_orphaned(self):
        directory = temp_schemas()
        (directory / 'task-ledger-r7-v1.schema.json').write_bytes(SCHEMA_R5.read_bytes())
        joined = '\n'.join(run_on(ledger_document(), schema_dir=directory)['failures'])
        self.assertIn('orphan_schema', joined)
        self.assertIn('task-ledger-r7-v1.schema.json', joined)

    def test_an_absent_schemaVersion_is_a_hard_failure_not_a_silent_pass(self):
        ledger = ledger_document()
        del ledger['schemaVersion']
        self.assertIn(gate.MISSING_SCHEMA, '\n'.join(run_on(ledger)['failures']))

    def test_the_real_ledger_version_is_the_one_the_gate_selects(self):
        """Positive control: the failure modes above would also fire if the resolver had gone
        deaf. Prove it selects the right file for the two versions that exist."""
        self.assertEqual(gate.schema_path_for('design-lab/task-ledger/r5-v1').name,
                         'task-ledger-r5-v1.schema.json')
        self.assertEqual(gate.schema_path_for('design-lab/task-ledger/r3-v1').name,
                         'task-ledger-r3.schema.json')
        self.assertEqual(gate.pairing_errors(), [])


class MutualAccountability(unittest.TestCase):
    """Direction one: data the schema does not declare. Direction two: the reverse."""

    def test_an_undeclared_field_fails_and_names_its_path(self):
        ledger = ledger_document()
        ledger['tasks'][0]['surprise'] = 'nobody declared this'
        joined = '\n'.join(run_on(ledger)['failures'])
        self.assertIn('undeclared_field /tasks[]/surprise', joined)
        self.assertIn('Additional properties are not allowed', joined)

    def test_an_undeclared_field_in_an_evidence_record_fails_too(self):
        """Records are being appended right now; a new receipt field is exactly how the last
        drift started, and it must not be able to arrive quietly."""
        ledger = ledger_document()
        ledger['evidence'][-1]['approver'] = 'someone'
        joined = '\n'.join(run_on(ledger)['failures'])
        self.assertIn('undeclared_field /evidence[]/approver', joined)

    def test_a_new_software_key_is_not_drift(self):
        """The wildcard halves of the contract stay wildcards: a new measurement field is
        honest, and the gate must not train people to fear appending evidence."""
        ledger = ledger_document()
        ledger['evidence'][-1]['software']['comfyui'] = '0.33.1'
        self.assertEqual(run_on(ledger)['failures'], [])

    def test_an_unused_declaration_is_reported_unless_registered(self):
        def add_ghost(schema):
            schema['$defs']['task']['properties']['ghost_field'] = {'type': 'string'}

        directory = temp_schemas(r5_mutate=add_ghost)
        joined = '\n'.join(run_on(ledger_document(), schema_dir=directory)['failures'])
        self.assertIn('unused_declaration /tasks[]/ghost_field', joined)
        self.assertEqual(len(joined.splitlines()), 1, joined)

    def test_a_register_entry_the_ledger_has_outgrown_goes_stale(self):
        ledger = ledger_document()
        ledger['tasks'][-1]['condition_decisions'] = {
            'TTS_required': {'required': True, 'reason': 'owner recorded the case choice'}}
        joined = '\n'.join(run_on(ledger)['failures'])
        self.assertIn(f'stale_sanction {R3_UNUSED_IN_R5}', joined)
        self.assertEqual(len(joined.splitlines()), 1, joined)

    def test_an_unregistered_r5_field_reaches_the_r3_pair_too(self):
        """The predecessor pair is audited by the same two directions, so a defect there is
        caught the same way -- and the 7 registered r3 fields must not silently grow."""
        predecessor = read_json(gate.PREDECESSOR)
        predecessor['tasks'][0]['invented'] = True
        with tempfile.TemporaryDirectory(prefix='dl-schema-') as tmp:
            path = Path(tmp) / 'predecessor.json'
            path.write_text(json.dumps(predecessor, ensure_ascii=False), encoding='utf-8')
            result = gate.run(gate.LEDGER, path, gate.SCHEMA_DIR)
        joined = '\n'.join(result['failures'])
        self.assertIn('frozen r3 predecessor :: undeclared_field /tasks[]/invented', joined)

    def test_the_two_directions_are_genuinely_different_checks(self):
        """Otherwise 'both directions' is one check wearing a coat: prove the live pair is
        clean in one direction and knowingly dirty in the other."""
        undeclared, unused = gate.drift(read_json(SCHEMA_R5), ledger_document())
        self.assertEqual(undeclared, [])
        self.assertEqual(unused, [R3_UNUSED_IN_R5, R3_UNUSED_IN_R5 + '/*/reason',
                                  R3_UNUSED_IN_R5 + '/*/required'])
        self.assertEqual(gate.prune_nested(unused), [R3_UNUSED_IN_R5])


class NotWeakerThanTheExistingContract(unittest.TestCase):
    """The r5 schema must not be a soft version of what the ledger already had to satisfy."""

    def setUp(self):
        self.r5 = read_json(SCHEMA_R5)
        self.r3 = read_json(SCHEMA_R3)
        self.resolved_r3 = gate.resolve(self.r3, self.r3)

    def test_shared_enums_are_the_same_vocabularies(self):
        r3_evidence = self.resolved_r3['properties']['evidence']['items']['properties']
        r5_evidence = self.r5['$defs']['evidenceRecord']['properties']
        pairs = [
            ('axis state', self.resolved_r3['$defs']['axis']['properties']['state']['enum'],
             self.r5['$defs']['axis']['properties']['state']['enum']),
            ('axis name',
             self.resolved_r3['properties']['tasks']['items']['properties']['required_axes']['items']['enum'],
             self.r5['$defs']['axisName']['enum']),
            ('kind', r3_evidence['kind']['enum'], r5_evidence['kind']['enum']),
            ('outcome', r3_evidence['outcome']['enum'], r5_evidence['outcome']['enum']),
            ('binding', r3_evidence['binding']['enum'], r5_evidence['binding']['enum']),
        ]
        for label, before, after in pairs:
            with self.subTest(field=label):
                self.assertEqual(sorted(before), sorted(after))

    def test_the_r5_evidence_record_requires_every_field_r3_required(self):
        r3_required = set(self.resolved_r3['properties']['evidence']['items']['required'])
        self.assertTrue(r3_required <= set(self.r5['$defs']['evidenceRecord']['required']),
                        f'r5 dropped {r3_required - set(self.r5["$defs"]["evidenceRecord"]["required"])}')

    def test_the_r5_schema_closes_the_objects_r3_left_open(self):
        """The r3 task items never set additionalProperties, which is how seven undeclared
        fields lived in the frozen r3 file unnoticed. r5 does not repeat that."""
        self.assertIs(self.r5['$defs']['task']['additionalProperties'], False)
        self.assertNotIn('additionalProperties',
                         self.resolved_r3['properties']['tasks']['items'])
        _undeclared, unused = gate.drift(read_json(SCHEMA_R3), read_json(gate.PREDECESSOR))
        self.assertEqual(unused, [], 'the r3 schema declares something its own file never used')

    def test_hash_and_sha_patterns_match_the_r3_definitions(self):
        self.assertEqual(self.r3['$defs']['hash']['pattern'], self.r5['$defs']['hash']['pattern'])
        self.assertEqual(self.r3['$defs']['hash']['not'], self.r5['$defs']['hash']['not'])
        self.assertEqual(self.r3['properties']['baseline_sha']['pattern'],
                         self.r5['$defs']['gitSha']['pattern'])
        self.assertEqual(
            self.resolved_r3['properties']['evidence']['items']['properties']['subject_sha']['pattern'],
            self.r5['$defs']['gitSha']['pattern'])

    def test_the_values_r5_contract_pins_as_consts_are_pinned_here_too(self):
        named, strings = contract_names()
        source = self.r5['properties']['source']['properties']
        self.assertEqual(source['path']['const'], named['SOURCE_PATH'])
        self.assertEqual(source['sha256']['const'], named['SOURCE_HASH'])
        self.assertEqual(
            self.r5['properties']['predecessor']['properties']['sha256']['const'],
            named['PREDECESSOR_HASH'])
        self.assertEqual(self.r5['properties']['plan_path']['const'],
                         'docs/history/taskpacks/r5-20260908/02-TASKS.md')
        self.assertIn(self.r5['properties']['plan_path']['const'], strings)
        self.assertIn(self.r5['properties']['schemaVersion']['const'], strings)
        self.assertEqual(self.r5['$defs']['task']['properties']['reassessment']['enum'],
                         contract_rule(r"'reassessment': \{'enum': (\[[^]]*\])\}"))
        self.assertEqual(self.r5['$defs']['r5TaskId']['pattern'],
                         contract_rule(r"\['id'\]\['pattern'\] = ('[^']*')"))
        self.assertEqual(sorted(self.r5['$defs']['task']['required']),
                         sorted(contract_rule(r"task_schema\['required'\] = (\[[^\]]*\])")))
        self.assertEqual(contract_rule(r"props\['tasks'\]\['minItems'\] = props\['tasks'\]\['maxItems'\] = (\d+)"),
                         self.r5['properties']['tasks']['maxItems'])
        decision = self.r5['$defs']['conditionDecision']
        self.assertEqual(sorted(decision['required']), ['reason', 'required'])
        self.assertIs(decision['additionalProperties'], False)

    def test_the_task_count_is_the_frozen_taskpack_s_count(self):
        self.assertEqual(len(read_json(R5_SOURCE)['tasks']), 28)
        self.assertEqual(self.r5['properties']['tasks']['minItems'], 28)
        self.assertEqual(self.r5['properties']['tasks']['maxItems'], 28)

    def test_the_evidence_array_is_not_count_pinned(self):
        """The ledger is being appended to while this schema exists; a maxItems here would be
        a date wearing a contract, and it would convict an honest new receipt."""
        self.assertNotIn('maxItems', self.r5['properties']['evidence'])
        self.assertEqual(self.r5['properties']['evidence']['minItems'], 1)

    def test_the_r5_contract_module_still_accepts_the_real_ledger(self):
        """Read-only cross-check: the procedural contract CI runs and my declarative schema
        agree on the live ledger. Shelled out rather than imported -- ``design_lab.governance``
        is an active concurrent-edit zone, and an import error in someone else's file must not
        turn this module into a pile of errors. Compared, not merged: that module owns the
        rules a JSON Schema cannot say."""
        script = ROOT / 'design-lab' / 'scripts' / 'verify_task_ledger_contract.py'
        result = subprocess.run([sys.executable, '-B', str(script)], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('TASK_LEDGER_CONTRACT=OK', result.stdout)


class MutatedFailureModes(unittest.TestCase):
    """Each shape defect, demonstrated against a copy."""

    def test_a_dropped_required_key_is_rejected(self):
        for key in ('definition', 'reassessment', 'predecessor_task_ids', 'required_axes'):
            ledger = ledger_document()
            del ledger['tasks'][3][key]
            joined = '\n'.join(run_on(ledger)['failures'])
            with self.subTest(key=key):
                self.assertIn(f'{key!r} is a required property', joined)

    def test_a_dropped_top_level_key_is_rejected(self):
        ledger = ledger_document()
        del ledger['predecessor']
        joined = '\n'.join(run_on(ledger)['failures'])
        self.assertIn("'predecessor' is a required property", joined)

    def test_a_task_id_the_pattern_rejects_is_rejected(self):
        ledger = ledger_document()
        ledger['tasks'][0]['id'] = 'DL-R5-029'
        joined = '\n'.join(run_on(ledger)['failures'])
        self.assertIn('does not match', joined)
        self.assertIn('DL-R5-029', joined)

    def test_a_predecessor_task_id_outside_the_r3_shape_is_rejected(self):
        ledger = ledger_document()
        ledger['tasks'][0]['predecessor_task_ids'] = ['DL-R5-001']
        self.assertIn('does not match', '\n'.join(run_on(ledger)['failures']))

    def test_a_forged_provenance_const_is_rejected(self):
        ledger = ledger_document()
        ledger['source']['sha256'] = '0' * 64
        self.assertIn('31dde89e', '\n'.join(run_on(ledger)['failures']))

    def test_a_zero_digest_artifact_is_rejected(self):
        ledger = ledger_document()
        ledger['evidence'][-1]['artifacts'][0]['sha256'] = '0' * 64
        self.assertIn('0000000000000000', '\n'.join(run_on(ledger)['failures']))

    def test_an_evidence_kind_outside_the_vocabulary_is_rejected(self):
        ledger = ledger_document()
        ledger['evidence'][-1]['kind'] = 'vibes'
        self.assertIn('is not one of', '\n'.join(run_on(ledger)['failures']))

    def test_a_receipt_with_no_subject_bytes_is_rejected(self):
        """subject_files is the only part of a record a stranger can recompute. The validator's
        wording for minProperties varies across jsonschema releases, so the assertion is on the
        path it convicts and on the schema rule, not on one vendor sentence."""
        schema = read_json(SCHEMA_R5)
        self.assertEqual(schema['$defs']['evidenceRecord']['properties']['subject_files']['minProperties'], 1)
        ledger = ledger_document()
        ledger['evidence'][-1]['subject_files'] = {}
        joined = '\n'.join(run_on(ledger)['failures'])
        self.assertIn('subject_files', joined)
        self.assertIn(f"/evidence/{len(ledger['evidence']) - 1}/subject_files", joined)

    def test_a_tampered_predecessor_hash_is_rejected(self):
        ledger = ledger_document()
        ledger['predecessor']['sha256'] = 'a' * 64
        self.assertIn('predecessor_sha256', '\n'.join(run_on(ledger)['failures']))

    def test_an_inline_predecessor_that_is_not_the_frozen_file_is_rejected(self):
        ledger = ledger_document()
        ledger['predecessor']['ledger']['tasks'][0]['title'] = 'rewritten history'
        joined = '\n'.join(run_on(ledger)['failures'])
        self.assertIn('predecessor_ledger', joined)
        self.assertIn('deep-equal', joined)

    def test_a_completion_state_on_an_unreviewed_task_still_needs_the_python_rule(self):
        """Documented division of labour: the schema cannot say "PASS requires REVIEWED", so
        r5_contract.py owns it and the schema must not pretend. Both halves are asserted."""
        schema = read_json(SCHEMA_R5)
        axis = schema['$defs']['axis']
        states = axis['properties']['state']['enum']
        self.assertIn('PASS', states)
        for keyword in ('if', 'then', 'else', 'dependentRequired', 'dependentSchemas'):
            self.assertNotIn(keyword, axis,
                             f'the schema should not fake {keyword}: r5_contract.py owns it')
        ledger = ledger_document()
        for task in ledger['tasks']:
            if any(axis['state'] in {'PASS', 'IMPLEMENTED_LOCAL'} for axis in task['axes'].values()):
                task['reassessment'] = 'PENDING_EVIDENCE_REVIEW'
                break
        else:
            self.fail('no task carries a completion state to test')
        self.assertEqual(run_on(ledger)['failures'], [],
                         'the shape is legal by design; r5_contract.py is what rejects it')
        # `r5_contract.validate` calls `current_execution.validate` before any R5 rule, and that
        # guard compares `ledger['tasks']` / `ledger['evidence']` against the frozen predecessor
        # snapshot -- the very field this fixture mutates. Dropping the partition removes only
        # the guard scoped to it; without the drop the assertion below fails with
        # `frozen predecessor partition changed: tasks` and never reaches the rule it names.
        ledger.pop('currentExecution', None)
        sys.path.insert(0, str(ROOT / 'src'))
        from design_lab.governance import reporting
        with self.assertRaisesRegex(Exception, 'reassessment'):
            reporting._validate(reporting.Reader(ROOT), ledger)


if __name__ == '__main__':
    unittest.main(verbosity=2)
