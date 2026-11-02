# DESIGN-LAB 深化优化独立任务包

- TaskPack ID：`DL-DEEPEN-20260825-V1`
- 目标仓库：[DTALEX66/DESIGN-LAB](https://github.com/DTALEX66/DESIGN-LAB)
- 状态：`READY_FOR_EXECUTION`
- 执行边界：只修改 DESIGN-LAB；宿主/工具配置通过 adapter 和独立授权操作。

## 1. 纠错后的项目定位

DESIGN-LAB 是面向职业视觉设计的、AI 原生、平台中立、宿主原生的设计智能与生产能力层。它拥有：

- Brief、Reference、Direction、Design System、Domain Pack 和 Method；
- 视觉质量、专业 Jury、反 AI 痕迹、可访问性和商业预检；
- Host/Agent/Adobe/Figma/Penpot/Blender/FFmpeg 等受控 adapter；
- 可编辑交付、BOM、provenance、Evidence 和 rollback。

它不重建第二套画布、聊天客户端、Agent runtime、模型网关、账号系统或通用知识库。Open Design 是当前参考宿主，不是 DESIGN-LAB 的产品身份；仓库是能力 SSOT，宿主只保存可重建运行镜像。

## 2. 审计快照与已完成基线

本轮本地审计副本为干净 `main`，HEAD `9468c40ea8b739499b06e80a7edf5d5542659778`。但 `reports/current/PROJECT_STATUS.md` 仍写旧 SHA `a6fdc5e...` 和 dirty，说明生成状态已过期，必须先修复而不是引用旧数字。

以下属于 `DONE_BASELINE`：

- DESIGN-LAB 新身份、九份 SSOT、root README、product manifest/schema 和 identity gate；
- MiniGame 收敛为冻结的 game-visual fixture；
- Contract-First V2、核心对象、DesignProject 状态机、Domain Packs、Design Memory、Quality Gate、Preflight、Review Surface；
- Open Design/Figma/Penpot/Blender/FFmpeg/Adobe 等 adapter 合同的 E0/E1 结构；
- 大批设计方法/skill/source 的受治理吸收、162 遗留隔离、能力和证据索引；
- Canonical/Python/MiniGame/CI 的多轮历史验证。

身份迁移和 V2 不再整包重做；本轮重点是当前状态生成、真实宿主/工具运行、人工视觉校准、可编辑生产交付和开源资产减法。

## 3. 当前未完成与阻塞

| 类别 | 当前结论 | 处理 |
|---|---|---|
| 当前状态 | PROJECT_STATUS 与审计 HEAD 不一致 | P0 修复生成链 |
| Agent 操作指南 | 审计副本根目录未见活动 `AGENTS.md`，跨软件规则可能再次丢失 | P0 核对/补齐 |
| Open Design | 合同和历史 E2/E3 记录存在，但当前版本 live registration/artifact/provenance 需重新取证 | P0/P1 真实重验 |
| 人工质量 | 12 Evidence Cards authoritative accepts=0；五案例真人 Jury、REJECT 样本、偏好校准未闭环 | P0 产品门 |
| Adobe | 旧 Photoshop/Illustrator/Acrobat 已卸载，旧 E3 当前不可复现 | `BLOCKED_RUNTIME`，新版本安装后重验 |
| Illustrator/Eagle | 可编辑 `.ai` 和专用 Eagle 测试库/MCP 未闭环 | 条件任务 |
| OpenPencil/Penpot/Krita/InvokeAI | 多数停留在 E0/研究或批准前 | 单选 bake-off，禁止全装 |

## 4. 任务 DAG

### DL-000 — 当前事实、dirty 与生成状态修复

- 优先级/状态：`P0 / TODO`
- 动作：执行时重新读取本地/远端 SHA、branch、dirty、CI；确认所有未跟踪 handoff/用户资产归属；运行 `generate_project_status.py` 并修复其确定性/过期检测。
- 修改：生成状态必须包含 `source_sha`、dirty digest、generator version、生成时间和证据等级；README/ROADMAP 只引用生成状态，不复制数字。
- 验收：同一 clean tree 重跑字节稳定；HEAD 改变后旧状态门禁失败；不 reset/clean 用户文件。

### DL-010 — 活动指令与 SSOT 连续性

- 优先级/状态：`P0 / TODO`
- 依赖：DL-000。
- 核对根 `AGENTS.md` 是否在当前远端被遗漏、归档或故意移除；若无活动等价文件，新增最小项目操作指南。
- 必须写明：项目定位、owner/SSOT、host-native 边界、E0–E5、用户 dirty 保护、禁止读凭据/E 盘、独立 commit/PR/test/rollback、Open Design 双身份。
- 检查活动文档无旧产品名、旧静态计数、绝对运行路径、把 Open Design 写成产品 SSOT、把 MiniGame 写成产品线。
- 验收：identity/authority verifier 覆盖根操作指南和九份 SSOT；历史目录允许旧名但必须标历史。

### DL-020 — Open Design 当前版本 live requalification

- 优先级/状态：`P0 / TODO`
- 依赖：DL-000、DL-010。
- 上游：[nexu-io/open-design](https://github.com/nexu-io/open-design)。锁当前安装版本和上游 commit/release，不硬编码动态端口、namespace 或私有 DB。
- 流程：doctor → 只读能力枚举 → 插件/skill/design-system plan → 经批准注册 → 最小真实 Brief → Artifact → editable/source export → provenance/readback → 失败/恢复 → 卸载/回滚。
- 规则：只用官方 CLI/API/MCP/插件扩展面；仓库为 SSOT，Open Design 为运行投影；WORK-LAB 管 client 全局配置，DESIGN-LAB 管设计 capability。
- 验收：版本、runtime ID、注册项、任务输入、artifact hash、provenance、失败与回滚都有收据；仅文件存在不高于 E1。

### DL-030 — 可编辑 UI/矢量宿主单选 bake-off

- 优先级/状态：`P1 / CONDITIONAL`
- 依赖：DL-020。
- 候选：OpenPencil 与 Penpot；Penpot 已有 E0 adapter，OpenPencil 历史评估待批准。
- 同一 3 个 brief 比较：设计树可读写、tokens/components、约束/auto-layout、lint、`.fig/.pen/SVG/PDF/HTML-CSS` 导入导出、Windows 稳定、MCP/CLI、离线、许可、备份回滚。
- 裁决：只选一个 `PRIMARY_EDITABLE_UI_ADAPTER`，另一个保持 reference/fallback；不得把两套编辑器 vendored 到仓库。
- 验收：源文件可重开编辑，导出后设计层级/文字/组件可读回；视觉截图相似不能替代结构可编辑性。

### DL-040 — CLI-Anything 创意工具 adapter 基座

- 优先级/状态：`P1 / TODO`
- 依赖：DL-010。
- 上游：[HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) 当前已有 Krita、Blender、Inkscape、GIMP、Kdenlive、OBS、Audacity、LibreOffice 等 harness 候选。
- 先吸收 harness 结构和测试方法，不整仓复制；每个工具建立 DESIGN-LAB AdapterRecord、权限、dry-run、文件根、timeout、读回和 rollback 映射。
- 第一批只选 2 个高价值真实场景：建议 Blender + Krita 或 Inkscape；第二批再扩音视频。
- 验收：Brief → Design IR → ToolActionPlan → approval → execution → editable artifact → readback → quality/preflight；禁止 Agent 直接任意 shell 写用户目录。

### DL-050 — 专业视觉质量与人工 Jury 产品门

- 优先级/状态：`P0 / TODO`
- 依赖：DL-020。
- 执行五个黄金案例，至少覆盖品牌/电商/UIUX/平面或包装/动效或 3D；建立盲评 A/B、明确 REJECT 样本和失败原因。
- 人工校准 12 Evidence Cards；模型/VLM 自评只能做辅助信号，不能作为 authoritative accept。
- 记录真实迭代数、延迟、token、成本、编辑时间、通过率和 Pareto；manifest 规格不能代替运行数据。
- 验收：Jury 人员/协议/随机化/评分/分歧/复审可追溯；至少一个失败案例触发质量 gate 并成功修复；冻结黄金纵切和 regression assets。

### DL-060 — 专业工具与生产交付

- 优先级/状态：`P1 / CONDITIONAL`
- Adobe：当前旧软件已卸载；只有用户安装新版本后才执行 Photoshop/Illustrator runtime 重验。Photoshop 必须包含图层组、可编辑文字、蒙版、调整层、链接对象、保存关闭重开；Illustrator 必须安全处理未保存文档并产出可读回 `.ai`/PDF/SVG。
- Eagle：必须使用专用测试资料库和官方 API/MCP；禁止写个人资料库。
- 非 Adobe 主线：Blender scene/source、FFmpeg 时间线/媒体、Inkscape/SVG、PDF/X/字体/色彩/出血/分辨率 preflight。
- 验收：每个工具独立 E0–E3；无安装/账号/安全测试库时标 BLOCKED；旧证据不得自动继承到新版本。

### DL-070 — 图像生成运行时单选与隔离

- 优先级/状态：`P2 / CONDITIONAL`
- 候选：Krita AI Diffusion 或 InvokeAI。只有 DL-050 证明真实场景存在缺口时才启动 bake-off。
- 比较：局部编辑/蒙版/ControlNet、批量、可重复参数、显存、Windows、许可证、离线、API 稳定、可编辑交付和 provenance。
- 选中项只做外部 runtime adapter；模型权重、安装器、缓存和用户素材不进入仓库。
- ComfyUI/H3 保持用户既有冻结，除非用户另行解冻。

### DL-080 — 设计知识与 ArcheAxis 双向接口

- 优先级/状态：`P1 / TODO`
- 依赖：DL-050；ArcheAxis AA-040/AA-080。
- 读取：只通过版本化查询获取 verified design knowledge；不得直连 ArcheAxis DB。
- 写回：ResearchFinding、MethodCard、Jury correction、Production failure 只能作为 `LessonCandidate/CandidateKnowledge`，带来源、rights、artifact/evidence hash 和 DESIGN-LAB exact SHA。
- 在 ArcheAxis 未完成接收门前，候选保留在 DESIGN-LAB `knowledge-staging`，不得伪造已迁移。
- 验收：重复提交幂等；拒绝/冲突/撤销可读回；ArcheAxis 不可用时 DESIGN-LAB 独立运行。

### DL-090 — 开源资产、能力库和隔离区减法审计

- 优先级/状态：`P1 / TODO`
- 依赖：DL-000。
- 审计当前活动来源、2424 级能力索引、497 master records/方法卡、162 quarantined 项、历史 vendored skills 和 adapter registry。
- 状态：`ACTIVE_CODE`、`ACTIVE_METHOD`、`ADAPTER`、`REFERENCE`、`QUARANTINE`、`REMOVE`。
- 每项验证：正确上游/commit/license、消费者、专业增益、是否重复、是否只是 prompt 堆积、运行依赖、更新和退出策略。
- 清理重点：无来源/无 rights/无测试/无消费者的 prompt、重复 skill、失效链接、旧宿主身份文档；有历史价值但无运行价值的移入 history 并从活动索引删除。
- 验收：active 来源与能力数量由生成器得出；accepted evidence 不因清理虚增；SBOM、NOTICE、license 和 provenance 完整。

### DL-100 — E4/E5 与发布收敛

- 优先级/状态：`P2 / TODO`
- 依赖：DL-020、DL-050，以及本期选中的 DL-030/040/060/070。
- 运行 Canonical、Python、MiniGame fixture、host/tool E3、人工 Jury、production preflight 和 exact-SHA CI。
- 发布包必须包含 editable sources、preview、BOM、rights、quality、preflight、provenance、rollback，而不是只给 PNG/视频。
- 独立复审后再更新 capability evidence floor；未达到的 adapter 保持 E0/E1/BLOCKED。

## 5. 底座与融合最终裁决

| 候选 | 角色 | 当前裁决 |
|---|---|---|
| Open Design | 参考宿主/产品入口 | 已采用 adapter 路线，需当前版本 live requalification |
| OpenPencil / Penpot | 可编辑 UI/矢量工具 | 单选 bake-off，不做产品内核 |
| CLI-Anything | 创意软件 adapter 生成/测试基座 | 优先融合 harness 方法和少量工具 adapter |
| Krita AI Diffusion / InvokeAI | 图像生产 runtime | 有真实缺口后单选，外置运行 |
| Adobe/Figma/Blender/FFmpeg | 专业生产工具 | 官方 API/CLI/MCP/UXP/脚本 adapter；写操作需人工门 |

## 6. 明确不做

- 不重写 Open Design 或新建第二画布/聊天前端。
- 不把 648/2424 个 skill/能力数量当作质量；没有消费者和证据就清理或隔离。
- 不把图片相似度、VLM 自评或 schema pass 冒充商业可用。
- 不在未安装 Adobe、新建专用 Eagle 库或获得用户批准前伪造工具 E3。
- 不把设计知识迁到 WORK-LAB；WORK-LAB 只传执行与上下文收据。

## 7. 最终交付物

- 与 exact SHA 绑定的生成状态和根操作指南
- Open Design 当前版本 E3 requalification 包
- 可编辑 UI/矢量工具单选裁决
- CLI-Anything 驱动的 2 个真实创意工具 adapter
- 五黄金案例、12 Evidence Cards 和真实 REJECT/修复样本
- 可编辑生产交付与专业 preflight
- ArcheAxis candidate/verified knowledge 双向接口
- 开源资产减法台账、SBOM 和 exact-SHA 发布收据

