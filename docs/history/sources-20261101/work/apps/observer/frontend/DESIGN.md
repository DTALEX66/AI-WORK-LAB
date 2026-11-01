---
version: alpha
name: WORK-LAB Observer — Liquid Glass control plane
description: "Design contract for the WORK-LAB Observer desktop front-end, captured from the shipped implementation (pinned B10 skin + L10b overlay + src/theme/tokens.ts) and from measured rendering evidence. Dark is the default theme; light is an overlay. Read-only projection surface, so no component in this system may mutate workflow state."
colors:
  primary: "#2A91FF"
  secondary: "#20CDE1"
  on-primary: "#050D16"
  ink: "#EEF6FC"
  muted: "#8EABBC"
  canvas: "#050D16"
  surface-sidebar: "#07111C"
  surface-panel: "#081420"
  surface-raised: "#0C1B2A"
  hairline: "#17435D"
  success: "#22C55E"
  warning: "#F59E0B"
  danger: "#EF4444"
  info: "#3882F6"
typography:
  kpi-value:
    fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif"
    fontSize: 30px
    fontWeight: 700
    lineHeight: 1
    letterSpacing: -0.025em
  heading-lg:
    fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif"
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0px
  brand-name:
    fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif"
    fontSize: 17px
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: 0px
  body-md:
    fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  body-strong:
    fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: 0px
  label-caps:
    fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: 0.08em
  meta-sm:
    fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.35
    letterSpacing: 0px
  code-mono:
    fontFamily: "'JetBrains Mono', Consolas, monospace"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
rounded:
  none: 0px
  sm: 12px
  md: 10px
  lg: 16px
  xl: 22px
  full: 9999px
spacing:
  xxs: 4px
  xs: 6px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  xxl: 32px
  section: 40px
components:
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
    height: 38px
  nav-item-active:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
    height: 38px
  action-button:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "10px 16px"
    height: 44px
  text-input-search:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "10px 14px"
    height: 44px
  kpi-card:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.ink}"
    typography: "{typography.kpi-value}"
    rounded: "{rounded.xl}"
    padding: "20px"
  state-chip:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.muted}"
    typography: "{typography.code-mono}"
    rounded: "{rounded.sm}"
    padding: "2px 6px"
  status-danger:
    backgroundColor: "transparent"
    textColor: "{colors.danger}"
    typography: "{typography.heading-lg}"
    rounded: "{rounded.none}"
    padding: "0px"
  brand-mark:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary}"
    rounded: "{rounded.none}"
    width: 42px
    height: 22px
---

# WORK-LAB Observer design contract

## Overview

This system was **captured from the shipped implementation**, not designed first. Three sources carry
numbers today and they do not agree; the authority order is fixed below and every token in the
frontmatter is traceable to source #1.

1. `src/theme/tokens.ts` — declared single source of truth, mirrored by `src/index.css` and asserted by
   `src/theme/tokens.test.ts`. **Authoritative.**
2. `src/skins/b10.css` (pinned skin, immutable per decision D-11) and `src/skins/l10b-shell.css`
   (overlay). Binding for anything they define that #1 is silent about; the overlay may only add, never
   rewrite #1's roles.
3. `src/assets/brand/design-tokens.json` (`name: WORK-LAB Observer Liquid Glass`, `version: 2.0.0`).
   Supporting evidence for brand accents and glass parameters only — its `radii` block conflicts with
   #1 and is recorded in Known Gaps rather than merged.

Product feel: dark, dense, instrument-like. A control plane, not a marketing surface. Cyan→blue accents
carry state; nothing decorative may outrank a number. The surface is a strict read-only projection —
no component in this file authorises a write, approve, retry or rollback action.

Two orthogonal axes exist and must not be confused:

- **Theme**: `dark` (default, `:root`) / `light` (`html.light`). Colour roles only.
- **Density view**: `?view=full` / `?view=compact`. Layout density only. **This is a user-selected mode,
  not a responsive breakpoint** — see Responsive Behavior.

## External standards this contract is measured against

Every numeric clause below cites a primary source. Where two authorities conflict the clause names both
and picks one with a reason; it never averages them.

**Text size.** WCAG 2.2 sets **no** minimum font size — small text is policed by contrast (1.4.3), by
200% zoom (1.4.4), by reflow at 320 CSS px (1.4.10) and by text spacing (1.4.12). The floors below come
from design systems, and they are product rules, not WCAG claims: Apple's "UI Design Dos" says text should
be at least **11pt**; Material 3's smallest role is `label-small` **11sp/16**; IBM Carbon's scale bottoms
out at **12px/16**; PatternFly's `--pf-t--global--font--size--100` is **12px**; Grafana's
`createTypography.ts` uses base **14** with **12** as the small step. No authoritative source endorses
9px, so this contract's floor is **12px** for any text a user must read.

**Contrast.** WCAG 1.4.3 AA: **4.5:1** normal, **3:1** large, where "large" is 18pt (≈24px) or 14pt bold
(≈18.66px bold); AAA is 7:1 / 4.5:1. 1.4.11 AA: **3:1** for UI-component states, boundaries and graphical
objects, exempting purely decorative ones. 1.4.1 A: colour is never the only carrier — a status surface
needs a label or glyph plus shape/weight/position, and must not rely on red-vs-green alone.

**Targets.** WCAG 2.5.8 AA is the hard floor: **24×24 CSS px**, with the Spacing exception permitting a
smaller visible control if a 24×24 clearance surrounds it. Apple asks **44×44pt**, Microsoft **7.5mm ≈
40×40px at 135 PPI**, Google commonly 48dp, NN/g 1cm² — these conflict and are *not* averaged. For a
mouse-driven desktop WebView the defensible floor is 2.5.8's 24×24, and this product additionally requires
**≥32px** for a repeated primary control because the rail row is the highest-frequency target.

**Focus.** WCAG 2.2 adds 2.4.11 **Focus Not Obscured (Minimum)** (AA) — the focused component may not be
entirely hidden by author content, which is a direct constraint on an overlapping top bar — and 2.4.13
Focus Appearance (AAA: indicator area of a 2px perimeter, 3:1 focused-vs-unfocused).

**Rail behaviour.** No design system mandates a scrollable rail; the binding rules are 2.1.1 Keyboard,
2.4.11 and the ARIA APG **Disclosure Navigation** pattern (each group is a disclosure button,
`aria-expanded`, Space/Enter toggles, Escape returns focus). The expectation is therefore **both**: the
rail is its own keyboard-reachable scroll container *and* its groups collapse. Rancher's
`shell/components/nav/Group.vue` implements the per-group form.

**Toolbar overflow.** Fluent **CommandBar** specifies a "see more" overflow button with primary commands
moving to the secondary area when space is limited; Carbon **OverflowMenu** is the named pattern for
"more options exist but space is constrained". A toolbar that wraps into a vertical column satisfies
neither.

## Colors

Semantic roles, dark theme (measured contrast against the role it sits on, WCAG 2.1 relative luminance,
alpha composited down the ancestor chain):

| Token | Value | Role | Measured |
|---|---|---|---|
| `{colors.canvas}` | `#050D16` | app background | — |
| `{colors.ink}` | `#EEF6FC` | primary text | 17.87:1 on canvas |
| `{colors.muted}` | `#8EABBC` | secondary text, labels | 8.09:1 on canvas, 7.22:1 on `{colors.surface-raised}` |
| `{colors.primary}` | `#2A91FF` | accent, links, focus | 6.13:1 on canvas |
| `{colors.danger}` | `#EF4444` | error, refused, offline | 5.19:1 on canvas |
| `{colors.hairline}` | `#17435D` | borders | 1.23:1 vs canvas — **decorative only, never carries meaning alone** |

Light theme re-binds the same role names (`src/index.css` `html.light` block plus the mirrored skin
tokens in `src/skins/l10b-shell.css`): canvas `#F4F7FA`, ink `#0B1420` (17.21:1), muted `#4A6172`
(5.64:1 on panel, 6.02:1 on canvas), hairline `#D5E2EC`.

Muted is `#4A6172` and not `#5A7184` because the two token vocabularies in this shell disagreed (see
Known Gaps): the B10 skin already carried `#4A6172`, and the Tailwind layer carried `#5A7184`, which
measures 4.43:1 on `panel2` — under AA by a margin made entirely of one duplicated role name. One
value per role removed the failure and the discrepancy at the same time.

**Text-accent rule (normative).** A fill accent and an accent used as text are different roles.
`{colors.primary}` `#1B7FE6` in light measures 3.74:1 on the rail, so text that wants the accent takes
`--primary-text` `#1565C0` (5.34:1) instead of darkening every filled control. The secondary accent had
the same defect one width-band further out: `text-secondary` (`#0E93A5`) measured **3.49:1** on a light
panel in the task-packs table IDs and a work-view link, so it gains the same pair — `--secondary-ink-rgb`
is `11 95 107` in light (6.4–7.3:1) and unchanged in dark, where the fill already reads. Darkening a
fill to fix text, or accepting 3.49:1 because "it's only a link", are both wrong: the role decides.

**Contrast rule (normative).** Text a user must read: ≥ 4.5:1 at sizes below 18.66px, ≥ 3:1 at
≥ 18.66px bold or ≥ 24px. Non-text UI and icons: ≥ 3:1. A hairline may be below 3:1 only if the
information it separates is also conveyed by spacing or a label.

**How a ratio is computed (normative).** The instrument composites the ancestor stack root-first, but
the *decider* is the first layer from the text outward that carries a gradient or is opaque — and a
gradient is evaluated at every colour stop, with each stop's own alpha preserved. Two reasons, both
measured here: listing the page background as a candidate scored white text on a green pill at 1.04:1
"against white", a backdrop the glyph never touches; and dropping a stop's alpha turned
`.nav button.active`'s 26%-primary wash into solid `#2A91FF` and reported an 11:1 selected row as a
2.92:1 failure. A wrong number in the instrument sends the fix to the wrong file.

**Disabled text (normative).** WCAG 1.4.3 exempts inactive controls. This contract does not, at the
lower bar: a disabled label must clear **3:1**. The reason is specific to a read-only projection — the
disabled button *is* the message ("执行由 Task Protocol 创建，Observer 不发起执行"), so a control whose
label cannot be read has lost the only thing it was there to say. `opacity: 0.55` over b10's bright
filled gradient measured 1.62:1 in dark and 1.71:1 in light; the disabled state is now carried by a
neutral surface with `--muted` ink, which clears 5:1 in both themes. Opacity is not a contrast strategy.

**On-primary rule.** `{colors.on-primary}` is `{colors.canvas}` in dark (6.13:1 on `{colors.primary}`).
In light theme white-on-primary measures **4.02:1** and therefore fails the text rule: light-theme
filled controls must use `#0B1420` ink on the accent, or a darker accent stop. See Known Gaps.

## Typography

Rendered census of the shipped Overview screen at 1262×668, both themes
(`scripts/audit/text_legibility_via_cdp.py`, receipt `.project-local/artifacts/LEGIBILITY_AFTER_FLOOR.json`):
33 leaf text nodes, **smallest 12px**, lowest measured ratio 5.19:1 in dark and 5.34:1 in light. Before
the floor sweep the same instrument found 12 nodes below 12px (a 9px `{components.state-chip}`, the 10px
`{typography.label-caps}` group captions, the brand caption, the first-frame strip, the zoom readout)
and 3 AA failures in light.

**2026-10-19 re-census, swept per lane with a live backend.** The same instrument now scrolls every
scrollable region in viewport-sized steps before sampling, so the population is the product rather than the
first screen: 31 lanes × both themes at the 900×600 window floor, 2,676 sampled leaf nodes (light 2,678),
minimum 12px, `aa_failures=0`, `belowFloor=0`, `no_horizontal_overflow_at_this_width` clean at 900px. The
evidence lane alone went from 42 nodes (heading and shelf only — the handle rows sat below the fold and were
never sampled) to 120, including 32 handle-row cells and 20 path strings, all at 12px. Without the scroll
pass the run reported the same green it had reported while blind to the new block, which is why the sweep,
a `coverage_was_reported` check and the two coverage checks are part of the instrument now — and why
`tests/ci/test_text_legibility_gate.py` carries planted cases for all three: a lane that stops reporting
coverage, a lane that overflows the asked width, and a scrollable lane that yields no new text must each be
convicted. What CI does **not** do is launch the browser sweep over the shipped bundle; its browser step runs
the geometry gate, so a legibility sweep is hand-produced evidence until someone authorises wiring it in.

**That census was scoped to the degraded state, and said so too broadly.** With no backend the shell
renders the offline card, so the 33 nodes never included a filled status pill, a disabled primary action
or a KPI numeral — precisely where the light theme was still failing. Run against a live v3 snapshot
(`--live-backend`, the release line's own sidecar on a dynamic loopback port) the same screen yields 61
nodes and found three more defects: `.tag` pills at 1.15:1, the disabled `新建执行` at 1.62:1 dark /
1.71:1 light, and the gradient-backdrop arithmetic in the instrument itself. After those fixes the live
census reads 61 nodes, 0 below floor, 0 AA failures, 0 disabled-label failures in **both** themes
(receipt `.project-local/artifacts/LEGIBILITY_LIVE2.json`). Ledger ERR-218 records the over-broad claim
so the next measured sentence states what it measured.

**Every view, with data (`--all-views`, 2026-10-08):** the census now clicks all 23 rail lanes and
scores each screen it produces — 1023 text nodes per theme, **0 below floor, 0 AA failures, 0
disabled-label failures, 0 thin views** in both themes
(receipt `.project-local/artifacts/LEGIBILITY_ALLVIEWS2.json`). Reaching that took four fixes the
single-view census could not see: the observer topology's node names were `fontSize="5"` inside a
100-unit viewBox (5 CSS px — they now live in `GraphLegend` at 12px, selectable, state named in words);
the segmented filter's selected tab was white on b10's primary→cyan gradient at 2.56:1 dark / 2.88:1
light; light-theme `--warning` amber used as *text* measured 4.48:1; and the instrument itself could not
parse the `oklab()` colours Chrome reports, which turned ten measurable nodes into UNKNOWN failures.

**Every view, at every surface the product can take (`--all-views --live-backend --sizes`, 2026-10-08):**
23 lanes × 3 widths (1280 / 900 / 440 — the main window's default, its `minWidth`/`minHeight` floor, and
the HUD) × 2 themes = 6 reports and **5,815 node measurements**, 0 below floor, 0 AA failures, 0
disabled-label failures, 0 unparsable colours, 0 thin views
(receipt `.project-local/artifacts/LEGIBILITY_REACHABLE_1.json`). Per-lane node counts differ across
lanes and widths (47–70 per lane; 1176 / 952 / 779 per report), and the rendered text contains `LIVE`
and not `OFFLINE` — the two facts that make this a measurement of real screens rather than of the
offline card repeated 46 times. Each report also asserts `window_is_the_width_asked`, so a claimed
width is a measured one.

**Type floor (normative).** No text a user must read below **12px**. Below 12px is permitted only for a
decorative glyph that repeats information available elsewhere, and such a node must be `aria-hidden`.
The floor is enforced twice: the rendered instrument fails any node under 12px whose role is not
declared (and the declaration list is empty — every role that claimed an exemption turned out to be
text a user reads), and `tests/workflow-assistance/test_no_sub_floor_text_in_the_observer_source.py`
fails the source for the views a single page load does not render. The pinned skin is the one place a
sub-12 declaration may still be written, and only because `l10b-shell.css` restates that selector at
12px or above — "we cannot change it" is not the same as "nobody did".

Tabular figures are required on every metric (`font-variant-numeric: tabular-nums` on
`{typography.kpi-value}`), so KPI columns do not jitter between polls.

## Layout

- Shell: fixed left rail + top bar + scrolling main. Rail width 210px at comfortable density.
- Rail rhythm: nav groups separated by `{spacing.xs}` inside a group and `{spacing.md}` between groups;
  each group carries a `{typography.label-caps}` caption.
- Main content max rhythm follows `{spacing.section}` between cards; cards use `{spacing.lg}` internal
  padding at KPI size, `{spacing.md}` elsewhere.
- **The rail is a scroll container and must be bounded.** See the reachability rule in Responsive
  Behavior — this is the single most severe gap in the current implementation.

## Elevation & Depth

- `{components.kpi-card}` and panels: `--shadow: 0 20px 80px rgba(0,0,0,.35)`; softer surfaces use
  `--shadow-soft: 0 12px 48px rgba(0,0,0,.22)`.
- Glass: blur 18px (`--blur`), brand file claims 34px — conflict recorded, `src/theme/tokens.ts` wins.
- The top bar is separated from content by a hairline only. Because a hairline alone failed the
  legibility intent (measured 0.8px at 60% alpha), a band boundary must be carried by **either** a
  visible surface change **or** ≥ `{spacing.lg}` gap **or** a labelled region. Overlapping the main
  region under the bar (measured: main top sits 128px above the bar bottom) is permitted only when the
  main region reserves matching padding — and that pairing must be asserted, not assumed.

## Shapes

`{rounded.sm}` is **12px**, not the 4px this file used to state: `src/skins/b10.css` declares `--radius-sm:12px`
and `main.tsx` imports `index.css` before the skin, so 12px is what renders (measured by reading both sheets
and the import order; `scripts/ci/verify_css_token_mirror.py` and
`src/theme/tokensMirror.contract.test.ts` now keep the records in step). Its live consumer is the overflow-menu
item (`.action-overflow-item`); Tailwind's `rounded-sm` utility is used **0** times. `{rounded.md}` 10px carries
`.panel`, `.panel2` and the overflow menu itself, plus 2 `rounded-md` usages. `{rounded.lg}` 16px and
`{rounded.xl}` 22px are declared and currently consumed by nothing — a scale step nobody uses is not a rule,
so treat them as reserved rather than as guidance. Chips are **not** small-radius: `.tag` is `999px`
(`{rounded.full}`, 14 usages), which is why "4px chips and inline code" could never have been true — no rule
gave inline code a radius at all. The pinned skin also owns `--radius` 18px for its own cards; that is a
different scale from this one and is named differently on purpose.

## Components

State coverage required for every interactive family: default, hover, **focus-visible**, active,
disabled, loading, empty, error. `{components.nav-item-active}` is expressed with both a fill change and
a `::before` edge bar plus `aria-current="page"` — colour alone is never the only signal.
`{components.brand-mark}` is the cut-out project logo used as a CSS mask with the skin gradient behind
it; the glow lives on the unmasked parent, because a mask applied after a filter clips its own glow.

## Do's and Don'ts

- **Do** take colour, radius and duration from `{colors.*}` / `{rounded.*}` / the motion scale in
  `src/theme/tokens.ts`. **Don't** write a hex, an `arbitrary Tailwind value` or a `px` radius in a
  component.
- **Do** keep `src/skins/b10.css` byte-identical (decision D-11). All new shell behaviour goes in the
  overlay with a specificity-raising selector.
- **Do** treat `?view=compact` as a density mode. **Don't** cite it as evidence of responsive support.
- **Don't** render a fabricated value. An unavailable field shows `UNKNOWN`; an offline source shows the
  degraded card. **But** the degraded card must name the view it belongs to (see SCREEN_SPEC.md).
- **Don't** let a theme crossfade pass through a sub-AA frame; colour changes on theme switch are
  instant, motion is reserved for state, not for repainting the palette.
- **Don't** put meaningful text below 12px, and never make a hairline the only separator.
- **Don't** let a box ellipsise a fact. If `text-overflow: ellipsis` eats characters, the complete
  string must still be reachable (`title`, or an ancestor's `aria-label`). `UNKNO…` is not a value and
  must never be mistaken for one — see SCREEN_SPEC's clipped-text rule for the HUD measurement.

## Responsive Behavior

Normative sizes, to be asserted by `scripts/audit/topbar_geometry_via_cdp.py`:

- **≥ 1100px**: rail 210px, action row inline, no wrapping.
- **900–1099px**: rail 210px, action row may drop secondary controls into an overflow menu; the primary
  action and the theme toggle stay visible.
- **Below 900px there is no rail state to design.** The main window is floored at `minWidth: 900` /
  `minHeight: 600` in `apps/observer/src-tauri/tauri.conf.json`, the 440×680 surface is the rail-less
  HUD, and the owner decision of 2026-10-07 deleted the phone shell. This document once carried a
  "**< 760px**: rail collapses to an icon rail or a drawer; every control ≥ 44px tall" row; see
  Known Gap 10 for what building it produced and why the row, not the implementation, was the defect.
- **Vertical reachability (every size)**: every item in `{components.nav-item}` is either visible in the
  viewport or reachable by scrolling the rail. A scroll container that cannot scroll is a defect, not a
  layout. The rail must be height-bounded (`100dvh` or grid row sizing) so its `overflow-y` is live.
  Measured at the 900×600 floor: the rail is a 345px scroll box over 1778px of content, **27 lanes**, 7
  group disclosures, last item hit-testable (`geometry2.json`, 2026-10-09; the same 27/7 at 1280 with
  `clientH 432`). The 2026-10-08 receipt above was taken at 23 lanes and is kept as the dated record of
  that head, not restated as today's count.
- **The navigation model is data, in one file.** `{components.nav-item}` grouping, which lanes are daily
  destinations, and which lane left the default rail all live in `src/lib/navigation.ts`; the rail, the
  command palette and the contract tests read it, and `navInvariantViolations()` is asserted empty. No
  test may pin a group count: the taskpack's rule is to repair a stale number, not to replace it with a
  new permanent one. A lane may leave the rail only through `OFF_DEFAULT_NAV_IDS`, and only while its
  registry entry, its deep link, its palette entry and an on-arrival reason all remain.
- **Colour themes are additive, never a replacement.** The shipped `DARK`/`LIGHT` values in
  `src/theme/tokens.ts` are what a bare address renders and are pinned by `tokensMirror` and by
  `paletteMirror.contract.test.ts`, which also fails if the pack's hex values appear in the default
  scopes. The 20261009 pack's palette is opt-in at `?palette=master` and overlays only the variables its
  source names — the channels it does not specify (secondary/info) keep the shipped value rather than
  being invented.
- **A utility that must beat the pinned skin needs a two-class rule in the last layer.** `src/main.tsx`
  loads `index.css` (Tailwind utilities) before `apps/observer/frontend/src/skins/b10.css`, so equal-specificity skin declarations
  win over utilities; `.list-item{align-items:center}` silently centred every stacked detail row while
  all text and contrast assertions stayed green. Overrides belong in `apps/observer/frontend/src/skins/l10b-shell.css` (b10 is
  pinned verbatim by D-11) and must carry a test that pins both the override and the conflict.
- Overflow收纳: when the action row cannot fit, controls collapse into a `更多` menu; they must not
  stack vertically forever.

## Reference systems

Closest analogues to a dark, dense, read-only control plane, with where their tokens actually live —
consulted rather than copied wholesale, and each with one thing not to take.

| System | Token source | Take | Don't take |
|---|---|---|---|
| Grafana | `packages/grafana-data/src/themes/createTypography.ts`, `createSpacing.ts`, `public/sass/grafana.dark.scss` | 14px base / 12px floor, even-pixel discipline for size and line-height | variable-density panels and plugin theme overrides |
| EUI (Kibana) | `packages/eui/src/global_styling/variables/`, `eui-theme-common/…/size.ts` | the 8-step spacing ramp and the `EuiSideNav` group model | light-first defaults |
| PatternFly (Keycloak admin UI) | `patternfly:src/patternfly/base/tokens/tokens-dark.scss` | a paired dark token set and the 12/14px ramp | a 16px base body |
| Portainer | `app/assets/css/theme.css`, `colors.json` | a JSON colour token file feeding a dark admin shell | Bootstrap/RDash 11–12px legacy chrome |
| Rancher Dashboard | `shell/assets/styles/`, `shell/components/nav/`, `HeaderPageActionMenu.vue` | collapsible + pinned nav groups and a page-action overflow menu | mixed Element-Plus sizing |
| Jaeger UI | `packages/jaeger-ui/src` (no token file found) | waterfall row density and the left rail | inline-styled MUI with no token layer |
| Langfuse | `web/src/styles/globals.css`, `fonts.ts` | one CSS-variable token set driving both themes — which is exactly the shape of the light-theme failures recorded below | doc-site prose typography leaking into app chrome |
| SigNoz | `frontend/src/styles/`, antd theme tokens | log/trace table density | theme values left inline instead of tokenised |

Every value in the `Token source` column is a path inside *that project's own* repository. This tree does
not contain them and must not be read as if it did, so `scripts/ci/verify_authority_index_paths.py` needs
each one declared at the sentence rather than excused repo-wide:
[no-tree-claim CROSS_PROJECT ref=packages/grafana-data/][no-tree-claim CROSS_PROJECT ref=packages/eui/][no-tree-claim CROSS_PROJECT ref=public/sass/][no-tree-claim CROSS_PROJECT ref=app/assets/css/][no-tree-claim CROSS_PROJECT ref=shell/assets/styles/][no-tree-claim CROSS_PROJECT ref=shell/components/nav/][no-tree-claim CROSS_PROJECT ref=web/src/styles/][no-tree-claim CROSS_PROJECT ref=frontend/src/styles/]

## Known Gaps

`needs-design-decision` unless marked otherwise (implementation deviation).

1. ~~**Dead rail scroll**~~ — CLOSED 2026-10-08. `.app` had no height, so the rail grew to its content
   (1707px in an 807px viewport) and `.nav { overflow-y: auto }` never engaged; 9 of 23 items were
   reachable. The shell layer now gives the column a real height and the rail scrolls and collapses:
   measured `clientH 432 / scrollH 1554`, `overflow=True`, last item hit-testable, 7 group disclosures.
   Enforced by `scripts/audit/topbar_geometry_via_cdp.py` (`nav_items_reachable`,
   `nav_groups_are_disclosures`).
2. **Theme is not persisted to web storage — by contract, not by accident.** I first recorded this as a
   gap and built the storage fallback; `apps/observer/tests/test_production_surface_static_contract.js`
   ("theme and layout state never persist to web storage") fails the build on any `localStorage` /
   `sessionStorage` use in the UI layer, so the feature was reverted rather than the test relaxed: a
   projection whose appearance depends on hidden client state cannot be reproduced from its URL, and this
   project's evidence depends on exactly that. The sanctioned mechanism already works — toggling the
   theme rewrites the address (`?theme=light`), so reloading *that* URL comes back light, measured by the
   legibility instrument (`theme_actually_applied PASS asked=light html.class='light'`) and asserted by
   `src/themeSwitch.contract.test.tsx`. Reloading the bare address returns to dark, which is the design
   language, not a loss. If the owner wants the choice to survive a bare relaunch, the place that decides
   is the desktop shell's launch URL, and that is an owner-level call, not a UI-layer storage exception.
3. ~~**Sub-AA frames during theme crossfade**~~ — CLOSED 2026-10-08. The pinned skin eases colour over
   ~200-300ms and nav text was measured passing through 1.22:1. `App.tsx` now holds `transition` and
   `animation` off on `<html>` for the two frames the swap needs (`.theme-instant`), so the palette
   changes in one frame and hover/press motion stays animated; the release is asserted on real
   `requestAnimationFrame` boundaries, not on timers.
4. ~~**Light-theme contrast failures (settled state)**~~ — CLOSED 2026-10-08. The three failures were
   `.avatar` (white glyph on light `--surface2`, 1.13:1), `.brand small` (`var(--primary)` as text,
   3.74:1) and the 9px hint chip (4.43:1). Fixed in the shell layer because b10 stays verbatim (D-11):
   the avatar glyph takes ink in light, the brand caption takes `--primary-text`, and `--color-muted`
   was aligned to the value the skin already carried. Same instrument, same viewport:
   0 AA failures in either theme, lowest ratio 5.34:1 in light.
5. ~~**Type floor violated**~~ — CLOSED 2026-10-08. 125 `text-[9px]/[10px]/[11px]` utilities across 30
   files and three shell micro roles were raised to 12px; see Typography for the two enforcement points.
6. **Closed: three token sources disagreed** — reconciled 2026-10-08 by measurement, not by decision. The UI scale is
   `src/theme/tokens.ts` + the `:root` / `html.light` blocks in `src/index.css`, because those are what the
   components and the sheets actually use; `src/assets/brand/design-tokens.json` is a **brand handoff
   artefact** — no application code imports it (measured with `git grep`: the readers are
   `apps/observer/tests/test_production_surface_static_contract.js`, which asserts its themes/views/
   constraints, and its own entry in `.project/governance/recovered-source-registry.json`; everything else is
   prose), so its 11/20/30 radii and 34px blur are not
   claims about this product and are no longer treated as a conflict. What was wrong has been corrected to the
   rendered value: `{rounded.sm}` and `tokens.ts` both said 4px while the pinned skin's `--radius-sm:12px`
   wins the cascade. Two guards keep it that way — `scripts/ci/verify_css_token_mirror.py` (sheet vs sheet) and
   `src/theme/tokensMirror.contract.test.ts` (tokens vs sheets).
7. **Closed: two parallel variable vocabularies** — closed 2026-10-08 for the part that was real, corrected for the
   part this file stated wrongly. Measured across both theme scopes: `--color-bg/-sidebar/-panel/-panel2/
   -border/-ink/-muted` and `--bg/-sidebar/-surface/-surface2/-border/-text/-muted` carry **the same value per
   theme** (84 scoped declarations, no cross-sheet collision once `--radius-sm` was fixed), and
   `--color-surface` / `--color-primary` / `--color-text` do not exist at all — so "the same word names
   different values" was never true of border/surface/primary as written here. The genuine instances were in
   the *other* direction: `tokens.ts` holding values the sheets had already moved — light `muted` #5A7184
   against #4A6172, light `warning` 180 83 9 against 154 74 5, `radius.sm` 4px against 12px — and all three
   reached the DOM, because `TopStatusBar` paints its status dot from `THEMES[theme].colors`. That drift is now
   a red test instead of a paragraph.
8. **Closed: the micro-role allowlist now expires instead of accumulating.**
   `apps/observer/tests/test_production_surface_static_contract.js` used to permit sub-12px CSS in seven
   named roles (`.winctl-zoom`, `.load-strip`, `.brand small`, `.topbar-brand-word`, `.tag`, `.badge`,
   `.kpi small`). After the floor sweep exactly **one** sub-12px declaration remains in the shipped
   sheets — `.brand small → 10px`, pinned by `b10.css` and overridden to the floor by the shell — so six
   of the seven were permissions nobody held, and the assertion printed "no offenders" while its own list
   rotted. The check now answers two questions (`microRoleFindings`): a sub-floor rule no role claims is
   an **offender**, and a role no sub-floor rule matches is **dead** — both fail. `ALLOWED` is one entry.
   Falsified on the real file rather than in a fixture: adding a `.ghost-role` permission turns the run red
   naming it, and the file is restored byte-identically
   (`.project-local/runs/falsify_stale_permission.py`). The same pass also strips comments before reading
   declarations, because these sheets quote the numbers they fix and a comment is not a rule.
9. **The rendered proof does not run in CI** — both browser instruments need a Chromium binary, which
   the Actions runner does not have, so they are run locally against `dist` and their receipts are cited
   by hand. CI enforces the source-level guards. `verify_design_contract.py` still parses token files and
   touches no rendered value, so its `DESIGN_CONTRACT_PASS` is not evidence of UI compliance.
10. **Closed by deleting the requirement, not by building it.** This gap read "the `< 760px` band is
    declared and not built", and the fix looked like an icon rail. It was built, and every number passed
    at a pinned 430px viewport — 60px rail, 23 lane targets of 45×44, `scrollWidth == 430`, no lane
    unnamed — and then the screenshot showed what the numbers had no field for: 23 lanes as 23 identical
    dots, because `.nav-dot` is a status marker rather than an icon and hiding `.truncate` had removed
    the only distinguishing content. A drawer was built next, which is when the contradiction surfaced:
    `tauri.conf.json` floors the main window at 900×600, the 440×680 surface renders no rail, and
    `tests/ci/test_desktop_only_shell.py` pins both that floor and the absence of a mobile navigation
    surface (owner decision 2026-10-07, 优先跑通全量执行桌面端电脑端 UI，先删除手机端其他端). Both
    attempts were discarded before commit; the diff is archived at
    `.project-local/artifacts/NARROW_BAND_ATTEMPT_20261008.diff`. **The standard row was the defect**, so
    SCREEN_SPEC now states window surfaces instead of a phone band, the target rule reads 24×24 (WCAG
    2.5.8) rather than the 44px figure that came with the deleted row, and the gate measures the real
    floor. ERR-219 records it. What remained genuinely open was a design question the deleted row was
    papering over: the rail had no per-lane icon set, so it could not be made narrow on purpose — only by
    removing information.
    **Closed on the picture half 2026-10-29, and the diagnosis changed.** `src/lib/viewRegistry.ts` had
    declared one Lucide glyph per lane all along (32 rows, 30 distinct glyphs, the two repeats being the
    registry's own pairing convention: `executions`/`execution-detail` share `PlayCircle`, `privacy`/`trust`
    share `ShieldCheck`); the field simply had **no consumer**, so the rail painted 31 identical `.nav-dot`
    circles and every source-level grep read as delivered. `src/components/layout/Sidebar.tsx` now renders
    each lane's declared glyph in place of the dot. Measured on the built bundle at 1280×820: 31/31 rows
    paint a glyph, label truncation 0 before and 0 after (`truncated=0` in
    `.project-local/runs/live-probe-20261029/rail-before-main.json` and `rail-after-icons.json`), and the
    geometry, legibility and pressed-state gates are unchanged — the glyph replaces a 10px decoration with a
    15px one instead of adding to it, which is the difference between this attempt and the discarded one.
    `src/laneIcons.contract.test.tsx` binds the painted row to the registry row and fails if a lane loses
    its name. **What is still open is the width decision, not the icon set**: the rail may now be narrowed
    on purpose, and whether to do that is an owner call about the professional shell.
11. **One role, two literals, kept equal by a guard rather than by one definition.**
    `--color-bg / -sidebar / -panel / -panel2 / -border / -ink / -muted` in `src/index.css` repeat, character
    for character, what `src/skins/b10.css` (`:root`) and `src/skins/l10b-shell.css` (`html.light`) declare for
    `--bg / -sidebar / --surface / --surface2 / --border / --text / --muted` — measured 2026-10-08 across the
    84 theme-scoped declarations of the three sheets. `scripts/ci/verify_css_token_mirror.py` now makes a
    divergence red, which the pair never had, but the duplication remains: an edit that changes both files the
    same way still passes. The owed change is to derive the Tailwind-facing set (`--color-border:
    var(--border)`), so one literal per role exists — custom-property references resolve at use time, so the
    import order does not matter. Deliberately not done in this round: it rewrites seven declarations in the
    layer every contrast number in this file was measured against.
12. **The status pills bypass the accent channels.** `.tag.ok`, `.tag.warn` and `.tag.bad` fill with literal
    gradients (`#27c86a→#11a74d`, `#f2b541→#c98c00`, `#f86b6b→#cb3e3e`) while `.tag.info` uses
    `var(--primary)`/`var(--secondary)` — read from `skins/b10.css:258-261`. A pill's green is therefore
    neither `--success` in dark (`#22C55E`) nor in light (`#15803D`), in either theme, so a pill and a label
    that name the same state are different colours; the pinned skin (D-11) cannot be edited to fix it, so the
    override belongs in `src/skins/l10b-shell.css`.
    **The measurement this gap asked for now exists, and it found a hole in the gate rather than in the
    pills.** Every legibility sweep before 2026-10-10 ran against the static preview, where all 28 lanes
    collapse to the offline panel: the receipt held 980 nodes, `every_text_node_meets_AA` passed, and
    **zero `.tag` nodes existed anywhere** — so the AA claim never covered a single pill, in either theme,
    while reading as full coverage. Re-running with `--live-backend`
    (`.project-local/artifacts/wui-20261009/legibility-live-views.json`, bundle `3929e3f84a97ee2f`) renders
    34 pill nodes per theme — `tag.bg-panel2.text-muted` ×18, `tag.info` ×8, `tag.ok` ×4, `tag.warn` ×4 —
    inside a sweep of 0 AA failures and 0 sub-floor nodes, and `every_lane_reached_its_own_content` PASS with
    an empty offline-panel list. `tag.bad` never appears in the live projection, so its literal gradient is
    still unmeasured; the colour-mismatch design question above is likewise open, and it is a decision, not a
    missing number. The instrument now records `backend` per row and enforces the two coverage checks only in
    live mode, printing `NOT_ENFORCED` in static mode, so a chrome-only sweep cannot be quoted as lane
    coverage again (ERR-237).
13. **Closed 2026-10-13: the fixed HUD now fits the acceptance screen at 200% display scaling.** This gap
    read: `tauri.conf.json` declares the panel as 440×780 with `resizable: false`, so at 200% the physical
    demand was 880×1560 against a 2560×1392 work area (the −48px taskbar is an assumption the receipt
    prints rather than hides), and it asked for an owner decision — shrink the declared HUD, make it
    resizable with a floor, or accept the loss. The declaration is now 440×680, so the derived demand is
    880×1360 with 32px spare. The 780 figure was the declaration at the time of the finding; the
    2026-10-13 correction and the gate pass are recorded in
    `taskpacks/current/OPEN-TASK-REGISTER.md`, and this line keeps that history rather than rewriting the
    measurement. Still unverified for the reason in row 14: whether tao clamps a non-resizable window to
    the work area needs a release binary to read back.
14. **No DPI-awareness readback exists for this product.** `src-tauri/build.rs` is a bare
    `tauri_build::build()` and the repo carries no Windows manifest of its own, so Per-Monitor v2 is framework
    behaviour asserted by dependency rather than something this repository states. The native half of WUI-14
    is therefore unmeasured, and the reason is recorded rather than glossed:
    `.project-local/artifacts/wui-20261009/keyboard-focus-fresh.json` carries the artifact gate's
    `STALE_OR_MISSING_BINARY` with `src-tauri/target/release/app.exe` `exists=false`. What IS measured is the
    browser half — four scaling levels, 21 geometry checks each, with `window.devicePixelRatio` asserted
    against the asked scale so a sweep of four identical rasters cannot pass as four DPIs.
15. **Reading position is proven at the mechanism level, not in pixels.**
    `src/desktopInteractionPreservation.contract.test.tsx` pushes a new snapshot through the live hook's own
    state setter and asserts that the lane root and the rail scroll container survive as the SAME nodes, that
    focus and `selectionStart/End` stay in the field being typed in, and that a text selection stays attached —
    with a negative control that switches lane and proves `isConnected` can report false. jsdom performs no
    layout, so no `scrollTop` number is asserted; the production tree contains no `scrollTo(`, `scrollTop =` or
    `removeAllRanges` anywhere under `src/`, which makes node survival the complete mechanism rather than a
    proxy for it. The pixel half is now measured: `scripts/audit/sse_revision_via_cdp.py` serves real
    `snapshot_api.build_snapshot` payloads to Chromium and lets the PAGE release the next revision (a fixed
    clock was falsified twice — pushed too fast and rev 9 was already on screen before the reading, pushed too
    slow and nothing changed at all), then measures `rail scrollTop 240 → 240` with `railScrollable=true`, the
    selection still attached and focus still in the INPUT across an observed `rev7 → rev9` advance, while a
    deliberately trailing LOWER revision is served and never reaches the screen.
    `.project-local/artifacts/wui-20261009/sse-revision.json` holds the pass; `--revisions 7,9,10` produced the
    matching red, so the check can report a wrong answer.
    What stays open is the reconnect half: that stream never dropped, the receipt records
    `reconnectCursor=[]`, and so `Last-Event-ID` resumption is covered only by
    `src/lib/transportTruthContract.test.ts:155`, not by a live disconnect readback.
