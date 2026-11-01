// SPDX-License-Identifier: MIT
// Comparative typography measurement: B10 reference vs workbench implementation.
// Loads BOTH in the same browser and diffs computed text styles, so a leak from a
// legacy element-level rule shows up as a concrete px delta rather than a guess.
import { createServer } from 'node:http';
import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const CHROME = 'D:/All projects/OS External Configuration/toolchains/playwright/chromium-1228/chrome-win64/chrome.exe';
const MIME = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8' };

// --- B10 reference (from the DESIGN-LAB-specific originals) ---
const REFROOT = resolve('.project-local/task-artifacts/designlab-followup-taskpack-20260928/ui-originals/B10');
const refServer = createServer((req, res) => {
  const p = decodeURIComponent(req.url.split('?')[0]);
  const f = join(REFROOT, p === '/' ? '/index.html' : p);
  if (!existsSync(f)) { res.statusCode = 404; res.end('nf'); return; }
  res.setHeader('Content-Type', MIME[extname(f)] || 'application/octet-stream');
  res.end(readFileSync(f));
});
await new Promise((r) => refServer.listen(0, '127.0.0.1', r));
const REF = `http://127.0.0.1:${refServer.address().port}/index.html#dashboard`;

// --- workbench (production CSP + committed build) ---
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'";
const WB = resolve('apps/workbench');
const R = {
  '/workbench/style.css': [join(WB, 'style.css'), 'text/css; charset=utf-8'],
  '/workbench/main.js': [join(WB, 'build', 'main.js'), 'text/javascript; charset=utf-8'],
};
const wbServer = createServer((req, res) => {
  const p = req.url.split('?')[0];
  res.setHeader('Content-Security-Policy', CSP);
  const h = R[p];
  if (h) { res.setHeader('Content-Type', h[1]); res.end(readFileSync(h[0])); return; }
  if (p.startsWith('/workbench')) { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(readFileSync(join(WB, 'index.html'))); return; }
  res.statusCode = 404; res.end('nf');
});
await new Promise((r) => wbServer.listen(0, '127.0.0.1', r));
const WBURL = `http://127.0.0.1:${wbServer.address().port}/workbench?dev=1#/dashboard`;

const outDir = resolve('.project-local/task-artifacts/designlab-followup-taskpack-20260928');
mkdirSync(outDir, { recursive: true });
const profile = join(outDir, 'chrome-profile-typo');
mkdirSync(profile, { recursive: true });
const ctx = await chromium.launchPersistentContext(profile, { executablePath: CHROME, headless: true, viewport: { width: 1600, height: 1000 } });
const page = ctx.pages()[0] || await ctx.newPage();

// The same semantic elements exist on both sides.
const PROBE = () => {
  const pick = (sel) => {
    const e = document.querySelector(sel);
    if (!e) return null;
    const c = getComputedStyle(e);
    return { tag: e.tagName.toLowerCase(), cls: (e.className || '').toString(),
             fontSize: c.fontSize, lineHeight: c.lineHeight, color: c.color, marginTop: c.marginTop, marginBottom: c.marginBottom };
  };
  return {
    'page-head p': pick('.page-head p'),
    'page-head h2': pick('.page-head h2'),
    'panel h3': pick('.panel h3'),
    'kpi small': pick('.kpi small'),
    'kpi strong': pick('.kpi strong'),
    'list-item strong': pick('.list-item strong'),
    'list-item small': pick('.list-item small'),
    'muted div': pick('.muted'),
    'tag': pick('.tag'),
    'sidebar h1': pick('.brand h1'),
    'sidebar small': pick('.brand small'),
    'nav button span': pick('.nav button span:last-child'),
    'search': pick('.search'),
    'ghost-btn': pick('.ghost-btn'),
  };
};

await page.goto(REF, { waitUntil: 'load' });
await page.waitForTimeout(2000);
const ref = await page.evaluate(PROBE);
await page.goto(WBURL, { waitUntil: 'load' });
await page.waitForTimeout(2500);
const wb = await page.evaluate(PROBE);

const deltas = [];
console.log('element                 tag(ref/impl)   prop         B10 ref        workbench      match');
for (const k of Object.keys(ref)) {
  const tagPair = `${ref[k]?.tag ?? '-'}/${wb[k]?.tag ?? '-'}`;
  const tagMismatch = ref[k]?.tag !== wb[k]?.tag;
  for (const prop of ['fontSize', 'lineHeight', 'color', 'marginTop', 'marginBottom']) {
    const a = ref[k]?.[prop], b = wb[k]?.[prop];
    if (a === undefined && b === undefined) continue;
    const same = a === b;
    if (!same) deltas.push({ element: k, prop, ref: a, impl: b, tagMismatch, tagPair });
    console.log(`${k.padEnd(22)} ${tagPair.padEnd(15)} ${prop.padEnd(12)} ${String(a ?? '-').padEnd(14)} ${String(b ?? '-').padEnd(14)} ${same ? 'ok' : '**DIFF**'}`);
  }
  if (tagMismatch) console.log(`  ^^ TAG MISMATCH for ${k}: the two sides are different elements; props are not comparable`);
}

console.log('\n' + '='.repeat(70));
console.log(`DIFFS: ${deltas.length}`);
for (const d of deltas) console.log(`  ${d.element} . ${d.prop}: B10=${d.ref}  impl=${d.impl}`);
writeFileSync(join(outDir, 'W01-TYPO-DIFF.json'), JSON.stringify({ ref, wb, deltas }, null, 2), 'utf-8');
await ctx.close();
refServer.close();
wbServer.close();
