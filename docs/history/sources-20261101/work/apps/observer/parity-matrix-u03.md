# U03 — Static-web → React Parity Matrix

> Taskpack U03 (P0): "Create static-web → React parity matrix, migrate valid
> capability, then retire static web as production." This document is the
> required parity matrix. It is evidence-based (call-site scans of the running
> static surface vs. the React UI), not a claim.

## Decision scope

The retired static surface lives at `apps/observer/web/` (9 scripts, 5 styles,
6 node contract suites). The React production UI lives at
`apps/observer/frontend/` (Tauri ships `frontend/dist` via `frontendDist:
"../frontend/dist"`; the live browser read-only entry opens `web/index.html`
with `?api=` pointed at the sidecar). `observer_live_server.py` is a **retired
fail-closed stub** (exit 2, by design) — the real static-serving path is
`services/orchestration/sidecar.py`.

Deletion of `web/` is **not** this step. Per the iron law "no deletion before
parity" and the release iron law (no claim without a real WebView artifact),
`web/` retirement is gated on **U19** (Windows Tauri E2E) and the exact-SHA
release. U03 here = **parity matrix + migrate valid capability only**.

## Capability-by-capability verdict

| Static capability | Source | Call sites in running static app | React status | Verdict | Action |
|---|---|---|---|---|---|
| **`WlA11y.announce`** — WCAG 2.2 AA polite live-region announcements (theme switch, LIVE/STALE/OFFLINE data-source transitions) | `web/scripts/accessibility.js` | `app.js` ×4 (`WlA11y.announce(...)`) | **Missing** | **VALID gap** | **Migrated** to React `src/lib/a11y.ts` (stateless DOM live-region, pure + SSR-safe) and wired into `App.tsx` theme + data-source transitions; covered by `src/lib/a11y.test.ts` (5 tests) |
| `WlA11y.bindSectionNav` / `setActiveNav` — in-page anchor navigation + keyboard nav | `web/scripts/accessibility.js` | `render.js` | React sidebar/view registry (`viewRegistry.ts`) + URL routing replaces in-page anchor nav | Redundant in React (a different, better IA) | **Not migrated** — capability superseded by the view registry, not dropped |
| **`WlCharts.lineChart`** — native SVG line/area chart | `web/scripts/charts.js` | `render.js` ×1 (pre-v3 legacy path only) | Missing | **NOT valid surface** | **Not migrated** — the v3 snapshot carries **no time-series data source**; rendering a chart would be a fabricated KPI (forbidden by the front-truth discipline). Left for a task that first ships the data source |
| `WlFormat.escapeHtml` | `web/scripts/formatters.js` | `app.js` ×1 | React auto-escapes string children | Redundant in React | **Not migrated** |
| `WlFormat` other helpers (intOrDash/tokens/costAmount/duration/relativeTime) | `web/scripts/formatters.js` | not called by the running v3 app | React `lib/api.ts` `fmt*` (truth-preserving: null → UNKNOWN/—) | Parity already held by `api.ts` | **Not re-migrated** — `api.ts` formatters already encode the null→UNKNOWN discipline |

## What "parity" means here (and is now true)

- **Valid a11y capability (announcer)**: React now owns a WCAG AA polite
  live region, announced on the same four state words the static surface used
  (theme dark/light, LIVE loaded, STALE last-good, OFFLINE no-fake-data).
  Real-DOM tests (`a11y.test.ts`) prove an announce lands in
  `div[role=status][aria-live=polite]` and that the singleton region is
  reused, not duplicated.
- **Charts / escapeHtml**: intentionally *not* ported — porting them would
  either duplicate React-native behavior (escapeHtml) or fabricate a KPI with
  no data source (WlCharts). The matrix records this as an explicit,
  evidence-based decision, not an oversight.
- **Navigation**: the static anchor-nav is superseded by the typed view
  registry + URL routing (U04), which is the better IA — not a loss.

## Evidence

- `a11y.test.ts`: 5/5 green (jsdom real DOM).
- Full React suite: 23/23 green (was 18; +5 a11y), `tsc` clean, `vite build`
  green.
- Call-site scan: `WlCharts` 1 site (legacy render.js, no v3 data),
  `WlFormat` 1 site (`escapeHtml`), `WlA11y.announce` 4 sites — the matrix is
  derived from these counts, not from assumption.

## Remaining gate (not this step)

Retiring `web/` from production requires:
1. **U19** — a real Windows Tauri E2E (WebView, not `about:blank`) proving the
   React `dist` surface is the production entry.
2. The exact-SHA release (tag + checksum + installer + public readback).
Only then is `web/` deletion "parity reached" and safe. Until then the static
surface stays as the browser read-only entry — it is live, not dead.


## 2026-10-07 实测对等清单（本轮新增，非沿用旧表格）

方法说明：先按断言名逐个统计旧树套件，再按**测试标题**（不是关键字命中）在生产树里找等价物。
关键字搜索曾给出"概念已存在"的假乐观（例如 `UNKNOWN` 在 `frontend/src` 出现 36 处），
但"出现该词"不等于"有一条断言守着它"，因此下表只认后者。

| 旧树套件 | 断言数 | 契约主题 | 生产侧等价物 |
|---|---|---|---|
| `test_projection_contract.js` | 13 | 不伪造真值（UNKNOWN、估算≠账单、RFC3339、覆盖率、前向兼容） | **无** |
| `test_read_only_surface.js` | 17 | 只读面（无可变控件、无重试控件、无 CDN、不读凭据、仅 loopback、last-good、拒绝低 revision 乱序） | **无** |
| `test_render_v3.js` | 19（另一声明风格，按套件运行计入总数） | v3 渲染契约 | **无** |
| `test_responsive_contract.js` | 11 | 响应式（无横向溢出、DPI 安全断点、body ≥12px、tabular-nums、CJK/SHA 换行、reduced-motion、320px-safe） | 部分（`test_desktop_component_contract.js` 只钉住顶部留白与网格归属） |
| `test_visual_assets_r2.js` | 5 | 品牌资产与设计令牌（本地 SVG、批准的关注主题/视图、只读） | 部分（主题令牌有 `theme/tokens.test.ts` 断言双主题与 legacy purple 清除） |

生产侧现存量：vitest/RTL 标题 84 条（焦点陷阱、提示语义、主题令牌、CommandPalette、
空态/未知态诚实标题），桌面契约 11 条（能力授权映射、原生调用 await、无边框留白、
窄屏动作簇可达、标签单源、KPI 网格归属、错误边界挂载）。

**结论（纠正本轮开始时的判断）**：U03 的卡点不是浏览器入口——入口已在
`tests/workflow-assistance/test_sidecar_ui_browser_entry.py`（8 例）里钉到同一份 Vite `dist/`。
真正的卡点是：这 65 条只读与不伪造契约目前**只存在于旧树套件中**，
`git rm -r apps/observer/web` 会连带删掉它们所描述的对象，而这些套件读的就是
`web/index.html`、`web/styles/*.css`、`web/scripts/*.js`。
先删除即等于**删除项目的铁律测试**，与"truth tests outrank new features"相反。

因此切换的可执行顺序（逐项可验证，不做无法验证的那一步）：
1. 把 `test_read_only_surface.js` 与 `test_projection_contract.js` 的断言逐条重锚到生产面
   （`frontend/index.html`、`frontend/src/skins/*.css`、`frontend/dist` 与
   `src-tauri/tauri.conf.json`/`capabilities`），并保留同名主题；
2. 把 `test_responsive_contract.js` 的溢出/字号/换行/reduced-motion/320px 断言重锚到壳层 CSS，
   `test_visual_assets_r2.js` 重锚到 `frontend/src/assets` 与令牌；
3. 两条生产侧入口都各有门禁之后，删除 `web/` 与 `helpers.js` 的 `WEB/loadScripts`，
   同步 `scripts/ci/required_groups.json:27` 的 glob 与 `tests/ci/test_failfast_group.py`
   钉死清单（ERR-109）、`run_quality_gate.py:1362` 受护路径、README/架构文档、
   `observer_live_server.py` 退役桩文案；
4. 删除前落 `web/` 全量哈希清单与整目录保留点，并更新 `WORK-LAB-AUTHORITY.md` §7 的日期事实。

第 1 步完成前，`web/` 不删；U03 保持 PARTIAL。

### 2026-10-07 步骤 1 落地进度（同一轮内）

新增 `apps/observer/tests/test_production_surface_static_contract.js`（11 条静态契约），
把旧树里**文件级**那部分保证重锚到生产面：入口无远程运行时/CDN、skins 无 `url(http`/`@import http`、
UI 层无写请求（`method: POST/PUT/PATCH/DELETE` 与带 options 的 `fetch` 都为 0）、
UI 层不读凭据/env/cookie、主题与布局态不落 web storage（编辑器画布模型为唯一具名例外）、
横向溢出抑制、tabular-nums、CJK/SHA 换行、`prefers-reduced-motion`、
基础字号不被压低且**所有 <12px 声明必须落在具名微角色**（`.winctl-zoom`、`.load-strip`、
`.brand small`、`.tag/.badge`、`.kpi small`）。

断言先证伪再用：注入 CDN script、组件里加 PATCH、正文加 10px 规则、往 `lib/a11y.ts` 塞
`localStorage` —— 4/4 各自变红，文件按字节复原（`falsify_prod_surface.py`）。
两条断言首版**是我自己写错**而非生产偏离：路径分隔符未归一导致编辑器没被排除（报出 4 处
"违规"），以及把 body 字号规则误用成"任何 px 字号"（把品牌小标签算成违规）；
都按事实改正而不是放宽。

**步骤 1 只完成一半**：`test_projection_contract.js`(13) 与 `test_render_v3.js`(19) 的
**投影真值与渲染契约仍未重锚**（它们断言的是 fixture 数值、估算≠账单、RFC3339、
覆盖率、乱序 revision 拒绝等，React 侧由 `truth.test.tsx`/`lib/api.test.ts` 部分承担但
未逐条对齐），故 `apps/observer/web` 仍不删，U03 保持 PARTIAL。基准 `214acb0`。

### 2026-10-07 投影真值 13 条的逐条归属（只认具名测试标题）

生产侧现有 87 条具名断言被用于判定；下列 13 条旧断言里，**5 条**能指到具名等价物，**8 条 OPEN**。

| 旧断言（test_projection_contract.js） | 生产侧归属 |
|---|---|
| fixture parses as valid JSON object with core keys | **OPEN — no named production assertion covers this** |
| inline API FIXTURE matches authoritative fixture numbers | **OPEN — no named production assertion covers this** |
| input/output/cache/cost never collapsed into a fabricated total token | lib/api.test.ts — fmtTokens null/undefined -> UNKNOWN, never "0"; executionsToRows: unknown project -> null tokens + UNKNOWN quality (no 0) |
| cost shown as API estimate / USD, never as an exact bill | lib/api.test.ts — fmtCostQuality: absent -> UNKNOWN; components/truth.test.tsx — TokenPanel with no data renders UNKNOWN everywhere, no 0 |
| subscriptionUsage=not-metered renders as 订阅未计量, never 0 | **OPEN — no named production assertion covers this** |
| all fixture dates are strict RFC3339 | **OPEN — no named production assertion covers this** |
| coverage has numerator/denominator/scope | **OPEN — no named production assertion covers this** |
| unknown/new fields are forward compatible (extra keys ignored, no crash) | **OPEN — no named production assertion covers this** |
| missing required core keys degrade gracefully (no crash, partial/unknown shown) | **OPEN — no named production assertion covers this** |
| empty-new-install fixture renders (empty state, no crash, no fake success) | components/truth.test.tsx — ProjectPanel with no data says the registry is empty / UNKNOWN; ExecutionTable with no data and no source says waiting, not fabricates rows |
| schema file is valid JSON and lists the 10 core required keys | **OPEN — no named production assertion covers this** |
| bundled snapshot has an explicit non-live mode | App.behavior.test.tsx — without a ?api= the write-back adds no api param (no fabricated source); every KPI number is UNKNOWN when there is no snapshot |
| compact header reflects the active data mode | components/truth.test.tsx — CompactHUD with no data shows UNKNOWN transport + 0-fabrication; App.behavior.test.tsx — ?view=compact renders the Compact HUD, no sidebar rail |

`test_render_v3.js` 的 19 条同法处理前，`web/` 不删。OPEN 项的共同主题：fixture 数值一致性、RFC3339 严格日期、覆盖率三元组、未知字段前向兼容、缺键优雅降级、schema 必含 10 键、not-metered 渲染为「订阅未计量」而非 0——这些都是可从 v3 快照/`lib/api.ts` 直接断言的纯函数级性质，迁移不需要真实素材。

### 2026-10-07 步骤 1 完成：8 条 OPEN 投影契约已重锚（基准 `10ae5cb`）

新增 `frontend/src/lib/projectionTruthContract.test.ts`（8 条具名行为断言，标题里写清它替代哪条旧断言）
与 `tests/test_production_surface_static_contract.js` 的 3 条文件级断言（11→14）。
文件级那一半不能放进 vitest：`frontend/tsconfig.json` 没有 `@types/node`，
`node:fs` 直接 `TS2307`，而 CI 会跑 `npm run typecheck`——所以磁盘扫描留在 node 套件里。

| 旧断言 | 生产侧新标题（节选） | 位置 |
|---|---|---|
| fixture parses as valid JSON object with core keys | legacy "fixture parses as valid JSON object with core keys": a v3 snapshot carries every key the front reads, with the declared type | vitest |
| 同上（typed model 漂移守护） | the typed front model declares the v3 core keys, with `software` the only optional | node |
| inline API FIXTURE matches authoritative fixture numbers | legacy "inline API FIXTURE…": with no injected endpoint the descriptor is the labelled non-authoritative loopback fallback, never a fabricated source | vitest |
| 同上（不许内嵌快照字面量） | no v3 snapshot literal is embedded in the production source | node |
| cost shown as API estimate / USD, never as an exact bill ＋ subscriptionUsage=not-metered renders as 订阅未计量, never 0 | legacy "cost shown as API estimate / USD…": the token summary carries counts plus a quality label and nothing that could be read as a bill | vitest |
| 同上（整树不得出现金额/订阅字样） | the production tree renders no currency amount and no subscription wording | node |
| all fixture dates are strict RFC3339 | legacy "all fixture dates are strict RFC3339": real dates localise, malformed ones render UNKNOWN, never "Invalid Date" | vitest |
| coverage has numerator/denominator/scope | legacy "coverage has numerator/denominator/scope": the triple survives projection, a real 0 stays 0, an absent triple stays null | vitest |
| unknown/new fields are forward compatible | legacy "unknown/new fields are forward compatible…": extra keys at any level and unknown enum values never fabricate a positive | vitest |
| missing required core keys degrade gracefully | legacy "missing required core keys degrade gracefully…": absent nested objects degrade to UNKNOWN/null instead of throwing or 0 | vitest |
| empty-new-install fixture renders | legacy "empty-new-install fixture renders…": an empty install projects zero rows and an UNKNOWN transport | vitest |

**迁移时发现的真缺陷（不是测试写错）**：生产侧 7 处日期渲染都是
`x ? new Date(x).toLocaleString() : 'UNKNOWN'`。两个后果：
（1）不合法字符串会渲染成字面 "Invalid Date"；
（2）更坏——`Date.parse('2026-02-30T10:00:00Z')` **不失败**，它滚成 3 月 2 日，
把损坏时间戳伪装成可信时刻。旧契约的"严格 RFC3339"正是防这个。
因此 `lib/api.ts` 新增 `isRfc3339`/`fmtTimestamp`（形状 + 月/日/时/分/秒 + 偏移量 + 闰年的日历校验），
`Views.tsx`(5)、`SoftwareView.tsx`(1)、`WorkflowsView.tsx`(1) 全部改用它。
生产侧两个发射方（`collector_scheduler._now_iso`、`durable_worker`）都输出 `...Z`，
所以严格门不会把真数据判成 UNKNOWN——这条我是先核发射方再改渲染方的。
另外 `snapshotToTransportTruth`/`executionsToRows`/`snapshotToProjectTokens`
原先对 `snap.transport.x` 直接取属性，缺键即抛；快照跨进程（sidecar 可能不同版本），
故按旧契约补了降级。

**证伪 11/11**（`.project-local/runs/convergence-20261007-c/falsify_u03_ports.py`，每条注入后按字节复原并核对 SHA-256）：
`types.ts` 键改名、`api.ts` 里 `authoritative:false→true`、`?? 'UNKNOWN'→'ZERO'`、
绕过 RFC3339 门、覆盖率补 0、`stateTone` 默认落到 `done`、去掉可选链使其抛错、
UNKNOWN 传输粉饰成 LIVE、往 `a11y.ts` 塞 v3 字面量、塞 `USD $4.29`、
以及删掉测试自身 fixture 的一个核心键（这条是断言的变异测试，证明它真在断言）。

两处证伪**首版是我预期写错**而非门禁失效，都已按事实改注入而不是放宽断言：
`transportState ?? 'LIVE'` 打不中"空安装"一例（该例显式传 'UNKNOWN'，`??` 不触发），
`tokenTruth` 补零也打不中它——空安装例的 tokenSummary 是存在且为 null；
换成"把 UNKNOWN 传输粉饰成 LIVE"后由空安装例与降级例同时变红。
`a11y.ts` 那次也暴露 node 侧 needle 要写"账单形状"而不是裸 `$`：`api.ts` 里
`replace(..., 'http://$1')` 的 `$1` 会被裸 `$`+数字命中，第一版把我自己的合规代码报成违规。

实测存量更新：vitest/RTL **具名标题 95 条 / 执行 95 条（15 个文件）**，node 静态契约 **14 条**，
旧树 5 个套件仍为 13/17/19/11/5。（这两个数字后被"步骤 2"一节纠正：只读面实测 24 条，旧树总量 72。）全量：`vitest run` 15 files / 95 passed，
`tests/run_all_tests.js` 97 passed 0 failed，`tsc --noEmit` 干净，`vite build` 绿。

**仍未完成**：`test_render_v3.js`(19)、`test_read_only_surface.js`(17)、
`test_responsive_contract.js`(11)、`test_visual_assets_r2.js`(5) 的逐条归属；
这四张表填完并且第 1 步的等价物全部落地之前，`apps/observer/web` 不删，U03 保持 PARTIAL。

### 2026-10-07 `test_render_v3.js` 19 条逐条归属（基准 `580df3c`）

方法同投影表：只认具名生产标题。生产侧候选归属池 = vitest 95 条标题（15 文件）
＋ node 静态契约 14 条 = 109 条。下表引用的 8 条生产标题已逐条 `grep` 回原文核对，
不是转述。**实测统计：COVERED 4 / PORTED 0 / OPEN 10 / LEGACY-ONLY 5（共 19）**。
PORTED 为 0 这件事本身是结论：14 条静态契约全是文件级（入口/skins/源码文本），
一条都不承接 v3 渲染性质。

| 旧断言（test_render_v3.js，文件顺序，逐字） | 它守的性质 | 判定 | 生产侧归属 / 理由 |
|---|---|---|---|
| connection strip reports the real sidecar/event state without 0/0 coverage | 传输结论逐字呈现 + 展示真实 sourceWatermark；覆盖率缺失不得写成 0/0；不泄漏内部表名 | OPEN | 需挂载连接条：transportState 逐字、sourceWatermark 出现、coverage 为 null 时是 UNKNOWN 而非 "0/0"、正文不含 `collector_health` |
| last-good becomes visibly OFFLINE when the EventSource transport fails | 本地流/轮询失败要把 last-good 翻成 OFFLINE，并撤掉"已连接"宣称 | OPEN | 驱动 `useLiveSnapshot` 的 SSE onError + 已接受过快照，断言 OFFLINE 标注；`l10-views.test.tsx — an honest OFFLINE snapshot keeps every metric UNKNOWN-ish, never a fake LIVE` 只覆盖快照自带 OFFLINE，不覆盖本地传输失败 |
| project surface keeps canonical registry and local Git facts | 项目面呈现注册表与本地 Git 事实（分支、短 SHA、dirtyCount、观测时刻、REGISTERED 措辞） | OPEN | `ProjectPanel.tsx` 源码里这么渲染，但没有标题断言它；`truth.test.tsx — ProjectPanel with no data…` 只覆盖空态 |
| unsupported execution/CI/governance fields never become cards | v3 没有的模块不得变成卡片/KPI | OPEN | 生产面反向成立（车道恒在、诚实显示 UNKNOWN/EmptyState），端口应断言"模型/时序/资源/逐执行成本"这四类无卡 |
| task and usage sections appear only when canonical samples exist | 任务与用量段只从规范数据出现 | OPEN | 任务半边已归属（`views.test.tsx — TaskPacksView renders the real task-family counts and plan tasks`）；用量半边无归属 |
| full view: connection + token dash + status matrix + governance only | 旧单页 innerHTML 组成 | LEGACY-ONLY | 断言的是旧单页字符串；React 有意把 taskpack/history/evidence 拆成独立只读车道 |
| production v3 entry calls fusion + truthful surfaces | 旧 `app.js` 接线 `WlFusionV3.render`，且不调用四个退役渲染器 | LEGACY-ONLY | 读的是 `web/scripts/app.js` 文本与 `Wl*` 全局，生产树无这些标识符 |
| metric cards render real data only | KPI 卡呈现真实项目/任务/Token 总数与覆盖 | OPEN | `fmtTokens` 只测格式化器，没有标题断言挂载后的 KPI 数值 |
| metric cards never fabricate from UNKNOWN/zero | 无规范数据时不产出正向或 0 指标 | COVERED | `App.behavior.test.tsx — every KPI number is UNKNOWN when there is no snapshot` |
| full view has no per-project task matrix | 旧 DOM id `wl-taskpack`/`wl-project-truth-card` 不在字符串里 | LEGACY-ONLY | 断言旧 id 缺失；React 壳无这些 id，且任务包车道是既定生产视图 |
| platform status matrix shows project/platform/activity | 跨项目行呈现名称/平台/活动态/分支 | OPEN | `WorkView.behavior.test.tsx — real snapshot -> the closed loop renders project -> execution -> CI -> evidence` 只覆盖名称与状态 |
| token dashboard renders real tokens only | Token 面板呈现真实总数与缓存命中率 | OPEN | 真实数值半边需端口；命中率半边不可移植——`TokenSummary` 只有 input/output/total/costQuality，v3 无缓存字段，移植即造 KPI |
| token dashboard empty when no sample | 无样本→诚实空态 | COVERED | `components/truth.test.tsx — TokenPanel with no data renders UNKNOWN everywhere, no 0` |
| full view prefers runtime matrix over task matrix | 旧 id 的 index-of 先后 | LEGACY-ONLY | 字符串次序无生产对应物（车道是路由） |
| CC2: single unified project grid (no duplicated surfaces | 一个全局命令 + 一个项目面，不重复 | COVERED | `lib/viewRegistry.test.ts — P1-01: NAV_GROUPS has 7 primary entries and covers every reachable lane exactly once`（命令入口：`components/ui/components.test.tsx — CommandPalette: filters by query and Enter runs the item`） |
| CC2: truth - token telemetry empty state when no sample | 无样本不写 "0 Token" | COVERED | `components/truth.test.tsx — TokenPanel with no data renders UNKNOWN everywhere, no 0` |
| CC2: telemetry renders real tokens | 遥测段呈现真实总量＋命中率 | OPEN | 同第 12 行：数值半边可移植，命中率不可 |
| CC2: project card shows platform/git/status | 项目卡呈现平台/分支/状态点 | OPEN | 旧 id 名不可移植，但数据真值无归属 |
| app.js wires fusion render | 旧入口脚本含 `WlFusionV3.render` | LEGACY-ONLY | 退役脚本源码文本 grep |

10 条 OPEN 收敛成 6 个可移植性质（其余是同一性质换个旧包装）：连接条逐字真值与
"缺失≠0/0"、本地传输失败翻 OFFLINE、项目面 Git 事实、Token 面板真实数值、
KPI 条真实数值、v3 无字段不得成卡。5 条 LEGACY-ONLY 随 `web/` 一起退役，不需要归属。

**门禁结论不变**：`apps/observer/web` 仍不删，U03 仍 PARTIAL——但删除阻塞现在是可枚举的：
10 条 render_v3 OPEN ＋ 下面三张表的 OPEN 项。

### 2026-10-07 步骤 2 落地：render_v3 的 10 条 OPEN 已收敛为 8 条挂载断言（基准 `580df3c`）

新增 `frontend/src/views/renderTruthContract.test.tsx`（8 条具名标题，挂真实组件：
ProjectPanel / TokenPanel / OverviewView / CompactHUD / 真 `useLiveSnapshot`）。
**先纠正上一轮的计数**：`test_read_only_surface.js` 实测是 **24 条**（17 条 `t(` ＋ 7 条
`asyncTest(`），不是 17；因此旧树五套件总量是 **72**（13+24+19+11+5），不是 65。
方法教训：按 `t(` 计数会漏掉同一套件里的另一种断言风格。

8 条移植断言（标题里带被替代的旧断言名）：注册表身份/平台/执行数/branch@sha/脏数渲染；
**未观测的 dirtyCount 绝不显示"干净"**；Token 面板呈现真实数值且不编造命中率
（`TokenSummary` 只有 input/output/total/costQuality，v3 无缓存字段）；
无 token 数据时不画进度条也不写 0；总览 KPI 条渲染快照真值；
覆盖率三元组缺失时是 `覆盖 UNKNOWN` 而不是 `覆盖 0/0`（而测得的 0/0 仍按数字显示）；
v3 没有的字段不得长成指标卡（CPU/GPU/内存/显存/磁盘/QPS/模型数）；
**读取路径失败必须停止 LIVE 宣称并保留 last-good**。

顺带修掉两处生产真缺陷（都先证伪再改，都写进台账 ERR-120）：
1. `ProjectPanel.tsx:42` 与 `Views.tsx:72` 都写 `dirty ? 脏N : 干净`——
   `dirtyCount` 为 null（未观测）会渲染成"干净"，等于把未知报成正面结论，
   而本仓库自己的说明文字就写着"缺失即 UNKNOWN，不伪造『全部干净』"（RulesPolicyView）。
   现在 null → `脏 UNKNOWN`，0 → `干净`，>0 → `脏 N`，三态各自有断言。
2. 读取失败时 `useLiveSnapshot` 只 `setError` 不动 `live`，于是 CompactHUD 继续播
   上次快照里烤进去的 `LIVE`。现在拉取失败即 `live=false` 且回到非 live 标签，
   HUD 状态词改由新增的 `frontTransportState(snap, live, error)` 给出：
   无数据 UNKNOWN、本地读失败 OFFLINE、否则用快照自己的传输词。数据不清空，只改宣称。

证伪 8/8（`.project-local/runs/convergence-20261007-c/falsify_render_ports.py`，
每次注入后按字节复原并核对 SHA-256；注入全打在生产组件上，不打在测试自身夹具上）。
**第 7 条首版是门禁自己瞎**：断言写 `/\bCPU\b/`，而 `textContent` 把标签和数值连成
`CPU11`，词边界不成立——我把一个 CPU 指标卡注入 OverviewView，套件仍然全绿。
去掉 `\b` 后同一注入立刻变红。这条教训与"针要写违规的形状，不写裸 token"是同族：
DOM 文本拼接会吃掉词边界。

实测存量更新：vitest/RTL **16 文件 / 具名标题 103 条 / 执行 103 条**，node 静态契约 14 条，
`run_all_tests.js` 97 passed 0 failed，`tsc --noEmit` 干净。

### 2026-10-07 其余三套件逐条归属（`test_read_only_surface.js` 24 / `test_responsive_contract.js` 11 / `test_visual_assets_r2.js` 5）

判定同样只认具名标题；下表引用的生产标题、`src-tauri/src/lib.rs` 的 Rust 测试名、
`index.html:5` viewport、`src/index.css:220` 320px 下限，**全部逐条 grep 回原文核对**。

#### 只读面 24 条

| 旧断言（逐字，文件顺序） | 它守的性质 | 判定 | 生产侧归属 / 理由 |
|---|---|---|---|
| api layer exposes no success path for POST/PUT/PATCH/DELETE | 非 GET 动词不可能成功 | PORTED | `test_production_surface_static_contract.js — read-only: no write request leaves the UI layer`（生产侧无运行时 `rejectNonGet` 门，只有源码级扫描） |
| snapshot fetch rejects legacy and partial LIVE success payloads | 载荷校验 fail-closed | OPEN | `fetchSnapshot` 直接 `res.json() as SnapshotV3`，零校验（api.ts:83-91） |
| snapshot fetch is explicitly cache-bypassed | GET 带 `cache:"no-store"` | OPEN | 现只带 Origin 头——缓存快照可能被当成当前值呈现 |
| v3 display mode cannot override the backend transport verdict | 传输结论优先于载荷 mode | OPEN | `frontTransportState` 是对应物但尚无断言；`live` 直接取自载荷 |
| LIVE v3 requires exact coverage, timestamps, and loopback events URL | LIVE 门槛：覆盖相等、时间戳齐、eventsUrl 是 loopback | OPEN | 生产侧无 LIVE 门，静态契约只钉住类型键 |
| rendered full+compact surfaces have no mutating controls | 无可交互写控件 | COVERED | `WorkView.behavior.test.tsx — WorkView is strictly read-only: zero interactive write affordances` ＋ `l10-views.test.tsx — exposes ZERO write/approve/deny/retry controls (read-only iron law)`（按车道，不是全局：编辑器/模态确实有按钮） |
| blocker evidence card offers NO retry control | 错误/证据面无重试 | COVERED | 同上两条 ＋ `lane-error-boundary.test.tsx — recovers when the lane changes, without retrying the read itself`；「只读观察，不提供重试操作」这句文案本身无归属 |
| index.html references no remote runtime/framework/CDN | 入口无远程资产 | PORTED | `the production entry loads no remote runtime, framework or CDN` |
| no credentials/session/prompt/secret access in scripts | 不读凭据/存储/auth | PORTED | `read-only: no credential, auth store or env read in the UI layer`（两个扫描都未覆盖 prompt/response 正文） |
| api layer never writes; only GET fetch exists | 网络层只 GET | PORTED | 同上；「显式 `method:'GET'`」这一半无归属（生产依赖 fetch 默认值） |
| retired dashboard helper fails closed without a network request | 退役 `WlApi.fetchDashboard` 抛错 | LEGACY-ONLY | 断言 `Wl*` 全局；其实质（退役 `/api/dashboard` 被拒）由下面的 Rust 测试承接 |
| snapshot endpoint accepts only explicit loopback read-only URL (v3) | 端点必须 loopback、无 query、非旧路径 | COVERED | `src-tauri/src/lib.rs — #[test] fn observer_api_is_loopback_get_only`（cargo 侧，拒绝 https/外链、`?write=1`、`/api/dashboard`） |
| theme toggle is memory-only | 不写服务端、不写存储 | PORTED | `theme and layout state never persist to web storage`；URL 那一半由 `App.behavior.test.tsx — navigating does not drop a Tauri-injected ?api= endpoint` 承接 |
| EventSource open refreshes the read-only snapshot after sidecar reconnect | onOpen 立即重读快照 | OPEN | api.ts `onOpen` 只改 source，不重读；子断言多为对 `web/scripts/app.js` 的正则 |
| state last-good survives refresh error (never clears to zero) | 失败保留 last-good 并标记过期 | OPEN | 本轮已补 `live=false` 与 `source` 回落，但"新鲜度必须翻 STALE"仍无专属标题 |
| state rejects an out-of-order lower-revision projection | revision 单调 | OPEN | `apply()` 无条件覆盖，迟到的旧载荷会赢 |
| heartbeat avoids snapshot GET and refresh bursts are coalesced | 心跳不发 GET、突发合并 | OPEN | 只绑 `snapshot`/`message`；轮询与 SSE 无协调 |
| SSE failure fences an older GET and preserves native reconnect | 传输失败保持 OFFLINE 且不关源 | OPEN | `onError` 是空的；迟到的 GET 仍会把 live 置真 |
| rejected lower revision cannot rotate the EventSource endpoint | 载荷不能改订阅端点 | OPEN | 结构上成立（URL 来自 descriptor），但浏览器路径的 `?api=` 未校验，且不拒旧 revision |
| malformed SSE payload degrades without waiting for a transport reopen | 协议错误与传输错误分离 | OPEN | 解析失败→`apply(null)`→不降级，仍显示旧 LIVE |
| refresh errors preserve string-valued v3 quality fields without throwing | 出错时质量字符串不丢 | OPEN | 无 `markRefreshError` 对应物 |
| bundled snapshot is always rendered stale rather than live | 静态/内置快照不得显新鲜 | OPEN | `static-preview` 有标注（这一半由 `projectionTruthContract.test.ts` 承接），但从不强制 stale |
| SSE client accepts only loopback event endpoint and forwards named events | 端点信任 ＋ 具名事件派发 | OPEN | `loadRuntimeDescriptor` 对 `?api=` 字符串不设限；`observed`/`heartbeat`/`resync_required` 未绑；坏帧被吞 |
| web tree has no server/backoffice entry points | 只引用 `/api/v1/snapshot` | LEGACY-ONLY | 扫的是 `web/index.html` 与 `web/scripts/api.js`；端点那一半归 Rust 测试，需补一条对 `frontend/src` 的扫描 |

#### 响应式 11 条

| 旧断言 | 性质 | 判定 | 归属 / 理由 |
|---|---|---|---|
| viewport meta present | `width=device-width` | HOLDS-BUT-UNGUARDED | `frontend/index.html:5` 成立；无人断言——补一条 querySelector 即可 |
| horizontal overflow suppressed | 页面不横滚 | PORTED | `responsive: horizontal page overflow is suppressed by construction`（`.table-wrap` 那一半未钉） |
| truth cards reflow at the DPI-safe breakpoints (800/640) | 断点回流 | HOLDS-BUT-UNGUARDED | 生产断点在 840/1160/1240/1000 ＋ `@container page` 820/900/760，**无 640/420**，也无断言 |
| compact view is a separate single-column layout | 紧凑面独立 | COVERED | `App.behavior.test.tsx — ?view=compact renders the Compact HUD, no sidebar rail` |
| body font-size >= 12px | 可读下限 | PORTED | `legibility: no rule sets the page or lane base text below 12px` |
| tabular numerals enabled | 数字等宽 | PORTED | `responsive: numeric columns use tabular numerals` |
| long CJK / SHA / tokens wrap | 长串换行 | PORTED | `responsive: long CJK, SHA and token strings wrap instead of overflowing` |
| prefers-reduced-motion honored | 尊重减弱动效 | PORTED | `motion: a reduced-motion preference is honoured` |
| no horizontal page scroll by construction (min-width 320) | 320px 壳下限 | HOLDS-BUT-UNGUARDED | `src/index.css:220` 成立，但静态契约只读 `skins/*`，从不读 `index.css` |
| v3 compact view is 320px-safe (WLGM-200) | 紧凑面无固定宽 | HOLDS-BUT-UNGUARDED | CompactHUD 无超宽、SHA 截断、chip 带文字；旧断言扫的是自己的 `render-v3.js` 路径 |
| status never relies on color alone | 状态带文字 | COVERED | `l10-views.test.tsx — projects the B10 metric row from the REAL v3 transport/coverage truth` ＋ `truth.test.tsx — CompactHUD with no data shows UNKNOWN transport + 0-fabrication`；图标那一半是旧标记（生产小圆点 `aria-hidden`） |

#### 视觉资产 5 条

| 旧断言 | 性质 | 判定 | 归属 / 理由 |
|---|---|---|---|
| R2 brand assets are checked in under web/assets/brand | 5 个品牌文件在场 | OPEN | `frontend/src/assets/` 不存在；Tauri 打包用 `src-tauri/icons/*`，删了不坏构建，但品牌资产会丢 |
| R2 design tokens declare the approved themes/views and read-only constraints | 机器可读约束 | OPEN | `src/theme/tokens.ts` 未声明约束；主题与视图各自有归属，约束只隐含 |
| R2 brand SVGs are local and structurally valid | SVG 本地且无远程 href | OPEN | 必须先把它复制进生产树才谈得上断言 |
| index uses only local visual assets and preserves read-only web surface | 入口只引用本地资产 | PORTED | 无远程那一半已由静态契约承接；但「品牌挂载」失败（`frontend/index.html` 无 favicon/品牌 link），且「只读」措辞搬到了 `App.tsx:263` 无归属 |
| compact R2 hierarchy keeps four KPIs and a dense project list | 4 KPI ＋ 密集列表 | OPEN | CompactHUD 确实是 4 张 KPI（传输/项目/Token/质量），但旧版 `slice(0,3)` 密集项目列表无生产对应物 |

#### 三套件合并计数与步骤 3 工作单

**COVERED 5 · PORTED 11 · HOLDS-BUT-UNGUARDED 4 · OPEN 18 · LEGACY-ONLY 2（共 40 行）。**
加上 render_v3 的 8 条（本轮已全部落地）与投影 13 条（上一轮全部落地），
`web/` 退役的剩余阻塞就是下面这 18 条 OPEN，按危险度排序（前 6 条是**会产生假象的生产缺陷**，
不只是缺测试）：

1. revision 单调：迟到的低 revision 载荷不得覆盖 last-good（现在会覆盖，会显示旧事实）。
2. `fetchSnapshot` 载荷校验：v2/仅 mode/残缺 LIVE 载荷必须 fail-closed，而不是当 v3 渲染。
3. SSE 失败必须保持 OFFLINE 且不关原生重连；坏帧按协议错误降级，不能继续播旧 LIVE。
4. `cache:'no-store'`：否则缓存快照会被当成当前值。
5. 浏览器路径 `?api=` 的信任：非 loopback / 带 query / 带 userinfo 必须先拒（Rust 侧已拒，浏览器路径未拒）。
6. `static-preview`/内置快照必须显示过期，不能显示新鲜。
7. `frontTransportState` 的专属具名断言（现在只有间接归属）。
8. 载荷不能改订阅中的 events 端点。
9. onOpen 立即重读规范快照；心跳不发 GET、突发合并为「一次在途 ＋ 一次追平」。
10. 刷新出错时保留字符串型质量字段。
11. 出错时 last-good 保留 **且** 新鲜度必须翻 STALE 的直接断言。
12. 具名 SSE 事件（`observed`/`heartbeat`/`resync_required`）派发与 Last-Event-ID 透传。
13. 把 5 个品牌 SVG 复制进 `frontend/src/assets/brand` 并钉「在场 ＋ 无远程 href」。
14. `src/theme/tokens.ts` 声明约束（`readOnly:true / externalMutation:false / modelSummary:false`）。
15. 紧凑面：4 KPI 已成立需钉住；密集项目列表要么移植、要么记录为有意放弃。
16. viewport meta、320px 下限、DPI 断点回流三条 HOLDS-BUT-UNGUARDED 各补一行守卫（含让静态契约读 `index.css`）。
17. 「只读观察，不提供重试操作」等文案的具名归属。
18. 对 `frontend/src` 补一条「只引用 `/api/v1/*` 端点、无后台入口」的静态扫描。

**这 18 条做完之前 `apps/observer/web` 不删。**

### 2026-10-07 工作单收口：18 条全部关闭

后续三轮把上面工作单逐条落地：1-12 由步骤 3（`transportTruthContract.test.ts` 11 条 ＋
node 文件级 2 条，证伪 15/15）关闭；13／15／16／17 与"只读文案归属"由步骤 4
（品牌 5 件迁入并断言、紧凑四张 KPI 钉住、密集项目列表记为有意放弃、断点按**行为**移植、
`Views.tsx`/`App.tsx` 的只读与不伪造措辞各有具名断言，证伪 5/5）关闭；
最后一条 14 由 `theme/tokens.ts` 新增 `VIEW_CONSTRAINTS` 与 `design-tokens.json.constraints`
的**双向对撞断言**关闭（`the declared read-only constraints agree between TypeScript and the
brand JSON`，node 契约 23→24）——两处各写一份不叫单源，两处一旦不一致就红，
所以证伪用了三针：改 JSON、删 tokens 声明、只改 tokens 里的 `readOnly`，三针各自变红
（第三针第一次被判 SURVIVED 是**我的预期字符串写错**——它先撞上"disagrees"那条断言，
报错文本是 `readOnly disagrees: tokens.ts=false design-tokens.json=true`，门是对的）。

至此旧树 72 条断言全部有归属，`apps/observer/web` 已在 `891c871` 退役删除，
CI 两条工作流在该提交上全绿。**留给下轮的不是工作单条目，而是两件新事**：
把迁入的品牌 SVG 真正挂到头部（视觉改动，需单独走查），以及把 CDP 布局探针接成 CI 门
（现在它只量不门，窄屏那类缺陷靠静态形状契约兜，不如真实盒模型硬）。

### 2026-10-07 步骤 3 落地：传输面 OPEN 已收（基准 `78a81c3`）

工作单头 12 条是**会产生假象的生产缺陷**，不是缺测试，所以先做它们。
新增 `frontend/src/lib/transportTruthContract.test.ts`（11 条具名断言，真 `useLiveSnapshot`
＋可控 EventSource 替身）与 `test_production_surface_static_contract.js` 2 条文件级（14→16）。
生产侧改动全在 `lib/api.ts`：

| 工作单项 | 关闭方式 |
|---|---|
| 1 revision 单调 | `apply()` 记住 `lastRevision`，低 revision 载荷被拒并写错误，画面保持上次投影 |
| 2 载荷校验 fail-closed | 新增 `parseSnapshotPayload`：schemaVersion/revision/数组/五个对象键逐项核，v2 与残缺载荷返回 null |
| 3 SSE 失败保持 OFFLINE、坏帧即刻降级 | `onError` 改为停止 LIVE 宣称（不 close，交给浏览器原生重连）；`snapshot` 帧走同一校验，坏帧降级；无类型 `message` 帧**不**算协议失败 |
| 4 `cache:'no-store'` | `fetchSnapshot` 带 `method:'GET'` ＋ `cache:'no-store'`；静态契约同时升级要求"带 options 的 fetch 必须显式声明 GET" |
| 5 浏览器路径 `?api=` 信任 | 新增 `isTrustedObserverEndpoint`：拒 https、外链、URL 内凭据、query/hash、非 `/api/v1` 路径；不信任就整体退回 non-authoritative，绝不向它发一个字节 |
| 6 non-authoritative 不得显新鲜 | `setLive(descriptor.authoritative && payload==='LIVE')` |
| 7 `frontTransportState` 具名归属 | 步骤 2 的挂载断言 ＋ 本文件的 transport-failure 断言 |
| 8 载荷不得改订阅端点 | 断言订阅 URL 只来自 descriptor；注入"用载荷 eventsUrl 再开一条流"即变红，且我们出错时从不 `close()` |
| 9 onOpen 重读、心跳零 GET、突发合并 | `onOpen` 触发一次读；`heartbeat` 不读；在途只一次，多余请求合并成**一次**追平 |
| 10 出错保留字符串质量字段 | 断言 `costQuality/matchState/governance.families.memory.state` 在失败后仍在 |
| 11 last-good 保留并回落 STALE | `reportReadFailure` 不清空快照，只改 live/source/error |
| 12 具名 SSE 事件绑定 | 断言 `open/snapshot/message/heartbeat/observed/resync_required/error` 都绑上 |
| 16（一半）viewport 与 320px 下限 | 文件级两条：入口 `width=device-width`、`src/index.css` 的 `[data-layout=compact]{min-width:320px}` |
| 18 只引用 loopback v1 端点 | 文件级一条：UI 层任何带 scheme 的 URL 必须是 `http://127.0.0.1|localhost|[::1]:port/api/v1/(snapshot\|events)` |

**证伪 15/15**：vitest 11 条（`falsify_transport_ports.py`）＋ node 4 条
（`falsify_step3_node.py`），注入全部落在 `api.ts`/`index.html`/源码上，每次按字节复原核对 SHA-256。

三条**门禁自己先写错**、按事实改正而非放宽（都记进台账 ERR-121）：
① 新的显式 `method:'GET'` 撞上旧断言"任何带 options 的 fetch 都要可疑"——旧条款把
"必须显式 GET"这一半反着钉了；改成要求带 options 的 fetch 必须声明 GET，并在扫描命中 0 条时直接失败。
② `parseSnapshotPayload` 里的 schema 常量被"不得内嵌 v3 快照"的裸文本针判成违规——
针改成属性赋值形状（`schemaVersion: '…'`），验证器里的比较句不再误伤。
③ 端点扫描把 `@tauri-apps/api/window`（模块路径）和正则里的 `http://$1`（替换串）当成 URL——
针改为必须带 scheme 且主机首字符是字母数字，并把"扫不到任何 URL"判为失败而不是通过。

**仍未关闭**：工作单 13（5 个品牌 SVG 未迁入生产树）、14（`theme/tokens.ts` 未声明约束）、
15（紧凑面 4 KPI 需钉、密集项目列表需决定移植或有意放弃）、17（"只读观察，不提供重试操作"等文案无具名归属）、
16 的 DPI 断点回流一半（生产断点与旧 800/640 不同，需先决定是移植语义还是记录为新契约）。
`apps/observer/web` 仍不删，U03 仍 PARTIAL。实测存量：vitest 17 文件 **114** 条、node 静态契约 **16** 条、
`run_all_tests.js` **99 passed 0 failed**、`tsc --noEmit` 干净、`vite build` 绿。

### 2026-10-07 步骤 4：品牌/约束/文案/紧凑层与断点归属（基准 `be6c2de`）

工作单剩余 5 条全部关闭（node 静态契约 16→21）：

- **13 品牌资产已迁入生产树**：`apps/observer/web/assets/brand/` 的 5 个文件
  （`design-tokens.json`、`observer-icons.svg`、`work-lab-observer-symbol.svg`、
  `work-lab-observer-tray.svg`、`app-icon-512.png`）逐字节复制到
  `apps/observer/frontend/src/assets/brand/`，5/5 SHA-256 与源文件相同后落盘；
  新断言钉「在场 ＋ SVG 以 `<svg>` 开头 ＋ 无远程 href/src」。
  本轮**只迁移不挂载**：生产头部品牌是文字标，插入 SVG 属于视觉改动，另案处理。
- **14 只读约束已有机器可读位置**：`design-tokens.json` 的 `constraints`
  （`readOnly:true / externalMutation:false / modelSummary:false`）＋ themes 含 dark/light、
  views 含 full/compact 由新断言逐项核。
- **15 紧凑层四张 KPI 已钉**（传输/项目/Token/质量，多一张少一张都红）。
  **密集项目列表记为有意放弃**，不是遗漏：紧凑 HUD 是单列状态条，
  项目真值在「项目」车道（`ProjectPanel` 已有挂载断言），在 HUD 里再列一份会造出第二处项目视图，
  与旧断言自己反对的"重复项目面"（CC2 single unified project grid）相矛盾。
- **17 只读与不伪造文案有具名归属**：`Views.tsx` 的「只读」「不构成第二 Update Authority」
  与 `App.tsx` 的「不伪造 / 保持 UNKNOWN 真相」各有断言。首版我写成扫全量 `appCode`，
  那样连测试自己引用的文字都能算命中；改为分别扫这两个具体文件，
  删掉 `Views.tsx` 那句"第二 Update Authority"即变红。
- **16 断点那一半按行为而非数值移植**：生产用容器查询（`@container page 760px`
  把 `.two-col/.three-col/.split` 收成 `1fr`）而不是旧的 800/640 媒体查询，
  所以断言读的是**声明值必须是单个 `1fr`**（写 `1fr 1fr` 也红），外加 840px 媒体查询与
  `src/index.css` 的 320px 下限仍在。

**一条有意不移植，理由是要守更高的规则**：只读表里"LIVE v3 requires exact coverage,
timestamps, and loopback events URL"（前端自己重算 LIVE 门）**不移植**——
LIVE 结论由后端 `snapshot_api/sidecar` 判，前端再算一遍就是第二个 Update Authority，
违反铁律。前端只做三件属于它自己的事：不接受不可信端点（步骤 3）、
非权威来源不得显 LIVE（步骤 3）、乱序与坏帧不覆盖（步骤 3）。这三件都已钉住。

**证伪 5/5**（`.project-local/runs/convergence-20261007-c/falsify_step4_node.py`，
注入都落在生产文件上并按字节复原核对 SHA-256）：给品牌 SVG 加远程 `href`、把
`constraints.readOnly` 改成 false、删掉"第二 Update Authority"字样、
往紧凑 HUD 塞第 5 张 KPI、把 `1fr` 改成 `1fr 1fr`。

至此**旧树 72 条断言全部有判定**（投影 13 ＋ 渲染 19 ＋ 只读 24 ＋ 响应式 11 ＋ 视觉 5），
矩阵第 1、2 步完成。剩下的只是切换本身（矩阵第 3、4 步）：
`web/` 与其 5 个 JS 套件与 `helpers.js` 的删除、四处清单绑定
（`scripts/ci/required_groups.json`、`tests/ci/test_failfast_group.py` 钉死清单、
`run_quality_gate.py` 受护路径、`run_all_tests.js` 注册表）、README/架构文档/退役桩文案，
以及 `WORK-LAB-AUTHORITY.md` §7 的日期事实更正。

### 2026-10-07 切换完成：静态面已退役（矩阵第 3、4 步）

**先落审计清单与可恢复点，再删除**：
`docs/audits/OBSERVER_WEB_RETIREMENT_MANIFEST_2026-10-07.json`（提交 `d6976dc`，
早于删除提交）逐文件记录 24 个 `web/` 文件（242,007 字节）与 6 个套件/`helpers.js`
（63,363 字节）的 SHA-256 与字节数，写完后又回读工作树逐个复核哈希；
恢复点就是清单里的 `pre_deletion_commit`（已推到 origin 的提交），
恢复命令 `git checkout 6de25fe -- apps/observer/web apps/observer/tests`；
另有一份工作树副本放在 `.project-local/artifacts/observer-web-retired-20261007/`（48 文件）。
**不新推 tag**（owner 要求不发布），可恢复性由已推送历史 + 清单承担。

删除：`apps/observer/web/`（24 文件）＋ `test_projection_contract.js`、
`test_read_only_surface.js`、`test_render_v3.js`、`test_responsive_contract.js`、
`test_visual_assets_r2.js`、`helpers.js`。

四处绑定与四处文案同批改：
`run_all_tests.js` 注册表去掉 5 条旧套件；
`scripts/ci/required_groups.json` 的 `observer-web-contracts` 去掉 `web/scripts/*.js` glob；
`tests/ci/test_failfast_group.py` 的钉死命令清单同步（ERR-109 纪律：改清单必须改钉死表）；
`run_quality_gate.py` 的 `observer-no-business-write` 触发路径由 `apps/observer/web/`
换成 `apps/observer/frontend/src`；`observer_live_server.py` 退役桩文案、
`observer-source-architecture.md`（加 2026-10-07 规范修订，并把运行入口从
`python -m http.server 8089 --directory apps/observer/web` 换成 sidecar `--frontend-root`）、
`docs/current/…/skill-references/observer.md`、`WORK-LAB-AUTHORITY.md` §7。

验证（删除之后）：`failfast_group --group observer-web-contracts` commands=1 PASS；
`run_all_tests.js` 绿；`tests/ci/test_failfast_group.py` 绿；
`generate_current_state.py --check-current` CURRENT_STATE_FRESHNESS_PASS；
`verify_blueprint_coverage` 绿；十门电池 **BATTERY_FAILURES=0**；
vitest 与 `tsc --noEmit` 未受影响（未改前端源）。

顺带修一处**我自己记错的可执行性**：`tests/workflow-assistance/test_sidecar_ui_browser_entry.py`
没有做 `sys.path` 前置，靠 gate 的 PYTHONPATH 才能跑，而台账与登记行里把它写成
可直接运行的回归命令——单独运行会 `ModuleNotFoundError: sidecar`。
现按同目录兄弟测试的做法加上 ROOT/sys.path 前置，命令自洽。
**一处未解释的现象保持未知**：加前置后首跑 8 例里 1 例 error，随后连续三次单独运行 8/8 OK
（端口是 `0` 由系统分配，非端口冲突），未定位到原因，记在台账 ERR-122 的 remaining_boundary 里。

U03 到此为**已切换**：生产 UI 只有 `apps/observer/frontend`（Tauri 打包 `dist`，
sidecar `--frontend-root` 只读服务同一份 dist）。本文件的判定表继续作为
"旧断言去哪了"的唯一归属记录，删除内容可由清单 + 历史提交逐字节复核。

