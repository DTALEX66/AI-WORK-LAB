// SPDX-License-Identifier: MIT
// W14 runtime sampler (browser half). Driven by w14-runtime-sampling.py, which owns
// the real loopback service and passes W14_SERVICE_URL / W14_TOKEN.
//
// Measures the three things the pack asks to sample FIRST, and nothing else:
//   A. local first-interactive time
//   B. hot-route interaction latency, P50/P95 over all 12 routes
//   C. the 1920x1080 / 2560x1440 x 100/125/150/200% matrix: horizontal overflow and
//      elements pushed off-screen
//
// Measurement-integrity notes (each is a trap this session has already hit):
//   - `#route-view` carries aria-busy while a view renders; a click handler sets it in
//     the same task, so we must yield a frame BEFORE waiting for it to clear, otherwise
//     the "settled" read races the handler and reports ~0 ms.
//   - Closed overlays are INTENTIONALLY off-screen (.drawer{right:-540px},
//     .palette/.toast/.overlay hidden) and .ambient is decoration. They are whitelisted
//     explicitly; an earlier harness of mine reported them as defects.
//   - An element inside an ancestor with overflow-x auto/scroll/hidden is clipped or
//     scrollable by design, so it is not an overflow defect.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);

const URL_BASE = process.env.W14_SERVICE_URL;
const TOKEN = process.env.W14_TOKEN;
const BROWSER = process.env.W14_BROWSER;
const OUT = process.env.W14_OUT;
if (!URL_BASE || !TOKEN || !BROWSER || !OUT) {
  console.error('missing env (W14_SERVICE_URL/W14_TOKEN/W14_BROWSER/W14_OUT)');
  process.exit(2);
}
const base = URL_BASE.replace(/\/$/, '');
const ROUTE_SAMPLES = 5;
const VIEWPORTS = [[1920, 1080], [2560, 1440]];
const SCALES = [1, 1.25, 1.5, 2];

const result = {
  kind: 'design-lab-w14-runtime-sampling',
  service_url: base,
  browser: BROWSER,
  chromium_version: null,
  hot_route_samples_per_route: ROUTE_SAMPLES,
  measured_at: new Date().toISOString(),
  first_interactive_ms: null,
  navigation_timing: null,
  hot_route: {},
  hot_route_summary: null,
  viewport_scale_matrix: [],
  console_errors: [],
  page_errors: [],
};

const browser = await chromium.launch({ executablePath: BROWSER, headless: true });
result.chromium_version = browser.version();

// Connect once per context: each fresh context has no service token in memory.
async function connect(page) {
  await page.goto(base + '/workbench', { waitUntil: 'load' });
  await page.locator('#token').fill(TOKEN);
  await page.locator('#connect-form button').first().click();
  await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
  await page.waitForTimeout(400);
}

// ---- A. first interactive -----------------------------------------------------
{
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') result.console_errors.push(m.text()); });
  page.on('pageerror', (e) => result.page_errors.push(String(e)));
  const t0 = Date.now();
  await page.goto(base + '/workbench', { waitUntil: 'load' });
  // interactive := the login control exists and accepts input
  await page.locator('#token').waitFor({ state: 'visible', timeout: 20000 });
  await page.locator('#token').fill('probe');
  result.first_interactive_ms = Date.now() - t0;
  result.navigation_timing = await page.evaluate(() => {
    const n = performance.getEntriesByType('navigation')[0];
    const fcp = performance.getEntriesByType('paint').find((p) => p.name === 'first-contentful-paint');
    return n ? {
      dom_content_loaded_ms: Math.round(n.domContentLoadedEventEnd),
      load_event_ms: Math.round(n.loadEventEnd),
      response_start_ms: Math.round(n.responseStart),
      first_contentful_paint_ms: fcp ? Math.round(fcp.startTime) : null,
    } : null;
  });
  await ctx.close();
}

// ---- B. hot-route interaction latency -----------------------------------------
// In-page settle probe. Returns ms from click to "view rendered".
//
// WHY A MutationObserver AND NOT rAF POLLING (first attempt was invalid):
// the first version clicked, yielded 2 frames and then watched aria-busy. On localhost
// the whole render can finish BEFORE the first frame, so aria-busy was observed on only
// 1 of 60 samples; 11 of 12 routes fell into a 3-frame fallback (~50 ms), and every
// route then reported a suspiciously tight 53-82 ms. That is the measurement FLOOR, not
// render time -- the numbers looked like a healthy result while measuring nothing.
// The observer watches the real mutations and reports whether it saw the busy/loading
// phase at all, so an invalid sample is visible as such instead of silently plausible.
// The `workbench` route does NOT render into `#route-view`: show() treats it specially
// (`showWorkbench` -> it just toggles the legacy #workspace/#login regions and returns
// before any render). A #route-view observer therefore never settles for it and every
// sample times out at 5 s. That is a property of the app, not a defect -- so it is
// measured as what it actually is (a synchronous visibility toggle, no data fetch) and
// excluded from the render-latency aggregate rather than polluting it with timeouts.
const LEGACY_ROUTES = new Set(['workbench']);

const settleProbe = ({ route, mode }) => {
  const rv = document.getElementById('route-view');
  const btn = [...document.querySelectorAll('.app-nav-item')].find((b) => b.dataset.route === route);
  if (!rv || !btn) return Promise.resolve(null);
  const raf = () => new Promise((r) => requestAnimationFrame(r));
  if (mode === 'visibility-toggle') {
    const ws = document.getElementById('workspace');
    const before = ws ? ws.hasAttribute('hidden') : null;
    return (async () => {
      const t0 = performance.now();
      btn.click();
      await raf(); await raf();
      return { ms: performance.now() - t0, via: 'visibility', observed: true,
               kind: 'visibility-toggle', hidden_before: before,
               hidden_after: ws ? ws.hasAttribute('hidden') : null };
    })();
  }
  const beforeLen = rv.innerHTML.length;
  return new Promise((resolve) => {
    let t0 = 0, sawBusy = false, sawLoading = false, settled = false;
    const finish = (via) => {
      if (settled) return;
      settled = true;
      obs.disconnect();
      requestAnimationFrame(() => resolve({
        ms: performance.now() - t0, via, sawBusy, sawLoading,
        observed: sawBusy || sawLoading,
        kind: 'route-view-render',
        changed: rv.innerHTML.length !== beforeLen,
      }));
    };
    const obs = new MutationObserver(() => {
      if (rv.getAttribute('aria-busy') === 'true') sawBusy = true;
      if (rv.querySelector('.view-loading')) sawLoading = true;
      if (sawBusy || sawLoading) {
        if (rv.getAttribute('aria-busy') !== 'true') finish('mutation');
      } else if (rv.innerHTML.length !== beforeLen) {
        finish('mutation');   // synchronous view: content changed without a busy phase
      }
    });
    obs.observe(rv, { childList: true, subtree: true, characterData: true, attributes: true });
    t0 = performance.now();
    btn.click();
    setTimeout(() => finish('timeout'), 5000);
  });
};

{
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => result.page_errors.push(String(e)));
  await connect(page);
  const routes = await page.evaluate(() => [...document.querySelectorAll('.app-nav-item')].map((b) => b.dataset.route));
  // Round-robin across routes instead of N clicks on the same one. Clicking the route
  // that is ALREADY active sets an unchanged location.hash, so no hashchange fires and
  // nothing re-renders: samples 2..N then hit the timeout, which is exactly what the
  // second run produced (11 of 12 routes timed out 4/5). Alternating also matches real
  // "hot route" usage, which is switching between views.
  for (let p = 0; p < ROUTE_SAMPLES; p++) {
    const order = p % 2 === 1 ? [...routes].reverse() : routes;
    for (const route of order) {
      // guarantee a real transition: if `route` is already showing, step away first
      await page.evaluate((r) => {
        const active = document.querySelector('.app-nav-item.active');
        if (active && active.dataset.route === r) {
          const other = [...document.querySelectorAll('.app-nav-item')].find((b) => b.dataset.route !== r);
          if (other) other.click();
        }
      }, route);
      await page.waitForTimeout(260);
      const mode = LEGACY_ROUTES.has(route) ? 'visibility-toggle' : 'route-view-render';
      const r = await page.evaluate(settleProbe, { route, mode });
      if (!r) continue;
      if (!result.hot_route[route]) {
        result.hot_route[route] = { kind: r.kind, samples_ms: [], p50_ms: null, p95_ms: null,
          validity: { samples_observed_phase: 0, samples_timed_out: 0, valid: false } };
      }
      const cell = result.hot_route[route];
      cell.samples_ms.push(Math.round(r.ms * 100) / 100);
      // one boolean per SAMPLE: a sample can see both the busy attribute and the loading
      // node, so summing two counters can exceed the sample count (the previous formula
      // made every valid route read as invalid).
      if (r.observed) cell.validity.samples_observed_phase++;
      if (r.via === 'timeout') cell.validity.samples_timed_out++;
      await page.waitForTimeout(120);
    }
  }
  for (const cell of Object.values(result.hot_route)) {
    cell.samples_ms.sort((a, b) => a - b);
    const s = cell.samples_ms;
    cell.p50_ms = s.length ? s[Math.floor(s.length * 0.5)] : null;
    cell.p95_ms = s.length ? s[Math.min(s.length - 1, Math.ceil(s.length * 0.95) - 1)] : null;
    const v = cell.validity;
    v.valid = s.length === ROUTE_SAMPLES && v.samples_timed_out === 0
      && (v.samples_observed_phase === s.length || cell.kind === 'visibility-toggle');
  }
  const renderRoutes = Object.entries(result.hot_route).filter(([k, v]) => v.kind === 'route-view-render');
  const all = renderRoutes.flatMap(([, r]) => r.samples_ms).sort((a, b) => a - b);
  const validRoutes = renderRoutes.filter(([, v]) => v.validity.valid).map(([k]) => k);
  result.hot_route_summary = all.length ? {
    scope: 'route-view render latency; the workbench route is excluded (see legacy_visibility_routes)',
    n: all.length,
    p50_ms: all[Math.floor(all.length * 0.5)],
    p95_ms: all[Math.min(all.length - 1, Math.ceil(all.length * 0.95) - 1)],
    max_ms: all[all.length - 1],
    target_p95_ms: 200,
    meets_target: all[Math.min(all.length - 1, Math.ceil(all.length * 0.95) - 1)] <= 200,
    routes_total: Object.keys(result.hot_route).length,
    routes_in_scope: renderRoutes.length,
    routes_valid: validRoutes.length,
    // A P95 over samples that never observed the async render phase is not evidence.
    trustworthy: validRoutes.length === renderRoutes.length,
    legacy_visibility_routes: Object.entries(result.hot_route)
      .filter(([, v]) => v.kind === 'visibility-toggle')
      .map(([k, v]) => ({ route: k, p95_ms: v.p95_ms, note: 'synchronous region toggle, no render into #route-view' })),
  } : null;
  await ctx.close();
}

// ---- C. viewport x scale matrix ------------------------------------------------
const layoutProbe = () => {
  const vw = window.innerWidth;
  const WHITELIST = ['.ambient', '.drawer', '.palette', '.toast', '.overlay'];
  const clipped = (el) => {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') return true;
    }
    return false;
  };
  const inWhitelist = (el) => WHITELIST.some((sel) => el.closest(sel));
  const offenders = [];
  for (const el of document.querySelectorAll('.app *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') continue;
    if (inWhitelist(el) || clipped(el)) continue;
    if (r.right > vw + 1 || r.left < -1) {
      offenders.push({
        tag: el.tagName.toLowerCase(),
        cls: (typeof el.className === 'string' ? el.className : '').slice(0, 60),
        left: Math.round(r.left), right: Math.round(r.right), vw,
      });
      if (offenders.length >= 12) break;
    }
  }
  const de = document.documentElement;
  const content = document.querySelector('.content');
  const app = document.querySelector('.app');
  const appDisplay = app ? getComputedStyle(app).display : null;
  return {
    inner_width: vw,
    // CRITICAL validity field: on the default `workbench` route the B10 `.app` shell is
    // display:none (the legacy region is shown instead). Scanning `.app *` there finds
    // nothing and reports a false "clean" -- which is exactly how the first control
    // measured a 0x0 injected element. A cell whose shell is hidden is not a measurement.
    app_display: appDisplay,
    app_visible: appDisplay !== null && appDisplay !== 'none',
    doc_scroll_width: de.scrollWidth,
    horizontal_overflow: de.scrollWidth > vw + 1,
    body_scroll_width: document.body.scrollWidth,
    content_rect: content ? (() => { const r = content.getBoundingClientRect(); return { left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width) }; })() : null,
    content_within_viewport: content ? content.getBoundingClientRect().right <= vw + 1 : null,
    offenders,
  };
};

// Windows display scaling shrinks the CSS viewport; it does not change CSS layout.
// The first attempt set only deviceScaleFactor, which leaves innerWidth/scrollWidth
// untouched -- all 16 cells were therefore the SAME layout measured four times, and the
// "clean" result proved nothing. Faithful emulation: keep the physical screen and
// divide the CSS viewport by the scale (a 2560x1440 screen at 150% => 1707x960 CSS px).
for (const [pw, ph] of VIEWPORTS) {
  for (const dsf of SCALES) {
    const vp = { width: Math.round(pw / dsf), height: Math.round(ph / dsf) };
    const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: dsf });
    const page = await ctx.newPage();
    await connect(page);
    for (const route of ['dashboard', 'projects']) {
      await page.evaluate((r) => {
        const b = [...document.querySelectorAll('.app-nav-item')].find((x) => x.dataset.route === r);
        if (b) b.click();
      }, route);
      await page.waitForTimeout(700);
      const probe = await page.evaluate(layoutProbe);
      result.viewport_scale_matrix.push({
        physical_screen: `${pw}x${ph}`,
        scale_percent: Math.round(dsf * 100),
        css_viewport: `${vp.width}x${vp.height}`,
        route, ...probe,
      });
    }
    await ctx.close();
  }
}

// ---- C2. positive control for the layout probe ---------------------------------
// "0 offenders in 16 cells" is only meaningful if the probe CAN see an offender. The
// first control failed and thereby proved nothing: it appended a 3000px div into `.app`,
// which is a grid container, so the div got a zero-width grid track (measured width 0)
// and the document never overflowed. This version injects a `position:fixed` element
// that must exceed the viewport and runs THE SAME offender predicate the real probe uses,
// requiring the injected element to appear in the result.
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();
  await connect(page);
  // the control MUST run with the B10 shell visible: after connect the app sits on the
  // default `workbench` route, where `.app` is display:none and an injected element
  // measures 0x0 (that is why the first two controls "failed").
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.app-nav-item')].find((x) => x.dataset.route === 'dashboard');
    if (b) b.click();
  });
  await page.waitForTimeout(900);
  const control = await page.evaluate(() => {
    const offendersOf = (extra) => {
      const vw = window.innerWidth;
      const WHITELIST = ['.ambient', '.drawer', '.palette', '.toast', '.overlay'];
      const clipped = (el) => {
        for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
          const ox = getComputedStyle(p).overflowX;
          if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') return true;
        }
        return false;
      };
      const out = [];
      for (const el of document.querySelectorAll('.app *')) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') continue;
        if (WHITELIST.some((sel) => el.closest(sel)) || clipped(el)) continue;
        if (r.right > vw + 1 || r.left < -1) out.push(el.id || el.className || el.tagName);
      }
      return { count: out.length, sample: out.slice(0, 5), vw };
    };
    const baseline = offendersOf();
    const d = document.createElement('div');
    d.id = '__w14_overflow_control';
    d.className = 'w14-overflow-control';
    d.style.position = 'fixed';
    d.style.left = '100%';       // starts exactly at the viewport edge
    d.style.top = '0';
    d.style.width = '200px';     // => right edge vw+200, unambiguously off-screen
    d.style.height = '20px';
    d.textContent = 'control';
    document.querySelector('.app').appendChild(d);
    const r = d.getBoundingClientRect();
    const after = offendersOf();
    const detected = after.count > baseline.count && after.sample.includes('__w14_overflow_control');
    d.remove();
    return {
      shell_display: getComputedStyle(document.querySelector('.app')).display,
      baseline_offenders: baseline.count,
      with_control_offenders: after.count,
      control_rect: { left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width) },
      control_detected: detected,
    };
  });
  result.layout_probe_control = {
    ...control,
    note: 'injected position:fixed element extending 200px past the viewport must appear in the offender list; if it does not, the 0-offender matrix is a detector blind spot rather than a clean result',
  };
  await ctx.close();
}

const fs = await import('node:fs');
fs.writeFileSync(OUT, JSON.stringify(result, null, 2), 'utf8');
console.log(`W14 sampler wrote ${OUT}`);
await browser.close();
