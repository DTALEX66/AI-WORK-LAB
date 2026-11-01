# SPDX-License-Identifier: MIT
"""Real subprocess CLI persistence and project ownership contracts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ServiceCliTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/service-cli-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'AGENTS.md').write_text('# owned test project', encoding='utf-8')

    def invoke(self, *args):
        env = dict(os.environ)
        env.pop('PROJECT_LOCAL_ROOT', None)
        code = "import sys; sys.path.insert(0, sys.argv.pop(1)); from design_lab.cli import main; sys.exit(main())"
        return subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'src'),
                               '--project', str(self.root), *args],
                              cwd=self.root, env=env, capture_output=True, text=True,
                              encoding='utf-8')

    def test_create_then_new_process_lists_persisted_project(self):
        created = self.invoke('projects', 'create', '--name', 'Editable poster')
        self.assertEqual(created.returncode, 0, created.stderr + created.stdout)
        record = json.loads(created.stdout)['project']
        listed = self.invoke('projects', 'list')
        self.assertEqual(listed.returncode, 0, listed.stderr + listed.stdout)
        envelope = json.loads(listed.stdout)
        # `projects list` answers a roll-up, not the create echo. Identity is what has to survive the
        # process boundary; the counts are read from this checkout's tables and say which surfaces
        # were never opened here (null) rather than holding nothing (0).
        self.assertEqual(
            [{'id': row['id'], 'name': row['name'], 'created_at': row['created_at']}
             for row in envelope['projects']], [record])
        self.assertEqual(envelope['schemaVersion'], 'design-lab/project-list/v1')
        row = envelope['projects'][0]
        self.assertEqual(row['objects']['assets'], 0)
        self.assertIsNone(row['objects']['promptResults'])
        self.assertIn('promptResults', row['absentSurfaces'])
        self.assertTrue((self.root / '.project-local/task-runtime/service/state.db').is_file())

    def test_list_and_paths_do_not_create_runtime_state(self):
        for args in (('projects', 'list'), ('paths',)):
            result = self.invoke(*args)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse((self.root / '.project-local').exists())

    def test_invalid_name_does_not_create_database(self):
        result = self.invoke('projects', 'create', '--name', '   ')
        self.assertEqual(result.returncode, 2)
        self.assertIn('INVALID_PROJECT_NAME', result.stdout)
        self.assertFalse((self.root / '.project-local').exists())

    def test_missing_project_marker_is_rejected_without_creating_directory(self):
        absent = self.root / 'not-a-project'
        result = self.invoke('--project', str(absent), 'paths')
        self.assertEqual(result.returncode, 2)
        self.assertIn('owning project marker is missing', result.stdout)
        self.assertFalse(absent.exists())


if __name__ == '__main__':
    unittest.main()
