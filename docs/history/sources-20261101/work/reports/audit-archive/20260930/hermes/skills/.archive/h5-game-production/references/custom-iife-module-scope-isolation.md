# Custom IIFE bundler: lexical isolation and executable-bundle tests

Use this when a mini-game build strips ESM syntax and concatenates modules into one generated IIFE.

## Durable failure mode

Registering modules in dependency order is necessary but not sufficient. If stripped module bodies share one lexical scope, private top-level `const`, `let`, or `class` names can collide as the module set grows. Converting all declarations to `var` only hides syntax errors and can silently overwrite bindings.

## Minimal safe pattern

For each JavaScript module:

1. Read the original source before stripping exports.
2. Collect public bindings from:
   - `export function|const|let|var|class name`
   - `export { local as exported }`
   - identifier defaults such as `export default CONFIG`
3. Emit a module-unique export bag in the outer IIFE scope.
4. Execute the stripped module body inside its own lexical block.
5. Capture public local bindings into the export bag before leaving the block.
6. Lift those public bindings into the outer compatibility scope for later modules.
7. Keep JSON/config injection and module ordering deterministic.

Conceptual output:

```js
var __exports_src_state_js = {};
{
  const privateHelper = ...;
  function createInitialState() { ... }
  __exports_src_state_js.createInitialState = createInitialState;
}
var createInitialState = __exports_src_state_js.createInitialState;
```

A module-import alias that must refer to an earlier export may need an explicit build-time capture inside the new block. Do not leave stripped aliases unresolved, and ensure platform checkers do not reject obsolete alias names.

## TDD acceptance

RED must prove the old generated bundle lacks isolation. GREEN should verify all of the following:

- generated source contains a lexical block per JS module;
- repeated builds are byte-identical;
- the untouched target bundle boots against a minimal host API mock;
- a test-only copy with startup replaced executes in `node:vm`;
- functions exported by different modules can be called after bundle execution;
- existing target checks report zero runtime blockers;
- full tests and package-size gates pass.

A syntax-only check is insufficient: it cannot catch export lifting, alias capture, initialization-order, or runtime host-contract failures.

## Generated artifacts

If platform bundles are tracked, rebuild and stage the canonical generated outputs explicitly. Do not claim or document an Android/WebView artifact as modified unless `git status` confirms it. After tests that generate temporary targets, remove only the known generated directory and re-check status before staging.
