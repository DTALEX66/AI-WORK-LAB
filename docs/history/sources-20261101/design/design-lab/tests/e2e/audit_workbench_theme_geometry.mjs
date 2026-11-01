// SPDX-License-Identifier: MIT
// Workbench theme geometry gate — does the OPTIONAL palette actually change geometry?
//
// Env: E2E_SERVICE_URL E2E_TOKEN E2E_NODE_MODULES [E2E_BROWSER]
//      [THEME_WIDTHS=1920,1200,960,768,700] [THEME_OUT=<json path>]
//
// Why this gate exists. `style.css` registers the 20261009 pack's layout numbers as `--uif-*`
// tokens, and the palette block re-points colours only. Measured 2026-10-11: the sidebar and both
// gutters were declared, never read, and the registered values were not even the pack's — so the
// claim "新包取值做成可选主题" was true for colour and empty for geometry. A stylesheet can say a
// thing twice: once in a declaration nobody consumes, once in the pixels a person sees. Only the
// second one is the product, and only a browser can read it.
//
// So this gate measures, per width and per palette:
//   · the nav rail's painted width (getBoundingClientRect, not the declaration);
//   · the content column's margin-left and padding-right, which must move WITH the rail — a rail
//     that widens without the offset is content sliding underneath it, which no text-clip check
//     would call clipped;
//   · and that the DEFAULT palette is bit-for-bit what it was (168 / 192 / 0), because the owner
//     boundary is that the existing palette is never overridden.
// Below the pack's own 768px breakpoint the theme must fall back to the default geometry: mobile is
// FROZEN_DEFERRED, so a min-width that leaks into the narrow layout would be an unauthorised change.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';

const serviceUrl = process.env.E2E_SERVICE_URL;
const nmDir = process.env.E2E_NODE_MODULES;
const browserPath = process.env.E2E_BROWSER || undefined;
const widths = (process.env.THEME_WIDTHS || '1920,1200,960,768,700')
  .split(',').map((w) => Number.parseInt(w, 10)).filter((w) => Number.isFinite(w) && w > 0);
const outPath = process.env.THEME_OUT || '';

const fail = (reason) => { console.error('TG_FAIL: ' + reason); process.exit(2); };
if (!serviceUrl || !nmDir) fail('TG_CONFIG_MISSING');
if (widths.length === 0) fail('THEME_WIDTHS_EMPTY');

const req = createRequire(nmDir + '/noop.js');
const { chromium } = req('playwright');

const REPO = process.cwd();
const STYLE = path.join(REPO, 'apps/workbench/style.css');
const BUNDLE = path.join(REPO, 'apps/workbench/build/main.js');
const digest = (file) => createHash('sha256').update(readFileSync(file)).digest('hex');

// Expectations by palette and width. The rail is 168 and the content offset 192 for the default
// theme at every desktop width; ui2026 swaps in the pack's 256/30 (>=1200) and 216/22 (768-1199);
// under 768 the pack has no desktop layout to assert, so both themes must read the same numbers.
function expected(width) {
  if (width < 768) return { theme: null, rail: null, offset: null, pad: null };
  if (width < 1200) return { theme: 216, offset: 216 + 22, pad: 22 };
  return { theme: 256, offset: 256 + 30, pad: 30 };
}

// The variant list is read out of the product's own table rather than typed a second time here.
// It used to be hardcoded to design-lab/dark + ui2026 in both schemes, which meant the pearl-white
// face -- the one the 20261023 pack actually specifies -- was never measured by this gate at all,
// while the contrast gate injected the attribute and so graded a face nobody could reach by
// clicking. shell.ts declares PALETTES with each palette's own `schemes`, so one parse here keeps
// the two gates honest about the same population.
function readPaletteTable() {
  const shell = readFileSync(path.join(REPO, 'apps/workbench/shell.ts'), 'utf8');
  const block = shell.slice(shell.indexOf('const PALETTES'), shell.indexOf('function paletteSpec'));
  const out = [];
  const each = /\{\s*id:\s*'([\w-]+)'[^}]*?schemes:\s*\[([^\]]*)\]/g;
  let match;
  while ((match = each.exec(block))) {
    for (const scheme of match[2].split(',').map((s) => s.trim().replace(/'/g, '')).filter(Boolean)) {
      out.push([match[1], scheme]);
    }
  }
  return out;
}

const PALETTES = readPaletteTable();

const READ = () => {
  const rail = document.querySelector('.app-nav');
  const main = document.querySelector('.dl-shell > main') || document.querySelector('main');
  if (!rail || !main) return null;
  const cs = getComputedStyle(main);
  return {
    railRect: Math.round(rail.getBoundingClientRect().width),
    railComputed: Math.round(parseFloat(getComputedStyle(rail).width)),
    marginLeft: Math.round(parseFloat(cs.marginLeft)),
    paddingRight: Math.round(parseFloat(cs.paddingRight)),
    docOverflowX: document.documentElement.scrollWidth - window.innerWidth,
  };
};

const browser = await chromium.launch({ executablePath: browserPath, args: ['--no-sandbox'] });
const report = {
  subject: {
    styleSha256: digest(STYLE), bundleSha256: digest(BUNDLE),
    styleBytes: readFileSync(STYLE).length, bundleBytes: readFileSync(BUNDLE).length,
  },
  widths: {},
};
const findings = [];

for (const width of widths) {
  const seen = {};
  for (const [palette, scheme] of PALETTES) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.addInitScript(([p, s]) => {
      const apply = () => {
        document.documentElement.setAttribute('data-palette', p);
        if (s === 'light') document.documentElement.setAttribute('data-scheme', 'light');
        else document.documentElement.removeAttribute('data-scheme');
      };
      if (document.documentElement) apply();
      else document.addEventListener('DOMContentLoaded', apply);
    }, [palette, scheme]);
    await page.goto(serviceUrl.replace(/\/$/, '') + '/workbench', { waitUntil: 'load' });
    await page.waitForSelector('.app-nav', { timeout: 15000 });
    const read = await page.evaluate(READ);
    seen[`${palette}/${scheme}`] = read;
    if (!read) findings.push(`NO_GEOMETRY ${width} ${palette}/${scheme}: .app-nav or main never mounted`);
    await page.close();
  }

  const base = seen['design-lab/dark'];
  const exp = expected(width);
  report.widths[String(width)] = seen;
  if (!base) continue;
  // Every other palette the product declares must be GEOMETRICALLY indistinguishable from the
  // default face. The 20261023 pack states six colours (09_DESIGN.md:9) and no rail width, so a
  // stitch-specific number here would be a value this repository invented -- which is why the
  // assertion is equality with the default rather than a new constant. A difference is an
  // unauthorised layout change, so this runs at every width including the narrow ones.
  for (const [key, read] of Object.entries(seen)) {
    if (key === 'design-lab/dark' || key.startsWith('ui2026/') || !read) continue;
    for (const field of ['railRect', 'railComputed', 'marginLeft', 'paddingRight']) {
      if (read[field] !== base[field]) {
        findings.push(`PALETTE_MOVES_GEOMETRY @${width} ${key}: ${field}=${read[field]} vs `
                      + `default ${base[field]} -- the 20261023 pack declares colours only, so `
                      + 'a layout difference here is not authorised');
      }
    }
  }
  if (exp.rail === null) {
    // Below the pack's 768px breakpoint the shell collapses the rail into a bar (measured: the rail
    // takes the full 700px viewport and the content margin drops to 16). That layout is
    // FROZEN_DEFERRED, so no absolute number is asserted here for either theme; what IS asserted is
    // that the optional palette is indistinguishable from the default -- a min-width that leaked
    // into the narrow layout would be an unauthorised mobile change.
    for (const variant of ['ui2026/dark', 'ui2026/light']) {
      const read = seen[variant];
      if (!read) continue;
      for (const field of ['railRect', 'railComputed', 'marginLeft', 'paddingRight']) {
        if (read[field] !== base[field]) {
          findings.push(`THEME_LEAKS_INTO_MOBILE @${width} ${variant}: ${field}=${read[field]} `
                        + `vs default ${base[field]}`);
        }
      }
    }
    continue;
  }
  if (base.railRect !== 168 || base.railComputed !== 168) {
    findings.push(`DEFAULT_RAIL_MOVED @${width}: expected 168, saw rect=${base.railRect} computed=${base.railComputed}`);
  }
  if (base.marginLeft !== 192) findings.push(`DEFAULT_OFFSET_MOVED @${width}: expected 192, saw ${base.marginLeft}`);
  if (base.paddingRight !== 0) findings.push(`DEFAULT_PAD_MOVED @${width}: expected 0, saw ${base.paddingRight}`);

  for (const variant of ['ui2026/dark', 'ui2026/light']) {
    const read = seen[variant];
    if (!read) continue;
    if (read.railRect !== exp.theme || read.railComputed !== exp.theme) {
      findings.push(`THEME_RAIL_NOT_APPLIED @${width} ${variant}: expected ${exp.theme}px, saw rect=${read.railRect} computed=${read.railComputed}`);
    }
    if (read.marginLeft !== exp.offset) {
      findings.push(`CONTENT_OFFSET_MISMATCH @${width} ${variant}: expected ${exp.offset}, saw ${read.marginLeft} (rail ${read.railRect} + gutter)`);
    }
    if (read.paddingRight !== exp.pad) {
      findings.push(`GUTTER_NOT_APPLIED @${width} ${variant}: expected ${exp.pad}, saw ${read.paddingRight}`);
    }
    if (read.docOverflowX > 0) {
      findings.push(`THEME_OVERFLOW @${width} ${variant}: document is ${read.docOverflowX}px wider than the viewport`);
    }
  }
}

if (outPath) {
  report.findings = findings;
  writeFileSync(outPath, JSON.stringify(report, null, 2) + '\n', 'utf8');
}

for (const width of widths) console.log(`TG_READ ${width} ` + JSON.stringify(report.widths[String(width)]));
console.log(`TG_SUMMARY widths=${widths.length} palettes=${PALETTES.length} findings=${findings.length} `
  + `style=${report.subject.styleSha256.slice(0, 12)} bundle=${report.subject.bundleSha256.slice(0, 12)}`);
if (findings.length) {
  for (const line of findings) console.error('  FINDING ' + line);
  fail(`${findings.length} geometry finding(s)`);
}
console.log('TG_OK');
process.exit(0);
