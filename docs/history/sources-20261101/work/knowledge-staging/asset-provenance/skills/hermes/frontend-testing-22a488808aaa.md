---
name: frontend-testing
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/frontend-testing/SKILL.md
---

---
name: frontend-testing
description: "Use when adding or running Vitest + RTL component tests."
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [vitest, react-testing-library, jsdom, a11y, component-tests]
---

# Frontend Testing (Vitest + React Testing Library)

## When to use

- Adding a Vitest + RTL test skeleton to a Vite/React frontend (package.json devDeps, vite.config `test` block, setup file).
- Writing component tests with accessibility assertions (roles, accessible names, `aria-current`, landmarks, keyboard focus).
- Debugging `Found multiple elements` query failures or focus/focus-visible assertions in jsdom.

## Dependency matrix (validated on vite ^5.4 / react 18 / TS 5.5, 2026-08)

- `vitest` **^2.1.x** — vitest 2 pairs with vite ^5; vitest 3 requires vite ^6+. Do not mix.
- `@testing-library/react` ^16 (React 18/19; peer `@testing-library/dom` ^10 auto-installed by npm).
- `@testing-library/jest-dom` ^6 — import `"@testing-library/jest-dom/vitest"` (the `/vitest` entry, not the bare import).
- `@testing-library/user-event` ^14 — `userEvent.setup()` + `user.tab()` for keyboard tests.
- `jsdom` ^25 — works with vitest 2.1.x; supports `:focus-visible` matching (≥ 22).

## Setup steps

1. `package.json` scripts: `"test": "vitest run"`, `"test:watch": "vitest"`.
2. `vite.config.ts`: `/// <reference types="vitest" />` at top (augments vite's `UserConfig` with `test`; keep `defineConfig` from `"vite"`), then:
   ```ts
   test: {
     environment: "jsdom",
     setupFiles: ["./src/test/setup.ts"],
   },
   ```
3. `src/test/setup.ts`:
   ```ts
   import "@testing-library/jest-dom/vitest";
   import { cleanup } from "@testing-library/react";
   import { afterEach } from "vitest";
   afterEach(() => {
     cleanup();
   });
   ```
   **Critical pitfall**: without `globals: true`, RTL's auto-cleanup is NOT registered, so rendered DOM accumulates across tests and queries start matching elements from previous tests ("Found multiple elements…"). The explicit `afterEach(cleanup)` fixes it without enabling globals.
4. Import `describe/it/expect/vi` explicitly from `"vitest"` (no globals) → no `tsconfig` `types` changes needed.

## Build interplay

- Tests under `src/` are type-checked by `tsc --noEmit` (often part of `npm run build`). jest-dom matcher types (`toBeInTheDocument`, `toHaveAttribute`, `toHaveFocus`) augment the whole TS program once `setup.ts` (which imports the `/vitest` entry) is in the compilation.
- Always re-run `npm run build` after adding tests — new test files must not break the build.

## A11y assertion patterns

- Accessible names: `getByRole("button", { name: "Library" })` — proves the control is reachable by its name; combine with `within(nav)` to scope.
- `aria-current`: `toHaveAttribute("aria-current", "page")` on the active item; `not.toHaveAttribute("aria-current")` on the others (assert exactly one current).
- Landmarks: `getByRole("banner")`, `getByRole("navigation", { name: … })`, `getByRole("main", { name: … })`.
- Keyboard focus + focus-visible: loop `await user.tab()` over the focusable elements; assert `expect(el).toHaveFocus()` and `expect(el.matches(":focus-visible")).toBe(true)` (works on jsdom ≥ 22).
- Status badges: assert readable text (`textContent?.trim()` non-empty) — never color-only indicators.
- Prefer role queries over `getByText` when the same text can appear in multiple renders/regions; scope with `within(region)`.

## Async transport/state-machine tests

For UIs combining EventSource/WebSocket transport with snapshot GETs, test ordering—not just final happy paths or source-code regexes.

- Keep canonical data truth separate from local transport truth. Assert that cloning `lastGood` cannot resurrect an old `LIVE`/connected transport after a local OFFLINE latch.
- Use fake timers plus deferred promises to force both race directions: stale success after a newer transport failure, and stale failure after a newer reconnect success.
- Cover `onError → generic refresh error`, `onError → reconnect/onOpen`, simultaneous snapshot-retry and reconnect timers, duplicate error callbacks, and retry backoff reset/cap behavior.
- Assert stale callbacks cannot close or overwrite a newer EventSource instance. Production code normally needs a transport epoch/request id or abort strategy; tests should prove old generations are ignored.
- Render after each transition and assert symmetry across internal mode, transport fields, badges, and accessible status text. A state such as `mode=OFFLINE` plus `transportState=LIVE` is a failure even if each field was individually valid earlier.
- Regex/source assertions can enforce read-only API shape, but they do not validate temporal behavior; pair them with executable timer/promise tests.

## Host-specific invocation

On the ArcheAxis host, npm/vitest run through the project-data guard wrapper (child cwd pinned to git top-level, literal external paths blocked). See `windows-development-environment` skill → `references/npm-under-wrapper-windows.md` for the junction + `bash -c 'cd frontend && …'` recipe.

## Pitfalls recap

- Missing RTL cleanup → duplicate-element failures (fix in setup.ts, not by enabling globals).
- vitest major must match vite major (2 ↔ 5).
- jest-dom bare import may not register matchers for vitest's expect — use `@testing-library/jest-dom/vitest`.
