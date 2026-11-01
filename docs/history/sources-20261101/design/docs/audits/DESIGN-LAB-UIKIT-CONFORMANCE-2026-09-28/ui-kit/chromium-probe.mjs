// SPDX-License-Identifier: MIT
import { chromium } from 'file:///D:/All projects/DESIGN-LAB/apps/workbench/node_modules/playwright/index.mjs';
try {
  const b = await chromium.launch({ headless: true });
  const page = await b.newPage();
  await page.setContent('<title>probe</title>');
  console.log('CHROMIUM_LAUNCH_OK ' + b.version());
  await b.close();
} catch (e) {
  console.error('CHROMIUM_LAUNCH_FAIL ' + String(e).slice(0, 400));
  process.exit(3);
}
