// SPDX-License-Identifier: MIT
// Workbench visual overflow audit — real Chromium against the real loopback
// service. Answers ONE question: is any text cut off (invisible) or painted
// outside the viewport with no way to scroll to it?
//
// Env: E2E_SERVICE_URL E2E_TOKEN E2E_NODE_MODULES [E2E_BROWSER]
//      [OV_WIDTHS=1440,1024,390] [OV_OUT=<json path>] [OV_STRICT=1]
//      [OV_HEIGHT=900] [OV_SHORT_HEIGHT=620]
//      [UI_PALETTE=design-lab|ui2026] [UI_SCHEME=dark|light]
//
// Geometry is graded per theme, not once: a palette block that re-points only colours still
// changes what a screen looks like to a person, and a gate that measures one palette cannot
// see a collapse that only the other palette shows. The theme is recorded in the summary line
// so a reader knows which subject a given OV_OK speaks for.
//
// The gate is FALSIFIABLE: before it is trusted it must be seen to go RED on a
// known-bad build. Verified 2026-10-06 against the pre-fix build, which failed
// with `settings div.panel clipped 388px`; the same build passes after the fix.
//
// What counts as a failure (see classify()):
//   CLIPPED  content wider/taller than its box AND the box clips it -> invisible.
//   STRAY    painted past the viewport right edge with NO scrollable ancestor
//            -> user can never reach it.
// What does NOT count:
//   · .sr-status — the deliberate screen-reader-only live region (its own CSS
//     clips it by design, so it is allowlisted explicitly, not silently).
//   · anything inside a real overflow:auto|scroll ancestor -> reachable by
//     scrolling (.table-wrap tables, the mobile .app-nav). These are reported
//     as SCROLL_OK so the number stays visible and reviewable.
import { createRequire } from 'node:module';
import { readFileSync, statSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const serviceUrl = process.env.E2E_SERVICE_URL;
const token = process.env.E2E_TOKEN;
const nmDir = process.env.E2E_NODE_MODULES;
const browserPath = process.env.E2E_BROWSER || undefined;
// 1536 is not a fourth "random laptop": it is 1920 physical at Windows 125% display scaling, the
// same mapping the zoom receipts use (100% / 125% / 150% of a 1920-wide panel = 1920 / 1536 / 1280
// CSS px). 1280 was already swept, so before 1536 was added this gate measured two of the three
// zoom cases and skipped the middle one. Height stays the gate's own budget (900 nominal, 620
// short) rather than a scaled one: the claim being made here is about width-driven clipping.
const widths = (process.env.OV_WIDTHS || '1440,1280,1536,1920')
  .split(',').map((w) => Number.parseInt(w, 10)).filter((w) => Number.isFinite(w) && w > 0);
const outPath = process.env.OV_OUT || '';
const strict = process.env.OV_STRICT === '1';
// The two viewport heights the gate judges, now overridable so a coverage question gets answered by
// measuring rather than by arguing: `OV_HEIGHT=1100` asks what the sidebar looks like on a machine
// whose working area is 1104 tall. Defaults are unchanged -- 900 is the nominal pass, 620 the short
// end where the cue band, the cut line and the footer crowd together -- and that is what CI runs.
const mainHeight = Number.parseInt(process.env.OV_HEIGHT || '900', 10);
const shortHeight = Number.parseInt(process.env.OV_SHORT_HEIGHT || '620', 10);
const uiPalette = process.env.UI_PALETTE || 'design-lab';
const uiScheme = process.env.UI_SCHEME || 'dark';

// Same mechanism as the contrast gate: the Workbench decides its theme at mount, so the two
// <html> attributes must exist BEFORE any page script runs. Setting them after `load` would
// measure one palette while the page's own controls describe another.
async function paintTheme(p) {
  await p.addInitScript(([palette, scheme]) => {
    const apply = () => {
      document.documentElement.setAttribute('data-palette', palette);
      if (scheme === 'light') document.documentElement.setAttribute('data-scheme', 'light');
      else document.documentElement.removeAttribute('data-scheme');
    };
    if (document.documentElement) apply();
    else document.addEventListener('DOMContentLoaded', apply);
  }, [uiPalette, uiScheme]);
}

const fail = (reason) => { console.error('OV_FAIL: ' + reason); process.exit(2); };
if (!serviceUrl || !token || !nmDir) fail('OV_CONFIG_MISSING');
if (!/^[0-9a-f]{64}$/.test(token)) fail('OV_TOKEN_SHAPE');
if (widths.length === 0) fail('OV_WIDTHS_EMPTY');

const req = createRequire(nmDir + '/noop.js');
const { chromium } = req('playwright');

const ROUTES = [
  ['workbench', ''], ['dashboard', '#/dashboard'], ['projects', '#/projects'],
  ['research', '#/research'], ['brand-systems', '#/brand-systems'], ['domains', '#/domains'],
  ['tools', '#/tools'], ['preflight', '#/preflight'], ['deliverables', '#/deliverables'],
  ['evidence', '#/evidence'], ['collaboration', '#/collaboration'], ['settings', '#/settings'],
  // DL-UI-U02 (2026-10-09): the three new slots. A route that is not in this list is
  // never rendered by this gate, so it cannot fail it either -- that omission is the
  // 2026-10-07 finding (8 of 12 routes had never been captured), not a hypothetical.
  ['capabilities', '#/capabilities'], ['states', '#/states'], ['components', '#/components'],
  // R2 §5: the parameterized detail address is its own measured state. The id is a record
  // from the committed vendor/sources.lock.json; if it ever disappears the view renders the
  // honest "未找到该记录" panel, which this gate would then see as its own geometry.
  ['capability-detail', '#/capabilities/anydesign'],
  // R2 §2: a domain pack's own address, measured as its own state for the same reason.
  // `brand-design` is one of the 12 directories the repo checker accepts today; the
  // rejected one (minigame-design) is reachable too but its panel carries the checker's
  // 11 reasons, so it would change what "fits" means and is checked in the vm suite.
  ['domain-detail', '#/domains/brand-design'],
  ['intake', '#/intake'],
  // 提示词工程与模型选择是两条新读面。不进这份清单就永远不会被这个闸渲染，也就
  // 永远不会让它失败——2026-10-07 记下的正是这种覆盖洞，而不是假设。
  ['prompt-intelligence', '#/prompts'],
  ['model-selection', '#/models'],
  ['plan', '#/plan'],
  ['analysis', '#/analysis'],
  ['records', '#/records'],
  // DL-KB-03/06: 知识与提示词库是本批新增的读面，搜索框、meta 行与两栏详情都在几何闸里。
  ['knowledge', '#/knowledge'],
  // DL-KB-08: 设计辅助。成对字段行（.as-row）与四态药丸在窄一档的桌面窗口里最先溢出。
  ['assistant', '#/assistant'],
  // DL-KB-10: 目标组合选择面板。五个选择框、两栏对照与最多两条路线都在这一面；长中文型号名
  // （「MiniMax H3（ComfyUI 集成）」）与档案正文的长句是这一屏最容易在该档被切到的东西
  // ——02:150 / 06:48 要验的就是这三档桌面视口下的它。
  ['target-profiles', '#/target-profiles'],
  ['automation', '#/automation'],
];

// Deliberate clip: the screen-reader-only route-change announcer.
// A route sweep cannot see a panel that only appears after a click, and a button-gated readback is
// exactly where a clipped KPI grid or a sub-11px caption hides. Each interaction is measured as its
// own named state; a selector that is not there, or a read that never settles, fails the gate rather
// than being skipped -- an unrun measurement is not a passing one.
const INTERACTIONS = [
  ['evidence', '#evidence-projection-run', 'projection-read',
    `() => {
      const box = document.getElementById('evidence-projection-outcome');
      if (!box) return 'no-box';
      if (box.querySelector('.error')) return 'refused';
      if (box.querySelector('[data-count]')) return 'read';
      return false;
    }`],
  // R2 §9: the grouped object search is an overlay, so no route sweep can see it. Opening it
  // on a real route and waiting until every group has answered is what makes its geometry --
  // and the claim that a group never silently shows "0" -- measurable.
  ['capabilities', '#openPalette', 'global-search',
    `() => {
      const groups = document.querySelectorAll('#paletteObjects .palette-group');
      if (groups.length !== 4) return 'no-groups';
      const bodies = Array.from(groups).map((g) => (g.querySelector('.palette-group-body')
        || {}).textContent || '');
      if (bodies.some((t) => t.includes('尚未读取'))) return false;
      // Every group must land on one of the three answers a reader can act on. A body that is
      // simply empty would satisfy "not 尚未读取" while telling nobody anything.
      const answered = Array.from(groups).every((g) => {
        const body = g.querySelector('.palette-group-body');
        if (!body) return false;
        const text = body.textContent || '';
        return Boolean(body.querySelector('.item'))
          || text.includes('0 个对象') || text.includes('未读回');
      });
      if (!answered) return false;
      return 'read';
    }`],
];

const ALLOWLIST = ['sr-status'];

const MEASURE = () => {
  const allow = ['sr-status'];
  const desc = (e) => {
    const cls = (e.getAttribute('class') || '').trim();
    const id = e.id ? `#${e.id}` : '';
    const txt = (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70);
    return `${e.tagName.toLowerCase()}${id}${cls ? '.' + cls.split(/\s+/).join('.') : ''} :: ${txt}`;
  };
  const inAllowlist = (e) => allow.some((c) => (e.getAttribute('class') || '').includes(c));
  // A painted overflow is only acceptable if SOME ancestor actually scrolls.
  const hasScrollableAncestor = (e) => {
    for (let p = e.parentElement; p; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if ((ox === 'auto' || ox === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true;
    }
    return false;
  };
  // Geometry is a claim about what a person can see, and a closed `<details>` is the one place
  // where Chromium's layout boxes and its paint disagree: `::details-content` is
  // `content-visibility: hidden` with `overflow: clip`, so every box below would be measured while
  // nothing is drawn. Open the panels first so CLIPPED / STRAY / TINY describe the state a designer
  // actually reaches, and report how many closed panels that took: a run that says 0 on a screen
  // known to have them means the expansion was removed and the numbers are invisible layout again.
  const expanded = document.querySelectorAll('details:not([open])').length;
  for (const host of document.querySelectorAll('details:not([open])')) host.open = true;
  const out = { docOverflowX: 0, clipped: [], stray: [], scrollOk: 0, tiny: [],
                detailsExpanded: expanded };
  const de = document.documentElement;
  out.docOverflowX = de.scrollWidth - de.clientWidth;
  const vw = window.innerWidth;
  for (const e of Array.from(document.querySelectorAll('body *'))) {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') continue;
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (inAllowlist(e)) continue;
    const d = desc(e);
    const ox = cs.overflowX, oy = cs.overflowY;
    const dx = e.scrollWidth - e.clientWidth;
    const dy = e.scrollHeight - e.clientHeight;
    if (dx > 1 && (ox === 'hidden' || ox === 'clip')) out.clipped.push({ axis: 'x', by: dx, el: d });
    if (dy > 1 && (oy === 'hidden' || oy === 'clip')) out.clipped.push({ axis: 'y', by: dy, el: d });
    if (r.right > vw + 1) {
      if (hasScrollableAncestor(e)) out.scrollOk++;
      else out.stray.push({ over: Math.round(r.right - vw), el: d });
    }
    const fs = parseFloat(cs.fontSize);
    if (fs > 0 && fs < 11 && (e.textContent || '').trim().length > 0) out.tiny.push({ px: fs, el: d });
  }
  // Layout census, recorded per route and per theme. Clipping alone cannot see a column
  // that quietly becomes a third of the viewport: nothing is cut off, the page just stops
  // using the space it was given. A PNG is read by eye and a number is read by a gate; when
  // the two disagree, this is the field that says which one is lying.
  const rail = document.querySelector('#app-sidebar, .app-sidebar, aside');
  const main = document.querySelector('#route-view');
  const table = document.querySelector('#route-view table');
  const drawer = document.querySelector('.cap-drawer');
  out.layout = {
    vw: window.innerWidth,
    narrow760: window.matchMedia('(max-width:760px)').matches,
    railW: rail ? Math.round(rail.getBoundingClientRect().width) : null,
    mainW: main ? Math.round(main.getBoundingClientRect().width) : null,
    mainLeft: main ? Math.round(main.getBoundingClientRect().left) : null,
    tableW: table ? Math.round(table.getBoundingClientRect().width) : null,
    drawerW: drawer ? Math.round(drawer.getBoundingClientRect().width) : null,
  };
  // 首屏双列（owner 2026-10-28 那一刀：最近方案进右列）。这条只在遗留工作台那面有值，其余路由
  // 返回 null，因为 `#workspace` 在路由页是隐藏的——隐藏不等于"这一列不存在"，所以下游读的是
  // null 与非 null 的分布，而不是把 null 当成通过。它量的是"两列是否真在两侧、方案面板是否
  // 真在第二列里、那块说法文字是否真的画出来了"：光看 markup 里有 `.col` 不能证明浏览器把它
  // 排成了两列（media query 与 grid-template 都能在没有报错的情况下把它变回一列）。
  out.firstScreen = (() => {
    const grid = document.querySelector('#workspace .grid');
    if (!grid) return null;
    const gridBox = grid.getBoundingClientRect();
    if (gridBox.width < 1) return null;
    const box = (node) => {
      const r = node.getBoundingClientRect();
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width),
        h: Math.round(r.height), right: Math.round(r.right), bottom: Math.round(r.bottom) };
    };
    const cols = Array.from(grid.children);
    const list = document.querySelector('#recent-plans');
    const panel = list ? list.closest('.panel') : null;
    const info = document.querySelector('#recent-plans-info');
    const first = cols.length ? box(cols[0]) : null;
    const second = cols.length > 1 ? box(cols[1]) : null;
    return {
      colCount: cols.length,
      colBoxes: cols.map(box),
      tracks: getComputedStyle(grid).gridTemplateColumns.split(' ').filter(Boolean).length,
      sideBySide: Boolean(first && second && second.x > first.x + 1),
      plansFound: Boolean(panel),
      plansInSecondCol: Boolean(panel && cols.length > 1 && cols[1].contains(panel)),
      plansBox: panel ? box(panel) : null,
      // Rows of content, not sentences inside the list: the empty state is a real <li> too (a bare
      // text node in a <ul> is the WCAG 4.1.1 defect this repo already fixed once), and counting it
      // as a plan row would make the painted number and the painted list disagree on purpose.
      rowCount: list ? list.querySelectorAll('li:not(.empty)').length : -1,
      firstRow: (list && list.children.length)
        ? (list.children[0].textContent || '').trim().slice(0, 60) : null,
      infoText: info ? (info.textContent || '').trim() : null,
      infoBox: info ? box(info) : null,
      viewport: [innerWidth, innerHeight],
      pageWide: document.documentElement.scrollWidth - innerWidth,
    };
  })();
  // A panel painted over a global control is invisible to every other check here: nothing
  // is clipped, nothing leaves the viewport, no text is small -- the control simply stops
  // answering. Hit-test the affordances that must always be reachable. An element that is
  // absent or has no box on this route is skipped (the legacy workbench chrome hides the
  // B10 topbar), because "not on screen" is not the same claim as "covered by something".
  const CRITICAL = [['#openSettings', '顶栏设置'], ['#openDrawer', '顶栏工作区'],
    ['#openPalette', '顶栏搜索入口']];
  out.occluded = [];
  // A centre point that is not inside the viewport is not "covered by something": the file's own
  // rule says the two claims differ. Scrolling a long detail out of the header's reach shows up
  // here, so it gets its own bucket with the numbers, instead of being reported as an occlusion
  // the reader would go looking a z-index bug for.
  out.notInView = [];
  // A modal overlay is *supposed* to cover the page behind it -- that is not the defect this
  // check guards. When one is open the hit-test is skipped, and the report says so instead of
  // going silently quiet.
  const modal = document.querySelector('.palette.open, .modal.open, .drawer.open');
  if (modal) {
    out.occludedSkipped = `${modal.tagName.toLowerCase()}.${String(modal.className).trim()}`;
  } else {
  for (const [sel, label] of CRITICAL) {
    const e = document.querySelector(sel);
    if (!e) continue;
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
    if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) {
      out.notInView.push({ sel, label, centre: [cx, cy], viewport: [innerWidth, innerHeight],
                           top: Math.round(r.top), bottom: Math.round(r.bottom) });
      continue;
    }
    const hit = document.elementFromPoint(cx, cy);
    if (!hit) { out.occluded.push({ sel, label, by: 'elementFromPoint returned null' }); continue; }
    if (hit !== e && !e.contains(hit)) {
      out.occluded.push({ sel, label,
        by: `${hit.tagName.toLowerCase()}${hit.id ? '#' + hit.id : ''}`
          + `${hit.className ? '.' + String(hit.className).trim().split(/\s+/).join('.') : ''}` });
    }
  }
  }
  // The nav is the sidebar's only scroll region and the identity footer sits directly under
  // it. When the list overflows, an item is always cut in half at that edge -- nothing is
  // clipped *out of* its box, so no CLIPPED check can see it. What makes it a defect is the
  // footer's 1px top border landing on the cut line: the hairline reads as an underline drawn
  // under a half-visible word. Record the gap between the two edges so the boundary has a
  // number, and which kind of item happens to straddle it.
  // Heading order is the screen-reader map of a screen: h2 straight to h4 reads as "a section
  // went missing". axe reports it only when it evaluates the node, and it declined 9-71 nodes
  // per screen here, so the sequence is measured from the rendered DOM instead.
  out.headings = (() => {
    const view = document.querySelector('#route-view');
    if (!view) return { levels: [], skip: null, note: 'no #route-view' };
    const nodes = Array.from(view.querySelectorAll('h1,h2,h3,h4,h5,h6'))
      .filter((h) => h.getClientRects().length > 0);
    const levels = nodes.map((h) => Number(h.tagName.slice(1)));
    for (let i = 1; i < levels.length; i += 1) {
      if (levels[i] > levels[i - 1] + 1) {
        return { levels, note: null, skip: `h${levels[i - 1]} -> h${levels[i]} at `
          + `"${(nodes[i].textContent || '').trim().slice(0, 40)}"` };
      }
    }
    return { levels, skip: null, note: null };
  })();
  // The cascade, checked where it actually lands. Two silent regressions came from folding
  // repeated inline `style:` strings into utility classes: a component class defined later in the
  // stylesheet took the property back by source order (`.quick-launch{margin-top:0}`,
  // `.row-card{display:flex;gap:12px}`), and no gate noticed because none of them measures how far
  // apart two panels sit. So read the computed value on every element that carries a utility class
  // and compare it against the token the class is supposed to apply.
  out.utilityGeometry = (() => {
    const rootStyle = getComputedStyle(document.documentElement);
    const token = (name) => rootStyle.getPropertyValue(name).trim();
    const space2 = token('--uif-space-2');
    const space4 = token('--uif-space-4');
    const EXPECT = [['spaced-top', 'margin-top', space4],
                    ['grid-stack', 'display', 'grid'],
                    ['grid-stack', 'gap', space2]];
    const bad = [];
    const seen = {};
    let checked = 0;
    for (const [cls, prop, want] of EXPECT) {
      if (!want) { bad.push({ cls, prop, want: 'a resolved token', got: 'empty/missing token' }); continue; }
      for (const node of document.querySelectorAll(`.${cls}`)) {
        checked += 1;
        seen[cls] = (seen[cls] || 0) + 1;
        const got = getComputedStyle(node)[prop];
        if (got !== want) {
          bad.push({ cls, prop, want, got,
                     coClasses: Array.from(node.classList).filter((c) => c !== cls).join('.') });
        }
      }
    }
    return { checked, seen, bad, tokens: { space2, space4 } };
  })();
  out.navEdge = (() => {
    const nav = document.querySelector('.sidebar .nav');
    const foot = document.querySelector('.sidebar-footer');
    if (!nav || !foot) return null;
    const nr = nav.getBoundingClientRect();
    const fr = foot.getBoundingClientRect();
    const straddling = Array.from(nav.children).filter((c) => {
      const r = c.getBoundingClientRect();
      return r.height > 0 && r.top < nr.bottom - 1 && r.bottom > nr.bottom + 1;
    });
    return {
      gap: Math.round(fr.top - nr.bottom),
      overflow: nav.scrollHeight - nav.clientHeight,
      straddling: straddling.map((c) => c.className || c.tagName.toLowerCase()),
      labelStraddling: straddling.some((c) => c.classList.contains('nav-group')),
    };
  })();
  return out;
};

const browser = await chromium.launch({ executablePath: browserPath, args: ['--no-sandbox'] });
// A geometry receipt that does not name the bytes it measured cannot be re-checked later:
// the bundle is rebuilt between batches, and "0 clipped" over one build says nothing about
// another. Read the file the page actually loaded and bind this report to it.
// The stylesheet is bound too, and that is not decoration: layout is what this gate measures,
// and the CSS is served as its own file -- editing a rule left `main.js` byte-identical, so a
// bundle-only subject would have reported the same sha before and after a layout change.
const bundlePath = new URL('../../../apps/workbench/build/main.js', import.meta.url);
const stylePath = new URL('../../../apps/workbench/style.css', import.meta.url);
const bundleSha256 = createHash('sha256').update(readFileSync(bundlePath)).digest('hex');
const styleSha256 = createHash('sha256').update(readFileSync(stylePath)).digest('hex');
const report = { serviceUrl, widths, routes: {}, brand: {}, navEdge: {}, uiPalette, uiScheme,
  subject: { bundle: 'apps/workbench/build/main.js', bundleSha256,
    bundleBytes: statSync(bundlePath).size,
    stylesheet: 'apps/workbench/style.css', styleSha256,
    styleBytes: statSync(stylePath).size } };
let clippedTotal = 0, strayTotal = 0, tinyTotal = 0;
const interactionMissing = [];
const specProblems = [];
const interactionStates = [];
// The brand tile, measured once per width. See BRAND_PROBE below for what it proves.
const brandProblems = [];
// One record per route whose sidebar list actually scrolls; reduced to the tightest gap per
// width below, because the nav is global chrome and repeats on every route.
const navEdges = [];

// The entry detail is measured as its own named state (see the knowledge step in the sweep), and
// a state needs something in it: one synthetic entry, written through the same service the page
// reads and discarded with the temp state root. Marked synthetic in created_by so nobody can read
// it as design work.
async function seedKnowledgeEntryForAudit(prefix) {
  const body = {
    entry_type: 'METHOD', title: '镜头拆解三步法（合成）',
    summary: '把一段脚本拆成镜头表：先定节拍，再定景别，最后只标必要的转场。',
    domain_tags: ['film'], task_tags: ['storyboard'], target_tools: ['storyboarder'],
    body: '第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场，'
      + '并留下"引号"、逗号, 与一段较长的说明文字，用来量这块面板在窄一侧的换行与溢出。',
    applicability: '适合 30-90 秒短片的分镜前置。', limits: '不适用于需要精确口型对位的动画。',
    source: { sourceId: 'UNUSED', origin: 'UNKNOWN', author: 'UNKNOWN', license: 'UNKNOWN',
              licenseStatus: 'unknown', allowedUsage: 'UNKNOWN', citationScope: 'UNKNOWN',
              version: 'UNKNOWN', observedAt: 'UNKNOWN', contentHash: 'UNKNOWN',
              verification: 'UNVERIFIED' },
    related_capability_ids: [], recommended: true,
    created_by: `${prefix} 脚手架（合成，不是真人）`, supersedes: null,
  };
  const res = await fetch(serviceUrl.replace(/\/$/, '') + '/api/knowledge-entries', {
    method: 'POST', headers: { Authorization: `Bearer ${token}`,
                               'Content-Type': 'application/json' },
    body: JSON.stringify(body) });
  const json = await res.json().catch(() => ({}));
  if (res.status !== 201) {
    fail(`OV_SEED_KNOWLEDGE_REFUSED ${JSON.stringify(json).slice(0, 200)}`);
  }
  return { entry: json.entry.knowledge_entry_id };
}

// The mirror image of the knowledge gap: the contrast ruler has opened a plan detail for a while,
// the geometry ruler never has. So the shot table, the export panel and the feedback block inside a
// plan have had no claim about 1280, 1536 or 1920 -- which is exactly where a long Chinese
// objective or a wide table would have gone sideways without anyone noticing.
async function seedAssistancePlanForAudit(prefix) {
  const base = serviceUrl.replace(/\/$/, '');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  const post = async (path, body) => {
    const res = await fetch(base + path, { method: 'POST', headers,
      body: JSON.stringify(body) });
    return { status: res.status, json: await res.json().catch(() => ({})) };
  };
  const project = await post('/api/projects', { name: `${prefix}-audit` });
  if (project.status !== 201) {
    fail(`OV_SEED_PROJECT_REFUSED ${JSON.stringify(project.json).slice(0, 200)}`);
  }
  const pid = project.json.project.id;
  const plan = {
    objective: '为秋季新品做一条 15 秒主视觉动效，标题落在大面积留白里，副标题带上说明文字',
    output_type: 'MOTION',
    neutral_creative: '两束交叉光缓慢推移，标题以一次落定收束。',
    brand_constraints: ['只用两种油墨', '标题不使用描边'],
    role_constraints: [],
    lens: '俯拍整张桌面', sound: '低频垫底，无对白', references: [],
    shots: [
      { index: 1, duration_s: 4, purpose: '开场：侧光落在纸纤维上', camera: '缓推',
        sound: null, reference_role: '主参考' },
      { index: 2, duration_s: null, purpose: '收束：标题落定，副标题带"引号"、逗号, 与一段较长的说明',
        camera: '固定', sound: '低频收干', reference_role: null },
    ],
    external_steps: [{ step: '在宿主里手动导出 MP4', tool: 'After Effects',
                       job_id: null, operation_id: null }],
    known_gaps: ['目标平台码率未定'],
    limits: ['不含多语言字幕', '不产出可编辑源文件'],
    created_by: `${prefix} 脚手架（合成，不是真人）`,
  };
  const created = await post(`/api/projects/${pid}/assistance-plans`, plan);
  if (created.status !== 201) {
    fail(`OV_SEED_PLAN_REFUSED ${JSON.stringify(created.json).slice(0, 200)}`);
  }
  const planId = created.json.plan.plan_id;
  // A second revision so the comparison panel has two documents to line up -- the state whose
  // twelve side-by-side rows are most likely to break a layout at the narrow end.
  const second = await post(`/api/projects/${pid}/assistance-plans/${planId}/revisions`,
    { ...plan, objective: '第二版：把标题落点改成右下方留白，副标题缩短一行',
      expected_revision: 1 });
  if (second.status !== 201) {
    fail(`OV_SEED_REVISION_REFUSED ${JSON.stringify(second.json).slice(0, 200)}`);
  }
  return { project: pid, plan: planId, revision: second.json.revision };
}

// Settle on the panel's own words: the rows landed and the status line stopped saying 正在读回
// and is not a failure. Text alone is not the mark -- an honest empty answer has text too.
async function openPlanCompare(page, key, problems) {
  await page.evaluate(() => {
    const details = document.getElementById('as-compare');
    if (details) details.open = true;
  });
  await page.selectOption('#as-compare-from', '1');
  await page.selectOption('#as-compare-to', '2');
  await page.click('#as-compare-run');
  const settled = await page.waitForFunction(() => {
    const body = document.getElementById('as-compare-body');
    const status = document.getElementById('as-compare-status');
    return !!body && body.querySelectorAll('li').length >= 12 && !!status
      && !/正在读回|失败/.test(status.textContent || '');
  }, null, { timeout: 20000 }).then(() => true).catch(() => false);
  if (!settled) {
    problems.push(`${key}: 两案对照没有把十二个字段读回来（按不动、读回失败或行数不足），`
      + '这一态的几何无人认领');
  }
  return settled;
}

// Choose a target the way the screen asks. The settled mark is the panel's own state flag
// (#tp-combination's data-mode reaches 'target' only when a real profile resolves), not "some text
// appeared" -- an honest empty answer also has text.
// The last "only exists after an action" panel here: one recorded piece of external feedback and
// its read-back row. Fewest fields the form accepts, and a name that says out loud it is
// scaffolding -- a gate row is not a human sign-off and must not be able to read like one later.
async function openFeedbackState(page, key, problems) {
  const word = await page.locator('#as-fb-outcome option').nth(1).getAttribute('value');
  await page.selectOption('#as-fb-outcome', word ?? '');
  await page.fill('#as-fb-target', '闸门合成：秋季主视觉在客户会上放过一次');
  await page.fill('#as-fb-actor', '审计脚手架（合成，不是真人签署）');
  await page.click('#as-fb-save', { timeout: 20000 });
  const settled = await page.waitForFunction(() => {
    const history = document.getElementById('as-fb-history');
    const status = document.getElementById('as-fb-status');
    return !!history && history.querySelectorAll('li').length >= 1 && !!status
      && !/正在|失败/.test(status.textContent || '');
  }, null, { timeout: 20000 }).then(() => true).catch(() => false);
  if (!settled) {
    problems.push(`${key}: 记录一条合成外部反馈后没有读回历史行（按钮按不动、被拒或列表为空），`
      + '这一态的几何无人认领');
  }
  return settled;
}

async function openCombinationState(page, key, problems) {
  for (const id of ['tp-software', 'tp-agent', 'tp-entry', 'tp-model', 'tp-task-mode']) {
    const select = page.locator('#' + id);
    if (await select.count() !== 1) continue;
    if (await page.locator('#' + id + ' option').count() < 2) continue;
    if (await select.inputValue() !== '') continue;
    await select.selectOption({ index: 1 });
  }
  const settled = await page.waitForFunction(() => {
    const line = document.getElementById('tp-combination');
    return !!line && line.dataset.mode === 'target';
  }, null, { timeout: 20000 }).then(() => true).catch(() => false);
  if (!settled) {
    problems.push(`${key}: 依次选了软件／Agent／接入方式之后仍未解析到一份目标档案，`
      + '这一态的几何无人认领');
  }
  return settled;
}

const planSeed = await seedAssistancePlanForAudit('几何审计');
report.auditSeed = { kind: 'synthetic-assistance-plan', project: planSeed.project,
  plan: planSeed.plan, product_data: false,
  note: '只为让方案详情能被几何测量而写进本次临时状态；创建人标明是合成的，随状态目录一起丢弃' };
const kbSeed = await seedKnowledgeEntryForAudit('几何审计');
report.auditKnowledgeSeed = { kind: 'synthetic-knowledge-entry', entry: kbSeed.entry,
  product_data: false,
  note: '只为让知识条目详情能被几何测量而写进本次临时状态，随状态目录一起丢弃' };

// One sink for every panel this sweep opens by clicking. Accumulating in two places would give the
// same counters two owners, and the route loop's own accumulation cannot see a row added out here:
// without this, an opened panel is reported but never graded, which is a coverage claim that
// protects nothing.
function absorbPanel(key, m) {
  report.routes[key] = m;
  interactionStates.push(`${key}=${m.state}`);
  clippedTotal += m.clipped.length;
  strayTotal += m.stray.length;
  tinyTotal += m.tiny.length;
  for (const o of m.occluded) {
    specProblems.push(`${key} ${o.label} (${o.sel}) covered by ${o.by}`);
  }
}

for (const w of widths) {
  const page = await browser.newPage({ viewport: { width: w, height: mainHeight } });
  await paintTheme(page);
  await page.goto(serviceUrl.replace(/\/$/, '') + '/workbench', { waitUntil: 'load' });
  await page.fill('#token', token);
  await page.click('#connect-form button');
  await page.waitForTimeout(1500);
  for (const [name, hash] of ROUTES) {
    await page.evaluate((h) => { window.location.hash = h; }, hash);
    await page.waitForTimeout(1000);
    // A route that is still awaiting its reads renders a `.view-loading` paragraph and no headings,
    // and a fixed sleep cannot prove that has stopped: on a loaded CI runner this measured
    // `1440:capabilities` mid-mount and the heading assertion convicted the screen of having no
    // headings when the truth was "not mounted yet". Wait for the mount to finish before judging
    // it; a route that never settles is reported as such rather than measured as an empty shell.
    const settled = await page.waitForFunction(() => {
      const host = document.getElementById('route-view');
      return !!host && !host.querySelector('.view-loading');
    }, null, { timeout: 20000 }).then(() => true).catch(() => false);
    if (!settled) {
      console.log(`OV_UNSETTLED ${w}:${name} still shows a loading placeholder after 20s`);
      interactionMissing.push(`${w}:${name} never finished mounting, so its geometry is unclaimed`);
    }
    const m = await page.evaluate(MEASURE);
    report.routes[`${w}:${name}`] = m;
    if (name === 'knowledge') {
      // The entry detail is the panel this sweep used to stop short of, so the judgement trail's
      // small print, both judgement forms and the refused-clipboard fallback box were never
      // geometry-checked -- a fallback textarea wider than its panel is exactly the kind of thing
      // no clip check on the list screen can see. Open it as a person does and measure it as its
      // own named state; a detail that never assembled is recorded as unclaimed, not measured empty.
      await page.locator('#kb-results .kb-open').first().click();
      const detailSettled = await page.waitForFunction(() => {
        const host = document.getElementById('kb-detail');
        if (!host || host.querySelector('.view-loading')) return false;
        if (!document.getElementById('kb-copy-body')) return false;
        if (!document.getElementById('kb-judge-reason')) return false;
        return (document.getElementById('kb-detail-content')?.textContent ?? '').trim().length >= 8;
      }, null, { timeout: 20000 }).then(() => true).catch(() => false);
      if (!detailSettled) {
        interactionMissing.push(`${w}:knowledge+entry-detail 的详情面板在 20s 内没有装配完，`
          + '它的几何无人认领');
      } else {
        const panel = await page.evaluate(MEASURE);
        // The panel's own verdict, read off what is painted: a detail that came back with the
        // served body is a read, one that says 未读回 is a named refusal. The wrapper asserts every
        // button-gated panel settled on one or the other, so this cannot be left unset.
        panel.state = await page.evaluate(() => (
          /未读回/.test((document.getElementById('kb-detail')?.textContent ?? ''))
            ? 'refused' : 'read'));
        absorbPanel(`${w}:knowledge+entry-detail`, panel);
      }
    }
    if (name === 'assistant') {
      // Same rule for the plan detail: open it, wait for the reads that only land once the panel is
      // assembled (the shot rows and the served material formats -- not "every status line has
      // text", which an honest empty note would fail forever), then measure it as its own state.
      // A missing row is a fact the report states, not a crash the run dies on: an uncaught
      // timeout here hides what the screen said and makes the next reader re-instrument the gate.
      const planRow = page.locator('#as-list .as-plan-open').first();
      if (await planRow.count() !== 1) {
        const said = await page.locator('#as-list-meta').innerText().catch(() => '(读不到 #as-list-meta)');
        interactionMissing.push(`${w}:assistant+plan-detail 的方案清单里没有可点开的行，`
          + `屏上写的是「${said}」`);
      } else {
      await planRow.click();
      const planSettled = await page.waitForFunction(() => {
        const host = document.getElementById('as-plan');
        if (!host || host.querySelector('.view-loading')) return false;
        if (host.querySelectorAll('#as-shots li').length < 1) return false;
        return host.querySelectorAll('#as-material option').length >= 4;
      }, null, { timeout: 20000 }).then(() => true).catch(() => false);
      if (!planSettled) {
        interactionMissing.push(`${w}:assistant+plan-detail 的方案详情在 20s 内没有把镜头表与`
          + '材料格式读回来，它的几何无人认领');
      } else {
        const panel = await page.evaluate(MEASURE);
        panel.state = await page.evaluate(() => (
          /未读回/.test((document.getElementById('as-plan')?.textContent ?? ''))
            ? 'refused' : 'read'));
        absorbPanel(`${w}:assistant+plan-detail`, panel);
      }
      if (await openPlanCompare(page, `${w}:assistant+plan-compare`, interactionMissing)) {
        const panel = await page.evaluate(MEASURE);
        panel.state = await page.evaluate(() => (
          /失败|没有可读的修订/.test(document.getElementById('as-compare-status')?.textContent ?? '')
            ? 'refused' : 'read'));
        absorbPanel(`${w}:assistant+plan-compare`, panel);
      }
      if (await openFeedbackState(page, `${w}:assistant+plan-feedback`, interactionMissing)) {
        const panel = await page.evaluate(MEASURE);
        panel.state = await page.evaluate(() => (
          /失败|未读回/.test(document.getElementById('as-fb-status')?.textContent ?? '')
            ? 'refused' : 'read'));
        absorbPanel(`${w}:assistant+plan-feedback`, panel);
      }
      }
    }
    if (name === 'target-profiles') {
      // Selecting a target is the state where the two truth columns and the combination sentence
      // actually fill, so the layout claim belongs to that state and not to the empty screen.
      if (await openCombinationState(page, `${w}:target-profiles+combination`, interactionMissing)) {
        const panel = await page.evaluate(MEASURE);
        panel.state = await page.evaluate(() => (
          document.getElementById('tp-combination')?.dataset.mode === 'target'
            ? 'read' : 'refused'));
        absorbPanel(`${w}:target-profiles+combination`, panel);
      }
    }
    if (m.navEdge && m.navEdge.overflow > 0) {
      navEdges.push({ key: `${w}:${name}`, ...m.navEdge });
    }
    // R2 §3 fixes the capability detail panel at 450 CSS px on desktop widths. A panel that
    // quietly turns full-width is neither clipped nor stray, so nothing else in this gate
    // would notice; assert the number the spec actually names. The domain detail reuses the
    // same drawer component, so the same ruler applies to it.
    if ((name === 'capability-detail' || name === 'domain-detail') && w >= 1200
      && m.layout.drawerW !== 450) {
      specProblems.push(`${w}:${name} drawer width ${m.layout.drawerW} != 450 (R2 §3)`);
    }
    // R2 §2: the cross-catalog action has to reach the screen in the state the data actually
    // supports. There is no domain↔capability join axis (measured 2026-10-11 against the live
    // readback: all 60 capability records list `domains` among the service's own unclassified
    // axes), so the action must be disabled -- and since batch 18 the panel also reports WHICH
    // empty it is, so this gate checks the disabled state and the named state agree. A panel that
    // said 已接线 N 条 while the button stayed disabled, or the reverse, would be a contradiction
    // no clip check can see.
    if (name === 'domain-detail') {
      const join = await page.evaluate(() => {
        const drawer = document.querySelector('#domain-drawer');
        const button = drawer
          ? Array.from(drawer.querySelectorAll('button'))
            .find((b) => b.textContent.includes('按该领域查看能力')) : null;
        const text = drawer ? drawer.textContent : '';
        // `无已接线关联` contains the substring `已接线`, so a hit-count claim needs its own shape
        // rather than a substring test -- measured while writing this check.
        return {
          drawer: !!drawer,
          label: button ? button.textContent.trim() : '',
          disabled: button ? button.disabled : null,
          matched: /已接线 \d+ 条/.test(text),
          states: ['未读回', '无关联键', '还没有分类', '目录为空', '无已接线关联']
            .filter((word) => text.includes(word)),
          forbidden: (() => {
            // The panel is allowed to QUOTE the phrase in order to deny it
            // (这是"分类还没做"，不是"该领域没有能力"), so a substring ban misfires.
            // Every mention must sit inside a negation; a bare assertion is what is forbidden.
            const mentions = (text.match(/该领域没有能力/g) || []).length;
            const negated = (text.match(/(不是|不等于)"?该领域没有能力/g) || []).length;
            return mentions !== negated;
          })(),
        };
      });
      if (!join.drawer) specProblems.push(`${w}:domain-detail 详情面板不在文档里`);
      if (!join.label) specProblems.push(`${w}:domain-detail 跨目录动作没有上屏`);
      else if (!join.label.includes('按该领域查看能力'))
        specProblems.push(`${w}:domain-detail 跨目录动作标签变了：${join.label}`);
      else if (join.matched && join.disabled)
        specProblems.push(`${w}:domain-detail 面板说有已接线关联，动作却仍禁用：两者必须一致`);
      else if (!join.matched && !join.disabled)
        specProblems.push(`${w}:domain-detail 状态是 ${join.states.join('/') || '(无状态词)'}，`
          + '动作却不禁用：没有已接线关联时这个按钮点了只会落到空结果');
      if (!join.matched && !join.states.length)
        specProblems.push(`${w}:domain-detail 关联行没有说出这是哪一种空`);
      if (join.forbidden)
        specProblems.push(`${w}:domain-detail 面板把"没有已接线关联"断言成了"该领域没有能力"`);
    }
    // Found by reading the rendered #/domains, not by any assertion: when a row's trailing
    // columns are sized by their own content, `justify-content:space-between` parks the
    // action at whatever x its neighbours leave, so the 查看详情 buttons sat several px apart
    // and the verdict pills with them. Nothing was clipped or stray, so the gate was green
    // over a visibly ragged list. Actions must share a column and pills must share a column.
    // A control that is present but zero-width is neither aligned nor reachable, so it is
    // convicted rather than skipped -- an earlier version of this check passed when the
    // buttons were hidden, because a 0x0 rect at (0,0) is perfectly "aligned".
    if (name === 'domains') {
      const cols = await page.evaluate(() => {
        const read = (sel, side) => Array.from(document.querySelectorAll(sel)).map((n) => {
          const r = n.getBoundingClientRect();
          return { w: r.width, v: side === 'left' ? r.left : r.right };
        });
        const spread = (list) => (list.length
          ? Math.max(...list.map((e) => e.v)) - Math.min(...list.map((e) => e.v)) : 0);
        const actions = read('.list-item > button', 'left');
        // Pills are measured only in rows that carry an action. Other `.list-item`s on this
        // route (the shape-notice rows below the registry) legitimately have no trailing
        // button, so their pills sit elsewhere by design -- sweeping them in convicted a
        // correct layout with a 656px "ragged" spread on the first run of this check.
        const pills = read('.list-item:has(> button) > .tag', 'right');
        const liveActions = actions.filter((e) => e.w > 0);
        const livePills = pills.filter((e) => e.w > 0);
        return {
          actionTotal: actions.length,
          actionVisible: liveActions.length,
          actionSpread: Math.round(spread(liveActions)),
          pillTotal: pills.length,
          pillInvisible: pills.length - livePills.length,
          pillSpread: Math.round(spread(livePills)),
        };
      });
      if (cols.actionTotal < 2) {
        specProblems.push(`${w}:domains showed ${cols.actionTotal} row action(s) -- the `
          + 'registry carries one per declared pack_id, so alignment cannot be judged here');
      } else if (cols.actionVisible !== cols.actionTotal) {
        specProblems.push(`${w}:domains ${cols.actionTotal - cols.actionVisible} of `
          + `${cols.actionTotal} row actions have zero width; an invisible control is `
          + 'neither aligned nor reachable and must not be counted as tidy');
      } else if (cols.actionSpread > 1) {
        specProblems.push(`${w}:domains row actions are ragged across ${cols.actionSpread}px`);
      }
      if (cols.pillTotal >= 2 && cols.pillInvisible === 0 && cols.pillSpread > 1)
        specProblems.push(`${w}:domains verdict pills are ragged across ${cols.pillSpread}px`);
    }
    for (const [route, selector, label, predicate] of INTERACTIONS) {
      if (route !== name) continue;
      const key = `${w}:${name}+${label}`;
      const present = await page.locator(selector).count();
      if (present !== 1) { interactionMissing.push(`${key} ${selector} count=${present}`); continue; }
      await page.click(selector);
      let settled = null;
      try {
        // Each predicate is authored above as a function-expression string so the sweep stays
        // declarative. Playwright evaluates a bare string as an EXPRESSION, which would make the
        // predicate itself the (truthy) result, so it has to become a function first.
        settled = await page.waitForFunction(eval(predicate), { timeout: 25000 });
      } catch (unused) {
        interactionMissing.push(`${key}: the readback never settled within 25s`);
        await page.keyboard.press('Escape');
        continue;
      }
      const state = await settled.jsonValue();
      if (state === 'no-box' || state === 'no-groups') {
        interactionMissing.push(`${key}: the measured surface vanished from the document`);
        await page.keyboard.press('Escape');
        continue;
      }
      await page.waitForTimeout(400);
      const im = await page.evaluate(MEASURE);
      // The state travels with the measurement: a clean geometry report from a panel that showed a
      // refusal would otherwise look identical to a clean one from a panel that read the ledger back.
      im.state = state;
      report.routes[key] = im;
      interactionStates.push(`${key}=${state}`);
      if (label === 'global-search') {
        // A panel that clips its own tail is invisible to every sideways check: nothing is
        // clipped per element and nothing crosses the right edge, the content is simply below
        // an `overflow:hidden` box. Prove the last row can actually be reached.
        const proof = await page.evaluate(() => {
          const items = document.getElementById('paletteItems');
          if (!items) return { ok: false, why: 'no #paletteItems' };
          const scrollable = items.scrollHeight > items.clientHeight + 1;
          const before = items.scrollTop;
          items.scrollTop = items.scrollHeight;
          const reached = !scrollable || items.scrollTop > before;
          const rows = items.querySelectorAll('.item');
          const last = rows[rows.length - 1];
          let hit = 'no-last-row';
          if (last) {
            const r = last.getBoundingClientRect();
            const probe = document.elementFromPoint(Math.round(r.left + r.width / 2),
              Math.round(r.top + Math.min(r.height / 2, 8)));
            hit = (probe === last || last.contains(probe)) ? 'reachable'
              : (probe ? `covered-by ${probe.tagName}.${probe.className || probe.id}` : 'null');
          }
          const out = { ok: reached && hit === 'reachable', scrollable, reached, hit,
            scrollHeight: items.scrollHeight, clientHeight: items.clientHeight,
            rows: rows.length };
          items.scrollTop = before;
          return out;
        });
        report.routes[key].scrollProof = proof;
        if (!proof.ok) {
          specProblems.push(`${key} grouped search cannot reach its last row: `
            + JSON.stringify(proof));
        }
      }
      // An overlay left open would ride along into every later route's measurement.
      await page.keyboard.press('Escape');
      await page.waitForTimeout(250);
      clippedTotal += im.clipped.length;
      strayTotal += im.stray.length;
      tinyTotal += im.tiny.length;
      for (const o of im.occluded) {
        specProblems.push(`${key} ${o.label} (${o.sel}) covered by ${o.by}`);
      }
      console.log(`w=${String(w).padEnd(5)} ${key.padEnd(34)} docX=${String(im.docOverflowX).padStart(3)} `
        + `clipped=${String(im.clipped.length).padStart(2)} stray=${String(im.stray.length).padStart(2)} `
        + `scrollOk=${String(im.scrollOk).padStart(2)} tiny=${String(im.tiny.length).padStart(2)} `
        + `state=${state}`);
    }
    clippedTotal += m.clipped.length;
    strayTotal += m.stray.length;
    tinyTotal += m.tiny.length;
    for (const o of m.occluded) {
      specProblems.push(`${w}:${name} ${o.label} (${o.sel}) covered by ${o.by}`);
    }
    console.log(`w=${String(w).padEnd(5)} ${name.padEnd(13)} docX=${String(m.docOverflowX).padStart(3)} clipped=${String(m.clipped.length).padStart(2)} stray=${String(m.stray.length).padStart(2)} scrollOk=${String(m.scrollOk).padStart(2)} tiny=${String(m.tiny.length).padStart(2)}`);
  }
  // T08 — the sidebar's "more below" cue. Every UI gate so far varied only the WIDTH, so a
  // nav list that overflows vertically was never exercised at all. The cue is a sticky 26px
  // band with `pointer-events:none` over a gradient, so covering the last item is its design
  // and asserting non-overlap would be wrong. What has to hold is that it appears exactly
  // while there is more to see and disappears at the end -- and that a window short enough to
  // make the question real was actually measured.
  await page.setViewportSize({ width: w, height: shortHeight });
  await page.waitForTimeout(700);
  const cue = await page.evaluate(async () => {
    const nav = document.querySelector('.nav');
    if (!nav) return { present: false };
    const foot = document.querySelector('.sidebar-footer');
    const read = () => ({
      // scrollHeight is viewport-independent, so DESIGN.md can quote the list's own height
      // instead of re-deriving it from (hiddenPx + clientHeight) at one window size.
      contentPx: nav.scrollHeight,
      hiddenPx: nav.scrollHeight - nav.clientHeight,
      atEnd: nav.scrollTop + nav.clientHeight >= nav.scrollHeight - 1,
      cue: nav.classList.contains('has-scroll-more'),
      // The same boundary the nominal-height pass measures, now at a height short enough that
      // the list overflows hard. Height was the one dimension no gate asserted: the nav's
      // bottom gap is a fixed margin so it should hold, but "should" is what this file is
      // for -- and at the short height the cue band, the cut line and the footer crowd together.
      gap: foot ? Math.round(foot.getBoundingClientRect().top - nav.getBoundingClientRect().bottom) : null,
    });
    nav.scrollTop = 0;
    nav.dispatchEvent(new Event('scroll'));
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const top = read();
    nav.scrollTop = nav.scrollHeight;
    nav.dispatchEvent(new Event('scroll'));
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const end = read();
    return { present: true, top, end };
  });
  report.navCue = report.navCue || {};
  report.navCue[w] = cue;
  if (!cue.present) {
    specProblems.push(`${w}: 侧栏 .nav 不在文档里，溢出提示无从判断`);
  } else if (cue.top.hiddenPx <= 0) {
    specProblems.push(`${w}: ${shortHeight}px 高的窗口下侧栏没有溢出（hiddenPx=${cue.top.hiddenPx}），`
      + '溢出提示这条断言因此没有测到任何东西');
  } else {
    if (!cue.top.cue)
      specProblems.push(`${w}: 侧栏在顶部且还有 ${cue.top.hiddenPx}px 没显示，`
        + '却没有出现"下面还有"提示');
    if (cue.end.cue)
      specProblems.push(`${w}: 侧栏已滚到底，提示仍然亮着`);
    // 6px is the same floor the nominal-height pass uses: below that the footer hairline is close
    // enough to a half-cut glyph to read as an underline drawn under it.
    if (cue.top.gap === null)
      specProblems.push(`${w}: ${shortHeight}px 高下找不到 .sidebar-footer，边界无从判断`);
    else if (cue.top.gap < 6)
      specProblems.push(`${w}@${shortHeight}h: 页脚边框在导航切割线下方 ${cue.top.gap}px`);
    console.log(`w=${String(w).padEnd(5)} nav-cue     hiddenPx=${String(cue.top.hiddenPx).padStart(4)} `
      + `atTop=${cue.top.cue} atEnd=${cue.end.cue} gap${shortHeight}=${cue.top.gap}`);
  }
  // The brand mark is the owner's vector, inlined into the stylesheet as a data URI (the service
  // serves a fixed three-path allowlist under `img-src data:`), so "is the logo showing?" cannot
  // be answered from the CSS text: the declaration survives a malformed URI, and the vm harness
  // never mounts the shell at all (its MockElement has no querySelector, which is the shell's own
  // capability guard).
  //
  // This probe measured the superseded bitmap tile until 2026-10-25 and went red on the exact-SHA
  // cloud run: it decoded a `data:image/png` and required 144x144 with a 48x48 box and a bloom.
  // The shipped surface is now `.app-nav-mark` -- 22px, an SVG encoding that flips to the theme's
  // ink, and no filter (a drop-shadow on a masked glyph is clipped away by paint order anyway).
  // So the assertions are about the vector: the URI decodes to an svg carrying path geometry and
  // the ink the token claims, the figure paints at its declared size, it stays out of the
  // accessible name, and the name itself is still text next to it.
  const brand = await page.evaluate(() => {
    const tile = document.querySelector('.app-nav-mark');
    if (!tile) return { present: false };
    const style = getComputedStyle(tile);
    const rect = tile.getBoundingClientRect();
    const match = /url\("?(data:image\/svg\+xml;base64,[A-Za-z0-9+/=]+)"?\)/
      .exec(style.backgroundImage || '');
    const brand = document.querySelector('.app-nav-brand');
    return {
      present: true,
      text: (tile.textContent || '').trim(),
      ariaHidden: tile.getAttribute('aria-hidden'),
      size: [Math.round(rect.width), Math.round(rect.height)],
      uri: match ? match[1] : '',
      name: brand ? (brand.textContent || '').trim() : '',
    };
  });
  // Decoding inside the page proves the URI is loadable by a real SVG decoder, and reading the
  // bytes back out proves which artwork it is -- an image that decodes is not yet the right image.
  const decode = brand.uri
    ? await page.evaluate(async (uri) => {
      const ok = await new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(true);
        img.onerror = () => resolve(false);
        img.src = uri;
      });
      const text = atob(uri.split(',')[1]);
      return { loads: ok, svg: text.startsWith('<svg'), paths: (text.match(/<path /g) || []).length,
        fills: ['#EEF2F5', '#17212B'].filter((f) => text.includes(f)) };
    }, brand.uri)
    : { loads: false, svg: false, paths: 0, fills: [] };
  const seen = { ...brand, uriChars: brand.uri.length, decode };
  delete seen.uri; // 6.6 KB of base64 does not belong in a report a human reads.
  report.brand[w] = seen;
  if (!brand.present) {
    brandProblems.push(`${w}: no .app-nav-mark in the mounted shell`);
  } else {
    if (brand.text) brandProblems.push(`${w}: the figure carries text "${brand.text}"`);
    if (brand.ariaHidden !== 'true') brandProblems.push(`${w}: the figure is not aria-hidden`);
    if (brand.uriChars < 500) brandProblems.push(`${w}: the inlined uri is ${brand.uriChars} chars`);
    if (!decode.loads) brandProblems.push(`${w}: the data uri did not decode in the browser`);
    if (!decode.svg) brandProblems.push(`${w}: the uri is not an svg document`);
    if (decode.paths < 1) brandProblems.push(`${w}: the svg carries no path geometry`);
    if (decode.fills.length !== 1) {
      brandProblems.push(`${w}: the mark should carry exactly one of the two brand inks, `
        + `got ${JSON.stringify(decode.fills)}`);
    }
    if (!brand.name.includes('DESIGN-LAB')) brandProblems.push(`${w}: no wordmark beside the mark`);
    // A collapsed rail legitimately has no box to measure.
    if (brand.size[0] > 0 && brand.size.join('x') !== '22x22')
      brandProblems.push(`${w}: the mark is ${brand.size.join('x')}, not 22x22`);
  }
  await page.close();
}
await browser.close();

// Reduce the nav/footer boundary to the tightest observation per width. A scrolling list must
// cut SOME item in half at its edge; that is not the defect. The defect is the identity
// footer's 1px top border sitting on that cut line, where it reads as an underline drawn
// under a half-visible word -- and no CLIPPED check can see it, because the item is whole
// inside its own box. Six px is the shortest gap that separates a hairline from a glyph.
const navEdgeProblems = [];
for (const e of navEdges) {
  const w = e.key.split(':')[0];
  if (!report.navEdge[w] || e.gap < report.navEdge[w].gap) report.navEdge[w] = e;
}
for (const [w, e] of Object.entries(report.navEdge)) {
  if (e.gap < 6) {
    navEdgeProblems.push(`${w}px: footer hairline ${e.gap}px under the nav cut line`
      + (e.labelStraddling ? ', a group label is half-cut on it' : ''));
  }
}

if (outPath) writeFileSync(outPath, JSON.stringify(report, null, 2));
if (specProblems.length) {
  console.log('OV_SPEC_BROKEN ' + specProblems.join(' | '));
  fail('OV_SPEC_BROKEN');
}
if (interactionMissing.length) {
  console.log('OV_INTERACTION_UNMEASURED ' + interactionMissing.join(' | '));
  fail('OV_INTERACTION_UNMEASURED');
}
if (brandProblems.length) {
  console.log('OV_BRAND_BROKEN ' + brandProblems.join(' | '));
  fail('OV_BRAND_BROKEN');
}
if (navEdgeProblems.length) {
  console.log('OV_NAV_EDGE_TIGHT ' + navEdgeProblems.join(' | '));
  fail('OV_NAV_EDGE_TIGHT');
}

console.log('');
console.log(`OV_SUMMARY clipped=${clippedTotal} stray=${strayTotal} tiny=${tinyTotal} interactions=${interactionStates.length} [${interactionStates.join(',')}] brand=${Object.keys(report.brand).length} navEdge=${Object.keys(report.navEdge).length} spec=${specProblems.length} theme=${uiPalette}/${uiScheme}`);
if (clippedTotal > 0) {
  for (const [k, v] of Object.entries(report.routes)) {
    for (const c of v.clipped) console.log(`  CLIPPED ${k} +${c.by}px ${c.el.slice(0, 100)}`);
  }
  console.error('OV_FAIL: content is being cut off');
  process.exit(1);
}
if (strayTotal > 0) {
  for (const [k, v] of Object.entries(report.routes)) {
    for (const s of v.stray) console.log(`  STRAY ${k} +${s.over}px ${s.el.slice(0, 100)}`);
  }
  console.error('OV_FAIL: content is unreachable (no scrollable ancestor)');
  process.exit(1);
}
if (strict && tinyTotal > 0) {
  console.error(`OV_FAIL: ${tinyTotal} text node(s) below 11px`);
  process.exit(1);
}
console.log('OV_OK: no clipped or unreachable text');
