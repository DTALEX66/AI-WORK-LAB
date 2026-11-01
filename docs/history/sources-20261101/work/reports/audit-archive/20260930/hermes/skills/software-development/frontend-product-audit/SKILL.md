---
name: frontend-product-audit
description: Use for multi-dimensional user-facing frontend audits.
version: 1.0.0
---

# Frontend Product Audit

## Use when

Use when a user reports that a frontend is difficult to use, visually unchanged, inconsistent, too much like a backend console, has mixed language, lacks direct manipulation such as folder picking, or when a large frontend needs a multi-dimensional audit before delivery.

## Product-first operating rules

1. Treat the user's visible runtime as the acceptance surface. Source changes, unit tests, a successful route, or a build are supporting evidence, not visual or usability acceptance.
2. Audit the canonical frontend only. Identify and freeze the production entrypoint, embedded/bootstrap assets, desktop shell, and route surface before editing; do not polish an obsolete parallel UI.
3. Convert every complaint into an observable acceptance criterion. Examples: “选择文件夹” means a native directory chooser works in the desktop shell; “方便” means the primary path needs no manual path typing; “界面没变” means the delivered runtime visibly contains the intended design and language changes.
4. Execute the full bounded task without repeated status-only updates. If CI or a build is running, advance independent read-only audits or local verification rather than issuing identical polling messages.
5. Preserve fail-closed behavior: unsupported browser fallback, unavailable native APIs, failed validation, and rejected writes must be visible and must not be reported as success.

## Multi-dimensional audit matrix

Audit each production route or space across all dimensions below, recording concrete evidence and severity (P0 blocks use, P1 materially harms the primary flow, P2 polish/debt):

### 1. Entry and information architecture

- Can a first-time user tell what the product does and where to begin?
- Are primary actions visible without knowing internal IDs, commands, package names, or artifact terminology?
- Are navigation labels consistent, concise, and ordered by the user's workflow rather than backend modules?
- Are obsolete, duplicate, demo, mock, and sidecar surfaces excluded from the ordinary user path?

### 2. Task completion and interaction cost

- Count the steps for the primary task from a clean state.
- Replace manual path entry with native folder/file selection where the desktop platform supports it.
- Provide sensible defaults, recent locations, clear confirmation, validation feedback, and recovery after cancellation.
- Support direct manipulation appropriate to the task (folder picker, drag/drop, browse button), while retaining an explicit accessible fallback when native capability is unavailable.
- Avoid requiring users to understand filesystem syntax, API keys, JWTs, internal IDs, or approval mechanics for local single-user flows.

### 3. Visual hierarchy and design system

- Verify one coherent color, typography, spacing, radius, border, state, and icon language across every route.
- Check primary/secondary/destructive button hierarchy, hover/focus/pressed/disabled states, and touch target size.
- Look for backend-console symptoms: dense tables without hierarchy, arbitrary badges, raw technical labels, excessive panels, default browser controls, or inconsistent English/Chinese strings.
- Compare the real rendered surface against the chosen reference language (for example, restrained Linear/Obsidian/Notion-style information density), not against a screenshot generated from a different build.

### 4. Responsive and viewport behavior

Test at least desktop, tablet, and a narrow mobile width (390px is a useful contract). Measure `scrollWidth` versus `clientWidth`; inspect fixed rails, subnavigation, toolbars, grids, long labels, editors, and dialogs.

For a narrow viewport, prefer a deliberate transformation: collapse icon-capable rails, hide nonessential labels, allow flex children to shrink with `min-width: 0`, stack dense grids, and keep the primary action reachable. Do not hide overflow or weaken a geometry assertion merely to make a test pass.

### 5. Language and accessibility

- Ordinary user-facing copy is Chinese-first unless it is a product name, format, model name, or necessary technical identifier.
- Remove decorative emoji and unexplained abbreviations from operational controls.
- Use semantic headings, landmark roles, labels, keyboard focus, logical tab order, and visible focus rings.
- Verify disabled, loading, error, empty, and success states are understandable without inspecting the console.

### 6. Data, truth, and failure paths

- Trace each displayed value to a real API/adapter/command receipt; do not accept demo objects, `MockAdapter`, `UNBOUND`, or placeholder success.
- Test empty data, invalid input, cancelled chooser, unavailable backend, conversion failure, optimistic-lock conflict, and retry/re-read recovery.
- Ensure partial failure is clearly distinct from completed success and that a restart reads back the same durable state.

### 7. Desktop integration and packaging

- Verify the native shell loads the same canonical frontend assets that were audited.
- Verify native dialog plugins are registered in Rust and permitted by the shell configuration.
- Verify Windows child processes do not open unwanted console windows when launched from the desktop app.
- After packaging, launch the actual green/runtime artifact and re-check title, language, theme, routes, native dialogs, and persistence. A source checkout or dev server is not packaging evidence.

## Evidence-driven workflow

1. Discover available skills and load the matching audit/build/test skill.
2. Identify the canonical frontend and production desktop boundary.
3. Build an audit table by route and the seven dimensions above.
4. Prioritize P0/P1 issues affecting first-run completion, direct manipulation, visible hierarchy, responsive correctness, and truth boundaries.
5. For each fix, add or update a regression test where practical, but also perform a real rendered interaction check.
6. Run the exact local build and complete frontend suite. Run the real browser smoke at its declared viewports; do not infer responsive correctness from jsdom.
7. Rebuild and synchronize embedded/bootstrap assets. For desktop changes, require a fresh native build; never claim the green artifact contains source changes until its bytes or runtime behavior are verified.
8. Commit only the focused canonical changes, push, and bind CI results to the full head SHA. Require every required job to reach terminal success before delivery.
9. Re-open the exact target route and verify the user's original complaint is visibly resolved. Record unresolved items explicitly instead of substituting a test count.

## Common pitfalls

- Patching a source frontend while launching an older green executable or stale embedded bootstrap.
- Adding a native API only in React without registering its desktop plugin and permissions.
- Calling a text-input fallback a folder picker when the primary desktop path still requires pasting a path.
- Treating a green build/unit suite as proof of visual consistency, responsive layout, or user-friendly flow.
- Fixing a narrow-screen failure by accepting horizontal scrolling, clipping content, or weakening the browser assertion.
- Repeating identical copy/sync/poll commands after the intended state is already confirmed; inspect state and change strategy.

## References

- See `references/responsive-browser-smoke-case.md` for a concrete exact-SHA geometry failure and the durable remediation pattern.
