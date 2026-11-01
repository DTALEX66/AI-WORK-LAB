// SPDX-License-Identifier: MIT
// W03 browser half: drive the real Brief flow in the route shell and assert W03's
// acceptance lines. Driven by w03-brief-editor-verify.py (which owns the service).
//
// Every assertion is on OBSERVED DOM/state, and the failure case asserts a NEGATIVE
// (no success text anywhere) -- because "失败不弹『保存成功』" is only proven by showing
// the success string is absent, not by showing an error is present.
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);

const base = process.env.W03_SERVICE_URL.replace(/\/$/, '');
const token = process.env.W03_TOKEN;
const BROWSER = process.env.W03_BROWSER;
const OUT = process.env.W03_OUT;

const checks = [];
const check = (name, pass, detail) => { checks.push({ name, pass: !!pass, detail }); };
const consoleErrors = [];
const pageErrors = [];
// Console errors are attributed to a PHASE. This run deliberately provokes one failed
// write (the STALE_REVISION probe) and the browser logs the 409 as a console error, so a
// blanket "zero console errors" assertion would be wrong: it would fail on the very
// behaviour under test. What must hold is that the ONLY console error is that expected
// 409, and that it belongs to the stale-rejection phase.
let phase = 'setup';

const browser = await chromium.launch({ executablePath: BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push({ phase, text: m.text() }); });
page.on('pageerror', (e) => pageErrors.push({ phase, text: String(e) }));

const statusText = () => page.locator('#pd-brief-status').innerText();
const briefRows = () => page.locator('.panel .list .list-item strong').allInnerTexts();
// Select brief rows by STATE, not by position: `.first()` is unstable because versions
// created in the same second come back in an order that is not guaranteed (a run using
// .first() for the "stale" case actually revised the LIVE version and created version 3).
// `.tag.ok` marks the live version, `.tag.warn` marks a superseded one.
const rowButton = (tagClass) => page.locator('.panel .list .list-item')
  .filter({ has: page.locator(`.tag.${tagClass}`) })
  .locator('button.ghost-btn');

// ---- connect + create a project (the project card source) ----------------------
await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
const projectName = 'W03 Brief ' + Date.now();
await page.locator('#project-name').fill(projectName);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: projectName }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: projectName });
const projectId = await page.locator('#project').inputValue();
check('project created and selectable', !!projectId, { projectId });

// ---- 1. from the project card into the real brief editor -----------------------
await page.evaluate((pid) => { window.location.hash = `#/projects/${encodeURIComponent(pid)}`; }, projectId);
await page.locator('#pd-brief-status').waitFor({ state: 'visible', timeout: 20000 });
const navCount = await page.locator('.app-nav-item').count();
check('project-detail route renders the brief editor', await page.locator('#pd-brief-create').count() === 1, {});
check('.app-nav-item stays 12 (B07 IA invariant)', navCount === 12, { navCount });
check('no invented KPI on an empty project', (await briefRows()).some((t) => t.includes('尚无简报')),
  { rows: await briefRows() });

// ---- create a brief (real write) ----------------------------------------------
await page.locator('#pd-brief-title').fill('秋季品牌视觉');
await page.locator('#pd-brief-goals').fill('现代, 温暖, 克制');
await page.locator('#pd-brief-constraints').fill('不改变 logo 拓扑');
await page.locator('#pd-brief-create').click();
await page.waitForFunction(() => {
  const el = document.getElementById('pd-brief-status');
  return el && /已保存并读回/.test(el.textContent || '');
}, null, { timeout: 20000 });
const afterCreate = await briefRows();
check('brief created and READ BACK from the service', afterCreate.some((t) => t.includes('秋季品牌视觉') && t.includes('v1')),
  { rows: afterCreate });
const createdStatus = await statusText();
check('create reported success only after the write resolved', /已保存并读回/.test(createdStatus), { createdStatus });

// ---- 1b. W03 interaction requirement: focus + error locating -------------------
phase = 'validation-focus';
await page.locator('#pd-brief-title').fill('');
await page.locator('#pd-brief-goals').fill('');
await page.locator('#pd-brief-create').click();
await page.waitForTimeout(500);
const emptySubmit = await page.evaluate(() => ({
  active: document.activeElement ? document.activeElement.id : null,
  invalid: document.getElementById('pd-brief-title')?.getAttribute('aria-invalid'),
  status: document.getElementById('pd-brief-status')?.textContent,
  statusClass: document.getElementById('pd-brief-status')?.className,
}));
check('empty submit focuses the offending field', emptySubmit.active === 'pd-brief-title', emptySubmit);
check('offending field is marked aria-invalid', emptySubmit.invalid === 'true', emptySubmit);
check('validation failure is an error and claims no save',
  /error/.test(emptySubmit.statusClass || '') && !/已保存/.test(emptySubmit.status || ''), emptySubmit);

// ---- 2. open a version, revise it, and read the new version back ---------------
phase = 'revise';
await rowButton('ok').first().click();
await page.waitForFunction(() => /正在修订/.test(document.getElementById('pd-rev-target')?.textContent || ''),
  null, { timeout: 20000 });
const prefilled = await page.locator('#pd-rev-title').inputValue();
check('「新版本」 prefills the source version', prefilled === '秋季品牌视觉', { prefilled });
check('「新版本」 moves focus to the field being revised',
  (await page.evaluate(() => document.activeElement?.id)) === 'pd-rev-title',
  { active: await page.evaluate(() => document.activeElement?.id) });
// loadLineage() is async and the hint above is set synchronously, so counting here
// without waiting measured 0 items. Wait for the lineage to actually render.
await page.waitForFunction(() => document.querySelectorAll('#pd-brief-lineage .list-item').length >= 2,
  null, { timeout: 20000 }).catch(() => {});
const lineageCount = await page.locator('#pd-brief-lineage .list-item').count();
const lineageText = await page.locator('#pd-brief-lineage').innerText().catch(() => '');
check('version lineage is read back', lineageCount >= 2 && /版本 1/.test(lineageText),
  { lineageCount, lineageText: lineageText.slice(0, 160) });

await page.locator('#pd-rev-goals').fill('现代, 温暖, 克制, 可复用');
await page.locator('#pd-brief-revise').click();
await page.waitForFunction(() => /已保存为版本 2/.test(document.getElementById('pd-brief-status')?.textContent || ''),
  null, { timeout: 20000 });
const afterRevise = await briefRows();
check('revision created version 2 and read it back', afterRevise.some((t) => t.includes('v2')), { rows: afterRevise });
const tags = await page.locator('.panel .list .list-item .tag').allInnerTexts();
check('the superseded version is tagged as such (old content not rewritten)',
  tags.some((t) => /已被版本/.test(t)) || tags.some((t) => /取代/.test(t)), { tags });

// ---- 3. FAILURE honesty: revise the now-stale v1 and require NO success text ----
phase = 'stale-rejection';
await rowButton('warn').first().click();
await page.waitForTimeout(400);
await page.locator('#pd-brief-revise').click();
await page.waitForFunction(() => {
  const el = document.getElementById('pd-brief-status');
  return el && el.className.includes('error');
}, null, { timeout: 20000 }).catch(() => {});
const failStatus = await statusText();
const failClass = await page.locator('#pd-brief-status').getAttribute('class');
check('stale revision is rejected and explained (STALE_REVISION)', /STALE_REVISION/.test(failStatus), { failStatus });
check('failure is rendered as an error, not a hint', /error/.test(failClass || ''), { failClass });
check('NO success text anywhere after a rejected write',
  !/已保存/.test(failStatus) && !(await page.locator('body').innerText()).includes('已保存为版本'),
  { failStatus });

// ---- 4. reload keeps the project context --------------------------------------
phase = 'reload';
await page.reload({ waitUntil: 'load' });
await page.waitForTimeout(1500);
const hashAfter = await page.evaluate(() => window.location.hash);
check('reload keeps the project route (context preserved)', hashAfter.includes(projectId), { hashAfter });

// ---- hygiene -------------------------------------------------------------------
phase = 'hygiene';
const cspErrors = consoleErrors.filter((e) => /Content Security Policy|violates/i.test(e.text));
const unexpected = consoleErrors.filter((e) => !(e.phase === 'stale-rejection' && /409 \(Conflict\)/.test(e.text)));
check('no CSP violation in console', cspErrors.length === 0, { cspErrors: cspErrors.slice(0, 3) });
check('the only console error is the deliberate 409 from the stale-revision probe',
  unexpected.length === 0, { unexpected: unexpected.slice(0, 4), all: consoleErrors });
check('no page errors', pageErrors.length === 0, { pageErrors: pageErrors.slice(0, 3) });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w03-brief-editor',
  project_id: projectId,
  checks,
  console_errors: consoleErrors,
  page_errors: pageErrors,
  measured_at: new Date().toISOString(),
}, null, 2), 'utf8');

for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W03 checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
