// SPDX-License-Identifier: MIT
// Verify a suspected real defect: the legacy `button:hover{background:var(--accent-hover)}`
// rule is unscoped, and B10's `.ghost-btn:hover` does not declare `background`,
// so ghost buttons may turn blue on hover -- a deviation from B10.
// Measure the real computed background before and during hover.
import { createServer } from 'node:http';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const CHROME = 'D:/All projects/OS External Configuration/toolchains/playwright/chromium-1228/chrome-win64/chrome.exe';
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'";
const WB = resolve('apps/workbench');
const R = {
  '/workbench/style.css': [join(WB, 'style.css'), 'text/css; charset=utf-8'],
  '/workbench/main.js': [join(WB, 'build', 'main.js'), 'text/javascript; charset=utf-8'],
};
const server = createServer((req, res) => {
  const p = req.url.split('?')[0];
  res.setHeader('Content-Security-Policy', CSP);
  const h = R[p];
  if (h) { res.setHeader('Content-Type', h[1]); res.end(readFileSync(h[0])); return; }
  if (p.startsWith('/workbench')) { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(readFileSync(join(WB, 'index.html'))); return; }
  res.statusCode = 404; res.end('nf');
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;
const outDir = resolve('.project-local/task-artifacts/designlab-followup-taskpack-20260928');
mkdirSync(outDir, { recursive: true });
const profile = join(outDir, 'chrome-profile-hover');
mkdirSync(profile, { recursive: true });
const ctx = await chromium.launchPersistentContext(profile, { executablePath: CHROME, headless: true, viewport: { width: 1600, height: 1000 } });
const page = ctx.pages()[0] || await ctx.newPage();
await page.goto(base + '/workbench?dev=1#/dashboard', { waitUntil: 'load' });
await page.waitForTimeout(2000);

const read = (sel) => page.evaluate((s) => {
  const e = document.querySelector(s);
  if (!e) return null;
  const c = getComputedStyle(e);
  return { bg: c.backgroundColor, bgImage: c.backgroundImage.slice(0, 40), color: c.color, transform: c.transform };
}, sel);

const targets = [
  ['topbar 通知 (.ghost-btn)', '#topNotice'],
  ['dashboard 导出周报 (.ghost-btn)', '#route-view .page-actions .ghost-btn'],
  ['dashboard + 新建项目 (.primary-btn)', '#route-view .page-actions .primary-btn'],
];
const out = [];
for (const [name, sel] of targets) {
  await page.mouse.move(5, 5);           // move away first
  await page.waitForTimeout(250);
  const before = await read(sel);
  const box = await page.locator(sel).first().boundingBox();
  if (!box) { out.push({ name, sel, before, hover: null, note: 'not found' }); continue; }
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(400);        // let the transition settle
  const during = await read(sel);
  out.push({ name, sel, before, hover: during });
  console.log(`\n===== ${name} =====`);
  console.log(`  before hover : bg=${before?.bg}  transform=${before?.transform}`);
  console.log(`  during hover : bg=${during?.bg}  transform=${during?.transform}`);
}

const btn = out.find((o) => o.name.includes('通知'));
const blueish = (c) => c && (c === 'rgb(37, 88, 219)' || /^rgb\((2[0-9]|3[0-9]|4[0-9]|5[0-9]),/.test(c));
const verdict = {
  ghost_hover_background_is_legacy_accent: blueish(btn?.hover?.bg),
  ghost_rest_background: btn?.before?.bg ?? null,
  note: 'legacy --accent-hover is #2558DB = rgb(37,88,219); B10 .ghost-btn has no background on :hover',
};
console.log('\n' + '='.repeat(60));
console.log('VERDICT');
for (const [k, v] of Object.entries(verdict)) console.log(`  ${k}: ${v}`);
writeFileSync(join(outDir, 'W02-GHOST-HOVER-PROBE.json'), JSON.stringify({ out, verdict }, null, 2), 'utf-8');
await ctx.close();
server.close();
