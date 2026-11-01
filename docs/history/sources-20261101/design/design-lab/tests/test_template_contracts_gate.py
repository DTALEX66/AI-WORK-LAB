# SPDX-License-Identifier: MIT
"""Teeth for design-lab/scripts/verify_template_contracts.py.

The gate's claim is that a copyable template cannot be the source of an invalid record. Measured
before the gate existed, all three templates in the repository were broken and none of the breaks
were visible: one pointed at a path outside the checkout, one was rejected three times by the schema
it names, and one named no contract at all. Each mutation below is the lie the corresponding rule is
supposed to catch, checked on a scratch tree so the shipped files are never the only thing exercised
-- a gate that has only ever printed OK over three known-broken inputs is not evidence of anything.

Two properties got their own tests because they bit while writing this: the pointer resolves under
both conventions actually in use (file-relative ``$schema`` and repo-root ``rubric``), and a schema
with an unresolvable ``$ref`` is reported instead of raising, because jsonschema reaches for the
network for such a reference and a crashed gate reads the same as a clean one.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_PATH = REPO / 'design-lab' / 'scripts' / 'verify_template_contracts.py'
SCRATCH_BASE = (REPO / '.project-local' / 'task-runtime'
                / f'template-contracts-scratch-p{os.getpid()}')

DRAFT = 'https://json-schema.org/draft/2020-12/schema'
TEMPLATE_REL = 'design-lab/templates/thing.template.json'
SCHEMA_REL = 'design-lab/schemas/thing.schema.json'
RUBRIC_REL = 'design-lab/evals/rubrics/core.rubric.json'

THING_SCHEMA = {
    '$schema': DRAFT,
    '$id': 'https://example.invalid/schemas/thing.schema.json',
    'type': 'object',
    'required': ['version', 'label'],
    'properties': {
        '$schema': {'type': 'string'},
        'version': {'const': 'thing/v1'},
        'label': {'type': 'string', 'minLength': 1},
    },
    'additionalProperties': False,
}


def load_gate():
    spec = importlib.util.spec_from_file_location('verify_template_contracts', GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GATE = load_gate()


def write_json(root: Path, rel: str, document) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = document if isinstance(document, str) else json.dumps(document, indent=2)
    path.write_text(text, encoding='utf-8')
    return path


def good_template() -> dict:
    return {'$schema': '../schemas/thing.schema.json', 'version': 'thing/v1', 'label': 'replace-me'}


def score_template() -> dict:
    return {'rubric': 'design-lab/evals/rubrics/core.rubric.json',
            'scores': {'alpha': 0, 'beta': 0}}


class ScratchCase(unittest.TestCase):
    """One scratch repository per test, removed with the process' own directory."""

    def setUp(self) -> None:
        self.root = SCRATCH_BASE / self.id().split('.')[-1]
        if self.root.exists():
            shutil.rmtree(self.root)
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        write_json(self.root, SCHEMA_REL, THING_SCHEMA)

    def build(self, template: dict | str, *, rel: str = TEMPLATE_REL,
              inventory: tuple[str, ...] = (TEMPLATE_REL,)) -> dict:
        write_json(self.root, rel, template)
        return GATE.audit(self.root, inventory)

    def rules(self, result: dict) -> list[str]:
        """The rule name each error line asserts.

        Error text is ``<path>: <RULE>: <detail>`` for a per-template finding and ``<RULE>: ...`` for
        a scan-level one, so the rule is the colon-separated segment that is nothing but an all-caps
        identifier -- a plain split would return the file path instead.
        """
        found = []
        for error in result['errors']:
            for part in error.split(': '):
                if re.fullmatch(r'[A-Z][A-Z_]+', part):
                    found.append(part)
                    break
        return found


class ShippedTreeTests(ScratchCase):
    def test_the_shipped_templates_now_all_satisfy_their_own_contracts(self) -> None:
        result = GATE.audit(REPO)
        self.assertEqual([], result['errors'])
        self.assertEqual(3, result['templates'])
        self.assertEqual({'OK'}, {row['state'] for row in result['rows']})

    def test_the_gate_cites_the_contract_it_checked_for_every_template(self) -> None:
        result = GATE.audit(REPO)
        for row in result['rows']:
            self.assertTrue(row['pointers'], f"{row['template']} passed without a resolved pointer")
        resolved = {name for row in result['rows'] for name in row['pointers'].values()}
        self.assertIn('design-lab/schemas/bom.schema.json', resolved)
        self.assertIn('design-lab/schemas/jury-record.schema.json', resolved)

    def test_the_verdict_line_counts_what_it_scanned(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = GATE.main([])
        out = buffer.getvalue()
        self.assertEqual(0, code)
        self.assertIn('TEMPLATE_CONTRACTS=OK templates=3 clean=3', out)
        for pinned in GATE.INVENTORY:
            self.assertIn(pinned, out)

    def test_the_repair_is_visible_in_the_templates_themselves(self) -> None:
        """A template that pre-fills a passing verdict would hand a false green to whoever copies it."""
        jury = json.loads((REPO / 'packages/capabilities/quality/jury'
                           / 'JuryRecord.template.json').read_text(encoding='utf-8'))
        self.assertNotIn('OK', jury['deterministic']['result'])
        self.assertEqual('REVISE', jury['verdict'])
        self.assertEqual('REVISE', jury['humanReview']['verdict'])
        self.assertTrue(all(score == 1 for score in jury['axes'].values()))
        bom = json.loads((REPO / 'design-lab/production/handoff'
                          / 'BOM.template.json').read_text(encoding='utf-8'))
        self.assertEqual('design-lab/bom/v1', bom['version'])
        self.assertIn(bom['items'][0]['kind'], ['editable-source', 'export', 'derived'])


class PointerTests(ScratchCase):
    def test_a_valid_template_on_a_scratch_tree_passes(self) -> None:
        result = self.build(good_template())
        self.assertEqual([], result['errors'])
        self.assertEqual({TEMPLATE_REL: 'design-lab/schemas/thing.schema.json'},
                         {row['template']: list(row['pointers'].values())[0]
                          for row in result['rows']})

    def test_a_repo_root_relative_pointer_is_honoured(self) -> None:
        """The score sheet writes its rubric path from the repository root; that must not be a lie."""
        write_json(self.root, RUBRIC_REL, {'id': 'core', 'axes': [{'id': 'alpha'}, {'id': 'beta'}]})
        result = self.build(score_template())
        self.assertEqual([], result['errors'])

    def test_a_template_naming_no_contract_is_red(self) -> None:
        template = {'version': 'thing/v1', 'label': 'replace-me'}
        result = self.build(template)
        self.assertEqual(['NO_CONTRACT_POINTER'], self.rules(result))

    def test_a_pointer_to_a_missing_file_is_red(self) -> None:
        template = good_template()
        template['$schema'] = '../schemas/nope.schema.json'
        result = self.build(template)
        self.assertEqual(['POINTER_UNRESOLVED'], self.rules(result))

    def test_a_pointer_that_climbs_out_of_the_checkout_is_red(self) -> None:
        template = good_template()
        template['$schema'] = '../../../../../../escaped.schema.json'
        result = self.build(template)
        self.assertEqual(['POINTER_OUTSIDE_REPO'], self.rules(result))

    def test_a_pointer_to_a_remote_url_is_red_and_is_never_fetched(self) -> None:
        template = good_template()
        template['$schema'] = 'https://example.invalid/thing.schema.json'
        result = self.build(template)
        self.assertEqual(['POINTER_OUTSIDE_REPO'], self.rules(result))


class ValidationTests(ScratchCase):
    def test_a_schema_that_is_not_draft_2020_12_is_red(self) -> None:
        write_json(self.root, SCHEMA_REL, {**THING_SCHEMA, '$schema': 'http://json-schema.org/'
                                           'draft-07/schema#'})
        result = self.build(good_template())
        self.assertEqual(['SCHEMA_UNLOADABLE'], self.rules(result))

    def test_an_extra_field_a_closed_schema_forbids_is_red(self) -> None:
        template = {**good_template(), 'surprise': 'x'}
        result = self.build(template)
        self.assertEqual(['TEMPLATE_INVALID'], self.rules(result))

    def test_a_version_that_disagrees_with_the_pinned_const_is_red(self) -> None:
        """This is the BOM template's real defect: 1.0.0 where the contract pins design-lab/bom/v1."""
        template = {**good_template(), 'version': 'thing/v2'}
        result = self.build(template)
        self.assertEqual(['TEMPLATE_INVALID'], self.rules(result))
        self.assertIn('version', result['errors'][0])

    def test_a_placeholder_outside_a_closed_enum_is_red(self) -> None:
        schema = {**THING_SCHEMA, 'properties': {**THING_SCHEMA['properties'],
                                                 'label': {'enum': ['a', 'b']}}}
        write_json(self.root, SCHEMA_REL, schema)
        result = self.build({**good_template(), 'label': 'a | b'})
        self.assertEqual(['TEMPLATE_INVALID'], self.rules(result))

    def test_an_unresolvable_ref_is_reported_instead_of_crashing_the_gate(self) -> None:
        schema = {**THING_SCHEMA, 'properties': {**THING_SCHEMA['properties'],
                                                 'label': {'$ref': 'https://nowhere.invalid/x'}}}
        write_json(self.root, SCHEMA_REL, schema)
        result = self.build(good_template())
        self.assertEqual(['SCHEMA_REF_UNRESOLVABLE'], self.rules(result))


class RubricTests(ScratchCase):
    def setUp(self) -> None:
        super().setUp()
        write_json(self.root, RUBRIC_REL, {'id': 'core',
                                           'axes': [{'id': 'alpha'}, {'id': 'beta'}]})

    def test_a_sheet_billing_a_dimension_the_rubric_does_not_define_is_red(self) -> None:
        template = score_template()
        template['scores'] = {'alpha': 0, 'gamma': 0}
        result = self.build(template)
        self.assertEqual(['RUBRIC_AXES_MISMATCH'], self.rules(result))
        self.assertIn('beta', result['errors'][0])
        self.assertIn('gamma', result['errors'][0])

    def test_a_rubric_declaring_no_axes_cannot_back_a_sheet(self) -> None:
        write_json(self.root, RUBRIC_REL, {'id': 'core', 'axes': []})
        result = self.build(score_template())
        self.assertEqual(['RUBRIC_HAS_NO_AXES'], self.rules(result))

    def test_a_sheet_naming_a_rubric_without_scores_is_red(self) -> None:
        template = {'rubric': RUBRIC_REL}
        result = self.build(template)
        self.assertEqual(['RUBRIC_AXES_MISMATCH'], self.rules(result))


class UnreadableTests(ScratchCase):
    def test_a_template_that_is_not_json_is_red(self) -> None:
        result = self.build('{ "version": ')
        self.assertEqual(['TEMPLATE_NOT_JSON'], self.rules(result))

    def test_a_template_that_is_not_an_object_is_red(self) -> None:
        result = self.build('[1, 2, 3]')
        self.assertEqual(['TEMPLATE_NOT_OBJECT'], self.rules(result))


class InventoryTests(ScratchCase):
    def test_an_empty_scan_is_a_failure_not_a_pass(self) -> None:
        result = GATE.audit(self.root, inventory=())
        self.assertIn('NOTHING_SCANNED', self.rules(result))

    def test_a_pinned_template_that_was_deleted_is_red(self) -> None:
        """Both directions: a pinned row that vanished, and a file nobody pinned."""
        result = self.build(good_template(), rel='design-lab/templates/other.template.json',
                            inventory=(TEMPLATE_REL,))
        self.assertEqual(['INVENTORY_MOVED', 'INVENTORY_MOVED'], self.rules(result))
        self.assertIn(TEMPLATE_REL, result['errors'][0])
        self.assertIn('design-lab/templates/other.template.json', result['errors'][1])

    def test_a_new_template_is_not_absorbed_silently(self) -> None:
        result = self.build(good_template(), inventory=())
        self.assertEqual(['INVENTORY_MOVED'], self.rules(result))

    def test_the_shipped_inventory_names_files_that_exist(self) -> None:
        for rel in GATE.INVENTORY:
            self.assertTrue((REPO / rel).is_file(), f'{rel} is pinned but absent')


class SurgicalityTests(ScratchCase):
    def test_one_lie_produces_one_line(self) -> None:
        """The gate must not convict a template twice for the same defect, or a reader cannot count."""
        template = good_template()
        template['version'] = 'thing/v9'
        result = self.build(template)
        self.assertEqual(1, len(result['errors']), result['errors'])

    def test_the_walk_skips_build_residue_and_only_takes_template_files(self) -> None:
        """A template copied into a dependency tree by a build is not a contract anyone maintains.

        The shipped tree is also what this checks: the gate's own source names every broken pointer
        in its docstring, so a scan that read ``.py`` text would convict or bless files by quoting
        itself. The walk is restricted to ``*.template.json`` and to the pinned scopes.
        """
        residue = self.root / 'design-lab' / 'node_modules' / 'pkg'
        residue.mkdir(parents=True)
        shutil.copy(GATE_PATH, residue / 'thing.template.json')
        (self.root / 'design-lab' / 'templates').mkdir(parents=True, exist_ok=True)
        (self.root / 'design-lab' / 'templates' / 'notes.md').write_text('# just notes',
                                                                        encoding='utf-8')
        result = GATE.audit(self.root, inventory=())
        self.assertEqual([], result['rows'])
        self.assertEqual(['NOTHING_SCANNED'], self.rules(result))


if __name__ == '__main__':
    unittest.main()
