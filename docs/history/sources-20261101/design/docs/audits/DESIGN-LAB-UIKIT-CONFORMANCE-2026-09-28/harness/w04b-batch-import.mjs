// SPDX-License-Identifier: MIT
// W04 remainder — 批量导入可取消并报告部分失败.
// Driven by w03-brief-editor-verify.py (shared runner; W03_NODE_SCRIPT/W03_OUT).
//
// The two claims under test, and how each is made deterministic:
//   partial failure -> a batch of 3 where one file is a wrong media type (client gate)
//                      and one POST is aborted (server path). Both must be reported with
//                      their own reason, and NEITHER may appear in the read-back list.
//   cancel          -> the FIRST POST is delayed while in flight, so cancel lands while a
//                      file is genuinely being uploaded. The stated semantics are: the
//                      in-flight file finishes and reports its REAL outcome, the rest are
//                      reported 已取消 -- and none of them may be silently dropped.
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

const PNG = Buffer.from(
  '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489' +
  '0000000b49444154789c6360000200000500017a5eab3f0000000049454e44ae426082', 'hex');
const file = (name, buf = PNG, mimeType = 'image/png') => ({ name, mimeType, buffer: buf });

const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push({ phase, text: m.text() }); });
page.on('pageerror', (e) => consoleErrors.push({ phase, text: 'pageerror: ' + String(e) }));

const summaryText = () => page.locator('#pd-ref-import-summary').innerText();
const resultRows = async () => page.locator('#pd-ref-import-results .list-item').evaluateAll(
  (rows) => rows.map((r) => ({ text: r.innerText, tag: (r.querySelector('.tag') || {}).textContent || '' })));

// ---- setup
await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
const name = 'W04 Batch ' + Date.now();
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: name });
const pid = await page.locator('#project').inputValue();
await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-ref-files').waitFor({ state: 'visible', timeout: 20000 });

// ---- A. partial failure: one wrong type + one aborted POST ----------------------
phase = 'partial-failure';
let postCount = 0;
await page.route('**/api/projects/*/assets', async (route) => {
  if (route.request().method() !== 'POST') return route.continue();
  postCount += 1;
  if (postCount === 2) return route.abort();       // the 2nd real upload fails server-side
  return route.continue();
});
await page.locator('#pd-ref-files').setInputFiles([
  file('good1.png'), file('bad.txt', Buffer.from('not an image'), 'text/plain'), file('good2.png'),
]);
const selected = await page.locator('#pd-ref-selection').innerText();
check('selection count is disclosed before importing', /已选择 3 个文件/.test(selected), { selected });
// Wait for the read-back to have SETTLED, not merely for the loop to have finished.
// The first version waited on /导入 3 个：/ -- a condition phase A's summary already
// satisfied -- so phase B read phase A's rows. The UI now appends a "正在从服务端重新读回
// 清单…" marker while the read-back runs, which makes "loop done" and "list settled"
// distinguishable; these waits require the marker to be GONE.
const settled = (needle) => page.waitForFunction((n) => {
  const s = document.getElementById('pd-ref-import-summary');
  const t = s ? s.textContent || '' : '';
  return t.includes(n) && !t.includes('正在从服务端重新读回');
}, needle, { timeout: 40000 });

await page.locator('#pd-ref-import').click();
await settled('成功 1 · 失败 2 · 已取消 0');
await page.waitForFunction(() => /参考素材（1）/.test(document.getElementById('pd-ref-heading')?.textContent || ''),
  null, { timeout: 20000 });
const rowsA = await resultRows();
const summaryA = await summaryText();
check('partial failure is counted honestly (1 ok · 2 failed · 0 cancelled)',
  /成功 1 · 失败 2 · 已取消 0/.test(summaryA), { summaryA });
check('each failure states its own reason',
  rowsA.some((r) => /不支持的媒体类型/.test(r.text)) && rowsA.some((r) => /失败/.test(r.tag) && !/不支持的媒体类型/.test(r.text)),
  { rowsA });
check('a failed file is never reported as imported',
  rowsA.filter((r) => /已导入/.test(r.tag)).length === 1, { rowsA });
await page.unroute('**/api/projects/*/assets');
// Real read-back: only the successful file may exist server-side.
const headingA = await page.locator('#pd-ref-heading').innerText();
check('read-back list contains exactly the one successful import', /参考素材（1）/.test(headingA), { headingA });

// ---- B. cancel while a file is genuinely in flight ------------------------------
phase = 'cancel';
let postCountB = 0;
await page.route('**/api/projects/*/assets', async (route) => {
  if (route.request().method() !== 'POST') return route.continue();
  postCountB += 1;
  if (postCountB === 1) { await new Promise((r) => setTimeout(r, 1800)); }   // hold file #1 in flight
  return route.continue();
});
await page.locator('#pd-ref-files').setInputFiles([file('c1.png'), file('c2.png'), file('c3.png')]);
await page.locator('#pd-ref-import').click();
await page.waitForTimeout(300);                    // file #1 is now in flight
await page.locator('#pd-ref-cancel').click();
await settled('已取消 2');                          // phase-B-specific, cannot match phase A
await page.waitForFunction(() => /c3\.png/.test(document.getElementById('pd-ref-import-results')?.textContent || ''),
  null, { timeout: 20000 });
const rowsB = await resultRows();
const summaryB = await summaryText();
const cancelledB = rowsB.filter((r) => /已取消/.test(r.tag)).length;
const finishedB = rowsB.filter((r) => /已导入|失败/.test(r.tag)).length;
check('cancel stops the queue and reports the skipped files (not silently dropped)',
  rowsB.length === 3 && cancelledB === 2, { rowsB, summaryB });
check('the in-flight file still reports a REAL outcome', finishedB === 1, { rowsB });
check('summary matches the per-file rows', /成功 \d+ · 失败 \d+ · 已取消 2/.test(summaryB), { summaryB });
check('cancel semantics are stated (in-flight completes, rest not started)',
  /正在上传的这个文件会完成/.test(await page.locator('#pd-ref-selection').innerText())
  || rowsB.some((r) => /取消后未开始/.test(r.text)), { rowsB });
await page.unroute('**/api/projects/*/assets');

// ---- C. no fake success after cancel: the list is a real read-back --------------
phase = 'readback';
const headingB = await page.locator('#pd-ref-heading').innerText();
const countB = Number((/参考素材（(\d+)）/.exec(headingB) || [])[1] ?? -1);
const okB = rowsB.filter((r) => /已导入/.test(r.tag)).length;
check('the list count equals 1 (phase A) + the files actually imported in phase B',
  countB === 1 + okB, { headingB, okB, summaryB });

phase = 'hygiene';
// The aborted POST is deliberate; anything else is unexpected.
const unexpected = consoleErrors.filter((e) => !(e.phase === 'partial-failure' && /ERR_FAILED|Failed to load resource/.test(e.text)));
check('console errors are limited to the deliberately aborted upload',
  unexpected.length === 0, { unexpected: unexpected.slice(0, 3), all: consoleErrors.length });

writeFileSync(OUT, JSON.stringify({
  kind: 'design-lab-w04-batch-import', project_id: pid, checks, console_errors: consoleErrors,
  rows_partial_failure: rowsA, rows_cancel: rowsB,
  measured_at: new Date().toISOString(),
}, null, 2), 'utf8');
for (const c of checks) console.log(`  ${c.pass ? 'PASS' : '**FAIL**'}  ${c.name}`);
console.log(`W04b checks: ${checks.filter((c) => c.pass).length}/${checks.length}`);
await browser.close();
process.exit(checks.every((c) => c.pass) ? 0 : 1);
