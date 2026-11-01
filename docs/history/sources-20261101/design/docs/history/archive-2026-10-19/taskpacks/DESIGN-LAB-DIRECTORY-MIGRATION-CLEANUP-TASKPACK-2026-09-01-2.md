> SUPERSEDED by DL-TP-20260904-STANDALONE-FIRST (2026-09-04). Historical record, not current.

# DESIGN-LAB 项目内目录迁移、第三方隔离与彻底清理任务包

> STATUS: SUPERSEDED by `DESIGN-LAB-DIRECTORY-MIGRATION-CLEANUP-TASKPACK-2026-09-01-3.md`
> (authoritative revision; corrects design-system/docs/fixtures deletion-scope errors).
> Retained for audit history only — do not execute against this revision.

```yaml
id: DL-DIR-MIG-R1
name: DESIGN-LAB product-vendor boundary convergence and repository cleanup
version: 1.0.0
date: 2026-09-01
project: DESIGN-LAB
baseline_sha: 33488c882d267d683250ae684caf28d0916d9099
executor: any-qualified-executor
execution_role: bounded-writer
priority: P0
mode: sequential-single-writer
mutation_policy: task-path-allowlist
commit_policy: atomic-local-commits
push_policy: explicit-user-approval
merge_policy: exact-sha-ci-and-human-approval
network_policy: default-deny-except-locked-upstream-hosts-and-github
runtime_policy: repository-root-zero-spill
```

## 1. 交付目标

将DESIGN-LAB从“产品能力＋设计知识＋整仓第三方源码＋工具指令＋MiniGame runtime＋project-memory混合树”收敛为清晰的专业设计生产系统：

1. 保留DESIGN-LAB独有的Design IR、Domain Pack、设计质量、人工审核、Creative Tool Adapter和交付；
2. 将Open Design、Adobe、Figma、Blender、OpenPencil等固定为Host/Canvas Adapter；
3. 将Hermes/Codex/WORK固定为可替换Executor/Control Adapter；
4. 停止把完整第三方仓库复制进活跃产品树；
5. 只吸收通过资格化的最小能力，其余改成URL＋精确SHA＋许可证＋补丁清单；
6. 将第三方下载/源码缓存放进本项目 `.project-local/cache/vendor`，不外溢；
7. 把`project-memory`重分类为架构、决策、当前状态和历史；
8. 将`minigame-runtime`迁成游戏视觉fixture；
9. 完整测试和商业Jury通过后，删除旧目录、第三方完整副本、工具指令污染、空目录和重复内容。

## 2. 产品边界与强制保留

DESIGN-LAB拥有：

- Brief、Design IR、设计方向和中间状态；
- 职业Domain Pack和设计知识候选；
- 视觉质量、人工Jury、production preflight；
- 资产来源、许可证、交付包和证据；
- Open Design/Adobe/Figma/Blender等宿主适配。

DESIGN-LAB不拥有：

- 第二个Photoshop/Figma/Blender完整编辑器；
- 通用Agent Runtime、模型网关、账号系统；
- WORK-LAB的全局配置/权限/Observer；
- ArcheAxis长期知识和学习状态；
- 第三方上游项目的完整历史与工具身份。

强制人工审核节点不能因production模式、目录迁移或上游Host而绕过。

## 3. 当前基线与风险

当前主要规模：

| 路径 | tracked文件 | 约体积/特征 | 处置 |
|---|---:|---|---|
| `design-lab/` | 3039 | 产品、能力、知识、第三方源码混合 | 拆分 |
| `design-lab/knowledge` | 1474 | 约22.3MB，含大量完整技能仓 | 资格化/外置/删除旧树 |
| `design-lab/intelligence` | 740 | 约15.6MB，含完整上游和工具指令 | 资格化/外置/删除旧树 |
| `minigame-runtime` | 214 | 名称与fixture边界冲突 | 迁至fixtures后删除 |
| `project-memory` | 38 | 实为产品定义/决策/路线图/历史 | 迁至docs后删除 |

已确认约232个tracked `AGENTS.md`、`CLAUDE.md`、`SKILL.md`、`.agents`、`.claude`类发现文件。文档声明`INERT_BLOB`不足以阻止IDE/Agent递归加载，必须物理退出活跃发现面。

## 4. 最终目录树

```text
DESIGN-LAB/
├─ .project/
│  ├─ manifest.yaml
│  └─ governance/
│     ├─ gates.yaml
│     ├─ path-risk.yaml
│     ├─ data-ownership.yaml
│     └─ active-capability-allowlist.yaml
├─ .github/
├─ .project-local/                    # ignored
│  ├─ worktrees/
│  ├─ runs/
│  ├─ cache/
│  │  └─ vendor/
│  ├─ toolchains/
│  ├─ build/
│  ├─ artifacts/
│  └─ locks/
├─ apps/
│  └─ workbench/
├─ services/
│  ├─ jobs/
│  ├─ review/
│  ├─ quality/
│  └─ delivery/
├─ packages/
│  ├─ contracts/
│  ├─ capabilities/                   # 仅已资格化、已吸收的最小能力
│  ├─ packages/design-system/
│  ├─ asset-model/
│  └─ ui/
├─ integrations/
│  ├─ hosts/
│  │  ├─ open-design/
│  │  ├─ adobe/
│  │  ├─ figma/
│  │  ├─ blender/
│  │  └─ inkscape/
│  ├─ canvases/openpencil/
│  ├─ generators/comfyui/
│  └─ executors/
│     ├─ hermes/
│     ├─ codex/
│     └─ work-lab/
├─ vendor/
│  ├─ sources.lock.json               # URL/SHA/license/use/patch/exit
│  ├─ licenses/
│  └─ patches/
├─ research/
│  └─ candidates/
├─ assets/
│  ├─ canonical/
│  └─ licensed-fixtures/
├─ fixtures/
│  └─ domains/game-visual/
├─ config/
├─ scripts/
├─ tests/
├─ docs/
│  ├─ architecture/
│  ├─ decisions/
│  ├─ current/
│  ├─ taskpacks/
│  └─ history/
├─ reports/
│  └─ release/
└─ LICENSES/
```

最终不得存在：根 `design-lab/`混合容器、`design-lab/intelligence/`、`design-lab/knowledge/`、`docs/`、`fixtures/domains/game-visual/`、工具可递归发现的第三方 `.agents/.claude/AGENTS/CLAUDE/SKILL`完整树、被跟踪真实导出物和旧 `.hermes`新写入。

## 5. 迁移裁决模型

每个第三方项目只能得到以下一种状态：

| 状态 | 含义 | Git中保留内容 |
|---|---|---|
| `ABSORB_MINIMAL` | 已通过真实用例，提取最小实现 | `packages/capabilities/<id>`＋许可＋来源＋测试 |
| `ADAPTER_ONLY` | 由官方API/CLI/插件接入 | `integrations/<type>/<id>` |
| `LOCK_REFERENCE` | 只作方法/设计参考 | `vendor/sources.lock.json`记录，不保存完整源码 |
| `CONDITIONAL_POC` | 尚未资格化 | `research/candidates/<id>.md`，源码在ignored vendor cache |
| `REJECT_REMOVE` | 越界、许可/安全/维护不合格 | 删除源码，仅在decision ledger记录 |

禁止`COPY_WHOLE_REPO_INTO_ACTIVE_TREE`。

## 6. 路径迁移矩阵

| 旧路径 | 新路径 | 方法 | 旧路径最终状态 |
|---|---|---|---|
| `packages/capabilities/atoms`、自有skills/bundles/plugins/scenarios | `packages/capabilities` | 去重、统一能力manifest和测试 | 删除旧容器 |
| `design-lab/adapters/hosts` | `integrations/hosts` | 保持Host合同 | 删除旧路径 |
| `integrations/executors` | `integrations/executors` | 仅薄适配 | 删除旧路径 |
| `packages/capabilities/reconstruction` | `packages/capabilities/reconstruction` | 保持schema、security、golden corpus | 删除旧路径 |
| `packages/capabilities/quality` | `services/quality` + `services/review` | 人工Jury和自动检查拆分 | 删除旧路径 |
| `design-lab/exports` | `.project-local/artifacts/exports`或Release | 小型黄金fixture另存fixtures | 删除tracked生成物目录 |
| `design-lab/intelligence/*` | capabilities/adapters/vendor lock/research | 逐项目资格化 | 删除整个intelligence |
| `design-lab/knowledge/*` | capabilities/vendor lock/research | 逐项目资格化 | 删除整个knowledge |
| `packages/design-system/` | `packages/packages/design-system/` | 保持DTCG/主题/组件合同 | 删除根旧目录 |
| `docs/*` | `docs/{architecture,decisions,current,history}` | 按语义拆分 | 删除 |
| `fixtures/domains/game-visual/` | `fixtures/domains/game-visual/` | 保持测试fixture身份 | 删除 |
| `.hermes/*` | `.project-local/*` | 复制/哈希/宿主读回 | 清理旧本地目录 |

## 7. 执行任务 DAG

### DL-DIR-000：创建项目内隔离执行面

1. 分支：`migration/dl-directory-convergence-r1`。
2. worktree：`.project-local/worktrees/DL-DIR-MIG-R1/`。
3. run root：`.project-local/runs/DL-DIR-MIG-R1/<attempt-id>/`。
4. TEMP/TMP、pip/npm/bun、Playwright、模型、Adobe/Open Design任务profile全部重定向到项目内。
5. 未知第三方程序使用Windows Sandbox或等价严格隔离，只映射本项目根，默认断网。

### DL-DIR-010：冻结全量资产与来源清单

为每个tracked文件记录：Git blob SHA、大小、Owner、来源仓URL、精确SHA、许可证、活动引用、工具发现风险、目标裁决。

必须输出：

- 232个指令发现文件的active/inert/reject清单；
- intelligence/knowledge每个上游身份与许可；
- 完整副本与已吸收能力之间的代码/功能重复；
- exports、截图、二进制、模型和大文件清单；
- source registry、SBOM、LICENSES差异。

使用成熟工具：Git、`rg`、gitleaks、Syft/SPDX、git-sizer；不自研第二套SBOM或secret scanner。

### DL-DIR-020：建立 `.project`、allowlist和零外溢根

1. 新建项目manifest、数据Owner、Gate、path-risk。
2. 新建`active-capability-allowlist.yaml`，只有DESIGN自有且已资格化能力可进入工具发现。
3. `.gitignore`递归忽略 `.project-local`、真实宿主profile、导出、缓存、模型、构建和临时DB。
4. no-spill门覆盖盘符、UNC、junction、Adobe临时目录、浏览器profile、ComfyUI output和模型下载。
5. 当前 `.hermes`只读迁移，新写入只用 `.project-local`。

### DL-DIR-030：第三方项目逐项资格化

每个上游必须完成48小时内可重复的真实用例：

1. 从官方URL按精确SHA拉取到 `.project-local/cache/vendor/<id>/<sha>`；
2. 校验archive SHA、许可证和依赖；
3. 在严格sandbox运行其官方测试/最小用例；
4. 用DESIGN真实场景验证输入→输出→写后读回→重启；
5. 记录性能、稳定性、格式损失、Windows兼容、8GB显存影响；
6. 裁决为五种状态之一；
7. 未通过不得进入capability index或宣传为能力。

优先裁决既有高价值项：Open Design、OpenPencil、Penpot方法、baoyu-design、anydesign、UI/UX技能、视觉质量工具、Adobe/Figma桥、Blender/ComfyUI适配。不得因仓库已复制就默认保留。

### DL-DIR-040：吸收最小能力并删除完整副本

对`ABSORB_MINIMAL`：

1. 只提取被调用的模块、合同、fixture和测试；
2. 保留上游版权头和许可证；
3. 使用稳定namespace，不保留Claude/Codex/Hermes身份；
4. 新增与上游行为对照的contract/golden测试；
5. 将本地修改保存为`vendor/patches`或在吸收代码中记录provenance；
6. 删除原完整上游目录；
7. 重新生成SBOM和source registry。

对`ADAPTER_ONLY/LOCK_REFERENCE/CONDITIONAL_POC/REJECT_REMOVE`：仓库中不保留完整源码。PoC源码仅存在ignored vendor cache；最终Release不依赖未锁定在线主分支。

### DL-DIR-050：重构产品能力树

1. 将自有atoms/skills/bundles/plugins/scenarios去重为`packages/capabilities`。
2. 每项能力必须有唯一ID、Owner、输入/输出schema、成熟度E0-E5、测试和回滚。
3. reconstruction迁至资格化能力包，保留security/golden/Adobe readback。
4. 自动质量检查迁`services/quality`；人工Jury/approval迁`services/review`。
5. jobs只管理设计作业状态，不复制Dagu/Hermes通用工作流引擎。
6. delivery管理preflight、来源、许可、可编辑源文件和交付包。

### DL-DIR-060：迁移宿主和执行器适配

- Open Design → `integrations/hosts/open-design`，作为主要宿主；
- Adobe → `integrations/hosts/adobe`，Photoshop先行，其他软件逐项资格化；
- Figma/Blender/Inkscape →各自Host Adapter；
- OpenPencil → Canvas Adapter；
- ComfyUI → Generator Adapter；
- Hermes/Codex/WORK → `integrations/executors`，不得包含全局配置/凭据/运行时。

所有适配器必须：能力探测、版本范围、权限、超时、失败、写后读回、撤销、证据和fail-closed。

### DL-DIR-070：迁移设计系统、project-memory和MiniGame

1. `git mv design-system packages/design-system`，更新DTCG、prompt生成和CI。
2. 将`project-memory`按语义分入docs；PRODUCT_DEFINITION/BOUNDARY/ROADMAP进入current或architecture，旧交接进入history。
3. 当前权威文档只保留一个，其他标SUPERSEDED并去重。
4. `git mv minigame-runtime fixtures/domains/game-visual`。
5. 更新Node脚本、Android/WebView drift、测试和路径规则。
6. 禁止MiniGame恢复成独立Runtime产品线。
7. 完成后删除根`design-system`、`project-memory`、`minigame-runtime`。

### DL-DIR-080：处理导出、素材和二进制

1. 真正交付物进入Release或用户指定交付位置；项目过程导出进 `.project-local/artifacts/exports`。
2. 只保留最小、有许可、确定性的黄金fixture。
3. 每个tracked二进制有来源、许可、SHA和用途；无记录则阻断迁移。
4. 重复截图/导出按hash去重。
5. 不自动删除客户原件；外部原件只读导入本次`input`，后续处理副本。

### DL-DIR-090：全引用和工具发现迁移

更新：Python import、manifest、capability index、source registry、SBOM、CI、文档、prompt生成器、Open Design/Adobe路径、MiniGame测试路径。

工具发现门：

- active allowlist外的 `AGENTS.md/CLAUDE.md/SKILL.md/.agents/.claude/.claude-plugin/.cursorrules`为0；
- vendor lock记录可以提到这些文件，但仓库中不存其完整可发现树；
- 客户端prompt由中性能力spec生成，不维护Codex/Hermes/Claude三份人工副本。

### DL-DIR-100：本地运行数据迁移

1. dry-run列出 `.hermes`中的Open Design、Adobe、重建、截图、模型和证据；
2. 复制到 `.project-local`并逐文件哈希；
3. 对PSD/AI/SVG/FIG/Blender/JSON执行宿主或解析器读回；
4. 重启Open Design/适配器验证任务状态；
5. 旧目录移入项目内quarantine；
6. 完成一个Brief→生产→人工审核→可编辑交付闭环后，按manifest删除旧目录内容；
7. 不处理宿主软件全局用户库和其他项目。

### DL-DIR-110：测试矩阵

Canonical门：

```text
python design-lab/scripts/verify_design_lab.py
python design-lab/scripts/verify_identity_gate.py
python design-lab/scripts/verify_adapter_matrix.py
python design-lab/scripts/update_evidence_binding.py --check
python design-lab/scripts/verify_product_manifest_v3.py
python design-lab/scripts/verify_runtime_contracts_v3.py
python design-lab/scripts/verify_visual_scoring_v3.py
python design-lab/scripts/verify_license_coverage.py
python scripts/run_python_tests.py
python -m compileall -q packages services integrations scripts
```

路径迁移完成后，上述命令必须同步到新位置；任务包中的旧命令只是基线入口，不允许为通过测试而留下旧目录副本。

MiniGame fixture门：

```text
node fixtures/domains/game-visual/scripts/run-tests.cjs
node fixtures/domains/game-visual/scripts/check-android-drift.mjs
git diff --exit-code -- fixtures/domains/game-visual
```

供应链和仓库卫生：

```text
gitleaks detect --source .
syft dir:. -o spdx-json
git diff --check
git status --short
```

真实商业Jury必须至少验证：

1. Brief→方向→Open Design/宿主生产；
2. AI图→矢量/分层转换，记录精度和不适用场景；
3. Photoshop/Illustrator真实写入与读回；
4. 多版本视觉比较和人工批注；
5. production模式无法绕过人工审批；
6. 输出PSD/SVG/PDF/PNG及交付manifest；
7. 来源、许可证、模型、操作和证据完整；
8. 运行前后项目外任务指纹为0。

### DL-DIR-120：旧目录彻底清理

只有DL-DIR-110全绿后允许：

1. 按迁移manifest精确`git rm`旧tracked树；
2. 删除完整第三方源码副本、第三方工具指令、空目录、`.gitkeep`、重复prompt、重复导出和兼容副本；
3. 删除根`design-lab`混合容器、`design-system`、`project-memory`、`minigame-runtime`；
4. `.hermes`本地内容按DL-DIR-100清理，不使用无清单通配删除；
5. 禁止使用`git clean -fdx`或对未知WIP执行递归删除；所有删除目标必须来自已验证manifest；
6. 重新生成source registry、SBOM、capability index和license coverage；
7. 完整复测、fresh clone、Windows宿主读回、exact-SHA CI；
8. 最终commit后`git status --short`为空。

## 8. 清理硬门

禁止合并，如果：

- `design-lab/intelligence`或`design-lab/knowledge`仍存在；
- 任一完整第三方项目仍位于活跃产品树；
- 发现文件仍可被工具递归加载但不在allowlist；
- `project-memory`或`minigame-runtime`仍存在；
- 旧`design-system`根仍存在；
- capability index包含未资格化项目；
- SBOM、source registry、license coverage不一致；
- production可以绕过人审；
- tracked exports/模型/临时文件无来源；
- fresh clone不clean、测试不全绿或检测到项目外写入。

## 9. 回滚

- 每阶段一个本地原子commit，失败回滚该阶段，不硬重置；
- 第三方原始版本由URL+SHA+archive hash可重建，不靠保留整仓副本；
- tracked资产从前一commit恢复；
- ignored运行数据从项目内quarantine恢复；
- 用户客户素材不参与自动删除；
- 发现许可或secret问题立即停线，不在普通迁移中掩盖。

## 10. 完成定义

只有全部满足才能标记`E5 RELEASED`：

1. 新apps/services/packages/integrations/vendor/fixtures结构成为唯一活动面；
2. intelligence、knowledge、project-memory、minigame-runtime、旧design-system和混合design-lab根物理删除；
3. 第三方完整副本退出Git，只保留锁定来源/许可/补丁或最小吸收代码；
4. active工具发现面只包含批准的DESIGN能力；
5. canonical tests、供应链、SBOM、license、fresh clone全绿；
6. Open Design/Adobe真实商业Jury通过且人工审批不可绕过；
7. no-spill为0；
8. Release证据绑定最终SHA；
9. 用户批准push、merge和release。
