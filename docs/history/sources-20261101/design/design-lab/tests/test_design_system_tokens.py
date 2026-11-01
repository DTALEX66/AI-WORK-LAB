# SPDX-License-Identifier: MIT
"""Design-system TOKEN documents: the write path, its versions and its refusals.

This is the chain the product did not have (measured in
``docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/findings/W06-TOKEN-WRITE-GAP.md``
as G1/G2/G3/G4): a design system had a BINDING but no writable, versioned,
readable-back token VALUES. The tests below drive the service method directly --
contract -> service write -> persisted row -> restart readback -- and pin every
refusal reason separately, because a chain that only works when the input is good
is not a chain, it is a demo.

What is claimed: E1 structural contract + E2-controlled local persistence of a
synthetic document through the real SQLite state database. What is NOT claimed:
no host (Figma/Penpot/Style Dictionary) round trip, no token-tool run, no jury
acceptance, no release. Readback here is the persisted row, nothing more.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

# A canonical DTCG 2025.10 document: $type inheritance, a resolvable alias and a
# full five-member typography composite.
TOKENS = {
    'color': {
        '$type': 'color',
        'brand': {'$value': '#2563EB'},
        'surface': {'$value': '{color.brand}'},
    },
    'scale': {
        '$type': 'dimension',
        'space': {'md': {'$value': '16px'}},
    },
    'font': {
        'body': {'$type': 'typography', '$value': {
            'fontFamily': 'Inter', 'fontSize': '16px', 'fontWeight': 400,
            'letterSpacing': '0px', 'lineHeight': 1.5}},
    },
}
DESIGN_SYSTEM = 'uiux-commercial-light'
_DEFAULT = object()


def _writer(layer, project_id, *, document=_DEFAULT, expected_version=0,
            actor='ALEX', actor_kind='human', key='tok-1', name=DESIGN_SYSTEM):
    return layer.write_tokens(
        project_id, name, document=TOKENS if document is _DEFAULT else document,
        expected_version=expected_version, actor=actor, actor_kind=actor_kind,
        idempotency_key=key)


class TokenWriteTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'src'))
        self.addCleanup(sys.path.remove, str(ROOT / 'src'))
        parent = ROOT / '.project-local' / 'task-runtime' / 'design-system-token-tests'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'AGENTS.md').write_text('# synthetic design-system token project',
                                             encoding='utf-8')
        env = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(self.root / '.project-local')})
        env.start()
        self.addCleanup(env.stop)
        self._service = None
        self.project_id = self.new_service().create_project('Token chain')['id']

    def new_service(self):
        """A fresh ProjectService over the same root -- the restart seam."""
        from design_lab.service import ProjectService
        self._service = ProjectService(str(self.root))
        return self._service

    def layer(self):
        from design_lab.design_layer import DesignLayer
        return DesignLayer(self._service)

    def db(self):
        return sqlite3.connect(str(self._service.database))

    # -- the chain ----------------------------------------------------------
    def test_write_persists_and_reads_back_after_a_restart(self):
        written = _writer(self.layer(), self.project_id)['token_document']
        self.assertEqual(written['version'], 1)
        self.assertEqual(written['design_system_name'], DESIGN_SYSTEM)
        self.assertEqual(written['document'], TOKENS)
        self.assertEqual(written['token_count'], 4)
        self.assertEqual(written['dtcg_schema_version'], '2025.10')
        self.assertTrue(written['spec_sha256'].startswith('sha256:'))
        self.assertIsNone(written['superseded_by'])

        # A NEW service instance over the same root: the row is the truth, not the
        # object that wrote it.
        self.new_service()
        readback = self.layer().get_tokens(self.project_id, DESIGN_SYSTEM)['token_document']
        self.assertEqual(readback, written)
        listed = self.layer().list_token_documents(self.project_id)['token_documents']
        self.assertEqual([row['token_document_id'] for row in listed], [written['token_document_id']])

    def test_each_write_appends_a_version_and_supersedes_only_the_pointer(self):
        layer = self.layer()
        first = _writer(layer, self.project_id)['token_document']
        revised = json.loads(json.dumps(TOKENS))
        revised['scale']['space']['md']['$value'] = '20px'
        second = _writer(layer, self.project_id, document=revised,
                         expected_version=first['version'], key='tok-2')['token_document']
        self.assertEqual(second['version'], 2)
        self.assertEqual(second['document']['scale']['space']['md']['$value'], '20px')

        conn = self.db()
        rows = {row[0]: row for row in conn.execute(
            "SELECT token_document_id, version, superseded_by, document_json, spec_sha256,"
            " actor, created_at FROM design_system_token ORDER BY version")}
        conn.close()
        self.assertEqual(rows[first['token_document_id']][1], 1)
        # The live tip is the second row; the first row's ONLY changed column is
        # superseded_by -- its content bytes and digest are untouched.
        self.assertEqual(rows[first['token_document_id']][2], second['token_document_id'])
        self.assertEqual(json.loads(rows[first['token_document_id']][3]), TOKENS)
        self.assertEqual(rows[first['token_document_id']][4],
                         first['spec_sha256'].removeprefix('sha256:'))
        self.assertIsNone(rows[second['token_document_id']][2])
        lineage = self.layer().token_lineage(self.project_id, DESIGN_SYSTEM)['lineage']
        self.assertEqual([v['version'] for v in lineage['versions']], [1, 2])
        self.assertEqual(lineage['root_id'], first['token_document_id'])
        self.assertEqual(lineage['live_id'], second['token_document_id'])

    def test_a_recorded_version_cannot_be_rewritten_in_place(self):
        """Append-only is a database property, not a convention this module obeys."""
        written = _writer(self.layer(), self.project_id)['token_document']
        conn = self.db()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE design_system_token SET document_json='{}'"
                         " WHERE token_document_id=?", (written['token_document_id'],))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM design_system_token WHERE token_document_id=?",
                         (written['token_document_id'],))
        conn.rollback()
        # superseded_by is the one column a revision may move, and only to a real row.
        conn.execute("UPDATE design_system_token SET superseded_by=? WHERE token_document_id=?",
                     ('tokdoc-' + '0' * 32, written['token_document_id']))
        conn.rollback()
        conn.close()

    def test_idempotent_replay_returns_the_same_version_and_appends_nothing(self):
        layer = self.layer()
        first = _writer(layer, self.project_id)['token_document']
        again = _writer(layer, self.project_id)['token_document']
        self.assertEqual(again, first)
        conn = self.db()
        count = conn.execute("SELECT COUNT(*) FROM design_system_token").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_a_replayed_key_with_different_content_conflicts(self):
        from design_lab.design_layer import DesignLayerError
        layer = self.layer()
        _writer(layer, self.project_id)
        revised = json.loads(json.dumps(TOKENS))
        revised['color']['brand']['$value'] = '#111827'
        with self.assertRaises(DesignLayerError) as caught:
            _writer(layer, self.project_id, document=revised, key='tok-1')
        self.assertEqual((caught.exception.status, caught.exception.code),
                         (409, 'IDEMPOTENCY_CONFLICT'))

    # -- the refusals -------------------------------------------------------
    def test_unknown_design_system_is_refused_and_nothing_is_written(self):
        from design_lab.design_layer import DesignLayerError
        with self.assertRaises(DesignLayerError) as caught:
            _writer(self.layer(), self.project_id, name='not-in-the-catalog')
        self.assertEqual((caught.exception.status, caught.exception.code),
                         (400, 'UNKNOWN_DESIGN_SYSTEM'))
        self.assertEqual(self.layer().list_token_documents(self.project_id)['token_documents'], [])

    def test_schema_invalid_document_is_refused_with_field_paths(self):
        from design_lab.design_layer import DesignLayerError
        broken = json.loads(json.dumps(TOKENS))
        broken['color']['brand']['$value'] = 12           # not a color, wrong type
        del broken['scale']
        broken['$unknown'] = 'nope'                       # not a DTCG document member
        with self.assertRaises(DesignLayerError) as caught:
            _writer(self.layer(), self.project_id, document=broken)
        error = caught.exception
        self.assertEqual((error.status, error.code), (400, 'TOKEN_DOCUMENT_INVALID'))
        self.assertTrue(error.detail, 'a refusal the reviewer cannot act on is not a refusal')
        self.assertTrue(any('$unknown' in item for item in error.detail), error.detail)
        self.assertEqual(self.layer().list_token_documents(self.project_id)['token_documents'], [])

    def test_semantic_failure_is_refused_with_the_path_that_failed(self):
        from design_lab.design_layer import DesignLayerError
        broken = json.loads(json.dumps(TOKENS))
        broken['color']['surface']['$value'] = '{color.missing}'
        with self.assertRaises(DesignLayerError) as caught:
            _writer(self.layer(), self.project_id, document=broken)
        self.assertEqual(caught.exception.code, 'TOKEN_DOCUMENT_INVALID')
        self.assertIn('color.missing', ' '.join(caught.exception.detail))

    def test_a_legacy_document_is_refused_and_not_silently_adapted(self):
        """The in-repo converter emits pre-2025.10 types; adapting server-side
        would write values the reviewer never typed, so the canonical path refuses."""
        from design_lab.design_layer import DesignLayerError
        legacy = json.loads(json.dumps(TOKENS))
        legacy['text'] = {'$type': 'string', 'body': {'$value': 'hello'}}
        with self.assertRaises(DesignLayerError) as caught:
            _writer(self.layer(), self.project_id, document=legacy)
        self.assertEqual(caught.exception.code, 'TOKEN_DOCUMENT_INVALID')
        self.assertIn('from_legacy_document', ' '.join(caught.exception.detail))

    def test_an_empty_or_non_object_document_is_refused(self):
        from design_lab.design_layer import DesignLayerError
        for candidate in ({}, [], None, {'scale': {'nested': {'deep': {1: 'x'}}}}):
            with self.subTest(document=candidate), self.assertRaises(DesignLayerError) as caught:
                _writer(self.layer(), self.project_id, document=candidate)
            self.assertEqual(caught.exception.code, 'TOKEN_DOCUMENT_INVALID')

    def test_a_write_that_would_drop_a_version_is_refused(self):
        from design_lab.design_layer import DesignLayerError
        layer = self.layer()
        _writer(layer, self.project_id)
        _writer(layer, self.project_id, expected_version=1, key='tok-2')
        # Stale: this writer saw v1 and would supersede the v2 it never read.
        with self.assertRaises(DesignLayerError) as caught:
            _writer(layer, self.project_id, expected_version=1, key='tok-3')
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'STALE_REVISION'))
        # And a first write against a chain that already exists is stale too.
        with self.assertRaises(DesignLayerError) as caught:
            _writer(layer, self.project_id, expected_version=0, key='tok-4')
        self.assertEqual(caught.exception.code, 'STALE_REVISION')
        tip = layer.get_tokens(self.project_id, DESIGN_SYSTEM)['token_document']
        self.assertEqual(tip['version'], 2)
        conn = self.db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM design_system_token").fetchone()[0], 2)
        conn.close()

    def test_a_second_writer_holding_the_lease_is_refused(self):
        """Concurrency uses the repo's ONE writer lease (asset_writer_lock with
        generation fencing), not a second lock invented for tokens."""
        from design_lab.design_layer import DesignLayerError
        from design_lab.runtime import asset_store as assets
        from design_lab.creative import store as cstore
        resource = 'design-system-tokens:' + self.project_id + ':' + DESIGN_SYSTEM
        # closing(): sqlite3.Connection's own context manager commits, it never
        # closes, and an open handle holds the Windows file lock past cleanup.
        with closing(cstore.connect(self._service.database,
                                   project_root=self._service.paths.project_root)) as other:
            self.assertTrue(assets.acquire_writer(other, resource, 'other-holder'))
            try:
                with self.assertRaises(DesignLayerError) as caught:
                    _writer(self.layer(), self.project_id)
                self.assertEqual((caught.exception.status, caught.exception.code),
                                 (409, 'TOKEN_WRITER_BUSY'))
            finally:
                assets.release_writer(other, resource, 'other-holder', generation=1)
        # Released, so the write now goes through.
        self.assertEqual(_writer(self.layer(), self.project_id)['token_document']['version'], 1)
        conn = self.db()
        rows = conn.execute("SELECT holder_attempt_id, generation, state FROM asset_writer_lock"
                            " WHERE resource_key=?", (resource,)).fetchall()
        conn.close()
        self.assertEqual(len(rows), 1, 'one lease row for this document -- no second lock family')
        self.assertEqual(rows[0][2], 'RELEASED')
        self.assertTrue(rows[0][0].startswith('token-writer-'), rows[0][0])
        self.assertEqual(rows[0][1], 2, 'the token write took over the SAME lease row, so the'
                                        ' generation advanced from the external holder (1) to 2')

    def test_invalid_actor_and_version_shapes_are_refused(self):
        from design_lab.design_layer import DesignLayerError
        cases = (
            ({'actor_kind': 'CODEX'}, (400, 'INVALID_ACTOR_KIND')),
            ({'actor': '   '}, (400, 'INVALID_FIELD')),
            ({'expected_version': True}, (400, 'INVALID_EXPECTED_VERSION')),
            ({'expected_version': '1'}, (400, 'INVALID_EXPECTED_VERSION')),
            ({'expected_version': -1}, (400, 'INVALID_EXPECTED_VERSION')),
        )
        for override, expected in cases:
            arguments = {'document': TOKENS, 'expected_version': 0, 'actor': 'ALEX',
                         'actor_kind': 'human', 'idempotency_key': 'tok-shape'}
            arguments.update(override)
            with self.subTest(**override):
                with self.assertRaises(DesignLayerError) as caught:
                    self.layer().write_tokens(self.project_id, DESIGN_SYSTEM, **arguments)
                self.assertEqual((caught.exception.status, caught.exception.code), expected)

    def test_unknown_project_and_missing_document_fail_closed(self):
        from design_lab.design_layer import DesignLayerError
        layer = self.layer()
        with self.assertRaises(DesignLayerError) as caught:
            _writer(layer, '0' * 32)
        self.assertEqual((caught.exception.status, caught.exception.code), (404, 'PROJECT_NOT_FOUND'))
        with self.assertRaises(DesignLayerError) as caught:
            layer.get_tokens(self.project_id, DESIGN_SYSTEM)
        self.assertEqual((caught.exception.status, caught.exception.code),
                         (404, 'TOKEN_DOCUMENT_NOT_FOUND'))
        with self.assertRaises(DesignLayerError) as caught:
            layer.token_lineage(self.project_id, DESIGN_SYSTEM)
        self.assertEqual(caught.exception.code, 'TOKEN_DOCUMENT_NOT_FOUND')

    def test_two_design_systems_keep_separate_chains(self):
        layer = self.layer()
        _writer(layer, self.project_id)
        second = _writer(layer, self.project_id, name='anomaly-monitor-dark', key='tok-b')['token_document']
        self.assertEqual(second['version'], 1)
        listed = self.layer().list_token_documents(self.project_id)['token_documents']
        self.assertEqual(sorted(row['design_system_name'] for row in listed),
                         ['anomaly-monitor-dark', DESIGN_SYSTEM])


if __name__ == '__main__':
    unittest.main()
