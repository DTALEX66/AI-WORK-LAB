// SPDX-License-Identifier: MIT
// Workbench motion gate — is the primary motion actually composited, as Chromium parses it?
//
// Env: E2E_SERVICE_URL E2E_NODE_MODULES [E2E_BROWSER] [MOTION_OUT=<json path>] [MOTION_WIDTH=1440]
//
// Why this gate exists. `packages/capabilities/standards/MOTION_ACCESSIBILITY.md` states rule
// SRC-T07-MOTION-COMPOSITED: primary motion animates only `transform` and `opacity`; the
// layout-triggering properties (`width`, `height`, `top`, `left`, `right`, `bottom`, `margin*`,
// `padding*`) must not be animated. That rule was already checked over the shipped text by
// `design-lab/scripts/verify_selected_source_adaptation.py`, which greps `transition:` and
// `animation:` declarations in seven files. A grep cannot see three things a browser can: what
// Chromium's CSSOM actually parsed (including inside `@media` and `@supports`), what the
// `@keyframes` blocks animate, and what an element's computed style ends up carrying after the
// bundle has run. This gate measures those, so "the landing is consumed" means the page was
// rendered and read, not that a file matched a pattern.
//
// Deliberately the SAME banned property set as the text gate. Two gates owning one rule with two
// different definitions is how a byte goes red in one rollup and green in the other.
//
// Not convicted here, and said out loud rather than hidden: `transition: all` and properties like
// `stroke-dashoffset` are counted and reported, not failed, because the rule names layout
// properties and this gate does not invent a stricter standard than the one it claims to consume.
// This is E2 controlled-runtime measurement of the built bundle: no host run, no human visual
// jury, and no claim that the motion looks good.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';

const serviceUrl = process.env.E2E_SERVICE_URL;
const nmDir = process.env.E2E_NODE_MODULES;
const browserPath = process.env.E2E_BROWSER || undefined;
const outPath = process.env.MOTION_OUT || '';
const width = Number.parseInt(process.env.MOTION_WIDTH || '1440', 10) || 1440;

const fail = (reason) => { console.error('MA_FAIL: ' + reason); process.exit(2); };
if (!serviceUrl || !nmDir) fail('MA_CONFIG_MISSING');

const req = createRequire(nmDir + '/noop.js');
const { chromium } = req('playwright');

const REPO = process.cwd();
const STYLE = path.join(REPO, 'apps/workbench/style.css');
const BUNDLE = path.join(REPO, 'apps/workbench/build/main.js');
const digest = (file) => createHash('sha256').update(readFileSync(file)).digest('hex');

// One scanner, run against the live page and against the planted control, so the plant proves that
// the code which ran on the product is code which can fail.
const SCAN = () => {
  const layout = new Set(['width', 'height', 'top', 'left', 'right', 'bottom']);
  const isLayout = (prop) => {
    const name = String(prop == null ? '' : prop).trim().toLowerCase();
    if (!name || name === 'none') return false;
    if (layout.has(name)) return true;
    return name === 'margin' || name === 'padding'
      || name.startsWith('margin-') || name.startsWith('padding-');
  };
  const read = (v) => (v == null ? '' : String(v));
  const out = {
    violations: [], transitionAll: [], otherAnimated: [],
    coverage: { sheets: 0, unreadableSheets: 0, styleRules: 0, keyframeRules: 0,
      keyframeSteps: 0, elements: 0 },
    origins: { stylesheet: 0, computed: 0 },
  };
  const walk = (rules) => {
    for (const rule of rules || []) {
      // Chromium names a keyframe rule's steps `keyRules` (with `cssRules` as an alias), so the
      // branch is keyed on the rule TYPE; testing for a `keyFrames` property would silently send
      // every @keyframes block down the plain-rule path and read zero animated properties.
      const isKeyframes = rule.type === CSSRule.KEYFRAMES_RULE
        || (rule.constructor && rule.constructor.name === 'CSSKeyframesRule');
      if (isKeyframes) {
        out.coverage.keyframeRules += 1;
        const frameName = read(rule.name);
        for (const step of rule.cssRules || []) {
          out.coverage.keyframeSteps += 1;
          for (let i = 0; i < step.style.length; i += 1) {
            const prop = step.style.item(i);
            if (isLayout(prop)) {
              out.violations.push({ origin: 'stylesheet', property: prop,
                where: `@keyframes ${frameName} ${read(step.keyText)}`,
                declaration: `${prop}: ${read(step.style.getPropertyValue(prop))}` });
              out.origins.stylesheet += 1;
            } else if (prop !== 'transform' && prop !== 'opacity') {
              out.otherAnimated.push({ where: `@keyframes ${frameName}`, property: prop });
            }
          }
        }
        continue;
      }
      // A plain style rule is judged on its own declarations; nesting made `cssRules` a property
      // of CSSStyleRule too, so testing `rule.cssRules` first swallows every rule in the sheet and
      // the gate reports a clean page it never actually read.
      if (rule.style) {
        out.coverage.styleRules += 1;
        const selector = read(rule.selectorText).slice(0, 120);
        const names = read(rule.style.transitionProperty).split(',');
        const animated = read(rule.style.animationName);
        if (names.some((p) => p.trim().toLowerCase() === 'all')) {
          out.transitionAll.push({ where: selector, declaration: 'transition: all' });
        }
        for (const prop of names) {
          if (!isLayout(prop)) continue;
          out.violations.push({ origin: 'stylesheet', property: prop.trim(), where: selector,
            declaration: `transition-property: ${read(rule.style.transitionProperty)}` });
          out.origins.stylesheet += 1;
        }
        if (animated) {
          out.otherAnimated.push({ where: selector, property: `animation-name:${animated}` });
        }
      }
      if (rule.cssRules && rule.cssRules.length && !rule.style) walk(rule.cssRules);
    }
  };
  // Measured in this Chromium build (2026-10-22): `document.styleSheets` does NOT list the
  // document's adopted (constructed) stylesheets, so reading only that list would let a page built
  // with `adoptedStyleSheets` scan clean. Both collections are walked, and neither is deduplicated
  // away, because a rule that reached the document twice is exactly the duplication worth seeing.
  const sheets = Array.from(document.styleSheets)
    .concat(Array.from(document.adoptedStyleSheets || []));
  for (const sheet of sheets) {
    out.coverage.sheets += 1;
    let rules = null;
    try { rules = sheet.cssRules; } catch { out.coverage.unreadableSheets += 1; }
    if (rules) walk(rules);
    out.coverage.sheetRules = (out.coverage.sheetRules || 0) + (rules ? rules.length : 0);
    out.sheets = (out.sheets || []).concat([{ href: String(sheet.href || ''),
      ownerNode: sheet.ownerNode ? sheet.ownerNode.tagName : '(adopted)',
      ruleCount: rules ? rules.length : -1 }]);
  }
  for (const el of document.querySelectorAll('body *')) {
    out.coverage.elements += 1;
    const cs = getComputedStyle(el);
    const names = read(cs.transitionProperty).split(',').filter(isLayout);
    if (names.length === 0) continue;
    const firstClass = (el.className && typeof el.className === 'string'
      && el.className.trim()) ? '.' + el.className.trim().split(/\s+/)[0] : '';
    out.violations.push({ origin: 'computed', property: names.join(','),
      where: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + firstClass,
      declaration: `computed transition-property: ${read(cs.transitionProperty)}` });
    out.origins.computed += 1;
  }
  return out;
};

const PLANT = '@keyframes dlMotionPlant{from{width:10px}to{width:20px}}'
  + '.dl-motion-plant{transition:width 200ms ease}';

const browser = await chromium.launch({ executablePath: browserPath, headless: true,
  args: ['--no-sandbox'] });
let totalViolations = [];
let plant = null;
try {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  await page.goto(serviceUrl.replace(/\/$/, '') + '/workbench', { waitUntil: 'load' });
  await page.waitForSelector('.app-nav', { timeout: 20000 });
  // The routes are the nav the bundle actually painted, read by clicking it -- not a list copied
  // into this file. A nav item whose hash the router ignores therefore shows up here as a view the
  // scanner never reached, rather than as a green run over a route nobody visits.
  const navItems = page.locator('.app-nav-item');
  const navCount = await navItems.count();
  if (navCount === 0) fail('MA_NO_NAV_ITEMS');

  const report = {
    kind: 'workbench-motion-e2',
    subject: { styleSha256: digest(STYLE), bundleSha256: digest(BUNDLE),
      styleBytes: readFileSync(STYLE).length, bundleBytes: readFileSync(BUNDLE).length },
    rule: 'SRC-T07-MOTION-COMPOSITED',
    standard: 'packages/capabilities/standards/MOTION_ACCESSIBILITY.md',
    viewport: { width, height: 900 },
    routes: {},
  };
  const seen = {};
  const scanHere = async (label) => {
    const result = await page.evaluate(SCAN);
    seen[label] = { violations: result.violations, coverage: result.coverage,
      transitionAll: result.transitionAll.length, otherAnimated: result.otherAnimated.length };
    if (label === '(first paint)') report.firstPaintSheets = result.sheets;
    totalViolations = totalViolations.concat(result.violations);
    return result;
  };
  await scanHere('(first paint)');
  const hashes = new Set();
  for (let index = 0; index < navCount; index += 1) {
    const item = navItems.nth(index);
    const info = await item.evaluate((el) => ({
      view: el.dataset.route || '', label: (el.textContent || '').trim(),
    }));
    if (info.view) {
      // The shipped handler is what moves the app, and it is invoked, not simulated: Playwright's
      // actionability wait is the overflow gate's business, not this one's.
      await item.evaluate((el) => { el.click(); });
      await page.waitForFunction(() => document.readyState === 'complete', null,
        { timeout: 10000 }).catch(() => false);
      await page.waitForTimeout(200);
    }
    const hash = await page.evaluate(() => window.location.hash);
    hashes.add(hash);
    await scanHere(`${info.label} ${hash}`);
  }
  report.navItemCount = navCount;
  report.distinctHashes = Array.from(hashes).sort();
  if (report.distinctHashes.length < 10) {
    fail(`MA_NAV_NOT_MOVED: ${navCount} nav items were clicked but the router reached only `
         + `${report.distinctHashes.length} locations (${report.distinctHashes.join(' ')}); `
         + 'a single-view scan is not a walk over the product');
  }

  // The control, run last so it cannot contaminate a measured route: the same scanner has to
  // convict a planted layout motion on the same live document. It is planted as a constructed
  // stylesheet rather than a <style> element because the Workbench's own CSP says
  // `style-src 'self'` and inline style is refused -- and a gate that had to loosen the product's
  // policy to prove itself would be measuring a page the user never gets.
  const before = totalViolations.length;
  const plantState = await page.evaluate(([css]) => {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(css);
    document.adoptedStyleSheets = document.adoptedStyleSheets.concat([sheet]);
    return { adopted: document.adoptedStyleSheets.length, sheets: document.styleSheets.length,
      rules: document.adoptedStyleSheets.length
        ? document.adoptedStyleSheets[document.adoptedStyleSheets.length - 1].cssRules.length : -1,
      cspBlocked: false };
  }, [PLANT]).catch((error) => ({ cspBlocked: true, error: String(error).slice(0, 200) }));
  const after = await page.evaluate(SCAN);
  plant = {
    declared: PLANT,
    state: plantState,
    convicted: after.violations.filter((v) => /dlMotionPlant|dl-motion-plant/.test(v.where)),
    addedViolations: totalViolations.length - before,
  };
  await page.close();

  const unique = [];
  const keys = new Set();
  for (const v of totalViolations) {
    const key = `${v.origin}|${v.where}|${v.property}`;
    if (keys.has(key)) continue;
    keys.add(key);
    unique.push(v);
  }
  // The plant's own findings are excluded from the shipped count: they were injected after the
  // last route was read, and a receipt that counted them would report a fault the product does not
  // have. The scan that found them is the point of the plant, not a violation of the standard.
  const shipped = unique.filter((v) => !/dlMotionPlant|dl-motion-plant/.test(v.where));
  report.routes = seen;
  report.routeCount = Object.keys(seen).length;
  report.coverageTotals = Object.values(seen).reduce((all, one) => {
    all.styleRules += one.coverage.styleRules;
    all.keyframeRules += one.coverage.keyframeRules;
    all.keyframeSteps += one.coverage.keyframeSteps;
    all.elements += one.coverage.elements;
    return all;
  }, { styleRules: 0, keyframeRules: 0, keyframeSteps: 0, elements: 0 });
  report.rawViolationCount = totalViolations.length;
  report.violationCount = shipped.length;
  report.violations = shipped.slice(0, 20);
  report.transitionAllCount = Object.values(seen).reduce((n, one) => n + one.transitionAll, 0);
  report.otherAnimatedCount = Object.values(seen)
    .reduce((n, one) => n + one.otherAnimated, 0);
  report.selfTest = { convictedCount: plant.convicted.length, plant: PLANT };

  if (outPath) writeFileSync(outPath, JSON.stringify(report, null, 2) + '\n');
  console.log('MA_SUMMARY ' + JSON.stringify({
    routes: report.routeCount, navItems: report.navItemCount,
    distinctHashes: report.distinctHashes.length,
    styleRules: report.coverageTotals.styleRules,
    keyframes: report.coverageTotals.keyframeRules, elements: report.coverageTotals.elements,
    violations: report.violationCount, transitionAll: report.transitionAllCount,
    otherAnimated: report.otherAnimatedCount, plant: plant.convicted.length,
  }));

  if (report.violationCount) {
    for (const v of report.violations.slice(0, 10)) {
      console.error(`MA_LAYOUT_MOTION ${v.origin} ${v.where} -> ${v.property} (${v.declaration})`);
    }
    fail(`MA_LAYOUT_MOTION ${report.violationCount} animated layout propert` +
         (report.violationCount === 1 ? 'y' : 'ies'));
  }
  // Three findings are expected from one plant: the `from` step, the `to` step, and the rule.
  // Anything less means the CSSOM walk or the computed walk stopped seeing the document, and a
  // zero-violation product run would then be an artefact of a blind scanner.
  if (plant.convicted.length < 3) {
    fail('MA_SELF_TEST_INCONCLUSIVE: the planted layout transition was not fully convicted, '
        + 'so a zero-violation run proves nothing. '
        + JSON.stringify({ convicted: plant.convicted, added: plant.addedViolations,
          state: plant.state, after: after.coverage }));
  }
  console.log('MA_OK plant_convicted=' + plant.convicted.length
    + ' shipped_violations=0 routes=' + report.routeCount);
} catch (error) {
  if (outPath) {
    writeFileSync(outPath, JSON.stringify({ kind: 'workbench-motion-e2', result: 'FAIL',
      error: String(error && error.message || error), selfTest: plant }, null, 2) + '\n');
  }
  fail('MA_ERROR ' + String(error && error.message || error).split('\n')[0]);
} finally {
  await browser.close();
}
