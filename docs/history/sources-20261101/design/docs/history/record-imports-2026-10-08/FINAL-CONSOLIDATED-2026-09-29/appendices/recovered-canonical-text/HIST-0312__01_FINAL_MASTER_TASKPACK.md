# OPEN-DESIGN-Assistance 最终全量执行任务书 v4.2

## 0. 总裁决

本项目不在“数据知识库”和“独立前后端产品”之间二选一。最终形态是：

```text
Open Design 用户入口与运行时
        ↓
OPEN-DESIGN-Assistance 专业能力运行层
        ↓
受治理的知识、标准、来源与证据层
        ↓
可编辑 Artifact、生产预检与商业交付
```

知识是燃料，运行能力是产品，Open Design 是用户主入口。禁止复制 Open Design 的 Home、Studio、画布、Agent、模型路由、Artifact、预览和导出；只有上游接口明确需要时，才允许建立最小、无用户界面的本地服务。

## 1. 产品使命

把灵感、业务目标、参考资料、品牌资产和生产约束，转化为：

- 结构真正不同的设计方向；
- 可编辑、可回退的设计系统与作品；
- 有来源、有权利边界、有专业评审的结果；
- 可进入 UI 开发、品牌执行、电商上线、印刷、空间施工、3D、视频、音频或游戏制作的交付包。

完整闭环：

```text
Inspiration → Brief → Research → Direction → Design System
→ Create/Edit → Critique/Repair → Production Preflight
→ Editable Handoff → Evidence/Feedback/Learning
```

## 2. 用户与产品模式

同一能力引擎提供不同披露与控制强度，不创建多套产品：

| 用户 | 模式 | 必须提供的价值 |
|---|---|---|
| 小白、新手 | Guided | Brief 向导、安全默认值、逐步解释、模板、版权和生产防错 |
| 职业设计师 | Copilot | 参考 DNA、三方向、Token/组件、批量变体、跨格式、精修、预检 |
| 资深设计师、艺术指导 | Director | 自定义 Rubric、方向评审、局部锁定、人工覆盖、版本比较、回退 |
| 大师、研究者、教育者 | Method | 有来源的方法拆解、匿名转译、反模仿、专家校对、版本演进 |
| 品牌方、客户、生产方 | Production | Brief/审批追踪、品牌一致性、权利 BOM、规格、可编辑交付、签收 |

“大师能力”不得做成姓名风格按钮。只允许基于证据拆解构图、比例、字体、材料、光影、叙事、节奏和决策方法；最终生成指令不得含大师姓名，不得复制签名元素。

## 3. 唯一职责边界

### Open Design

负责桌面应用、项目、Studio/画布、Agent 启动、插件运行时、Stage event、GenUI、Artifact、预览、导出及已存在的 CLI/MCP 能力。

### 本仓库

负责：

- Domain Pack、Scenario、Bundle、Plugin/Atom；
- Brief、参考 DNA、方向、设计系统、评审与有界修复；
- UIUX、平面、品牌、电商、空间、3D、动效、视频、音频、游戏视觉等专业协议；
- 开源资料、标准、大师方法、失败模式及来源治理；
- 无障碍、印刷、包装、空间、3D、视频、音频与权利预检；
- 可编辑交付合同、Benchmark、人工评审和能力证据。

### MiniGame

`minigame-runtime` 已存在于云端 `main`。只允许：安全修复、构建修复、资产完整性、既有测试，以及 HUD/UI/图标/视觉规范/皮肤/提示词/设计 fixture/runtime reference。禁止平台工程、广告、变现、发行、运营和完整产品逻辑扩张。

## 4. 执行角色

- **Coordinator**：读取事实、管理任务状态、依赖、风险、审批和证据；客户端中立。
- **Writer**：同一 worktree 同一时间唯一写者。
- **Reviewer**：绑定冻结 tree 的独立只读复审；不得参与该 tree 的实现。
- **Open Design Runtime**：只用于真实注册、任务运行、Artifact 和恢复验证。
- **GitHub**：远端事实、PR、exact-SHA CI 和发布证据。

任何工具、模型、版本和路径都必须现场发现。兼容基线可记录 Open Design 0.18.1，但不得把实现永久锁死在该版本。

## 5. 全局安全与写入合同

1. 先记录 branch、HEAD、tree、remote、status、活跃 writer 和未完成 Git 操作；事实变更时重新审计。
2. 不访问项目外无关目录，不读取 `.env`、OAuth、Cookie、Token、私钥或私有认证。
3. 不使用广域 reset、clean、递归删除或覆盖用户脏工作区。
4. Open Design 集成默认 plan-only；不得直接写其私有 app config。
5. 第三方代码、Skill、字体、模型、图片、音频、3D 资产先进入 quarantine，许可与执行风险通过后才能采用。
6. 未获用户授权，不 commit、push、开 PR、改 Ruleset、merge 或 release。
7. 每项修改必须限定 allowed paths；共享 SSOT 串行写入。
8. 最多三轮自动修复；仍失败则保留证据并 BLOCKED，不得改测试掩盖问题。

## 6. 能力与证据等级

| 等级 | 名称 | 最低证明 |
|---|---|---|
| E0 | DECLARED | 文档或清单声明 |
| E1 | STRUCTURAL | Schema、Manifest、结构和静态验证 |
| E2 | ISOLATED_RUNTIME | 隔离环境真实命令、退出码和产物 |
| E3 | LIVE_RUNTIME | 当前 Open Design/真实工具中运行，含任务 ID、Artifact、provenance、失败恢复 |
| E4 | RELEASE | 冻结 tree、commit、push、PR/review、exact-SHA CI 和远端回读 |
| E5 | COMMERCIAL | 客户、设计师、开发、印刷或生产方真实签收 |

每条证据必须记录 capability、状态、SHA/tree、OS、运行时/版本、命令或任务 ID、开始/结束、退出码、Artifact/hash、provenance、人工 reviewer、Rubric、时间戳和限制。静态检查、mock、skip、合成截图和模型自评分不得冒充 E3。

## 7. 十五阶段执行顺序

### Phase 0：执行时事实冻结

重读云端、本地、分支、CI、Open Design 与当前资产；如果 HEAD 不再是审计基线，先生成 delta audit。把全部现有能力降级到证据可支持的等级。

Gate：形成 baseline、capability map、current-SHA CI map 和 writer/dirty-state 判定；未知脏状态阻断写入。

### Phase 1：真实性与 P0 修复

修复当前已证实的问题：兼容矩阵旧版本、README 无效参数、配置脚本私有写入矛盾、clean-tree 门禁不失败、workflow 路径漏触发、插件/Bundle/Domain Pack 计数失真、适配器“声明即 available”以及 MiniGame 状态口径。

Gate：SSOT 一致；当前 HEAD 有 exact-SHA CI；配置脚本只有 plan/export 行为；无虚假 available。

### Phase 2：产品宪章与数据模型

固化唯一产品定义、上游/本仓库边界、五类用户和模式、Project/Knowledge/Evidence/Artifact 四类对象及生命周期。禁止先建设独立 SaaS、账号系统和泛用向量库。

Gate：README、产品定义、架构、能力矩阵引用同一 SSOT；没有第二套前端/Agent runtime。

### Phase 3：Open Design 原生运行合同

现场发现上游插件、Bundle、Artifact、事件、CLI/MCP 合同；完成三个核心 Bundle 的真实注册：`commercial-design-core`、`visual-quality-core`、`production-handoff`。验证安装、发现、启动、运行、Artifact、provenance、取消、失败和恢复。

Gate：至少三 Bundle E3；不得通过修改私有配置达成；必须有一条失败恢复证据。

### Phase 4：UIUX 黄金纵切

先完成一个满足 Domain Pack V2 十部分合同的 `uiux-design` 包，并完成五个案例：B2B 后台、移动任务流、电商 PDP/结算、设置/无障碍、响应式内容页面。

每例必须包含：Brief、参考/来源、三种结构方向、选择与锁定、DESIGN.md/DTCG Token、组件、三视口、键盘路径、无障碍、基线/增强、可编辑 Artifact、评审、预检、交付和证据。

Gate：五例全部可复现；Axe critical/serious 为 0；人工总分 ≥82；增强偏好率 ≥70%；至少一例 E3；不得只交截图。

### Phase 5：视觉质量与大师方法引擎

实现参考 DNA、方向 Jury、构图/字体、色彩/材质/光影、摄影真实性、反 AI 痕迹、有界精修和锁定保护。大师方法只使用已核验、有来源、适用条件明确的方法卡。

Gate：三方向不是换色；修复不破坏锁定项；禁止姓名式模仿；原始性和签名元素风险为 0 blocker。

### Phase 6：生产、权利与可编辑交付

建立素材/字体/模型/音乐权利 BOM，无障碍、数字、印刷/PDF、包装、空间、3D、视频和音频预检，以及源文件、资产、Token、规范、版本、批准和回退合同。

Gate：无 license unknown blocker；至少一种开发交付和一种生产交付通过人工复核。

### Phase 7：开源与专业知识运行化

将当前 112 个通用来源、22 个视觉来源迁移到 V3 字段和成熟度模型；区分 reference、derive、adapter、vendor-adapt、quarantine。497 条大师记录分层核验，先完成不超过 20 张高价值、有完整来源的方法卡。实现有范围、有权限、有版本的检索，不允许把整个知识库塞入 Prompt。

Gate：未核验资料不得 runtime eligible；每次检索可解释来源、选择原因和使用边界；知识增强必须通过任务级 A/B 评测。

### Phase 8：第一批职业 Domain Packs

在 UIUX 模板稳定后依次完成：平面/整合视觉、品牌/VI/KV、电商/商品视觉。每个领域都必须复制完整闭环，不是复制目录和提示词。

Gate：每个领域至少五个黄金案例、一个 E3、一个失败恢复、一个可编辑交付和人工偏好证据。

### Phase 9：复杂媒介与游戏设计能力

扩展空间/展厅展馆、3D/材质/灯光、动效/视频、音频、包装/编辑/插画/IP。游戏只扩展视觉、UI、HUD、图标、动效和音频设计能力；MiniGame 只作 fixture。

Gate：外部工具状态必须由版本、真实任务和 Artifact 证明；Blender/FFmpeg 未安装时保持 BLOCKED/UNVERIFIED。

### Phase 10：Benchmark 与真实能力证据

建立 `capability-evidence-index.json`，运行现有 12 类 Benchmark 的 baseline/enhanced、负例、恢复和人工 Jury。证据卡从 E0 升级必须绑定真实 Artifact。

Gate：不得挑选性只报告成功；成本、耗时、失败率、人工分和偏好率完整记录。

### Phase 11：安全、许可证、CI 与发布门禁

完成 REUSE、第三方 BOM、SBOM、二进制 sidecar、依赖与 Skill 供应链审计；建立 Linux/Windows 分层 CI、变更感知门禁和 exact-SHA release gate。

Gate：clean-tree 真正 fail-closed；required check 无 mock/skip；当前提交有 exact-SHA 证据。

### Phase 12：Open Design 内的产品界面

通过 Open Design 的 GenUI、Artifact、插件或面板落地 Inspiration Board、Brief Builder、Direction Room、Design System Workspace、Critique Console、Production Preflight、Handoff Center 和 Method Explorer。采用渐进披露支持 Guided/Copilot/Director/Method/Production。

Gate：不创建第二套应用壳；五类用户完成各自核心任务的可用性测试。

### Phase 13：单一入口与文档收敛

README 只讲产品、安装、真实能力状态、使用路径和证据；能力、来源、Bundle、Domain Pack 与证据索引自动生成。旧 V2/V2.1/V3/V4 文档明确 deprecated，不再竞争 SSOT。

Gate：无失真计数、过期版本和双入口；新用户能从 README 到一次真实设计任务。

### Phase 14：冻结、复审、PR 与最终验收

运行全套测试，冻结 tree，独立 reviewer 复核全部 blocker；经用户授权后 commit、push、draft PR、exact-SHA CI、合并与 main readback。记录用户/设计师/生产方验收和后续冻结 backlog。

Gate：Reviewer GO、CI success、main readback 一致、证据索引无断链；否则只能 READY_FOR_APPROVAL 或 BLOCKED。

## 8. 质量硬门槛

- 总体专业评分 ≥82/100，任一领域 blocker 必须为 0；
- 基线/增强盲评偏好率 ≥70%；
- 三方向在信息架构、构图或视觉语法上有结构差异；
- 用户锁定的比例、结构、品牌元素、文案和关键资产不可漂移；
- UIUX：三视口、键盘可用、Axe critical/serious 0；
- 视觉：避免过度锐化、假材质、假透视、统一人脸、错误产品比例、无意义遮罩和模板化 AI 痕迹；
- 商业交付：可编辑源、预览、资产、字体/素材 BOM、Token/规范、版本、provenance、预检和批准记录齐全；
- 运行：至少任务 ID、真实退出状态、Artifact、hash、失败恢复；
- 发布：exact tree、exact SHA、review、CI 与 main readback 对齐。

## 9. 数据与知识策略

建立四种受治理对象，而不是泛用资料堆积：

1. **Project Graph**：Brief、用户、目标、限制、参考、方向、锁定、设计系统、Artifact、评审和交付。
2. **Knowledge Graph**：原则、方法、标准、案例、反例、失败模式、来源、适用条件和许可。
3. **Evidence Graph**：能力、版本、运行、Artifact、Reviewer、指标、权利和验收。
4. **Artifact Store**：可编辑源、预览、Token、组件、资产、交付包和哈希。

初期以开放、可版本化文件和局部索引实现；只有多人协作、权限和规模数据证明必要时才引入数据库。任何检索系统必须先通过检索正确率、引用覆盖率、权限泄漏和任务增益评测。

## 10. 任务执行规则

- 严格按 `tasks/task-cards.json` 的依赖执行；Phase Gate 未通过不得进入下一阶段。
- 单任务流程：事实基线 → 测试/fixture → 实现 → 定向验证 → 负例 → 证据 → Git scope → Reviewer。
- 共享文件和 Schema 串行；只读研究可并行；同一 checkout 唯一 writer。
- 任务状态仅允许：`NOT_STARTED | IN_PROGRESS | PASS | FAIL | BLOCKED | READY_FOR_REVIEW | APPROVED | SKIPPED_OPTIONAL`。
- `SKIPPED_OPTIONAL` 不得用于 required gate。
- 任何“完成”必须同时满足产物、测试、证据等级和人工/机器验收。

## 11. 最终完成定义

项目阶段性完成必须同时满足：

1. P0 真实性缺陷全部修复；
2. 三个核心 Bundle 已真实注册；
3. UIUX 五案例黄金纵切通过；
4. 平面、品牌、电商各有完整 Domain Pack 与 E3；
5. 视觉质量、权利、生产预检和可编辑交付成为强制 Gate；
6. 开源与大师资料具有来源、许可和成熟度，不再作为未核验 prompt 原料；
7. Benchmark 有 baseline/enhanced、人工盲评和失败恢复；
8. 当前 main 具备 exact-SHA CI、独立 review 和远端 readback；
9. MiniGame 没有越界扩张；
10. README 与事实索引无过期、失真或重复入口。

在此之前，项目应被描述为“专业设计能力蓝图和结构化原型”，不得宣传为成熟商业设计平台。

## 12. 项目漂移强制门禁

`06_PROJECT_DRIFT_CONTROL.md` 是与产品宪章同级的强制合同。每个任务开始、每个 Phase Gate、引入新子系统、PR 前、merge 前和 release 前都必须生成漂移报告。

以下任一情况立即停止：复制 Open Design 主入口或运行时、把项目改成纯知识库/Agent/聊天工具、重新耦合 WORK-LAB、扩张 MiniGame 产品逻辑、UIUX 未闭环即铺开空壳领域、用静态或模型自评冒充能力、未经审查把资料送入 runtime、无批准新增数据库/SaaS/daemon 或降低证据与质量门槛。

状态为 `DRIFTED` 时先修复；状态为 `BLOCKED_REAUTH` 时只有用户明确重新授权才能继续。
