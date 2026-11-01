// SPDX-License-Identifier: MIT
// W03 remainder: 待审/失败 triage panels + real 最近项目.
// Driven by w03-brief-editor-verify.py (W03_NODE_SCRIPT override), which owns the service.
//
// Validity notes:
//  - The three triage branches are all exercised: UNREADABLE (dev seam, no token),
//    EMPTY (connected, no tasks), and the rule text. A panel that always says "0" would
//    pass an EMPTY-only test, so the unreadable case is asserted to say 未读回 instead.
//  - The classifier cannot be exercised with real FAILED tasks (the repo E2E never queues
//    tasks, and the failure states need a dispatched host), so its vocabulary is instead
//    cross-checked against job_store.py by the Python driver -- see VOCAB check there.
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const base = process.env.W03_SERVICE_URL.replace(/\/$/, '');
const token = process.env.W03_TOKEN;
const OUT = process.env.W03_OUT;

const checks = [];
const check = (name, pass, detail) => checks.push({ name, pass: !!pass, detail });
const consoleErrors = [];
// Console errors are attributed to a PHASE: the unreadable-branch test deliberately
// aborts the tasks endpoint, and the browser logs that aborted request as an error. A
// blanket "zero console errors" assertion would fail on the behaviour under test.
let phase = 'setup';

const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push({ phase, text: m.text() }); });
page.on('pageerror', (e) => consoleErrors.push({ phase, text: 'pageerror: ' + String(e) }));

const panelByTitle = (t) => page.locator('.panel').filter({ has: page.locator('h3', { hasText: t }) });

// ---- A. UNREADABLE branch ------------------------------------------------------
// Reached by ABORTING the per-project tasks endpoint, not via the dev-mode seam: the
// Python service requires auth for the /workbench DOCUMENT itself, so an unauthenticated
// `?dev=1` load gets a 401 JSON body and no app at all (the first version of this harness
// assumed otherwise and found no panels). Intercepting the endpoint isolates exactly the
// readback failure the triage panels must report honestly.
const name = 'W03 Triage ' + Date.now();
await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: name });
const pid = await page.locator('#project').inputValue();

phase = 'unreadable-probe';
await page.route('**/api/projects/*/tasks*', (route) => route.abort());
await page.evaluate(() => { window.location.hash = '#/dashboard'; });
await page.waitForTimeout(2500);
const humanPanel = panelByTitle('待审');
const failPanel = panelByTitle('失败');
check('待审 panel renders', await humanPanel.count() === 1, { count: await humanPanel.count() });
check('失败 panel renders', await failPanel.count() === 1, { count: await failPanel.count() });
const unreadHuman = await humanPanel.first().innerText();
const unreadFail = await failPanel.first().innerText();
check('unreadable tasks endpoint shows 未读回, NOT a fabricated 0',
  /未读回/.test(unreadHuman) && /未读回/.test(unreadFail) && !/（0）/.test(unreadHuman) && !/（0）/.test(unreadFail),
  { unreadHuman, unreadFail });
const bodyText = await page.locator('body').innerText();
check('the derivation rule is stated in the UI and cites the authority',
  /job_store\.py/.test(bodyText) && /OUTCOME_UNKNOWN/.test(bodyText), {});
await page.unroute('**/api/projects/*/tasks*');

// ---- B. EMPTY branch: connected, tasks reachable, none queued ------------------
// Same-document hash navigation keeps the in-memory token, so no reconnect is needed
// here. The hash must actually CHANGE or no hashchange fires and the view is never
// re-rendered (setting it to the value it already holds is a no-op) -- so step away and
// back rather than re-assigning '#/dashboard'.
phase = 'empty-branch';
await page.evaluate(() => { window.location.hash = '#/projects'; });
await page.waitForTimeout(1200);
await page.evaluate(() => { window.location.hash = '#/dashboard'; });
await page.waitForTimeout(2500);
const emptyHuman = await panelByTitle('待审').first().innerText();
const emptyFail = await panelByTitle('失败').first().innerText();
check('connected + no tasks -> honest empty lists (readback count shown)',
  /无待审任务/.test(emptyHuman) && /无失败任务/.test(emptyFail) && /已读回 \d+\/\d+/.test(emptyHuman),
  { emptyHuman, emptyFail });
check('connected panels do not claim 未读回', !/未读回/.test(emptyHuman) && !/未读回/.test(emptyFail),
  { emptyHuman, emptyFail });
const kpis = await page.locator('.kpi-grid strong').allInnerTexts();
check('KPI numbers come from readback (project count >= 1)', kpis.some((k) => /^[1-9]/.test(k)), { kpis });

// ---- C. real 最近项目 (recency) ------------------------------------------------
await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-brief-status').waitFor({ state: 'visible', timeout: 20000 });   // detail rendered => remembered
await page.evaluate(() => { window.location.hash = '#/dashboard'; });
await page.waitForTimeout(2000);
const recentPanel = panelByTitle('最近项目').first();
const recentText = await recentPanel.innerText();
check('the opened project is marked 最近打开 on the dashboard', /最近打开/.test(recentText), { recentText: recentText.slice(0, 200) });
check('recency ordering rule is disclosed', /最近打开的项目排序|服务返回顺序/.test(recentText), {});
const firstRecentRow = await recentPanel.locator('.list .list-item').first().innerText();
check('the opened project is listed first (recency order)', firstRecentRow.includes(name), { firstRecentRow });

// ---- D. reload behaviour: route context + local recency survive; session does not
await page.reload({ waitUntil: 'load' });
await page.waitForTimeout(2000);
const afterReloadRaw = await page.evaluate(() => ({
  hash: window.location.hash,
  text: document.getElementById('route-view') ? document.getElementById('route-view').innerText : '',
}));
check('reload keeps the route context (hash still the dashboard)', afterReloadRaw.hash.includes('dashboard'),
  { hash: afterReloadRaw.hash });
// The service token is held in memory ONLY (workbench.ts: `export let token = ''`), so a
// reload lands back on the connect prompt. That is asserted rather than worked around --
// and it is the honest no-fake-data behaviour: no phantom KPIs before a connection.
check('after reload the app asks to reconnect instead of showing stale/fake data',
  /请先在工作台连接本机设计服务/.test(afterReloadRaw.text), { text: afterReloadRaw.text.slice(0, 160) });
// Reconnect: the login form only shows on the workbench route
// (`login.hidden = showWorkbench ? connected : true`), so navigate there first.
await page.evaluate(() => { window.location.hash = ''; });
await page.locator('#token').waitFor({ state: 'visible', timeout: 20000 });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
await page.evaluate(() => { window.location.hash = '#/dashboard'; });
await page.waitForTimeout(2500);
const afterReload = await panelByTitle('最近项目').first().innerText();
check('local recency survives a reload (persisted outside the in-memory session)',
  /最近打开/.test(afterReload) && afterReload.includes(name), { afterReload: afterReload.slice(0, 220) });

// ---- E. 继续项目 (pack §101) ---------------------------------------------------
phase = 'continue-project';
const continuePanel = page.locator('.panel').filter({ has: page.locator('h3', { hasText: '继续项目' }) });
check('继续项目 panel renders', await continuePanel.count() === 1, {});
check('it names the most recently opened project', (await continuePanel.first().innerText()).includes(name),
  { text: (await continuePanel.first().innerText()).slice(0, 160) });
await continuePanel.locator('#pd-continue').click();
await page.waitForTimeout(1200);
check('继续 navigates into that project', (await page.evaluate(() => window.location.hash)).includes(pid),
  { hash: await page.evaluate(() => window.location.hash) });
phase = 'hygiene';
const unexpected = consoleErrors.filter((e) => e.phase !== 'unreadable-probe');
check('the only console errors are the deliberately aborted tasks requests',
  unexpected.length === 0, { unexpected: unexpected.slice(0, 4), all: consoleErrors.length });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w03-triage-recent', project_id: pid, checks, console_errors: consoleErrors,
  measured_at: new Date().toISOString(),
}, null, 2), 'utf8');
for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W03b checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
