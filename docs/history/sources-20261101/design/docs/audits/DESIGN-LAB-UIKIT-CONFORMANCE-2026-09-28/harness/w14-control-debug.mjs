// SPDX-License-Identifier: MIT
// Focused diagnostic: why did the injected layout-control element measure 0x0?
// The control is the only thing standing between "0 layout offenders" and "the detector
// is blind", so it has to be understood rather than assumed.
import { pathToFileURL } from 'node:url';
const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const base = process.env.W14_SERVICE_URL.replace(/\/$/, '');
const token = process.env.W14_TOKEN;
const browser = await chromium.launch({ executablePath: process.env.W14_BROWSER, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
const page = await ctx.newPage();
await page.goto(base + '/workbench', { waitUntil: 'load' });
await page.locator('#token').fill(token);
await page.locator('#connect-form button').first().click();
await page.locator('#workspace').waitFor({ state: 'visible', timeout: 20000 });
await page.waitForTimeout(300);

const diag = await page.evaluate(() => {
  const apps = [...document.querySelectorAll('.app')];
  const host = apps[0];
  const hostCS = host ? getComputedStyle(host) : null;
  const d = document.createElement('div');
  d.id = '__ctl';
  d.style.position = 'fixed';
  d.style.left = '100%';
  d.style.top = '0';
  d.style.width = '200px';
  d.style.height = '20px';
  d.textContent = 'ctl';
  host.appendChild(d);
  const r = d.getBoundingClientRect();
  const c = getComputedStyle(d);
  const out = {
    app_count: apps.length,
    host_display: hostCS ? hostCS.display : null,
    host_position: hostCS ? hostCS.position : null,
    host_visibility: hostCS ? hostCS.visibility : null,
    host_overflow_x: hostCS ? hostCS.overflowX : null,
    control_connected: d.isConnected,
    control_offsetParent: d.offsetParent === null ? null : d.offsetParent.className,
    control_rect: { left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width), height: Math.round(r.height) },
    control_computed: { display: c.display, position: c.position, width: c.width, height: c.height, left: c.left, visibility: c.visibility, cssText: d.style.cssText },
    doc_scroll_width: document.documentElement.scrollWidth,
    inner_width: window.innerWidth,
  };
  d.remove();
  return out;
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();
