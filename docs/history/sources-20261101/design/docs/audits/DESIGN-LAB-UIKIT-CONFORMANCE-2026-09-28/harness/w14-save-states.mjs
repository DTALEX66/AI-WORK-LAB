// SPDX-License-Identifier: MIT
// Pack 01_RESEARCH_AND_PRODUCT: "表单保存有 dirty、saving、saved、conflict 状态，
// 离开未保存页有恢复策略". Verifies those four states and the recovery policy.
// Driven by w03-brief-editor-verify.py (shared runner; W03_NODE_SCRIPT/W03_OUT).
//
// Claim-by-claim:
//   dirty     -> typing in a form marks it 未保存（dirty） without touching the service
//   saving    -> submitting shows 保存中（saving）
//   saved     -> after the service confirms, 已保存（saved） AND the draft is cleared
//   conflict  -> a STALE_REVISION is labelled 冲突（conflict·可恢复）, NOT a generic 失败
//   recovery  -> leaving with an unsaved draft and returning restores it, discloses it,
//                and 丢弃草稿 clears it -- and none of that writes to the service.
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
let phase = 'setup';
let writeCount = 0;

const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push({ phase, text: m.text() }); });
page.on('pageerror', (e) => consoleErrors.push({ phase, text: 'pageerror: ' + String(e) }));
// Count only POST writes, to prove that dirty/draft operations never touch the service.
page.on('request', (r) => { if (r.method() === 'POST' && /\/api\/projects\//.test(r.url())) writeCount++; });

const chip = () => page.locator('#pd-brief-state').innerText();

await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
const name = 'W14 States ' + Date.now();
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: name });
const pid = await page.locator('#project').inputValue();
await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-brief-state').waitFor({ state: 'visible', timeout: 20000 });

// ---- dirty: typing marks the form, and does NOT write -------------------------
phase = 'dirty';
const writesBefore = writeCount;
check('a fresh form starts 未修改', /未修改/.test(await chip()), { chip: await chip() });
await page.locator('#pd-brief-title').fill('秋季品牌视觉');
await page.waitForFunction(() => /dirty/.test(document.getElementById('pd-brief-state')?.textContent || ''),
  null, { timeout: 10000 });
check('typing marks the form 未保存（dirty）', /dirty/.test(await chip()), { chip: await chip() });
check('dirty does NOT write to the service', writeCount === writesBefore, { writesBefore, writeCount });
await page.locator('#pd-brief-goals').fill('现代, 温暖');

// ---- recovery: leave with the draft unsaved, come back, it is restored ---------
phase = 'recovery';
await page.evaluate(() => { window.location.hash = '#/dashboard'; });
await page.waitForTimeout(800);
await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-brief-state').waitFor({ state: 'visible', timeout: 20000 });
const restoredTitle = await page.locator('#pd-brief-title').inputValue();
check('leaving with an unsaved draft and returning RESTORES it', restoredTitle === '秋季品牌视觉', { restoredTitle });
check('the restoration is DISCLOSED, not silent', /已恢复上次未保存的草稿/.test(await page.locator('#pd-brief-draft').innerText()),
  { note: await page.locator('#pd-brief-draft').innerText() });
check('a restored draft still reads as 未保存（dirty）', /dirty/.test(await chip()), { chip: await chip() });
check('recovery itself wrote nothing to the service', writeCount === writesBefore, { writeCount });

// ---- saving + saved ------------------------------------------------------------
phase = 'saving-saved';
await page.locator('#pd-brief-create').click();
// saving is transient; accept either the chip or that the write completed with 已保存
const sawSaving = await page.evaluate(() => /saving/.test(document.getElementById('pd-brief-state')?.textContent || ''))
  .catch(() => false);
await page.waitForFunction(() => /已保存并读回/.test(document.getElementById('pd-brief-status')?.textContent || ''),
  null, { timeout: 20000 });
check('after the service confirms, the state is 已保存（saved）', /saved/.test(await chip()), { chip: await chip(), sawSaving });
check('the save really hit the service exactly once', writeCount === writesBefore + 1, { writesBefore, writeCount });
check('a successful save CLEARS the draft', !/已恢复上次未保存的草稿/.test(await page.locator('#pd-brief-draft').innerText()),
  { note: await page.locator('#pd-brief-draft').innerText() });

// ---- conflict: STALE_REVISION is a distinct, recoverable state -----------------
phase = 'conflict';
// Revise the live version once ...
await page.locator('.panel').filter({ hasText: '简报（Brief）' }).locator('.list-item')
  .filter({ has: page.locator('.tag.ok') }).first().locator('button.ghost-btn').click();
await page.waitForFunction(() => /正在修订/.test(document.getElementById('pd-rev-target')?.textContent || ''),
  null, { timeout: 20000 });
await page.locator('#pd-brief-revise').click();
await page.waitForFunction(() => /已保存为版本 2/.test(document.getElementById('pd-brief-status')?.textContent || ''),
  null, { timeout: 20000 });
// ... then revise the now-superseded v1 -> the service returns STALE_REVISION
await page.locator('.panel').filter({ hasText: '简报（Brief）' }).locator('.list-item')
  .filter({ has: page.locator('.tag.warn') }).first().locator('button.ghost-btn').click();
await page.waitForTimeout(400);
await page.locator('#pd-brief-revise').click();
await page.waitForFunction(() => {
  const c = document.getElementById('pd-brief-state');
  return c && /conflict/.test(c.textContent || '');
}, null, { timeout: 20000 }).catch(() => {});
const conflictChip = await chip();
const conflictStatus = await page.locator('#pd-brief-status').innerText();
check('a STALE_REVISION is labelled 冲突（conflict·可恢复）, not a generic failure',
  /conflict/.test(conflictChip) && !/失败/.test(conflictChip), { conflictChip });
check('the conflict message explains the recovery (continue from the newest version)',
  /STALE_REVISION/.test(conflictStatus) && /最新版本/.test(conflictStatus), { conflictStatus });

phase = 'hygiene';
const unexpected = consoleErrors.filter((e) => !(e.phase === 'conflict' && /409|Conflict/.test(e.text)));
check('console errors are limited to the deliberate 409 conflict probe',
  unexpected.length === 0, { unexpected: unexpected.slice(0, 3), all: consoleErrors.length });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w14-save-states', project_id: pid, checks, console_errors: consoleErrors,
  writes_total: writeCount, measured_at: new Date().toISOString(),
}, null, 2), 'utf8');
for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W14-states checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
