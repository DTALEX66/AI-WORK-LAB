# SPDX-License-Identifier: MIT
"""Teeth for src/design_lab/assurance/delivery_bom.py -- the module that refuses to invent a BOM.

The contract ``design-lab/schemas/bom.schema.json`` has existed since the handoff templates were
written, and until 2026-10-08 nothing in the product loaded it. The only ``bom`` in the code was a
three-key link fragment inside the preflight report, which the contract rejects -- so the declared
delivery bill was a document nobody could produce and no check would notice.

What this module does instead is state where every required field comes from, and stop when a field
has no source. The tests below are therefore mostly about the refusal: an implementation that filled
``provenance.boundTreeSha`` with the word ``unknown`` would satisfy the schema's ``minLength`` and
print a bill of materials that means nothing. Both paths are exercised -- the refusal, and the
rejection of the placeholder that a lazy fix would reach for.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from design_lab.assurance import delivery_bom  # noqa: E402
from design_lab.interop import load_schema  # noqa: E402

ATTESTED = {'handoff': 'handoff-2026-10-08', 'repo_tree_sha': 'e' * 40,
            'tool_version': 'psd-adapter-1.2.3', 'generated_at': '2026-10-08T03:00:00Z'}


def manifest(**overrides) -> dict:
    document = {
        'files': {
            'design.psd': {'role': 'primary', 'sha256': 'a' * 64},
            'preview.png': {'role': 'preview', 'sha256': 'b' * 64},
            'fonts/Inter.ttf': {'role': 'input', 'sha256': 'c' * 64},
        },
        'metadata': {'host': 'photoshop', 'host_version': '26.0',
                     'native_attempt_id': 'attempt-7f3', 'job_sha256': 'd' * 64,
                     'project_id': 'project-9', 'rights': 'CLEARED',
                     'input_assets': [{'member': 'fonts/Inter.ttf', 'id': 'asset-42'}]},
    }
    document.update(overrides)
    return document


def build(**overrides) -> dict:
    params = {'manifest': manifest()}
    params.update(overrides)
    params.setdefault('handoff', ATTESTED['handoff'])
    params.setdefault('repo_tree_sha', ATTESTED['repo_tree_sha'])
    params.setdefault('tool_version', ATTESTED['tool_version'])
    params.setdefault('generated_at', ATTESTED['generated_at'])
    return delivery_bom.build(**params)


class RefusalTests(unittest.TestCase):
    def test_nothing_can_be_attested_from_a_bundle_today_so_the_bill_is_declined(self) -> None:
        result = delivery_bom.build(manifest=manifest())
        self.assertEqual('DELIVERY_BOM_INCOMPLETE', result['status'])
        self.assertEqual(list(delivery_bom.UNATTESTED), result['missing'])
        self.assertEqual([], result['attested'])

    def test_every_unattested_field_carries_its_own_reason_not_a_generic_one(self) -> None:
        result = delivery_bom.build(manifest=manifest())
        for field, reason in result['reasons'].items():
            self.assertGreaterEqual(len(reason), 40, f'{field} reason is decorative')
            self.assertNotIn('unknown', reason.lower())

    def test_attesting_one_field_moves_it_from_missing_to_attested(self) -> None:
        result = delivery_bom.build(manifest=manifest(), handoff=ATTESTED['handoff'])
        self.assertEqual(['repo_tree_sha', 'tool_version', 'generated_at'], result['missing'])
        self.assertEqual(['handoff'], result['attested'])

    def test_whitespace_is_not_an_attestation(self) -> None:
        result = delivery_bom.build(manifest=manifest(), handoff='   ',
                                    repo_tree_sha=ATTESTED['repo_tree_sha'],
                                    tool_version=ATTESTED['tool_version'],
                                    generated_at=ATTESTED['generated_at'])
        self.assertEqual(['handoff'], result['missing'])

    def test_a_manifest_naming_no_files_says_there_is_no_bill_to_write(self) -> None:
        result = delivery_bom.build(manifest={'files': {}, 'metadata': {}}, **ATTESTED)
        self.assertEqual('DELIVERY_BOM_INCOMPLETE', result['status'])
        self.assertIn('items', result['missing'])
        self.assertIn('no files', result['reasons']['items'])


class AcceptedTests(unittest.TestCase):
    def test_with_every_field_attested_the_document_satisfies_the_contract(self) -> None:
        result = build()
        self.assertEqual('DELIVERY_BOM', result['status'], result.get('errors'))
        self.assertEqual(delivery_bom.bom_version(), result['version'])
        self.assertEqual(3, len(result['bom']['items']))

    def test_the_version_is_read_from_the_schema_not_typed_into_the_module(self) -> None:
        schema = load_schema(delivery_bom.BOM_SCHEMA_PATH)
        self.assertEqual(schema['properties']['version']['const'], delivery_bom.bom_version())
        self.assertEqual(delivery_bom.bom_version(), build()['bom']['version'])

    def test_a_schema_without_a_version_const_cannot_be_claimed(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / 'bom.schema.json'
            schema = {**load_schema(delivery_bom.BOM_SCHEMA_PATH)}
            schema['properties'] = {k: v for k, v in schema['properties'].items() if k != 'version'}
            path.write_text(json.dumps(schema), encoding='utf-8')
            original = delivery_bom.BOM_SCHEMA_PATH
            delivery_bom.BOM_SCHEMA_PATH = path
            try:
                with self.assertRaisesRegex(ValueError, 'no version const'):
                    delivery_bom.bom_version()
            finally:
                delivery_bom.BOM_SCHEMA_PATH = original

    def test_items_take_kind_from_role_and_format_from_the_member_suffix(self) -> None:
        by_path = {item['path']: item for item in build()['bom']['items']}
        self.assertEqual('export', by_path['design.psd']['kind'])
        self.assertEqual('derived', by_path['preview.png']['kind'])
        self.assertEqual('derived', by_path['fonts/Inter.ttf']['kind'])
        self.assertEqual('psd', by_path['design.psd']['format'])
        self.assertEqual('ttf', by_path['fonts/Inter.ttf']['format'])

    def test_a_member_without_a_suffix_says_unknown_instead_of_guessing_a_format(self) -> None:
        document = manifest(files={'design': {'role': 'primary', 'sha256': 'a' * 64}})
        item = build(manifest=document)['bom']['items'][0]
        self.assertEqual('unknown', item['format'])

    def test_an_input_is_billed_to_its_registered_asset_and_a_render_to_its_attempt(self) -> None:
        by_path = {item['path']: item for item in build()['bom']['items']}
        self.assertEqual('asset-42', by_path['fonts/Inter.ttf']['source'])
        self.assertEqual('native-attempt:attempt-7f3/photoshop', by_path['design.psd']['source'])

    def test_an_input_with_no_registered_asset_says_so_instead_of_inventing_one(self) -> None:
        document = manifest(metadata={**manifest()['metadata'], 'input_assets': []})
        by_path = {item['path']: item
                   for item in build(manifest=document)['bom']['items']}
        self.assertEqual('unregistered-input:fonts/Inter.ttf', by_path['fonts/Inter.ttf']['source'])

    def test_the_license_is_what_rights_recorded_and_never_a_plausible_spdx_id(self) -> None:
        by_path = {item['path']: item for item in build()['bom']['items']}
        self.assertEqual('CLEARED', by_path['design.psd']['license'])
        document = manifest(metadata={k: v for k, v in manifest()['metadata'].items()
                                      if k != 'rights'})
        unreviewed = {item['path']: item for item in build(manifest=document)['bom']['items']}
        self.assertEqual('NOT_REVIEWED', unreviewed['design.psd']['license'])


class RejectionTests(unittest.TestCase):
    def test_a_placeholder_in_place_of_a_tree_sha_is_rejected_not_accepted(self) -> None:
        """The lazy fix for the refusal: write 'unknown'. The contract's minLength is the guard."""
        result = build(repo_tree_sha='unknown')
        self.assertEqual('DELIVERY_BOM_REJECTED', result['status'])
        self.assertTrue(any('boundTreeSha' in error for error in result['errors']), result['errors'])

    def test_an_extra_field_the_closed_contract_forbids_is_rejected(self) -> None:
        original = delivery_bom.items
        delivery_bom.items = lambda manifest: [{**original(manifest)[0], 'note': 'extra'}]
        try:
            result = build()
        finally:
            delivery_bom.items = original
        self.assertEqual('DELIVERY_BOM_REJECTED', result['status'])
        self.assertIn('note', result['errors'][0])

    def test_an_empty_digest_is_rejected_rather_than_ignored(self) -> None:
        document = manifest(files={'design.psd': {'role': 'primary', 'sha256': ''}})
        result = build(manifest=document, **ATTESTED)
        self.assertEqual('DELIVERY_BOM_REJECTED', result['status'])
        self.assertTrue(any('sha256' in error for error in result['errors']), result['errors'])


class SummaryTests(unittest.TestCase):
    def test_each_status_gets_a_sentence_that_says_what_was_done(self) -> None:
        self.assertIn('交付清单已按', delivery_bom.summary(build()))
        rejected = build(repo_tree_sha='unknown')
        self.assertIn('未通过合同', delivery_bom.summary(rejected))
        declined = delivery_bom.build(manifest=manifest())
        sentence = delivery_bom.summary(declined)
        self.assertIn('无法写成', sentence)
        for field in declined['missing']:
            self.assertIn(field, sentence)


if __name__ == '__main__':
    unittest.main()
