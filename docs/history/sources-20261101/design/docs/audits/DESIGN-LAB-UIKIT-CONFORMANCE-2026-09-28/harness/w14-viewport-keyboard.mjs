// SPDX-License-Identifier: MIT
// W14 first slice — real evidence for the acceptance clause
// "无阻断级溢出/遮挡/键盘陷阱" (no blocking overflow / occlusion / keyboard trap)
// across the viewport x zoom matrix the task pack names.
//
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
const R = {
  '/workbench/style.css': [join(WB, 'style.css'), 'text/css; charset=utf-8'],
  '/workbench/main.js': [join(WB, 'build', 'main.js'), 'text/javascript; charset=utf-8'],
};
const server = createServer((req, res) => {
  const p = req.url.split('?')[0];
  res.setHeader('Content-Security-Policy', CSP);
  const h = R[p];
  if (h) { res.setHeader('Content-Type', h[1]); res.end(readFileSync(h[0])); return; }
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
const profile = join(outDir, 'chrome-profile-w14');
mkdirSync(profile, { recursive: true });
const ctx = await chromium.launchPersistentContext(profile, { executablePath: CHROME, headless: true });

const GEOM = () => {
  const de = document.documentElement;
  const q = (s) => document.querySelector(s);
  const rect = (s) => { const e = q(s); if (!e) return null; const r = e.getBoundingClientRect(); return { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) }; };
  // blocking overflow: elements wider than the viewport that are NOT inside a
  // scroll container AND are NOT a closed overlay. B10's overlays are designed
  // to sit off-screen when closed (.drawer{right:-540px} + .drawer.open{right:0}),
  // so a closed overlay is not an overflow at all -- counting it would be a
  // false positive. Elements inside a closed overlay are skipped; the open
  // state is asserted separately below.
  const closedOverlay = (e) => {
    for (let n = e; n && n !== document.body; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.position === 'fixed') {
        const cls = (n.className || '').toString();
        const isOverlay = /(^|\s)(overlay|drawer|palette|toast|modal)(\s|$)/.test(cls);
        const open = n.classList.contains('open') || n.classList.contains('show');
        if (isOverlay && !open) return true;
      }
    }
    return false;
  };
  const offenders = [];
  for (const e of document.querySelectorAll('body *')) {
    const r = e.getBoundingClientRect();
    if (r.width === 0) continue;
    if (r.right > de.clientWidth + 1) {
      if (closedOverlay(e)) continue;
      let scrollable = false;
      for (let p = e.parentElement; p; p = p.parentElement) {
        const ov = getComputedStyle(p).overflowX;
        if (ov === 'auto' || ov === 'scroll') { scrollable = true; break; }
        if (p === document.body) break;
      }
      if (!scrollable) offenders.push(`${e.tagName.toLowerCase()}.${(e.className || '').toString().split(' ')[0]} right=${r.right.toFixed(0)}`);
    }
  }
  return {
    viewport: { w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio },
    docScrollWidth: de.scrollWidth, docClientWidth: de.clientWidth,
    horizontalOverflow: de.scrollWidth > de.clientWidth + 1,
    offenders: offenders.slice(0, 8),
    sidebar: rect('.sidebar'), topbar: rect('.topbar'), content: rect('.content'),
    app: rect('.app'),
    sidebarVisible: q('.sidebar') ? getComputedStyle(q('.sidebar')).display !== 'none' : false,
    topbarVisible: q('.topbar') ? getComputedStyle(q('.topbar')).display !== 'none' : false,
    // occlusion: does the topbar sit above the content's top edge?
    contentBelowTopbar: (() => {
      const t = rect('.topbar'), c = rect('.content');
      return t && c ? c.y >= t.y + t.h - 1 : null;
    })(),
  };
};

const VP = [
  [2560, 1440, 1], [2560, 1440, 1.5],
  [1920, 1080, 1], [1920, 1080, 1.25], [1920, 1080, 1.5], [1920, 1080, 2],
  [1366, 768, 1],
];
const results = [];
for (const [w, h, dpr] of VP) {
  await ctx.close();
  const c2 = await chromium.launchPersistentContext(profile, {
    executablePath: CHROME, headless: true,
    viewport: { width: w, height: h }, deviceScaleFactor: dpr,
  });
  const page = c2.pages()[0] || await c2.newPage();
  await page.goto(base + '/workbench?dev=1#/dashboard', { waitUntil: 'load' });
  await page.waitForTimeout(1500);
  const g = await page.evaluate(GEOM);

  // keyboard reachability: Tab must reach the sidebar nav and the topbar actions
  const reached = new Set();
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press('Tab');
    const id = await page.evaluate(() => {
      const a = document.activeElement;
      if (!a) return null;
      if (a.closest('.nav')) return 'nav';
      if (a.closest('.topbar')) return 'topbar';
      if (a.closest('.content')) return 'content';
      if (a.closest('.sidebar')) return 'sidebar-other';
      return a.tagName.toLowerCase();
    });
    if (id) reached.add(id);
  }
  g.keyboardReachable = [...reached].sort();

  // the OPEN drawer must be fully visible: this is the meaningful counterpart to
  // skipping closed overlays above. The drawer animates
  // (transition:right .28s), so the measurement must happen AFTER the transition
  // settles -- measuring immediately reads the start of the animation and
  // falsely reports the closed position.
  await page.evaluate(() => {
    const d = document.querySelector('aside.drawer') || document.querySelector('.drawer');
    if (d) d.classList.add('open');
  });
  await page.waitForTimeout(600);
  g.drawerOpen = await page.evaluate(() => {
    const d = document.querySelector('aside.drawer') || document.querySelector('.drawer');
    if (!d) return null;
    const r = d.getBoundingClientRect();
    const ok = r.right <= window.innerWidth + 1 && r.left >= -1 && r.width > 0;
    return { x: +r.x.toFixed(1), right: +r.right.toFixed(1), w: +r.width.toFixed(1),
             viewport: window.innerWidth, rightCss: getComputedStyle(d).right, fitsWhenOpen: ok };
  });

  results.push({ w, h, dpr, ...g });
  console.log(`\n===== ${w}x${h} @${dpr}x =====`);
  console.log(`  doc scrollWidth/clientWidth : ${g.docScrollWidth}/${g.docClientWidth}  overflow=${g.horizontalOverflow}`);
  console.log(`  offenders(blocking)         : ${g.offenders.length ? g.offenders.join(' | ') : '(none)'}`);
  console.log(`  sidebar                     : ${JSON.stringify(g.sidebar)} visible=${g.sidebarVisible}`);
  console.log(`  topbar                      : ${JSON.stringify(g.topbar)} visible=${g.topbarVisible}`);
  console.log(`  content below topbar        : ${g.contentBelowTopbar}`);
  console.log(`  keyboard reached            : ${g.keyboardReachable.join(', ')}`);
  console.log(`  drawer OPEN fits viewport   : ${JSON.stringify(g.drawerOpen)}`);
  await c2.close();
}

const checks = {
  'no horizontal document overflow anywhere': results.every((r) => !r.horizontalOverflow),
  'no blocking (non-scrollable, non-closed-overlay) overflow': results.every((r) => r.offenders.length === 0),
  'open drawer fits inside the viewport': results.every((r) => r.drawerOpen?.fitsWhenOpen === true),
  'sidebar visible at every desktop viewport': results.every((r) => r.sidebarVisible),
  'sidebar width 280px (B10 grid column)': results.every((r) => Math.abs((r.sidebar?.w ?? 0) - 280) <= 1),
  'topbar visible and 78px (B10)': results.every((r) => r.topbarVisible && Math.abs((r.topbar?.h ?? 0) - 78) <= 1),
  'content starts below the topbar (no occlusion)': results.every((r) => r.contentBelowTopbar === true),
  'keyboard reaches .nav': results.every((r) => r.keyboardReachable.includes('nav')),
  'keyboard reaches .topbar': results.every((r) => r.keyboardReachable.includes('topbar')),
};
console.log('\n' + '='.repeat(64));
console.log('CHECKS (W14: overflow / occlusion / keyboard)');
for (const [k, v] of Object.entries(checks)) console.log(`  ${v ? 'PASS' : '**FAIL**'}  ${k}`);
const allOk = Object.values(checks).every(Boolean);
console.log(`\nRESULT: ${allOk ? 'PASS' : 'FAIL'}`);
writeFileSync(join(outDir, 'W14-VIEWPORT-KEYBOARD.json'),
  JSON.stringify({ results, checks, allOk }, null, 2), 'utf-8');
server.close();
process.exit(allOk ? 0 : 1);
