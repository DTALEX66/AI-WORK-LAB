---
name: worklab-ui-replication
description: Use when landing WORK-LAB UI套件 into observer frontend 1:1.
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [work-lab, observer, frontend, ui, design-system, replication]
related_skills: [web-dashboard-delivery, frontend-testing, github-pr-workflow]
---

# WORK-LAB UI 套件 → Observer Frontend 1:1 Replication

## When to Use
- The user hands a WORK-LAB UI/VI/Design-System execution prompt pointing at the `D:\All projects\UI套件` batch suite (B01–B10).
- The goal is to reproduce the reference visual system into the existing `apps/observer/frontend`, not to make a new dashboard.
- The task mentions 权威等级 / 1:1 复刻 / UI 落地 / WORK-LAB 品牌锁死.

Recurring task class: the user issues a master execution prompt (model / 执行模式 / 权威等级 / 页面清单) and the reference suite at `D:\All projects\UI套件` is landed 1:1 into the real frontend. Never a new demo/prototype directory; never "参考后自行发挥" — reference batches = visual & interaction fact source, the repo = implementation vehicle.

## Standing rules (from the prompt + user memory, non-negotiable)

- **Authority order** (conflicts resolve to the higher batch): B10 最终版可部署UI > B09 交互Demo > B08 React/TS原型 > B07 工程包 > B06 交互状态 > B05 高保真页面 > B04 组件/tokens > B03 页面母版 > B02 > B01. Lower batches only supplement detail; they can never override Layout/Color/Logo/Nav/Card/Motion a higher batch fixed. Log per-item adjudications in `UI_DECISIONS.md`.
- **Brand lock**: deep-navy #050D16 + Electric Blue #2A91FF + Cyan #20CDE1 (always re-read the batch `index.html` :root and commit what it actually says — batches drift and earlier transcriptions are unreliable. Verified B10 source :root: bg #050D16 · sidebar #07111C · surface #081420 · surface2 #0C1B2A · border #17435D · primary #2A91FF · secondary #20CDE1 · text #EEF6FC · muted #8EABBC · success #22C55E · warning #F59E0B · error #EF4444 · radius 18px). No orange/gold/cream/magazine, no AAOS (ArcheAxis) or DESIGN-LAB skins mixed in, no logo redesign. The 'no overdone glass / excessive gradients' ban is on EXCESS: B10's own skin uses gradient + backdrop-blur on nearly every panel/button/tag surface — replicate B10's usage 1:1, neither add to it nor strip it.
- **Truth discipline**: Observer is strictly read-only — no execute/approve/retry/rollback/state-write buttons; UNKNOWN stays UNKNOWN (no 0, no fake LIVE, no phantom KPIs). 视觉验收前不自动 commit (standing user rule).
- **Reports are tracked at repo root**: `UI_REFERENCE_MANIFEST.md`, `UI_IMPLEMENTATION_REPORT.md`, `ASSET_REPLACEMENT_MANIFEST.md`, `VISUAL_QA_REPORT.md` (plus `UI_DECISIONS.md` for adjudications). `.hermes/` is runtime data only.

## Procedure (P0 → P12, in order; do not stop at analysis)

1. **Baseline**: `git status`; branch from latest main (short-lived `p1/ui-*` branch); check open-PR merge ordering. Frontend lives in `apps/observer/frontend` (React 18 + Vite + Tailwind + TS + vitest; **no router dependency** — views are `viewRegistry.ts` lanes dispatched in `App.tsx` via URL param `?view=`; keep the lane mechanism).
2. **Expand** only the WORK-LAB zips (`WORK-LAB_*.zip`, `work-lab_*.zip`) into `.project-local/runs/ui-suite/<archive>/`; record SHA256 + entry count in an extraction report JSON. Three-project 全量包 zips are mere repacks, not authority sources. Reference zips/PNGs are NEVER committed; audit copies stay project-local. When the suite is already expanded, locate the batch source with `find .project-local/runs/ui-suite -name 'index.html'` + `wc -c` (B10 ≈ 43.7KB / 48.6K chars) — never hand-type the archive dir name: expanded dir names come from zip entry names and mix simplified/traditional variants (最终版 vs 最終版), so a guessed path 404s.
3. **Manifest**: write `UI_REFERENCE_MANIFEST.md` (batch → file → type/page/component → final-authority-or-not → target code location). It is the shared fact source for every agent in the wave — agents must not decide visuals independently.
4. **Shared ground layer, mainline first**: extend `src/theme/tokens.ts` + `src/index.css` (CSS vars + B10 keyframes + the existing `prefers-reduced-motion` block) **in the same commit** — `src/theme/tokens.test.ts` asserts the trio. Only after the ground layer is green fan out delegate_task agents per page group (independent file sets); mainline owns commits/pushes/merges (user preference: parallel sub-agents, concurrent during CI waits).
5. **Pages** per the B07 route matrix (12 routes: overview / workflows / editor / task-packs / observer / policies / integrations / memory / audit / approvals / settings / executions). Reclass `Sidebar.tsx` NAV_GROUPS to the B07 IA. Editor save/publish/run and approval approve/deny buttons render **disabled with a tooltip** until the real workflow schema / approval contract is wired — B10 button chrome is visual reference only.
6. **Verify & QA**: in `apps/observer/frontend`: `npx tsc -p tsconfig.json --noEmit`, `npx vitest run`, `npm run build` (this repo has no `typecheck` script). Visual QA against B10/B05 with priority 结构 > 比例 > 布局 > 颜色 > 组件 > 字体 > 细节 > 光效 > 动效; fix visible drift directly, then screenshot-readback in a real browser before claiming completion. If no GUI screenshot channel is available (preview pane unresponsive + browser-use CLI not installed), record the 光效/动效 pixel layer as UNVERIFIED in the QA report and stop — never escalate to 'verified'.
7. **Merge discipline (ERR-089)**: exact-SHA CI = the PR-end `work-lab-gate` run terminal-success on all jobs (observer gate is long, ~15min — poll every 2-5 min, do not assume it is stuck before checking logs) AND the main-end `work-lab-gate` run on the merge commit. Squash-merge + delete branch only after both are green; write closeout evidence to `.project-local/runs/ui-suite/` (gitignored, does not re-trigger CI).

## Full 1:1 mode (user demands 完全复刻, not convergence)

Convergence mode (the default above) ports B10 structure/tokens onto existing components. When the user demands a FULL 1:1 replica, the procedure changes:

1. **Lock the test contract BEFORE reskinning the shell.** Grep every `*.test.tsx`/`*.test.ts` under `apps/observer/frontend/src` for `getByText|getByRole|queryBy` and enumerate the anchored strings + aria-labels; every anchor must survive the reskin (or be updated in the SAME PR — never leave the gate red). Current-main standing anchors: App smoke ('搜索或命令…', 'Ctrl K', aside aria-label '侧边导航', lane button '审计追踪' → '无审计记录' empty-state anchor, 'LIVE' ≥1); viewRegistry invariant (NAV_GROUPS = 7 groups, reachable lanes partitioned exactly once); per-lane views (page titles + honest empty-state titles).
2. **Port B10's skin as a separate file.** Extract the batch `index.html` `<style>` block verbatim into `src/skins/b10.css` and import it AFTER `src/index.css` in `main.tsx` so B10 classes win over the old `wl-*`/tailwind surfaces. A separate file also keeps the `tokens.test.ts` asserted trio in index.css intact. Then reskin the shell (App/Sidebar/TopStatusBar/CommandPalette) and all 12 pages with B10 class names (`.app` 280px grid · `.ambient` · `.grid-bg` · `.sidebar/.brand/.nav/.nav-dot` · `.topbar/.search/.ghost-btn` · `.panel/.kpi/.table/.tag/.list-item/.metric-row/.graph-stage/.canvas/.node/.flow-svg`), B10 structure carrying REAL v3 snapshot data with honest UNKNOWN.
3. **Verify big ports on disk.** After writing the ~500-line skin file, probe with `wc -c`/`wc -l` + grep for the LAST keyframe/selector — large tool payloads can be elided by context compaction, and a truncated CSS builds green while silently losing half the skin.
4. Standard gates still apply (tsc + vitest + build, screenshot QA when a channel exists, exact-SHA CI, step-7 merge discipline) — full-1:1 mode skips nothing.

## Session rollover (user asks for a handoff instead of finishing)

When the user switches from "finish or don't reply" to "close this round + handoff prompt + new session" (完成本轮 / 交接 / 重开新会话), stop pushing the unfinished replica and do a clean rollover:

1. **Verify the baseline AT the handoff point**: tsc + vitest + `npm run build` all green on the working branch; commit the finished slices (skin layer, handoff doc) so the next session starts from a verified state, not a dirty tree.
2. **Push the branch, then read back the remote**. A branch that exists only locally is unreachable from the user's second machine (GitHub is the only sync channel). After push, confirm with `git ls-remote origin <branch>` and compare to local `git rev-parse <branch>` — push reporting "Everything up-to-date" proves nothing about the branch existing on the remote.
3. **Write `HANDOFF-*.md` at the repo root (tracked)** — `.project-local/` is gitignored and would not survive. Content: the verbatim user directive, exact branch + commit state, the authoritative visual source path with the note that it must be read via execute_code/Python (terminal boundary hook blocks `D:\` absolute paths there), the remaining work, the FULL test-anchor contract, known pitfalls, the delivery checklist, and a paste-ready new-session prompt (read-first list + task + hard constraints + execution rules + done criteria).
4. **Report with honest tiers**: VERIFIED (baseline green, doc committed + pushed, remote readback) vs UNFINISHED (reskin not started / pixel QA). Never present the handoff as task completion.

## Verified pitfalls

- **CSS comment `*/` early-close kills the whole build**: writing token names like `--glow-*/--grid-line` inside a `/* */` comment in `index.css` terminates the comment mid-line, leaving bare CSS that makes postcss-selector-parser fail `vite build` (tsc and vitest stay green, so only the build catches it). Never write `*/` inside CSS comments; rephrase (`--glow- and --grid-line`).
- **jsdom lacks ResizeObserver**: interactive canvas/graph components that use `ResizeObserver` crash under vitest jsdom. Stub it in `src/test/setup.ts` (no-op class) before mounting such components.
- **Testing-library `getByRole(..., {name: /regex/})` type friction**: in this repo's setup, prefer exact-string `name:` args (add `aria-label` to icon-only toolbar buttons); for role+regex probes use `document.querySelector('[role=...]')` + `getAttribute('aria-label')` instead.
- **Duplicate test anchors across list+detail renders**: a page that renders the same string in a list cell and a detail panel breaks single-`getByText` assertions — use `getAllByText`/`queryByText`.
- **Free-tier subagent models (glm-5.x-free) are unreliable**: delegated batches get stuck in 'waiting for the provider to recover' and interrupt with zero output. For convergence-critical UI waves, execute serially on the mainline; treat subagents as an optional speed-up, never the only path.
- **No-auth constraint for local research deployments**: when the user says local personal research (本地个人研究), no lock screen / access-token / API-key / credential / approval-reason input may appear on any page — even the Settings lane; verify with a repo-wide grep (`访问令牌|apiKey|password|secret|鉴权|OAuth|credential|审批理由|type=..password`) and leave the disclosure copy, remove any control.
- **"CSS layer appended" is NOT 1:1 — the render code's DOM must match the reference's HTML per view.** A reskin that leaves the existing lower-fidelity component bodies in place reads as "prototype-level" in user screenshots even though the reference CSS exists in the file and the build is green. When the user demands a full replica, extract the reference's structural blocks (view panels, sidebar, KPI grid), diff them against the render module's generated DOM per view, list the missing classes/nesting, and patch the render module so each view emits the reference structure (class names, nesting, hierarchy, copy) using ONLY classes already present in the absorbed CSS — never invent new ones.
- **Full-1:1 gaps are judged by screenshots, not by the CSS diff.** "The class exists in style.css" proves nothing about the rendered page — a dead class with no DOM usage is invisible. Before claiming 1:1, produce a screenshot-readback of each route and diff it against the reference view; a CSS-superset check plus green build is the floor, not the finish line.
- **`git push` saying "Everything up-to-date" is NOT proof the branch is on the remote**: read back `git ls-remote origin <branch>` and compare against local `git rev-parse <branch>` — that comparison is the only evidence a second machine (or a new session on it) can actually fetch the branch.

## Pitfalls

- The token trio (`tokens.ts` ↔ `index.css` ↔ `tokens.test.ts`) must move together; changing an asserted value without the test goes CI red.
- Accent tokens use the channel form `rgb(var(--X-rgb) / <alpha-value>)`: adding a color means the hex AND a `*-rgb` triple, or Tailwind alpha modifiers (`bg-primary/10`) break at runtime.
- Runtime visuals come from CSS tokens + components; reference PNGs are audit-only. Genuinely missing bitmaps are regenerated into `src/assets/generated/` and registered in `ASSET_REPLACEMENT_MANIFEST.md` (原参考 / 为何不能直接用 / 位置 / 尺寸 / 页面 / 差异) — random stock or other-project assets are forbidden.
- File operations (unzipping, reading suite files) go through execute_code Python. Terminal-tool rules: git/npm run through `python <Hermes-home>/bin/hermes-project-data.py --project . run -- <single command>` (bare `run -- git/npm`, no `bash -c` wrapper — the boundary hook accepts the single-command form and the legacy `bash -c '<single command>'` variant is unnecessary) with the tool's `workdir` set to the project root — a bare `cd` is blocked ('terminal calls must declare an explicit Git-project workdir'), and child commands must not contain absolute `D:\` paths or `/dev/null` (use `2>&1`, not redirects to /dev/null).
- `recharts` is already in dependencies (bar/line/spark charts); do not add another chart lib.
- 混入 AAOS 配色纠正 or DESIGN-LAB visuals = wrong product: B03's AAOS 母版 belongs to ArcheAxis, WORK-LAB keeps the deep-navy skin.
