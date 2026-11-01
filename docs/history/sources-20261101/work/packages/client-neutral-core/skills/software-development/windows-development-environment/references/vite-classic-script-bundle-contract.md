# Vite flat-classic-script bundle contract (vm-driven) and modular split

Some workspaces (DESIGN-LAB `apps/workbench` is the canonical case) ship a
committed single-file bundle `build/main.js` that must be loadable **two ways**:
1. the browser, via `<script type="module">`; and
2. a Node contract test, via `node` `vm.runInContext` as a **classic script**.

Because of (2) the emitted bundle must carry **no top-level import/export** and
must keep every shared-state binding as a **bare top-level `let`/`const`/
function global** — the test drives it by writing/reading bare globals inside
the same `vm` context (`vm.runInContext("project='p'", ctx)`). The build config
that produces this is: `format: 'es'`, single entry, `inlineDynamicImports: true`,
`minify: false` (tests grep top-level function names and UI text).

## The load-bearing invariant (and the refactor trap)

The original single `main.ts` works because it has **zero runtime imports**
(only `import type`, erased at build), so Rollup emits a flat script. The
decisive trap when you **split it into multiple modules**:

- **Do NOT centralize state in a `const S = { project, epoch, ... }` object.**
  Rollup emits `const S = {...}`; the bare top-level `let project` the vm test
  writes to disappears, so `project='p'` lands in a different binding than the
code's `S.project` → every vm contract test silently fails to drive the UI.
- **Do NOT write to another module's state binding from your module.**
  `import * as S from './state.js'; S.project = x` is a cross-module write:
  some TypeScript versions/tsconfigs reject it with **TS2540** ("Cannot
  assign to 'project' because it is a read-only property"), others accept it
  (e.g. the workbench tsc 5.6.3 + `moduleResolution: bundler` accepted it).
  Do not design around either behavior — route the write through the owning
  module (rule 3 below) so correctness never depends on the compiler's
  strictness.

## Verified working shape

Proven with the project's own Rollup (4.63.3): source modules using
`export let x` + a consumer that does `import * as S` **do** flatten —
`export let a` → bare top-level `let a = 1;` in the bundle, and the consumer's
`S.a = 42` / `S.f()` rewrite to bare `a = 42; f();`. `import type` and value
imports both vanish (inlined), no top-level import/export survives. So the flat
contract *is* achievable from multiple source files. **Status:** the
flattening mechanics are proven by the toy probe only. A full workbench attempt
on this shape reached the three build-only gates green, but the native-UI vm
pytest gate still failed (16 tests, root cause not established) and was rolled
back to the monolith — do not treat a split as done until the vm gate passes
on the real multi-module build; a 2-file toy can emit differently from a graph
where several modules consume the same state module. The rules:

1. **Each state variable is declared, written, AND exported in the one module
   that owns it.** Intra-module write = plain `x = ...` (legal, emits `x = ...`).
   Never write a binding that is owned/exported by a *different* module.
2. **Cross-module access to another module's state is read-only**, via
   `import { x } from './<owner>.js'` (named) — reads rewrite to bare globals
   and are TS-clean. No writes.
3. **If a reset/init routine in module A must clear state owned by module B,
   move that clearing into a function exported by B** (e.g. B exports
   `resetDesignRevision()` that nulls its own 5 vars) and have A *call* it.
   Function calls are clean ESM; cross-module state writes are not.
4. **Circular value imports are safe** as long as no binding is *used at
   module-init (top-level) time* — use it only inside function bodies
   (call-time). Note the hoisting asymmetry that makes this constraint real:
   `function` declarations are hoisted and callable before their line, but a
   `const`/arrow or `let` sits in the temporal dead zone until its own
   declaration line runs. In an *acyclic* graph Rollup emits declarations
   before their uses, so the constraint holds; in a *cyclic* graph a top-level
   use of the peer's `const` can be emitted before that `const` initializes
   (module-init TDZ) — see the 'Second trap' section below.
5. **The entry module (`main.ts`) stays the single import root** with no
   exports; it does top-level DOM/event wiring + mount guard. All other
   modules are declaration-only at top level.
6. **Always verify against the ACTUAL bundler, never by theory.** Before
   committing a split, run a 2-file toy through the *project's* Rollup/Vite
   (`format:'es'`, single file) and assert on the emitted text: bare `let <x>`
   present at top level, the namespace write inlined to a bare `x = ...`, and
   **no** top-level `import`/`export`. A tiny probe beats 1500 lines of
   guesswork — write it under `.project-local/` and run it via the wrapper.

## Second trap: module-init TDZ under a value-import cycle

The `const S` regression above fails *at the test level*; a subtler one fails
*at load time*, surfacing as `ReferenceError: Cannot access '<name>' before
initialization` when the vm contract test executes the bundle.

Mechanism: **`function` declarations are hoisted and callable before their line
runs; `const`/arrow and `let` are NOT** — they stay in the temporal dead zone
until their own declaration line executes. In a flat single-file bundle the
modules are inlined, but their top-level statements still run in *emit order*.
When two modules value-import each other (a cycle, e.g. `workbench ↔ design`),
Rollup cannot order them topologically, so one module's top-level executable
statements can be emitted before the other module's `const` helper is
initialized. A top-level wiring line `byId(...).onsubmit = ...` that reads a
`const byId` owned by the cycle peer then throws `Cannot access 'byId' before
initialization`.

Both naive layouts hit a wall:
- **All top-level wiring in the entry `main.ts`** → the entry runs last (safe
  for *reading* any module's consts), but state-*writing* wiring
  (`token = …`, `project = …`) is a named-import in the entry, and writing an
  imported binding is **TS2632** ("Cannot assign to … because it is an
  import"). So state-writing wiring cannot move to the entry.
- **Each module keeps its own top-level wiring** → the wiring that only READS a
  cycle peer's `const` hits the TDZ above.

Fix direction (diagnosed; verify against the real bundle + vm gate before
declaring done, per the Status note):
1. **Break the value-import cycle.** Extract the shared helpers both peers need
   (`byId`, `api`, `setStatus`, `errMsg`, `button`) into a leaf module that
   imports nothing from either peer. Then `workbench → leaf` and
   `design → leaf` with no peer-to-peer cycle; ordering becomes topological and
   no top-level cross-module `const` read remains at init time.
2. **Split wiring by write-ownership, not by region.** Top-level wiring that
   only READS state → entry module (runs last, so safe). Top-level wiring that
   WRITES state → its owning module (the only place a write is legal). With the
   cycle broken in step 1, the owning module's init-time reads are of its own
   leaf-declared helpers, so no TDZ.
3. **Re-run the vm/native-UI gate on the REAL multi-module build** — the toy
   probe flattens, but only the full graph with its cycle resolved proves the
   init order is safe. Then re-lock `sha256sum` of the re-committed bundle.

## Pre-split census (do before slicing anything)

- **Write-ownership census.** For every shared state variable, grep its
  assignment sites across the whole file (word-boundary `v =` / `v +=` /
  `v -=`, excluding `==` / `=>` / `<=` / `>=` false matches) and classify
  each site by the region it sits in. A variable written from more than one
  region is a design constraint: move those writes into the owning module's
  exported reset/mutator (rule 3) and have the other region *call* it. Run
  the census BEFORE slicing — it is the only input that tells you how many
  mutators the split needs.
- **Enumerate the vm contract surface first.** Regex the vm test source's
  `runInContext` string arguments for bare write targets (`x = ...`), bare
  calls (`fn(...)`), and bare reads; that identifier set is the top-level
  col-0 name set the emitted bundle must keep. Carry it as the split's
  acceptance checklist.
- **Compute import sets with word-boundary scans, then let the project tsc
  arbitrate.** Scans produce false positives from comment-only mentions and
  from locally-shadowed names (a top-level `function el(...)` vs a local
  `const el = byId(...)` in another region). tsc reports missing imports as
  errors and tolerates stray extra named imports, so over-include from the
  scan and only trim what tsc flags — and verify names that appear only in
  comments are not imported.

## Verifying the no-drift + vm contract after the split

- `sha256sum build/main.js` before (committed) and after (fresh build) — must
  be identical for a no-drift gate; if the split changes the byte layout, the
  gate needs the new bundle re-committed *as the source of truth* (rebuild,
  commit, confirm the diff is only the expected reordering).
- Run the vm/native-UI contract tests **first** — they are the gate that
  catches the `const S` regression (bare globals missing). If they fail
  with `Cannot read properties of undefined (reading 'children')`-style
  errors, that is the binding-landing symptom (a test writes a bare global
  the bundle no longer reads, or vice versa), not a DOM-mock bug.
- **Before rolling back** a failed split, diff the emitted bundle's col-0
  global names against the enumerated vm contract surface and save that diff
  plus the failing-test list under `.project-local/` — the rollback then
  carries its root-cause evidence instead of forcing the next attempt to
  re-derive the constraint surface from scratch.
- A full monolith→modules split that breaks the vm contract is safer to
  **revert to the green baseline** (`git checkout -- <files>` + delete the
  new modules) than to push through: re-lock `sha256sum` of the committed
  bundle and the two vm gate scripts, then redesign the split rather than
  chasing a red build. A partial green (unit gates pass, vm gate red) is a
  trap — "all gates green" is the bar.

## Windows tooling notes specific to this flow

- pnpm shims double-translate under the project-data wrapper on Windows → run
  the tool bin directly with the project node (`node apps/x/node_modules/vite/bin/vite.js build`),
  `cd` into the package dir (Vite CAC rejects `--config`+`--root` together).
- Typecheck the split with the project tsc: `node apps/x/node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`.
- Long path literals / large output truncate in the `execute_code` kernel → put
  that logic in a script under `.project-local/` and run it via the wrapper.
