# DESIGN-LAB（设计实验室）

> **面向职业视觉设计的、AI 原生、平台中立的设计智能与生产能力实验室。它把设计研究、合规知识、设计方法、领域能力、视觉质量、专业工具适配、生产预检（commercial preflight）、可编辑交付和证据体系（evidence & provenance）组织为可组合、可执行、可验证、可回滚的设计能力闭环。**

> **Agent-platform-neutral design intelligence and production laboratory for professional visual design. Host-native; no default host, agent, or model binding.**

## GitHub 交付

> 上传/审核云端库请见 [`GITHUB_DELIVERY.md`](GITHUB_DELIVERY.md)（WORK-LAB 交付加速器：上传一键推送 + PR 审核聚合判定）。

## 一屏说明

**DESIGN-LAB 不是第二个设计软件前端，也不是静态资料库。** 它是一个**产品化的设计能力系统**：

```text
研究/开源资料                    = 受治理的知识与证据底座
可测试的 Method / Rubric / Pack   = 可复用专业能力
Host / Agent / Tool Adapters      = 在现有工作界面中执行能力
Preflight / Handoff / Evidence    = 商业生产闭环
```

设计师在已接入的宿主/工具 Adapter（Open Design、Adobe/Figma/Blender/ComfyUI 等，按需接入）中工作；DESIGN-LAB 自身可独立完成设计生产闭环（Standalone-first，ADR-001），提供合同、方法、质量门、可编辑交付和适配器。**host-native first，不重建第二画布、聊天客户端、模型网关或通用 SaaS 后端，不依赖未安装的外部项目。**

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
旧 `generate_project_status.py` 入口转发到同一生成器。

## 验证入口

```bash
python design-lab/scripts/verify_design_lab.py   # 全验证链
python -m pytest design-lab/tests/               # 单元 + fixture 测试
```
