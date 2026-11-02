# DESIGN-LAB 新对话交接摘要（权威压缩版）

> 用途：把本对话已确认的 DESIGN-LAB 决策、云端事实、开源选型、MiniMax 裁决和下一步任务带到新对话。它是交接索引，不替代代码、可复现实测或许可证核验。凡与旧摘要、README 或自述冲突者，以“当前云端可复现证据 + 本文件的明确裁决”为准。

**更新时间**：2026-09-02  
**云端仓库**：`DTALEX66/DESIGN-LAB`  
**审计基线**：`origin/main` = `33488c882d267d683250ae684caf28d0916d9099`（2026-08-31 21:41:18 +08:00，工作树当时干净）  
**本机预期目录**：`D:\All projects\DESIGN-LAB`  
**目标设备**：Windows 11、64 GB RAM、RTX 5060 8 GB VRAM；优先本地、低资源可用，涉及私有素材的云端模型必须显式同意。

## 1. 项目身份与不可越界边界

- 正式名称固定为 **DESIGN-LAB / 设计实验室 / `design-lab`**。旧的 `OPEN-DESIGN-Assistance` 等命名退出产品身份；“Open Design”仅指第三方宿主产品。
- DESIGN-LAB 是 AI-native 的专业设计生产与质量系统：拥有 **DesignIR、Domain Packs、Rubrics、Human Jury、Rights、Preflight、Delivery Receipt、创意工具适配合同**。
- 它不是第二个 Photoshop、Figma、Blender 或通用画布；复杂编辑留在专业宿主中完成。
- 它不是通用 Agent Runtime、模型网关、账号系统、WORK-LAB 的全局配置中心，亦不应吞并 ArcheAxis 的知识/证据真相源。
- WORK-LAB 只负责全局编排、权限、预算、隔离与回执；ArcheAxis 只负责知识、原件、来源和证据。DESIGN-LAB 在两者不可用时仍须能完成本地设计生产闭环。
- Hermes、Codex、MCP、Adobe、模型和任何开源工具都是可替换 Adapter/Executor，永远不是产品身份或领域模型。

## 2. 从不同用户视角确定的产品界面

| 角色 | 真正需要的入口 | DESIGN-LAB 自己必须提供 | 不能重复制造 |
|---|---|---|---|
| 小白/运营 | Quick Create、Campaign、可理解的成本与状态 | Brief 引导、约束、审核、可交付说明、失败恢复 | 通用聊天壳、全功能绘图软件 |
| 专业设计师 | Open Design / OpenPencil / Adobe / Blender 等宿主 | 项目、资产、版本、批注、局部对比、Human Jury、Preflight、交付回执 | 高精度排版、矢量编辑、3D 编辑器本体 |
| 技术美术/工程师 | ComfyUI/API/宿主插件与可复现执行 | 模型/工作流/输入输出 hash、成本上限、权限、运行证据 | 另建完整模型运行时或工作流引擎 |

**前端最终形态**：一个薄的 DESIGN-LAB Workbench（生产控制、审核、质量、交付）+ 外部创作宿主；不得继续把前端做成“第二个设计软件”。前端展示必须区分 `UNKNOWN`、`DECLARED`、`VERIFIED`、`FAILED`，不能把声明或空值伪装成可用能力。

## 3. 已确认的开源/成熟产品复用路线

| 对象 | 角色与裁决 | 可复用范围 | 明确禁止 |
|---|---|---|---|
| Open Design | `ADOPT_PRIMARY_EXTERNAL_HOST`：主要外部创作入口/产品宿主 | 官方插件、CLI/MCP、预览和导出合同 | 让它成为 DesignIR、审核或权利的 SSOT；整仓 vendoring |
| OpenPencil | `EDITABLE_UI_BAKEOFF`：可编辑 UI/矢量候选 | node tree、组件、auto-layout、文件交换 | 与 Penpot 同时作为双主画布；未验证即生产化 |
| Adobe（Photoshop 优先） | `ADAPTER_ONLY`：专业修图/分层交付首个 MVP | UXP/官方 API/脚本/读回；后续 Illustrator、InDesign、AE、Premiere 等 | 依赖屏幕点击作为正常自动化路径 |
| Blender / Inkscape / Krita / Penpot | 外部专业宿主/协作适配器 | 官方接口、文件交换、最小权限插件 | 复制其编辑器或把未知插件放进主进程 |
| ComfyUI | `EXTERNAL_RUNTIME` | 标准 HTTP/WebSocket、workflow JSON、运行回执；App Mode/Partner Nodes 可评估 | Fork 后作为 DESIGN-LAB 内建运行时 |
| VTracer、LayerD、PaddleOCR、GroundingDINO、SAM2、BiRefNet | 中立能力提供者 | 矢量化、分层/理解/抠图等能力的时间盒 PoC | 将任何单一模型写死为核心能力 |
| XState | 工作流状态机方法/库 | Gate 状态、恢复、可测试流程 | 用它替代真实人工审批和证据 |

**统一原则**：先采用整包产品或官方 API，再提炼最小模块；只有不存在成熟方案且有明确成本证明时才自研。任何第三方先标注 `ABSORB_MINIMAL`、`ADAPTER_ONLY`、`LOCK_REFERENCE`、`CONDITIONAL_POC` 或 `REJECT_REMOVE`，而不是复制进主树。

## 4. MiniMax Design：本轮最终裁决

### 4.1 四个不同对象，绝不能混为“MiniMax 已接入”

| 对象 | 真实定位 | DESIGN-LAB 裁决 | 成熟度上限（截至本交接） |
|---|---|---|---|
| MiniMax Design 桌面产品 | 专有本地桌面创作控制台，文本/图像/视频/音频流程 | `CONDITIONAL_SECONDARY_HOST`：小白快速创作、电商/广告/短视频第二宿主 | E1，尚未 Windows 实机资格化 |
| MiniMax API | 托管图像、视频、语音等模型服务 | `EXTERNAL_GENERATOR_PROVIDER`，经后端合同接入 | E1，尚未完成合同/预算验证 |
| MiniMax H3 权重 | Community License 的视频模型权重 | `CONDITIONAL_EXTERNAL_RUNTIME`：官方 API 或本地二选一 | E1，必须重新核权 |
| `MiniMax-AI/minimax-desgin-plugin` | GPL-3.0 的 ComfyUI 前后端快照（仓名拼写即如此） | `REFERENCE_EXTRACT`：仅提炼协议与测试方法 | E2 静态审计，不可整包并入 |

### 4.2 可以帮什么、不能替代什么

- MiniMax Design 适合作为“Quick Create / Campaign”第二宿主：一句话 Brief、并行生成、统一画布、初稿、分镜和短视频方向探索。
- 它不能替代 Open Design 的主外部宿主地位，也不能替代 DESIGN-LAB 的 DesignIR、Rights、Human Jury、Preflight 和 Delivery Receipt；公开材料尚未证明稳定 SDK/CLI/MCP、可编程审批/暂停/读回、可编辑源文件模型或可验证的专业格式导出。
- 只有在安装、数据根、网络、导出可编辑性和人工审核实测全部通过后，才可从 E1 升级；否则仅可用于非保密探索。
- MiniMax API 必须经过 server-side adapter：显式用户同意、预算/频率/地区控制、幂等、取消、超时、输入输出 hash、任务成本与回执；密钥只进入凭据管理器/密钥代理，不能放仓库。

### 4.3 自动分层与矢量化不能过度承诺

- 官方快照包含 `Image to Layers (Qwen-Image-Layered)` 工作流，可作为“输出 RGBA 图层批次”的 PoC。
- 它**不等于** PSD 分层，不等于 SVG/AI 矢量，也不等于可商用的专业源文件；仍需图层命名、层序、混合模式、蒙版、文字重建、PSD 打包和宿主读回。
- 其 BF16 主模型约 40.9 GB，RTX 5060 8 GB 不适合直接运行。先测试云端/高显存/经验证量化或 offload，再用 IoU、边缘污染、遮挡恢复、文字完整性、重组质量、人工修改时间和 PSD 重开完整性评估。
- 矢量交付仍应由 VTracer/结构重建/OpenPencil/Illustrator 等独立链路完成；绝不能宣传“像素级 1:1 复刻”或“自动得到可编辑矢量源文件”。

## 5. 当前云端已证实的真值债务与阻塞

| 优先级 | 问题 | 影响 | 处理原则 |
|---|---|---|---|
| P0 | `capability-index.json` 对 ComfyUI/H3 标 E0/unsupported，却又标 runtime-verified；Open Design 也有声明冲突 | 前端和报告会错报能力 | 建一个 canonical registry，所有 dashboard/manifest/政策从它生成 |
| P0 | MiniMax H3 在 adapter/manifest、rights policy、能力索引之间身份和许可证不一致 | 合规和上线风险 | 拆四身份并重新核权；未通过前 fail-closed |
| P0 | Human Gate 可能被 production 叙述或自动评分绕过 | 设计质量和权利审核失真 | Direction、Quality、Rights、Production、Release Gate 都不可绕过，必须有真实 `REJECT → 修复 → 复验` |
| P0 | `.hermes/task-runtime` 等运行写入不符合项目内隔离要求 | 数据外溢、不可清理 | 统一迁入 `.project-local`，阻止外部盘符/用户目录写入 |
| P0 | 测试环境不完整：结构验证曾通过，但 governance/action 单测因缺 `jsonschema` 出现 9 error + 1 failure | “绿”不等于可复现 | 锁依赖、干净环境重跑、区分结构检查和实际产品测试 |
| P1 | Open Design 的许可证/角色/版本在 registry 与旧文档中互相冲突，插件运行注册仍是 E3 pending | 主宿主无法证明能跑 | 正式资格化，官方 extension surface + 运行读回 |
| P1 | `design-lab/knowledge`、`intelligence` 含大量完整第三方源码；MiniGame、memory、design-system 混在根目录 | 许可证、供应链、维护和边界混乱 | 逐项目资格化、最小吸收或外置，然后清理旧树 |
| P1 | 内部尚无成熟统一 Workbench，已有材料/声明多于真实闭环 | 用户无法实际完成工作 | 先做一条黄金流程再扩张功能 |

## 6. 数据、运行时与沙箱硬约束

- **所有项目运行数据必须留在项目根内**：`.project-local/{worktrees,runs,temp,cache,artifacts,exports,logs}`；不准默认散落到 `.hermes`、用户目录、其他项目或其他盘符。
- `D:\All projects\Design assets` 只是受控摄入/暂存区，不是知识真相源；摄入要有 hash、来源、权利和删除规则。
- 未知第三方程序、插件和 Agent 默认网络隔离、最小权限；Windows Sandbox 或等价隔离环境先资格化。第三方 Skill/Marketplace 视为不可信指令，禁止自动安装和自动取得资产权限。
- 客户素材、Brief、生成文件不得进入 Git；生成物只在 `.project-local` 或明确 Release/fixture 位置。密钥不得进文件或日志。
- 外部宿主只能经官方接口、受控文件交换或最薄 Adapter 通信；禁止 UI 自动点击、私有数据库逆向写入或用截图冒充读回。

## 7. 目标仓库目录（尚未完成迁移）

```text
DESIGN-LAB/
├─ apps/workbench/                 # 薄控制/审核/交付 UI
├─ services/{jobs,review,quality,delivery}/
├─ packages/{capabilities,design-system,asset-model,ui}/
├─ integrations/{hosts,canvases,generators,executors}/
├─ vendor/                         # 仅 source lock、license、SBOM；非整仓副本
├─ research/{candidates,quarantine}/
├─ assets/                         # 受控、非客户原件
├─ fixtures/domains/game-visual/   # MiniGame 仅作为回归 fixture
├─ docs/{architecture,decisions,current,history,taskpacks}/
└─ .project-local/                 # ignored，唯一运行数据根
```

迁移目标：将旧 `design-lab/*` 按语义拆入 `packages/`、`services/`、`integrations/`、`docs/`；`design-system/` 迁至 `packages/design-system/`；`project-memory/` 迁至 `docs/`；`minigame-runtime/` 迁至 fixture；`knowledge/` 和 `intelligence/` 中的整仓第三方源码逐项资格化后移除。只有迁移、哈希、引用更新、干净克隆测试和宿主读回全部通过，才能删除旧目录；不得先删后证。

## 8. 下一阶段唯一合理的执行顺序

1. **先修真相源（0–1 天）**：完成 `DL-MM-001` 四类 MiniMax 身份拆分、`DL-MM-002` H3 权利重核；建立唯一 capability/adapter registry，生成所有投影，清除冲突声明。
2. **先跑可用闭环（1–7 天）**：Open Design 主外部宿主 + Photoshop 首个 Adapter；用一个品牌/电商 Campaign 从 Brief → 方向 → 生成/编辑 → 人审 → Preflight → 交付回执跑通。必须真实拒绝一次并修复。
3. **资格化 MiniMax（1–7 天，可并行）**：`DL-MM-010` 安装/签名/卸载，`DL-MM-011` 数据根和网络边界，`DL-MM-020/021/022` 分别验证小白 Campaign、专业可编辑性和 Jury 循环。通过前不写生产集成。
4. **再做最薄整合（第 2 周）**：`DL-MM-030` MiniMax 桌面 Host Adapter（探测版本、打开受控交换、观察输出、导入回执）；`DL-MM-031` API provider；`DL-MM-032` 官方 ComfyUI 标准 adapter。三者均不操纵私有数据库或自动点击 UI。
5. **最后做分层/向量 PoC（第 2–3 周）**：`DL-MM-040` Qwen Image Layered，严格按黄金集指标决定。然后执行 `DL-MM-050` Adopt/Hold/Reject。
6. **有证据后再目录迁移和清理**：按 `DL-DIR-000` 至 `DL-DIR-120` 完成内部隔离、来源锁、最小吸收、测试、清理旧目录。迁移不是阻塞黄金闭环的前置借口，但也不能在未验证时把第三方代码继续复制入新树。

## 9. 近期可验收的“0.1 usable”定义

- 用户可在 Workbench 创建 Brief；受控地进入 Open Design 或受资格化的 MiniMax Design；专业编辑可转 Photoshop/OpenPencil 等宿主。
- 每次生成/编辑都记录工具版本、模型/工作流、输入输出 hash、权利状态、成本、操作者和回执。
- 人工可查看对比、批注并作 `APPROVE` 或 `REJECT`；被拒绝的产物不能走到交付。
- Preflight 检查格式、尺寸、字体/链接、色彩、版权/来源和导出完整性；最终交付必须可重新打开或由宿主读回验证。
- 环境从空工作树按锁定依赖可复现；运行数据不外溢；仓库中不存在客户原件、密钥、生成缓存或完整未经资格化的第三方源码。

## 10. 禁回归清单

- 不把 MiniMax、Open Design、ComfyUI、Adobe、Hermes 或 Codex写成 DESIGN-LAB 本体。
- 不把 `DECLARED`、`UNKNOWN`、模型自评或静态文档写成 `VERIFIED`。
- 不以 production 模式、模型评分或“快速交付”绕过人工审核和权利 Gate。
- 不把 RGBA 图层宣传成 PSD/矢量/1:1 可编辑复刻。
- 不整仓 fork/vendor GPL 快照，不重复造完整编辑器、工作流引擎或模型运行时。
- 不强制所有数据先传 ArcheAxis 或所有任务先经 WORK-LAB；跨项目交换必须最小、批准后、可撤销。
- 不在仓库或系统外无边界写入运行数据；不在迁移未验收时鲁莽删除旧目录。

## 11. 可直接交给新对话的启动指令

```text
请以《DESIGN-LAB 新对话交接摘要（2026-09-02）》为现行约束，先只读复核云端 main 是否仍是 33488c882d267d683250ae684caf28d0916d9099；若已变化，做差异审计而不是沿用旧结论。目标是先完成一条可验收的 DESIGN-LAB 0.1 usable 黄金闭环：薄 Workbench + Open Design 主外部宿主 + Photoshop 首个专业 Adapter + 强制 Human Jury + Preflight + Delivery Receipt。严格开源/成熟方案优先，不自研完整编辑器/运行时；所有第三方需许可证、版本、隔离和真实运行读回证据。MiniMax Design 只能按 CONDITIONAL_SECONDARY_HOST 资格化，未经 Windows、数据边界、可编辑性和审核循环测试不得接入生产。先输出当前差异、阻塞、选型和任务 DAG，再在我明确授权后修改代码。
```

## 12. 需优先读取的现有文件

1. `DESIGN-LAB-MINIMAX-DESIGN-INTEGRATION-AUDIT-2026-09-02.md`：MiniMax 深度审计、证据、任务 `DL-MM-*`。
2. `DESIGN-LAB-DIRECTORY-MIGRATION-CLEANUP-TASKPACK-2026-09-01.md`：目标目录、隔离、迁移和清理硬门，任务 `DL-DIR-*`。
3. 云端仓库内 `docs/taskpacks/DLR-FINAL-20260826-R2-OSS-FAST-TRACK.md`：开源快速成品化路线；若和本文件冲突，以本文件的“外部主宿主但 DESIGN-LAB 保持 SSOT”裁决为准。
4. 云端仓库内 `design-lab/config/capability-index.json`、`design-lab/adapters/adapter-registry.json`、`design-lab/adapters/creative-tools/minimax-h3/rights-and-provider-policy.md`：当前冲突真相源，先修复再扩张。

## 13. 交接文件校验

本文档不包含客户资产、密钥或第三方完整源码。创建后应记录其 SHA-256，并在新对话先验证云端 SHA 是否变化。
