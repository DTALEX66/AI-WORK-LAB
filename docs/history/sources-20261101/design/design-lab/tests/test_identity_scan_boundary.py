# SPDX-License-Identifier: MIT
"""The identity gate inspects active source, never ignored runtime/private data."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


class IdentityScanBoundaryTests(unittest.TestCase):
    def setUp(self):
        path = ROOT/'design-lab/scripts/verify_identity_gate.py'
        spec = importlib.util.spec_from_file_location('identity_boundary_fixture', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        parent = ROOT/'.project-local/task-runtime/identity-boundary-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.module.ROOT = self.root

    def write(self, relative, raw):
        path = self.root/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def write_zip(self, relative, names, body=b'# SPDX-License-Identifier: MIT\n'):
        """A real ZIP container holding those member names -- wheel-shaped bytes."""
        import io
        import zipfile
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for name in names:
                archive.writestr(name, body)
        self.write(relative, buffer.getvalue())

    def test_runtime_database_does_not_fail_source_identity_gate(self):
        self.write('.project-local/task-runtime/fixture.db', b'\xff\x00SQLite fixture')
        self.write('src/good.py', b'# SPDX-License-Identifier: MIT\n')
        self.assertEqual(self.module.scan(), [])

    def test_runtime_tree_is_pruned_before_enumeration(self):
        self.write('.project-local/task-runtime/fixture.json', b'{}')
        code = """
import importlib.util, json, pathlib, sys
spec = importlib.util.spec_from_file_location('probe', sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.ROOT = pathlib.Path(sys.argv[2])
visited = []
def audit(event, args):
    if event == 'os.scandir':
        visited.append(str(args[0]))
sys.addaudithook(audit)
m.scan()
print(json.dumps(visited))
"""
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT/'design-lab/scripts/verify_identity_gate.py'), str(self.root)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        visited = json.loads(result.stdout)
        self.assertTrue(visited)
        self.assertFalse(any(Path(p).is_relative_to(self.root/'.project-local') for p in visited), visited)

    def test_private_synthetic_files_are_not_opened(self):
        # Dedicated sentinels, not user credentials or real private runtime state.
        for relative in ('.env', 'auth.json', '.codex/config.toml', '.openhuman/memory.json'):
            self.write(relative, b'\xff private fixture')
        self.assertEqual(self.module.scan(), [])

    def test_active_violation_and_unreadable_source_still_fail(self):
        self.write('src/identity.txt', b'Open Design Assistance is the product')
        self.write('src/unreadable.py', b'\xff\x00')
        hits = self.module.scan()
        self.assertEqual(len(hits), 2)
        self.assertTrue(any('src/identity.txt' in h for h in hits))
        self.assertTrue(any('src/unreadable.py: unreadable' in h for h in hits))

    def test_active_workflow_is_checked_but_archived_names_and_ignore_rules_are_not_branding(self):
        self.write('.github/workflows/active.yml', b'name: Open Design Assistance')
        self.write('.github/workflows-archive/old.yml', b'name: Open Design Assistance')
        self.write('.gitignore', b'opendesign-assistance/generated/\n')
        hits = self.module.scan()
        self.assertEqual(len(hits), 1, hits)
        self.assertTrue(hits[0].startswith('.github/workflows/active.yml:'))

    def test_built_wheel_is_not_judged_as_utf8_text(self):
        """The regression this branch produced.

        `uv build` writes dist/*.whl, which is ignored by git but visible to this walk.
        A wheel is a ZIP: reading it as text raises a decode error, and the gate reported
        that as an identity hit. So every local build turned the gate red while detecting
        nothing -- and CI, which never has a dist/, could not see the defect at all.
        """
        self.write_zip('dist/design_lab-0.1.0a0-py3-none-any.whl',
                       ['design_lab/__init__.py', 'design_lab-0.1.0a0.dist-info/METADATA'])
        self.write('src/good.py', b'# SPDX-License-Identifier: MIT\n')
        self.assertEqual(self.module.scan(), [])

    def test_legacy_package_name_inside_a_container_is_caught(self):
        """Falsification: the container branch must have teeth, not just tolerance.

        Member names are where a legacy package identity travels -- a wheel for the old
        name would otherwise have passed straight through the binary skip.
        """
        self.write_zip('dist/opendesign_assistance-0.1-py3-none-any.whl',
                       ['opendesign_assistance/__init__.py'])
        hits = self.module.scan()
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(':: member opendesign_assistance/__init__.py', hits[0])

    def test_unopenable_container_fails_closed(self):
        self.write('fixtures/corrupt.zip', b'\x00\x00not a zip at all\xff')
        hits = self.module.scan()
        self.assertEqual(len(hits), 1, hits)
        self.assertIn('container unreadable', hits[0])


if __name__ == '__main__':
    unittest.main()
