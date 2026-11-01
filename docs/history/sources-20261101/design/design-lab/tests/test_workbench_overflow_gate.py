# SPDX-License-Identifier: MIT
"""Workbench overflow gate: no text may be silently clipped or unreachable.

`design-lab/tests/e2e/audit_workbench_overflow.mjs` measures the rendered
Workbench in a real Chromium served by the real Python loopback service and
fails on CLIPPED (content wider than its clipping box) and STRAY (painted past
the viewport with no scrollable ancestor). In strict mode it also fails on body
text below 11px.

This module is the CI-side harness for that gate. It mirrors
`test_workbench_design_layer_e2e.py` exactly where it matters: a synthetic
project root, an OS-chosen port, an in-memory token, and PROBE-driven honest
skips when the toolchain is absent. `verify_browser_e2e_ran.py` enforces the
no-skip policy, so a skip turns the required job red instead of quietly green.

The gate was FALSIFIED before being trusted (project iron rule), measured
2026-10-06 in this same CI-shaped configuration:

  - pre-fix checkout (main `f2172744`)  -> OV_SUMMARY clipped=5 stray=8 tiny=70, exit 1
  - post-fix checkout (audit commit)    -> OV_SUMMARY clipped=0 stray=0 tiny=0, exit 0

so the job is not green merely because the synthetic fixture renders an empty
UI. It claims E2 controlled-runtime evidence only — geometry measured in a real
browser, not an E3 host run, not an E4 human visual jury, and no claim that the
UI looks good.
"""
import json
import re
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
GATE_SCRIPT = _TESTS_DIR / 'e2e' / 'audit_workbench_overflow.mjs'
# 1440 / 1280 / 1536 / 1920: the last three are the Windows 100 % / 125 % / 150 % zoom cases on a
# 1920-wide panel (1920 ÷ scale = CSS px), which is what DL-KB-13 asks the geometry receipts to
# cover; 1440 is the laptop width this product is also used at.
WIDTHS = os.environ.get('OV_WIDTHS', '1440,1280,1536,1920')


def _evidence_dir():
    override = os.environ.get('E2E_EVIDENCE_DIR')
    if override:
        return Path(override)
    return ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e'


def vucc_utility_names():
    """The class names the static conflict gate guards.

    Both guards must cover the same set: if the stylesheet gains a utility that only one of them
    knows about, the other silently stops being relevant and nothing says so.
    """
    import importlib.util
    script = ROOT / 'scripts' / 'verify_utility_class_conflicts.py'
    spec = importlib.util.spec_from_file_location('verify_utility_class_conflicts', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return sorted(module.UTILITIES)


class WorkbenchOverflowGateTests(unittest.TestCase):
    def _run_gate(self, report_name, theme_env=None):
        """Boot the real service, run the audit once, and hand back what it printed.

        Factored out because the theme is a parameter of this gate, not of the browser: the
        stylesheet re-points the neutral family per `data-palette`/`data-scheme`, so the same
        layout can collapse under one theme and hold under another. Only the default theme was
        ever measured here, while the contrast and theme-geometry gates already sweep more than
        one -- an unmeasured theme is an unshipped theme.
        """
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
            self.skipTest('E2E toolchain unavailable: no locally installed Chromium '
                          'revision found (probe $E2E_BROWSER / ms-playwright registry)')

        sys.path.insert(0, str(ROOT / 'src'))
        from design_lab.service import ProjectService
        from design_lab.http_service import make_server
        from unittest.mock import patch

        parent = ROOT / '.project-local' / 'task-runtime' / 'e2e-overflow-gate'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        root = Path(tmp.name)
        (root / 'AGENTS.md').write_text('# synthetic overflow-gate project', encoding='utf-8')
        token = secrets.token_hex(32)

        evidence = _evidence_dir()
        evidence.mkdir(parents=True, exist_ok=True)
        report_path = evidence / report_name
        # Windows: subprocess.run(capture_output=..., timeout=...) can leave the
        # pipe handle blocking after the child is killed, so the child writes to
        # a file and we wait on the process instead of the pipe.
        log_path = parent / (report_name.replace('.json', '') + '.log')

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
                    'OV_WIDTHS': WIDTHS,
                    'OV_STRICT': '1',
                    'OV_OUT': str(report_path),
                    **(theme_env or {}),
                }
                with open(log_path, 'w', encoding='utf-8') as logf:
                    proc = subprocess.Popen(
                        [node, str(GATE_SCRIPT)], env=env, stdout=logf,
                        stderr=subprocess.STDOUT, cwd=str(ROOT))
                    try:
                        code = proc.wait(timeout=240)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        self.fail('E2E_OVERFLOW_TIMEOUT: the gate did not finish in 240s')
                with open(log_path, encoding='utf-8', errors='replace') as fh:
                    out = fh.read()
            finally:
                server.shutdown()
                worker.join()
                server.server_close()
                tmp.cleanup()
        return code, out, report_path

    def _fail_open(self, code, out, report_path):
        summary = next((line for line in out.splitlines()
                        if line.startswith('OV_SUMMARY')), out[-800:])
        if code != 0:
            self.fail(f'OVERFLOW_GATE_FAILED (exit {code}) widths={WIDTHS} strict=1\n'
                      f'{summary}\n--- output ---\n{out[-3000:]}')
        self.assertIn('OV_OK', out, f'gate exited 0 without OV_OK:\n{out[-2000:]}')
        self.assertTrue(report_path.is_file(),
                        f'gate produced no report at {report_path}')
        return json.loads(report_path.read_text(encoding='utf-8'))

    # `#route-view` is what a screen-reader user navigates by heading, so a jump from h2 straight
    # to h4 reads as a section that vanished. axe reports that only when it evaluates the node, and
    # it declined 9-71 nodes per screen here, so the rendered sequence is asserted instead.
    # `workbench` is the landing route: its h1 is the static header outside the route view, so it
    # has no heading in here by design -- the exception is named rather than left implicit.
    HEADINGLESS_ROUTES = {'workbench'}

    def _assert_heading_order(self, report):
        measured = 0
        for key, value in sorted(report['routes'].items()):
            if '+' in key or not isinstance(value, dict) or 'headings' not in value:
                continue
            route = key.split(':', 1)[-1]
            headings = value['headings']
            self.assertIsNone(headings.get('skip'),
                              f'{key}: the rendered heading order skips a level '
                              f'({headings.get("skip")})')
            if headings.get('levels'):
                measured += 1
            else:
                self.assertIn(route, self.HEADINGLESS_ROUTES,
                              f'{key}: this screen renders no heading at all, so a screen reader '
                              'has nothing to jump to')
        self.assertGreaterEqual(measured, 15,
                                f'only {measured} screens produced a heading sequence; the '
                                'measurement has stopped covering the route table')

    def test_the_heading_assertion_can_fail(self):
        """A guard nobody has seen red guards nothing: both branches are planted here."""
        skipped = {'routes': {'1440:dashboard': {'headings': {
            'levels': [2, 4], 'skip': 'h2 -> h4 at "某面板"'}}}}
        with self.assertRaises(AssertionError) as raised:
            self._assert_heading_order(skipped)
        self.assertIn('skips a level', str(raised.exception))

        nameless = {'routes': {'1440:dashboard': {'headings': {'levels': [], 'skip': None}}}}
        with self.assertRaises(AssertionError) as raised:
            self._assert_heading_order(nameless)
        self.assertIn('no heading at all', str(raised.exception))

        # The count floor is what stops a measurement that quietly stopped measuring from
        # passing as a clean run.
        thin = {'routes': {f'1440:r{i}': {'headings': {'levels': [2, 3], 'skip': None}}
                           for i in range(3)}}
        with self.assertRaises(AssertionError) as raised:
            self._assert_heading_order(thin)
        self.assertIn('stopped covering the route table', str(raised.exception))

    def _assert_utility_geometry(self, report, label):
        """Every element carrying a layout utility must actually compute the token's value.

        This is the browser-side half of the guard: the static conflict check can see that two
        classes set the same property, but only the rendered style says who won. Both regressions
        from folding inline styles into `.spaced-top` / `.grid-stack` were invisible to every
        existing assertion because none of them measures inter-panel spacing.
        """
        checked = 0
        seen: dict[str, int] = {}
        for key, value in sorted(report['routes'].items()):
            if '+' in key or not isinstance(value, dict):
                continue
            geometry = value.get('utilityGeometry')
            if not geometry:
                continue
            checked += geometry['checked']
            for cls, count in (geometry.get('seen') or {}).items():
                seen[cls] = seen.get(cls, 0) + count
            self.assertTrue(geometry['tokens'].get('space2') and geometry['tokens'].get('space4'),
                            f'{label} {key}: the spacing tokens the utilities rely on did not '
                            f'resolve ({geometry["tokens"]})')
            self.assertEqual(geometry['bad'], [],
                             f'{label} {key}: a utility class lost the cascade -- '
                             + '; '.join(f".{b['cls']} expected {b['prop']}:{b['want']} but "
                                         f"computed {b['got']} alongside .{b.get('coClasses') or '-'}"
                                         for b in geometry['bad']))
        # Division of labour, stated because it is load-bearing: the static gate covers all twenty
        # sites, this one covers the sites the fixture actually renders. `grid-stack` lives on panels
        # that need data the walk does not always have, so an absent utility is reported as coverage
        # rather than failed -- and the static conflict check is what guards those sites meanwhile.
        self.assertGreaterEqual(checked, 1,
                                f'{label}: no rendered element carried any utility class '
                                f'({seen}); this pass computed nothing')
        missing = sorted(set(vucc_utility_names()) - set(seen))
        if missing:
            print(f'NOTE {label} computed only {seen}; not rendered under this fixture: {missing} '
                  '(guarded statically by scripts/verify_utility_class_conflicts.py)')

    #: The three states a first-screen plan column can be in, and the one sentence shape that
    #: would be a lie in the first two. Each marker is a phrase workbench.ts actually writes:
    #: 没有读过 (no project selected), 没读到 (the read was refused), 未读回 (the answer had no
    #: `plans` field). '没有方案记录' or '共 0 条' says the *project* has none, which only the
    #: real zero state may say.
    UNREAD_MARKERS = ('没有读过', '没读到', '未读回')
    ZERO_CLAIM_MARKERS = ('没有方案记录', '共 0 条')

    def _assert_first_screen_columns(self, report, label):
        """首屏两列：asserted on the painted boxes, not on the markup.

        The cut moved the two import panels into a left column and put 最近方案 in the right one.
        Whether a browser actually lays that out as two columns is a computed-style fact that a
        static check cannot see: a media query or a missing `min-width:0` collapses it back to one
        column without any error, and the panel then sits below the fold instead of beside it. The
        landing is the only route whose reading is non-null, because `#workspace` is hidden on
        every route view -- so an absent reading is graded here as a hole, not skipped.
        """
        landings = [key for key in report['routes']
                    if ':' in key and key.split(':', 1)[-1] == 'workbench' and '+' not in key]
        self.assertGreaterEqual(len(landings), 2,
                                f'{label}: the landing was geometry-measured at only '
                                f'{landings} width(s), so this pass covers nothing')
        for key in sorted(landings):
            screen = report['routes'][key].get('firstScreen')
            self.assertIsNotNone(screen,
                                 f'{label} {key}: the landing produced no first-screen reading, '
                                 'so the two columns were never looked at')
            self.assertEqual(screen['colCount'], 2,
                             f'{label} {key}: `.grid` has {screen["colCount"]} column child(ren), '
                             'expected the two `.col` wrappers')
            self.assertEqual(screen['tracks'], 2,
                             f'{label} {key}: the landing computes {screen["tracks"]} grid '
                             f'track(s) over {screen["viewport"][0]}px, so the cut is one column '
                             f'({screen["colBoxes"]})')
            self.assertTrue(screen['sideBySide'],
                            f'{label} {key}: the two columns do not sit side by side: '
                            f'{screen["colBoxes"]}')
            first, second = screen['colBoxes'][0], screen['colBoxes'][1]
            self.assertLessEqual(first['right'], second['x'] + 1,
                                 f'{label} {key}: the columns overlap: {screen["colBoxes"]}')
            self.assertTrue(screen['plansFound'],
                            f'{label} {key}: no panel wraps #recent-plans on the landing')
            self.assertTrue(screen['plansInSecondCol'],
                            f'{label} {key}: 最近方案 is not inside the second column, so the cut '
                            'this gate exists for did not land')
            box = screen['plansBox']
            self.assertLessEqual(box['right'], screen['viewport'][0],
                                 f'{label} {key}: the plan panel runs past the viewport edge '
                                 f'({box["right"]} > {screen["viewport"][0]})')
            self.assertLessEqual(screen['pageWide'], 0,
                                 f'{label} {key}: the document is {screen["pageWide"]}px wider '
                                 'than the viewport with the landing showing')
            # Painted, not merely present: a box with no height is a sentence nobody reads.
            self.assertGreater(screen['infoBox']['w'], 0, f'{label} {key}: the meta line is unplaced')
            self.assertGreater(screen['infoBox']['h'], 0, f'{label} {key}: the meta line is unplaced')
            text = screen['infoText'] or ''
            rows = screen['rowCount']
            unread = any(mark in text for mark in self.UNREAD_MARKERS)
            if rows > 0:
                self.assertTrue(screen['firstRow'],
                                f'{label} {key}: {rows} row(s) were counted but none carries text')
                self.assertFalse(unread,
                                 f'{label} {key}: the column paints {rows} plan row(s) and its own '
                                 f'line says it read nothing: {text!r}')
                self.assertIn('读到 %d 条' % rows, text,
                              f'{label} {key}: the printed count and the painted list disagree -- '
                              f'{rows} row(s) are on screen, the line says {text!r}')
            else:
                self.assertTrue(unread or '读到 0 条' in text,
                                f'{label} {key}: with nothing painted the line must say either '
                                f'that it read nothing or that the project has zero plans, and it '
                                f'says {text!r}')
                if unread:
                    self.assertFalse(any(mark in text for mark in self.ZERO_CLAIM_MARKERS),
                                     f'{label} {key}: a column that never got an answer claims the '
                                     f'project has no plans: {text!r}')

    def test_the_first_screen_column_assertion_can_fail(self):
        """Both directions are planted, so this guard cannot pass by being unconditional."""
        base_box = {'x': 0, 'y': 400, 'w': 600, 'h': 700, 'right': 600, 'bottom': 1100}
        good = {'firstScreen': {
            'colCount': 2, 'colBoxes': [base_box, dict(base_box, x=620, right=1220)],
            'tracks': 2, 'sideBySide': True, 'plansFound': True, 'plansInSecondCol': True,
            'plansBox': dict(base_box, x=620, right=1220, h=250, bottom=650),
            'rowCount': 1, 'firstRow': '为秋季新品做一张克制的主视觉海报',
            'infoText': '这一页读到 1 条，服务按写入时间倒序发回；这个项目共 1 条。',
            'infoBox': {'x': 640, 'y': 460, 'w': 500, 'h': 20, 'right': 1140, 'bottom': 480},
            'viewport': [1440, 900], 'pageWide': 0}}
        report = {'routes': {'1440:workbench': good, '1280:workbench': good}}
        self._assert_first_screen_columns(report, 'planted/good:')

        stacked = {'firstScreen': dict(good['firstScreen'], tracks=1, sideBySide=False,
                                       colBoxes=[base_box, dict(base_box, x=0, right=600)])}
        with self.assertRaises(AssertionError) as raised:
            self._assert_first_screen_columns(
                {'routes': {'1440:workbench': stacked, '1280:workbench': stacked}},
                'planted/stacked:')
        self.assertIn('grid track', str(raised.exception))

        wrong_col = {'firstScreen': dict(good['firstScreen'], plansInSecondCol=False)}
        with self.assertRaises(AssertionError) as raised:
            self._assert_first_screen_columns(
                {'routes': {'1440:workbench': wrong_col, '1280:workbench': wrong_col}},
                'planted/wrong-col:')
        self.assertIn('second column', str(raised.exception))

        miscounted = {'firstScreen': dict(
            good['firstScreen'], rowCount=2,
            infoText='这一页读到 5 条，服务按写入时间倒序发回；这个项目共 5 条。')}
        with self.assertRaises(AssertionError) as raised:
            self._assert_first_screen_columns(
                {'routes': {'1440:workbench': miscounted, '1280:workbench': miscounted}},
                'planted/miscounted:')
        self.assertIn('disagree', str(raised.exception))

        silent_rows = {'firstScreen': dict(
            good['firstScreen'], infoText='未选项目，因此这一列没有读过任何方案。')}
        with self.assertRaises(AssertionError) as raised:
            self._assert_first_screen_columns(
                {'routes': {'1440:workbench': silent_rows, '1280:workbench': silent_rows}},
                'planted/silent-rows:')
        self.assertIn('says it read nothing', str(raised.exception))

        lying = {'firstScreen': dict(good['firstScreen'], rowCount=0, firstRow=None,
                                     infoText='未选项目，这一列没有读过任何方案；'
                                              '所以这个项目还没有方案记录。')}
        with self.assertRaises(AssertionError) as raised:
            self._assert_first_screen_columns(
                {'routes': {'1440:workbench': lying, '1280:workbench': lying}},
                'planted/lying:')
        self.assertIn('claims the', str(raised.exception))

        blind = {'routes': {'1440:workbench': {'firstScreen': None},
                            '1280:workbench': {'firstScreen': None}}}
        with self.assertRaises(AssertionError) as raised:
            self._assert_first_screen_columns(blind, 'planted/blind:')
        self.assertIn('never looked at', str(raised.exception))

    def test_no_clipped_or_unreachable_text_in_real_browser(self):
        if not GATE_SCRIPT.is_file():
            self.skipTest(f'overflow gate script missing: {GATE_SCRIPT}')
        code, out, report_path = self._run_gate('workbench-overflow-gate.json')
        report = self._fail_open(code, out, report_path)
        # A closed <details> keeps layout boxes for text Chromium does not paint, so the geometry
        # claims below only describe what a person can see if the gate opened those panels first.
        # The field counts how many each run expanded: zero everywhere means the step has gone and
        # CLIPPED / STRAY / TINY are once again measuring invisible layout.
        expanded = {key: value.get('detailsExpanded') for key, value in report['routes'].items()
                    if value.get('detailsExpanded')}
        self.assertTrue(expanded,
                        'no route reported expanding a collapsed detail, so this gate is measuring '
                        'boxes behind closed panels again: %s'
                        % sorted(report['routes'])[:3])
        self._assert_heading_order(report)
        self._assert_utility_geometry(report, 'design-lab/dark:')
        self._assert_first_screen_columns(report, 'design-lab/dark:')
        # Every named interaction has to have settled on something a reader can tell apart, and at
        # least one has to have actually read the ledger back: a panel that renders a refusal at
        # every width is well-formed UI over a readback nobody ever saw.
        interactions = {key: value for key, value in report['routes'].items() if '+' in key}
        self.assertTrue(interactions, 'the gate measured no button-gated panel at all')
        # Both click-opened panels must be measured at EVERY width the gate walks: a panel checked
        # at 1440 only is not a geometry claim about 1280 or 1920.
        measured_widths = [w.strip() for w in WIDTHS.split(',') if w.strip()]
        absent = ['%s:%s' % (w, panel) for w in measured_widths
                  for panel in ('knowledge+entry-detail', 'assistant+plan-detail',
                                'assistant+plan-compare', 'assistant+plan-feedback',
                                'target-profiles+combination')
                  if '%s:%s' % (w, panel) not in report['routes']]
        self.assertEqual(absent, [],
                         'these panel states were never geometry-checked, so their layout is '
                         'unclaimed rather than good: %s' % absent)
        # A row in the report is not the same fact as a row the gate graded. The first version of
        # this extension recorded both panels into the report without feeding the counters, so
        # clipped/stray/occluded on an opened panel would have been printed and ignored -- a
        # coverage claim with nothing behind it. The summary's own count must equal the rows.
        panel_rows = [k for k in report['routes'] if '+' in k]
        graded = int(re.search(r'interactions=(\d+)', out).group(1))
        self.assertEqual(graded, len(panel_rows),
                         'the gate reported %d button-gated panels but graded %s, so a defect in '
                         'the ungraded ones would print and pass: %s'
                         % (len(panel_rows), graded, sorted(panel_rows)))
        for key, value in sorted(interactions.items()):
            self.assertIn(value.get('state'), ('read', 'refused'),
                          f'{key} settled on {value.get("state")!r}, which is neither a read-back '
                          'nor a named refusal')
        self.assertIn('read', {value.get('state') for value in interactions.values()},
                      'no width ever displayed the readback itself; the gate would have passed on '
                      'an error card, so the rendered panel is unverified')
        # The brand mark at every width the gate walked. `decode` is the load-bearing one: it is
        # the browser reporting that the inlined data URI loaded as an SVG document, how many
        # paths it carries, and which brand ink it was drawn in -- the only proof here that the
        # stylesheet paints the mark rather than a declaration pointing at nothing. It used to
        # read `144x144`, the natural size of the superseded bitmap cut-out, and a bloom on the
        # tile; both belonged to the retired pipeline.
        brand = report.get('brand', {})
        measured = [w.strip() for w in WIDTHS.split(',') if w.strip()]
        self.assertEqual(sorted(brand, key=str), sorted(measured, key=str),
                         'the gate reported the brand mark for some widths and not others')
        for width, seen in brand.items():
            self.assertTrue(seen.get('present'), f'{width}: no .app-nav-mark was mounted')
            self.assertEqual(seen.get('text', 'x'), '',
                             f'{width}: the figure carries text, so a screen reader says the name twice')
            self.assertEqual(seen.get('ariaHidden'), 'true',
                             f'{width}: the decorative figure is exposed to assistive tech')
            decoded = seen.get('decode') or {}
            self.assertTrue(decoded.get('loads'),
                            f'{width}: the inlined data uri did not load as an image at all')
            self.assertTrue(decoded.get('svg'),
                            f'{width}: the inlined mark is not an svg document')
            self.assertEqual(decoded.get('paths'), 2,
                             f'{width}: the mark decoded with {decoded.get("paths")} paths, not the '
                             'two of the tracked monogram')
            self.assertEqual(decoded.get('fills'), ['#EEF2F5'],
                             f'{width}: the default palette should paint the paper glyph, got '
                             f'{decoded.get("fills")}')
            self.assertGreater(seen.get('uriChars', 0), 500,
                               f'{width}: the data URI is a stub, not the mark')
            self.assertIn('DESIGN-LAB', seen.get('name', ''),
                          f'{width}: the wordmark is missing beside the figure')
            if seen.get('size', [0, 0])[0]:
                self.assertEqual(seen['size'], [22, 22],
                                 f'{width}: the mark box is {seen["size"]}, not the declared 22px')


    def test_the_ui2026_light_theme_is_graded_by_the_same_geometry_gate(self):
        """DL-UI-U02's rule applied to layout: an unmeasured theme is an unshipped theme.

        The theme re-points the neutral family -- background, surface, border, text and the
        status colours -- and a border or surface width that only exists under one palette can
        change what fits. Contrast and theme geometry already sweep the combinations; this gate
        owns CLIPPED / STRAY / TINY / the nav-cut boundary and the scroll cue, and until now it
        measured one theme.
        """
        if not GATE_SCRIPT.is_file():
            self.skipTest(f'overflow gate script missing: {GATE_SCRIPT}')
        code, out, report_path = self._run_gate(
            'workbench-overflow-gate-ui2026-light.json',
            {'UI_PALETTE': 'ui2026', 'UI_SCHEME': 'light'})
        report = self._fail_open(code, out, report_path)
        # The receipt has to name the theme it describes, or a green file is ambiguous about
        # which subject was actually cleared.
        self._assert_utility_geometry(report, 'ui2026/light:')
        self._assert_first_screen_columns(report, 'ui2026/light:')
        self.assertEqual('ui2026', report['uiPalette'])
        self.assertEqual('light', report['uiScheme'])
        # The sidebar boundary that started this: the nav's cut line must not sit on the
        # identity footer's hairline under either theme.
        for width, edge in sorted(report['navEdge'].items()):
            self.assertGreaterEqual(
                edge['gap'], 6,
                f'ui2026/light @{width}: footer hairline {edge["gap"]}px under the nav cut '
                f'line{" with a group label half-cut on it" if edge["labelStraddling"] else ""}')
        self.assertTrue(report['brand'], 'the themed run measured no brand tile')
        for width, seen in report['brand'].items():
            if seen.get('size', [0])[0]:
                self.assertEqual([48, 48], seen['size'],
                                 f'ui2026/light @{width}: the tile is {seen["size"]}, not 48x48')


    def test_the_stitch_pearl_theme_is_graded_by_the_same_geometry_gate(self):
        """Same rule the 20261009 baseline established, applied to the 20261023 pack's palette:
        an unmeasured theme is an unshipped theme.

        The stitch palette re-points the neutral family (background, surface, border, text, muted)
        and the accent, so it can change what fits as well as what is readable -- and it ships as an
        additive third choice, which is exactly the case a geometry gate must not skip.
        """
        if not GATE_SCRIPT.is_file():
            self.skipTest(f'overflow gate script missing: {GATE_SCRIPT}')
        code, out, report_path = self._run_gate(
            'workbench-overflow-gate-stitch-light.json',
            {'UI_PALETTE': 'stitch', 'UI_SCHEME': 'light'})
        report = self._fail_open(code, out, report_path)
        self._assert_utility_geometry(report, 'stitch/light:')
        self._assert_first_screen_columns(report, 'stitch/light:')
        self.assertEqual('stitch', report['uiPalette'])
        self.assertEqual('light', report['uiScheme'])
        for width, edge in sorted(report['navEdge'].items()):
            self.assertGreaterEqual(
                edge['gap'], 6,
                f'stitch/light @{width}: footer hairline {edge["gap"]}px under the nav cut '
                f'line{" with a group label half-cut on it" if edge["labelStraddling"] else ""}')
        # The panels this round started opening must be graded under the new palette too, not only
        # under the two themes that were already measured: a panel checked in one palette only is
        # an untested surface in the others.
        measured_widths = [w.strip() for w in WIDTHS.split(',') if w.strip()]
        absent = ['%s:%s' % (w, panel) for w in measured_widths
                  for panel in ('knowledge+entry-detail', 'assistant+plan-detail',
                                'assistant+plan-compare', 'assistant+plan-feedback')
                  if '%s:%s' % (w, panel) not in report['routes']]
        self.assertEqual(absent, [],
                         'these panels were never geometry-checked under the stitch theme: %s'
                         % absent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
