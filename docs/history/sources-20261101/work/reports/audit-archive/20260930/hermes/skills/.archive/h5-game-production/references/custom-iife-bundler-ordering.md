# Custom IIFE Bundler Ordering (build.js)

The MINIGAME repo uses a custom IIFE bundler at `build.js` (not webpack/rollup/esbuild). It concatenates source modules into a single IIFE after stripping ESM `import`/`export` with regex. This has several non-obvious constraints.

## Module Registration

Every module that exports functions used by another module must be listed in `CORE_MODULES` in `build.js`:

```js
const CORE_MODULES = [
  { path: 'src/gameConfig.js',     type: 'js' },
  { path: 'src/skins/elevator/skin.json', type: 'skin' },
  { path: 'src/skinManager.js',    type: 'js' },
  // ...
  { path: 'src/anomalyContent.js', type: 'js' },  // ← must be before visualState.js
  { path: 'src/visualState.js',    type: 'js' },  // ← depends on anomalyContent.js
];
```

**Load order rule:** If module A imports from module B, B must appear FIRST in the array. The `stripESM()` function removes all import statements, so at IIFE runtime the function from module B must already be defined when module A's code executes.

## Diagnostic

A module missing from `CORE_MODULES` produces `ReferenceError: <function> is not defined` at bundle runtime (the generated `douyin-minigame/game.js`), even when Node `npm test` passes perfectly (since Node resolves ESM imports independently of the build order).

**To confirm:** After building, grep the generated bundle for the missing function name:
```bash
grep -c 'function getAnomalyCctvState' douyin-minigame/game.js
# 0 → function is missing from the bundle
```

Then check if the source module is in `CORE_MODULES`:
```bash
grep 'anomalyContent' build.js
```

## MINI_ENTRY_MODULES

The mini-game build list (`MINI_ENTRY_MODULES`) starts by spreading `CORE_MODULES`:

```js
const MINI_ENTRY_MODULES = [
  ...CORE_MODULES.filter(module => module.path !== 'src/uiLabels.js'),
  { path: 'platform/canvasLabels.js', type: 'js' },
  // ...
];
```

So any module added to `CORE_MODULES` is automatically included in mini-game builds. Only platform-specific modules go into the spread.

## Limitations

- **No tree-shaking:** Once a module is included, ALL its code ends up in the bundle. The only dead-code elimination is manual (`if (false)` blocks).
- **No scope isolation:** All module code runs in the same IIFE scope. `const`/`let` declarations in different modules become closure-scoped variables.
- **`release.config.json` override only reaches `src/gameConfig.js`:** The `applyReleaseOverrides()` function specifically checks `modPath !== 'src/gameConfig.js'`. Other config-like modules won't get release overrides injected.
- **Skin JSON is injected as a global variable:** `var __SKIN_DATA__` is set from the JSON file contents. The `skinManager.js` module is specifically rewritten to reference `__SKIN_DATA__` instead of `SKIN_DATA`.
