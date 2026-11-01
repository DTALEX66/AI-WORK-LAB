// SPDX-License-Identifier: MIT
// Diagnostic: what did the dev-mode dashboard actually render?
import { pathToFileURL } from 'node:url';
const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const base = process.env.W03_SERVICE_URL.replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.W03_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
page.on('pageerror', (e) => console.log('PAGEERROR:', String(e).slice(0, 300)));
page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE-ERR:', m.text().slice(0, 200)); });
await page.goto(base + '/workbench?dev=1#/dashboard', { waitUntil: 'load' });
await page.waitForTimeout(3000);
const dump = await page.evaluate(() => ({
  hash: window.location.hash,
  routeViewLen: document.getElementById('route-view')?.innerHTML.length,
  panelCount: document.querySelectorAll('.panel').length,
  h3s: [...document.querySelectorAll('.panel h3')].map((h) => h.textContent),
  bodyHead: document.body.innerText.slice(0, 300),
  hasStorage: typeof localStorage !== 'undefined',
}));
console.log(JSON.stringify(dump, null, 2));
await browser.close();
