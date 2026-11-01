# SPDX-License-Identifier: MIT
"""Official personal launcher in a real browser, no injected access token."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_workbench_design_layer_e2e import _find_browser, _find_node_modules_dir

ROOT = Path(__file__).resolve().parents[2]


class PersonalWorkbenchE2E(unittest.TestCase):
    def test_personal_start_reload_and_navigation(self):
        browser, modules = _find_browser(), _find_node_modules_dir()
        if not browser or not modules:
            if os.environ.get('E2E_REQUIRED') == '1':
                self.fail('required personal browser environment unavailable')
            self.skipTest('local Chromium/Playwright unavailable')
        parent = ROOT / '.project-local/task-runtime/personal-browser'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temp:
            project = Path(temp)
            (project / 'AGENTS.md').write_text('# synthetic personal product acceptance', encoding='utf-8')
            env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'),
                   'PROJECT_LOCAL_ROOT': str(project / '.project-local')}
            proc = subprocess.Popen([sys.executable, '-m', 'design_lab', '--project', str(project),
                                     'workbench', '--no-browser'], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            try:
                announcement = json.loads(proc.stdout.readline())
                self.assertNotIn('token', announcement)
                env.update(E2E_SERVICE_URL=announcement['url'].rsplit('/workbench', 1)[0],
                           E2E_BROWSER=str(browser), E2E_NODE_MODULES=str(modules),
                           E2E_EVIDENCE_DIR=str(ROOT / '.project-local/task-artifacts/personal-browser'))
                result = subprocess.run(['node', str(ROOT / 'design-lab/tests/e2e/browser_personal_workbench.mjs')],
                                        env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            finally:
                proc.terminate()
                proc.wait(timeout=15)
                proc.stdout.close()
                proc.stderr.close()
