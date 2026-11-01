# SPDX-License-Identifier: MIT
"""The native-asset and bundle listings must give one honest entry per delivery.

This surface had no test at all: `/assets` and the bundle list project registered
artifacts onto rows, one row per artifact, while paging and the one-row contract in
`verify()` are both written as if a row were an asset. An asset that registered a
preview beside its deliverable therefore appeared twice, and `verify()` answered 404
for an asset that is on disk.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from design_lab.native_assets import Bundles, ImageAssetError, NativeAssets   # noqa: E402
from design_lab.runtime import asset_store                                     # noqa: E402
from design_lab.service import ProjectService                                 # noqa: E402

NATIVE_ID = 'native-' + '0' * 64
BUNDLE_ID = 'bundle-native-' + '1' * 64


class OneRowPerAssetTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        parent = ROOT / '.project-local' / 'task-runtime' / 'native-listing'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'AGENTS.md').write_text('# native listing fixture', encoding='utf-8')
        self.service = ProjectService(self.root)
        self.project = self.service.create_project('Native listing')['id']
        self.store = self.service.paths.category_dir('projects', self.project, 'assets')
        self.store.mkdir(parents=True, exist_ok=True)

    def _publish(self, asset_id, kind, payload: bytes, artifact_name='native.psd'):
        source = self.root / f'in-{asset_id[:12]}-{len(payload)}-{artifact_name}.psd'
        source.write_bytes(payload)
        digest = 'sha256:' + hashlib.sha256(payload).hexdigest()
        with closing(asset_store.connect(self.service.database,
                                         project_root=self.service.paths.project_root)) as conn:
            asset_store.register_asset(conn, self.project, asset_id, kind)
            attempt = 'attempt-' + asset_id[:16]
            self.assertTrue(asset_store.acquire_writer(conn, f'asset:{asset_id}', attempt))
            generation = asset_store.writer_token(conn, f'asset:{asset_id}', attempt)
            version = asset_store.publish_version(conn, asset_id, source, store_root=self.store,
                                                 artifact_name=artifact_name,
                                                 expected_sha256=digest,
                                                 holder_attempt_id=attempt, generation=generation)
            asset_store.release_writer(conn, f'asset:{asset_id}', attempt, generation=generation)
        return version, digest

    def _register_preview(self, version, payload: bytes):
        """A second artifact whose name sorts BEFORE native.psd."""
        preview = self.store / 'aa-preview.png'
        preview.write_bytes(payload)
        with closing(sqlite3.connect(self.service.database)) as conn:
            conn.execute('INSERT INTO artifact (artifact_id, version_id, path, sha256,'
                         ' byte_size, role) VALUES (?,?,?,?,?,?)',
                         ('a-preview', version, str(preview),
                          'sha256:' + hashlib.sha256(payload).hexdigest(),
                          preview.stat().st_size, 'preview'))
            conn.commit()
        return preview

    def test_an_asset_with_two_registered_files_lists_once_on_the_deliverable(self):
        version, digest = self._publish(NATIVE_ID, 'psd', b'native photoshop bytes')
        self._register_preview(version, b'preview' * 9)
        listing = NativeAssets(self.service).list(self.project)
        self.assertEqual([row['id'] for row in listing['assets']], [NATIVE_ID],
                         f'one asset must be one row: {listing["assets"]}')
        self.assertEqual(listing['assets'][0]['sha256'], digest,
                         'the listed digest is the deliverable, not the preview')
        self.assertIsNone(listing['next_cursor'],
                          'a cursor appears only past the page, and rows are counted per asset')

    def test_verify_still_answers_for_an_asset_that_registered_a_preview(self):
        version, digest = self._publish(NATIVE_ID, 'psd', b'native photoshop bytes')
        self._register_preview(version, b'preview' * 9)
        read = NativeAssets(self.service).verify(self.project, NATIVE_ID)
        self.assertEqual(read['asset']['verification'], 'HASH_VERIFIED')
        self.assertEqual(read['asset']['sha256'], digest)

    def test_a_replaced_revision_is_listed_as_the_current_one(self):
        first, _ = self._publish(NATIVE_ID, 'psd', b'native photoshop bytes')
        second, second_digest = self._publish(NATIVE_ID, 'psd', b'revised native bytes')
        listing = NativeAssets(self.service).list(self.project)
        self.assertEqual([row['id'] for row in listing['assets']], [NATIVE_ID])
        self.assertEqual(listing['assets'][0]['sha256'], second_digest,
                         f'the read returned revision {first}, not {second}')

    def test_the_bundle_list_is_one_entry_per_delivery(self):
        version, digest = self._publish(BUNDLE_ID, 'other', b'{"deliverables": []}')
        self._register_preview(version, b'contact sheet')
        listing = Bundles(self.service).list(self.project)
        self.assertEqual([row['id'] for row in listing['bundles']], [BUNDLE_ID],
                         f'a delivery counted twice is two promises: {listing["bundles"]}')
        self.assertEqual(listing['bundles'][0]['sha256'], digest)

    def test_a_bundle_that_registered_a_preview_is_still_downloadable(self):
        """content() demands one row, so a second registered file made a real package 404."""
        import io
        import zipfile
        from design_lab.native_delivery import NativeDelivery
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('poster.png', b'shipped bytes')
        payload = archive.getvalue()
        version, digest = self._publish(BUNDLE_ID, 'other', payload,
                                        artifact_name='delivery.zip')
        self._register_preview(version, b'contact sheet' * 4)
        with NativeDelivery(self.service).content(self.project, BUNDLE_ID, version) as read:
            stream, size, actual = read
            self.assertEqual(stream.read(), payload)
        self.assertEqual(size, len(payload))
        self.assertEqual(actual, hashlib.sha256(payload).hexdigest())
        self.assertEqual('sha256:' + actual, digest)

    def test_an_unknown_native_asset_is_still_a_404_for_the_right_reason(self):
        """The fix must not turn 'no rows' into a success -- the code has to stay put."""
        with self.assertRaises(ImageAssetError) as caught:
            NativeAssets(self.service).verify(self.project, 'native-' + '9' * 64)
        self.assertEqual(caught.exception.code, 'NATIVE_ASSET_NOT_FOUND')
        with self.assertRaises(ImageAssetError):
            NativeAssets(self.service).verify(self.project, 'not-even-a-native-id')


if __name__ == '__main__':
    unittest.main()
