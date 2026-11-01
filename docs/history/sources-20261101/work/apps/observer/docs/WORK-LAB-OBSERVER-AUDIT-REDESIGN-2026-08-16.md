# WORK-LAB Observer 全量审计与重设计任务包

状态：本地副本审计与安全修复草案，不代表已写入云端

审计基线：`DTALEX66/WORK-LAB@fadcded4c4db8d6e1543e078b67cb746f0159a1f`

范围：`packages/client-neutral-core`、`apps/observer`、
`config/project-platform-map.json`、v3 Snapshot、SSE、Web/Tauri 只读壳。

## 1. 结论

当前仓库已经有 v3 Snapshot、loopback GET、SSE、SQLite WAL、项目 allowlist
和只读前端，但“Command Center 2.0 已完成”的结论过早。当前产品仍是控制面原型：

- 数据链已经比历史版本可靠，但存在会把其他项目显示成 WORK-LAB、把真实 Token 隐藏、把未知显示成 0 的问题；
- v2/v3、旧 renderer、旧事件模型、inline fixture 同时存在，增加漂移面；
- Observer 文档、CURRENT_OBSERVER_AUDIT、COMMAND_CENTER_2_VALIDATION 的基线 SHA 与当前主线不一致；
- 视觉层过去是多个设计语言叠加，Light 主题没有真正的 Command Center token，布局是“卡片堆叠”而不是执行观测台；
- 没有浏览器截图/真实 Tauri 回归证据，不能把“测试通过”当成“好看、准确、可用”。

成熟度判定：`Prototype / controlled local canary`，不是正式可用产品。

## 2. 已确认的 P0/P1

### P0 — 必须先修

1. **跨项目 Git 串值**

   `composition_root._git_state()` 原来取第一条 `scope=git` 记录并作为全局
   `git_state` 传给每个项目。多项目时会把一个项目的 branch、HEAD、dirtyCount
   渲染到所有项目。

2. **Token 字段在适配器中丢失**

   `api.normalizeV3()` 输出 `usage`，而 Command Center 读取 `tokenSummary`，因此
   真实 Token 存在时仪表盘仍会显示无样本。

3. **有效 v3 快照可能不进入 last-good**

   `state.accept()` 过去要求 v2 `summary.registeredProjects` 才保存 last-good，
   合法的 v3 零项目快照可能被丢弃，界面随后表现为冻结或 OFFLINE。

4. **伪 0 破坏数据质量语义**

   Data Trust 将 `malformed`、`dropped` 写死为 `0`；coverage 缺少 numerator 时
   使用 `|| 0`。未知必须是 `—/UNKNOWN`，只有 canonical 明确观测到 0 才能显示 0。

5. **平台观测表每轮无界增长**

   `platform_collector` 每次用随机 UUID 写入 `platform_observations`，UPSERT
   永远命不中。重复行会膨胀 SQLite，并让查询顺序成为隐含真值。

6. **第二事件写入面仍在仓库中**

   `10-workflow/.../observer_event.py`、`30-observer/src/observer_runtime.py`
   仍提供 append/event-log/projection API，且仍被测试和迁移脚本引用。它们不能继续
   被描述成“已退休”而不从权威路径、测试入口和文档中移除。

### P1 — P0 后立即处理

- `activityState` 与 execution state 语义混用；项目注册状态不能代表正在运行；
- `sourceRefs` 主要来自 execution，Git/CI/usage/provenance 不完整；
- `project-platform-map.json` 是静态映射，不等于运行时事实，应标明 `CONFIGURED`
  与 `OBSERVED` 两层；
- v3 SSE history 只在内存中，重启后依靠整快照恢复，需将 cursor/resync 语义写入
  明确的协议测试；
- inline v2 fixture 与 v2 `live-snapshot.json` 易被误认为真实数据，必须成为显式
  `FIXTURE` 开发入口，不能作为生产 fallback；
- 旧 `render.js`、`render-v3.js`、v2 schema 仍在生产树，需隔离为 legacy test-only；
- Full/Compact 仍共用同一信息结构，Compact 不是独立的监控 HUD；
- 没有真实浏览器截图、Light/Dark 对照、Windows WebView2 回归证据；
- Tauri 使用嵌入静态 Web，Web 改完而不重新构建 Tauri 会产生版本错觉。

## 3. 本地副本已经完成的安全热修

以下修改只存在于本地审计副本，未 commit、未 push、未改云端：

- Git projection 改为按 `project_id` 选择最新 source-quality 记录，并保留单项目兼容 helper；
- v3 project projection 在有 execution evidence 时将 REGISTERED/IDLE 显式提升为 ACTIVE；
- platform observation 使用稳定键并在读取时按项目去重；
- v3 normalizer 同时保留 canonical `tokenSummary` 与兼容字段 `usage`，并保留 `agentPlatform`、`quality`；
- `lastGood` 接受合法 v3 空项目快照；
- Data Trust 不再把缺失的 coverage/malformed/dropped/revision 渲染为伪 0；
- Command Center 改为黑白中性、真实 Light token、可展开文字导航、弱边框和更稳定的栅格。

验证：Observer UI contract `76 passed`；Workflow v3 snapshot/sidecar 定向测试
`25 passed`。全量 Python 896 tests 在当前沙箱不是绿灯：主要缺少 `jsonschema`
等依赖，另有测试夹具目录与 CLI 参数隔离问题；这不是本次 UI patch 的失败证据，
但必须在 Windows CI 的完整依赖环境重新跑。

## 4. 目标架构（下一版）

### Canonical facts

```
approved ProductProject
  ├─ repositories / worktrees / modules
  ├─ execution_instances
  ├─ task ledger
  ├─ usage samples
  ├─ CI runs
  └─ source-quality + provenance
          ↓  (Workflow-owned read-only composition)
workflow/snapshot/v4 (v3-compatible migration window)
          ↓
GET /api/v1/snapshot + SSE /api/v1/events
          ↓
Observer Web / Tauri (no write capability)
```

硬约束：Observer 不建事件库、不接管 canonical.sqlite、不执行命令、不批准、不重试、
不写 Git、不扫描未批准根目录。所有外部状态都必须有 `sourceRef`、`observedAt`、
`quality`、`freshness`、`coverage`。`UNKNOWN`、`STALE`、`OFFLINE`、`FIXTURE` 与
`LIVE` 是互斥显示状态。

### Snapshot envelope

顶层必须统一包含：`schemaVersion`、`revision`、`generatedAt`、`sourceWatermark`、
`transport`、`coverage`、`quality`、`provenance`、`projects`、`executions`、
`tokenSummary`、`ci`、`governance`。每个项目的 Git、平台、execution、CI、usage
必须按 `projectId` 绑定，禁止全局字段下沉到项目卡片。

## 5. 全量界面设计（建议作为 Command Center 3.0）

### Full（桌面）

1. **左侧导航**：Overview、Executions、Projects、Delivery、Telemetry、Trust；
   184px 宽，文字导航；窄屏退化为图标栏，不再只有无意义图标。
2. **顶栏**：WORK-LAB Observer、只读标识、transport 状态、generatedAt、当前
   revision；不把 LIVE 当成项目运行状态。
3. **Truth strip**：四个小块固定显示 Source、Freshness、Coverage、Revision；
   任何缺失显示 `—`，并提供 evidence tooltip/详情抽屉。
4. **Projects matrix**：单一项目表/网格，列为 Project、Activity、Agent、Worktree、
   Local SHA、CI SHA、Match、Last observed。支持按 attention/freshness/activity
   排序，禁止再复制三套 project overview/runtime matrix/health card。
5. **Executions feed**：仅在有真实 execution 时出现，显示 project、agent、state、
   worktree、heartbeat age、stateQuality；没有执行时显示明确空状态而非 UNKNOWN 卡。
6. **Telemetry**：输入/输出/总量、cache read/write、provider/model、cost quality、
   采样窗口。订阅制显示 `not metered`，不显示 `$0`；无样本不渲染趋势图。
7. **Delivery**：每项目只显示自己的 branch、local/remote/CI SHA、exact-SHA match、
   dirty count、CI run；dirty null 必须是 `—`。
8. **Trust drawer**：字段级 quality、coverage、freshness、sourceRef、last-good、
   malformed/dropped/duplicate；内容只读，不能出现 Retry/Apply/Approve。

### Compact（监控 HUD）

独立设计，不是 Full 缩小：transport + 运行/阻塞数量 + 三行项目列表 + Token/coverage
摘要；固定 320px 安全边界；无侧栏、无装饰图表、无滚动卡片墙。

### 视觉规则

- 黑白为主：深色 `#090909/#111111`，浅色 `#f5f5f2/#ffffff`；状态只用低饱和绿/黄/红；
- 8/12/16/24 spacing，8–10px radius，弱边框，取消紫色渐变和大面积玻璃；
- 标题使用普通无衬线，SHA/token 使用等宽数字；所有状态有文字，不依赖颜色；
- 不使用前端框架或远程 CDN，保留本地 vanilla JS + Tauri 便携壳；
- 趋势图只在有明确历史样本时绘制，不能用 fixture 补齐。

## 6. 开源方案吸收边界

- SigNoz：吸收 OTel 风格的 source → collector → query → visualization 分层，
  不引入 ClickHouse/多租户运行时；
- Grafana：吸收 panel 的 query/transform/visualization 分离和固定 max datapoints，
  不引入可写 dashboard/editor；
- Langfuse：吸收 trace/session/cost attribution 思路，但永远不采集 prompt/response；
- Perses：吸收 schema-driven panel 与 dashboard composition，不复制其后端平台；
- HyperDX/OpenObserve/OneUptime/Coroot/Beszel：只作为交互和数据质量参考，当前不
  纳入依赖，避免把个人本地观察层膨胀成 SaaS/基础设施平台。

## 7. 执行顺序与验收

### WLO-200 Truth backend

- 增加 project-scoped Git/CI/usage/sourceRefs contract tests；
- 统一 v3/v4 schema，标记 v2 仅 legacy fixture；
- 删除权威路径中的 ObserverEventStore/append API，迁移脚本只读历史；
- 稳定 platform observation 主键并验证重复 tick 不增加行数；
- exact-SHA、coverage、freshness、last-good、resync 对抗测试。

### WLO-240 UI composition

- 单一 `fusion-v3` 过渡到单一 `command-center` renderer；
- Projects matrix、Execution feed、Trust drawer；
- Full/Compact 独立信息架构；
- Dark/Light、320px、WebView2、键盘导航、reduced-motion 验证。

### WLO-280 visual evidence

- 静态 server 截图：Full/Compact × Dark/Light × live/delayed/offline/fixture；
- Windows Tauri WebView2 截图和窗口缩放回归；
- 不得用“Node contract tests passed”替代视觉证据。

### WLO-300 canary

- WORK-LAB + 一个批准的真实 OS 项目；
- 只读运行 24 小时；
- 对比 canonical SQLite、Git exact SHA、CI、usage sample 和 UI 截图；
- 出现任何串项目、伪 0、伪 LIVE、越界扫描即回滚。

完成合同：P0 全部关闭；v2 仅留 fixture/test；每个展示字段可回指 sourceRef；
Full/Compact 四种视图有截图证据；Tauri 与 Web 使用同一版本资源；无 Observer 第二事实库；
Windows CI exact-SHA 通过；未批准的 commit/push/PR/release 仍保持 WAITING_APPROVAL。

