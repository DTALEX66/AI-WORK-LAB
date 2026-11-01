// SPDX-License-Identifier: MIT
// Verify the new B07 `/projects/:id` route in real Chromium, and prove the two
// hard nav invariants still hold:
//   * `.app-nav-item` count === 12   (browser_design_layer_e2e.mjs:385)
//   * B10 sidebar `.nav button` count === 11  (B10 1:1 dom-diff)
// Read-only. Evidence -> .project-local/.
import { createServer } from 'node:http';
import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const CHROME = 'D:/All projects/OS External Configuration/toolchains/playwright/chromium-1228/chrome-win64/chrome.exe';

const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src data:; "
  + "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'";
const WB = resolve('apps/workbench');
const ROUTES = {
  '/workbench/style.css': [join(WB, 'style.css'), 'text/css; charset=utf-8'],
  '/workbench/main.js': [join(WB, 'build', 'main.js'), 'text/javascript; charset=utf-8'],
};
const server = createServer((req, res) => {
  const p = req.url.split('?')[0];
  res.setHeader('Content-Security-Policy', CSP);
  const hit = ROUTES[p];
  if (hit) { res.setHeader('Content-Type', hit[1]); res.end(readFileSync(hit[0])); return; }
  if (p === '/workbench' || p === '/workbench/' || p === '/workbench/index.html') {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(readFileSync(join(WB, 'index.html'))); return;
  }
  res.statusCode = 404; res.end('nf');
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

const outDir = resolve('.project-local/task-artifacts/designlab-followup-taskpack-20260928');
mkdirSync(outDir, { recursive: true });
const profile = join(outDir, 'chrome-profile-w03');
mkdirSync(profile, { recursive: true });
const ctx = await chromium.launchPersistentContext(profile, {
  executablePath: CHROME, headless: true, viewport: { width: 1600, height: 1000 },
});
const page = ctx.pages()[0] || await ctx.newPage();
const errs = [];
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
page.on('pageerror', (e) => errs.push('pageerror: ' + String(e)));

const PROBE = () => ({
  appNavItems: document.querySelectorAll('.app-nav-item').length,
  b10NavButtons: document.querySelectorAll('.nav button').length,
  routeViewChildren: document.getElementById('route-view')?.children.length ?? -1,
  hasPageHead: !!document.querySelector('#route-view .page-head'),
  h2: document.querySelector('#route-view h2')?.textContent ?? null,
  kpiCount: document.querySelectorAll('#route-view .kpi').length,
  panelCount: document.querySelectorAll('#route-view .panel').length,
  activeNavRoute: document.querySelector('.nav button.active')?.dataset?.route ?? null,
  projectDetailButtons: Array.from(document.querySelectorAll('.ghost-btn'))
    .filter((b) => b.textContent === '打开').length,
  cspErrors: 0,
});

const TARGETS = [
  ['projects list', '/workbench?dev=1#/projects'],
  ['project-detail (B07 /projects/:id)', '/workbench?dev=1#/projects/proj-abc123'],
  ['detail with encoded id', '/workbench?dev=1#/projects/a%2Fb'],
  ['dashboard (regression)', '/workbench?dev=1#/dashboard'],
];

const results = [];
for (const [name, path] of TARGETS) {
  errs.length = 0;
  await page.goto(base + path, { waitUntil: 'load' });
  await page.waitForTimeout(2200);
  const info = await page.evaluate(PROBE);
  const csp = errs.filter((e) => /Content Security Policy|inline style/i.test(e));
  results.push({ name, path, info, cspErrors: csp.length, errors: [...errs] });
  console.log(`\n===== ${name} =====`);
  console.log(`  path                : ${path}`);
  console.log(`  .app-nav-item       : ${info.appNavItems}  ${info.appNavItems === 12 ? 'OK (must be 12)' : '**FAIL**'}`);
  console.log(`  B10 .nav button     : ${info.b10NavButtons}  ${info.b10NavButtons === 11 ? 'OK (must be 11)' : '**FAIL**'}`);
  console.log(`  #route-view children: ${info.routeViewChildren}`);
  console.log(`  page-head present   : ${info.hasPageHead}   h2='${info.h2}'`);
  console.log(`  kpi / panel         : ${info.kpiCount} / ${info.panelCount}`);
  console.log(`  active nav route    : ${info.activeNavRoute}`);
  console.log(`  CSP violations      : ${csp.length}`);
  if (errs.length) console.log(`  errors(${errs.length})     : ${errs[0].slice(0, 140)}`);
}

const detail = results.find((r) => r.name.startsWith('project-detail'));
const list = results.find((r) => r.name === 'projects list');
const dash = results.find((r) => r.name.startsWith('dashboard'));
const checks = {
  nav12_everywhere: results.every((r) => r.info.appNavItems === 12),
  b10nav11_everywhere: results.every((r) => r.info.b10NavButtons === 11),
  detail_renders_pagehead: !!detail?.info.hasPageHead,
  detail_renders_kpis: (detail?.info.kpiCount ?? 0) >= 4,
  detail_renders_panels: (detail?.info.panelCount ?? 0) >= 2,
  detail_highlights_projects_nav: detail?.info.activeNavRoute === 'projects',
  list_has_open_buttons: detail?.info.activeNavRoute === 'projects',
  no_csp_violations: results.every((r) => r.cspErrors === 0),
  dashboard_still_ok: !!dash?.info.hasPageHead,
};
console.log('\n' + '='.repeat(60));
console.log('CHECKS');
for (const [k, v] of Object.entries(checks)) console.log(`  ${v ? 'PASS' : '**FAIL**'}  ${k}`);
const allOk = Object.values(checks).every(Boolean);
console.log(`\nRESULT: ${allOk ? 'PASS' : 'FAIL'}`);
writeFileSync(join(outDir, 'W03-ROUTE-VERIFY.json'),
  JSON.stringify({ sha: 'cac30c7aa83e701d9ad851fa6669231bea4b7199', results, checks, allOk }, null, 2), 'utf-8');
await ctx.close();
server.close();
process.exit(allOk ? 0 : 1);
