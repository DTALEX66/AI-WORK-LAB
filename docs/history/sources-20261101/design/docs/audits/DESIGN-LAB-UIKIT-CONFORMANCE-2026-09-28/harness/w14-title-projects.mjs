// SPDX-License-Identifier: MIT
// Pack §103: "中文长标题截断有全称入口" -- third surface: the PROJECTS LIST table.
// Driven by w03-brief-editor-verify.py (shared runner; W03_NODE_SCRIPT/W03_OUT).
//
// Kept as a SEPARATE file on purpose: the previous two attempts edited the already-verified
// w14-title-entry.mjs harness with string surgery and broke its syntax, so the run died
// before writing evidence and the change had to be reverted twice. A new file cannot damage
// a verified harness.
//
// Two hard rules learned the hard way, applied here:
//   · assert on the whole table (count) and dump its text -- never .evaluate() a possibly
//     empty row locator, which waits 30 s and throws before the evidence file is written;
//   · the project name used here is long AND CJK-ish in length so truncation must trigger.
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

const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + String(e)));

// A long CJK project name, so truncation must actually trigger (TITLE_MAX is 18).
const name = '跨渠道一致性交付规范与秋季品牌视觉系统重构';

await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });

await page.evaluate(() => { window.location.hash = '#/projects'; });
await page.waitForTimeout(2000);

const tableText = String(await page.locator('table.table').innerText().catch(() => 'n/a'));
const expanders = await page.locator('table.table .title-expand').count();
check('projects table renders the created project', tableText.includes(name.slice(0, 10)), { tableText: tableText.slice(0, 300) });
check('projects-list name gets the full-text entry point', expanders >= 1, { expanders, tableText: tableText.slice(0, 300) });

// The control must actually work (a rendered button that does nothing would still pass a
// count-only assertion), and the truncated cell must keep the full text for pointer users.
if (expanders >= 1) {
  const cell = page.locator('table.table .title-cell').first();
  const strong = cell.locator('strong.title-text').first();
  const before = await strong.innerText().catch(() => 'n/a');
  const titleAttr = await strong.getAttribute('title').catch(() => null);
  check('the projects-list heading is truncated in place', typeof before === 'string' && before.endsWith('…'), { before });
  check('it keeps the full name in title=', titleAttr === name, { titleAttr });
  const btn = cell.locator('.title-expand').first();
  check('the control carries aria-expanded=false', (await btn.getAttribute('aria-expanded')) === 'false', {});
  await btn.click();
  await page.waitForTimeout(200);
  check('clicking it reveals the full project name', (await strong.innerText()) === name, { now: await strong.innerText() });
  check('aria-expanded flips to true', (await btn.getAttribute('aria-expanded')) === 'true', {});
  await page.keyboard.press('Tab');
  await btn.focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(200);
  check('Enter on the focused control collapses it again (keyboard-operable)', (await strong.innerText()).endsWith('…'), { now: await strong.innerText() });
} else {
  check('SKIPPED: no control rendered, see tableText', false, { tableText: tableText.slice(0, 300) });
}

check('no console errors', consoleErrors.length === 0, { consoleErrors: consoleErrors.slice(0, 3) });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w14-title-projects', project_name: name, checks, console_errors: consoleErrors,
  measured_at: new Date().toISOString(),
}, null, 2), 'utf8');
for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W14-projects-title checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
