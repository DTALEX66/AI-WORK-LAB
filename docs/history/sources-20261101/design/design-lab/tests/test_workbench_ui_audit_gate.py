# SPDX-License-Identifier: MIT
"""Put the quantitative UI audit under CI, and keep it honest about what it ran.

`scripts/audit_workbench_ui.py` measures 65 scopes across five viewports -- overflow,
contrast, keyboard reachability, touch targets, accessible names, degraded-state wording
and console noise -- and it was, until now, a manual command. That is not a theoretical
gap: on 2026-10-07 it reported `violations=12`, every one of them the same element,
`button#navToggle` at 62x23, the only control a phone user has to leave the page they
landed on. Nothing noticed because nothing ran it.

The count was also unactionable at first ("1 targets under 24px", on every route, with no
identity), so the probe now carries the element and its measured box. Two assertions here
exist to keep this file from becoming a green light that proves nothing: it fails if the
audit reports any violation, and it fails if the audit ran zero scopes.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TESTS_DIR))

from test_workbench_design_layer_e2e import _find_browser, _find_node_modules_dir  # noqa: E402

ROOT = _TESTS_DIR.parents[1]
AUDITOR = ROOT / 'scripts' / 'audit_workbench_ui.py'
# 2048 joined the swept widths on 2026-10-19 because that is the CSS viewport the owner's
# machine actually renders at: Screen.Bounds 2048x1152, WorkingArea 2048x1104,
# AppliedDPI 120 (125% scaling on a 2560x1440 panel). 2560 is the panel, not the box the
# browser gets, and neither width was measured by any gate before this. Cost: 13 scopes
# x 3 widths instead of 2. First local attempt came back red on a transient
# `net::ERR_NO_BUFFER_SPACE` console error at 1280 (this machine, three browser runs back
# to back); the second was green. That failure is the gate doing its job - a console error
# is a violation here - not a product defect, so it is recorded rather than smoothed over.
WIDTHS = os.environ.get('UI_AUDIT_WIDTHS', '1280,1920,2048')


def _evidence_dir() -> Path:
    override = os.environ.get('E2E_EVIDENCE_DIR')
    if override:
        return Path(override)
    return ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e'


class WorkbenchUiAuditGateTests(unittest.TestCase):
    def test_quantitative_ui_audit_is_clean(self) -> None:
        if not AUDITOR.is_file():
            self.skipTest(f'auditor missing: {AUDITOR}')
        node = shutil.which('node')
        if not node:
            self.skipTest('E2E toolchain unavailable: node not on PATH')
        if not _find_node_modules_dir():
            self.skipTest('E2E toolchain unavailable: no resolvable `playwright`')
        if not _find_browser():
            self.skipTest('E2E toolchain unavailable: no locally installed Chromium')

        evidence = _evidence_dir()
        evidence.mkdir(parents=True, exist_ok=True)
        report_path = evidence / 'workbench-ui-audit.json'
        if report_path.exists():
            report_path.unlink()
        parent = ROOT / '.project-local' / 'task-runtime' / 'e2e-ui-audit'
        parent.mkdir(parents=True, exist_ok=True)

        # The child writes the report itself, so the run is judged on the artifact plus
        # the exit code -- a truncated stdout must not be able to hide a violation.
        with tempfile.TemporaryDirectory(dir=parent) as tmp:
            log_path = Path(tmp) / 'ui-audit.log'
            with log_path.open('wb') as handle:
                proc = subprocess.run(
                    [sys.executable, '-X', 'utf8', '-B', str(AUDITOR),
                     '--out', str(report_path), '--widths', WIDTHS],
                    cwd=str(ROOT), stdout=handle, stderr=subprocess.STDOUT, timeout=1500)
            output = log_path.read_text(encoding='utf-8', errors='replace')

        if 'AUDIT_BLOCKED' in output:
            self.fail(f'the audit reported AUDIT_BLOCKED instead of measuring: {output[-400:]}')
        self.assertTrue(report_path.is_file(),
                        f'no report written; audit output:\n{output[-600:]}')
        report = json.loads(report_path.read_text(encoding='utf-8'))

        # The report carries ok/violations/notes/worst/environment; the scope count is only
        # on the wrapper's line, so a run that measured nothing has to be caught here
        # rather than by an empty violations list that looks identical to a clean one.
        measured = re.search(r'AUDIT_SCOPES\s+(\d+)', output)
        self.assertIsNotNone(measured,
                             f'no AUDIT_SCOPES line, so coverage is unknown:\n{output[-600:]}')
        scopes = int(measured.group(1))
        self.assertGreater(scopes, 0, 'the audit measured zero scopes -- a green that means nothing')
        # Closed <details> keep layout boxes for content Chromium does not paint, so the audit opens
        # them before measuring. This count is how many it expanded: zero means the step is gone and
        # the violations list below is once again a statement about invisible layout.
        expanded = (report.get('notes') or {}).get('detailsExpanded')
        self.assertIsInstance(expanded, int,
                              'the report does not say how many collapsed panels were expanded: %s'
                              % sorted((report.get('notes') or {})))
        self.assertGreater(expanded, 0,
                           'the audit expanded no collapsed detail anywhere, so it is measuring '
                           'boxes behind panels nobody has opened')
        self.assertEqual(
            report.get('violations'), [],
            f'{len(report.get("violations") or [])} UI violations across {scopes} scopes '
            f'(widths {WIDTHS}):\n' + '\n'.join(map(str, (report.get('violations') or [])[:12])))
        self.assertTrue(report.get('ok'), 'the auditor itself says ok=False')


if __name__ == '__main__':
    unittest.main()
