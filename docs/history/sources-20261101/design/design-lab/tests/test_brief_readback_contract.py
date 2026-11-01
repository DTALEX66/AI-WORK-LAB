# SPDX-License-Identifier: MIT
"""Teeth for the brief readback contract (design-lab/schemas/brief-readback.schema.json).

The brief list the Workbench pages through used to be described only by a TypeScript interface in
shell.ts, and ``design-brief.schema.json`` -- the file the object model names for the brief -- declares
a content model (discipline, objective, audience, deliverables) that no code in this repository stores.
So the payload had no contract while a contract existed for a payload nobody serves.

``design_layer._check_brief_readback`` now judges every brief record and the list envelope against the
schema on the way out. These tests exist because that is only worth anything if it can fail: each one
mutates the emitted record the way a future edit would (a renamed key, a dropped ``sha256:`` prefix,
an empty goal list, a version that is 0) and asserts the refusal is named and carries the field path.
The last case proves the guard reads the file rather than a constant: point it at a schema with no
record definition and it must say so instead of passing everything.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from design_lab import design_layer  # noqa: E402
from design_lab.interop import load_schema  # noqa: E402

SCHEMA_PATH = design_layer.BRIEF_READBACK_SCHEMA_PATH
RECORD_FIELDS = ('brief_id', 'title', 'goals', 'constraints', 'reference_asset_ids',
                 'spec_sha256', 'version', 'superseded_by', 'created_at')


def record(**overrides) -> dict:
    """One brief record exactly as ``DesignLayer._brief`` emits it."""
    base = {
        'brief_id': 'brief-' + 'a' * 32,
        'title': 'Launch poster',
        'goals': ['modern', 'warm'],
        'constraints': 'single-colour print',
        'reference_asset_ids': ['img-' + 'b' * 64],
        'spec_sha256': 'sha256:' + 'c' * 64,
        'version': 1,
        'superseded_by': None,
        'created_at': '2026-10-08T04:00:00Z',
    }
    base.update(overrides)
    return base


def envelope(*records) -> dict:
    return {'schemaVersion': design_layer.BRIEF_READBACK_SCHEMA_VERSION,
            'briefs': list(records), 'next_cursor': None}


class SchemaShapeTests(unittest.TestCase):
    def test_the_shipped_schema_pins_the_envelope_and_every_record_field(self) -> None:
        schema = load_schema(SCHEMA_PATH)
        self.assertEqual(['schemaVersion', 'briefs', 'next_cursor'], schema['required'])
        self.assertIs(False, schema['additionalProperties'],
                      'an open envelope would let a renamed field pass unnoticed')
        brief = schema['$defs']['brief']
        self.assertEqual(sorted(RECORD_FIELDS), sorted(brief['required']))
        self.assertIs(False, brief['additionalProperties'])

    def test_the_version_is_one_value_on_both_sides(self) -> None:
        schema = load_schema(SCHEMA_PATH)
        self.assertEqual(schema['properties']['schemaVersion']['const'],
                         design_layer.BRIEF_READBACK_SCHEMA_VERSION)

    def test_the_envelope_version_literal_is_written_in_the_emitter_not_in_a_scratch_file(self) -> None:
        source = (REPO / 'src/design_lab/design_layer.py').read_text(encoding='utf-8')
        self.assertIn(f"BRIEF_READBACK_SCHEMA_VERSION = '{design_layer.BRIEF_READBACK_SCHEMA_VERSION}'",
                      source)

    def test_a_real_record_and_a_real_envelope_pass(self) -> None:
        self.assertEqual(design_layer._check_brief_readback(record(), envelope=False), record())
        self.assertEqual(design_layer._check_brief_readback(envelope(record()), envelope=True),
                         envelope(record()))

    def test_an_empty_list_is_served_not_refused(self) -> None:
        """A project with no briefs answers an empty page; that is not a contract violation."""
        self.assertEqual([], design_layer._check_brief_readback(envelope(), envelope=True)['briefs'])


class RefusalTests(unittest.TestCase):
    def check(self, mutated, *, envelope_mode=False):
        """Judge the payload exactly as given.

        ``envelope_mode`` only chooses which half of the schema is applied, so an envelope test has
        to build its own envelope: wrapping it here would compare a record against a record and read
        as a pass for the wrong reason.
        """
        with self.assertRaises(design_layer.DesignLayerError) as caught:
            design_layer._check_brief_readback(mutated, envelope=envelope_mode)
        self.assertEqual(500, caught.exception.status)
        self.assertEqual('BRIEF_CONTRACT_VIOLATION', caught.exception.code)
        return caught.exception.detail

    def test_a_renamed_key_is_refused_with_the_field_path(self) -> None:
        mutated = record()
        mutated['specHash'] = mutated.pop('spec_sha256')
        detail = self.check(mutated)
        self.assertTrue(any('spec_sha256' in problem for problem in detail), detail)

    def test_a_digest_without_the_sha256_prefix_is_refused(self) -> None:
        detail = self.check(record(spec_sha256='c' * 64))
        self.assertTrue(any('spec_sha256' in problem for problem in detail), detail)

    def test_an_empty_goal_list_is_refused_rather_than_read_as_no_goals(self) -> None:
        """The writer requires goals, so a served record with none means the row was not written here."""
        detail = self.check(record(goals=[]))
        self.assertTrue(any('goals' in problem for problem in detail), detail)

    def test_a_blank_title_is_refused(self) -> None:
        self.check(record(title=''))

    def test_version_zero_is_refused(self) -> None:
        detail = self.check(record(version=0))
        self.assertTrue(any('version' in problem for problem in detail), detail)

    def test_an_extra_field_a_closed_record_forbids_is_refused(self) -> None:
        detail = self.check({**record(), 'notes': 'sneaked in'})
        self.assertTrue(any('notes' in problem for problem in detail), detail)

    def test_a_malformed_brief_id_is_refused(self) -> None:
        self.check(record(brief_id='brief-zz'))

    def test_a_missing_envelope_version_is_refused(self) -> None:
        mutated = envelope(record())
        mutated.pop('schemaVersion')
        detail = self.check(mutated, envelope_mode=True)
        self.assertTrue(any('schemaVersion' in problem for problem in detail), detail)

    def test_a_wrong_envelope_version_is_refused(self) -> None:
        detail = self.check({**envelope(record()), 'schemaVersion': 'design-lab/brief-readback/v2'},
                            envelope_mode=True)
        self.assertTrue(any('schemaVersion' in problem for problem in detail), detail)

    def test_a_next_cursor_that_is_not_a_brief_id_is_refused(self) -> None:
        self.check({**envelope(record()), 'next_cursor': 'anything'}, envelope_mode=True)


class GuardIsLiveTests(unittest.TestCase):
    def test_the_guard_reads_the_shipped_file_not_a_bundled_constant(self) -> None:
        """Point it at a schema with no record definition and it must say so, not pass everything."""
        original = design_layer.BRIEF_READBACK_SCHEMA_PATH
        scratch = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        try:
            hollow = scratch / 'brief-readback.schema.json'
            hollow.write_text(json.dumps({'$schema': 'https://json-schema.org/draft/2020-12/schema',
                                          '$id': 'https://x.invalid/brief-readback.json',
                                          'type': 'object'}), encoding='utf-8')
            design_layer.BRIEF_READBACK_SCHEMA_PATH = hollow
            with self.assertRaisesRegex(design_layer.DesignLayerError, 'no \\$defs.brief record'):
                design_layer._check_brief_readback(record(), envelope=False)
        finally:
            design_layer.BRIEF_READBACK_SCHEMA_PATH = original
            import shutil
            shutil.rmtree(scratch, ignore_errors=True)

    def test_the_three_brief_reads_all_run_the_guard(self) -> None:
        """list, get and lineage each call it; a silent omission on one path is the whole gap."""
        source = (REPO / 'src/design_lab/design_layer.py').read_text(encoding='utf-8')
        for name in ('def list_briefs', 'def get_brief', 'def lineage_brief'):
            start = source.index(name)
            body = source[start:start + 1400]
            self.assertIn('_check_brief_readback', body, f'{name} no longer judges its payload')


class ProductProofTests(unittest.TestCase):
    """The guard is proven against a real record produced by the real write path."""

    def setUp(self) -> None:
        self.saved = os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        project = self.base / 'project'
        (project / 'design-lab' / 'config').mkdir(parents=True)
        (project / '.project').mkdir(parents=True)
        (project / 'AGENTS.md').write_text('# brief readback contract fixture', encoding='utf-8')
        from design_lab.service import ProjectService
        self.service = ProjectService(project)
        self.layer = design_layer.DesignLayer(self.service)
        self.project_id = self.service.create_project('Brief Contract')['id']

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.base, ignore_errors=True)
        if self.saved is not None:
            os.environ['PROJECT_LOCAL_ROOT'] = self.saved

    def test_a_brief_written_and_read_back_satisfies_the_contract(self) -> None:
        created = self.layer.create_brief(self.project_id, title='Poster', goals=['warm'],
                                          constraints=None, reference_asset_ids=[],
                                          idempotency_key='k-1')
        self.assertEqual('brief-', created['brief']['brief_id'][:6])
        listed = self.layer.list_briefs(self.project_id)
        self.assertEqual(design_layer.BRIEF_READBACK_SCHEMA_VERSION, listed['schemaVersion'])
        self.assertEqual(1, len(listed['briefs']))
        read = self.layer.get_brief(self.project_id, created['brief']['brief_id'])
        self.assertEqual(created['brief']['spec_sha256'], read['brief']['spec_sha256'])
        chain = self.layer.lineage_brief(self.project_id, created['brief']['brief_id'])
        self.assertEqual([1], [item['version'] for item in chain['lineage']['versions']])

    def test_a_row_whose_stored_bytes_no_longer_match_the_contract_is_refused(self) -> None:
        """Simulate the divergence this guard exists for: the writer changed, the contract did not.

        The class attribute is taken and put back from ``__dict__`` on purpose. ``DesignLayer._brief``
        reads as a plain function, so assigning that back installs an unbound function on the class --
        which then binds ``self`` as the first argument and every later call in the process dies with
        "takes 1 positional argument but 2 were given". That is exactly how this one test put 47
        failures across three other modules into a bound run while passing alone.
        """
        self.layer.create_brief(self.project_id, title='Poster', goals=['warm'], constraints=None,
                               reference_asset_ids=[], idempotency_key='k-2')
        holder = design_layer.DesignLayer.__dict__['_brief']
        try:
            def mutated(row):
                record = holder.__func__(row)
                record.pop('created_at')
                return record
            design_layer.DesignLayer._brief = staticmethod(mutated)
            with self.assertRaises(design_layer.DesignLayerError) as caught:
                self.layer.list_briefs(self.project_id)
        finally:
            design_layer.DesignLayer._brief = holder
        self.assertIsInstance(design_layer.DesignLayer.__dict__['_brief'], staticmethod,
                              'the restore must leave a staticmethod, not a bare function')
        self.assertEqual('BRIEF_CONTRACT_VIOLATION', caught.exception.code)
        self.assertTrue(any('created_at' in problem for problem in caught.exception.detail),
                        caught.exception.detail)


if __name__ == '__main__':
    unittest.main()
