// SPDX-License-Identifier: MIT
// W06 (first half) — DesignSystem catalog + bind, and the W05->W06 gate composition.
// Driven by w03-brief-editor-verify.py (shared runner; W03_NODE_SCRIPT/W03_OUT).
//
// Claims under test:
//   1. The catalog is read back from the service with its own evidence_level (no promotion).
//   2. Binding is UNAVAILABLE until a human has chosen a direction, and the UI says why --
//      so W05's human gate composes into W06 rather than being bypassable.
//   3. After the human choice, binding succeeds, is read back, and the binding is
//      CONSISTENT with the chosen direction.
//   4. A binding is not presented as production/quality acceptance.
//   5. The Token WRITE half does not exist yet, so the panel says so instead of offering a
//      fake editor (the gap is documented in findings/W06-TOKEN-WRITE-GAP.md).
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
const dsPanel = () => panel('设计系统（DesignSystem）');

await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
const name = 'W06 DS ' + Date.now();
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: name });
const pid = await page.locator('#project').inputValue();
await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-ds-bind').waitFor({ state: 'visible', timeout: 20000 });

// ---- 1 + 2: catalog read back, and the gate is CLOSED before a human choice -------
phase = 'gate-closed';
const panelText0 = await dsPanel().innerText();
const catCount = Number((/目录 (\d+) 项/.exec(panelText0) || [])[1] ?? -1);
check('catalog is read back with a non-zero count', catCount > 0, { catCount, panelText0: panelText0.slice(0, 200) });
check('catalog entries expose the service evidence_level', /证据 E\d/.test(panelText0), { panelText0: panelText0.slice(0, 240) });
check('bind is DISABLED while no direction is chosen', await page.locator('#pd-ds-bind').isDisabled(), {});
check('the gate states why (human choice required first)',
  /绑定不可用：尚无人选定方向/.test(await page.locator('#pd-ds-gate').innerText())
  && /AI 候选不会自动成为选定方向/.test(await page.locator('#pd-ds-gate').innerText()),
  { gate: await page.locator('#pd-ds-gate').innerText() });

// ---- create + human-choose a direction (the W05 flow) ---------------------------
phase = 'choose-direction';
await page.locator('#pd-brief-title').fill('秋季品牌视觉');
await page.locator('#pd-brief-goals').fill('现代, 温暖');
await page.locator('#pd-brief-create').click();
await page.waitForFunction(() => /已保存并读回/.test(document.getElementById('pd-brief-status')?.textContent || ''),
  null, { timeout: 20000 });
await page.locator('#pd-dir-title').fill('方向甲');
await page.locator('#pd-dir-create').click();
await page.waitForFunction(() => /候选不会自动成为选定方向/.test(document.getElementById('pd-dir-status')?.textContent || ''),
  null, { timeout: 20000 });
await panel('方向（Direction）').locator('.list-item').filter({ hasText: '方向甲' }).locator('button.ghost-btn').click();
await page.waitForFunction(() => /选定人：/.test(document.body.innerText), null, { timeout: 20000 });

// ---- 3: the gate OPENS only after the human choice ------------------------------
phase = 'gate-open';
const gateText = await page.locator('#pd-ds-gate').innerText();
check('after the human choice, bind becomes available', !(await page.locator('#pd-ds-bind').isDisabled()), { gateText });
check('the gate names the chosen direction it will bind', /将绑定到已选定方向「方向甲」/.test(gateText), { gateText });

// ---- 4: bind, then read it back and check consistency ---------------------------
phase = 'bind';
const chosenName = await page.locator('#pd-ds-name').inputValue();
await page.locator('#pd-ds-bind').click();
await page.waitForFunction(() => /设计系统已绑定：/.test(document.getElementById('pd-ds-status')?.textContent || ''),
  null, { timeout: 20000 });
await page.waitForFunction(() => /一致：活动绑定所属方向/.test(document.body.innerText), null, { timeout: 20000 }).catch(() => {});
const panelText1 = await dsPanel().innerText();
check('the binding is read back and names the bound design system',
  panelText1.includes(chosenName) && /已绑定/.test(panelText1), { chosenName, panelText1: panelText1.slice(0, 300) });
check('the binding is CONSISTENT with the human-chosen direction',
  /一致：活动绑定所属方向就是人工选定的方向/.test(panelText1), { panelText1: panelText1.slice(0, 300) });
check('a binding is not presented as production/quality acceptance',
  /制作与质量验收仍未执行/.test(panelText1), {});
check('bindings count increased from a real readback', /绑定 [1-9]\d* 次/.test(panelText1), { panelText1: panelText1.slice(0, 160) });

// ---- 5: no fake token editor ---------------------------------------------------
phase = 'no-fake-editor';
check('the panel states the Token write gap instead of offering a fake editor',
  /Token 编辑\/预览\/版本 diff\/发布\/回滚在服务端尚不存在/.test(panelText1), { panelText1: panelText1.slice(0, 400) });
const tokenInputs = await dsPanel().locator('input[id*="token" i], button[id*="token" i]').count();
check('there is no token edit control in the panel', tokenInputs === 0, { tokenInputs });

phase = 'hygiene';
check('no console errors', consoleErrors.length === 0, { consoleErrors: consoleErrors.slice(0, 3) });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w06-designsystem-bind', project_id: pid, checks, console_errors: consoleErrors,
  resolved_binding_name: chosenName, measured_at: new Date().toISOString(),
}, null, 2), 'utf8');
for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W06 checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
