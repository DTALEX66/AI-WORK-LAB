# START HERE — DESIGN-LAB（唯一入口）

> 本文件是唯一的项目总入口。旧 V2/V2.1/V3/V4 活动入口已归档；当前 SSOT 以 `docs/PRODUCT_DEFINITION.md`、`docs/BOUNDARY_CONTRACT.md` 和 `design-lab/config/product-manifest.json` 为准。

## 定位
以 **平台中立、Host-native first** 为原则，面向职业视觉设计的**设计智能与生产能力实验室**（唯一权威定义：`docs/PRODUCT_DEFINITION.md`，边界合同：`docs/BOUNDARY_CONTRACT.md`，并与 `design-lab/config/product-manifest.json` 一致）。当前 Open Design 只是参考 Host，不是默认绑定。

配套合同：`docs/BOUNDARY_CONTRACT.md`（职责边界）、
`docs/USER_MODES.md`（用户模式）、
`docs/OBJECT_MODEL.md`（核心对象模型）。

Open Design 拥有 Studio/画布、Agent 启动、插件/Scenario/Atom 运行、Artifact、预览与导出；本仓库负责专业设计方法、Domain Pack、视觉质量、来源权利、生产预检、可编辑交付、Benchmark 与证据。本仓库**不拥有第二前端、Agent runtime、模型网关、账号系统或泛用向量库**。

## 唯一权威任务包
当前唯一活动执行入口是 **R4 Governance Closure & Anti-Drift（命名空间 `DL-*`）**。旧 V2/V2.1/V3/V4/ODA4 任务卡均为历史参考（`reports/history/`、`docs/history/`），禁止机械重跑或新增旧命名任务（DL-MIG-004）。

## 三个公开入口
1. `commercial-design-core` — 商业设计路由与核心
2. `visual-quality-core` — 视觉质量与去 AI 味
3. `production-handoff` — 生产预检与可编辑交付

内部 21 个 Atom 是可测试组件；7 个旧插件为兼容适配器（见 `config/entrypoint-convergence.json`）。

## 生成状态（DL-MIG-005）

- `reports/current/PROJECT_STATUS.md` / `.json` — 由 `scripts/generate_project_status.py` 生成（来源/能力/测试/资产计数不手写）

## 能力索引（机器 SSOT 生成）
- `design-lab/config/CAPABILITY_INDEX.md`
- `design-lab/config/product-manifest.json`（SSOT）

## 验证链
```bash
python design-lab/scripts/verify_design_lab.py
python scripts/run_python_tests.py
cd minigame-runtime && node scripts/run-tests.cjs
```

## 证据分级
无 E3 不称运行可用；无 E4 不称发布完成；无 E5 不称商业验证完成。

## 边界
- 不访问 E:\；不读凭据；不写项目外目录。
- 默认不 commit/push/PR/merge/tag/release；只有当前请求明确授权时才执行远端写入。人工验收、Photoshop、真实 Host 运行和商业生产证据不能由静态验证代做。
