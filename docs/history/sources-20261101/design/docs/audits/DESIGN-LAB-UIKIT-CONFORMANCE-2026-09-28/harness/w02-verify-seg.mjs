// SPDX-License-Identifier: MIT
// Verify the unscoped `.seg` primitive: (a) standalone works with B07's four
// declared states, (b) `.toolbar .seg` appearance is byte-identical (no regression).
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
const profile = join(outDir, 'chrome-profile-seg');
mkdirSync(profile, { recursive: true });
const ctx = await chromium.launchPersistentContext(profile, { executablePath: CHROME, headless: true, viewport: { width: 1600, height: 1000 } });
const page = ctx.pages()[0] || await ctx.newPage();
await page.goto(base + '/workbench?dev=1#/dashboard', { waitUntil: 'load' });
await page.waitForTimeout(2200);

// inject BOTH a standalone .seg and a .toolbar .seg, plus a disabled member.
// The probe MUST live inside the visible `.content` region: appended to <body>
// it lands below the `.app` block, off-screen, where the mouse can never reach it
// (that produced two false failures: an unreachable hover and an unreadable focus
// state). Placing it in `.content` also keeps it a real descendant of `.app`, so
// the selectors under test are exercised in their actual context.
await page.evaluate(() => {
  const h = document.createElement('div');
  h.id = '__seg';
  h.innerHTML =
    '<div class="seg" id="s1"><button id="s1a" class="active">A</button><button id="s1b">B</button><button id="s1c" disabled>C</button></div>'
    + '<div class="toolbar" id="t1"><div class="seg" id="s2"><button id="s2a" class="active">A</button><button id="s2b">B</button></div></div>';
  document.querySelector('.content').appendChild(h);
  h.scrollIntoView({ block: 'center' });
});
await page.waitForTimeout(300);
const cs = (id) => page.evaluate((i) => {
  const e = document.getElementById(i);
  const c = getComputedStyle(e);
  return { display: c.display, gap: c.gap, flexWrap: c.flexWrap,
           bg: c.backgroundColor, bgImage: c.backgroundImage.slice(0, 30),
           border: c.borderTopColor, borderWidth: c.borderTopWidth,
           radius: c.borderRadius, padding: c.padding,
           opacity: c.opacity, cursor: c.cursor, transition: c.transitionDuration,
           color: c.color, transform: c.transform,
           outlineWidth: c.outlineWidth, outlineStyle: c.outlineStyle,
           outlineOffset: c.outlineOffset, outlineColor: c.outlineColor };
}, id);

const standalone = { wrap: await cs('s1'), active: await cs('s1a'), normal: await cs('s1b'), disabled: await cs('s1c') };
const inToolbar = { wrap: await cs('s2'), active: await cs('s2a'), normal: await cs('s2b') };
console.log('=== standalone .seg (new) ===');
for (const [k, v] of Object.entries(standalone)) console.log(`  ${k.padEnd(9)} display=${v.display} bg=${v.bg} radius=${v.radius} opacity=${v.opacity} transition=${v.transition}`);
console.log('=== .toolbar .seg (must be unchanged) ===');
for (const [k, v] of Object.entries(inToolbar)) console.log(`  ${k.padEnd(9)} display=${v.display} bg=${v.bg} radius=${v.radius} transition=${v.transition}`);

// B10's original .toolbar rules, read verbatim from the kit source, declare a FIXED
// property set -- and `.seg` copies those literals exactly. So the invariant to prove
// is not "4 sampled properties match" but: on every computed property B10's rules can
// reach, `.toolbar .seg*` is IDENTICAL to the same member rendered unscoped, and the
// ONLY permitted difference is `transition` (which B10's toolbar rule never declares,
// hence the explicit restoration). Any other divergence is a real leak.
const KEYS = Object.keys(inToolbar.wrap);
const diffBag = (a, b, keys = KEYS) => keys.filter((k) => a[k] !== b[k]);
const wrapDiff = diffBag(standalone.wrap, inToolbar.wrap);
const normalDiff = diffBag(standalone.normal, inToolbar.normal);
const activeDiff = diffBag(standalone.active, inToolbar.active);
const fmt = (d) => (d.length ? d.join(', ') : '(none)');
console.log('=== leak scan: unscoped .seg vs .toolbar .seg, property-by-property ===');
console.log(`  wrap   props=${KEYS.length} differing=${wrapDiff.length} -> ${fmt(wrapDiff)}`);
console.log(`  normal props=${KEYS.length} differing=${normalDiff.length} -> ${fmt(normalDiff)}`);
console.log(`  active props=${KEYS.length} differing=${activeDiff.length} -> ${fmt(activeDiff)}`);

// hover + focus on the standalone member
await page.mouse.move(2, 2); await page.waitForTimeout(200);
const b = await page.locator('#s1b').boundingBox();
await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
await page.waitForTimeout(300);
const hovered = await cs('s1b');
// HARNESS NOTE (3rd occurrence of the same bug class): `.seg button` declares
// `transition:all 120ms`, which includes outline-width and outline-offset. Reading
// getComputedStyle in the SAME task as focus() returns the transition START state --
// pre-focus outline-width is the initial `medium` (3px) and outline-offset 0px, so it
// read "3px solid offset=0px" and looked like the legacy `button:focus-visible` rule
// had won. It had not: the style was mid-interpolation. Focus first, settle, then read.
const focusState = await page.evaluate(() => {
  const e = document.getElementById('s1b');
  e.focus({ focusVisible: true });
  return { fv: e.matches(':focus-visible') };
});
await page.waitForTimeout(400); // > the 120ms hover/focus transition
const focused = await page.evaluate((fv) => {
  const e = document.getElementById('s1b');
  const c = getComputedStyle(e);
  return { fv, settledFv: e.matches(':focus-visible'),
           outlineWidth: c.outlineWidth, outlineStyle: c.outlineStyle,
           outlineOffset: c.outlineOffset, outlineColor: c.outlineColor,
           // decisive: which rule won? primary #316CFF = rgb(49,108,255)
           // vs legacy secondary #4BAFFF = rgb(75,175,255)
           wonByPrimary: c.outlineColor === 'rgb(49, 108, 255)',
           wonBySecondary: c.outlineColor === 'rgb(75, 175, 255)',
           matchedRulesHint: { tag: e.tagName, cls: e.className, inSeg: !!e.closest('.seg') } };
}, focusState.fv);
console.log('=== states on the standalone member ===');
console.log(`  hover  bg=${hovered.bg} border=${hovered.border}`);
console.log(`  focus  :focus-visible=${focused.fv}(settled=${focused.settledFv}) outline=${focused.outlineWidth} ${focused.outlineStyle} offset=${focused.outlineOffset} color=${focused.outlineColor} primary=${focused.wonByPrimary} secondary=${focused.wonBySecondary}`);

const checks = {
  'standalone .seg is display:flex': standalone.wrap.display === 'flex',
  'standalone .seg button keeps B10 base look (radius 12px)': standalone.normal.radius === '12px',
  'standalone .active gets the B10 gradient': /gradient/.test(standalone.active.bgImage),
  'standalone :disabled honoured (opacity .45, not-allowed)':
    standalone.disabled.opacity === '0.45' && standalone.disabled.cursor === 'not-allowed',
  'B07 Hover 120ms applied': standalone.normal.transition === '0.12s',
  'B07 Focus 2px ring + 2px offset': focused.fv && focused.outlineWidth === '2px' && focused.outlineOffset === '2px',
  'hover changes the border (interactive)': hovered.border !== standalone.normal.border,
  // B10 kit literals for .toolbar .seg* (read from B10/index.html:285-297)
  '.toolbar .seg keeps B10 display:flex/gap:8px/wrap': inToolbar.wrap.display === 'flex' && inToolbar.wrap.gap === '8px' && inToolbar.wrap.flexWrap === 'wrap',
  '.toolbar .seg wrap has ZERO property leak (all props equal)': wrapDiff.length === 0,
  '.toolbar .seg button leaks ONLY transition (B10 never declares it)': normalDiff.length === 1 && normalDiff[0] === 'transition',
  '.toolbar .seg button.active leaks ONLY transition': activeDiff.length === 1 && activeDiff[0] === 'transition',
  '.toolbar .seg button keeps B10 padding 10px 12px': inToolbar.normal.padding === '10px 12px',
  '.toolbar .seg button keeps B10 border 1px': inToolbar.normal.borderWidth === '1px',
  // NOTE: color-mix() results serialize as `color(srgb ...)`, not rgb()/rgba().
  // An earlier literal `rgba(0, 0, 0, 0)` here was a MISREAD of the wrap row in the
  // dump above and produced a false FAIL; assert identity instead of a guessed literal.
  '.toolbar .seg button keeps B10 background (no accent fill)':
    inToolbar.normal.bg === standalone.normal.bg && inToolbar.normal.bg !== 'rgb(49, 108, 255)',
  '.toolbar .seg still display:flex': inToolbar.wrap.display === 'flex',
  '.toolbar .seg wrap transition untouched (none)': inToolbar.wrap.transition === '0s',
  '.toolbar .seg button transition untouched (none)': inToolbar.normal.transition === '0s',
  '.toolbar .seg .active still gradient': /gradient/.test(inToolbar.active.bgImage),
  '.toolbar .seg button radius untouched': inToolbar.normal.radius === '12px',
};
console.log('\n' + '='.repeat(66));
for (const [k, v] of Object.entries(checks)) console.log(`  ${v ? 'PASS' : '**FAIL**'}  ${k}`);
const allOk = Object.values(checks).every(Boolean);
console.log(`\nRESULT: ${allOk ? 'PASS' : 'FAIL'}`);
writeFileSync(join(outDir, 'W02-SEG-VERIFY.json'), JSON.stringify({ standalone, inToolbar, hovered, focused, checks, allOk }, null, 2), 'utf-8');
await ctx.close();
server.close();
process.exit(allOk ? 0 : 1);
