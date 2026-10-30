// SPDX-License-Identifier: MIT
// DESIGN-LAB Workbench — deterministic node-side smoke (taskpack 12.5 workbench-gate).
//
// Runs the COMMITTED Vite output (build/main.js, D003 Build Output Truth) as a
// classic script and asserts the facts the Python contract suite
// (design-lab/tests/test_workbench_native_ui.py) does NOT cover:
//   * build/main.js exists, is non-trivial, and has NO top-level import/export
//     (D004: the production path is not "treat .ts as .js" — Vite already bundled
//      it, so the artifact must be loadable by a plain classic <script>).
//   * strict-typecheck survived: user-visible labels and handler names are intact
//      (a strict rewrite that renamed/dropped them would fail here).
//   * the fixed API route prefix is unchanged (frontend/backend contract).
//
// stdlib-only (node:fs, node:vm) so it is deterministic and needs no Playwright.
// Browser-level E2E (real Chromium) is a separate, opt-in step in the gate.

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const bundlePath = join(here, '..', 'build', 'main.js');

let failures = 0;
const fail = (msg) => { failures += 1; console.error(`FAIL: ${msg}`); };
const pass = (msg) => console.log(`ok: ${msg}`);

if (!existsSync(bundlePath)) {
  console.error(`FAIL-CLOSED: ${bundlePath} missing — run \`pnpm --filter @design-lab/workbench build\` first (D003 Build Output Truth)`);
  process.exit(1);
}
const src = readFileSync(bundlePath, 'utf8');

// 1) Non-trivial artifact.
if (src.length < 1000) fail(`build/main.js looks too small (${src.length} bytes); expected the full Workbench bundle`);
else pass(`build/main.js present (${src.length} bytes)`);

// 2) No top-level ES module syntax (must load as a classic script).
const moduleSyntax = /^\s*(import|export)\b/m.test(src);
if (moduleSyntax) fail('build/main.js contains top-level import/export — it would not load as a classic <script> (D004)');
else pass('build/main.js has no top-level import/export (classic-script loadable)');

// 3) A classic-script load must not throw (lazy element mock, same semantics as
//    the Python contract suite: getElementById creates on first access).
class MockElement {
  constructor() { this.children = []; this.style = {}; this.classList = { toggle() {} }; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren() { this.children = []; }
  removeAttribute() {}
  addEventListener() {}
}
const mockElements = {};
const ctx = vm.createContext({
  document: {
    getElementById: (id) => (mockElements[id] ??= new MockElement()),
    createElement: () => new MockElement(),
  },
});
try {
  vm.runInContext(src, ctx, { filename: 'build/main.js' });
  pass('build/main.js executes under vm without throwing');
} catch (error) {
  fail(`build/main.js threw under classic-script load: ${String(error)}`);
}

// 4) Strict rewrite preserved user-visible labels + handler names + route prefix.
const required = [
  'startTask', 'cancelTask', 'exportBundle', 'preview', 'verifyNative',
  '不代表制作成功', '请求取消', '启动任务', '导出交付包', '/api',
];
for (const token of required) {
  if (!src.includes(token)) fail(`build/main.js lost expected token "${token}"`);
}
if (failures === 0) pass('labels, handler names, and /api route prefix all present');

if (failures > 0) {
  console.error(`\nWORKBENCH SMOKE: ${failures} failure(s)`);
  process.exit(1);
}
console.log('\nWORKBENCH SMOKE: all checks passed');
