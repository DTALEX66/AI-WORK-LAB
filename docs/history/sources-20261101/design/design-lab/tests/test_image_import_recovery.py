# SPDX-License-Identifier: MIT
"""Failure after real file rename must not become a successful import receipt."""
import base64
from contextlib import closing
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.service import ProjectService
from design_lab.image_assets import ImageAssets, ImageAssetError
from design_lab.runtime import asset_store


class RasterCurrentVersionTests(unittest.TestCase):
    """A raster asset with a replaced revision is one asset, not two, and not missing.

    `publish_version` never demotes the bytes it replaced, so `_read` used to see every
    ACTIVE revision: the library listed the same asset once per revision, and
    `content()` -- which insists on exactly one row -- answered 404 ASSET_NOT_FOUND for
    an asset that exists. Both are read-side lies about bytes that are on disk.
    """

    def _png(self, colour):
        from PIL import Image
        stream = io.BytesIO()
        Image.new('RGB', (10, 8), colour).save(stream, format='PNG')
        return stream.getvalue()

    def test_a_replaced_raster_revision_is_read_as_the_current_one(self):
        parent = ROOT / '.project-local/task-runtime/raster-current'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            os.environ.pop('PROJECT_LOCAL_ROOT', None)
            root = Path(temporary)
            (root / 'AGENTS.md').write_text('# raster current version fixture', encoding='utf-8')
            service = ProjectService(root)
            project = service.create_project('Raster rounds')['id']
            images = ImageAssets(service)
            first, second = self._png('green'), self._png('blue')
            versions = [self._publish(service, project, 'img-1', first),
                        self._publish(service, project, 'img-1', second)]

            listed = images.list(project)
            self.assertEqual([row['id'] for row in listed], ['img-1'],
                             f'the same asset must not be listed per revision: {listed}')
            served = images.content(project, 'img-1')
            self.assertEqual(base64.b64decode(served['content_base64']), second,
                             'the bytes served must be the current revision')
            self.assertNotEqual(served['asset']['version_id'], versions[0],
                                 'the replaced revision must not be what the read returns')
            with closing(sqlite3.connect(service.database)) as conn:
                self.assertEqual(conn.execute(
                    'SELECT COUNT(*) FROM asset_version WHERE state="ACTIVE"').fetchone()[0], 2,
                    'the store really does keep both ACTIVE rows -- that is the premise here')

    def test_a_second_artifact_on_the_same_version_does_not_split_the_asset(self):
        """One row per asset, on the deliverable, whatever the artifact table holds."""
        parent = ROOT / '.project-local' / 'task-runtime' / 'raster-artifacts'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            os.environ.pop('PROJECT_LOCAL_ROOT', None)
            root = Path(temporary)
            (root / 'AGENTS.md').write_text('# raster artifact fixture', encoding='utf-8')
            service = ProjectService(root)
            project = service.create_project('Raster artifacts')['id']
            images = ImageAssets(service)
            deliverable = self._png('orange')
            version = self._publish(service, project, 'img-2', deliverable)
            # A preview whose NAME sorts before the deliverable's, so a read that ordered
            # by path alone would serve the wrong bytes.
            store = service.paths.category_dir('projects', project, 'assets')
            preview = store / 'aa-preview.png'
            preview.write_bytes(self._png('purple'))
            with closing(sqlite3.connect(service.database)) as conn:
                conn.execute('INSERT INTO artifact (artifact_id, version_id, path, sha256,'
                             ' byte_size, role) VALUES (?,?,?,?,?,?)',
                             ('a-preview', version, str(preview),
                              'sha256:' + hashlib.sha256(preview.read_bytes()).hexdigest(),
                              preview.stat().st_size, 'preview'))
                conn.commit()
            listed = images.list(project)
            self.assertEqual([row['id'] for row in listed], ['img-2'],
                             f'an extra registered file must not duplicate the asset: {listed}')
            self.assertEqual(listed[0]['sha256'],
                             'sha256:' + hashlib.sha256(deliverable).hexdigest(),
                             'the listed digest must be the deliverable, not a preview')
            served = images.content(project, 'img-2')
            self.assertEqual(base64.b64decode(served['content_base64']), deliverable)


    def _publish(self, service, project_id, asset_id, payload: bytes):
        from contextlib import closing
        store = service.paths.category_dir('projects', project_id, 'assets')
        source = self._source(service, asset_id, payload)
        digest = 'sha256:' + hashlib.sha256(payload).hexdigest()
        with closing(asset_store.connect(service.database,
                                         project_root=service.paths.project_root)) as conn:
            if conn.execute('SELECT 1 FROM asset WHERE asset_id=?', (asset_id,)).fetchone() is None:
                asset_store.register_asset(conn, project_id, asset_id, 'raster')
            attempt = f'attempt-{asset_id}-{digest[7:19]}'
            self.assertTrue(asset_store.acquire_writer(conn, f'asset:{asset_id}', attempt))
            generation = asset_store.writer_token(conn, f'asset:{asset_id}', attempt)
            version = asset_store.publish_version(conn, asset_id, source, store_root=store,
                                                 artifact_name='reference.png',
                                                 expected_sha256=digest,
                                                 holder_attempt_id=attempt, generation=generation)
            asset_store.release_writer(conn, f'asset:{asset_id}', attempt, generation=generation)
            return version

    @staticmethod
    def _source(service, asset_id, payload: bytes):
        root = service.paths.category_dir('runtime', f'source-{asset_id}-{len(payload)}')
        root.mkdir(parents=True, exist_ok=True)
        source = root / 'input.png'
        source.write_bytes(payload)
        return source


class ImageImportRecoveryTests(unittest.TestCase):
    def test_real_rename_failure_stays_unknown_then_quarantines(self):
        from PIL import Image
        parent = ROOT / '.project-local/task-runtime/image-import-recovery'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary, patch.dict(os.environ):
            os.environ.pop('PROJECT_LOCAL_ROOT', None)
            root = Path(temporary)
            (root / 'AGENTS.md').write_text('# synthetic recovery fixture', encoding='utf-8')
            service = ProjectService(root)
            project = service.create_project('Recovery fixture')['id']
            images = ImageAssets(service)
            stream = io.BytesIO()
            Image.new('RGB', (12, 8), 'green').save(stream, format='PNG')
            encoded = base64.b64encode(stream.getvalue()).decode()
            with patch.object(asset_store, '_after_rename', side_effect=OSError('synthetic post-rename interruption')):
                with self.assertRaises(OSError):
                    images.import_image(project, encoded, 'recovery')
            with closing(sqlite3.connect(service.database)) as conn:
                self.assertEqual(conn.execute('SELECT state FROM attempt_state').fetchall(), [('OUTCOME_UNKNOWN',)])
                self.assertEqual(conn.execute('SELECT state FROM operation_state').fetchall(), [('OUTCOME_UNKNOWN',)])
                self.assertEqual(conn.execute('SELECT state FROM asset_publication').fetchall(), [('PREPARED',)])
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0], 0)
            with self.assertRaises(ImageAssetError) as raised:
                images.import_image(project, encoded, 'recovery')
            self.assertEqual(raised.exception.code, 'IMPORT_REQUIRES_RECONCILIATION')
            with closing(asset_store.connect(service.database, project_root=root)) as conn:
                recovered = asset_store.recover_publications(
                    conn, store_root=service.paths.category_dir('projects', project, 'assets'), project_root=root)
                self.assertEqual([r['state'] for r in recovered], ['QUARANTINED'])
                self.assertEqual(Path(recovered[0]['path']).read_bytes(), stream.getvalue())
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM attempt_state').fetchone()[0], 1)
            self.assertEqual(images.list(project), [])


if __name__ == '__main__':
    unittest.main()
