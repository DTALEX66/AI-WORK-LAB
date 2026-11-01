# SPDX-License-Identifier: MIT
"""Catch broad runtime traversal without reading any actual private data."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'design-lab/scripts/verify_visual_quality_v21.py'


class VisualQualityScanBoundaryTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/visual-quality-boundary-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.script = self.root / 'design-lab/scripts/verify_visual_quality_v21.py'
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.script)
        for relative in (
            'design-lab/research/style-lineages/STYLE_LINEAGES.json',
            'design-lab/research/style-lineages/STYLE_ANALYSIS_CARDS.json',
            'design-lab/research/master-studies/MASTER_REGISTRY.json',
            'design-lab/research/master-studies/ANCHOR_METHOD_CARDS.json',
            'design-lab/research/visual-quality/SOURCE_REGISTRY_VISUAL_V21.json',
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def run_gate(self):
        probe = '''
import json, runpy, sys
visited = []
def audit(event, args):
    if event == 'os.scandir': visited.append(str(args[0]))
sys.addaudithook(audit)
try:
    runpy.run_path(sys.argv[1], run_name='__main__')
finally:
    print('VISITED=' + json.dumps(visited))
'''
        result = subprocess.run([sys.executable, '-B', '-c', probe, str(self.script)],
                                capture_output=True, text=True, encoding='utf-8')
        visited = json.loads(next(line[8:] for line in result.stdout.splitlines()
                                  if line.startswith('VISITED=')))
        return result, visited

    def test_runtime_and_private_trees_are_pruned_before_enumeration(self):
        excluded = ('.project-local', '.hermes', '.git', '.codex', '.openhuman',
                    '.venv', 'node_modules', 'nested/.venv')
        for relative in excluded:
            path = self.root / relative / 'nested/fixture.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}\n{}', encoding='utf-8')
        for name in ('auth.json', 'credentials.json', 'tokens.json', '.env.json'):
            (self.root / name).write_text('synthetic private sentinel', encoding='utf-8')
        result, visited = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for relative in excluded:
            self.assertFalse(any(Path(p).is_relative_to(self.root / relative)
                                 for p in visited), (relative, visited))

    def test_malformed_active_source_still_fails(self):
        path = self.root / 'src/broken.json'
        path.parent.mkdir()
        path.write_text('{}\n{}', encoding='utf-8')
        result, _ = self.run_gate()
        self.assertEqual(result.returncode, 1)
        self.assertIn('src', result.stdout)
        self.assertIn('broken.json: invalid JSON', result.stdout)

    def test_new_source_directory_is_not_silently_excluded(self):
        path = self.root / 'new-product/data.json'
        path.parent.mkdir()
        path.write_text('{"valid":true}', encoding='utf-8')
        result, visited = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(path.parent), visited)

    def test_source_link_is_rejected_without_reading_target(self):
        target = self.root / '.project-local/linked-target'
        target.mkdir(parents=True)
        (target / 'sentinel.json').write_text('not JSON', encoding='utf-8')
        link = self.root / 'linked-source'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f'Native symlink privilege unavailable: {exc}')
        result, visited = self.run_gate()
        self.assertEqual(result.returncode, 1)
        self.assertIn('active reparse point not scanned', result.stdout)
        self.assertNotIn('sentinel.json: invalid JSON', result.stdout)
        self.assertFalse(any(Path(p).is_relative_to(link) for p in visited))


if __name__ == '__main__':
    unittest.main()
