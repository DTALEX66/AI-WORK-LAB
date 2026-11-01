# Game001 V5 夜班协议进度报告

> 更新日期：2026-07-12
> 当前分支：`feat/game001-v5-night-protocol`
> 当前执行策略：玩法与内容优先；视觉、Canvas 布局和 CCTV 素材冻结。

## 总体状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| Pre-Audit | ✅ 完成 | `docs/V5_PRE_AUDIT.md`，基线 260/260 |
| Phase 1 玩法基础 | ✅ 完成 | 协议集合、调查证据、三类工具、多摄像头纯逻辑 |
| Phase 2 内容系统 | ✅ 完成 | 30 异常、10 正常、5 乘客、3 事件链及引用测试 |
| Phase 3 UI | 🔄 进行中 | ui-v5-full 已审计；8 张无文字 CCTV 场景已提取并进入三端资产清单 |
| Phase 4 留存与后果 | ✅ 完成 | 污染后果、高危处置、复盘时间线、5 个结局纯逻辑 |

## Phase 1：完成内容

### 夜班协议

- 保留已有每局 2—3 条协议生成逻辑。
- 新增协议集合评估：只评估对当前班次适用的规则。
- 输出适用协议、违反协议和合并后的可靠验证路径。
- 规则不适用时不会随机改变班次答案。

### 证据系统

- 保留楼层、人数、门状态快速判断。
- 新增调查证据评估。
- 单个工具或单一来源不能直接定案。
- 至少两条独立来源对同一 `conflictKey` 相互印证，才形成可提交的封锁结论。
- 调查阶段输出保持 `presentationTone: neutral`。

### 调查工具

新增 `src/investigationTools.js`：

- `thermal`：每局 2 次，每次消耗 8 电力；只揭示热源证据。
- `replay`：每局 2 次，每次消耗 4 电力；只揭示三秒回放证据。
- `protocol`：不限次数、0 电力；返回当前夜班协议。
- 电力不足或次数耗尽时拒绝执行且不改变状态。
- 返回值没有 `decision` 字段，工具不能成为直接答案按钮。

### 多摄像头逻辑

- 支持 CAM-01 / CAM-03 / CAM-07 由班次内容声明。
- 切换摄像头时只返回该摄像头证据。
- 不可用摄像头会被拒绝。
- 已发现证据按 ID 去重保存。

### 构建链

- `investigationTools.js` 已加入自定义 IIFE bundler 模块顺序。
- 本阶段未接 Canvas UI、未新增永久按钮。

## 修改文件

```text
src/protocolEngine.js
src/evidenceEngine.js
src/investigationTools.js
build.js
tests/protocolEngine.test.js
tests/evidenceEngine.test.js
tests/investigationTools.test.js
docs/V5_PROGRESS_REPORT.md
```

## Phase 1 定向测试

```text
protocol + evidence + investigation tools
14 tests
14 pass
0 fail
```

覆盖：

- 规则影响判断；
- 只评估适用规则；
- 规则提供验证路径；
- 单一工具证据不能直接定案；
- 两条独立来源相互印证；
- CAM 证据隔离；
- 热源扫描消耗次数和电力；
- 回放两次上限；
- 电力不足拒绝；
- 协议查询不消耗资源；
- 工具结果不返回答案。

## 截图

Phase 1 不修改 UI，按用户要求不生成或更新视觉截图。正式截图留到 Phase 3 解冻后执行。

## Phase 1 全量验证

```text
npm test: 267/267 pass
npm run content:v5:check: pass
npm run skins:check: 5/5 valid
npm run douyin:build: pass
npm run douyin:check: 16/17 pass, 1 tourist AppID warning, 0 runtime blockers
```

## Phase 2：内容与连续事件

### 内容规模

- `anomalies.json`：30 个异常模板，人物/数量/空间/时间/设备/动态各 5 个。
- `normalShifts.json`：10 个画面与主控一致的正常班次。
- `passengers.json`：5 个身份角色，包含胸牌、允许楼层、计数方式与核验路径。
- `eventChains.json`：重复乘客、不存在楼层、摄像头替换三条三阶段事件链。

### 身份系统

- 胸牌和目标楼层均参与核验。
- 维修员 `countMode: ignore` 真正改变主控人数计算。
- 身份冲突返回明确字段和 CAM/协议核验路径。

### 内容证据

- 每个异常均声明 `roundType`、六类 `category`、多摄像头证据、热源证据和回放证据。
- 每个异常至少有两条无音频验证路径。
- 30 个异常均引用两个存在的正常变体。
- 正常班次引用存在的乘客；事件链步骤引用存在的班次或异常。

### 事件链

- 每次只推进一个阶段。
- 错误判断写入持久 flags，后续阶段可读取。
- 链结束后按 flags 输出污染增量和后续班次修饰符。

### Phase 2 验证

```text
Phase 2 定向测试：9/9 pass
V5 内容校验：6 个容器全部通过
npm test：276/276 pass
抖音构建：pass
抖音严格检查：16/17，1 个游客 AppID 警告，0 runtime blockers
```

### Phase 2 修改文件

```text
src/identitySystem.js
src/eventChainEngine.js
src/content/anomalies.json
src/content/normalShifts.json
src/content/passengers.json
src/content/eventChains.json
schemas/anomaly-content.schema.json
schemas/normal-shift.schema.json
schemas/passenger.schema.json
scripts/validate-v5-content.mjs
tests/identitySystem.test.js
tests/eventChain.test.js
tests/v5ContentPhase2.test.js
tests/contentSchemasV5.test.js
```

### Phase 2 截图

按用户要求视觉冻结，本阶段不修改 UI，也不生成替代视觉截图。

## Phase 4：后果、处置与复盘（无视觉改动）

### 污染与后续可信度

- 正确/错误决定按内容配置改变污染值，并记录内容 ID 与因果。
- 错误不会直接结束夜班。
- 污染阶段逐步使 CAM-07、主控面板、其他摄像头变为不可靠来源。
- 即使严重污染，仍保留热源和回放两条独立验证路径。
- 污染效果不包含 `isAnomaly` 或 `correctDecision`，不会随机泄露答案。

### 高危处置

新增 `src/highRiskResolution.js`：

- 支持急停、重启、封锁楼层三种上下文动作。
- 动作具有真实电力成本。
- 正确动作结算当前事件。
- 错误动作写入 `nextShiftModifiers`，但 `gameOver` 保持 false。

### 局后复盘与结局

新增 `src/debriefTimeline.js`：

- 合并决定、事件链阶段和污染历史并按顺序复盘。
- 精确统计正确、错误、准确率、污染峰值和事件阶段数。
- 结局按条件和优先级确定，事件链结局高于普通污染结局。
- `endings.json` 已填充 5 个结局：替换信号、第十三层、带回来的夜班、清醒交班、未决记录。

### Phase 4 验证

```text
Phase 4 定向测试：10/10 pass
V5 内容校验：endings 5 entries，全部容器通过
npm test：281/281 pass
抖音构建：pass
抖音严格检查：16/17，1 个游客 AppID 警告，0 runtime blockers
```

### Phase 4 修改文件

```text
src/contamination.js
src/highRiskResolution.js
src/debriefTimeline.js
src/content/endings.json
tests/contamination.test.js
tests/highRiskResolution.test.js
tests/debriefTimeline.test.js
build.js
```

### Phase 4 截图

按用户要求视觉冻结，本阶段不修改 UI，不生成替代截图。

## Phase 3：视觉资产接收（进行中）

资产源：

```text
asset-handoff-hermes-2026-07-12/ui-v5-full
```

执行结果：

- `393x852/` 与 `360x640/` 的 16 张完整 UI 仅作布局参考，未进入运行包。
- `source-gpt-image/` 的整张机柜源图未直接使用。
- 按 `render_ui_v5.py` 的 `SCENE` 坐标只提取中央 CCTV 场景。
- 输出 8 张 720×420、无文字、无 HUD、无机柜按钮的运行时素材。
- 新增可重复生成脚本 `scripts/prepare-v5-ui-assets.py`。
- `platform/canvasAssets.js` 新增 `v5Cctv` manifest、预加载和 `getV5Cctv()`。
- 微信、抖音和 Android WebView 资产同步测试均覆盖新增素材。

验证：

```text
Canvas/资产定向测试：5/5 pass
npm test：281/281 pass
抖音严格检查：16/17，0 runtime blockers
抖音包体：18,141,296 bytes / 20 MB
```

限制：本提交只完成资产规范化和运行时登记；协议条、摄像头标签、工具栏、动态按钮仍须由 Canvas 绘制，禁止整屏贴图。

## 构建作用域隔离：完成内容

### 选择原因

按睡觉循环优先级，`build.js` 的 `CORE_MODULES` 仍把所有去除 ESM 语法后的源码直接拼进同一个 IIFE 词法作用域；后续继续注入 V5 内容与 runtime 模块时，任意模块私有 `const` / `let` / `class` 同名都会让整个小游戏 bundle 无法执行。因此本轮先闭环构建安全性，而不提前接 UI 或调度。

### 实现

- 每个 JS 模块生成独立词法块，模块私有绑定不再共享 `CORE_MODULES` 全局作用域。
- 构建时确定性收集命名导出、默认标识符导出和 `export { ... }`，在模块块结束后提升公开绑定，保持现有按依赖顺序执行的 IIFE 契约。
- 保留 `events.js` 对皮肤隐藏日志函数的构建期别名兼容，同时移除发布检查禁止的 `_getHiddenLog` 残留。
- 新增 bundle 执行回归测试：真实构建抖音包、断言模块隔离结构、在 Node VM 中执行 bundle，并调用 `createInitialState` 与 `createInvestigationState` 验证跨模块导出可用。

### 本轮修改文件

```text
build.js
tests/build.test.js
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：模块隔离/执行测试 0/1 pass（旧 bundle 没有模块词法块）
GREEN 定向：build + Douyin bundle smoke 8/8 pass
回归定向：Android/WebView + WeChat check + build + Douyin smoke 13/13 pass
npm test：282/282 pass
npm run douyin:build：pass，bundle 169.9 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,159,564 bytes / 20 MB
```

### 截图

本轮是构建链纵向切片，不修改 Canvas 布局或视觉，不生成截图；393×852 / 360×640 完整参考图仍仅作验收依据，未作为运行时背景。

## V5 内容确定性注入：完成内容

### 选择原因

构建作用域隔离已由最新提交 `3ec1a3c` 完成，因此按睡觉循环优先级跳到下一项。Phase 2 的六个 JSON 内容容器此前只在源码与校验脚本中存在，正式微信/抖音 bundle 无法读取，阻塞后续 `activeProtocols`、`currentShift` 与 `roundType` 调度。本轮只闭环内容注入，不提前改状态、调度或 Canvas UI。

### 实现

- `build.js` 使用固定容器顺序注入 `anomalies`、`endings`、`eventChains`、`normalShifts`、`passengers`、`protocols`。
- 注入前递归按对象键排序；数组保持策划定义顺序，重复构建输出逐字节一致。
- 六个容器合并为 bundle 内部 `__V5_CONTENT__`，可供后续 runtime 模块直接消费；未引入整屏 UI 参考图或额外视觉素材。
- bundle VM 执行测试验证真实容器规模：30 异常、10 正常班次、5 乘客、6 协议，并检查全部六个容器及重复构建一致性。

### 本轮修改文件

```text
build.js
tests/build.test.js
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：build 定向 5/6 pass；新增内容注入测试因 bundle 缺少 __V5_CONTENT__ 按预期失败
GREEN 定向：build + Douyin bundle smoke 9/9 pass
V5 内容校验：protocols 6、normalShifts 10、anomalies 30、eventChains 3、passengers 5、endings 5，pass
npm test：283/283 pass
npm run douyin:build：pass，bundle 222.0 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,220,534 bytes / 20 MB
```

### 截图

本轮只改变确定性构建数据，不修改 Canvas 布局或视觉，因此不生成截图；393×852 / 360×640 完整参考图仍未进入运行包。

## V5 可回滚夜班状态：完成内容

### 选择原因

前两项构建作用域隔离与 V5 内容确定性注入已分别由 `3ec1a3c`、`fa632fe` 完成。按睡觉循环优先级，本轮选择扩展 `createInitialState`：正式调度前必须先让协议、当前班次、回合类型与调查资源进入统一状态树，并确保现有快照/广告复活不会丢失或浅拷贝这些嵌套数据。

### 实现

- `createInitialState()` 新增独立 `night` 状态，预留 `activeProtocols`、`currentShift`、`roundType`、班次索引、决定历史、事件链状态与后续班次修饰符。
- 复用 `createInvestigationState()` 创建 `investigation`，初始电力与主状态一致，包含 CAM、热源/回放/协议工具和已发现证据。
- 每次初始化均创建独立嵌套对象，避免新局之间共享协议或工具次数。
- 现有 `cloneState`、`saveSnapshot`、`reviveFromAd` 的深拷贝链已用真实嵌套班次/证据验证：失败后的晚到数据不会污染快照，复活后的修改也不会反写快照。
- 本轮只完成状态地基，不提前接调度或 Canvas UI；未引入任何完整 UI 参考图。

### 本轮修改文件

```text
src/state.js
tests/state.test.js
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：state 定向 19/21 pass；新增 night/investigation 初态与回滚测试按预期失败
GREEN 定向：state + investigation tools + build 32/32 pass
npm test：285/285 pass
npm run douyin:build：pass，bundle 222.3 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,220,854 bytes / 20 MB
```

### 截图

本轮只改变可回滚状态树，不修改 Canvas 布局或视觉，因此不生成截图；393×852 / 360×640 完整参考图仍未进入运行包。

## V5 夜班内容调度：完成内容

### 选择原因

优先级 a—c 已由最近三个提交完成；正式 bundle 虽已拥有内容和可回滚状态树，但小游戏启动仍走 V4 空夜班状态。因而本轮选择闭环 `activeProtocols` / `currentShift` / `roundType` 调度，为下一轮原生 Canvas 协议条与 CAM tabs 提供真实、可测试的数据源。

### 实现

- 新增纯逻辑 `nightScheduler`，从 10 个正常班次、30 个异常和 6 条协议中接受可注入随机源进行确定选择。
- 夜班启动固定先产生正常班次；后续班次按 normal/anomaly 交替调度，更新 `shiftIndex`、`shiftKind`、`currentShift` 与 `roundType`。
- 每局生成 2—3 条不重复 `activeProtocols`，保证至少一条对候选内容适用，并把独立副本附着到当前班次，供工具查询和后续 Canvas 绘制使用。
- 切换班次时重置 CAM-01、工具次数和已发现证据，不污染上一班调查状态。
- `createRuntimeSession` / `restartRuntimeSession` 接受 bundle 内 `__V5_CONTENT__`；微信/抖音正式 Canvas runtime 启动与重开均实际初始化夜班调度。
- 内容容器缺失时明确失败，不静默创建空回合；未修改 Canvas 布局，未使用完整 UI 参考图。

### 本轮修改文件

```text
src/nightScheduler.js
src/runtimeSession.js
platform/miniGameRuntime.js
build.js
tests/nightScheduler.test.js
tests/build.test.js
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：nightScheduler 定向 0/1 pass；模块不存在，新增测试按预期失败
GREEN 定向：nightScheduler + runtimeSession + build + Douyin bundle smoke 15/15 pass
npm test：288/288 pass
npm run douyin:build：pass，bundle 225.1 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,223,720 bytes / 20 MB
```

### 截图

本轮只接内容调度和正式小游戏 runtime 数据源，不修改 Canvas 布局或视觉，因此不生成截图；393×852 / 360×640 完整参考图仍未进入运行包。

## V5 原生协议条与 CAM tabs：完成内容

### 选择原因

优先级 a—d 已由最近四个提交完成，正式 runtime 已具备真实 `activeProtocols`、`currentShift` 与 `roundType`，但 Canvas 仍只显示 V4 单条规则且无法切换班次摄像头。本轮因此闭环优先级 e，让调度数据首次成为可见、可交互的原生 Canvas UI，同时保持大 CCTV 为最大表面。

### 实现

- `canvasRenderer` 新增原生 `protocolBar`：从 `state.night.activeProtocols` 读取最多 3 条当前协议并实时绘制；前两班教学期间保留原有上下文提示，不泄露答案。
- 新增原生 CAM-01 / CAM-03 / CAM-07 tabs：只展示当前班次证据实际提供的摄像头，并高亮 `investigation.activeCamera`。
- CAM 点击命中区与绘制布局共用同一数据；正式小游戏 runtime 调用 `switchCamera`，切换后只发现对应摄像头证据，并提供点击音效与轻震反馈。
- 布局为协议条与 CAM tabs 预留独立区域；1334 设计高度下 CCTV 仍至少 520px，并显著大于协议条与相机栏之和。未加入工具栏或永久七按钮。
- 393×852 / 360×640 完整参考图未进入 bundle；所有协议文字、CAM 标签和状态均由 Canvas 实时绘制。

### 本轮修改文件

```text
platform/canvasRenderer.js
platform/miniGameRuntime.js
tests/canvasRenderer.test.js
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：Canvas 定向测试无法导入 getCanvasCameraTabs，0/1 文件通过（缺少原生协议/CAM API）
GREEN 定向：Canvas renderer + runtime + investigation tools 36/36 pass
bundle 回归定向：Canvas + runtime + Douyin smoke 34/34 pass
npm test：291/291 pass
npm run douyin:build：pass，bundle 228.3 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,226,886 bytes / 20 MB
```

### 截图

本轮完成原生 Canvas 结构与交互，但精准双尺寸截图验收属于优先级 h，须在工具、动态动作和协议查询等正式 UI 接线完成后统一执行；本轮不生成不完整验收图。完整 UI 参考图仍仅作布局依据，未作为运行时背景。

## V5 原生工具栏与动态动作：完成内容

### 选择原因

优先级 a—e 已由最近提交闭环；正式 Canvas 已能显示协议和切换 CAM，但玩家仍无法使用 Phase 1 的热源、回放、协议工具，底部也未消费 `roundType`。本轮因此选择优先级 f，将已有调查逻辑接入原生 Canvas，并用上下文动作替换固定控制层，为下一轮分类、高危和复盘主链提供可交互入口。

### 实现

- 新增三枚原生 Canvas 工具：热源扫描、三秒回放、夜班协议；实时显示剩余次数、电力成本和禁用状态，永远不超过三枚。
- 工具点击命中与绘制共用布局；正式小游戏 runtime 调用 `useInvestigationTool()`，同步调查电力、已发现证据和反馈，不直接返回正确答案。
- 底部动作按 `night.roundType` 派生：`quick` 仅放行/封锁，`investigation` 仅标记疑点/进入分类，`identity` 仅放行/拒绝/核验；不恢复永久七按钮。
- 保留首两班引导和第三班独立 quick 判断，修复初版动态动作导致 bundle 教学回归缺少放行/封锁的问题。
- 为工具栏重新分配纵向预算；360px 宽设备上的主要动作高度仍超过 48px，CCTV 保持至少 520 设计像素并继续是最大单一表面。
- 所有工具、读数和动作均由 Canvas 实时绘制；393×852 / 360×640 完整参考图未进入运行包。

### 本轮修改文件

```text
platform/canvasRenderer.js
platform/miniGameRuntime.js
tests/canvasRenderer.test.js
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：Canvas 定向 0/1 文件通过；缺少 getCanvasToolButtons 导出，按预期失败
GREEN 定向：Canvas renderer + mini-game runtime + investigation tools 39/39 pass
教学回归初检：npm test 293/294；动态 roundType 提前替换第三班 quick 动作
修复后 Douyin bundle smoke：3/3 pass
npm test：294/294 pass
npm run douyin:build：pass，bundle 232.1 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,231,061 bytes / 20 MB
```

### 截图

本轮完成工具与动态动作结构接线，但 classification / highRisk / debrief 尚未进入正式交互主链；按既定优先级，双尺寸精准截图留到优先级 h 统一验收，避免提交不完整状态截图。

## V5 协议查询、分类、高危与复盘主链：完成内容

### 选择原因

优先级 a—f 已由最近提交完成；Canvas 虽已显示工具与动态动作，但协议工具仍只有反馈文字，classification / highRisk / debrief 也没有正式业务结算。该缺口会让 V5 在调查阶段断链，因此本轮选择优先级 g，以纯逻辑状态机、原生 Canvas 和正式小游戏 runtime 一次闭环交互主链，不提前进行双尺寸截图精修。

### 实现

- 新增 `nightInteraction` 纯逻辑模块：协议查询覆盖层开关不消耗次数或电力；六类异常分类记录决定并应用污染后果；高危急停/重启/封锁楼层消耗真实电力，错误只写入后续班次修饰符且不结束夜班；局后复盘从真实决定与污染历史生成时间线、准确率和确定性结局。
- 原生 Canvas 新增六类 classification 动作、三项 highRisk 动作，以及协议查询/局后复盘覆盖层；按钮继续按 `roundType` 动态替换，没有恢复永久七按钮。
- 正式小游戏 runtime 接入协议工具覆盖层、进入分类、分类结算、高危结算、下一班调度和 game-over 复盘；业务状态与 Canvas 点击共用正式 API。
- `nightInteraction.js` 加入自定义 IIFE bundle，微信/抖音生成包均已更新并通过真实 VM 启动回归。
- CCTV 布局和既有无文字场景资产未改；393×852 / 360×640 完整参考图仍未作为运行时背景。

### 本轮修改文件

```text
src/nightInteraction.js
platform/canvasRenderer.js
platform/miniGameRuntime.js
build.js
tests/nightInteraction.test.js
tests/canvasRenderer.test.js
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED 逻辑：nightInteraction 定向 0/1 文件通过；模块不存在，按预期失败
RED Canvas：Canvas 定向 0/1 文件通过；缺少 getCanvasOverlayModel，按预期失败
GREEN 定向：nightInteraction + Canvas renderer 31/31 pass
V5 内容校验：protocols 6、normalShifts 10、anomalies 30、eventChains 3、passengers 5、endings 5，pass
npm test：299/299 pass
npm run douyin:build：pass，bundle 241.0 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,240,411 bytes / 20 MB
```

### 截图

本轮完成正式交互主链，但双尺寸精准截图属于下一优先级 h；本轮不提交未经精修的验收图。所有协议、分类、高危动作和复盘文字均由 Canvas 实时绘制。

## 双尺寸 V5 竖屏布局验收与精准修复：完成内容

### 选择原因

优先级 a—g 已由最近提交全部闭环，剩余最高价值缺口是官方 `393×852` 与 `360×640` 双尺寸验收。原布局在 393×852 上把 CCTV 拉到约 425px，超过 handoff 的 360px；在 360×640 上又固定为约 250px，挤压底部区域。该偏差会破坏短屏完整可达性，并使 bundle smoke 的点击坐标与真实动作区漂移。

### 实现

- `getCanvasLayout()` 按两个官方视口锚点计算 CCTV 高度：360×640 为 230px，393×852 为 360px，中间设备线性插值。
- CCTV 仍是最大的玩法表面；没有缩成装饰窗，也没有产生底部空洞。
- 两个视口的反馈区均保持在屏内，主动作实际触控高度均不低于 48px。
- 更新真实 Douyin bundle 点击 smoke，使教学放行/封锁命中新的动作区中心。
- 继续只使用无文字 CCTV 场景；协议、CAM、读数、工具、动态动作和覆盖层均由 Canvas 实时绘制，完整 UI 参考图未进入运行包。

### 本轮修改文件

```text
platform/canvasRenderer.js
tests/canvasRenderer.test.js
tests/douyinBundleSmoke.test.js
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：Canvas 定向 27/28 pass；393×852 CCTV 高度与 handoff 不符，按预期失败
GREEN 定向：Canvas renderer 28/28 pass
Canvas + 可执行 Douyin bundle smoke：31/31 pass
npm test：300/300 pass
npm run douyin:build：pass，bundle 241.3 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,240,678 bytes / 20 MB
```

### 截图验收

本轮运行环境没有可用桌面应用窗口（后台桌面枚举为空），因此未伪造“实机截图”文件。双尺寸几何验收直接以 `UI_V5_DIMENSIONS.json` 的官方像素值驱动可执行布局测试，并由真实 Douyin bundle Canvas 点击 smoke 验证交互命中。视觉截图仍需在安装抖音开发者工具的图形环境中补采；这不影响本轮布局、构建和包体验收门禁。

## 正式 Canvas 双尺寸截图补采：完成内容

### 选择原因

优先级 a—h 的逻辑、接线和几何验收已由最新提交完成，但上一轮因桌面应用枚举为空，仍缺少 `393×852` 与 `360×640` 的真实运行画面证据。本轮选择补齐该最后视觉门禁，并在截图中发现协议长文在短屏横向截断，因此同时闭环一项可测试的精准修复。

### 实现与截图

- 新增 `scripts/v5-canvas-acceptance.html`，直接加载正式 `canvasRenderer` 与正式初始状态，按查询参数生成指定设备尺寸的 V5 classification 场景；它是验收入口，不是第二套 UI。
- 使用 Windows Chrome headless 在 `393×852`、`360×640` 两个官方视口真实执行 Canvas renderer，生成：
  - `docs/screenshots/v5-runtime-393x852.png`
  - `docs/screenshots/v5-runtime-360x640.png`
- 截图确认 CCTV 始终为最大单一表面、反馈区完整在屏内、六类动态分类按钮可读，没有永久七按钮或底部空洞。
- 针对初次截图暴露的协议横向截断，新增确定性短摘要：每条协议保留 9 个字符并加省略号，使两条当前协议在 360px 短屏同时可见；完整协议仍可通过“夜班协议”覆盖层查询。
- 截图只使用正式 renderer 绘制的协议、CAM、读数、工具、分类和反馈；没有把 handoff 完整参考图作为背景。
- 新增 PNG 尺寸回归测试，要求两张运行截图存在且像素尺寸严格为 393×852 / 360×640。

### 本轮修改文件

```text
platform/canvasRenderer.js
scripts/v5-canvas-acceptance.html
tests/canvasRenderer.test.js
tests/v5ScreenshotAcceptance.test.js
docs/screenshots/v5-runtime-393x852.png
docs/screenshots/v5-runtime-360x640.png
wechat-minigame/game.js
douyin-minigame/game.js
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED 截图门禁：0/1 pass；验收入口与双尺寸 PNG 均不存在
RED 协议短屏：Canvas 测试无法导入 getCanvasProtocolSummary，按预期失败
GREEN 定向：Canvas + 截图门禁 30/30 pass
npm test：302/302 pass
npm run douyin:build：pass，bundle 241.7 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音包体：18,241,123 bytes / 20 MB
```

## Identity 状态双尺寸截图验收：完成内容

### 选择原因

优先级 a—h 及 classification 双尺寸截图已完成；进度报告明确剩余最高优先是逐阶段补采 identity / highRisk / protocol-query / debrief。按“每轮一个纵向切片”，本轮先选择 identity：它是尚未有正式截图证据的首个动态动作状态，且三列身份动作在 360px 短屏最容易出现文字或触控区拥挤。

### 实现与截图

- 扩展既有 `scripts/v5-canvas-acceptance.html`，按 `round=identity` 注入确定的身份班次、楼层、人数和反馈；仍直接执行正式 `createInitialState` 与 `canvasRenderer`，没有复制第二套 UI。
- 使用 Windows Chrome headless 在两个官方视口生成：
  - `docs/screenshots/v5-runtime-identity-393x852.png`
  - `docs/screenshots/v5-runtime-identity-360x640.png`
- 目视验收确认：CCTV 在两种尺寸均为最大单一表面；放行/拒绝/核验三项身份动作同时可见；反馈完整；没有永久七按钮、底部空洞或整屏参考图背景。
- 截图回归门禁扩展为四张正式运行图，严格校验 PNG 签名与像素尺寸。
- `.gitignore` 忽略 headless Chrome 的仓库内临时 profile；未删除或修改 `asset-handoff`。

### 本轮修改文件

```text
.gitignore
scripts/v5-canvas-acceptance.html
tests/v5ScreenshotAcceptance.test.js
docs/screenshots/v5-runtime-identity-393x852.png
docs/screenshots/v5-runtime-identity-360x640.png
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：截图门禁 0/1 pass；缺少 v5-runtime-identity-393x852.png，按预期失败
GREEN 定向：Canvas + 截图门禁 30/30 pass
npm test：302/302 pass
npm run douyin:build：pass，bundle 241.7 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音检查口径包体：18,241,123 bytes / 20 MB
```

## HighRisk 状态双尺寸截图验收：完成内容

### 选择原因

优先级 a—h、classification 与 identity 双尺寸截图均已完成；剩余阶段截图中 highRisk 优先级最高。该状态同时承载三项带真实电力成本的处置按钮，360px 短屏最需要确认动作文字、成本和反馈没有拥挤或截断，因此本轮只闭环 highRisk 视觉证据。

### 实现与截图

- 扩展既有 `scripts/v5-canvas-acceptance.html`，按 `round=highRisk` 注入确定的设备异常班次、13 层读数、三名乘客与高危反馈；仍直接执行正式 `createInitialState` 与 `canvasRenderer`，没有复制第二套 UI。
- 使用 Windows Chrome headless 在两个官方视口生成：
  - `docs/screenshots/v5-runtime-high-risk-393x852.png`
  - `docs/screenshots/v5-runtime-high-risk-360x640.png`
- 目视验收确认：CCTV 在两种尺寸均为最大单一表面；急停、重启、封锁楼层三项动作及 15/10/12 电力成本完整可读；反馈未截断；没有永久七按钮、底部空洞或整屏参考图背景。
- 截图回归门禁扩展为六张正式运行图，严格校验 PNG 签名与像素尺寸。
- 未修改或删除 `asset-handoff`；所有协议、读数、工具和按钮继续由 Canvas 实时绘制。

### 本轮修改文件

```text
scripts/v5-canvas-acceptance.html
tests/v5ScreenshotAcceptance.test.js
docs/screenshots/v5-runtime-high-risk-393x852.png
docs/screenshots/v5-runtime-high-risk-360x640.png
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：截图门禁 0/1 pass；缺少 v5-runtime-high-risk-393x852.png，按预期失败
GREEN 定向：Canvas + 截图门禁 30/30 pass
npm test：302/302 pass
npm run douyin:build：pass，bundle 241.7 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音检查口径包体：18,241,123 bytes / 20 MB
```

## Protocol Query 状态双尺寸截图验收：完成内容

### 选择原因

优先级 a—h、classification、identity 与 highRisk 双尺寸截图均已完成；剩余阶段截图中 protocol-query 是当前最高优先。该覆盖层必须在 360px 短屏完整展示当前协议全文和返回入口，同时保持底层大 CCTV 语境，因此本轮只闭环协议查询视觉证据。

### 实现与截图

- 扩展既有 `scripts/v5-canvas-acceptance.html`，按 `round=protocolQuery` 注入确定的调查班次，并设置正式 `night.overlay` / `night.protocolQuery` 状态；仍直接执行正式 `createInitialState` 与 `canvasRenderer`，没有复制第二套 UI。
- 使用 Windows Chrome headless 在两个官方视口生成：
  - `docs/screenshots/v5-runtime-protocol-query-393x852.png`
  - `docs/screenshots/v5-runtime-protocol-query-360x640.png`
- 目视验收确认：底层 CCTV 在两种尺寸均保持最大玩法表面；两条协议全文与“返回监控”按钮完整可读；反馈未截断；没有永久七按钮、底部空洞或整屏参考图背景。
- 截图回归门禁扩展为八张正式运行图，严格校验 PNG 签名与像素尺寸。
- 未修改或删除 `asset-handoff`；协议、读数、工具、按钮和覆盖层继续由 Canvas 实时绘制。

### 本轮修改文件

```text
scripts/v5-canvas-acceptance.html
tests/v5ScreenshotAcceptance.test.js
docs/screenshots/v5-runtime-protocol-query-393x852.png
docs/screenshots/v5-runtime-protocol-query-360x640.png
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：截图门禁 0/1 pass；缺少 v5-runtime-protocol-query-393x852.png，按预期失败
GREEN 定向：Canvas + 截图门禁 30/30 pass
npm test：302/302 pass
npm run douyin:build：pass，bundle 241.7 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音检查口径包体：18,241,123 bytes / 20 MB
```

## Debrief 状态双尺寸截图验收：完成内容

### 选择原因

优先级 a—h 以及 classification、identity、highRisk、protocol-query 的双尺寸截图均已完成；剩余阶段截图中 debrief 是唯一未闭环的正式 Canvas 视觉门禁。本轮按“一轮一个纵向切片”只补采局后复盘，重点验证 360px 短屏中的结局摘要、统计与返回入口。

### 实现与截图

- 扩展既有 `scripts/v5-canvas-acceptance.html`，按 `round=debrief` 注入确定的真实复盘数据形状：8 次判断、75% 准确率、污染峰值 34 与“清醒交班”结局；仍直接执行正式 `createInitialState` 与 `canvasRenderer`，没有复制第二套 UI。
- 使用 Windows Chrome headless 在两个官方视口生成：
  - `docs/screenshots/v5-runtime-debrief-393x852.png`
  - `docs/screenshots/v5-runtime-debrief-360x640.png`
- 目视验收确认：底层 CCTV 仍是最大玩法表面；复盘标题、判断统计、污染峰值、结局摘要与“返回监控”完整可读；反馈未截断；没有永久七按钮、底部空洞或整屏参考图背景。
- 截图回归门禁扩展为十张正式运行图，严格校验 PNG 签名与像素尺寸。
- 未修改或删除 `asset-handoff`；协议、读数、工具、按钮和复盘覆盖层继续由 Canvas 实时绘制。

### 本轮修改文件

```text
scripts/v5-canvas-acceptance.html
tests/v5ScreenshotAcceptance.test.js
docs/screenshots/v5-runtime-debrief-393x852.png
docs/screenshots/v5-runtime-debrief-360x640.png
docs/V5_PROGRESS_REPORT.md
```

### TDD 与真实验证

```text
RED：截图门禁 0/1 pass；缺少 v5-runtime-debrief-393x852.png，按预期失败
GREEN 定向：Canvas + 截图门禁 30/30 pass
npm test：302/302 pass
npm run douyin:build：pass，bundle 241.7 KB
npm run douyin:check：16/17 pass，1 个游客 AppID warning，0 runtime blockers
抖音检查口径包体：18,241,123 bytes / 20 MB
```

## 第 15 轮：抖音真实 AppID 接入与 Lite 模式根因修复

### 选择原因

用户提供正式抖音小游戏 AppID `ttfd408bfd63251fff02`，但开发工具无法修改。实测根因是 `build.js` 每次构建都把 `douyin-minigame/project.config.json` 重写为 `touristappid`，开发工具因而持续处于 Lite/游客模式；手工在工具内修改也会被下一次构建覆盖。

### 实现

- 本地 ignored `release.config.json` 保存正式 AppID，不上传广告配置或账号凭据。
- `build.js` 在存在本地抖音发布配置时，将真实 AppID 同时写入开发工具实际读取的 `project.config.json` 和 ignored `project.private.config.json`；没有本地配置的 CI/其他克隆仍回退 `touristappid`。
- tracked 抖音项目配置更新为用户提供的正式 AppID，开发工具重新编译后游戏成功刷新，未出现 AppID 配置错误。
- 新增回归测试，验证 release config 必须注入主项目配置，防止再次出现“私有配置正确但开发工具仍是游客模式”。

### 验证

```text
build 定向测试：6/6 pass
npm test：302/302 pass
npm run douyin:check：17/17 pass，0 warning，0 runtime blockers
project.config.json AppID：ttfd408bfd63251fff02
project.private.config.json AppID：ttfd408bfd63251fff02
抖音包体：18,241,210 bytes / 20 MB
```

### 工具会话说明

重新编译已成功读取配置并刷新游戏。开发工具标题栏仍显示“退出 Lite 模式”，这是当前开发工具会话状态；原生标题栏需要用户手动点击一次“退出 Lite 模式”或关闭后重新导入 `douyin-minigame`。代码侧不再覆盖真实 AppID。

### 循环终止

本轮为用户指定的第 15 轮。完成测试、提交和推送后停止睡觉循环，不执行第 16 轮。

## V5 声音与震动语义反馈增强

### 真实缺口

V5 工具和动态动作虽然已经可交互，但热源扫描、三秒回放、协议查询和进入分类此前全部复用普通点击音；高危拒绝也缺少震动，玩家无法仅凭声光电反馈区分调查行为和风险等级。

### 实现

- 新增纯函数 `getV5FeedbackProfile()`，集中定义 V5 行为的音效与震动强度。
- CAM 切换：点击音 + 轻震。
- 热源扫描：警戒音 + 中震。
- 三秒回放：电机音 + 轻震。
- 夜班协议：启动提示音 + 轻震。
- 进入身份/异常分类：警戒音 + 中震。
- 分类正确：封锁音 + 中震；分类错误：错误音 + 重震。
- 高危正确处置：封锁音 + 重震；高危错误或动作被拒绝：错误音 + 重震。
- 关闭协议/复盘覆盖层：点击音 + 轻震。
- 复用已有本地短音效，没有新增音频素材或整屏资源。

### 验证

```text
音频 + runtime 定向测试：13/13 pass
npm test：303/303 pass
npm run douyin:check：17/17 pass，0 warning，0 runtime blockers
抖音包体：18,242,347 bytes / 20 MB
```

## V5 身份核验正式结算修复

### 真实缺口

事件链审计发现 `identity` 回合的“核验”此前会直接把 `roundType` 改为 `classification`。正常身份班次没有异常 `category`，因此玩家核验后选择任何六类分类都会被判错；“放行/拒绝”又落入通用电梯动作，未记录夜班决定，也不影响污染或后续班次。

### 实现

- 新增 `verifyCurrentIdentity()`：核验只揭示当前身份班次的 CAM-01 证据，保持 `identity` 回合，不提交答案、不泄露直接判定。
- 新增 `resolveIdentityDecision()`：正常身份期望放行，异常身份期望拒绝；记录 `identity:release/reject` 决定。
- 错误身份判断按内容配置增加污染，但不直接结束夜班。
- Runtime 正式接线 `identityVerify`、`identityRelease`、`identityReject`；结算后调度下一班。
- 身份核验、正确结算和错误结算均复用 V5 语义音效与震动。
- 该修复解除三阶段事件链第一阶段的真实阻塞，不新增永久按钮。

### 验证

```text
night interaction + runtime 定向测试：14/14 pass
npm test：305/305 pass
npm run douyin:check：17/17 pass，0 warning，0 runtime blockers
抖音包体：18,245,075 bytes / 20 MB
```

## 三阶段事件链 Runtime 接入

### 真实缺口

此前 `eventChains.json` 和 `eventChainEngine.js` 只有内容/纯逻辑证据，正式夜班调度没有读取事件链，玩家无法稳定遇到三阶段后续事件。

### 已实现

- `createNightSchedule()` 初始化事件链状态，但首三班教学保持原路径；
- 教学完成后，`scheduleNextNightShift()` 按事件链步骤绑定真实 `contentId`、`roundType` 和步骤 ID；
- 身份放行/拒绝、异常分类、高危处置均通过统一 Runtime 出口推进当前事件链；
- 每个阶段记录正确/错误历史；
- 错误阶段写入事件链 flags；
- 三阶段完成后按 flags 应用污染增量和下一班修饰符；
- 复盘优先读取 `night.eventChainHistory`，并为每条链保留同步的 `history` 视图，确保三阶段不会从局后时间线丢失；

### 验证

- 调度/事件链/身份/Runtime 定向测试：`19/19`；
- 全量测试：`307/307`；
- 抖音严格检查：`17/17`；
- 包体：`18,248,898 bytes / 20 MB`；
- Runtime blockers：`0`。

### 尚未声称完成的部分

当前证据证明的是正式 Bundle 的代码接线、内容绑定和自动化回归；抖音开发者工具现有窗口的完整三阶段人工操作仍需单独验收，不能用自动化测试替代。

## V5 视觉质量修复（审计后第一轮）

### 修复项

1. **CCTV 比例失真**：393×852 下直接铺满造成 1.54× 纵向拉伸，改为 cover 居中铺满——窗口尺寸不变、无黑边、无拉伸，两侧边缘裁切、轿厢主体居中完整。
2. **V5 交接美术首次真正上屏**：`getV5CctvScreenId()` 按回合（quick/investigation/identity/classification/highRisk/protocolQuery）选择 V5 场景图，运动/异常瞬时态回退 24 状态机图。同时修复验收 harness 从未加载真实资产的根因（浏览器无 wx/tt/canvas.createImage，`init` 新增可注入 `options.imageFactory`，发布 bundle 保持零 document/window 引用）。
3. **威胁态红框**：`getCanvasCctvTreatment` 新增 border 色（威胁红/glitch 琥珀/实体紫/稳定绿），修复 strokeStyle=undefined 静默失效。
4. **动态扫描光束**：pending 状态 sweep 覆盖层随可暂停帧时钟自上而下扫过，替代静态横带。
5. **按钮按压反馈**：`noteCanvasPress` + `drawPressShade`，CAM 标签/工具/决策按钮点击后有 180ms 下沉暗化+高亮描边。
6. **协议摘要截断 9→14 字**：保留"必须封锁/不属于异常"等结论子句。
7. **结算页中文化**：failureEyebrow `SYSTEM FAILURE` → `系统故障`。

### 验证

- 双尺寸 10 张截图重新捕获：各回合 CCTV 像素 diff 12.4–35.4（此前为 0，证明 V5 场景真实上屏）；
- canvasRenderer 定向测试 32/32，相关套件 38/38；
- 全量测试 310/310；
- 抖音严格检查 17/17、0 blocker、包体 18,252,234 bytes / 20 MB。

## V5 视觉氛围修复（审计后第二轮）

用户反馈上一轮“没有一点氛围”，复核确认构图缺陷不是素材加载，而是 CCTV 监控层资产只预加载未绘制：`overlay_cctv_frame`、`overlay_scanlines`、`overlay_vignette` 未进入 `drawCctvScene`。

本轮只改 CCTV 表现层：

- 新增 `drawCctvAtmosphere`，将扫描线、镜头暗角、CRT 扫描带、录制红点、`CAM-03 // NIGHT WATCH` 运行时角标和监控角框真正叠到主画面；
- 威胁态使用红色脉冲内框，普通态使用低亮度绿框，状态变化有镜头语义而不是只变按钮颜色；
- 所有氛围层被 CCTV clip 限制，不覆盖协议条、工具栏或决策按钮；
- 保留 cover 裁切与真实 V5 场景图，不回退到程序占位图。

验收：上一版与本版 393×852 截图尺寸一致，128×128 归一化后 27.8% 区域发生变化；全量测试 312/312，抖音严格检查 17/17、0 blocker，包体 18,255,074 bytes / 20 MB。

## V5 夜班协议全量接线（2026-07-27）

### 本轮真实修复

- Runtime 在教学结束时安装事件链首步并创建新的 pending inspection；后续决策和超时才推进事件链，避免跳步或进入不可操作状态；
- quick 回合 `release/lockdown` 使用 decision 分流，身份、协议关闭和判断结果使用独立音频语义；
- debrief ending 使用 `eventChainFlags`，`nextShiftModifiers` 独立保留；
- `duplicate_feed`、`floor_13_bleed`、`unreliable_cam07` 在下一班安装时一次性消费，并转换为可观察的 CCTV visualState；
- 决策、事件链和污染记录开始使用统一 `timelineSequence`；
- V5 `visualState` 接入 Canvas CCTV treatment；`14_duplicate_subject` 通过显式资产 alias 映射到已发布影子主体素材；
- `visual/` 声明为 `v5-visual` subpackage，主包非视觉部分约 2.96 MB，总包约 18.26 MB；构建会清理旧版 `电梯异常` 输出目录；
- 微信构建默认不再生成中文 AppID 占位符，正式 release 仍必须通过私有 release config 注入真实 AppID。

### 本轮门禁证据

```text
npm test                         318/318 pass
npm run douyin:check             17/17 pass, 0 runtime blocker
wechat strict bundle check       8/8 pass, 0 blocker
git diff --check                 pass
wechat total package             18,259,743 bytes
wechat non-visual main portion   2,959,773 bytes
douyin total package             18,259,816 bytes
remote exact SHA                 d3e20b09d62e467fed9d7efd4d5222d49c80e86b
```

本轮提交已推送至 `feat/game001-v5-night-protocol`。自动化证据不替代真实微信/抖音开发者工具和真机人工验收；正式发布仍需真实 AppID、广告位及平台验收。

## 剩余问题

1. 发布仍需真实微信/抖音 AppID 与广告位配置；当前构建产物仅使用游客/开发 fallback，release readiness 应继续 fail-closed。
2. 真实微信/抖音开发者工具、生命周期、InnerAudioContext、触摸和真机视觉验收仍需单独执行，不能由浏览器截图或自动化测试替代。
3. 后续只处理真实 Game001 V5 验收发现，不扩展平台或新游戏。
