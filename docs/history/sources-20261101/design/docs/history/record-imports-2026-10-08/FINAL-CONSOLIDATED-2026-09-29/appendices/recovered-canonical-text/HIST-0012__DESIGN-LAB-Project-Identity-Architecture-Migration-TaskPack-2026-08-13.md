# DESIGN-LAB 项目身份与架构迁移任务包

**日期：** 2026-08-13  
**状态：** 远端仓库重命名已确认；内部身份迁移待实施  
**目标身份：** `DESIGN-LAB` / `设计实验室` / `design-lab`  
**仓库：** `DTALEX66/DESIGN-LAB`（原 `OPEN-DESIGN-Assistance` 已直接重命名）  
**审计基线：** `DTALEX66/DESIGN-LAB`，`main` @ `f8664ee24ea7d373d6a1a0056387fef47d3f99ab`

## 0. 决策记录（不可重新解释）

从本迁移开始，唯一活动项目身份为：

```text
英文正式名：DESIGN-LAB
中文正式名：设计实验室
技术 ID：design-lab
仓库名：DTALEX66/DESIGN-LAB
本地目录：D:\All projects\DESIGN-LAB
```

`OPEN-DESIGN-Assistance`、`Open Design Assistance`、`opendesign-assistance`、`Design Intelligence Layer`、`Design Intelligence Capability Kit` 退出产品、目录、Schema namespace、任务 ID、脚本、CI、活动文档和默认运行时命名。

历史名称仅可在下列三种位置出现：历史档案、明确标注的来源、明确标注的第三方 Host Adapter/兼容对象。它们不得再定义产品身份、默认入口或核心能力。

**正式定位：**

> DESIGN-LAB（设计实验室）是一个面向 AI Agent、设计师、设计平台和专业创意工具链的开放式职业设计研究、智能增强与生产能力实验平台。它将专业设计知识、设计方法、领域能力、视觉质量判断、AI 设计智能、创意工具适配、生产预检、可编辑交付和能力证据，组织为可组合、可调用、可验证、可持续演进的设计能力体系。

产品类别为 **AI-Native Professional Visual Design Lab（AI 原生职业视觉设计实验室）**。Design Intelligence 是内部能力层，不是第二个产品名。

## 1. 云端审计结论

| 项目 | 证据与结论 | 判定 |
| --- | --- | --- |
| 远端仓库 | `DTALEX66/DESIGN-LAB` 已存在，仓库 ID 与旧 URL 指向同一对象；默认分支为 `main`。旧 URL 的重定向是 GitHub rename 兼容行为 | 仓库身份切换已完成 |
| 本地目录 | 用户确认原 OP 本地仓库已改名为 `D:\All projects\DESIGN-LAB`；当前网页端/审计沙箱无法读取该本机路径 | 用户确认；待使用者本机 readback |
| 默认分支 | 当前 `main` 为 `f8664ee…99ab`，最后提交为平台中立化文档更新 | 可作为迁移基线 |
| 活动根目录 | `opendesign-assistance/` 约占 427 个跟踪文件；产品 Manifest、Schema、Verifier、README 与路径均硬编码旧身份 | P0 身份漂移 |
| 旧名覆盖 | 审计到约 920 处旧名文本命中（跨字段和短语有重叠，不可直接相加为独立文件数） | 不能做机械全局替换 |
| 当前架构资产 | 已有 Design Core、Atoms、Bundles、Scenarios、Domain Packs、Quality、Production/Handoff、Evidence、Adapter Registry；约 112 个登记源、21 Atoms、6 Scenarios、3 公共 Bundles、19 Rubrics | 值得迁移，不应重建 |
| 验证 | 总验证器在审计快照输出 `467/467`；Python 全量测试在本审计环境因缺少 `jsonschema` 出现 5 个环境错误，不能据此声称 main CI 已绿；远端 main 的 CI 运行记录也未能由当前连接器读取 | `UNVERIFIED_MAIN_CI` |
| MiniGame | 冻结边界和 README 顶部已将其定义为游戏 UI/视觉设计 fixture/runtime reference；但 README 内部、`game.manifest.json` 和部分测试仍保留“小游戏合集平台”、IAA 广告位、新内容包和发行流程 | 已向游戏设计转向，但 P0/P1 旧产品语义尚未清除 |

**总体判定：** 仓库和本地目录的外部身份切换已完成；项目能力资产可迁，但内部目录、Schema namespace、Manifest、验证器和活动文档仍不可直接视为 DESIGN-LAB 完成态。迁移前必须先冻结 MiniGame 漂移、建立稳定 SSOT、替换旧 namespace，并重新生成当前树的证据。不得把历史 V4.2/E3 证据冒充为 DESIGN-LAB 当前树证据。

## 2. 产品边界

DESIGN-LAB 是：

```text
Design Intelligence
Professional Design Knowledge
Domain Capability
Visual Quality
Creative Tool Adapter
Production Intelligence
Editable Delivery
Research / Benchmark / Evidence
```

DESIGN-LAB 不是：

```text
第二套 Adobe / Figma / Agent / 聊天客户端 / 模型网关 / 通用自动化平台
单纯 Prompt 仓 / 静态资料库 / 素材下载站 / 大师模仿器
```

不新增独立 Agent Runtime、通用 SaaS 后端、第二个前端或模型聚合网关。Hermes、Codex、Claude Code、OpenCode、Aider 等只可作为 `Agent Interface / Execution Coordinator`。Open Design 仅是 Host Adapter，不是默认入口；Adobe、Figma、Blender、ComfyUI 等仅是 Creative Tool Adapter。

## 3. 目标能力模型

```text
DESIGN-LAB
├─ 01 Design Intelligence
├─ 02 Professional Domains
├─ 03 Visual Quality
├─ 04 Creative Toolchain
├─ 05 Production & Handoff
└─ 06 Research & Evidence
```

专业领域至少按能力包组织：Graphic、Brand、UI/UX、E-commerce、Editorial、Packaging、Spatial、Exhibition、3D、Motion、Video、Audio、Game。公共入口保留并迁移：

```text
commercial-design-core
visual-quality-core
production-handoff
```

### 3.1 视觉设计为第一主线

DESIGN-LAB 的范围仍覆盖完整职业设计链路，但资源优先级从“泛设计能力集合”收束为**视觉设计智能与生产**：

```text
品牌视觉 / 平面与编辑 / UI·UX / 电商视觉 / 空间与展陈
3D / 动效 / 视频视觉 / 游戏视觉与交互界面
  → 视觉方向、设计系统、材质与版式、质量评审、可编辑交付
```

这不是只做静态视觉资料库：所有领域仍必须通过 Brief、设计推理、Visual Quality、Tool Adapter、Production/Handoff 和 Evidence 的闭环。游戏设计在本项目中以**游戏视觉设计、HUD/UI、交互反馈、场景氛围、皮肤系统、图标/动效和可运行视觉 fixture**为范围；不得重新扩张为小游戏产品、发行平台、广告变现或运营系统。

标准工作闭环：

```text
Brief / 商业目标 / 权利与约束
  → 设计推理与专业方法
  → Domain Pack + 质量 Rubric
  → 可选 Agent / Host / Tool Adapter
  → 可编辑产物
  → Production Preflight
  → Evidence + Human Decision
  → 可回滚交付
```

人始终在 Brief、参考物授权、审美方向、关键设计判断、生产放行和最终交付节点做决定。自动化不能绕过这些决策。

## 4. 目标目录与迁移映射

```text
DESIGN-LAB/
├─ design-lab/
│  ├─ core/
│  ├─ intelligence/
│  ├─ atoms/
│  ├─ bundles/
│  ├─ scenarios/
│  ├─ domain-packs/
│  ├─ adapters/
│  │  ├─ agents/{hermes,codex}/
│  │  ├─ creative-tools/{adobe,comfyui,figma,blender,penpot,ffmpeg,minimax-h3}/
│  │  └─ hosts/open-design/
│  ├─ quality/
│  ├─ production/
│  ├─ knowledge/
│  ├─ research/
│  ├─ evals/
│  ├─ schemas/
│  ├─ config/
│  ├─ scripts/
│  ├─ templates/
│  └─ assets/
├─ design-system/
├─ minigame-runtime/
├─ project-memory/
├─ reports/
└─ README.md
```

| 现有对象 | 目标对象 | 迁移规则 |
| --- | --- | --- |
| `opendesign-assistance/` | `design-lab/` | `git mv`，再逐项修订内部 ID、Schema、路径和文档；禁止批量替换后直接提交 |
| `open-design.json` | 保留为 Host Adapter 描述符 | 文件名和上游 `$schema` 可保留，但必须明确属于 Open Design Host Adapter；不得再充当核心产品 manifest |
| 旧 `plugins/` 和宿主专用 runtime 文档 | `design-lab/adapters/hosts/open-design/` 或其兼容投影 | 先维持可兼容的打包路径，再逐步引入中立 canonical manifest；不破坏上游契约 |
| `verify_open_design_assistance.py` | `verify_design_lab.py` | 将根目录、namespace、任务 ID、默认运行时等硬编码替换为中立规则 |
| `generate_open_design_indexes.py` | `generate_capability_indexes.py` | 输出中立 capability index；旧索引保留为历史可追溯记录 |
| V4/V42/FINAL 活动文件 | `project-memory/history/` | 历史内容、旧 SHA、旧哈希不得改写；活动 SSOT 另建 |
| 活动报告 | `reports/` | 旧报告进 `reports/history/`，并在历史索引保留旧树 SHA 与原证据指针 |

活动 SSOT 只保留：

```text
project-memory/
├─ PRODUCT_DEFINITION.md
├─ ARCHITECTURE.md
├─ BOUNDARY_CONTRACT.md
├─ ROADMAP.md
├─ OBJECT_MODEL.md
├─ USER_MODES.md
├─ NEUTRALITY_POLICY.md
├─ EVIDENCE_POLICY.md
├─ ADAPTER_POLICY.md
└─ history/
```

版本使用文件元数据、Git commit、tag 和精确 SHA 管理；不再以 `V42_FINAL_FINAL2.md` 类文件作为活动 SSOT。

## 5. Manifest、Schema 与中立性契约

新的产品 manifest namespace 固定为：

```json
{
  "schemaVersion": "design-lab/product-manifest/v1",
  "product": { "id": "design-lab", "name": "DESIGN-LAB" }
}
```

Schema `$id`、生成器、SBOM/CPE、报告头、测试 fixture、CI display name、脚本名、任务 ID 必须同步迁移到 `design-lab`。`primaryRuntime`、`fiveNeutralities`、`rightsNeutral` 从产品契约移除。

替代规则：

```text
Model Neutral
Agent Neutral
Host Neutral
Tool Neutral
Domain Neutral
Style Neutral
Version Neutral
Rights Governed
```

`Rights Governed` 表示每个外部模型、素材、字体、参考图、工作流、节点和输出都需记录来源、许可证、允许用途、版本/哈希和责任人；它不是“版权中立”。运行时具体 Host、Agent、模型或工具选择只能保存在项目级/本地环境选择中，不能回写为产品默认身份。

## 6. Creative Toolchain：Adobe、MiniMax H3、ComfyUI

### 6.1 Adobe

Adobe 是 `design-lab/adapters/creative-tools/adobe/` 下的一组适配器，Photoshop 为首个 MVP；绝不新建 Adobe 平台。目标结构：

```text
adobe/
├─ common/
├─ photoshop/{uxp,commands,schemas,tests}/
├─ illustrator/
├─ indesign/
├─ premiere/
├─ after-effects/
├─ acrobat/
├─ lightroom/
└─ firefly/
```

通用链路是 `AI/Agent → Tool Contract/MCP → Tool Adapter → UXP/Script/API/Plugin → 可编辑源文件`；屏幕鼠标自动化只允许作为人工观察下的最后兜底。

### 6.2 MiniMax H3：媒体模型适配器，不是项目中枢

新增位置：`design-lab/adapters/creative-tools/minimax-h3/`，推荐稳定 ID：`model-minimax-h3`。

MiniMax 官方将 H3 描述为可接收文本、图像、视频、音频输入并生成原生视听内容的全模态生成模型；公开信息提到最长 15 秒、2K 的输出能力。[MiniMax H3 公告](https://minimaxi.com/blog/minimax-h3)

当前任务只建立 **声明级（E0）** 合同，不能虚构官方 API 模型 ID、端点、价格、权重、许可证或 ComfyUI 节点。官方 API 总览的已列模型与 H3 公告可能存在发布节奏差异，实施时必须重新锁定官方契约。[MiniMax API 总览](https://platform.minimaxi.com/docs/api-reference/api-overview)

H3 适配器职责：

```text
接受经授权的 MediaGenerationRequest
→ 检查 Brief、参考物、时长/分辨率、品牌与权利约束
→ 调用经批准的官方提供方合同（若已具备）
→ 保存不可伪造的请求、版本、输出、权利与质量证据
```

H3 不承担通用推理、Agent 编排、知识库入口或默认模型角色。对本地 RTX 3060 Ti 8G 环境不得承诺 H3 本地推理；是否可本地运行必须以官方权重、硬件要求和实际试验为准。密钥仅由使用者在本地环境配置，禁止进入仓库、前端、日志和证据包。

### 6.3 ComfyUI：用户自有的本地工作流执行器

新增位置：`design-lab/adapters/creative-tools/comfyui/`，稳定 ID：`tool-comfyui-local`，运行模式为 `external-local-api`。ComfyUI 官方文档说明其本地节点工作流和本地 API；工作流以 JSON 表示，提交 API 工作流后以 prompt ID 异步查询结果。[ComfyUI 文档](https://docs.comfy.org/) [工作流格式](https://docs.comfy.org/development/core-concepts/workflow) [API 概览](https://docs.comfy.org/development/overview)

ComfyUI 只能作为用户自行安装、用户自行启动的外部本地工具：

```text
DESIGN-LAB 生成已审查的工作流/参数包
→ loopback-only ComfyUI API
→ prompt_id / 输出轮询或 WebSocket
→ 产物、workflow JSON、依赖清单、预检和证据
```

硬规则：不自动安装 ComfyUI、模型或自定义节点；不 vendoring ComfyUI；不托管常驻 daemon；不开放公网端口；不新增 DESIGN-LAB 后端或 UI；不在未审查的情况下下载/执行节点、工作流或模型。每个可执行工作流必须钉住 ComfyUI 版本、节点版本/来源、模型 hash、许可证、输入、输出和批准记录。

### 6.4 H3 与 ComfyUI 的关系

两者先独立适配，不能直接声称已经互通。仅当同时满足以下条件，才可建立 `minimax-h3 → comfyui` bridge：

1. MiniMax 已公开且可核验的 H3 权重，或存在经审查、版本锁定、许可清晰的官方/可信提供方接口或节点；
2. ComfyUI workflow 在干净、本地、loopback-only 环境可复现；
3. 节点/模型/工作流均有 SBOM、哈希、许可证和回滚版本；
4. 成功完成 E3 实际执行、视觉质量 Rubric 与人工验收。

在此之前，H3 为 `E0 DECLARED`，ComfyUI 为 `E0 DECLARED` 至 `E1 CONTRACTED`；不得使用“已集成”“本地可跑 H3”或“官方 ComfyUI 节点”等表述。

建议中立请求模型：

```text
MediaGenerationRequest
  brief + permittedReferences + brandConstraints + productionConstraints + rights
    → adapter negotiation
    → model-minimax-h3 | tool-comfyui-local | other approved adapter
    → editable/traceable Artifact
    → visual-quality + production preflight + evidence
```

Adapter contract enum 应新增 `external-local-api` 与 `external-provider-api`；原有 `in-process`、`process-isolated`、`external-cli`、`none` 保持兼容。任何 direct provider adapter 必须是 `external-provider-api`，没有已锁定官方 H3 契约前不得启用。

## 7. MiniGame 冻结边界修复（切换阻断项）

`minigame-runtime/` 保留为冻结的**游戏视觉设计 fixture/runtime reference**，不得删除、回迁到 WORK-LAB 或扩展为活动产品。它可接受的变更仅限安全、构建、资产、测试、游戏 UI/HUD/交互视觉/皮肤/场景氛围和视觉 fixture 修复。

迁移前完成以下工作：

1. 将现有冻结边界与 README 顶部的“游戏 UI/视觉设计 fixture/runtime reference”提升为唯一有效身份；明确游戏设计范围是视觉、HUD/UI、交互反馈、皮肤、场景与资产规范。
2. 修订 README、`AGENTS.md`、游戏 manifest、定位文档和测试断言，删除或历史化“小游戏合集平台”、IAA 广告位、商业化、发版、后续内容包、平台扩张、运营措辞。
3. 将多端 runtime/build 脚本标为视觉 fixture 的兼容/回归验证，不作为发行能力或活动产品功能入口。
4. 添加防漂移测试：拒绝 `platformRole: launch-game`、IAA/广告位、monetization、new content pack、release roadmap 等活动产品表述；允许仅为旧证据保留的历史档案必须位于明确 history 路径并被 allowlist 精确限定。
5. 重跑 `npm test` 并建立新的边界证据。

此项未完成前，DESIGN-LAB 不可切换为已交付状态。

## 8. 任务序列与验收

| ID | 任务 | 主要产出 | 必须通过的验收 |
| --- | --- | --- | --- |
| DL-MIG-000 | 冻结与可回滚基线 | 精确 SHA、清洁工作树、变更清单、回退指令 | 无直接修改 main；无删改历史证据 |
| DL-MIG-001 | MiniGame 游戏视觉定位封口 | 游戏视觉 fixture 边界、修订测试与文档 | 321+ 测试及新防漂移规则通过；无活动平台/广告/运营身份；HUD/UI/皮肤/视觉测试可保留 |
| DL-POS-001 | 建立活动 SSOT | 9 个稳定文档与术语表 | 每个活动入口只使用 DESIGN-LAB 身份 |
| DL-ARC-001 | 重构产品 manifest/schema | `design-lab/*/v1`、中立性与 Rights Governed 契约 | schema/fixtures/generator 全部通过；无 `primaryRuntime` |
| DL-MIG-002 | 树与脚本迁移 | `design-lab/`、新 verifier/index generator | `opendesign-assistance/` 不再是活动根；兼容 Host payload 精确隔离 |
| DL-ADP-001 | Adapter Policy/Registry V3 | host、agent、tool/model 的中立 registry | Host/Agent/Tool 未设置默认主入口；本地选择不入库 |
| DL-ADP-002 | ComfyUI 合同 | `tool-comfyui-local`、workflow/dependency/evidence schema | loopback、无自动安装、E0/E1 状态和测试成立 |
| DL-ADP-003 | MiniMax H3 合同 | `model-minimax-h3`、provider contract schema | E0，仅接受已钉住官方合同；无假定 endpoint/价格/权重 |
| DL-ADB-PS-001 | Photoshop MVP 适配器 | 最小可逆、可编辑文件操作合同 | 仅在明确宿主实际验证后升为 E3 |
| DL-QLT-001 | 视觉质量迁移 | 跨领域 Rubric/评审节点 | 质量门可追踪且保留人工批准 |
| DL-PRD-001 | 生产与可编辑交付 | Preflight、handoff、rollback 包 | 字体/颜色/分辨率/格式/许可证均可审计 |
| DL-EVD-001 | 重新取证 | 新树 hash、SBOM、测试报告、E0–E5 索引 | 历史 V42 E3 明确标为历史；新树逐级重测 |
| DL-MIG-003 | 仓库/本地身份切换 | GitHub rename、origin readback、本地目录切换 | **远端 rename 已确认；本地改名由用户确认**。内部迁移完成后读取 origin、README、CI、clone URL 和本地路径，确认没有遗留活动身份 |
| DL-REL-001 | 首次迁移发布门 | release checklist / tag proposal | CI、兼容、权限、证据、人审全部通过后才可合并 |

新任务只使用：`DL-POS`、`DL-ARC`、`DL-CORE`、`DL-INT`、`DL-DOM`、`DL-QLT`、`DL-ADP`、`DL-ADB`、`DL-PRD`、`DL-EVD`、`DL-MIG`。旧 `V42-*` 只在历史文档中保留原样。

## 9. 实施顺序与控制点

1. 从精确基线新建迁移分支，例如 `migration/design-lab-identity-20260813`；禁止直接在 main 改名。
2. 先完成 DL-MIG-001，再建立 SSOT、边界和 adapter policy；此阶段不移动大量文件。
3. 使用 `git mv` 做结构迁移，按 domain 小批次修改并逐批运行验证；不得使用“全仓替换旧名”作为迁移手段。
4. 宿主兼容 descriptor 必须以 allowlist 管理：旧 Host 名只能出现在 `adapters/hosts/open-design/`、明确的兼容 payload、来源说明和 `history/`；CI 必须拒绝其他活动路径中的旧身份词。
5. 全部 schema、生成索引、SBOM、验证器、fixtures 和活动文档完成后，重新生成证据。为新树运行 Python venv，并从 requirements 安装 `jsonschema` 后再判断测试结果。
6. GitHub 仓库 rename 与用户本地目录切换已完成，**不得重复 rename 或重新创建仓库**。内部迁移完成后，读取远端 `origin`、默认分支、clone URL、CI badges、release links 和 exact SHA；确认无活动旧身份后才允许合并/发布。

## 10. 防漂移机制（持续强制）

新增 `identity-boundary` CI gate，最低要求：

```text
1. 产品 ID/目录/Schema/README/CI 必须为 design-lab。
2. Open Design 只能出现在精确 allowlist 的 Host Adapter、历史或来源文件。
3. 不允许 primaryRuntime、默认 Agent、默认模型、默认 Host 写入产品 manifest。
4. 新 adapter 必有 type、mode、owner、version、rights、evidence level、rollback、scope。
5. 未通过 E3 的 adapter 不得被 README、roadmap 或 UI 表述为“已集成/可用”。
6. ComfyUI 禁止公网监听、自动安装/下载或执行未知 custom node。
7. MiniGame 仅允许游戏视觉设计 fixture：禁止平台化、广告/商业化、运营/发版、玩法和内容包扩张；允许 HUD/UI、皮肤、图标、交互视觉、场景与资产规范的有证据改进。
8. E0–E5 证据与其 bound tree SHA 绑定；移动/改名后必须重新取证。
9. 每个 PR 必须声明：身份影响、边界影响、adapter 影响、权利影响、证据影响和回滚方式。
```

## 11. 最低验证矩阵

| 层 | 必测项 |
| --- | --- |
| 文件/身份 | `rg` 旧名 allowlist 扫描、目录和 Git path 验证、文档链接检查 |
| Schema | 产品 manifest、adapter registry、MediaGenerationRequest、workflow/dependency/evidence JSON schema fixtures |
| 代码 | `verify_design_lab.py`、`generate_capability_indexes.py`、Python 测试（依赖完整 venv） |
| MiniGame | `npm test`、冻结边界/反平台化断言 |
| Host 兼容 | Open Design adapter payload 的静态检查和实际宿主 smoke test；旧 E3 不能复用 |
| ComfyUI | 只在使用者启动的 loopback 实例上做已批准 workflow 的 E3 test；保存 prompt、workflow、依赖和输出证据 |
| H3 | 仅在官方契约可核验后进行 provider contract test；如要 bridge，再做完整 E3/许可/质量/人工验收 |
| 交付 | Preflight、可编辑源文件、SBOM、许可证、回滚包、精确 SHA 和人工放行 |

## 12. 发布门与回滚

**不得合并/发布的阻断条件：** MiniGame 仍含活动平台/IAA 身份；活动路径仍含旧产品身份；schema 或总验证器未通过；Python 依赖环境未完整验证；当前树没有新证据；H3/ComfyUI 被夸大为已集成；外部工具存在自动安装、公网暴露、凭据入库或权利不明。

**回滚原则：**

```text
所有迁移仅在迁移分支完成
→ 每个阶段保留可检出的 Git SHA 与报告
→ GitHub rename 前不得删除任何可恢复的工作树
→ rename 后若验证失败，优先恢复默认分支/原远端名与 origin，不重写历史、不删除证据
```

## 13. 当前批准状态

本任务包批准的是：审计结论、目标身份、目标架构、H3/ComfyUI 的中立适配方案、迁移顺序和验收门。

本任务包**不**批准：直接提交、推送、PR、合并、发布、读取/写入任何凭据、自动安装 ComfyUI/模型/节点，或把 MiniMax H3 宣传为已可用的本地/ComfyUI 集成。仓库 rename 已完成，不应重复执行。

**最终状态：** `REMOTE_REPOSITORY_RENAME_CONFIRMED`；`LOCAL_RENAME_USER_CONFIRMED`；`INTERNAL_IDENTITY_MIGRATION_PENDING`。整体仍为 `NOT_READY_FOR_CUTOVER`：先完成 `DL-MIG-001`、`DL-POS-001`、`DL-ARC-001`、`DL-MIG-002` 和重新取证，再进行最终一致性确认。
