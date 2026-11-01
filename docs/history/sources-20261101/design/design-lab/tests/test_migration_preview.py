# SPDX-License-Identifier: MIT
"""R3-02: inventory explicit files, never migrate or inspect private runtime state."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
import subprocess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))


class MigrationPreviewTests(unittest.TestCase):
    def setUp(self):
        from design_lab.runtime.migration_preview import preview
        self.preview = preview
        parent = ROOT/'.project-local/task-runtime/migration-preview-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'AGENTS.md').write_text('# project fixture', encoding='utf-8')
        self.source = self.root/'.project-local/old/artifact.svg'
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b'<svg/>')
        self.dest = '.project-local/projects/p/artifact.svg'
        self.manifest = {'schemaVersion':'design-lab/migration-selection/v1', 'files':[
            {'source':self.source.relative_to(self.root).as_posix(), 'destination':self.dest}]}

    def run_preview(self):
        return self.preview(self.manifest, project_root=self.root, environ={})

    def test_explicit_preview_hashes_sources_without_creating_destinations(self):
        before = {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.run_preview()
        self.assertEqual(result['status'], 'PREVIEW_READY')
        self.assertEqual(result['files'][0]['sha256'], hashlib.sha256(b'<svg/>').hexdigest())
        self.assertFalse(result['migration_executed'])
        self.assertFalse(result['writers_stopped_verified'])
        self.assertFalse((self.root/self.dest).exists())
        after = {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after, before)

    def test_missing_source_is_blocked_not_invented(self):
        self.manifest['files'][0]['source'] = '.project-local/old/missing.svg'
        result = self.run_preview()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['files'][0]['status'], 'SOURCE_MISSING')

    def test_conflicting_destination_is_preserved(self):
        dest = self.root/self.dest
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'accepted user version')
        result = self.run_preview()
        self.assertEqual(result['files'][0]['status'], 'DESTINATION_CONFLICT')
        self.assertEqual(dest.read_bytes(), b'accepted user version')

    def test_identical_destination_is_reuse_not_copy(self):
        dest = self.root/self.dest
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'<svg/>')
        self.assertEqual(self.run_preview()['files'][0]['status'], 'ALREADY_IDENTICAL')

    def test_private_external_and_unbounded_selections_are_rejected(self):
        for path in ('.hermes/sessions.db', '.hermes/task-runtime/auth.json', '.env',
                     'E:/private', '../escape', '.project-local/old/*', '.project-local/old'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.manifest['files'][0]['source'] = path
                self.run_preview()

    def test_duplicate_casefolded_destinations_are_rejected(self):
        self.manifest['files'].append({'source':self.source.relative_to(self.root).as_posix(),
                                       'destination':self.dest.upper()})
        with self.assertRaises(ValueError):
            self.run_preview()

    def test_hardlinked_source_is_rejected(self):
        os.link(self.source, self.source.with_name('other.svg'))
        with self.assertRaises(ValueError):
            self.run_preview()

    def test_active_sqlite_companion_prevents_snapshot_claim(self):
        database = self.source.with_name('state.db')
        with closing(sqlite3.connect(database)) as conn:
            conn.execute('CREATE TABLE operation_intent(operation_id TEXT PRIMARY KEY)')
        Path(str(database)+'-wal').write_bytes(b'active-wal-fixture')
        self.manifest['files'][0].update(source=database.relative_to(self.root).as_posix(),
                                         destination='.project-local/projects/p/state.db')
        result = self.run_preview()
        self.assertEqual(result['files'][0]['status'], 'DATABASE_COMPANION_PRESENT')
        self.assertNotIn('sha256', result['files'][0])

    def test_sqlite_backup_remains_required_even_for_quiescent_snapshot(self):
        database = self.source.with_name('state.db')
        with closing(sqlite3.connect(database)) as conn:
            conn.executescript((ROOT/'design-lab/schemas/state/design-lab-state-v1.sql').read_text(encoding='utf-8'))
        self.manifest['files'][0].update(source=database.relative_to(self.root).as_posix(),
                                         destination='.project-local/projects/p/state.db')
        result = self.run_preview()
        self.assertEqual(result['files'][0]['status'], 'READY_FOR_BACKUP')
        self.assertTrue(result['files'][0]['backup_required'])
        self.assertFalse(result['writers_stopped_verified'])

    def test_byte_budget_blocks_before_reading_large_source(self):
        result = self.preview(self.manifest, project_root=self.root, environ={}, max_total_bytes=1)
        self.assertEqual(result['files'][0]['status'], 'BYTE_BUDGET_EXCEEDED')
        self.assertNotIn('sha256', result['files'][0])

    def test_doctor_cli_runs_read_only_preview_from_foreign_cwd(self):
        manifest = {'schemaVersion':'design-lab/migration-selection/v1', 'files':[
            {'source':self.source.relative_to(ROOT).as_posix(),
             'destination':(self.root/'.project-local/new/artifact.svg').relative_to(ROOT).as_posix()}]}
        path = self.source.parent/'selection.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        command = [sys.executable, '-B', str(ROOT/'scripts/design_lab_doctor.py'),
                   '--migration-preview', str(path), '--json']
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, encoding='utf-8',
                                env={**os.environ, 'PROJECT_LOCAL_ROOT':str(ROOT/'.project-local')})
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['status'], 'PREVIEW_READY')
        self.assertFalse(data['migration_executed'])
        self.assertFalse((self.root/'.project-local/new').exists())


if __name__ == '__main__':
    unittest.main()
