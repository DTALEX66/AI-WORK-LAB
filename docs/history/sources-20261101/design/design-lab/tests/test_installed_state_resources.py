# SPDX-License-Identifier: MIT
"""Installed-layout SQL reads must not reach back into a source checkout."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class InstalledStateResourcesTests(unittest.TestCase):
    def test_stores_read_bundled_sql_without_source_tree(self):
        parent = ROOT / '.project-local/task-runtime/installed-state-resource-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            stage = Path(temporary) / 'lib'
            package = stage / 'design_lab'
            shutil.copytree(ROOT / 'src/design_lab', package,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            bundled = package / 'resources/state'
            bundled.mkdir(parents=True)
            for source in (ROOT / 'design-lab/schemas/state').glob('*.sql'):
                shutil.copyfile(source, bundled / source.name)
            code = '''
import json, sqlite3, sys
sys.path.insert(0, sys.argv[1])
from design_lab.runtime import state_store, asset_store, job_store
conn = sqlite3.connect(':memory:')
conn.executescript(state_store.DDL.read_text(encoding='utf-8'))
conn.executescript(asset_store._SCHEMA.read_text(encoding='utf-8'))
conn.executescript(asset_store._V2_SCHEMA.read_text(encoding='utf-8'))
conn.executescript(job_store._SCHEMA.read_text(encoding='utf-8'))
conn.executescript(job_store._V2_SCHEMA.read_text(encoding='utf-8'))
print(json.dumps([r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]))
conn.close()
'''
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(stage)],
                                    cwd=temporary, capture_output=True, text=True,
                                    encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            tables = json.loads(result.stdout)
            self.assertIn('operation_intent', tables)
            self.assertIn('asset_version', tables)

    def test_unknown_resource_name_is_rejected(self):
        sys.path.insert(0, str(ROOT / 'src'))
        from design_lab.runtime.state_resources import state_schema
        for name in ('../secret.sql', 'unknown.sql', '/absolute.sql'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                state_schema(name)

    def test_missing_distribution_resource_does_not_fall_back_to_cwd(self):
        parent = ROOT / '.project-local/task-runtime/installed-state-resource-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            stage = Path(temporary) / 'lib'
            shutil.copytree(ROOT / 'src/design_lab', stage / 'design_lab',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            code = '''
import sys
sys.path.insert(0, sys.argv[1])
from design_lab.runtime.state_resources import state_schema
try:
    state_schema('design-lab-state-v1.sql')
except FileNotFoundError:
    print('MISSING_RESOURCE_REJECTED')
else:
    raise AssertionError('installed package silently borrowed a source checkout')
'''
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(stage)],
                                    cwd=ROOT, capture_output=True, text=True,
                                    encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('MISSING_RESOURCE_REJECTED', result.stdout)


if __name__ == '__main__':
    unittest.main()
