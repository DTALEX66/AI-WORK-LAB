// SPDX-License-Identifier: MIT
// Theme affordance gate: does clicking the palette control actually change what is painted,
// and does the URL the control writes come back as a page instead of a 401?
//
// Why this exists: the DOT audit (D13) found that both theme buttons were no-ops in a real
// browser and that `?palette=ui2026` answered 401. Neither could be seen from the vm contract
// suite (which never asserted a theme change) or from the capture driver (which sets the <html>
// attributes directly, so it renders the light theme without the product path ever working).
// This gate drives the shipped bundle in Chromium, clicks the real buttons, and reads the
// computed background before and after -- the only reading that can tell "the attribute moved"
// apart from "the page changed".
//
// 2026-10-26 extension: the walk no longer stops after one click. It cycles the WHOLE palette
// table and grades every hop, because the table grew a third entry (`stitch`, the 20261023
// pearl-white pack) that the old one-step probe never reached: `ui2026` was the only non-default
// palette this gate ever landed on by clicking, so a palette that the click path cannot actually
// paint was invisible here. The expected table is read out of `apps/workbench/shell.ts` rather
// than restated in this file -- a second hard-coded list is exactly how
// `audit_workbench_theme_geometry.mjs` came to measure three states and call that the whole
// table, and it is the reason `stitch` never appeared there either. When PALETTES gains a fourth
// id, this walk has to grow to four hops on its own.
//
// What the per-hop ratio is, and what it is not: the repo's one owner of contrast maths is
// `audit_workbench_contrast.mjs`, and it cannot be imported -- it is a top-level script that
// launches its own browser and exits the process. This file deliberately does NOT grow a second
// OKLab / color-mix / gradient-compositing implementation to disagree with it. The number printed
// per hop exists only as a CHANGE DETECTOR (did this click move the ink, yes or no), and it is
// computed only when the probe's own foreground and its whole background chain are plain opaque
// `rgb()` triples; in every other case the reading is `null` and the change judgement falls back
// to the raw colour strings of that chain. The AA verdict for any palette -- stitch's light side
// included -- stays with the contrast gate, which runs it per route via `UI_PALETTE`/`UI_SCHEME`.
// The small luminance formula below is pinned to the same four published WCAG 2.1 reference pairs
// the owner gate pins itself to, so a broken copy here goes red instead of quietly drifting.
//
// Env: E2E_SERVICE_URL E2E_TOKEN E2E_NODE_MODULES E2E_BROWSER [AFF_OUT] [AFF_WIDTH=1440]
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const serviceUrl = process.env.E2E_SERVICE_URL;
const token = process.env.E2E_TOKEN;
const nmDir = process.env.E2E_NODE_MODULES;
const browserPath = process.env.E2E_BROWSER;
const outPath = process.env.AFF_OUT || '';
const width = Number.parseInt(process.env.AFF_WIDTH || '1440', 10);

const fail = (reason) => { console.error('AFF_FAIL: ' + reason); process.exit(2); };
if (!serviceUrl || !token || !nmDir) fail('missing E2E_SERVICE_URL / E2E_TOKEN / E2E_NODE_MODULES');

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..', '..');
const req = createRequire(nmDir + '/noop.js');
const { chromium } = req('playwright');

// ----------------------------------------------------------------------------
// The palette table, read from the product source instead of restated here.
// One owner (PALETTES in shell.ts) means a palette added to the interface is a
// palette this gate must click; a palette the click path cannot reach is a finding.
// ----------------------------------------------------------------------------
const SHELL_TS = path.join(REPO, 'apps/workbench/shell.ts');
const shellSource = readFileSync(SHELL_TS, 'utf8');
const tableBlock = /const PALETTES: readonly PaletteSpec\[\] = \[([\s\S]*?)\n\];/.exec(shellSource);
if (!tableBlock) {
  fail(`no \`const PALETTES: readonly PaletteSpec[] = [\` block found in ${SHELL_TS} -- `
    + 'this gate cycles the product table, so without reading it there is nothing to cycle');
}
const PALETTE_TABLE = [...tableBlock[1].matchAll(
  /\{\s*id:\s*'([^']+)'[\s\S]*?schemes:\s*\[([^\]]*)\]/g,
)].map((m) => ({
  id: m[1],
  schemes: [...m[2].matchAll(/'([^']+)'/g)].map((s) => s[1]),
}));
if (PALETTE_TABLE.length < 2)
  fail(`the palette table parsed to ${PALETTE_TABLE.length} entries (${JSON.stringify(PALETTE_TABLE)}); `
    + 'a one-entry table cannot be cycled, and a failed parse reads exactly like that');
const TABLE_IDS = PALETTE_TABLE.map((p) => p.id);

// A stable text run: the sidebar's group caption. It exists in every palette, its ink comes from
// `--muted` -> `--color-muted` (a token every palette block re-points), and its text never changes
// when the theme changes -- so a difference in its computed colour is a difference in what is
// painted, not a difference in which string happened to be measured.
const PROBE_SELECTOR = '.nav-group';

const READ = (probeSelector) => {
  const root = document.documentElement;
  const buttons = Array.from(document.querySelectorAll('.theme-toggle'));
  // The document ships TWO navigations by design (the legacy flat `.app-nav` and the routed B10
  // sidebar), each carrying its own `.nav-group` captions, and exactly one set is hidden. Picking
  // `querySelector(selector)` blindly returns the first in DOM order, which is the unpainted one,
  // so the probe would measure an ink nobody sees. Choose the first candidate that is actually
  // painted, and say how many candidates there were.
  const candidates = Array.from(document.querySelectorAll(probeSelector));
  let probe = null;
  let paintedAt = -1;
  for (let i = 0; i < candidates.length; i += 1) {
    const c = candidates[i];
    const cs = getComputedStyle(c);
    const box = c.getBoundingClientRect();
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (box.width < 1 || box.height < 1 || parseFloat(cs.opacity) === 0) continue;
    probe = c;
    paintedAt = i;
    break;
  }
  // The background chain is collected as RAW serialised strings, in paint order from the probe
  // outward, and the walk stops at the first opaque layer. Deliberately no compositing here:
  // translucent backdrops, gradients and oklab serialisations are the owner gate's problem, and
  // a second half-built implementation is how two gates start disagreeing about one page.
  const bgChain = [];
  let chainOpaqueAt = -1;
  let chainInertOnly = true;
  if (probe) {
    for (let p = probe; p; p = p.parentElement) {
      const bg = getComputedStyle(p).backgroundColor;
      bgChain.push(`${p.tagName.toLowerCase()}${p.id ? '#' + p.id : ''}=${bg}`);
      // An alpha-0 layer is the identity of `source-over` -- skipping it is arithmetic, not a
      // compositing model, so it does not count as inventing a second implementation. Anything
      // ELSE that is not fully opaque does, and takes the reading back to `rgbOnly: false`.
      const alpha0 = /^rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*0\s*\)$/.test(bg);
      if (alpha0) continue;
      if (/^rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$/.test(bg)) { chainOpaqueAt = bgChain.length - 1; break; }
      chainInertOnly = false;
    }
  }
  return {
    palette: root.getAttribute('data-palette') || '(absent)',
    scheme: root.getAttribute('data-scheme') || '(absent)',
    bodyBg: getComputedStyle(document.body).backgroundColor,
    surfaceVar: getComputedStyle(root).getPropertyValue('--surface').trim(),
    primaryVar: getComputedStyle(root).getPropertyValue('--primary').trim(),
    controls: buttons.map((b) => ({ action: b.dataset.themeAction || '?',
                                    label: (b.textContent || '').trim(),
                                    visible: b.offsetParent !== null
                                    && getComputedStyle(b).visibility !== 'hidden' })),
    search: location.search,
    probe: probe ? {
      selector: probeSelector,
      candidates: candidates.length,
      paintedAt,
      text: (probe.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40),
      color: getComputedStyle(probe).color,
      bgChain,
      // Only an all-opaque rgb() chain can be graded without inventing a compositing model.
      rgbOnly: chainOpaqueAt >= 0 && chainInertOnly
        && /^rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$/.test(getComputedStyle(probe).color),
      opaqueBg: chainOpaqueAt >= 0
        ? (/=rgb\([\d,\s]+\)$/.exec(bgChain[chainOpaqueAt]) || [''])[0].slice(1) : '',
    } : { selector: probeSelector, candidates: candidates.length, paintedAt: -1,
          text: '(no painted candidate)', color: '(none)', bgChain: [], rgbOnly: false,
          opaqueBg: '' },
  };
};

// ---- WCAG 2.1 relative contrast, for the change detector only ----------------
// Pinned against the same published reference pairs `audit_workbench_contrast.mjs` pins itself
// against. If this copy and the owner copy ever disagree about the maths, this goes red rather
// than letting two gates print two different numbers for one painted page.
const hexRgb = (h) => ({ r: parseInt(h.slice(1, 3), 16), g: parseInt(h.slice(3, 5), 16),
                         b: parseInt(h.slice(5, 7), 16) });
const lum = (c) => {
  const f = (v) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
};
const ratioOf = (a, b) => {
  const [x, y] = [lum(a), lum(b)];
  const [hi, lo] = x >= y ? [x, y] : [y, x];
  return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100;
};
const MATH = [
  ['#777777', '#777777', 1], ['#FFFFFF', '#000000', 21],
  ['#767676', '#FFFFFF', 4.54], ['#777777', '#FFFFFF', 4.48],
].map(([a, b, want]) => {
  const got = ratioOf(hexRgb(a), hexRgb(b));
  return { a, b, want, got, ok: Math.abs(got - want) <= 0.06 };
});
const mathBad = MATH.filter((c) => !c.ok);
if (mathBad.length)
  fail(`contrast maths self-test failed on ${JSON.stringify(mathBad)} -- the change detector `
    + 'below would be measuring a number this file invented');

// ---- probe availability ----------------------------------------------------
// The whole walk grades one text run, so a page on which that run is never painted makes every
// reading equal to every other and the cycle look stable and clean. Wait for a PAINTED candidate,
// and fail loudly when there is none.
async function waitForProbe(p, where, list) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    const value = await p.evaluate(READ, PROBE_SELECTOR);
    if (value.probe.paintedAt >= 0) return true;
    await p.waitForTimeout(200);
  }
  list.push(`${where}: no painted ${PROBE_SELECTOR} text run appeared within 15s -- the probe `
    + 'this gate grades is absent, so every colour comparison below would be vacuous');
  return false;
}

// ---- theme settle ------------------------------------------------------------
// The click repaints through token changes, and any surface carrying a `transition:all` utility
// class can sit between two states for a frame or two. A fixed sleep can therefore read a colour
// that no rule declares. So a reading is only accepted once the probe's ink AND its background
// chain have held identical across consecutive frames, with a deadline that names the probe when
// it never settles.
async function settle(p, tag, findings) {
  let prev = null;
  let stable = 0;
  const deadline = Date.now() + 6000;
  while (Date.now() < deadline) {
    const value = await p.evaluate(READ, PROBE_SELECTOR);
    const signature = JSON.stringify([value.palette, value.scheme, value.probe.color,
                                      value.probe.bgChain]);
    if (prev !== null && signature === prev) stable += 1; else stable = 0;
    prev = signature;
    if (stable >= 2) return value;
    await p.evaluate(() => new Promise((res) => requestAnimationFrame(() => res())));
  }
  findings.push(`${tag}: the painted theme never settled within 6s `
    + `(probe=${PROBE_SELECTOR} ink=${(prev || 'unread')}) -- a value read mid-transition is not `
    + 'a measurement of either palette');
  return await p.evaluate(READ, PROBE_SELECTOR);
}

const browser = await chromium.launch({ executablePath: browserPath, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width, height: 900 } });
const findings = [];
const measures = {};
const statuses = [];

page.on('response', (r) => {
  const u = new URL(r.url());
  if (u.pathname === '/workbench') statuses.push(`${r.status()} ${u.search || '(no query)'}`);
});

async function read(tag) {
  const value = await page.evaluate(READ, PROBE_SELECTOR);
  measures[tag] = value;
  return value;
}

// 1. the plain page, on a routed view where the shell header renders the controls
await page.goto(`${serviceUrl}/workbench#/capabilities`, { waitUntil: 'load' });
await waitForProbe(page, 'the routed view', findings);
const before = await settle(page, 'opening state', findings);
measures.plainBeforeClick = before;
// Two sets of controls exist in the document by design -- the legacy workbench topbar and the
// routed shell header -- and exactly one of each is hidden. Clicking the hidden one is what
// made the first version of this probe time out, so the count of VISIBLE controls per action is
// itself the assertion: a person must have exactly one thing to press.
const visibleCount = (list, action) => list.filter((c) => c.action === action && c.visible).length;
const paletteVisible = visibleCount(before.controls, 'palette');
if (paletteVisible !== 1)
  findings.push(`#${'capabilities'} shows ${paletteVisible} visible palette control(s) out of `
    + `${before.controls.length} .theme-toggle nodes -- there must be exactly one to press, `
    + 'and an invisible twin is a phantom control');

const startPalette = before.palette;
if (!TABLE_IDS.includes(startPalette))
  findings.push(`the page opened on palette "${startPalette}", which is not on the product table `
    + `${JSON.stringify(TABLE_IDS)} -- the walk below counts hops from wherever it started, so `
    + 'an off-table start makes the cycle meaningless');

// 2. walk the WHOLE table by clicking: one hop per entry, then back to the starting palette.
// The old version stopped after a single click, so `ui2026` was the only alternate palette this
// path ever proved anything about, and `stitch` -- the pack the owner adopted on 2026-10-23 --
// was never reached by the interface at all.
const hops = [];
if (paletteVisible === 1 && TABLE_IDS.includes(startPalette)) {
  const paletteButton = page.locator('.theme-toggle[data-theme-action="palette"]:visible').first();
  const expectedHops = TABLE_IDS.length;
  let previous = before;
  for (let hop = 1; hop <= expectedHops; hop += 1) {
    await paletteButton.click();
    const value = await settle(page, `palette hop ${hop}`, findings);
    // The shot is taken from the click path itself, not from a driver that presets the
    // attributes, so the PNG and the computed colours describe the same interaction.
    if (process.env.AFF_SHOTS) {
      mkdirSync(process.env.AFF_SHOTS, { recursive: true });
      await page.screenshot({ path: path.join(process.env.AFF_SHOTS,
        `clicked-${previous.palette}-to-${value.palette}@${width}.png`) });
    }
    const prev = previous;
    const painted = `${value.probe.color} on ${value.probe.bgChain.join(' | ')}`;
    const prevPainted = `${prev.probe.color} on ${prev.probe.bgChain.join(' | ')}`;
    const fg = /^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/.exec(value.probe.color);
    const bg = /^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/.exec(value.probe.opaqueBg);
    const rgbRatio = value.probe.rgbOnly && fg && bg
      ? ratioOf({ r: +fg[1], g: +fg[2], b: +fg[3] }, { r: +bg[1], g: +bg[2], b: +bg[3] })
      : null;
    const moved = painted !== prevPainted;
    const paletteMoved = value.palette !== prev.palette;
    hops.push({
      hop,
      palette: value.palette,
      scheme: value.scheme,
      url: value.search,
      probeText: value.probe.text,
      ink: value.probe.color,
      backdrop: value.probe.opaqueBg,
      bgChain: value.probe.bgChain,
      // A number only when nothing had to be composited to get it; otherwise the raw strings
      // above are the change judgement and this field says why it is null.
      changeRatio: rgbRatio,
      ratioBasis: rgbRatio === null
        ? 'background chain is not all-opaque rgb(); change is judged on the raw colour strings'
        : 'opaque rgb() ink over opaque rgb() backdrop',
      moved,
      paletteMoved,
      paint: painted,
    });
    // `afterPaletteClick` keeps its v1 meaning -- the state the FIRST click produced -- so the
    // long-standing wrapper reading stays about the same interaction. The walk's own per-hop
    // readings are `paletteHop1..N` and `hops[]`.
    if (hop === 1) measures.afterPaletteClick = value;
    measures[`paletteHop${hop}`] = value;
    if (!paletteMoved)
      findings.push(`palette hop ${hop} left data-palette at ${value.palette} -- `
        + 'the handler re-read a source that had not been written yet (D13)');
    if (!moved)
      findings.push(`palette hop ${hop} (${prev.palette} -> ${value.palette}) painted nothing new `
        + `-- the probe stayed at ${painted}. An attribute that moves without changing what is `
        + 'painted is not a theme (D13)');
    if (value.search === prev.search)
      findings.push(`palette hop ${hop} left the URL at "${value.search}" -- the control is `
        + 'supposed to record its own choice so a reload repeats it');
    previous = value;
  }

  // 2b. every entry on the table must have been the landing state of some click, and the walk
  // must come round to where it started. A table the loop only partially walks looks like a pass
  // unless it is counted, which is precisely how `stitch` stayed unclicked for so long.
  const landed = Array.from(new Set(hops.map((h) => h.palette)));
  const unclicked = TABLE_IDS.filter((id) => !landed.includes(id));
  if (unclicked.length)
    findings.push(`the palette walk clicked ${hops.length} time(s) and landed on `
      + `${JSON.stringify(landed)}, but ${JSON.stringify(unclicked)} on the product table `
      + `${JSON.stringify(TABLE_IDS)} was never reached -- a palette no click can arrive at is `
      + 'not an option, it is dead weight in the interface');
  if (hops.length && hops[hops.length - 1].palette !== startPalette)
    findings.push(`after ${hops.length} clicks (one per table entry) the page sits on `
      + `${hops[hops.length - 1].palette}, not back on the starting ${startPalette} -- the cycle `
      + 'length does not match the table this gate read');

  // 2c. the pearl-white reading, stated as a colour rather than as an attribute. `stitch` only
  // publishes its light side, and style.css declares those values under
  // `:root[data-palette="stitch"][data-scheme="light"]`, so a hop that lands the palette without
  // the scheme attribute paints the DEFAULT sheet while still claiming `stitch` on <html>.
  const stitchSpec = PALETTE_TABLE.find((p) => p.id === 'stitch');
  const stitchHop = hops.find((h) => h.palette === 'stitch');
  const defaultHop = hops.find((h) => h.palette === 'design-lab');
  if (stitchSpec && stitchHop && defaultHop) {
    if (stitchHop.paint === defaultHop.paint)
      findings.push(`clicking to palette=stitch painted exactly what palette=design-lab paints `
        + `(${stitchHop.paint}) -- the pearl-white token block is keyed on `
        + '[data-palette="stitch"][data-scheme="light"] and the click landed '
        + 'data-scheme="' + stitchHop.scheme + '", so the shipped interface cannot reach the '
        + '20261023 palette by pressing its own control');
  }
}

// 3. the scheme axis: only a palette with two declared sides may offer it.
for (const hop of hops) {
  const spec = PALETTE_TABLE.find((p) => p.id === hop.palette);
  if (!spec) continue;
  const hopMeasures = measures[`paletteHop${hop.hop}`];
  const schemeControls = visibleCount(hopMeasures.controls, 'scheme');
  if (spec.schemes.length > 1 && schemeControls !== 1)
    findings.push(`palette ${hop.palette} declares ${JSON.stringify(spec.schemes)} but shows `
      + `${schemeControls} visible scheme control(s)`);
  if (spec.schemes.length === 1 && schemeControls !== 0)
    findings.push(`palette ${hop.palette} declares only ${JSON.stringify(spec.schemes)} yet still `
      + `offers a scheme button -- a second side this stylesheet never declares would be invented`);
}
{
  const ui2026 = hops.find((h) => h.palette === 'ui2026');
  if (ui2026) {
    const schemeBefore = await settle(page, 'before scheme click', findings);
    measures.beforeSchemeClick = schemeBefore;
    if (visibleCount(schemeBefore.controls, 'scheme') === 1) {
      await page.locator('.theme-toggle[data-theme-action="scheme"]:visible').first().click();
      const schemeAfter = await settle(page, 'scheme click', findings);
      measures.afterSchemeClick = schemeAfter;
      if (schemeAfter.scheme === schemeBefore.scheme)
        findings.push('the scheme control left data-scheme at ' + schemeBefore.scheme + ' (D13)');
      if (schemeAfter.probe.color === schemeBefore.probe.color
          && schemeAfter.probe.bgChain.join('|') === schemeBefore.probe.bgChain.join('|'))
        findings.push(`the scheme click painted nothing new (ink=${schemeBefore.probe.color})`);
    } else if (PALETTE_TABLE.find((p) => p.id === schemeBefore.palette)?.schemes.length > 1) {
      findings.push(`palette ${schemeBefore.palette} has two declared sides but no scheme control `
        + 'was visible to press at that moment');
    }
  }
}

// 4. the URL the control writes must come back as a page, and must be applied on load.
// A fresh page is used because Playwright returns null from goto() when the target is a
// same-document change, and `/workbench#/x` -> `/workbench?palette=..#/x` is exactly that
// edge case: a null response would have been read as "no answer at all" rather than measured.
const themedPage = await browser.newPage({ viewport: { width, height: 900 } });
themedPage.on('response', (r) => {
  const u = new URL(r.url());
  if (u.pathname === '/workbench') statuses.push(`${r.status()} ${u.search || '(no query)'}`);
});
const themed = await themedPage.goto(
  `${serviceUrl}/workbench?palette=ui2026&scheme=light#/capabilities`, { waitUntil: 'load' });
if (!themed) findings.push('the themed navigation produced no response object to grade');
else if (themed.status() !== 200)
  findings.push(`GET /workbench?palette=ui2026&scheme=light answered HTTP ${themed.status()} -- `
    + 'the page route matched the query string, so a reload of the interface own URL fails');
await waitForProbe(themedPage, 'the ui2026 deep link', findings);
const readOn = async (p, tag) => {
  const value = await settle(p, tag, findings);
  measures[tag] = value;
  return value;
};
const fromUrl = await readOn(themedPage, 'loadedFromQueryUrl');
if (themed && themed.status() === 200) {
  if (fromUrl.palette !== 'ui2026')
    findings.push(`the URL asked for palette=ui2026 but the page applied ${fromUrl.palette}`);
  if (fromUrl.scheme !== 'light' && fromUrl.palette !== 'design-lab')
    findings.push(`the URL asked for scheme=light but the page applied ${fromUrl.scheme} `
      + 'on a palette that publishes it');
}

// 5. the pearl-white DEEP LINK, asserted on its own terms. The click path and the URL path are
// two different routes to the same two attributes, and only the URL path can prove the block is
// wired at all: `?palette=stitch&scheme=light` must answer 200, land BOTH attributes on <html>,
// and paint an ink that differs from the default palette's. If the click cycle fails here and the
// deep link passes, that says precisely which of the two paths is broken.
const deepLink = { asked: 'palette=stitch&scheme=light', status: null, palette: null,
                   scheme: null, ink: null, backdrop: null, bgChain: [],
                   paintsLikeDefault: null };
if (PALETTE_TABLE.some((p) => p.id === 'stitch')) {
  const stitchPage = await browser.newPage({ viewport: { width, height: 900 } });
  let stitchStatus = null;
  stitchPage.on('response', (r) => {
    const u = new URL(r.url());
    if (u.pathname === '/workbench') {
      stitchStatus = r.status();
      statuses.push(`${r.status()} ${u.search || '(no query)'}`);
    }
  });
  const stitchNav = await stitchPage.goto(
    `${serviceUrl}/workbench?palette=stitch&scheme=light#/capabilities`, { waitUntil: 'load' });
  deepLink.status = stitchNav ? stitchStatus : null;
  if (!stitchNav) findings.push('the stitch deep-link navigation produced no response object');
  else if (stitchNav.status() !== 200)
    findings.push(`GET /workbench?palette=stitch&scheme=light answered HTTP ${stitchNav.status()}`
      + ' -- the 20261023 palette is unreachable even by its own URL');
  else {
    await waitForProbe(stitchPage, 'the stitch deep link', findings);
    const landed = await readOn(stitchPage, 'loadedFromStitchUrl');
    deepLink.palette = landed.palette;
    deepLink.scheme = landed.scheme;
    deepLink.ink = landed.probe.color;
    deepLink.backdrop = landed.probe.opaqueBg;
    deepLink.bgChain = landed.probe.bgChain;
    if (landed.palette !== 'stitch')
      findings.push(`the deep link asked for palette=stitch but <html> says ${landed.palette}`);
    if (landed.scheme !== 'light')
      findings.push(`the deep link asked for scheme=light but <html> says data-scheme=`
        + `${landed.scheme}; the pearl-white block is keyed on both attributes, so the page `
        + 'landed on the default sheet');
    const defaultInk = measures.plainBeforeClick.probe;
    const samePaint = landed.probe.color === defaultInk.color
      && landed.probe.bgChain.join('|') === defaultInk.bgChain.join('|');
    deepLink.paintsLikeDefault = samePaint;
    if (samePaint)
      findings.push('the stitch deep link paints the same ink and backdrop chain as the default '
        + `palette (${landed.probe.color}) -- one of the two token blocks is inert`);
  }
  await stitchPage.close();
}

// 6. the painted difference must be observable between the two palettes
const defaultSurface = measures.plainBeforeClick.surfaceVar || measures.plainBeforeClick.bodyBg;
const themedSurface = fromUrl.surfaceVar || fromUrl.bodyBg;
if (defaultSurface && defaultSurface === themedSurface
    && measures.plainBeforeClick.palette !== fromUrl.palette)
  findings.push(`the two palettes resolve to the same painted surface ${themedSurface} -- `
    + 'one of the two token blocks is inert');

await browser.close();

for (const h of hops) {
  console.log(`  HOP ${h.hop} ${h.palette}/${h.scheme} url=${h.url || '(none)'}`
    + ` ink=${h.ink} over=${h.backdrop || '(no opaque ancestor layer)'} probe="${h.probeText}"`
    + ` ratio=${h.changeRatio === null ? 'n/a' : h.changeRatio}`
    + ` moved=${h.moved ? 'yes' : 'NO'} chain=${h.bgChain.join(' | ')}`);
}
console.log(`  DEEPLINK status=${deepLink.status} landed=${deepLink.palette}/${deepLink.scheme}`
  + ` ink=${deepLink.ink} over=${deepLink.backdrop || '(none)'}`
  + ` paintsLikeDefault=${deepLink.paintsLikeDefault}`);

const subject = {
  bundle: 'apps/workbench/build/main.js',
  bundleSha256: createHash('sha256').update(readFileSync(path.join(REPO, 'apps/workbench/build/main.js'))).digest('hex'),
  style: 'apps/workbench/style.css',
  styleSha256: createHash('sha256').update(readFileSync(path.join(REPO, 'apps/workbench/style.css'))).digest('hex'),
  shell: 'apps/workbench/shell.ts',
  shellSha256: createHash('sha256').update(shellSource).digest('hex'),
  width,
};
const report = { kind: 'workbench-theme-affordance', schemaVersion: 'design-lab/browser-gate/v2',
  generatedAt: new Date().toISOString().slice(0, 19) + 'Z', subject, statuses, measures,
  paletteTable: PALETTE_TABLE, probe: { selector: PROBE_SELECTOR,
    note: 'ink over its own background chain; change judgement only' },
  math: MATH, hops, deepLink,
  aaAuthority: 'design-lab/tests/e2e/audit_workbench_contrast.mjs',
  findings };
if (outPath) {
  mkdirSync(path.dirname(outPath), { recursive: true });
  writeFileSync(outPath, JSON.stringify(report, null, 1) + '\n');
}
console.log('AFF_SUMMARY findings=' + findings.length
  + ' table=' + JSON.stringify(TABLE_IDS)
  + ' landed=' + JSON.stringify(Array.from(new Set(hops.map((h) => h.palette))))
  + ' statuses=' + JSON.stringify(statuses)
  + ' plain=' + measures.plainBeforeClick.palette + '/' + measures.plainBeforeClick.scheme
  + ' afterClick=' + (measures.afterPaletteClick || {}).palette
  + ' fromUrl=' + fromUrl.palette + '/' + fromUrl.scheme
  + ' surface ' + defaultSurface + ' -> ' + themedSurface);
for (const f of findings) console.log('  FINDING: ' + f);
if (findings.length) { console.error('AFF_DONE=FAIL findings=' + findings.length); process.exit(1); }
console.log('AFF_OK');
