// SPDX-License-Identifier: MIT
// Quantitative Workbench UI audit against the real service and a real Chromium.
// Measures what the eye claims: overflow, contrast, keyboard reachability,
// touch targets, accessible names, degraded-state wording and console noise,
// then fails closed on any hard violation so the numbers cannot drift silently.
// Env: E2E_SERVICE_URL E2E_TOKEN E2E_NODE_MODULES [E2E_BROWSER] AUDIT_WIDTHS
import { createRequire } from 'node:module';
import process from 'node:process';

const serviceUrl = process.env.E2E_SERVICE_URL;
const token = process.env.E2E_TOKEN;
const nmDir = process.env.E2E_NODE_MODULES;
const browser = process.env.E2E_BROWSER;
if (!serviceUrl || !token || !nmDir) {
  console.error('AUDIT_CONFIG_MISSING');
  process.exit(2);
}
const widths = (process.env.AUDIT_WIDTHS || '1280,1920,2560')
  .split(',').map((w) => Number.parseInt(w, 10)).filter(Number.isFinite);
// Heights are the CSS viewport each width is judged at. 2048x1152 is not an arbitrary
// large desktop: it is the owner's own machine measured this round
// (Win32_VideoController/Screen.Bounds = 2048x1152 logical, WorkingArea 2048x1104,
// AppliedDPI 120 i.e. 125% scaling on a 2560x1440 panel). The browser sees 2048 CSS px,
// so 2560 is the panel, not the render box, and no gate measured the width the product
// is actually used at.
const HEIGHT = { 390: 844, 768: 1024, 1280: 800, 1920: 1080, 2048: 1152, 2560: 1440 };

const pw = createRequire(nmDir + '/noop.js')('playwright');
const launchOpts = { headless: true };
if (browser) launchOpts.executablePath = browser;

const violations = [];
const metrics = [];
const notes = {};
const add = (kind, detail) => violations.push(`${kind}: ${detail}`);

const b = await pw.chromium.launch(launchOpts);

// In-page measurement: contrast is computed from the used colour values,
// walking up for a non-transparent background the way a browser paints it.
const PROBE = () => {
  // A closed `<details>` keeps layout boxes for content Chromium does not paint, so reachability,
  // legibility and geometry are all judged in the state a person can actually reach. The count is
  // reported so a wrapper can tell "nothing was collapsed here" from "this expansion step went
  // away and the numbers describe invisible layout again".
  const expanded = document.querySelectorAll('details:not([open])').length;
  for (const host of document.querySelectorAll('details:not([open])')) host.open = true;
  const lum = (c) => {
    const [r, g, bl] = c.map((v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const parse = (value) => {
    const m = value.match(/-?[\d.]+/g);
    if (!m) return null;
    const nums = m.slice(0, 3).map(Number);
    return (m.length > 3 && Number(m[3]) === 0) ? null : nums;
  };
  const bgOf = (el) => {
    let node = el;
    while (node) {
      const style = getComputedStyle(node);
      // A gradient lives in background-image, so backgroundColor is transparent
      // and walking further up compares the text against a surface nobody sees.
      // Those pairs are NOT measurable from computed styles: report them as
      // indeterminate instead of inventing a pass or a fail. Their ratios are
      // asserted statically against the exact gradient stops in style.css.
      if (style.backgroundImage && style.backgroundImage !== 'none') return null;
      const colour = parse(style.backgroundColor);
      if (colour) return colour;
      node = node.parentElement;
    }
    return [255, 255, 255];
  };
  const ratio = (a, c) => {
    const l1 = lum(a);
    const l2 = lum(c);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };
  const text = (el) => (el.textContent || '').trim();
  // An element inside a `hidden` ancestor keeps its own `display` value, so
  // checking the element alone measures text nobody can see. Layout boxes are
  // the only honest "is this rendered" test.
  const rendered = (el) => el.getClientRects().length > 0;
  const contrast = [];
  let gradientBacked = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (!text(el) || el.children.length || !rendered(el)) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden') continue;
    if (Number(style.opacity) < 0.35) continue;
    const fg = parse(style.color);
    if (!fg) continue;
    const bg = bgOf(el);
    if (bg === null) { gradientBacked += 1; continue; }
    const size = parseFloat(style.fontSize) || 16;
    const bold = Number(style.fontWeight) >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    const got = ratio(fg, bg);
    if (got < need) {
      contrast.push({ tag: el.tagName.toLowerCase(), size: Math.round(size),
                      need, got: Number(got.toFixed(2)),
                      text: text(el).slice(0, 40) });
    }
  }
  const focusables = Array.from(document.querySelectorAll(
    'a[href],button,input,select,textarea,[tabindex]')).filter(rendered);
  const clickables = Array.from(document.querySelectorAll('body *'))
    .filter((el) => (el.onclick || el.getAttribute('onclick')) && rendered(el));
  const clickableNotReachable = clickables.filter((el) => {
    if (['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) return false;
    if (el.getAttribute('role') === 'button') return false;
    const tabindex = el.getAttribute('tabindex');
    return tabindex === null || Number(tabindex) < 0;
  }).map((el) => `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}`
    + `${el.className ? '.' + String(el.className).split(' ')[0] : ''}`);
  const unnamed = Array.from(document.querySelectorAll('input,select,textarea'))
    .filter(rendered)
    .filter((el) => {
      if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return false;
      if (el.labels && el.labels.length) return false;
      const id = el.id;
      return !(id && document.querySelector(`label[for="${id}"]`));
    }).map((el) => `${el.tagName.toLowerCase()}#${el.id || '(no-id)'}`);
  const images = Array.from(document.querySelectorAll('img'))
    .filter((el) => rendered(el) && !el.hasAttribute('alt')).length;
  const overflow = document.documentElement.scrollWidth
    - Math.min(window.innerWidth, document.documentElement.clientWidth);
  // The count alone was not actionable: the audit reported "1 target under 24px"
  // on every route at 390 for a whole run without naming the element, so the
  // violation could be seen but not fixed. Identity and measured box travel together now.
  const smallTargets = Array.from(document.querySelectorAll(
    'button,a[href],input,select,[role="button"]'))
    .filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && (r.height < 24 || r.width < 24);
    })
    .map((el) => {
      const r = el.getBoundingClientRect();
      const cls = typeof el.className === 'string' && el.className.trim()
        ? '.' + el.className.trim().split(/\s+/).join('.') : '';
      const text = (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 18);
      return `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${cls} `
        + `${Math.round(r.width)}x${Math.round(r.height)} "${text}"`;
    });
  const targets = smallTargets.length;
  // A project picker with exactly one real option and nothing selected is a dead
  // end, not a choice: the readback already named the only project there is.
  const pickers = Array.from(document.querySelectorAll('select.project-select'))
    .filter(rendered)
    .map((el) => ({ id: el.id || '(no-id)',
                    real: Array.from(el.options).filter((o) => o.value).length,
                    selected: !!el.value }));
  // ARIA in HTML does not permit `dialog` on a landmark element: `<aside role="dialog">`
  // was what the external axe run could not grade (`aria-allowed-role`, unevaluated, on
  // every screen). The pair is asserted here so it cannot come back silently, and the
  // accessible name is asserted with it because removing a role must not remove the name.
  const landmarkDialog = Array.from(document.querySelectorAll(
    'aside[role="dialog"],main[role="dialog"],nav[role="dialog"],'
    + 'section[role="dialog"],form[role="dialog"]'))
    .map((el) => `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}[role=dialog]`);
  const drawer = document.querySelector('#drawer');
  return {
    detailsExpanded: expanded,
    contrast, clickableNotReachable, unnamed, images, overflow, targets,
    targetDetail: smallTargets,
    pickers,
    landmarkDialog,
    drawer: drawer ? { role: drawer.getAttribute('role'),
                       name: (drawer.getAttribute('aria-label') || '').trim() } : null,
    gradientBacked,
    focusables: focusables.length,
    paint: Math.round(performance.getEntriesByType('paint')
      .find((e) => e.name === 'first-contentful-paint')?.startTime ?? -1),
  };
};

// Same-document hash change. `page.goto` with a fragment can force a document
// reload, and the session token lives only in page memory (shell.ts keeps it in
// a closure), so a reload would silently swap every view for the
// "请先…连接" placeholder and the audit would measure a shell instead of a UI.
const navigate = async (page, hash) => {
  await page.evaluate((value) => { window.location.hash = value; }, hash);
  await page.waitForFunction(() => {
    const view = document.querySelector('#route-view');
    return !!view && !view.querySelector('.view-loading');
  }, null, { timeout: 20000 });
};

// Every measurement must describe a LIVE view. Anything else is no evidence.
const assertLive = async (page, width, route) => {
  const state = await page.evaluate(() => {
    const view = document.querySelector('#route-view');
    const workspace = document.querySelector('#workspace');
    const login = document.querySelector('#login');
    return {
      hasView: !!view,
      placeholder: /请先在工作台连接本机设计服务/.test(view ? view.textContent : ''),
      readFailed: /视图读回失败/.test(view ? view.textContent : ''),
      workspaceVisible: !!workspace && !workspace.hidden,
      loginVisible: !!login && !login.hidden,
    };
  });
  // The empty-hash route owns #workspace; hash routes own #route-view.
  const live = route === '' ? state.workspaceVisible && !state.loginVisible
                             : state.hasView && !state.placeholder;
  if (!live) {
    add('measurement-invalid', `${width} ${route || '(workbench)'} was not a live view: `
      + JSON.stringify(state));
    return false;
  }
  if (state.readFailed) add('view-readback-failure',
                            `${width} ${route || '(workbench)'} ${state.readFailed}`);
  return true;
};

// WCAG 2.4.1 bypass block. The link used to live inside legacy <main> and point at
// #content inside the hidden B10 `.app`: on the legacy view it jumped into a hidden
// subtree and rewrote the hash to a non-route, and on every routed view the link was
// hidden together with its parent. Focus it (the :focus rule makes it visible),
// activate it with Enter, and require the ONE visible content region with an
// unchanged route.
const skipLinkLands = async (page, width, route) => {
  const label = route || '(workbench)';
  const before = await page.evaluate(() => {
    const link = document.querySelector('a.skip-link');
    if (!link) return null;
    link.focus();
    const r = link.getBoundingClientRect();
    const style = getComputedStyle(link);
    const hidden = (node) => {
      for (let n = node; n; n = n.parentElement) if (n.hidden) return n.id || n.tagName;
      return null;
    };
    return {
      hash: window.location.hash,
      focused: document.activeElement === link,
      hiddenAncestor: hidden(link),
      onscreen: r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0
        && r.right <= innerWidth && r.bottom <= innerHeight,
      display: style.display,
      visibility: style.visibility,
    };
  });
  if (!before) {
    add('skip-link', `${width} ${label} has no a.skip-link`);
    return;
  }
  if (!before.focused) add('skip-link', `${width} ${label} skip link cannot take focus`);
  if (before.hiddenAncestor) {
    add('skip-link', `${width} ${label} skip link is inside hidden ${before.hiddenAncestor}`);
  }
  if (before.display === 'none' || before.visibility === 'hidden' || !before.onscreen) {
    add('skip-link', `${width} ${label} focused skip link is not on screen`
      + ` (${before.display}/${before.visibility})`);
  }
  await page.keyboard.press('Enter');
  const after = await page.evaluate(() => {
    const active = document.activeElement;
    const hidden = (node) => {
      for (let n = node; n; n = n.parentElement) if (n.hidden) return n.id || n.tagName;
      return null;
    };
    const r = active ? active.getBoundingClientRect() : null;
    return {
      hash: window.location.hash,
      id: active ? active.id : '',
      tag: active ? active.tagName : '',
      hiddenAncestor: active ? hidden(active) : null,
      size: r ? { w: r.width, h: r.height } : null,
    };
  });
  const expected = route === '' ? 'workspace' : 'content';
  if (after.hash !== before.hash) {
    add('skip-link', `${width} ${label} activating the skip link changed the route`
      + ` ${before.hash || '(empty)'} -> ${after.hash}`);
  }
  if (after.id !== expected) {
    add('skip-link', `${width} ${label} skip link landed on`
      + ` ${after.tag || 'nothing'}${after.id ? '#' + after.id : ''}, expected #${expected}`);
  }
  if (after.hiddenAncestor) {
    add('skip-link', `${width} ${label} skip target #${after.id || '?'}`
      + ` is inside hidden ${after.hiddenAncestor}`);
  }
  if (!after.size || after.size.w <= 0 || after.size.h <= 0) {
    add('skip-link', `${width} ${label} skip target #${after.id || '?'} has no box`);
  }
};

const connect = async (width) => {
  const ctx = await b.newContext({ viewport: { width, height: HEIGHT[width] ?? 900 } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => add('pageerror', `${width} ${String(e).slice(0, 120)}`));
  page.on('console', (m) => {
    if (m.type() === 'error') add('console-error', `${width} ${m.text().slice(0, 120)}`);
  });
  await page.goto(serviceUrl + '/workbench', { waitUntil: 'load' });
  // WCAG 2.4.1 also requires the bypass link to be the FIRST Tab stop. This is a
  // fresh document, so the sequential focus starting point is the top of the page.
  await page.keyboard.press('Tab');
  const firstStop = await page.evaluate(() => {
    const el = document.activeElement;
    return { tag: el ? el.tagName : '', cls: el ? String(el.className || '') : '',
             id: el ? el.id : '' };
  });
  if (firstStop.tag !== 'A' || !firstStop.cls.split(/\s+/).includes('skip-link')) {
    add('skip-link', `${width} first Tab stop is ${firstStop.tag || 'nothing'}`
      + `${firstStop.id ? '#' + firstStop.id : ''} (${firstStop.cls}) instead of the skip link`);
  }
  await page.locator('#token').fill(token);
  await page.locator('#connect-form button').first().click();
  await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
  return { ctx, page };
};

// --- bootstrap real state so the panels have something true to show ---------
const { ctx: bootCtx, page: boot } = await connect(1280);
await boot.locator('#project-name').fill('UI Audit ' + Date.now());
await boot.locator('#create-form button').first().click();
await boot.locator('#project option').last().waitFor({ state: 'attached', timeout: 20000 });
await boot.locator('#project').selectOption({ index: 1 });
const projectId = await boot.locator('#project').inputValue();
await boot.locator('#brief-title').fill('Audit brief');
await boot.locator('#brief-goals').fill('auditable, honest');
await boot.locator('#brief-submit').click();
await boot.locator('#design-briefs li').first().waitFor({ state: 'visible', timeout: 20000 });
await bootCtx.close();

// '' is the legacy workbench view, which is the only view that owns #workspace.
// prompt-intelligence and model-selection joined on 2026-10-20, the day they became reachable:
// the overflow and contrast sweeps already carried them, and leaving them out of this one meant
// their contrast floor, keyboard reachability and geometry were never measured anywhere.
const ROUTES = ['', '#/dashboard', '#/projects', `#/projects/${projectId}`, '#/tools',
                '#/deliverables', '#/evidence', '#/preflight', '#/settings',
                '#/research', '#/domains', '#/collaboration', '#/brand-systems',
                '#/prompts', '#/models', '#/knowledge', '#/assistant',
                // DL-KB-10 (2026-10-24): 目标组合选择面板。五条 /api/target-profile* 路由的第一
                // 次上屏；两栏对照、最多两条路线与五个选择框都在这一面，不进来就等于从没被量过。
                '#/target-profiles',
                // owner 2026-10-28 解冻自动化能力类后的自动化连接器屏。不进这几份清单
                // 就等于从没被这把闸渲染过，也就永远不会让它失败——这个覆盖洞
                // 2026-10-07 与本仓 §5.83 各记过一次。
                '#/automation'];

for (const width of widths) {
  const { ctx, page } = await connect(width);
  for (const route of ROUTES) {
    await navigate(page, route);
    if (!(await assertLive(page, width, route))) continue;
    await skipLinkLands(page, width, route);
    const probe = await page.evaluate(PROBE);
    metrics.push({ width, route: route || '(workbench)', ...probe });
    for (const item of probe.contrast) {
      add('contrast', `${width} ${route} <${item.tag}> ${item.got}:1 need ${item.need}:1 `
        + `size=${item.size} "${item.text}"`);
    }
    for (const item of probe.clickableNotReachable) {
      add('keyboard', `${width} ${route} click target not reachable: ${item}`);
    }
    for (const item of probe.unnamed) add('label', `${width} ${route} ${item}`);
    for (const p of probe.pickers) {
      if (p.real === 1 && !p.selected) {
        add('picker-dead-end', `${width} ${route} select#${p.id} offers exactly one `
          + 'project and has none selected, so the view shows its empty state');
      }
    }
    if (probe.images) add('alt', `${width} ${route} ${probe.images} img without alt`);
    if (probe.overflow > 0) add('overflow', `${width} ${route} +${probe.overflow}px`);
    for (const bad of probe.landmarkDialog) {
      add('role-permittedness', `${width} ${route} ${bad} -- a landmark element may not claim`
        + ' role="dialog" (ARIA in HTML); the external axe run could not grade this pair');
    }
    // `#drawer` is mounted on every view, so an absent reading is a broken measurement
    // rather than a pass. Its name must survive the role removal, or the region becomes
    // an anonymous landmark a screen reader cannot announce usefully.
    if (!probe.drawer) {
      add('role-permittedness', `${width} ${route} #drawer was not in the document`);
    } else {
      if (probe.drawer.role) {
        add('role-permittedness', `${width} ${route} #drawer carries role="${probe.drawer.role}"`);
      }
      if (!probe.drawer.name) add('label', `${width} ${route} #drawer has no accessible name`);
    }
    if (width <= 430 && probe.targets) {
      add('touch-target', `${width} ${route} ${probe.targets} targets under 24px`
        + `: ${probe.targetDetail.slice(0, 3).join(' | ')}`);
    }
  }

  // Command palette: it is the only route switch left under 840px, and it used
  // to navigate to `#dashboard` while the router matches `#/dashboard`, so every
  // row landed on the legacy workbench page. Assert the row's label and the
  // route that actually renders are the same page.
  await navigate(page, '');
  await page.keyboard.press('Control+k');
  const paletteOpen = await page.evaluate(() => document.querySelector('#palette')
    ?.classList.contains('open'));
  if (!paletteOpen) {
    add('palette', `${width} Ctrl+K did not open the palette`);
  } else {
    // Probe a PAGE row, not rows[0]: the object groups are appended before the page list
    // and settle asynchronously, so rows[0] can be a capability row whose destination is
    // the shared 能力目录 page headed by the page title, not by the object name. The
    // label-equals-heading contract only holds for rows that ARE pages.
    const rows = await page.evaluate(() => {
      const groups = Array.from(document.querySelectorAll('#paletteItems .palette-group'));
      const pages = groups.find((g) => g.dataset.group === '页面') || document;
      return Array.from(pages.querySelectorAll('.item')).map((i) => ({
        label: i.textContent.replace('打开', '').trim(), go: i.dataset.go,
        keyboard: i.tagName === 'BUTTON' || i.tabIndex >= 0,
      }));
    });
    if (!rows.length) add('palette', `${width} palette has no rows`);
    if (rows.some((r) => !r.keyboard)) add('palette-keyboard', `${width} palette rows are not focusable`);
    const probeRow = rows[0];
    if (probeRow) {
      await page.evaluate((go) => {
        document.querySelector(`#paletteItems .item[data-go="${go}"]`).click();
      }, probeRow.go);
      // Route render is async (off-DOM then commit); reading the heading before
      // it lands proves nothing about where the row went.
      await page.waitForFunction(() => {
        const view = document.querySelector('#route-view');
        const heading = view && view.querySelector('h2');
        return !!heading && (heading.textContent || '').trim().length > 0
          && !view.querySelector('.view-loading');
      }, null, { timeout: 15000 }).catch(() => {});
      const landed = await page.evaluate(() => ({
        hash: window.location.hash,
        heading: (document.querySelector('#route-view h2') || {}).textContent || '',
      }));
      if (landed.hash !== probeRow.go) {
        add('palette-route', `${width} row ${probeRow.go} landed on ${landed.hash}`);
      } else if (!landed.heading.includes(probeRow.label)) {
        add('palette-route', `${width} landed on ${landed.hash} but the heading is `
          + `"${landed.heading.trim()}" not "${probeRow.label}"`);
      }
    }
  }

  // Degraded state, in-session: the explicit disconnect must leave an honest
  // "not read back" notice on every view, never a confident zero.
  await navigate(page, '#/dashboard');
  await navigate(page, '');
  await page.locator('#disconnect').click();
  await page.waitForFunction(() => {
    const login = document.querySelector('#login');
    return !!login && !login.hidden;
  }, null, { timeout: 20000 }).catch(() => add('degraded-state',
    `${width} disconnect did not return to the connect panel`));
  await navigate(page, '#/dashboard');
  const body = await page.locator('body').innerText();
  const honest = /未读回|未连接|请先在工作台连接|连接本机设计服务/.test(body);
  if (!honest) add('degraded-state', `${width} offline view claims values`);
  notes[`disconnect-${width}`] = {
    showsPlaceholder: /请先在工作台连接本机设计服务/.test(body),
    hasUnreadBack: /未读回/.test(body),
    hasNotConnectedBadge: /未连接/.test(body),
  };

  // Degraded state, cold start: a fresh document has no token in memory, so the
  // view must refuse to render data AND must still offer a way to connect.
  // `show()` deliberately hides #login on every routed view, so an instruction
  // to "connect first" without an action would be a dead end.
  await page.reload({ waitUntil: 'load' });
  await page.waitForFunction(() => {
    const view = document.querySelector('#route-view');
    return !!view && (view.textContent || '').length > 0;
  }, null, { timeout: 20000 }).catch(() => {});
  const cold = await page.evaluate(() => ({
    loginVisible: (() => { const n = document.querySelector('#login'); return !!n && !n.hidden; })(),
    connectAction: Array.from(document.querySelectorAll('#route-view button'))
      .some((b) => /前往工作台连接/.test(b.textContent || '')),
    claimsData: !/未读回|未连接|请先|连接本机设计服务/.test(document.querySelector('#route-view')
      ? document.querySelector('#route-view').textContent : ''),
  }));
  if (cold.claimsData) add('cold-start', `${width} cold load shows confident data with no session`);
  if (!cold.loginVisible && !cold.connectAction) {
    add('cold-start', `${width} cold load on a routed view offers neither a connect form nor a way to reach it`);
  }
  notes[`cold-${width}`] = cold;
  // The action works: follow it and the connect form must appear.
  if (!cold.loginVisible && cold.connectAction) {
    await page.locator('#route-view button').first().click();
    const reached = await page.waitForFunction(() => {
      const n = document.querySelector('#login');
      return !!n && !n.hidden;
    }, null, { timeout: 5000 }).then(() => true).catch(() => false);
    if (!reached) add('cold-start', `${width} 前往工作台连接 did not reveal the connect form`);
  }
  await ctx.close();
}

// --- nav overflow in a short window, and the collapsed drawer in a narrow one ----------
// The width sweep above runs at 900px+ heights, where 11 destinations fit and the sidebar
// never overflows. Both failures guarded here were measured, not imagined: at 1280x720 the
// nav hides 68px of list and at 900x480 it hides 308px, with no cue of any kind before
// `.nav.has-scroll-more` existed; and below 840px every destination lives behind
// #navToggle, where Escape used to leave the drawer open. Asserted as geometry and as
// hit-tests, because a class can be present while the thing it styles paints nothing.
for (const [w, h, label] of [[1280, 500, 'short'], [380, 844, 'narrow']]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => add('pageerror', `${label} ${String(e).slice(0, 120)}`));
  await page.goto(serviceUrl + '/workbench', { waitUntil: 'load' });
  await page.locator('#token').fill(token);
  await page.locator('#connect-form button').first().click();
  await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
  await page.evaluate(() => { window.location.hash = '#/dashboard'; });
  await page.waitForTimeout(900);

  const NAV_STATE = () => {
    const nav = document.querySelector('.sidebar .nav');
    if (!nav) return { present: false };
    const items = [...nav.querySelectorAll('button')];
    const last = items[items.length - 1];
    const navClient = nav.getBoundingClientRect();
    const reach = (el) => {
      const r = el.getBoundingClientRect();
      const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
      if (cy < 0 || cy > innerHeight || cx < 0 || cx > innerWidth) return 'offscreen';
      // Below/above the scroll box is CLIPPED, not covered: scrolling reveals it, and the
      // two failures need different verdicts. `covered` means an element at a point the
      // scroller is already showing is hit by something else, which scrolling never fixes.
      if (cy < navClient.top || cy > navClient.bottom) return 'clipped';
      const top = document.elementFromPoint(cx, cy);
      return top && (top === el || el.contains(top) || top.contains(el)) ? 'hit' : 'covered';
    };
    const after = getComputedStyle(nav, '::after');
    return {
      present: true, items: items.length,
      room: nav.scrollHeight - nav.clientHeight,
      cue: nav.classList.contains('has-scroll-more'),
      cueContent: after.content, cuePosition: after.position,
      lastLabel: (last.textContent || '').trim(), lastReach: reach(last),
      unreachable: items.filter((i) => reach(i) !== 'hit').length,
      unreachableDetail: items.filter((i) => reach(i) !== 'hit')
        .map((i) => `${(i.textContent || '').trim()}:${reach(i)}`),
      toggle: (() => {
        const t = document.getElementById('navToggle');
        return t ? { shown: t.offsetParent !== null, expanded: t.getAttribute('aria-expanded') } : null;
      })(),
    };
  };

  if (label === 'short') {
    const before = await page.evaluate(NAV_STATE);
    notes[`nav-${label}`] = before;
    if (!before.present) add('nav-overflow', 'short: no sidebar nav to measure');
    else if (before.room > 1) {
      if (!before.cue) add('nav-overflow', `short: ${before.room}px of nav hidden with no cue`);
      if (before.cueContent === 'none' || before.cuePosition !== 'sticky') {
        add('nav-overflow', `short: cue claims ${before.cue} but paints content=${before.cueContent} at ${before.cuePosition}`);
      }
      if (before.lastReach !== 'offscreen' && before.lastReach !== 'clipped') {
        add('nav-overflow', `short: last item "${before.lastLabel}" reported ${before.lastReach} while overflowing`);
      }
      await page.evaluate(() => {
        const nav = document.querySelector('.sidebar .nav');
        nav.scrollTop = nav.scrollHeight;
      });
      await page.waitForTimeout(350);
      const after = await page.evaluate(NAV_STATE);
      notes[`nav-${label}-scrolled`] = after;
      if (after.lastReach !== 'hit') {
        add('nav-overflow', `short: after scrolling to the bottom "${after.lastLabel}" is ${after.lastReach}`);
      }
      if (after.cue) add('nav-overflow', 'short: the cue stays on once nothing is left below');
    } else if (before.cue) {
      add('nav-overflow', 'short: the cue is on while the nav does not overflow');
    }
  } else {
    const closed = await page.evaluate(NAV_STATE);
    notes['nav-narrow-closed'] = closed;
    if (!closed.toggle || !closed.toggle.shown) {
      add('nav-drawer', 'narrow: no visible #navToggle to open the drawer with');
    } else {
      if (closed.toggle.expanded !== 'false') add('nav-drawer', `narrow: drawer starts expanded=${closed.toggle.expanded}`);
      if (closed.unreachable !== closed.items) {
        add('nav-drawer', `narrow: ${closed.items - closed.unreachable} destinations are reachable while the drawer is closed`);
      }
      await page.locator('#navToggle').click();
      await page.waitForTimeout(400);
      const open = await page.evaluate(NAV_STATE);
      notes['nav-narrow-open'] = open;
      if (open.toggle.expanded !== 'true') add('nav-drawer', 'narrow: opening left aria-expanded false');
      // Eighteen destinations cannot all fit a phone-height drawer: measured at 380x844 the
      // nav is a 535px-tall scroll box. The invariant is the one the short-window branch
      // already proves -- the cue is on while there is more below, the box actually scrolls,
      // and the last destination is reachable once it has. An item that is COVERED near the
      // top is still a failure: scrolling never frees it.
      const covered = open.unreachableDetail.filter((entry) => entry.endsWith(':covered'));
      if (covered.length) {
        add('nav-drawer', `narrow: ${covered.length} destinations covered with the drawer open: `
          + covered.slice(0, 4).join(' | '));
      }
      if (open.room > 1) {
        if (!open.cue) add('nav-drawer', `narrow: ${open.room}px of drawer nav hidden with no cue`);
        await page.evaluate(() => {
          const nav = document.querySelector('.sidebar .nav');
          nav.scrollTop = nav.scrollHeight;
        });
        await page.waitForTimeout(350);
        const scrolled = await page.evaluate(NAV_STATE);
        notes['nav-narrow-scrolled'] = scrolled;
        if (scrolled.lastReach !== 'hit') {
          add('nav-drawer', `narrow: after scrolling to the bottom "${scrolled.lastLabel}" is ${scrolled.lastReach}`);
        }
        if (scrolled.cue) add('nav-drawer', 'narrow: the cue stays on once nothing is left below');
      } else if (open.unreachable) {
        add('nav-drawer', `narrow: ${open.unreachable} of ${open.items} destinations unreachable although the drawer nav does not overflow`);
      }
      await page.keyboard.press('Escape');
      await page.waitForTimeout(350);
      const escaped = await page.evaluate(NAV_STATE);
      notes['nav-narrow-escape'] = escaped;
      if (escaped.toggle.expanded !== 'false') {
        add('nav-drawer', `narrow: Escape left the drawer at aria-expanded=${escaped.toggle.expanded}`);
      }
    }
  }
  await ctx.close();
}

await b.close();

notes.totalMetrics = metrics.length;
notes.detailsExpanded = metrics.reduce((n, m) => n + (m.detailsExpanded || 0), 0);
notes.hardViolations = violations.length;
console.log(JSON.stringify({ ok: violations.length === 0, violations, notes,
  worst: metrics.filter((m) => m.contrast.length).slice(0, 12) }, null, 2));
process.exit(violations.length === 0 ? 0 : 1);
