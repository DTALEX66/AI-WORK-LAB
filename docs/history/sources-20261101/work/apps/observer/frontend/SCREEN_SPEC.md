# SCREEN_SPEC — WORK-LAB Observer main surface

Companion to `DESIGN.md`. Where DESIGN.md owns tokens and component contracts, this file owns
**page-level layout, state behaviour and reachability**, and every clause here is written as something
`scripts/audit/topbar_geometry_via_cdp.py` can assert on a rendered window. Numbers marked *measured*
come from `.project-local/artifacts/design-qa-20261008/` (screenshots at six widths,
`live-state.json`, `contrast-corrected.json`).

Target surface: `apps/observer/frontend`, route `/?view=<evidence|work|execution|taskpacks|delivery|
execution-detail|agents|projects|workflows|…>`, desktop WebView (Chromium) and desktop browser.

## Regions

```
┌──────────┬───────────────────────────────────────────────┐
│          │  A  top bar: brand-mark + search + status      │
│  R rail  ├───────────────────────────────────────────────┤
│          │  B  action row: 通知 / 工作区 / 密度 / 主题 …   │
│          ├───────────────────────────────────────────────┤
│          │  C  main: view content                         │
└──────────┴───────────────────────────────────────────────┘
```

- **R rail** — fixed 210px (`{spacing}` rhythm per DESIGN.md Layout). Contains brand block, grouped nav,
  footer. It is the only element permitted to be full-height.
- **A top bar** — one row, height ≤ 64px at comfortable density. *Measured 129px tall including region B;
  the two rows are one visual band today and must either be declared one band or be separated.*
- **B action row** — grouped controls. Belongs to the top bar band; must be visually attached to A
  (shared surface or an explicit divider), not floating over C.
- **C main** — scrolls. Never scrolls the document instead of itself.

## Boundary rules (normative)

1. Every band boundary must be carried by **at least two** of: a surface/colour step, a ≥ `{spacing.lg}`
   gap, a visible divider ≥ 1px at ≥ 3:1 against both sides, or a labelled region.
   *Violation today (measured): the top bar separates from content with a 0.8px hairline at 60% alpha
   (1.23:1), no shadow, and `main` has no top border; region B floats over region C.*
2. Region C must not start underneath region A. If overlap is used for a glass effect, the reserved
   padding must be ≥ A's height and the assertion must check both numbers.
   *Violation today (measured): `main.top` is 128px above `topbar.bottom` at every width, in both themes.*
   This is not only a visual grouping problem: WCAG 2.2 **2.4.11 Focus Not Obscured (Minimum)** forbids
   author content entirely hiding the focused component, so an overlapping bar must be proven not to cover
   a focused control — asserted by focusing the first and last focusable element of region C and checking
   their rects against region A's, not by eyeballing a screenshot.
3. The rail's right edge may use `{colors.hairline}`, but the rail must also be a distinct surface
   (`{colors.surface-sidebar}` ≠ `{colors.canvas}`) so the boundary survives a hairline being invisible.
4. Every interactive target is ≥ **24×24 CSS px** (WCAG 2.5.8 AA, including its Spacing exception) and any
   repeated primary control ≥ 32px on its shortest side; see DESIGN.md `External standards` for the
   conflicting vendor numbers and why 24 was chosen over 40/44/48.

## Navigation reachability (normative)

1. **Every nav item is reachable.** For each `.nav button`, either its rect is inside the viewport, or
   its scroll ancestor reports `scrollHeight > clientHeight` and scrolling to it brings it into view.
   A container with `overflow-y: auto` whose `clientHeight == scrollHeight` is a defect, not a scroll
   container.
   *Violation today (measured at 1386×807): `.sidebar` height 1707px with `overflow-y: visible`;
   `.nav` `clientHeight == scrollHeight == 1496`; document `scrollHeight == clientHeight == 807`;
   23 nav items, 9 reachable, the rest permanently clipped.*
2. The rail is height-bounded to the viewport (`100dvh` or grid row sizing) so rule 1 can be satisfied
   at any window height, including the smallest supported 600px. **Fixed by `36f9a297`** — measured after
   the change: `.nav` clientHeight 1505 → 595 against scrollHeight 1505, `scrollTop` reaches 910, the last
   item (设置) is visible with `elementFromPoint` landing inside its own button, and clicking it moves
   `.active`.
3. Scrolling is necessary but not sufficient. Per the ARIA APG **Disclosure Navigation** pattern (and
   Rancher's `shell/components/nav/Group.vue`), each group is a disclosure button with `aria-expanded`,
   Space/Enter toggling and Escape returning focus, so a long rail can be shortened as well as scrolled.
   ~~Group collapse is **not implemented** — recorded as an open deviation, not as satisfied by the fix.~~
   **追正（2026-10-09，实测）**：这句话与本文件自己的门禁覆盖段（`nav_groups_are_disclosures`）互相矛盾，
   而且实现早在代码里。`src/components/layout/Sidebar.tsx` 的每个组标题是 `type="button"` 的披露按钮，带
   `aria-expanded` 与 `aria-controls`；收起时该组的项**从文档中移除**（不是靠样式隐藏，所以键盘与读屏都拿不到）；
   Escape 从当前视图所在组收起并把焦点交回该组按钮，焦点已在按钮上时不重复动作；折叠状态只存在组件里，
   既不写 URL 也不写 web storage。本轮补上 `src/navDisclosure.contract.test.tsx`（7 例）并逐属性反证：
   删掉 `aria-controls`、让收起后的项仍留在文档里、去掉 Escape 的焦点回交、把折叠状态写进 localStorage——
   4/4 判红，组件按字节还原。这条"未实现"能活到今天，正是因为没有任何测试问过它。
   [no-tree-claim CROSS_PROJECT ref=shell/components/nav/]
4. Group captions (`{typography.label-caps}`) are decorative duplicates of the item labels below them
   and must not be the only way to find a group by keyboard.
5. Active item is marked by fill **plus** edge bar **plus** `aria-current="page"` — colour alone is
   insufficient, and the active state must be distinguishable in the light theme too.

## Action row and overflow (normative)

1. The action row never stacks vertically. When the band cannot fit all controls, controls beyond the
   primary action and the theme toggle collapse into a `更多` menu button. This is the named pattern in
   Fluent **CommandBar** (a "see more" button; primary commands move to the secondary area when space is
   limited) and Carbon **OverflowMenu** ("additional options… but there is a space constraint") — a
   wrapping column satisfies neither.
   *Was a violation, fixed 2026-10-08: `.top-actions { flex-wrap: wrap }` with 4 children and no overflow
   control stacked the row into a column at narrow widths. Measured now, `action_row_does_not_stack`
   reports `children=4 rows=1` at the 1280 default and `children=4 rows=1` at the 900×600 floor, with the
   fold trigger present when the band needs it.*
2. The overflow menu is a real menu: `aria-expanded`, keyboard operable, focus returned to the trigger on
   close, and it must not be clipped by region A's bounds.
3. Minimum click target **24×24px** (WCAG 2.5.8 Target Size (Minimum)) for every control in A and B.
   *This row previously demanded 44×44px. That figure belonged to the phone row deleted under "Window
   surfaces": on a
   desktop product with no touch surface, 44px is not a standard anyone wrote down, and the shipped
   window controls measure 32×32. The enforced number is now the one the gate measures
   (`top_bar_targets_meet_the_floor`, 16 controls harvested, 0 offenders). If the product ever targets
   touch input, 44×44 returns as a new decision, not a reverted edit.*

## Window surfaces (normative)

The product has exactly two windows, and both sizes are declared in `apps/observer/src-tauri/tauri.conf.json`:

| Surface | Size | Rail | Action row | Search | Required assertions |
|---|---|---|---|---|---|
| `main`, default | 1280×820, resizable | 214.5px measured at a 1262px inner width (`clamp(210px, 17vw, 280px)`; 2026-10-09 `geometry2.json`) | inline, overflow menu when the band cannot hold it | full width | no horizontal overflow; no wrap; every lane reachable |
| `main`, at its floor | ≥ 900×600 (`minWidth`/`minHeight`) | rail is its own scroll box, 345px over 1778px of content, 27 lanes, last item hit-testable | overflow menu allowed | full width | the same set, re-measured at 900×600 |
| `panel` (HUD) | 440×680, `resizable: false` | none by design | inline | icon only (label + Ctrl K chip remain in the DOM, named by aria-label/title) | no rail; no horizontal overflow; command row stays on one line |

**There is no narrow band.** Owner decision 2026-10-07 (优先跑通全量执行桌面端电脑端 UI，先删除手机端其他端)
deleted the phone shell, and `tests/ci/test_desktop_only_shell.py` pins both the absence of a mobile
navigation surface in source and `main.minWidth >= 900`. A rail at 760px is therefore not a state this
product can enter, and no CSS breakpoint may reintroduce one.

*How the row three claim was tested, 2026-10-08: an icon rail was actually built for it and measured at
a pinned 430px viewport — 60px rail, 23 lane targets of 45×44, `scrollWidth == 430`, every lane still
`aria-label`led, all numbers green. The screenshot then showed the failure the numbers could not see:
23 lanes rendered as 23 identical dots, because `.nav-dot` is a status marker and not an icon, and
hiding `.truncate` removed the only thing that distinguished them. A drawer was then built, which is
the second half of the deleted decision. Both attempts are archived at
`.project-local/artifacts/NARROW_BAND_ATTEMPT_20261008.diff`; neither shipped. The standard was the
defect.*

`?view=compact` is a user density mode, not a breakpoint, and must never be cited as responsive evidence.

Legibility is swept across the surfaces that exist rather than sampled at one width. Measured
2026-10-08 against a **live backend** (`--all-views --live-backend --sizes 1280,900,440`): 23 lanes ×
3 widths × 2 themes = 6 reports, **5,815 node measurements**, 0 below the floor, 0 AA failures, 0
unreadable disabled labels, 0 empty views, 0 unparsable colours, and every report carries
`window_is_the_width_asked` so the width claimed is the width measured (receipt
`.project-local/artifacts/LEGIBILITY_REACHABLE_1.json`; the earlier 4-width sweep including the
unreachable 700/430 columns is kept as `LEGIBILITY_SIZES_D.json` and superseded, not deleted).
Per-lane node counts differ (1176 / 952 / 779 at the three widths, 47–70 nodes per lane) and the page
text contains `LIVE` and not `OFFLINE`, which is what distinguishes this from re-measuring the offline
card 46 times — the mistake ERR-218 was filed for. Reaching a clean result required a `secondary-ink`
text role (DESIGN.md's text-accent rule) after `text-secondary` measured 3.49:1 in the task-packs
table, and the width assertion after the harness once reported twelve confident measurements of
one-pixel-wide windows.

## Degraded and offline states (normative)

1. When the backend snapshot is unreachable, the surface must show the degraded card. Showing fabricated
   or cached-as-live data is forbidden (`UNKNOWN ≠ 0`, `STALE ≠ LIVE`).
2. **The degraded card must identify the view it belongs to.** Ten views currently render a byte-identical
   card, so a successful navigation is indistinguishable from a dead click — the owner's report of
   "左侧导航没反应" came from exactly this, not from a broken handler (verified: `active`/`aria-current`
   move, and the card's reason line changes from `事件流中断 — 已停止 LIVE 宣称…` to
   `快照获取失败 (数据源离线或端点不可达) — 保持 UNKNOWN，不伪造数据`).
   Required: view title, the specific resource that is unavailable, and the last known freshness or
   `UNKNOWN`.
3. Retry affordance must be visible and must state what retrying does in a read-only projection
   (re-read only; no side effects).
4. A reconnect loop must not cause a visible flash: no region may repaint its background before its text
   colours, and theme/palette changes are excluded from colour transitions.
   *Fixed 2026-10-08: `.theme-instant` holds colour transitions off for the two frames a theme swap
   needs, so the switch lands in one frame. It previously eased through 1.22:1 for ~300ms.*

## States required per region

State lists here follow the repo's own truth rule — `docs/history/archive/root-ui-records-20261019/UI_DECISIONS.md`: "UNKNOWN ≠ 0，不伪造 KPI" — so a
lane that has not received a value renders `UNKNOWN`, and a skeleton would be a fabricated state. No
region below "requires" one.

- Rail item: default, hover, focus-visible, active/selected, disabled, collapsed-group and expanded
  (the disclosure carries `aria-expanded`).
- Action button: default, hover, focus-visible, pressed, disabled; folded into the overflow menu when
  the band cannot hold it.
- Search: empty, focused (visible ring, not colour-only), typing, no-result, cleared.
- Main card: populated, empty-with-reason, degraded/offline distinguishable per view, error with reason
  code. Before the first snapshot the lane keeps rendering its `UNKNOWN` values and the first-frame strip
  alone answers "still fetching?".

## Text and contrast (normative, restated from DESIGN.md)

- No meaningful text below 12px. *Re-measured 2026-10-19 with a per-lane scroll sweep: 31 lanes in both
  themes at the 900×600 window floor, 2,676 sampled leaf nodes (dark; light 2,678), minimum 12px,
  `aa_failures=0`, `belowFloor=0`, and no horizontal overflow (`scrollWidth=900 = innerWidth`). Enforcement
  is split, and stated as such: the probe's arithmetic and its verdict (colour parsing, alpha compositing,
  thresholds, the per-lane coverage checks) are gated in CI by `tests/ci/test_text_legibility_gate.py`
  (52 cases) and the source-level rule by `tests/workflow-assistance/test_no_sub_floor_text_in_the_observer_source.py`;
  the browser sweep of the shipped bundle is not a CI step — the CI browser job runs
  `scripts/audit/topbar_geometry_via_cdp.py`, so a fresh `LEGIBILITY_GATE_PASS` from
  `scripts/audit/text_legibility_via_cdp.py` is evidence produced by hand, not a gate the pipeline asserts.
  The earlier figure "33 leaf nodes at 1262×668" was a single-view census, which
  this instrument's own ERR-218 lesson says cannot stand for the product.*
- **A box may not ellipsise a fact.** Any painted element that clips its own text with
  `text-overflow: ellipsis` must carry the whole string somewhere a reader can reach (`title`, or an
  ancestor's `aria-label`); otherwise it is a violation of the assertion
  `no_text_is_clipped_without_a_fallback`. *Found by looking at the 440px HUD on 2026-10-08: all four
  KPI cards rendered `UNKNO…`. The component asked for 22px, b10's unlayered `.kpi strong` gave it
  35px, and 35px "UNKNOWN" measures 193px against the 184px a two-up card gets in that window — 9px
  lost per card. A truncated UNKNOWN is the worst possible truncation in this product: it reads as the
  prefix of a value, which is exactly the guess the token exists to refuse. Fixed in the shell with
  `.compact-hud .kpi strong { font-size: 22px }` (121px, 63px of headroom). The HUD's search label
  still loses 11px and is allowed to, because the field carries `aria-label="搜索或命令"`.*
- Text contrast ≥ 4.5:1 below 18.66px (≥ 3:1 for large/bold). Measured in the settled state: 0 failures
  in either theme; lowest 5.19:1 dark, 5.34:1 light. The three light-theme failures this spec recorded
  (avatar glyph 1.13:1, brand sub-label 3.74:1, hint chip 4.43:1) are fixed and named in DESIGN.md
  Known Gaps 4.
- Theme and density state travels in the URL, never in web storage. `?theme=`/`?layout=` are rewritten
  on every change, so reloading the address the app is showing restores what the user chose; a bare
  address restores the design default (dark). *Measured 2026-10-08: after a click the address carries
  `theme=light`, `localStorage` holds no key, and `?theme=light` loads with `html.class='light'`.*
- A theme switch must not pass through an unreadable palette. *Fixed 2026-10-08 with `.theme-instant`;
  it previously eased through 1.22:1 for ~300ms.*

## Gate coverage owed

All six assertion families this section listed are now enforced. `topbar_geometry_via_cdp.py` runs three
passes over the shipped bundle — 20 checks at the 1280×820 default, 14 at the 440×680 HUD, 21 at the
900×600 window floor — and `text_legibility_via_cdp.py` asserts 6 per theme plus three for the switch
itself. Delivered: rail reachability (`nav_items_reachable`, `nav_groups_are_disclosures` — and since
2026-10-09 the disclosure *behaviour* rather than only its markup, 7 cases in
`src/navDisclosure.contract.test.tsx`, each property falsified by removing it),
action folding (`action_row_does_not_stack`), the type floor and AA contrast in both themes, the
degraded-state-per-view rule (the offline surface names the active view, asserted for all 22 registered
lanes plus distinctness of the 22 headings by `src/offlineViewIdentity.contract.test.tsx`), and region
boundaries:

- `content_clears_topbar` — measured `topbarBottom=129 / contentTop=129` in the full shell and
  `111 / 111` in the panel: the content region starts exactly at the bar's bottom edge, so nothing is
  drawn under it. The check is deliberately **not** "`main` starts below the bar": `.main` is a
  full-height 0→668 column by design with the bar floating over its first rows, and asking that
  question would have failed the intended layout (measured, then re-framed).
- `topbar_edge_is_painted` — the boundary must be carried by something: `1px solid` today, a shadow as
  an accepted alternative, and neither is optional.
- `focused_control_is_not_obscured` + `every_visible_probe_takes_focus` — WCAG 2.4.11 in the only form a
  rect check can express: focus the control, hit-test its own centre. Five controls are probed in the
  full shell (search ARIA button, action row, window control, rail item, group disclosure). Probing
  `.search input` found nothing — the field is `role="button" tabIndex=0`, not an input — and an empty
  probe list would have reported "nothing obscured". A control below the rail's fold is now excluded by
  `inViewport`, because off-screen is not obscured; a probe that never reported the field is still
  treated as in-viewport, so an older harvest shape cannot disarm the check by absence.
- Per lane, in both main-window passes: `every_lane_is_named` (text or `aria-label`/`title`),
  `lane_labels_are_distinguishable` (no blank, no two lanes spelling the same thing — the failure mode
  the icon-rail attempt reached: 23 identical dots), and `lane_targets_meet_the_floor`. Lanes measuring
  0×0 are excluded as unrendered, and the count of lanes actually measured is printed next to the count
  that exist, so the exclusion cannot hide a rail that painted nothing.
- `top_bar_targets_meet_the_floor` measures regions A and B against the 24px rule above: 16 controls
  harvested, 0 offenders at the floor. An empty harvest fails rather than passing vacuously.
- `no_mobile_navigation_surface_is_painted` sweeps `.mobile-nav`, `.topbar-mobile`, `.rail-toggle`,
  `.rail-scrim`, `.rail-close` and `[data-mobile-nav]` in all three windows. It exists because the
  implementation this round first shipped and then discarded was exactly that surface; the positive
  control (same expression, selector swapped for `.topbar-brand`) reports `["topbar-brand"]`, so `[]` on
  the real page means absent rather than unchecked
  (`.project-local/runs/falsify_mobile_sweep.py`).
- The floor the gate measures is bound to the window config, not restated:
  `test_the_floor_the_gate_measures_is_the_floor_the_window_config_declares` reads
  `tauri.conf.json` and asserts `VIEWPORT["floor"] == (main.minWidth, main.minHeight)`. Lower the floor
  in the config and this test goes red, which is the point — the band question has to be re-opened on
  purpose.

Theme "persistence" is not an open gap: web storage is forbidden in the UI layer by
`test_production_surface_static_contract.js`, and `?theme=` in the address is the sanctioned mechanism
(DESIGN.md Known Gap 2).

What remains unproven is not a missing assertion but a missing environment: neither browser instrument
runs in CI (no Chromium on the runner), so these numbers are local receipts cited by hand while the
source-level guards are what CI enforces. Each new assertion ships with a planted-failure control
proving it can go red; an assertion that cannot fail guards nothing (ERR-143's rule).
