## What

De-couples the route-host heading from pre-B10 legacy CSS.

The placeholder headings rendered straight into `#route-view` (`el('h2', {}, view)` for an unopened/unconnected view, `shell.ts:783/868`) carry **no class**, so their vertical margins were supplied by the pre-B10 unscoped `h2{margin:0 0 14px}` rule — not by any B10 declaration.

This is the same hidden-coupling class as the three earlier fixes (1240px body cap, ghost-button hover, 13px paragraphs). All four existed for one reason: the legacy element rules still reach into `.app`.

## How it was found

Delete every unscoped element-only rule through CSSOM and diff **all** computed longhands of every `.app` element, on all 12 routes (328 elements). Deleting them reverted those two `h2` margins to the UA default `19.92px` — i.e. **8 in-`.app` property bindings** came from legacy CSS.

`.route-view h2` already declared `font-size` (which is why the font-size never leaked) but never `margin`.

| | in-`.app` legacy bindings |
|---|---|
| before | **8** |
| after | **0** |

## The fix

Declare the margin where the app already declares the heading's font-size. The frozen values are **exactly the previously computed ones**, so this removes the dependency without changing what the browser paints — a de-coupling, not a redesign.

The font-size divergence itself is deliberately **not** touched: this host renders 24px while B10's own page heading is `.page-head h2{font-size:32px;margin:0 0 6px}`. That is a W01 typography item tied to pending owner rulings **X-1/X-2**, and silently "fixing" it here would pre-empt a decision that is not mine to make.

## Harness integrity

The sweep carries an **end-to-end positive control** (an injected element-only leak must be reported) because three separate harness bugs had already produced false results:

1. `.app-nav-item` is a `<button>` with `data-route`, not an `<a href>` — route discovery returned `null ×12`, URLs became `?dev=1null`, dev mode never engaged and the sweep silently measured the login screen. Discovery now aborts loudly.
2. A `goto` differing only in the hash is a **same-document** navigation, so each route now gets a unique query to force a real document load.
3. **Same-task staleness**: `getComputedStyle` read in the same task as the CSSOM mutation returns the pre-mutation value. Measured directly — the rule list went 10 → 8 and the deleted rules were gone, yet before/after for the first button were byte-identical. Prepare and read are now separate tasks; without this the sweep undercounted leaks.

## Important boundary

The sweep also reports **1923** legacy-supplied bindings that live **outside** `.app`: the login/connect screen, `#workspace` and `nav.app-nav` are the legacy app, which B10 does not govern. This is why the legacy element rules **cannot** simply be scoped away — an earlier plan to do exactly that would have broken the login and workspace screens. Recorded in the evidence file.

Evidence: `.project-local/task-artifacts/designlab-followup-taskpack-20260928/W02-LEAK-SWEEP.txt`. Local gates: workbench smoke + appshell regression pass.

CSS-only change; `apps/workbench/build/` is untouched (the sheet is served separately at `/workbench/style.css`).
