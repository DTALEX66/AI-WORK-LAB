// SPDX-License-Identifier: MIT
// DESIGN-LAB Workbench Vite build (taskpack 24/25/26 / UCR-E).
// Emits a single deterministic, un-minified ES file `build/main.js` that is
// loaded two ways and must therefore carry NO top-level import/export:
//   1. the browser, via index.html <script type="module" src="/workbench/main.js">
//   2. the native-UI contract tests, via node vm.runInContext (classic script).
// main.ts keeps zero RUNTIME imports (only `import type`, erased at build), so
// the output is plain statements: valid both as an ES module and a classic script.
// minify is OFF: the tests read top-level function names and UI text, and a
// mangled bundle would silently break the contract. The workbench-gate CI job
// rebuilds and asserts `git diff --exit-code` over build/ (no drift), so the
// committed artifact stays the source of truth (MiniGame committed-bundle pattern).
import { defineConfig, type Plugin } from 'vite';
import { existsSync, readFileSync } from 'node:fs';

// Dev-only: index.html references /workbench/style.css and /workbench/main.js
// (production URL contract, D003). Under the Vite dev server (root =
// apps/workbench), those /workbench/* paths have no physical match, so Vite
// falls back to the SPA index.html and the browser sees HTML instead of
// CSS/JS. This middleware serves the real files for /workbench/* in dev so the
// SAME index.html works unchanged in production (Python service) and dev.
function workbenchDevAlias(): Plugin {
  return {
    name: 'design-lab:workbench-dev-alias',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.method !== 'GET' || !req.url) return next();
        const path = req.url.split('?')[0]!;
        if (!path.startsWith('/workbench/')) return next();
        const sub = path.slice('/workbench/'.length);
        if (sub === 'style.css') {
          const file = server.config.root + '/style.css';
          if (existsSync(file)) {
            res.setHeader('Content-Type', 'text/css; charset=utf-8');
            res.end(readFileSync(file));
            return;
          }
        } else if (sub === 'main.js') {
          // main.js entry: let Vite's native module transform handle it by
          // rewriting the URL to /main.js, which Vite serves as the entry module.
          req.url = '/main.js' + (req.url.includes('?') ? '?' + req.url.split('?')[1]! : '');
          // fall through to Vite middleware chain (next() re-dispatches with new url).
          next();
          return;
        } else if (sub === '') {
          // /workbench -> index.html (SPA fallback already handles this)
          next();
          return;
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [workbenchDevAlias()],
  base: '',
  build: {
    outDir: 'build',
    emptyOutDir: true,
    minify: false,
    target: 'es2022',
    rollupOptions: {
      input: 'main.ts',
      output: {
        format: 'es',
        entryFileNames: 'main.js',
        chunkFileNames: 'chunks/[name].js',
        inlineDynamicImports: true,
      },
    },
  },
});
