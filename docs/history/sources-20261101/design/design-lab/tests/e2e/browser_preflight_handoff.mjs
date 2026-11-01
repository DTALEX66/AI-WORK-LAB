// SPDX-License-Identifier: MIT
// UI-plan step ⑤/⑦: a real Chromium drives the 预检 / QA view through the one case the
// acceptance gate demands — a hard block, a fix, and a re-check that must observe the
// fix — and then asserts that 交付中心 reports a read zero as a read zero.
//
// Controlled-runtime (E2): real browser, committed build/main.js, real loopback
// service, a real `design-lab/config/task-resources.json` fixture under the service
// root. It claims no E3 host run and no E4 human jury.
//
// Driven by design-lab/tests/test_workbench_preflight_handoff_e2e.py. Environment:
//   E2E_SERVICE_URL, E2E_TOKEN, E2E_NODE_MODULES  required (same contract as the
//   design-layer slice); E2E_BROWSER optional; E2E_FIXTURE registry path to rewrite
//   between the block and the re-check.
// Prints `E2E_PREFLIGHT_OK steps=<n>` and exits 0 on a full pass; otherwise prints
// `E2E_PREFLIGHT_FAIL <reason>` and exits 1.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import process from 'node:process';

const serviceUrl = process.env.E2E_SERVICE_URL;
const token = process.env.E2E_TOKEN;
const nmDir = process.env.E2E_NODE_MODULES;
const browserPath = process.env.E2E_BROWSER || undefined;
const fixture = process.env.E2E_FIXTURE;
if (!serviceUrl || !token || !nmDir) {
  console.log('E2E_PREFLIGHT_FAIL missing E2E_SERVICE_URL / E2E_TOKEN / E2E_NODE_MODULES');
  process.exit(2);
}
const require = createRequire(nmDir + '/noop.js');
const pw = require('playwright');

const launchOpts = { headless: true };
if (browserPath) launchOpts.executablePath = browserPath;
const browser = await pw.chromium.launch(launchOpts);
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push(String(e)));

const fail = (why) => { console.log(`E2E_PREFLIGHT_FAIL ${why}`); return process.exit(1); };
const writeRegistry = (blockedRefName) => {
  const doc = {
    schemaVersion: 'design-lab/task-resources/v1',
    resources: {
      'tool-present': { kind: 'tool', name: 'git', host_scope: 'none' },
      // The fix is a declaration change, not an install: the task stops naming a
      // tool that no search scope contains and names one that does.
      'tool-missing': { kind: 'tool', name: blockedRefName, host_scope: 'none' },
    },
    tasks: {
      'UIE2E::ready': ['tool-present'],
      'UIE2E::blocked': ['tool-missing'],
    },
  };
  fs.writeFileSync(fixture, JSON.stringify(doc, null, 2) + '\n', { encoding: 'utf8' });
};

let steps = 0;
try {
  // Connect first, then route. Landing on #/preflight before the token exists shows
  // the connect form instead, and `show()` returns the app to the landing view once
  // the session is established - the route has to be taken after that.
  await page.goto(serviceUrl + '/workbench', { waitUntil: 'load' });
  await page.locator('#token').fill(token);
  await page.locator('#connect-form button').first().click();
  await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
  await page.evaluate(() => { window.location.hash = '#/preflight'; });
  await page.waitForFunction(() => !!document.getElementById('preflight-run'),
    null, { timeout: 20000 })
    .catch(() => fail('preflight view never mounted (no #preflight-run)'));
  await page.locator('#preflight-task-input').waitFor({ state: 'visible', timeout: 15000 });
  steps += 1;

  const runPreflight = async (taskId) => {
    await page.locator('#preflight-task-input').fill(taskId);
    await page.locator('#preflight-run').click();
    // The verdict pill only exists after a run has answered; waiting on it (rather
    // than on the absence of a loading word) cannot match the initial hint panel.
    await page.waitForFunction(() => {
      const box = document.querySelector('.preflight-result');
      return box && box.querySelector('.tag') && !/正在读回/.test(box.textContent || '');
    }, null, { timeout: 20000 });
    return page.evaluate(() => {
      const box = document.querySelector('.preflight-result');
      const tag = box?.querySelector('.tag');
      const verdict = Array.from(document.querySelectorAll('.kpi strong'))
        .map((n) => (n.textContent || '').trim());
      return {
        text: (box?.textContent || '').replace(/\s+/g, ' ').trim(),
        tagText: (tag?.textContent || '').trim(),
        tagClass: tag?.className || '',
        kpis: verdict,
      };
    });
  };

  // 1. A task whose declared resource resolves: READY, and the verdict KPI is filled.
  writeRegistry('designlab-no-such-tool-zzz');
  const ready = await runPreflight('UIE2E::ready');
  if (ready.tagText !== 'READY') fail(`expected READY, got "${ready.tagText}"`);
  if (!/tag ok/.test(ready.tagClass)) fail('READY verdict tag is not the ok variant');
  if (!ready.kpis.includes('READY')) fail(`verdict KPI not filled: ${JSON.stringify(ready.kpis)}`);
  steps += 1;

  // 2. The block case. The previous READY must not survive on screen.
  const blocked = await runPreflight('UIE2E::blocked');
  if (blocked.tagText !== 'BLOCKED') fail(`expected BLOCKED, got "${blocked.tagText}"`);
  if (!/tag bad/.test(blocked.tagClass)) fail('BLOCKED verdict tag is not the bad variant');
  // The view names the blocked resource by its registry ref and shows the state word
  // the service emitted (UNAVAILABLE), not the tool binary name.
  if (!blocked.text.includes('tool-missing'))
    fail(`the blocked resource ref is not named: ${blocked.text.slice(0, 200)}`);
  if (!blocked.text.includes('UNAVAILABLE'))
    fail(`the blocked state word is absent: ${blocked.text.slice(0, 200)}`);
  if (blocked.kpis.includes('READY'))
    fail(`stale READY verdict survived the re-run: ${JSON.stringify(blocked.kpis)}`);
  steps += 1;

  // 3. Fix the declaration, re-check the SAME task id, and require the fix observed.
  const fixed = JSON.parse(fs.readFileSync(fixture, 'utf8'));
  fixed.resources['tool-missing'] = { kind: 'tool', name: 'git', host_scope: 'none' };
  fs.writeFileSync(fixture, JSON.stringify(fixed, null, 2) + '\n', { encoding: 'utf8' });
  const rechecked = await runPreflight('UIE2E::blocked');
  if (rechecked.tagText !== 'READY')
    fail(`block -> fix -> re-check did not reach READY: "${rechecked.tagText}"`);
  steps += 1;

  // 4. Handoff readback: connected with no bundles must read as a real zero, not as
  //    "unread" — the distinction #260 exists to keep.
  await page.evaluate(() => { window.location.hash = '#/deliverables'; });
  await page.waitForFunction(() => {
    const view = document.getElementById('route-view');
    return view && !view.querySelector('.view-loading');
  }, null, { timeout: 20000 });
  const handoff = await page.evaluate(() => Array.from(
    document.querySelectorAll('#route-view h3'))
    .map((h) => (h.textContent || '').trim())
    .filter((t) => t.includes('交付包')));
  if (!handoff.length) fail('交付中心 shows no 交付包 heading');
  if (handoff.some((t) => t.includes('未读回')))
    fail(`a connected zero-bundle readback rendered as unread: ${JSON.stringify(handoff)}`);
  steps += 1;

  if (consoleErrors.length) fail(`console errors: ${consoleErrors.slice(0, 3).join(' | ')}`);
} catch (error) {
  // A bare "locator timed out" cannot be acted on. Report what the page actually is.
  const state = await page.evaluate(() => ({
    hash: window.location.hash,
    loginHidden: document.getElementById('login')?.hidden,
    workspaceHidden: document.getElementById('workspace')?.hidden,
    routeViewHidden: document.getElementById('route-view')?.hidden,
    inputPresent: !!document.getElementById('preflight-task-input'),
    inputVisible: !!document.getElementById('preflight-task-input')?.offsetParent,
    headings: Array.from(document.querySelectorAll('#route-view h2, #route-view h3'))
      .map((h) => (h.textContent || '').trim()).slice(0, 6),
  })).catch(() => 'unreadable');
  await browser.close();
  fail(`exception: ${error && error.message ? error.message : String(error)} | page=${JSON.stringify(state)}`);
}
await browser.close();
console.log(`E2E_PREFLIGHT_OK steps=${steps}`);
