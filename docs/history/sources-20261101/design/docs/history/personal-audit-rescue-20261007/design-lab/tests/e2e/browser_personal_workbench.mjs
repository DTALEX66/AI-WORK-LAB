// SPDX-License-Identifier: MIT
// Real official launcher: no token supplied by the harness, persisted project reload,
// unified desktop/mobile navigation, and user-visible screenshots.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const pw = createRequire(process.env.E2E_NODE_MODULES + '/noop.js')('playwright');
const browser = await pw.chromium.launch({ headless: true, executablePath: process.env.E2E_BROWSER });
const out = process.env.E2E_EVIDENCE_DIR;
fs.mkdirSync(out, { recursive: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
const check = (condition, message) => { if (!condition) throw new Error(message); };
try {
  await page.goto(process.env.E2E_SERVICE_URL + '/workbench');
  await page.locator('#workspace').waitFor({ state: 'visible' });
  check(await page.locator('#login').isHidden(), 'automatic connection must hide sign-in');
  await page.locator('#project-name').fill('个人使用验收项目');
  await page.locator('#create-form button').click();
  await page.waitForFunction(() => document.querySelector('#project')?.value);
  const pid = await page.locator('#project').inputValue();
  await page.reload();
  await page.locator('#workspace').waitFor({ state: 'visible' });
  check(await page.locator('#project').inputValue() === pid, 'reload lost active project');
  check(await page.locator('#b10-app').isVisible(), 'homepage lost unified shell');
  check(await page.locator('.app-nav').isHidden(), 'legacy navigation still visible');
  await page.screenshot({ path: path.join(out, 'personal-home-desktop.png') });
  for (const route of ['dashboard', 'projects', 'brand-systems', 'creative-tools', 'deliverables', 'evidence', 'settings']) {
    await page.locator(`#app-sidebar button[data-route="${route}"]`).click();
    await page.locator('#route-view').waitFor({ state: 'visible' });
    await page.waitForFunction(() => !document.querySelector('#route-view')?.hasAttribute('aria-busy'));
    check(await page.locator('#route-view').isVisible(), `${route} view hidden`);
    check(!(await page.locator('#route-view').innerText()).includes('请先在工作台连接'), `${route} lost connection`);
  }
  await page.reload();
  await page.waitForFunction(() => document.querySelector('#personal-connection')?.textContent === '本机服务已连接');
  await page.waitForFunction(() => !document.querySelector('#route-view')?.hasAttribute('aria-busy'));
  for (const width of [840, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.locator('#navToggle').click();
    await page.locator('#app-sidebar button[data-route="workbench"]').click();
    await page.locator('#workspace').waitFor({ state: 'visible' });
    const sizes = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, viewport: innerWidth }));
    check(sizes.doc <= sizes.viewport + 1, `horizontal overflow at ${width}: ${JSON.stringify(sizes)}`);
    check(!(await page.locator('#app-sidebar').evaluate((el) => el.classList.contains('open'))), 'drawer did not close');
    await page.waitForFunction(() => document.querySelector('#app-sidebar')?.getBoundingClientRect().right <= 1);
    await page.screenshot({ path: path.join(out, `personal-home-${width}.png`) });
    await page.locator('#navToggle').click();
    await page.locator('#app-sidebar button[data-route="dashboard"]').click();
  }
  check(errors.length === 0, `browser errors: ${errors.join('; ')}`);
  fs.writeFileSync(path.join(out, 'personal-browser-summary.json'), JSON.stringify({ result: 'PASS', evidence: 'E2_CONTROLLED_RUNTIME', scenarios: ['automatic-connect', 'create-project', 'reload-active-project', 'unified-home-shell', 'route-readbacks', 'cold-hash-reconnect', 'mobile-drawer', 'mobile-overflow'], browser: browser.version(), errors }, null, 2));
  console.log('PERSONAL_WORKBENCH_E2E_PASS');
} catch (error) {
  await page.screenshot({ path: path.join(out, 'personal-fail.png') });
  throw error;
} finally { await browser.close(); }
