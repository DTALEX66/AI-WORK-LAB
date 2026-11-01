// SPDX-License-Identifier: MIT
// Verify B07's shared-ui-core utility contract by COMPUTED STYLE in real
// Chromium at three viewport widths -- not by grepping the CSS text.
// Read-only. Evidence -> .project-local/.
import { createServer } from 'node:http';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const CHROME = 'D:/All projects/OS External Configuration/toolchains/playwright/chromium-1228/chrome-win64/chrome.exe';
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'";
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
  if (p.startsWith('/workbench')) {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(readFileSync(join(WB, 'index.html'))); return;
  }
  res.statusCode = 404; res.end('nf');
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

const outDir = resolve('.project-local/task-artifacts/designlab-followup-taskpack-20260928');
mkdirSync(outDir, { recursive: true });
const profile = join(outDir, 'chrome-profile-w02util');
mkdirSync(profile, { recursive: true });
const ctx = await chromium.launchPersistentContext(profile, { executablePath: CHROME, headless: true, viewport: { width: 1600, height: 1000 } });
const page = ctx.pages()[0] || await ctx.newPage();
const cspErrs = [];
page.on('console', (m) => { if (m.type() === 'error' && /Content Security Policy|inline style/i.test(m.text())) cspErrs.push(m.text()); });

const PROBE = () => {
  let host = document.getElementById('__util_probe');
  if (!host) {
    host = document.createElement('div');
    host.id = '__util_probe';
    host.innerHTML = '<div class="responsive-grid" id="rg"><i></i><i></i><i></i></div>'
      + '<div class="desktop-only" id="do">d</div>'
      + '<button class="focus-ring" id="fr">f</button>'
      + '<button class="pressable" id="pr">p</button>'
      + '<div class="ui-motion-fast" id="mf">m</div>'
      + '<div class="ui-motion-slow" id="ms">m</div>';
    document.body.appendChild(host);
  }
  const cs = (id) => getComputedStyle(document.getElementById(id));
  const rg = cs('rg');
  return {
    viewport: window.innerWidth,
    responsiveGrid: { display: rg.display, columns: rg.gridTemplateColumns, gap: rg.gap },
    desktopOnlyDisplay: cs('do').display,
    focusRing: { outlineWidth: cs('fr').outlineWidth, outlineStyle: cs('fr').outlineStyle, outlineOffset: cs('fr').outlineOffset, outlineColor: cs('fr').outlineColor },
    motionFast: cs('mf').transitionDuration,
    motionSlow: cs('ms').transitionDuration,
    pressableTransform: cs('pr').transform,
  };
};

const results = [];
for (const w of [1600, 1000, 600]) {
  await page.setViewportSize({ width: w, height: 1000 });
  await page.goto(base + '/workbench?dev=1#/dashboard', { waitUntil: 'load' });
  await page.waitForTimeout(1800);
  const r = await page.evaluate(PROBE);

  // :focus-visible and :active are PSEUDO-CLASSES: an unfocused / unpressed
  // element legitimately reports the initial value (outline "3px none",
  // transform "none"). They must be probed by actually focusing and pressing.
  r.focusRing = await page.evaluate(() => {
    const b = document.getElementById('fr');
    b.focus({ focusVisible: true });
    const c = getComputedStyle(b);
    return {
      matchesFocusVisible: b.matches(':focus-visible'),
      outlineWidth: c.outlineWidth, outlineStyle: c.outlineStyle,
      outlineOffset: c.outlineOffset, outlineColor: c.outlineColor,
    };
  });
  const box = await page.locator('#pr').boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  r.pressable = await page.evaluate(() => {
    const c = getComputedStyle(document.getElementById('pr'));
    return { matchesActive: document.getElementById('pr').matches(':active'), transform: c.transform };
  });
  await page.mouse.up();

  results.push(r);
  console.log(`\n===== viewport ${w} =====`);
  console.log(`  .responsive-grid   display=${r.responsiveGrid.display}  cols=${r.responsiveGrid.columns.split(' ').length}  gap=${r.responsiveGrid.gap}`);
  console.log(`  .desktop-only      display=${r.desktopOnlyDisplay}`);
  console.log(`  .focus-ring        focus-visible=${r.focusRing.matchesFocusVisible}  outline=${r.focusRing.outlineWidth} ${r.focusRing.outlineStyle} offset=${r.focusRing.outlineOffset}`);
  console.log(`  .pressable         active=${r.pressable.matchesActive}  transform=${r.pressable.transform}`);
  console.log(`  .ui-motion-fast    transition-duration=${r.motionFast}`);
  console.log(`  .ui-motion-slow    transition-duration=${r.motionSlow}`);
}

const [w1600, w1000, w600] = results;
const cols = (r) => r.responsiveGrid.columns.split(' ').length;
const checks = {
  'responsive-grid is display:grid': results.every((r) => r.responsiveGrid.display === 'grid'),
  'responsive-grid gap = 16px (--space-4)': results.every((r) => r.responsiveGrid.gap === '16px'),
  'responsive-grid @1600 -> 12 cols (B07 >=1200)': cols(w1600) === 12,
  'responsive-grid @1000 -> 2 cols (B07 768-1199)': cols(w1000) === 2,
  'responsive-grid @600 -> 1 col (B07 <=767)': cols(w600) === 1,
  'desktop-only hidden <=767 (600)': w600.desktopOnlyDisplay === 'none',
  'desktop-only visible >767 (1600/1000)': w1600.desktopOnlyDisplay !== 'none' && w1000.desktopOnlyDisplay !== 'none',
  'focus-ring actually matches :focus-visible': results.every((r) => r.focusRing.matchesFocusVisible),
  'focus-ring outline 2px (B07 contract)': results.every((r) => r.focusRing.outlineWidth === '2px'),
  'focus-ring offset 2px (B07 contract)': results.every((r) => r.focusRing.outlineOffset === '2px'),
  'pressable actually matches :active': results.every((r) => r.pressable.matchesActive),
  'pressable scale(0.99) applied': results.every((r) => /matrix\(0\.99/.test(r.pressable.transform)),
  'ui-motion-fast = 0.12s (--motion-fast)': results.every((r) => r.motionFast === '0.12s'),
  'ui-motion-slow = 0.28s (--motion-slow)': results.every((r) => r.motionSlow === '0.28s'),
  'no CSP violations': cspErrs.length === 0,
};
console.log('\n' + '='.repeat(64));
console.log('CHECKS (computed style, not text grep)');
for (const [k, v] of Object.entries(checks)) console.log(`  ${v ? 'PASS' : '**FAIL**'}  ${k}`);
const allOk = Object.values(checks).every(Boolean);
console.log(`\nRESULT: ${allOk ? 'PASS' : 'FAIL'}`);
writeFileSync(join(outDir, 'W02-UTILITY-VERIFY.json'),
  JSON.stringify({ sha: '2190f5eeb43b1c16c6ffca77b0754edc786dd9ad', results, checks, allOk }, null, 2), 'utf-8');
await ctx.close();
server.close();
process.exit(allOk ? 0 : 1);
