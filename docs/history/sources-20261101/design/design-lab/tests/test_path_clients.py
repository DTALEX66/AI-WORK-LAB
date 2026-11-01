# SPDX-License-Identifier: MIT
"""R3-02 callers must honor the selected root, including explicit DB paths."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import importlib.util
import io
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))


class PathClientTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT/'.project-local/task-runtime/path-client-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.selected = self.root/'.project-local/selected'
        self.selected.parent.mkdir()
        (self.root/'AGENTS.md').write_text('# isolated project fixture', encoding='utf-8')
        self.env = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT':str(self.selected)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_all_database_initializers_reject_unselected_root_before_writing(self):
        from design_lab.runtime import asset_store, job_store, state_store
        for name, opener in [('asset', asset_store.connect), ('job', job_store.connect), ('state', state_store.init_db)]:
            path = self.root/(name+'-wrong.db')
            with self.subTest(name=name):
                try:
                    conn = opener(path)
                except (ValueError, RuntimeError):
                    pass
                else:
                    conn.close()
                    self.fail('unselected database root accepted')
                self.assertFalse(path.exists())

    def test_selected_databases_open_and_reopen_without_cwd_dependency(self):
        from design_lab.runtime import asset_store, job_store, state_store
        self.selected.mkdir()
        for name, opener in [('asset', asset_store.connect), ('job', job_store.connect), ('state', state_store.init_db)]:
            path = self.selected/(name+'.db')
            with self.subTest(name=name):
                opener(path).close()
                opener(path).close()
                self.assertGreater(path.stat().st_size, 0)

    def test_asset_publication_rejects_store_outside_selected_root(self):
        from design_lab.runtime import asset_store as assets
        self.selected.mkdir()
        with assets.connect(self.selected/'assets.db') as conn:
            self.addCleanup(conn.close)
            assets.create_project(conn, 'p', 'Fixture')
            assets.register_asset(conn, 'p', 'a', 'psd')
            assets.acquire_writer(conn, 'asset:a', 'worker')
            token = assets.writer_token(conn, 'asset:a', 'worker')
            source = self.selected/'source.psd'
            source.write_bytes(b'fixture')
            rejected = self.root/'old-store'
            with self.assertRaises(assets.AssetError):
                assets.publish_version(conn, 'a', source, store_root=rejected, artifact_name='poster.psd',
                    expected_sha256=hashlib.sha256(b'fixture').hexdigest(), holder_attempt_id='worker', generation=token)
            self.assertFalse(rejected.exists())
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM asset_publication').fetchone()[0], 0)

    def test_intake_cli_writes_under_selected_root_and_dry_run_writes_nothing(self):
        manifest = self.root/'collection.json'
        manifest.write_text(json.dumps({'collectionId':'fixture', 'displayName':'Dedicated fixture',
            'selectedPaths':['reference.txt'], 'intendedUse':'test', 'rightsReviewRequired':True,
            'outputTargets':[], 'createdBy':'fixture', 'createdAt':'2026-09-06'}), encoding='utf-8')
        command = [sys.executable, '-B', str(ROOT/'design-lab/scripts/external_asset_intake.py'), '--manifest', str(manifest)]
        dry = subprocess.run([*command, '--dry-run'], cwd=self.root, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertFalse(self.selected.exists())
        # Intercept the actual reported output to inspect bytes, not only a config constant.
        run = subprocess.run(command, cwd=self.root, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stderr)
        path = Path(next(line.partition('=')[2] for line in run.stdout.splitlines() if line.startswith('RUNTIME_STATE=')))
        self.assertTrue(path.is_relative_to(self.selected), str(path))
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['manifest']['collectionId'], 'fixture')

    def test_sidecar_summary_respects_selected_root_without_modifying_sources(self):
        path = ROOT/'design-lab/scripts/upgrade_asset_sidecars.py'
        spec = importlib.util.spec_from_file_location('sidecar_path_fixture', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fake_module_root = self.root/'design-lab'
        fake_module_root.mkdir()
        # No tracked input binaries in this dedicated fixture. The real summary writer runs.
        git_result = subprocess.CompletedProcess(['git'], 0, '', '')
        with patch.object(module, 'ROOT', fake_module_root), patch.object(subprocess, 'run', return_value=git_result), redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 0)
        result = self.selected/'task-runtime/asset-sidecar-upgrade.json'
        self.assertTrue(result.is_file())
        self.assertEqual(json.loads(result.read_text(encoding='utf-8')), {'upgraded':[], 'skipped':[], 'errors':[]})

    def test_attestation_writer_resolves_selected_root_at_execution(self):
        spec = importlib.util.spec_from_file_location('attestation_path_fixture', ROOT/'design-lab/scripts/update_evidence_binding.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Limit the legacy fallback to this fixture; no report is written to the real default root.
        module.ROOT = self.root
        module.ATTR_OUT = self.root/'.project-local/task-runtime/evidence'
        with patch.object(module, 'git_head', return_value='a'*40), patch.object(module, 'git_tree', return_value='b'*40), \
             patch.object(sys, 'argv', ['update_evidence_binding.py', '--attestation']), redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 0)
        outputs = list((self.selected/'task-runtime/evidence').glob('*.json'))
        self.assertEqual(len(outputs), 1)
        self.assertEqual(json.loads(outputs[0].read_text(encoding='utf-8'))['subjectCommitSha'], 'a'*40)


if __name__ == '__main__':
    unittest.main()
