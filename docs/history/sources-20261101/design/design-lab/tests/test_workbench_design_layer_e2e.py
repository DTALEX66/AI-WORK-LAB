# SPDX-License-Identifier: MIT
"""E-SLICE-02 browser E2E: drive the Workbench 05 design layer slice in a real
Chromium served by the real Python loopback service (E2 controlled-runtime).

This is the browser-level E2E the workbench-gate CI comment says is owned by
the E-slice gate ("NOT silently dropped"). It proves the vertical slice
(Project -> Brief -> Direction -> DesignSystem) works end-to-end through the
committed `build/main.js` in a real browser, against the live API. It claims
E2 controlled-runtime evidence only — not an E3 host run or an E4 human jury.

Toolchain is PROBE-driven so a clean CI checkout (which lacks the gitignored
in-repo Playwright npm-cache and the pre-installed Chromium) skips HONESTLY
rather than faking a pass: if `node` + the in-repo `playwright` npm-cache + a
locally installed Chromium are all present, the real browser drives the slice
and the test asserts the persisted DOM readback; otherwise it skips with the
exact reason it is unavailable.

P0-G evidence chain: when the toolchain is present the browser driver also
writes a machine-readable `browser-e2e-summary.json` (+ `fail.png` on failure)
into `.project-local/task-artifacts/browser-e2e/` (override: $E2E_EVIDENCE_DIR).
With `E2E_REQUIRED=1` (the CI no-skip job) a run must leave a PASS summary
behind; locally the test stays honest — a missing summary is never a failure,
the honest local answer is the skip reason, not an evidence gap.
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

ROOT = Path(__file__).resolve().parents[2]
NODE_SCRIPT = Path(__file__).resolve().parent / 'e2e' / 'browser_design_layer_e2e.mjs'


def _find_node_modules_dir():
    """Return the directory that CONTAINS a `node_modules/playwright`, or None.

    `E2E_NODE_MODULES` wins; otherwise discover the in-repo gitignored npx
    cache (a hash-suffixed dir under the playwright task-runtime root).
    """
    override = os.environ.get('E2E_NODE_MODULES')
    if override and (Path(override) / 'node_modules' / 'playwright').is_dir():
        return Path(override)
    npx_root = ROOT / '.project-local' / 'task-runtime' / 'playwright' / 'npm-cache' / '_npx'
    if npx_root.is_dir():
        for child in npx_root.iterdir():
            if (child / 'node_modules' / 'playwright').is_dir():
                return child
    return None


def _find_browser():
    """Return a locally installed Chromium executable, or None.

    `E2E_BROWSER` wins; otherwise scan the per-user ms-playwright registries
    for the newest chromium revision (headless shell preferred, falls back to
    full Chromium). Returning None means the browser E2E cannot run here.
    """
    override = os.environ.get('E2E_BROWSER')
    if override and Path(override).is_file():
        return Path(override)
    roots = []
    local_appdata = os.environ.get('LOCALAPPDATA')
    if local_appdata:
        roots.append(Path(local_appdata) / 'ms-playwright')
    roots.append(Path.home() / '.cache' / 'ms-playwright')
    for root in roots:
        if not root.is_dir():
            continue
        for name in sorted(root.iterdir(), reverse=True):
            if name.name.startswith(('chromium_headless_shell-', 'chromium-')):
                exe_names = {'chrome-headless-shell.exe', 'chrome-headless-shell',
                             'chrome.exe', 'chrome'}
                for candidate in sorted(name.rglob('*'), reverse=True):
                    if candidate.is_file() and candidate.name in exe_names:
                        return candidate
    return None


class WorkbenchDesignLayerE2ETests(unittest.TestCase):
    def test_design_layer_slice_in_real_browser(self):
        if not NODE_SCRIPT.is_file():
            self.skipTest(f'E2E browser script missing: {NODE_SCRIPT}')
        node = shutil.which('node')
        if not node:
            self.skipTest('E2E toolchain unavailable: node not on PATH')
        node_modules_dir = _find_node_modules_dir()
        if not node_modules_dir:
            self.skipTest('E2E toolchain unavailable: in-repo Playwright npm-cache '
                          f'not found (probe $E2E_NODE_MODULES / '
                          f'{ROOT / ".project-local/task-runtime/playwright"})')
        browser = _find_browser()
        if not browser:
            self.skipTest('E2E toolchain unavailable: no locally installed Chromium '
                          'revision found (probe $E2E_BROWSER / ms-playwright registry)')

        # Spin up a real loopback service on an OS-chosen port, mirroring the
        # design-layer contract tests' harness (fresh project, in-memory token).
        sys.path.insert(0, str(ROOT / 'src'))
        from design_lab.service import ProjectService
        from design_lab.http_service import make_server
        from unittest.mock import patch
        parent = ROOT / '.project-local' / 'task-runtime' / 'e2e-design-layer'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        root = Path(tmp.name)
        (root / 'AGENTS.md').write_text('# synthetic e2e browser project', encoding='utf-8')
        token = secrets.token_hex(32)
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
                    'E2E_EVIDENCE_DIR': str(
                        ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e'),
                }
                if browser:
                    env['E2E_BROWSER'] = str(browser)
                proc = subprocess.run(
                    [node, str(NODE_SCRIPT)],
                    env=env, capture_output=True, text=True, encoding='utf-8',
                    errors='replace', timeout=200, cwd=str(ROOT))
            finally:
                server.shutdown()
                worker.join()
                server.server_close()
                tmp.cleanup()
            if proc.returncode != 0:
                self.fail('E2E browser run exited %d (toolchain present, real failure):\n'
                          '--- stdout ---\n%s\n--- stderr ---\n%s'
                          % (proc.returncode, proc.stdout, proc.stderr))
            self.assertIn('E2E_OK', proc.stdout, 'E2E did not reach a full-slice readback:\n'
                                                  + proc.stdout + proc.stderr)
            # P0-G evidence chain: required mode (CI no-skip job, $E2E_REQUIRED=1)
            # must leave a machine-readable PASS summary behind.
            #
            # This block used to run ONLY under E2E_REQUIRED=1, which a local run does not set.
            # That made every evidence assertion below it invisible until a push: the 2026-10-24
            # A5 roster typo (a list compared against `sorted(...)`, typed in the driver's
            # insertion order) stayed green locally and was convicted only by CI. A run that
            # reached this line has a real toolchain and a driver that exits non-zero when a
            # walked fact is missing, so the summary is read whenever it exists -- and a required
            # run that wrote no summary at all is still a hard failure.
            summary = ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e' / \
                'browser-e2e-summary.json'
            if os.environ.get('E2E_REQUIRED') == '1' or summary.is_file():
                self.assertTrue(summary.is_file(),
                                'E2E_REQUIRED but no evidence summary written: '
                                f'{summary}')
                payload = json.loads(summary.read_text(encoding='utf-8'))
                self.assertEqual(payload.get('kind'), 'workbench-browser-e2',
                                 'E2E summary kind drifted: ' + str(payload.get('kind')))
                self.assertEqual(payload.get('result'), 'PASS',
                                 'E2E summary is not a PASS run: '
                                 + summary.read_text(encoding='utf-8'))
                # B3 (2026-10-21): the prompt-result slice must be visible in the
                # artifact, not only on stdout — a required run whose evidence says
                # "compose → store → human signature" never happened is a gap, and
                # an overclaim in the shipped panel is a lie.
                self.assertIn('prompt-result-compose-store-sign',
                              payload.get('scenario') or [],
                              'E2E_REQUIRED summary does not list the prompt-result '
                              'scenario: ' + str(payload.get('scenario')))
                loop = payload.get('promptLoop') or {}
                self.assertEqual(
                    [loop.get('unsignedRow'), loop.get('signedRow'),
                     loop.get('reviewerShown'), loop.get('overclaim')],
                    [True, True, True, False],
                    'E2E prompt-result facts are not the expected shape: '
                    + json.dumps(loop, ensure_ascii=False))
                self.assertTrue(re.match(r'^(prompt|reversal)-[0-9a-f]{32}$',
                                         str(loop.get('resultId'))),
                                'E2E prompt-result id is not the id shape the route '
                                'accepts: ' + str(loop.get('resultId')))
                # DL-KB-08: the design-assistant screen must be visible in the artifact.
                # The four states are asserted from the rendered page in the driver; this
                # records what the artifact says they were, so a green run whose evidence
                # never mentions the assistant is a gap, not a pass.
                self.assertIn('assistance-plan-four-states',
                              payload.get('scenario') or [],
                              'E2E_REQUIRED summary does not list the design-assistant '
                              'scenario: ' + str(payload.get('scenario')))
                assistant = payload.get('assistantLoop') or {}
                self.assertEqual(
                    [assistant.get('saved'), assistant.get('providedAfterSave'),
                     assistant.get('chosenAfterSave'), assistant.get('externalVerified')],
                    [True, False, False, False],
                    'E2E design-assistant states after the first save are not the '
                    'expected shape: ' + json.dumps(assistant, ensure_ascii=False))
                self.assertEqual(
                    [assistant.get('copyWorked'), assistant.get('copyCarriedHonesty'),
                     assistant.get('copyWroteNothing'), assistant.get('copyChoseNothing'),
                     assistant.get('emptyObjectiveRefused'),
                     assistant.get('suppliedCreative'), assistant.get('chosen'),
                     assistant.get('chosenActorShown'), assistant.get('reloadReadback'),
                     assistant.get('noChatSurface'), assistant.get('providerPrimary'),
                     assistant.get('revisionRows')],
                    [True, True, True, True, True, True, True, True, True, True,
                     'as-choose', 2],
                    'E2E design-assistant flow facts are not the expected shape: '
                    + json.dumps(assistant, ensure_ascii=False))
                # DL-KB-16: the voluntary external-use report is the last link of the chain, and
                # the three things a reader cannot take on trust are that its words came from the
                # service, that writing one left the plan alone, and that it survived the page
                # being thrown away. Each is a measured field in the artifact, not a sentence.
                self.assertEqual(
                    [assistant.get('feedbackOutcomeOptionsRendered'),
                     assistant.get('feedbackRecorded'), assistant.get('feedbackKeptPlan'),
                     assistant.get('feedbackOverclaim'), assistant.get('feedbackWrites'),
                     assistant.get('feedbackSurvivedReload')],
                    [4, True, True, False, 1, True],
                    'E2E external-use-feedback facts are not the expected shape: '
                    + json.dumps({key: assistant.get(key) for key in (
                        'feedbackOutcomeOptionsRendered', 'feedbackRecorded',
                        'feedbackKeptPlan', 'feedbackOverclaim', 'feedbackWrites',
                        'feedbackSurvivedReload')}, ensure_ascii=False))
                # DL-KB-11: the handoff materials the screen offered, the one refusal a designer
                # hits first, and the one download that carried the answer's own name and digest.
                self.assertEqual(
                    [assistant.get('copyFormat'), assistant.get('materialFormatsOffered'),
                     assistant.get('materialCsvRefused'), assistant.get('materialDownloaded')],
                    ['markdown', 4, True, True],
                    'E2E handoff-material facts are not the expected shape: '
                    + json.dumps({key: assistant.get(key) for key in (
                        'copyFormat', 'materialFormatsOffered', 'materialCsvRefused',
                        'materialDownloaded')}, ensure_ascii=False))
                # DL-KB-12: the retrieval face. Three things a reader cannot take on trust, each
                # measured rather than narrated: a filtered list that says which subset it read,
                # two revisions whose stored digests differ (a comparison of one revision twice
                # would produce identical ones), and a copy whose source kept its revision count
                # and its voluntary feedback records.
                self.assertEqual(
                    [assistant.get('planSearchFiltered'),
                     assistant.get('filterSurvivedReload'),
                     assistant.get('compareRealRevisions'),
                     assistant.get('duplicateLeftSourceAlone'),
                     assistant.get('sourceRevisionsAfterCopy'),
                     assistant.get('sourceFeedbackAfterCopy')],
                    [True, True, True, True, 2, 1],
                    'E2E plan-retrieval facts are not the expected shape: '
                    + json.dumps({key: assistant.get(key) for key in (
                        'planSearchFiltered', 'filterSurvivedReload', 'compareRealRevisions',
                        'duplicateLeftSourceAlone', 'sourceRevisionsAfterCopy',
                        'sourceFeedbackAfterCopy')}, ensure_ascii=False))
                self.assertRegex(str(assistant.get('duplicateId')), r'^aplan-[0-9a-f]{32}$',
                                 'the copy\'s id is not the shape the create route mints -- a page '
                                 'that invented one would look identical here')
                self.assertGreaterEqual(int(assistant.get('compareFieldRows') or 0), 10,
                                        'the comparison compared almost nothing: '
                                        + str(assistant.get('compareFieldRows')))
                # DL-KB-12 second half: 「重启后仍能看到…未完成的编辑」. Four claims, in the order the
                # scenario produced them -- no draft left over from the saves that came before, one
                # written for the unfinished edit, that edit back in the form after the page was
                # thrown away, the service list unchanged while it was only a draft, and the draft
                # gone once the write really succeeded.
                self.assertEqual(
                    [assistant.get('draftKeysAfterSaves'),
                     assistant.get('draftWrittenKeys'),
                     assistant.get('draftSurvivedReload'),
                     assistant.get('draftListUntouched'),
                     assistant.get('draftClearedAfterSubmit')],
                    [0, 1, True, True, True],
                    'E2E plan-draft facts are not the expected shape: '
                    + json.dumps({key: assistant.get(key) for key in (
                        'draftKeysAfterSaves', 'draftWrittenKeys', 'draftSurvivedReload',
                        'draftListUntouched', 'draftClearedAfterSubmit')}, ensure_ascii=False))
                # DL-KB-14: the six states, each asserted against what the page actually showed.
                # The scenario name is only pushed when the step ran, so a run that skipped it
                # cannot satisfy this -- and `allSixAsserted` is derived from the six keys, so a
                # state that never got measured cannot hide behind a `true` someone typed in.
                self.assertIn('six-state-surfaces', payload.get('scenario') or [],
                              'E2E_REQUIRED summary does not list the six-state scenario: '
                              + str(payload.get('scenario')))
                states = (payload.get('stateLoop') or {}).get('states') or {}
                # Both rosters are wrapped in sorted() on purpose. Each is compared against
                # `sorted(...)`, so a literal typed in the driver's insertion order is unmatchable
                # -- and until 2026-10-24 this whole block ran only when E2E_REQUIRED=1, which CI
                # sets and a local run does not. That combination is how the A5 roster sat green
                # locally and failed CI: an order typo was invisible to every local signal.
                self.assertEqual(
                    sorted(states),
                    sorted(['attachmentUnparsed', 'knowledgeEmpty', 'modelUnavailable',
                            'oldVersionReadOnly', 'saveFailureNamed', 'targetIncompatibleShown']),
                    'the six-state surface card is not the six states this card names: '
                    + json.dumps(states, ensure_ascii=False))
                self.assertEqual(
                    (payload.get('stateLoop') or {}).get('allSixAsserted'), True,
                    'at least one of the six states was not asserted in the browser: '
                    + json.dumps(payload.get('stateLoop'), ensure_ascii=False))

                # DL-KB-05 D5 (2026-10-24): the entry detail and both judgement forms, walked in
                # Chromium. The card is the shape of the claim -- a run that never opened an entry
                # leaves `knowledgeLoop` unset and this whole block goes red rather than reading as
                # "the panel was checked and passed".
                self.assertIn('knowledge-detail-judgement-walk', payload.get('scenario') or [],
                              'E2E_REQUIRED summary does not list the knowledge-detail walk: '
                              + str(payload.get('scenario')))
                kb_states = (payload.get('knowledgeLoop') or {}).get('states') or {}
                self.assertEqual(
                    sorted(kb_states),
                    sorted(['blankFieldsStoredAsUnknown', 'clipboardHoldsTheServedBody',
                            'emptyTrailSaidNotAskedAndAnswered', 'entryWrittenAndOpened',
                            'judgementRecordedOnce', 'nameRefusedWithoutRequest',
                            'pickerOffersAllFiveKinds', 'planCitesEveryKind',
                            'planCitesTheKnowledgeEntry', 'reasonRefusedWithoutRequest',
                            'screenMatchesServedReadback',
                            'sourceNeedsAnOpenableReplacement']),
                    'the knowledge-detail card is not the twelve facts this walk names: '
                    + json.dumps(kb_states, ensure_ascii=False))
                self.assertEqual(
                    (payload.get('knowledgeLoop') or {}).get('allAsserted'), True,
                    'the knowledge detail or its judgement panel was not asserted in the browser: '
                    + json.dumps(payload.get('knowledgeLoop'), ensure_ascii=False))
                # `screenMatchesServedReadback` compares the painted rows with the POST's own
                # readback, so a page that renders a trail the service never wrote is caught here
                # rather than by a substring someone typed into the driver.
                loop = payload.get('knowledgeLoop') or {}
                self.assertEqual((loop.get('served') or {}).get('trail'),
                                 (loop.get('onScreen') or {}).get('trailRows'),
                                 'the painted judgement rows do not match the served readback: '
                                 + json.dumps(loop, ensure_ascii=False))
                # Per-phase counters, so a double send names the click that caused it.
                posts = loop.get('posts') or {}
                self.assertEqual(
                    [posts.get('afterReasonClick'), posts.get('afterNameClick'),
                     posts.get('afterJudgeClick'), posts.get('afterSourceClick')],
                    [0, 0, 1, 1],
                    'the judgement forms posted at the wrong moment -- a local refusal must send '
                    'nothing, and the source form without a replacement must send nothing: '
                    + json.dumps(posts, ensure_ascii=False))

    def test_e2e_script_is_lint_clean(self):
        # The browser driver must be a parseable ESM module; guard against a
        # stray syntax edit by loading it through node's parser only when the
        # toolchain is present (a syntax error here would otherwise surface
        # only mid-run).
        if not NODE_SCRIPT.is_file():
            self.skipTest(f'E2E browser script missing: {NODE_SCRIPT}')
        node = shutil.which('node')
        if not node:
            self.skipTest('node not on PATH')
        proc = subprocess.run([node, '--check', str(NODE_SCRIPT)],
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=60, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 0, 'E2E browser script syntax check failed: '
                                              + proc.stderr)


if __name__ == '__main__':
    unittest.main()
