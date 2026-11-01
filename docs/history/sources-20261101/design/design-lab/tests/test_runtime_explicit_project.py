# SPDX-License-Identifier: MIT
"""Explicit project ownership for task databases and native artifact publication."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if os.environ.get('DESIGN_LAB_TEST_INSTALLED') != '1':
    sys.path.insert(0, str(ROOT / 'src'))
from design_lab.runtime import asset_store as assets, job_store as jobs, state_store
from design_lab.runtime.paths import PathPolicyError


class ExplicitProjectTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/explicit-project-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'owner'
        self.root.mkdir()
        (self.root / 'AGENTS.md').write_text('# synthetic owning project', encoding='utf-8')
        self.local = self.root / '.project-local'
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('PROJECT_LOCAL_ROOT', None)

    def test_task_state_persists_in_explicit_project(self):
        db = self.local / 'task-runtime/service/state.db'
        try:
            conn = jobs.connect(db, project_root=self.root)
        except TypeError as exc:
            self.fail(f'explicit project task connection unavailable: {exc}')
        with conn:
            first = jobs.begin_attempt(conn, 'job', operation_id='operation', idempotency_scope='test',
                                       idempotency_key='one', request_hash='a' * 64)
        conn.close()
        conn = jobs.connect(db, project_root=self.root)
        try:
            self.assertEqual(jobs.latest_attempt(conn, 'job'), first)
            self.assertEqual(first['state'], 'PENDING')
        finally:
            conn.close()

    def test_state_initializer_honors_owner_and_rejects_sibling(self):
        db = self.local / 'task-runtime/state.db'
        try:
            conn = state_store.init_db(db, project_root=self.root)
        except TypeError as exc:
            self.fail(f'explicit project initializer unavailable: {exc}')
        try:
            self.assertEqual(state_store.schema_version(conn), 'v1')
        finally:
            conn.close()
        foreign = self.base / 'sibling/.project-local/state.db'
        for connect, error in ((state_store.init_db, PathPolicyError), (jobs.connect, jobs.AttemptError),
                               (assets.connect, assets.AssetError)):
            with self.assertRaises(error):
                connect(foreign, project_root=self.root)
        self.assertFalse(foreign.parent.exists())

    def test_publish_and_reopen_artifact_use_explicit_owner(self):
        db = self.local / 'task-runtime/state.db'
        conn = assets.connect(db, project_root=self.root)
        self.addCleanup(conn.close)
        assets.create_project(conn, 'project', 'Synthetic')
        assets.register_asset(conn, 'project', 'art', 'vector')
        source = self.local / 'input.svg'
        content = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
        source.write_bytes(content)
        assets.acquire_writer(conn, 'asset:art', 'worker')
        token = assets.writer_token(conn, 'asset:art', 'worker')
        options = dict(artifact_name='result.svg', expected_sha256=hashlib.sha256(content).hexdigest(),
                       holder_attempt_id='worker', generation=token, project_root=self.root)
        store = self.local / 'projects/store'
        try:
            version = assets.publish_version(conn, 'art', source, store_root=store, **options)
        except TypeError as exc:
            self.fail(f'explicit project publication unavailable: {exc}')
        path = Path(conn.execute('SELECT path FROM artifact WHERE version_id=?', (version,)).fetchone()[0])
        self.assertTrue(path.is_relative_to(store))
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(assets.recover_publications(conn, store_root=store, project_root=self.root), [])
        foreign = self.base / 'sibling/.project-local/store'
        with self.assertRaises(assets.AssetError):
            assets.publish_version(conn, 'art', source, store_root=foreign, **options)
        with self.assertRaises(assets.AssetError):
            assets.recover_publications(conn, store_root=foreign, project_root=self.root)
        self.assertFalse(foreign.parent.exists())


if __name__ == '__main__':
    unittest.main()
