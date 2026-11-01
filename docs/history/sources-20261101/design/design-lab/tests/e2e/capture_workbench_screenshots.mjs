// SPDX-License-Identifier: MIT
// Viewport screenshot capture for the Workbench (E1/E2 visual proof only).
// Drives the REAL loopback service with the committed build/main.js in a real
// Chromium: bootstrap a project through the UI, then capture every routed page
// at each declared viewport and write PNGs + a hash manifest next to them.
// Env: E2E_SERVICE_URL E2E_TOKEN E2E_NODE_MODULES [E2E_BROWSER]
//      CAP_OUT_DIR CAP_COMMIT CAP_WIDTHS CAP_SOURCE_IMAGE CAP_PYTHON_VERSION
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import path from 'node:path';

const serviceUrl = process.env.E2E_SERVICE_URL;
const token = process.env.E2E_TOKEN;
const nmDir = process.env.E2E_NODE_MODULES;
const browser = process.env.E2E_BROWSER;
const outDir = process.env.CAP_OUT_DIR;
const commit = process.env.CAP_COMMIT || 'unknown';
const sourceImage = process.env.CAP_SOURCE_IMAGE || '';
// Set by --seed-native-plan: submit one never-run native plan into the project THIS run creates.
const seedNativePlan = process.env.CAP_SEED_NATIVE_PLAN === '1';
// Set by --seed-assistance-plan: file one synthetic assistance plan with shot rows, a second
// revision, a named choice and one voluntary report, so the plan-detail surfaces can be rendered
// at all (they are states of a stored plan, not of the empty form).
const seedAssistancePlan = process.env.CAP_SEED_ASSISTANCE_PLAN === '1';
// Repo-relative when the file is inside the checkout, absolute (and visibly so) when the
// operator pointed at something outside it.
const referenceSourceRecorded = (() => {
  if (!sourceImage) return null;
  const rel = path.relative(process.cwd(), sourceImage).split(path.sep).join('/');
  return rel && !rel.startsWith('..') && !path.isAbsolute(rel) ? rel : sourceImage;
})();
const pythonVersion = process.env.CAP_PYTHON_VERSION || 'unknown';
const widths = (process.env.CAP_WIDTHS || '1280,1920,2560').split(',').map((w) => Number.parseInt(w, 10)).filter((w) => Number.isFinite(w) && w > 0);

// DL-UI-U02 (2026-10-09): which colour theme a PNG shows belongs to the evidence, so it
// comes from the environment, is applied to every page before it is shot, and goes into
// the filename. The default theme keeps the byte-identical file names it had before, so
// nothing that reads this directory has to change; only a themed run gets a suffix.
// This drives the same two <html> attributes applyTheme() writes from ?palette/?scheme
// (the service dispatches `/workbench` by exact path, so a query string is not an option
// for a driver that reloads the page).
const uiPalette = process.env.UI_PALETTE || 'design-lab';
const uiScheme = process.env.UI_SCHEME || 'dark';
const themeTag = (uiPalette === 'design-lab' && uiScheme === 'dark')
  ? '' : `@${uiPalette}-${uiScheme}`;
// addInitScript runs before ANY page script, so the two <html> attributes already
// exist when the bundle mounts. Setting them after `load` instead would leave the
// theme controls describing the palette that was read at boot (the app renders its
// label from the applied state), i.e. a PNG whose caption contradicts its pixels.
const paintTheme = async (page) => {
  await page.addInitScript(([p, s]) => {
    const apply = () => {
      document.documentElement.setAttribute('data-palette', p);
      if (s === 'light') document.documentElement.setAttribute('data-scheme', 'light');
      else document.documentElement.removeAttribute('data-scheme');
    };
    if (document.documentElement) apply();
    else document.addEventListener('DOMContentLoaded', apply);
  }, [uiPalette, uiScheme]);
};

// Heights are the CSS viewport each width is captured at. 2048x1152 is measured, not invented:
// it is the box the owner's machine renders in (Screen.Bounds 2048x1152, AppliedDPI 120 on a
// 2560x1440 panel at 125%). Without this entry the fallback below would have captured that width
// at 1270 -- an aspect ratio nobody has.
const VIEWPORT_HEIGHT = { 390: 844, 768: 1024, 1280: 800, 1440: 900, 1920: 1080, 2048: 1152, 2560: 1440 };
const heightFor = (w) => VIEWPORT_HEIGHT[w] ?? Math.round(w * 0.62);

const fail = (reason) => {
  console.error('CAP_FAIL: ' + reason);
  process.exit(2);
};
if (!serviceUrl || !token || !nmDir || !outDir) fail('CAP_CONFIG_MISSING');
if (!/^[0-9a-f]{64}$/.test(token)) fail('CAP_TOKEN_SHAPE');
if (widths.length === 0) fail('CAP_WIDTHS_EMPTY');

const req = createRequire(nmDir + '/noop.js');
const pw = req('playwright');

// ---------------------------------------------------------------------------
// ROUTE INVENTORY -- derived from the served bundle, never typed.
//
// Same parser, same reasoning and the same fail-closed shape as the browser E2E step
// (design-lab/tests/e2e/browser_design_layer_e2e.mjs explains why the source is the bytes
// `GET /workbench/main.js` hands the browser rather than shell.ts or build/main.js on disk:
// `design_lab.workbench.resource()` prefers the installed wheel copy, so committed and
// served bytes can diverge, and the served copy is what a PNG can actually show).
// It is duplicated here instead of imported because a capture driver and an E2E driver are
// launched with different cwd/env contracts, and neither may fail to start because the
// other file moved; the duplication is two owned files, not a third contract.
//
// What this buys: the hand-written PAGES list below can be checked against the routes the
// served app really mounts, so a new ROUTE_VIEWS entry cannot silently go uncaptured and a
// captured hash that no longer names a route cannot silently keep producing a PNG of a
// "not open" panel.
// ---------------------------------------------------------------------------
const ROUTE_TABLE_MARKER = 'const ROUTE_VIEWS = [';

const sliceArrayBody = (text, openIndex) => {
  let depth = 0, inStr = null, esc = false;
  for (let i = openIndex; i < text.length; i += 1) {
    const ch = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === '\\') esc = true;
      else if (ch === inStr) inStr = null;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') inStr = ch;
    else if (ch === '[' || ch === '{') depth += 1;
    else if (ch === ']' || ch === '}') {
      depth -= 1;
      if (depth === 0) return text.slice(openIndex + 1, i);
    }
  }
  return null;
};

const sliceEntryObjects = (body) => {
  const out = [];
  let depth = 0, buf = '', inStr = null, esc = false;
  for (const ch of body) {
    if (inStr) {
      buf += ch;
      if (esc) esc = false;
      else if (ch === '\\') esc = true;
      else if (ch === inStr) inStr = null;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') { inStr = ch; buf += ch; continue; }
    if (ch === '{') depth += 1;
    if (depth > 0) buf += ch;
    if (ch === '}') {
      depth -= 1;
      if (depth === 0) { out.push(buf); buf = ''; }
    }
  }
  return out;
};

const stringField = (obj, key) => {
  const m = obj.match(new RegExp('\\b' + key + '\\s*:\\s*["\']([^"\']*)["\']'));
  return m ? m[1] : null;
};

/** -> [{hash, view}] | null; null means "unreadable", never "no routes". */
const parseRouteViews = (bundleText) => {
  const markerAt = bundleText.indexOf(ROUTE_TABLE_MARKER);
  if (markerAt < 0) return null;
  const body = sliceArrayBody(bundleText, markerAt + ROUTE_TABLE_MARKER.length - 1);
  if (body === null) return null;
  const routes = [];
  for (const obj of sliceEntryObjects(body)) {
    const hash = stringField(obj, 'hash');
    const view = stringField(obj, 'view');
    if (hash === null || view === null) return null;
    if (hash !== '' && !hash.startsWith('#/')) return null;
    routes.push({ hash, view });
  }
  return routes.length > 0 ? routes : null;
};

/** Read the route table out of the bundle this service is serving. */
const deriveRouteInventory = async () => {
  let res;
  try {
    res = await fetch(serviceUrl.replace(/\/$/, '') + '/workbench/main.js');
  } catch (err) {
    fail('CAP_ROUTE_INVENTORY_UNAVAILABLE: GET /workbench/main.js threw ' +
      String(err && err.message ? err.message : err).split('\n')[0]);
  }
  if (!res || !res.ok) {
    fail('CAP_ROUTE_INVENTORY_UNAVAILABLE: GET /workbench/main.js answered ' +
      (res ? res.status : 'no response'));
  }
  const text = await res.text();
  const routes = parseRouteViews(text);
  if (routes === null) {
    fail('CAP_ROUTE_INVENTORY_UNREADABLE: no parseable `' + ROUTE_TABLE_MARKER +
      '` in the served bundle (' + text.length + ' chars)');
  }
  return { routes, chars: text.length, sha256: sha256Hex(text) };
};

const sha256Hex = (text) => createHash('sha256').update(text).digest('hex');

// Routed pages, in capture order. `dynamic` pages need the bootstrapped id and name the
// table route they drill into through `base` (a parameterized address is not a ROUTE_VIEWS
// entry of its own -- see shell.ts's B07 note -- so it covers its list route, never itself).
//
// This list used to cover 8 of the 12 entries in shell.ts ROUTE_VIEWS, so four routed
// pages -- including 品牌系统, which has a real /api/* readback -- had never been
// rendered by any screenshot round. A route that is never captured cannot fail the
// geometry gates either, so the omission read as "the UI is audited".
//
// That hole is now machine-checked, not just documented: the gate under this list compares
// PAGES against the route table of the bundle the service is serving and exits non-zero if
// a routed entry has no page here (or if a page here names a route the table no longer
// has). Adding a route to shell.ts and forgetting it in this list is a red run, not a
// silent gap in the evidence.
//
// The landing surface (工作台) is the app shell, not a `#route-view` page: measured,
// at the landing URL `#route-view` stays present but empty and hidden, so waiting on it
// times out. It used to be left out on the belief that the browser E2E shot it -- that
// E2E only writes a PNG on failure (`fail.png`), so in a normal run the primary surface
// was never captured by anything. It is captured here against its own host element.
const PAGES = [
  { key: 'workbench', hash: '', host: '#workspace' },
  { key: 'dashboard', hash: '#/dashboard' },
  { key: 'projects', hash: '#/projects' },
  { key: 'project-detail', hash: null, dynamic: true, base: '#/projects' },
  { key: 'research', hash: '#/research' },
  { key: 'brand-systems', hash: '#/brand-systems' },
  { key: 'domains', hash: '#/domains' },
  { key: 'creative-tools', hash: '#/tools' },
  { key: 'deliverables', hash: '#/deliverables' },
  { key: 'evidence', hash: '#/evidence' },
  { key: 'collaboration', hash: '#/collaboration' },
  { key: 'preflight', hash: '#/preflight' },
  { key: 'settings', hash: '#/settings' },
  // DL-UI-U02 (2026-10-09): 首批页面。能力目录读 GET /api/capabilities；界面状态与
  // 组件规范是规格面。不进这份清单就等于从没被渲染过，也就不会在任何闸报错。
  { key: 'capabilities', hash: '#/capabilities' },
  // R2 §5 (DL-UI-U03): 一条能力的独立地址。id 来自已提交的 vendor/sources.lock.json；
  // 若该记录不再存在，界面会画出"未找到该记录"的诚实面板，实拍就会把它照出来。
  { key: 'capability-detail', hash: '#/capabilities/anydesign' },
  // R2 §2 (DL-UI-U03): 一个域包的独立地址。brand-design 是本批读回里通过结构校验的
  // 目录之一；被拒绝的 minigame-design 也能寻址，但它的面板带 11 条校验原因，留给
  // vm 合同面逐条核对，这里取一张能代表常规形态的图。
  { key: 'domain-detail', hash: '#/domains/brand-design' },
  { key: 'states', hash: '#/states' },
  { key: 'components', hash: '#/components' },
  { key: 'intake', hash: '#/intake' },
  { key: 'plan', hash: '#/plan' },
  { key: 'analysis', hash: '#/analysis' },
  // 提示词工程与模型选择是两条新读面：#/prompts 读 design-layer 与 assets 并发两条
  // POST 路由，#/models 读 GET /api/models。不进这份清单就等于从没被渲染过，也就不会
  // 在任何几何闸上报错——这个洞 2026-10-07 记过一次，清单与路由表的比对现在是机器做的。
  { key: 'prompt-intelligence', hash: '#/prompts' },
  { key: 'model-selection', hash: '#/models' },
  // R2 §7 (DL-UI-U04): 制作记录与待继续。读 GET /projects/{id}/tasks。
  { key: 'records', hash: '#/records' },
  // DL-KB-03 (2026-10-23): 知识与提示词库。搜索是主视觉，读 GET /api/knowledge-entries/search；
  // 不进这份清单就等于这一面从没被真实渲染过，也就不会在任何闸上报错。
  { key: 'knowledge', hash: '#/knowledge' },
  // DL-KB-08 (2026-10-24): 设计辅助的初始态与方案详情。空台账下只有表单与「尚无方案」，
  // 四态图例与输出类型词表都来自服务读回；它是日常入口，不能只存在于路由表里。
  { key: 'assistant', hash: '#/assistant' },
  // The plan detail, reached the way a person reaches it: click a row in 最近的方案. With
  // CAP_SEED_ASSISTANCE_PLAN the row exists and carries a shot table, a named choice, a second
  // revision and one voluntary report, so the four state chips, the 镜头表, the material formats,
  // the feedback history and the revision comparison are all in the frame.
  { key: 'assistant-plan', hash: '#/assistant', click: '#as-list .as-plan-open',
    settle: '#as-plan' },
  // DL-KB-10 (2026-10-24): 目标组合选择面板。默认态是「暂不指定」：五个选择框、两栏对照
  // （官方支持 / 本项目未测试）与"这一屏不给路线"那句状态说明都来自五条 /api/target-profile*
  // 读回。不进这份清单就等于这一面从没被真实渲染过，也就不会在任何闸上报错。
  { key: 'target-profiles', hash: '#/target-profiles' },
  // R2 §9 (DL-FINAL-T08): 分组全局搜索是浮层，只能靠真实点击打开后才有可审阅的一张图。
  { key: 'search-groups', hash: '#/capabilities', click: '#openPalette' },
  { key: 'automation', hash: '#/automation' },
];

// --- route coverage gate: runs before the browser launches, so a gap costs no PNGs ------
// Every hash the served app mounts as a route must have a page in PAGES, and every hash in
// PAGES must still name a route (or drill into one, for the detail addresses). The hand
// list stays the order/extra-screens authority -- project-detail, the seeded states and the
// search overlay are not ROUTE_VIEWS entries and are not required to be -- but it can no
// longer be silently incomplete.
const inventory = await deriveRouteInventory();
const routeInventory = {
  source: 'served bundle GET /workbench/main.js',
  bundleSha256: inventory.sha256,
  bundleChars: inventory.chars,
  routeEntryCount: inventory.routes.length,
};
const tableHashes = new Set(inventory.routes.map((r) => r.hash));
const byHash = new Map(inventory.routes.map((r) => [r.hash, r]));

// Drilling forms are legal only as `<table hash>/<id>`: a detail address is a second-level
// entry of a list route (shell.ts B07), never a route of its own.
const drillsIntoTable = (hash) => [...tableHashes]
  .some((t) => t !== '' && (hash === t + '/' || hash.startsWith(t + '/')));

const stale = PAGES
  .filter((p) => !p.dynamic && typeof p.hash === 'string' &&
    !tableHashes.has(p.hash) && !drillsIntoTable(p.hash))
  .map((p) => p.key + ' -> ' + p.hash);
if (stale.length > 0) {
  fail('CAP_ROUTE_NOT_IN_TABLE: ' + stale.join(', ') +
    ' -- the served route table has no such hash, so this page renders a "not open" panel ' +
    'and the PNG would be evidence of a route that does not exist');
}
const badDynamic = PAGES
  .filter((p) => p.dynamic && (typeof p.base !== 'string' || !tableHashes.has(p.base)))
  .map((p) => p.key + ' base=' + String(p.base));
if (badDynamic.length > 0) {
  fail('CAP_DYNAMIC_PAGE_BASE_UNKNOWN: ' + badDynamic.join(', ') +
    ' -- a dynamic page must name the route table hash it drills into via `base`');
}

const covered = new Set(PAGES
  .filter((p) => !p.dynamic && typeof p.hash === 'string')
  .map((p) => p.hash));
const uncaptured = inventory.routes
  .filter((r) => !covered.has(r.hash))
  .map((r) => (r.hash === '' ? '(landing)' : r.hash) + ' ' + (byHash.get(r.hash) || {}).view);
if (uncaptured.length > 0) {
  fail('CAP_ROUTE_UNCAPTURED: ' + uncaptured.join(', ') +
    ' -- a served route with no PAGES entry is a route no screenshot round has ever ' +
    'rendered, which is the coverage hole this file documented and did not check');
}
console.log('CAP_ROUTE_COVERAGE routes=' + inventory.routes.length +
  ' captured=' + covered.size + ' of ' + inventory.routes.length +
  ' pageEntries=' + PAGES.length + ' bundleSha256=' + inventory.sha256);

mkdirSync(outDir, { recursive: true });

const launchOpts = { headless: true };
if (browser) launchOpts.executablePath = browser;
const b = await pw.chromium.launch(launchOpts);
let browserVersion = 'unknown';
try {
  browserVersion = b.version();
} catch {
  // version probe is best-effort; launch errors must dominate the run.
}

const shots = [];
const problems = [];
const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');

// Build Output Truth: the served bundle is the committed byte, so bind its hash
// to the record instead of only naming the commit.
const bundleSubject = () => {
  const rel = path.join('apps', 'workbench', 'build', 'main.js');
  const abs = path.resolve(rel);
  if (!existsSync(abs)) return { bundle: rel, bundleSha256: 'MISSING' };
  const bytes = readFileSync(abs);
  return { bundle: rel, bundleBytes: bytes.length, bundleSha256: sha256(bytes) };
};

// A failed bootstrap is far more diagnosable with the live DOM next to the
// stack, so dump the visible status/notice text before exiting.
let livePage = null;
const dumpDiagnostics = async (err) => {
  let text = 'no live page';
  if (livePage) {
    text = await livePage
      .evaluate(() => Array.from(document.querySelectorAll('p[id],ul[id]'))
        .map((n) => n.id + ' :: ' + (n.textContent || '').trim().slice(0, 300)).join('\n'))
      .catch(() => 'diagnostics unavailable');
  }
  writeFileSync(path.join(outDir, 'capture-debug.txt'),
    String(err && err.stack ? err.stack : err) + '\n\n' + text, 'utf8');
  console.error(text);
  fail('CAP_BOOTSTRAP_FAILED');
};

const openWorkspace = async (width) => {
  const ctx = await b.newContext({ viewport: { width, height: heightFor(width) } });
  const page = await ctx.newPage();
  livePage = page;
  page.on('pageerror', (e) => problems.push(`pageerror@${width}: ` + String(e)));
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push(`console@${width}: ` + m.text());
  });
  await paintTheme(page);
  await page.goto(serviceUrl + '/workbench', { waitUntil: 'load' });
  await page.locator('#token').fill(token);
  await page.locator('#connect-form button').first().click();
  await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
  return { ctx, page };
};

// --- bootstrap a real project through the UI (no fixture injection) ---------
const stamp = Date.now();
const projectName = 'Closeout ' + stamp;
let projectId = '';
try {
  const { ctx, page } = await openWorkspace(1280);
  await page.locator('#project-name').fill(projectName);
  await page.locator('#create-form button').first().click();
  await page.locator('#project option', { hasText: projectName })
    .first().waitFor({ state: 'attached', timeout: 20000 });
  await page.locator('#project').selectOption({ label: projectName });
  projectId = await page.locator('#project').inputValue();
  if (!projectId) fail('CAP_PROJECT_ID_MISSING');

  // --- capture scaffolding: one never-run native plan, on THIS project -------------------------
  // Every capture run boots its own synthetic state, so `#/records` reads zero tasks and the
  // affordances that exist only on a native row -- the 接续 entry -- appear on no screenshot.
  // The order matters and was measured the hard way: seeding before the driver creates its project
  // yields two projects, and the page stops at the chooser (it auto-selects a lone project only).
  // This is scaffolding, not evidence of a submitted job: the plan has no layers, is never run, and
  // dies with the temporary root. `capture-scaffold.json` says so beside the PNGs.
  if (seedNativePlan) {
    const base = serviceUrl.replace(/\/$/, '');
    const auth = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    const plan = {
      host: 'photoshop',
      rir: {
        schemaVersion: 'design-lab/reconstruction-ir/v1',
        canvas: { width: 8, height: 6, colorSpace: 'srgb',
                  background: { color: '#ffffff', recorded: true } },
        layers: [],
      },
      text_styles: {},
      idempotency_key: 'capture-scaffold-0001',
    };
    const submitted = await fetch(`${base}/api/projects/${projectId}/native-plans`,
      { method: 'POST', headers: auth, body: JSON.stringify(plan) });
    const body = await submitted.json().catch(() => ({}));
    if (submitted.status !== 202) {
      fail(`CAP_SEED_NATIVE_PLAN_REFUSED ${submitted.status} ${JSON.stringify(body).slice(0, 200)}`);
    }
    const kind = String((body.task || {}).kind || '');
    if (!kind.endsWith('-native')) {
      fail(`CAP_SEED_NATIVE_PLAN_KIND ${kind || '(empty)'}: not a native kind, so the row would `
        + 'carry no 接续 entry and the screenshots would prove nothing');
    }
    // Read the row back through the same endpoint the page uses: a plan that the projection does
    // not list would render nothing, and the PNG would then be evidence of an absent control.
    const listed = await (await fetch(`${base}/api/projects/${projectId}/tasks`,
      { headers: { Authorization: `Bearer ${token}` } })).json().catch(() => ({}));
    const rows = Array.isArray(listed.tasks) ? listed.tasks : [];
    if (!rows.some((row) => String(row.kind || '').endsWith('-native'))) {
      fail(`CAP_SEED_NATIVE_PLAN_NOT_LISTED kinds=[${rows.map((r) => r.kind).join(',')}]`);
    }
    writeFileSync(path.join(outDir, 'capture-scaffold.json'), JSON.stringify({
      scaffolding: true,
      note: '合成捕获脚手架：一个从未运行的 native plan，只为让接续入口出现在画面里；'
        + '随临时项目根一起丢弃，不是任何人提交的作业。',
      project_id: projectId,
      project_name: projectName,
      task_id: (body.task || {}).id || (body.task || {}).job_id,
      task_kind: kind,
      attempt_state: ((body.task || {}).attempt || {}).state,
      listed_rows: rows.length,
      host: plan.host,
      rir_layers: plan.rir.layers.length,
      never_run: true,
      no_host_side_effects: true,
    }, null, 2) + '\n', 'utf8');
    console.log(`CAP_SCAFFOLD=SEEDED kind=${kind} rows=${rows.length} project=${projectId}`);
  }

  // --- capture scaffolding: one synthetic assistance plan with shot rows -------------------------
  // Without this, every screenshot of `#/assistant` shows the empty form, and the plan screen's
  // actual surfaces -- the four state chips, the 镜头表, the four material formats, the voluntary
  // feedback history, the revision comparison -- are never rendered for anyone to look at. A review
  // that never saw them cannot claim the screen was reviewed. Like the native scaffold above, this
  // dies with the temporary project root, and the actor names say it is not a person's statement.
  if (seedAssistancePlan) {
    const base = serviceUrl.replace(/\/$/, '');
    const auth = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    const synthetic = '捕获脚手架（合成，不是真人）';
    const shotPlan = {
      objective: '为秋季新品做一条 15 秒主视觉动效，标题落在大面积留白里',
      output_type: 'MOTION',
      neutral_creative: null,
      brand_constraints: ['只用两种油墨', '标题不使用描边'],
      role_constraints: [],
      lens: '俯拍整张桌面',
      sound: '低频垫底，无对白',
      shots: [
        { index: 1, duration_s: 4, purpose: '开场：侧光落在纸纤维上',
          camera: '缓推', sound: null, reference_role: '主参考' },
        { index: 2, duration_s: null, purpose: '收束：标题一次落定，留出落版空白',
          camera: '固定', sound: '低频收干', reference_role: null },
      ],
      references: [],
      external_steps: [{ step: '在宿主里手动导出 MP4', tool: 'After Effects',
                         job_id: null, operation_id: null }],
      known_gaps: ['目标平台码率未定'],
      limits: ['不含多语言字幕', '不产出可编辑源文件'],
      created_by: synthetic,
    };
    const created = await (await fetch(`${base}/api/projects/${projectId}/assistance-plans`,
      { method: 'POST', headers: auth, body: JSON.stringify(shotPlan) })).json()
      .catch(() => ({}));
    const planId = (created.plan || {}).plan_id;
    if (!planId) {
      fail(`CAP_SEED_ASSISTANCE_PLAN_REFUSED ${JSON.stringify(created).slice(0, 240)}`);
    }
    // A second revision, so the revision list and the comparison have two real rows to show. It
    // carries the same shot table: a revision inherits the plan's content, so dropping the rows
    // here would make r2 -- the one the detail renders -- the "no shot rows" branch instead.
    const revisedBody = { ...shotPlan, neutral_creative: '两束交叉光缓慢推移，标题以一次落定收束。',
      created_by: synthetic, expected_revision: created.revision };
    const revised = await fetch(`${base}/api/projects/${projectId}/assistance-plans/${planId}/revisions`,
      { method: 'POST', headers: auth, body: JSON.stringify(revisedBody) });
    if (revised.status !== 201) {
      fail(`CAP_SEED_ASSISTANCE_REVISION_REFUSED ${revised.status} `
          + JSON.stringify(await revised.json().catch(() => ({}))).slice(0, 240));
    }
    const chose = await fetch(`${base}/api/projects/${projectId}/assistance-plans/${planId}/choose`,
      { method: 'POST', headers: auth,
        body: JSON.stringify({ actor: synthetic, actor_kind: 'human', revision: 2 }) });
    if (chose.status !== 200) {
      fail(`CAP_SEED_ASSISTANCE_CHOOSE_REFUSED ${chose.status} `
          + JSON.stringify(await chose.json().catch(() => ({}))).slice(0, 240));
    }
    const reported = await fetch(
      `${base}/api/projects/${projectId}/assistance-plans/${planId}/feedback`,
      { method: 'POST', headers: auth, body: JSON.stringify({
        outcome: 'PARTIALLY_MATCHES', target_key: 'elevenlabs--web-app--music',
        actor: synthetic, note: '标题落点可用，时长要手改（合成脚手架，不是任何人的使用记录）',
        source_ref: null, revision: 2, target_model: null,
        dimensions: [{ name: '画幅', verdict: 'PARTIALLY_MATCHES', note: null }],
        issue_timecodes: ['00:03-00:05'] }) });
    if (reported.status !== 201) {
      fail(`CAP_SEED_ASSISTANCE_FEEDBACK_REFUSED ${reported.status} `
          + JSON.stringify(await reported.json().catch(() => ({}))).slice(0, 240));
    }
    // Prove each surface has something to render by reading it back through the page's own routes;
    // a PNG of an empty list is not evidence that the control works.
    const readback = await (await fetch(
      `${base}/api/projects/${projectId}/assistance-plans/${planId}`, { headers: auth }))
      .json().catch(() => ({}));
    if ((readback.revisions || []).length !== 2 || !readback.states?.chosen
        || !readback.states?.provided) {
      fail(`CAP_SEED_ASSISTANCE_NOT_READ_BACK revisions=${(readback.revisions || []).length} `
          + JSON.stringify(readback.states || {}));
    }
    const history = await (await fetch(
      `${base}/api/projects/${projectId}/assistance-plans/${planId}/feedback`, { headers: auth }))
      .json().catch(() => ({}));
    if ((history.records || []).length !== 1) {
      fail(`CAP_SEED_ASSISTANCE_FEEDBACK_NOT_LISTED records=${(history.records || []).length}`);
    }
    const materials = await (await fetch(
      `${base}/api/assistance-plan-output-types`, { headers: auth })).json().catch(() => ({}));
    if (!Array.isArray(materials.export_formats) || materials.export_formats.length !== 4) {
      fail(`CAP_SEED_ASSISTANCE_MATERIALS_UNSERVED formats=`
          + JSON.stringify(materials.export_formats ?? null));
    }
    writeFileSync(path.join(outDir, 'capture-scaffold-assistance.json'), JSON.stringify({
      scaffolding: true,
      note: '合成捕获脚手架：一条带两行镜头的方案、第二次修订、一次具名选用与一条自愿反馈。'
        + '它只为让方案详情在截图里真的长出内容；记录人姓名标明是合成的，'
        + '随临时项目根一起丢弃，不是任何人的使用记录，也不进入任何知识出口。',
      project_id: projectId,
      plan_id: planId,
      revisions: (readback.revisions || []).length,
      shot_rows: (readback.current?.shots || []).length,
      states: readback.states,
      feedback_records: (history.records || []).length,
      formats_offered: (materials.export_formats || []).map((row) => row.value),
      synthetic_actor: synthetic,
      never_run: true,
      nothing_sent: true,
    }, null, 2) + '\n', 'utf8');
    console.log(`CAP_ASSISTANCE_SCAFFOLD=SEEDED plan=${planId} revisions=2 shots=`
      + `${(readback.current?.shots || []).length} formats=`
      + `${(materials.export_formats || []).length} project=${projectId}`);
  }

  if (sourceImage && existsSync(sourceImage)) {
    const buffer = readFileSync(sourceImage);
    await page.locator('#file').setInputFiles({
      name: path.basename(sourceImage), mimeType: 'image/png', buffer,
    });
    await page.locator('#import-button').click();
    await page.locator('#reference-picker input[type=checkbox]').first()
      .waitFor({ state: 'visible', timeout: 20000 });
    await page.locator('#reference-picker input[type=checkbox]').first().check();
  }

  await page.locator('#refresh').click();
  await page.locator('#design-systems li').first().waitFor({ state: 'visible', timeout: 20000 });
  // The refresh repopulates the project select; keep it on the bootstrapped
  // project so the bind click has a current project owner.
  await page.locator('#project').selectOption({ label: projectName });

  await page.locator('#brief-title').fill('Closeout visual proof');
  await page.locator('#brief-goals').fill('commercial, restrained, editable');
  await page.locator('#brief-submit').click();
  await page.locator('#design-briefs li', { hasText: 'BRIEF · Closeout visual proof' })
    .first().waitFor({ state: 'visible', timeout: 20000 });

  await page.locator('#direction-brief').selectOption({ index: 1 });
  await page.locator('#direction-title').fill('Closeout Direction');
  await page.locator('#direction-color').fill('warm');
  await page.locator('#direction-submit').click();
  await page.locator('#design-directions li', { hasText: 'DIRECTION · Closeout Direction' })
    .first().waitFor({ state: 'visible', timeout: 20000 });
  await page.locator('#design-directions li button', { hasText: '选为方向' })
    .first().click();
  await page.locator('#design-directions li', { hasText: 'CHOSEN by workbench-user' })
    .first().waitFor({ state: 'visible', timeout: 20000 });

  await page.locator('#design-system').selectOption({ index: 1 });
  await page.locator('#design-system-bind').click();
  await page.locator('#design-bindings li', { hasText: 'BINDING ·' })
    .first().waitFor({ state: 'visible', timeout: 20000 });
  await page.locator('#design-binding-active', { hasText: '已绑定设计系统' })
    .first().waitFor({ state: 'visible', timeout: 20000 });
  await ctx.close();
} catch (err) {
  await dumpDiagnostics(err);
}

// --- capture ----------------------------------------------------------------
// A dynamic page builds its address from the table hash it drills into (`base`), so the
// coverage gate above and the capture below cannot drift apart over that literal.
const pageHash = (p) => (p.dynamic ? p.base + '/' + encodeURIComponent(projectId) : p.hash);

// DL-KB-06: the sidebar renders from ROUTE_VIEWS, but "derived in source" is a claim until
// the buttons a person can actually click are compared with the route table parsed from the
// SERVED bundle. A hand-copied nav or a route that silently loses its button fails here.
let navProof = null;
const assertNavSet = async (page, width) => {
  const rendered = await page.evaluate(() => Array.from(
    document.querySelectorAll('#app-sidebar .nav button'))
    .map((node) => ({ hash: node.getAttribute('data-hash'), route: node.dataset.route || '' })));
  const expected = inventory.routes.filter((route) => route.hash !== '');
  const missing = expected.filter((route) => !rendered.some((node) => node.hash === route.hash));
  const extra = rendered.filter((node) => !expected.some((route) => route.hash === node.hash));
  const duplicates = rendered.filter((node, index) =>
    rendered.findIndex((other) => other.hash === node.hash) !== index);
  if (rendered.length === 0 || missing.length || extra.length || duplicates.length)
    fail('CAP_NAV_SET_MISMATCH rendered=' + rendered.length + ' expected=' + expected.length
      + ' missing=[' + missing.map((route) => route.hash).join(' ') + ']'
      + ' extra=[' + extra.map((node) => String(node.hash)).join(' ') + ']'
      + ' duplicates=[' + duplicates.map((node) => String(node.hash)).join(' ') + ']');
  navProof = {
    width,
    expected: expected.length,
    rendered: rendered.length,
    hashes: rendered.map((node) => node.hash),
    matchesRouteTable: true,
  };
  console.log('CAP_NAV_SET rendered=' + rendered.length + ' expected=' + expected.length + ' equal=1');
};

for (const width of widths) {
  const { ctx, page } = await openWorkspace(width);
  if (!navProof) await assertNavSet(page, width);
  for (const p of PAGES) {
    const hash = pageHash(p);
    const host = p.host || '#route-view';
    if (p.host) {
      // The landing surface reveals itself only while the session token lives in
      // THIS document's closure (`show()` hides #workspace whenever !connected), so a
      // reload cannot reach it -- it would capture the connect form and call it the
      // workbench. Step out to a routed view and back with same-document hash changes
      // so the token survives and the hashchange actually fires.
      await page.evaluate(() => { window.location.hash = '#/dashboard'; });
      await page.locator('#route-view').waitFor({ state: 'visible', timeout: 20000 });
      await page.evaluate(() => { window.location.hash = ''; });
    } else {
      await page.goto(serviceUrl + '/workbench' + hash, { waitUntil: 'load' });
      await paintTheme(page);
    }
    await page.locator(host).waitFor({ state: 'visible', timeout: 20000 });
    await page.waitForFunction((sel) =>
      !document.querySelector(sel + ' .view-loading'), host, { timeout: 30000 })
      .catch(() => problems.push(`loading-timeout@${width} ${p.key}`));
    // KPI count-up is JS-driven, so a mid-animation frame would freeze a wrong
    // number into the evidence; wait until every readback value has settled.
    await page.waitForFunction((sel) => Array.from(
        document.querySelectorAll(sel + ' strong[data-count]'))
      .every((n) => (n.textContent || '').trim() === n.dataset.count),
    host, { timeout: 8000 }).catch(() => problems.push(`kpi-settle-timeout@${width} ${p.key}`));
    if (p.click) {
      // An overlay cannot be reached by a hash, so the shot that proves the grouped search
      // exists has to drive the same click a person would -- and wait until every object group
      // has answered, or the image would show four "尚未读取" placeholders and look like a pass.
      await page.click(p.click);
      if (p.settle) {
        // Same rule for a detail screen assembled from several reads: the host must exist and no
        // part of it may still say 正在读回. A PNG of placeholders would otherwise be filed under
        // "the plan screen was reviewed". What is NOT required here is that every [role="status"]
        // line has text: the material reply and the note slot are legitimately empty until a
        // person acts, and demanding text made this wait unsatisfiable -- three settle timeouts on
        // a panel that had in fact rendered everything. The scaffold's own read-back assertions
        // (shot rows, formats, revisions, the feedback record) are what prove content landed.
        await page.waitForFunction((sel) => {
          const host = document.querySelector(sel);
          if (!host) return false;
          if (host.querySelector('.view-loading')) return false;
          const stuck = Array.from(host.querySelectorAll('[role="status"]'))
            .filter((node) => /正在读回|正在从服务读取/.test((node.textContent || '').trim()));
          return stuck.length === 0;
        }, p.settle, { timeout: 30000 })
          .catch(async () => {
            // Name what is still open, so a timeout says which read never landed instead of
            // sending the next reader to instrument this file to learn it.
            const why = await page.evaluate((sel) => {
              const host = document.querySelector(sel);
              if (!host) return 'no-host';
              if (host.querySelector('.view-loading')) return 'still-reading';
              const stuck = Array.from(host.querySelectorAll('[role="status"]'))
                .filter((node) => /正在读回|正在从服务读取/.test((node.textContent || '').trim()))
                .map((node) => node.id || node.className);
              return stuck.length ? 'unread:' + stuck.join(',') : 'other';
            }, p.settle);
            problems.push(`settle-${why}@${width} ${p.key}`);
          });
      } else {
        await page.waitForFunction(() => {
          const groups = document.querySelectorAll('#paletteObjects .palette-group');
          if (groups.length !== 4) return false;
          return Array.from(groups).every((g) => {
            const body = g.querySelector('.palette-group-body');
            const text = (body && body.textContent) || '';
            return Boolean(body && body.querySelector('.item'))
              || text.includes('0 个对象') || text.includes('未读回');
          });
        }, { timeout: 25000 }).catch(() => problems.push(`palette-not-settled@${width} ${p.key}`));
      }
    }
    await page.waitForTimeout(400);
    const file = `${String(shots.length).padStart(2, '0')}-${p.key}@${width}${themeTag}.png`;
    const filePath = path.join(outDir, file);
    const buffer = await page.screenshot({ path: filePath, fullPage: false, animations: 'disabled' });
    const bytes = readFileSync(filePath);
    // The numbers the PNG shows are recorded next to the PNG. Prose that
    // re-describes a screenshot is a second, unbound source of truth, and this
    // file already has one fabricated round behind it; quoting the manifest
    // instead means the same bytes back both.
    const rendered = await page.evaluate((sel) => ({
      host: sel,
      kpis: Array.from(document.querySelectorAll(sel + ' .kpi')).map((card) => ({
        value: (card.querySelector('strong') || {}).textContent?.trim() ?? '',
        label: (card.querySelector('small') || {}).textContent?.trim() ?? '',
        note: (card.querySelector('.trend') || {}).textContent?.trim() ?? '',
      })),
      headings: Array.from(document.querySelectorAll(sel + ' h2, ' + sel + ' h3'))
        .map((h) => h.textContent.trim()).slice(0, 14),
      unreadBack: /未读回|未连接/.test(document.querySelector(sel)?.textContent ?? ''),
    }), host);
    shots.push({
      file,
      page: p.key,
      hashRoute: hash,
      viewport: { width, height: heightFor(width) },
      url: serviceUrl + '/workbench' + hash,
      bytes: bytes.length,
      bufferBytes: buffer.length,
      sha256: sha256(bytes),
      rendered,
      capturedAt: new Date().toISOString(),
    });
    writeFileSync(filePath + '.license', JSON.stringify({
      schemaVersion: 'design-lab/asset-sidecar/v1',
      file: path.relative(process.cwd(), filePath).split(path.sep).join('/'),
      sha256: 'sha256:' + sha256(bytes),
      license: 'MIT',
      author: 'DESIGN-LAB Workbench rendered by scripts/capture_workbench_screenshots.py '
        + 'for DTALEX66 (DESIGN-LAB project owner)',
      redistributable: true,
      modelInputAllowed: false,
      commercialUse: true,
      sourceId: null,
      exception: {
        approvedBy: 'DTALEX66 (project owner)',
        expiresAt: '2027-10-05',
      },
      notes: 'First-party screenshot of this repository\'s own Workbench served by its own '
        + 'loopback service, rendered at commit ' + commit + '. Visible content: project UI '
        + '(MIT), one first-party MIT eval reference raster, and text set in locally installed '
        + 'system fonts. Font output rights are asserted only for the local OS licence; no '
        + 'third-party artwork, stock imagery or model output is embedded. Approval basis: the '
        + 'owner\'s 2026-10-05 closeout instruction to capture and archive real UI screenshots '
        + 'in this directory. modelInputAllowed=false because no training right is asserted.',
    }, null, 2) + '\n', 'utf8');
    console.log(`CAP ok: ${file} ${bytes.length}B`);
  }
  await ctx.close();
}

await b.close();

if (problems.length > 0) {
  console.error(problems.join('\n'));
  fail('CAP_BROWSER_DIAGNOSTICS count=' + problems.length);
}

const manifest = {
  kind: 'workbench-viewport-screenshots',
  // which colour theme these PNGs show, so the manifest names its own subject
  uiPalette: process.env.UI_PALETTE || 'design-lab',
  uiScheme: process.env.UI_SCHEME || 'dark',
  schema: 'design-lab/screenshot-manifest/v1',
  generatedAt: new Date().toISOString(),
  commit,
  subject: bundleSubject(),
  project: { name: projectName, id: projectId },
  // Recorded relative to the repo, the same way the PNG sidecars record their own path.
  // The absolute form made the committed manifest machine-specific: running the identical
  // capture from a linked worktree produced a different record, so the evidence could not
  // be committed from anywhere but the primary checkout. An outside-repo --source-image
  // keeps its absolute form and says so, rather than being smuggled into a repo-relative
  // path that resolves to nothing.
  referenceSourceImage: referenceSourceRecorded,
  service: { origin: serviceUrl, pythonVersion },
  browser: { engine: 'chromium', version: browserVersion, executable: browser || 'playwright-default', headless: true },
  nodeVersion: process.version,
  capture: {
    fullPage: false, mockUsed: false, viewports: widths, pages: PAGES.map((p) => p.key),
    // The gate that ran above is part of the record: a reader can see which route table
    // this page set was checked against, and that the check ran at all.
    routeInventory,
    routeCoverageChecked: true,
    navRouteProof: navProof,
  },
  screenshots: shots,
};
writeFileSync(path.join(outDir, 'screenshot-manifest.json'),
  JSON.stringify(manifest, null, 2) + '\n', 'utf8');
console.log('CAP_DONE shots=' + shots.length + ' out=' + outDir);
