// SPDX-License-Identifier: MIT
// W04 — 参考与资产: reference panel in the route shell.
// Driven by w03-brief-editor-verify.py (shared service runner; W03_NODE_SCRIPT/W03_OUT).
//
// Acceptance lines exercised here (pack W04):
//   图片不被默认裁剪  -> preview computed object-fit is `contain`, not `cover`
//   alpha 可见        -> a checkerboard ground is applied behind the preview
//   缺失引用可定位    -> a failing asset names its own id and shows no stale image
//   未知 rights       -> NOT_REVIEWED is surfaced as blocking production certification
//   鉴权图像路径      -> a BARE <img src=/api/...> cannot load bytes (401); only the
//                        Authorization-header path through api() works
//   大图按需生成预览  -> the list issues ZERO content requests until a row is clicked
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const base = process.env.W03_SERVICE_URL.replace(/\/$/, '');
const token = process.env.W03_TOKEN;
const OUT = process.env.W03_OUT;

const checks = [];
const check = (name, pass, detail) => checks.push({ name, pass: !!pass, detail });
const consoleErrors = [];
let phase = 'setup';
let contentRequests = 0;

const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push({ phase, text: m.text() }); });
page.on('pageerror', (e) => consoleErrors.push({ phase, text: 'pageerror: ' + String(e) }));
page.on('request', (r) => { if (/\/assets\/[^/]+\/content/.test(r.url())) contentRequests++; });

// ---- setup: connect, create project, import one tiny PNG (same bytes as the repo E2E)
await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
const name = 'W04 Refs ' + Date.now();
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: name });
const pid = await page.locator('#project').inputValue();
const png = Buffer.from(
  '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489' +
  '0000000b49444154789c6360000200000500017a5eab3f0000000049454e44ae426082', 'hex');
await page.locator('#file').setInputFiles({ name: 'ref.png', mimeType: 'image/png', buffer: png });
await page.locator('#import-button').click();
await page.locator('#reference-picker input[type=checkbox]').first().waitFor({ state: 'visible', timeout: 20000 });

// ---- list readback, with ZERO content fetches ----------------------------------
phase = 'list';
contentRequests = 0;
await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-ref-list').waitFor({ state: 'visible', timeout: 20000 });
await page.waitForFunction(() => /参考素材（\d+）/.test(document.getElementById('pd-ref-heading')?.textContent || ''),
  null, { timeout: 20000 }).catch(() => {});
const listText = await page.locator('#pd-ref-list').innerText();
check('asset list reads back the imported asset', /1 × 1/.test(listText) && /image\/png/.test(listText),
  { listText: listText.slice(0, 220) });
check('asset id and sha256 are shown (locatable provenance)',
  /img-[0-9a-f]{8}/.test(listText) && /sha256 [0-9a-f]{8}/.test(listText) && !/sha256 sha256:/.test(listText),
  { listText: listText.slice(0, 220) });
// The live payload omits `kind`/`version_no` that contracts.ts declares; the first version
// of this panel therefore printed "undefined" in the row. Nothing may ever render undefined.
check('no field renders as the literal "undefined"',
  !/undefined/.test(await page.locator('#pd-ref-list').innerText()), { listText: listText.slice(0, 220) });
check('unreviewed rights are surfaced as such', /权利未审查/.test(listText) && /权利未审查/.test(await page.locator('#pd-ref-status').innerText()),
  { listText: listText.slice(0, 120) });
check('unknown rights are stated to block production certification',
  /阻止生产认证|不能作为生产认证依据/.test(await page.locator('#pd-ref-status').innerText()), {});
check('大图按需生成预览: the list issues ZERO content requests', contentRequests === 0, { contentRequests });
const hiddenBefore = await page.locator('#pd-ref-preview').isHidden();
check('preview starts hidden (nothing pre-rendered)', hiddenBefore === true, { hiddenBefore });

// ---- on-demand preview ---------------------------------------------------------
phase = 'preview';
await page.locator('#pd-ref-list button.ghost-btn').first().click();
await page.waitForFunction(() => {
  const img = document.getElementById('pd-ref-preview');
  return img && !img.hidden && (img.getAttribute('src') || '').startsWith('data:image/');
}, null, { timeout: 20000 });
const afterClick = await page.evaluate(() => {
  const img = document.getElementById('pd-ref-preview');
  const cs = getComputedStyle(img);
  return {
    src: (img.getAttribute('src') || '').slice(0, 40),
    complete: img.complete,
    naturalWidth: img.naturalWidth,
    objectFit: cs.objectFit,
    backgroundImage: cs.backgroundImage.slice(0, 60),
    info: document.getElementById('pd-ref-info')?.textContent,
  };
});
check('preview loads on demand through the authenticated api() path',
  afterClick.src.startsWith('data:image/png;base64') && afterClick.naturalWidth === 1, afterClick);
check('exactly one content request was made for one preview', contentRequests === 1, { contentRequests });
check('图片不被默认裁剪: object-fit is contain (not cover)',
  afterClick.objectFit === 'contain', { objectFit: afterClick.objectFit });
check('alpha 可见: a checkerboard ground is applied behind the preview',
  /gradient/.test(afterClick.backgroundImage), { backgroundImage: afterClick.backgroundImage });
check('preview reports real dimensions and rights', /1 × 1/.test(afterClick.info || '') && /rights: NOT_REVIEWED/.test(afterClick.info || ''),
  { info: afterClick.info });

// ---- 鉴权图像路径: two DIFFERENT facts, asserted separately ----------------------
// The first version of this check called a bare <img> and reported success as "cannot
// load asset bytes (header-only auth)". That conclusion was WRONG about the cause: the
// browser logged `img-src data:` CSP, so the request never reached the service and auth
// was never exercised. The two facts are now separated.
phase = 'bare-img';
const bare = await page.evaluate(async (p) => {
  const small = document.querySelector('#pd-ref-list .list-item small');
  const m = small ? /(img-[0-9a-f]{64})/.exec(small.textContent || '') : null;
  const assetId = m ? m[1] : null;
  if (!assetId) return { assetId: null, reason: 'no asset id in the row' };
  const url = `/api/projects/${p}/assets/${assetId}/content`;
  const imgResult = await new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve({ loaded: true, naturalWidth: img.naturalWidth });
    img.onerror = () => resolve({ loaded: false, naturalWidth: img.naturalWidth });
    img.src = url;
    setTimeout(() => resolve({ loaded: img.naturalWidth > 0, naturalWidth: img.naturalWidth }), 4000);
  });
  // Isolate AUTH from CSP: fetch() is governed by connect-src 'self' (same-origin, allowed)
  // and exposes the status code, so an unauthenticated request can be observed directly.
  let status = null;
  try { status = (await fetch(url, { headers: {} })).status; } catch (e) { status = 'fetch-failed:' + String(e).slice(0, 40); }
  return { assetId, imgLoaded: imgResult.loaded, imgNaturalWidth: imgResult.naturalWidth, unauthenticatedStatus: status };
}, pid);
check('a bare <img src=/api/...> is blocked by CSP `img-src data:`',
  bare.assetId !== null && bare.imgLoaded === false, bare);
check('鉴权图像路径: the same URL without an Authorization header returns 401',
  bare.unauthenticatedStatus === 401, bare);

// ---- 缺失引用可定位 -------------------------------------------------------------
phase = 'missing';
await page.route('**/api/projects/*/assets/*/content', (route) => route.abort());
await page.locator('#pd-ref-list button.ghost-btn').first().click();
await page.waitForFunction(() => /读取失败/.test(document.getElementById('pd-ref-status')?.textContent || ''),
  null, { timeout: 20000 }).catch(() => {});
const missing = await page.evaluate(() => ({
  status: document.getElementById('pd-ref-status')?.textContent,
  statusClass: document.getElementById('pd-ref-status')?.className,
  previewHidden: document.getElementById('pd-ref-preview')?.hidden,
  src: document.getElementById('pd-ref-preview')?.getAttribute('src'),
}));
check('a failing asset is located by id and explained', /img-[0-9a-f]{8}/.test(missing.status || ''), { missing });
check('failure is an error and leaves NO stale image', /error/.test(missing.statusClass || '') && missing.previewHidden === true && !missing.src,
  missing);
await page.unroute('**/api/projects/*/assets/*/content');

// ---- hygiene -------------------------------------------------------------------
phase = 'hygiene';
// Two phases legitimately produce console errors: the bare-<img> CSP block, and the
// deliberately aborted content request. Everything else must be clean.
const EXPECTED_PHASES = new Set(['bare-img', 'missing']);
const unexpected = consoleErrors.filter((e) => !EXPECTED_PHASES.has(e.phase));
check('console errors are limited to the deliberately provoked CSP block and abort',
  unexpected.length === 0, { unexpected: unexpected.slice(0, 3), all: consoleErrors.length });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w04-references', project_id: pid, checks, console_errors: consoleErrors,
  measured_at: new Date().toISOString(),
}, null, 2), 'utf8');
for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W04 checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
