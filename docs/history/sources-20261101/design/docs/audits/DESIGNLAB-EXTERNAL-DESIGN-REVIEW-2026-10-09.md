# DESIGN-LAB 外部 design-review runner 首跑与数字对账（2026-10-09）

证据等级：**E2 CONTROLLED_RUNTIME**。固定版本的第三方审计器在真实 Chromium 上跑本仓 committed
bundle，绑定 exact SHA 与产物哈希；不含宿主渲染，不含人工 Jury 判定，不构成 E3。

本轮要做的事只有一件：让"界面是否符合设计标准"这个问题第一次拿到**本仓之外**的读数，
并且把两边的分歧逐条落到规则上 —— 不挑对自己有利的那一个。

## 0. 运行绑定（可复核）

| 项 | 实测值 |
|---|---|
| 被测量提交 | `700ee3fbfe32c2f5e166d8034999d5d07df7694e`（工作区对其 clean） |
| 第三方工具 | `design-review` 插件 `0.1.0`（`~/.qoder-cn/plugins/cache/qoder-marketplace/`，**未 vendored 进仓**） |
| 其依赖（装在本仓 `.project-local/runs/node-libs`） | fast-glob 3.3.3 · yaml 2.9.1 · @axe-core/playwright 4.13.0 · axe-core 4.13.0 · @playwright/test 1.63.0 · playwright 1.63.0 |
| 浏览器 | chrome-headless-shell **v1243 = Chromium 153.0.8010.12**，落到 `.project-local/runs/pw-browsers`（114.6 MiB，本仓自装，未写系统缓存） |
| 被服务的界面 | `bundleOrigin=source`，`served_bundle_sha256=f5eff17ad21bfd2800fbc485f4c5ea1e061a29257c15937e685a7c77117af858` |
| 服务 | 产品自己的 `design_lab.http_service.make_server(ProjectService(synthetic), port=8931, local_session=True)` |
| 命令 | `python scripts/run_design_review_plugin.py`（debt + a11y）· `python scripts/design_debt_baseline.py --check` |
| 原始 JSON | `.project-local/runs/design-review/.design-qa/reports/{design-debt,a11y}.json`；运行台账 `.project-local/task-artifacts/design-review/plugin-run.json` |

复现前先绑 PATH：`D:\All projects\OS External Configuration\10-toolchains\scoop\apps\nodejs-lts\24.18.0`。

### 0.1 一次性 harness 安装（命令，本机两处陷阱都要绕）

```bash
# 依赖装在仓内被忽略的目录里，插件缓存一律不动
npm install --no-audit --no-fund \
  --cache "D:/All projects/DESIGN-LAB/.project-local/runs/npm-cache" \
  --registry=https://registry.npmjs.org \
  --prefix "D:/All projects/DESIGN-LAB/.project-local/runs/node-libs" \
  fast-glob@3.3.3 yaml@2.9.1 @axe-core/playwright@4.13.0 @playwright/test@1.63.0

# 浏览器：必须用「运行期真正解析到的」那份 playwright-core 的 CLI，
# 顶层被提升成 1.64.0 的那一份要的是 build 1248，装上照样启动失败
PLAYWRIGHT_BROWSERS_PATH="D:\All projects\DESIGN-LAB\.project-local\runs\pw-browsers" \
  node ".project-local/runs/node-libs/node_modules/playwright/node_modules/playwright-core/cli.js" \
  install chromium-headless-shell
```

两条不是可选项而是本机事实：`C:\Users\ALEX\scoop` 是指向
`D:\All projects\OS configuration\toolchains\scoop` 的 junction，目标已不存在，
所以 npm 默认缓存目录 `mkdir` 报 `ENOTDIR`（`--cache` 必须显式给可写处）；
`ms-playwright` 系统缓存里只有 1208/1228，没有 1.63.0 要的 **1243**，
所以 build 由本仓自己下到 `.project-local/runs/pw-browsers`（114.6 MiB），
而不是拿别的 Chromium 顶替 —— 顶替就等于把"用 X 引擎测出的结论"写成"用 Y 引擎测出的"。

## 1. 先把 runner 跑起来：两个自证型缺陷

runner 之前"跑不起来"的原因不是网络，也不是缺工具，而是本仓自己写的两件东西：

1. `register.mjs` 是用 printf 拼的字符串，写到 `register('file:///D:/All` 就断了 —— 路径里的空格
   需要的是 percent-encoding，而 encoding 应由 `pathToFileURL()` 生成，不该由手拼生成。
   现在它自己用 `pathToFileURL(join(here,'resolver.mjs')).href`。
2. 修好第一处后仍失败，但报错换了个人：`import { chromium } from '@playwright/test'` 抛
   `Named export 'chromium' not found`。根因在解析钩子：`createRequire().resolve()` 走的是
   **require 条件**，返回 CJS `index.js`，而 playwright 的具名导出是运行期动态挂的，
   `cjs-module-lexer` 看不见。改为把裸标识符交回 Node 自己的解析器
   （`next(spec, {...ctx, parentURL: import.meta.url})`，parent 落在 node-libs 内），
   `exports` 表的 `import` 条件被命中，具名导出就成立了。
3. 顺带一条与本机事实有关的更正：`C:\Users\ALEX\scoop` 是指向
   `D:\All projects\OS configuration\toolchains\scoop` 的 junction，而那个目标目录已不存在，
   所以 npm 默认缓存 `mkdir 'C:\Users\ALEX\scoop'` 报 `ENOTDIR`。缓存根必须显式指到可写处；
   这是机器事实，不改任何工具配置。

另有一条版本陷阱值得写下来：`npm install @playwright/test@1.63.0` 把 `playwright-core` 顶层提升成了
**1.64.0**，而运行期真正生效的是 `playwright@1.63.0` 自带的那份，它要的 build 是 **1243**。
用顶层 1.64.0 的 CLI 去 `install`，下载的是 1248 —— 装完照样启动失败。判定"要哪个 build"必须问
**运行期解析到的那个 core 的 `browsers.json`**，不能问最外层那个。本机 `ms-playwright` 缓存里只有
1208/1228，所以本仓自己下载 1243 进 `.project-local`，而不是拿别的 build 冒充（仓内自有 e2e 门是显式
传 `executablePath` 才用 1228 的，那是另一条路径）。

## 2. 设计债：同一批字节上的三套数字

| 断言 | §36.4 手点（旧） | 外部插件 | 本仓规则（`design_debt_baseline.py`） | 对插件的独立复算 |
|---|---|---|---|---|
| 字面色值 | 18 | 44（hex 28 + functional 16） | **34** | 44（逐格相等） |
| 字面 px | 360 | 602 | **516** | 602（逐格相等） |
| 阴影 | 9「未走令牌」 | 26（`box-shadow:` 全部） | **26 条，其中 18 条已读 var()** → 8 条未走 | 26 |
| Tailwind 任意值 | 未量 | 2 | 不适用（本项目无 Tailwind） | 2 |
| 扫描面 | 只有 style.css 且整块删 `:root` | 8 个文件逐匹配 | 7 个界面源文件逐匹配、删注释、跳令牌声明行 | 同插件 |

三点结论，各自有据：

- **插件的算术可信，语义不可全信。**我用另一套实现（不同正则、不同宿主语言）复算了它的
  674 条 finding，按 (文件 × 类型) 分格比对：**差异格 0**。所以它没有算错。
  但它把注释里的 `13px / 20.15px / #316CFF` 也算成债（px 差 86 处、色差 10 处），
  注释不是样式决策；它的 `tailwind-arbitrary-value` 正则
  `[A-Za-z0-9_:/-]+-\[[^\]]+\]` 撞上的是 TS 正则字符类
  `/bundles/bundle-native-[0-9a-f]`、`/versions/v-[0-9a-f]`（workbench.ts:302），
  **真实 Tailwind 存量是 0，不是 2**。
- **旧存量是手点的，任何规则都复现不出来。**`18` 与「删掉整个 `:root` 后 style.css 的字面色」
  对不上（那条口径是 41 处，去掉 `#fff/#000` 是 26）；`360` 最接近的是同一口径下的
  **按行**计数 345，而不是按匹配 560；`9` 读起来像"未走令牌的阴影"，该口径现值是 **8**
  （26 条 `box-shadow` 里 18 条读 `var()`），而这 8 条里还有 1 条是 `box-shadow:none`
  —— 那是**重置**不是取值债，两边都会把它算成债。真字面阴影债是 7 条。
  契约要当验收标准，就不能留这种数：现在 §4 那句话由脚本产出，
  `design-lab/tests/test_design_debt_baseline.py` 看守"文档说的 = 量出来的"，
  并且带正控制（注释剥离与令牌跳过必须真的让数字变小，否则测试红）。
- **单位不同不是分歧，口径不同才是。**插件按匹配计数、含注释、含 `vite.config.ts`（其贡献为 0）；
  本仓按匹配计数、去注释、只算 7 个界面源文件。两边都写在文档里，谁也不替代谁。

色值这条真正要治的东西，插件和本仓看法一致：44 处色面 finding 里只有 **8 处**是"复述了
`:root` 已声明的令牌"（其中 **3 处是 `#316CFF` 本身**，即 `--color-primary` 被重新打字了一遍），
剩下 **36 处是契约不认识的 off-palette 色**，头部就是契约 §3 点名的"差不多蓝"：
`#1D4FC4`×5、`#2A63D8`×4、`#2563eb`、`#3c8aff`、`rgb(37,88,219)`，外加一组状态色影子
`#c03030 / #8f2a2a / #27c86a / #11a74d / #f2b541 / #c98c00 / #f87171 / #ee5f5f`。
清理顺序因此明确：先消灭 3 处主色字面量，再收"差不多蓝"。

## 3. 可访问性：0 violation 不等于已验证

插件的 `audit-a11y.mjs` 扫了 design.qa.yaml 里的 16 屏（12 路由 ×1440×900 + 4 屏 390×844，
`reducedMotion: reduce`），产出 **16 scans / 0 findings / ok=true**。

这个"0"如果不加限定就是造假，所以我用自己的探针（同一服务、同一 bundle、同一 build、同一版 axe）
把它丢掉的那一半读回来：

| 屏 | axe 判定的 contrast 节点 | **未判定（incomplete）** | 未判定原因（axe 原话） |
|---|---|---|---|
| workbench | 28 | 71 | `background color could not be determined due to a pseudo element` |
| dashboard | 22 | 55 | `... due to a background gradient` |
| projects | 22 | 35 | `... due to a background gradient` |
| settings | 22 | 36 | `... due to a background gradient` |
| evidence @390 | 22 | 9 | `... because it is overlapped by another element` |

即：**每屏有 9–71 个文本节点 axe 根本没评**，而它评的部分没有违规。对比度在本仓只能由
`design-lab/tests/e2e/audit_workbench_contrast.mjs`（自己按 used-value 上溯背景）负责 ——
这也正是 DESIGN.md §3.1 那条 4.45:1 红线的来源。把 axe 的 `ok=true` 当"对比度已验证"就是
本仓最忌讳的那类假绿。

两条新覆盖（本仓自有门不回答的问题）：

- `aria-allowed-role` 对 `#drawer` **每屏未判定 1 处**：`aside.drawer#drawer role="dialog" aria-modal="false"`
  （shell.ts:5138）。`aside` 的隐式角色是 `complementary`，HTML-AAM 不允许它直接改挂 `dialog`，
  而它同时又不是模态的。仓内已有守卫只查抽屉的**行为与几何**
  （`audit_workbench_ui.mjs` 的 `nav-drawer`：起始 `aria-expanded=false`、关闭态可达项数、开启态；
  `test_workbench_sidebar_pinning.py` 的 `position:fixed`），**没有任何一处检查角色合法性** ——
  这是一块真实盲区，不是一个新阈值。改法有两种（`<div role="dialog">` 或保留 landmark 去掉 role），
  属界面决策，本轮只落档不擅改。
- `skip-link` 未判定 1 处：`Skip link target should become visible on activation` —— 探针不激活链接，
  所以 axe 只能说"没看"。本仓的键盘可达性门覆盖的是焦点顺序，不覆盖"激活后目标是否可见"。

同时，扫描确实量到了认证后的界面而不是登录墙：每屏 `#login` 不可见、`#route-view` 存在、
313–380 个元素、`#connection` 徽标为 `本机已连接`。这条证明是本轮自己要求的，因为插件只会
`goto + waitForSelector`，不会打字。

## 4. 与仓内已提交产物的对照（含一处口径警告）

`docs/UI-CONVERGENCE-20260930/ui-audit/report.json`（本仓自有 UI 门的 committed 产物）：
`ok=true`、`violations=0`、65 项 metric、5 个宽度 × 12 路由 + 冷启动/断连态。
**它绑的是 `05d6d761`，不是本轮的 `700ee3fb`** —— 拿一份别的提交的已存产物当"当前状态"是本仓
反复犯过的错，这里只做方法学对照，不当复验。

两侧范围也不同，且这解释了为什么两边都是 0：本仓门会先创建一个真实项目再测（有数据的视图），
外部插件只做导航（认证后空态视图）。两种状态都值得测，本轮补上的是后者。

## 5. 本轮落进仓里的东西

- `design.qa.yaml`（根，插件原生入口）：扫描面、16 屏、输出目录、debt 阈值；端口写死并在被占时拒绝运行。
- `scripts/run_design_review_plugin.py`：驱动两个审计器；缺 node/插件/钩子/端口占用一律
  `DESIGN_REVIEW_BLOCKED` 退出 3，绝不静默少测；bundle 与 HEAD 有差异时拒绝测量。
  它是测量工具，**不是 CI 门**（未接入聚合，避免把外部工具的口径变化变成仓内红灯）。
- `scripts/design_debt_baseline.py` + `design-lab/tests/test_design_debt_baseline.py`：
  契约存量数字的产出者与看守者（含"排除项必须真的有效"的正控制）。
- `DESIGN.md`：frontmatter 补 `externalRunner` 与 `measuredDebtBy/AtCommit`；§4 存量改为规则产出句；
  §6 更正"runner 仍没跑起来"的旧陈述，并把分歧去处写明。
- `docs/INDEX.md` §6：新增三条放置约定（契约存量数字、外部工具的入仓面、其产物不入仓）。

本轮跑过的判定（均为实测产物）：
`VERIFY_DESIGN_LAB=OK total=69 failed=0`；
`BOUND_TEST_RUN=OK tests=4 failures=0 errors=0 skipped=0`（`--modules test_design_debt_baseline`）；
`--modules test_gate_reachability … OK`（新增脚本未成为孤儿门）；
`REPO_CLASSIFICATION=OK`＋`DRIFT_NOTICE`（工作区 60.22→60.27 MiB，提交后需重绑投影）；
CI `700ee3fb`：Python gate / strict-TS / Authority / DeepSeek chain / wheel+launch / MiniGame /
Open Design / generated-artifact **全部 success**，仅 2 个**产物上传步骤**红
（`License & secret hygiene gate :: Upload secret history report`、
`Workbench browser E2E :: Upload E2 evidence artifact`），原因是 GitHub Actions
**artifact 存储配额已用满**，属 owner 侧清理项，不是测量失败。

## 6. 仍未闭口（不代签、不代决策）

1. **owner 裁决**：DESIGN.md 主色 `#316CFF` 红线（改色 vs 改用法）、2 份 sidecar 签字、
   3 个 REQUESTED 包、投影是否继续嵌 run_id。
2. **owner 侧运维**：Actions artifact 配额（删除远端产物不属我的授权范围）。
3. 新落档的可治项：3 处主色字面量改 `var(--color-primary)`（需重建并提交 bundle，走 Build Output Truth）；
   36 处 off-palette 色按 §2 顺序收；`#drawer` 的角色合法性；
   对比度仍只有本仓一处证据，axe 无法接手。
4. 界面对标（Figma/Blender/Illustrator/Linear/Raycast 真实参考屏 + CSS/DOM 双层比对）本轮**未做**，
   它是 design.qa.yaml 之外的另一件事。

---

## 7. 追正（同日第二批）：上面有三处要说错的地方，以及据此做掉的真实清理

规则：**已入账的数字不改写，追正另立新段**。本节取代 §2 表里「本仓规则」一列与 §6 的第 3 条。

### 7.1 我说「3 处主色字面量待消灭」——这句是错的，实测为 0

`#316CFF` 在 style.css 里出现在第 2、14、167、671 行：**14 行是令牌定义本身**
（`--color-primary:#316CFF;`），2/167/671 全在注释里。插件报的 3 处正是那三条注释。
所以主色**没有任何重复字面量**，清理顺序里排在第一的那件事不存在。
这也是「按次清理」必须先落到 file:line 而不是落到计数的原因——于是它现在落到了：
`design-lab/config/ui-off-palette-colours.json`，26 行逐条带 file/line/value/kind/declaration，
`adjudication` 是 owner 专用字段（脚本重写必须保留它，测试看守），新增一处字面量即门红。

### 7.2 我自己的规则里有两处假债，已修

- `box-shadow:none` 被当取值债计数：实测 2 处（style.css:1355、1357），**阴影存量 26 → 24**。
  重置不是发明一个 elevation。测试直接断言 `RESET_VALUE` 认 `none`/`inherit` 而不认
  `0 4px 18px rgba(0,0,0,.35)`，并且 `shadowResetsSkipped > 0`，防止该分支从未被走到。
- 中性 alpha 与有色相字面量混在一个数里，导致「色值存量」无法指导行动。现分两类：
  `rgba(0,0,0,α)` / `rgba(255,255,255,α)` 记为 neutral-alpha（遮罩、阴影、状态层），
  其余记为 chromatic。追正后一次实测：**26 = 13 chromatic + 13 neutral-alpha**。

另有一条实测后**没有**加进去的机制，写明以免下轮重犯：行尾 `//` 注释里是否有漏网的字面量？
对整个扫描面量得 **0 处**，所以注释规则保持在保守的「整行」形式，不引入会啃掉字符串里
`https://` 的引号感知切分。

### 7.3 做完的清理：8 处字面量变成令牌引用，像素逐处实测未变

| 改动 | 处数 | 像素未变的证明（真实 Chromium，服务的是 `style.css` 本体） |
|---|---|---|
| 三处相同的 `linear-gradient(135deg,#1D4FC4,#2A63D8)` → `var(--brand-gradient-from/-to)`（新令牌在 `:root` 声明，值即原端点） | 6 | 计算值 `linear-gradient(135deg, rgb(29, 79, 196), rgb(42, 99, 216))` |
| `rgba(13,18,33,.85)` → `color-mix(in srgb, var(--color-surface) 85%, transparent)` | 1 | 计算值 `color(srgb 0.0509804 0.0705882 0.129412 / 0.85)` ≡ `rgba(13, 18, 33, .85)` |
| `rgba(75,175,255,.45)` → `color-mix(in srgb, var(--color-secondary) 45%, transparent)` | 1 | 计算值同上，等于 `rgba(75, 175, 255, .45)` |

探针第一次报的 `DOES-NOT preview scrim` 是**探针缺陷**不是产品缺陷：Chromium 把解析后的
`color-mix` 序列化成 `color(srgb …)` 而把字面量序列化成 `rgba(…)`，拿字符串比等于比语法。
改成按 8-bit 通道解析后比较（容差半级），三处全部 EQUAL，最大通道差 0.13/255。

**没有顺手改的两类**，因为它们需要的是判断而不是机械替换：`.tag.ok/.warn/.bad/.danger`
四组状态渐变（786–789、683：`#27c86a/#11a74d`、`#f2b541/#c98c00`、`#f87171/#ee5f5f`、
`#c03030/#8f2a2a`）与棋盘格纹理 `#1a2231/#222c3e`。算术上先否掉了一条"顺手"路子：
`#1D4FC4` **不等于** `color-mix(in srgb, #316CFF X%, black)` 的任何单一 X
（R 需 0.592、G 需 0.731、B 需 0.769 三个不同比例），和 `--color-bg` 混也凑不出单一比例——
也就是说这些蓝是独立取值，替换就必然改像素，属于 §3.1 那条待 owner 裁的红线范围。
它们现在逐条在登记册里等人裁决，而不是在文档里当一句口号。

### 7.4 本轮判定（实测产物）

`DESIGN_DEBT literal_colors=26 literal_px=516 shadow_declarations=24 shadow_reading_var=18
shadow_resets_skipped=2 chromatic=13 neutral_alpha=13`；`DESIGN_DEBT_BASELINE=PASS`（含
`PENDING-OWNER-ADJUDICATION count=26` 这条 NOTICE，它不是红灯：裁决是 owner 的活）；
`TOKEN_PIXEL_FAILURES=0`；`COLOUR_EQUIVALENCE_FAILURES=0`；
`BOUND_TEST_RUN=OK tests=65 failures=0 errors=0 skipped=0`
（`--modules test_workbench_css_single_definition test_design_system_tokens
test_workbench_brand_asset test_design_debt_baseline test_workbench_packaging`，subject `8e63c6be`）。
本轮**没有**重跑界面几何门，理由写明：改动被逐处证明为像素与布局中立（计算值相同），
几何断言无变量可动。

## 8. §3 新增加的一条：`#drawer` 的角色合法性（已修，逐处实测）

原码 `apps/workbench/shell.ts:5138` 是 `aside.drawer#drawer role="dialog" aria-modal="false"`。
两处自相矛盾：ARIA in HTML 不允许 `aside` 改挂 `dialog`；而这个面板不模态——没有焦点约束，
背后页面照常可用。axe 因此在**每一屏**都把 `aria-allowed-role` 记成"未判定"而不是通过。
本仓此前没有任何门问"这个角色这个标签合不合法"：已有的抽屉守卫测的是行为与几何
（`aria-expanded` 起始 false、关闭态可达项数、`position:fixed`）。

改法取"它本来就是补充性区域"：`<aside>` 保留隐式 `complementary`，删掉 `role`/`aria-modal`，
`aria-label="工作区详情"` 原样留着（删角色不许顺手删掉名字，否则变成无名 landmark）。

| 检查 | 改前 | 改后（同一探针、同一服务、committed bundle） |
|---|---|---|
| `aria-allowed-role` 未判定 | 每屏 1 处（`#drawer`），5/5 屏 | **0 处** |
| axe passes（通过规则组数） | 40 / 35 / 37 / 35 / 32 | 40 / 35 / 37 / 35 / 32（未变） |
| 判定的对比度节点 | 28 / 22 / 22 / 22 / 22 | 28 / 22 / 22 / 22 / 22（未变） |
| `color-contrast` 未判定 | 71 / 55 / 35 / 36 / 9 | 71 / 55 / 35 / 36 / 9（**没被这次改动解决，仍是缺口**） |
| bundle 里 `dialog` 字面量 | 2（drawer + 命令面板） | 1（只剩命令面板，`div[role=dialog]` 合法） |
|  served bundle sha | `f5eff17a…` | `0c3f7dc7795094764612c6c5703d66d37f9de92cd55c6a3d804861b945b5ed64` |

看守落进已接入 CI 的 `design-lab/tests/e2e/audit_workbench_ui.mjs`（新增 `role-permittedness`：
landmark 挂 dialog 即红、`#drawer` 不在文档里即红——缺席不算通过、`#drawer` 丢名字即红）。
断言被证伪过才有意义：`role_predicate_falsification.mjs` 在同一页面上先读 CLEAN
（`matches=[]`、`drawerRole=null`、名字仍在），再把 `role="dialog"` 种回去，选择器读出
`["aside#drawer[role=dialog]"]` → `ROLE_PREDICATE_FALSIFICATION=OK`。

本轮判定：`AUDIT_SCOPES 39 violations=0 ok=True`（`scripts/audit_workbench_ui.py`，
输出写到 `.project-local/.../workbench-ui-audit-rolegate.json`，不去改那份绑在 `05d6d761`
的已提交报告）；workbench 三个 vm 契约套件 `unit/appshell/shape-notice-coverage` 全 0；
`tsc --noEmit` 0；`vite build` 0（bundle 与源码同提交，否则 UI 门自己会拒绝测量）。
重跑全套没有理由，因此没跑：改动面是一个属性删除 + 一条门内断言，CI 的 Python gate
会在 exact SHA 上给全套结论。

## 9. 对比度：先追正我上一轮写错的一句，再修本仓门的真实盲区

**追正（先于一切）**：我在 8 节之后给下一轮的口述里写过"本仓的对比度门每屏只能判 22–28 个节点"。
那句把 **axe 的**判定数当成了**本仓门**的判定数。实测：`audit_workbench_contrast.mjs`
在 24 个 路由×宽度 组合上判了 **2461** 个文本运行（单路由 21–92，research 一屏 698），
而 22–28 是 axe 自己每屏肯判的量。两边都不该拿对方的数字当自己的覆盖率。

### 9.1 门里真正存在的洞：它读不懂 `color(srgb …)`

`parse()` 只认 `rgb()/rgba()`。而 Chromium 把解析后的 `color-mix()` 序列化成
`color(srgb r g b / a)` —— 本仓 style.css 里本来就有若干 `color-mix()`，我上一轮又加了 2 处。
真实页面实测（探针 `contrast_parser_gap.mjs`，服务的是 committed bundle）：

| 量 | 实测 |
|---|---|
| 页面自有文本节点 | 2688 |
| 前景色读不懂 | 0 |
| **坐在 `color(srgb …)` 背景上的文本节点** | **73** |
| 伪元素层里出现 `color(srgb …)` | 24 |
| 渐变值内含 `color(srgb …)` 端点 | 12 |

背景层读不懂就会被当成不存在：那 73 个节点被拿去对着**页面画布**判对比度，而不是对着
它们真正的遮罩。这不是保守，是假绿。

修法两件事一起做：
1. `parse()` 认 `color(srgb …)`（0..1 与百分比两种写法）；
2. **读不懂就红**：任何页面计算出的颜色若解析失败，计入 `unparsable` 并拒绝通过 ——
   不是记为 0，不是跳过。哨兵也种进门里：每条路由临时插一个"白字 + `background:color(srgb 1 1 1)`"
   的节点，1:1 必须被判为违规；判不出来就说明门瞎了。

实测（`run_contrast.py`， widths=1440,390）：`checked=2461 belowAA=0 pseudoLayers=1852
unparsable=0 controlMisses=0`，`CT_MARGIN tightest=4.11 need=3`。
证伪（`falsify_contrast.py`：把源码复制到忽略目录、只把 `/^color\(` 改成 `/^COLORX\(`，
先 `node --check` 确认故障副本语法有效）：12/12 路由 `CONTROL-MISSED`、`unparsable=144`、
退出码 1。也就是说这个控制**能红**，它的绿才有意义。

### 9.2 我自己引入过的一个新错：把 3px 指示条当成整块背景

第一版我把"渲染中的伪元素背景"一律加入背景层候选。结果是门报出每条路由一个 2.21:1 违规。
量过之后才知道是我的建模错了：活动导航项的 `::before` 是 `3px×25px`、`left:-4px` 的指示条
（探针 `nav_paint_behind_label.mjs` 读出 `elementFromPoint` 命中标签自身、
按钮背景为 `color(srgb 0.0666667 0.0941176 0.164706 / 0.68)`，实测 17.2:1），
文字根本不落在那条亮蓝渐变上。把不可能的背景放进候选集，正是本文件早已写下要避免的那类 bug。

改成：伪元素层只有在其解析出的盒子覆盖宿主 ≥60% 时才进入候选（全屏遮罩是 `inset:0`，指示条不是）。
实测差异：故障副本的非控制违规 11 → 0，正确副本始终 0。

### 9.3 现在这门能说什么、不能说什么

能说：文本自身、祖先链、渐变端点、`color-mix()` 遮罩、祖先透明度合成都算进去了，
读不懂的颜色一律红。不能说：**无关元素的重叠**（axe 第三类 decline 原因）与只覆盖局部的
伪元素仍不在模型内 —— 这条限制写在代码注释里，不留成口头保证。
CI 侧看守加了两条断言（`test_workbench_contrast_gate.py`）：`controlMisses==0`、
`unparsable==0`；本地实测该模块 `Ran 2 tests … OK`（57.6s）。

## 10. 层级表补上了（DESIGN.md §2 记的那条缺口）

§2 原文："z-index 目前 12 处且无层级表 → 新增层层必须先进表再使用"。这句话此前没有任何东西检查。
本轮实测：`style.css` 里 **12 处声明、11 个不同值**（注释里提到的 `z-index:65`/`z-index:20` 是历史叙述，
不计入 —— 计数前先把注释抹平，这条也写成了测试），全部换成命名令牌：

| 令牌 | 值 | 承载规则（实测） |
|---|---|---|
| `--layer-canvas-grid` | -3 | `.grid-bg` |
| `--layer-canvas-ambient` | -2 | `.ambient`(+伪元素) |
| `--layer-flow-figure` / `--layer-flow-node` | 0 / 2 | `.flow-svg` / `.node` |
| `--layer-topbar` | 50 | `.dl-shell > header` |
| `--layer-nav-rail` | 60 | `.app-nav` |
| `--layer-drawer` | 88 | `.drawer`、`.sidebar` |
| `--layer-scrim` / `--layer-palette` / `--layer-toast` | 90 / 95 / 110 | `.overlay` / `.palette` / `.toast` |
| `--layer-skip-link` | 200 | `.skip-link` |

真页面回读（`layer_resolve.mjs`、三档视口）：除 `.sidebar` 外全部按表解析；
`.sidebar` 的 88 只在 ≤840px 生效（实测 820→88、390→88、1440→`auto`，那里它是 sticky 列，
本来就不需要层级）。**没改任何数值**，所以层序与渲染不变。

两条真实收获，都不是"表建好了"本身：

1. **验自己的解析器被测试当场抓住两次**。第一版 `TOKEN_DECL` 以行首锚定，紧凑写法
   `:root{--a:1;--b:2}` 下第二个令牌读不到，于是凭空报 `UNDECLARED-TOKEN` + `TABLE-STALE-LAYER`；
   改成"分隔符锚定"后又踩到正则匹配不重叠的坑（吃掉前一个 `;` 就看不见下一个声明）。
   现解法是先取 `:root{…}` 块再在块内配对，测试同时钉住两种写法。
2. **两处疑似死样式**：`.flow-svg`/`.node` 在 12 条路由 × 1440/820/390 的真实 DOM 里从未出现。
   本轮不删（删除要判断，且这两层所属组件可能是待接回的功能），但把它们钉在表的 `note` 字段里，
   `--write` 重新生成时保留人工/实测字段，只重算值与选择器。

门与看守：`design-lab/scripts/verify_ui_layering.py`（已进聚合，`total=69 → 70`），
拒绝裸数字、未声明令牌、表值漂移、失效行、选择器归属漂移、没人解释的层；
`design-lab/tests/test_ui_layering.py` 11 项里 7 项是**种出来的故障**（每条分支各一种），
另有空集正控制，防止"分支从未走到"。实测：`UI_LAYERING=PASS declarations=12 layers=11
values=[-3,-2,0,2,50,60,88,90,95,110,200]`，`Ran 11 tests … OK`，
`DESIGN_DEBT_BASELINE=PASS`（债存量未受影响：26 / 516 / 24），`test_gate_reachability OK`。

## 11. 重叠：量完之后，这一格既不是缺口也不是免费的答案

上一轮把 axe 的第三类拒绝（`overlapped by another element`）当成"本仓模型的缺口"列进了计划。
真去量之后这个说法要分两半，而且我第一版实现自己造了一个假违规。

**实测**（`overlap_census.mjs`，12 条路由 × 1440/390，命中测试用 `elementsFromPoint`）：
2461 个文本运行里，**只有 1 处**的像素被非祖先元素占据 ——
390 宽下 `p.eyebrow :: 02 / VERIFIED READBACK` 被 `nav.app-nav` 压住，而 `app-nav` 是**不透明**的（a=1）。
不透明遮住的文字看不见，WCAG 1.4.3 管的是"看得见文字"的对比度，所以这不是对比度失败；
"该不该被遮住"是几何门的活。因此现在它被单列为 `obscured` 计数并跳过评分，
既不记成通过也不记成失败。

**我第一版把这条做错了，被自己的数字抓住**：那次 `belowAA=1`、`CT_MARGIN tightest=1`，
报的就是这个 eyebrow。原因是我把外来元素的**渐变第一个色标**当成整块不透明蒙版 ——
和上一轮 3px 指示条同一类错（不可能存在的背景进候选集）。修正两条：
不透明外来元素 → 算 obscured 不评分；半透明外来层 → 只有它的盒子真的罩住文本盒才参与合成。

**半透明那一格必须能被证明工作**：于是加了第三个控制，放在**自己的文档**里
（`CT_VEIL_CONTROL`）——白字底下深色，上面盖一层 `rgba(255,255,255,.92)`。
放进真实页面是不行的：控制件必须在视口内才拿得到命中测试，而把它盖在 UI 上就会污染要量的东西
（第一版正是这样，控制件在 `left:-10000px`，命中测试永远看不到它，于是"控制没被抓到"其实是控制没在场）。
实测输出：`CT_VEIL_CONTROL caught=yes coveredForeign=1 ratio=1.18`（1.18:1 < 3:1，红得对）。

最终一轮（widths=1440,390）：
`CT_SUMMARY checked=2460 belowAA=0 pseudoLayers=1852 coveredForeign=0 obscured=1 unparsable=0
controlMisses=0 strict=1 mathChecks=4 mathBad=0`，`CT_MARGIN tightest=4.11 need=3`。
CI 侧 `test_workbench_contrast_gate.py` 新增三条断言（`controlMisses==0`、`unparsable==0`、
`CT_VEIL_CONTROL caught=yes` 且 `obscured` 字段存在），`Ran 2 tests … OK`（57.3s，1440/1920）。
