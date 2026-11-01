# SPDX-License-Identifier: MIT
"""Workbench contrast gate: no rendered text may fall below WCAG 2.1 AA.

`design-lab/tests/e2e/audit_workbench_contrast.mjs` measures the real Workbench
in a real Chromium served by the real Python loopback service and fails on any
text run whose contrast against its painted background is under 4.5:1 (3:1 for
large text). Gradient backgrounds are resolved to their colour stops and the
worst stop is used, and ancestor opacity is composited in -- both are cases the
existing UI checks skip entirely.

This module is the CI-side harness. It mirrors
`test_workbench_overflow_gate.py` where it matters: a synthetic project root, an
OS-chosen port, an in-memory token, PROBE-driven honest skips when the toolchain
is absent, and a file-backed child process on Windows so a killed subprocess
cannot leave a pipe handle blocking. `verify_browser_e2e_ran.py` enforces the
no-skip policy across TEST_MODULES, so a skip turns the required job red instead
of quietly green.

FALSIFICATION RECORD (2026-10-06, this machine, real Chromium + real service):
  - the probe's WCAG reference table was mutated (#777777-on-#777777 expected 3:1
    instead of 1:1) -> "MATH ... got=1 want=3 WRONG", exit 1. The self-check is
    therefore not vacuous.
  - an earlier DOM-injection fixture was abandoned deliberately: the injected
    node's computed colour was not what the fixture set, so it proved the fixture
    rather than the gate. The maths is this gate's real failure mode, so the maths
    is what gets asserted.
  - two bugs the falsification caught first, either of which would have made the
    gate lie: background layers were composited inside-out, and an "or no stop at
    all" branch put an impossible background into the candidate set, so every
    gradient pill reported 1:1. 44 phantom offenders disappeared once both were
    fixed.
  - measured on the current build: checked=995 text runs, belowAA=0, mathBad=0 (2026-10-06).
  - 2026-10-24, same gate after it learned to open collapsed details and read OKLab: both themes
    measured 50 route-runs (24 routes x 1440/1920 plus the plan detail at each width),
    checked=14002 text runs, belowAA=0, collapsedOpened=6228, controlMisses=0, unparsable=0,
    colourBad=0, tightest margin 4.11:1 (dark) / 4.14:1 (light). That run is what found the two
    defects below, so the growth in `checked` is the point, not a side effect.
  - FALSE FAILURE the gate produced first, then a real one it produced second:
    · a closed `<details>` keeps a real layout box for text Chromium does not paint
      (`::details-content { content-visibility: hidden }`), so the invisible 接入明细 lines were
      graded against whatever sibling panel happened to own that pixel -- a 1.31:1 report on text
      nobody could read. Fixed by opening every detail before the sweep and counting the runs that
      brought in (`collapsed`), with a planted closed white-on-white control that is only reported
      when the opening really happened; without the control the skip would look like coverage loss.
    · `oklab(...)` -- how Chromium serialises a resolved `color-mix(in oklab, …)` -- was unparsable,
      which the gate refuses loudly rather than dropping the layer. The conversion is now graded
      against the CSS Color 4 spec's own four sRGB <-> OKLab vectors.

It claims E2 controlled-runtime evidence only: contrast computed from what a real
browser painted, not an E3 host run and not an E4 human judgement about whether
the UI looks good.
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
from unittest.mock import patch

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from test_workbench_design_layer_e2e import _find_browser, _find_node_modules_dir  # noqa: E402

ROOT = _TESTS_DIR.parents[1]
GATE_SCRIPT = _TESTS_DIR / 'e2e' / 'audit_workbench_contrast.mjs'
WIDTHS = os.environ.get('CT_WIDTHS', '1440,1920')


def _evidence_dir():
    override = os.environ.get('E2E_EVIDENCE_DIR')
    if override:
        return Path(override)
    return ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e'


_GATE_RUNS = {}


def _run_gate(env_extra):
    """Boot the real service on a synthetic root and run the probe once per distinct environment.

    Returns (exit_code, stdout, report_path) so every assertion shares one measurement rather than
    re-running the browser. The memo is not a speed convenience only: a test that reads the receipt
    back used to find no file at all, because the class that writes it runs later in alphabetical
    order -- and it papered over that with `skipTest`, which the no-skip policy correctly turns
    into a failure. Sharing one run inside the process makes the receipt always there.
    """
    key = json.dumps(env_extra, sort_keys=True)
    if key in _GATE_RUNS:
        return _GATE_RUNS[key]
    result = _run_gate_once(env_extra)
    _GATE_RUNS[key] = result
    return result


def _run_gate_once(env_extra):
    node = shutil.which('node')
    node_modules_dir = _find_node_modules_dir()
    browser = _find_browser()
    if not GATE_SCRIPT.is_file():
        raise unittest.SkipTest('contrast gate script missing: %s' % GATE_SCRIPT)
    if not node:
        raise unittest.SkipTest('E2E toolchain unavailable: node not on PATH')
    if not node_modules_dir:
        raise unittest.SkipTest('E2E toolchain unavailable: no resolvable `playwright`')
    if not browser:
        raise unittest.SkipTest('E2E toolchain unavailable: no locally installed Chromium')

    sys.path.insert(0, str(ROOT / 'src'))
    from design_lab.service import ProjectService
    from design_lab.http_service import make_server

    parent = ROOT / '.project-local' / 'task-runtime' / 'e2e-contrast-gate'
    parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.TemporaryDirectory(dir=parent)
    root = Path(tmp.name)
    (root / 'AGENTS.md').write_text('# synthetic contrast-gate project', encoding='utf-8')
    token = secrets.token_hex(32)

    evidence = _evidence_dir()
    evidence.mkdir(parents=True, exist_ok=True)
    # The path handed back to the caller has to be the path the child was told to write. It used to
    # be the baseline name regardless of CT_OUT, so a caller trusting the returned path could read
    # another run's receipt than the one its own invocation produced.
    report_path = evidence / Path(env_extra.get('CT_OUT')
                                  or 'workbench-contrast-gate.json').name

    with patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(root / '.project-local')}):
        service = ProjectService(str(root))
        server = make_server(service, token, port=0)
        port = server.server_address[1]
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            env = {
                **os.environ,
                'E2E_SERVICE_URL': 'http://127.0.0.1:%d' % port,
                'E2E_TOKEN': token,
                'E2E_NODE_MODULES': str(node_modules_dir),
                'E2E_BROWSER': str(browser),
                'CT_WIDTHS': WIDTHS,
                'CT_STRICT': '1',
                'CT_OUT': str(report_path),
                'CT_REFUSAL_WORDS': json.dumps(refusal_prefixes(), ensure_ascii=False),
                # Identity of THIS run, written into the receipt. CI uploads the whole evidence
                # directory, so a receipt whose palette and enforce-mode cannot be recovered from
                # its own bytes is a receipt that can be archived by accident -- which is what the
                # owner audit of 2026-10-26 found (finding 6). Derived from what this invocation
                # actually asked for, and spelled out rather than inherited: an ambient
                # CT_SPEC_ENFORCE in the runner's environment must not decide what a "baseline"
                # run enforced, and a themed run must not be labelled design-lab.
                'CT_RUN_PALETTE': str(env_extra.get('UI_PALETTE') or 'design-lab'),
                'CT_RUN_SCHEME': str(env_extra.get('UI_SCHEME') or 'dark'),
                'CT_SPEC_ENFORCE': str(env_extra.get('CT_SPEC_ENFORCE') or '0'),
                'CT_GIT_SHA': subprocess.run(
                    ['git', 'rev-parse', 'HEAD'], cwd=str(ROOT), capture_output=True,
                    text=True).stdout.strip(),
                **env_extra,
            }
            # One log per report, named after the report this run actually writes. Sharing one
            # path meant a themed run overwrote the default run's log -- and the receipt reads
            # CT_SUMMARY and CT_SPEC_ENFORCED out of that file, so a green themed receipt could
            # have quoted the other theme's numbers. `workbench-overflow-gate-<theme>.log`
            # already worked this way; this closes the same hole in the contrast harness.
            log_path = parent / (Path(env['CT_OUT']).stem + '.log')
            with open(log_path, 'w', encoding='utf-8') as logf:
                proc = subprocess.Popen([node, str(GATE_SCRIPT)], env=env, stdout=logf,
                                        stderr=subprocess.STDOUT, cwd=str(ROOT))
                try:
                    code = proc.wait(timeout=240)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    raise AssertionError('E2E_CONTRAST_TIMEOUT: gate did not finish in 240s')
            with open(log_path, encoding='utf-8', errors='replace') as fh:
                out = fh.read()
        finally:
            server.shutdown()
            worker.join()
            server.server_close()
            tmp.cleanup()
    return code, out, report_path


def refusal_prefixes():
    """The product's own refusal words, read out of shell.ts -- never hand-copied.

    `09_DESIGN.md:13` says 「错误紧邻字段」. The audit can only grade that over a population, and
    the local refusals are written into `p.view-hint` lines whose text opens with `未提交：`,
    `未签署：`, `未记录：` and friends. A second copy of that vocabulary in the test would drift
    from the product the same way the status-word list was warned about, so the set is derived
    here and passed to the gate as CT_REFUSAL_WORDS; an empty set is refused by the gate itself.
    """
    source = (ROOT / 'apps' / 'workbench' / 'shell.ts').read_text(encoding='utf-8')
    found = set(re.findall(r"textContent = [`'\"](未[一-鿿]{1,6})：", source))
    return sorted(found)


def _balanced(text):
    """The substring from a leading '{' through its matching '}', quote-aware.

    Used to read the argument literals of this module's own `_run_gate` calls out of its source.
    A regex would stop at the first '}' inside an f-string or a nested dict, and the receipt names
    are built with `_evidence_dir() / '...'`, so the scan has to track depth and string state the
    way the parser does.
    """
    depth = 0
    quote = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == '\\':
                index += 2
                continue
            if char == quote:
                quote = None
        elif char == '#':
            index = text.find('\n', index)
            if index == -1:
                break
            continue
        elif char in "'\"":
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[:index + 1]
        index += 1
    raise AssertionError('unbalanced braces in the scanned source')


BASELINE_KEYS = {'UI_PALETTE', 'UI_SCHEME', 'CT_WIDTHS', 'CT_SPEC_ENFORCE'}


def non_baseline_runs_without_a_name(source):
    """The `_run_gate` calls in `source` that change the configuration but write the baseline file.

    One function, because the guard and the plant that proves the guard have to agree on what the
    rule IS -- two copies of the predicate would let the plant convict a rule the test does not
    actually enforce.
    """
    found = []
    for literal in _run_gate_call_literals(source):
        keys = set(re.findall(r"'([A-Z_]+)':", literal))
        if keys & BASELINE_KEYS and 'CT_OUT' not in keys:
            found.append(sorted(keys))
    return found


def _run_gate_call_literals(source):
    """Every dict literal passed to `_run_gate(` in this module's own source."""
    for match in re.finditer(r'_run_gate\(\s*\{', source):
        brace = source.index('{', match.start())
        yield _balanced(source[brace:])


def _summary(out):
    line = next((l for l in out.splitlines() if l.startswith('CT_SUMMARY')), '')
    return dict(tok.split('=', 1) for tok in line.split()[1:] if '=' in tok)


def _spec_fields(out):
    """The three CT_SPEC lines merged into one dict.

    The pack's numbers are printed as three lines because they measure three different
    populations (text, controls, surfaces); the assertions read them as one record, so the
    merge happens here rather than in three places that could disagree about a key name.
    """
    fields = {}
    for line in out.splitlines():
        if not line.startswith('CT_SPEC'):
            continue
        for tok in line.split()[2:]:
            if '=' in tok and '[' not in tok and '/' not in tok:
                key, value = tok.split('=', 1)
                fields.setdefault(key, value)
    return fields


class WorkbenchContrastGateTests(unittest.TestCase):
    def test_every_rendered_text_run_meets_aa(self):
        code, out, report_path = _run_gate({})
        if code != 0:
            low = [l for l in out.splitlines() if l.strip().startswith('LOWCONTRAST')]
            detail = '\n'.join(low[:25])
            self.fail('CONTRAST_GATE_FAILED (exit %d) widths=%s\n'
                      '--- first 25 offenders ---\n%s\n--- tail ---\n%s'
                      % (code, WIDTHS, detail, out[-1200:]))
        self.assertIn('CT_OK', out, 'gate exited 0 without CT_OK:\n%s' % out[-2000:])
        self.assertTrue(report_path.is_file(), 'gate produced no report at %s' % report_path)
        # A probe that measured nothing would also print CT_OK, so coverage is
        # asserted separately from the verdict.
        checked = int(_summary(out).get('checked', '0'))
        self.assertGreaterEqual(checked, 500,
                                'probe measured only %d text runs; coverage is suspect' % checked)
        # The gate plants a white-on-`color(srgb 1 1 1)` pair on every route. Chromium
        # serialises a resolved color-mix() that way, so a parser that cannot read it drops
        # the background and grades the text against the page instead -- a 21:1 pass on a
        # 1:1 pair. Both fields must stay at zero or the pass counts are not trustworthy.
        summary = _summary(out)
        self.assertEqual(summary.get('controlMisses'), '0',
                         'the parser control was not caught somewhere: %s' % summary)
        self.assertEqual(summary.get('unparsable'), '0',
                         'a colour the page computes could not be parsed, so at least one '
                         'background was dropped from the stack: %s' % summary)
        # OKLab is a colour space this page actually computes in (a resolved
        # `color-mix(in oklab, …)`), and the conversion is graded against the CSS Color 4
        # spec's own vectors rather than a helper of this file's.
        self.assertEqual(summary.get('colourChecks'), '4',
                         'the oklab->sRGB reference vectors did not run: %s' % summary)
        self.assertEqual(summary.get('colourBad'), '0',
                         'the oklab conversion disagrees with published spec vectors: %s'
                         % summary)
        # The veil control answers a different question: text seen *through* a scrim must be
        # graded against the blended pairing. Its own document, because a fixture has to be
        # inside the viewport for a hit test to find it.
        self.assertIn('CT_VEIL_CONTROL caught=yes', out,
                      'the translucent-veil control did not fire: %s' % out[-800:])
        self.assertIn('obscured', summary,
                      'obscured text runs are no longer counted: %s' % summary)
        # Collapsed `<details>` text is painted only once a person opens it, so a route sweep
        # that never expanded would silently measure a fraction of the screen it names. The count
        # has to be non-zero for the population to include that content at all.
        self.assertGreaterEqual(int(summary.get('collapsedOpened', '0')), 1,
                                'not one collapsed run was brought into the sweep, so this '
                                'gate only measures whatever the page happened to leave open: %s'
                                % summary)
        # The plan detail and the knowledge entry detail are the two panels this gate opens by
        # clicking into; a name in the log is not proof either was measured under every width, so
        # the report itself is read back. Both are asserted because the entry detail's row title
        # is exactly where a real AA failure turned up the moment it started being measured.
        import json
        recorded = json.loads(report_path.read_text(encoding='utf-8'))
        # A baseline receipt has to identify itself too, otherwise "the archive is clean" is a
        # claim about an unknown configuration.
        self.assertEqual((recorded.get('run') or {}).get('specEnforce'), False,
                         'the baseline receipt does not state that it ran without pack-number '
                         'enforcement, so a planted-red run could not be distinguished from it')
        self.assertEqual((recorded.get('run') or {}).get('palette'), 'design-lab')
        wanted = ['%s:assistant+plan-detail' % w for w in WIDTHS.split(',')]
        wanted += ['%s:assistant+plan-compare' % w for w in WIDTHS.split(',')]
        wanted += ['%s:assistant+plan-feedback' % w for w in WIDTHS.split(',')]
        wanted += ['%s:knowledge+entry-detail' % w for w in WIDTHS.split(',')]
        wanted += ['%s:target-profiles+combination' % w for w in WIDTHS.split(',')]
        # The dirty CTA is the state CI's Linux runner convicted and the local sweep kept
        # walking past; if it is absent from the report, its contrast is unclaimed, not good.
        wanted += ['%s:target-profiles+combination-after-change' % w for w in WIDTHS.split(',')]
        missing = [k for k in wanted if k not in recorded.get('routes', {})]
        self.assertEqual(missing, [],
                         'these panel states were never measured, so their contrast is unclaimed '
                         'rather than good: %s' % missing)
        self.assertIs(recorded.get('auditSeed', {}).get('product_data'), False,
                      'the seeded plan must be recorded as synthetic scaffolding')
        self.assertIs(recorded.get('auditKnowledgeSeed', {}).get('product_data'), False,
                      'the seeded knowledge entry must be recorded as synthetic scaffolding')

    def test_a_run_clipped_by_its_own_scroller_is_excluded_and_named(self):
        """The clip rule has to be able to fail in BOTH directions, or it is not a rule.

        A text run that an ancestor's `overflow` has scrolled entirely out of that ancestor's box
        paints nothing, so grading it invents an offender. The shipped rail produced exactly that:
        `.nav{overflow:auto}` scrolled to y=817 left a nav label laid out at y=20 while the nav's
        own box starts at y=125, and the gate composited that invisible label against the
        semi-transparent sidebar gradient it happened to overlap and convicted it at 1.5:1.

        Excluding unpainted text is only honest if the sweep keeps grading the text that IS
        painted, so one run is planted clipped (must be named in `clippedOutExamples`, must never
        become a product row) and one is planted in the open (must still be convicted) in the same
        measurement. A gate that dropped everything would pass the first half and fail this one.
        """
        import json
        code, out, report_path = _run_gate({})
        low = [l for l in out.splitlines() if l.strip().startswith('LOWCONTRAST')]
        self.assertEqual(code, 0, 'the AA sweep still convicts a non-rendered run; first '
                                  'offenders=%s' % low[:6])
        recorded = json.loads(report_path.read_text(encoding='utf-8'))
        total = (recorded.get('run') or {}).get('clippedOutOfScroller')
        self.assertIsInstance(total, int,
                              'the receipt does not publish how many runs the clip rule excluded, '
                              'so the exclusion could not be audited: %s' % recorded.get('run'))
        self.assertGreaterEqual(total, 1,
                                'the clip rule excluded nothing at all, which means it is dead '
                                'code and the rail offender is still being graded')
        routes = recorded.get('routes') or {}
        examples = [e for row in routes.values() for e in row.get('clippedOutExamples') or []]
        self.assertTrue(any('#ct-clipped' in e for e in examples),
                        'the planted zero-height-overflow control was not excluded, so the rule '
                        'does not fire on a fully clipped run: %s' % examples[:6])
        product = [f_ for row in routes.values() for f_ in row.get('productFails') or []]
        self.assertFalse([f_ for f_ in product if 'ct-clipped' in f_['el']],
                         'the clipped control was graded anyway, so the exclusion is a label '
                         'and not a skip: %s' % product[:4])
        convicted = [f_ for row in routes.values() for f_ in row.get('fails') or []
                     if '#ct-control' in f_['el']]
        self.assertTrue(convicted,
                        'the open white-on-white control stopped being convicted at the same '
                        'moment the new skip started working -- the sweep has stopped measuring')
        # The anti-blanket guard. Every excluded run is published, and the share is capped, so a
        # future page that clips its whole body cannot turn this gate green by measuring nothing.
        # `checked + clippedOut` is the population this pass looked at; the pre-skip number is
        # recovered from the receipt's own fields rather than from a remembered baseline.
        checked = sum(row.get('checked', 0) for row in routes.values())
        self.assertGreaterEqual(checked, 500,
                                'the sweep graded only %d runs after the clip rule, so coverage '
                                'collapsed rather than being corrected' % checked)
        self.assertLess(total * 2, checked + total,
                        'the clip rule now excludes at least half of the population it sees '
                        '(clipped=%d vs graded=%d); name what it is dropping before trusting '
                        'the green' % (total, checked))

    def test_ui2026_light_theme_is_graded_by_the_same_aa_gate(self):
        """DL-UI-U02 (2026-10-09): the 20261009 baseline ships as a *theme*, so it has
        to clear the same AA bar as the default one -- an unmeasured theme is an
        unshipped theme, and a screenshot glance is not a contrast measurement.

        The design-lab palette stays the default and keeps every pixel it had; the
        pack's values only re-point the neutral family (background / surface / border /
        text / the three status colours). Brand blues, --accent-hover and
        --border-strong stay at their measured floor values on purpose, so this case
        measures what the theme actually changed and not a re-brand.
        """
        report = _evidence_dir() / 'workbench-contrast-gate-ui2026-light.json'
        code, out, _ = _run_gate({
            'UI_PALETTE': 'ui2026',
            'UI_SCHEME': 'light',
            'CT_OUT': str(report),
        })
        if code != 0:
            low = [l for l in out.splitlines() if l.strip().startswith('LOWCONTRAST')]
            self.fail('CONTRAST_GATE_FAILED under ui2026/light (exit %d)\n'
                      '--- first 25 offenders ---\n%s\n--- tail ---\n%s'
                      % (code, '\n'.join(low[:25]), out[-1200:]))
        self.assertIn('CT_OK', out, 'gate exited 0 without CT_OK:\n%s' % out[-2000:])
        self.assertTrue(report.is_file(), 'themed run produced no report at %s' % report)
        # The receipt must name its own subject, or a green file says nothing about
        # which theme was measured.
        import json
        recorded = json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(recorded.get('uiPalette'), 'ui2026',
                         'the report does not say which palette it measured')
        self.assertEqual(recorded.get('uiScheme'), 'light',
                         'the report does not say which scheme it measured')
        checked = int(_summary(out).get('checked', '0'))
        self.assertGreaterEqual(checked, 500,
                                'themed probe measured only %d text runs; coverage is suspect'
                                % checked)
        summary = _summary(out)
        self.assertEqual(summary.get('controlMisses'), '0',
                         'the parser control was not caught under the new theme: %s' % summary)
        self.assertEqual(summary.get('unparsable'), '0',
                         'a colour the new theme computes could not be parsed: %s' % summary)

    def test_stitch_pearl_theme_is_graded_by_the_same_aa_gate(self):
        """DL-KB-06 follow-on (2026-10-25): the 20261023 pack's STITCH prompt names six exact
        colours and ships them as a third optional palette. Same rule as the 20261009 baseline --
        an unmeasured theme is an unshipped theme, and the pack's own numbers are no proof that
        its text is readable on its own background.

        The default palette is untouched by this theme (owner ruling: a new pack's colours become
        a selectable theme, never an override), and the measured floor values stay where the
        contrast gate put them, so what this case measures is exactly the six values.

        The pack's numbers are graded on the objects its sentence actually names. 圆角 6–10px is
        written for 输入/按钮, so the graded population is input/select/textarea plus the four
        action-button classes -- measured at 501 controls in this run. The other 909 painted
        controls are list rows, nav items and chips, and the same pack puts 面板 at 12–16px while
        its own reference HTML ships a 20px `.status` pill; those keep their radius and stay in the
        printed histogram. 控件高度 is written as 「约36–40px」, so it is reported (主动作 measures
        41–47px, i.e. taller than the target) and not asserted. Both readings are stated here
        because a band applied to a different population than the spec names is not a 1:1 check.
        """
        report = _evidence_dir() / 'workbench-contrast-gate-stitch-light.json'
        code, out, _ = _run_gate({
            'UI_PALETTE': 'stitch',
            'UI_SCHEME': 'light',
            'CT_OUT': str(report),
            # The 20261023 pack writes its visual rules as numbers too, and this is the theme
            # that carries the pack, so the same painted document is graded on both scales.
            'CT_SPEC_ENFORCE': '1',
        })
        if code != 0:
            low = [l for l in out.splitlines()
                   if l.strip().startswith(('LOWCONTRAST', 'SPEC-VIOLATION'))]
            self.fail('CONTRAST_GATE_FAILED under stitch/light (exit %d)\n'
                      '--- first 25 offenders ---\n%s\n--- tail ---\n%s'
                      % (code, '\n'.join(low[:25]), out[-1200:]))
        self.assertIn('CT_OK', out, 'gate exited 0 without CT_OK:\n%s' % out[-2000:])
        self.assertTrue(report.is_file(), 'themed run produced no report at %s' % report)
        import json
        recorded = json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(recorded.get('uiPalette'), 'stitch',
                         'the report does not say which palette it measured')
        self.assertEqual(recorded.get('uiScheme'), 'light',
                         'the report does not say which scheme it measured')
        summary = _summary(out)
        self.assertGreaterEqual(int(summary.get('checked', '0')), 500,
                                'themed probe measured only %s text runs; coverage is suspect'
                                % summary.get('checked'))
        self.assertEqual(summary.get('controlMisses'), '0',
                         'the parser control was not caught under the stitch theme: %s' % summary)
        self.assertEqual(summary.get('unparsable'), '0',
                         'a colour the stitch theme computes could not be parsed: %s' % summary)
        # Same panels as the default run: a theme that is only checked on the closed screens
        # has not been checked on the panels where this round added content.
        wanted = ['%s:assistant+plan-detail' % w for w in WIDTHS.split(',')]
        wanted += ['%s:assistant+plan-compare' % w for w in WIDTHS.split(',')]
        wanted += ['%s:assistant+plan-feedback' % w for w in WIDTHS.split(',')]
        wanted += ['%s:knowledge+entry-detail' % w for w in WIDTHS.split(',')]
        wanted += ['%s:target-profiles+combination' % w for w in WIDTHS.split(',')]
        # The dirty CTA is the state CI's Linux runner convicted and the local sweep kept
        # walking past; if it is absent from the report, its contrast is unclaimed, not good.
        wanted += ['%s:target-profiles+combination-after-change' % w for w in WIDTHS.split(',')]
        missing = [k for k in wanted if k not in recorded.get('routes', {})]
        self.assertEqual(missing, [],
                         'the stitch theme was never measured for these panels: %s' % missing)
        # The pack's numbers, read off the same painted document in the same run.
        self.assertIn('CT_SPEC_ENFORCED', out,
                      'CT_SPEC_ENFORCE=1 was set but the run never reported the pack numbers'
                      ' as enforced:\n%s' % out[-1500:])
        spec = _spec_fields(out)
        self.assertGreaterEqual(int(spec.get('textRuns', '0')), 1000,
                                'the pack-number pass looked at only %s text runs; coverage is '
                                'suspect' % spec.get('textRuns'))
        self.assertGreaterEqual(int(spec.get('formControls', '0')), 20,
                                'no form controls were measured, so the 6-10px radius band and '
                                'the control-height reading are both unmeasured claims')
        self.assertGreaterEqual(float(spec.get('minPx', '0')), 12,
                                'the pack puts the smallest readable text at 12px: %s' % spec)
        self.assertEqual(spec.get('below12'), '0',
                        '元数据至少12px is not satisfied under the pack theme: %s' % spec)
        self.assertEqual(spec.get('translucentTextHosts'), '0',
                        '长文字与列表实底 is not satisfied under the pack theme: %s' % spec)
        self.assertEqual(spec.get('glassOffAllowlist'), '0',
                        'backdrop-filter is used outside 顶栏／导航／临时面板: %s' % spec)
        self.assertEqual(spec.get('formRadiusOver10'), '0',
                        '圆角输入／按钮 6–10px is not satisfied under the pack theme: %s' % spec)
        self.assertEqual(spec.get('bigOver25pct'), '0',
                        '避免大面积渐变 is not satisfied under the pack theme: %s' % spec)
        # Reported, not asserted: flattening the accent produced two AA failures on CI's Linux
        # runner that the same bytes did not produce on Windows, so the pack's single-accent rule
        # stays an open, measured debt until a colour ruling lands.
        # The position rules measure a population, so the coverage is asserted even while the
        # verdict is still a report: 247 labelled controls and a non-empty heading ladder were
        # read off the painted document. A ruler that reports 0 labelled fields would mean the
        # selector broke, not that the UI is clean.
        self.assertGreaterEqual(int(spec.get('labelled', '0')), 200,
                                'only %s labelled controls were measured; the caption pass is not '
                                'reaching the forms' % spec.get('labelled'))
        self.assertIn('labelAbove', spec, 'the caption-placement count stopped being reported')
        # The heading ladder is a list, so it is read from the report rather than the log line.
        self.assertGreaterEqual(len(recorded.get('spec', {}).get('headingLadder') or []), 5,
                                'the heading ladder reported %r; the pass measured too little to '
                                'say anything about hierarchy'
                                % (recorded.get('spec', {}).get('headingLadder'),))
        self.assertIn('brandBluePaints', spec,
                      'the single-accent count stopped being measured at all: %s' % sorted(spec))
        self.assertGreater(int(spec.get('brandBluePaints', '0')), 0,
                           'the pack theme was expected to still carry the brand blues; if that '
                           'changed, re-read the CI finding in style.css before asserting zero')
        # The receipt carries the same numbers the log printed, so a reader holding the JSON can
        # check which pack rules this run graded without re-running the browser.
        recorded_spec = recorded.get('spec') or {}
        for key in ('below12', 'veilHosts', 'formRadiusOver10', 'bigGradients'):
            self.assertEqual(recorded_spec.get(key), 0,
                             'the report does not carry %s=0 from this run: %s'
                             % (key, sorted(recorded_spec)))
        self.assertEqual(recorded_spec.get('glassOffAllowlist'), [],
                         'the report lists glass surfaces outside the pack allowance: %s'
                         % recorded_spec.get('glassOffAllowlist'))

    def test_the_pack_number_assertion_refuses_a_theme_it_was_not_applied_to(self):
        """An assertion that cannot fail guards nothing. The 实底 fix is scoped to the pack's own
        theme (owner ruling: a new pack's values become a selectable theme, never an override of
        the shipped one), so the default palette still paints list rows on a translucent surface
        and the identical enforcement must go red there -- naming the pack sentence it enforces,
        not a generic failure. Run at one width: this is a red-proof, not a coverage sweep."""
        code, out, red_path = _run_gate({
            'UI_PALETTE': 'design-lab',
            'UI_SCHEME': 'dark',
            'CT_WIDTHS': '1440',
            'CT_SPEC_ENFORCE': '1',
            # A deliberate red is a measurement too, but it is not the baseline. Sharing the
            # baseline filename meant the last writer -- this falsifier, which runs after the
            # coverage cases in alphabetical order -- decided what CI archived.
            'CT_OUT': str(_evidence_dir() / 'workbench-contrast-gate-enforce-red.json'),
        })
        self.assertNotEqual(code, 0,
                            'the pack-number enforcement passed on a theme whose list rows are '
                            'still translucent, so the assertion is vacuous:\n%s' % out[-1500:])
        violations = [l for l in out.splitlines() if l.strip().startswith('SPEC-VIOLATION')]
        self.assertTrue(any('实底' in v for v in violations),
                        'the run failed, but not for the translucent-surface rule: %s' % violations)
        self.assertTrue(any('大面积渐变' in v for v in violations),
                        'the default theme was expected to keep its panel wash and grid, so the '
                        'gradient rule should be what goes red here too: %s' % violations)
        self.assertNotIn('CT_OK', out,
                        'a red pack-number run still printed the AA verdict, so the two are not'
                        ' separated in the log')
        # 元数据≥12px was raised globally, not per theme, so it must NOT be what goes red here.
        spec = _spec_fields(out)
        self.assertEqual(spec.get('below12'), '0',
                        'the 12px floor was only fixed for one palette, so the default theme '
                        'still ships 11px metadata: %s' % spec)
        # The separation is asserted, not assumed.
        self.assertTrue(red_path.is_file(), 'the falsification run wrote no receipt of its own')
        self.assertEqual(red_path.name, 'workbench-contrast-gate-enforce-red.json')
        red_report = json.loads(red_path.read_text(encoding='utf-8'))
        self.assertEqual((red_report.get('run') or {}).get('specEnforce'), True,
                         'the planted-red receipt does not say it enforced the pack numbers, so '
                         'its own bytes cannot tell it apart from a baseline run')
        self.assertEqual((red_report.get('run') or {}).get('widths'), '1440')

    def test_a_run_that_is_not_the_baseline_has_to_name_its_own_receipt(self):
        """The overwrite is only fixed until someone writes the next one, so the rule is graded on
        this file's own source: any gate invocation that changes the configuration -- a theme, a
        width list, or pack-number enforcement -- produces a receipt that is NOT the baseline and
        must therefore say so in its filename. Static, so it costs no browser.

        The defect the owner audit found was exactly this shape: a falsifier that enforced the pack
        numbers wrote over the passing run, and CI archives the whole evidence directory, so the
        artefact a reader trusted could be the deliberate red.
        """
        source = Path(__file__).read_text(encoding='utf-8')
        self.assertEqual(non_baseline_runs_without_a_name(source), [],
                         'these gate runs differ from the baseline configuration but write the '
                         'baseline filename, so the last of them decides what CI archives: %s'
                         % non_baseline_runs_without_a_name(source))

    def test_the_naming_rule_can_actually_catch_the_collision(self):
        """A guard that cannot fail guards nothing: drop the falsifier's own filename from a copy
        of this file and the rule has to convict it."""
        source = Path(__file__).read_text(encoding='utf-8')
        blinded = source.replace(
            "            'CT_OUT': str(_evidence_dir() / 'workbench-contrast-gate-enforce-red.json'),\n",
            '')
        self.assertNotEqual(blinded, source,
                            'the plant did not move the bytes, so this test says nothing about '
                            'the guard')
        offenders = non_baseline_runs_without_a_name(blinded)
        self.assertEqual(len(offenders), 1,
                         'the blinded copy was not convicted -- or several runs were -- so the '
                         'rule above does not describe the collision it exists to prevent: %s'
                         % offenders)
        self.assertEqual(offenders[0],
                         sorted(BASELINE_KEYS | {'UI_PALETTE'}),
                         'the convicted run is not the pack-number falsifier, so the plant missed '
                         'its target: %s' % offenders)

    def test_contrast_maths_reference_table_is_satisfied(self):
        """The probe recomputes published WCAG 2.1 ratios with the same lum()/ratio()
        it applies to real text. If that table were skipped, the verdict above would
        be measuring a broken formula."""
        _code, out, _rep = _run_gate({})
        summary = _summary(out)
        self.assertEqual(summary.get('mathChecks'), '4',
                         'reference table did not run: %s' % summary)
        self.assertEqual(summary.get('mathBad'), '0',
                         'contrast maths disagrees with WCAG reference ratios: %s' % summary)


class ActionButtonInkIsNotInterpolated(unittest.TestCase):
    """The AA gate convicted an ink that no stylesheet declares.

    Measured 2026-10-25 on this machine at 1920/stitch-light with a requestAnimationFrame
    sampler (one row per painted frame): #tp-validate's `color` ramped
    rgb(23,33,43) -> 74,82,90 -> 187,190,193 -> 226,227,228 -> 251,251,252 -> rgb(255,255,255)
    over ~230ms while its `background-color` faded from opaque white to transparent over the
    brand gradient. One of those frames -- rgb(187,190,193) seen through a 29% white veil on
    rgb(29,79,196) -- composes to 1.97:1. CI's Linux runner landed inside the same window and
    named rgb(157,161,165) at 1.06:1 (stitch) and rgb(209,213,217) at 2.6:1 (ui2026). Those two
    greys are exact linear blends of white with each theme's --text (#17212B at t=0.422 and
    #152b3d at t=0.198, all three channels agreeing), and enumerating document.styleSheets found
    only three `color` declarations matching the element -- all three white. That is why the
    reading was never reproducible on Windows: the local sweep always arrived after the ramp
    finished. The same commit, red only in the cloud, because the runner sampled a mid-frame.

    The cause is one `transition` shorthand with no property list, i.e. `transition-property:
    all`, on the four action-button classes. Both endpoints of the enabled/disabled swap clear
    AA; only the frames between them fail, so the fix is to stop interpolating the ink and the
    backdrop and keep the hover motion the rule was actually there for. The motion gate cannot
    catch this: `color` and `background` are not layout properties, so it discloses the
    `transition: all` count and declines to convict it -- contrast is a different ruler.
    """

    SELECTOR = r'\.ghost-btn,\.soft-btn,\.primary-btn,\.danger-btn'
    #: Properties whose interpolation puts a colour on screen that no rule declares.
    PAINTED = ('all', 'color', 'background', 'background-color')

    def _button_block(self):
        css = (ROOT / 'apps' / 'workbench' / 'style.css').read_text(encoding='utf-8')
        bare = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        block = re.search(self.SELECTOR + r'\{([^}]*)\}', bare)
        self.assertIsNotNone(block,
                             'the four action-button classes lost their shared rule, so this '
                             'guard is reading a stylesheet that no longer has one owner')
        return block.group(1)

    def _animated_properties(self):
        block = self._button_block()
        names = []
        shorthand = re.search(r'(?<![-\w])transition:([^;]*)', block)
        if shorthand:
            for layer in shorthand.group(1).split(','):
                tokens = [t.strip() for t in layer.split() if t.strip()]
                # A layer may be `transition: 200ms` (no property -> all) or
                # `transition: transform .2s ease`; the property is whichever token is not a
                # time/easing/fraction.
                named = [t for t in tokens
                         if not re.match(r'^[\d.]+m?s$', t)
                         and not t.startswith(('cubic-bezier', 'steps', 'ease', 'linear'))]
                names.append(named[0] if named else 'all')
        explicit = re.search(r'transition-property:([^;]*)', block)
        if explicit:
            names.extend(t.strip() for t in explicit.group(1).split(',') if t.strip())
        return names

    def test_the_action_buttons_do_not_animate_their_ink_or_their_backdrop(self):
        names = self._animated_properties()
        convicted = [n for n in names if n in self.PAINTED]
        self.assertEqual(
            convicted, [],
            'the shared action-button rule animates %s, so switching between the enabled and '
            'disabled ink paints every frame in between; the two endpoints clear AA and the '
            'blend between them does not (see this class docstring for the measured ramp). '
            'Full animated property list: %s' % (', '.join(convicted), names))


class MotionBandFollowsThePack(unittest.TestCase):
    """The pack's own motion sentence, graded over every transition in the stylesheet.

    `docs/taskpacks/20261023-ui-kb/source/09_DESIGN.md:21` says 「仅必要的120–180ms
    opacity/transform 过渡；减少动态效果时移除」. Before this ruler existed the shipped
    stylesheet had 20 `transition` declarations and 16 of them were outside that sentence:
    ten of them had no property list at all, which is `transition-property:all` -- the exact
    defect class that produced the CI-only AA red recorded in section 5.55, because `all`
    interpolates the ink and the backdrop as well as the movement. Measured then: 220ms at
    four sites, 200ms at two, 280ms at two, 550ms at one, and `background`, `border-color`,
    `box-shadow`, `filter` and the SVG geometry attribute `r` each animated somewhere.

    Durations are read after resolving `--motion-fast/-base/-slow` from the stylesheet's own
    definitions, so the ruler judges the number Chromium sees (120ms / 180ms / 280ms) rather
    than the token name, and a rule may move a token without this test noticing a string.

    This is a different ruler from `SRC-T07-MOTION-COMPOSITED`: that rule bans animating
    properties that re-lay-out, and it explicitly declines to convict `transition: all`
    (audit_workbench_motion.mjs publishes `transitionAllCount` instead). Paint properties and
    the pack's duration band are outside it, so silence there is not compliance here.
    """

    LOW = 120.0
    HIGH = 180.0
    ALLOWED = ('opacity', 'transform')
    # A step in `visibility` moves a panel into and out of the a11y tree; it interpolates no
    # painted value. Its own duration is 0s and only its delay rides along with the slide.
    COMPANION = ('visibility',)
    KILLS_MOTION = ('none',)
    TIMING_WORDS = ('ease', 'ease-in', 'ease-out', 'ease-in-out', 'linear', 'cubic-bezier',
                    'steps', 'step-start', 'step-end')
    #: Out-of-band declarations, by exact text, each with the reason it is not this product's
    #: motion. Pinned in both directions: a fourth entry, or one that stops existing, is red.
    EXCEPTIONS = {
        'all var(--motion-fast) cubic-bezier(.2,0,0,1)':
            '.ui-motion-fast is a B07 UIKIT export, not a workbench surface: zero consumers in '
            'build/main.js, in all eight apps/workbench/*.ts sources and in index.html',
        'all var(--motion-base) cubic-bezier(.2,0,0,1)':
            '.ui-motion-base, same B07 export and the same measured zero consumers',
        'all var(--motion-slow) cubic-bezier(.2,0,0,1)':
            '.ui-motion-slow is out of the pack band by 100ms, and its 0.28s is a value pinned '
            'by docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/evidence/'
            'W02-UTILITY-VERIFY.json ("ui-motion-slow = 0.28s (--motion-slow)"), so changing it '
            'here would rewrite a delivered UIKIT contract instead of this product',
    }

    def _declarations(self, css_text=None):
        """Every (line, raw value, properties, durations-in-ms) transition in the stylesheet."""
        text = css_text if css_text is not None else \
            (ROOT / 'apps' / 'workbench' / 'style.css').read_text(encoding='utf-8')
        # Blank comment bodies but keep their newlines: the prose in them explains durations,
        # and reading it as a declaration would convict a sentence instead of a rule.
        blanked = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)),
                         text, flags=re.S)
        tokens = dict(re.findall(r'(?<![-\w])(--motion-[a-z]+)\s*:\s*([^;]+);', blanked))

        def resolve(value):
            return re.sub(r'var\(\s*(--motion-[a-z]+)\s*\)',
                          lambda m: tokens.get(m.group(1).strip(), '0s'), value)

        rows = []
        for match in re.finditer(r'(?<![-\w])transition\s*:\s*([^;{}]+)', blanked):
            value = match.group(1).strip()
            line = blanked[:match.start()].count('\n') + 1
            props, durations, depth, current, entries = [], [], 0, '', []
            for ch in value:
                depth += ch == '('
                depth -= ch == ')'
                if ch == ',' and depth == 0:
                    entries.append(current)
                    current = ''
                else:
                    current += ch
            entries.append(current)
            for entry in entries:
                body = resolve(entry)
                head = re.match(r'\s*([a-zA-Z][-\w]*)', body)
                if head and head.group(1) not in self.TIMING_WORDS:
                    props.append(head.group(1))
                for number, unit in re.findall(r'(?<![\w.-])(\d*\.\d+|\d+)(ms|s)\b', body):
                    durations.append(float(number) * (1000.0 if unit == 's' else 1.0))
            rows.append((line, value, props, durations))
        return rows

    def _grade(self, rows):
        out_of_band = []
        for line, raw, props, durations in rows:
            if any(p in self.KILLS_MOTION for p in props):
                continue
            bad = []
            if not props:
                bad.append('no property list, i.e. transition-property:all')
            for prop in props:
                if prop in self.ALLOWED or prop in self.COMPANION:
                    continue
                bad.append('animates %s' % prop)
            for duration in durations:
                if duration and not (self.LOW <= duration <= self.HIGH):
                    bad.append('%gms is outside 120-180ms' % duration)
            if bad:
                out_of_band.append((line, raw, '; '.join(bad)))
        return out_of_band

    def test_every_shipped_transition_is_inside_the_pack_band(self):
        offenders = self._grade(self._declarations())
        unexpected = [o for o in offenders if o[1] not in self.EXCEPTIONS]
        self.assertEqual(
            unexpected, [],
            'these transitions violate 「仅必要的120–180ms opacity/transform 过渡」: %s'
            % '; '.join('style.css:%d %s (%s)' % o for o in unexpected))
        stale = [key for key in self.EXCEPTIONS
                 if key not in {row[1] for row in offenders}]
        self.assertEqual(
            stale, [],
            'the exception register still lists %s, which no longer appears as an out-of-band '
            'transition -- register entries may not outlive the rule they excuse' % stale)

    def test_the_ruler_convicts_a_planted_out_of_band_transition(self):
        """An assertion that cannot fail guards nothing, so plant three faults and re-read."""
        css = (ROOT / 'apps' / 'workbench' / 'style.css').read_text(encoding='utf-8')
        planted = css + ('\n.dl-motion-plant-a{transition:background-color 400ms ease}\n'
                         '.dl-motion-plant-b{transition:.5s ease}\n'
                         '.dl-motion-plant-c{transition:transform 90ms ease}\n')
        offenders = {(line, raw, why) for line, raw, why in self._grade(
            self._declarations(css_text=planted))}
        convicted = [o for o in offenders if 'dl-motion' not in o[1] and o[1] not in
                     self.EXCEPTIONS]
        by_raw = {raw: why for _, raw, why in offenders}
        self.assertIn('background-color 400ms ease', by_raw,
                      'the planted paint transition was not read at all')
        self.assertIn('animates background-color', by_raw['background-color 400ms ease'])
        self.assertIn('400ms is outside 120-180ms', by_raw['background-color 400ms ease'])
        self.assertIn('.5s ease', by_raw,
                      'a bare shorthand has no property list, so the plant was invisible')
        self.assertIn('no property list, i.e. transition-property:all', by_raw['.5s ease'])
        self.assertIn('transform 90ms ease', by_raw,
                      'a transform under the band floor was not convicted')
        self.assertEqual(len(convicted), 3,
                         'the three planted faults should all be new offenders, got %d'
                         % len(convicted))

    def test_no_shipped_transition_animates_the_ink_it_would_have_to_ramp(self):
        """Section 5.55 in one sentence: `all` anywhere in the product is the red's root cause.

        The action-button class checks its own rule; this one checks that nobody reintroduces
        the same shape on a different selector, because the failure only shows up when the
        runner samples mid-frame.
        """
        rows = self._declarations()
        painted = {'all', 'color', 'background', 'background-color', 'fill', 'stroke'}
        offenders = [(line, raw, p) for line, raw, props, _ in rows
                     for p in props if p in painted and raw not in self.EXCEPTIONS]
        self.assertEqual(
            offenders, [],
            'these declarations interpolate a colour, so a frame between the two endpoints '
            'paints an ink that no rule declares: %s' % offenders)


class EnhancedMotionLayerStaysComposited(unittest.TestCase):
    """The owner's enhanced-motion layer may only move things, never recolour them.

    Owner 2026-10-25 asked for more animation on top of the static reproduction
    (「STITCH 更多是静态页面 一比一复刻完成后 找牛逼的组件库 加入更多动画动效粒子等UI组件库」).
    Section 5.55 already proved what happens when this is done with colour: an interpolated
    ink is painted in a frame that exists in no stylesheet, and the AA gate can only catch it
    on the machine that happens to sample mid-ramp -- which is why that red was cloud-only.
    So the new layer ships transform-only, opt-in, and inert under prefers-reduced-motion.

    This reads the shipped source, not a screenshot: `apps/workbench/motion.ts` is inlined by
    Vite into `build/main.js`, so these writes are exactly what runs. It is a different
    instrument from `MotionBandFollowsThePack` above -- that one grades `transition:` in the
    stylesheet, and a JS `style.transform =` assignment appears in no CSS rule at all.
    """

    MOTION_TS = 'apps/workbench/motion.ts'
    #: Writing these via `el.style.X =` from the app layer is what put an undeclared grey on
    #: screen before. `willChange` is a hint and paints nothing.
    FORBIDDEN_STYLE_WRITES = ('color', 'background', 'backgroundcolor', 'fill', 'stroke',
                              'opacity', 'filter', 'boxshadow', 'bordercolor')

    def _source(self, override=None):
        if override is not None:
            return override
        return (ROOT / self.MOTION_TS).read_text(encoding='utf-8')

    def _style_writes(self, source):
        return re.findall(r'\.style\.([A-Za-z-]+)\s*=', source)

    def test_the_layer_only_writes_composited_style_channels(self):
        writes = self._style_writes(self._source())
        self.assertTrue(writes, 'no style writes found at all -- the reader broke, so this '
                                'assertion would be vacuously green')
        offenders = sorted({w for w in writes if w.lower() in self.FORBIDDEN_STYLE_WRITES})
        self.assertEqual(
            offenders, [],
            'motion.ts writes %s; any interpolated ink or backdrop paints frames no rule '
            'declares (section 5.55). Allowed set is transform/willChange/transition, got %s'
            % (offenders, sorted(set(writes))))

    def test_any_transition_this_layer_sets_is_transform_only_and_in_band(self):
        source = self._source()
        declared = re.findall(r'style\.transition\s*=\s*[`\'"]([^`\'"]+)[`\'"]', source)
        for value in declared:
            resolved = re.sub(r'\$\{[A-Za-z_]+\}', '150', value)
            for name in re.findall(r'(?<![-\w])([a-z-]+)(?=\s)', resolved):
                if name in ('cubic-bezier', 'ease', 'linear'):
                    continue
                self.assertIn(name, ('transform', 'opacity'),
                              'the layer transitions %r, which interpolates a paint value: %s'
                              % (name, value))
            for number, unit in re.findall(r'(\d+(?:\.\d+)?)(ms|s)', resolved):
                ms = float(number) * (1000.0 if unit == 's' else 1.0)
                self.assertTrue(120 <= ms <= 180,
                                'the layer sets %gms, outside the pack band 120-180ms: %s'
                                % (ms, value))

    def test_the_layer_is_off_until_asked_and_stops_for_reduced_motion(self):
        source = self._source()
        self.assertIn("get('motion') === 'enhanced'", source,
                      'the enhanced layer is no longer opt-in, so it would change the static '
                      'screens every geometry and contrast gate was measured against')
        self.assertIn('(prefers-reduced-motion: reduce)', source,
                      'the layer stopped consulting the OS signal the stylesheet also obeys')
        mode = source[source.index('export function motionMode'):
                      source.index('function reducedMotion')]
        self.assertRegex(mode, r"return reducedMotion\(\) \? 'static' : 'enhanced'",
                         'motionMode() no longer lets the OS signal win over the URL, so '
                         '`?motion=enhanced` would override a request for no motion')
        mount = source[source.index('export function mountEnhancedMotion'):]
        self.assertRegex(mount, r"if \(mode !== 'enhanced'\)",
                         'mountEnhancedMotion no longer returns before wiring anything when the '
                         'layer is off -- a guard that wires first and checks later is not a guard')

    def test_every_wired_surface_is_actually_rendered(self):
        """A motion host that no screen builds is a decoration the product cannot show.

        This case exists because the first cut listed `.seg button`, `.review-card`, a
        `[data-motion="count"]` marker and `.soft-btn`: each of those class names occurs in
        `build/main.js` exactly once, and the only occurrence is the selector string this layer
        itself wrote. shell.ts alone would be too narrow a population -- a class can be built in
        workbench.ts, design.ts, ui-primitives.ts or straight into index.html -- so every source
        that can construct DOM is read. And because a name can be assembled from a fragment
        (`class: <code>-btn`), any such template in the sources marks that family as built
        rather than convicting it: a probe that reports a false negative is worse than no probe.
        """
        source = self._source()
        built = '\n'.join(
            (ROOT / 'apps' / 'workbench' / name).read_text(encoding='utf-8')
            for name in sorted(p.name for p in (ROOT / 'apps' / 'workbench').glob('*.ts'))
            if name != 'vite.config.ts') + \
            (ROOT / 'apps' / 'workbench' / 'index.html').read_text(encoding='utf-8')
        fragments = set(re.findall(r'`[^`]*\$\{[^}`]*\}(-[a-z]+(?:-btn|card|item|stack|group))',
                                   built))
        listed = re.findall(r"^const (?:MAGNETIC|TILT|REVEAL)_SELECTOR = (.*?);\s*$",
                            source, re.M | re.S)
        self.assertEqual(len(listed), 3,
                         'the three host lists are no longer all present, so this sweep would '
                         'silently check less than it claims')
        raw = ' '.join(re.findall(r"'([^']+)'", ' '.join(listed)))
        selectors = sorted({s.strip() for s in raw.split(',') if s.strip()})
        self.assertGreaterEqual(len(selectors), 7, 'the host sweep lost population: %s' % selectors)
        missing = []
        for selector in selectors:
            classes = re.findall(r'\.([A-Za-z][-\w]*)', selector)
            if not classes:
                continue
            covered = any(re.search(r'(?<![-\w])%s(?![-\w])' % re.escape(c), built)
                          for c in classes)
            if not covered and any(c.endswith(tuple(fragments)) for c in classes):
                covered = True  # assembled from a fragment, so the literal is not expected
            if not covered:
                missing.append(selector)
        self.assertEqual(
            missing, [],
            'these motion hosts name a class the shipped product never builds, so they would wire '
            'nothing and still report a host count: %s' % missing)

    def test_the_mount_wires_by_delegation_because_route_views_rerender(self):
        source = self._source()
        mount = source[source.index('export function mountEnhancedMotion'):]
        self.assertNotIn('addEventListener(', mount.replace('delegate(', ''),
                         'the mount path attaches listeners per element again; the shell '
                         're-renders route views on navigation and those listeners would '
                         'detach silently, leaving a screen that looks motionless but is '
                         'still paying for the wiring')
        self.assertRegex(source, r"root\.addEventListener\('pointermove'",
                         'delegation was removed from `delegate`, so the behaviours above '
                         'have no owner')

    def test_the_reader_convicts_a_planted_colour_write_and_a_bare_shorthand(self):
        source = self._source()
        planted = source + ('\nexport function dlMotionPlant(el: HTMLElement): void {\n'
                            '  el.style.color = \'#fff\';\n'
                            '  el.style.transition = \'background 400ms ease\';\n}\n')
        writes = self._style_writes(planted)
        self.assertIn('color', writes, 'the planted colour write was not even read')
        offenders = {w for w in writes if w.lower() in self.FORBIDDEN_STYLE_WRITES}
        self.assertEqual(offenders, {'color'},
                         'the reader let a planted ink write through: %s' % offenders)
        declared = re.findall(r'style\.transition\s*=\s*[`\'"]([^`\'"]+)[`\'"]', planted)
        self.assertIn('background 400ms ease', declared,
                      'the planted transition was not found, so the band check cannot fail')


    #: Infinite loops whose selector the shipped bundle never renders. Published, not judged:
    #: a loop that cannot paint is dead weight, not a violation of 「无持续循环」. The list is
    #: pinned in both directions -- one leaving it (a dead screen gets mounted) turns into a
    #: live loop that has to be scoped or registered, and one joining it must be named here.
    DEAD_LOOPS = ('dashMove', 'pulse', 'scanSweep')

    def _animations(self, css_text=None, bundle_text=None):
        """(line, selector, name, durations-ms, infinite, live?) per `animation:` declaration."""
        css = css_text if css_text is not None else \
            (ROOT / 'apps' / 'workbench' / 'style.css').read_text(encoding='utf-8')
        bundle = bundle_text if bundle_text is not None else \
            (ROOT / 'apps' / 'workbench' / 'build' / 'main.js').read_text(
                encoding='utf-8', errors='replace')
        blanked = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)),
                         css, flags=re.S)
        rows = []
        for match in re.finditer(r'([^{}]+)\{([^{}]*)\}', blanked):
            selector = match.group(1).strip().replace('\n', ' ')
            for decl in re.finditer(r'(?<![-\w])animation\s*:\s*([^;]+)', match.group(2)):
                value = decl.group(1).strip()
                parts = value.split()
                durations = [float(n) * (1000.0 if u == 's' else 1.0)
                             for n, u in re.findall(r'(?<![\w.-])(\d*\.\d+|\d+)(ms|s)\b', value)]
                wanted = re.findall(r'\.([A-Za-z][-\w]*)', selector)
                # Every class in the selector has to appear as a whole token in the bundle.
                # `.graph-stage .core` looks live if the word `core` appears anywhere, and it
                # does -- inside the prose "DESIGN-LAB design core". All-token matching is what
                # makes `dead` mean dead here.
                found = [t for t in wanted
                         if re.search(r'(?<![-\w])%s(?![-\w])' % re.escape(t), bundle)]
                rows.append((blanked[:match.start(2)].count('\n') + 1, selector,
                             parts[0] if parts else '?', durations, 'infinite' in value,
                             bool(wanted) and len(found) == len(wanted)))
        return rows

    def test_the_static_face_carries_no_live_infinite_loop(self):
        """`09_DESIGN.md:21` forbids 「无持续循环、自动播放和浮动装饰」 on what actually paints.

        Measured before this rule existed: 4 `animation:` declarations, all `infinite`, and the
        only one with a renderer was `.ambient` -- a blurred glow mounted on every route
        (shell.ts builds `el('div', {class: 'ambient'})`), looping for 12s forever. Neither
        motion ruler could see it: both read `transition:`, and this is `animation:`. It now
        only runs under `:root[data-motion="enhanced"]`, which motion.ts sets from
        `?motion=enhanced` and never under prefers-reduced-motion.
        """
        rows = self._animations()
        self.assertTrue(rows, 'no animation read at all, so this assertion would be vacuous')
        live_loops = [r for r in rows if r[4] and r[5]]
        unscoped = [r for r in live_loops if 'data-motion="enhanced"' not in r[1]]
        self.assertEqual(
            unscoped, [],
            'these live loops run on the default face: %s' % [(r[0], r[1], r[2]) for r in unscoped])
        dead = sorted({r[2] for r in rows if r[4] and not r[5]})
        self.assertEqual(
            dead, sorted(self.DEAD_LOOPS),
            'the dead-loop register moved: %s are unrendered infinite animations today, and a '
            'dead one that gets mounted becomes a live loop that must be scoped or named' % dead)
        published = [(r[0], r[1], r[2], r[4], r[5]) for r in rows]
        self.assertGreaterEqual(len(published), 4,
                                'the animation census shrank, so the ruler lost population')

    def test_the_animation_reader_convicts_a_planted_live_loop(self):
        css = (ROOT / 'apps' / 'workbench' / 'style.css').read_text(encoding='utf-8')
        planted = css + '\n.ambient{animation:dlMotionPlantLoop 9s linear infinite}\n'
        rows = self._animations(css_text=planted,
                                bundle_text='class: "ambient"')
        live = [r for r in rows if r[5] and r[2] == 'dlMotionPlantLoop']
        self.assertEqual(len(live), 1,
                         'a planted infinite loop on a rendered class was not read as live: %s'
                         % [r for r in rows if r[2] == 'dlMotionPlantLoop'])
        self.assertNotIn('data-motion="enhanced"', live[0][1],
                         'the plant was scoped, so the unscoped test would not have fired')


class RefusalPopulationIsGraded(unittest.TestCase):
    """「错误紧邻字段」 was being read over an empty set, and the zero looked like a pass.

    The audit's error loop selected `.error, [role=alert], .field-note, .refusal`. Nothing on any
    route the walk visits carries those classes: the product writes its local refusals into
    `p.view-hint` lines (`#knowledge-outcome`, `#jury-outcome`, `#rights-review-outcome`,
    `#research-review-outcome`), so `errors=0` described the selector, not the interface. Two
    things had to change together -- the population has to include the class the product actually
    uses, and a state with no refusal in it has to be provoked, because a walk that only visits
    successful reads can never show one.
    """

    def test_the_product_refusal_vocabulary_is_read_from_the_source(self):
        words = refusal_prefixes()
        self.assertGreaterEqual(len(words), 3,
                                'only %s refusal prefix(es) were derived, so the population would '
                                'be nearly empty: %s' % (len(words), words))
        for expected in ('未提交', '未签署', '未记录'):
            self.assertIn(expected, words,
                          '%s is written by shell.ts today; losing it from the derived set would '
                          'shrink the measured population silently' % expected)

    def test_the_gate_refuses_an_empty_word_list_and_selects_the_class_the_product_uses(self):
        script = GATE_SCRIPT.read_text(encoding='utf-8')
        self.assertIn("CT_REFUSAL_WORDS is empty", script,
                      'the audit no longer refuses to grade with no refusal words, so an empty '
                      'list would read as errors=0 again')
        self.assertIn('.view-hint', script,
                      'the error population no longer includes .view-hint, which is where the '
                      'product writes refusals')

    def test_the_refusal_state_is_named_in_the_receipt(self):
        """Measure here rather than reading whatever an earlier test happened to leave behind.

        This method used to `skipTest` when the receipt was missing, and the receipt was missing on
        every fresh checkout because the class that writes it runs later in alphabetical order --
        which the no-skip policy is right to refuse.
        """
        code, out, path = _run_gate({})
        self.assertEqual(code, 0,
                         'the gate did not complete, so there is no receipt to read: %s'
                         % out[-1200:])
        report = json.loads(path.read_text(encoding='utf-8'))
        rows = [k for k in report.get('routes', {}) if k.endswith('+refusal')]
        self.assertTrue(rows, 'the receipt has no knowledge+refusal row, so the provoked state '
                              'was never measured')
        spec = report.get('spec') or {}
        self.assertGreaterEqual(int(spec.get('errors', '0')), 1,
                                'errors=%s over a provoked refusal state -- the population is '
                                'still invisible' % spec.get('errors'))


class TheSingleAccentIsGradedWhereItIsPainted(unittest.TestCase):
    """Section 5.52 left the pack's 「单一低饱和强调色 #356B92」 with two candidate fixes and one
    unmeasured risk: "use a deeper step of the same hue as the fill, but then white ink has to be
    re-graded". This class grades it, so the owner's ruling is a design choice and not a bet.

    Two facts decide what WCAG even has to say here. First, no shipped rule paints the accent as
    glyph ink -- the token is consumed by backgrounds, borders, outlines, shadows and SVG fill or
    stroke -- so 1.4.3 never attaches to the accent as text colour, and the number that matters is
    the ink sitting *on top of* an accent backdrop. Second, of the two directions 5.52 put on the
    table, only one clears AA: paper ink on the accent measures 5.72:1, the dark body ink on the
    same accent measures 2.85:1. The shipped rules already chose the safe one; this guard is what
    stops a later edit from quietly picking the other.
    """

    ACCENT = '#356B92'          # style.css:1805, the stitch (pearl-white) palette's accent
    ACCENT_HOVER = '#2558DB'    # style.css:92, the hover step the same rules reach for
    PAPER = '#EEF2F5'           # 09_DESIGN.md:9, the pack's pearl-white paper
    INK = '#17212B'             # the pack's dark ink, also the body text token value
    WHITE = '#FFFFFF'
    AA = 4.5
    # The literals the shipped rules actually write beside an accent backdrop.
    PAPER_INK = ('#fff', '#ffffff', 'white', 'var(--brand-mark-paper)', 'var(--color-paper)')

    @staticmethod
    def _channel(byte):
        value = byte / 255.0
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    @classmethod
    def _luminance(cls, hex_colour):
        digits = hex_colour.lstrip('#')
        red, green, blue = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
        return (0.2126 * cls._channel(red) + 0.7152 * cls._channel(green)
                + 0.0722 * cls._channel(blue))

    @classmethod
    def _ratio(cls, foreground, background):
        hi = max(cls._luminance(foreground), cls._luminance(background))
        lo = min(cls._luminance(foreground), cls._luminance(background))
        return round((hi + 0.05) / (lo + 0.05), 2)

    @staticmethod
    def _css():
        return (ROOT / 'apps' / 'workbench' / 'style.css').read_text(encoding='utf-8')

    @staticmethod
    def _enclosing_block(css, position):
        """The flat declaration list a match sits in; nearest braces outward are the rule's own."""
        start = css.rfind('{', 0, position)
        end = css.find('}', position)
        return '' if start < 0 or end < 0 else css[start + 1:end]

    def _accent_backdrops(self, css):
        return list(re.finditer(
            r'\bbackground(?:-color)?\s*:\s*[^;{}]*var\(--accent[a-z-]*\)', css))

    def _ink_on_accent(self, css):
        """[(where, colour)] for every `color:` declared beside an accent backdrop that is not paper."""
        offenders = []
        for match in self._accent_backdrops(css):
            where = css[max(0, match.start() - 90):match.start()].replace('\n', ' ')[-70:]
            for colour_match in re.finditer(r'(?:^|[;{\s])color\s*:\s*([^;{}]+)',
                                            self._enclosing_block(css, match.start())):
                colour = colour_match.group(1).strip().lower()
                if not any(colour == paper or colour.startswith(paper + ' ')
                           for paper in self.PAPER_INK):
                    offenders.append((where, colour))
        return offenders

    def test_the_directions_5_52_left_unmeasured_now_have_numbers(self):
        self.assertGreaterEqual(self._ratio(self.WHITE, self.ACCENT), self.AA,
                                'white ink on the pack accent reads %s:1, so the "same hue as a '
                                'fill" direction 5.52 could not price is not AA-safe after all'
                                % self._ratio(self.WHITE, self.ACCENT))
        self.assertGreaterEqual(self._ratio(self.WHITE, self.ACCENT_HOVER), self.AA,
                                'the hover step reads %s:1 under white ink'
                                % self._ratio(self.WHITE, self.ACCENT_HOVER))
        self.assertLess(self._ratio(self.INK, self.ACCENT), self.AA,
                        'dark ink on the accent now reads %s:1 -- the other direction 5.52 offered '
                        'has stopped costing AA, so this class has to be re-read, not re-tuned'
                        % self._ratio(self.INK, self.ACCENT))
        self.assertGreaterEqual(self._ratio(self.ACCENT, self.PAPER), self.AA,
                                'the accent as glyph ink on pearl reads %s:1; it is not shipped that '
                                'way (see the next test) and must not become a red if someone ships '
                                'it that way' % self._ratio(self.ACCENT, self.PAPER))

    def test_the_accent_is_never_declared_as_glyph_ink(self):
        css = self._css()
        consumed = len(re.findall(r'var\(--accent[a-z-]*\)', css))
        self.assertGreaterEqual(consumed, 8,
                                'only %s accent consumption(s) were read, so the population this '
                                'test describes is nearly gone' % consumed)
        as_ink = re.findall(r'(?:^|[;{\s])color\s*:\s*[^;{}]*var\(--accent[a-z-]*\)', css)
        self.assertEqual(as_ink, [],
                         'the accent is now painted as text ink %s time(s); 1.4.3 begins to apply '
                         'to it and the number above is the grade it has to clear' % len(as_ink))

    def test_every_accent_backdrop_carries_paper_ink(self):
        css = self._css()
        self.assertGreaterEqual(len(self._accent_backdrops(css)), 1,
                                'no rule paints an accent backdrop any more, so this guard would '
                                'pass on an empty set')
        offenders = self._ink_on_accent(css)
        self.assertEqual(offenders, [],
                         'these rules put a non-paper ink on an accent backdrop, where the dark '
                         'body colour reads %s:1: %s' % (self._ratio(self.INK, self.ACCENT),
                                                         offenders))

    def test_the_reader_convicts_a_planted_swap_to_dark_ink(self):
        """A guard that cannot fail guards nothing, so both halves of it get a planted fault."""
        css = self._css()
        needle = 'background:var(--accent-hover);color:#fff;'
        self.assertIn(needle, css, 'the planted fault has nowhere to land; the shipped rule that '
                                   'writes the paper ink beside an accent backdrop was renamed')
        dark = 'background:var(--accent-hover);color:%s;' % self.INK.lower()
        convicted = self._ink_on_accent(css.replace(needle, dark))
        self.assertTrue(convicted, 'swapping paper ink for the dark body ink on an accent backdrop '
                                   'did not convict, so %s:1 would ship unseen'
                        % self._ratio(self.INK, self.ACCENT))
        self.assertTrue(any(offender[1] == self.INK.lower() for offender in convicted),
                        'the plant was convicted for the wrong reason: %s' % (convicted,))
        ink_plant = css + '\n#planted-accent-ink{color:var(--accent)}\n'
        as_ink = re.findall(r'(?:^|[;{\s])color\s*:\s*[^;{}]*var\(--accent[a-z-]*\)', ink_plant)
        self.assertEqual(len(as_ink), 1,
                         'a planted `color:var(--accent)` was not read as glyph ink (%s)' % (as_ink,))


def adjacency_offenders(rows, limit=24):
    """Which provoked refusals did not land on the field they name.

    Kept out of the test method so a planted row can be pushed through the same rule that reads
    the real artefact: an assertion that only ever sees measured bytes cannot be shown to bite.
    """
    bad = []
    for row in rows:
        if not row.get('shown', True):
            bad.append('%s: no refusal appeared' % row.get('key'))
        elif not row.get('dataFor'):
            bad.append('%s: the refusal names no field' % row.get('key'))
        elif not row.get('referentExists'):
            bad.append('%s: data-for points at #%s, which is not in the document'
                       % (row.get('key'), row.get('dataFor')))
        elif not row.get('painted'):
            bad.append('%s: the refusal of #%s is not painted' % (row.get('key'),
                                                                  row.get('dataFor')))
        elif (row.get('dy') or 0) > limit:
            bad.append('%s: %spx from #%s' % (row.get('key'), row.get('dy'),
                                              row.get('dataFor')))
        # The knowledge walker also records the two shapes that only that form's layout can break.
        # Absent keys (the assistant family) are not graded here, so this cannot convict a family
        # that never claimed the rule.
        elif row.get('insideRow') is False:
            bad.append('%s: the refusal of #%s is not inside that field\'s own .field-row, so in '
                       'the two-column form it paints beside an unrelated field'
                       % (row.get('key'), row.get('dataFor')))
        elif row.get('labelNamed') is False:
            bad.append('%s: the refusal of #%s does not repeat that field\'s label word「%s」'
                       % (row.get('key'), row.get('dataFor'), row.get('labelWord', '')))
    return bad


class FieldRefusalsLandOnTheFieldTheyName(unittest.TestCase):
    """「错误紧邻字段」 was being graded against the wrong element, and the product was passing.

    The audit picked `host.querySelector(...)`: the FIRST control inside the panel. On the intake
    form that is the 需求 textarea at the top, while the alert is written at the foot of a form with
    twenty fields, so the only refusal this gate ever provoked measured dy=1199px and the pack's
    adjacency number read 0 of 8. Both halves were wrong: the metric could not know which field a
    message was about, and the message really was 1199px from the field it named.

    The product now names its referent through `data-for` and moves the alert next to that field;
    the metric grades exactly that pair. The number below is the same rule, re-measured.
    """

    def test_every_graded_refusal_is_adjacent_to_the_field_it_names(self):
        code, out, path = _run_gate({})
        self.assertEqual(code, 0,
                         'the gate did not complete, so the adjacency rule has no measurement to '
                         'grade: %s' % out[-1200:])
        report = json.loads(path.read_text(encoding='utf-8'))
        spec = report.get('spec') or {}
        seen = (report.get('refusalAdjacency') or {}).get('seen') or []
        proved = [row.get('key', '') for row in (report.get('refusals') or {}).get('proved', [])]
        # The rule the pack states is about a message and THE FIELD IT NAMES, so that pair is what
        # gets enforced. `errors == errorAdjacent` was the first shape of this assertion and it only
        # held because the population then contained no message without a referent; the knowledge
        # family, now provoked for real, contributes four compound messages that name three fields
        # at once and sit 82px from any control. Requiring the whole count to be adjacent would
        # have been satisfied by dropping those from the count -- so the count is asserted to
        # include them, and the obligation is asserted on the named subset.
        self.assertGreaterEqual(spec.get('errorNamed', 0), 1,
                                'no graded message carried a data-for referent, so the adjacency '
                                'rule is back to guessing which field a sentence is about')
        self.assertEqual(spec.get('errorNamed'), spec.get('errorNamedAdjacent'),
                         'named=%s namedAdjacent=%s: a refusal that says which field it is about '
                         'is not sitting on that field' % (spec.get('errorNamed'),
                                                           spec.get('errorNamedAdjacent')))
        # This is where the suite used to assert `errors > errorNamed`. That clause demanded that
        # unnamed compound messages KEEP existing, so fixing them into per-field lines would have
        # turned this gate red -- the owner audit of 2026-10-26 (finding 5) named exactly that as a
        # defect of the tests. What has to be guarded is the population shrinking, not the defect
        # persisting: every provoked per-field case must appear among the named messages, and the
        # named ones must be a subset of everything measured.
        self.assertGreaterEqual(spec.get('errorNamed', 0), len(seen),
                                'errorNamed=%s is below the %s refusal(s) this run provoked, so '
                                'the painted population no longer contains what the walk made '
                                'visible' % (spec.get('errorNamed'), len(seen)))
        self.assertGreaterEqual(spec.get('errors', 0), spec.get('errorNamed', 0),
                                'errors=%s is below named=%s: the named subset is no longer a '
                                'subset of what was counted, so the denominator moved'
                                % (spec.get('errors'), spec.get('errorNamed')))
        knowledge_named = [row for row in seen if ':knowledge' in row.get('key', '')]
        self.assertGreaterEqual(len(knowledge_named), 3,
                                'only %s per-field knowledge refusal(s) were provoked, so the '
                                'compound 「标题、一句话用途和正文都必须填写」 sentence has not been '
                                'fully replaced on the painted document' % len(knowledge_named))
        self.assertEqual(adjacency_offenders(knowledge_named), [],
                         'these per-field knowledge refusals did not land on the field they name')
        for family in (':assistant+refusal', ':knowledge+refusal'):
            self.assertTrue([k for k in proved if k.endswith(family)],
                            'no run provoked the %s family, so 「错误紧邻字段」 is being graded on '
                            'half the refusal population' % family)
        self.assertGreaterEqual(len(seen), 3,
                                'only %s field refusal(s) were provoked, which is how the old '
                                'reading came to describe one element instead of the family'
                                % len(seen))
        self.assertEqual(adjacency_offenders(seen), [],
                         'these provoked refusals did not land on the field they name')

    def test_the_knowledge_form_is_reached_by_the_ids_that_route_really_builds(self):
        """`#knowledge-title` never existed here: the create form's fields are `kb-new-*`.

        That phantom naming is why this family reported `absent` for every run since it was first
        asked for, and why `errors` looked like a one-family population. The provocation now reveals
        the form through the route's own `#kb-new` affordance and addresses the panel by structure,
        because its submit button and status region carry no id at all.
        """
        script = GATE_SCRIPT.read_text(encoding='utf-8')
        self.assertIn("'#kb-form [role=status]', '#kb-new-title', '#kb-form .primary-btn'",
                      script, 'the knowledge provocation went back to ids this route does not '
                              'build, so the family silently stops being provoked')
        self.assertIn("page.click('#kb-new')", script,
                      'the create form is no longer revealed, so its refusal cannot exist on the '
                      'walked state')
        self.assertNotIn("'knowledge-title', 'knowledge-create-submit'", script,
                      'the phantom ids are back')
        source = (ROOT / 'apps' / 'workbench' / 'shell.ts').read_text(encoding='utf-8')
        self.assertIn("el('div', { id: 'kb-form' })", source,
                      'the panel that holds the create form was renamed, so the probe targets '
                      'silently point at nothing')

    def test_the_product_writes_each_field_refusal_through_one_door(self):
        source = (ROOT / 'apps' / 'workbench' / 'shell.ts').read_text(encoding='utf-8')
        self.assertEqual(source.count('const formError = el('), 1,
                         'the intake form has more than one alert node, so `data-for` on one of '
                         'them would be read as the whole story')
        self.assertGreaterEqual(source.count('showFieldRefusal('), 5,
                                'only %s field-named refusals go through the door that sets '
                                'data-for; the rest are ungradeable' % source.count(
                                    'showFieldRefusal('))
        self.assertIn("formError.setAttribute('data-for', control.id)", source,
                      'the helper no longer records which field the message is about, so the '
                      'audit falls back to guessing and the 1199px reading can come back')
        stray = re.findall(r"formError\.textContent\s*=\s*'[^']*[\u4e00-\u9fff]", source)
        self.assertEqual(stray, [],
                         'these refusals are written straight into the alert without naming a '
                         'field: %s' % [s[:48] for s in stray])

    def test_the_metric_reads_the_referent_instead_of_the_first_control(self):
        script = GATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("el.getAttribute('data-for')", script,
                      'the audit no longer resolves the field a refusal names')
        self.assertIn('adjacencyBad', script,
                      'nothing fails the run when a refusal is far from its field, so the number '
                      'is printed advice again')
        self.assertIn('walkFieldRefusals', script,
                      'a single provoked state cannot grade a rule that is about one field per '
                      'message')
        self.assertIn('walkKnowledgeFieldRefusals', script,
                      'the knowledge form is no longer walked on the painted document, so its '
                      'per-field refusals are only proved in the DOM harness')

    def test_the_rule_convicts_a_row_that_is_far_from_its_field(self):
        near = {'key': 'x#case1', 'shown': True, 'dataFor': 'as-author',
                'referentExists': True, 'painted': True, 'dy': 6}
        self.assertEqual(adjacency_offenders([near]), [])
        far = dict(near, dy=1199)
        self.assertEqual(adjacency_offenders([far]),
                        ['x#case1: 1199px from #as-author'],
                        'the row that reproduces the recorded defect is not convicted')
        anonymous = dict(near, dataFor='')
        self.assertTrue(adjacency_offenders([anonymous]),
                        'a refusal that names no field passes, so the population could be emptied '
                        'by dropping data-for')
        orphan = dict(near, referentExists=False)
        self.assertTrue(adjacency_offenders([orphan]),
                        'a data-for pointing at a missing id is not convicted')
        # The two shapes only the knowledge form's two-column layout can break. A near row carries
        # neither key, which is what an assistant-family case looks like -- so these clauses must
        # not convict it, and must convict the planted one.
        self.assertEqual(adjacency_offenders([dict(near, insideRow=True, labelNamed=True)]), [],
                         'a refusal that is inside its field\'s row and repeats its label word is '
                         'convicted anyway, so the clause is not measuring what it claims')
        beside = adjacency_offenders([dict(near, dataFor='kb-new-body', insideRow=False)])
        self.assertEqual(len(beside), 1,
                         'a refusal painted in the next COLUMN of a two-column form, rather than '
                         'under its own field, is not convicted: %s' % beside)
        nameless = adjacency_offenders([dict(near, dataFor='kb-new-title', insideRow=True,
                                             labelNamed=False, labelWord='标题')])
        self.assertEqual(len(nameless), 1,
                         'a refusal that never says which field it blocks, while claiming to be '
                         'that field\'s, is not convicted: %s' % nameless)


if __name__ == '__main__':
    unittest.main(verbosity=2)
