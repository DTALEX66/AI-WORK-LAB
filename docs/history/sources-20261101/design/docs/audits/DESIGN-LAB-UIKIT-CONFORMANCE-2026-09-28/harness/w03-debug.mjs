// SPDX-License-Identifier: MIT
// Focused diagnostic: after a successful create, what is actually in the panel DOM?
import { pathToFileURL } from 'node:url';
const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const base = process.env.W03_SERVICE_URL.replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('pageerror', (e) => console.log('PAGEERROR:', String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE-ERR:', m.text().slice(0, 200)); });

await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(process.env.W03_TOKEN);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
const name = 'W03 Debug ' + Date.now();
await page.locator('#project-name').fill(name);
await page.locator('#create-form button').first().click();
await page.locator('#project option', { hasText: name }).first().waitFor({ state: 'attached', timeout: 20000 });
await page.locator('#project').selectOption({ label: name });
const pid = await page.locator('#project').inputValue();

await page.evaluate((p) => { window.location.hash = `#/projects/${encodeURIComponent(p)}`; }, pid);
await page.locator('#pd-brief-status').waitFor({ state: 'visible', timeout: 20000 });
console.log('panels:', await page.locator('.panel').count());
console.log('status id count:', await page.locator('#pd-brief-status').count());
console.log('create button count:', await page.locator('#pd-brief-create').count());

await page.locator('#pd-brief-title').fill('调试简报');
await page.locator('#pd-brief-goals').fill('现代, 温暖');
await page.locator('#pd-brief-create').click();
await page.waitForTimeout(3000);

const dump = await page.evaluate(() => {
  const panel = document.getElementById('pd-brief-status')?.closest('.panel');
  return {
    status_text: document.getElementById('pd-brief-status')?.textContent,
    status_class: document.getElementById('pd-brief-status')?.className,
    status_count: document.querySelectorAll('#pd-brief-status').length,
    panel_html_len: panel ? panel.innerHTML.length : -1,
    panel_text: panel ? panel.innerText.slice(0, 400) : null,
    ghost_buttons: [...document.querySelectorAll('.panel button.ghost-btn')].map((b) => b.textContent),
    all_buttons: [...document.querySelectorAll('.panel button')].map((b) => b.textContent),
    list_items: document.querySelectorAll('.panel .list .list-item').length,
    strongs: [...document.querySelectorAll('.panel .list .list-item strong')].map((s) => s.textContent),
  };
});
console.log(JSON.stringify(dump, null, 2));
await browser.close();
