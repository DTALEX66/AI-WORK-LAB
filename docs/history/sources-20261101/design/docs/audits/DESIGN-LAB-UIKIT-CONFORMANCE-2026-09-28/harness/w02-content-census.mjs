// SPDX-License-Identifier: MIT
// Diagnostic: does route content actually render in the `?dev=1` offline seam, or is
// the sweep only ever seeing the static B10 shell (login screen)? A leak sweep whose
// subject never rendered is worthless, so this is checked before trusting any result.
import { createServer } from 'node:http';
import { readFileSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const PW = 'D:/All projects/DESIGN-LAB/node_modules/.pnpm/playwright@1.63.0/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);
const CHROME = 'D:/All projects/OS External Configuration/toolchains/playwright/chromium-1228/chrome-win64/chrome.exe';
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'";
const WB = resolve('apps/workbench');
const R = {
  '/workbench/style.css': [join(WB, 'style.css'), 'text/css; charset=utf-8'],
  '/workbench/main.js': [join(WB, 'build', 'main.js'), 'text/javascript; charset=utf-8'],
};
const server = createServer((req, res) => {
  const p = req.url.split('?')[0];
  res.setHeader('Content-Security-Policy', CSP);
  const h = R[p];
  if (h) { res.setHeader('Content-Type', h[1]); res.end(readFileSync(h[0])); return; }
  if (p.startsWith('/workbench')) { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(readFileSync(join(WB, 'index.html'))); return; }
  res.statusCode = 404; res.end('nf');
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;
const outDir = resolve('.project-local/task-artifacts/designlab-followup-taskpack-20260928');
mkdirSync(outDir, { recursive: true });
const ctx = await chromium.launchPersistentContext(join(outDir, 'chrome-profile-census'), { executablePath: CHROME, headless: true, viewport: { width: 1600, height: 1000 } });
const page = ctx.pages()[0] || await ctx.newPage();
page.on('pageerror', (e) => console.log('  PAGEERROR: ' + String(e).slice(0, 160)));

for (const url of ['/workbench#/dashboard', '/workbench?dev=1#/dashboard', '/workbench?dev=1#/projects']) {
  await page.goto(base + url, { waitUntil: 'load' });
  await page.waitForTimeout(3000);
  const info = await page.evaluate(() => {
    const q = (s) => document.querySelector(s);
    const content = q('.content');
    const census = {};
    for (const el of document.querySelectorAll('.app *')) {
      const t = el.tagName.toLowerCase();
      census[t] = (census[t] || 0) + 1;
    }
    return {
      hasApp: !!q('.app'),
      loginHidden: q('#login') ? q('#login').hidden : 'no #login',
      workspaceHidden: q('#workspace') ? q('#workspace').hidden : 'no #workspace',
      contentLen: content ? content.innerHTML.length : -1,
      routeViewChildren: q('#route-view') ? q('#route-view').children.length : -1,
      navItems: document.querySelectorAll('.app-nav-item').length,
      census,
    };
  });
  console.log(`\n=== ${url} ===`);
  console.log(`  .app=${info.hasApp} #login.hidden=${info.loginHidden} #workspace.hidden=${info.workspaceHidden}`);
  console.log(`  .content innerHTML length=${info.contentLen}  #route-view children=${info.routeViewChildren}  navItems=${info.navItems}`);
  console.log(`  census(.app *): ${Object.entries(info.census).sort((a, b) => b[1] - a[1]).map(([t, n]) => `${t}:${n}`).join(' ')}`);
}
await ctx.close();
server.close();
