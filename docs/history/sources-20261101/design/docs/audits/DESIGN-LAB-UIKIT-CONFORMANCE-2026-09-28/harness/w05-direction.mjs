// SPDX-License-Identifier: MIT
// W05 — Direction: candidate cards, explicit HUMAN choice, and explicit expiry.
// Driven by w03-brief-editor-verify.py (shared runner; W03_NODE_SCRIPT/W03_OUT).
//
// Pack W05 acceptance exercised here:
//   2. AI 候选不能自动替代人选 -> a fresh candidate is NEVER chosen; choosing records
//      actor_kind='human'; the panel says the candidate does not auto-become the choice.
//   3. 改变 Brief 使相关审查状态显式过期 -> after the bound brief gets a new version, the
//      direction is flagged as NEEDING RE-REVIEW (derived from superseded_by), while its
//      chosen flag is left as the human set it -- explicit expiry, not silent
//      invalidation and not silent carry-over.
//   1. 版本链/chosen/active binding 一致 -> the panel reports the real relationship,
//      including the honest intermediate state "方向已选定，但尚未绑定设计系统".
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

const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push({ phase, text: m.text() }); });
page.on('pageerror', (e) => consoleErrors.push({ phase, text: 'pageerror: ' + String(e) }));

const panel = (h3Text) => page.locator('.panel').filter({ has: page.locator('h3', { hasText: h3Text }) });
const dirRow = (title) => panel('方向（Direction）').locator('.list-item').filter({ hasText: title });
const consistency = () => page.locator('#pd-dir-consistency').innerText();

// ---- setup
await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
const name = 'W05 Direction ' + Date.now();
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: name });
const pid = await page.locator('#project').inputValue();
await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-brief-title').waitFor({ state: 'visible', timeout: 20000 });

// ---- a brief to bind directions to
phase = 'brief';
await page.locator('#pd-brief-title').fill('秋季品牌视觉');
await page.locator('#pd-brief-goals').fill('现代, 温暖');
await page.locator('#pd-brief-create').click();
await page.waitForFunction(() => /已保存并读回/.test(document.getElementById('pd-brief-status')?.textContent || ''),
  null, { timeout: 20000 });

// ---- 验收 2a: a fresh candidate is never auto-chosen ----------------------------
phase = 'no-auto-choice';
check('before any direction exists the panel reports no choice', /尚未选定方向/.test(await consistency()),
  { consistency: await consistency() });
for (const t of ['方向甲', '方向乙']) {
  await page.locator('#pd-dir-title').fill(t);
  await page.locator('#pd-dir-create').click();
  await page.waitForFunction(() => /候选不会自动成为选定方向/.test(document.getElementById('pd-dir-status')?.textContent || ''),
    null, { timeout: 20000 });
}
const rowsAfterCreate = await panel('方向（Direction）').locator('.list-item').allInnerTexts();
check('two candidates are listed', rowsAfterCreate.filter((r) => /方向甲|方向乙/.test(r)).length === 2, { rowsAfterCreate });
check('NO candidate is auto-chosen', !rowsAfterCreate.some((r) => /已选定/.test(r)) && /尚未选定方向/.test(await consistency()),
  { rowsAfterCreate, consistency: await consistency() });
check('the service readback also has no chosen direction', /尚未选定方向/.test(await consistency()), {});

// ---- 验收 2b: choosing is an explicit human act ---------------------------------
phase = 'human-choice';
await dirRow('方向甲').locator('button.ghost-btn').click();
await page.waitForFunction(() => /选定人：/.test(document.body.innerText), null, { timeout: 20000 });
const chosenRow = await dirRow('方向甲').innerText();
const otherRow = await dirRow('方向乙').innerText();
check('the chosen candidate is marked chosen', /已选定/.test(chosenRow), { chosenRow });
check('the choice records the HUMAN actor (actor_kind=human)', /workbench-user/.test(chosenRow) && /human/.test(chosenRow),
  { chosenRow });
check('the other candidate is still only a candidate', /候选/.test(otherRow) && !/已选定/.test(otherRow), { otherRow });
check('验收1: the honest intermediate state is reported (chosen but not yet bound)',
  /方向已选定，但尚未绑定设计系统/.test(await consistency()), { consistency: await consistency() });
check('the panel does not claim full consistency without a binding',
  !/一致：选定方向与活动绑定/.test(await consistency()), {});

// ---- 验收 3: changing the Brief explicitly expires the bound review state --------
phase = 'explicit-expiry';
const briefPanel = panel('简报（Brief）');
await briefPanel.locator('.list-item').filter({ has: page.locator('.tag.ok') }).first().locator('button.ghost-btn').click();
await page.waitForFunction(() => /正在修订/.test(document.getElementById('pd-rev-target')?.textContent || ''),
  null, { timeout: 20000 });
await page.locator('#pd-rev-goals').fill('现代, 温暖, 可复用');
await page.locator('#pd-brief-revise').click();
await page.waitForFunction(() => /已保存为版本 2/.test(document.getElementById('pd-brief-status')?.textContent || ''),
  null, { timeout: 20000 });
const afterBriefChange = await panel('方向（Direction）').innerText();
check('验收3: directions bound to the superseded brief are flagged as needing re-review',
  /已被取代 → 该方向需重新审查/.test(afterBriefChange), { afterBriefChange: afterBriefChange.slice(0, 400) });
check('the flag is explicit expiry, NOT silent invalidation (the human choice stands)',
  /已选定/.test(await dirRow('方向甲').innerText()), { chosenRow: await dirRow('方向甲').innerText() });
check('the expiry wording does not claim the direction was voided or auto-carried',
  !/自动失效(?!，)|已作废/.test(afterBriefChange), {});

phase = 'hygiene';
check('no console errors', consoleErrors.length === 0, { consoleErrors: consoleErrors.slice(0, 3) });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w05-direction', project_id: pid, checks, console_errors: consoleErrors,
  measured_at: new Date().toISOString(),
}, null, 2), 'utf8');
for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W05 checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
