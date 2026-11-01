# 视觉设计实验室 · DESIGN-LAB
**Visual Design Lab**

> 面向职业视觉设计的 **AI 原生、平台中立、宿主原生**的设计智能与生产能力层。它把设计研究、方法与
> 领域能力、视觉质量判断、专业宿主适配、生产预检（commercial preflight）与可编辑交付，组织成
> **可执行、可验证、可回滚**的闭环：Brief → Reference → Direction → Design System → 宿主原生产物
> → 读回（readback）→ 证据（evidence & provenance）→ 回滚。

> An AI-native, agent-platform-neutral, host-native design intelligence and production layer for
> professional visual design. Every capability claim is graded (E0–E5) and re-runnable; nothing in
> this repository is asserted on file existence alone.

## 它是什么 / 它不是什么

| 拥有（owns） | 不拥有（does not own） |
|---|---|
| Design Brief、Reference、Direction、Design System、Design IR、Domain Pack、Method | 第二个设计软件、第二画布、通用聊天客户端 |
| 专业 Jury、视觉质量、反 AI 痕迹、可访问性 | 通用 Agent runtime、模型网关、账号系统、通用知识库 |
| rights、production preflight、BOM、可编辑交付 | WORK-LAB 的跨软件全局配置 / 权限 / 任务 / Observer |
| provenance、readback、rollback、Host/Tool Adapter | ArcheAxis 的长期知识与学习状态 |
| 设计实践产生的受审 `KnowledgeCandidate` 出口 | 宿主的私有数据库与用户个人素材库 |

**Standalone-first（ADR-001）**：DESIGN-LAB 可独立完成完整设计生产闭环；启动、测试、恢复、
Golden Workflow **不探测也不要求** WORK-LAB 或 ArcheAxis（二者默认关闭）。Open Design 是可选的
宿主 / 工具 Adapter，不是运行依赖，也不享有预设入口的地位。设计师在已接入的专业宿主（Photoshop、
Illustrator、Figma、Blender 等）里做真正的原生编辑；工作台是**用户可见的设计控制面**，不是第二画布。

## 能力覆盖矩阵（声称口径，不是进度表）

本表只回答一个问题：**这类能力最高能被声称到哪一级，以及用什么复跑证明它。**
当前四轴实况一律由投影生成，读 [`reports/current/PROJECT_STATUS.md`](reports/current/PROJECT_STATUS.md)
与 [`design-lab/config/task-ledger-r3.json`](design-lab/config/task-ledger-r3.json)。
本表刻意不复制任何数字，因此不会与数字一起腐烂。

| 能力面 | 可声称的最高证据级 | 证明它的最小复跑 | 尚不能声称 |
|---|---|---|---|
| 工作台（Projects / Brief / References / Research / Directions / …） | E2 受控运行 | Workbench strict-TS gate + browser E2E + 溢出闸门（均为 required CI） | 人工视觉验收（E4，未执行） |
| 后端设计链路（Brief→Direction→Design System、状态、读回、证据） | E1–E2 结构与受控运行 | `python -m pytest design-lab/tests/` | 真实宿主产物链路（E3） |
| 宿主 Adapter（Photoshop / Illustrator，host-native JSX/UXP） | **E1 结构** | `python design-lab/scripts/verify_adapter_matrix.py`（E0/E1 only） | **E3 真实工作流：未读回** |
| 生成侧（ComfyUI 等） | E1–E2 | 合成 fixture 下的受控调用与读回 | 真实生产闭环 |
| 质量 / Jury | 自动质量 E1–E2；人工 Jury 未执行 | 自动评分、预检与交付就绪测试 | **E4 独立验收（禁止由 agent 执行）** |
| rights / preflight / 可编辑交付 / BOM | E1 合同 | 预检与交付就绪测试 | 商业出账认证（未达 E3/E4 不写"可交付"） |
| 发布与可重复性 | 无 | exact-SHA release + 安装 / 升级 / 恢复 | **E5 未达成** |

## 权威链（做任何审计或改动前，按此顺序读）

[`AUTHORITY.md`](AUTHORITY.md) →
[`.project/governance/authority-index.json`](.project/governance/authority-index.json) →
[`AGENTS.md`](AGENTS.md) → 当前 integrated TaskPack → **唯一任务账本**
→ live `main` / open PR / exact SHA / branch protection → CI 与 artifact →
[`reports/current/`](reports/current/)（仅在 freshness 校验通过后）→ 历史只经 crosswalk 用于解释血统。

记忆、会话摘要、交接文档、旧 TaskPack、旧报告、分支名、commit 数**一律不构成权威**；
只有落仓文件可以授权改动。Handoff 永远不是顶层权威。

## 唯一账本与四轴

- 唯一状态编辑源：[`design-lab/config/task-ledger-r3.json`](design-lab/config/task-ledger-r3.json)；
  冻结任务定义：[`docs/history/taskpacks/r5-20260908/tasks.json`](docs/history/taskpacks/r5-20260908/tasks.json)
  （原件逐字节哈希钉住，禁止用它编辑执行状态）。
- 四条独立记录轴：`implementation` / `unit` / `host_live` / `delivery`，**互不推断**。
  测试套件通过只支持 `unit`，不支持 `host_live` 与 `delivery`。
- 每条证据必须齐 6 个字段：`source_sha`、`environment_versions`、`commands_and_exit_codes`、
  `artifact_hashes`、`limitations`、`rollback_record`，并绑定 exact SHA。
- 历史证据不自动提升当前 SHA；**不批量翻牌**。`PARTIAL` 不是遮掩，含义是"这条轴还没有当期证据"。
- 生成时间不是测试时间；投影里的 Git 信息是生成时观察，不是此刻 HEAD。

## current / future / candidate

| 分区 | 含义 | 入口 |
|---|---|---|
| **current** | 现在就能用、且有当期证据的面 | 工作台（见下方一条命令）、设计与预检合同、自动质量、CI 闸门 |
| **future** | 已定义但当期无证据，按账本排期 | 真实宿主 E3（`DL-R5-011/012/015`）、DesignSystem→DesignIR→可编辑产物、人工 Jury E4、E5 发布 |
| **candidate** | 观察过但未吸收，不进能力计数 | [`research/candidates/`](research/candidates/)；上游 `AGENTS/SKILL/install/affiliate` 只作 inert 数据 |

## Ongoing

真正的视觉生产发生在专业宿主里，所以本仓库长期只有三类推进：**把某个能力面的证据等级往上顶**
（E1→E2→E3）、**把肉眼可见的界面缺陷修掉**（并同时给测量数字与对渲染像素的逐屏判读）、
**把账本逐任务复核做实**。其余治理文件只在权威链本身变化时才改。
"几何全绿"不等于"界面好"，两者必须同时取证。

## 视觉设计是第一主线

品牌视觉 / 平面与编辑 / UI·UX / 电商视觉 / 包装 / 空间与展陈 / 3D / 动效 / 视频视觉 / 游戏视觉与交互界面。

## 六能力域

```text
01 Design Intelligence    02 Professional Visual Domains    03 Visual Quality
04 Creative Toolchain     05 Production & Handoff           06 Research & Evidence
```

## 当前主目录 / 云端仓库

```text
主目录：D:\All projects\DESIGN-LAB
云端：  https://github.com/DTALEX66/DESIGN-LAB
```

## 目录职责

本机资料、模型与工具链的固定入口：[本机环境与外置目录](docs/LOCAL_ENVIRONMENT.md)；机器路径配置：[paths.json](.project/paths.json)。诊断先复用这些记录，不重复假设软件未安装。

```text
design-lab/     能力层：core / intelligence / atoms / bundles / scenarios /
               domain-packs / quality / production / knowledge / research /
               evals / schemas / config / scripts / templates / assets / adapters
packages/design-system/  中性设计协议资产（DESIGN.md / Schema / Tokens / component rules）
fixtures/domains/game-visual/  游戏视觉设计 fixture / runtime reference（冻结边界，非产品）
docs/  九份活动 SSOT + history/
reports/        阶段验收、证据与交接报告
```

## 关键文档

当前统一剩余任务入口：[FINAL Authority Convergence TaskPack](docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md)。
上传/审核云端库的 WORK-LAB 交付加速器说明见 [`GITHUB_DELIVERY.md`](GITHUB_DELIVERY.md)——
它是**外部项目的交付工具**，不是 DESIGN-LAB 的依赖、入口或组成部分（Standalone-first，ADR-001）。
R5 任务包仅作为冻结的产品血统与依赖定义，不是当前派工入口。
任务状态唯一编辑源：[版本化任务账本（保留原路径）](design-lab/config/task-ledger-r3.json)；
[生成状态](reports/current/PROJECT_STATUS.md)分代码、测试、宿主实机和交付四轴。
09-04/09-05 任务包保留为历史需求与映射来源；知识迁移继续延后。

```text
AUTHORITY.md                              ← 顶层权威
docs/current/PRODUCT_DEFINITION.md        ← 产品定义
docs/architecture/ARCHITECTURE.md         ← 技术架构
docs/architecture/BOUNDARY_CONTRACT.md    ← 职责边界
docs/decisions/NEUTRALITY_POLICY.md       ← 平台中立
docs/decisions/EVIDENCE_POLICY.md         ← 证据政策
docs/decisions/ADAPTER_POLICY.md          ← 适配器政策
docs/architecture/OBJECT_MODEL.md         ← 核心对象模型
docs/current/USER_MODES.md                 ← 五类用户
docs/current/ROADMAP.md                    ← 路线图
design-lab/config/product-manifest.json ← 机器可读 SSOT
```

## 主规则

1. **宿主原生交付**：按已验证的 Adapter/profile 选择宿主，Open Design 是可选适配器；工作台可用于任务与产物检查。
2. **本仓库增强专业判断与交付能力**：协议、知识、Domain Pack、质量门禁、预检、可编辑交付、证据。
3. **不做宿主替代品**：不重建画布/编辑器/模型网关/SaaS 后端。
4. **不把文件存在冒充运行可用**：静态文件/Manifest 只证明 E1；真实执行与读回才是 E3。
5. **平台中立**：产品契约不绑定默认 host/agent/model；宿主选择属于本地 profile/项目级配置。
6. **证据分级诚实**：E0–E5 各级不互相冒充；未达 E3 不写"已集成"。

## 已吸收内容（历史）

- 原 MINIGAME 游戏生产系统 → 收敛为 `fixtures/domains/game-visual/` 游戏视觉 fixture。
- 原 Design-system → 收敛为 `packages/design-system/` 中性设计协议资产。
- 旧 `OPEN-DESIGN-Assistance` 身份 → 历史归档（`docs/history/`、`reports/history/`），不再作为活动产品名。

## 生成状态（DL-MIG-005）

```text
reports/current/PROJECT_STATUS.md   ← 由 scripts/generate_current_reports.py 生成
reports/current/PROJECT_STATUS.json
reports/current/TASK_PROGRESS.json ← 由 design-lab/config/task-ledger-r3.json 投影
```

活动文档不手写测试数/能力数/来源数；一律引用生成状态。

生成全部当前报告：`python scripts/generate_current_reports.py`；
只读核对输入/产物哈希和内容漂移：`python scripts/generate_current_reports.py --check`。
报告中的 Git 信息是生成时观察，不是此刻 HEAD；`--check` 验证绑定输入与输出的完整性，不替代当前 Git 状态或 GitHub exact-SHA 读回。提交报告不会仅因提交自身改变 HEAD 而造成自引用漂移；更新源码/证据后仍需重新生成和验证。
`--check` 的两种非失败读数要分清：绑定输入（`inputHashes` 列出的那组文件）没变、只是 HEAD 前移了，返回 `STALE` 且退出码 0——这是设计语义，**不得当成产品通过**（DL-UCR-012 / FA-03）；绑定输入本身变了，才返回 `DRIFT` 且退出码 1，此时必须重新生成。因此**只有改动被绑定输入的合并**会让投影真正变红，其余合并只留下 `STALE`。
旧 `generate_project_status.py` 入口转发到同一生成器。

## 启动 Workbench（一条命令）

```bash
python -m design_lab --project <设计项目目录> workbench
```

- 首行输出 `{"status":"LISTENING","url":"http://127.0.0.1:<port>/workbench","token":"<64-hex>"}`；
  默认自动打开本机浏览器（`--no-browser` 关闭），把 token 粘进登录框即可进入。
- 只有一个进程：静态 UI 与 `/api/*` 同源，不需要先起别的内部服务。
- token 只存在于该进程与这次终端输出，不进命令行参数、不落盘，进程退出即失效。
- 脚本化/CI 场景用底层入口：`python -m design_lab --project <dir> serve --port <p>`，
  token 由 stdin 注入（`serve` 在 tty 上直接拒绝启动，避免误以为可以手敲）。
- 项目数据持久化在 `<项目>/.project-local/`；服务重启后项目、简报、方向与绑定仍在
  （`design-lab/tests/test_workbench_launch.py` 覆盖启动、CSP、bundle 与重启读回）。

## 验证入口

```bash
python design-lab/scripts/verify_design_lab.py   # 全验证链
python -m pytest design-lab/tests/               # 单元 + fixture 测试
```
