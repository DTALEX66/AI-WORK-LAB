## What

Adds the **unscoped `.seg` segmented control** that B07's component-registry maps `Tabs` onto.

B10 (the in-repo UI kit) defines the segmented control **only inside `.toolbar`**, so the class is unusable anywhere else. B07 registers all 46 components with **four** declared states (default / hover / focus / disabled), while B10's toolbar rule declares only `default` and `active`.

## Change

- copy B10's `.toolbar .seg*` literals **verbatim** as unscoped `.seg*`
- add the two states B07 declares but B10 never expressed: hover (`120ms`, `--motion-fast`) and focus (`2px` ring, `2px` offset), plus `:disabled` (`opacity .45`, `not-allowed`)
- no new tokens, no new dependency, no B10 restyle

## Leak containment (the interesting part)

`.seg button` `(0,1,1)` also matches **inside** the toolbar. Every property B10's `.toolbar .seg button` `(0,2,1)` declares — `border`, `background`, `color`, `padding`, `border-radius` — is copied as the **same literal**, so the only property that can leak is one `.seg button` declares that B10's toolbar rule never declares: `transition`. It did leak (measured `none → 0.12s`), so `.toolbar .seg button{transition:none}` restores the pre-existing value explicitly.

Proven by an **18-property computed-style diff** of unscoped `.seg*` vs `.toolbar .seg*`:

| member | properties compared | differing |
|---|---|---|
| `.seg` (wrap) | 18 | **0** |
| `.seg button` | 18 | 1 — `transition` (restored) |
| `.seg button.active` | 18 | 1 — `transition` (restored) |

## Evidence

`w02-verify-seg.mjs` — **19/19 PASS** under the exact CSP the service serves.

Local gates: workbench smoke **4/4**, appshell regression **all checks passed**.

## Harness corrections (tooling defects, NOT product defects)

Both were found while verifying and are recorded in the probe:

1. The focus probe called `getComputedStyle` in the **same task** as `focus()`, so it read the **transition start state** — pre-focus `outline-width` is the initial `medium` (`3px`) and offset `0px`. That looked exactly like the legacy `body`-level `button:focus-visible` rule (`3px solid` secondary) had won. After settling: `2px solid rgb(49,108,255)` = `--color-primary`, i.e. the intended rule **does** win on specificity `(0,2,1)` vs `(0,1,1)`. Third occurrence of this bug class in this session.
2. A literal `rgba(0, 0, 0, 0)` background assertion was a **misread of the wrap row** in the dump and produced a false FAIL; replaced with an identity assertion. `color-mix()` results serialize as `color(srgb ...)`, not `rgb()`/`rgba()`.

## State

Not a claim of any capability-axis promotion: this is a CSS-only structural addition (E1 STRUCTURAL). `host_live`/`delivery` axes remain untouched and still require real host hardware.
