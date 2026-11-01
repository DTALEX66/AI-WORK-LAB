// SPDX-License-Identifier: MIT
// Legacy-leak sweep: does any UNscoped, element-only legacy rule still reach into
// `.app` (the B10 shell), supplying styling B10 never specified?
//
// WHY THIS IS A MEASUREMENT, NOT A SPECIFICITY ARGUMENT
//   B10 styles everything by CLASS (specificity >= 0,1,0). A bare element rule can
//   therefore never beat a B10 rule -- it can only fill a property B10 leaves
//   undeclared. So the question is exactly "which properties does the legacy block
//   supply?", and that is measurable: DELETE the element-only rules through CSSOM and
//   diff every computed longhand before/after. No specificity math, no hand-written
//   property list (getComputedStyle's own index list is used).
//
// HARNESS CORRECTNESS (each of these was a real false result before being fixed)
//   1. `data-route`, not `href`: `.app-nav-item` is a <button>. Reading href gave
//      null x12, so URLs were `?dev=1null`, dev mode never engaged, and the whole
//      sweep silently measured the login screen (census h3:0 while the source
//      renders five h3s). Route discovery now fails LOUDLY instead.
//   2. Same-document navigation: a goto differing only in the hash does not reload,
//      so each route gets a unique query string to force a real document load.
//   3. SAME-TASK STALENESS (the big one): getComputedStyle read in the same task as
//      the CSSOM mutation returns the PRE-mutation value -- measured directly: the
//      rule list went 10 -> 8 and the deleted rules were gone, yet before/after for
//      the first button were byte-identical. The sweep therefore UNDERCOUNTED leaks.
//      Prepare (measure + mutate) and read are now separate tasks.
//   4. The positive control must not be vacuous: it asserts the insert took effect
//      across a task boundary, that the filter collected it, that the sheet really
//      lost it, AND that the diff reported it.
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
const ctx = await chromium.launchPersistentContext(join(outDir, 'chrome-profile-leaksweep'), { executablePath: CHROME, headless: true, viewport: { width: 1600, height: 1000 } });
const page = ctx.pages()[0] || await ctx.newPage();

const TAGS = 'h1,h2,h3,h4,p,label,input,select,textarea,button,a,ul,li';

// Shared in-page helpers, injected as one function body via these two entry points.
const HELPERS = `
  const part = /^[a-zA-Z][a-zA-Z0-9]*((::?[a-zA-Z-]+(\\([^)]*\\))?)*)$/;
  const BANNED = /^(html|body|\\*)$/;
  const isLegacy = (sel) => sel.split(',').every((s) => {
    const t = s.trim();
    if (!t || BANNED.test(t)) return false;
    return part.test(t.replace(/\\s+/g, ''));
  });
  const collect = () => {
    const out = [];
    for (const sh of [...document.styleSheets]) {
      let rules; try { rules = sh.cssRules; } catch { continue; }
      for (let i = 0; i < rules.length; i++) {
        if (rules[i].selectorText && isLegacy(rules[i].selectorText)) out.push({ sh, i, sel: rules[i].selectorText });
      }
    }
    return out;
  };
  const bag = (els) => els.map((el) => {
    const c = getComputedStyle(el);
    const o = {};
    for (let i = 0; i < c.length; i++) { const p = c[i]; o[p] = c.getPropertyValue(p); }
    return o;
  });
`;

// TASK 1: tag the subject, snapshot it, then delete the legacy rules.
// `root` selects the swept subtree: the B10 shell (`.app`) for the 12 routes, but the
// legacy login screen lives OUTSIDE `.app` on the default empty-hash workbench view
// (`login.hidden = showWorkbench ? connected : true`), so it needs its own root or it
// is never measured at all.
const PREP = new Function('args', `${HELPERS}
  // page.evaluate passes exactly ONE argument, so both inputs arrive as one object
  // (passing an array bound the array to 'control' and insertRule got "undefined,.app").
  const { control, rootSel } = args || {};
  const root = (rootSel && document.querySelector(rootSel)) || document.querySelector('.app') || document.body;
  if (!root) return { error: 'no sweep root' };
  if (control) {
    const sh = [...document.styleSheets].find((s) => (s.href || '').endsWith('style.css'))
      || [...document.styleSheets].find((s) => { try { return s.cssRules.length; } catch { return false; } });
    sh.insertRule(control, sh.cssRules.length);
  }
  const els = [...root.querySelectorAll('${TAGS}')];
  els.forEach((e, i) => e.setAttribute('data-sweep-idx', String(i)));
  const hits = collect();
  const before = bag(els);
  const bySheet = new Map();
  for (const h of hits) { if (!bySheet.has(h.sh)) bySheet.set(h.sh, []); bySheet.get(h.sh).push(h.i); }
  let deleted = 0, failed = 0;
  for (const [sh, idxs] of bySheet) {
    idxs.sort((a, b) => b - a);
    for (const i of idxs) { try { sh.deleteRule(i); deleted++; } catch { failed++; } }
  }
  const remaining = collect().length;
  return { n: els.length, before, deleted, failed, remaining,
           rootInsideApp: !!root.closest('.app'), rootSel: rootSel || '.app',
           legacyRules: hits.map((h) => h.sel),
           census: els.reduce((m, el) => { const t = el.tagName.toLowerCase(); m[t] = (m[t] || 0) + 1; return m; }, {}) };
`);

// TASK 2 (separate task => no same-task staleness): re-read the tagged subject.
const READ = new Function(`${HELPERS}
  const els = [...document.querySelectorAll('[data-sweep-idx]')];
  els.sort((a, b) => Number(a.getAttribute('data-sweep-idx')) - Number(b.getAttribute('data-sweep-idx')));
  return { n: els.length, after: bag(els), remaining: collect().length,
           ids: els.map((e) => (e.closest('.app') ? 'IN:' : 'OUT:')
             + e.tagName.toLowerCase()
             + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\\s+/).join('.') : '')
             + (e.parentElement && typeof e.parentElement.className === 'string' && e.parentElement.className
                ? '<' + e.parentElement.tagName.toLowerCase() + '.' + e.parentElement.className.trim().split(/\\s+/).join('.') : '')) };
`);

async function sweep(control, rootSel) {
  // Pass the function OBJECT: `page.evaluate((c) => PREP(c))` would serialize the
  // arrow function and PREP does not exist inside the page (ReferenceError).
  const pre = await page.evaluate(PREP, { control, rootSel });
  if (pre.error) return pre;
  await page.waitForTimeout(200);           // cross the task boundary
  const post = await page.evaluate(READ);
  if (post.n !== pre.n) return { error: `subject changed during sweep: ${pre.n} -> ${post.n}` };
  const diffs = [];
  for (let e = 0; e < pre.n; e++) {
    for (const k of Object.keys(pre.before[e])) {
      if (pre.before[e][k] !== post.after[e][k]) {
        diffs.push({ idx: e, id: post.ids[e], prop: k, before: pre.before[e][k], after: post.after[e][k] });
      }
    }
  }
  return { n: pre.n, rootInsideApp: pre.rootInsideApp, census: pre.census, legacyRules: pre.legacyRules,
           deleted: pre.deleted, failed: pre.failed, remainingAfterDelete: post.remaining, diffs };
}

// ---- route discovery (fails loudly rather than sweeping an empty subject) ----
await page.goto(base + '/workbench?dev=1&discover=1#/dashboard', { waitUntil: 'load' });
await page.waitForTimeout(2500);
const hrefs = await page.evaluate(() => [...document.querySelectorAll('.app-nav-item')].map((b) => {
  const raw = b.dataset.route || b.getAttribute('href') || b.getAttribute('data-href') || '';
  return raw.startsWith('#/') ? raw : (raw ? '#/' + raw : '');
}));
const badRoutes = hrefs.filter((h) => !/^#\/[a-z0-9-]+$/.test(h));
console.log(`routes discovered from .app-nav-item[data-route]: ${hrefs.length}`);
if (hrefs.length !== 12 || badRoutes.length) {
  console.log(`ROUTE DISCOVERY FAILED: unusable=${JSON.stringify(badRoutes)} -> aborting rather than sweeping an empty subject`);
  await ctx.close(); server.close(); process.exit(2);
}

// ---- positive control, on its own document load, before the pass it validates ----
const CONTROL = 'button{word-spacing:9px !important;text-indent:13px !important}';
await page.goto(base + '/workbench?dev=1&control=1#/dashboard', { waitUntil: 'load' });
await page.waitForTimeout(2500);
let ctl = { insertTookEffect: null, collected: null, sheetLostIt: null, reported: null };
{
  const ins = await page.evaluate((sel) => {
    const sh = [...document.styleSheets].find((s) => (s.href || '').endsWith('style.css'));
    sh.insertRule(sel, sh.cssRules.length);
    return { sheet: sh.href, ruleText: sh.cssRules[sh.cssRules.length - 1].cssText };
  }, CONTROL);
  await page.waitForTimeout(250);
  const applied = await page.evaluate(() => {
    const b = document.querySelector('.app button');
    const c = getComputedStyle(b);
    return [c.wordSpacing, c.textIndent];
  });
  const r = await sweep(undefined);   // do NOT pass control: it is already in the sheet
  ctl = {
    inserted: ins,
    insertTookEffect: applied[0] === '9px' && applied[1] === '13px',
    applied,
    collected: r.legacyRules.filter((s) => s === 'button').length,
    expectedCollected: 2,             // the real legacy `button` rule + the injected one
    sheetLostIt: r.remainingAfterDelete === 0,
    reported: r.diffs.filter((d) => d.prop === 'word-spacing' || d.prop === 'text-indent').length,
    reportedSample: r.diffs.filter((d) => d.prop === 'word-spacing').slice(0, 2).map((d) => `${d.id} ${d.before}`),
  };
  console.log('\n=== POSITIVE CONTROL (detector sensitivity) ===');
  console.log(`  injected into ${ins.sheet}: ${ins.ruleText}`);
  console.log(`  computed [word-spacing, text-indent] on first .app button after insert: ${JSON.stringify(applied)} (took effect: ${ctl.insertTookEffect})`);
  console.log(`  filter collected bare 'button' rules: ${ctl.collected} (expected ${ctl.expectedCollected})`);
  console.log(`  element-only rules remaining after deletion: ${ctl.sheetLostIt ? 0 : 'NONZERO'}`);
  console.log(`  reported as legacy-supplied: ${ctl.reported} binding(s) ${JSON.stringify(ctl.reportedSample)}`);
  const ok = ctl.insertTookEffect && ctl.collected === ctl.expectedCollected && ctl.sheetLostIt && ctl.reported > 0;
  console.log(ok ? '  CONTROL PASS: the detector reports an injected leak end-to-end'
                 : '  **CONTROL FAIL: a zero/clean result from this sweep is NOT trustworthy**');
}

// ---- the real pass: all 12 routes ----
const totals = { elements: 0, census: {}, routes: {}, legacyRules: null, failed: 0 };
let n = 0;
console.log('\n=== per-route sweep (unique query per route forces a real document load) ===');
for (const href of hrefs) {
  await page.goto(`${base}/workbench?dev=1&sweep=${n++}${href}`, { waitUntil: 'load' });
  await page.waitForTimeout(2500);
  const r = await sweep(undefined, '.app');
  if (r.error) { console.log(`  ${href}  ERROR ${r.error}`); continue; }
  const c = r.census || {};
  console.log(`  ${href.padEnd(16)} els=${String(r.n).padStart(3)}  h3=${c.h3 || 0} p=${c.p || 0} button=${c.button || 0} li=${c.li || 0}  legacyRules=${r.legacyRules.length} deleted=${r.deleted} failed=${r.failed}  diffs=${r.diffs.length}`);
  totals.elements += r.n;
  totals.failed += r.failed;
  for (const [t, cnt] of Object.entries(c)) totals.census[t] = Math.max(totals.census[t] || 0, cnt);
  if (!totals.legacyRules) totals.legacyRules = r.legacyRules;
  totals.routes[href] = r.diffs;
}

// ---- the LEGACY screen: default empty-hash workbench without dev mode ----
// This is where the legacy element rules are most likely load-bearing, and the 12
// dev routes never render it: `login.hidden = showWorkbench ? connected : true`, so
// the login form only appears on the empty-hash workbench view with no connection.
console.log('\n=== non-dev legacy screens (NOT covered by the 12 routes above) ===');
for (const [label, url, root] of [
  ['login/connect (empty hash)', '/workbench?legacy=1', '#login'],
  ['workbench view (#/workbench)', '/workbench?legacy=2#/workbench', '#login'],
  ['whole body (empty hash)', '/workbench?legacy=3', 'body'],
]) {
  await page.goto(base + url, { waitUntil: 'load' });
  await page.waitForTimeout(2000);
  const r = await sweep(undefined, root);
  if (r.error) { console.log(`  ${label.padEnd(30)} ERROR ${r.error}`); continue; }
  const c = r.census || {};
  console.log(`  ${label.padEnd(30)} root=${root.padEnd(7)} inApp=${r.rootInsideApp} els=${String(r.n).padStart(3)}  input=${c.input || 0} select=${c.select || 0} label=${c.label || 0} button=${c.button || 0} form=${c.form || 0}  diffs=${r.diffs.length}`);
  totals.legacy = totals.legacy || {};
  totals.legacy[label] = r.diffs;
  for (const [t, cnt] of Object.entries(c)) totals.census[t] = Math.max(totals.census[t] || 0, cnt);
}

console.log('\n=== legacy element-only rules reaching into the document ===');
for (const s of totals.legacyRules || []) console.log('  ' + s);
console.log(`\n=== elements swept across all 12 routes: ${totals.elements} (deletion failures: ${totals.failed}) ===`);
console.log('=== tag census inside .app (max per route) -- a tag absent here is NOT exercised ===');
console.log('  ' + Object.entries(totals.census).sort((a, b) => b[1] - a[1]).map(([t, c]) => `${t}:${c}`).join('  '));
console.log('=== properties actually SUPPLIED to .app elements by the legacy rules ===');
let total = 0;
const report = (title, groups) => {
  let local = 0;
  const lines = [];
  for (const [href, diffs] of Object.entries(groups)) {
    if (!diffs.length) continue;
    lines.push(`\n  ${href}`);
    // group per element+value and DEDUPE property names: the raw longhand list repeats
    // a name once per logical property (margin/margin-block/margin-top share values),
    // which produced an unreadable multi-thousand-token dump.
    const byEl = new Map();
    for (const d of diffs) {
      const k = `${d.id}|${d.before}|${d.after}`;
      if (!byEl.has(k)) byEl.set(k, new Set());
      byEl.get(k).add(d.prop);
      local++;
    }
    for (const [k, props] of byEl) {
      const [id, before, after] = k.split('|');
      lines.push(`    ${id}  {${[...props].sort().join(' ')}} = ${before}  <- legacy (reverts to ${after})`);
    }
  }
  if (lines.length) console.log(`\n--- ${title} ---` + lines.join('\n'));
  return local;
};
total += report('dev-mode B10 routes (.app)', totals.routes);
total += report('legacy screens (default view + login, In/Out of .app split)', totals.legacy || {});
const inApp = Object.values(totals.routes).flat().length
  + Object.values(totals.legacy || {}).flat().filter((d) => d.id.startsWith('IN:')).length;
const outApp = Object.values(totals.legacy || {}).flat().filter((d) => d.id.startsWith('OUT:')).length;
console.log(`\nTOTAL legacy-supplied property bindings found: ${total}`);
console.log(`SPLIT: inside .app = ${inApp} binding(s)   outside .app (legacy chrome) = ${outApp} binding(s)`);
console.log(inApp === 0
  ? 'RESULT: .app CLEAN -- 0 legacy-supplied bindings in the B10 shell (the 1:1 subject).'
  : `RESULT: LEAK PRESENT -- ${inApp} property binding(s) inside .app still come from pre-B10 CSS.`);
console.log(`NOTE: the ${outApp} out-of-.app bindings are expected and NOT a defect of this`);
console.log('      shell: the login/connect screen, #workspace and nav.app-nav are the legacy');
console.log('      app that B10 does not govern. They are the reason the legacy element rules');
console.log('      CANNOT simply be scoped away -- see W02-LEAK-SWEEP.txt.');

await ctx.close();
server.close();
