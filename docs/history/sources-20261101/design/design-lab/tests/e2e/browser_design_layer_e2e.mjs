// SPDX-License-Identifier: MIT
// E-SLICE-02 browser E2E: real Chromium drives the Workbench 05 design layer
// vertical slice (Project -> Brief -> Direction -> DesignSystem) end to end,
// served by the real Python loopback service (same-origin fetch).
//
// F-2b extends the SAME run with the revision chain: the brief is revised, then
// the CHOSEN direction is revised, and the assertions read back the persisted
// DOM — version numbers, 当前 vs 已取代 with the superseded_by pointer, both
// lineage panels, and the honest "绑定需重新建立" state that appears when the
// append-only design-system binding is left behind on the retired direction
// version (active_binding === null must NEVER render as a current binding).
// The run then RELOADS the page and rebuilds the same DOM from the service, so
// the readback cannot be an in-memory illusion.
//
// This is a controlled-runtime (E2) proof: a real browser loads the committed
// `apps/workbench/build/main.js` and exercises the user-visible forms against
// the live API, then the assertions read back the persisted DOM state. It does
// NOT claim an E3 host run or an E4 human jury acceptance.
//
// Driven by the Python shell test_workbench_design_layer_e2e.py via
// `node browser_design_layer_e2e.mjs`. Environment:
//   E2E_SERVICE_URL     required  e.g. http://127.0.0.1:56321
//   E2E_TOKEN           required  64-hex service bearer token
//   E2E_NODE_MODULES    required  dir that CONTAINS node_modules/ so that
//                                 `playwright` resolves (repo npm-cache).
//   E2E_BROWSER         optional  explicit chromium executablePath; when set
//                                 it bypasses playwright's revision lookup so a
//                                 pre-installed browser works with zero download.
//   E2E_EVIDENCE_DIR    optional  dir for browser-e2e-summary.json (+ fail.png
//                                 on failure); default
//                                 .project-local/task-artifacts/browser-e2e
// Exits 0 with `E2E_OK ...` on a full chain pass; non-zero otherwise. Every
// exit path writes the evidence summary so CI artifacts and local runs carry
// the same machine-readable trail.
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import path from 'node:path';
import process from 'node:process';

const serviceUrl = process.env.E2E_SERVICE_URL;
const token = process.env.E2E_TOKEN;
const nmDir = process.env.E2E_NODE_MODULES;
const browser = process.env.E2E_BROWSER || null;
const evidenceDir = path.resolve(process.env.E2E_EVIDENCE_DIR || '.project-local/task-artifacts/browser-e2e');
const errors = [];
let browserInfo = browser ? String(browser) : null;
let page = null;
// Hoisted so the reload step can re-select the SAME project after the page
// (and its in-memory project id) is thrown away.
let projectName = '';
let projectId = '';
// What the route-inventory step actually derived, so the evidence names its own
// subject instead of leaving a reader to guess which number was in play.
let routeInventory = null;
// The desktop nav-containment reading, recorded in the artifact so a reader does
// not have to scrape stdout for the numbers the assertion used.
let navVisibility = null;
// Set only when the prompt-result slice actually ran, so the summary can never
// claim a scenario that was skipped and a reader need not scrape stdout.
let promptLoop = null;
// DL-KB-08: the design-assistant (assistance plan) slice. Same rule: only set
// when the steps actually ran, so a summary never claims a skipped scenario.
let assistantLoop = null;
// DL-KB-16: the reload half of the feedback assertion is measured after the page has been thrown
// away, so it lives beside the loop object rather than inside the lane's locals.
let feedbackSurvivedReload = false;
// DL-KB-10: 屏幕三 目标组合选择面板. Same rule as above -- set only when the
// steps actually ran, so the evidence can never describe a screen it skipped.
let targetProfileLoop = null;
// DL-KB-14: 状态与错误面。六种状态各自在真实浏览器里被读到才写这张卡；跳过这一步的运行
// 不会在 summary 里冒充它发生过。
let stateLoop = null;
// DL-KB-05 D5: the knowledge detail walk. Set only when the steps really ran, so a run that
// never opened an entry cannot leave a summary that describes the panel as browser-proven.
let knowledgeLoop = null;
// Counts the /api/target-profile* POSTs from the wire, not from the DOM: a "nothing was
// executed" claim that still posted twice, or a validate that never left the page, are both
// invisible to a text-only assertion.
let targetProfilePosts = 0;
let targetProfileValidates = 0;
// Counts every assistance-plan write the page issued. The copy/choose split is
// only provable from the wire: copying must leave these counters untouched.
let assistanceWrites = 0;
let assistanceChooses = 0;
// DL-KB-16: a voluntary external-use report is a POST under the same path prefix, so it moves
// assistanceWrites too. This counter separates the two: the lane needs to say "the plan was
// revised zero times and exactly one feedback record left the page", which the shared counter
// cannot tell apart.
let feedbackWrites = 0;

// P0-G: single evidence writer, used by every exit path (PASS and FAIL).
const writeSummary = (result, error) => {
  fs.mkdirSync(evidenceDir, { recursive: true });
  const scenario = ['create-project', 'import-reference', 'create-brief',
                    'create-direction', 'choose-direction', 'bind-design-system',
                    'revise-brief', 'revise-chosen-direction',
                    'binding-rebuild-readback', 'reload-persisted-readback',
                    'persisted-readback', 'mobile-appshell-layout',
                    'nav-route-inventory-derived-from-served-bundle',
                    'desktop-nav-active-visible'];
  if (promptLoop) scenario.push('prompt-result-compose-store-sign');
  if (assistantLoop) scenario.push('assistance-plan-four-states');
  if (stateLoop) scenario.push('six-state-surfaces');
  if (knowledgeLoop) scenario.push('knowledge-detail-judgement-walk');
  if (targetProfileLoop) scenario.push('target-combination-panel-two-columns-b2');
  const payload = {
    kind: 'workbench-browser-e2',
    subjectSha: process.env.E2E_SUBJECT_SHA || 'local',
    browser: { engine: 'chromium', version: browserInfo },
    workflowRunId: process.env.E2E_WORKFLOW_RUN_ID || 'local',
    scenario,
    consoleErrors: errors.length,
    result,
  };
  if (promptLoop) payload.promptLoop = promptLoop;
  if (assistantLoop) payload.assistantLoop = assistantLoop;
  if (stateLoop) payload.stateLoop = stateLoop;
  if (knowledgeLoop) payload.knowledgeLoop = knowledgeLoop;
  if (targetProfileLoop) payload.targetProfileLoop = targetProfileLoop;
  if (routeInventory) payload.routeInventory = routeInventory;
  if (navVisibility) payload.navVisibility = navVisibility;
  if (error) payload.error = error;
  fs.writeFileSync(path.join(evidenceDir, 'browser-e2e-summary.json'),
                   JSON.stringify(payload, null, 2) + '\n');
};

if (!serviceUrl || !token || !nmDir) {
  console.error('E2E_CONFIG_MISSING: need E2E_SERVICE_URL, E2E_TOKEN, E2E_NODE_MODULES');
  writeSummary('FAIL', 'E2E_CONFIG_MISSING: need E2E_SERVICE_URL, E2E_TOKEN, E2E_NODE_MODULES');
  process.exit(3);
}
if (!/^[0-9a-f]{64}$/.test(token)) {
  console.error('E2E_TOKEN_SHAPE: must be 64-hex');
  writeSummary('FAIL', 'E2E_TOKEN_SHAPE: must be 64-hex');
  process.exit(3);
}

// Resolve `playwright` from the directory that owns node_modules/ (the repo
// npm-cache), not from this script's location.
const req = createRequire(nmDir + '/noop.js');
const pw = req('playwright');

const launchOpts = { headless: true };
if (browser) launchOpts.executablePath = browser;

const step = (name, fn) => {
  process.stdout.write(`E2E step: ${name}\n`);
  return Promise.resolve()
    .then(fn)
    .then(() => console.log(`E2E ok: ${name}`));
};

// One fail-closed exit shape: log the reason, screenshot the live page while it
// still exists, write the machine-readable summary, exit non-zero.
const abort = async (reason, code, ctx, b) => {
  console.error(reason);
  await captureFailureShot(ctx, b);
  writeSummary('FAIL', reason);
  process.exit(code);
};

// ---------------------------------------------------------------------------
// ROUTE INVENTORY -- derived, never typed.
//
// `ROUTE_VIEWS` (apps/workbench/shell.ts) is the authority for the routes the Workbench
// mounts, and mountAppShell() renders exactly one `.app-nav-item` button per entry,
// stamped `data-route="<view>"` (verified: one `app-nav-item` construction site in the
// bundle, and navGroupChunks() drops nothing). The mobile-layout step used to compare the
// button count against a literal integer a human re-typed on every IA change (12 -> 15 ->
// 18 -> 19, with three stale "12" comments found the same day). The number and the
// comments are the same drift class; this parses the inventory instead.
//
// Source of the expected inventory: the bundle bytes the SERVICE HANDS TO THE BROWSER
// (`GET /workbench/main.js`), fetched with Node and parsed here. Two measured reasons:
//   * the DOM alone cannot answer it -- `ROUTE_VIEWS` is not exported to `window` (the
//     only global the bundle installs is `window.__dlToast`), so a page-side read sees the
//     MOUNTED buttons, not the table they came from. Expecting the mount to equal the
//     mount would be a tautology, so the expectation has to come from outside the DOM;
//   * not `apps/workbench/build/main.js` on disk either -- `design_lab.workbench.resource()`
//     prefers the installed wheel copy when one exists, so served and committed bytes CAN
//     diverge (workbench.py's D003 note records a 72,051 B installed bundle vs a 157,747 B
//     committed one). Serving the checkout is what the browser executed, and the identity
//     is asserted below (the page hashes the same URL and must agree) rather than assumed.
// `minify:false` (apps/workbench/vite.config.ts) keeps the array readable, so the entries
// are recoverable without a TS compiler.
//
// Fail-closed: an unreadable marker, an unbalanced literal, an entry without `hash`/`view`
// or an empty table all ABORT the run -- a parse that yields nothing never degrades into
// "no expectation, therefore no failure".
// ---------------------------------------------------------------------------
const ROUTE_TABLE_MARKER = 'const ROUTE_VIEWS = [';

/** Body of the array literal whose '[' sits at `openIndex`, string-aware. */
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

/** Each top-level `{ ... }` of an object-array body, comments and all. */
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

const sha256Hex = (text) => createHash('sha256').update(text).digest('hex');

/** -> [{hash, view}] | null (null means "could not read the table", never "no routes"). */
const parseRouteViews = (bundleText) => {
  const markerAt = bundleText.indexOf(ROUTE_TABLE_MARKER);
  if (markerAt < 0) return null;
  const body = sliceArrayBody(bundleText, markerAt + ROUTE_TABLE_MARKER.length - 1);
  if (body === null) return null;
  const objects = sliceEntryObjects(body);
  const routes = [];
  for (const obj of objects) {
    const hash = stringField(obj, 'hash');
    const view = stringField(obj, 'view');
    if (hash === null || view === null) return null;
    if (hash !== '' && !hash.startsWith('#/')) return null;
    routes.push({ hash, view });
  }
  return routes.length > 0 ? routes : null;
};

try {
  const b = await pw.chromium.launch(launchOpts);
  try {
    browserInfo = await b.browserVersion() || browserInfo;
  } catch {
    // version probe is best-effort; launch errors must dominate the summary.
  }
  const ctx = await b.newContext();
  page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push('pageerror: ' + String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  // DL-KB-08: count assistance-plan writes/choices from the wire itself. A copy
  // that secretly chose, or a "no write" refusal that still posted, would pass a
  // DOM-only assertion; these counters cannot.
  page.on('request', (request) => {
    if (request.method() !== 'POST') return;
    const url = request.url();
    if (/\/target-profiles(\/|$)/.test(url)) {
      targetProfilePosts += 1;
      if (/\/validate$/.test(url)) targetProfileValidates += 1;
    }
    if (!/\/assistance-plans(\/|$)/.test(url)) return;
    assistanceWrites += 1;
    if (/\/choose$/.test(url)) assistanceChooses += 1;
    if (/\/feedback$/.test(url)) feedbackWrites += 1;
  });

  const base = serviceUrl.replace(/\/$/, '');
  await page.goto(base + '/workbench', { waitUntil: 'load' });

  await step('connect', async () => {
    await page.locator('#token').fill(token);
    await page.locator('#connect-form button').first().click();
    await page.locator('#workspace').waitFor({ state: 'visible', timeout: 15000 });
  });

  await step('create project', async () => {
    projectName = 'E2E Autumn ' + Date.now();
    await page.locator('#project-name').fill(projectName);
    await page.locator('#create-form button').first().click();
    // The project select repopulates only after the create POST plus the projects()
    // refresh round-trip settles; wait for the new <option> to attach before we can
    // select it (an immediate read sees the pre-create placeholder only).
    await page.locator('#project option', { hasText: projectName })
      .first().waitFor({ state: 'attached', timeout: 20000 });
    await page.locator('#project').selectOption({ label: projectName });
    projectId = await page.locator('#project').inputValue();
  });

  // P0-05 B04: import a real reference asset and let the picker carry it into the brief.
  // The PNG is a PIL-verified valid 1x1 RGBA image (not a broken placeholder).
  await step('import reference', async () => {
    const png = Buffer.from(
      '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489' +
      '0000000b49444154789c6360000200000500017a5eab3f0000000049454e44ae426082', 'hex');
    await page.locator('#file').setInputFiles({ name: 'ref.png', mimeType: 'image/png', buffer: png });
    await page.locator('#import-button').click();
    // sendImport() -> refresh() -> populateReferencePicker: one checkbox per imported asset.
    await page.locator('#reference-picker input[type=checkbox]').first()
      .waitFor({ state: 'visible', timeout: 20000 });
  });

  // Refresh loads the design-system catalog + design-layer readback into 05.
  await step('refresh design systems', async () => {
    await page.locator('#refresh').click();
    await page.locator('#design-systems li').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  await step('persist brief with reference', async () => {
    // P0-05 B04: the imported asset is a real reference; check it so the brief
    // carries a genuine asset id (not an empty list), then prove the readback.
    await page.locator('#reference-picker input[type=checkbox]').first().check();
    await page.locator('#brief-title').fill('E2E Autumn');
    await page.locator('#brief-goals').fill('modern, warm, restrained');
    await page.locator('#brief-submit').click();
    await page.locator('#design-briefs li', { hasText: 'BRIEF · E2E Autumn' })
      .first().waitFor({ state: 'visible', timeout: 15000 });
    const briefLine = await page.locator('#design-briefs li').first().innerText();
    if (!/参考 1/.test(briefLine)) {
      await abort('E2E_REFERENCE_NOT_CARRIED: ' + briefLine, 6, ctx, b);
    }
    // F-2b: a freshly created record is version 1 and is the current version.
    if (!/v1 · 当前/.test(briefLine)) {
      await abort('E2E_BRIEF_VERSION_MISSING: ' + briefLine, 6, ctx, b);
    }
  });

  await step('raise direction', async () => {
    // #direction-brief is repopulated by refreshDesign after the brief landed.
    await page.locator('#direction-brief').selectOption({ index: 1 });
    await page.locator('#direction-title').fill('Warm Gradient');
    await page.locator('#direction-color').fill('warm');
    await page.locator('#direction-submit').click();
    await page.locator('#design-directions li', { hasText: 'DIRECTION · Warm Gradient' })
      .first().waitFor({ state: 'visible', timeout: 15000 });
  });

  await step('choose direction', async () => {
    await page.locator('#design-directions li button', { hasText: '选为方向' })
      .first().click();
    await page.locator('#design-directions li', { hasText: 'CHOSEN by workbench-user' })
      .first().waitFor({ state: 'visible', timeout: 15000 });
  });

  await step('bind design system', async () => {
    await page.locator('#design-system').selectOption({ index: 1 });
    await page.locator('#design-system-bind').click();
    await page.locator('#design-bindings li', { hasText: 'BINDING ·' })
      .first().waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('#design-binding-active', { hasText: '已绑定设计系统' })
      .first().waitFor({ state: 'visible', timeout: 15000 });
    const bindingLine = await page.locator('#design-bindings li').first().innerText();
    if (!/生效中/.test(bindingLine)) {
      await abort('E2E_BINDING_NOT_ACTIVE: ' + bindingLine, 6, ctx, b);
    }
  });

  // ------------------------------------------------------------------------
  // F-2b: revise the brief. The row's「新版本」entry must prefill the form from
  // that version's persisted content, the POST must land on the revision route,
  // and the result must be read back (new live version + retired old version).
  // ------------------------------------------------------------------------
  await step('revise brief', async () => {
    const row = page.locator('#design-briefs li', { hasText: 'BRIEF · E2E Autumn' }).first();
    await row.locator('button', { hasText: '新版本' }).click();
    const prefillTitle = await page.locator('#revision-brief-title').inputValue();
    const prefillGoals = await page.locator('#revision-brief-goals').inputValue();
    const checkedRefs = await page.locator('#reference-picker input[type=checkbox]:checked').count();
    if (prefillTitle !== 'E2E Autumn' || !/modern, warm, restrained/.test(prefillGoals) || checkedRefs !== 1) {
      await abort('E2E_REVISION_PREFILL_MISSING: title=' + prefillTitle +
                  ' goals=' + prefillGoals + ' refs=' + checkedRefs, 7, ctx, b);
    }
    const target = await page.locator('#revision-brief-target').innerText();
    if (!/版本 1/.test(target)) {
      await abort('E2E_REVISION_TARGET_MISSING: ' + target, 7, ctx, b);
    }
    await page.locator('#revision-brief-goals').fill('modern, warm, restrained, night');
    await page.locator('#brief-revision-submit').click();
    await page.locator('#brief-lineage li', { hasText: '版本 2' })
      .first().waitFor({ state: 'visible', timeout: 15000 });

    if (await page.locator('#design-briefs li').count() !== 2) {
      await abort('E2E_BRIEF_VERSION_COUNT: ' +
                  JSON.stringify(await page.locator('#design-briefs li').allInnerTexts()), 7, ctx, b);
    }
    const live = page.locator('#design-briefs li', { hasText: '当前' }).first();
    const retired = page.locator('#design-briefs li', { hasText: '已取代' }).first();
    const liveLine = await live.innerText();
    const retiredLine = await retired.innerText();
    // The new version carries the edited content; the retired row keeps its own.
    if (!/night/.test(liveLine) || /night/.test(retiredLine) ||
        !/已取代 → 版本 2/.test(retiredLine) || !/v1/.test(retiredLine)) {
      await abort('E2E_BRIEF_VERSION_STATE:\n' + liveLine + '\n' + retiredLine, 7, ctx, b);
    }
    // Success must move the highlight + focus onto the NEW version's row.
    if (await page.locator('#design-briefs li.highlight').count() !== 1) {
      await abort('E2E_BRIEF_HIGHLIGHT_MISSING', 7, ctx, b);
    }
    const focused = await page.evaluate(
      () => (document.activeElement && document.activeElement.textContent) || '');
    if (!/night/.test(focused)) {
      await abort('E2E_BRIEF_FOCUS_NOT_ON_NEW_VERSION: ' + focused, 7, ctx, b);
    }
    // The version chain is read back from the service, oldest version first.
    const chain = await page.locator('#brief-lineage li').allInnerTexts();
    const chainTitle = await page.locator('#brief-lineage-title').innerText();
    if (chain.length !== 2 || !/^版本 2 · 当前/.test(chain[1]) ||
        !/^版本 1 · 已取代 → 版本 2/.test(chain[0]) || !/共 2 个版本/.test(chainTitle)) {
      await abort('E2E_BRIEF_LINEAGE:\n' + chainTitle + '\n' + chain.join('\n'), 7, ctx, b);
    }
  });

  // ------------------------------------------------------------------------
  // F-2b: revise the CHOSEN direction. The human Choice follows the new version,
  // but the append-only design-system binding stays on the retired version, so
  // the UI must say「绑定需重新建立」and must NOT show the old binding as current.
  // ------------------------------------------------------------------------
  await step('revise chosen direction', async () => {
    const row = page.locator('#design-directions li', { hasText: 'CHOSEN by workbench-user' }).first();
    await row.locator('button', { hasText: '新版本' }).click();
    const prefillTitle = await page.locator('#revision-direction-title').inputValue();
    const prefillColor = await page.locator('#revision-direction-color').inputValue();
    const target = await page.locator('#revision-direction-target').innerText();
    if (prefillTitle !== 'Warm Gradient' || prefillColor !== 'warm' ||
        !/版本 1/.test(target) || !/已选定方向/.test(target)) {
      await abort('E2E_DIRECTION_REVISION_PREFILL: title=' + prefillTitle +
                  ' color=' + prefillColor + ' target=' + target, 8, ctx, b);
    }
    await page.locator('#revision-direction-title').fill('Warm Gradient II');
    await page.locator('#direction-revision-submit').click();
    await page.locator('#direction-lineage li', { hasText: '版本 2' })
      .first().waitFor({ state: 'visible', timeout: 15000 });

    if (await page.locator('#design-directions li').count() !== 2) {
      await abort('E2E_DIRECTION_VERSION_COUNT: ' +
                  JSON.stringify(await page.locator('#design-directions li').allInnerTexts()), 8, ctx, b);
    }
    const liveLine = await page.locator('#design-directions li', { hasText: '当前' }).first().innerText();
    const retiredLine = await page.locator('#design-directions li', { hasText: '已取代' }).first().innerText();
    // Choice carried forward / retired row must NOT still read as chosen.
    if (!/Warm Gradient II/.test(liveLine) || !/CHOSEN by workbench-user/.test(liveLine) ||
        !/已取代 → 版本 2/.test(retiredLine) || /CHOSEN by/.test(retiredLine)) {
      await abort('E2E_DIRECTION_VERSION_STATE:\n' + liveLine + '\n' + retiredLine, 8, ctx, b);
    }
    const chain = await page.locator('#direction-lineage li').allInnerTexts();
    if (chain.length !== 2 || !/^版本 2 · 当前/.test(chain[1]) || !/已选定（workbench-user）/.test(chain[1]) ||
        !/^版本 1 · 已取代 → 版本 2/.test(chain[0]) || !/未选定/.test(chain[0])) {
      await abort('E2E_DIRECTION_LINEAGE:\n' + chain.join('\n'), 8, ctx, b);
    }
    if (await page.locator('#design-directions li.highlight').count() !== 1) {
      await abort('E2E_DIRECTION_HIGHLIGHT_MISSING', 8, ctx, b);
    }
  });

  await step('binding rebuild readback', async () => {
    const activeText = await page.locator('#design-binding-active').first().innerText();
    const bindingLine = await page.locator('#design-bindings li').first().innerText();
    if (!/绑定需重新建立/.test(activeText) || /已绑定设计系统/.test(activeText)) {
      await abort('E2E_ACTIVE_BINDING_NOT_HONEST: ' + activeText, 9, ctx, b);
    }
    if (!/未生效/.test(bindingLine) || /生效中/.test(bindingLine)) {
      await abort('E2E_RETIRED_BINDING_SHOWN_ACTIVE: ' + bindingLine, 9, ctx, b);
    }
  });

  // ------------------------------------------------------------------------
  // F-2b persistence: throw the page away and rebuild everything from the
  // service. Same versions, same chain, same honest binding state — i.e. the
  // DOM was never the source of truth.
  // ------------------------------------------------------------------------
  await step('reload persisted readback', async () => {
    await page.reload({ waitUntil: 'load' });
    await page.locator('#token').fill(token);
    await page.locator('#connect-form button').first().click();
    await page.locator('#workspace').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('#project option', { hasText: projectName })
      .first().waitFor({ state: 'attached', timeout: 20000 });
    await page.locator('#project').selectOption({ label: projectName });
    await page.locator('#design-briefs li').first().waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('#design-directions li').first().waitFor({ state: 'visible', timeout: 15000 });

    const briefRows = await page.locator('#design-briefs li').allInnerTexts();
    const directionRows = await page.locator('#design-directions li').allInnerTexts();
    if (briefRows.length !== 2 || !briefRows.some((l) => /已取代 → 版本 2/.test(l)) ||
        !briefRows.some((l) => /当前/.test(l) && /night/.test(l)) ||
        directionRows.length !== 2 ||
        !directionRows.some((l) => /CHOSEN by workbench-user/.test(l) && /Warm Gradient II/.test(l))) {
      await abort('E2E_RELOAD_VERSIONS:\n' + briefRows.join('\n') + '\n--\n' + directionRows.join('\n'),
                  10, ctx, b);
    }
    // Both chains are re-read from the service on the reloaded page.
    await page.locator('#design-briefs li', { hasText: '当前' }).first()
      .locator('button', { hasText: '版本链' }).click();
    await page.locator('#brief-lineage li', { hasText: '版本 2' })
      .first().waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('#design-directions li', { hasText: '当前' }).first()
      .locator('button', { hasText: '版本链' }).click();
    await page.locator('#direction-lineage li', { hasText: '版本 2' })
      .first().waitFor({ state: 'visible', timeout: 15000 });

    const briefChain = await page.locator('#brief-lineage li').allInnerTexts();
    const directionChain = await page.locator('#direction-lineage li').allInnerTexts();
    if (briefChain.length !== 2 || !/^版本 1 · 已取代 → 版本 2/.test(briefChain[0]) ||
        !/^版本 2 · 当前/.test(briefChain[1]) ||
        directionChain.length !== 2 || !/^版本 1 · 已取代 → 版本 2/.test(directionChain[0]) ||
        !/^版本 2 · 当前/.test(directionChain[1])) {
      await abort('E2E_RELOAD_LINEAGE:\n' + briefChain.join('\n') + '\n--\n' + directionChain.join('\n'),
                  10, ctx, b);
    }
    const activeText = await page.locator('#design-binding-active').first().innerText();
    if (!/绑定需重新建立/.test(activeText) || /已绑定设计系统/.test(activeText)) {
      await abort('E2E_RELOAD_BINDING_NOT_HONEST: ' + activeText, 10, ctx, b);
    }
  });

  await step('mobile appshell layout', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    const layout = await page.evaluate(async () => {
      const nav = document.querySelector('.app-nav');
      const items = Array.from(document.querySelectorAll('.app-nav-item'));
      const rect = nav?.getBoundingClientRect();
      const firstStyle = items.length ? getComputedStyle(items[0]) : null;
      // Hash the module THIS document was able to load from the same origin: the page and
      // the driver must be describing the same bytes, or the inventory below is about some
      // other bundle. (crypto.subtle is present on http://127.0.0.1, which Chrome treats as
      // a secure context; when it is absent the length check below still applies.)
      const served = await fetch('/workbench/main.js');
      const servedText = await served.text();
      let servedSha = null;
      if (globalThis.crypto?.subtle) {
        const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(servedText));
        servedSha = Array.from(new Uint8Array(buf))
          .map((x) => x.toString(16).padStart(2, '0')).join('');
      }
      return {
        itemRoutes: items.map((i) => i.dataset?.route ?? ''),
        fontSize: firstStyle ? Number.parseFloat(firstStyle.fontSize) : 0,
        navLeft: rect?.left ?? -1,
        navWidth: rect?.width ?? 0,
        navHeight: rect?.height ?? 0,
        overflowX: nav ? getComputedStyle(nav).overflowX : '',
        servedStatus: served.status,
        servedLength: servedText.length,
        servedSha,
      };
    });
    // The app-shell geometry reading is unchanged: same thresholds, same exit code.
    if (layout.fontSize < 10 || layout.navLeft !== 0 || layout.navWidth < 380 ||
        layout.navHeight > 120 || layout.overflowX !== 'auto') {
      await abort('E2E_MOBILE_APPSHELL_LAYOUT: ' + JSON.stringify(layout), 11, ctx, b);
    }

    // --- route inventory: mounted nav vs the table that produced it --------------
    let bundleText = null;
    let bundleStatus = 'FETCH_THREW';
    try {
      const res = await fetch(base + '/workbench/main.js');
      bundleStatus = String(res.status);
      if (res.ok) bundleText = await res.text();
    } catch (e) {
      bundleStatus = 'FETCH_ERROR ' + e.message.split('\n')[0];
    }
    if (bundleText === null) {
      await abort('E2E_BUNDLE_FETCH_FAILED: /workbench/main.js answered ' + bundleStatus, 12, ctx, b);
    }
    const table = parseRouteViews(bundleText);
    if (table === null) {
      await abort('E2E_ROUTE_TABLE_UNREADABLE: no parseable `' + ROUTE_TABLE_MARKER +
                  '` in the served bundle (' + bundleText.length + ' chars, sha256:' +
                  sha256Hex(bundleText) + ')', 12, ctx, b);
    }
    const parsedSha = sha256Hex(bundleText);
    if (layout.servedStatus !== 200 || layout.servedLength !== bundleText.length ||
        (layout.servedSha !== null && layout.servedSha !== parsedSha)) {
      await abort('E2E_BUNDLE_IDENTITY_MISMATCH: driver parsed sha256:' + parsedSha +
                  ' (' + bundleText.length + ' chars) but the page fetched status=' +
                  layout.servedStatus + ' length=' + layout.servedLength +
                  ' sha256:' + (layout.servedSha ?? 'unavailable'), 12, ctx, b);
    }
    const mounted = [...layout.itemRoutes].sort();
    const expected = table.map((r) => r.view).sort();
    routeInventory = {
      source: 'served bundle GET ' + base + '/workbench/main.js',
      bundleSha256: parsedSha,
      bundleChars: bundleText.length,
      tableEntryCount: table.length,
      navItemCount: mounted.length,
      tableViews: table.map((r) => r.view),
      tableHashes: table.map((r) => r.hash),
      navRoutes: mounted,
    };
    // EXACT equality on both the count and the membership, for the same reason the
    // literal did: this is the reading that says every table entry reached the screen as
    // a real button and no button exists that the table does not name. A route that stops
    // rendering, a button that appears without a route, and a re-labelled view all go red.
    // It is an inventory, not a product limit: the taskpack says the menu count is not
    // fixed ("不机械固定3菜单/16页"), and it now moves with the table with nobody editing
    // this file.
    if (mounted.length !== table.length || mounted.join('\u0000') !== expected.join('\u0000')) {
      await abort('E2E_NAV_ROUTE_INVENTORY: nav=' + mounted.length +
                  ' table=' + table.length +
                  ' nav-only=[' + mounted.filter((v) => !expected.includes(v)).join(',') +
                  '] table-only=[' + expected.filter((v) => !mounted.includes(v)).join(',') +
                  '] ' + JSON.stringify(routeInventory), 12, ctx, b);
    }
    console.log('E2E_ROUTE_INVENTORY: ' + JSON.stringify({
      nav: mounted.length, table: table.length, bundleSha256: parsedSha,
    }));
  });

  // ------------------------------------------------------------------------
  // K-NAV-VISIBLE: on a routed screen the B10 sidebar is the only element that
  // says "you are here", and its 21 buttons live in an `overflow:auto` column
  // that is taller than a desktop window. Opening a late route must scroll the
  // COLUMN to the selected button; before 2026-10-24 sync() only toggled
  // .active/aria-current, so the screen could open with no visible selection.
  // The target is the last ROUTE_VIEWS row, read back from the inventory step
  // above rather than typed here. That is what makes the reading directional:
  // once the column overflows, the last button can only be inside the
  // scrollport if the column itself moved (scrollTop > 0), never because the
  // item happened to be on screen.
  // ------------------------------------------------------------------------
  await step('the rail users actually see is the folded one', async () => {
    // 2026-10-27: the first STITCH fold landed on `.app-nav`, which mountB10Shell hides on every
    // routed screen -- the change was gated, green, and invisible. This step is the guard for that
    // class: it measures the element the operator actually sees, and it fails if the legacy rail is
    // the visible one, so a fold applied only there can never pass again.
    // The viewport is set here because `offsetParent` is null for the whole rail below 840px (the
    // sidebar becomes an off-canvas drawer there); the first run of this step proved that by
    // reporting 23 buttons and 0 visible -- a precondition of the measurement, not a product defect.
    // The hash matters for the same reason: on the legacy workbench view (empty hash) the B10
    // sidebar is the thing that hides, so the step must be standing on a routed screen to measure
    // the rail an operator sees.
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.evaluate(() => { window.location.hash = '#/knowledge'; });
    await page.locator('#app-sidebar .nav button[data-route="knowledge"]')
      .waitFor({ state: 'visible', timeout: 15000 });
    const reading = await page.evaluate(() => {
      const nav = document.querySelector('#app-sidebar .nav');
      const legacy = document.querySelector('.app-nav');
      const all = nav ? [...nav.querySelectorAll('button[data-route]')] : [];
      const shown = () => all.filter((b) => b.offsetParent !== null).map((b) => b.dataset.route);
      const fold = nav ? nav.querySelector('.nav-fold') : null;
      const closedFirst = shown().length;
      if (fold) fold.click();
      const opened = shown().length;
      if (fold) fold.click();
      const closed = shown().length;
      return {
        total: all.length, closedFirst, opened, closed, hasFold: !!fold,
        legacyVisible: !!legacy && legacy.offsetParent !== null,
        groupsShown: nav ? [...nav.querySelectorAll('.nav-group')]
          .filter((g) => g.offsetParent !== null).length : -1,
      };
    });
    if (!reading.hasFold || reading.legacyVisible) {
      await abort('E2E_NAV_FOLD_SURFACE: the fold must live on the visible sidebar and the legacy '
                  + 'rail must stay hidden on a routed screen: ' + JSON.stringify(reading), 13, ctx, b);
    }
    // `closedFirst` may already be the full list when the current route is a folded one -- sync()
    // opens the rail so the active item is visible -- so the assertion is on the toggle's two ends,
    // not on what the page happened to show first.
    if (!(reading.closed < reading.total) || reading.opened !== reading.total) {
      await abort('E2E_NAV_FOLD_INERT: folding hides nothing, or 全部功能 does not restore every '
                  + 'route: ' + JSON.stringify(reading), 13, ctx, b);
    }
    if (reading.groupsShown !== 0) {
      await abort('E2E_NAV_FOLD_GROUPS: the boards carry no group headings in the rail, and the '
                  + 'fold is supposed to hide them: ' + JSON.stringify(reading), 13, ctx, b);
    }
    console.log('E2E_NAV_FOLD: ' + JSON.stringify(reading));
  });
  await step('desktop sidebar keeps the active route visible', async () => {
    if (!routeInventory) {
      await abort('E2E_NAV_ACTIVE_NO_INVENTORY: route inventory step did not run', 13, ctx, b);
    }
    const lastView = routeInventory.tableViews[routeInventory.tableViews.length - 1];
    const lastHash = routeInventory.tableHashes[routeInventory.tableHashes.length - 1];
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.evaluate((hash) => { window.location.hash = hash; }, lastHash);
    // aria-current is stamped by the same sync() loop that scrolls the column,
    // so waiting for it waits for the scroll without sleeping.
    await page.locator('#app-sidebar .nav button[data-route="' + lastView + '"][aria-current="page"]')
      .waitFor({ state: 'attached', timeout: 15000 });
    const reading = await page.evaluate((view) => {
      const nav = document.querySelector('#app-sidebar .nav');
      const active = nav?.querySelector('button[data-route="' + view + '"]');
      const navRect = nav.getBoundingClientRect();
      const itemRect = active.getBoundingClientRect();
      return {
        view,
        selected: active.getAttribute('aria-current') === 'page',
        scrollTop: nav.scrollTop,
        scrollHeight: nav.scrollHeight,
        clientHeight: nav.clientHeight,
        navTop: navRect.top, navBottom: navRect.bottom,
        itemTop: itemRect.top, itemBottom: itemRect.bottom, itemHeight: itemRect.height,
      };
    }, lastView);
    // A column that fits its content cannot prove the mechanism, so this is a
    // declared precondition: if the sidebar ever stops overflowing at 1280x800,
    // re-think this reading instead of letting it pass while asserting nothing.
    if (reading.clientHeight < 1 || reading.scrollHeight <= reading.clientHeight + 1) {
      await abort('E2E_NAV_SCROLL_PRECONDITION: the sidebar does not scroll at 1280x800, so ' +
                  'this reading would be vacuous: ' + JSON.stringify(reading), 13, ctx, b);
    }
    if (!reading.selected || reading.itemHeight < 1 || reading.scrollTop <= 0 ||
        reading.itemTop < reading.navTop - 1 || reading.itemBottom > reading.navBottom + 1) {
      await abort('E2E_NAV_ACTIVE_NOT_VISIBLE: ' + JSON.stringify(reading), 13, ctx, b);
    }
    console.log('E2E_NAV_ACTIVE_VISIBLE: ' + JSON.stringify(reading));
    navVisibility = reading;
    // Hand the page back to the legacy workbench view (and the viewport the
    // mobile step left behind) that the closing persisted-state readback reads.
    await page.evaluate(() => { window.location.hash = ''; });
    await page.locator('#design-briefs li').first()
      .waitFor({ state: 'visible', timeout: 15000 });
    await page.setViewportSize({ width: 390, height: 844 });
  });

  // Read back the final state as the persisted-state proof.
  const activeText = await page.locator('#design-binding-active').first().innerText();
  const bindingLine = await page.locator('#design-bindings li').first().innerText();
  const directionLine = await page.locator('#design-directions li', { hasText: '当前' }).first().innerText();
  const briefLine = await page.locator('#design-briefs li', { hasText: '当前' }).first().innerText();
  const directionChain = await page.locator('#direction-lineage li').allInnerTexts();
  const briefChain = await page.locator('#brief-lineage li').allInnerTexts();

  // Failure checks happen BEFORE the teardown so a failure screenshot can be
  // captured while the page (and its DOM state) is still alive.
  if (errors.length) {
    const tail = errors.slice(0, 8).join(' ;; ');
    await abort('E2E_BROWSER_ERRORS: ' + tail, 4, ctx, b);
  }
  if (!/绑定需重新建立/.test(activeText) || /已绑定设计系统/.test(activeText) ||
      !/未生效/.test(bindingLine) || /生效中/.test(bindingLine) ||
      !/CHOSEN by workbench-user/.test(directionLine) || !/night/.test(briefLine) ||
      briefChain.length !== 2 || directionChain.length !== 2) {
    const detail = 'E2E_READBACK_MISMATCH:\n' + activeText + '\n' + bindingLine + '\n' +
                   directionLine + '\n' + briefLine + '\n' + briefChain.join('\n') + '\n--\n' +
                   directionChain.join('\n');
    await abort(detail, 5, ctx, b);
  }

  // The export exit, in a real browser. appshell ㉒ already drives the same sequence in jsdom,
  // but a DOM shim cannot say whether the control is really clickable, whether the GET really
  // leaves the page, or whether the panel really paints the service's bytes. This is the chain
  // that answers those three: create -> a named human approves -> the row's control goes live ->
  // the panel renders both projections, the stored ids and the outbound facts.
  await page.evaluate(() => { window.location.hash = '#/records'; });
  await page.locator('#knowledge-create-submit').waitFor({ state: 'visible', timeout: 20000 });
  await page.locator('#knowledge-type').selectOption('METHOD');
  await page.locator('#knowledge-title').fill('E2E export chain');
  await page.locator('#knowledge-statement')
    .fill('the export exit is reachable from the page, not only from a route');
  await page.locator('#knowledge-applies-to').fill('editorial');
  await page.locator('#knowledge-license').fill('project-internal');
  await page.locator('#knowledge-rights').selectOption('CHECKED');
  await page.locator('#knowledge-client-asset').selectOption('false');
  await page.locator('#knowledge-third-party').selectOption('false');
  await page.locator('#knowledge-job-mode').selectOption('fill');
  await page.locator('#knowledge-job').fill('job-e2e-export');
  // The declination branch, exercised on the wire: 不使用 sends the literal, and the filled
  // job_id above travels unchanged beside it.
  await page.locator('#knowledge-operation-mode').selectOption('unused');
  await page.locator('#knowledge-evidence').fill('sha256:' + 'e'.repeat(64));
  await page.locator('#knowledge-create-submit').click();
  // Wait on the control's actual state, not its visibility: the row is already on screen before
  // the reload, so a visibility wait passes against the stale DOM and reads the wrong answer.
  const outcomeText = async () => page.locator('#knowledge-outcome').innerText();
  const waitExportEnabled = async (want) => page.waitForFunction((expected) => {
    const button = document.getElementById('knowledge-export-0');
    return !!button && (expected ? !button.disabled : button.disabled);
  }, want, { timeout: 20000 }).then(() => true).catch(() => false);
  if (!await waitExportEnabled(false)) {
    await abort('E2E_EXPORT_LIVE_BEFORE_APPROVAL: an unapproved candidate offered a working '
                + 'export control; outcome=' + await outcomeText(), 13, ctx, b);
  }
  await page.locator('#knowledge-review-target').selectOption({ index: 0 });
  await page.locator('#knowledge-decision').selectOption('APPROVE');
  await page.locator('#knowledge-reviewer').fill('E2E Reviewer');
  await page.locator('#knowledge-review-submit').click();
  if (!await waitExportEnabled(true)) {
    await abort('E2E_EXPORT_STILL_BLOCKED_AFTER_APPROVAL: outcome=' + await outcomeText()
                + ' row=' + await page.locator('#knowledge-body').innerText()
                  .then((text) => text.slice(0, 300)), 13, ctx, b);
  }
  await page.locator('#knowledge-export-0').click();
  // The panel starts in a loading state; read it only once that text is gone, or the assertion
  // below measures a spinner.
  await page.waitForFunction(() => {
    const node = document.getElementById('knowledge-export-body');
    return !!node && !/正在读回/.test(node.textContent) && node.textContent.length > 40;
  }, null, { timeout: 20000 });
  const exportText = await page.locator('#knowledge-export-body').innerText();
  const missing = ['CANDIDATE_EXPORT',
    // The envelope and the document it wraps carry DIFFERENT versions: the envelope is
    // ...-export-envelope/v1, the wrapped v2 export document has always been ...-export/v1.
    // Asserting both, side by side, is the browser-side twin of the collision the render caught.
    'design-lab/assurance-knowledge-candidate-export-envelope/v1',
    'design-lab/assurance-knowledge-candidate-export/v1',
    'design-lab/candidate-knowledge/v1',
    'job-e2e-export:UNUSED', 'USER_SUPPLIED', 'EXPLICITLY_UNUSED',
    'NOT_CONNECTED', 'sent_count=0', 'bytes=']
    .filter((needle) => !exportText.includes(needle));
  if (missing.length || /已发送|发送成功|delivered/i.test(exportText)) {
    await abort('E2E_EXPORT_PANEL: missing=' + JSON.stringify(missing)
                + ' text=' + exportText.slice(0, 300), 13, ctx, b);
  }
  console.log('E2E_EXPORT_EXIT: ' + JSON.stringify({
    envelope: exportText.includes(
      'design-lab/assurance-knowledge-candidate-export-envelope/v1'),
    sentClaim: /已发送|发送成功|delivered/i.test(exportText),
    bytes: (exportText.match(/bytes=(\d+)/) || [])[1] ?? null,
  }));

  // 14. The prompt result travels through the shipped page. The two prompt routes used to answer
  // and keep nothing, so nothing on this page could be signed; this section drives the real
  // affordance -- compose -> the stored row appears -> a named human signs it -> the row's own
  // state word changes. Every wait here is on a DOM fact the panel can only have after the wire
  // answered: the panel's own explanatory copy mentions UNREVIEWED / ACCEPTED / NOT_CURRENT as
  // words, so a substring search over the whole panel can pass with zero rows. That is how the
  // first version of this section lied to itself, and it is why the row is identified by the
  // OPTION VALUE the service mints, not by prose.
  await page.evaluate(() => { window.location.hash = '#/prompts'; });
  await page.locator('#prompt-brief').waitFor({ state: 'visible', timeout: 20000 });
  // The chain revised its brief, so this select carries a v1 labelled 已被取代 and a v2 that is
  // current. Choosing by index would silently pick whichever one the server refuses.
  const currentBrief = await page.locator('#prompt-brief option').evaluateAll(
    (options) => (options.find((o) => o.value && !/已被取代/.test(o.textContent ?? ''))
      ?? {}).value ?? '');
  if (!currentBrief) {
    await abort('E2E_PROMPT_NO_CURRENT_BRIEF: the brief select offered no un-superseded option',
      14, ctx, b);
  }
  await page.locator('#prompt-brief').selectOption(currentBrief);
  await page.locator('#prompt-target').selectOption('image-generation');
  const storedRowId = () => page.locator('#prompt-review-result option').evaluateAll(
    (options) => options.map((o) => o.value).find((value) =>
      /^(prompt|reversal)-[0-9a-f]{32}$/.test(value)) ?? '');
  await page.locator('#prompt-compose').click();
  await page.waitForFunction(() => Array.from(
    document.querySelectorAll('#prompt-review-result option'))
    .some((o) => /^(prompt|reversal)-[0-9a-f]{32}$/.test(o.value)), null,
  { timeout: 30000 }).catch(() => false);
  const reviewTarget = await storedRowId();
  if (!reviewTarget) {
    const diagnostics = await page.evaluate(() => ({
      options: Array.from(document.querySelectorAll('#prompt-review-result option'))
        .map((o) => o.value),
      compose: (document.getElementById('prompt-compose-outcome')?.innerText ?? '').slice(0, 300),
      status: (document.getElementById('prompt-compose-status')?.innerText ?? '').slice(0, 200),
    }));
    await abort('E2E_PROMPT_NO_STORED_ROW: '
                + JSON.stringify(diagnostics).replace(/[\r\n]+/g, ' · '), 14, ctx, b);
  }
  const resultsText = () => page.locator('#prompt-results-panel').innerText();
  const rowText = await page.locator('#prompt-results-panel tbody tr').first().innerText();
  if (!/UNREVIEWED/.test(rowText) || !/没人签过/.test(rowText)) {
    await abort('E2E_PROMPT_ROW_STATE: the stored row did not present itself as produced but '
                + 'unsigned. row=' + rowText.replace(/[\r\n]+/g, ' · '), 14, ctx, b);
  }
  if (!/reviewer_kind="human"/.test(await resultsText())) {
    await abort('E2E_PROMPT_SIGN_BOUNDARY_MISSING: the panel must say that signing is a human act '
                + 'the service enforces.', 14, ctx, b);
  }
  await page.locator('#prompt-review-result').selectOption(reviewTarget);
  await page.locator('#prompt-review-decision').selectOption('ACCEPTED');
  // The local refusal first: an unnamed signature must never reach the wire.
  await page.locator('#prompt-review-submit').click();
  const refusedLocally = await resultsText();
  if (!/未提交：裁决人未署名/.test(refusedLocally)) {
    await abort('E2E_PROMPT_ANON_SIGN_NOT_REFUSED: an empty reviewer name should be stopped on '
                + 'the page. text=' + refusedLocally.slice(-300).replace(/[\r\n]+/g, ' · '),
    14, ctx, b);
  }
  await page.locator('#prompt-review-reviewer').fill('E2E Reviewer');
  await page.locator('#prompt-review-note').fill('read the assembled fields against the digest');
  await page.locator('#prompt-review-submit').click();
  await page.waitForFunction(() => {
    const rows = document.querySelectorAll('#prompt-results-panel tbody tr');
    return rows.length > 0 && /ACCEPTED/.test(rows[0].textContent)
      && /E2E Reviewer/.test(rows[0].textContent);
  }, null, { timeout: 30000 }).catch(() => false);
  const signedRow = await page.locator('#prompt-results-panel tbody tr').first().innerText();
  if (!/ACCEPTED/.test(signedRow) || !/E2E Reviewer/.test(signedRow)) {
    await abort('E2E_PROMPT_SIGN_NOT_READ_BACK: the row did not come back carrying the human '
                + 'signature. row=' + signedRow.replace(/[\r\n]+/g, ' · '), 14, ctx, b);
  }
  const panelAfter = await resultsText();
  if (/已发送|发送成功|delivered|模型已执行/.test(panelAfter)) {
    await abort('E2E_PROMPT_OVERCLAIM: the results panel asserted a delivery or an inference run: '
                + panelAfter.slice(0, 300), 14, ctx, b);
  }
  promptLoop = {
    resultId: reviewTarget,
    unsignedRow: /UNREVIEWED/.test(rowText),
    signedRow: /ACCEPTED/.test(signedRow),
    reviewerShown: /E2E Reviewer/.test(signedRow),
    overclaim: /已发送|发送成功|delivered|模型已执行/.test(panelAfter),
  };
  console.log('E2E_PROMPT_LOOP: ' + JSON.stringify(promptLoop));

  // ------------------------------------------------------------------------
  // DL-KB-08: the design-assistant screen. The acceptance is about the RENDERED
  // page, so every claim below is read from the DOM after the service answered:
  //   · the initial screen exposes requirement / reference / output type only
  //     (no tool or model picker), and the vocabulary comes from the service;
  //   · one saved plan shows the four states separately: 已保存 / 方案已提供 /
  //     用户选用 / 外部未验证;
  //   · copying is a real, working action BEFORE any adoption, and it puts no
  //     write or choose on the wire;
  //   · an empty requirement is refused locally and the form still works, so
  //     there is no dead end;
  //   · supplying the missing creative appends r2, a named human chooses it, and
  //     a full page reload rebuilds the same four states from the service.
  // ------------------------------------------------------------------------
  await step('design assistant four states', async () => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.evaluate(() => { window.location.hash = '#/assistant'; });
    await page.locator('#as-objective').waitFor({ state: 'visible', timeout: 20000 });

    const initial = await page.evaluate(() => {
      const form = document.getElementById('as-form');
      const controls = Array.from(form.querySelectorAll('select,input,textarea'));
      const chips = Array.from(
        document.querySelectorAll('#as-output-type input[type=radio]'));
      // A chip whose label breaks into one CJK character per line is not "narrow", it is
      // unreadable -- and every geometry gate stays green over it because the box still fits.
      // So the label's own line boxes are counted, via the Range over its text node.
      const labelBoxes = Array.from(
        document.querySelectorAll('#as-output-type .as-chip span')).map((span) => {
        const range = document.createRange();
        range.selectNodeContents(span);
        return range.getClientRects().length;
      });
      return {
        selects: Array.from(form.querySelectorAll('select')).map((s) => s.id),
        toolish: controls.map((c) => c.id).filter((id) => /tool|model/i.test(id)),
        chips: chips.map((chip) => chip.value),
        chipGroup: document.querySelector('#as-output-type')?.getAttribute('role') ?? '',
        preselected: chips.filter((chip) => chip.checked).length,
        multiLineLabels: labelBoxes.filter((boxes) => boxes > 1).length,
        canvases: document.querySelectorAll('#route-view canvas').length,
        logs: document.querySelectorAll('#route-view [role="log"]').length,
      };
    });
    // The task says the initial screen exposes requirement, reference attachment
    // and output type; tools and models are chosen later. Two selects is the
    // rendered shape of that sentence (workspace + reference picker), and an id naming a
    // tool/model would mean the deferred picker had crept back in. The output type is the
    // chip row the board draws, so its shape is asserted as a radiogroup carrying the six
    // served words with nothing preselected -- a chip the page chose itself would be the
    // page deciding what the designer wants.
    if (initial.selects.length !== 2 || initial.toolish.length !== 0 ||
        initial.chipGroup !== 'radiogroup' || initial.preselected !== 0 ||
        initial.multiLineLabels !== 0 ||
        initial.chips.length !== 6 || !initial.chips.includes('STORYBOARD')) {
      await abort('E2E_ASSISTANT_INITIAL_SURFACE: ' + JSON.stringify(initial), 15, ctx, b);
    }
    if (initial.canvases !== 0 || initial.logs !== 0) {
      await abort('E2E_ASSISTANT_CHAT_SURFACE: the route rendered a canvas or a message log: '
                  + JSON.stringify(initial), 15, ctx, b);
    }
    // Printed on the way through, so a green run leaves the shape it accepted behind.
    console.log('E2E_ASSISTANT_INITIAL: ' + JSON.stringify(initial));

    const objectiveText = '为秋季新品写一条可读的分镜目标，给标题留白';
    await page.locator('#as-output-type input[value="STORYBOARD"]').check();
    const outputTypeLabel = await page.evaluate(() => (
      document.querySelector('#as-output-type label:has(input:checked) span')?.textContent ?? ''
    ).trim());
    await page.locator('#as-objective').fill(objectiveText);
    await page.locator('#as-author').fill('E2E Assistant Author');
    await page.locator('#as-submit').click();
    const savedTrue = () => page.waitForFunction(() => {
      const node = document.getElementById('as-saved');
      return !!node && node.dataset.state === 'true';
    }, null, { timeout: 25000 }).then(() => true).catch(() => false);
    if (!await savedTrue()) {
      const why = await page.evaluate(() => ({
        error: document.getElementById('as-form-error')?.textContent ?? '',
        status: document.getElementById('as-form-status')?.textContent ?? '',
        detail: document.getElementById('as-detail')?.textContent?.slice(0, 300) ?? '',
      }));
      await abort('E2E_ASSISTANT_NOT_SAVED: ' + JSON.stringify(why), 15, ctx, b);
    }

    const readStates = () => page.evaluate(() => {
      const chip = (id) => {
        const node = document.getElementById(id);
        return node ? { text: node.textContent ?? '', state: node.dataset.state ?? '' } : null;
      };
      const primary = Array.from(
        document.querySelectorAll('#as-actions .primary-btn')).map((b) => b.id);
      return { saved: chip('as-saved'), provided: chip('as-provided'),
               chosen: chip('as-chosen'), external: chip('as-external'), primary };
    });
    const afterSave = await readStates();
    if (!afterSave.saved || afterSave.saved.state !== 'true' ||
        afterSave.provided?.state !== 'false' || afterSave.chosen?.state !== 'false' ||
        afterSave.external?.state !== 'false' ||
        afterSave.primary.length !== 1 || afterSave.primary[0] !== 'as-supply') {
      await abort('E2E_ASSISTANT_STATES_AFTER_SAVE: ' + JSON.stringify(afterSave), 15, ctx, b);
    }
    const detailText = () => page.locator('#as-plan').innerText();
    const savedDetail = await detailText();
    if (!/尚未提供创意/.test(savedDetail)
        || !/还没有可读的脚本；这条方案也没有登记镜头行/.test(savedDetail)) {
      await abort('E2E_ASSISTANT_STORYBOARD_WITHOUT_CREATIVE: '
                  + savedDetail.slice(0, 400).replace(/[\r\n]+/g, ' · '), 15, ctx, b);
    }

    // Empty requirement: refused on the page, and no assistance-plan write leaves.
    const writesBeforeEmpty = assistanceWrites;
    await page.locator('#as-submit').click();
    const emptyRefused = await page.waitForFunction(() => {
      const node = document.getElementById('as-form-error');
      return !!node && /请先写下/.test(node.textContent ?? '');
    }, null, { timeout: 8000 }).then(() => true).catch(() => false);
    const focusAfterEmpty = await page.evaluate(
      () => document.activeElement?.id ?? '');
    if (!emptyRefused || assistanceWrites !== writesBeforeEmpty ||
        focusAfterEmpty !== 'as-objective') {
      await abort('E2E_ASSISTANT_EMPTY_DEAD_END: refused=' + emptyRefused +
                  ' writes=' + assistanceWrites + '/' + writesBeforeEmpty +
                  ' focus=' + focusAfterEmpty, 15, ctx, b);
    }

    // Copy is available with no approval and no adoption, and it is provably not
    // an adoption: the counters must not move.
    const choosesBeforeCopy = assistanceChooses;
    const writesBeforeCopy = assistanceWrites;
    await page.bringToFront();
    await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: base });
    await page.locator('#as-copy').click();
    const copyNote = await page.waitForFunction(() => {
      const note = document.getElementById('as-copy-note');
      if (!note) return false;
      return /已复制/.test(note.textContent ?? '') || !!note.querySelector('textarea');
    }, null, { timeout: 8000 }).then(() => page.locator('#as-copy-note').innerText())
      .catch(() => '');
    let clipboardText = '';
    try {
      clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    } catch { /* the note path below is still evidence */ }
    if (!/已复制/.test(copyNote) && !clipboardText.includes(objectiveText)) {
      await abort('E2E_ASSISTANT_COPY_BLOCKED: note=' + JSON.stringify(copyNote), 15, ctx, b);
    }
    // The clipboard now carries a material the service rendered (DL-KB-11), not text the page
    // assembled. The two sentences asserted here are the emitter's own: the state line that says
    // no external result was verified, and the closing line that says a download is not a
    // delivery. Copying must still move neither counter.
    if (!clipboardText.includes(objectiveText) ||
        !clipboardText.includes('外部结果未被系统核验') ||
        !clipboardText.includes('下载不等于交付')) {
      await abort('E2E_ASSISTANT_COPY_TEXT: clipboard=' + JSON.stringify(clipboardText.slice(0, 200)),
                  15, ctx, b);
    }
    if (assistanceWrites !== writesBeforeCopy || assistanceChooses !== choosesBeforeCopy) {
      await abort('E2E_ASSISTANT_COPY_WROTE: writes=' + assistanceWrites + '/' + writesBeforeCopy +
                  ' chooses=' + assistanceChooses + '/' + choosesBeforeCopy, 15, ctx, b);
    }
    const copyWroteNothing = assistanceWrites === writesBeforeCopy;
    const copyChoseNothing = assistanceChooses === choosesBeforeCopy;

    // Supply the missing creative: the primary action opens the prefilled form,
    // saving appends r2 and the provided state flips — the "no dead end" path.
    await page.locator('#as-supply').click();
    const editReady = await page.waitForFunction(() => {
      const submit = document.getElementById('as-submit');
      return !!submit && /保存为新修订/.test(submit.textContent ?? '');
    }, null, { timeout: 15000 }).then(() => true).catch(() => false);
    if (!editReady) {
      await abort('E2E_ASSISTANT_EDIT_NOT_PREFILLED', 15, ctx, b);
    }
    await page.locator('#as-creative').fill(
      '镜头 1：俯拍整张桌面；镜头 2：手指沿纸边划过；镜头 3：标题留白收束。');
    await page.locator('#as-submit').click();
    const providedTrue = await page.waitForFunction(() => {
      const node = document.getElementById('as-provided');
      return !!node && node.dataset.state === 'true';
    }, null, { timeout: 25000 }).then(() => true).catch(() => false);
    if (!providedTrue) {
      await abort('E2E_ASSISTANT_CREATIVE_NOT_READ_BACK: '
                  + JSON.stringify(await readStates()), 15, ctx, b);
    }
    const afterProvided = await readStates();
    if (afterProvided.saved?.state !== 'true' || afterProvided.chosen?.state !== 'false' ||
        afterProvided.external?.state !== 'false' ||
        afterProvided.primary.length !== 1 || afterProvided.primary[0] !== 'as-choose') {
      await abort('E2E_ASSISTANT_STATES_AFTER_CREATIVE: ' + JSON.stringify(afterProvided),
                  15, ctx, b);
    }
    const providedDetail = await detailText();
    // The shot table exists now, so the honesty this guard asks for is the sharper version: the
    // screen must say THIS plan registered no rows, must refuse to pass an empty table off as a
    // storyboard, and must name where the rows are written. A creative that enumerates 镜头 1/2/3
    // in prose is exactly the case where a page could be tempted to print a table it does not have.
    if (!/没有登记镜头行/.test(providedDetail)
        || !/页面不画一张空表/.test(providedDetail)
        || !/逐行写镜头/.test(providedDetail)) {
      await abort('E2E_ASSISTANT_STORYBOARD_HONESTY: the storyboard section did not say this plan '
                  + 'registered no shot rows, that no empty table will be drawn, and where to '
                  + 'write them: '
                  + providedDetail.slice(0, 400).replace(/[\r\n]+/g, ' · '), 15, ctx, b);
    }

    // A named human adopts it; the actor is rendered in the detail, not only in
    // a transient note.
    await page.locator('#as-choose').click();
    await page.locator('#as-choose-name').fill('E2E Assistant Reviewer');
    const choosesBeforeAdopt = assistanceChooses;
    await page.locator('#as-choose-submit').click();
    const chosenTrue = await page.waitForFunction(() => {
      const node = document.getElementById('as-chosen');
      return !!node && node.dataset.state === 'true';
    }, null, { timeout: 25000 }).then(() => true).catch(() => false);
    if (!chosenTrue || assistanceChooses !== choosesBeforeAdopt + 1) {
      await abort('E2E_ASSISTANT_CHOOSE_NOT_RECORDED: chosen=' + chosenTrue +
                  ' chooses=' + assistanceChooses + '/' + (choosesBeforeAdopt + 1) +
                  ' states=' + JSON.stringify(await readStates()), 15, ctx, b);
    }
    const afterChoose = await readStates();
    const choiceLine = await page.locator('#as-choice').innerText();
    if (afterChoose.primary.length !== 1 || afterChoose.primary[0] !== 'as-revise' ||
        !/E2E Assistant Reviewer/.test(choiceLine) || !/r2/.test(afterChoose.chosen?.text ?? '')) {
      await abort('E2E_ASSISTANT_STATES_AFTER_CHOOSE: ' + JSON.stringify(afterChoose)
                  + ' choice=' + choiceLine, 15, ctx, b);
    }
    // Revision history keeps both versions, newest marked 最新.
    await page.locator('#as-revisions > summary').click();
    await page.waitForFunction(
      () => document.querySelectorAll('#as-revisions li').length >= 2,
      null, { timeout: 10000 }).catch(() => {});
    const revisionRows = await page.locator('#as-revisions li').allInnerTexts();
    // assistance_plan.detail() orders revisions ascending (`ORDER BY revision`), and the
    // page renders that readback order unchanged; the newest row carries 最新.
    if (revisionRows.length !== 2 || !/^r1/.test(revisionRows[0]) ||
        !/旧版本/.test(revisionRows[0]) || !/^r2/.test(revisionRows[1]) ||
        !/最新/.test(revisionRows[1])) {
      await abort('E2E_ASSISTANT_REVISIONS: ' + JSON.stringify(revisionRows), 15, ctx, b);
    }

    // ---- DL-KB-11 交接材料 -----------------------------------------------------
    // The format list the page offers is the list the service renders: the vocabulary envelope is
    // read here as its own request, and the rendered <option> set must equal it. Four words typed
    // into shell.ts would render four plausible options and still fail this comparison.
    const vocabulary = await page.evaluate(async (bearer) => (
      await (await fetch('/api/assistance-plan-output-types',
        { headers: { Authorization: 'Bearer ' + bearer } })).json()), token);
    const servedFormats = (vocabulary.export_formats ?? []).map((row) => row.value);
    const materialDom = await page.evaluate(() => Array.from(
      document.querySelectorAll('#as-material option')).map((o) => o.value).filter(Boolean));
    const copyFormat = await page.evaluate(
      () => document.getElementById('as-material')?.value ?? '');
    if (servedFormats.length !== 4
        || JSON.stringify(materialDom) !== JSON.stringify(servedFormats)) {
      await abort('E2E_ASSISTANT_MATERIAL_FORMATS: dom=' + JSON.stringify(materialDom)
                  + ' served=' + JSON.stringify(servedFormats), 15, ctx, b);
    }
    // The plan this lane filed has no shot rows, so the 分镜 CSV must be refused by name rather
    // than downloaded as an empty table. The refusal arrives through the same button a designer
    // would press, which is the only way to prove the page shows the reason instead of a spinner.
    const noteWhen = (source) => page.waitForFunction((needle) => {
      const node = document.getElementById('as-copy-note');
      const text = node ? (node.textContent ?? '') : '';
      return text.includes(needle) ? text : null;
    }, source, { timeout: 20000 }).then((handle) => handle.jsonValue()).catch(() => '');
    const csvValue = servedFormats.find((value) => value === 'storyboard_csv') ?? '';
    await page.locator('#as-material').selectOption(csvValue);
    const csvGet = page.waitForResponse(
      (r) => /\/assistance-plans\/aplan-[0-9a-f]{32}\/export/.test(r.url())
             && /[?&]format=storyboard_csv/.test(r.url()), { timeout: 25000 });
    const errorsBeforeCsv = errors.length;
    await page.locator('#as-download').click();
    const csvStatus = await csvGet.then((r) => r.status()).catch(() => 0);
    const csvNote = await noteWhen('PLAN_EXPORT_NO_SHOTS');
    // Chromium logs every non-2xx response as a console error, and this 409 is the point of the
    // step. The lane's net is "no UNEXPECTED console error", so this single message is accounted
    // for here and only here -- anything else the page logged still fails the run at the end.
    let csvConsole = [];
    for (let tick = 0; tick < 60; tick += 1) {
      csvConsole = errors.splice(errorsBeforeCsv);
      if (csvConsole.length) break;
      await new Promise((resolve) => { setTimeout(resolve, 50); });
    }
    const csvRefused = csvStatus === 409 && /PLAN_EXPORT_NO_SHOTS/.test(csvNote)
      && /下一步/.test(csvNote) && csvConsole.length === 1
      && /status of 409 \(Conflict\)/.test(csvConsole[0]);
    if (!csvRefused) {
      await abort('E2E_ASSISTANT_MATERIAL_CSV_REFUSAL: status=' + csvStatus
                  + ' note=' + JSON.stringify(csvNote)
                  + ' console=' + JSON.stringify(csvConsole.slice(0, 3)), 15, ctx, b);
    }
    // Back to a format that renders: the download must carry the served filename and content type,
    // and the note must be built from what the answer said (bytes, digest, the emitter's own
    // "a download is not a delivery" sentence).
    await page.locator('#as-material').selectOption(servedFormats[0]);
    const mdGet = page.waitForResponse(
      (r) => /\/assistance-plans\/aplan-[0-9a-f]{32}\/export/.test(r.url())
             && r.url().includes('format=' + servedFormats[0]), { timeout: 25000 });
    await page.locator('#as-download').click();
    const mdAnswer = await mdGet.then((r) => r.json()).catch(() => null);
    const mdNote = await noteWhen('已下载');
    const materialDownloaded = !!mdAnswer && mdAnswer.format === servedFormats[0]
      && /已下载/.test(mdNote) && mdNote.includes(mdAnswer.format_label)
      && mdNote.includes(mdAnswer.body_sha256) && mdNote.includes('不是选用')
      && mdNote.includes(mdAnswer.not_executed);
    if (!materialDownloaded) {
      await abort('E2E_ASSISTANT_MATERIAL_DOWNLOAD: note=' + JSON.stringify(mdNote)
                  + ' answer=' + JSON.stringify(mdAnswer && mdAnswer.filename), 15, ctx, b);
    }

    // ---- DL-KB-12 找回：搜索、筛选、修订对比 --------------------------------------
    // The list route has no q parameter, so the search box filters the page that was read. The
    // assertion here is that the page says WHICH rows it read and how many matched -- a list that
    // quietly shows fewer rows would otherwise read as "you have no more plans".
    await page.locator('#as-plan-search').fill('秋季新品');
    await page.locator('#as-plan-filter-state').selectOption('chosen');
    await page.waitForFunction(() => /按当前条件显示/.test(
      document.getElementById('as-list-meta')?.textContent ?? ''),
    null, { timeout: 15000 }).catch(() => {});
    const filterLine = await page.locator('#as-list-meta').innerText();
    const filteredRows = await page.locator('#as-list .as-plan-row').count();
    const searchApplied = /这个工作区共 \d+ 条/.test(filterLine)
      && /这一页读到 \d+ 条/.test(filterLine)
      && /按当前条件显示 \d+ 条/.test(filterLine)
      && /不是全库搜索/.test(filterLine) && filteredRows >= 1;
    if (!searchApplied) {
      await abort('E2E_ASSISTANT_PLAN_SEARCH: meta=' + JSON.stringify(filterLine)
                  + ' rows=' + filteredRows, 15, ctx, b);
    }

    // Two real revisions: both bodies come back from the by-revision route. The fault this guards is
    // a comparison that renders the current revision twice -- which is why the two digests, not just
    // the two labels, have to differ in the served answers.
    await page.locator('#as-compare > summary').click();
    await page.locator('#as-compare-from').selectOption('1');
    await page.locator('#as-compare-to').selectOption('2');
    const revisionGets = ['1', '2'].map((number) => page.waitForResponse(
      (r) => r.request().method() === 'GET' && r.url().endsWith('/revisions/' + number),
      { timeout: 25000 }));
    await page.locator('#as-compare-run').click();
    const revisionAnswers = await Promise.all(revisionGets.map((p) => p.then((r) => r.json())));
    const compareStatus = await page.waitForFunction(() => {
      const node = document.getElementById('as-compare-status');
      const text = node ? (node.textContent ?? '') : '';
      return text.includes('对比的是') ? text : null;
    }, null, { timeout: 20000 }).then((handle) => handle.jsonValue()).catch(() => '');
    const compareRows = await page.locator('#as-compare-body li').allInnerTexts();
    const compareReal = revisionAnswers.length === 2
      && revisionAnswers[0].content_sha256 !== revisionAnswers[1].content_sha256
      && revisionAnswers[0].revision === 1 && revisionAnswers[1].revision === 2
      && revisionAnswers[0].is_latest === false && revisionAnswers[1].is_latest === true
      && compareStatus.includes(revisionAnswers[0].content_sha256)
      && compareStatus.includes(revisionAnswers[1].content_sha256)
      && compareRows.some((row) => /设计建议/.test(row) && /不同/.test(row))
      && compareRows.some((row) => /目标/.test(row) && /相同/.test(row));
    if (!compareReal) {
      await abort('E2E_ASSISTANT_PLAN_COMPARE: status=' + JSON.stringify(compareStatus)
                  + ' digests=' + JSON.stringify(revisionAnswers.map((a) => a && a.content_sha256))
                  + ' rows=' + JSON.stringify(compareRows.slice(0, 4)), 15, ctx, b);
    }


    // Re-open the plan while listening to the readback the panel itself issues, then require the
    // rendered <option> list to be exactly the pairs that response carried. A hand-copied
    // vocabulary in shell.ts would still render three plausible options; it would not survive
    // this comparison, and that is the point -- the words are the service's, not the page's.
    const planShape = () => page.evaluate(() => ({
      chips: ['as-saved', 'as-provided', 'as-chosen', 'as-external']
        .map((id) => document.getElementById(id)?.dataset.state ?? ''),
      revisions: document.querySelectorAll('#as-revisions li').length,
      choice: document.getElementById('as-choice')?.textContent ?? '',
    }));
    const shapeBeforeFeedback = await planShape();
    const feedbackGet = page.waitForResponse(
      (r) => /\/assistance-plans\/aplan-[0-9a-f]{32}\/feedback$/.test(r.url())
             && r.request().method() === 'GET', { timeout: 25000 });
    await page.locator('#as-list .as-plan-open').first().click();
    const feedbackServed = await feedbackGet.then((r) => r.json()).catch(() => null);
    if (!feedbackServed || !Array.isArray(feedbackServed.outcome_words)) {
      await abort('E2E_ASSISTANT_FEEDBACK_NO_READBACK: 面板没有从服务读到反馈历史', 15, ctx, b);
    }
    await page.locator('#as-fb-add-dimension').click();
    const feedbackDom = await page.evaluate(() => ({
      outcomes: Array.from(document.querySelectorAll('#as-fb-outcome option'))
        .map((o) => ({ value: o.value, label: o.textContent ?? '' })),
      verdicts: Array.from(document.querySelectorAll('#as-fb-dimensions select option'))
        .map((o) => ({ value: o.value, label: o.textContent ?? '' })),
      saveDisabled: document.getElementById('as-fb-save')?.disabled ?? true,
      addDisabled: document.getElementById('as-fb-add-dimension')?.disabled ?? true,
    }));
    const servedOutcomes = [{ value: '', label: '暂不记录' },
      ...feedbackServed.outcome_words.map((w) => ({ value: w.value, label: w.label }))];
    const servedVerdicts = feedbackServed.dimension_verdict_words
      .map((w) => ({ value: w.value, label: w.label }));
    if (JSON.stringify(feedbackDom.outcomes) !== JSON.stringify(servedOutcomes) ||
        JSON.stringify(feedbackDom.verdicts) !== JSON.stringify(servedVerdicts) ||
        feedbackDom.saveDisabled || feedbackDom.addDisabled) {
      await abort('E2E_ASSISTANT_FEEDBACK_WORDS: dom=' + JSON.stringify(feedbackDom)
                  + ' served=' + JSON.stringify({ outcomes: servedOutcomes,
                                                  verdicts: servedVerdicts }), 15, ctx, b);
    }

    const partialWord = servedOutcomes[2];
    const dimensionRow = page.locator('#as-fb-dimensions .as-fb-dimension').nth(0);
    await page.locator('#as-fb-outcome').selectOption(partialWord.value);
    await page.locator('#as-fb-target').fill('elevenlabs--web-app--music');
    await page.locator('#as-fb-actor').fill('E2E Feedback Human');
    await dimensionRow.locator('input').nth(0).fill('画幅');
    await dimensionRow.locator('select').selectOption(servedVerdicts[0].value);
    const feedbackPost = page.waitForResponse(
      (r) => /\/assistance-plans\/aplan-[0-9a-f]{32}\/feedback$/.test(r.url())
             && r.request().method() === 'POST', { timeout: 25000 });
    await page.locator('#as-fb-save').click();
    const feedbackWritten = await feedbackPost.then((r) => r.json()).catch(() => null);
    if (!feedbackWritten || (feedbackWritten.feedback || {}).outcome !== partialWord.value) {
      await abort('E2E_ASSISTANT_FEEDBACK_NOT_WRITTEN: '
                  + JSON.stringify(feedbackWritten) + ' status='
                  + await page.locator('#as-fb-error').innerText(), 15, ctx, b);
    }
    // The confirmation and the row must both come from the readback that follows the write; the
    // empty 外部编号 stays the literal UNUSED because nothing here mints an identifier.
    const feedbackRowText = await page.waitForFunction((no) => {
      const node = document.getElementById(`as-fb-row-${no}`);
      return node ? (node.textContent ?? '') : null;
    }, feedbackWritten.feedback.feedback_no, { timeout: 25000 })
      .then((handle) => handle.jsonValue()).catch(() => null);
    const feedbackStatus = await page.locator('#as-fb-status').innerText();
    const shapeAfterFeedback = await planShape();
    const feedbackPanelText = await page.locator('#as-feedback').innerText();
    const feedbackRecorded = !!feedbackRowText && feedbackRowText.includes(partialWord.label)
      && feedbackRowText.includes('E2E Feedback Human')
      && feedbackRowText.includes('elevenlabs--web-app--music')
      && feedbackRowText.includes('UNUSED')
      && feedbackStatus.includes(`已记录：${partialWord.label}`)
      && feedbackStatus.includes('外部未验证');
    const feedbackKeptPlan = JSON.stringify(shapeBeforeFeedback)
      === JSON.stringify(shapeAfterFeedback);
    const feedbackOverclaim = /已发送|发送成功|delivered|模型已执行/i.test(feedbackPanelText);
    if (!feedbackRecorded || !feedbackKeptPlan || feedbackOverclaim) {
      await abort('E2E_ASSISTANT_FEEDBACK: recorded=' + feedbackRecorded
                  + ' keptPlan=' + feedbackKeptPlan + ' overclaim=' + feedbackOverclaim
                  + ' row=' + JSON.stringify(feedbackRowText) + ' status='
                  + JSON.stringify(feedbackStatus) + ' shape='
                  + JSON.stringify([shapeBeforeFeedback, shapeAfterFeedback]), 15, ctx, b);
    }

    // Throw the page away. The four states must be rebuilt from the service.
    //
    // A reload at #/assistant has no in-memory token, and the routed view
    // deliberately hides the login panel — it shows「请先在工作台连接」instead.
    // Going back to the workbench first is that screen's own instruction, not a
    // test shortcut: the token field is only reachable on the workbench view.
    // One helper, because this dance is run twice below and a copy would drift.
    const reloadAssistant = async () => {
      await page.reload({ waitUntil: 'load' });
      await page.evaluate(() => { window.location.hash = ''; });
      await page.locator('#token').waitFor({ state: 'visible', timeout: 15000 });
      await page.locator('#token').fill(token);
      await page.locator('#connect-form button').first().click();
      await page.locator('#workspace').waitFor({ state: 'visible', timeout: 15000 });
      await page.evaluate(() => { window.location.hash = '#/assistant'; });
      await page.locator('#as-objective').waitFor({ state: 'visible', timeout: 20000 });
      await page.locator('#as-list .as-plan-open').first()
        .waitFor({ state: 'visible', timeout: 20000 });
    };
    await reloadAssistant();
    const listRow = await page.locator('#as-list .as-plan-row').first().innerText();
    if (!/方案已提供/.test(listRow) || !/用户选用 r2/.test(listRow)) {
      await abort('E2E_ASSISTANT_RELOAD_LIST: ' + listRow.replace(/[\r\n]+/g, ' · '), 15, ctx, b);
    }
    // The card asks for the last filter to survive a restart. It is client-local state, so this is
    // the only place that can tell "restored" from "the page happens to show everything": the box
    // still holds the word that was typed, the state filter still holds the choice, and the meta
    // line still says it is showing a filtered subset of what it read.
    const filtersRestored = await page.waitForFunction(() => {
      const search = document.getElementById('as-plan-search');
      const state = document.getElementById('as-plan-filter-state');
      const meta = document.getElementById('as-list-meta');
      if (!search || !state || !meta) return null;
      return search.value === '秋季新品' && state.value === 'chosen'
             && /按当前条件显示/.test(meta.textContent ?? '');
    }, null, { timeout: 20000 }).then(() => true).catch(() => false);
    if (!filtersRestored) {
      await abort('E2E_ASSISTANT_PLAN_FILTER_RELOAD: ' + JSON.stringify(await page.evaluate(() => ({
        search: document.getElementById('as-plan-search')?.value ?? '',
        state: document.getElementById('as-plan-filter-state')?.value ?? '',
        meta: document.getElementById('as-list-meta')?.textContent ?? '',
      }))), 15, ctx, b);
    }
    await page.locator('#as-list .as-plan-open').first().click();
    const reloaded = await page.waitForFunction(() => {
      const node = document.getElementById('as-chosen');
      return !!node && node.dataset.state === 'true';
    }, null, { timeout: 20000 }).then(readStates).catch(() => null);
    if (!reloaded || reloaded.saved?.state !== 'true' || reloaded.provided?.state !== 'true' ||
        reloaded.chosen?.state !== 'true' || reloaded.external?.state !== 'false') {
      await abort('E2E_ASSISTANT_RELOAD_STATES: ' + JSON.stringify(reloaded), 15, ctx, b);
    }
    const reloadedChoice = await page.locator('#as-choice').innerText();
    if (!/E2E Assistant Reviewer/.test(reloadedChoice) ||
        !/外部未验证/.test(await page.locator('#as-plan').innerText())) {
      await abort('E2E_ASSISTANT_RELOAD_CHOICE: ' + reloadedChoice, 15, ctx, b);
    }
    // The voluntary report is the one thing this run wrote that has no plan state to ride on, so
    // it is asserted where it matters: after the page is thrown away, the history must come back
    // from the service with the same words and the same tally, and the plan must still be two
    // revisions -- a feedback write that adopted or revised the plan would show up here as r3.
    const reloadedRow = await page.waitForFunction((no) => {
      const node = document.getElementById(`as-fb-row-${no}`);
      return node ? (node.textContent ?? '') : null;
    }, feedbackWritten.feedback.feedback_no, { timeout: 25000 })
      .then((handle) => handle.jsonValue()).catch(() => null);
    const reloadedFeedbackStatus = await page.locator('#as-fb-status').innerText();
    await page.locator('#as-revisions > summary').click();
    const reloadedRevisionCount = await page.evaluate(
      () => document.querySelectorAll('#as-revisions li').length);
    feedbackSurvivedReload = !!reloadedRow && reloadedRow.includes(partialWord.label)
      && reloadedRow.includes('E2E Feedback Human')
      && reloadedFeedbackStatus.includes('已读回')
      && reloadedFeedbackStatus.includes(`${partialWord.label} 1`)
      && reloadedFeedbackStatus.includes('外部未验证')
      && reloadedRevisionCount === 2;
    if (!feedbackSurvivedReload) {
      await abort('E2E_ASSISTANT_FEEDBACK_RELOAD: row=' + JSON.stringify(reloadedRow)
                  + ' status=' + JSON.stringify(reloadedFeedbackStatus)
                  + ' revisions=' + reloadedRevisionCount, 15, ctx, b);
    }

    // ---- DL-KB-12 复制一份 -------------------------------------------------------
    // A copy is a create: the new id has to come from the service, exactly one write has to leave
    // the page, and the plan that was copied must not move at all -- same revision count, same
    // voluntary feedback history. Asserting the copy alone would not catch a copy that also
    // adopted or revised its source.
    await page.locator('#as-list .as-plan-open').first().click();
    await page.locator('#as-duplicate').waitFor({ state: 'visible', timeout: 20000 });
    // The detail is assembled from several independent reads, and the two counts compared below
    // come from different ones: waiting only on the adoption badge let CI read
    // `feedback: 0` while the history request was still in flight, which looked exactly like a
    // copy that had rewritten its source. Wait on every panel whose numbers are compared.
    const detailAnswered = () => page.waitForFunction(() => {
      const chosen = document.getElementById('as-chosen');
      const fb = document.getElementById('as-fb-status');
      return !!chosen && chosen.dataset.state === 'true'
        && !!fb && (fb.textContent ?? '').trim() !== ''
        && document.querySelectorAll('#as-revisions li').length >= 1;
    }, null, { timeout: 25000 });
    if (!await detailAnswered().then(() => true).catch(() => false)) {
      await abort('E2E_ASSISTANT_SOURCE_DETAIL_UNANSWERED: the source detail did not finish its '
                  + 'own reads before the copy was attempted, so its shape cannot be recorded',
                  15, ctx, b);
    }
    const sourceShape = await page.evaluate(() => ({
      revisions: document.querySelectorAll('#as-revisions li').length,
      feedback: document.querySelectorAll('#as-fb-history li').length,
      digest: document.querySelector('#as-revisions li')?.textContent ?? '',
    }));
    const writesBeforeDuplicate = assistanceWrites;
    const planCreatePost = page.waitForResponse((r) => r.request().method() === 'POST'
      && /\/assistance-plans$/.test(r.url()), { timeout: 25000 });
    await page.locator('#as-duplicate').click();
    // 「复制一份」is an async read: the source's own words have to be IN the form before the
    // submit, or the submit saves whatever was there a moment ago and the advisory lands after
    // the confirmation. CI run 40526168978 (head 5388b62f) is exactly that race lost -- the plan
    // was created (revision 1, fresh id, detail rendered) while the cell still read the advisory,
    // so the wait below could never see the sentence it asserts. Locally the seed wins the race,
    // which is why four local runs said OK. Wait for the seeded state, not for the click.
    const seeded = await page.waitForFunction(() => {
      const field = document.getElementById('as-objective');
      const status = document.getElementById('as-form-status');
      return !!field && (field.value || '').trim() !== ''
        && /以上内容取自 /.test(((status && status.textContent) || '').trim());
    }, null, { timeout: 25000 }).then(() => true).catch(() => false);
    if (!seeded) {
      await abort('E2E_ASSISTANT_DUPLICATE_NOT_SEEDED: the copy read never put the source '
                  + 'content into the form, so any submit from here is not a copy', 15, ctx, b);
    }
    await page.locator('#as-author').fill('E2E Copier');
    await page.locator('#as-submit').click();
    const copied = await planCreatePost.then((r) => r.json()).catch(() => null);
    const copyId = (copied && copied.plan) ? copied.plan.plan_id : '';
    // The confirmation is written by `afterWrite`, which runs after the page's own POST promise
    // settles -- so reading the status cell the instant the response arrives races the render. CI run
    // 40352855984 (head cf30ee05) did exactly that and convicted a copy that had been written: the
    // cell still carried the pre-save advisory (「保存会新建一条方案」) while the service had already
    // returned revision 1 with a fresh id. Wait for the state the assertion needs, using the SAME
    // words as the predicate, so nothing about what counts as success gets loosened.
    const copySettled = /^aplan-[0-9a-f]{32}$/.test(copyId)
      && await page.waitForFunction((id) => {
        const el = document.getElementById('as-form-status');
        const text = ((el && el.textContent) || '').trim();
        return /已复制为新的方案 /.test(text) && text.includes(id);
      }, copyId, { timeout: 25000 }).then(() => true).catch(() => false);
    const copyStatus = await page.locator('#as-form-status').innerText();
    const copyWritten = !!copied && /^aplan-[0-9a-f]{32}$/.test(copyId)
      && copied.revision === 1 && copySettled
      && /已复制为新的方案 /.test(copyStatus)
      && copyStatus.includes(copyId) && assistanceWrites === writesBeforeDuplicate + 1;
    if (!copyWritten) {
      await abort('E2E_ASSISTANT_PLAN_DUPLICATE: status=' + JSON.stringify(copyStatus)
                  + ' answer=' + JSON.stringify(copied && { revision: copied.revision,
                                                             id: copied.plan?.plan_id })
                  + ' writes=' + assistanceWrites + '/' + (writesBeforeDuplicate + 1)
                  + ' confirmationRendered=' + copySettled,
                  15, ctx, b);
    }
    // Reopen the SOURCE plan -- the copy carries the same objective, so the badges are what tells
    // the two rows apart -- and read it back from the service.
    await page.locator('#as-list .as-plan-row', { hasText: '用户选用 r2' }).first()
      .locator('.as-plan-open').click();
    const sourceAfterCopy = await detailAnswered().then(() => page.evaluate(() => ({
      revisions: document.querySelectorAll('#as-revisions li').length,
      feedback: document.querySelectorAll('#as-fb-history li').length,
    }))).catch(() => null);
    const copyLeftSourceAlone = !!sourceAfterCopy
      && sourceAfterCopy.revisions === sourceShape.revisions
      && sourceAfterCopy.feedback === sourceShape.feedback;
    if (!copyLeftSourceAlone) {
      await abort('E2E_ASSISTANT_DUPLICATE_MOVED_SOURCE: before='
                  + JSON.stringify(sourceShape) + ' after='
                  + JSON.stringify(sourceAfterCopy), 15, ctx, b);
    }
    // ---- 未完成的编辑（DL-KB-12）----------------------------------------------
    // The card asks for「重启后仍能看到上一次筛选与未完成的编辑」. Filters were checked above; this
    // is the draft half, and both directions are asserted: a draft that is written but never offered
    // back is as useless as one never written, and a draft that outlives its own successful save
    // would paste yesterday's text into the next plan. Nothing here may reach the service.
    const draftKeys = () => page.evaluate(() => Object.keys(localStorage)
      .filter((key) => key.startsWith('design-lab.plan-draft')).sort());
    const keysAfterSaves = await draftKeys();
    if (keysAfterSaves.length > 0) {
      await abort('E2E_PLAN_DRAFT_SURVIVED_ITS_OWN_SAVE: ' + JSON.stringify(keysAfterSaves),
                  15, ctx, b);
    }
    const draftObjective = '草稿回归：这条没有保存，只该活在本机的存储里';
    const draftCreative = '草稿里的创意——提交前的一个字都不该进服务。';
    const draftPurpose = '草稿镜头：一次落定';
    const rowsBeforeDraft = await page.locator('#as-list .as-plan-row').count();
    await page.locator('#as-objective').fill(draftObjective);
    await page.locator('#as-creative').fill(draftCreative);
    await page.locator('#as-add-shot').click();
    await page.locator('#as-shot-rows .as-shot-row').last().locator('input').nth(2)
      .fill(draftPurpose);
    await page.waitForTimeout(900);  // the write is debounced; a snapshot taken too early is not a failure
    const keysWritten = await draftKeys();
    await reloadAssistant();
    const draftBack = await page.waitForFunction(([o, c, p]) => {
      const objective = document.getElementById('as-objective');
      const creative = document.getElementById('as-creative');
      const status = document.getElementById('as-form-status');
      const purposes = Array.from(document.querySelectorAll('#as-shot-rows input'))
        .map((node) => node.value);
      return objective && creative && status
        && objective.value === o && creative.value === c
        && purposes.includes(p)
        && /未完成的编辑/.test(status.textContent ?? '')
        && /参考与附件不在草稿里/.test(status.textContent ?? '');
    }, [draftObjective, draftCreative, draftPurpose], { timeout: 20000 })
      .then(() => true).catch(() => false);
    const rowsAfterDraft = await page.locator('#as-list .as-plan-row').count();
    if (keysWritten.length !== 1) {
      await abort('E2E_PLAN_DRAFT_WRITE: expected exactly one draft key, got '
                  + JSON.stringify(keysWritten), 15, ctx, b);
    }
    if (!draftBack) {
      await abort('E2E_PLAN_DRAFT_NOT_RESTORED: ' + JSON.stringify(await page.evaluate(() => ({
        objective: document.getElementById('as-objective')?.value ?? '',
        creative: document.getElementById('as-creative')?.value ?? '',
        shots: Array.from(document.querySelectorAll('#as-shot-rows input'))
          .map((node) => node.value).slice(0, 8),
        status: document.getElementById('as-form-status')?.textContent ?? '',
      }))), 15, ctx, b);
    }
    if (rowsAfterDraft !== rowsBeforeDraft) {
      await abort(`E2E_PLAN_DRAFT_WROTE_TO_SERVICE: list went ${rowsBeforeDraft} -> `
                  + `${rowsAfterDraft} from an unsaved draft`, 15, ctx, b);
    }
    // Then the edit is really saved: the draft must go with it, otherwise the next plan opens with
    // this one's text pasted back in. The type is picked here on purpose -- a draft never stores it,
    // so this is the served word list doing the choosing, the same as the designer would do.
    await page.locator('#as-output-type input[value="MOTION"]').check();
    await page.locator('#as-author').fill('E2E Assistant Draft Author');
    await page.locator('#as-submit').click();
    const draftSaved = await page.waitForFunction(() => {
      const status = document.getElementById('as-form-status');
      return !!status && /已保存 r1/.test(status.textContent ?? '');
    }, null, { timeout: 20000 }).then(() => true).catch(() => false);
    const keysAfterDraftSave = await draftKeys();
    if (!draftSaved || keysAfterDraftSave.length > 0) {
      await abort('E2E_PLAN_DRAFT_AFTER_SUBMIT: saved=' + draftSaved
                  + ' keys=' + JSON.stringify(keysAfterDraftSave), 15, ctx, b);
    }
    if (errors.length) {
      await abort('E2E_ASSISTANT_BROWSER_ERRORS: ' + errors.slice(0, 6).join(' ;; '),
                  15, ctx, b);
    }

    assistantLoop = {
      outputType: outputTypeLabel,
      draftKeysAfterSaves: keysAfterSaves.length,
      draftWrittenKeys: keysWritten.length,
      draftSurvivedReload: draftBack,
      draftListUntouched: rowsBeforeDraft === rowsAfterDraft,
      draftClearedAfterSubmit: keysAfterDraftSave.length === 0,
      saved: afterSave.saved.state === 'true',
      providedAfterSave: afterSave.provided.state === 'true',
      chosenAfterSave: afterSave.chosen.state === 'true',
      externalVerified: afterSave.external.state === 'true',
      copyWorked: /已复制/.test(copyNote),
      copyCarriedHonesty: clipboardText.includes('外部结果未被系统核验') &&
                          clipboardText.includes('下载不等于交付'),
      copyFormat,
      materialFormatsOffered: materialDom.length,
      materialCsvRefused: csvRefused,
      materialDownloaded,
      copyWroteNothing,
      copyChoseNothing,
      emptyObjectiveRefused: emptyRefused,
      suppliedCreative: providedTrue,
      providerPrimary: afterProvided.primary[0] ?? '',
      chosen: chosenTrue,
      chosenActorShown: /E2E Assistant Reviewer/.test(choiceLine),
      revisionRows: revisionRows.length,
      reloadReadback: reloaded.chosen.state === 'true',
      noChatSurface: initial.canvases === 0 && initial.logs === 0,
      feedbackOutcomeOptionsRendered: feedbackDom.outcomes.length,
      feedbackRecorded,
      feedbackKeptPlan,
      feedbackOverclaim,
      feedbackWrites,
      feedbackSurvivedReload,
      planSearchFiltered: searchApplied,
      filterSurvivedReload: filtersRestored,
      compareRealRevisions: compareReal,
      compareFieldRows: compareRows.length,
      duplicateId: copyId,
      duplicateLeftSourceAlone: copyLeftSourceAlone,
      sourceRevisionsAfterCopy: sourceAfterCopy ? sourceAfterCopy.revisions : 0,
      sourceFeedbackAfterCopy: sourceAfterCopy ? sourceAfterCopy.feedback : 0,
    };
    console.log('E2E_ASSISTANT_LOOP: ' + JSON.stringify(assistantLoop));
  });

  // ------------------------------------------------------------------------
  // DL-KB-14 屏幕六：状态与错误面。六种状态各有一条真断言，每种都读它在屏幕上看到的东西。
  // 这里刻意不用 route 拦截伪造失败：②那条保存失败是服务自己按名字拒绝的（把镜头行写给一份
  // 平面方案），所以同一条断言同时证明「页面说的拒绝理由来自服务」和「没写进去」。
  // ------------------------------------------------------------------------
  await step('six state surfaces', async () => {
    const states = {};
    const overclaim = /已发送|发送成功|delivered|模型已执行/;
    // `<summary>` clicks toggle, and two earlier steps in this lane already opened these panels --
    // a second click would have closed them and the hidden control would fail for the wrong reason.
    // Opening by the property is idempotent and says what the step actually needs.
    const openDetails = (selector) => page.locator(selector)
      .evaluate((node) => { node.open = true; });

    // ③ 附件未解析：方案详情里那条参考必须说清它只是登记了链接，没有反推证据。
    // 这里开的是有两次修订的那条源方案：复制出来的那条只有一个修订，⑥就没有两个可比的对象。
    await page.evaluate(() => { window.location.hash = '#/assistant'; });
    await page.locator('#as-list .as-plan-row', { hasText: '用户选用 r2' }).first()
      .locator('.as-plan-open').click();
    await page.locator('#as-basis > summary').waitFor({ state: 'visible', timeout: 20000 });
    const basisHead = await page.locator('#as-basis > summary').innerText();
    await openDetails('#as-basis');
    const basisBody = await page.locator('#as-basis').innerText();
    const basisRows = await page.locator('#as-basis li').allInnerTexts();
    states.attachmentUnparsed = /已分析 \d+ · 仅登记链接 \d+/.test(basisHead)
      && basisRows.length >= 1 && /仅登记链接|未分析|LINKED_ONLY/.test(basisBody)
      && !overclaim.test(basisBody);

    // ⑥ 旧版本查看：读 r1 是一次都不写的读，四个状态与列表都不能动。
    const writesBeforeView = assistanceWrites;
    await openDetails('#as-compare');
    await page.locator('#as-compare-from').selectOption('1');
    await page.locator('#as-compare-to').selectOption('2');
    const chipsBeforeView = await page.evaluate(() => ['as-saved', 'as-provided', 'as-chosen',
      'as-external'].map((id) => document.getElementById(id)?.dataset.state ?? ''));
    await page.locator('#as-compare-run').click();
    await page.waitForFunction(() => /对比的是/.test(
      document.getElementById('as-compare-status')?.textContent ?? ''),
    null, { timeout: 20000 }).catch(() => {});
    const chipsAfterView = await page.evaluate(() => ['as-saved', 'as-provided', 'as-chosen',
      'as-external'].map((id) => document.getElementById(id)?.dataset.state ?? ''));
    states.oldVersionReadOnly = assistanceWrites === writesBeforeView
      && JSON.stringify(chipsBeforeView) === JSON.stringify(chipsAfterView);

    // ② 保存失败：把镜头行写给一份 IMAGE 方案，服务按名字 409 拒绝，页面把那句理由原样说出，
    // 需求留在框里，列表不能多出一条。
    const plansBeforeRefusal = await page.locator('#as-list .as-plan-row').count();
    await page.locator('#as-objective').fill('把同一份镜头行写给一张海报方案，看服务怎么拒绝');
    await page.locator('#as-author').fill('E2E State Tester');
    await page.locator('#as-output-type input[value="IMAGE"]').check();
    await openDetails('#as-advanced');
    await page.locator('#as-add-shot').click();
    // The row's inputs are 序号(只读) / 时长 / 要完成什么 / 镜头运动 / 声音 / 参考角色.
    await page.locator('#as-shot-rows .as-shot-row input').nth(2)
      .fill('这一行不该出现在海报方案里');
    const refusalPost = page.waitForResponse((r) => r.request().method() === 'POST'
      && /\/assistance-plans$/.test(r.url()), { timeout: 25000 });
    const errorsBeforeRefusal = errors.length;
    await page.locator('#as-submit').click();
    const refusalStatus = await refusalPost.then((r) => r.status()).catch(() => 0);
    // Chromium logs a console error for the deliberate 409, and the `errors` array is shared by
    // every step in this file. Account for this one message here, or a later step would report a
    // failure it did not cause -- the same reason the 分镜 CSV refusal above splices its own entry.
    let refusalConsole = [];
    for (let tick = 0; tick < 60; tick += 1) {
      refusalConsole = errors.splice(errorsBeforeRefusal);
      if (refusalConsole.length) break;
      await new Promise((resolve) => { setTimeout(resolve, 50); });
    }
    const refusalError = await page.waitForFunction(() => {
      const node = document.getElementById('as-form-error');
      const text = node ? (node.textContent ?? '') : '';
      return text.includes('ASSISTANCE_PLAN_SHOTS_NOT_APPLICABLE') ? text : null;
    }, null, { timeout: 20000 }).then((handle) => handle.jsonValue()).catch(() => '');
    const plansAfterRefusal = await page.locator('#as-list .as-plan-row').count();
    states.saveFailureNamed = refusalStatus === 409
      && refusalError.includes('ASSISTANCE_PLAN_SHOTS_NOT_APPLICABLE')
      && /要么|改成/.test(refusalError) && refusalError.includes('你的输入还在')
      && refusalConsole.length === 1 && /status of 409 \(Conflict\)/.test(refusalConsole[0])
      && !/。。/.test(refusalError)
      && plansAfterRefusal === plansBeforeRefusal
      && (await page.locator('#as-objective').inputValue()).includes('看服务怎么拒绝');

    // ① 知识空态：搜一个库里不存在的词。页面不能把任何东西画成命中，也要把话说完。
    await page.evaluate(() => { window.location.hash = '#/knowledge'; });
    await page.locator('#kb-query').waitFor({ state: 'visible', timeout: 20000 });
    const nonsense = 'zzqqx不存在的检索词';
    const searchGet = page.waitForResponse((r) => /\/knowledge-entries\/search/.test(r.url()),
      { timeout: 25000 });
    await page.locator('#kb-query').fill(nonsense);
    await page.locator('#kb-search').click();
    const servedSearch = await searchGet.then((r) => r.json()).catch(() => null);
    const kbResultText = await page.locator('#kb-results').innerText();
    states.knowledgeEmpty = !!servedSearch && Array.isArray(servedSearch.entries)
      && servedSearch.entries.length === 0 && servedSearch.total === 0
      && !/kentry-/.test(kbResultText) && kbResultText.length > 0
      && !overclaim.test(kbResultText);

    // ④ 模型不可用：模型屏必须把「合格 0」说出来，而且不把可选说成可用。
    await page.evaluate(() => { window.location.hash = '#/models'; });
    await page.locator('#route-view').waitFor({ state: 'visible', timeout: 20000 });
    await page.waitForFunction(() => /合格本地模型/.test(
      document.getElementById('route-view')?.textContent ?? ''),
    null, { timeout: 20000 }).catch(() => {});
    const modelText = await page.locator('#route-view').innerText();
    states.modelUnavailable = /合格本地模型\s*0/.test(modelText) && !overclaim.test(modelText);

    // ⑤ 目标不兼容：目标档案屏的「本项目未测试」栏必须真有内容，两栏不能长成同一句话。
    await page.evaluate(() => { window.location.hash = '#/target-profiles'; });
    await page.locator('#tp-untested-list').waitFor({ state: 'visible', timeout: 25000 });
    const untestedRows = await page.locator('#tp-untested-list li').count();
    const untestedText = await page.locator('#tp-untested-list').innerText();
    const officialText = await page.locator('#tp-official-list').innerText();
    // The column's own sentence is the proof: an official page mentions the item, this project has
    // never run it. Matching the phrase the panel prints -- not a guessed synonym -- is what keeps
    // this guard from going red on wording the service chose and green on a claim it never made.
    states.targetIncompatibleShown = untestedRows >= 1
      && /本项目没有跑过|未测试|未触达|条件可用/.test(untestedText)
      && untestedText !== officialText && !overclaim.test(untestedText);

    const missing = Object.keys(states).filter((key) => states[key] !== true);
    stateLoop = { states, allSixAsserted: missing.length === 0, missing };
    console.log('E2E_STATE_LOOP: ' + JSON.stringify(stateLoop));
    if (missing.length) {
      await abort('E2E_STATE_SURFACES_NOT_ASSERTED: ' + JSON.stringify(missing)
                  + ' detail=' + JSON.stringify({
                    refusal: refusalError.slice(0, 200), kb: kbResultText.slice(0, 160),
                    model: modelText.slice(0, 160), untested: untestedText.slice(0, 160),
                  }), 15, ctx, b);
    }
  });

  await step('knowledge detail and judgement walk', async () => {
    // DL-KB-05 D5 (2026-10-24). The entry detail -- and the judgement panel inside it -- had never
    // been painted in a real browser: the contrast and geometry gates measure the list screen, so
    // nothing said the detail is legible or that its buttons do what the service answers. This
    // walk creates an entry through the UI, lets the page open it, then drives both forms and
    // compares what is on screen against the readback the route itself returned.
    const title = 'E2E 判断走查条目';
    let judgePosts = 0;
    const watch = (request) => {
      if (request.method() === 'POST' && /\/judgements$/.test(request.url())) judgePosts += 1;
    };
    page.on('request', watch);
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.evaluate(() => { window.location.hash = '#/knowledge'; });
    await page.locator('#kb-query').waitFor({ state: 'visible', timeout: 20000 });
    await page.locator('#kb-new').click();
    await page.locator('#kb-new-entry-type').waitFor({ state: 'visible', timeout: 20000 });
    await page.locator('#kb-new-entry-type').selectOption('METHOD');
    await page.locator('#kb-new-title').fill(title);
    await page.locator('#kb-new-summary').fill('用一次真实点击，确认判断面板上屏并按服务读回。');
    await page.locator('#kb-new-body').fill('第一步定节拍；第二步定景别；第三步只标必要转场。');
    await page.locator('#kb-new-author').fill('E2E Judgement Recorder');
    const created = page.waitForResponse((r) => /\/api\/knowledge-entries$/.test(r.url())
      && r.request().method() === 'POST', { timeout: 25000 });
    await page.locator('#kb-form button.primary-btn').click();
    const createdBody = await created.then((r) => r.json()).catch(() => null);

    const detailReady = await page.waitForFunction((want) => {
      const text = document.getElementById('kb-detail-content')?.textContent ?? '';
      return text.includes('判断与来源状态') && text.includes('还没有人记下判断')
        && text.includes(want);
    }, title, { timeout: 25000 }).then(() => true).catch(() => false);

    // Wait on the sentence, not on a wall clock: a refusal that never renders must read as false.
    const paintedSentence = (needle) => page.waitForFunction((want) => ((
      document.getElementById('kb-detail-content')?.textContent ?? '').includes(want)),
    needle, { timeout: 15000 }).then(() => true).catch(() => false);

    // The two local refusals are the part a browser alone can prove: a page that posts an empty
    // judgement would leave the refusal to the service and paint nothing while the user waits.
    // Each phase carries its own post counter, so "it posted twice" names the phase that did it.
    await page.locator('#kb-judge-submit').click();
    const postsAfterReasonClick = judgePosts;
    const reasonRefused = await paintedSentence('判断必须写出理由');
    await page.locator('#kb-judge-reason').fill('这一步在实际项目里更常回来用。');
    await page.locator('#kb-judge-submit').click();
    const postsAfterNameClick = judgePosts;
    const nameRefused = await paintedSentence('必须填上记录人');
    await page.locator('#kb-judge-name').fill('张工');
    const judged = page.waitForResponse((r) => /\/judgements$/.test(r.url())
      && r.request().method() === 'POST', { timeout: 25000 });
    await page.locator('#kb-judge-submit').click();
    const judgedBody = await judged.then((r) => r.json()).catch(() => null);
    const postsAfterJudgeClick = judgePosts;
    const served = judgedBody && {
      recommended: judgedBody.recommended_revision,
      basis: judgedBody.recommendation_basis,
      trail: (judgedBody.judgements ?? []).length,
      recordedBy: (judgedBody.judgements ?? [])[0]?.recorded_by ?? null,
    };
    // The page re-reads the entry after the write, so reading the DOM here would measure the panel
    // from BEFORE the judgement existed. Wait for the trail row, then compare.
    const trailPainted = await page.waitForFunction(() => document
      .querySelectorAll('.kb-judgements .list > .list-item').length >= 1,
    null, { timeout: 25000 }).then(() => true).catch(() => false);
    const onScreen = await page.evaluate(() => {
      const text = document.getElementById('kb-detail-content')?.textContent ?? '';
      return {
        trailRows: document.querySelectorAll('.kb-judgements .list > .list-item').length,
        named: text.includes('张工'), reason: text.includes('这一步在实际项目里更常回来用。'),
        basis: text.includes('来自一次后来记下的判断'),
        stillSaysNobody: text.includes('还没有人记下判断'),
      };
    });

    // A5's copy leg in the real browser: the clipboard must receive the served body byte for byte.
    // The DOM harness above covers the refused-clipboard fallback; this covers the granted path, and
    // comparing against `createdBody.entry.body` (the bytes the create route answered) is what
    // keeps the page from passing on text it composed itself.
    await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: serviceUrl });
    await page.locator('#kb-copy-body').click();
    let clipboardText = '';
    try {
      clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    } catch {
      clipboardText = '';
    }
    const copyNote = await page.evaluate(() => document.getElementById('kb-copy-status')?.textContent ?? '');
    const clipboardHoldsTheServedBody = clipboardText === (createdBody?.entry?.body ?? null)
      && clipboardText.length > 0 && /已复制正文/.test(copyNote);

    await page.locator('#kb-source-value').selectOption('INVALID');
    await page.locator('#kb-source-reason').fill('原稿下架。');
    await page.locator('#kb-source-name').fill('张工');
    await page.locator('#kb-source-submit').click();
    const sourceRefused = await paintedSentence('替代条目的编号');
    const postsAfterSourceClick = judgePosts;

    // ---- the reuse link, in the same browser session -------------------------------------
    // The reference picker used to offer only this workspace's assets, so a plan could never cite
    // the library entry it actually worked from. Drive the picker: the entry this walk just created
    // must be selectable, and the plan must come back pinned to its revision and digest.
    await page.evaluate(() => { window.location.hash = '#/assistant'; });
    await page.locator('#as-objective').waitFor({ state: 'visible', timeout: 20000 });
    await page.locator('#as-output-type').waitFor({ state: 'visible', timeout: 20000 });
    const optionValues = await page.evaluate(() => Array.from(
      document.getElementById('as-reference-select')?.options ?? []).map((o) => o.value));
    const entryId = createdBody?.entry?.knowledge_entry_id ?? '';
    // The service accepts five reference kinds; the picker used to offer two of them, so three
    // of the project's own materials (its brief, its direction, its prompt results) could be
    // stored but never cited from the screen. Earlier lanes of this very walk created all of
    // them in this project, so each kind must now show up as a selectable option.
    const optionOf = (kind) => optionValues.find((value) => value.startsWith(`${kind}:`)) ?? '';
    const pickerOffersAllFiveKinds = ['ASSET', 'BRIEF', 'DIRECTION', 'PROMPT_RESULT', 'KNOWLEDGE']
      .every((kind) => optionOf(kind) !== '');
    await page.selectOption('#as-reference-select', `KNOWLEDGE:${entryId}`);
    await page.locator('#as-reference-add').click();
    for (const kind of ['BRIEF', 'DIRECTION', 'PROMPT_RESULT']) {
      const value = optionOf(kind);
      if (value) {
        await page.selectOption('#as-reference-select', value);
        await page.locator('#as-reference-add').click();
      }
    }
    const citedRow = await page.evaluate(() => ((
      document.getElementById('as-references')?.textContent ?? '')));
    // STORYBOARD, not IMAGE: this page session still carries the shot rows an earlier
    // lane step left in the form, and the store refuses shots on a print plan with
    // ASSISTANCE_PLAN_SHOTS_NOT_APPLICABLE -- a correct refusal the walk must not fight.
    await page.locator('#as-output-type input[value="STORYBOARD"]').check();
    await page.locator('#as-objective').fill('把刚读回的拆解法用进一条秋季主视觉');
    await page.locator('#as-author').fill('E2E Plan Author');
    const planSaved = page.waitForResponse((r) => /\/assistance-plans$/.test(r.url())
      && r.request().method() === 'POST', { timeout: 25000 });
    await page.locator('#as-submit').click();
    const planBody = await planSaved.then((r) => r.json()).catch(() => null);
    const citedList = planBody?.plan?.references ?? [];
    const cited = citedList.find((entry) => entry?.kind === 'KNOWLEDGE') ?? null;
    const citeDiagnosis = {
      rowText: citedRow.slice(0, 160),
      planStatus: planBody?.status ?? planBody?.error ?? null,
      formError: await page.evaluate(() => document.getElementById('as-form-error')
        ?.textContent ?? ''),
      formStatus: await page.evaluate(() => document.getElementById('as-form-status')
        ?.textContent ?? ''),
      references: citedList,
      want: { kind: 'KNOWLEDGE', id: entryId, revision: createdBody?.entry?.revision,
              sha256: createdBody?.entry?.content_sha256 },
    };
    const planCitesTheKnowledgeEntry = citedRow.includes(entryId)
      && citedRow.includes('知识条目')
      && cited?.kind === 'KNOWLEDGE' && cited?.id === entryId
      && cited?.revision === createdBody?.entry?.revision
      && cited?.sha256 === createdBody?.entry?.content_sha256;
    // Every kind the picker offered must come back pinned by the STORE: a revision number and a
    // digest that the service resolved from its own rows. The page never sends either of those,
    // so a picker that listed an id the store could not resolve would fail here rather than
    // quietly saving an unpinnable citation.
    const planCitesEveryKind = ['KNOWLEDGE', 'BRIEF', 'DIRECTION', 'PROMPT_RESULT']
      .every((kind) => {
        const entry = citedList.find((item) => item?.kind === kind);
        return !!entry && Number.isInteger(entry.revision) && entry.revision >= 1
          && typeof entry.sha256 === 'string' && entry.sha256.length >= 64;
      });
    page.off('request', watch);

    const states = {
      entryWrittenAndOpened: !!createdBody && createdBody.stored === true && detailReady,
      // The two boxes the walk deliberately left empty. The route demands the key, the store owns
      // the sentinel, so the saved bytes must say UNKNOWN -- and no bare INVALID_PROJECT_FIELDS.
      blankFieldsStoredAsUnknown: !!createdBody
        && createdBody.entry?.applicability === 'UNKNOWN'
        && createdBody.entry?.limits === 'UNKNOWN',
      emptyTrailSaidNotAskedAndAnswered: detailReady,
      reasonRefusedWithoutRequest: reasonRefused && postsAfterReasonClick === 0,
      nameRefusedWithoutRequest: nameRefused && postsAfterNameClick === 0,
      judgementRecordedOnce: !!served && postsAfterJudgeClick === 1
        && postsAfterNameClick === 0 && served.trail === 1 && served.recordedBy === '张工'
        && served.basis === 'recorded-judgement',
      screenMatchesServedReadback: trailPainted && !!served
        && onScreen.trailRows === served.trail && onScreen.named && onScreen.reason
        && onScreen.basis && !onScreen.stillSaysNobody,
      sourceNeedsAnOpenableReplacement: sourceRefused
        && postsAfterSourceClick === postsAfterJudgeClick,
      // The reuse link: the picker offers every kind the service accepts, and the plan that
      // cites them comes back pinned to revisions and digests the STORE resolved -- not the
      // numbers the page sent, because the page sends only kind and id.
      pickerOffersAllFiveKinds,
      planCitesTheKnowledgeEntry,
      planCitesEveryKind,
      clipboardHoldsTheServedBody,
    };
    const missing = Object.keys(states).filter((key) => states[key] !== true);
    knowledgeLoop = { states, allAsserted: missing.length === 0, missing, served, onScreen,
                      trailPainted, entryId: createdBody?.entry?.knowledge_entry_id ?? null,
                      posts: { afterReasonClick: postsAfterReasonClick,
                               afterNameClick: postsAfterNameClick,
                               afterJudgeClick: postsAfterJudgeClick,
                               afterSourceClick: postsAfterSourceClick } };
    console.log('E2E_KNOWLEDGE_LOOP: ' + JSON.stringify(knowledgeLoop));
    if (missing.length) {
      await abort('E2E_KNOWLEDGE_DETAIL_NOT_WALKED: ' + JSON.stringify(missing)
                  + ' detail=' + JSON.stringify({ createdStatus: createdBody?.status,
                    served, onScreen, posts: knowledgeLoop.posts, trailPainted,
                    citeDiagnosis, clipboard: clipboardText.slice(0, 120), copyNote }), 15, ctx, b);
    }
  });

  // ------------------------------------------------------------------------
  // DL-KB-10 屏幕三：目标组合选择面板（#/target-profiles）。
  //
  // 这里断言的是几何与状态，不是"元素存在"：
  //  · 两栏必须是并排的两个框、标题与数值互不相同（08:13「显示官方支持与本项目未测试的
  //    区别」），并且四档 support_state 药丸的计算背景两两不同——UNREACHED 与 CONDITIONAL
  //    必须看得出和 DOCUMENTED_CLAIM 不是一回事；
  //  · 选择顺序必须是先软件/Agent 再看下游（08:13 那句的前半），所以没选软件时那四个
  //    下游选择框只能有占位这一项；
  //  · 路线最多两条、并列、不打分（02:66「不做没有样本依据的"最强榜"和虚构百分制评分」）；
  //  · 每个状态只有一个主要动作——这条约定写在 08 line 12（屏幕二那句「每个状态仅一个主要
  //    动作」），本屏按同一约定走，不冒充是屏幕三自己说的；
  //  · 切换目标模型时，创意方向与品牌约束必须是**同一批 DOM 节点**且逐字节同值，而校验区
  //    必须变脏并重新发一次 validate；服务返回的每条 verdict 的 grants_execution 恒 false
  //    （06:20 验收 B2「切换目标模型，原创意和品牌约束保留，参数及参考角色重新校验」）；
  //  · 长中文型号名（「MiniMax H3（ComfyUI 集成）」）在 1440×900 / 1280×800 / 1920×1080
  //    三档都必须整段落在自己的框里、不被 ellipsis 截掉、不越出视口（02:150 / 06:48；
  //    三档视口本身出自 08:1）。「暂不指定」出自 08 line 9（屏幕一那句）。
  // ------------------------------------------------------------------------
  await step('target combination panel', async () => {
    const read = () => page.evaluate(() => {
      const text = (id) => (document.getElementById(id)?.textContent ?? '').trim();
      const rect = (id) => {
        const node = document.getElementById(id);
        if (!node) return null;
        const r = node.getBoundingClientRect();
        return { left: Math.round(r.left), right: Math.round(r.right),
          top: Math.round(r.top), bottom: Math.round(r.bottom),
          width: Math.round(r.width), height: Math.round(r.height) };
      };
      const article = document.querySelector('#tp-routes article');
      return {
        mode: document.getElementById('tp-combination')?.dataset.mode ?? '',
        combination: text('tp-combination'),
        limits: text('tp-limits'),
        meta: text('tp-meta'),
        selects: ['tp-software', 'tp-agent', 'tp-entry', 'tp-model', 'tp-task-mode']
          .map((id) => ({ id, options: document.getElementById(id)?.options.length ?? -1 })),
        official: rect('tp-official'), untested: rect('tp-untested'),
        officialHead: (document.querySelector('#tp-official h3')?.textContent ?? '').trim(),
        untestedHead: (document.querySelector('#tp-untested h3')?.textContent ?? '').trim(),
        officialCount: (document.querySelector('#tp-official-head p')?.textContent ?? '').trim(),
        measuredAll: document.getElementById('tp-measured-count')?.dataset.all ?? '',
        measuredProfile: document.getElementById('tp-measured-count')?.dataset.profile ?? '',
        officialRows: document.querySelectorAll('#tp-official-list li').length,
        untestedRows: document.querySelectorAll('#tp-untested-list li').length,
        supports: Array.from(document.querySelectorAll('#tp-support-histogram [data-support]'))
          .map((t) => ({ support: t.dataset.support ?? '',
            bg: getComputedStyle(t).backgroundImage,
            lang: t.firstElementChild?.lang ?? '' })),
        routes: Array.from(document.querySelectorAll('#tp-routes article'))
          .map((a) => ({ id: a.id, profile: a.dataset.profile ?? '',
            support: a.dataset.support ?? '',
            width: Math.round(a.getBoundingClientRect().width) })),
        routesEmpty: !!document.getElementById('tp-routes-empty'),
        routeNote: text('tp-route-note'),
        routeAdvantage: text('tp-route-1-advantage'),
        routeLimit: text('tp-route-1-limit'),
        routeDisclaimer: article
          ? (article.querySelector('p.view-hint')?.textContent ?? '').trim() : '',
        primaries: Array.from(document.querySelectorAll('#route-view .primary-btn'))
          .filter((b) => b.getClientRects().length > 0).map((b) => b.id),
        validateDisabled: !!document.getElementById('tp-validate')?.disabled,
        validateLabel: text('tp-validate'),
        verifyState: text('tp-verify-state'),
        verdictKey: document.getElementById('tp-verdict-list')?.dataset.answerKey ?? '',
        verdictGrants: document.getElementById('tp-verdict-list')
          ?.dataset.grantsExecution ?? '(no list)',
        verdicts: Array.from(document.querySelectorAll('#tp-verdict-list li'))
          .filter((li) => li.querySelector('[data-verdict]'))
          .map((li) => ({
            head: (li.querySelector('strong')?.textContent ?? '').trim(),
            verdict: li.querySelector('[data-verdict]')?.dataset.verdict ?? '',
            grants: li.querySelector('[data-grants]')?.dataset.grants ?? '',
          })),
        reachRows: document.querySelectorAll('#tp-reach-attempts small').length,
        conditional: text('tp-conditional-reason'),
        executionNote: text('tp-execution-note'),
        creative: document.getElementById('tp-creative')?.value ?? '',
        brand: document.getElementById('tp-brand')?.value ?? '',
        draftOut: text('tp-draft-out'),
        // 02:66 禁的是"没有样本依据的榜单与虚构百分制"。这里量的是**渲染出来的分数形状**
        // （数字加百分号、n/100、星、最强榜/排行榜），不是页面自己写的"不排名"那句说明——
        // 把后者也算成违规，这条断言就变成了惩罚诚实的措辞。
        scores: Array.from(document.querySelectorAll(
          '#route-view p, #route-view li, #route-view h3, #route-view h4, #route-view strong'))
          .map((n) => (n.textContent ?? '').trim())
          .filter((t) => /\d+(?:\.\d+)?\s*[%％]|\d+\s*\/\s*100|[★☆]|最强榜|排行榜/.test(t))
          .slice(0, 3),
        // 按 class **整词**找排名构件，不用子串：子串会把 .kb-badges-start 里的 "start"
        // 读成 "star"，27 个假阳性就是这么来的（那是一条测量错误，不是一条设计发现）。
        rankingParts: Array.from(document.querySelectorAll('#route-view [class]')).filter((n) =>
          String(n.className).toLowerCase().split(/[\s_.-]+/)
            .some((token) => ['score', 'ranking', 'rank', 'leaderboard', 'star', 'stars']
              .includes(token))).length,
        pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
      };
    });

    // 只在**已排版**的文本节点上量几何：<option> 的矩形在 Chromium 里是 0×0，把它算进来
    // 就得到一次"全都对"的空测量。长名必须至少出现在两处可见文本里（组合读回与路线标题），
    // 否则这一条等于没测。
    const longNameGeometry = () => page.evaluate(() => {
      const root = document.getElementById('route-view');
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const hits = [];
      let node = walker.nextNode();
      while (node) {
        const value = node.textContent ?? '';
        if (/MiniMax H3（ComfyUI 集成）/.test(value)) {
          const owner = node.parentElement;
          const r = owner.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) {
            const box = owner.closest('.list-item, .row-card, .panel, article')
              ?? owner.parentElement;
            const br = box.getBoundingClientRect();
            const style = getComputedStyle(owner);
            hits.push({
              tag: owner.tagName.toLowerCase(), id: owner.id,
              text: value.trim().slice(0, 42),
              inside: r.right <= br.right + 1 && r.bottom <= br.bottom + 1,
              insideViewport: r.left >= 0 && r.right <= window.innerWidth + 1,
              clips: style.overflowX !== 'visible' || style.overflowY !== 'visible',
              ellipsis: style.textOverflow === 'ellipsis',
              overflowX: owner.scrollWidth - owner.clientWidth,
              overflowY: owner.scrollHeight - owner.clientHeight,
              wraps: style.overflowWrap,
            });
          }
        }
        node = walker.nextNode();
      }
      return hits;
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.evaluate(() => { window.location.hash = '#/target-profiles'; });
    await page.locator('#tp-software').waitFor({ state: 'visible', timeout: 20000 });
    const opened = await read();

    if (opened.mode !== 'unspecified' || !opened.routesEmpty || opened.routes.length !== 0
        || opened.validateDisabled !== true || opened.verdicts.length !== 0) {
      await abort('E2E_TARGET_UNINITIALISED: ' + JSON.stringify({
        mode: opened.mode, routesEmpty: opened.routesEmpty, routes: opened.routes,
        validateDisabled: opened.validateDisabled, verdicts: opened.verdicts.length }), 17, ctx, b);
    }
    // 屏幕三那句的顺序在这一屏是可测的：软件没定，"该入口可用的模型/模式"就只能是空集。
    const alreadyOpen = opened.selects.filter((s) => s.id !== 'tp-software' && s.options > 1);
    if (opened.selects[0].options < 2 || alreadyOpen.length) {
      await abort('E2E_TARGET_PICKER_ORDER: 软件未选时下游选择框已经铺开了候选 '
                  + JSON.stringify(opened.selects), 17, ctx, b);
    }
    // 两栏对照：并排的两个框，标题不同，而且两栏说的不是同一个数。
    if (!opened.official || !opened.untested || opened.official.width <= 0
        || opened.untested.width <= 0
        || opened.official.right > opened.untested.left + 1
        || opened.officialHead === opened.untestedHead
        || !/官方支持/.test(opened.officialHead) || !/未测试/.test(opened.untestedHead)) {
      await abort('E2E_TARGET_TWO_COLUMNS: ' + JSON.stringify({
        official: opened.official, untested: opened.untested,
        heads: [opened.officialHead, opened.untestedHead] }), 17, ctx, b);
    }
    if (opened.measuredAll !== '0') {
      await abort('E2E_TARGET_MEASURED_NOT_ZERO: 服务读回的实测字段数是 '
                  + opened.measuredAll + '，本轮必须是 0', 17, ctx, b);
    }
    // UNREACHED / CONDITIONAL / DOCUMENTED_CLAIM 必须能被眼睛分开（08:13）。
    const three = ['DOCUMENTED_CLAIM', 'CONDITIONAL', 'UNREACHED']
      .map((state) => opened.supports.find((s) => s.support === state));
    const backgrounds = new Set(three.map((s) => (s ? s.bg : '')));
    if (three.some((s) => !s) || backgrounds.size !== 3) {
      await abort('E2E_TARGET_SUPPORT_STATES 分不开: ' + JSON.stringify(opened.supports), 17, ctx, b);
    }
    if (three.some((s) => s.lang !== 'en')) {
      await abort('E2E_TARGET_SUPPORT_STATE_NOT_MARKED: 状态词没有 lang="en"，读屏会用中文'
                  + '音读它 ' + JSON.stringify(opened.supports.map((s) => [s.support, s.lang])),
                  17, ctx, b);
    }
    if (opened.primaries.length !== 1 || opened.primaries[0] !== 'tp-validate') {
      await abort('E2E_TARGET_PRIMARY_ACTIONS: ' + JSON.stringify(opened.primaries), 17, ctx, b);
    }

    await page.locator('#tp-software').selectOption('MiniMax H3');
    const picked = await read();
    const entryOptions = picked.selects.find((s) => s.id === 'tp-entry')?.options ?? 0;
    const modelOptions = picked.selects.find((s) => s.id === 'tp-model')?.options ?? 0;
    const modeOptions = picked.selects.find((s) => s.id === 'tp-task-mode')?.options ?? 0;
    if (picked.mode !== 'target' || entryOptions < 2 || modelOptions < 2 || modeOptions < 2
        || picked.routes.length < 1 || picked.routes.length > 2
        || picked.routes[0].profile !== 'minimax-h3--api--video-reference'
        || picked.officialRows < 1 || picked.measuredProfile !== '0'
        || !/不给分|不排名/.test(picked.routeDisclaimer)) {
      await abort('E2E_TARGET_AFTER_SOFTWARE: ' + JSON.stringify({
        mode: picked.mode, entryOptions, modelOptions, modeOptions, routes: picked.routes,
        officialRows: picked.officialRows, measuredProfile: picked.measuredProfile,
        routeDisclaimer: picked.routeDisclaimer.slice(0, 120) }), 17, ctx, b);
    }

    // 创意方向与品牌约束：B2 要求它们跨目标存在，所以这里填的是真实文本而不是默认值。
    const CREATIVE = '镜头 1：俯拍整张桌面；镜头 2：手指沿纸边划过；镜头 3：标题留白收束。';
    const BRAND = '只用两种油墨、大面积留白、不用渐变';
    await page.locator('#tp-creative').fill(CREATIVE);
    await page.locator('#tp-brand').fill(BRAND);
    await page.locator('#tp-dim-negative_input').waitFor({ state: 'attached', timeout: 15000 });
    const writesBeforeValidate = targetProfilePosts;
    await page.locator('#tp-validate').click();
    await page.waitForFunction(() => !!document.getElementById('tp-verdict-list'),
      null, { timeout: 25000 }).catch(() => {});
    const first = await read();
    if (first.verdictKey !== 'minimax-h3--api--video-reference'
        || first.verdictGrants !== 'true' || first.verdicts.length < 4
        || first.verdicts.some((v) => v.grants !== 'false')
        || !/不授予可执行状态/.test(first.executionNote)
        || !/已重新校验/.test(first.verifyState)
        || targetProfilePosts !== writesBeforeValidate + 1
        || targetProfileValidates < 1) {
      await abort('E2E_TARGET_VALIDATE_NOT_READ_BACK: ' + JSON.stringify({
        verdictKey: first.verdictKey, verdictGrants: first.verdictGrants,
        verdicts: first.verdicts, executionNote: first.executionNote.slice(0, 120),
        verifyState: first.verifyState.slice(0, 120),
        posts: targetProfilePosts + '/' + (writesBeforeValidate + 1),
        validates: targetProfileValidates }), 17, ctx, b);
    }

    // ---- B2：换目标模型，创意与品牌保留，参数与参考角色重新校验 ----------------
    // 节点身份也是断言之一：文本相同但节点被重建，就说明"保留"只是页面重画了一遍。
    await page.evaluate(() => {
      window.__tpKept = {
        creative: document.getElementById('tp-creative'),
        brand: document.getElementById('tp-brand'),
        route: document.querySelector('#tp-routes article'),
      };
    });
    await page.locator('#tp-software').selectOption('Black Forest Labs FLUX.2');
    await page.waitForFunction(() => {
      const article = document.querySelector('#tp-routes article');
      return !!article && article.dataset.profile === 'flux2--api--image-generation';
    }, null, { timeout: 20000 }).catch(() => {});
    const switched = await read();
    const kept = await page.evaluate(() => ({
      sameCreative: document.getElementById('tp-creative') === window.__tpKept.creative,
      sameBrand: document.getElementById('tp-brand') === window.__tpKept.brand,
      sameRouteNode: document.querySelector('#tp-routes article') === window.__tpKept.route,
      creativeValue: document.getElementById('tp-creative')?.value ?? '',
      brandValue: document.getElementById('tp-brand')?.value ?? '',
    }));
    if (!kept.sameCreative || !kept.sameBrand || kept.creativeValue !== CREATIVE
        || kept.brandValue !== BRAND || switched.verdicts.length !== 0
        || switched.verdictKey !== '' || !/需要重新校验/.test(switched.verifyState)
        || !/flux2--api--image-generation/.test(switched.verifyState)
        || switched.routes[0]?.profile !== 'flux2--api--image-generation') {
      await abort('E2E_TARGET_B2_NOT_PRESERVED: kept=' + JSON.stringify(kept)
                  + ' switched=' + JSON.stringify({
                    verdictKey: switched.verdictKey, verdicts: switched.verdicts.length,
                    verifyState: switched.verifyState.slice(0, 160),
                    routes: switched.routes }), 17, ctx, b);
    }
    // 换了目标，创意两栏的节点不许被重建；路线卡则必须被重建，否则"参数或参考角色变化"
    // 这件事根本不会显示出来。
    if (kept.sameRouteNode) {
      await abort('E2E_TARGET_ROUTE_NOT_REVALIDATED: 换了目标但路线卡节点没重建 '
                  + JSON.stringify(switched.routes), 17, ctx, b);
    }
    const writesBeforeFlux = targetProfilePosts;
    await page.locator('#tp-validate').click();
    await page.waitForFunction(() => {
      const list = document.getElementById('tp-verdict-list');
      return !!list && list.dataset.answerKey === 'flux2--api--image-generation';
    }, null, { timeout: 25000 }).catch(() => {});
    const flux = await read();
    const negative = flux.verdicts.find((v) => /^negative_input/.test(v.head));
    if (flux.verdictKey !== 'flux2--api--image-generation'
        || flux.verdictGrants !== 'true'
        || flux.verdicts.some((v) => v.grants !== 'false')
        || !negative || negative.verdict !== 'DOCUMENTED_NOT_SUPPORT'
        || !/不支持负向提示/.test(flux.routeLimit)
        || writesBeforeFlux + 1 !== targetProfilePosts) {
      await abort('E2E_TARGET_FLUX_VERDICT: ' + JSON.stringify({
        verdictKey: flux.verdictKey, verdictGrants: flux.verdictGrants, negative,
        verdicts: flux.verdicts.map((v) => [v.head.slice(0, 24), v.verdict, v.grants]),
        routeLimit: flux.routeLimit.slice(0, 160),
        posts: targetProfilePosts + '/' + (writesBeforeFlux + 1) }), 17, ctx, b);
    }
    // 档案正文里的否定必须原样上屏（服务在 reason 里写的就是"按原样报告，不软化"）。
    if (!/不软化|按原样报告/.test(flux.verdicts.map((v) => v.head).join(' '))) {
      // reason 不在 strong 里，这里读整段文本再判一次，避免断言退化成只看 verdict 词。
      const raw = await page.evaluate(() => (document
        .getElementById('tp-verdict-list')?.textContent ?? ''));
      if (!/不软化/.test(raw)) {
        await abort('E2E_TARGET_NEGATIVE_NOT_QUOTED: ' + raw.slice(0, 300), 17, ctx, b);
      }
    }

    // UNREACHED：Meshy 的每一次取回尝试都要上屏，不能只折叠成"不支持"。
    await page.locator('#tp-software').selectOption('Meshy');
    await page.waitForFunction(() => {
      const a = document.querySelector('#tp-routes article');
      return !!a && a.dataset.support === 'UNREACHED';
    }, null, { timeout: 20000 }).catch(() => {});
    const meshy = await read();
    if (meshy.routes[0]?.support !== 'UNREACHED' || meshy.reachRows !== 4
        || meshy.measuredProfile !== '0' || meshy.scores.length !== 0) {
      await abort('E2E_TARGET_UNREACHED: ' + JSON.stringify({
        routes: meshy.routes, reachRows: meshy.reachRows,
        measuredProfile: meshy.measuredProfile, scores: meshy.scores }), 17, ctx, b);
    }

    // CONDITIONAL：官方页自述 coming soon 的那份档案；长中文名几何同样在三档里量。
    await page.locator('#tp-software').selectOption('MiniMax H3（ComfyUI 集成）');
    await page.waitForFunction(() => {
      const a = document.querySelector('#tp-routes article');
      return !!a && a.dataset.support === 'CONDITIONAL';
    }, null, { timeout: 20000 }).catch(() => {});
    const conditional = await read();
    if (conditional.routes[0]?.support !== 'CONDITIONAL'
        || !/coming soon/i.test(conditional.conditional)) {
      await abort('E2E_TARGET_CONDITIONAL: ' + JSON.stringify({
        routes: conditional.routes, conditional: conditional.conditional.slice(0, 160) }),
        17, ctx, b);
    }
    const viewports = [[1440, 900], [1280, 800], [1920, 1080]];
    const geometryByWidth = {};
    for (const [width, height] of viewports) {
      await page.setViewportSize({ width, height });
      const hits = await longNameGeometry();
      geometryByWidth[width + 'x' + height] = hits;
      if (hits.length < 2) {
        await abort(`E2E_TARGET_LONG_NAME_NOT_MEASURED at ${width}x${height}: `
                    + '长中文型号名在已排版的文本节点里只出现 ' + hits.length
                    + ' 次（要求至少 2 次），几何检查不能对空集合成立', 17, ctx, b);
      }
      const bad = hits.filter((h) => !h.inside || !h.insideViewport
        || h.ellipsis || h.clips || h.overflowX > 1 || h.overflowY > 1 || h.wraps !== 'anywhere');
      if (bad.length) {
        await abort(`E2E_TARGET_LONG_NAME_CLIPPED at ${width}x${height}: `
                    + JSON.stringify(bad), 17, ctx, b);
      }
      const pageWide = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth);
      if (pageWide > 0) {
        await abort(`E2E_TARGET_PAGE_OVERFLOW at ${width}x${height}: +${pageWide}px`, 17, ctx, b);
      }
    }
    await page.setViewportSize({ width: 1440, height: 900 });

    // 「仅规划」与「暂不指定」：两个状态都要把"没有运行"说出来，且各自仍只有一个主要动作。
    await page.locator('#tp-plan-only').check();
    const planning = await read();
    if (planning.mode !== 'plan-only' || !/仅规划/.test(planning.limits)
        || !/executable=false/.test(planning.limits)
        || planning.primaries.length !== 1 || planning.scores.length !== 0
        || planning.rankingParts !== 0) {
      await abort('E2E_TARGET_PLAN_ONLY: ' + JSON.stringify({
        mode: planning.mode, limits: planning.limits.slice(0, 200),
        primaries: planning.primaries, scores: planning.scores,
        rankingParts: planning.rankingParts }), 17, ctx, b);
    }
    await page.locator('#tp-plan-only').uncheck();
    await page.locator('#tp-software').selectOption('');
    const unspecified = await read();
    if (unspecified.mode !== 'unspecified' || !unspecified.routesEmpty
        || unspecified.validateDisabled !== true
        || !/executable=false/.test(unspecified.limits)
        || unspecified.primaries.length !== 1) {
      await abort('E2E_TARGET_UNSPECIFIED: ' + JSON.stringify({
        mode: unspecified.mode, routesEmpty: unspecified.routesEmpty,
        validateDisabled: unspecified.validateDisabled,
        limits: unspecified.limits.slice(0, 200),
        primaries: unspecified.primaries }), 17, ctx, b);
    }

    // 草稿目标：这一屏的第 4 条路由。空 source_ref 必须读回字面 UNUSED——页面不代人铸编号。
    await page.locator('#tp-software').selectOption('ElevenLabs');
    await page.locator('#route-view details.advanced > summary').click();
    await page.locator('#tp-actor').fill('E2E Target Reviewer');
    const postsBeforeDraft = targetProfilePosts;
    await page.locator('#tp-draft-save').click();
    await page.waitForFunction(() => {
      const node = document.getElementById('tp-draft-out');
      return !!node && /已存为草稿/.test(node.textContent ?? '');
    }, null, { timeout: 25000 });
    // Wait on the screen's own "the post-write re-read landed" flag, not on the number this case
    // then asserts: waiting for total=6 would make the assertion true by construction.
    await page.waitForFunction(
      () => document.getElementById('tp-meta')?.dataset?.reread === 'done',
      null, { timeout: 25000 });
    const draft = await read();
    // total 从 5 变 6 才算"按服务返回的清单重读过"；组合仍写着"还没唯一到一个目标"才算
    // 没有替两份同键档案偷偷挑一份。
    if (!/USER_DRAFT/.test(draft.draftOut) || !/UNUSED/.test(draft.draftOut)
        || !/本项目未实测该入口/.test(draft.draftOut)
        || postsBeforeDraft + 1 !== targetProfilePosts
        || !/total=6/.test(draft.meta)
        || !/还没唯一到一个目标/.test(draft.combination)) {
      await abort('E2E_TARGET_DRAFT_WRITE: ' + JSON.stringify({
        draftOut: draft.draftOut.slice(0, 240), meta: draft.meta.slice(0, 160),
        combination: draft.combination.slice(0, 200),
        posts: targetProfilePosts + '/' + (postsBeforeDraft + 1) }), 17, ctx, b);
    }

    if (errors.length) {
      await abort('E2E_TARGET_PROFILE_BROWSER_ERRORS: ' + errors.slice(0, 6).join(' ;; '),
                  17, ctx, b);
    }

    targetProfileLoop = {
      viewports: viewports.map(([w, h]) => `${w}x${h}`),
      longNameHits: Object.fromEntries(Object.entries(geometryByWidth)
        .map(([key, hits]) => [key, hits.length])),
      twoColumnsSideBySide: opened.official.right <= opened.untested.left + 1,
      supportStatesSeparable: backgrounds.size,
      routeCounts: [picked.routes.length, switched.routes.length, flux.routes.length],
      negativeVerdict: negative ? negative.verdict : '',
      creativePreserved: kept.creativeValue === CREATIVE,
      brandPreserved: kept.brandValue === BRAND,
      creativeNodesReused: kept.sameCreative && kept.sameBrand,
      revalidatedAfterSwitch: flux.verdictKey === 'flux2--api--image-generation',
      grantsExecutionFalse: flux.verdicts.every((v) => v.grants === 'false')
        && flux.verdictGrants === 'true',
      unreachedAttemptsShown: meshy.reachRows,
      conditionalShown: /coming soon/i.test(conditional.conditional),
      planOnlyStated: /仅规划/.test(planning.limits),
      unspecifiedStated: unspecified.mode === 'unspecified' && unspecified.routesEmpty,
      draftStored: /USER_DRAFT/.test(draft.draftOut),
      sourceRefUnusedLiteral: /UNUSED/.test(draft.draftOut),
      scoreShapesFound: opened.scores.length + meshy.scores.length + flux.scores.length,
      rankingPartsFound: planning.rankingParts,
      primaryActionsPerState: [opened.primaries.length, picked.primaries.length,
        planning.primaries.length, unspecified.primaries.length],
      validatesPosted: targetProfileValidates,
    };
    console.log('E2E_TARGET_PROFILE_LOOP: ' + JSON.stringify(targetProfileLoop));
  });

  await ctx.close();
  await b.close();

  writeSummary('PASS');
  console.log('E2E_OK design_layer=' + JSON.stringify({
    project: projectId,
    brief: briefLine,
    briefChain,
    direction: directionLine,
    binding: bindingLine,
    active: activeText,
    directionChain,
  }));
} catch (e) {
  const reason = 'E2E_FAIL: ' + e.message.split('\n')[0];
  console.error(reason);
  await captureFailureShot();
  writeSummary('FAIL', reason);
  process.exit(1);
}

// P0-G: screenshot the live page when a real failure happens mid-chain, so a
// CI artifact can show WHERE the slice broke. Best-effort: in the catch path
// the browser/context may already be dead (or never created — see `let page`)
// and the shot is skipped; that is not itself a failure.
async function captureFailureShot(ctx, b) {
  if (!page) return;
  try {
    fs.mkdirSync(evidenceDir, { recursive: true });
    await page.screenshot({ path: path.join(evidenceDir, 'fail.png') });
    console.error('E2E_FAIL_SCREENSHOT: ' + path.join(evidenceDir, 'fail.png'));
  } catch {
    console.error('E2E_FAIL_SCREENSHOT: unavailable (page/browser already closed)');
  } finally {
    if (ctx) { try { await ctx.close(); } catch { /* already torn down */ } }
    if (b) { try { await b.close(); } catch { /* already torn down */ } }
  }
}
