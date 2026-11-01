# SPDX-License-Identifier: MIT
"""Theme affordance gate: the palette buttons must change what is painted, and the URL they
write must reload as a page.

Companion to `test_workbench_theme_tokens.py` (which proves the stylesheet's registered numbers
are read by some rule) and `test_workbench_theme_geometry_gate.py` (which proves the optional
palette moves geometry when the attributes are set). This one is the only gate that *clicks*:
the DOT audit finding D13 was invisible to both, because the vm contract suite never asserted a
theme change and the capture driver sets the <html> attributes itself, so it renders the alternate
palette without the product path ever having worked.

Harness is the same as the other browser gates: synthetic project root, OS-chosen port, in-memory
token, PROBE-driven honest skips when the toolchain is absent, and `verify_browser_e2e_ran.py`
enforcing the no-skip policy in CI.

Passing here means five separate things were observed, and each is asserted rather than implied:
the control existed, the walk pressed once per palette on the product table and came round to its
start, EVERY hop moved the painted colour (not merely the first one), the pearl-white deep link
`?palette=stitch&scheme=light` answered 200 and painted something the default palette does not,
and `?palette=ui2026&scheme=light` answered 200.

The per-hop colour numbers in the receipt are a CHANGE DETECTOR, not an AA verdict: the repo's one
owner of contrast maths is `audit_workbench_contrast.mjs`, it is a top-level script and cannot be
imported, and this suite refuses a second OKLab/color-mix/gradient-compositing copy that could
drift from it. Whether stitch's light side clears WCAG AA is answered by
`test_workbench_contrast_gate.py`, which runs that owner with `UI_PALETTE=stitch`; this gate only
answers "can a person reach that palette by pressing the interface's own button".
"""
import hashlib
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
from unittest.mock import patch

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from test_workbench_design_layer_e2e import _find_browser, _find_node_modules_dir  # noqa: E402

ROOT = _TESTS_DIR.parents[1]
GATE_SCRIPT = _TESTS_DIR / 'e2e' / 'audit_workbench_theme_affordance.mjs'
SHELL_TS = ROOT / 'apps' / 'workbench' / 'shell.ts'


def _product_palette_table():
    """The palette ids the interface actually declares, read from `shell.ts`.

    This is deliberately a SECOND reader of the table, not a trust in the one baked into the
    report. The node gate needs the table to know how far to cycle; if the wrapper only checked
    that the two ends of its own list matched, a gate whose regex silently narrowed would shrink
    the walk and still report a clean pass. The geometry gate is the cautionary example: its
    hard-coded `PALETTES = [['design-lab', ...], ['ui2026', ...], ['ui2026 light']]` is a list of
    three STATES, never re-read from the product, and it went on measuring a two-palette table
    after the owner adopted the third.
    """
    text = SHELL_TS.read_text(encoding='utf-8')
    block = re.search(
        r'const PALETTES: readonly PaletteSpec\[\] = \[(.*?)\n\];', text, re.DOTALL)
    if not block:
        return None
    return re.findall(r"\{\s*id:\s*'([^']+)'", block.group(1))


def _evidence_dir():
    override = os.environ.get('E2E_EVIDENCE_DIR')
    if override:
        return Path(override)
    return ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e'


class WorkbenchThemeAffordanceGateTests(unittest.TestCase):
    def test_clicking_the_theme_control_changes_the_painted_page(self):
        if not GATE_SCRIPT.is_file():
            self.skipTest(f'affordance gate script missing: {GATE_SCRIPT}')
        node = shutil.which('node')
        if not node:
            self.skipTest('E2E toolchain unavailable: node not on PATH')
        node_modules_dir = _find_node_modules_dir()
        if not node_modules_dir:
            self.skipTest('E2E toolchain unavailable: no resolvable `playwright`')
        browser = _find_browser()
        if not browser:
            self.skipTest('E2E toolchain unavailable: no locally installed Chromium')

        sys.path.insert(0, str(ROOT / 'src'))
        from design_lab.service import ProjectService
        from design_lab.http_service import make_server

        parent = ROOT / '.project-local' / 'task-runtime' / 'e2e-theme-affordance'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        root = Path(tmp.name)
        (root / 'AGENTS.md').write_text('# synthetic theme-affordance-gate project', encoding='utf-8')
        token = secrets.token_hex(32)
        evidence = _evidence_dir()
        evidence.mkdir(parents=True, exist_ok=True)
        report_path = evidence / 'workbench-theme-affordance-gate.json'
        log_path = parent / 'theme-affordance.log'

        with patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(root / '.project-local')}):
            service = ProjectService(str(root))
            server = make_server(service, token, port=0)
            port = server.server_address[1]
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                env = {**os.environ,
                       'E2E_SERVICE_URL': f'http://127.0.0.1:{port}',
                       'E2E_TOKEN': token,
                       'E2E_NODE_MODULES': str(node_modules_dir),
                       'E2E_BROWSER': str(browser),
                       'AFF_OUT': str(report_path),
                       'AFF_SHOTS': str(evidence / 'affordance-shots')}
                with open(log_path, 'w', encoding='utf-8') as logf:
                    proc = subprocess.Popen([node, str(GATE_SCRIPT)], env=env, stdout=logf,
                                            stderr=subprocess.STDOUT, cwd=str(ROOT))
                    try:
                        code = proc.wait(timeout=180)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        self.fail('E2E_AFFORDANCE_TIMEOUT: the gate did not finish in 180s')
                with open(log_path, encoding='utf-8', errors='replace') as fh:
                    out = fh.read()
            finally:
                server.shutdown()
                worker.join()
                server.server_close()
                tmp.cleanup()

        summary = next((line for line in out.splitlines()
                        if line.startswith('AFF_SUMMARY')), out[-800:])
        if code != 0:
            self.fail(f'THEME_AFFORDANCE_GATE_FAILED (exit {code})\n{summary}\n--- output ---\n'
                      f'{out[-3000:]}')
        self.assertIn('AFF_OK', out, f'gate exited 0 without AFF_OK:\n{out[-2000:]}')
        self.assertTrue(report_path.is_file(), f'no report at {report_path}')

        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(report['findings'], [],
                         f'gate reported findings while exiting 0: {report["findings"]}')
        for field, disk in (('styleSha256', (ROOT / 'apps/workbench/style.css').read_bytes()),
                            ('bundleSha256', (ROOT / 'apps/workbench/build/main.js').read_bytes()),
                            ('shellSha256', SHELL_TS.read_bytes())):
            self.assertEqual(report['subject'][field], hashlib.sha256(disk).hexdigest(),
                             f'{field} in the receipt does not match the bytes on disk')

        # Non-vacuity: the click must have been observed changing the applied palette, and the
        # themed reload must have actually been requested. A report where nothing moved and
        # nothing was refuted is a scan that matched nothing, not a pass.
        measures = report['measures']
        self.assertIn('afterPaletteClick', measures,
                      'no palette click was measured -- the control was never driven')
        self.assertNotEqual(measures['plainBeforeClick']['palette'],
                            measures['afterPaletteClick']['palette'],
                            'the applied palette did not change, yet the gate reported no finding')
        self.assertNotEqual(measures['plainBeforeClick']['bodyBg'],
                            measures['afterPaletteClick']['bodyBg'],
                            'the painted background did not change after the palette click')
        self.assertTrue(any('200' in s and 'palette=ui2026' in s for s in report['statuses']),
                        f'the themed reload was never answered 200: {report["statuses"]}')

        self._assert_full_palette_walk(report)

    def _assert_full_palette_walk(self, report):
        """The two hard conditions of the 2026-10-26 extension, as their own method.

        Split out so each can be falsified against a report it did not produce: a condition that
        only ever runs inside the browser test can go red for the wrong reason (the node gate
        exiting non-zero fails the test long before this code runs), and then nothing has been
        shown about the condition itself.

        Hard condition 1 -- EVERY palette on the product table must have been landed on by a
        click, once per table entry, and the cycle must come back to where it started. Skipping
        one palette is a FAIL, not a number in a summary line: `stitch` sat on the table reachable
        only through hand-written <html> attributes, and a gate that reported "how many palettes
        were seen" without requiring all of them is exactly how that stayed green.

        Hard condition 2 -- every hop must really move the painted colour. `data-palette` changing
        while the ink stays put is the D13 defect, now checked per hop rather than once: a cycle
        can repaint on press 1 and go inert on press 2, and the old single-step probe could not
        see that.
        """
        table = _product_palette_table()
        self.assertIsNotNone(table,
                             f'no PALETTES table could be read from {SHELL_TS} -- without the '
                             'product list there is nothing to require a click for')
        self.assertGreaterEqual(len(table), 2,
                                f'the palette table parsed to {table}; a one-entry table cannot '
                                'be cycled, and a failed regex reads exactly like that')
        hops = report.get('hops') or []
        self.assertEqual(
            len(hops), len(table),
            f'the click walk made {len(hops)} hop(s) but the product table declares '
            f'{len(table)} palettes {table} -- one press per palette, no more and no less')
        landed = [hop['palette'] for hop in hops]
        for palette_id in table:
            self.assertIn(
                palette_id, landed,
                f'palette {palette_id!r} is on the product table {table} but no click ever '
                f'landed on it (landed: {landed}) -- the interface cannot reach it by pressing '
                'its own control, so it is not an option a person can choose')
        self.assertEqual(
            hops[-1]['palette'], report['measures']['plainBeforeClick']['palette'],
            f'after {len(table)} presses the page sits on {hops[-1]["palette"]!r}, not back on '
            f'the starting {report["measures"]["plainBeforeClick"]["palette"]!r} -- the cycle '
            'length disagrees with the table')
        self.assertEqual(
            sorted(set(landed)), sorted(set(table)),
            f'the walk landed on {sorted(set(landed))} but the table is {sorted(set(table))} '
            '-- an off-table palette means the click wrote something the product never declared')

        for hop in hops:
            self.assertTrue(
                hop['moved'],
                f"hop {hop['hop']} ({hop['palette']}/{hop['scheme']}) changed the attribute but "
                f"painted the same ink and background chain as the previous state "
                f"({hop['ink']}) -- an attribute that moves without changing what is painted is "
                'not a theme')
            self.assertTrue(
                hop['paletteMoved'],
                f"hop {hop['hop']} left data-palette at {hop['palette']!r} -- the press did not "
                'advance the cycle at all')
        # And the pearl-white side specifically: reaching the id is not reaching the theme. The
        # 20261023 block is keyed on [data-palette="stitch"][data-scheme="light"], so a hop that
        # lands `stitch` with the scheme attribute missing paints the default sheet while the
        # <html> tag claims otherwise.
        if 'stitch' in table:
            self.assertTrue([h for h in hops if h['palette'] == 'stitch'],
                            'no hop landed on stitch')
            deep = report.get('deepLink') or {}
            self.assertEqual(
                deep.get('status'), 200,
                f'GET /workbench?palette=stitch&scheme=light answered {deep.get("status")} -- '
                'the adopted palette is unreachable even by its own URL')
            self.assertEqual(deep.get('palette'), 'stitch',
                             f'the stitch deep link landed <html data-palette> at '
                             f'{deep.get("palette")!r}')
            self.assertEqual(deep.get('scheme'), 'light',
                             f'the stitch deep link landed <html data-scheme> at '
                             f'{deep.get("scheme")!r}')
            self.assertIsNot(
                deep.get('paintsLikeDefault'), True,
                'the stitch deep link paints the same ink and background chain as the default '
                'palette -- the pearl-white token block is inert even when both attributes land')


if __name__ == '__main__':
    unittest.main()
