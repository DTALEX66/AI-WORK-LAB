# DL-DIR-MIG-R1 收尾交接 — 错误总结与仓库状态

- 日期：2026-09-03
- 分支：`migration/dl-directory-convergence-r1`
- PR：#112（feat: DL-DIR-MIG-R1 directory migration convergence）
- 任务包：13/13 完成（DL-DIR-110 测试矩阵、DL-DIR-120 旧目录清理均 completed）
- 文件数：3507 → 3258（-249）；跟踪文件现 3280（含本轮恢复文件）

## 一、本轮修复错误总结（按根因分类）

### 1. 迁移时"盲目批量替换"造成的三类回归（ERR 教训）
迁移过程中用全局替换把**代码内的逻辑引用一并改写**，超出"仅移动文件路径"的范围：

| 错误类型 | 具体表现 | 修复 |
|---|---|---|
| schema URI 被误改 | `design-lab/reconstruction-*/v1` → `packages/capabilities/reconstruction-*/v1`（`reconstruction-tools.json` 受 SHA256 锚点保护，改后 digest 不匹配 → RenderError） | 全仓还原连字符形态 schema URI（目录路径斜杠形态不受影响）；registry 文件恢复 main 原版（digest 99c00e1d…） |
| 路径深度未同步 | 旧 `design-lab/reconstruction/`（3 层）→ 新 `packages/capabilities/reconstruction/`（4 层），`parents[2]`→`parents[3]`；`providers/` 子目录再深一层需 `parents[4]` | registry.py `parents[3]`→`parents[4]`；顶层文件确认 `parents[3]` 正确 |
| 未定义引用 | 多脚本引用 `PROJECT_ROOT` 但迁移时定义行丢失（reconstruct_design.py、benchmark_reconstruction.py、qualify_reconstruction_runtime.py） | 补 `PROJECT_ROOT = parents[2]`（=仓库根） |
| sys.path.insert 插错位置 | test_reconstruction_intake/semantics 头部被插入裸代码行破坏语法 | 移除错误插入 |

### 2. 迁移遗漏（文件删除未同步依赖方）
| 遗漏 | 表现 | 修复 |
|---|---|---|
| 测试引用已删第三方工具 | `test_anydesign_network_boundaries.py` 依赖 LOCK_REFERENCE 删除的 anydesign 脚本 | 删除该测试 |
| adobe 适配器文件整体丢失 | `adapter.manifest.json`、`reconstruction-assemble.jsx`、`photoshop-reconstruction/`、`rights-and-provider-policy.md`、`evidence/`（DL-DIR-060 删 design-lab/adapters/ 时未迁） | 从 main 恢复至 `integrations/hosts/adobe/`；illustrator/photoshop 验证器路径同步 |
| comfyui 适配器文件丢失 | `adapter.manifest.json`、`rights-and-provider-policy.md` | 从 main 恢复至 `integrations/generators/comfyui/`；verify_comfyui_gate 路径更新 |
| 验证器路径残留 | verify_design_lab.py 的 host-verifier 解析仍用 `adapters/` 前缀；jury-anti-slop 指向旧 `design-lab/quality/`；comfyui gate 旧路径 | 全部对齐新结构 |
| 能力索引扫描旧目录 | generate_capability_indexes.py 扫已删 intelligence/knowledge/adapters | CAPABILITY_DIRS 改为 design-lab/{domain-packs,production} + packages/capabilities/{atoms,scenarios,bundles,plugins,quality}（314 条） |

### 3. 测试文件路径引用未同步（占失败大头）
- `test_verifier_internals.py`：load_rel 加 quality/ → packages/capabilities 分支；integrations/、registry、comfyui rights 全部改经 `ROOT.parent`
- `test_op_personal_design_system.py`：ROOT 常量 → REPO_ROOT 前缀 + kind→目录映射
- `test_oda4_0302_manifest_compat.py`：plugins/bundles glob → packages/capabilities
- `test_reconstruction_illustrator/photoshop_adapter.py`：adobe 路径 → integrations/hosts/adobe
- `test_core_gates.py`：license 排除断言 → research/candidates/
- `install_op_expert_suite.py`（installer 本体）：`parents[5]`→`parents[4]`；常量全改新结构；asset 闭包复制改为 manifest-relative 镜像 + legacy fallback
- `verify_minigame_domain_pack.py`：minigame-runtime → fixtures/domains/game-visual

### 4. 治理/验证器路径（DL-DIR-110 前期已修，汇总）
verify_license_coverage（排除前缀 → research/candidates/）、verify_project_drift、verify_adapter_registry/matrix（→ integrations/adapter-registry.json，自 d44d3d8 恢复 30 adapters）、verify_product_manifest_v3（root_relative_prefixes 扩容）、verify_runtime_contracts_v3（repo_root 不再 .parent）、verify_visual_quality_v21（research → design-lab/research + f-string 修复）、verify_knowledge_lifecycle（重写）等。

## 二、当前验证状态

- **本地 verify_design_lab.py：total=49 failed=0（PASS 全绿）**，含 verify_reconstruction_bundle（此前为环境 FAIL）
- **本地全量单测：507 tests，2 failures + 1 error**（此前 13 failures + 46 errors）
  - 已确认修复：metrics/providers/performance/qualification/illustrator/photoshop/adobe_job/verifier_internals/op_personal_design_system/oda4_0302/core_gates 等全部 OK
  - 本地超时项：test_reconstruction_evidence（本地 skimage 首次编译慢，CI Linux 无此问题）
- 5 gate：Open Design host adapter gate / License / MiniGame / Generated-artifact 稳定 PASS；Python gate 为唯一失守项，已随本轮修复推送等待 CI
- 预存环境 FAIL（非迁移引起）：ComfyUI 未运行、resvg/vtracer 缺失、Illustrator 未安装 → CI 侧不必然复现

## 三、后续动作（已执行完结）

1. ✅ **2026-09-03 PR #112 已 squash 合并**（c9cde8a），5 gate（含 Python gate）全绿；分支已删
2. ✅ main 已同步本机（本地 = origin/main，双端一致）
3. 规范化（对照 -3 权威任务包）核对结果：
   - ✅ 硬门目录全删：intelligence/knowledge/project-memory/minigame-runtime/design-system/adapters
   - ✅ .project 治理（manifest/gates/path-risk/data-ownership/allowlist）+ .project-local 结构齐全
   - ✅ canonical 门（verify_design_lab 49/49、identity、adapter matrix、compileall、diff-check）全绿
   - ✅ -3 任务包入库、-2 标 SUPERSEDED（修正 design-system/docs/fixtures 删除范围笔误）
   - ⚠ 待后续（DL-DIR-030 资格化裁决）：research/candidates 8 仓 1931 文件（33.6MB）为
     CONDITIONAL_POC 保真收录区（均带 SOURCE.md/LICENSE）——逐个裁决后按 ABSORB/LOCK/REJECT
     分流，源码移至 ignored vendor cache；vendor/sources.lock.json 目前仅 6 项 LOCK_REFERENCE

## 四、规范化终版（9e8cb1b，2026-09-04）——第三条款关闭

对照 -3 权威任务包 §10 完成定义，**第 3 条（第三方完整副本退出 Git）本次执行完毕**：

1. **37 个第三方候选根（1913 文件，39MB）退出 Git** → 保真移至 ignored
   `.project-local/cache/vendor/<id>`；`research/candidates/` 转为纯索引区（README 登记
   每仓 URL/许可/裁决/cache 键）；`vendor/sources.lock.json` 6 → 43 项（37 CONDITIONAL_POC）
2. **18 个 DESIGN 自有视觉质量方法论文档**（AI_SLOP_FAILURE_MODES 等，原混在 candidates 根下）
   经核实为自有协议族 → 移入 `design-lab/research/visual-quality/`（自有知识区）
3. **过期治理引用修复**（指向已删路径）：
   - `.project/governance/path-risk.yaml`：删 intelligence/knowledge 规则，补 candidates/vendor 语义
   - `.project/governance/active-capability-allowlist.yaml`：adobe → `integrations/hosts/adobe`
   - `design-lab/config/capability-index.json`：adobe owner/source 路径修正
   - `design-lab/README.md`、`core/README.md`：adapters 章节迁出说明
   - `product-manifest.json`：visual-quality family paths → `design-lab/research/visual-quality/`
   - `design-assets-example-001.json`：outputTargets → `research/master-studies/`
4. **生成器迁移残留 bug 修复**：`generate_open_design_adapter_indexes.py` 仍扫已删
   `design-lab/plugins`/`bundles`/expert-suite 旧路径（asset-counts.json 旧数据长期掩盖）；
   修复为 packages/capabilities + integrations/hosts 新结构、受管 design-system 计数=3，
   重新生成 CAPABILITY_INDEX.md / asset-counts.json / plugins INDEX.md
5. **验证结果**：verify_design_lab 49/49 + 549 项全绿；tracked 文件 3280 → 1371；
   pack 207.5MiB（预算 256）；单测 66 核心断言 + test_op_personal_design_system 33 全过
6. 文档：`docs/THIRD_PARTY_ISOLATION.md` 重写为仓库外隔离模型

### 5.1 遗留（未裁决，待 DL-DIR-030）
- 37 仓仍在 CONDITIONAL_POC：需真实用例验证后 ABSORB_MINIMAL / LOCK_REFERENCE / REJECT
- 源码在 `.project-local/cache/vendor/`（本机保真 39MB）；fresh clone 不含第三方源码

## 五、追加修复（add26a5，CI 干净环境暴露的最后 2 个失败）
| 失败 | 根因 | 修复 |
|---|---|---|
| evidence closure 测试（CI） | evidence.py `_discover_execution_source_paths` 仍扫已空的 `design-lab/reconstruction/`（本体漏改，本地因旧缓存掩盖） | rglob 根 → `packages/capabilities/reconstruction`；测试 fixture 布局 + expected_modules 同步 |
| intake 跨进程测试（CI） | 子进程 sys.path 仅含 design-lab/，reconstruction 包已迁 packages/capabilities | 头部 + 子进程参数均补 `packages/capabilities` |

## 六、恢复源 commit 备忘
- d44d3d8：治理基线（adapter-registry.json、E3_FIXTURE_PROTOCOL.md）
- fabd4bc^：minigame-mobile-controls exports
- origin/main：adobe/comfyui 适配器文件
