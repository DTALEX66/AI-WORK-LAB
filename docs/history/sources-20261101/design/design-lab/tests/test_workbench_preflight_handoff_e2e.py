# SPDX-License-Identifier: MIT
"""Browser gate for the Preflight block -> fix -> re-check case, plus the handoff
read-zero assertion (UI plan steps 5 and 7).

Mirrors the design-layer slice's honesty contract: it runs the real Chromium chain
when the toolchain is present, and when it is not it SKIPS with a stated reason rather
than reporting a pass. It additionally refuses to pretend when the fixture's premise
is false: the registry names `git` as the resolvable tool, so if `git` is not on this
process's PATH the run is skipped, not failed — a missing tool in the probe scope is an
environment fact, not a UI defect.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
NODE_SCRIPT = ROOT / 'design-lab' / 'tests' / 'e2e' / 'browser_preflight_handoff.mjs'
REGISTRY_REL = Path('design-lab') / 'config' / 'task-resources.json'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'design-lab' / 'tests'))

# The two browser/toolchain probes are the shared ones, not a third local copy.
# This module's own `_browser()` looked only at `$HOME/AppData/Local/ms-playwright` with a
# `chrome-win*` glob, so it returned None on Linux; the private `_node_modules_dir()` walked
# only `apps/workbench` and the repo root. Both are the same question every other browser
# gate already asks, and `test_workbench_contrast_gate.py:68` sets the precedent of
# importing those two functions (helpers, not a TestCase class, so nothing double-runs).
# Importing here is also what makes CI registration honest: a gate whose browser discovery
# is platform-bound silently skips wherever it cannot find one, and a silent skip in a
# required job is a green that nobody measured.
from test_workbench_design_layer_e2e import _find_browser, _find_node_modules_dir  # noqa: E402


def _node_modules_dir():
    return _find_node_modules_dir()


def _browser():
    found = _find_browser()
    return str(found) if found else None


class PreflightHandoffE2ETests(unittest.TestCase):
    def setUp(self):
        if not NODE_SCRIPT.is_file():
            self.skipTest(f'browser script missing: {NODE_SCRIPT}')
        if not shutil.which('node'):
            self.skipTest('node not on PATH')
        if not _node_modules_dir():
            self.skipTest('playwright node_modules not found')
        if not shutil.which('git'):
            self.skipTest('the fixture resolves `git` as its present tool; '
                          'git is absent from this probe scope')

    def test_block_fix_recheck_in_real_browser(self):
        import secrets
        from design_lab.service import ProjectService
        from design_lab.http_service import make_server

        parent = ROOT / '.project-local' / 'task-runtime' / 'e2e-preflight'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        root = Path(tmp.name)
        (root / 'AGENTS.md').write_text('# synthetic preflight e2e project', encoding='utf-8')
        registry = root / REGISTRY_REL
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({'schemaVersion': 'design-lab/task-resources/v1',
                                        'resources': {}, 'tasks': {}}), encoding='utf-8')
        token = secrets.token_hex(32)
        env = dict(os.environ)
        env.update({'PROJECT_LOCAL_ROOT': str(root / '.project-local'),
                    'E2E_FIXTURE': str(registry)})
        try:
            with patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(root / '.project-local')}):
                service = ProjectService(str(root))
                # One project so 交付中心 has something to select: with a connected
                # session and no bundles its heading must read as a real zero.
                service.create_project('UIE2E Handoff')
                server = make_server(service, token, port=0)
                port = server.server_address[1]
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                env['E2E_SERVICE_URL'] = f'http://127.0.0.1:{port}'
                env['E2E_TOKEN'] = token
                env['E2E_NODE_MODULES'] = str(_node_modules_dir())
                browser = _browser()
                if browser:
                    env['E2E_BROWSER'] = browser
                try:
                    proc = subprocess.run([shutil.which('node'), str(NODE_SCRIPT)],
                                          env=env, capture_output=True, text=True,
                                          encoding='utf-8', errors='replace',
                                          timeout=240, cwd=str(ROOT))
                finally:
                    server.shutdown()
                    worker.join()
                    server.server_close()
        finally:
            tmp.cleanup()
        self.assertEqual(proc.returncode, 0,
                         'preflight e2e exited %d:\n%s\n%s'
                         % (proc.returncode, proc.stdout, proc.stderr))
        self.assertIn('E2E_PREFLIGHT_OK', proc.stdout,
                      'no full block -> fix -> re-check pass:\n' + proc.stdout + proc.stderr)
        # Exact, not >=: the five asserted steps are mount, READY, BLOCKED (with the
        # stale verdict cleared), block -> fix -> re-check, and the handoff read-zero.
        # A short count means one of them stopped being exercised.
        self.assertIn('steps=5', proc.stdout,
                      'expected 5 asserted steps, saw: ' + proc.stdout.strip())


if __name__ == '__main__':
    unittest.main()
