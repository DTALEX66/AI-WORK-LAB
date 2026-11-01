// SPDX-License-Identifier: MIT
// Pack §103: "中文长标题截断有全称入口".
// Driven by w03-brief-editor-verify.py (shared runner; W03_NODE_SCRIPT/W03_OUT).
//
// LESSON FROM THE PREVIOUS ATTEMPT (which had to be reverted): it located the control by
// its LABEL text (`button:has-text("全称")`), matched nothing, and then threw on a later
// call so no evidence file was written -- an unverifiable change. This version (a) locates
// the control by its stable `.title-expand` class, and (b) DUMPS the row HTML into the
// check detail BEFORE asserting anything, so a failure is diagnosable from the evidence
// file rather than by re-running.
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
const LONG = '秋季品牌视觉系统重构与跨渠道一致性交付规范';
const SHORT = '秋季视觉';

const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + String(e)));

await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
const name = 'W14 Title ' + Date.now();
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: name });
const pid = await page.locator('#project').inputValue();
await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-brief-title').waitFor({ state: 'visible', timeout: 20000 });

const createBrief = async (title, goals) => {
  await page.locator('#pd-brief-title').fill(title);
  await page.locator('#pd-brief-goals').fill(goals);
  await page.locator('#pd-brief-create').click();
  await page.waitForFunction(() => /已保存并读回/.test(document.getElementById('pd-brief-status')?.textContent || ''),
    null, { timeout: 20000 });
  await page.waitForTimeout(400);
};

// ---- SHORT title: no control (nothing was hidden) ------------------------------
await createBrief(SHORT, '现代');
const briefPanel = page.locator('.panel').filter({ has: page.locator('h3', { hasText: '简报（Brief）' }) });
const shortRow = briefPanel.locator('.list-item').filter({ hasText: SHORT }).first();
const shortHtml = await shortRow.evaluate((r) => r.outerHTML).catch(() => 'n/a');
check('SHORT title shown in full', (await shortRow.innerText()).includes(SHORT), { shortHtml });
check('SHORT title has NO expand control', await shortRow.locator('.title-expand').count() === 0, { shortHtml });

// ---- LONG CJK title: truncated, with a real entry point ------------------------
await createBrief(LONG, '可复用');
const longRow = briefPanel.locator('.list-item').filter({ hasText: LONG.slice(0, 8) }).first();
const rowHtml = await longRow.evaluate((r) => r.outerHTML).catch((e) => 'DUMP FAILED: ' + String(e));
const strong = longRow.locator('strong.title-text').first();
const beforeText = await strong.innerText().catch(() => 'n/a');
const beforeTitle = await strong.getAttribute('title').catch(() => null);
check('LONG CJK title is truncated in place', typeof beforeText === 'string' && beforeText.endsWith('…'), { beforeText, rowHtml });
check('truncated heading keeps the full text for pointer users', beforeTitle === `${LONG} · v1`, { beforeTitle, rowHtml });

const btn = longRow.locator('.title-expand').first();
const btnCount = await btn.count();
check('the truncation HAS an entry point (a real control)', btnCount === 1, { btnCount, rowHtml });

if (btnCount === 1) {
  check('the entry point is a <button> carrying aria-expanded',
    (await btn.evaluate((b) => b.tagName)) === 'BUTTON' && (await btn.getAttribute('aria-expanded')) === 'false',
    { tag: await btn.evaluate((b) => b.tagName) });
  await btn.click();
  await page.waitForTimeout(200);
  check('clicking it reveals the FULL title', (await strong.innerText()) === `${LONG} · v1`, { now: await strong.innerText() });
  check('aria-expanded flips to true', (await btn.getAttribute('aria-expanded')) === 'true', {});
  await btn.click();
  await page.waitForTimeout(200);
  check('clicking again collapses it', (await strong.innerText()).endsWith('…'), { now: await strong.innerText() });
  await btn.focus();
  check('the entry point is keyboard-focusable', (await page.evaluate(() => document.activeElement?.tagName)) === 'BUTTON', {});
  await page.keyboard.press('Enter');
  await page.waitForTimeout(200);
  check('Enter expands it (keyboard, not hover-only)',
    (await strong.innerText()) === `${LONG} · v1` && (await btn.getAttribute('aria-expanded')) === 'true', {});
} else {
  check('SKIPPED: control absent, see rowHtml', false, { note: 'entry point not rendered' });
}

// direction-row titles use the SAME control (they used to be a plain <strong>)
await page.locator('#pd-dir-title').fill(LONG);
await page.locator('#pd-dir-create').click();
await page.waitForFunction(() => /候选不会自动成为选定方向/.test(document.getElementById('pd-dir-status')?.textContent || ''),
  null, { timeout: 20000 });
const dirRow = page.locator('.panel').filter({ has: page.locator('h3', { hasText: '方向（Direction）' }) })
  .locator('.list-item').filter({ hasText: LONG.slice(0, 8) }).first();
const dirBtn = await dirRow.locator('.title-expand').count();
check('direction-row titles get the same full-text entry point', dirBtn === 1,
  { dirBtn, dirRowHtml: await dirRow.evaluate((r) => r.outerHTML).catch(() => 'n/a') });
check('no console errors', consoleErrors.length === 0, { consoleErrors: consoleErrors.slice(0, 3) });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w14-long-title-entry', project_id: pid, checks, console_errors: consoleErrors,
  measured_at: new Date().toISOString(),
}, null, 2), 'utf8');
for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W14-title checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
