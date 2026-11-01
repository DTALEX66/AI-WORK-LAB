# Game001《异常电梯》V5 夜班协议升级：开发前审计

> 审计日期：2026-07-12
> 仓库：`DTALEX66/MINIGAME`
> 工作目录：`D:\All projects\MINIGAME`
> 范围：仅 Game001《异常电梯》；不扩展合集、第二游戏、皮肤、商城、排行榜或 Unity/Cocos。

## 1. Git 基线

```text
分支：feat/game001-v5-night-protocol
HEAD：31c8a7e6945f5b8dc57d37808ab546b4a374e64d
短 SHA：31c8a7e
提交：fix(game001): fit CCTV art into the fixed monitor viewport
审计前工作树：clean
审计后工作树：clean（本报告写入前）
```

最近关键提交：

```text
31c8a7e fix(game001): fit CCTV art into the fixed monitor viewport
c2a221b feat(game001): replace baked-HUD art and integrate night-shift music
920674b feat(game001): add V5 protocol evidence and contamination foundation
fa8306f fix: remove only baked floor-route text from CCTV artwork
```

## 2. 安装与测试基线

为避免只读审计生成新 lockfile，执行：

```text
npm install --package-lock=false
up to date, audited 1 package
0 vulnerabilities
```

全量测试：

```text
npm test
260 tests
260 pass
0 fail
```

V5 内容校验：

```text
protocols.json: 6 entries
normalShifts.json: 0 entries
anomalies.json: 0 entries
eventChains.json: 0 entries
endings.json: 0 entries
schemas and content containers valid
```

## 3. 当前项目结构

### 核心游戏逻辑

```text
src/
├── actions.js
├── anomalyArchive.js
├── anomalyContent.js
├── archive.js
├── contamination.js          # V5 Phase A 已有
├── evidenceEngine.js         # V5 Phase A 已有
├── events.js
├── game.js
├── gameConfig.js
├── incidentDecision.js
├── protocolEngine.js         # V5 Phase A 已有
├── runtimeSession.js
├── state.js
├── visualState.js
└── content/
    ├── protocols.json        # 6 条
    ├── normalShifts.json     # 空
    ├── anomalies.json        # 空
    ├── eventChains.json      # 空
    └── endings.json          # 空
```

### 正式平台运行时

```text
platform/
├── canvasRenderer.js         # 正式 Canvas UI
├── canvasAssets.js
├── miniGameRuntime.js        # 微信/抖音游戏循环
├── miniGameAudio.js
└── platform.js
```

### 当前 V5 测试

```text
tests/protocolEngine.test.js
tests/evidenceEngine.test.js
tests/contamination.test.js
tests/contentSchemasV5.test.js
```

## 4. 当前正式 V4 玩家流程

当前正式抖音/微信 Canvas 流程仍然是：

```text
启动授权
  ↓
大 CCTV
  ↓
读取画面楼层 / 人数 / 门状态
  ↓
与主控数据比较
  ↓
放行 / 封锁
  ↓
系统自动处置或进入下一班
```

已验证保留的优势：

- 大 CCTV 第一视觉；
- 竖屏单手布局；
- 放行/封锁两个低门槛入口；
- 工业监控风格；
- Canvas Runtime；
- 首三班渐进式教学；
- 无七按钮控制台；
- CCTV 素材无固定楼层答案和烘焙 HUD；
- 常态/异常双轨 BGM 已接入生命周期。

当前限制：

1. 所有班次最终都归结为三字段一致性判断；
2. 玩家没有主动调查步骤；
3. 没有多摄像头空间证据；
4. 没有乘客身份与胸牌核验；
5. 协议系统没有进入正式运行循环和 UI；
6. 班次之间缺少连续事件因果；
7. 错误主要改变分数、稳定度和异常压力，没有改变后续夜班信息结构；
8. 污染度只有数据模块和初始状态，尚未成为可玩的长期后果。

## 5. 已完成的 V5 Phase A 地基

### 5.1 夜班协议

`src/protocolEngine.js` 已实现：

- 每局选择 2—3 条不重复规则；
- 保证至少一条规则对候选班次适用；
- 条件比较与 release/lockdown 结果；
- 输出 `verificationPaths`。

`protocols.json` 已有 6 条初始协议，覆盖楼层、身份、设备、时间和人员。

**缺口：** 尚未生成正式夜班 session；规则未进入 mini-game runtime、CCTV/UI 或班次判定主链。

### 5.2 证据系统

`src/evidenceEngine.js` 已实现：

- 比较楼层、人数、门状态；
- 合并协议冲突；
- 判断前保持中性视觉；
- 检查无音频时是否仍可判断。

**缺口：** 尚无摄像头证据容器、证据发现状态、工具解锁证据、身份证据或事件链证据。

### 5.3 污染度

`src/contamination.js` 已实现：

- 0—100 clamp；
- normal/light/medium/severe 四档；
- 因果历史；
- 视觉干扰和可靠验证路径派生。

`state.js` 已有污染度初始状态。

**缺口：** 未由玩家错误/事件链改变；未进入班次生成、调查工具可靠性、UI、复盘或结局。

## 6. V5 目标对照表

| 系统 | 当前状态 | 证据 | Phase |
|---|---|---|---|
| 夜班协议 2—3 条 | ⚠️ 逻辑地基 | `protocolEngine.js`、6 条协议 | Phase 1 接线 |
| 核心证据比较 | ⚠️ 逻辑地基 | `evidenceEngine.js` | Phase 1 扩展 |
| 调查工具 | ❌ 缺失 | 无 `investigationTools.js` | Phase 1 |
| CAM-01/03/07 | ❌ 缺失 | 当前单 CCTV 状态图 | Phase 1/3 |
| 乘客身份 | ❌ 缺失 | 无 `identitySystem.js` / passengers | Phase 2 |
| 30 异常模板 | ❌ 缺失 | V5 `anomalies.json` 为 0 | Phase 2 |
| 10 正常班次 | ❌ 缺失 | `normalShifts.json` 为 0 | Phase 2 |
| 3 条事件链 | ❌ 缺失 | `eventChains.json` 为 0 | Phase 2 |
| 动态 roundType | ❌ 缺失 | 当前只有 normal/anomaly inspection | Phase 2/3 |
| 动态按钮 | ❌ 缺失 | 当前固定放行/封锁 | Phase 3 |
| 协议条/工具栏/摄像头切换 | ❌ 缺失 | Canvas 无相关入口 | Phase 3 |
| 污染长期影响 | ⚠️ 数据地基 | `contamination.js` | Phase 4 |
| 档案/复盘 | ⚠️ 旧异常时间线地基 | `anomalyArchive.js` | Phase 4 扩展 |
| 结局 | ❌ 缺失 | `endings.json` 为 0 | Phase 4 |

## 7. 架构决策

1. **保留现有 Canvas Runtime，不重构引擎。**
2. **保留大 CCTV 和基础放行/封锁。** 调查、身份、高危时才动态替换按钮。
3. **新增系统必须是纯逻辑模块 + JSON 内容 + runtime 接线。** 不能只画 UI。
4. **每条规则和异常必须具有至少两条可验证路径，音频不能是唯一证据。**
5. **调查工具不能直接返回答案。** 工具只能揭示结构化证据。
6. **污染度不直接决定正常/异常。** 它只改变延迟、设备可靠性和可用查证路径。
7. **事件链状态跨班次保存，但每阶段推进必须由可观察事件触发。**
8. **继续使用自定义 IIFE bundler。** 每个新增模块都必须在 `build.js` 中按依赖顺序注册。
9. **首批 UI 不恢复永久七按钮。** 工具栏最多三个上下文工具，底部按钮由 `roundType` 动态生成。

## 8. 严格开发顺序

### Phase 1：玩法基础

- 补强协议 session 与规则适用性；
- 扩展多来源 evidence 模型；
- 新增 `investigationTools.js`；
- 首版热源扫描、三秒回放、协议查询；
- 工具次数、电力消耗、非唯一答案约束；
- 单元测试先行；
- 不改正式 UI。

### Phase 2：内容系统

- 30 个异常模板；
- 10 个正常班次；
- 5 个乘客角色；
- 3 条事件链；
- 身份系统和事件链引擎；
- 内容/schema/交叉引用测试。

### Phase 3：UI 升级

- 协议条；
- CAM-01/03/07 切换；
- 回放/热源/协议工具栏；
- quick/investigation/identity/highRisk 动态按钮；
- 393×852 与 360×640 官方运行截图。

### Phase 4：留存与后果

- 污染度接入决策后果；
- 跨班次可信度变化；
- 档案与局后时间线；
- 结局内容；
- 错误改变今晚后续班次而非立即结束。

## 9. Phase 1 进入条件

审计结论：**可以进入 Phase 1，但不能重复创建已有协议/证据/污染模块。**

Phase 1 首个 TDD 垂直切片应为：

```text
生成夜班规则
  ↓
创建 investigation 班次证据集
  ↓
玩家消耗一次热源扫描
  ↓
系统仅揭示热源证据，不返回答案
  ↓
证据引擎结合协议与已发现证据给出可验证路径
```

验收门：

- `protocolEngine.test.js`；
- `evidenceEngine.test.js`；
- 新增 `investigationTools.test.js`；
- 全量 `npm test`；
- `npm run content:v5:check`；
- 独立 Phase 1 提交。
