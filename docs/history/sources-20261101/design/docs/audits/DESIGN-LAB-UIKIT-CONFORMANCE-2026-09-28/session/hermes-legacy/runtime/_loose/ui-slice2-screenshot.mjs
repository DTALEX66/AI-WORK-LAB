// SPDX-License-Identifier: MIT
// UI Slice 2 visual acceptance: drive the REAL AppShell (new bundle) against a
// real loopback service, capture each view. No fake data — every rendered
// value is a live /api readback; unopened IA slots show their honest copy.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const nmDir = process.env.E2E_NODE_MODULES;
const serviceUrl = process.env.E2E_SERVICE_URL;
const token = process.env.E2E_TOKEN;
const browser = process.env.E2E_BROWSER || null;
const outDir = process.env.SLICE2_SHOT_DIR;
if (!nmDir || !serviceUrl || !token || !outDir) {
  console.error('SHOT_CONFIG_MISSING');
  process.exit(3);
}
fs.mkdirSync(outDir, { recursive: true });
const req = createRequire(nmDir + '/noop.js');
const pw = req('playwright');
const launchOpts = { headless: true };
if (browser) launchOpts.executablePath = browser;

const b = await pw.chromium.launch(launchOpts);
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror: ' + String(e)));
const base = serviceUrl.replace(/\/$/, '');

try {
  await page.goto(base + '/workbench', { waitUntil: 'load' });
  await page.locator('#token').fill(token);
  await page.locator('#connect-form button').first().click();
  await page.locator('#workspace').waitFor({ state: 'visible', timeout: 15000 });
  await page.screenshot({ path: path.join(outDir, 'shell-workbench.png'), fullPage: true });
  console.log('shot: shell-workbench');

  await page.evaluate(() => { window.location.hash = '#/dashboard'; });
  await page.locator('#route-view .kpi-card').first().waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outDir, 'shell-dashboard.png'), fullPage: true });
  console.log('shot: shell-dashboard');

  await page.evaluate(() => { window.location.hash = '#/settings'; });
  await page.locator('#route-view .resource-table').first().waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outDir, 'shell-settings.png'), fullPage: true });
  console.log('shot: shell-settings');

  await page.evaluate(() => { window.location.hash = '#/preflight'; });
  await page.locator('#preflight-task-input').waitFor({ timeout: 15000 });
  await page.locator('#preflight-task-input').fill('DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-H020');
  await page.locator('#route-view button', { hasText: '读回判定' }).click();
  await page.locator('#route-view .preflight-verdict, #route-view .error').first().waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outDir, 'shell-preflight.png'), fullPage: true });
  console.log('shot: shell-preflight');

  await page.evaluate(() => { window.location.hash = '#/research'; });
  await page.locator('#route-view .view-unopened').first().waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outDir, 'shell-research-unopened.png'), fullPage: true });
  console.log('shot: shell-research-unopened');

  if (errors.length) {
    console.error('PAGE_ERRORS: ' + errors.join(' ;; '));
    process.exitCode = 2;
  }
  console.log('SHOTS_OK');
} catch (e) {
  console.error('SHOTS_FAIL: ' + String(e).split('\n')[0]);
  try {
    await page.screenshot({ path: path.join(outDir, 'shell-fail.png') });
  } catch { /* page dead */ }
  process.exit(1);
} finally {
  await ctx.close();
  await b.close();
}
