// SPDX-License-Identifier: MIT
// AppShell regression tests for the 2026-09-22 UI convergence slice.

import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const bundlePath = join(here, '..', 'build', 'main.js');
const source = readFileSync(bundlePath, 'utf8');

let lastFocused = null;

class MockElement {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.dataset = {};
    this.className = '';
    this.classList = { add() {}, toggle() {} };
    this.hidden = false;
    this.value = '';
    this._text = '';
    this.attributes = new Map();
    // `id` is an IDL attribute in the DOM: `node.id = 'x'` writes the attribute, and reading it
    // returns '' when absent. Without the bridge here, product code that guards on `control.id`
    // took the "no id" branch in this harness while taking the real branch in a browser -- which is
    // exactly how a per-field refusal could be tested as "placed but unlabelled".
    // Tree links, because the per-field refusal placement walks them. `el()` builds a document by
    // calling `append`, and a shim that records only the children gives every node a `null`
    // parentNode -- so `row.parentNode?.insertBefore(line, row.nextSibling)` silently does
    // nothing, and a test of "the refusal lands under the field it names" would pass while the
    // product put the line nowhere. Real DOM nodes know their parent; these now do too.
    this.parentNode = null;
  }
  get id() { return this.attributes.get('id') ?? ''; }
  set id(value) { this.attributes.set('id', String(value)); }
  get nextSibling() {
    const siblings = this.parentNode?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
  }
  appendChild(node) { this.append(node); return node; }
  insertBefore(node, reference) {
    // `reference == null` means "at the end", which is what the DOM does and what the last field's
    // refusal depends on.
    const at = reference == null ? this.children.length : this.children.indexOf(reference);
    if (at < 0) throw new Error('insertBefore: reference is not a child of this node');
    if (node.parentNode) node.parentNode.children.splice(node.parentNode.children.indexOf(node), 1);
    this.children.splice(at, 0, node);
    node.parentNode = this;
    return node;
  }
  remove() {
    const at = this.parentNode?.children.indexOf(this) ?? -1;
    if (at >= 0) this.parentNode.children.splice(at, 1);
    this.parentNode = null;
  }
  closest(selector) {
    // Upward walk with the same four selector shapes `matches` understands. A no-op `closest()`
    // would let the refusal land on the field itself and the adjacency test would still read green.
    for (let node = this; node; node = node.parentNode)
      if (node.matches?.(selector)) return node;
    return null;
  }
  set textContent(value) {
    this._text = String(value ?? '');
    this.children = [];
  }
  get textContent() {
    return this._text + this.children.map((child) => child?.textContent ?? String(child)).join('');
  }
  get childNodes() { return this.children; }
  // A real HTMLSelectElement exposes its option elements (and a value that defaults to the
  // first one). The knowledge screen rebuilds the type filter only when `options.length`
  // changed -- without this getter that read throws inside renderAnswer and the view shows
  // the route-level failure, i.e. the gate would be measuring the shim, not the page.
  get options() { return this.children.filter((child) => child?.tagName === 'OPTION'); }
  append(...nodes) {
    this.children.push(...nodes);
    nodes.forEach((node) => { if (node && typeof node === 'object') node.parentNode = this; });
  }
  replaceChildren(...nodes) {
    // The old children are out of the document, so they must stop pointing here: `remove()` on a
    // node that was already dropped has to be a no-op, not a splice against a parent it no longer
    // has. Strings and raw text are not nodes and are skipped.
    this.children.forEach((child) => {
      if (child && typeof child === 'object' && child.parentNode === this) child.parentNode = null;
    });
    this.children = nodes;
    this._text = '';
    nodes.forEach((node) => { if (node && typeof node === 'object') node.parentNode = this; });
  }
  // openForm() scrolls the new panel into view. Browsers have it, a div mock does not, and
  // the throw happened inside the click handler before any assertion could run.
  scrollIntoView() {}
  // focus()/select() arrived with the copy fallback: when the browser refuses a clipboard write
  // the page puts the exact bytes in a read-only textarea, focuses it and selects the text so
  // Ctrl+C works. Without these two no-ops the refusal path threw inside the handler and the
  // message a user would actually see was untestable here -- the same shape of harness gap as
  // the crypto.subtle and TextEncoder notes below.
  focus() { lastFocused = this; }
  select() {}
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  // Returns null when absent, the way the DOM does: `''` would make "no association" and
  // "associated with the empty string" read the same to a test that is checking the link exists.
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener() {}
  // A stub with no `querySelector` does not fail loudly: the caller's `?.` returns undefined and
  // the branch is skipped, so a code path that only exists inside a selector lookup reads as
  // "nothing to test". The ⌘K palette was in exactly that state -- every one of its object
  // groups is rendered through `holder.querySelector('.palette-group-body')`. Selectors here are
  // the four shapes `el()` can build: `[data-x="y"]`, `.class`, `#id`, and a tag name.
  matches(selector) {
    const s = selector.trim();
    const data = /^\[data-([\w-]+)="([^"]*)"\]$/.exec(s);
    if (data) return this.dataset?.[data[1].replace(/-(\w)/g, (m, c) => c.toUpperCase())]
      === data[2];
    if (s.startsWith('.')) return String(this.className).split(/\s+/).includes(s.slice(1));
    if (s.startsWith('#')) return this.attributes.get('id') === s.slice(1);
    return this.tagName === s.toUpperCase();
  }
  querySelectorAll(selector) {
    const hits = [];
    for (const child of this.children) {
      if (child?.matches?.(selector)) hits.push(child);
      hits.push(...(child?.querySelectorAll?.(selector) ?? []));
    }
    return hits;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
}

function makeContext() {
  const elements = new Map();
  const pending = [];
  const listeners = new Map();
  const getElementById = (id) => {
    if (!elements.has(id)) elements.set(id, new MockElement());
    return elements.get(id);
  };
  const body = new MockElement('body');
  getElementById('login').hidden = false;
  getElementById('workspace').hidden = true;
  getElementById('connection').textContent = '未连接';
  const document = {
    body,
    getElementById,
    createElement: (tag) => new MockElement(tag),
  };
  const window = {
    location: { hash: '' },
    addEventListener: (name, callback) => listeners.set(name, callback),
  };
  const context = vm.createContext({
    document,
    window,
    // design.ts uuid() calls crypto.randomUUID(), which the context never had -- so the
    // intake write path died on 'crypto is not defined' before reaching fetch, and the
    // panel reported that as a service refusal. The counter keeps each call distinct,
    // which is what the idempotency assertions depend on.
    //
    // crypto.subtle.digest arrived with batch 22: the idempotency key is now the digest
    // of the content it identifies (shell.ts sha256Hex), not a fresh uuid per click. A
    // context with only randomUUID made every submit throw on 'crypto.subtle is not a
    // function' BEFORE fetch, so the plan-refusal block saw zero requests instead of one
    // -- a harness gap that made a real code path untested rather than tested. The digest
    // is the real SHA-256, so a key really derived from the same plan really is the same
    // key here too.
    crypto: {
      randomUUID: ((n) => () => {
        n += 1;
        return `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
      })(0),
      subtle: {
        digest: async (_algorithm, bytes) =>
          createHash('sha256').update(Buffer.from(bytes)).digest(),
      },
    },
    // A navigator with no clipboard: the copy paths in shell.ts ask `navigator.clipboard?.writeText`
    // and fall back to a selected read-only textarea when the browser will not grant the write.
    // Without this global the click threw before either branch, so the fallback -- the message a
    // user actually sees when the clipboard is denied -- was an untested line. The granted path is
    // proven in Chromium by design-lab/tests/e2e/browser_design_layer_e2e.mjs, not here.
    navigator: {},
    // TextEncoder came with the same key change: contentKey() encodes the joined intent
    // before hashing, so a context without it threw on that line instead of reaching
    // fetch -- the same failure mode as the missing crypto.subtle above.
    TextEncoder,
    // DL-KB-04: the knowledge screen builds its query with URLSearchParams before it calls
    // fetch. A fresh vm context has the language intrinsics but not the host's web globals,
    // so without this the whole view rejected on 'URLSearchParams is not defined' -- and the
    // request-failure sweep below then read a fabricated failure for a route that never got
    // as far as asking.
    URLSearchParams,
    Option: class Option extends MockElement {
      constructor(text, value) { super('option'); this.textContent = text; this.value = value; }
    },
    // D06 deadlines. `api()` now arms a deadline with setTimeout and aborts the fetch through an
    // AbortController, so a context without these three would throw before the request was even
    // issued -- and the timeout paths would then be untestable rather than untested. The fetch
    // mock below honours `init.signal`, so an abort really rejects here the way it does in a
    // browser instead of leaving a request nobody will ever resolve.
    setTimeout,
    clearTimeout,
    AbortController,
    AbortSignal,
    // `init` is recorded because block ⑧ has to see the METHOD and the BODY of a
    // submission: "one click, one request" is not proved by the path alone, and a rights
    // form that put the supersession link in the document instead of the query string would
    // still hit this exact path (the closed contract refuses that field, so it must not be
    // sent).
    fetch: (path, init) => new Promise((resolve, reject) => {
      const request = { path, init, resolve, reject };
      const signal = init?.signal;
      if (signal) {
        const onAbort = () => {
          const error = new Error('The operation was aborted.');
          error.name = 'AbortError';
          reject(error);
        };
        if (signal.aborted) onAbort();
        else signal.addEventListener('abort', onAbort, { once: true });
      }
      pending.push(request);
    }),
  });
  vm.runInContext(source, context, { filename: 'build/main.js' });
  return { context, elements, pending, window, dispatchHashchange: () => listeners.get('hashchange')?.() };
}

function response(value, ok = true, status = ok ? 200 : 400) {
  // `status` was implicit (undefined) until D06: nothing in this file used it, so the 401
  // branch in `api()` -- the one that clears a session the service no longer accepts -- had
  // no test at all. It defaults consistently with `ok`, so existing call sites are unchanged.
  return { ok, status, json: async () => value };
}

async function flush() {
  for (let i = 0; i < 20; i += 1) await null;
}

// The /api/projects envelope since 2026-10-22 (backend A): a row carries per-surface counts where
// null means "that surface was never opened on this checkout" and 0 means "empty". The fixture has
// to say the same thing the route does, or the shape guard below is right to complain.
const projectRow = (id, name) => ({
  id, name, created_at: '2026-10-22T00:00:00+00:00',
  objects: { assets: 0, briefs: null, currentBriefs: null, directions: null,
    designSystemBindings: null, designLayerEvents: null, promptResults: null,
    knowledgeCandidates: null, juryRecords: null, rightsDecisions: null,
    researchFindings: null, creativeJobs: null, modelSelectionRevisions: null,
    qualityRecords: null },
  absentSurfaces: ['briefs', 'currentBriefs', 'directions', 'designSystemBindings',
    'designLayerEvents', 'promptResults', 'knowledgeCandidates', 'juryRecords',
    'rightsDecisions', 'researchFindings', 'creativeJobs', 'modelSelectionRevisions',
    'qualityRecords'],
  last_activity_at: null,
  waiting: { promptResultsUnsigned: null, promptResultsNotCurrent: null,
    knowledgeCandidatesPendingReview: null, knowledgeCandidatesExportReady: null },
});
const projectsEnvelope = (rows) => ({
  schemaVersion: 'design-lab/project-list/v1', projects: rows,
  surfaceRule: 'null = 该表面在此检出从未建表；0 = 表在而此项目没有记录。两者不可互换。',
  does_not_say: ['对象计数不是完成度，也不等于有人验收过。'],
});

const shell = makeContext();
shell.window.location.hash = '#/dashboard';
shell.dispatchHashchange();
shell.window.location.hash = '';
shell.dispatchHashchange();
if (shell.elements.get('login').hidden || !shell.elements.get('workspace').hidden)
  throw new Error('未连接时从 dashboard 返回 workbench 必须恢复登录并隐藏 workspace');

const firstToken = shell.context.document.getElementById('token');
firstToken.value = '1'.repeat(64);
const firstConnect = shell.elements.get('connect-form').onsubmit({ preventDefault() {} });
firstToken.value = '2'.repeat(64);
const secondConnect = shell.elements.get('connect-form').onsubmit({ preventDefault() {} });
const firstConnectRequest = shell.pending.shift();
const secondConnectRequest = shell.pending.shift();
secondConnectRequest.resolve(response({ error: 'UNAUTHORIZED' }, false));
await secondConnect;
firstConnectRequest.resolve(response(projectsEnvelope([])));
await firstConnect;
await flush();
if (shell.elements.get('login').hidden || !shell.elements.get('workspace').hidden)
  throw new Error('过期连接成功不得覆盖较新的连接失败');

const token = shell.context.document.getElementById('token');
token.value = 'a'.repeat(64);
const connect = shell.elements.get('connect-form').onsubmit({ preventDefault() {} });
shell.pending.shift().resolve(response(projectsEnvelope([])));
await connect;
await flush();

shell.window.location.hash = '#/dashboard';
shell.dispatchHashchange();
const activeDashboard = shell.context.document.body.children[0].children
  .find((child) => child?.dataset?.route === 'dashboard');
if (activeDashboard?.attributes.get('aria-current') !== 'page')
  throw new Error('当前路由必须通过 aria-current=page 暴露给辅助技术');
shell.window.location.hash = '#/settings';
shell.dispatchHashchange();
const dashboardRequests = shell.pending.splice(0, 4);
// DL-KB-06: 设置页只收四件事，因此并发读回三条路由（环境、模型目录、知识索引）。
// 这三条要一起结清：漏掉任何一条，它会留到下一次 splice 里，让下一个 dashboard 的
// 四个请求整体错位，失败会以一句与原因无关的文案出现。
const settingsRequests = shell.pending.splice(0, 3);
settingsRequests[0].resolve(response({
  status: 'OK', schemaVersion: 'v1', project_root: 'D:/project', project_local_root: '.project-local',
  write_trace: 'NONE', migration: 'NONE', agent_profile: { status: 'DISABLED' },
  roots: {}, shared_inputs: {},
}));
settingsRequests[1].resolve(response({
  schemaVersion: 'design-lab/model-catalog/v1', observed_at: null,
  sources: {}, hardware: {}, policy: {},
  counts: { models: 0, endpoints: 0, qualified_local: 0, default_enabled_true: 0,
            weights_recorded: 0, placement: {} },
  models: [], endpoints: [],
  join: { key: null, reason: '' },
  selection: { mode: '', rules: [], transport: '', executed: false },
  claims_not_made: [],
}));
settingsRequests[2].resolve(response({
  schemaVersion: 'design-lab/knowledge-library/v1', query: null,
  filters: { type: null, domain: null, task: null, target: null },
  entryTypes: [], licenseStates: [], strategy: 'BROWSE',
  matched_terms: [], total: 0, offset: 0, limit: 1, returned: 0, next_offset: null,
  entries: [], explanation: null,
  index: { rows: 0, indexed: 0, rebuilt_at: null },
  does_not_say: [],
}));
await flush();
shell.window.location.hash = '#/dashboard';
shell.dispatchHashchange();
if (!shell.elements.get('route-view').textContent.includes('正在读回当前视图'))
  throw new Error('切换到新 route 后必须立即显示 loading，而不是保留旧页面');
const latestDashboardRequests = shell.pending.splice(0, 4);
// Resolve the OLD (gen1) dashboard's four requests — the third of which is the
// environment readback — first. Their late success must be rejected by the
// generation guard, so the current loading state survives.
dashboardRequests[0].resolve(response({ status: 'OK', version: 'test', scope: 'local' }));
dashboardRequests[1].resolve(response(projectsEnvelope([])));
dashboardRequests[2].resolve(response({ design_systems: [] }));
dashboardRequests[3].resolve(response({
  status: 'OK', schemaVersion: 'v1', project_root: 'D:/project', project_local_root: '.project-local',
  write_trace: 'NONE', migration: 'NONE', agent_profile: { status: 'DISABLED' },
  roots: {}, shared_inputs: {},
}));
await flush();
if (!shell.elements.get('route-view').textContent.includes('正在读回当前视图'))
  throw new Error('旧 dashboard success 不得覆盖新 dashboard 的 loading 状态');
// Now resolve the CURRENT (gen3) dashboard's requests so it commits.
latestDashboardRequests[0].resolve(response({ status: 'OK', version: 'test', scope: 'local' }));
latestDashboardRequests[1].resolve(response(projectsEnvelope([])));
latestDashboardRequests[2].resolve(response({ design_systems: [] }));
latestDashboardRequests[3].resolve(response({
  status: 'OK', schemaVersion: 'v1', project_root: 'D:/project', project_local_root: '.project-local',
  write_trace: 'NONE', migration: 'NONE', agent_profile: { status: 'DISABLED' },
  roots: {}, shared_inputs: {},
}));
await flush();
if (!shell.elements.get('route-view').textContent.includes('仪表盘'))
  throw new Error('当前 dashboard 请求完成后必须提交当前视图');

// State ⑤ of the UI state matrix, both directions.
// (a) A 200 response that omits a collection must degrade visibly: the page still
//     renders, and it says the field was missing rather than showing 尚无项目 as if the
//     server had answered zero. Before the fix this threw at data.projects.length and
//     the top-level catch replaced the whole view with a TypeError message.
shell.window.location.hash = '#/projects';
shell.dispatchHashchange();
const malformedProjects = shell.pending.shift();
malformedProjects.resolve(response({}));
await flush();
const malformedText = shell.elements.get('route-view').textContent;
if (!malformedText.includes('未读回：响应缺少 projects'))
  throw new Error('响应缺少集合时必须说明未读回，而不是渲染成"尚无项目"');
if (malformedText.includes('视图读回失败'))
  throw new Error('缺少一个集合不得让整页读回失败');

// (b) A well-formed response must NOT carry the notice — otherwise the guard is just
//     noise and the (a) assertion proves nothing.
shell.window.location.hash = '#/dashboard';
shell.dispatchHashchange();
shell.pending.splice(0, 4);   // the dashboard's own reads, left unresolved on purpose
shell.window.location.hash = '#/projects';
shell.dispatchHashchange();
const goodProjects = shell.pending.shift();
goodProjects.resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
await flush();
const goodText = shell.elements.get('route-view').textContent;
if (goodText.includes('未读回：响应缺少'))
  throw new Error('形状完整的响应不得出现形状告警');
if (!goodText.includes('Alpha'))
  throw new Error('形状完整的响应必须照常渲染');

// ⑤ SWEEP over every routable view, in both directions, driven from the route table
// itself (shape-notice-coverage.mjs proves each binding is REPORTED; this proves the
// report REACHES THE SCREEN). A view that reads through the seam and gets a 200 with a
// collection missing must render 未读回：响应缺少 …; a view that reads nothing is allowed
// to say nothing, but a mass of "reads nothing" is a rollout regression, so the count
// has a floor.
const shellSource = readFileSync(join(here, '..', 'shell.ts'), 'utf8');
const tableStart = shellSource.indexOf('export const ROUTE_VIEWS');
const tableEnd = shellSource.indexOf('export type RouteView');
if (tableStart < 0 || tableEnd < tableStart)
  throw new Error('ROUTE_VIEWS 表定位失败 —— 路由扫描失去覆盖面');
const routeHashes = [...shellSource.slice(tableStart, tableEnd)
  .matchAll(/hash: '(#[^']*)'/g)].map((m) => m[1]);
if (routeHashes.length < 10)
  throw new Error(`只从 ROUTE_VIEWS 提取到 ${routeHashes.length} 个 hash —— 提取式已失效，不要相信本扫描的覆盖面`);

let noticeViews = 0;
const silentViews = [];
for (const hash of routeHashes) {
  shell.window.location.hash = hash;
  shell.dispatchHashchange();
  // Drain until the route goes quiet, not just the first batch: a view that CHAINS its
  // reads (预检 / QA reads /projects for the jury panel, then again for the rights panel)
  // creates the second request only after the first one resolves. Splicing once would
  // leave that request unresolved forever, the router would never commit the view, and this
  // sweep would then be measuring the previous route's DOM -- a green gate about nothing.
  const requests = [];
  for (let round = 0; round < 8; round += 1) {
    const fresh = shell.pending.splice(0, shell.pending.length);
    if (!fresh.length) break;
    requests.push(...fresh);
    for (const request of fresh) request.resolve(response({}));
    await flush();
  }
  if (!requests.length) { silentViews.push(hash); continue; }
  const text = shell.elements.get('route-view').textContent;
  if (text.includes('视图读回失败'))
    throw new Error(`${hash}: 缺少集合把整页压成了读回失败（${text.slice(0, 120)}）`);
  if (!text.includes('未读回：响应缺少'))
    throw new Error(`${hash}: 发起 ${requests.length} 次 seam 读回却没有说明缺少哪个字段`);
  noticeViews += 1;
}
if (noticeViews < 8)
  throw new Error(`只有 ${noticeViews} 个视图报告了缺失形状（下限 8）—— ⑤ 的铺开出现了回归`);
console.log(`ok: ⑤ 形状告警渲染在 ${noticeViews} 个视图上；${silentViews.length} 个路由不读服务：${silentViews.join(' ')}`);

// ㉔ DL-KB-06: the vm smoke cannot mount the B10 sidebar (mountB10Shell asks the mock
// *document* for querySelector and the stub deliberately lacks it), so this pins the
// derivation at its source: B10_NAV must be computed from ROUTE_VIEWS, never a literal
// table. The rendered button set is compared against the served bundle's route table in
// the real browser by capture_workbench_screenshots.mjs (CAP_NAV_SET).
const b10Start = shellSource.indexOf('const B10_NAV');
const b10End = shellSource.indexOf('const navList', b10Start);
if (b10Start < 0 || b10End < b10Start)
  throw new Error('㉔ B10_NAV 定位失败 —— 导航派生检查失去覆盖面');
const b10Block = shellSource.slice(b10Start, b10End);
if (!/=\s*ROUTE_VIEWS\s*\.filter\([\s\S]*?\.map\(/.test(b10Block.replace(/\n\s*/g, ' ')))
  throw new Error('㉔ B10_NAV 不再从 ROUTE_VIEWS 派生：' + b10Block.slice(0, 200));
const handCopiedNav = b10Block.match(/hash:\s*'#/g) ?? [];
if (handCopiedNav.length)
  throw new Error(`㉔ B10_NAV 里出现 ${handCopiedNav.length} 个手抄 hash`);
console.log('ok: ㉔ B10_NAV 从 ROUTE_VIEWS 派生且没有手抄 hash；渲染集合由截图采集在真浏览器里比对');

// ⑤ TARGETED, #/domains. The sweep above proves a notice can reach a screen; it cannot
// prove this particular page asks for anything. `#/domains` was the route with no backend
// at all — listed, reachable, reading nothing while the repository held the packs and the
// checker. So this pins the three things that made the gap a gap:
//   1. the view makes exactly one read, of /api/domains (a page that reads nothing, or
//      reads somewhere else, is the old defect back);
//   2. a 200 that omits `packs` is reported as 未读回 and never rendered as "the project
//      has no packs" — the lie an empty <ul> tells;
//   3. a real payload renders real rows: the rejected pack's own checker reason is on
//      screen, and the verdict word is marked lang="en" (service vocabulary, WCAG 3.1.2).
shell.window.location.hash = '#/domains';
shell.dispatchHashchange();
const domainsReads = shell.pending.splice(0, shell.pending.length);
if (domainsReads.length !== 1)
  throw new Error(`#/domains 读回了 ${domainsReads.length} 次，应为恰好 1 次 GET /api/domains`);
if (domainsReads[0].path !== '/api/domains')
  throw new Error(`#/domains 打到了 ${domainsReads[0].path}，不是 /api/domains`);
domainsReads[0].resolve(response({}));
await flush();
const domainsShapeText = shell.elements.get('route-view').textContent;
// The notice lists every refilled field in template order, so `packs` is asserted to be
// NAMED by it rather than assumed to be first.
if (!/未读回：响应缺少[^；]*\bpacks\b/.test(domainsShapeText))
  throw new Error(`域包集合缺失时必须点名 packs：…${domainsShapeText.slice(-300)}`);
if (domainsShapeText.includes('尚无域包目录'))
  throw new Error('响应没有给出 packs 时，页面不得声称尚无域包目录');
if (domainsShapeText.includes('视图读回失败'))
  throw new Error('缺少 packs 不得把整页压成读回失败');

const DOMAINS_READBACK = {
  schemaVersion: 'design-lab/domain-pack-readback/v1',
  meaning: 'Read-only projection of the committed Domain Pack directories.',
  unmeasuredMeans: 'null = the manifest does not declare that field.',
  root: 'design-lab/domain-packs', rootState: 'PRESENT',
  validationVocabulary: ['VALIDATES', 'INVALID', 'UNREADABLE', 'NOT_CHECKED'],
  checker: { path: 'design-lab/scripts/verify_domain_pack_v2.py', state: 'LOADED', note: null },
  sources: { packRoot: 'design-lab/domain-packs' },
  counts: { packs: 2, byValidation: { VALIDATES: 1, INVALID: 1, UNREADABLE: 0, NOT_CHECKED: 0 } },
  packs: [
    { directory: 'uiux-design', packId: 'uiux-design', version: '0.1.0',
      displayName: 'UI/UX Design Domain Pack', domain: 'ui-ux',
      manifestSchemaVersion: 'design-lab/domain-pack/v2', dependencies: ['jsonschema'],
      validation: 'VALIDATES', validationErrors: [], validationErrorCount: 0, note: null },
    { directory: 'minigame-design', packId: 'minigame-design', version: '0.1.0',
      displayName: 'MINIGAME Design Domain Pack', domain: null,
      manifestSchemaVersion: 'workflow/domain-pack/v1', dependencies: null,
      validation: 'INVALID',
      validationErrors: ["schema validation failed: 'domain' is a required property"],
      validationErrorCount: 11, note: null },
  ],
};
shell.window.location.hash = '#/domains';
shell.dispatchHashchange();
const domainsGood = shell.pending.splice(0, shell.pending.length);
domainsGood[0].resolve(response(DOMAINS_READBACK));
await flush();
const domainsGoodText = shell.elements.get('route-view').textContent;
if (domainsGoodText.includes('未读回：响应缺少'))
  throw new Error('形状完整的域包读回不得出现形状告警');
if (!domainsGoodText.includes('域包登记（2）'))
  throw new Error(`域包数量必须由读回给出：${domainsGoodText.slice(0, 200)}`);
if (!domainsGoodText.includes('ui-ux') || !domainsGoodText.includes('jsonschema'))
  throw new Error('域包身份 / 领域 / 依赖没有上屏');
if (!domainsGoodText.includes("'domain' is a required property"))
  throw new Error('被拒绝的域包必须带着校验器的原因上屏，而不是只留一个数字');
if (!domainsGoodText.includes('校验器共 11 条'))
  throw new Error('原因被截断时必须注明校验器实际给出了多少条');
if (domainsGoodText.includes('13'))
  throw new Error(`页面又带上了没有出处的数字：${domainsGoodText.slice(0, 240)}`);
const englishVerdicts = [];
(function walkMarked(node) {
  if (node?.attributes?.get('lang') === 'en') englishVerdicts.push(node.textContent);
  for (const child of (node?.children ?? [])) walkMarked(child);
})(shell.elements.get('route-view'));
for (const state of ['VALIDATES', 'INVALID'])
  if (!englishVerdicts.includes(state))
    throw new Error(`判定 ${state} 必须带 lang="en" 标记（服务词汇，不翻译）：${englishVerdicts.join('/')}`);

// The reverse direction of the same sentence: a service that really answers an empty
// catalog may be described as empty. Without this the 尚无 wording above could be earned
// by a page that never renders rows at all.
shell.window.location.hash = '#/domains';
shell.dispatchHashchange();
const domainsEmpty = shell.pending.splice(0, shell.pending.length);
domainsEmpty[0].resolve(response({ ...DOMAINS_READBACK,
  counts: { packs: 0, byValidation: {} }, packs: [] }));
await flush();
const domainsEmptyText = shell.elements.get('route-view').textContent;
if (!domainsEmptyText.includes('尚无域包目录'))
  throw new Error('服务真的答了空目录时，页面必须照实说尚无域包目录');
// Asserted as the three notice SHAPES rather than the bare word: the page's own
// explanatory line names 未声明 / 未读回 as the two different things it distinguishes, and
// a substring check on the word alone would convict the explanation for the lie.
for (const notice of ['未读回：响应缺少', '未读回：未连接', '未读回判定基础'])
  if (domainsEmptyText.includes(notice))
    throw new Error(`一次形状完整的空读回不得出现 ${notice}：…${domainsEmptyText.slice(-300)}`);
console.log('ok: ⑤ #/domains 读一个路由、缺 packs 说未读回、真实读回上屏带 lang="en" 与原因、空目录照实说尚无');

// ⑪ R2 §2 — a domain pack is a SECOND-LEVEL entry: it needs its own address, its own
// readable facts, and it must stay highlighted inside 设计领域. The honest half of this
// block matters more than the pretty half. Measured 2026-10-09 against both real readbacks:
// GET /api/capabilities reports the `domains` classification axis as empty for all 60
// records, and its `domain` field carries model-radar families (`video-generation`, `asr`,
// …) whose only literal overlap with a pack slug is the string `3d`. There is therefore no
// join axis, so the panel has to show a disabled cross-catalog action with a reason instead
// of inventing "该领域下的能力".
function walkNodes(root, visit) {
  if (!root) return;
  visit(root);
  for (const child of (root.children ?? [])) walkNodes(child, visit);
}

function findNodes(root, tagName, needle) {
  const hits = [];
  walkNodes(root, (node) => {
    if (node?.tagName === tagName && (node.textContent ?? '').includes(needle)) hits.push(node);
  });
  return hits;
}

function drawerFor(hash) {
  let drawer = null;
  walkNodes(shell.elements.get('route-view'), (node) => {
    if (node?.attributes?.get('id') === 'domain-drawer') drawer = node;
  });
  if (!drawer) throw new Error(`${hash}: 没有渲染域包详情面板 —— 二级入口落空`);
  return drawer;
}

// The detail address reads TWO endpoints: the pack's own facts, then the capability library to
// report the join state. `caps` = null fails the second read, so the panel has to say 未读回.
function capabilityRecords(total, classifiedOf, domainOf) {
  return Array.from({ length: total }, (unused, index) => ({
    id: `cap-${index}`, kind: 'model', domain: null, title: `记录 ${index}`,
    disposition: 'UNKNOWN', license: null, presence: null, url: null, revision: null,
    revisionState: 'NOT_VERIFIED', revisionReason: null, repo: null, observedAt: null,
    contentDigest: null, qualified: null, qualificationEvidence: null,
    qualificationReason: '没有资格记录', sourceType: null, evidenceLevel: null,
    upstreamOwner: null, licenseUrl: null, rightsNotes: null, removalPath: null,
    popularity: null,
    unclassifiedAxes: index < classifiedOf ? [] : ['domains'],
    axes: { domains: index < classifiedOf ? [domainOf] : null, artifactTypes: null,
      capabilityLayers: null, aestheticAxes: null, styleArchetypes: null, tier: null,
      designQuality: null },
  }));
}

function capabilitiesPayload(total, classifiedOf, domainOf) {
  return {
    schemaVersion: 'design-lab/capability-library/v1',
    meaning: '能力目录', unmeasuredMeans: 'null = 未判定',
    counts: { total, byKind: {}, byLicense: {}, byRevisionState: {}, qualified: 0 },
    sources: {}, capabilities: capabilityRecords(total, classifiedOf, domainOf),
  };
}

async function renderDomainDetail(hash, payload = DOMAINS_READBACK,
  caps = capabilitiesPayload(60, 0, 'ui-ux')) {
  shell.window.location.hash = hash;
  shell.dispatchHashchange();
  const first = shell.pending.splice(0, shell.pending.length);
  if (first.length !== 1 || first[0].path !== '/api/domains')
    throw new Error(`${hash}: 第一步应恰好一次 GET /api/domains，实得 ${first.length} 次`
      + `（${first.map((r) => r.path).join(', ')}）`);
  first[0].resolve(response(payload));
  await flush();
  const second = shell.pending.splice(0, shell.pending.length);
  if (second.length !== 1 || second[0].path !== '/api/capabilities')
    throw new Error(`${hash}: 详情地址应再做一次 GET /api/capabilities 读回，实得 `
      + `${second.length} 次（${second.map((r) => r.path).join(', ')}）`);
  // `caps === null` asks for the shape the seam has to report: the service answered 200 but the
  // capability collection is absent, which is "no readback of that field", not "zero records".
  if (caps === null) second[0].resolve(response({ schemaVersion: 'design-lab/capability-library/v1',
    meaning: '能力目录', unmeasuredMeans: 'null = 未判定', counts: {}, sources: {} }));
  else second[0].resolve(response(caps));
  await flush();
  return drawerFor(hash);
}

// The registry route itself: no address is open, so there is no drawer to assert on and
// the slot must stay hidden rather than painted as an empty panel.
async function renderDomainRegistry(payload) {
  shell.window.location.hash = '#/domains';
  shell.dispatchHashchange();
  const reads = shell.pending.splice(0, shell.pending.length);
  if (reads.length !== 1)
    throw new Error(`#/domains 列表页应恰好一次读回（第二次读只属于详情地址），实得 ${reads.length} 次`
      + `（${reads.map((r) => r.path).join(', ')}）`);
  reads[0].resolve(response(payload));
  await flush();
  let drawer = null;
  walkNodes(shell.elements.get('route-view'), (node) => {
    if (node?.attributes?.get('id') === 'domain-drawer') drawer = node;
  });
  if (drawer) throw new Error('#/domains 没有寻址到任何 pack，不得渲染详情面板');
  return shell.elements.get('route-view');
}

const firstDrawer = await renderDomainDetail('#/domains/uiux-design');
for (const fact of ['UI/UX Design Domain Pack', 'ui-ux', 'jsonschema',
  'design-lab/domain-pack/v2'])
  if (!firstDrawer.textContent.includes(fact))
    throw new Error(`详情面板没有给出该域包自己的 ${fact}：${firstDrawer.textContent.slice(0, 200)}`);
const joinAction = findNodes(firstDrawer, 'BUTTON', '按该领域查看能力');
if (joinAction.length !== 1)
  throw new Error(`详情面板应给出一个"按该领域查看能力"动作，实得 ${joinAction.length} 个`);
if (!joinAction[0].attributes.has('disabled'))
  throw new Error('0 条已接线关联时这个动作必须禁用，不能留一个必然跳转空结果的按钮');
// The two empties are different facts and must not share a sentence: 60/60 records list
// `domains` in the service's own unclassified axis set, so the honest wording is 还没有分类.
if (!firstDrawer.textContent.includes('还没有分类'))
  throw new Error(`全未分类时面板要说"还没有分类"：${firstDrawer.textContent.slice(-320)}`);
// Every mention of the phrase must be a negation: the panel may explain that "no wired relation"
// is NOT "this domain has no capabilities", but it may never assert the latter. Counting mentions
// against negated mentions is the only form that survives the product quoting the phrase.
{
  const said = firstDrawer.textContent;
  const mentions = (said.match(/该领域没有能力/g) ?? []).length;
  const negated = (said.match(/(不是|不等于)"?该领域没有能力/g) ?? []).length;
  if (mentions !== negated)
    throw new Error(`面板把"没有已接线关联"说成了"该领域没有能力"（${negated}/${mentions} 次是否定式）`
      + `：${said.slice(-320)}`);
}
if (!/60 条读回里有 0 条|声明该领域的有 0 条/.test(firstDrawer.textContent))
  throw new Error(`关联行必须给出这次读回的实测数字：${firstDrawer.textContent.slice(-320)}`);

// A field the seam had to supply may not borrow the first read's confidence: no counts, 未读回.
const unreadDrawer = await renderDomainDetail('#/domains/uiux-design', undefined, null);
if (!unreadDrawer.textContent.includes('未读回'))
  throw new Error(`能力目录读不到时必须照实说：${unreadDrawer.textContent.slice(-320)}`);
if (/已接线 \d+ 条|0 条读回/.test(unreadDrawer.textContent))
  throw new Error(`读不到就不给报数：${unreadDrawer.textContent.slice(-320)}`);

// Some records ARE classified and none names this domain: that is 无已接线关联, not 还没有分类.
const partialDrawer = await renderDomainDetail('#/domains/uiux-design', undefined,
  capabilitiesPayload(60, 12, 'video-generation'));
if (!partialDrawer.textContent.includes('无已接线关联'))
  throw new Error(`部分已分类时要说"无已接线关联"：${partialDrawer.textContent.slice(-320)}`);
if (partialDrawer.textContent.includes('还没有分类'))
  throw new Error('已经给出分类的目录不能被写成"还没有分类"');

// A declared relationship enables the action, and the action still only moves the address.
const matchedDrawer = await renderDomainDetail('#/domains/uiux-design', undefined,
  capabilitiesPayload(60, 12, 'ui-ux'));
const matchedAction = findNodes(matchedDrawer, 'BUTTON', '按该领域查看能力')[0];
if (matchedAction.attributes.has('disabled'))
  throw new Error('有已接线关联时动作不该继续禁用');
const beforeHash = shell.window.location.hash;
shell.pending.splice(0, shell.pending.length);
if (typeof matchedAction.onclick !== 'function')
  throw new Error('关联动作没有 onclick，等于没有接线');
matchedAction.onclick();
if (shell.pending.length !== 0)
  throw new Error(`关联动作只许改地址，实得 ${shell.pending.length} 次请求`);
if (shell.window.location.hash === beforeHash)
  throw new Error('关联动作必须真的把地址切到能力目录，否则它什么都不做');
// D08: the tooltip promises the destination filters by the declared domain (`axes.domains`).
// A bare `#/capabilities` kept that promise uncheckable from here: the reader landed on the
// unfiltered library with nothing on screen saying which domain they had asked about.
if (shell.window.location.hash !== '#/capabilities?domain=ui-ux')
  throw new Error('关联动作必须把声明领域带进地址，实得 '
    + `${shell.window.location.hash} —— 一个不带条件的跳转与它自己的 tooltip 矛盾`);
if (!matchedDrawer.textContent.includes('已接线 12 条'))
  throw new Error(`命中数要按这次读回给出：${matchedDrawer.textContent.slice(-320)}`);

// A pack that declares no domain at all has no join key: that is neither "N matches" nor
// "this domain has no capabilities", and the panel must not imply either.
const noKeyDrawer = await renderDomainDetail('#/domains/minigame-design');
if (!noKeyDrawer.textContent.includes('无关联键'))
  throw new Error(`未声明领域的域包要说"无关联键"：${noKeyDrawer.textContent.slice(-320)}`);
if (noKeyDrawer.textContent.includes('已接线 0 条'))
  throw new Error(`没有关联键时不得给出命中数：${noKeyDrawer.textContent.slice(-320)}`);
const navOwner = [];
walkNodes(shell.context.document.body, (node) => {
  if (node?.dataset?.route === 'design-domains') navOwner.push(node);
});
if (navOwner.length !== 1)
  throw new Error(`导航里应当只有一个 design-domains 入口，实得 ${navOwner.length} 个`);
if (navOwner[0].attributes.get('aria-current') !== 'page')
  throw new Error('域包详情必须让父级 设计领域 入口保持高亮，否则读起来像已经离开目录');

// A rejected pack keeps its reasons when addressed directly, and a v1 manifest's silence
// about `domain` is shown as 未声明 rather than an empty slug.
const badDrawer = await renderDomainDetail('#/domains/minigame-design');
if (!badDrawer.textContent.includes("'domain' is a required property"))
  throw new Error('被拒绝的域包直接寻址时必须带着校验器原因');
if (!badDrawer.textContent.includes('校验器共 11 条'))
  throw new Error('原因被截断时必须注明校验器实际给出了多少条');
if (!badDrawer.textContent.includes('未声明'))
  throw new Error('v1 清单没有 domain 字段，详情要说未声明而不是留空');
const badMarked = [];
walkNodes(badDrawer, (node) => {
  if (node?.attributes?.get('lang') === 'en') badMarked.push(node.textContent);
});
if (!badMarked.includes('INVALID'))
  throw new Error(`详情里的判定词必须带 lang="en"（服务词汇）：${badMarked.join('/')}`);

// A legal-shaped id outside the readback says it was not found, and borrows nothing.
const missDrawer = await renderDomainDetail('#/domains/no-such-pack');
if (!missDrawer.textContent.includes('未找到该域包'))
  throw new Error(`未找到的详情必须照实说：${missDrawer.textContent.slice(0, 160)}`);
for (const borrowed of ['jsonschema', 'ui-ux', 'design-lab/domain-pack/v2'])
  if (missDrawer.textContent.includes(borrowed))
    throw new Error(`未找到的详情不得借用另一个域包的 ${borrowed}`);

// Only a pack that declares a pack_id owns an address. The list must say so for one that
// does not, instead of synthesising a link out of the directory name.
const idless = await renderDomainRegistry({ ...DOMAINS_READBACK,
  counts: { packs: 3, byValidation: { VALIDATES: 1, INVALID: 1, UNREADABLE: 0, NOT_CHECKED: 1 } },
  packs: [...DOMAINS_READBACK.packs, { directory: 'legacy-no-id', packId: null, version: null,
    displayName: null, domain: null, manifestSchemaVersion: null, dependencies: null,
    validation: 'NOT_CHECKED', validationErrors: [], validationErrorCount: 0, note: null }] });
if (!idless.textContent.includes('域包登记（3）'))
  throw new Error(`读回给出 3 个目录时列表必须写 3：${idless.textContent.slice(0, 160)}`);
const openButtons = findNodes(idless, 'BUTTON', '查看详情');
if (openButtons.length !== 2)
  throw new Error(`只有声明了 pack_id 的行才有入口，期望 2 实得 ${openButtons.length}`);
if (!idless.textContent.includes('无独立地址：清单未声明 pack_id'))
  throw new Error('没有 pack_id 的域包必须说明它为何没有地址');
shell.window.location.hash = '#/dashboard';
openButtons[0].onclick();
if (shell.window.location.hash !== '#/domains/uiux-design')
  throw new Error(`行内入口必须落到该 pack 自己的地址，实得 ${shell.window.location.hash}`);
console.log('ok: ⑪ 域包二级入口有独立地址、父级高亮、跨目录动作禁用并说明原因、借用与凭空计数都不出现');

// ⑫ R2 §4 资产类型 tabs. The shipped catalog has every classification axis empty and
// counts.qualifiedTrue = 0 (all 60 records sit in qualificationNotAdjudicated), so a tab strip
// built from that data alone cannot tell an honest
// empty state apart from a hardcoded one. This block therefore seeds a fixture where ONE
// record IS classified and IS qualified: the tabs must follow the fields, not the shipped
// emptiness. It also pins the two lies the design has to refuse -- counting 可调用能力 by
// `kind` (which would claim every record is callable), and drawing a confident 0 when the
// readback never answered.
const AXES_EMPTY = { domains: [], artifactTypes: [], capabilityLayers: [], aestheticAxes: [],
  styleArchetypes: [], tier: [], designQuality: [] };
const capabilityRecord = (over) => ({
  id: 'cap-x', kind: 'source', domain: null, title: 't', disposition: 'CONDITIONAL_POC',
  license: 'MIT', presence: 'UPSTREAM', url: null, revision: null, revisionState: 'NOT_VERIFIED',
  revisionReason: null, repo: null, observedAt: null, contentDigest: null,
  qualified: null, qualificationEvidence: null, qualificationReason: '尚无宿主运行与人工验收',
  axes: { ...AXES_EMPTY }, sourceType: null, evidenceLevel: null, upstreamOwner: null,
  licenseUrl: null, rightsNotes: null, removalPath: null, popularity: null,
  unclassifiedAxes: Object.keys(AXES_EMPTY), ...over,
});
const CAPABILITIES_READBACK = {
  schemaVersion: 'design-lab/capability-library/v1',
  meaning: 'Read-only projection.', unmeasuredMeans: 'null = not measured.',
  classification: { joined: 1, unclassifiedAxes: ['domains'], note: '填轴是人工分类工作。' },
  counts: { total: 3, byKind: { source: 2, model: 1 }, byLicense: { MIT: 3 },
    byRevisionState: { NOT_VERIFIED: 3 }, qualified: 1 },
  sources: {},
  capabilities: [
    capabilityRecord({ id: 'plain-one' }),
    capabilityRecord({ id: 'plain-two', kind: 'model' }),
    capabilityRecord({ id: 'classified-three', qualified: true,
      qualificationEvidence: ['E2-run-1'], qualificationReason: null,
      axes: { ...AXES_EMPTY, artifactTypes: ['template'], capabilityLayers: ['specification'] },
      unclassifiedAxes: ['domains'] }),
  ],
};

async function renderCapabilities(payload) {
  shell.window.location.hash = '#/dashboard';
  shell.dispatchHashchange();
  shell.pending.splice(0, shell.pending.length);
  shell.window.location.hash = '#/capabilities';
  shell.dispatchHashchange();
  const reads = shell.pending.splice(0, shell.pending.length);
  if (reads.length !== 1 || reads[0].path !== '/api/capabilities')
    throw new Error(`#/capabilities 应恰好一次 GET /api/capabilities，实得 ${reads.length} 次`);
  reads[0].resolve(response(payload));
  await flush();
  return shell.elements.get('route-view');
}

const tabButtons = (root) => findNodes(root, 'BUTTON', '').filter(
  (n) => n.attributes.get('role') === 'tab');
const TAB_LABELS = ['全部资产', '可调用能力', '规范与方法', '案例与参考', '模板与配方'];

const capView = await renderCapabilities(CAPABILITIES_READBACK);
const tabs = tabButtons(capView);
if (tabs.length !== TAB_LABELS.length)
  throw new Error(`§4 要求五张资产类型 tab，实得 ${tabs.length} 张`);
for (const [i, label] of TAB_LABELS.entries()) {
  if (!tabs[i].textContent.includes(label))
    throw new Error(`第 ${i + 1} 张 tab 不是 ${label}：${tabs[i].textContent}`);
}
const selected = tabs.filter((t) => t.attributes.get('aria-selected') === 'true');
if (selected.length !== 1)
  throw new Error(`tablist 必须恰好一个 aria-selected=true，实得 ${selected.length} 个`);

// The counts come from the fields, so the classified record is what separates the tabs.
// 全部资产 3 / 可调用能力 1 / 三个类型 tab 各 1 -- and crucially NOT 3 under 可调用能力,
// which is what mapping that tab to `kind` would have printed.
const counts = tabs.map((t) => t.textContent.replace(/\D+/g, ''));
if (counts.join(',') !== '3,1,1,1,1')
  throw new Error(`tab 计数没有跟着真实字段走，实得 ${counts.join(',')}（期望 3,1,1,1,1）`);

// Selecting a tab filters the table and keeps the entry.
tabs[1].onclick();
await flush();
const callable = shell.elements.get('route-view').textContent;
if (!callable.includes('classified-three') || callable.includes('plain-one'))
  throw new Error(`可调用能力应只剩有资格判定的那一条：${callable.slice(0, 200)}`);
if (!callable.includes('显示 1 / 3 条'))
  throw new Error(`切 tab 后计数行没跟着走：${callable.slice(0, 200)}`);

// An empty tab keeps its entry and names the field it asked, instead of implying the
// service judged the category empty.
tabs[2].onclick();
await flush();
const specTab = shell.elements.get('route-view').textContent;
if (!specTab.includes('规范与方法'))
  throw new Error('空结果的 tab 不得从屏上消失（R2 §2：不因零条移除分类）');
tabs[0].onclick();
await flush();

// The shipped catalog really is unclassified, so the shared-basis disclosure must appear.
const allEmpty = { ...CAPABILITIES_READBACK,
  capabilities: [capabilityRecord({ id: 'plain-one' }), capabilityRecord({ id: 'plain-two' })],
  counts: { ...CAPABILITIES_READBACK.counts, total: 2, qualified: 0 } };
const emptyView = await renderCapabilities(allEmpty);
const emptyTabs = tabButtons(emptyView);
// "0" and "never classified" are different claims. The axis carries no value on any record
// here, so the three type tabs must badge 未分类 while 可调用能力 keeps its measured zero
// (no qualification verdicts IS an answer) and 全部资产 keeps its count.
const emptyBadges = emptyTabs.map((t) => t.textContent.replace(t.children[0].textContent, ''));
if (emptyBadges.join('|') !== '2|0|未分类|未分类|未分类')
  throw new Error(`未分类不得被显示成 0 条，实得 ${emptyBadges.join('|')}`);
emptyTabs[2].onclick();
await flush();
const emptyText = shell.elements.get('route-view').textContent;
for (const phrase of ['同一个空集', 'artifactTypes', '不替它猜词表'])
  if (!emptyText.includes(phrase))
    throw new Error(`三个类型 tab 共用一个空轴时，屏上必须写明这一点，缺 ${phrase}`);
if (!emptyText.includes('未判定') && !emptyText.includes('没有给出任何命中的记录'))
  throw new Error(`空 tab 必须说清是哪一层空：${emptyText.slice(0, 240)}`);

// The lie block ⑨ exists to catch, in this view's own words: an unread readback must not
// be drawn as a measured zero.
const unreadView = await renderCapabilities({});
const unreadTabs = tabButtons(unreadView).map((t) => t.textContent);
// Not `/(?<!未读回)\b0\b/`: `\b` is a word boundary over \w only, and CJK is not a word
// character, so that guard could never have matched anything. The check is on the rendered
// form -- a tab labelled "未读回" carries no digit at all.
if (unreadTabs.some((t) => /\d/.test(t)))
  throw new Error(`未读回时 tab 上不得出现任何数字：${unreadTabs.join(' | ')}`);
if (!unreadTabs.every((t) => t.includes('未读回')))
  throw new Error(`未读回时每张 tab 都要标未读回：${unreadTabs.join(' | ')}`);
if (unreadView.textContent.includes('共 0 条'))
  throw new Error('未读回的计数被画成了 0 条');
// D07 — `qualified` is a verdict on a three-value domain: true / false / null (未判定). The
// 可调用能力 tab asked `!== null`, so a record the service had explicitly judged NOT callable
// sat beside the callable ones in the one tab whose whole purpose is "what can I actually call".
// A fixture with all three values is the only form that can tell the two predicates apart.
{
  const threeWay = { ...CAPABILITIES_READBACK, capabilities: [
    capabilityRecord({ id: 'callable-one', qualified: true,
      qualificationEvidence: ['E2-run-1'], qualificationReason: null }),
    capabilityRecord({ id: 'refused-two', qualified: false,
      qualificationReason: '许可不允许再分发' }),
    capabilityRecord({ id: 'unjudged-three', qualified: null }),
  ], counts: { ...CAPABILITIES_READBACK.counts, total: 3, qualified: 1 } };
  const view = await renderCapabilities(threeWay);
  const t = tabButtons(view);
  const badge = (tab) => tab.textContent.replace(tab.children[0].textContent, '');
  if (badge(t[1]) !== '1')
    throw new Error(`qualified=false 与 null 都不算可调用，这一 tab 应为 1，实得 ${badge(t[1])}`);
  t[1].onclick();
  await flush();
  const text = shell.elements.get('route-view').textContent;
  if (!text.includes('callable-one'))
    throw new Error(`可调用能力丢了唯一一条合格记录：${text.slice(0, 200)}`);
  if (text.includes('refused-two'))
    throw new Error('qualified=false 的记录被算成了可调用 —— 这正是 `!== null` 做的事');
  if (text.includes('unjudged-three'))
    throw new Error('未判定（null）不等于可调用，不得出现在这一类里');
  t[0].onclick();
  await flush();
}

// D08 — the capability library has to be able to ANSWER the condition the domain drawer puts in
// its address. Three claims are pinned: the conditional address still resolves to this route,
// the condition is shown as a condition (not silently applied), and removing it is its own
// action — 「清除检索条件」 is specified to clear the search only.
{
  // `byIdAttr` is declared further down the file, and a `const` read before its line is a TDZ
  // error rather than a null -- so this block carries its own finder over the ⑪ walkers.
  const condById = (root, id) => {
    let hit = null;
    walkNodes(root, (node) => { if (node?.attributes?.get('id') === id) hit = node; });
    return hit;
  };
  const readback = { ...CAPABILITIES_READBACK, capabilities: [
    capabilityRecord({ id: 'declares-ui-ux',
      axes: { ...AXES_EMPTY, domains: ['ui-ux'] }, unclassifiedAxes: [] }),
    capabilityRecord({ id: 'declares-other',
      axes: { ...AXES_EMPTY, domains: ['video-generation'] }, unclassifiedAxes: [] }),
    capabilityRecord({ id: 'never-classified', unclassifiedAxes: Object.keys(AXES_EMPTY) }),
  ], counts: { ...CAPABILITIES_READBACK.counts, total: 3, qualified: 0 } };
  // A conditional hash is still `#/capabilities`: matching the raw hash sent it to the legacy
  // workbench page, i.e. the condition quietly lost the route that carried it.
  shell.window.location.hash = '#/capabilities?domain=ui-ux';
  shell.dispatchHashchange();
  const reads = shell.pending.splice(0, shell.pending.length);
  if (reads.length !== 1 || reads[0].path !== '/api/capabilities')
    throw new Error(`带条件的地址没有解析成能力目录路由，实得 `
      + `${reads.map((r) => r.path).join(', ') || '零次读回'}（路由身份必须由路径决定）`);
  reads[0].resolve(response(readback));
  await flush();
  const conditioned = shell.elements.get('route-view');
  const activeBar = condById(conditioned, 'capability-active');
  if (!activeBar)
    throw new Error('条件没有上屏：地址里带着条件，屏上必须能看出在按什么过滤');
  if (!activeBar.textContent.includes('声明领域') || !activeBar.textContent.includes('ui-ux'))
    throw new Error(`条件条没有说出条件：${activeBar.textContent.slice(0, 200)}`);
  // "filtered out" and "never classified" are different answers, and the count has to separate
  // them -- otherwise a reader cannot tell a strict filter from an unclassified library.
  if (!/1 条在 axes\.domains 声明了/.test(activeBar.textContent)
    || !/1 条自己记着 domains 轴未分类/.test(activeBar.textContent))
    throw new Error(`条件条必须给出命中数与未分类数：${activeBar.textContent.slice(0, 240)}`);
  if (!conditioned.textContent.includes('declares-ui-ux')
    || conditioned.textContent.includes('declares-other'))
    throw new Error(`列表没有按声明领域过滤：${conditioned.textContent.slice(0, 200)}`);
  // 「清除检索条件」 must leave the domain choice alone (R2 §4 末段), and the chip's own × must
  // be the thing that removes it.
  const clearBtn = condById(conditioned, 'capability-clear');
  if (!clearBtn) throw new Error('条件条没有「清除检索条件」按钮');
  const hashBeforeClear = shell.window.location.hash;
  clearBtn.onclick();
  await flush();
  if (shell.window.location.hash !== hashBeforeClear)
    throw new Error('「清除检索条件」不允许清掉领域条件（它只清检索）');
  const chipX = (activeBar.querySelectorAll('.capability-chip-x') ?? [])[0];
  if (!chipX) throw new Error('条件条没有可单独移除的条件 chip');
  chipX.onclick();
  await flush();
  if (shell.window.location.hash !== '#/capabilities')
    throw new Error(`移除条件应把地址收回 #/capabilities，实得 ${shell.window.location.hash}`);
}

console.log('ok: ⑱ §4 可调用能力只收 qualified === true：false 与 null 各自都不算，'
  + '载入三类取值的读回才分得开这两个谓词');
console.log('ok: ⑲ §2→§4 声明领域条件随跳转进入地址（#/capabilities?domain=… 仍解析成能力目录）、'
  + '条件上屏且分别给出命中数与未分类数、「清除检索条件」不清领域、chip 的 × 才收回条件');

console.log('ok: ⑫ §4 资产类型 tabs 跟着真实字段计数、可调用能力不按 kind 充数、空轴共用同一空集并写明、未读回不画 0');

// ⑬ R2 §6 输入与目标的**写入**. design.ts createBrief() is the single seam that validates the
// draft and mints the idempotency key, and #/intake is its routed call site -- yet blocks
// ⑥⑦⑧⑩ each prove "one click, one POST, exactly the contract keys" for their own panel
// while this one had no such proof. An unmounted write path is not a delivered screen, and
// the panel puts a claim on screen ("相同内容重试会复用同一幂等键") that has to be tested.
// `byElementId` is declared further down the file, so this block uses its own finder built
// on the ⑪ walkers: `el()` routes `id` through setAttribute, not a property.
const byIdAttr = (root, id) => {
  let hit = null;
  walkNodes(root, (node) => { if (node?.attributes?.get('id') === id) hit = node; });
  return hit;
};
shell.window.location.hash = '#/intake';
shell.dispatchHashchange();
const intakeProjectsReq = shell.pending.shift();
if (intakeProjectsReq.path !== '/api/projects')
  throw new Error(`输入与目标没有先读项目列表，实得 ${intakeProjectsReq.path}`);
intakeProjectsReq.resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
await flush();
const intakeView = shell.elements.get('route-view');
const intakeSelect = byIdAttr(intakeView, '输入与目标-project');
if (!intakeSelect) throw new Error('输入与目标没有渲染项目选择器，⑬ 找不到入口');
intakeSelect.value = 'p1';
intakeSelect.onchange();
const intakeReads = shell.pending.splice(0, shell.pending.length);
for (const request of intakeReads) answerIntakeRead(request, { briefs: [] });
await flush();

const intakeTitle = byIdAttr(intakeView, 'intake-title');
const intakeGoals = byIdAttr(intakeView, 'intake-goals');
const intakeConstraints = byIdAttr(intakeView, 'intake-constraints');
const intakeSubmit = byIdAttr(intakeView, 'intake-submit');
for (const [name, node] of [['intake-title', intakeTitle], ['intake-goals', intakeGoals],
  ['intake-constraints', intakeConstraints], ['intake-submit', intakeSubmit]])
  if (!node) throw new Error(`输入与目标缺少控件 ${name}`);

// A blank title is refused locally: nothing may reach the service.
intakeTitle.value = '   ';
intakeGoals.value = '建立识别, , 复用版式';
intakeSubmit.onclick();
await flush();
const emptyTitleReqs = shell.pending.splice(0, shell.pending.length);
if (emptyTitleReqs.length)
  throw new Error(`空标题被本地拒绝时仍发出了 ${emptyTitleReqs.length} 个请求`);
if (!(intakeView.textContent || '').includes('请填写简报标题'))
  throw new Error('空标题必须给出可行动的拒绝原因');

// One click, one POST, exactly the five contract keys, with the goals split trimmed.
intakeTitle.value = '  秋季品牌视觉  ';
intakeGoals.value = '建立识别, , 复用版式';
intakeConstraints.value = '主色不得改';
intakeSubmit.onclick();
await flush();
const briefReqs = shell.pending.splice(0, shell.pending.length);
if (briefReqs.length !== 1) {
  const dbg = (intakeView.textContent || '').replace(/\s+/g, ' ');
  throw new Error(`一次提交应恰好一个请求，实得 ${briefReqs.length} 个 :: 屏上=${dbg.slice(-420)}`);
}
if (briefReqs[0].path !== '/api/projects/p1/briefs')
  throw new Error(`提交打到了 ${briefReqs[0].path}`);
const briefBody = JSON.parse(briefReqs[0].init.body);
const bodyKeys = Object.keys(briefBody).sort().join(',');
if (bodyKeys !== 'constraints,goals,idempotency_key,reference_asset_ids,title')
  throw new Error(`简报正文必须恰好是合同五个键，实得 ${bodyKeys}`);
if (briefBody.title !== '秋季品牌视觉')
  throw new Error(`标题必须去掉首尾空白后写入，实得 ${JSON.stringify(briefBody.title)}`);
if (briefBody.goals.join('|') !== '建立识别|复用版式')
  throw new Error(`空目标段必须被丢掉，实得 ${briefBody.goals.join('|')}`);
if (!Array.isArray(briefBody.reference_asset_ids))
  throw new Error('reference_asset_ids 必须是数组');
if (!/^[0-9a-f-]{36}$/.test(String(briefBody.idempotency_key)))
  throw new Error(`幂等键形状不对：${briefBody.idempotency_key}`);
briefReqs[0].resolve(response({ brief_id: 'brief-1', version: 1 }));
await flush();

// The claim printed on the panel: retrying the SAME content reuses the key, changing it
// does not. If createBrief ever stops doing this, the copy is the bug.
// The intake panel reads the brief list AND the project's design layer (for the knowledge
// context), so a drain must answer each path with its own shape. Handing the design-layer
// GET the briefs payload made the panel read `chosen_direction` off undefined -- and the
// suite still printed "all checks passed" while exiting 1, so this helper is used by every
// drain in this block and the exit code is what gets believed.
function answerIntakeRead(request, briefsPayload) {
  if ((request.init?.method ?? 'GET') !== 'GET')
    throw new Error(`读回阶段出现了写请求 ${request.path} —— 构建界面必须零 POST`);
  if (request.path.includes('/design-layer')) {
    request.resolve(response({ design_layer: { briefs: [], directions: [],
      chosen_direction: null, bindings: [], active_binding: null,
      design_systems: [] } }));
    return;
  }
  request.resolve(response(briefsPayload));
}

async function drainIntakeReads(briefsPayload) {
  await flush();
  const reads = shell.pending.splice(0, shell.pending.length);
  for (const request of reads) answerIntakeRead(request, briefsPayload);
  await flush();
  return reads.length;
}

const firstKey = briefBody.idempotency_key;
await drainIntakeReads({ briefs: [] });
intakeSubmit.onclick();
await flush();
const retryReqs = shell.pending.splice(0, shell.pending.length);
if (retryReqs.length !== 1)
  throw new Error(`重试应恰好一个请求，实得 ${retryReqs.length} 个`);
const retryKey = JSON.parse(retryReqs[0].init.body).idempotency_key;
if (retryKey !== firstKey)
  throw new Error(`相同内容重试换了幂等键（${firstKey} -> ${retryKey}），屏上那句话就成了假话`);
retryReqs[0].resolve(response({ brief_id: 'brief-1', version: 1 }));
await drainIntakeReads({ briefs: [] });
intakeTitle.value = '秋季品牌视觉 v2';
intakeSubmit.onclick();
await flush();
const changedReqs = shell.pending.splice(0, shell.pending.length);
const changedKey = JSON.parse(changedReqs[0].init.body).idempotency_key;
if (changedKey === firstKey)
  throw new Error('内容变了还复用同一个幂等键，第二次写入会被服务端当成同一次');
changedReqs[0].resolve(response({ brief_id: 'brief-2', version: 1 }));
await drainIntakeReads({ briefs: [] });

// A service refusal keeps the service's own words and never claims persistence.
intakeTitle.value = '另一个简报';
intakeGoals.value = '目标一';
intakeSubmit.onclick();
await flush();
const intakeRefused = shell.pending.splice(0, shell.pending.length);
intakeRefused[0].resolve(response({ error: 'RIGHTS_GATE_BLOCKED', message: '许可未过权利门' }, false));
await flush();
const refusalText = (intakeView.textContent || '').replace(/\s+/g, ' ');
if (refusalText.includes('简报已持久化'))
  throw new Error('服务拒绝了写入，屏上不得说已持久化');
console.log('ok: ⑬ 输入与目标的简报写入：构建零 POST、空标题本地拒、一次点击一个请求且只带合同五键、相同内容复用幂等键、改内容换新键、拒绝不谎报已写入');

// ⑭ DL-UI-U05 · 目标生成包的拒绝种类。U05 的验收把 error / forbidden / conflict / timeout
// 列为不同状态，而 native_submissions.py 确实用五个代码、三种状态码回答。此前 #/plan 把它们
// 全画成一张"未受理"卡片，读者无法判断该重试、该换键还是该换素材。
// The fixture carries the key set the live route serves (contracts.ts::AssetRecord, measured
// 2026-10-28): byte_size and version_id are in it, `kind` and `version_no` never were -- a
// fixture that keeps the phantom keys lets the page pass on fields no response can produce.
const PLAN_ASSET = { assets: [{ id: 'img-' + 'a'.repeat(62), media_type: 'image/png',
  width: 1080, height: 1920, rights: 'UNVERIFIED', byte_size: 2411520,
  version_id: 'v-' + 'b'.repeat(32), sha256: 'sha256:' + 'c'.repeat(64) }] };
const byAria = (root, label) => {
  let hit = null;
  walkNodes(root, (node) => {
    if (node?.attributes?.get('aria-label') === label) hit = node;
  });
  return hit;
};

async function openPlan() {
  shell.window.location.hash = '#/dashboard';
  shell.dispatchHashchange();
  shell.pending.splice(0, shell.pending.length);
  shell.window.location.hash = '#/plan';
  shell.dispatchHashchange();
  const projectsReq = shell.pending.shift();
  if (projectsReq.path !== '/api/projects')
    throw new Error(`#/plan 没有先读项目列表，实得 ${projectsReq.path}`);
  projectsReq.resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
  await flush();
  const view = shell.elements.get('route-view');
  const picker = byIdAttr(view, '目标生成包-project');
  if (!picker) throw new Error('#/plan 没有渲染项目选择器');
  picker.value = 'p1';
  picker.onchange();
  const assetReq = shell.pending.shift();
  if (!assetReq.path.endsWith('/assets'))
    throw new Error(`选项目后 #/plan 应读资产，实得 ${assetReq.path}`);
  assetReq.resolve(response(PLAN_ASSET));
  await flush();
  return view;
}

const planView = await openPlan();
const planAssets = byAria(planView, '参考底图资产');
const planSubmit = byIdAttr(planView, 'plan-submit');
if (!planAssets || !planSubmit)
  throw new Error('#/plan 缺少资产选择器或提交按钮');

// No asset chosen -> nothing may leave the page.
planSubmit.onclick();
await flush();
if (shell.pending.length)
  throw new Error('没有底图时 #/plan 仍然发出了请求；raster.path 必须指向已导入资产');
if (!(planView.textContent || '').includes('没有底图资产就不提交'))
  throw new Error('没有底图时页面必须说明为什么不提交');

planAssets.value = PLAN_ASSET.assets[0].id;
planAssets.onchange();
await flush();

// Each code gets its own sentence. The pairs that must NOT read alike are the ones a user
// could act on the wrong way: busy (retry) vs idempotency conflict (do not reuse the key).
// The third column is the STATE KIND, and it is here because the sentence alone can look
// right while wearing the wrong semantic class: until 2026-10-10 the 409 idempotency
// conflict rendered as `forbidden`, which tells the operator to request access when the
// real action is to stop reusing the key. Both 409s must also land on DIFFERENT kinds.
const REFUSALS = [
  ['NATIVE_PLAN_IDEMPOTENCY_CONFLICT', '冲突：这个幂等键已经登记过别的内容', 'conflict'],
  ['NATIVE_SUBMISSION_BUSY', '未排队：本机服务正忙', 'unknown'],
  ['NATIVE_PLAN_TOO_LARGE', '目标包超过受理上限', 'error'],
  ['INVALID_NATIVE_KEY', '幂等键不合法', 'error'],
  ['INVALID_NATIVE_PLAN', '目标包不符合合同', 'error'],
];
const seenTitles = new Set();
const seenKinds = new Map();
for (const [code, expected, expectedKind] of REFUSALS) {
  planSubmit.onclick();
  await flush();
  const reqs = shell.pending.splice(0, shell.pending.length);
  if (reqs.length !== 1)
    throw new Error(`${code}: 一次点击应恰好一个请求，实得 ${reqs.length} 个`);
  reqs[0].resolve(response({ error: code }, false));
  await flush();
  const text = (planView.textContent || '').replace(/\s+/g, ' ');
  if (!text.includes(expected))
    throw new Error(`${code} 必须给出它自己的说法「${expected}」：…${text.slice(-260)}`);
  const refusalBlocks = [];
  walkNodes(planView, (node) => {
    if (node?.dataset?.stateKind !== undefined) refusalBlocks.push(node);
  });
  if (refusalBlocks.length !== 1)
    throw new Error(`${code}: 拒绝面应当恰好一个带状态类别的块，实得 ${refusalBlocks.length} 个`);
  const kind = refusalBlocks[0].dataset.stateKind;
  if (kind !== expectedKind)
    throw new Error(`${code} 的状态类别是 ${kind}，应为 ${expectedKind}`
      + '（409 幂等冲突是 conflict，不是 forbidden：前者让人换键，后者让人去要权限）');
  seenKinds.set(code, kind);
  if (!text.includes(code))
    throw new Error(`${code}: 屏上必须带上服务端代码本身，那是运维带回 CLI 的把手`);
  seenTitles.add(expected);
}
if (seenTitles.size !== REFUSALS.length)
  throw new Error('五种拒绝里有两种说了同一句话');
if (seenKinds.get('NATIVE_PLAN_IDEMPOTENCY_CONFLICT') === seenKinds.get('NATIVE_SUBMISSION_BUSY'))
  throw new Error('两个 409 用了同一个状态类别：忙是可重试的，幂等冲突不是，共用一个类别'
    + '就是把"换键"和"再点一次"说成同一件事');

// A transport failure is not a server refusal: nothing was answered, so nothing may be
// claimed about acceptance -- and the reader is pointed at the task ledger first.
planSubmit.onclick();
await flush();
const lost = shell.pending.splice(0, shell.pending.length);
lost[0].reject(new Error('Failed to fetch'));
await flush();
const lostText = (planView.textContent || '').replace(/\s+/g, ' ');
if (!lostText.includes('请求没有到达服务端'))
  throw new Error(`没有回复时必须说"没有到达服务端"，而不是当成一次业务拒绝：${lostText.slice(-260)}`);
if (lostText.includes('未受理'))
  throw new Error('连接失败不得被说成服务端未受理——那等于替服务编了一个结论');

// Success still says queueing is not completion.
planSubmit.onclick();
await flush();
const okReq = shell.pending.splice(0, shell.pending.length);
okReq[0].resolve(response({ task_id: 'native-job-abc', state: 'QUEUED' }));
await flush();
const okText = (planView.textContent || '').replace(/\s+/g, ' ');
if (!okText.includes('排队不等于完成'))
  throw new Error('受理成功后仍要写明排队不等于宿主已启动');

// U05: 普通用户无需JSON -- the RIR is a secondary, collapsed review surface.
const rirDetails = [];
walkNodes(planView, (node) => {
  if (node?.tagName === 'DETAILS') rirDetails.push(node);
});
if (!rirDetails.length)
  throw new Error('RIR 应放在一个可折叠的次级查看面里，而不是主面板');
if (rirDetails.some((d) => d.attributes.has('open')))
  throw new Error('JSON 查看面默认必须收起');
console.log('ok: ⑭ 目标生成包的五种服务端拒绝各说各话且带代码、两种 409 落在不同状态类别、连接失败不冒充业务拒绝、无底图不发包、排队不等于完成、JSON 默认收起');

// ①/④ OFFLINE sweep. A second context that never connects: devMode() reads
// window.location.search, so '?dev=1' is what lets the seam answer with its honest empty
// payload. Those payloads are marked, and an empty that was never asked about must not be
// described with the wording reserved for a readback that really returned nothing.
const LIVE_ONLY_PHRASES = [
  '尚无项目。先在工作台新建项目，再读回此视图。',   // project picker
  '尚无项目 在工作台新建项目后出现。',              // projects table cell
  '尚无登记设计系统',                              // brand systems
  '尚无根登记', '尚无外置输入',                    // settings
  '尚无宿主任务',                                  // creative tools
  '尚无交付包',                                    // dashboard + deliverables
  '尚无任务 任务完成后交付包随读回导出。',          // deliverables tasks cell
  '尚无域包目录',                                  // design domains
];

const offline = makeContext();
offline.window.location.search = '?dev=1';
let offlineChecked = 0;
for (const hash of ['', ...routeHashes]) {
  offline.window.location.hash = hash;
  offline.dispatchHashchange();
  await flush();
  // The empty hash is the legacy workbench, which owns #workspace; every route view
  // renders into #route-view. Asking the wrong host would read an element that was
  // never built rather than the page that is actually on screen.
  const host = hash ? 'route-view' : 'workspace';
  const text = offline.elements.get(host)?.textContent ?? '';
  const leaked = LIVE_ONLY_PHRASES.filter((phrase) => text.includes(phrase));
  if (leaked.length)
    throw new Error(`未连接时 ${hash || '(workbench)'} 把没问过的事说成了实况：${leaked.join(' / ')}`);
  if (text.includes('未读回：未连接本机设计服务')) offlineChecked += 1;
}
if (offlineChecked < 5)
  throw new Error(`未连接态只有 ${offlineChecked} 个视图声明了未读回（下限 5）—— 空态措辞的门失效了`);
console.log(`ok: ① 未连接态 ${offlineChecked} 个视图报告未读回，${LIVE_ONLY_PHRASES.length} 条实况专属措辞零泄漏`);

// Positive control for the same switch: connected, with a service that really answers an
// empty collection, the page MUST claim the ledger is empty. Without this half the offline
// assertions above would be satisfied by deleting every empty-state sentence.
shell.window.location.hash = '#/projects';
shell.dispatchHashchange();
const emptyProjects = shell.pending.shift();
emptyProjects.resolve(response(projectsEnvelope([])));
await flush();
const liveEmptyText = shell.elements.get('route-view').textContent;
if (!liveEmptyText.includes('尚无项目 在工作台新建项目后出现。'))
  throw new Error(`服务真的答了空台账时，必须照实说尚无项目；实际读到：${liveEmptyText.slice(0, 240)}`);
if (liveEmptyText.includes('未读回'))
  throw new Error('一次形状完整的空读回不得出现任何未读回措辞');

shell.window.location.hash = '#/brand-systems';
shell.dispatchHashchange();
const emptySystems = shell.pending.shift();
emptySystems.resolve(response({ design_systems: [] }));
await flush();
const liveSystemsText = shell.elements.get('route-view').textContent;
if (!liveSystemsText.includes('尚无登记设计系统'))
  throw new Error('设计系统读回为空时页面必须说明为空');
console.log('ok: ④ 真实空读回仍照实报告为空（两个视图正向对照）');

// ② REQUEST FAILED, swept over every route. A connected session whose read comes back
// refused is the state most likely to lie by silence: the previous route's numbers could
// stay on screen and read as current. Measured behaviour being pinned here -- every route
// that asked the service shows ONLY the failure and its reason, and a route that never
// asks must not claim a failure it did not have.
let failedChecked = 0;
let sawTransport = false;
let sawUnparsable = false;
let sawServiceError = false;
for (const hash of routeHashes) {
  shell.window.location.hash = hash;
  shell.dispatchHashchange();
  const requests = shell.pending.splice(0, shell.pending.length);
  // Three different failures, cycled per route. They travel different code paths and the
  // operator needs a different next action from each: the request never reached the
  // service; the service answered with something that is not JSON; the service answered
  // with an error envelope. Cycling (rather than mixing inside one route) is required
  // because a view fires several reads together and the first rejection wins the catch.
  const kind = routeHashes.indexOf(hash) % 3;
  for (const request of requests) {
    if (kind === 0) request.reject(new Error('ECONNREFUSED 127.0.0.1'));
    else if (kind === 1) request.resolve({ ok: true, status: 200, json: async () => { throw new SyntaxError('Unexpected end of JSON input'); } });
    else request.resolve(response({ error: 'SERVICE_UNAVAILABLE' }, false));
  }
  await flush();
  const text = (shell.elements.get('route-view').textContent ?? '').trim();
  if (!requests.length) {
    if (text.includes('视图读回失败'))
      throw new Error(`${hash}: 这一面没有发起任何读回，却报告读回失败`);
    continue;
  }
  if (!text.startsWith('视图读回失败'))
    throw new Error(`${hash}: 读回被拒绝后页面没有以失败开头，旧内容可能留在屏上：${text.slice(0, 160)}`);
  if (!text.replace('视图读回失败：', '').trim())
    throw new Error(`${hash}: 只说失败、没有说原因`);
  if (!/无法连接本机设计服务|服务回复无法解析|SERVICE_UNAVAILABLE/.test(text))
    throw new Error(`${hash}: 失败原因里没有可诊断的信息：${text.slice(0, 160)}`);
  if (kind === 0) {
    if (!text.includes('无法连接本机设计服务') || !text.includes('ECONNREFUSED'))
      throw new Error(`${hash}: 连不上服务时既要说出"连不上"，也要保留底层原因：${text.slice(0, 160)}`);
    sawTransport = true;
  } else if (kind === 1) {
    if (!text.includes('服务回复无法解析') || !text.includes('HTTP 200'))
      throw new Error(`${hash}: 回复不是 JSON 时应说明无法解析与状态码：${text.slice(0, 160)}`);
    sawUnparsable = true;
  } else {
    if (!text.includes('SERVICE_UNAVAILABLE'))
      throw new Error(`${hash}: 服务错误码应原样上屏：${text.slice(0, 160)}`);
    sawServiceError = true;
  }
  if (text.includes('未读回：未连接'))
    throw new Error(`${hash}: 已连接但请求被拒，不是未连接，两种状态不得混用`);
  const leaked = LIVE_ONLY_PHRASES.filter((phrase) => text.includes(phrase));
  if (leaked.length)
    throw new Error(`${hash}: 失败页仍带着成功读回才有的措辞：${leaked.join(' / ')}`);
  failedChecked += 1;
}
if (failedChecked < 8)
  throw new Error(`② 失败态只有 ${failedChecked} 个视图被验证（下限 8）—— 该列的门失效了`);
// A single-request route can only ever show the transport path, so "both paths measured"
// has to be counted rather than asserted by intent.
if (!sawTransport || !sawServiceError || !sawUnparsable)
  throw new Error(`② 三种失败只测到 ${[
    sawTransport && '传输被拒', sawUnparsable && '回复不可解析', sawServiceError && '服务错误',
  ].filter(Boolean).join(' + ') || '无'}，另一种没有任何视图走过`);
console.log(`ok: ② 请求失败时 ${failedChecked} 个视图只报失败与原因（传输被拒 + 回复不可解析 + 服务错误三条路径都实测到），无旧内容残留`);

// ⑥ 产物预检 column, driven from a real click on the real bundle. The static contract
// (design-lab/tests/test_artifact_preflight_ui_contract.py) proves the page declares the
// profiles the route accepts and paints the fields the service sends; that is a text
// check and cannot see behaviour. This block proves: nothing is asked of the service
// while the page is being built, one click makes exactly one request to that bundle's
// own route, the readback carries the criterion behind each verdict, and a refusal
// replaces the previous verdict rather than decorating it.
function findIn(node, predicate) {
  if (node && predicate(node)) return node;
  for (const child of (node && node.children ? node.children : [])) {
    const hit = findIn(child, predicate);
    if (hit) return hit;
  }
  return null;
}
const byElementId = (root, id) => findIn(root, (node) => Boolean(node && node.attributes
  && typeof node.attributes.get === 'function' && node.attributes.get('id') === id));

const BUNDLE_ID = 'bundle-native-' + '0123456789abcdef'.repeat(4);
const BUNDLE_ROW = { id: BUNDLE_ID, kind: 'design-bundle', version_id: 'v-1', version_no: 1,
  byte_size: 2048, sha256: 'sha256:' + 'a'.repeat(64),
  rights: 'NOT_REVIEWED', verification: 'METADATA_ONLY' };
const TASK_ROW = (cancel) => ({ kind: 'photoshop-native', state: 'SUCCEEDED', job_id: 'job-1',
  cancel, attempt: { attempt_id: 'att-1', attempt_no: 1, state: 'RECEIPTED',
                     started_at: 'now', ended_at: 'now' } });
const resolveDeliverables = (requests, tasks) => {
  for (const request of requests)
    request.resolve(response(request.path.endsWith('/bundles') ? { bundles: [BUNDLE_ROW] }
      : { tasks }));
};
const PREFLIGHT_READBACK = {
  schemaVersion: 'design-lab/artifact-preflight/v1', profile: 'print',
  profileSchema: 'design-lab/preflight-profile/v1', verdict: 'INCOMPLETE',
  artifacts: [],
  findings: [
    { id: 'missing-links', severity: 'blocker', outcome: 'NOT_MEASURED',
      detail: '本构建没有该检查的测量器', criterion: '链接必须随包存在且摘要相符', measured: {} },
    { id: 'color-mode', severity: 'high', outcome: 'PASS',
      detail: '色彩模式 CMYK', criterion: '印刷交付应为 CMYK（ISO 12647 语境）', measured: {} },
  ],
  counts: { PASS: 1, WARNING: 0, FAIL: 0, NOT_MEASURED: 1, NOT_APPLICABLE: 0 },
  meaning: 'PASS 要求每条适用检查都被真量过且通过。',
};

shell.window.location.hash = '#/deliverables';
shell.dispatchHashchange();
const deliverableProjects = shell.pending.shift();
deliverableProjects.resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
await flush();
const routeView = shell.elements.get('route-view');
const projectSelect = byElementId(routeView, '交付中心-project');
if (!projectSelect) throw new Error('交付中心没有渲染项目选择器，⑥ 找不到入口');
// A real <select> defaults to its first option; the mock has no selection model, so the
// pick is applied the way the browser would apply it and the change handler runs.
projectSelect.value = 'p1';
projectSelect.onchange();
const built = shell.pending.splice(0, shell.pending.length);
for (const request of built)
  if (request.path.includes('/preflight'))
    throw new Error(`构建交付中心时就在预检 ${request.path} —— 没有人选过交付包，结论只能是猜测`);
resolveDeliverables(built, [TASK_ROW({ requested: true, acknowledged: false })]);
await flush();
// Reads that start after the awaited join still happen without a click, so the stray
// check has to run once the page has settled -- not only at the splice above.
const stray = shell.pending.splice(0, shell.pending.length);
if (stray.length)
  throw new Error(`没有人点击，页面却发出了 ${stray.map((r) => r.path).join(' ')} —— `
    + '预检结论不能来自一次没人请求的读取');

const runButton = byElementId(routeView, 'bundle-preflight-run');
if (!runButton) throw new Error('交付包读回后没有出现预检按钮');
if (runButton.disabled) throw new Error('有交付登记时预检按钮不得是禁用的');
const bundleSelect = byElementId(routeView, 'bundle-preflight-target');
const profileSelect = byElementId(routeView, 'bundle-preflight-profile');
if (!bundleSelect || !profileSelect) throw new Error('预检缺少交付包或 profile 选择器');
const outcomeHost = byElementId(routeView, 'bundle-preflight-outcome');
if (!outcomeHost) throw new Error('预检读回区不可定位 —— 它没有把结论挂在屏上的稳定位置');
bundleSelect.value = BUNDLE_ID;
profileSelect.value = 'print';
if (outcomeHost.textContent.includes('INCOMPLETE'))
  throw new Error('预检结论在没有点击之前就出现在屏幕上');

runButton.onclick();
const first = shell.pending.splice(0, shell.pending.length);
if (first.length !== 1) throw new Error(`一次点击发出了 ${first.length} 个请求，应为 1 个`);
if (first[0].path !== `/api/projects/p1/bundles/${BUNDLE_ID}/preflight?profile=print`)
  throw new Error(`点击预检打到了 ${first[0].path} —— 必须是所选交付包自己的路由`);
first[0].resolve(response(PREFLIGHT_READBACK));
await flush();
const outcomeText = outcomeHost.textContent;
for (const must of ['INCOMPLETE', 'missing-links', 'NOT_MEASURED', '未量 1 项 / 共 2 项',
                    '判据：印刷交付应为 CMYK（ISO 12647 语境）',
                    'PASS 要求每条适用检查都被真量过且通过。'])
  if (!outcomeText.includes(must))
    throw new Error(`预检读回缺少 ${must}：${outcomeText.slice(0, 200)}`);

// The refusal half: a rejected preflight must not leave the previous verdict standing.
bundleSelect.value = BUNDLE_ID;
runButton.onclick();
const second = shell.pending.splice(0, shell.pending.length);
if (second.length !== 1) throw new Error(`第二次点击发出了 ${second.length} 个请求`);
second[0].resolve(response({ error: '归档摘要与登记的字节不一致' }, false));
await flush();
const refused = outcomeHost.textContent;
if (!refused.includes('预检未确认') || !refused.includes('归档摘要与登记的字节不一致'))
  throw new Error(`预检被拒时页面没有说出拒绝原因：${refused.slice(0, 200)}`);
if (refused.includes('INCOMPLETE'))
  throw new Error('拒绝后上一条判定仍留在屏上，等于把失败的请求算成了一个结论');

// The cancel flags, on the same page. An attempt that receipted after the operator asked
// it to stop is a different outcome from an uncontested completion, and the state word
// alone cannot show it.
if (!routeView.textContent.includes('取消未确认'))
  throw new Error('取消未被确认却交付了结果时页面必须说出来，只写 RECEIPTED 会把被拒绝的操作说成被接受');
projectSelect.onchange();
const quiet = shell.pending.splice(0, shell.pending.length);
resolveDeliverables(quiet, [TASK_ROW({ requested: false, acknowledged: false })]);
await flush();
if (routeView.textContent.includes('取消未确认'))
  throw new Error('没有人请求取消时，页面不得说取消未确认');

console.log('ok: ⑥ 产物预检列不自动跑、一次点击一个请求、判据与未量项上屏、拒绝替换旧判定、未确认的取消上屏');

// ⑦ 证据系统 now reads back the operator records that already had working backends:
// the Human Jury verdicts (GET /jury), the artifact preflight of a chosen bundle and the
// delivery receipt of that bundle's version (GET .../receipt). Block ⑥ proved the same
// shape for the 交付中心 column; what is new here is (a) a route read that must
// distinguish "no receipt was recorded" from "these bytes will not be certified", and
// (b) a jury column that must not turn an unread readback into an empty list.
const EVIDENCE_VERSION_ID = 'v-' + '0123456789abcdef'.repeat(2);
const EVIDENCE_BUNDLE = { ...BUNDLE_ROW, version_id: EVIDENCE_VERSION_ID };
const JURY_SUBJECT = `version:${EVIDENCE_VERSION_ID}`;
const JURY_READBACK = {
  schemaVersion: 'design-lab/jury-readback/v1',
  records: [], verdict_count: 1, proposal_count: 2,
  current_verdicts: { [JURY_SUBJECT]: {
    verdict: 'APPROVE', kind: 'JURY_VERDICT',
    juror: { juror_id: 'dtalex66', kind: 'HUMAN', attestation: '在 100% 缩放下对照参考图审读' } } },
  reviewable_versions: [{ subject_ref: JURY_SUBJECT, artifact_sha256: 'sha256:' + 'a'.repeat(64),
                          asset_id: 'a1', version_no: 1 }],
  human_acceptance: 'ACCEPTED',
  // The denominator jury_review.py publishes with the word; the page has to show it.
  accepted_versions: 1, reviewable_active_versions: 1,
};
// The rights readback as `rights_review.readback()` shapes it: every collection the seam
// can report missing is here, the counts are numbers, and the clearance word is the one
// these rows actually support. Block ⑦ passes it so the jury assertions measure the jury;
// block ⑧ mutates it.
const RIGHTS_SCOPE_A = 'font-brandon-grotesk';
const RIGHTS_SCOPE_B = 'client-photo-01';
const RIGHTS_DECISION_A = 'rights-' + 'a'.repeat(32);
const RIGHTS_DECISION_B = 'rights-' + 'b'.repeat(32);
const RIGHTS_READBACK = {
  schemaVersion: 'design-lab/rights-readback/v1', project_id: 'p1',
  decisions: [], decision_count: 2,
  // The rows are `document_json` as rights_review.py returns it: the contract's own closed
  // property set, and nothing else. No actor_kind, no supersedes -- those are store columns
  // that never cross the HTTP boundary, which is exactly why name_checked_only exists.
  current_decisions: {
    [RIGHTS_SCOPE_A]: { decision_id: RIGHTS_DECISION_A,
      schemaVersion: 'design-lab/rights-decision/v1', use_scope: RIGHTS_SCOPE_A,
      decision: 'APPROVED', decided_by: 'dtalex66', decided_at: '2026-10-08T09:00:00Z',
      license_ref: 'LICENSE:OFL.txt', note: '对照 SIL OFL 1.1 全文确认桌面授权',
      territory: 'worldwide' },
    [RIGHTS_SCOPE_B]: { decision_id: RIGHTS_DECISION_B,
      schemaVersion: 'design-lab/rights-decision/v1', use_scope: RIGHTS_SCOPE_B,
      decision: 'DENIED', decided_by: 'dtalex66', decided_at: '2026-10-08T09:05:00Z' },
  },
  decision_states: { APPROVED: 1, DENIED: 1, PENDING_REVIEW: 0, BLOCKED_BY_LICENSE: 0 },
  filed_scope_count: 2, approved_scope_count: 1,
  unapproved_scopes: [{ use_scope: RIGHTS_SCOPE_B, decision: 'DENIED',
                        decision_id: RIGHTS_DECISION_B, decided_by: 'dtalex66' }],
  ever_filed_scopes: [RIGHTS_SCOPE_A, RIGHTS_SCOPE_B],
  scope_conflicts: [], name_checked_only: [RIGHTS_SCOPE_A, RIGHTS_SCOPE_B],
  rights_clearance: 'NOT_REVIEWED',
  clearance_vocabulary: ['CLEARED', 'NOT_REVIEWED'],
  decision_vocabulary: ['APPROVED', 'DENIED', 'PENDING_REVIEW', 'BLOCKED_BY_LICENSE'],
  does_not_prove: ['CLEARED covers the use scopes this project has actually filed a '
    + 'decision for; it holds no requirements list',
    'a rights decision clears none of the quality, production or release gates'],
};
// The document, and the envelope the route actually answers with. `rollback_proofs` is derived
// from the two `backup_ref` strings below and must stay consistent with them: the first is in the
// asset:<id>/version:<id> form the emitter writes and so can resolve, the second is not, and the
// aggregate word says plainly that only one of the two delivered artifacts has a live restore
// source. A fixture whose proofs disagreed with its own document would test the page against a
// payload no server can send.
const RECEIPT_SOURCE_ASSET = 'native-' + 'e'.repeat(64);
const RECEIPT_SOURCE_VERSION = 'v-' + 'd'.repeat(64);
const RECEIPT_DOCUMENT = {
  schemaVersion: 'design-lab/delivery-receipt/v2',
  job_id: 'native-job-' + '1'.repeat(64),
  created_at: '2026-10-08T09:00:00+00:00',
  axes: { delivery: 'PARTIAL' },
  receipt_id: 'receipt-' + 'a'.repeat(16),
  receipt_sha256: 'sha256:' + 'b'.repeat(64),
  deliverables: [
    { deliverable_id: 'native.psd', artifact_sha256: 'sha256:' + 'c'.repeat(64), byte_size: 4096,
      editable: true, host_readback: null, readback_matches_artifact: null,
      requirements: [{ req_id: 'req-rights-review', status: 'NOT_RUN' },
                     { req_id: 'req-native-bytes-verified', status: 'PASS' }],
      rollback: { backup_ref: `asset:${RECEIPT_SOURCE_ASSET}/version:${RECEIPT_SOURCE_VERSION}`,
        procedure: 'drop the appended version' } },
    { deliverable_id: 'preview.png', artifact_sha256: 'sha256:' + 'f'.repeat(64), byte_size: 1024,
      editable: false, host_readback: null, readback_matches_artifact: null,
      requirements: [{ req_id: 'req-rights-review', status: 'NOT_RUN' }],
      rollback: { backup_ref: `asset:${RECEIPT_SOURCE_ASSET}`,
        procedure: 'drop the appended version' } },
  ],
};
const RECEIPT_READBACK = {
  schemaVersion: 'design-lab/delivery-receipt-readback/v1',
  receipt: RECEIPT_DOCUMENT,
  rollback_state: 'PARTLY_UNRESOLVED',
  rollback_state_vocabulary: ['ALL_RESOLVED', 'PARTLY_UNRESOLVED', 'NONE_RESOLVED',
    'NOTHING_TO_CHECK', 'LEDGER_UNREADABLE'],
  rollback_states: ['RESOLVED', 'SOURCE_MISSING', 'OTHER_PROJECT', 'SOURCE_NOT_ACTIVE',
    'REF_UNPARSED'],
  state_meaning: {
    RESOLVED: 'the named asset version is still recorded here for this project and is ACTIVE',
    SOURCE_MISSING: 'no such version row exists for the named asset at all',
    OTHER_PROJECT: 'the version exists but its asset belongs to a different project',
    SOURCE_NOT_ACTIVE: 'the version row exists but is not ACTIVE',
    REF_UNPARSED: 'the reference is not in the asset:<id>/version:<id> form this emitter writes',
    ALL_RESOLVED: 'every deliverable names a restore source that still resolves',
    PARTLY_UNRESOLVED: 'some deliverables resolve and some do not',
    NONE_RESOLVED: 'no deliverable names a restore source that resolves',
    NOTHING_TO_CHECK: 'the receipt carries no deliverables, so there was nothing to resolve',
    LEDGER_UNREADABLE: 'the asset ledger could not be asked during this read, so no reference '
      + 'was checked',
  },
  rollback_proofs: [
    { deliverable_id: 'native.psd',
      backup_ref: `asset:${RECEIPT_SOURCE_ASSET}/version:${RECEIPT_SOURCE_VERSION}`,
      procedure: 'drop the appended version', state: 'RESOLVED',
      reason: `version 4 of asset ${RECEIPT_SOURCE_ASSET} is recorded ACTIVE for this project`,
      asset_id: RECEIPT_SOURCE_ASSET, version_id: RECEIPT_SOURCE_VERSION, version_no: 4,
      source_state: 'ACTIVE' },
    { deliverable_id: 'preview.png', backup_ref: `asset:${RECEIPT_SOURCE_ASSET}`,
      procedure: 'drop the appended version', state: 'REF_UNPARSED',
      reason: "it is not in the asset:<id>/version:<id> form, so it names no ledger row",
      asset_id: null, version_id: null, version_no: null, source_state: null },
  ],
  does_not_prove: [
    'a RESOLVED reference proves the source version is still recorded; no restore was performed',
    'resolution reads the asset ledger only; it opens no host document and re-runs no task',
  ],
};
const DESIGN_LAYER_EMPTY = { design_layer: { briefs: [], directions: [], chosen_direction: null,
  bindings: [], active_binding: null, design_systems: [] } };

function collectMarked(node, out = []) {
  if (node?.attributes?.get('lang') === 'en') out.push(node.textContent);
  for (const child of (node?.children ?? [])) collectMarked(child, out);
  return out;
}

shell.window.location.hash = '#/evidence';
shell.dispatchHashchange();
const evidencePickerRequest = shell.pending.splice(0, shell.pending.length);
if (evidencePickerRequest.length !== 1)
  throw new Error(`#/evidence 打开时发出了 ${evidencePickerRequest.length} 个请求，应只有项目台账`);
evidencePickerRequest[0].resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
await flush();
const evidenceView = shell.elements.get('route-view');
const evidenceSelect = byElementId(evidenceView, '证据系统-project');
if (!evidenceSelect) throw new Error('证据系统没有渲染项目选择器，⑦ 找不到入口');
evidenceSelect.value = 'p1';
evidenceSelect.onchange();
const evidenceBuild = shell.pending.splice(0, shell.pending.length);
const evidencePaths = evidenceBuild.map((request) => request.path);
for (const forbidden of ['/preflight', '/receipt'])
  if (evidencePaths.some((path) => path.includes(forbidden)))
    throw new Error(`构建证据页时就在运行交付结论 ${forbidden} —— 没有人选中交付包`);
const expects = ['/api/projects/p1/design-layer', '/api/projects/p1/bundles',
                 '/api/projects/p1/jury', '/api/projects/p1/rights'];
for (const expected of expects)
  if (!evidencePaths.includes(expected))
    throw new Error(`证据系统没有读回 ${expected}；实际读到 ${evidencePaths.join(' ')}`);
const answerEvidence = (requests, jury, bundles, rights) => {
  for (const request of requests) {
    if (request.path.endsWith('/jury')) request.resolve(response(jury));
    else if (request.path.endsWith('/bundles')) request.resolve(response(bundles));
    else if (request.path.endsWith('/rights')) request.resolve(response(rights ?? {}));
    else request.resolve(response(DESIGN_LAYER_EMPTY));
  }
};
// (a) A jury readback that never carried the collection must be reported as unread, and
// must NOT be shown as "there are no verdicts" -- the lie an empty <ul> tells.
answerEvidence(evidenceBuild, {}, { bundles: [EVIDENCE_BUNDLE] }, RIGHTS_READBACK);
await flush();
const unreadJuryText = evidenceView.textContent;
if (!/未读回[^\n]*current_verdicts|裁决未读回/.test(unreadJuryText))
  throw new Error(`jury 字段缺失时页面必须说未读回：…${unreadJuryText.slice(0, 260)}`);
if (unreadJuryText.includes('尚无人签署的裁决'))
  throw new Error('响应没有给出 current_verdicts 时，页面不得声称尚无人签署的裁决');
if (unreadJuryText.includes('视图读回失败'))
  throw new Error('缺少一个集合不得把整页压成读回失败');

// (b) A real verdict comes up with the service's own words, and the long ids stay on
// their own .value-mono rows.
shell.pending.splice(0, shell.pending.length);
evidenceSelect.onchange();
const juryReads = shell.pending.splice(0, shell.pending.length);
answerEvidence(juryReads, JURY_READBACK, { bundles: [EVIDENCE_BUNDLE] }, RIGHTS_READBACK);
await flush();
const juryText = evidenceView.textContent;
for (const must of ['APPROVE', JURY_SUBJECT, '在 100% 缩放下对照参考图审读',
                    '已签署 1 · Agent 建议 2', 'ACCEPTED', '当前版本已接受 1/1'])
  if (!juryText.includes(must))
    throw new Error(`人工裁决读回缺少 ${must}：${juryText.slice(0, 240)}`);
if (juryText.includes('尚无人签署的裁决'))
  throw new Error('有裁决可读回时页面仍说无人签署');
if (juryText.includes('未读回：响应缺少'))
  throw new Error('形状完整的裁决读回不得出现形状告警');
const juryMarked = collectMarked(evidenceView);
for (const word of ['ACCEPTED', 'JURY_VERDICT'])
  if (!juryMarked.includes(word))
    throw new Error(`判定 ${word} 必须带 lang="en"（服务词汇，不翻译）：${juryMarked.join('/')}`);

// (b2) A readback that carries no denominator must not have one invented for it.
// 0/0 would read as "nothing was left to accept" -- a claim about the ledger that the
// response never made, and exactly the shape this page has been caught on before.
shell.pending.splice(0, shell.pending.length);
evidenceSelect.onchange();
const bareReads = shell.pending.splice(0, shell.pending.length);
answerEvidence(bareReads, { ...JURY_READBACK,
                            accepted_versions: undefined,
                            reviewable_active_versions: undefined },
               { bundles: [EVIDENCE_BUNDLE] }, RIGHTS_READBACK);
await flush();
const bareText = evidenceView.textContent;
if (!bareText.includes('当前版本已接受 未读回'))
  throw new Error(`缺少分母时应说未读回：${bareText.slice(0, 240)}`);
if (bareText.includes('0/0'))
  throw new Error('页面把一个没读回的分数写成了 0/0');

// (c) The receipt: one click, one request to the selected version's own route.
const receiptButton = byElementId(evidenceView, 'evidence-receipt-run');
const preflightButton = byElementId(evidenceView, 'evidence-preflight-run');
const receiptBox = byElementId(evidenceView, 'evidence-receipt-outcome');
const preflightBox = byElementId(evidenceView, 'evidence-preflight-outcome');
const bundlePicker = byElementId(evidenceView, 'evidence-delivery-target');
const profilePicker = byElementId(evidenceView, 'evidence-delivery-profile');
if (!receiptButton || !receiptBox) throw new Error('证据系统没有交付收据的入口或读回框');
if (receiptButton.disabled || preflightButton.disabled)
  throw new Error('有交付登记时两个读回按钮都不得是禁用的');
if (receiptBox.textContent.includes('PARTIAL'))
  throw new Error('收据结论在没有点击之前就出现在屏幕上');
bundlePicker.value = EVIDENCE_BUNDLE.id;
profilePicker.value = 'print';
receiptButton.onclick();
const receiptRequests = shell.pending.splice(0, shell.pending.length);
if (receiptRequests.length !== 1)
  throw new Error(`一次收据点击发出了 ${receiptRequests.length} 个请求，应为 1 个`);
if (receiptRequests[0].path
  !== `/api/projects/p1/bundles/${EVIDENCE_BUNDLE.id}/versions/${EVIDENCE_VERSION_ID}/receipt`)
  throw new Error(`收据打到了 ${receiptRequests[0].path} —— 必须是所选版本自己的路由`);
receiptRequests[0].resolve(response(RECEIPT_READBACK));
await flush();
const receiptText = receiptBox.textContent;
for (const must of ['PARTIAL', 'native.psd', 'preview.png', 'sha256:' + 'c'.repeat(64),
                    'req-rights-review', 'NOT_RUN', '无宿主读回记录',
                    `回滚参照：${RECEIPT_READBACK.receipt.deliverables[0].rollback.backup_ref}`])
  if (!receiptText.includes(must))
    throw new Error(`交付收据读回缺少 ${must}：${receiptText.slice(0, 220)}`);
// The rollback column is the new fact, and it has to arrive as the service's words rather than
// as a paraphrase: each proof's own state, its own reason, and the emitter's caveat sentences.
for (const must of ['RESOLVED', 'REF_UNPARSED', 'PARTLY_UNRESOLVED', '版本 v4', '未解析出版本号',
                    'is recorded ACTIVE for this project',
                    'not in the asset:<id>/version:<id> form',
                    'no restore was performed', 'the source version is still recorded'])
  if (!receiptText.includes(must))
    throw new Error(`回滚核对列缺少 ${must}：${receiptText.slice(0, 260)}`);
if (receiptText.includes('全部可兑现') || receiptText.includes('回滚成功'))
  throw new Error('一个 RESOLVED 不能被页面说成全部可兑现或已回滚');
if (receiptText.includes('不在响应公布的词表内'))
  throw new Error('主夹具里每个词都在响应自己公布的词表内，不得被说成词表外');
if (receiptText.includes('该状态的释义未随响应给出'))
  throw new Error('响应给了 state_meaning，页面不得说释义缺失');
if (receiptText.includes('轴值未读回'))
  throw new Error('文档给出了 axes.delivery，页面不得说轴值未读回');
if (receiptText.includes('回滚参照未读回'))
  throw new Error('响应给了 rollback_proofs，页面不得说未读回');
const receiptMarked = collectMarked(receiptBox);
for (const word of ['PARTIAL', 'NOT_RUN', 'RESOLVED', 'REF_UNPARSED'])
  if (!receiptMarked.includes(word))
    throw new Error(`收据状态词 ${word} 必须带 lang="en"：${receiptMarked.join('/')}`);


// (c2) The rollback half has five ways to have nothing to show, and they are five different
// sentences. Re-clicking the same entry with a variant payload is the only way to prove a branch
// renders: the strings exist in the source either way, and an unrendered one has never been
// checked against the fact it is supposed to name.
async function renderReceiptVariant(payload, label) {
  receiptButton.onclick();
  const reads = shell.pending.splice(0, shell.pending.length);
  if (reads.length !== 1)
    throw new Error(`${label} 发出了 ${reads.length} 个请求，应为 1 个`);
  reads[0].resolve(response(payload));
  await flush();
  return receiptBox.textContent;
}

const proofless = { ...RECEIPT_READBACK };
delete proofless.rollback_proofs;
const prooflessText = await renderReceiptVariant(proofless, '缺 rollback_proofs');
if (!prooflessText.includes('回滚参照未读回'))
  throw new Error(`响应没给 rollback_proofs，页面必须说未读回：${prooflessText.slice(0, 240)}`);
if (!prooflessText.includes('PARTIAL'))
  throw new Error('回滚半边缺字段，不该把收据文档本身也一并抹掉');

const nothingText = await renderReceiptVariant(
  { ...RECEIPT_READBACK, rollback_proofs: [], rollback_state: 'NOTHING_TO_CHECK' },
  'NOTHING_TO_CHECK');
if (!nothingText.includes('回滚核对未做') || !nothingText.includes('没有交付物条目'))
  throw new Error(`NOTHING_TO_CHECK 要说成没有条目可核对：${nothingText.slice(0, 240)}`);
if (nothingText.includes('无法查询'))
  throw new Error('台账查得动、只是没有条目，不得说成无法查询');

// The service really does answer this way: when the ledger query raises during the read, _load
// reports LEDGER_UNREADABLE with no proofs. It is a failure to look, not a verdict on the sources.
const unreadableText = await renderReceiptVariant(
  { ...RECEIPT_READBACK, rollback_proofs: [], rollback_state: 'LEDGER_UNREADABLE' },
  'LEDGER_UNREADABLE');
if (!unreadableText.includes('LEDGER_UNREADABLE') || !unreadableText.includes('无法查询'))
  throw new Error(`LEDGER_UNREADABLE 要说成没有查过：${unreadableText.slice(0, 240)}`);
if (unreadableText.includes('没有交付物条目'))
  throw new Error('台账查不动的读回不得被说成这份收据没有条目');

// A newer emitter inventing a state word is the case the published vocabulary exists for. The
// page may not paint it the way it paints a word it simply has no colour for.
const unlistedText = await renderReceiptVariant({
  ...RECEIPT_READBACK,
  rollback_proofs: RECEIPT_READBACK.rollback_proofs.map((proof, index) =>
    index === 0 ? { ...proof, state: 'SOLVED_BY_A_NEWER_EMITTER' } : proof),
}, '词表外的状态词');
if (!unlistedText.includes('SOLVED_BY_A_NEWER_EMITTER')
  || !unlistedText.includes('不在响应公布的词表内'))
  throw new Error(`响应词表里没有的词必须被点名，不能悄悄按中性色处理：${unlistedText.slice(0, 240)}`);

const caveatText = await renderReceiptVariant(
  { ...RECEIPT_READBACK, does_not_prove: [] }, '空 does_not_prove');
if (!caveatText.includes('本读回未给出 does_not_prove'))
  throw new Error(`does_not_prove 为空必须点名，不能静默少一栏：${caveatText.slice(0, 200)}`);

const meaningText = await renderReceiptVariant(
  { ...RECEIPT_READBACK, state_meaning: {} }, '空 state_meaning');
if (!meaningText.includes('该状态的释义未随响应给出'))
  throw new Error(`响应没带释义时页面必须说出来：${meaningText.slice(0, 200)}`);
if (!meaningText.includes('REF_UNPARSED'))
  throw new Error('缺释义只影响释义列，条目本身仍须按服务端的状态词渲染');

// (d) The two refusals are two different sentences. 404 says nothing was recorded;
// 409 says these bytes will not be certified -- and neither may keep the document that
// the previous read put on the screen.
receiptButton.onclick();
const notFoundRead = shell.pending.splice(0, shell.pending.length);
if (notFoundRead.length !== 1) throw new Error(`第二次收据点击发出了 ${notFoundRead.length} 个请求`);
notFoundRead[0].resolve(response({ error: 'DELIVERY_RECEIPT_NOT_FOUND' }, false));
await flush();
const missingText = receiptBox.textContent;
if (!missingText.includes('DELIVERY_RECEIPT_NOT_FOUND') || !missingText.includes('没有收据不等于交付失败'))
  throw new Error(`无收据的 404 要说清是哪一件事：${missingText.slice(0, 200)}`);
if (missingText.includes('PARTIAL') || missingText.includes('native.psd'))
  throw new Error('拒绝后上一份收据文档仍留在屏上');
receiptButton.onclick();
const unverifiedRead = shell.pending.splice(0, shell.pending.length);
unverifiedRead[0].resolve(response({ error: 'DELIVERY_RECEIPT_UNVERIFIED' }, false));
await flush();
const refusedText = receiptBox.textContent;
if (!refusedText.includes('DELIVERY_RECEIPT_UNVERIFIED') || !refusedText.includes('拒绝出证'))
  throw new Error(`拒绝对字节出证必须说成另一件事：${refusedText.slice(0, 200)}`);
if (refusedText.includes('DELIVERY_RECEIPT_NOT_FOUND'))
  throw new Error('409 的框里还挂着 404 的说法，两种状态混成了一条');

// (e) The preflight lands in its own box, and does not touch the receipt's.
preflightButton.onclick();
const preflightReads = shell.pending.splice(0, shell.pending.length);
if (preflightReads.length !== 1)
  throw new Error(`一次预检点击发出了 ${preflightReads.length} 个请求，应为 1 个`);
if (preflightReads[0].path
  !== `/api/projects/p1/bundles/${EVIDENCE_BUNDLE.id}/preflight?profile=print`)
  throw new Error(`证据页预检打到了 ${preflightReads[0].path}`);
preflightReads[0].resolve(response(PREFLIGHT_READBACK));
await flush();
if (!preflightBox.textContent.includes('INCOMPLETE') || !preflightBox.textContent.includes('missing-links'))
  throw new Error('预检读回没有进入证据页自己的框');
if (!receiptBox.textContent.includes('拒绝出证'))
  throw new Error('预检把收据框自己的结论冲掉了 —— 两个框必须互不覆盖');

// (f) A delivery list that named a bundle but not its ACTIVE version is refused without
// a request: the receipt cannot be pointed at a version from memory.
evidenceSelect.onchange();
const rebuilt = shell.pending.splice(0, shell.pending.length);
answerEvidence(rebuilt, JURY_READBACK, { bundles: [{ ...EVIDENCE_BUNDLE, version_id: undefined }] },
               RIGHTS_READBACK);
await flush();
const blindBox = byElementId(shell.elements.get('route-view'), 'evidence-receipt-outcome');
const blindButton = byElementId(shell.elements.get('route-view'), 'evidence-receipt-run');
const blindPicker = byElementId(shell.elements.get('route-view'), 'evidence-delivery-target');
blindPicker.value = EVIDENCE_BUNDLE.id;
blindButton.onclick();
const strayReceipt = shell.pending.splice(0, shell.pending.length);
if (strayReceipt.length)
  throw new Error(`版本 id 未读回时仍然发出了 ${strayReceipt.map((r) => r.path).join(' ')} —— 收据不能指向凭记忆的版本`);
if (!blindBox.textContent.includes('未读回收据'))
  throw new Error(`版本 id 缺失时必须说明未读回：${blindBox.textContent.slice(0, 160)}`);
console.log('ok: ⑦ 证据系统读回裁决/预检/收据：缺字段说未读回不当作空列表、裁决与 lang="en" 上屏、一次点击一个收据请求、404 与 409 两种拒绝各说各话、两框互不覆盖、版本未读回时不发请求');

// ⑦b 证据链完整性读回. The projection publishes two verdicts per receipt and the page may not
// collapse them into one word, invent a count the service did not send, or let a refusal render as
// "no evidence problems". Each branch is proven by re-clicking with a variant payload: the strings
// exist in the source either way, and a branch that never rendered has never been checked against
// the fact it is supposed to name.
const projectionButton = byElementId(evidenceView, 'evidence-projection-run');
const projectionBox = byElementId(evidenceView, 'evidence-projection-outcome');
if (!projectionButton || !projectionBox)
  throw new Error('证据系统没有证据链完整性的入口或读回框 —— ⑦b 找不到面');
if (evidencePaths.includes('/api/evidence-projection'))
  throw new Error('构建证据页时就读了证据链状态；它要对当前检出逐条复算，必须是一次明确请求');
if (projectionBox.textContent.includes('VERIFIED'))
  throw new Error('结论在没有点击之前就出现在屏幕上');
if (projectionButton.disabled)
  throw new Error('证据链读回不依赖任何所选交付包，按钮不得是禁用的');

const PROJECTION_SUBJECT = 'c'.repeat(40);
const PROJECTION_RECEIPTS = [
  { id: 'r-intact-and-current', taskIds: ['DL-R5-003'], kind: 'local_test', outcome: 'PASS',
    subjectSha: 'a'.repeat(40), binding: 'COMMIT', observedAt: '2026-10-08T06:05:33Z',
    verified: true, current: true, integrityReasons: [], currencyReasons: [] },
  { id: 'r-intact-but-moved', taskIds: ['DL-R5-001'], kind: 'local_test', outcome: 'PASS',
    subjectSha: 'b'.repeat(40), binding: 'COMMIT', observedAt: '2026-10-08T05:06:06Z',
    verified: true, current: false, integrityReasons: [],
    currencyReasons: ['MOVED_SINCE_BOUND_COMMIT:src/design_lab/governance/reporting.py'] },
  { id: 'r-not-reproducible', taskIds: ['DL-R5-004'], kind: 'structural', outcome: 'PARTIAL',
    subjectSha: 'd'.repeat(40), binding: 'COMMIT', observedAt: '2026-09-28T14:00:00Z',
    verified: false, current: false,
    integrityReasons: ['ARTIFACT_IS_NOT_VERSIONED:src/design_lab/readiness/__pycache__/'
      + 'host_matrix.cpython-313.pyc'],
    currencyReasons: [] },
];
const PROJECTION_PAYLOAD = {
  schemaVersion: 'design-lab/evidence-projection/v1',
  subjectSha: PROJECTION_SUBJECT,
  ledger: 'design-lab/config/task-ledger-r3.json',
  totals: { records: PROJECTION_RECEIPTS.length, outcomePass: 2, verified: 2, unverified: 1,
            current: 1 },
  reasonCounts: { integrity: { OUTCOME_NOT_PASS: 1, ARTIFACT_IS_NOT_VERSIONED: 1 },
                  currency: { MOVED_SINCE_BOUND_COMMIT: 1, STALE_SUBJECT_SHA: 8 } },
  receipts: PROJECTION_RECEIPTS,
  taskCounts: { PARTIAL: 28 },
};

async function renderProjectionVariant(payload, label, ok = true) {
  projectionButton.onclick();
  const reads = shell.pending.splice(0, shell.pending.length);
  if (reads.length !== 1)
    throw new Error(`${label} 发出了 ${reads.length} 个请求，应为 1 个`);
  if (reads[0].path !== '/api/evidence-projection')
    throw new Error(`${label} 打到了 ${reads[0].path}，必须是证据链投影自己的路由`);
  reads[0].resolve(response(payload, ok));
  await flush();
  return projectionBox.textContent;
}

const projectionText = await renderProjectionVariant(PROJECTION_PAYLOAD, '完整读回');
// The KPI numbers are read off the cards' own data-count, not out of the text: '3' and '条收据' are
// two nodes, and a substring test on the concatenation would pass even if the value had been glued
// to the wrong label.
function kpiPairs(node, out = []) {
  const kids = node?.children ?? [];
  for (let index = 0; index < kids.length; index += 1) {
    const kid = kids[index];
    if (kid?.dataset?.count !== undefined)
      out.push([kid.dataset.count, kids[index + 1]?.textContent ?? '']);
    kpiPairs(kid, out);
  }
  return out;
}
const projectionKpis = kpiPairs(projectionBox);
const wantedKpis = [['3', '条收据'], ['2', '字节可复现'], ['1', '不可复现'], ['1', '仍适用当前检出']];
for (const [value, label] of wantedKpis) {
  if (!projectionKpis.some((pair) => pair[0] === value && pair[1] === label))
    throw new Error(`证据链 KPI 缺少 ${value} ${label}，实际读到 ${JSON.stringify(projectionKpis)}`);
}
for (const must of ['OUTCOME_NOT_PASS', 'ARTIFACT_IS_NOT_VERSIONED', 'MOVED_SINCE_BOUND_COMMIT',
                    'STALE_SUBJECT_SHA', 'r-intact-and-current', 'r-intact-but-moved',
                    'r-not-reproducible', 'design-lab/config/task-ledger-r3.json',
                    PROJECTION_SUBJECT.slice(0, 12)])
  if (!projectionText.includes(must))
    throw new Error(`证据链读回缺少 ${must}：${projectionText.slice(0, 260)}`);
// The two booleans are two questions. An intact receipt about moved bytes is honest history and is
// not evidence about this checkout, so it must not wear the same word as one that is still current.
for (const word of ['VERIFIED CURRENT', 'VERIFIED NOT CURRENT', 'NOT VERIFIED'])
  if (!projectionText.includes(word))
    throw new Error(`三种判定必须各说各话，屏幕上没有 ${word}：${projectionText.slice(0, 240)}`);
const projectionMarked = collectMarked(projectionBox);
for (const word of ['VERIFIED CURRENT', 'VERIFIED NOT CURRENT', 'NOT VERIFIED',
                    'OUTCOME_NOT_PASS', 'ARTIFACT_IS_NOT_VERSIONED', 'MOVED_SINCE_BOUND_COMMIT'])
  if (!projectionMarked.includes(word))
    throw new Error(`证据链词表中的 ${word} 必须带 lang="en"：${projectionMarked.join('/')}`);
if (projectionText.includes('全部已验证') || projectionText.includes('没有问题'))
  throw new Error('一页里只要有 NOT VERIFIED，页面不得说全部已验证或没有问题');

// A readback that caps its list must say it capped it: 12 shown out of N is not "there are 12".
const overflow = {
  ...PROJECTION_PAYLOAD,
  receipts: Array.from({ length: 13 }, (_unused, index) => ({
    ...PROJECTION_RECEIPTS[0], id: `r-${index}` })),
  totals: { records: 13, outcomePass: 13, verified: 13, unverified: 0, current: 13 },
};
const overflowText = await renderProjectionVariant(overflow, '超出展开上限');
if (!overflowText.includes('其余 1 条未逐条列出'))
  throw new Error(`列表被截断时必须说明，不得让 12 条读成全部：${overflowText.slice(0, 200)}`);
const overflowKpis = kpiPairs(projectionBox);
if (!overflowKpis.some((pair) => pair[0] === '13' && pair[1] === '条收据'))
  throw new Error(`计数要覆盖全部记录，与展开条数无关，实际读到 ${JSON.stringify(overflowKpis)}`);

// Every way this read can come back wrong is a different sentence, and none of them may keep the
// numbers from the previous read on screen.
const absentTotals = { ...PROJECTION_PAYLOAD };
delete absentTotals.totals;
const absentTotalsText = await renderProjectionVariant(absentTotals, '缺 totals');
if (!absentTotalsText.includes('未读回'))
  throw new Error(`响应没有 totals，页面必须说未读回：${absentTotalsText.slice(0, 200)}`);
if (kpiPairs(projectionBox).length || absentTotalsText.includes('VERIFIED CURRENT'))
  throw new Error('缺计数时不得沿用上一读的数，也不得画任何判定');

const absentReceipts = { ...PROJECTION_PAYLOAD };
delete absentReceipts.receipts;
const absentReceiptsText = await renderProjectionVariant(absentReceipts, '缺 receipts');
if (!absentReceiptsText.includes('未读回') || !absentReceiptsText.includes('receipts'))
  throw new Error(`响应没有 receipts 集合，页面要说未读回并点名缺什么：${
    absentReceiptsText.slice(0, 200)}`);

// A named refusal is the route saying it would not guess. The card has to carry the service's own
// code, and must not be softened into an empty ledger.
const projectionRefusedText = await renderProjectionVariant({ error: 'EVIDENCE_LEDGER_ABSENT' }, '服务端拒绝', false);
if (!projectionRefusedText.includes('EVIDENCE_LEDGER_ABSENT') || !projectionRefusedText.includes('未读回'))
  throw new Error(`拒绝要带上服务端的理由码：${projectionRefusedText.slice(0, 200)}`);
if (projectionRefusedText.includes('账本没有任何收据') || projectionRefusedText.includes('0 条收据'))
  throw new Error('一次拒绝不得被显示成"账本是空的"或 0 条记录');

// 200 with an error field in the body is a third thing again: the request completed and the
// readback still declined to carry counts.
const inlineRefusalText = await renderProjectionVariant(
  { error: 'EVIDENCE_CONTRACT_VIOLATION' }, '响应体内带拒绝码');
if (!inlineRefusalText.includes('EVIDENCE_CONTRACT_VIOLATION')
  || !inlineRefusalText.includes('未读回'))
  throw new Error(`200 但带 error 的响应要同时给出拒绝码与未读回：${inlineRefusalText.slice(0, 240)}`);
if (kpiPairs(projectionBox).length)
  throw new Error('一个带拒绝码的响应不得画出任何 KPI 数字');

// The view's own caption said no evidence read has a route, two rows above a card that reads one.
// Boundary text the page itself contradicts is how a stale limitation keeps getting quoted as fact.
const evidenceText = evidenceView.textContent;
if (!evidenceText.includes('/api/evidence-projection'))
  throw new Error('证据链面板没有说明它读的是哪条路由');
if (/E0[–-]E5 证据记录仍无服务路由/.test(evidenceText))
  throw new Error('路由已上线，caption 还在照抄旧的"无服务路由"，且没有说明上方卡片读的是什么');
if (!evidenceText.includes('逐条证据记录'))
  throw new Error('边界要保留：E0–E5 的逐条记录仍然没有路由，不能因为投影上线就被忘掉');

console.log('ok: ⑦b 证据链完整性：构建页面零读回、一次点击一个请求、三个判定各说各话且带 lang="en"、'
  + '理由分布来自服务端、截断要说明、缺 totals/receipts 说未读回不画数、拒绝带码且不冒充空账本、边界文案与已上线路由不矛盾');

// ⑧ 权利决定 · Human RIGHTS. The rights gate got a real route (GET/POST
// /api/projects/<32-hex>/rights, src/design_lab/rights_review.py) and now has a real
// surface: a form on 预检 / QA where a human signs, and a read-only column on 证据系统.
// Behaviour is what text cannot prove, so this block drives it: one click files exactly one
// decision to the POST route with the contract's own field set, no request leaves before
// the project and the supersession target have been read back, a refusal replaces the
// previous verdict instead of leaving a stale green, and every word on screen is the
// service's own (lang="en", never translated). The 未读回 half is the shape this repo has
// been burned on: a count the response never carried must not be drawn as 0/0, and
// NOT_REVIEWED must not read as "somebody owes an answer".
const RIGHTS_PROJECTS = projectsEnvelope([projectRow('p1', 'Alpha'), projectRow('p2', 'Beta')]);
let rightsFixture = RIGHTS_READBACK;
const rightsAnswer = (path) => (path === '/api/projects' ? RIGHTS_PROJECTS
  : path.includes('/rights') ? rightsFixture : JURY_READBACK);

// Drain every read a view chains, answering by path. 预检 / QA reads /projects twice (the
// jury panel and the rights panel each ask for themselves) and then the two ledgers, so a
// single splice would leave the second half of the page forever loading.
async function drainReads() {
  const seen = [];
  for (let round = 0; round < 8; round += 1) {
    // Settle first, then take what arrived: a read created only as the continuation of the
    // one resolved in the previous round (the rights form's reload-after-POST) is not in
    // the queue yet at the moment of the click.
    await flush();
    const fresh = shell.pending.splice(0, shell.pending.length);
    if (!fresh.length) break;
    seen.push(...fresh);
    for (const request of fresh) request.resolve(response(rightsAnswer(request.path)));
  }
  await flush();
  return seen;
}

shell.window.location.hash = '#/preflight';
shell.dispatchHashchange();
const qaReads = await drainReads();
const preflightView = shell.elements.get('route-view');
for (const expected of ['/api/projects', '/api/projects/p1/jury', '/api/projects/p1/rights'])
  if (!qaReads.some((request) => request.path === expected))
    throw new Error(`预检 / QA 没有读回 ${expected}；实际读到 ${
      qaReads.map((request) => request.path).join(' ')}`);
const rightsOutcome = byElementId(preflightView, 'rights-review-outcome');
const scopeField = byElementId(preflightView, 'rights-use-scope');
const signerField = byElementId(preflightView, 'rights-decided-by');
const supersedesField = byElementId(preflightView, 'rights-supersedes');
const rightsButton = byElementId(preflightView, 'rights-submit');
if (!rightsOutcome || !scopeField || !signerField || !supersedesField || !rightsButton)
  throw new Error('权利表单的某个入口在页面上不可定位 —— ⑧ 找不到提交面');
// The decision words offered are the readback's own `decision_vocabulary`, and nothing
// else. A radio the contract does not allow would be an offer nobody can honour; a
// pre-checked one would file a status nobody chose.
const markedWords = collectMarked(preflightView);
for (const word of ['APPROVED', 'DENIED', 'PENDING_REVIEW', 'BLOCKED_BY_LICENSE']) {
  const radio = byElementId(preflightView, `rights-decision-${word}`);
  if (!radio) throw new Error(`决定词 ${word} 没有出现在表单里，而它来自读回的 decision_vocabulary`);
  if (radio.value !== word)
    throw new Error(`决定词单选框的 value 是 ${radio.value}，不是合同的 ${word}`);
  if (!markedWords.includes(word))
    throw new Error(`决定词 ${word} 必须带 lang="en"（服务词汇，不翻译）`);
}
if (findIn(preflightView, (node) => node.attributes && node.attributes.get('name') === 'rights-decision'
  && node.checked === true))
  throw new Error('权利表单预先选中了一个决定词：没有人选择的状态不能是默认值');
const builtInPosts = qaReads.filter((request) => request.init && request.init.method === 'POST');
if (builtInPosts.length)
  throw new Error(`构建页面时发出了 POST：${builtInPosts.map((r) => r.path).join(' ')} —— `
    + '一条权利决定只能由点击提交，不能由打开页面替人签署');

// (a) Local refusals send nothing. An empty use scope and a supersession aimed at another
// scope are both doomed writes; refusing them here keeps the append-only ledger clean.
rightsButton.onclick();
if (shell.pending.length)
  throw new Error(`使用范围未填写时仍发出了 ${shell.pending.map((r) => r.path).join(' ')} —— `
    + '决定必须落在一个范围上');
if (!rightsOutcome.textContent.includes('未提交') || !rightsOutcome.textContent.includes('使用范围'))
  throw new Error(`缺使用范围时必须说明为什么没提交：${rightsOutcome.textContent.slice(0, 160)}`);
scopeField.value = RIGHTS_SCOPE_A;
signerField.value = 'dtalex66';
byElementId(preflightView, `rights-decision-${'DENIED'}`).checked = true;
supersedesField.value = RIGHTS_DECISION_B;   // decided RIGHTS_SCOPE_B, not SCOPE_A
rightsButton.onclick();
if (shell.pending.length)
  throw new Error(`替代目标与使用范围不同却仍发出了 ${shell.pending.map((r) => r.path).join(' ')} —— `
    + '跨范围替代会让被取代的决定无人计数，服务端也必然拒绝');
if (!rightsOutcome.textContent.includes('不是同一个使用范围'))
  throw new Error(`跨范围替代被拒时页面没有说明原因：${rightsOutcome.textContent.slice(0, 200)}`);
supersedesField.value = '';

// (b) One click, one POST, to the rights route with the contract's own field set.
const posted = { decision: 'DENIED', use_scope: RIGHTS_SCOPE_A };
rightsButton.onclick();
const submitted = shell.pending.splice(0, shell.pending.length);
if (submitted.length !== 1)
  throw new Error(`一次点击发出了 ${submitted.length} 个请求，应为 1 个`);
if (submitted[0].path !== '/api/projects/p1/rights')
  throw new Error(`提交打到了 ${submitted[0].path}，必须是所选项目的 rights 路由`);
if (!submitted[0].init || submitted[0].init.method !== 'POST')
  throw new Error('提交的 HTTP 方法不是 POST —— 一条权利决定不能被写成一次读取');
const RIGHT_FIELDS = ['schemaVersion', 'use_scope', 'decision', 'decided_by', 'decided_at'];
const sentBody = JSON.parse(submitted[0].init.body);
for (const field of RIGHT_FIELDS)
  if (!(field in sentBody))
    throw new Error(`提交缺少合同必备字段 ${field}：服务端会按契约拒绝，页面不该先漏掉它`);
if (sentBody.use_scope !== posted.use_scope || sentBody.decision !== posted.decision)
  throw new Error(`提交的 scope/decision 与所选不符：${JSON.stringify(sentBody)}`);
if (sentBody.schemaVersion !== 'design-lab/rights-decision/v1')
  throw new Error(`提交的 schemaVersion 是 ${sentBody.schemaVersion}，必须是契约绑定的版本`);
if ('supersedes' in sentBody || 'juror' in sentBody || 'actor_kind' in sentBody)
  throw new Error('提交把替代链接或评审人字段塞进了文档：契约关闭属性，supersedes 是查询参数');
if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(sentBody.decided_at))
  throw new Error(`decided_at ${sentBody.decided_at} 不是服务接受的 RFC3339 UTC 形状`);
const firstDecisionId = sentBody.decision_id;

// (c) Success reads the ledger back from the service. The outcome line lives outside the
// re-rendered panel on purpose: written inside it, the reload would detach the very node
// the message was put in and the operator would see nothing after a filed decision.
submitted[0].resolve(response(sentBody));
await drainReads();
if (!rightsOutcome.textContent.includes('已提交'))
  throw new Error(`提交成功后没有说明结论来自服务端读回：${rightsOutcome.textContent.slice(0, 160)}`);
if (!rightsOutcome.textContent.includes('上方读回来自服务端'))
  throw new Error('提交成功的说法必须指向服务端读回，而不是页面记住的输入');

// (d) The refusal replaces the verdict: the same box, no stale green sentence standing next
// to a write the service rejected, and the refusal reason in the service's own words.
// The success reload rebuilt the panel, so the fields are looked up in the NEW form and the
// decision word has to be chosen again -- nothing carries over except the outcome line,
// which lives outside the re-rendered body.
const previousView = shell.elements.get('route-view');
const previousScope = byElementId(previousView, 'rights-use-scope');
const previousSigner = byElementId(previousView, 'rights-decided-by');
const previousButton = byElementId(previousView, 'rights-submit');
const previousRadio = byElementId(previousView, 'rights-decision-DENIED');
if (!previousScope || !previousButton || !previousRadio || !previousSigner)
  throw new Error('提交成功读回后表单没有重新渲染 —— 一条决定不能留在已失效的面板上');
previousScope.value = 'third-party-model-weights';
previousSigner.value = 'dtalex66';
previousRadio.checked = true;
previousButton.onclick();
const refusedPosts = shell.pending.splice(0, shell.pending.length);
if (refusedPosts.length !== 1) throw new Error(`第二次点击发出了 ${refusedPosts.length} 个请求，应为 1 个`);
if (JSON.parse(refusedPosts[0].init.body).decision_id === firstDecisionId)
  throw new Error('改了内容的提交沿用了上一条的 decision_id：一条新决定必须是新的一行，'
    + '而服务端会把这个 id 当撞车拒绝');
refusedPosts[0].resolve(response({ error: 'RIGHTS_NOT_HUMAN',
  detail: 'an agent-signed rights decision is refused: `decided_by` \'review-agent\' names automation' },
  false));
await flush();
const afterRefusal = rightsOutcome.textContent;
if (!afterRefusal.includes('RIGHTS_NOT_HUMAN') || !afterRefusal.includes('names automation'))
  throw new Error(`权利提交被拒时页面没有带着拒绝码与理由上屏：${afterRefusal.slice(0, 200)}`);
if (afterRefusal.includes('已提交'))
  throw new Error('拒绝后上一条"已提交"仍留在屏上，等于把被拒的写入算成了一条决定');
if (!afterRefusal.includes('没有写入任何决定'))
  throw new Error('拒绝的说法必须说明服务端什么都没写，否则读者会以为上方读回是这次的结果');

// (e) The read-only column on 证据系统: what stands per scope, who decided, the clearance
// with its denominator, the two limit reports, and the service's own does-not-prove text.
shell.window.location.hash = '#/evidence';
shell.dispatchHashchange();
const evidenceRightsRequests = shell.pending.splice(0, shell.pending.length);
if (evidenceRightsRequests.length !== 1)
  throw new Error(`#/evidence 打开时发出了 ${evidenceRightsRequests.length} 个请求，应只有项目台账`);
evidenceRightsRequests[0].resolve(response(RIGHTS_PROJECTS));
await flush();
const rightsEvidenceView = shell.elements.get('route-view');
const rightsEvidenceSelect = byElementId(rightsEvidenceView, '证据系统-project');
rightsEvidenceSelect.value = 'p1';
rightsEvidenceSelect.onchange();
const evidenceReads = shell.pending.splice(0, shell.pending.length);
answerEvidence(evidenceReads, JURY_READBACK, { bundles: [EVIDENCE_BUNDLE] }, RIGHTS_READBACK);
await flush();
const rightsText = rightsEvidenceView.textContent;
for (const must of [
  '权利决定读回 · Human RIGHTS',
  RIGHTS_SCOPE_A, RIGHTS_SCOPE_B,
  `决定 ${RIGHTS_DECISION_A}`, '决定人 dtalex66',
  '当前批准 1/2', '决定总数 2',
  '本读回不证明',
  'CLEARED covers the use scopes this project has actually filed a decision for',
  // 两条限制必须逐条上屏，不能被折叠成一个数量。
  'a rights decision clears none of the quality, production or release gates',
  // scope_conflicts is empty here, so the conflict sentence must not appear at all;
  // name_checked_only is not, so its limit has to be stated.
  '仅按名字核查的范围 2 个',
  '已提交但未计入清算的范围：client-photo-01（DENIED）',
])
  if (!rightsText.includes(must))
    throw new Error(`权利读回列缺少 ${must}：${rightsText.slice(0, 260)}`);
if (rightsText.includes('范围冲突'))
  throw new Error('scope_conflicts 为空时页面不得声称存在范围冲突');
if (rightsText.includes('尚无人签署的权利决定'))
  throw new Error('有决定可读回时页面仍说无人签署');
if (rightsText.includes('未读回：响应缺少'))
  throw new Error('形状完整的权利读回不得出现形状告警');
const rightsMarked = collectMarked(rightsEvidenceView);
for (const word of ['NOT_REVIEWED', 'APPROVED', 'DENIED'])
  if (!rightsMarked.includes(word))
    throw new Error(`权利状态词 ${word} 必须带 lang="en"（服务词汇，不翻译）：${rightsMarked.join('/')}`);
// A chip colour is a claim too, and it is the one a reader parses before the words.
// `.tag.ok` is the affirmative pill the stylesheet draws green, so NOT_REVIEWED and DENIED
// may never wear it, and a scope the façade counts as approved must.
function tagsPainted(node, out = []) {
  if (node?.className && /^tag\b/.test(node.className)) out.push([node.className, node.textContent]);
  for (const child of (node?.children ?? [])) tagsPainted(child, out);
  return out;
}
const painted = tagsPainted(rightsEvidenceView);
const green = painted.filter(([klass]) => /\bok\b/.test(klass)).map(([, text]) => text);
const neutral = painted.filter(([klass]) => /neutral/.test(klass)).map(([, text]) => text);
if (green.includes('NOT_REVIEWED'))
  throw new Error('NOT_REVIEWED 被涂成了肯定色：一道没被清算的门不能看起来像通过了');
if (green.includes('DENIED'))
  throw new Error('DENIED 被涂成了肯定色：façade 列在未批准范围里的决定不能是绿的');
if (!green.includes('APPROVED'))
  throw new Error(`由 unapproved_scopes 判定为批准的范围必须带肯定色：实际绿标 ${green.join('/')}`);
if (painted.some(([klass, text]) => text === 'DENIED' && !/\bbad\b/.test(klass)))
  throw new Error('DENIED 必须用拒绝色，而不是一个中性标签');
if (neutral.length)
  throw new Error(`决定词读回完整时不应出现中性标签：${neutral.join('/')}`);

// (f) A count the response never carried is not a zero. 0/0 would read as "nothing needed
// clearing" -- the very vacuity rights_review.py refuses to compute as CLEARED.
rightsFixture = { ...RIGHTS_READBACK,
  approved_scope_count: undefined, filed_scope_count: undefined, decision_count: undefined };
rightsEvidenceSelect.onchange();
const bareRights = shell.pending.splice(0, shell.pending.length);
answerEvidence(bareRights, JURY_READBACK, { bundles: [EVIDENCE_BUNDLE] }, rightsFixture);
await flush();
const bareRightsText = rightsEvidenceView.textContent;
if (!bareRightsText.includes('当前批准 未读回'))
  throw new Error(`缺少分母时应说未读回：${bareRightsText.slice(0, 240)}`);
if (bareRightsText.includes('0/0'))
  throw new Error('页面把没读回的分数画成了 0/0');
if (!bareRightsText.includes('决定总数 未读回'))
  throw new Error('缺少决定总数时不得显示数字');

// (g) NOT_REVIEWED with nothing filed is "never asked", not "waiting for an answer".
rightsFixture = { ...RIGHTS_READBACK, current_decisions: {}, unapproved_scopes: [],
  ever_filed_scopes: [], scope_conflicts: [], name_checked_only: [],
  filed_scope_count: 0, approved_scope_count: 0,
  decision_count: 0, decision_states: { APPROVED: 0, DENIED: 0, PENDING_REVIEW: 0,
                                        BLOCKED_BY_LICENSE: 0 } };
rightsEvidenceSelect.onchange();
const nothingFiled = shell.pending.splice(0, shell.pending.length);
answerEvidence(nothingFiled, JURY_READBACK, { bundles: [EVIDENCE_BUNDLE] }, rightsFixture);
await flush();
const filedText = rightsEvidenceView.textContent;
if (!filedText.includes('尚无人签署的权利决定'))
  throw new Error('服务真的答了空台账时必须照实说尚无');
if (!filedText.includes('没有被问过'))
  throw new Error('未被提交过的权利门必须说"没有被问过"，而不是让 NOT_REVIEWED 读成有人在等答复');
if (/等待(审查|答复)|正在审查/.test(filedText.replace(/不是有人在等答复|不是"正在等待审查"/g, '')))
  throw new Error('空台账的读回把 NOT_REVIEWED 说成了正在等待审查');
if (filedText.includes('仅按名字核查'))
  throw new Error('name_checked_only 为空时页面不得声称存在仅按名字核查的行');
if (!filedText.includes('PENDING_REVIEW 0'))
  throw new Error('状态计数必须原样读回：没有人类提交的 PENDING_REVIEW 应显示 0，而不是缺席');

// (h) A fork in the chain is reported, not silently tie-broken.
rightsFixture = { ...RIGHTS_READBACK,
  scope_conflicts: [{ use_scope: RIGHTS_SCOPE_A, decision_ids: [RIGHTS_DECISION_A, 'rights-c'] }] };
rightsEvidenceSelect.onchange();
const conflicted = shell.pending.splice(0, shell.pending.length);
answerEvidence(conflicted, JURY_READBACK, { bundles: [EVIDENCE_BUNDLE] }, rightsFixture);
await flush();
const conflictText = rightsEvidenceView.textContent;
if (!conflictText.includes('范围冲突 1 项') || !conflictText.includes(RIGHTS_DECISION_A))
  throw new Error(`多条现行决定时必须点名范围与决定 id：${conflictText.slice(0, 240)}`);
if (!conflictText.includes('是不确定的'))
  throw new Error('冲突必须被说成"当前立场不确定"，而不是悄悄选一条显示');

// (i) A superseded scope must not let a clearance quietly cover less than anybody filed.
// `ever_filed_scopes` counts every scope anybody ever filed; `current_decisions` only the
// standing ones. The page states the difference rather than leaving the reader to notice
// the denominator moved.
rightsFixture = { ...RIGHTS_READBACK, ever_filed_scopes: [RIGHTS_SCOPE_A, RIGHTS_SCOPE_B,
  'third-party-model-weights'] };
rightsEvidenceSelect.onchange();
const narrowed = shell.pending.splice(0, shell.pending.length);
answerEvidence(narrowed, JURY_READBACK, { bundles: [EVIDENCE_BUNDLE] }, rightsFixture);
await flush();
const narrowedText = rightsEvidenceView.textContent;
if (!narrowedText.includes('曾提交过的范围 3 个'))
  throw new Error(`曾提交过的范围数必须来自 ever_filed_scopes：${narrowedText.slice(0, 200)}`);
if (!narrowedText.includes('1 个范围已不再出现在现行集合中'))
  throw new Error('被取代的范围离场时页面要说出差额，否则清算看起来覆盖了比实际更多的东西');
if (narrowedText.includes('2 个范围已不再出现'))
  throw new Error('差额的算术错了：3 个曾提交、2 个现行，只能差 1 个');

// (j) A field the response never carried is unread, never an empty list. `current_decisions`
// is a collection the seam must refill, so the column says which field is missing and does
// not claim nobody signed.
rightsFixture = { ...RIGHTS_READBACK, current_decisions: undefined, does_not_prove: undefined };
rightsEvidenceSelect.onchange();
const unreadRights = shell.pending.splice(0, shell.pending.length);
answerEvidence(unreadRights, JURY_READBACK, { bundles: [EVIDENCE_BUNDLE] }, rightsFixture);
await flush();
const unreadRightsText = rightsEvidenceView.textContent;
if (!unreadRightsText.includes('权利决定未读回'))
  throw new Error(`权利字段缺失时页面必须说未读回：${unreadRightsText.slice(0, 240)}`);
if (unreadRightsText.includes('尚无人签署的权利决定'))
  throw new Error('响应没有给出 current_decisions 时，页面不得声称尚无人签署的权利决定');
if (unreadRightsText.includes('视图读回失败'))
  throw new Error('缺少一个集合不得把整页压成读回失败');
if (!/未读回：响应缺少[^\n]*current_decisions/.test(unreadRightsText))
  throw new Error('未读回的说法必须点名缺的是哪个字段');
rightsFixture = RIGHTS_READBACK;
console.log('ok: ⑧ 权利门：决定词来自读回且带 lang="en"、无预选、构建页面零 POST、注定被拒的写不发请求、一次点击一个 POST 带契约字段与查询参数替代、成功后读回来自服务端、拒绝替换上一条已提交、证据列读回每人每范围决定与分母/冲突/仅名字核查/does_not_prove、缺分母说未读回不画 0/0、空台账说"没有被问过"不说等待审查');

// ⑨ 研究洞察 · persisted findings. GET/POST /api/projects/<32-hex>/research became a real
// route, and the slot that used to say "no persisted conclusions route exists" now reads the
// ledger back. The claims worth driving are the ones a static page cannot make: a write leaves
// only on click and carries exactly the closed contract field set (no schemaVersion, because
// this contract declares none), a supersede link travels as a query parameter and not inside the
// document, an identical retry keeps its finding_id so the service can call it a replay while a
// changed document must take a fresh one, and the page never invents a completion word -- the
// façade publishes `research_verdict: null` precisely because "how many findings exist" is not
// "is the research finished". A count the response never carried reads 未读回 rather than 0.
const RESEARCH_PROJECTS = { projects: [{ id: 'p1', name: 'Alpha' }, { id: 'p2', name: 'Beta' }] };
let researchFixture = {
  schemaVersion: 'design-lab/research-readback/v1', project_id: 'p1',
  findings: [
    { finding_id: 'rf-one', claim: '包装线上一半的返工来自色数超限', sourceRefs: ['interview-07'],
      confidence: 'medium' },
    { finding_id: 'rf-two', claim: '模板复用率随交付格式数量下降',
      sourceRefs: ['bench-figma-2026-05', 'telemetry-12'] },
  ],
  current_findings: { 'rf-one': {}, 'rf-two': {} },
  finding_count: 2, current_finding_count: 2, superseded_finding_count: 0,
  sourced_finding_count: 2, unsourced_finding_count: 0, source_ref_total: 3,
  source_ref_field: 'sourceRefs',
  confidence_counts: { high: 0, medium: 1, low: 0, speculative: 0 },
  confidence_vocabulary: ['high', 'medium', 'low', 'speculative'],
  stated_confidence_count: 1, unattributed_findings: ['rf-one', 'rf-two'],
  actor_kinds: { UNDECLARED: 2 }, undeclared_disclaimer: 'HTTP 提交不携带作者类型',
  proves_design_quality: false, is_knowledge_export: false,
  research_verdict: null,
  research_verdict_note: 'this surface publishes no completion or clearance word',
  does_not_prove: ['a finding is working input, not a design quality verdict'],
};
const researchAnswer = (path) => (path === '/api/projects' ? RESEARCH_PROJECTS
  : path.includes('/research') ? researchFixture : {});

async function drainResearchReads() {
  const seen = [];
  for (let round = 0; round < 8; round += 1) {
    await flush();
    const fresh = shell.pending.splice(0, shell.pending.length);
    if (!fresh.length) break;
    seen.push(...fresh);
    for (const request of fresh) request.resolve(response(researchAnswer(request.path)));
  }
  await flush();
  return seen;
}

shell.window.location.hash = '#/research';
shell.dispatchHashchange();
const researchReads = await drainResearchReads();
for (const expected of ['/api/projects', '/api/projects/p1/research'])
  if (!researchReads.some((request) => request.path === expected))
    throw new Error(`研究洞察没有读回 ${expected}；实际读到 ${
      researchReads.map((request) => request.path).join(' ')}`);
const researchView = shell.elements.get('route-view');
const researchOutcome = byElementId(researchView, 'research-review-outcome');
const claimField = byElementId(researchView, 'research-claim');
const sourcesField = byElementId(researchView, 'research-sources');
const confidenceField = byElementId(researchView, 'research-confidence');
const supersedeField = byElementId(researchView, 'research-supersedes');
const researchButton = byElementId(researchView, 'research-submit');
if (!researchOutcome || !claimField || !sourcesField || !confidenceField || !supersedeField
  || !researchButton)
  throw new Error('研究表单的某个入口在页面上不可定位 —— ⑨ 找不到提交面');

// The view replaced its own "not open" copy: the notice lives in VIEW_NOT_OPEN and the route is
// now dispatched, so both halves must be gone from the rendered page.
const researchText = (researchView.textContent || '');
if (researchText.includes('未开放') || researchText.includes('没有研究结论的持久化路由'))
  throw new Error(`研究洞察仍显示"未开放"文案，而路由已存在：${researchText.slice(0, 140)}`);
// No completion word may appear, and the null verdict must be explained rather than blanked.
for (const forbidden of ['RESEARCH_COMPLETE', 'CLEARED', 'PENDING_REVIEW', '研究已完成'])
  if (researchText.includes(forbidden))
    throw new Error(`研究读回出现了它不该有的判定词 ${forbidden}`);
if (!researchText.includes('无完成判定词'))
  throw new Error('research_verdict 为 null 时页面必须说明"无完成判定词"，而不是留一个空徽章');
if (!researchText.includes('this surface publishes no completion or clearance word'))
  throw new Error('服务端给出的 research_verdict_note 没有上屏');
if (!researchText.includes('a finding is working input, not a design quality verdict'))
  throw new Error('does_not_prove 的行文没有上屏，数字就会脱离它的限制条件被读');
const confidenceWords = ['high', 'medium', 'low', 'speculative'];
for (const word of confidenceWords) {
  const option = findIn(researchView, (node) => node.tagName === 'OPTION' && node.value === word);
  if (!option) throw new Error(`置信度 ${word} 来自读回的 confidence_vocabulary，却不在下拉里`);
}
if (confidenceField.value !== '')
  throw new Error('置信度下拉预先选了值：没有人选的置信度不能是默认值');

// Building the page writes nothing.
if (researchReads.some((request) => request.init && request.init.method === 'POST'))
  throw new Error('构建研究页面时发出了 POST —— 一条结论只能由点击记录');

// (a) The two local refusals send nothing: no claim, and no source. The store refuses an
// unsourced finding outright, so the page declines to send a doomed write instead of inventing
// a citation for the operator.
researchButton.onclick();
if (shell.pending.length)
  throw new Error(`结论正文为空时仍发出了 ${shell.pending.map((r) => r.path).join(' ')}`);
if (!researchOutcome.textContent.includes('未提交')
  || !researchOutcome.textContent.includes('结论正文为空'))
  throw new Error(`缺结论正文时页面没有说明原因：${researchOutcome.textContent.slice(0, 160)}`);
claimField.value = '包装改版后货架识别度下降';
sourcesField.value = '   ';
researchButton.onclick();
if (shell.pending.length)
  throw new Error('没有来源引用时仍发出了 POST：页面不替操作人补一个来源');
if (!researchOutcome.textContent.includes('没有任何来源引用'))
  throw new Error(`缺来源时页面没有说明原因：${researchOutcome.textContent.slice(0, 160)}`);

// (b) One click, one POST, with the closed contract field set and no invented schemaVersion.
sourcesField.value = 'interview-11, shelf-photo-03';
confidenceField.value = 'low';
researchButton.onclick();
const researchSent = shell.pending.splice(0, shell.pending.length);
if (researchSent.length !== 1)
  throw new Error(`一次点击发出了 ${researchSent.length} 个请求，应为 1 个`);
if (researchSent[0].path !== '/api/projects/p1/research')
  throw new Error(`提交打到了 ${researchSent[0].path}，必须是所选项目的 research 路由`);
if (!researchSent[0].init || researchSent[0].init.method !== 'POST')
  throw new Error('研究结论的提交不是 POST');
const researchBody = JSON.parse(researchSent[0].init.body);
const RESEARCH_REQUIRED = ['finding_id', 'claim', 'sourceRefs'];
for (const field of RESEARCH_REQUIRED)
  if (!(field in researchBody))
    throw new Error(`提交缺少契约必备字段 ${field}`);
if ('schemaVersion' in researchBody)
  throw new Error('提交带了 schemaVersion：research-finding 契约关闭属性且未声明该字段，服务端会按未知属性拒绝');
const allowedKeys = new Set(['finding_id', 'claim', 'sourceRefs', 'confidence', 'notDesignRule']);
for (const key of Object.keys(researchBody))
  if (!allowedKeys.has(key))
    throw new Error(`提交带了契约之外的字段 ${key}`);
if (!Array.isArray(researchBody.sourceRefs) || researchBody.sourceRefs.length !== 2
  || researchBody.sourceRefs[0] !== 'interview-11')
  throw new Error(`来源拆分不符：${JSON.stringify(researchBody.sourceRefs)}`);
if (researchBody.confidence !== 'low')
  throw new Error(`所选置信度没有原样送出：${researchBody.confidence}`);
if ('notDesignRule' in researchBody)
  throw new Error('未勾选的可选布尔字段被写成了 false： absence 与 false 是不同的记录');
if (!/^rf-[0-9a-f]{1,32}$/.test(researchBody.finding_id))
  throw new Error(`finding_id ${researchBody.finding_id} 形状与服务端生成的一致前缀不符`);
const firstFindingId = researchBody.finding_id;

// (c) An identical resend keeps the id, so the service can answer "replay" instead of filing the
// same claim twice; a changed document must take a fresh id, because the store refuses an id
// whose content moved.
researchButton.onclick();
const resend = shell.pending.splice(0, shell.pending.length);
if (resend.length !== 1)
  throw new Error(`第二次相同点击发出了 ${resend.length} 个请求`);
if (JSON.parse(resend[0].init.body).finding_id !== firstFindingId)
  throw new Error('完全相同的重复提交换了 finding_id：服务端会把一次主张记成两条结论');
claimField.value = '包装改版后货架识别度下降（补：夜间陈列）';
researchButton.onclick();
const changed = shell.pending.splice(0, shell.pending.length);
if (JSON.parse(changed[0].init.body).finding_id === firstFindingId)
  throw new Error('改过的正文仍沿用旧 finding_id：服务端会以 ID 已占用拒绝，页面不该发注定被拒的写');

// (d) Supersession is a query parameter, and only CURRENT findings are offered as targets.
supersedeField.value = 'rf-one';
researchButton.onclick();
const superseding = shell.pending.splice(0, shell.pending.length);
if (superseding.length !== 1 || !superseding[0].path.startsWith('/api/projects/p1/research')
  || !String(superseding[0].init.body).length)
  throw new Error(`替代提交形状不对：${superseding.length} 个请求 `
    + `${superseding.map((r) => `${r.path}|${r.init && r.init.method}`).join(' ; ')}`);
if (!superseding[0].path.includes('supersedes=rf-one'))
  throw new Error(`替代链接没有作为查询参数送出：${superseding[0].path}`);
if ('supersedes' in JSON.parse(superseding[0].init.body))
  throw new Error('提交把 supersedes 塞进了文档：契约关闭属性且未声明它');
if (!byElementId(researchView, 'research-supersedes'))
  throw new Error('替代选择器消失了');

// (e) Success reads the ledger back from the service; a refusal then replaces that sentence
// rather than leaving a stale green beside an error.
superseding[0].resolve(response({ finding_id: 'rf-new', claim: 'x', sourceRefs: ['s'] }));
await drainResearchReads();
if (!researchOutcome.textContent.includes('已记录'))
  throw new Error(`记录成功后没有说明结论来自服务端读回：${researchOutcome.textContent.slice(0, 160)}`);
researchButton.onclick();
const failing = shell.pending.splice(0, shell.pending.length);
failing[0].resolve(response({ error: 'RESEARCH_SOURCE_REQUIRED',
  detail: 'a finding must cite at least one source' }, false));
await flush();
if (!researchOutcome.textContent.includes('未记录')
  || !researchOutcome.textContent.includes('RESEARCH_SOURCE_REQUIRED'))
  throw new Error(`服务端拒绝没有替换上一条成功说法：${researchOutcome.textContent.slice(0, 200)}`);
if (researchOutcome.textContent.includes('已记录'))
  throw new Error('一次被拒的写留下了"已记录"：同一屏上出现两个矛盾判定');

// (f) The unread half. A read-back that never arrived must not be drawn as a project holding no
// findings, and a count the response did not carry must not appear as 0.
// Shape-complete but count-free, so this case measures exactly one thing: a count the response
// never carried. A malformed payload would be caught by the shape notice instead (block ② covers
// that path), and the counts line would never render.
researchFixture = { schemaVersion: 'design-lab/research-readback/v1', project_id: 'p1',
  findings: [], current_findings: {}, confidence_counts: {}, does_not_prove: [],
  actor_kinds: {}, unattributed_findings: [],
  confidence_vocabulary: ['high', 'medium', 'low', 'speculative'] };
shell.window.location.hash = '#/dashboard';
shell.dispatchHashchange();
await flush();
shell.window.location.hash = '#/research';
shell.dispatchHashchange();
await drainResearchReads();
const strippedView = shell.elements.get('route-view');
const strippedText = strippedView.textContent || '';
if (!strippedText.includes('共 未读回 条'))
  throw new Error(`响应没带计数时,读数行必须逐字说"共 未读回 条"：${strippedText.slice(0, 220)}`);
// Not `\b共 0 条\b`: \\b is a word boundary over \\w only, and CJK characters are not word
// characters in JavaScript, so the guard could never have matched anything. The check is on the
// exact rendered form instead -- which is what the falsifier's fourth case proved was load-bearing.
if (strippedText.includes('共 0 条'))
  throw new Error('未读回的计数被画成了 0 条：空响应与空台账是两件事');
if (!strippedText.includes('本项目尚无已持久化的研究结论')
  && !strippedText.includes('未读回不等于本项目没有结论'))
  throw new Error(`空且确已读回的台账必须说清"没有被记录"：${strippedText.slice(0, 200)}`);
if (strippedText.includes('RESEARCH_COMPLETE'))
  throw new Error('空台账被说成了完成');

console.log('ok: ⑨ 研究洞察读回已持久化的结论：判定词一个都不画、null 判定给出服务端的说明、置信度选项来自读回且无预选、构建页面零 POST、空正文与无来源两种本地拒绝都不发请求、一次点击一个 POST 且只带契约字段（无 schemaVersion、未勾选的布尔不写成 false）、相同重发沿用 finding_id 而改动必换新 id、替代作为查询参数且只列现行结论、成功后读回来自服务端、拒绝替换上一条已提交、缺计数说未读回不画 0 条');

// ⑩ 制作记录与待继续 · R2 §7 over the real GET /projects/<id>/tasks. The capture harness
// boots an empty synthetic project, so no round had ever rendered a task ROW -- an
// unmounted row function is not a delivered screen. Three records are seeded here:
// one in-flight, one needing a human (cancel requested, never acknowledged), one receipted.
// DL-UI-U06 fixtures and the per-path answer ⑩ and ⑯ share. Declared before ⑩ because ⑩
// renders the same page and must answer both of its reads.
const RUNTIME_ABSENT = {
  schemaVersion: 'design-lab/native-runtime-readback/v1', project_id: 'p1',
  host_guard: { table: 'ABSENT', rows: null },
  quiescence: { table: 'ABSENT', rows: null },
  reconciliation: { table: 'ABSENT', rows: null },
  recovery_protocol: { table: 'ABSENT', rows: null },
  executions: { table: 'ABSENT', rows: null },
  counts: { hosts_held: null, attempts_quiescent_receipted: null, reconciliations_open: null,
    executions_receipted: null, executions_with_result: null },
  budget: null,
  budget_reason: 'no table in this repository records a run budget, quota or cost',
  proves_production_ready: false, is_host_action_performed: false,
  does_not_say: ['a held guard row says a host is occupied by an attempt, not that waiting is right'],
};
const RUNTIME_HELD = {
  ...RUNTIME_ABSENT,
  host_guard: { table: 'PRESENT', rows: [{ host: 'photoshop', attempt_id: 'att-held',
    acquired_at: '2026-10-09T20:00:00Z' }] },
  quiescence: { table: 'PRESENT', rows: [{ attempt_id: 'att-held', started_at: 'x',
    receipt_json: null }] },
  reconciliation: { table: 'PRESENT', rows: [] },
  recovery_protocol: { table: 'PRESENT', rows: [{ attempt_id: 'att-held',
    protocol: 'os-lock-v1' }] },
  executions: { table: 'PRESENT', rows: [{ attempt_id: 'att-held', host: 'photoshop',
    receipt_json: 'r', result_json: null }] },
  counts: { hosts_held: 1, attempts_quiescent_receipted: 0, reconciliations_open: 0,
    executions_receipted: 1, executions_with_result: 0 },
};
let runtimeFixture = RUNTIME_ABSENT;

// DL-UI-U09 fixtures. The records page now also reads the knowledge readback, and ⑩/⑯/㉒
// all open that page; answering it by path keeps a tasks body from being served to the
// knowledge route (which would render as a shape notice and hide the forms ㉒ drives).
// GET …/knowledge-candidates/<id>/export 的信封，字段取自服务真实产出的那一版
// （design-lab/tests/test_knowledge_http.py 与 verify_route_payload_contracts.py 读回的同形物）。
const KNOWLEDGE_EXPORT_ENVELOPE = {
  schemaVersion: 'design-lab/assurance-knowledge-candidate-export-envelope/v1',
  status: 'CANDIDATE_EXPORT',
  project_id: 'p1',
  candidate_id: 'kc-' + '3'.repeat(32),
  revision: 1,
  export: {
    schemaVersion: 'design-lab/assurance-knowledge-candidate/v2',
    candidate_id: 'kc-' + '3'.repeat(32),
    candidate_type: 'JURY_CORRECTION',
    license_id: 'project-internal',
    payload_sha256: 'sha256:' + 'f'.repeat(64),
  },
  v1_projection: {
    schemaVersion: 'design-lab/candidate-knowledge/v1',
    candidate_id: 'kc-' + '3'.repeat(32),
    source_id: 'job-1:UNUSED',
    knowledge_type: 'JURY_CORRECTION',
    state: 'APPROVED',
    content_hash: 'sha256:' + 'f'.repeat(64),
  },
  provenance: {
    job_id: 'job-1', operation_id: 'UNUSED',
    job_id_state: 'USER_SUPPLIED', operation_id_state: 'EXPLICITLY_UNUSED',
    design_lab_sha: 'c'.repeat(40), payload_sha256: 'sha256:' + 'f'.repeat(64),
  },
  freshness: 'CURRENT',
  outbound: { transport: 'NOT_CONNECTED', sent_count: 0, bytes: 1234 },
  does_not_say: ['传输未实现：本服务不连接 ArcheAxis，也不会自动重试；export_ready 只表示本地合同允许导出，不代表已经发送或对方已经接收。'],
};

const KNOWLEDGE_CANDIDATES = [
  { candidate_id: 'kc-' + '1'.repeat(32), candidate_type: 'METHOD',
    review_state: 'PENDING_HUMAN_APPROVAL', revocation_state: 'ACTIVE', revision: 1,
    created_at: '2026-10-18T09:00:00+00:00', updated_at: '2026-10-18T09:00:00+00:00',
    source_design_lab_sha: 'a'.repeat(40), payload_sha256: 'b'.repeat(64), supersedes: null,
    title: '包装色数上限', statement: '色数超过四色时先做打样验证', applies_to: ['packaging'],
    license_id: 'project-internal', rights_gate_state: 'CHECKED',
    reviewer_id: null, reviewed_at: null, revoked_by: null, revoked_at: null,
    revocation_reason: null, freshness: 'CURRENT', export_ready: false,
    export_blocked_by: 'review_not_approved' },
  { candidate_id: 'kc-' + '2'.repeat(32), candidate_type: 'PRODUCTION_LESSON',
    review_state: 'APPROVED', revocation_state: 'REVOKED', revision: 2,
    created_at: '2026-10-17T08:00:00+00:00', updated_at: '2026-10-17T08:00:00+00:00',
    source_design_lab_sha: 'd'.repeat(40), payload_sha256: 'e'.repeat(64), supersedes: null,
    title: '夜间陈列对比度', statement: '夜间货架需要更高的明度差',
    applies_to: ['packaging', 'retail'],
    license_id: 'CC-BY-4.0', rights_gate_state: 'CHECKED',
    reviewer_id: 'Alice', reviewed_at: '2026-10-17T09:00:00+00:00', revoked_by: 'Bob',
    revoked_at: '2026-10-18T08:00:00+00:00', revocation_reason: '事实已经变化',
    freshness: 'STALE', export_ready: false, export_blocked_by: 'revoked' },
  { candidate_id: 'kc-' + '3'.repeat(32), candidate_type: 'JURY_CORRECTION',
    review_state: 'APPROVED', revocation_state: 'ACTIVE', revision: 1,
    created_at: '2026-10-18T10:00:00+00:00', updated_at: '2026-10-18T10:00:00+00:00',
    source_design_lab_sha: 'c'.repeat(40), payload_sha256: 'f'.repeat(64),
    supersedes: 'kc-' + '2'.repeat(32),
    title: '评审语汇纠偏', statement: '避免把完成度说成质量', applies_to: ['jury'],
    license_id: 'project-internal', rights_gate_state: 'CHECKED',
    reviewer_id: 'Carol', reviewed_at: '2026-10-18T11:00:00+00:00', revoked_by: null,
    revoked_at: null, revocation_reason: null, freshness: 'CURRENT', export_ready: true,
    export_blocked_by: null },
];
const KNOWLEDGE_READBACK = {
  schemaVersion: 'design-lab/assurance-knowledge-candidate-readback/v1', project_id: 'p1',
  candidates: KNOWLEDGE_CANDIDATES, candidate_count: 3, unreadable_count: 0,
  pending_review_count: 1, approved_count: 2, rejected_count: 0, revoked_count: 1,
  export_ready_count: 1, conflicts: [], revocation_receipts: [],
  head_sha: 'c'.repeat(40),
  outbound: { transport: 'NOT_CONNECTED', destination: 'ArcheAxis', sent_count: 0,
    last_attempt_at: null,
    note: '本服务没有 ArcheAxis 传输实现；sent_count 为 0 是因为从未发送，不是一次失败的重试。' },
  does_not_say: ['a candidate is working knowledge, not a design-quality verdict'],
};
let knowledgeFixture = KNOWLEDGE_READBACK;

function answerRecords(request) {
  if (request.path.includes('/native-runtime')) {
    request.resolve(response(runtimeFixture));
    return;
  }
  if (request.path.includes('/knowledge-candidates')) {
    request.resolve(response(knowledgeFixture));
    return;
  }
  request.resolve(response({ tasks: RECORD_TASKS, next_cursor: 'job-z' }));
}

// The knowledge read starts AFTER tasks + native-runtime resolve (recordsBody awaits the
// panel before rendering), so one flat splice would leave it dangling and the next block's
// "exactly one events read" assertion would count it. Drain in rounds until quiet.
async function drainRecordReads() {
  const seen = [];
  for (let round = 0; round < 8; round += 1) {
    await flush();
    const fresh = shell.pending.splice(0, shell.pending.length);
    if (!fresh.length) break;
    seen.push(...fresh);
    for (const request of fresh) answerRecords(request);
  }
  await flush();
  return seen;
}

const RECORD_TASKS = [
  { kind: 'photoshop-native', state: 'RUNNING', job_id: 'job-a',
    cancel: { requested: false, acknowledged: false },
    attempt: { attempt_id: 'att-a', attempt_no: 1, state: 'RUNNING' } },
  { kind: 'illustrator-native', state: 'CANCEL_REQUESTED', job_id: 'job-b',
    cancel: { requested: true, acknowledged: false },
    attempt: { attempt_id: 'att-b', attempt_no: 3, state: 'CANCEL_REQUESTED' } },
  { kind: 'photoshop-native', state: 'RECEIPTED', job_id: 'job-c',
    cancel: { requested: false, acknowledged: false },
    attempt: { attempt_id: 'att-c', attempt_no: 2, state: 'RECEIPTED' } },
  // ⑮ needs a non-native row: an imported raster has no target package to continue into,
  // so a 接续 button on it would be a control that leads nowhere.
  { kind: 'image-import', state: 'RECEIPTED', job_id: 'img-d',
    cancel: { requested: false, acknowledged: false },
    attempt: { attempt_id: 'att-d', attempt_no: 1, state: 'RECEIPTED' } },
];

shell.window.location.hash = '#/records';
shell.dispatchHashchange();
const recordProjects = shell.pending.shift();
recordProjects.resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
await flush();
const recordsView = shell.elements.get('route-view');
const recordSelect = byElementId(recordsView, '制作记录与待继续-project');
if (!recordSelect) throw new Error('制作记录没有渲染项目选择器，⑩ 找不到入口');
recordSelect.value = 'p1';
recordSelect.onchange();
const recordRequests = await drainRecordReads();
for (const request of recordRequests) {
  if (request.path.includes('/events'))
    throw new Error(`没有人展开任何一行，页面却读了 ${request.path} —— 最近确认点不能凭猜测取`);
}
const recordText = (recordsView.textContent || '').replace(/\s+/g, ' ');
for (const word of ['RUNNING', 'CANCEL_REQUESTED', 'RECEIPTED'])
  if (!recordText.includes(word))
    throw new Error(`状态词 ${word} 没有原样出现在读回面上（服务词汇不得翻译或改写）`);
if (!recordText.includes('领域：无该字段'))
  throw new Error('TaskRecord 没有领域字段，界面必须说"无该字段"而不是按 kind 猜一个');
if (!recordText.includes('宿主未确认'))
  throw new Error('取消请求与宿主确认是两段事实：requested 而未被 ack 时必须说未确认');
if (!recordText.includes('进行中 1') && !recordText.includes('进行中 1 条')) {
  if (!/进行中\s*1/.test(recordText))
    throw new Error(`分组计数错了：${recordText.slice(0, 260)}`);
}
// The dock counts only what still needs work: 2 of 3, never the receipted one.
const dock = byElementId(recordsView, 'activity-dock');
if (!dock) throw new Error('有 2 条作业仍在进行/待核对，任务条却没渲染');
const dockText = (dock.textContent || '').replace(/\s+/g, ' ');
if (!dockText.includes('2 条'))
  throw new Error(`任务条把待处理数说成了"${dockText.slice(0, 60)}"，应为 2 条`);
// Expanding one row is what asks for events -- exactly one request, for that job.
const detail = findIn(recordsView, (node) => Boolean(node && node.tagName === 'DETAILS'));
if (!detail) throw new Error('找不到"最近确认点与尝试"的展开面');
const before = shell.pending.length;
detail.open = true;
if (typeof detail.ontoggle !== 'function')
  throw new Error('展开面没有挂 toggle 处理函数 —— 最近确认点永远不会被读回');
detail.ontoggle();
await flush();
const eventRequests = shell.pending.splice(0, shell.pending.length);
if (eventRequests.length !== 1)
  throw new Error(`展开一行应当只发一次 events 读回，实际 ${eventRequests.length} 次`);
if (!eventRequests[0].path.includes('/tasks/job-a/events'))
  throw new Error(`展开第一行却读了 ${eventRequests[0].path}`);
eventRequests[0].resolve(response({
  events: [{ at: '2026-10-09T10:00:00Z', attempt_no: 1, from_state: 'PENDING',
    to_state: 'RUNNING' }],
  next_cursor: null,
}));
await flush();
const eventsText = (recordsView.textContent || '').replace(/\s+/g, ' ');
if (!eventsText.includes('最近确认点：RUNNING ← PENDING'))
  throw new Error(`最近确认点没有从事件读回里拼出来：${eventsText.slice(0, 260)}`);
if (before !== 0) throw new Error('展开前不该有挂起的读回请求');

console.log('ok: ⑩ 制作记录读回真实作业：状态词原样出现、领域字段缺失如实说明、取消的 requested 与 ack 分成两段、任务条只数仍在进行/待核对的 2 条而不是 3 条、没人展开就不读 events、展开一行恰好一次读回、最近确认点来自事件而不是猜测');

// ⑮ DL-UI-U05 · 接续入口。此前这一行只有一个人禁用「继续该任务」，理由写的是宿主副作用，
// 于是把"跳去编排面"和"驱动宿主"混成了同一件事：跳转不产生宿主效果，禁用它的理由根本不成立。
// 现在两条线分开，并用行为证明分开的那条确实只是跳转——一次点击只改 hash，不发任何请求。
const continueButtons = [];
const hostButtons = [];
walkNodes(recordsView, (node) => {
  if (node?.tagName !== 'BUTTON') return;
  const id = node.attributes?.get('id') ?? '';
  if (id.startsWith('record-continue-')) continueButtons.push(node);
  if ((node.textContent ?? '') === '启动 / 取消') hostButtons.push(node);
});
if (continueButtons.length !== 3)
  throw new Error(`三条原生作业应有 3 个接续入口，实得 ${continueButtons.length} 个`
    + '（素材导入那条不该拿到一个通向目标生成包的按钮）');
if (continueButtons.some((b) => b.attributes.has('disabled')))
  throw new Error('接续入口被禁用了：目标生成包页已经落地，跳转不是宿主副作用，没有理由禁');
if (continueButtons.some((b) => typeof b.onclick !== 'function'))
  throw new Error('接续按钮没有挂点击函数，看着能点其实点了没反应');
if (hostButtons.length !== 4)
  throw new Error(`四条记录应有 4 个启动/取消动作，实得 ${hostButtons.length} 个`);
if (hostButtons.some((b) => !b.attributes.has('disabled')))
  throw new Error('启动/取消必须保持禁用：本会话没有真实宿主副作用授权');
const continueText = (recordsView.textContent || '').replace(/\s+/g, ' ');
if (!continueText.includes('接续只做页面跳转'))
  throw new Error('接续入口要当场说清它只跳转、宿主与底图仍需重选，否则用户会以为状态被带过去了');
if (!continueText.includes('没有对应的目标生成包'))
  throw new Error('素材导入那条要说明为什么没有接续入口，不能只留一个空白');

const beforeContinue = shell.pending.length;
continueButtons[0].onclick();
if (shell.pending.length !== beforeContinue)
  throw new Error('点击接续发出了请求：这一跳应当只是打开编排面，不替服务编任何状态');
if (shell.window.location.hash !== '#/plan')
  throw new Error(`接续必须落到目标生成包自己的地址，实得 ${shell.window.location.hash}`);

// 声明面板必须和自己画出来的控件一致：这一页既然有了能点的接续按钮，
// "这个入口能说什么"那一段就不许再说接续未接线。这些断言必须在重渲染 #/intake 之前跑——
// 两条路由共用同一个 `route-view` 元素，一旦渲染输入页，这里的 recordsView 就换内容了。
const claimContinue = findNodes(recordsView, 'LI', '接续到目标生成包')[0];
if (!claimContinue)
  throw new Error('声明面板没有为接续单列一行，读者无从判断这一跳的边界');
if ((claimContinue.textContent || '').includes('未接线'))
  throw new Error('接续按钮已经接线，声明面板仍写"未接线"——页面自相矛盾');
if (!(claimContinue.textContent || '').includes('不会自动变成包结构'))
  throw new Error('声明面板要写清简报字段不会被带过去，否则"已接线"会被读成整条链都通了');
// 用"本会话无该授权"定位，而不是"启动 / 取消"：每条作业行里都有一个同名的禁用按钮，
// 按按钮文字找会先命中作业行，那条行当然不写"未接线"。
const claimHost = findNodes(recordsView, 'LI', '本会话无该授权')[0];
if (!claimHost || !(claimHost.textContent || '').includes('未接线'))
  throw new Error('启动/取消必须仍在声明面板里标未接线：那是本会话没有授权的真实宿主副作用');

// 输入与目标页上的同类禁用：DL-UI-U05 落地后「不该看起来可用」的理由已经过期，所以这一
// 个也接上了；仍然没说谎的地方是"简报字段不会自动变成包结构"。
shell.window.location.hash = '#/intake';
shell.dispatchHashchange();
const intakeProjectsReq2 = shell.pending.shift();
intakeProjectsReq2.resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
await flush();
const intakeView2 = shell.elements.get('route-view');
const intakeSelect2 = byIdAttr(intakeView2, '输入与目标-project');
if (!intakeSelect2) throw new Error('输入与目标没有渲染项目选择器，⑮ 找不到入口');
intakeSelect2.value = 'p1';
intakeSelect2.onchange();
const intakeReads2 = shell.pending.splice(0, shell.pending.length);
for (const request of intakeReads2) answerIntakeRead(request, { briefs: [] });
await flush();
const toPlan = byIdAttr(intakeView2, 'intake-to-plan');
if (!toPlan) throw new Error('输入与目标页没有渲染到目标生成包的入口');
if (toPlan.attributes.has('disabled'))
  throw new Error('目标生成包页已经落地，这一跳没有理由继续禁用');
const beforeIntake = shell.pending.length;
toPlan.onclick();
if (shell.pending.length !== beforeIntake)
  throw new Error('从输入与目标跳编排面却发出了请求：这一步只是换页');
if (shell.window.location.hash !== '#/plan')
  throw new Error(`输入与目标的接续必须落到 #/plan，实得 ${shell.window.location.hash}`);
const intakeNote = (intakeView2.textContent || '').replace(/\s+/g, ' ');
if (!intakeNote.includes('不会自动变成目标包字段'))
  throw new Error('必须写明简报字段不会被带进目标包，否则入口看起来像已经接通了整条链');

console.log('ok: ⑮ 接续入口只做跳转且真的能点：三条原生作业各一个入口、导入行不给入口、'
  + '启动/取消仍保持禁用、两次点击都只改 hash 不发请求、简报字段不被谎称带进目标包、'
  + '声明面板与画出来的控件一致');

// ⑯ DL-UI-U06 · 运行与恢复现场。这块要钉的不是"面板画出来了"，而是三种"没有"在屏上
// 确实是三句话：未读回 / 表不存在 / 表存在且为空。混起来就是本仓库已经犯过两次的错——
// 把没问到说成答案是零。
async function openRecordsWithRuntime(doc) {
  runtimeFixture = doc;
  shell.window.location.hash = '#/records';
  shell.dispatchHashchange();
  const projectsReq = shell.pending.shift();
  if (!projectsReq) throw new Error('重新进入制作记录没有读项目列表');
  projectsReq.resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
  await flush();
  const view = shell.elements.get('route-view');
  const select = byElementId(view, '制作记录与待继续-project');
  if (!select) throw new Error('⑯ 找不到项目选择器');
  select.value = 'p1';
  select.onchange();
  const reqs = await drainRecordReads();
  const paths = reqs.map((r) => r.path);
  if (!paths.some((p) => p.includes('/native-runtime')))
    throw new Error(`选了项目却没读运行时投影：${paths.join(' , ')}`);
  return view;
}

const absentView = await openRecordsWithRuntime(RUNTIME_ABSENT);
const absentText = (absentView.textContent || '').replace(/\s+/g, ' ');
if (!absentText.includes('运行与恢复现场'))
  throw new Error('运行时观察面板没有渲染');
if (!absentText.includes('从未记录过原生作业'))
  throw new Error('表不存在必须说成"从未记录过"，不能给一个零');
if (absentText.includes('当前没有尝试持有宿主'))
  throw new Error('ABSENT 被画成了"表存在且为空"：这是两种不同的事实');
if (/当前 0 个宿主被持有/.test(absentText))
  throw new Error('hosts_held=null 被印成了 0 —— 没问到不等于答案是零');
if (!absentText.includes('无该字段') || !absentText.includes('run budget'))
  throw new Error('预算要作为"无该字段"上屏并带上服务给的理由');
if (!absentText.includes('not that waiting is right'))
  throw new Error('does_not_say 的每一句都要成为一行，否则面板只给了数字没给边界');

const heldView = await openRecordsWithRuntime(RUNTIME_HELD);
const heldText = (heldView.textContent || '').replace(/\s+/g, ' ');
if (!heldText.includes('1 个宿主被持有：photoshop→att-held'))
  throw new Error(`占用宿主没有按 host→attempt 上屏：${heldText.slice(heldText.indexOf('宿主占用'), heldText.indexOf('宿主占用') + 120)}`);
if (!heldText.includes('已记录 1 条，其中带回执 0 条'))
  throw new Error('静默确认要把"记录了几条"和"几条带回执"分开说');
if (!heldText.includes('开着 0 条'))
  throw new Error('表存在且为空时，0 是一个真实答案，必须照说');
if (!heldText.includes('os-lock-v1'))
  throw new Error('恢复协议要原样上屏，不改写成人话里的另一个词');
if (!heldText.includes('读回 1 条'))
  throw new Error('执行记录要给出条数');

// A payload that arrived without `counts` is unread, not zero-filled. The sections are still
// carried here on purpose: with them absent the page would crash on a missing field instead of
// proving that the notice, not the table state, is what keeps the numbers off the screen.
const partialView = await openRecordsWithRuntime({
  schemaVersion: 'design-lab/native-runtime-readback/v1', project_id: 'p1',
  host_guard: { table: 'ABSENT', rows: null },
  quiescence: { table: 'ABSENT', rows: null },
  reconciliation: { table: 'ABSENT', rows: null },
  recovery_protocol: { table: 'ABSENT', rows: null },
  executions: { table: 'ABSENT', rows: null },
  budget: null, budget_reason: 'x', proves_production_ready: false,
  is_host_action_performed: false, does_not_say: [],
});
// Scoped to the panel: the task rows already say "最近确认点未读回", so grepping the whole
// view for 未读回 would pass even with the runtime notice switched off.
const runtimePanel = (view) => {
  const found = [];
  walkNodes(view, (node) => {
    if (node?.tagName === 'DIV' && (node.textContent || '').includes('运行与恢复现场'))
      found.push(node);
  });
  return found[found.length - 1] ?? null;
};
const panelOf = (view) => ((runtimePanel(view)?.textContent) || '').replace(/\s+/g, ' ');
const partialPanel = panelOf(partialView);
if (!partialPanel) throw new Error('找不到运行时面板本体');
if (!partialPanel.includes('未读回：没有问到'))
  throw new Error(`缺 counts 的读回必须在面板里报"未读回：没有问到"：${partialPanel.slice(0, 200)}`);
if (partialPanel.includes('从未记录过原生作业'))
  throw new Error('未读回时不得借用 ABSENT 的说法——那是对表存在与否的判断，而这次什么都没读到');

const heldView2 = await openRecordsWithRuntime(RUNTIME_HELD);
const heldPanel = panelOf(heldView2);
if (heldPanel.includes('未读回：没有问到'))
  throw new Error('完整读回却被当成未读回：notice 不能反过来吞掉已有的数字');

// The panel is observation only: no button inside it may be clickable.
const panelButtons = [];
walkNodes(runtimePanel(heldView2), (node) => {
  if (node?.tagName === 'BUTTON') panelButtons.push(node);
});
if (panelButtons.length)
  throw new Error(`运行时面板里画了 ${panelButtons.length} 个按钮：这一面只观察，`
    + '启动/取消是宿主副作用，不该出现在这里');

console.log('ok: ⑯ 运行与恢复现场：ABSENT/空表/未读回三种说法互不混用，占用按 host→attempt 上屏，'
  + '回执数与记录数分开，预算作为无该字段带理由，does_not_say 逐句成行，面板内没有任何可点动作');

// D05 — the palette's four object groups project a route's payload into rows, and until this
// batch that projection lived inside a browser-only scope, so nothing could check the field
// names. `/design-systems` answers `{design_systems: …}`; the group read `{systems: …}` and a
// successful readback rendered as "这一组当前读回 0 个对象" — a confident zero over real objects.
{
  const rows = shell.context.searchGroupRows;
  if (typeof rows !== 'function')
    throw new Error('searchGroupRows 不可达：调色板的分组投影又回到了浏览器专用作用域，'
      + '字段名将再次无人可测');
  const systems = rows('/design-systems', { design_systems: [
    { name: 'ui2026', title: 'UI 基线', version: '2.1', evidence_level: 'E1' },
  ] });
  if (systems.length !== 1 || systems[0].name !== 'ui2026' || !systems[0].kind.includes('2.1'))
    throw new Error(`#/design-systems 分组没有按合同字段 design_systems 取行：`
      + `${JSON.stringify(systems)}`);
  if (rows('/design-systems', { systems: [{ name: 'x' }] }).length !== 0)
    throw new Error('分组仍在读 `systems` —— 那是一个没有任何响应携带过的键');
  // The other three groups are pinned against their own route's key, so a fix here cannot be a
  // fix for one group only.
  if (rows('/capabilities', { capabilities: [{ id: 'c1', kind: 'model', license: null }] }).length !== 1)
    throw new Error('能力资产分组不认 capabilities');
  if (rows('/projects', { projects: [{ id: 'abcdefgh', name: 'P' }] }).length !== 1)
    throw new Error('项目分组不认 projects');
  if (rows('/domains', { packs: [{ packId: 'uiux-design', directory: 'uiux',
    displayName: 'UI/UX', domain: 'ui-ux' }] }).length !== 1)
    throw new Error('设计领域分组不认 packs');
  if (rows('/domains', { packs: [{ packId: 'uiux-design', directory: 'uiux',
    displayName: 'UI/UX', domain: 'ui-ux' }] })[0].go !== '#/domains/uiux-design')
    throw new Error('领域行必须落到该 pack 自己的地址');
}

console.log('ok: ⑰ 全局搜索的四组对象投影按各自路由的合同字段取行（design_systems 不是 systems），'
  + '领域行落到 pack 自己的地址');

// ⑳ DL-UI-U07 成果版本面板。该项目详情的版本面板在此之前从不渲染（阶段表把它标 PLANNED、panelId 为空），
// 所以"版本像什么"这条读数一直只能靠 Inspector 的版本环间接猜。本块把它变成可断言的：
// 读回真实的 BundleRecord 字段，当前 / 已被取代分得开，未读回不画 0。
{
  const PID = 'a'.repeat(32);
  const rows = [
    { id: 'bundle-native-' + '1'.repeat(64), kind: 'native-package', version_id: 'v-' + '1'.repeat(32),
      version_no: 1, byte_size: 4096, sha256: '2'.repeat(64), rights: 'UNCLEARED',
      verification: 'HASH_VERIFIED' },
    { id: 'bundle-native-' + '1'.repeat(64), kind: 'native-package', version_id: 'v-' + '3'.repeat(32),
      version_no: 2, byte_size: 5120, sha256: '4'.repeat(64), rights: 'CLEARED',
      verification: 'HASH_VERIFIED' },
    { id: 'bundle-web-' + '5'.repeat(64), kind: 'web-export', version_id: 'v-' + '6'.repeat(32),
      version_no: 1, byte_size: 2048, sha256: '7'.repeat(64), rights: 'CLEARED', verification: '' },
  ];
  const answer = async (bundles) => {
    for (let round = 0; round < 8; round += 1) {
      const reads = shell.pending.splice(0, shell.pending.length);
      if (!reads.length) break;
      for (const r of reads) {
        if (r.path.endsWith('/bundles')) r.resolve(response(bundles));
        else if (r.path.endsWith('/tasks')) r.resolve(response({ tasks: [] }));
        else if (r.path.endsWith('/design-layer')) r.resolve(response({ design_layer: {
          briefs: [], directions: [], chosen_direction: null, bindings: [], active_binding: null,
          design_systems: [] } }));
        else if (r.path.endsWith('/design-systems')) r.resolve(response({ design_systems: [] }));
        else if (r.path.endsWith('/design-system-tokens')) r.resolve(response({ token_documents: [] }));
        else if (r.path === '/projects') r.resolve(response(projectsEnvelope([projectRow(PID, 'Alpha')])));
        else r.resolve(response({}));
      }
      await flush();
    }
  };
  const open = async (bundles) => {
    shell.window.location.hash = '#/projects/' + PID;
    shell.dispatchHashchange();
    await answer(bundles);
    const panel = (() => {
      let hit = null;
      walkNodes(shell.elements.get('route-view'), (n) => {
        if (n?.attributes?.get('id') === 'pd-versions-panel') hit = n;
      });
      return hit;
    })();
    if (!panel) throw new Error('项目详情没有渲染 #pd-versions-panel');
    return panel;
  };

  const read = await open({ bundles: rows });
  const text = read.textContent;
  if (!text.includes('2 类 / 3 版本'))
    throw new Error(`版本面板的分类/版本数没有跟着读回走：${text.slice(0, 200)}`);
  if (!text.includes('v2 · 当前') || !text.includes('v1 · 已被后续版本取代'))
    throw new Error(`当前版本与已被取代的版本没有分开：${text.slice(0, 300)}`);
  if (!text.includes('4096 B') || !text.includes('sha256 ' + '4'.repeat(12)))
    throw new Error(`版本行必须给出该版本自己的字节数与摘要：${text.slice(0, 300)}`);
  // 权利与核验按服务端原词上屏，不做词表映射 —— 两个字段的取值集不在本文件合同里。
  if (!text.includes('权利 UNCLEARED') || !text.includes('权利 CLEARED'))
    throw new Error(`权利必须原词上屏：${text.slice(0, 300)}`);
  if (!text.includes('核验 HASH_VERIFIED'))
    throw new Error(`核验必须原词上屏：${text.slice(0, 300)}`);
  // 面板只读回：它不得声称自己提交改稿，也不得从 version_no 推断改稿来源。
  if (!text.includes('本面板只读回、不提交改稿'))
    throw new Error('面板必须写明它不提交改稿（局部改稿入口在 patch 路由）');

  const empty = await open({ bundles: [] });
  if (!empty.textContent.includes('尚无成果版本'))
    throw new Error(`空集合要说"尚无成果版本"：${empty.textContent.slice(0, 200)}`);
  const unread = await open({});
  if (!unread.textContent.includes('未读回'))
    throw new Error(`缺 bundles 字段要说未读回，不能画成 0 个版本：${unread.textContent.slice(0, 200)}`);
  if (/0 类 \/ 0 版本/.test(unread.textContent))
    throw new Error('未读回被画成了 0 类 / 0 版本');
}

console.log('ok: ⑳ DL-UI-U07 成果版本面板：读回真实 BundleRecord 的版本链（当前/已被取代、字节数与'
  + '摘要、权利与核验原词）、空集合说尚无、缺字段说未读回不画 0，并写明本面板只读回不提交改稿');

// ㉒ DL-UI-U09 · 知识回执与反馈（T16）。面板要钉的是可观察行为，而不是"控件画出来了"：
// 构建只读一次、零写；状态 / 新鲜度 / 导出词全部来自读回；创建表单不替人补 job_id、
// operation_id 或资产布尔；三个写路由的顶层键集合精确（7 / 6 / 3），未选的可选值发 null
// 而不是编一个 false；同一内容重发沿用 candidate_id；未读回时不提供裁决 / 撤销控件、
// 也不把占位零画成候选数。三条 Human Gate 边界必须写在可见文字里。
{
  if (shell.pending.length)
    throw new Error(`㉒ 开始前仍有未答复的请求：${shell.pending.map((r) => r.path).join(' ')}`);

  async function openKnowledgeView(payload) {
    knowledgeFixture = payload;
    shell.window.location.hash = '#/records';
    shell.dispatchHashchange();
    const projectsReq = shell.pending.shift();
    if (!projectsReq) throw new Error('㉒ 重新进入制作记录没有读项目列表');
    projectsReq.resolve(response(projectsEnvelope([projectRow('p1', 'Alpha')])));
    await flush();
    const view = shell.elements.get('route-view');
    const select = byElementId(view, '制作记录与待继续-project');
    if (!select) throw new Error('㉒ 找不到项目选择器');
    select.value = 'p1';
    select.onchange();
    const reads = await drainRecordReads();
    return { view, reads };
  }

  const first = await openKnowledgeView(KNOWLEDGE_READBACK);
  const view = first.view;
  const knowledgeReads = first.reads.filter((r) => r.path.includes('/knowledge-candidates'));
  if (knowledgeReads.length !== 1)
    throw new Error(`㉒ 构建知识面板应只读一次知识投影，实际 ${knowledgeReads.length} 次`);
  if (knowledgeReads[0].path !== '/api/projects/p1/knowledge-candidates'
    || knowledgeReads[0].init.method !== 'GET')
    throw new Error(`㉒ 知识读回打到了 ${knowledgeReads[0].init.method} ${knowledgeReads[0].path}`);
  if (first.reads.some((r) => r.init.method !== 'GET'))
    throw new Error('㉒ 构建知识面板时发出了写请求');

  const panel = byElementId(view, 'knowledge-panel');
  if (!panel) throw new Error('㉒ 知识面板没有渲染');
  const panelText = (panel.textContent || '').replace(/\s+/g, ' ');
  // The half that was NOT built stays visible, not inferred from a green tag.
  for (const sentence of ['没有建的那一半', '本服务没有 ArcheAxis 传输',
    'sent_count 的 0 表示从未发送', 'export_ready 只表示本地合同允许导出'])
    if (!panelText.includes(sentence))
      throw new Error(`㉒ 面板没有把未建的一半写出来（缺「${sentence}」）`);
  // Every word below is a stored projection field, not a client-side verdict.
  for (const word of ['PENDING_HUMAN_APPROVAL', 'APPROVED', 'REVOKED', 'CURRENT', 'STALE'])
    if (!panelText.includes(word))
      throw new Error(`㉒ 读回状态词 ${word} 没有上屏`);
  for (const count of ['共 3 条候选', '待裁决 1', '已批准 2', '已驳回 0', '已撤销 1',
    '不可读取 0 条行', '本地合同可导出 1 条'])
    if (!panelText.includes(count))
      throw new Error(`㉒ 计数没有按读回原样上屏（缺「${count}」）：${panelText.slice(0, 260)}`);
  if (!panelText.includes('NOT_CONNECTED') || !panelText.includes('ArcheAxis')
    || !panelText.includes('sent_count=0'))
    throw new Error('㉒ 出站边界没有按 readback 的 outbound 原样上屏');
  if (!panelText.includes('a candidate is working knowledge, not a design-quality verdict'))
    throw new Error('㉒ does_not_say 的每一句都要成为一行');
  if (!panelText.includes('本地合同允许导出，未发送')
    || !panelText.includes('不可导出：review_not_approved')
    || !panelText.includes('不可导出：revoked'))
    throw new Error('㉒ export_ready 的真假两种说法必须分开，且不等于发送');
  if (!panelText.includes('撤销原因：事实已经变化') || !panelText.includes('尚无人工裁决'))
    throw new Error('㉒ 人工裁决与撤销原因必须从读回上屏');
  const pendingTag = findIn(panel, (node) => node?.tagName === 'SPAN'
    && node.textContent === 'PENDING_HUMAN_APPROVAL');
  if (!pendingTag || pendingTag.attributes.get('lang') !== 'en')
    throw new Error('㉒ 服务状态词必须以 lang="en" 上屏');

  const outcome = byElementId(view, 'knowledge-outcome');
  const field = (id) => {
    const node = byElementId(view, id);
    if (!node) throw new Error(`㉒ 找不到控件 ${id}`);
    return node;
  };
  const sameKeys = (actual, expected) =>
    JSON.stringify([...actual].sort()) === JSON.stringify([...expected].sort());
  let createSubmit = field('knowledge-create-submit');
  const expectCreateRefusal = (needle) => {
    createSubmit.onclick();
    if (shell.pending.length)
      throw new Error(`㉒ 本地拒绝后仍发出了请求：${shell.pending.map((r) => r.path).join(' ')}`);
    if (!outcome.textContent.includes(needle))
      throw new Error(`㉒ 期望创建被本地拒绝「${needle}」，实际「${outcome.textContent.slice(0, 140)}」`);
  };

  // (a) Local refusals: the page never invents the facts only the operator has.
  const title = field('knowledge-title');
  const statement = field('knowledge-statement');
  const appliesTo = field('knowledge-applies-to');
  const license = field('knowledge-license');
  const rights = field('knowledge-rights');
  const clientAsset = field('knowledge-client-asset');
  const thirdParty = field('knowledge-third-party');
  const redaction = field('knowledge-redaction');
  const sha = field('knowledge-source-sha');
  const job = field('knowledge-job');
  const operation = field('knowledge-operation');
  const evidence = field('knowledge-evidence');
  field('knowledge-type').value = 'METHOD';
  if (sha.value !== 'c'.repeat(40))
    throw new Error('㉒ 来源修订必须只从读回的 head_sha 预填，不能凭空生成');
  if (clientAsset.value !== '' || thirdParty.value !== '')
    throw new Error('㉒ 资产布尔不得预选：absence 与 false 是不同的记录');
  expectCreateRefusal('标题为空');
  title.value = '色数上限';
  expectCreateRefusal('正文为空');
  statement.value = '四色以上先打样验证';
  expectCreateRefusal('没有任何适用设计域');
  appliesTo.value = 'packaging, print';
  license.value = 'project-internal';
  expectCreateRefusal('未选择权利门状态');
  rights.value = 'CHECKED';
  expectCreateRefusal('未声明是否包含客户素材');
  clientAsset.value = 'false';
  expectCreateRefusal('未声明是否包含第三方素材');
  thirdParty.value = 'false';
  sha.value = 'xyz';
  expectCreateRefusal('来源修订不是 40-64 位小写十六进制');
  sha.value = 'a'.repeat(40);
  // 编号的三个状态各说一句：没选、选了不使用却还留着输入、选了填写却空着。
  // 「没填」与「声明没有」在服务端是两个不同的事实（前者 400，后者存成 UNUSED），页面不能把它们
  // 压成同一条拒绝，也不能让操作者靠背一个魔法字符串来表达后者。
  const jobMode = field('knowledge-job-mode');
  const operationMode = field('knowledge-operation-mode');
  expectCreateRefusal('未声明 job_id 的来源');
  jobMode.value = 'fill';
  jobMode.onchange();
  if (job.disabled) throw new Error('㉒ 选择「我来填写」后填写框必须可用');
  expectCreateRefusal('job_id 为空：选了「我来填写」');
  job.value = 'job-a';
  expectCreateRefusal('未声明 operation_id 的来源');
  operationMode.value = 'unused';
  operationMode.onchange();
  if (!operation.disabled)
    throw new Error('㉒ 声明不使用时填写框应禁用（但已输入的内容不得被清空）');
  // 空着 + 不使用 = 一个说得过去的声明：本地不再拒绝编号，下一道坎是证据摘要。
  expectCreateRefusal('evidence_sha256 必须是');
  operation.value = 'op-7';
  expectCreateRefusal('operation_id 冲突：已选择「不使用」');
  operation.value = '';
  operationMode.value = 'fill';
  operationMode.onchange();
  if (operation.disabled) throw new Error('㉒ 改回「我来填写」后填写框仍被锁着');
  expectCreateRefusal('operation_id 为空：选了「我来填写」');
  operation.value = 'op-7';
  expectCreateRefusal('evidence_sha256 必须是');
  evidence.value = 'sha256:' + '9'.repeat(64);
  clientAsset.value = 'true';
  expectCreateRefusal('必须填写脱敏说明');
  redaction.value = '只保留色值与版式，不含客户品牌名';

  // (b) One click, one POST, exactly the seven closed-contract keys.
  createSubmit.onclick();
  const created = shell.pending.splice(0, shell.pending.length);
  if (created.length !== 1)
    throw new Error(`㉒ 一次创建点击发出了 ${created.length} 个请求`);
  if (created[0].path !== '/api/projects/p1/knowledge-candidates'
    || created[0].init.method !== 'POST')
    throw new Error(`㉒ 创建打到了 ${created[0].init.method} ${created[0].path}`);
  const createBody = JSON.parse(created[0].init.body);
  if (!sameKeys(Object.keys(createBody), ['candidate_id', 'candidate_type', 'source',
    'rights', 'payload', 'created_at', 'revocation_entrypoint']))
    throw new Error(`㉒ 创建体键集合不符：${Object.keys(createBody).join(',')}`);
  if ('schemaVersion' in createBody)
    throw new Error('㉒ 创建体带了 schemaVersion：服务端按未知属性拒绝');
  if (createBody.created_at !== null)
    throw new Error('㉒ created_at 必须发 null 让服务用自己的时钟');
  if (createBody.revocation_entrypoint !== 'design-lab/knowledge/revoke')
    throw new Error(`㉒ revocation_entrypoint 不符：${createBody.revocation_entrypoint}`);
  if (!/^kc-[0-9a-f]{1,32}$/.test(createBody.candidate_id))
    throw new Error(`㉒ candidate_id 形状不符：${createBody.candidate_id}`);
  if (createBody.candidate_type !== 'METHOD')
    throw new Error(`㉒ 所选类型没有原样送出：${createBody.candidate_type}`);
  if (!sameKeys(Object.keys(createBody.source),
    ['design_lab_sha', 'job_id', 'operation_id', 'evidence_sha256'])
    || createBody.source.job_id !== 'job-a'
    || createBody.source.operation_id !== 'op-7'
    || createBody.source.design_lab_sha !== 'a'.repeat(40)
    || createBody.source.evidence_sha256 !== 'sha256:' + '9'.repeat(64))
    throw new Error(`㉒ source 形状不符：${JSON.stringify(createBody.source)}`);
  if (!sameKeys(Object.keys(createBody.rights),
    ['license_id', 'rights_gate_state', 'contains_client_asset',
      'contains_third_party_asset', 'redaction_note'])
    || createBody.rights.contains_client_asset !== true
    || createBody.rights.contains_third_party_asset !== false
    || createBody.rights.redaction_note !== '只保留色值与版式，不含客户品牌名')
    throw new Error(`㉒ rights 形状不符：${JSON.stringify(createBody.rights)}`);
  if (!sameKeys(Object.keys(createBody.payload), ['title', 'statement', 'applies_to'])
    || JSON.stringify(createBody.payload.applies_to) !== JSON.stringify(['packaging', 'print']))
    throw new Error(`㉒ payload 形状不符：${JSON.stringify(createBody.payload)}`);
  const firstId = createBody.candidate_id;

  // (c) An identical resend replays the id; a changed document must not reuse it.
  createSubmit.onclick();
  const resent = shell.pending.splice(0, shell.pending.length);
  if (resent.length !== 1 || JSON.parse(resent[0].init.body).candidate_id !== firstId)
    throw new Error('㉒ 完全相同的重复提交换了 candidate_id：服务端会把一次主张记成两条');
  statement.value = '四色以上先打样验证（补：夜间）';
  createSubmit.onclick();
  const changed = shell.pending.splice(0, shell.pending.length);
  if (changed.length !== 1)
    throw new Error(`㉒ 改动后的重发发出了 ${changed.length} 个请求`);
  const changedBody = JSON.parse(changed[0].init.body);
  if (changedBody.candidate_id === firstId)
    throw new Error('㉒ 改过的正文仍沿用旧 candidate_id：页面在发注定被拒的写');

  // (d) Success reads the projection back and keeps the candidate pending.
  changed[0].resolve(response({ candidate_id: changedBody.candidate_id }));
  await flush();
  const afterCreate = shell.pending.splice(0, shell.pending.length);
  if (afterCreate.length !== 1 || !afterCreate[0].path.includes('/knowledge-candidates'))
    throw new Error(`㉒ 创建成功后应读回一次知识投影，实际 ${
      afterCreate.map((r) => r.path).join(' ')}`);
  afterCreate[0].resolve(response(KNOWLEDGE_READBACK));
  await flush();
  if (!outcome.textContent.includes('已记录一条候选')
    || !outcome.textContent.includes('PENDING_HUMAN_APPROVAL'))
    throw new Error(`㉒ 创建成功后没有说明候选仍需具名裁决：${outcome.textContent.slice(0, 180)}`);

  // (d2) 显式「不使用」必须真的上线路：发的是字面量 UNUSED，不是把空串丢给服务端去猜意图。
  operation.value = '';
  operationMode.value = 'unused';
  operationMode.onchange();
  createSubmit.onclick();
  const declined = shell.pending.splice(0, shell.pending.length);
  if (declined.length !== 1)
    throw new Error(`㉒ 一次「不使用」提交发出了 ${declined.length} 个请求`);
  const declinedBody = JSON.parse(declined[0].init.body);
  if (declinedBody.source.operation_id !== 'UNUSED')
    throw new Error(`㉒ 「不使用」没有发送字面量 UNUSED：${
      JSON.stringify(declinedBody.source)}`);
  if (declinedBody.source.job_id !== 'job-a')
    throw new Error(`㉒ 一条编号声明不使用，把另一条填写中的编号也带走了：${
      JSON.stringify(declinedBody.source)}`);
  declined[0].resolve(response({ candidate_id: declinedBody.candidate_id }));
  await flush();
  const afterDecline = shell.pending.splice(0, shell.pending.length);
  if (afterDecline.length !== 1 || !afterDecline[0].path.includes('/knowledge-candidates'))
    throw new Error('㉒ 「不使用」的候选写入后没有读回一次投影');
  afterDecline[0].resolve(response(KNOWLEDGE_READBACK));
  await flush();

  // (e) Human review: no anonymous approve, no reasonless reject, exactly six keys.
  const reviewTarget = field('knowledge-review-target');
  const decision = field('knowledge-decision');
  const reviewer = field('knowledge-reviewer');
  const note = field('knowledge-note');
  const reason = field('knowledge-reason');
  let reviewSubmit = field('knowledge-review-submit');
  reviewTarget.value = KNOWLEDGE_CANDIDATES[0].candidate_id;
  reviewSubmit.onclick();
  if (shell.pending.length || !outcome.textContent.includes('裁决人未署名'))
    throw new Error('㉒ 未署名的人工裁决必须被本地拒绝且不发请求');
  reviewer.value = 'Dana';
  decision.value = 'REJECT';
  reviewSubmit.onclick();
  if (shell.pending.length || !outcome.textContent.includes('驳回必须说明原因'))
    throw new Error('㉒ 无原因的驳回必须被本地拒绝且不发请求');
  decision.value = 'APPROVE';
  reason.value = '理由只属于驳回';
  reviewSubmit.onclick();
  const reviewed = shell.pending.splice(0, shell.pending.length);
  if (reviewed.length !== 1)
    throw new Error(`㉒ 一次裁决点击发出了 ${reviewed.length} 个请求`);
  if (reviewed[0].path !== `/api/projects/p1/knowledge-candidates/${
    KNOWLEDGE_CANDIDATES[0].candidate_id}/review`
    || reviewed[0].init.method !== 'POST')
    throw new Error(`㉒ 裁决打到了 ${reviewed[0].path}`);
  const reviewBody = JSON.parse(reviewed[0].init.body);
  if (!sameKeys(Object.keys(reviewBody), ['decision', 'reviewer_id', 'reviewer_kind',
    'reviewed_at', 'note', 'reason']))
    throw new Error(`㉒ 裁决体键集合不符：${Object.keys(reviewBody).join(',')}`);
  if (reviewBody.reviewer_kind !== 'human')
    throw new Error('㉒ reviewer_kind 不是 human：服务端会以 KNOWLEDGE_HUMAN_REVIEW_REQUIRED 拒绝');
  if (reviewBody.decision !== 'APPROVE' || reviewBody.reviewer_id !== 'Dana')
    throw new Error(`㉒ 裁决内容不符：${JSON.stringify(reviewBody)}`);
  if (reviewBody.note !== null || reviewBody.reason !== null)
    throw new Error('㉒ 未填写的可选字段必须发 null，不能编一个空串');
  if (!/^\d{4}-\d{2}-\d{2}T/.test(reviewBody.reviewed_at ?? ''))
    throw new Error('㉒ reviewed_at 必须是 RFC3339 形状的浏览器时钟');
  reviewed[0].resolve(response({ review_state: 'APPROVED' }));
  await flush();
  const afterReview = shell.pending.splice(0, shell.pending.length);
  if (afterReview.length !== 1 || !afterReview[0].path.includes('/knowledge-candidates'))
    throw new Error('㉒ 裁决成功后没有读回知识投影');
  afterReview[0].resolve(response(KNOWLEDGE_READBACK));
  await flush();
  if (!outcome.textContent.includes('已记录批准')
    || !outcome.textContent.includes('这条候选没有被发送'))
    throw new Error(`㉒ 批准后的说法把 export_ready 说成了发送：${outcome.textContent.slice(0, 180)}`);

  // (e2) 导出出口在界面上可达：一行候选一个按钮，被合同阻止的两行是禁用的，能读回的那一行
  // 发一次 GET，并把两份投影、编号回显与出站事实原样上屏——而且不得说成"已发送"。
  const exportBody = byElementId(view, 'knowledge-export-body');
  const exportButtons = [0, 1, 2].map((index) => field(`knowledge-export-${String(index)}`));
  if (exportButtons[0].attributes.has('disabled') === false
    || exportButtons[1].attributes.has('disabled') === false)
    throw new Error('㉒ export_ready=false 的行必须禁用导出按钮，而不是给一次注定被拒的点击');
  if (exportButtons[2].attributes.has('disabled'))
    throw new Error('㉒ export_ready=true 的行不该被挡住：本地合同允许导出就该能读回文档');
  if (!exportButtons[0].textContent.includes('本条被合同阻止'))
    throw new Error(`㉒ 禁用按钮要说出被挡住的是这一条：${exportButtons[0].textContent}`);
  if (!exportButtons[2].textContent.includes('不发送'))
    throw new Error('㉒ 按钮文字不得只写「导出」，那会被读成已经交付');
  exportButtons[2].onclick();
  await flush();
  const exportCall = shell.pending.splice(0, shell.pending.length);
  if (exportCall.length !== 1
    || exportCall[0].path !== `/api/projects/p1/knowledge-candidates/${
      KNOWLEDGE_CANDIDATES[2].candidate_id}/export`)
    throw new Error(`㉒ 导出读回打到了 ${exportCall.map((r) => r.path).join(' ')}`);
  if (exportCall[0].init && exportCall[0].init.method !== undefined
    && exportCall[0].init.method !== 'GET')
    throw new Error('㉒ 导出读回必须是 GET：它产出文档，不投递文档');
  exportCall[0].resolve(response(KNOWLEDGE_EXPORT_ENVELOPE));
  await flush();
  const exportText = exportBody.textContent;
  for (const needle of [
    'design-lab/assurance-knowledge-candidate-export-envelope/v1',
    'design-lab/assurance-knowledge-candidate/v2',
    'design-lab/candidate-knowledge/v1',
    'source_id job-1:UNUSED',
    'USER_SUPPLIED', 'EXPLICITLY_UNUSED',
    'NOT_CONNECTED', 'sent_count=0', 'bytes=1234',
    '传输未实现',
  ]) {
    if (!exportText.includes(needle))
      throw new Error(`㉒ 导出文档面板缺「${needle}」：${exportText.slice(0, 260)}`);
  }
  if (/已发送|发送成功|delivered/i.test(exportText))
    throw new Error(`㉒ 导出面板把一次读回说成了一次投递：${exportText.slice(0, 200)}`);
  // 409 是产品答案：拒绝要留下它自己的原因，而不是变成一个空面板。
  exportButtons[2].onclick();
  await flush();
  const refused = shell.pending.splice(0, shell.pending.length);
  refused[0].resolve(response({ status: 'ERROR', error: 'CANDIDATE_EXPORT_REFUSED',
    detail: 'candidate is PENDING_HUMAN_APPROVAL; only a named human approval releases it' },
  false, 409));
  await flush();
  const refusalText = exportBody.textContent;
  if (!refusalText.includes('导出被拒绝')
    || !refusalText.includes('CANDIDATE_EXPORT_REFUSED')
    || !refusalText.includes('PENDING_HUMAN_APPROVAL'))
    throw new Error(`㉒ 拒绝没有点名是哪道门拦住的：${refusalText.slice(0, 220)}`);

  // (f) Revocation writes a local receipt; it cannot recall a copy.
  const revokeTarget = field('knowledge-revoke-target');
  const revokeReason = field('knowledge-revoke-reason');
  const revokedBy = field('knowledge-revoked-by');
  const revokeSubmit = field('knowledge-revoke-submit');
  revokeTarget.value = KNOWLEDGE_CANDIDATES[0].candidate_id;
  revokeSubmit.onclick();
  if (shell.pending.length || !outcome.textContent.includes('撤销必须说明原因'))
    throw new Error('㉒ 无原因的撤销必须被本地拒绝且不发请求');
  revokeReason.value = '事实已经变化';
  revokeSubmit.onclick();
  if (shell.pending.length || !outcome.textContent.includes('撤销必须具名'))
    throw new Error('㉒ 未署名的撤销必须被本地拒绝且不发请求');
  revokedBy.value = 'Eve';
  revokeSubmit.onclick();
  const revoked = shell.pending.splice(0, shell.pending.length);
  if (revoked.length !== 1)
    throw new Error(`㉒ 一次撤销点击发出了 ${revoked.length} 个请求`);
  if (revoked[0].path !== `/api/projects/p1/knowledge-candidates/${
    KNOWLEDGE_CANDIDATES[0].candidate_id}/revoke`
    || revoked[0].init.method !== 'POST')
    throw new Error(`㉒ 撤销打到了 ${revoked[0].path}`);
  const revokeBody = JSON.parse(revoked[0].init.body);
  if (!sameKeys(Object.keys(revokeBody), ['reason', 'revoked_by', 'revoked_at']))
    throw new Error(`㉒ 撤销体键集合不符：${Object.keys(revokeBody).join(',')}`);
  if (revokeBody.revoked_at !== null || revokeBody.revoked_by !== 'Eve'
    || revokeBody.reason !== '事实已经变化')
    throw new Error(`㉒ 撤销内容不符：${JSON.stringify(revokeBody)}`);
  revoked[0].resolve(response({ revocation_state: 'REVOKED' }));
  await flush();
  const afterRevoke = shell.pending.splice(0, shell.pending.length);
  if (afterRevoke.length !== 1 || !afterRevoke[0].path.includes('/knowledge-candidates'))
    throw new Error('㉒ 撤销成功后没有读回知识投影');
  afterRevoke[0].resolve(response(KNOWLEDGE_READBACK));
  await flush();
  if (!outcome.textContent.includes('已写入撤销回执并阻止导出')
    || !outcome.textContent.includes('不能召回'))
    throw new Error(`㉒ 撤销后的说法越过了本机回执的边界：${outcome.textContent.slice(0, 200)}`);

  // (g) A payload the seam had to refill is unread: no forms, no zero counts.
  const unread = await openKnowledgeView({ ...KNOWLEDGE_READBACK,
    candidates: undefined, conflicts: undefined });
  const unreadText = ((byElementId(unread.view, 'knowledge-panel')?.textContent) || '')
    .replace(/\s+/g, ' ');
  if (!unreadText.includes('未读回') || !unreadText.includes('candidates')
    || !unreadText.includes('响应缺少'))
    throw new Error(`㉒ 缺集合必须点名未读回的字段：${unreadText.slice(0, 240)}`);
  if (unreadText.includes('共 0 条候选') || unreadText.includes('共 3 条候选'))
    throw new Error('㉒ 未读回被画成了候选数');
  for (const control of ['knowledge-create-submit', 'knowledge-review-submit',
    'knowledge-revoke-submit'])
    if (byElementId(unread.view, control))
      throw new Error(`㉒ 未读回时仍提供了 ${control}：不能对没有读到的记录动手`);
}

console.log('ok: ㉒ 知识回执与反馈：构建只读一次零写、状态/新鲜度/导出/出站边界全部来自读回、'
  + '未建的一半写在可见文字里、创建本地拒绝不替人补事实、7 键创建体（无 schemaVersion、'
  + 'created_at=null）、相同重发沿用 candidate_id 而改动换新、6 键 human 裁决与 3 键撤销、'
  + '成功后读回来自服务端、未读回不画候选数也不提供裁决/撤销控件');

// ㉑ D06 截止与取消。此前 `fetch` 没有 signal：服务接受了连接然后沉默，页面就永远转圈，
// 而"还在算"与"已经没了"在界面上分不出来。现在三种结局必须彼此可辨——读超时、写结果未知、
// 切页取消——因为操作员该做的事完全不同。写请求**不许**被说成失败：服务可能已经落库。
{
  const api = shell.context.api;
  const capture = async (promise) => {
    try { await promise; return null; } catch (error) { return error; }
  };
  const sleep = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

  // (1) 悬挂的读：有截止时间，且措辞说明无副作用、可直接重试
  const hangingRead = capture(api('/projects/hangs', undefined, { timeoutMs: 20 }));
  await flush();
  if (shell.pending.length !== 1) throw new Error('读超时用例没有发出请求');
  shell.pending.pop();               // 永不 resolve：就像服务接完连接就沉默
  const readError = await hangingRead;
  if (!readError || !/读取超时/.test(readError.message))
    throw new Error(`读超时没有按读口径报：${readError && readError.message}`);
  if (!/没有产生任何写入/.test(readError.message) || !/可以直接重试/.test(readError.message))
    throw new Error('读超时必须写明无副作用且可安全重试');
  if (readError.outcomeUnknown === true)
    throw new Error('读超时被当成了"写结果未知"');

  // (2) 丢答复的写：结果是"待核对"，不是失败，且明令不许盲目重发
  const hangingWrite = capture(api('/projects/x/briefs', { title: 'a' }, { timeoutMs: 20 }));
  await flush();
  shell.pending.pop();
  const writeError = await hangingWrite;
  // Ducked-typed on purpose: the error class is a lexical binding in the bundle, so it is
  // not reachable from this context and `instanceof` here would test against `undefined`.
  if (!(writeError && writeError.outcomeUnknown === true))
    throw new Error(`写超时必须是"结果待核对"这一类：${writeError && writeError.message}`);
  if (!/结果待核对/.test(writeError.message) || !/不要不看读回就重发/.test(writeError.message))
    throw new Error('写超时必须写明结果待核对并禁止盲目重发');
  // Precise, because a bare /失败/ also matches the sentence that forbids calling it one:/n  // the message must not CLAIM a failure ("已失败" / "提交失败" / "写入失败").
  if (/(已失败|提交失败|写入失败)/.test(writeError.message))
    throw new Error(`写超时不得被说成失败：${writeError.message}`);
  if (!/不是失败/.test(writeError.message))
    throw new Error('写超时必须明说它不是失败');

  // (3) 切页取消读，但**不**取消写：切页并不会撤销一次提交
  const abandoned = capture(api('/projects'));
  await flush();
  const readRequest = shell.pending.pop();
  shell.context.cancelPendingReads();
  await flush();
  const cancelled = await abandoned;
  if (!cancelled || !/页面已切换/.test(cancelled.message))
    throw new Error(`切页没有取回读请求：${cancelled && cancelled.message}`);
  if (readRequest.init.signal.aborted !== true)
    throw new Error('切页没有真的中止读请求的 signal');

  const liveWrite = capture(api('/projects/x/briefs', { title: 'b' }));
  await flush();
  const writeRequest = shell.pending.pop();
  shell.context.cancelPendingReads();
  await flush();
  if (writeRequest.init.signal.aborted === true)
    throw new Error('切页把写请求也中止了：一次提交不会因为换页而撤销');
  writeRequest.resolve(response({ task: {} }));
  if (await liveWrite !== null)
    throw new Error('写请求本该照常完成，却被判成出错');

  // (4) 401 仍清会话（D06 不许改动这条既有行为）。观察的是应用自己的输出面——连接徽标——
  // 而不是内部 `token` 变量：后者是词法绑定，从这里既读不到也不该读到。
  await sleep(1);
  const badge = shell.context.document.getElementById('connection');
  badge.textContent = '已连接';
  const refused = capture(api('/projects'));
  await flush();
  shell.pending.pop().resolve(response({ error: 'UNAUTHORIZED' }, false, 401));
  await refused;
  if (badge.textContent !== '未连接')
    throw new Error(`401 没有把会话清掉（徽标仍是 ${badge.textContent}）`);

  // (5) 不带参数时也必须真的装了截止时间：信号存在即证明"默认有 deadline"，
  // 而不去读那两个常量（同样是词法绑定，从 context 取不到）。
  const defaultedRead = capture(api('/projects'));
  await flush();
  if (!shell.pending.pop().init.signal) throw new Error('默认读请求没有装截止信号');
  shell.context.cancelPendingReads();
  await defaultedRead;
  const defaultedWrite = capture(api('/projects/x/briefs', { title: 'c' }));
  await flush();
  if (!shell.pending.pop().init.signal) throw new Error('默认写请求没有装截止信号');
  shell.context.cancelPendingReads();
  await defaultedWrite;

  // (6) 正文阶段也必须被截止时间与取消管住（owner 审计 2026-10-26 第 3 条）。以前头部一到就
  // `clearTimeout` 并摘掉监听，于是"答得快、正文慢慢滴"能无限越过预算。浏览器的契约是 signal 在
  // 正文期间触发会让 `response.json()` 以 AbortError 落定——替身必须照做，否则这段测不到。
  // 每一条等待都带看门狗：无人管辖的实现要**判红**，而不是把测试挂死——挂死既测不出回归，
  // 也会让 CI 把它当成超时环境噪声。三条的失败先收下、最后一起报：第一条就 throw 的话，后两条
  // 在拿旧实现跑反证时根本没被执行过，那就只证明了三分之一的修正。
  const bodyPhaseFailures = [];
  const expectBody = (label, ok, detail) => {
    if (!ok) bodyPhaseFailures.push(`${label}（${detail}）`);
  };
  const withWatchdog = (promise, ms, label) => Promise.race([
    promise,
    new Promise((_resolve, reject) => setTimeout(() => reject(
      new Error(`${label}：${ms}ms 内没有落定，说明截止时间或取消根本没有管到正文`)), ms)),
  ]);
  const bodyHang = (signal) => ({
    ok: true, status: 200,
    json: () => new Promise((_resolve, reject) => {
      const onAbort = () => {
        const error = new Error('The operation was aborted.');
        error.name = 'AbortError';
        reject(error);
      };
      if (signal.aborted) onAbort();
      else signal.addEventListener('abort', onAbort, { once: true });
    }),
  });

  const slowBodyRead = capture(withWatchdog(
    api('/projects/slow-body', undefined, { timeoutMs: 20 }), 3000, '正文慢过预算后读请求无人收尾'));
  await flush();
  const bodyRead = shell.pending.pop();
  bodyRead.resolve(bodyHang(bodyRead.init.signal));
  const bodyReadError = await slowBodyRead;
  expectBody('正文慢过预算要按读超时落定',
    Boolean(bodyReadError) && /读取超时/.test(bodyReadError.message),
    bodyReadError ? bodyReadError.message : '承诺一直没有落定');
  expectBody('正文超时不许报成连接或解析问题',
    Boolean(bodyReadError) && !/无法连接|无法解析/.test(bodyReadError.message),
    bodyReadError ? bodyReadError.message : '没有错误可查');

  // (7) 正文没读完就切页：读要按「页面已切换」落定，而不是变成一条无类错误
  const midBodyRead = capture(withWatchdog(
    api('/projects/aborted-body', undefined, { timeoutMs: 5000 }), 3000,
    '正文期间切页却收不到取消'));
  await flush();
  const midBodyRequest = shell.pending.pop();
  midBodyRequest.resolve(bodyHang(midBodyRequest.init.signal));
  await flush();
  shell.context.cancelPendingReads();
  const midBodyError = await midBodyRead;
  expectBody('正文期间切页要收到取消',
    Boolean(midBodyError) && /页面已切换/.test(midBodyError.message),
    midBodyError ? midBodyError.message : '承诺一直没有落定');

  // (8) 写：头部到了、正文丢了，仍然是"结果待核对"，不许被说成失败
  const lostBodyWrite = capture(withWatchdog(
    api('/projects/x/briefs', { title: 'd' }, { timeoutMs: 20 }), 3000,
    '正文期丢答复的写无人收尾'));
  await flush();
  const bodyWrite = shell.pending.pop();
  bodyWrite.resolve(bodyHang(bodyWrite.init.signal));
  const lostWriteError = await lostBodyWrite;
  expectBody('正文期丢答复的写要落到结果待核对',
    Boolean(lostWriteError) && lostWriteError.outcomeUnknown === true,
    lostWriteError ? lostWriteError.message : '承诺一直没有落定');
  expectBody('正文期丢答复的写不许说成失败',
    Boolean(lostWriteError) && !/(已失败|提交失败|写入失败)/.test(lostWriteError.message),
    lostWriteError ? lostWriteError.message : '没有错误可查');

  if (bodyPhaseFailures.length)
    throw new Error(`㉑ 正文阶段无人管辖，${bodyPhaseFailures.length} 项判红：`
      + bodyPhaseFailures.join(' | '));
}

console.log('ok: ㉑ D06 截止与取消：读超时（无副作用、可重试）与写超时（结果待核对、禁止盲目重发）'
  + '彼此可辨，切页只取消读不取消写，401 仍清会话，默认预算读 15s / 写 45s，'
  + '且截止时间与取消管到正文本身（慢正文按读超时、正文期切页按已取消、正文期丢答复的写按待核对）');

// ㉓ DL-KB-02/03/04 · 知识与提示词库。这一块要证明的不是"页面存在"：搜索是主入口、类目词表
// 来自读回、列表不带正文/哈希/路径、详情按需读回、新增与修订都是真实 POST 且一次点击只发一次、
// 写后立刻按服务返回的编号读回、无命中只解释不编造。㉑ 的最后一步按 401 清了会话，所以先重连：
// 在登出状态跑完整的新增流程，证明的是别的东西。
{
  const tokenField = shell.elements.get('token');
  tokenField.value = 'b'.repeat(64);
  const reconnect = shell.elements.get('connect-form').onsubmit({ preventDefault() {} });
  shell.pending.shift().resolve(response(projectsEnvelope([])));
  await reconnect;
  await flush();

  const routeView = () => shell.elements.get('route-view');
  const text = (node) => (node?.textContent || '').replace(/\s+/g, ' ');
  const sameKeys = (actual, expected) =>
    JSON.stringify([...actual].sort()) === JSON.stringify([...expected].sort());
  const expectQuiet = (label) => {
    if (shell.pending.length)
      throw new Error(`㉓ ${label}后仍有未答复的请求：${shell.pending.map((r) => r.path).join(' ')}`);
  };
  expectQuiet('重连');

  const VOCABULARY = [
    { value: 'STANDARD', label: '规范' }, { value: 'METHOD', label: '方法' },
    { value: 'PROMPT', label: '提示词' }, { value: 'MODEL_GUIDE', label: '模型指南' },
    { value: 'RECIPE', label: '配方' }, { value: 'CASE', label: '案例' },
  ];
  const SOURCE = {
    sourceId: 'internal-storyboard', origin: 'D:/guides/storyboard.md', author: 'ALEX-DESK',
    license: 'project-internal', licenseStatus: 'reviewed',
    allowedUsage: '仅本项目内部使用', citationScope: '内部引用，不转引',
    version: '2026-10', observedAt: '2026-10-23T09:00:00+00:00',
    contentHash: 'sha256:' + 'd'.repeat(64), verification: 'UNVERIFIED',
  };
  const entryView = (over = {}) => ({
    schemaVersion: 'design-lab/knowledge-entry/v1',
    knowledge_entry_id: 'kentry-1', revision: 2, entry_type: 'METHOD',
    title: '分镜拆解三步法', summary: '把一场戏拆成可拍摄的镜头',
    domain_tags: ['film', 'animation'], task_tags: ['storyboard'], target_tools: ['photoshop'],
    body: '先定机位，再定景别，最后核对轴线。',
    applicability: '实拍与动画分镜', limits: '不适用于纯文字脚本；镜头数超过 80 时先分层。',
    source: { ...SOURCE }, related_capability_ids: [],
    content_sha256: 'sha256:' + 'a'.repeat(64), supersedes: null, recommended: true,
    created_at: '2026-10-23T09:00:00+00:00', created_by: 'ALEX',
    claims_not_made: ['保存不等于核验'],
    ...over,
  });
  const rowView = (over = {}) => ({
    knowledge_entry_id: 'kentry-1', revision: 2, latest_revision: 2,
    recommended_revision: 1, recommended_is_latest: false, entry_type: 'METHOD',
    title: '分镜拆解三步法', summary: '把一场戏拆成可拍摄的镜头',
    domain_tags: ['film', 'animation'], task_tags: ['storyboard'], target_tools: ['photoshop'],
    status: 'ACTIVE', content_sha256: 'sha256:' + 'a'.repeat(64),
    updated_at: '2026-10-23T09:00:00+00:00', license: 'project-internal',
    license_status: 'reviewed', source_id: 'internal-storyboard', source_version: '2026-10',
    matched_fields: [], matched_terms: [],
    ...over,
  });
  const libraryView = (over = {}) => ({
    schemaVersion: 'design-lab/knowledge-library/v1', query: null,
    filters: { type: null, domain: null, task: null, target: null },
    entryTypes: VOCABULARY, licenseStates: ['reviewed', 'unknown', 'reference-only'],
    strategy: 'BROWSE', matched_terms: [], total: 2, offset: 0, limit: 50, returned: 2,
    next_offset: null, explanation: null,
    entries: [rowView(), rowView({
      knowledge_entry_id: 'kentry-2', revision: 2, recommended_revision: 2,
      recommended_is_latest: true, entry_type: 'PROMPT',
      title: '粒子光效提示词模板', summary: '给粒子光效写可复现的提示词',
      target_tools: ['after-effects'],
    })],
    index: { rows: 2, indexed: 2, rebuilt_at: '2026-10-23T09:05:00+00:00' },
    does_not_say: ['保存不等于核验', '索引不是第二真值'],
    ...over,
  });

  // (1) 首屏 = 一次检索读回。搜索框是主视觉，但词表与许可状态必须来自这一份答案。
  shell.window.location.hash = '#/knowledge';
  shell.dispatchHashchange();
  await flush();
  const firstReads = shell.pending.splice(0, shell.pending.length);
  if (firstReads.length !== 1)
    throw new Error(`㉓ 知识与提示词库首屏应只发一次检索读回，实际 ${firstReads.length} 次`);
  const firstRead = firstReads[0];
  if (firstRead.init.method !== 'GET' || !firstRead.path.startsWith('/api/knowledge-entries/search?'))
    throw new Error(`㉓ 首屏读回打到了 ${firstRead.init.method} ${firstRead.path}`);
  const firstParams = new URLSearchParams(firstRead.path.split('?')[1]);
  if (firstParams.get('offset') !== '0' || firstParams.get('limit') !== '50')
    throw new Error(`㉓ 首屏分页不诚实：offset=${firstParams.get('offset')} limit=${firstParams.get('limit')}`);
  if (firstParams.has('q') || firstParams.has('type'))
    throw new Error(`㉓ 首屏不该带检索词或类型筛选：${firstRead.path}`);
  firstRead.resolve(response(libraryView({ total: 52, returned: 2, next_offset: 50 })));
  await flush();

  const view = routeView();
  const results = byElementId(view, 'kb-results');
  if (!byElementId(view, 'kb-query')) throw new Error('㉓ 搜索框没有渲染');
  const typeSelect = byElementId(view, 'kb-type');
  if (!typeSelect || typeSelect.options.length !== VOCABULARY.length + 1)
    throw new Error(`㉓ 类型筛选应来自读回的 ${VOCABULARY.length} 项词表，实际 ${typeSelect?.options.length}`);
  if (typeSelect.options[1].textContent !== '规范')
    throw new Error(`㉓ 类型词表不是服务给的标签：${typeSelect.options[1].textContent}`);
  if (!results || results.children.length !== 2)
    throw new Error(`㉓ 检索答案应有 2 行，实际 ${results?.children.length}`);
  const metaText = text(view);
  if (!metaText.includes('共 52 条') || !metaText.includes('浏览模式')
    || !metaText.includes('策略 BROWSE') || !metaText.includes('索引 2/2'))
    throw new Error(`㉓ 检索说明不完整：${metaText.slice(0, 240)}`);
  const listText = text(results);
  if (!listText.includes('分镜拆解三步法') || !listText.includes('适用：photoshop')
    || !listText.includes('r2') || !listText.includes('ACTIVE')
    || !listText.includes('推荐 r1 · 非最新'))
    throw new Error(`㉓ 行字段不齐（标题/用途/目标/修订/状态/推荐）：${listText.slice(0, 240)}`);
  const latestRowText = text(results.children[1]);
  if (!latestRowText.includes('最新 r2 · 推荐版本'))
    throw new Error('㉓ 推荐即最新的一行没有合并成一个修订标记：' + latestRowText);
  if (latestRowText.includes('推荐 r2') || (latestRowText.match(/r2/g) || []).length !== 1)
    throw new Error('㉓ 推荐即最新的一行重复了修订号：' + latestRowText);
  if (listText.includes('先定机位') || listText.includes('sha256:')
    || listText.includes('D:/guides/storyboard.md'))
    throw new Error('㉓ 列表里出现了正文/哈希/路径：这些只应在详情里');
  if (!metaText.includes('服务声明：保存不等于核验；索引不是第二真值'))
    throw new Error('㉓ does_not_say 没有原样上屏');
  expectQuiet('首屏');

  // 初始页 ≤50 且下一页可继续：追加而不是替换，next_offset 为空时按钮必须消失。
  const moreHost = byElementId(view, 'kb-more');
  const moreButton = findIn(moreHost, (node) => node?.tagName === 'BUTTON'
    && String(node.textContent).startsWith('加载更多'));
  if (!moreButton) throw new Error('㉓ next_offset 非空时必须给出「加载更多」');
  if (!String(moreButton.textContent).includes('已显示 2 / 共 52'))
    throw new Error(`㉓ 加载更多没有报进度：${moreButton.textContent}`);
  moreButton.onclick();
  await flush();
  const pageTwo = shell.pending.splice(0, shell.pending.length);
  if (pageTwo.length !== 1) throw new Error(`㉓ 加载更多发出了 ${pageTwo.length} 个请求`);
  const pageTwoParams = new URLSearchParams(pageTwo[0].path.split('?')[1]);
  if (pageTwoParams.get('offset') !== '50' || pageTwoParams.get('limit') !== '50')
    throw new Error(`㉓ 加载更多的分页不对：${pageTwo[0].path}`);
  pageTwo[0].resolve(response(libraryView({
    total: 52, offset: 50, returned: 1, next_offset: null,
    entries: [rowView({ knowledge_entry_id: 'kentry-50', title: '第 51 条' })],
  })));
  await flush();
  if (results.children.length !== 3)
    throw new Error(`㉓ 加载更多应追加而不是替换，实际 ${results.children.length} 行`);
  if (findIn(moreHost, (node) => node?.tagName === 'BUTTON'
    && String(node.textContent).startsWith('加载更多')))
    throw new Error('㉓ next_offset 为 null 时「加载更多」必须消失');
  expectQuiet('加载更多');

  // (2) 详情按需读回：点行之前不预读，点了才发一次 GET。
  const openButton = findIn(results.children[0], (node) => node?.className === 'kb-open');
  if (typeof openButton?.onclick !== 'function') throw new Error('㉓ 行标题不是可打开的按钮');
  openButton.onclick();
  await flush();
  const detailReads = shell.pending.splice(0, shell.pending.length);
  if (detailReads.length !== 1 || detailReads[0].path !== '/api/knowledge-entries/kentry-1'
    || detailReads[0].init.method !== 'GET')
    throw new Error(`㉓ 详情读回不对：${detailReads.map((r) => `${r.init.method} ${r.path}`).join(' ')}`);
  detailReads[0].resolve(response({
    schemaVersion: 'design-lab/knowledge-entry-detail/v1',
    knowledge_entry_id: 'kentry-1', status: 'ACTIVE', latest_revision: 2,
    recommended_revision: 1, current: entryView(), recommended: entryView({ revision: 1 }),
    superseded_by: null,
    recommendation_basis: 'written-flag', recommendation_judgement: null,
    source_state: null, judgements: [],
    revisions: [
      { revision: 2, content_sha256: 'sha256:' + 'a'.repeat(64), entry_type: 'METHOD',
        title: '分镜拆解三步法', recommended: false, created_at: '2026-10-23T09:00:00+00:00',
        created_by: 'ALEX', readable: true },
      { revision: 1, content_sha256: 'sha256:' + 'c'.repeat(64), entry_type: 'METHOD',
        title: '分镜拆解两步法', recommended: true, created_at: '2026-10-22T09:00:00+00:00',
        created_by: 'ALEX', readable: true },
    ],
    unreadable_count: 0, index: { rows: 2, indexed: 2, rebuilt_at: null },
    does_not_say: ['保存不等于核验'],
  }));
  await flush();
  const detailText = text(byElementId(view, 'kb-detail'));
  for (const needle of ['先定机位', '来源与许可', 'internal-storyboard', 'project-internal',
    'sha256:' + 'a'.repeat(64), 'UNVERIFIED', '修订历史', 'r2 · 分镜拆解三步法',
    'r1 · 分镜拆解两步法', '推荐版本 r1（不是最新 r2）', '保存不等于核验'])
    if (!detailText.includes(needle))
      throw new Error(`㉓ 详情没有按读回上屏「${needle}」：${detailText.slice(0, 300)}`);
  expectQuiet('详情');

  // (2b) 最新即推荐：头部合成一个「最新 r2 · 推荐版本」标记。服务在两者相同时
  // 不下发推荐副本（recommended: null），页面也不应并排再打印一次相同的修订号，
  // 更不该凭空补一个「推荐 r2」徽章或重复的推荐正文区。
  const sameButton = findIn(results.children[1], (node) => node?.className === 'kb-open');
  if (typeof sameButton?.onclick !== 'function') throw new Error('㉓ 第二行标题不是可打开的按钮');
  sameButton.onclick();
  await flush();
  const sameReads = shell.pending.splice(0, shell.pending.length);
  if (sameReads.length !== 1 || sameReads[0].path !== '/api/knowledge-entries/kentry-2')
    throw new Error(`㉓ 第二条详情读回不对：${sameReads.map((r) => r.path).join(' ')}`);
  sameReads[0].resolve(response({
    schemaVersion: 'design-lab/knowledge-entry-detail/v1',
    knowledge_entry_id: 'kentry-2', status: 'ACTIVE', latest_revision: 2,
    recommended_revision: 2,
    current: entryView({ knowledge_entry_id: 'kentry-2', entry_type: 'PROMPT',
      title: '粒子光效提示词模板' }),
    recommended: null, superseded_by: null,
    recommendation_basis: 'written-flag', recommendation_judgement: null,
    source_state: null, judgements: [],
    revisions: [
      { revision: 2, content_sha256: 'sha256:' + 'b'.repeat(64), entry_type: 'PROMPT',
        title: '粒子光效提示词模板', recommended: true,
        created_at: '2026-10-23T09:00:00+00:00', created_by: 'ALEX', readable: true },
      { revision: 1, content_sha256: 'sha256:' + 'c'.repeat(64), entry_type: 'PROMPT',
        title: '粒子光效提示词模板（初稿）', recommended: false,
        created_at: '2026-10-22T09:00:00+00:00', created_by: 'ALEX', readable: true },
    ],
    unreadable_count: 0, index: { rows: 2, indexed: 2, rebuilt_at: null },
    does_not_say: ['保存不等于核验'],
  }));
  await flush();
  const samePanel = byElementId(view, 'kb-detail');
  const sameHead = findIn(samePanel, (node) => node?.className === 'kb-badges');
  if (!sameHead) throw new Error('㉓ 同版本详情没有渲染头部徽章');
  const headText = text(sameHead);
  if (!headText.includes('最新 r2 · 推荐版本'))
    throw new Error(`㉓ 最新即推荐时头部没有合并标记：${headText}`);
  if ((headText.match(/推荐/g) || []).length !== 1 || headText.includes('推荐 r2'))
    throw new Error(`㉓ 最新即推荐时头部重复了推荐标记：${headText}`);
  const samePanelText = text(samePanel);
  if (samePanelText.includes('（不是最新 r2）') || samePanelText.includes('无推荐版本'))
    throw new Error(`㉓ 最新即推荐时出现了不该有的推荐区/无推荐徽章：${samePanelText.slice(0, 240)}`);
  expectQuiet('同版本详情');

  // (3) 新增：本地拒绝不替人补事实，一次点击只发一次真实 POST。
  byElementId(view, 'kb-new').onclick();
  const form = () => byElementId(view, 'kb-form');
  const formText = () => text(form());
  const newType = byElementId(view, 'kb-new-entry-type');
  if (!newType || newType.options.length !== VOCABULARY.length)
    throw new Error(`㉓ 新增表单的类型选项应来自同一份读回词表，实际 ${newType?.options.length}`);
  if (!formText().includes('编号由服务生成') || !formText().includes('UNVERIFIED'))
    throw new Error(`㉓ 新增表单没有说明编号来源与核验状态：${formText().slice(0, 200)}`);
  // A fresh form used to open with the vocabulary's first state selected, so an untouched 新增
  // claimed 许可状态=reviewed while 许可 was still empty -- and the store refused that pair
  // with KNOWLEDGE_LICENSE_UNKNOWN_CONTRADICTION (found by the browser walk, 2026-10-24).
  // The default now has to be the state that says nobody has looked.
  if (byElementId(view, 'kb-new-license-status').value !== 'unknown')
    throw new Error('㉓ 新增表单替用户预选了许可状态：'
      + byElementId(view, 'kb-new-license-status').value);
  newType.value = 'METHOD';
  const submitNew = findIn(form(), (node) => node?.className === 'primary-btn');
  if (typeof submitNew?.onclick !== 'function') throw new Error('㉓ 新增表单没有提交按钮');
  submitNew.onclick();
  expectQuiet('空表单');
  // 一条拒绝一个字段，贴在它自己的行下面（owner 审计 2026-10-26 第 5 条）。以前这几个空字段
  // 合并成一句「标题、一句话用途和正文都必须填写」，于是填掉两个之后屏幕上还是同一句话，而且
  // 那条提示长在表单末尾，离任何输入框都有半屏。这里断言的是**形状**，不比对任何句子：
  // 措辞以后可以再改，「说的是哪个框、就贴在那个框下面、并且带上那个框自己的标签词、光标交给
  // 第一条」不能改。反过来也不许多拦：填好的字段不该还有拒绝挂着。
  const kbRefusalOf = (id) => findIn(form(), (node) => node?.attributes?.get?.('data-for') === id);
  const KB_GUARDED_FIELDS = ['kb-new-entry-type', 'kb-new-title', 'kb-new-summary', 'kb-new-body',
    'kb-new-author', 'kb-new-source-id', 'kb-new-source-version'];
  function expectFieldRefusals(ids, context, universe = KB_GUARDED_FIELDS) {
    const missing = ids.filter((id) => !kbRefusalOf(id));
    if (missing.length)
      throw new Error(`㉓ ${context}：这些空字段没有各自的拒绝：${missing.join(' ')}`);
    const extra = universe.filter((id) => !ids.includes(id) && kbRefusalOf(id));
    if (extra.length)
      throw new Error(`㉓ ${context}：已经填好的字段还被拦着：${extra.join(' ')}`);
    ids.forEach((id) => {
      const line = kbRefusalOf(id);
      const field = byElementId(view, id);
      const row = field.closest('.field-row');
      if (!row) throw new Error(`㉓ ${context}：#${id} 不在任何一个 field-row 里`);
      // 必须就在它自己的那一行里、排在这个输入框之后。两列布局下"下一格"不等于"这个框下面"，
      // 所以只比对 DOM 父子关系，不比对"行之后"。
      if (line.parentNode !== row)
        throw new Error(`㉓ ${context}：#${id} 的拒绝不在它自己的 field-row 里，`
          + `而是长在 ${line.parentNode === row.parentNode ? '表单容器' : '别处'}`);
      if (row.children.indexOf(line) <= row.children.indexOf(field))
        throw new Error(`㉓ ${context}：#${id} 的拒绝排在这个输入框之前，读起来不属于它`);
      if (field.getAttribute('aria-describedby') !== line.id)
        throw new Error(`㉓ ${context}：#${id} 没有指向拦住它的那条说明`);
      const label = findIn(row, (node) => node?.className === 'field-label');
      const word = text(label).replace(/（[^）]*）/g, '').trim();
      if (!word || !line.textContent.includes(word))
        throw new Error(`㉓ ${context}：#${id} 的说明没有出现这个字段自己的标签词「${word}」：`
          + line.textContent.slice(0, 80));
    });
    if (lastFocused !== byElementId(view, ids[0]))
      throw new Error(`㉓ ${context}：光标没有交给第一条被拦的字段，应停在 #${ids[0]}`);
  }
  expectFieldRefusals(['kb-new-title', 'kb-new-summary', 'kb-new-body', 'kb-new-author'],
    '空新增表单');
  byElementId(view, 'kb-new-title').value = '分镜拆解三步法';
  byElementId(view, 'kb-new-summary').value = '把一场戏拆成可拍摄的镜头';
  byElementId(view, 'kb-new-body').value = '先定机位，再定景别，最后核对轴线。';
  submitNew.onclick();
  expectQuiet('缺记录人');
  // 填掉的三个字段必须真的被放开：合并提示的年代，这里屏幕上的话和空表单时一模一样。
  expectFieldRefusals(['kb-new-author'], '缺记录人');
  byElementId(view, 'kb-new-applicability').value = '实拍与动画分镜';
  byElementId(view, 'kb-new-limits').value = '不适用于纯文字脚本；镜头数超过 80 时先分层。';
  byElementId(view, 'kb-new-domains').value = 'film、animation';
  byElementId(view, 'kb-new-tasks').value = 'storyboard';
  byElementId(view, 'kb-new-targets').value = 'photoshop';
  byElementId(view, 'kb-new-source-id').value = 'internal-storyboard';
  byElementId(view, 'kb-new-source-version').value = '2026-10';
  byElementId(view, 'kb-new-license').value = 'project-internal';
  byElementId(view, 'kb-new-license-status').value = 'reviewed';
  byElementId(view, 'kb-new-author').value = 'ALEX';
  submitNew.onclick();
  await flush();
  const createWrites = shell.pending.splice(0, shell.pending.length);
  if (createWrites.length !== 1)
    throw new Error(`㉓ 一次新增点击发出了 ${createWrites.length} 个请求`);
  if (createWrites[0].init.method !== 'POST' || createWrites[0].path !== '/api/knowledge-entries')
    throw new Error(`㉓ 新增打到了 ${createWrites[0].init.method} ${createWrites[0].path}`);
  const createBody = JSON.parse(createWrites[0].init.body);
  const createKeys = ['entry_type', 'title', 'summary', 'body', 'applicability', 'limits',
    'domain_tags', 'task_tags', 'target_tools', 'related_capability_ids', 'recommended',
    'source', 'created_by', 'supersedes'];
  if (!sameKeys(Object.keys(createBody), createKeys))
    throw new Error(`㉓ 新增体键集合不符：${Object.keys(createBody).join(',')}`);
  if ('schemaVersion' in createBody || 'created_at' in createBody)
    throw new Error('㉓ 新增体带了服务端字段（schemaVersion/created_at 由服务写）');
  if (createBody.created_by !== 'ALEX' || createBody.supersedes !== null)
    throw new Error(`㉓ 记录人/取代字段不符：${createBody.created_by} / ${createBody.supersedes}`);
  if (createBody.entry_type !== 'METHOD' || createBody.recommended !== true)
    throw new Error('㉓ 类型或推荐标记没有原样送出');
  if (JSON.stringify(createBody.domain_tags) !== JSON.stringify(['film', 'animation']))
    throw new Error(`㉓ 顿号分隔的领域标签没有拆开：${JSON.stringify(createBody.domain_tags)}`);
  if (!sameKeys(Object.keys(createBody.source),
    ['sourceId', 'version', 'license', 'licenseStatus']))
    throw new Error(`㉓ 留空的来源字段被页面编造了：${Object.keys(createBody.source).join(',')}`);

  const NEW_ID = 'kentry-20261023-storyboard';
  createWrites[0].resolve(response({
    schemaVersion: 'design-lab/knowledge-write/v1', status: 'WRITTEN', stored: true,
    revision: 1, entry: entryView({ knowledge_entry_id: NEW_ID, revision: 1 }),
    claims_not_made: ['保存不等于核验'],
  }));
  await flush();
  const createSearch = shell.pending.splice(0, shell.pending.length);
  if (createSearch.length !== 1 || !createSearch[0].path.startsWith('/api/knowledge-entries/search?'))
    throw new Error(`㉓ 写后应立刻重搜一次：${createSearch.map((r) => r.path).join(' ')}`);
  createSearch[0].resolve(response(libraryView({
    total: 3, returned: 3,
    entries: [rowView({ knowledge_entry_id: NEW_ID, revision: 1, latest_revision: 1,
      recommended_revision: 1, recommended_is_latest: true }), ...libraryView().entries],
  })));
  await flush();
  const createDetail = shell.pending.splice(0, shell.pending.length);
  if (createDetail.length !== 1 || createDetail[0].path !== `/api/knowledge-entries/${NEW_ID}`)
    throw new Error(`㉓ 写后没有按服务返回的编号读回详情：${createDetail.map((r) => r.path).join(' ')}`);
  createDetail[0].resolve(response({
    schemaVersion: 'design-lab/knowledge-entry-detail/v1',
    knowledge_entry_id: NEW_ID, status: 'ACTIVE', latest_revision: 1,
    recommended_revision: 1, current: entryView({ knowledge_entry_id: NEW_ID, revision: 1 }),
    recommended: entryView({ knowledge_entry_id: NEW_ID, revision: 1 }),
    superseded_by: null,
    recommendation_basis: 'written-flag', recommendation_judgement: null,
    source_state: null, judgements: [],
    revisions: [{ revision: 1, content_sha256: 'sha256:' + 'a'.repeat(64),
      entry_type: 'METHOD', title: '分镜拆解三步法', recommended: true,
      created_at: '2026-10-23T09:00:00+00:00', created_by: 'ALEX', readable: true }],
    unreadable_count: 0, index: { rows: 3, indexed: 3, rebuilt_at: null },
    does_not_say: ['保存不等于核验'],
  }));
  await flush();
  if (!formText().includes(`已写入 r1 · ${NEW_ID}`) || !formText().includes('sha256:' + 'a'.repeat(64)))
    throw new Error(`㉓ 写入回执没有按服务返回值上屏：${formText().slice(0, 240)}`);
  if (!text(byElementId(view, 'kb-detail')).includes(NEW_ID))
    throw new Error('㉓ 写后读回没有落在详情面');
  expectQuiet('新增读回');

  // (4) 修订：从读回的正文起稿，带上 expected_revision；旧版本留在历史里。
  const reviseButton = findIn(byElementId(view, 'kb-detail'),
    (node) => node?.tagName === 'BUTTON' && node.textContent === '修订为新版本');
  if (typeof reviseButton?.onclick !== 'function') throw new Error('㉓ 详情里没有修订入口');
  reviseButton.onclick();
  const reviseTitle = byElementId(view, 'kb-revise-title');
  if (!reviseTitle || reviseTitle.value !== '分镜拆解三步法')
    throw new Error('㉓ 修订表单没有从读回的标题起稿');
  if (byElementId(view, 'kb-revise-author').value !== '')
    throw new Error('㉓ 修订人不得预填：服务不持有身份，读回里也没有「现在的操作者」');
  byElementId(view, 'kb-revise-body').value = '先定机位，再定景别，最后核对轴线与视线高度。';
  // 适用场景 and 边界与反例 read as optional in this form, and the store does turn an empty
  // one into the literal UNKNOWN -- but the route demands the key, so the page must still send
  // it. Clearing both here is the control: a `|| undefined` in collect() drops the key and
  // the reader gets a bare INVALID_PROJECT_FIELDS (the other defect the browser walk found).
  byElementId(view, 'kb-revise-applicability').value = '';
  byElementId(view, 'kb-revise-limits').value = '';
  byElementId(view, 'kb-revise-author').value = 'ALEX';
  findIn(form(), (node) => node?.className === 'primary-btn').onclick();
  await flush();
  const reviseWrites = shell.pending.splice(0, shell.pending.length);
  if (reviseWrites.length !== 1
    || reviseWrites[0].path !== `/api/knowledge-entries/${NEW_ID}/revisions`)
    throw new Error(`㉓ 修订打到了 ${reviseWrites.map((r) => r.path).join(' ')}`);
  const reviseBody = JSON.parse(reviseWrites[0].init.body);
  if (reviseBody.applicability !== '' || reviseBody.limits !== '')
    throw new Error('㉓ 留空的可选字段没有作为空串送出，而是被丢掉了键：'
      + JSON.stringify([reviseBody.applicability, reviseBody.limits]));
  if (reviseBody.expected_revision !== 1 || reviseBody.created_by !== 'ALEX')
    throw new Error(`㉓ 修订没有带读到的 expected_revision：${JSON.stringify(reviseBody)}`);
  if ('schemaVersion' in reviseBody || 'supersedes' in reviseBody)
    throw new Error('㉓ 修订体不应携带 schemaVersion/supersedes');
  if (!reviseBody.body.includes('视线高度'))
    throw new Error('㉓ 修订后的正文没有送出');
  reviseWrites[0].resolve(response({
    schemaVersion: 'design-lab/knowledge-write/v1', status: 'WRITTEN', stored: true,
    revision: 2, entry: entryView({ knowledge_entry_id: NEW_ID, revision: 2,
      body: '先定机位，再定景别，最后核对轴线与视线高度。' }),
    claims_not_made: ['保存不等于核验'],
  }));
  await flush();
  const reviseSearch = shell.pending.splice(0, shell.pending.length);
  if (reviseSearch.length !== 1) throw new Error(`㉓ 修订后应重搜一次，实际 ${reviseSearch.length}`);
  reviseSearch[0].resolve(response(libraryView({
    total: 3, returned: 3,
    entries: [rowView({ knowledge_entry_id: NEW_ID, revision: 2, latest_revision: 2,
      recommended_revision: 2, recommended_is_latest: true }), ...libraryView().entries],
  })));
  await flush();
  const reviseDetail = shell.pending.splice(0, shell.pending.length);
  if (reviseDetail.length !== 1 || reviseDetail[0].path !== `/api/knowledge-entries/${NEW_ID}`)
    throw new Error(`㉓ 修订后没有读回详情：${reviseDetail.map((r) => r.path).join(' ')}`);
  reviseDetail[0].resolve(response({
    schemaVersion: 'design-lab/knowledge-entry-detail/v1',
    knowledge_entry_id: NEW_ID, status: 'ACTIVE', latest_revision: 2,
    recommended_revision: 2,
    current: entryView({ knowledge_entry_id: NEW_ID, revision: 2,
      body: '先定机位，再定景别，最后核对轴线与视线高度。' }),
    recommended: entryView({ knowledge_entry_id: NEW_ID, revision: 2,
      body: '先定机位，再定景别，最后核对轴线与视线高度。' }),
    superseded_by: null,
    recommendation_basis: 'written-flag', recommendation_judgement: null,
    source_state: null, judgements: [],
    revisions: [
      { revision: 2, content_sha256: 'sha256:' + 'b'.repeat(64), entry_type: 'METHOD',
        title: '分镜拆解三步法', recommended: true,
        created_at: '2026-10-23T10:00:00+00:00', created_by: 'ALEX', readable: true },
      { revision: 1, content_sha256: 'sha256:' + 'a'.repeat(64), entry_type: 'METHOD',
        title: '分镜拆解三步法', recommended: false,
        created_at: '2026-10-23T09:00:00+00:00', created_by: 'ALEX', readable: true },
    ],
    unreadable_count: 0, index: { rows: 3, indexed: 3, rebuilt_at: null },
    does_not_say: ['保存不等于核验'],
  }));
  await flush();
  if (!formText().includes(`已写入 r2 · ${NEW_ID}`))
    throw new Error(`㉓ 修订回执没有上屏：${formText().slice(0, 240)}`);
  if (!text(byElementId(view, 'kb-detail')).includes('r1 · 分镜拆解三步法'))
    throw new Error('㉓ 修订后旧版本必须仍在修订历史里');
  expectQuiet('修订读回');

  // (4b) DL-KB-05 D5：把推荐退回旧版本只能靠一条真人记下的判断——修订行是只追加的。
  // 表单必须把 kind/revision/reason/recorded_by 原样送出，写后按服务读回上屏。
  const judgedDetail = (basis, judgements, extra) => ({
    schemaVersion: 'design-lab/knowledge-entry-detail/v1',
    knowledge_entry_id: NEW_ID, status: 'ACTIVE', latest_revision: 2,
    recommended_revision: 1,
    current: entryView({ knowledge_entry_id: NEW_ID, revision: 2,
      body: '先定机位，再定景别，最后核对轴线与视线高度。' }),
    recommended: entryView({ knowledge_entry_id: NEW_ID, revision: 1,
      body: '先定机位，再定景别。' }),
    superseded_by: null,
    recommendation_basis: basis,
    recommendation_judgement: judgements.find((item) => item.kind === 'RECOMMENDATION') ?? null,
    source_state: judgements.find((item) => item.kind === 'SOURCE_STATE') ?? null,
    judgements,
    revisions: [
      { revision: 2, content_sha256: 'sha256:' + 'b'.repeat(64), entry_type: 'METHOD',
        title: '分镜拆解三步法', recommended: true,
        created_at: '2026-10-23T10:00:00+00:00', created_by: 'ALEX', readable: true },
      { revision: 1, content_sha256: 'sha256:' + 'a'.repeat(64), entry_type: 'METHOD',
        title: '分镜拆解三步法', recommended: false,
        created_at: '2026-10-23T09:00:00+00:00', created_by: 'ALEX', readable: true },
    ],
    unreadable_count: 0, index: { rows: 3, indexed: 3, rebuilt_at: null },
    does_not_say: ['保存不等于核验'],
    ...extra,
  });
  const RECOMMEND_ROW = {
    judgement_id: 'kjudge-' + 'd'.repeat(32), kind: 'RECOMMENDATION', revision: 1,
    value: 'RECOMMENDED', replaced_by: null, reason: '旧版本那三步在实际项目里更稳。',
    recorded_by: '张工', recorded_at: '2026-10-24T11:00:00+00:00',
  };
  byElementId(view, 'kb-judge-revision').value = '1';
  byElementId(view, 'kb-judge-name').value = '张工';
  byElementId(view, 'kb-judge-submit').onclick();
  await flush();
  if (shell.pending.length !== 0)
    throw new Error('㉓ 没有理由时页面把判断发给了服务：服务会拒绝，但这一页不该先问一次');
  if (!text(byElementId(view, 'kb-detail')).includes('判断必须写出理由'))
    throw new Error('㉓ 缺理由时页面没有就地说明缺什么');
  byElementId(view, 'kb-judge-reason').value = RECOMMEND_ROW.reason;
  byElementId(view, 'kb-judge-name').value = '';
  byElementId(view, 'kb-judge-submit').onclick();
  await flush();
  if (shell.pending.length !== 0 || !text(byElementId(view, 'kb-detail')).includes('必须填上记录人'))
    throw new Error('㉓ 缺记录人时页面没有拒绝并说明验收只接受具名真人');
  byElementId(view, 'kb-judge-name').value = '张工';
  byElementId(view, 'kb-judge-submit').onclick();
  await flush();
  const judgeWrites = shell.pending.splice(0, shell.pending.length);
  if (judgeWrites.length !== 1
    || judgeWrites[0].path !== `/api/knowledge-entries/${NEW_ID}/judgements`
    || judgeWrites[0].init.method !== 'POST')
    throw new Error(`㉓ 判断没有打到 judgements 路由：${judgeWrites.map((r) => `${r.init.method} ${r.path}`).join(' ')}`);
  const judgeBody = JSON.parse(judgeWrites[0].init.body);
  if (judgeBody.kind !== 'RECOMMENDATION' || judgeBody.revision !== 1
    || judgeBody.recorded_by !== '张工' || judgeBody.recorded_by_kind !== 'HUMAN'
    || judgeBody.replaced_by !== null || 'recorded_at' in judgeBody)
    throw new Error(`㉓ 判断体不对：${JSON.stringify(judgeBody)}`);
  judgeWrites[0].resolve(response(judgedDetail('recorded-judgement', [RECOMMEND_ROW])));
  await flush();
  const judgeSearch = shell.pending.splice(0, shell.pending.length);
  if (judgeSearch.length !== 1 || !judgeSearch[0].path.startsWith('/api/knowledge-entries/search?'))
    throw new Error('㉓ 记完判断没有重搜：列表的推荐标记必须跟着读回变');
  judgeSearch[0].resolve(response(libraryView({
    total: 3, returned: 3,
    entries: [rowView({ knowledge_entry_id: NEW_ID, revision: 2, latest_revision: 2,
      recommended_revision: 1, recommended_is_latest: false }), ...libraryView().entries],
  })));
  await flush();
  const judgeDetail = shell.pending.splice(0, shell.pending.length);
  if (judgeDetail.length !== 1 || judgeDetail[0].path !== `/api/knowledge-entries/${NEW_ID}`)
    throw new Error('㉓ 记完判断没有按编号读回详情');
  judgeDetail[0].resolve(response(judgedDetail('recorded-judgement', [RECOMMEND_ROW])));
  await flush();
  const judgedText = text(byElementId(view, 'kb-detail'));
  for (const needle of ['判断与来源状态', '推荐 r1', '张工', RECOMMEND_ROW.reason,
    '来自一次后来记下的判断', '来源状态没有人说过'])
    if (!judgedText.includes(needle))
      throw new Error(`㉓ 判断读回没有上屏「${needle}」：${judgedText.slice(0, 300)}`);
  expectQuiet('判断读回');

  // 来源失效必须带替代条目：一个打不开的替代不是替代，页面先问清再发。
  byElementId(view, 'kb-source-value').value = 'INVALID';
  byElementId(view, 'kb-source-reason').value = '原稿下架。';
  byElementId(view, 'kb-source-name').value = '张工';
  byElementId(view, 'kb-source-submit').onclick();
  await flush();
  if (shell.pending.length !== 0)
    throw new Error('㉓ 没有替代条目编号时不能把失效判断发给服务');
  if (!text(byElementId(view, 'kb-detail')).includes('替代条目的编号'))
    throw new Error('㉓ 失效判断缺替代时页面没有说明缺什么');
  const SOURCE_ROW = {
    judgement_id: 'kjudge-' + 'e'.repeat(32), kind: 'SOURCE_STATE', revision: null,
    value: 'INVALID', replaced_by: 'kentry-' + '9'.repeat(32), reason: '原稿下架。',
    recorded_by: '张工', recorded_at: '2026-10-24T11:30:00+00:00',
  };
  byElementId(view, 'kb-source-replacement').value = SOURCE_ROW.replaced_by;
  byElementId(view, 'kb-source-submit').onclick();
  await flush();
  const sourceWrites = shell.pending.splice(0, shell.pending.length);
  if (sourceWrites.length !== 1
    || sourceWrites[0].path !== `/api/knowledge-entries/${NEW_ID}/judgements`)
    throw new Error('㉓ 来源判断没有打到 judgements 路由');
  const sourceBody = JSON.parse(sourceWrites[0].init.body);
  if (sourceBody.kind !== 'SOURCE_STATE' || sourceBody.value !== 'INVALID'
    || sourceBody.revision !== null
    || sourceBody.replaced_by !== SOURCE_ROW.replaced_by)
    throw new Error(`㉓ 来源判断体不对：${JSON.stringify(sourceBody)}`);
  sourceWrites[0].resolve(response(judgedDetail('recorded-judgement',
    [RECOMMEND_ROW, SOURCE_ROW])));
  await flush();
  shell.pending.splice(0, shell.pending.length)
    [0].resolve(response(libraryView({
      total: 3, returned: 3,
      entries: [rowView({ knowledge_entry_id: NEW_ID, revision: 2, latest_revision: 2,
        recommended_revision: 1, recommended_is_latest: false }), ...libraryView().entries],
    })));
  await flush();
  shell.pending.splice(0, shell.pending.length)
    [0].resolve(response(judgedDetail('recorded-judgement', [RECOMMEND_ROW, SOURCE_ROW])));
  await flush();
  const sourcedText = text(byElementId(view, 'kb-detail'));
  for (const needle of ['已失效', `替代条目 ${SOURCE_ROW.replaced_by}`, '原稿下架。'])
    if (!sourcedText.includes(needle))
      throw new Error(`㉓ 来源判断读回没有上屏「${needle}」：${sourcedText.slice(0, 300)}`);
  expectQuiet('来源判断读回');

  // A5 的最后一格：复制。屏上的正文必须逐字进剪贴板；剪贴板被拒时，拒的就是那段正文，
  // 而不是页面另拼一份。这里量的是回退面（沙箱里没有 clipboard），真实 clipboard 由浏览器走查量。
  const copiedBody = '先定机位，再定景别，最后核对轴线与视线高度。';
  byElementId(view, 'kb-copy-body').onclick();
  const copyStatus = byElementId(view, 'kb-copy-status');
  const fallbackArea = findIn(copyStatus, (node) => String(node?.className ?? '')
    .includes('as-copy-fallback'));
  if (!fallbackArea || fallbackArea.value !== copiedBody)
    throw new Error('㉓ 剪贴板被拒时，页面没有把服务返回的正文原样交给用户复制：'
      + JSON.stringify({ found: !!fallbackArea, value: fallbackArea?.value }));
  if (!text(copyStatus).includes('浏览器没有允许写入剪贴板'))
    throw new Error('㉓ 复制回退没有说明是浏览器拒绝了写入：' + text(copyStatus).slice(0, 160));
  if (!text(copyStatus).includes('这只是复制，不是选用'))
    throw new Error('㉓ 复制回退没有把"这只是复制"说清楚：' + text(copyStatus).slice(0, 160));

  // (5) 无命中只解释，不编造：两字检索词走子串回退，答案为空时列表里只有一行解释。
  const searchForm = findIn(view, (node) => node?.tagName === 'FORM');
  byElementId(view, 'kb-query').value = '霓虹';
  searchForm.onsubmit({ preventDefault() {} });
  await flush();
  const missReads = shell.pending.splice(0, shell.pending.length);
  if (missReads.length !== 1 || !missReads[0].path.startsWith('/api/knowledge-entries/search?'))
    throw new Error(`㉓ 无命中查询没有发出检索：${missReads.map((r) => r.path).join(' ')}`);
  const missParams = new URLSearchParams(missReads[0].path.split('?')[1]);
  if (missParams.get('q') !== '霓虹') throw new Error(`㉓ 检索词没有送出：${missReads[0].path}`);
  missReads[0].resolve(response(libraryView({
    query: '霓虹', strategy: 'SHORT_FALLBACK', matched_terms: ['霓虹'],
    total: 0, returned: 0, entries: [], next_offset: null,
    explanation: '没有命中「霓虹」的条目。库中现有 3 条；检索只匹配标题、摘要、正文、'
      + '领域/任务标签和目标工具，不做近义词扩写，也不推荐未命中的相关条目。',
  })));
  await flush();
  const missText = text(view);
  if (!missText.includes('没有符合条件的结果') || !missText.includes('没有命中「霓虹」的条目'))
    throw new Error(`㉓ 无命中没有按服务解释上屏：${missText.slice(0, 260)}`);
  if (!missText.includes('策略 SHORT_FALLBACK') || !missText.includes('子串回退命中'))
    throw new Error('㉓ 两字检索词没有说明 trigram 答不了、由子串回退');
  const missRows = byElementId(view, 'kb-results').children.filter((node) => node?.tagName === 'LI');
  if (missRows.length !== 1)
    throw new Error(`㉓ 无命中时列表只能有一行解释，实际 ${missRows.length} 行`);
  if (text(missRows[0]).includes('分镜拆解三步法'))
    throw new Error('㉓ 无命中时上一次的答案仍留在列表里');
  if (findIn(view, (node) => node?.tagName === 'BUTTON'
    && String(node.textContent).startsWith('加载更多')))
    throw new Error('㉓ 无命中时不得出现「加载更多」');
  // 右侧详情保留上一次选中是主从布局的常态，但零结果时它离结果区只有一条边框：
  // 不标明"不属于本次结果"，读起来就像这次检索命中了它。
  const outsideNote = text(byElementId(view, 'kb-detail-outside'));
  if (!outsideNote.includes('不在本次检索结果里'))
    throw new Error('㉓ 零结果时旧选中条目仍挂在右侧，却没有标明它不属于本次检索');
  expectQuiet('无命中');

  // (6) 导入表单把剩下的分支也走一遍（owner 审计 2026-10-26 第 5 条点名的合并提示就在这条路上：
  // 「导入必须填写来源 ID 和来源版本」一句话说两个框）。这里不比对措辞，只数拒绝、看它落在哪个框
  // 下面。空表单这一发同时覆盖「类型清单未读回」分支：替身里的 select 没有浏览器那个"默认第一项"，
  // 新打开的表单类型就是空 —— 正是服务没连上时用户在屏上看到的形状。
  byElementId(view, 'kb-import').onclick();
  const IMPORT_FIELDS = ['kb-import-entry-type', 'kb-import-title', 'kb-import-summary',
    'kb-import-body', 'kb-import-author', 'kb-import-source-id', 'kb-import-source-version'];
  const submitImport = findIn(form(), (node) => node?.className === 'primary-btn');
  if (typeof submitImport?.onclick !== 'function') throw new Error('㉓ 导入表单没有提交按钮');
  submitImport.onclick();
  expectQuiet('空导入表单');
  expectFieldRefusals(IMPORT_FIELDS, '空导入表单', IMPORT_FIELDS);
  // 只留两个来源框为空：拒绝必须收窄到这两个，其余五条要跟着填好一起消失。
  byElementId(view, 'kb-import-entry-type').value = 'PROMPT';
  byElementId(view, 'kb-import-title').value = '油墨限定提示词';
  byElementId(view, 'kb-import-summary').value = '把两色限制写成可复用的约束句';
  byElementId(view, 'kb-import-body').value = '先列允许的两色，再写"除这两色外不使用任何油墨"。';
  byElementId(view, 'kb-import-author').value = 'ALEX';
  submitImport.onclick();
  expectQuiet('缺来源版本');
  expectFieldRefusals(['kb-import-source-id', 'kb-import-source-version'],
    '缺来源 ID 与版本', IMPORT_FIELDS);
}

console.log('ok: ㉓ DL-KB-02/03/04 知识与提示词库：首屏一次检索且词表/许可状态来自读回、列表不带正文哈希路径、'
  + '详情按需读回、空表单与缺记录人本地拒绝、新增 14 键 POST（无 schemaVersion/created_at、留空来源不编造）、'
  + '修订带 expected_revision 且旧版本留在历史、写后按返回编号读回、两字检索词走子串回退且无命中只解释不编造、'
  + '推荐退回旧版本只能靠一条真人判断（缺理由与缺记录人都本地拒绝、七键 POST 不带 recorded_at）、'
  + '来源失效必须带一个打得开的替代条目');

console.log('APPSHELL REGRESSION: all checks passed');
