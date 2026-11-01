# SPDX-License-Identifier: MIT
"""Motion gate: does the shipped Workbench actually animate only composited properties?

`design-lab/tests/e2e/audit_workbench_motion.mjs` walks every nav route in a real Chromium served
by the real Python loopback service and reads the motion out of Chromium's own CSSOM and computed
styles, not out of the stylesheet text. It is the E2 companion to the text scan in
`design-lab/scripts/verify_selected_source_adaptation.py`, whose `composited_motion_violations`
predicate this test deliberately re-uses: rule `SRC-T07-MOTION-COMPOSITED` in
`packages/capabilities/standards/MOTION_ACCESSIBILITY.md` is one rule, and two gates that own one
rule with two different definitions is how a byte goes red in one rollup and green in the other.

Why the browser half is needed. A grep over seven files cannot see what `@media` and `@supports`
actually contributed once parsed, what the `@keyframes` blocks animate, or what a rendered element
ends up carrying after the bundle has run. Those are the three readings that make
"this landing is consumed" a measurement instead of a pattern match.

Falsified before being trusted, in the same run rather than by hand: the harness injects
`@keyframes dlMotionPlant{from{width:10px}to{width:20px}} .dl-motion-plant{transition:width 200ms}`
into the live document last, and the SAME scanner has to convict it (three findings: the two keyframe
steps plus the rule). A zero-violation product run with a blind scanner would otherwise read green.

Same harness as the geometry gate: synthetic project root, OS-chosen port, in-memory token, and
PROBE-driven honest skips when the toolchain is absent. `verify_browser_e2e_ran.py` lists this module,
so the required CI job turns a skip red instead of quietly passing. Claims controlled-runtime
measurement of the built bundle only: no host run, no human visual jury, and no verdict on whether
the motion looks good.
"""
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from test_workbench_design_layer_e2e import _find_browser, _find_node_modules_dir  # noqa: E402

ROOT = _TESTS_DIR.parents[1]
GATE_SCRIPT = _TESTS_DIR / 'e2e' / 'audit_workbench_motion.mjs'
ADAPTATION_GATE = ROOT / 'design-lab' / 'scripts' / 'verify_selected_source_adaptation.py'
STANDARD = 'packages/capabilities/standards/MOTION_ACCESSIBILITY.md'
RULE = 'SRC-T07-MOTION-COMPOSITED'


def _evidence_dir():
    override = os.environ.get('E2E_EVIDENCE_DIR')
    if override:
        return Path(override)
    return ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e'


def _import_adaptation_gate():
    """Load the text-scan gate by path so the shared motion predicate is read, not re-typed."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('dl_motion_text_gate', str(ADAPTATION_GATE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkbenchMotionGateTests(unittest.TestCase):
    def test_shipped_motion_is_read_in_a_real_browser_and_convicts_a_planted_fault(self):
        if not GATE_SCRIPT.is_file():
            self.skipTest(f'motion gate script missing: {GATE_SCRIPT}')
        node = shutil.which('node')
        if not node:
            self.skipTest('E2E toolchain unavailable: node not on PATH')
        node_modules_dir = _find_node_modules_dir()
        if not node_modules_dir:
            self.skipTest('E2E toolchain unavailable: no resolvable `playwright` '
                          '(probe $E2E_NODE_MODULES / '
                          f'{ROOT / ".project-local/task-runtime/playwright"})')
        browser = _find_browser()
        if not browser:
            self.skipTest('E2E toolchain unavailable: no locally installed Chromium revision '
                          'found (probe $E2E_BROWSER / ms-playwright registry)')

        sys.path.insert(0, str(ROOT / 'src'))
        from design_lab.service import ProjectService
        from design_lab.http_service import make_server
        from unittest.mock import patch

        parent = ROOT / '.project-local' / 'task-runtime' / 'e2e-motion-gate'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        root = Path(tmp.name)
        (root / 'AGENTS.md').write_text('# synthetic motion-gate project', encoding='utf-8')
        token = secrets.token_hex(32)

        evidence = _evidence_dir()
        evidence.mkdir(parents=True, exist_ok=True)
        report_path = evidence / 'workbench-motion-gate.json'
        log_path = parent / 'motion-gate.log'

        with patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(root / '.project-local')}):
            service = ProjectService(str(root))
            server = make_server(service, token, port=0)
            port = server.server_address[1]
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                env = {
                    **os.environ,
                    'E2E_SERVICE_URL': f'http://127.0.0.1:{port}',
                    'E2E_TOKEN': token,
                    'E2E_NODE_MODULES': str(node_modules_dir),
                    'E2E_BROWSER': str(browser),
                    'MOTION_OUT': str(report_path),
                }
                with open(log_path, 'w', encoding='utf-8') as logf:
                    proc = subprocess.Popen([node, str(GATE_SCRIPT)], env=env, stdout=logf,
                                            stderr=subprocess.STDOUT, cwd=str(ROOT))
                    try:
                        code = proc.wait(timeout=240)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        self.fail('E2E_MOTION_TIMEOUT: the gate did not finish in 240s')
                with open(log_path, encoding='utf-8', errors='replace') as fh:
                    out = fh.read()
            finally:
                server.shutdown()
                worker.join()
                server.server_close()
                tmp.cleanup()

        summary = next((line for line in out.splitlines()
                        if line.startswith('MA_SUMMARY')), out[-800:])
        if code != 0:
            self.fail(f'MOTION_GATE_FAILED (exit {code})\n{summary}\n--- output ---\n{out[-3000:]}')
        self.assertIn('MA_OK', out, f'gate exited 0 without MA_OK:\n{out[-2000:]}')
        self.assertTrue(report_path.is_file(), f'gate produced no report at {report_path}')

        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(report.get('rule'), RULE,
                         'the receipt does not name the rule it measured')
        self.assertEqual(report.get('standard'), STANDARD,
                         'the receipt does not name the standard file it consumes')

        # The receipt names the bytes it measured, or "0 violations" describes some future bundle.
        for field, disk in (('styleSha256', (ROOT / 'apps/workbench/style.css').read_bytes()),
                            ('bundleSha256', (ROOT / 'apps/workbench/build/main.js').read_bytes())):
            self.assertEqual(report['subject'][field], hashlib.sha256(disk).hexdigest(),
                             f'{field} in the receipt does not match the bytes on disk')

        # Anti-vacuity: the scan has to have looked at something, or a zero is an empty input set.
        coverage = report['coverageTotals']
        self.assertGreaterEqual(report['routeCount'], 20,
                                'the walk did not reach the nav: ' + str(report['routeCount']))
        self.assertGreater(coverage['styleRules'], 1000,
                          'no parsed rules were scanned: ' + str(coverage))
        self.assertGreater(coverage['keyframeRules'], 0,
                          'the CSSOM walk never reached a @keyframes block, so animated '
                          'properties were not read at all: ' + str(coverage))
        self.assertGreater(coverage['keyframeSteps'], coverage['keyframeRules'],
                          'a @keyframes rule with no steps means the frame bodies were not read')
        self.assertGreater(coverage['elements'], 1000,
                           'no rendered elements were sampled: ' + str(coverage))

        # The plant: the same scanner must convict the injected layout motion.
        self.assertGreaterEqual(report['selfTest']['convictedCount'], 3,
                                'the planted layout transition was not fully convicted, so a '
                                'zero-violation product run is not evidence: '
                                + json.dumps(report['selfTest']))

        # The verdict.
        self.assertEqual(report['violations'], [],
                         f'gate reported layout motion while exiting 0: {report["violations"][:3]}')
        self.assertEqual(report['violationCount'], 0)
        # Publish what this gate declined to convict rather than silence it: `transition: all` is
        # not what the rule bans, and a gate that hides the count would read as a clean page.
        self.assertIsInstance(report['transitionAllCount'], int)

        # One rule, two surfaces: the browser reading and the shipped text scan must agree over the
        # same population, or the two gates own different definitions of the same byte.
        gate = _import_adaptation_gate()
        record = json.loads((ROOT / 'packages/capabilities/selected-sources.json')
                            .read_text(encoding='utf-8'))
        applies_to = next(landing['appliesTo']
                          for rec in record['selected']
                          for landing in rec['landing']
                          if landing.get('ruleId') == RULE)
        text_findings = gate.composited_motion_violations(ROOT, applies_to)
        self.assertEqual(len(text_findings), report['violationCount'],
                         f'the text scan sees {len(text_findings)} layout motions over '
                         f'{len(applies_to)} files and the browser sees '
                         f'{report["violationCount"]}: the two gates disagree about one rule')


if __name__ == '__main__':
    unittest.main(verbosity=2)
