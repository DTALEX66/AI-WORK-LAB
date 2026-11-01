// SPDX-License-Identifier: MIT
// Regression check for the button:hover scoping: the LEGACY page (login gate at
// /workbench with no dev bypass) must still get the legacy --accent-hover, while
// buttons inside the B10 `.app` must not.
import { createServer } from 'node:http';
import { readFileSync, mkdirSync } from 'node:fs';
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
const profile = join(outDir, 'chrome-profile-hoverreg');
mkdirSync(profile, { recursive: true });
const ctx = await chromium.launchPersistentContext(profile, { executablePath: CHROME, headless: true, viewport: { width: 1400, height: 900 } });
const page = ctx.pages()[0] || await ctx.newPage();

const read = (sel) => page.evaluate((s) => {
  const e = document.querySelector(s);
  if (!e) return null;
  const c = getComputedStyle(e);
  return { bg: c.backgroundColor, shadow: c.boxShadow.slice(0, 30) };
}, sel);

async function hoverProbe(url, sel, label) {
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForTimeout(2000);
  await page.mouse.move(2, 2);
  await page.waitForTimeout(250);
  const before = await read(sel);
  const box = await page.locator(sel).first().boundingBox();
  if (!box) { console.log(`  ${label}: selector not found`); return null; }
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(400);
  const during = await read(sel);
  console.log(`  ${label}\n    rest  bg=${before?.bg}  shadow=${before?.shadow}\n    hover bg=${during?.bg}  shadow=${during?.shadow}`);
  return { before, during };
}

console.log('=== LEGACY page (no dev bypass) — must STILL get --accent-hover (#2558DB) ===');
const legacy = await hoverProbe(base + '/workbench', '#login button', '#login 连接服务 button');

console.log('\n=== B10 shell — must NOT get --accent-hover ===');
const shell = await hoverProbe(base + '/workbench?dev=1#/dashboard', '#topNotice', 'topbar 通知 .ghost-btn');

const ACCENT = 'rgb(37, 88, 219)';
const checks = {
  'legacy button still gets --accent-hover on hover': legacy?.during?.bg === ACCENT,
  'B10 ghost-btn does NOT get --accent-hover on hover': shell?.during?.bg !== ACCENT,
  'B10 ghost-btn hover background preserved (tinted, not transparent)': /^color\(srgb/.test(shell?.during?.bg ?? ''),
};
console.log('\n' + '='.repeat(60));
for (const [k, v] of Object.entries(checks)) console.log(`  ${v ? 'PASS' : '**FAIL**'}  ${k}`);
const allOk = Object.values(checks).every(Boolean);
console.log(`\nRESULT: ${allOk ? 'PASS' : 'FAIL'}`);
await ctx.close();
server.close();
process.exit(allOk ? 0 : 1);
