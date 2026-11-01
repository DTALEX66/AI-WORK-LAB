# SPDX-License-Identifier: MIT
"""Theme geometry gate: the optional palette must actually move geometry, and the default must not.

`design-lab/tests/e2e/audit_workbench_theme_geometry.mjs` measures the painted nav-rail width and
the content column's offset in a real Chromium, per width and per palette. It is the E2 companion to
`test_workbench_theme_tokens.py`: that gate proves the stylesheet's registered numbers equal the
pack's and are read by some rule; this one proves the reading changes what a person sees.

Same harness as the overflow gate -- synthetic project root, OS-chosen port, in-memory token, and
PROBE-driven honest skips when the toolchain is absent (`verify_browser_e2e_ran.py` enforces the
no-skip policy in CI, so a skip turns the required job red rather than quietly green).

Falsified before being trusted, 2026-10-11, in this configuration:
  - with the two `:root[data-palette="ui2026"]` geometry rules deleted from the stylesheet the gate
    reports `THEME_RAIL_NOT_APPLIED @1920 ui2026/dark: expected 256px, saw rect=168 ...` and exits 1;
  - with the restored stylesheet it exits 0 with `TG_OK`.
It claims controlled-runtime geometry only: no host run, no human visual jury, no claim that the
theme looks right.
"""
import json
import os
import re
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
GATE_SCRIPT = _TESTS_DIR / 'e2e' / 'audit_workbench_theme_geometry.mjs'
WIDTHS = os.environ.get('THEME_WIDTHS', '1920,1200,960,768,700')


def declared_variants(shell_source=None):
    """Every palette/scheme pair the product itself declares, read out of shell.ts.

    This used to be a literal triple in the assertion below, which is how the pearl-white face --
    the one the 20261023 pack specifies -- went unmeasured by the geometry gate while the
    contrast gate was busy grading it through an injected attribute. Reading the table here means
    a fourth palette cannot join the product without also joining this gate's population, and a
    parse that found nothing is refused rather than read as a smaller world.
    """
    shell = shell_source if shell_source is not None else \
        (ROOT / 'apps' / 'workbench' / 'shell.ts').read_text(encoding='utf-8')
    block = shell[shell.index('const PALETTES'):shell.index('function paletteSpec')]
    out = []
    for match in re.finditer(r"\{\s*id:\s*'([\w-]+)'[^}]*?schemes:\s*\[([^\]]*)\]", block):
        for scheme in re.findall(r"'([\w-]+)'", match.group(2)):
            out.append('%s/%s' % (match.group(1), scheme))
    if len(out) < 4:
        raise AssertionError('the palette table shrank to %s; this gate would silently stop '
                             'measuring a theme it was told to cover' % out)
    return out


def _evidence_dir():
    override = os.environ.get('E2E_EVIDENCE_DIR')
    if override:
        return Path(override)
    return ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e'


class WorkbenchThemeGeometryGateTests(unittest.TestCase):
    def test_optional_palette_geometry_is_rendered_and_default_is_untouched(self):
        if not GATE_SCRIPT.is_file():
            self.skipTest(f'theme geometry gate script missing: {GATE_SCRIPT}')
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

        parent = ROOT / '.project-local' / 'task-runtime' / 'e2e-theme-geometry-gate'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        root = Path(tmp.name)
        (root / 'AGENTS.md').write_text('# synthetic theme-geometry-gate project', encoding='utf-8')
        token = secrets.token_hex(32)

        evidence = _evidence_dir()
        evidence.mkdir(parents=True, exist_ok=True)
        report_path = evidence / 'workbench-theme-geometry-gate.json'
        log_path = parent / 'theme-geometry-gate.log'

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
                    'THEME_WIDTHS': WIDTHS,
                    'THEME_OUT': str(report_path),
                }
                with open(log_path, 'w', encoding='utf-8') as logf:
                    proc = subprocess.Popen([node, str(GATE_SCRIPT)], env=env, stdout=logf,
                                            stderr=subprocess.STDOUT, cwd=str(ROOT))
                    try:
                        code = proc.wait(timeout=180)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        self.fail('E2E_THEME_GEOMETRY_TIMEOUT: the gate did not finish in 180s')
                with open(log_path, encoding='utf-8', errors='replace') as fh:
                    out = fh.read()
            finally:
                server.shutdown()
                worker.join()
                server.server_close()
                tmp.cleanup()

        summary = next((line for line in out.splitlines()
                        if line.startswith('TG_SUMMARY')), out[-800:])
        if code != 0:
            self.fail(f'THEME_GEOMETRY_GATE_FAILED (exit {code}) widths={WIDTHS}\n'
                      f'{summary}\n--- output ---\n{out[-3000:]}')
        self.assertIn('TG_OK', out, f'gate exited 0 without TG_OK:\n{out[-2000:]}')
        self.assertTrue(report_path.is_file(), f'gate produced no report at {report_path}')

        report = json.loads(report_path.read_text(encoding='utf-8'))
        # The findings belong in the receipt, not only in the console tail: a wrapper that quotes the
        # last 3000 characters cannot prove which widths it actually looked at.
        self.assertIsInstance(report.get('findings'), list,
                              'the report carries no findings list, so a passing run is unverifiable')
        self.assertEqual(report['findings'], [], f'gate reported findings while exiting 0: '
                                                f'{report["findings"]}')
        # The receipt has to name the bytes it measured, or "256px" describes some future stylesheet.
        for field, disk in (('styleSha256', (ROOT / 'apps/workbench/style.css').read_bytes()),
                            ('bundleSha256', (ROOT / 'apps/workbench/build/main.js').read_bytes())):
            import hashlib
            self.assertEqual(report['subject'][field], hashlib.sha256(disk).hexdigest(),
                             f'{field} in the receipt does not match the bytes on disk')
        measured = [w.strip() for w in WIDTHS.split(',') if w.strip()]
        self.assertEqual(sorted(report['widths'], key=str), sorted(measured, key=str),
                         'the gate skipped a width it was asked to walk')
        for width, seen in report['widths'].items():
            self.assertEqual(sorted(seen), sorted(declared_variants()),
                             f'{width}: not every palette was rendered')
            for variant, read in seen.items():
                self.assertIsNotNone(read, f'{width} {variant}: the gate read nothing')


class PalettePopulationIsDerived(unittest.TestCase):
    """The coverage list comes from the product, and a failed parse is loud.

    Without this, the gate could go back to measuring three variants forever while claiming to
    read the table: an empty or short derivation has to be an error, not a smaller denominator.
    """

    def test_the_pearl_white_face_is_in_the_population_this_gate_measures(self):
        variants = declared_variants()
        self.assertIn('stitch/light', variants,
                      'the geometry gate would stop measuring the pack face again: %s' % variants)
        self.assertGreaterEqual(len(variants), 4,
                                'the derivation found %s -- too few to be the real table'
                                % variants)

    def test_the_deriver_refuses_a_table_it_cannot_read(self):
        source = (ROOT / 'apps' / 'workbench' / 'shell.ts').read_text(encoding='utf-8')
        # Hide the schemes rather than the table name: a rename would make index() raise
        # ValueError for the wrong reason, and this guard is about reading an EMPTY population.
        blinded = source.replace('schemes: [', 'schemes_hidden: [')
        self.assertNotEqual(blinded, source, 'the plant did not change anything, so it proves '
                                             'nothing')
        with self.assertRaises(AssertionError) as caught:
            declared_variants(shell_source=blinded)
        self.assertIn('shrank', str(caught.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)
