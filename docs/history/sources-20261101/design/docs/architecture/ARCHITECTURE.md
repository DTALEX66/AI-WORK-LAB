# ARCHITECTURE — DESIGN-LAB 技术架构

- 版本：`1.0`｜状态：`ACTIVE`｜SSOT 角色：架构契约
- 定位：**Agent-platform-neutral** design intelligence and production laboratory for professional visual design with **commercial** production preflight and editable delivery; host-native, no default binding.

## 目标树（DL-DIR-MIG 后真实结构，与 `git ls-tree HEAD` 对齐）

```text
DESIGN-LAB/
├─ apps/
│  └─ workbench/                   # runnable frontend（strict-TS convergence 目标，§24/25）
├─ src/design_lab/                # Python runtime —— 唯一允许新运行时代码的根
│  ├─ adapters/  analysis/  assurance/  creative/  generators/
│  ├─ governance/  interop/  readiness/  reconstruction/  runtime/
│  ├─ http_service.py  service.py  workbench.py  cli.py  __main__.py
│  └─ native_*.py  task_*.py  image_assets.py
├─ packages/                       # 可复用设计能力（不含新运行时）
│  ├─ capabilities/
│  └─ design-system/               # 中立可复用设计协议资产
├─ integrations/                   # 宿主/工具/模型边界（host-native，无默认绑定）
│  ├─ hosts/  {adobe,blender,eagle,ffmpeg,figma,minimax-design,open-design,penpot}
│  ├─ executors/  generators/  mcp/
│  └─ adapter-registry.json
├─ design-lab/                    # 内容/契约/测试（authoring root，禁止新增运行时）
│  ├─ config/  schemas/  core/  domain-packs/  design-systems/
│  ├─ evals/  research/  production/  templates/  assets/  profiles/
│  ├─ tests/  scripts/  prompts/  skills/  memory/  readiness/
├─ fixtures/                      # 测试/回归夹具
├─ research/                      # 素材 intake
├─ vendor/                        # 锁定/最小审阅来源
├─ docs/                          # 人类权威/历史
│  ├─ current/                    # PRODUCT_DEFINITION.md（活动）
│  └─ architecture/              # ARCHITECTURE/BOUNDARY_CONTRACT/DIRECTORY-AUTHORITY/
│                                 #   LANGUAGE-POLICY/OBJECT_MODEL（活动契约）
├─ reports/                       # 投影/证据索引
├─ scripts/                       # 薄仓库工具
├─ .project/                      # 被跟踪的项目策略
└─ .project-local/               # 全部本地运行时状态（被 Git 忽略）
```

> 历史子树 `design-lab/{intelligence,atoms,bundles,scenarios,quality,knowledge,adapters}`
> 与 `integrations/adapters/{agents,hosts,creative-tools}` 已在 DL-DIR-MIG 中重构/消失，
> **不得再作为 current target 引用**。宿主适配已迁至 `integrations/hosts/<host>/`。

## 分层（对应真实目录）

1. **对象/契约层**：`design-lab/{schemas,config,core}` —— 中立 JSON schema、被检查的注册表、对象/契约/策略内容；
2. **运行时层**：`src/design_lab/` —— 唯一允许新运行时代码的根（含 `runtime/`、`governance/`、`http_service`、`workbench`）；
3. **可复用能力层**：`packages/{capabilities,design-system}` —— 中立可复用设计能力与协议资产；
4. **宿主/工具边界层**：`integrations/{hosts,executors,generators,mcp}` —— host-native 适配器（Adobe/Blender/Eagle/Figma/FFmpeg/MiniMax/Open Design/Penpot），无默认绑定；
5. **内容/领域层**：`design-lab/{domain-packs,design-systems,templates,assets,profiles,prompts}`；
6. **质量/生产/证据层**：`design-lab/{evals,research,production}` —— E0–E5 证据（evidence）、Preflight/Handoff/Provenance/Rollback；
7. **前端层**：`apps/workbench` —— 可运行前端（strict-TS convergence 目标）；
8. **索引层**：`reports/`（投影/证据索引）+ `research/`（intake）。

## Host compatibility without product pollution

`open-design.json` 文件名与上游 `$schema` 仅在其是字面 Open Design payload 时保留，且必须标记 `hostAdapter: open-design`。Open Design 特定安装/doctor/scaffold/runtime 代码位于 `integrations/hosts/open-design/`。不得因字符串含"Open Design"而全局改名上游契约；也不得以旧名作为活动 core 文档的默认产品身份。
