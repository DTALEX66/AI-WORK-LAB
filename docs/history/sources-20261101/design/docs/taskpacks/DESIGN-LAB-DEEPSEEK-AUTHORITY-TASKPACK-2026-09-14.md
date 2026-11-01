# DESIGN-LAB｜DeepSeek Authority Master TaskPack

## Repository Convergence · Cleanup · Spill Recovery · Language Governance · Structural Closeout

**TaskPack ID:** `DL-TP-20260914-DEEPSEEK-AUTHORITY-R1`
**目标仓库:** `DTALEX66/DESIGN-LAB`
**执行者:** DeepSeek / DSH
**真实宿主执行者:** Codex
**项目:** DESIGN-LAB ONLY
**状态:** `READY_AFTER_AUTHORITY_ACTIVATION`
**用途:** PERSONAL_RESEARCH_NONCOMMERCIAL
**默认策略:** REUSE-FIRST / STANDALONE-FIRST / HOST-NATIVE / FAIL-CLOSED

---

# 0. 本任务包的唯一目的

本包负责把 DESIGN-LAB 当前已经形成的大量结构能力真正收敛为：

```text
干净仓库
+
唯一治理入口
+
唯一目录规范
+
唯一语言规范
+
唯一运行数据边界
+
可验证的状态/契约
+
可维护的第三方依赖
+
可交给 Codex 做真实宿主验证的稳定底座
```

本包**不负责**：

* 操控 Photoshop
* 操控 Illustrator
* 操控 Premiere
* 操控 Blender
* 操控 OpenDesign
* 操控 MiniMax Design
* 启动 ComfyUI 做真实生成
* GPU 模型推理
* 真实视觉设计质量判断
* Human Jury 最终签字
* E3/E4 真实专业设计能力验收

这些全部留给 Codex。

---

# 1. Authority Activation Gate

## DLDS-A000｜任务包落仓

在任何代码修改以前，必须先完成：

```text
docs/taskpacks/
DESIGN-LAB-DEEPSEEK-AUTHORITY-TASKPACK-2026-09-14.md
```

文件内容必须与本 TaskPack 原文一致。

计算：

```text
SHA-256
```

记录：

```text
taskpack_id
taskpack_version
taskpack_sha256
created_at
authoritative=true
```

同时创建机器账本：

```text
reports/current/
DEEPSEEK-AUTHORITY-LEDGER-2026-09-14.json
```

在此之前：

`MUTATION_FORBIDDEN`

---

# 2. Authority Chain

## DLDS-A010｜权威关系收敛

必须读取并对账：

```text
AGENTS.md
.project/manifest.yaml
当前 R5 TaskPack
当前 task-ledger-r3.json
SESSION-RESTART-2026-09-12.md
04-REPOSITORY-LANGUAGE.md
09-04 TaskPack
09-05 Multimodal Plan
所有 current reports
```

本 TaskPack 激活以后：

```text
Current DeepSeek execution authority
=
DL-TP-20260914-DEEPSEEK-AUTHORITY-R1
```

旧任务包：

不得删除。

分类：

```text
SUPERSEDED
HISTORICAL
REFERENCE
CODEX_DEFERRED
```

不得同时存在第二个 DeepSeek current taskpack。

---

# 3. Task ID 新规则

禁止使用裸：

```text
DL-P0-001
DL-R5-001
```

作为唯一任务标识。

所有本包任务完整 ID：

```text
DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::<task_key>
```

例如：

```text
DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-C010
```

Machine ledger 必须同时存：

```text
taskpack_id
taskpack_sha256
task_key
run_id
executor
base_sha
branch
worktree
status
```

---

# 4. 禁止摘要授权执行

永久规则：

```text
CHAT SUMMARY
MEMORY SUMMARY
COMPRESSED CONTEXT
HANDOFF SUMMARY
```

均：

`NON_AUTHORITATIVE`

只有真实文件：

```text
AGENTS
TaskPack
Ledger
Manifest
Versioned Schema
```

可以授权 mutation。

如果真实 TaskPack 无法读取：

```text
TASK_AUTHORITY_UNRESOLVED
```

立即停止。

---

# 5. 停止线处理

## DLDS-A020｜Stop-line supersession

`SESSION-RESTART-2026-09-12.md` 保留。

本 TaskPack 只对本文列出的 DeepSeek 任务进行：

`EXPLICIT_SCOPE_SUPERSESSION`

其他开发仍被冻结。

特别是：

```text
Real Host
Design validation
GPU inference
Human Gate
```

停止线继续有效。

---

# 6. 当前脏工作树必须先处理

## DLDS-A030｜Dirty Worktree Freeze

当前 DSH 已产生的：

* 既有文件修改
* 新文件
* 数据库 migration
* contracts
* validators
* reports

全部先冻结。

不得继续叠新 Feature。

输出：

```text
reports/current/
DEEPSEEK-WORKTREE-INVENTORY.json

reports/current/
DEEPSEEK-WORKTREE-DIFF-SUMMARY.md
```

逐文件分类：

```text
KEEP
KEEP_WITH_FIX
DUPLICATE
OUT_OF_PACK
UNPROVEN
REVERT
```

---

# 7. Reconciliation

## DLDS-A040｜现有 DSH 成果重新归属

每一个当前新增/修改文件必须回答：

```text
属于哪个真实 Task？
为什么存在？
producer 是谁？
consumer 是谁？
有没有重复实现？
有没有 Schema？
有没有测试？
有没有 rollback？
```

不能回答：

`UNATTRIBUTED`

不得进入正式树。

---

# 8. 分支纪律

DeepSeek 后续只能工作在独立 reconciliation / execution branch。

允许：

* local branch
* local commit
* checkpoint commit

禁止：

* push main
* merge main
* release
* tag
* remote destructive mutation

除非 Owner 另行明确授权。

---

# 9. Wave 1 — Repository Normalization

## DLDS-B000｜全仓目录语义审计

审核当前所有一级/二级目录。

目标规范：

```text
DESIGN-LAB/
├─ apps/
├─ services/
├─ packages/
├─ integrations/
├─ src/design_lab/
├─ fixtures/
├─ evals/
├─ research/
├─ vendor/
├─ docs/
├─ reports/
├─ scripts/
├─ .project/
└─ .project-local/
```

不得为了“看起来整齐”强制创建空目录。

以实际职责决定。

---

# 10. 目录责任冻结

## DLDS-B010｜Directory Authority

定义：

### `src/design_lab/`

DESIGN-LAB 自有运行逻辑：

```text
runtime
analysis
state
orchestration
domain logic
```

### `services/`

可独立组合的产品服务：

```text
jobs
review
quality
delivery
```

### `packages/`

可复用设计域能力：

```text
capabilities
design-system
contracts/shared types
```

### `integrations/`

第三方边界：

```text
hosts
generators
executors
mcp
canvases
```

### `.project/`

治理真值。

### `.project-local/`

所有忽略的运行数据。

禁止一项能力同时存在两个默认实现。

---

# 11. 旧路径清退

## DLDS-B020｜Legacy Path Elimination

扫描：

* 旧 `design-lab/adapters`
* 旧 `project-memory`
* 旧 `knowledge`
* 旧 `intelligence`
* 旧 `exports`
* 旧 `.hermes` runtime references
* 旧路径 alias
* 旧 scripts import

分类：

```text
MIGRATED
HISTORICAL_ONLY
DELETE
BLOCKED
```

所有 active path 引用必须归零。

---

# 12. Current / History 分离

## DLDS-B030｜Documentation Authority

文档只能属于：

```text
docs/current
docs/architecture
docs/decisions
docs/taskpacks
docs/history
```

`reports/current`：

只允许当前状态投影。

历史报告：

```text
reports/history
```

禁止旧文档继续冒充 current。

---

# 13. Registry SSOT

## DLDS-B040

统一审计：

```text
product-manifest
adapter-registry
capability registry/index
rights registry
model registry
source lock
evidence index
```

一个事实只能有一个 authoring source。

其他全部生成投影。

---

# 14. PROJECT_STATUS 重构

## DLDS-B050

当前状态报告必须记录：

```text
subject_type
subject_sha
worktree_digest
worktree_clean
taskpack_id
taskpack_hash
test_run_id
generated_at
environment_fingerprint
```

dirty tree 时：

```text
subject_type=WORKTREE
```

不得冒充 commit 状态。

---

# 15. Wave 2 — Language Governance

## DLDS-C000｜语言全仓盘点

生成：

```text
reports/current/LANGUAGE-INVENTORY.json
```

包括：

```text
language
file_count
LOC
owner directories
runtime role
build system
dependency manager
```

---

# 16. DESIGN-LAB 正式语言政策

## DLDS-C010

冻结为：

### Python

权威职责：

```text
orchestration
runtime/state
QA
provider logic
reconstruction
analysis
CLI/tooling
```

### TypeScript

权威职责：

```text
Workbench UI
OpenDesign/Web integration
MCP client
IPC/web frontend
```

### Host-native JavaScript

仅用于：

```text
Adobe UXP / host-native extension
```

### JSON / JSON Schema 2020-12

跨语言权威契约。

### Rust

默认：

`NOT_PRIMARY`

只有满足：

```text
benchmark evidence
+
ADR
+
明确瓶颈
```

才允许用于：

* geometry
* image diff
* media scanning
* native watcher
* performance-critical helper

---

# 17. 禁止语言扩散

## DLDS-C020

未经 ADR 禁止新增：

* C#
* Go
* Java
* Kotlin
* C++
* 第二套 Python runtime architecture
* 第二套 Node backend

“某库使用该语言”不构成引入主语言理由。

---

# 18. Python 规范化

## DLDS-C030

统一：

```text
pyproject.toml
uv.lock
src layout
pytest
ruff
```

清除：

* scattered requirements
* unmanaged venv
* import path hacks
* duplicate dependency declarations

不得删除合法 host-specific scripts。

---

# 19. TypeScript/Node 规范化

## DLDS-C040

确定唯一：

```text
package manager
lock file
Node compatibility range
workspace boundary
```

避免：

```text
npm + pnpm + yarn
```

并存成为三个真值。

---

# 20. Cross-language Contract Gate

## DLDS-C050

Python / TS / Host extension 之间不得复制手写 enum。

权威来自：

```text
JSON Schema / versioned contract
```

生成或验证：

```text
status
asset types
operation types
rights states
evidence levels
```

---

# 21. Wave 3 — Repository Slimming

## DLDS-D000｜全量体积审计

输出：

```text
REPOSITORY-SIZE.json
LARGEST-FILES.json
SIZE-BY-DIRECTORY.json
SIZE-BY-EXTENSION.json
TRACKED-BINARY.json
UNTRACKED-RUNTIME.json
```

区分：

```text
Git tracked
Git ignored
external runtime
third-party cache
model cache
generated artifact
```

---

# 22. 第三方整仓清理

## DLDS-D010

任何第三方项目完整源码不得长期存在于产品 Git 中，除非：

```text
ABSORB_MINIMAL
```

并有明确许可证和维护理由。

默认：

```text
canonical URL
commit
hash
license
disposition
```

写入：

```text
vendor/sources.lock.json
```

完整源码：

```text
.project-local/cache/vendor/
```

或外部缓存。

---

# 23. 模型资产清理

## DLDS-D020

禁止 Git 保存：

* checkpoints
* safetensors
* ONNX 大模型
* LoRA
* video models
* Hugging Face cache

仓库只保存：

```text
model_id
source
revision
hash
license
hardware requirements
install recipe
```

---

# 24. Generated / Cache 清理

## DLDS-D030

扫描：

```text
node_modules
.venv
__pycache__
.pytest_cache
mypy cache
build
dist
temp
cache
render temp
screenshots
logs
browser cache
model downloads
```

确认可再生后迁出/删除。

---

# 25. 历史文档瘦身

## DLDS-D040

不得删除有决策价值的历史。

但必须：

* 去重复副本
* 去 `(1)` 重复文件
* 归档 superseded
* 合并重复 current report
* 保留 source hash

---

# 26. Repository Budget Gate

## DLDS-D050

重新测当前 Git pack。

建立：

```text
warning threshold
hard budget
```

不得沿用旧数字而不重新测。

超过 warning：

CI WARN。

超过 hard budget：

阻止新增非必要大文件。

---

# 27. Wave 4 — Spill Data Tracking

## DLDS-E000｜历史外溢数据 Census

扫描范围严格限定 DESIGN-LAB。

允许读取：

```text
DESIGN-LAB repo
DESIGN-LAB .project-local
明确登记的 DESIGN-LAB external cache
```

对 Agent global home：

`.hermes / .codex / .dsh`

只允许：

**metadata/path-level discovery of DESIGN-LAB-owned runtime artifacts**

禁止读取：

* 私人聊天内容
* 凭据
* unrelated sessions
* sibling projects

E:\ 继续禁止。

---

# 28. Spill Classification

每个外溢对象分类：

```text
SESSION_HISTORY
RUNTIME_STATE
CACHE
GENERATED_ARTIFACT
EVIDENCE
TEMP
THIRD_PARTY
UNKNOWN
```

同时记录：

```text
owner
size
hash
source_path
target_path
recreatable
delete_policy
```

---

# 29. Zero Spill Future Gate

## DLDS-E010

建立 file-system boundary test。

任何 DESIGN-LAB task 前后：

```text
before snapshot
after snapshot
diff
```

允许写入：

```text
repo tracked authorized paths
.project-local
explicit external cache paths
```

其他：

`SPILL_DETECTED`

---

# 30. Runtime 数据迁移

## DLDS-E020

DESIGN-LAB 自己拥有的旧 runtime：

迁入：

```text
.project-local/
```

按类型：

```text
runs/
state/
cache/
artifacts/
exports/
logs/
temp/
```

每次迁移：

```text
copy
hash compare
update pointer
readback
restart/reopen test
quarantine old
```

再删除。

---

# 31. `.hermes` 外溢处理

## DLDS-E030

禁止粗暴删除整个 `.hermes`。

只处理**可证明由 DESIGN-LAB 旧流程写出的 runtime/cache/artifact**。

禁止迁移/删除：

```text
Hermes native session history
Hermes personal memory
credentials
other projects
```

DESIGN-LAB 不拥有这些数据。

---

# 32. 删除策略

## DLDS-E040

自动允许删除的仅限：

```text
recreatable cache
temp
duplicate generated outputs
confirmed obsolete DESIGN-LAB runtime copy
```

必须：

* hash
* replacement confirmed
* no active refs
* delete manifest
* rollback/immediate restore path

其他：

`OWNER_DELETE_APPROVAL_REQUIRED`

---

# 33. Post-cleanup Audit

## DLDS-E050

清理后重新运行：

```text
repo size
Git status
path references
tests
zero-spill probe
current report generator
```

输出实际释放：

```text
bytes_before
bytes_after
bytes_reclaimed
```

禁止估算冒充实测。

---

# 34. Wave 5 — Contract / State Closeout

## DLDS-F000｜Contract Graph Gate

建立机器图：

```text
Schema
→ Python model
→ DB
→ producer
→ consumer
→ receipt
→ projection
```

覆盖：

* Job
* Attempt
* Operation
* Asset
* AssetVersion
* Requirement
* Decision
* Rights
* Evidence
* QA
* Delivery

发现断链：

CI fail。

---

# 35. Creative DB Migration 审计

## DLDS-F010

现有 creative-v1 migration：

统一状态：

```text
MIGRATION_CANDIDATE_PENDING_AUDIT
```

先在数据库副本验证：

```text
backup
migration
legacy readback
new writes
restart
rerun migration
trigger behavior
rollback
```

通过以前：

不得将其标为 production migration。

---

# 36. Foundation 文件审计

## DLDS-F020

重点审：

```text
asset_store.py
state_resources.py
```

确认：

* explicit INSERT columns
* backward compatibility
* state ownership
* terminal immutability
* no duplicate SSOT
* migration tests

---

# 37. Creative Lineage 结构层

## DLDS-F030

DeepSeek 可以完成结构，不做真实设计验证。

统一：

```text
CreativeJob
Operation
Attempt
Asset
AssetVersion
```

每层必须支持：

```text
id
parent
inputs
outputs
state
evidence refs
rollback
```

---

# 38. Requirement / Decision Ledger

## DLDS-F040

结构化实现：

```text
Requirement
DesignDecision
Approval
RejectedVersion
DeliveryReceipt
```

只做：

* Schema
* DB
* state transition
* tests

不做：

真实设计审美判断。

---

# 39. 标准兼容修复

## DLDS-F050

### DTCG

Canonical baseline：

**DTCG 2025.10 stable**。

`typography` 必须保留：

```text
fontFamily
fontSize
fontWeight
letterSpacing
lineHeight
```

legacy 兼容：

走 adapter。

不得放宽 canonical schema。

### OTIO

Transition：

```text
in_offset
out_offset
```

按官方语义。

不得自行定义相冲突的 overlaps truth。

### C2PA

Baseline：

**2.4**。

新 claim：

```text
c2pa.claim.v2
```

signature：

```text
c2pa.signature
```

内部 Asset Graph 不被 C2PA 替代。

### Penpot

v3：

```text
ZIP
+ manifest.json
+ JSON metadata
+ binary assets
```

必须验证 archive 内引用，不只判断 ZIP。

---

# 40. GLB Validator 修复

## DLDS-F060

公共 validator 返回必须：

`JSON_SERIALIZABLE`

raw bytes 不进入 validation report。

拆：

```text
parse_glb()
validate_glb()
summarize_glb()
```

验证 accessor：

```text
SCALAR
VEC2
VEC3
VEC4
MAT2
MAT3
MAT4
```

以及：

* component type
* alignment
* byteStride
* bounds
* sparse accessors

---

# 41. QA Policy 固化

## DLDS-F070

### Deterministic QA

允许：

```text
HARD_BLOCK
```

### Rights / Security

允许：

```text
HARD_BLOCK
```

### Model-assisted QA

允许：

```text
PASS
WARN
REVIEW_REQUIRED
```

不得单独产生最终：

`REJECTED`

### Human Jury

最终：

```text
APPROVE
REJECT
```

DeepSeek 只实现政策和测试。

不做设计判断。

---

# 42. Capability IDs

## DLDS-F080

废除逻辑层自由字符串：

```text
host_classes=["editor",...]
```

改成：

```text
host_capability_refs
```

引用 versioned Capability Registry ID。

human-readable label 只用于显示。

---

# 43. Wave 6 — Third-party Governance

## DLDS-G000｜Sources Lock

所有外部项目必须记录：

```text
name
canonical_url
commit/revision
observed_at
digest
license
role
disposition
```

禁止：

`latest`

成为 production identity。

---

# 44. Adapter Registry 清理

## DLDS-G010

状态只允许：

```text
DECLARED
STRUCTURAL
CONTROLLED_RUNTIME
REAL_WORKFLOW
INDEPENDENT_ACCEPTANCE
RELEASED
BLOCKED
REVOKED
```

不得：

manifest 声称 E3，但 evidence 只有 E1。

---

# 45. Rights Registry

## DLDS-G020

每个：

* model
* plugin
* code donor
* font
* asset
* external API

有：

```text
license
territory
use restriction
output restriction
redistribution
evidence source
observed_at
refresh policy
```

---

# 46. H3

## DLDS-G030

保持：

`BLOCKED_BY_LICENSE`

DeepSeek 不下载、不运行、不 benchmark H3。

只允许：

* license metadata
* provider contract
* rights gate

---

# 47. Supply Chain Gate

## DLDS-G040

运行：

* license audit
* secret scan
* third-party source audit
* lockfile audit
* generated artifacts audit
* executable/binary inventory

新增依赖必须：

```text
owner
reason
license
exact version
rollback
```

---

# 48. Wave 7 — Tests / CI / Evidence

## DLDS-H000｜Exact Subject Testing

以后测试报告必须绑定：

```text
COMMIT SHA
```

或：

```text
WORKTREE DIGEST
```

禁止：

“1351 OK”

但不知道测的是谁。

---

# 49. Full Test Gate

## DLDS-H010

运行：

* deterministic forward
* reverse
* randomized seeded
* critical module repetition

保持现有 test isolation discipline。

---

# 50. Fresh Clone

## DLDS-H020

从干净 clone 验证：

* install
* dependencies
* contracts
* generated reports
* tests
* path boundaries

不能使用本机隐形依赖冒充可复现。

---

# 51. Current Reports

## DLDS-H030

重新生成所有：

```text
PROJECT_STATUS
capability index
evidence index
adapter matrix
size report
language report
spill report
dependency report
```

全部绑定 exact subject。

---

# 52. Evidence Level Discipline

## DLDS-H040

DeepSeek 最高可以独立证明：

### E0

声明。

### E1

结构。

### E2

仅对它真正能运行的非专业宿主受控 runtime。

它不得自行声称：

```text
Adobe E3
OpenDesign E3
ComfyUI design E3
Blender E3
Human Jury E4
```

---

# 53. Independent Structural Audit

## DLDS-H050

实现者和最终审计者不能完全同一条 worker 路径。

重点审：

* Contract Graph
* migration
* cleanup
* authority
* language boundary
* spill
* repo size
* evidence overclaim

---

# 54. Wave 8 — Security / Failure Recovery

## DLDS-I000

所有 destructive operation：

必须有：

```text
plan
candidate list
backup
verification
rollback
receipt
```

---

# 55. Unknown Outcome Recovery

## DLDS-I010

保留现有 Operation/Attempt 原则：

未知结果：

不得自动重跑 destructive operation。

先：

```text
reconcile
```

---

# 56. Clean Tree Gate

## DLDS-I020

任何 Wave 完成：

```text
git status
```

必须：

* clean

或：

* 所有 dirty paths 有明确 owner/task attribution

---

# 57. Wave 9 — Codex Preparation

本 Wave 由 DeepSeek **只准备任务**。

不执行真实 Host。

## DLDS-J000｜Codex Queue Builder

输出：

```text
docs/taskpacks/
DESIGN-LAB-CODEX-REAL-HOST-HANDOFF.md
```

---

# 58. Codex 保留任务：Adobe

状态：

`DEFERRED_TO_CODEX`

包括：

```text
Photoshop create/readback/edit/reopen
Illustrator create/readback/edit/reopen
Premiere project/timeline/readback
Adobe failure/rollback
```

DeepSeek 只准备：

* contract
* fixture
* commands outline
* evidence template

---

# 59. Codex 保留任务：OpenDesign

`DEFERRED_TO_CODEX`

真实：

```text
install/probe
create
readback
modify
save
reopen
rollback
```

DeepSeek 不执行。

---

# 60. Codex 保留任务：MiniMax Design

`DEFERRED_TO_CODEX`

前提：

Rights / region / host qualification。

DeepSeek 只做静态 contract/rights。

---

# 61. Codex 保留任务：ComfyUI

`DEFERRED_TO_CODEX`

Codex 后续执行：

* install/runtime
* workflow submit
* GPU inference
* output readback
* partial rerun
* failure recovery

DeepSeek 只做 Workflow Contract / fingerprint / state machine。

---

# 62. Codex 保留任务：Penpot

`DEFERRED_TO_CODEX`

DeepSeek：

验证 `.penpot` structural format。

Codex：

真实 Penpot/MCP create/edit/readback。

---

# 63. Codex 保留任务：Blender / 3D

`DEFERRED_TO_CODEX`

DeepSeek：

* GLB validator
* scene schema
* asset contracts

Codex：

* Blender install
* scene control
* reopen
* render
* editable scene verification

---

# 64. Codex 保留任务：Design Quality

全部：

`DEFERRED_TO_CODEX/HUMAN`

包括：

* visual fidelity
* typography quality
* composition
* professional editability
* anti-AI visual quality
* client-facing quality
* Human Jury

DeepSeek 不得签字。

---

# 65. Codex 保留任务：Audio / Video

DeepSeek：

完成：

* provider contracts
* OTIO
* media metadata
* state
* delivery validators

Codex：

真实：

* ASR/TTS/music
* video generation
* Premiere
* playback/export

---

# 66. Wave 10 — Final DeepSeek Closeout

## DLDS-K000｜No-overclaim Audit

扫描仓库所有：

```text
integrated
verified
supported
ready
complete
E3
E4
```

确认与 evidence 相符。

---

# 67. Final Cleanup Audit

## DLDS-K010

确认：

```text
no stale active paths
no unauthorized third-party source
no model weights in Git
no runtime in Git
no active .hermes writes
no duplicate SSOT
no unknown spill
```

---

# 68. Final Language Audit

## DLDS-K020

确认：

* Python ownership 清晰
* TypeScript ownership 清晰
* Host JS ownership 清晰
* 无无授权新主语言
* 无 duplicate backend
* Schema 为跨语言 contract truth

---

# 69. Final Repository Audit

## DLDS-K030

必须输出：

```text
files before/after
Git pack before/after
runtime data before/after
bytes reclaimed
third-party copies removed
spill migrated
spill deleted
remaining exceptions
```

---

# 70. Final Evidence Packet

## DLDS-K040

输出：

```text
DEEPSEEK-FINAL-AUDIT.md
DEEPSEEK-TASK-STATE.json
REPOSITORY-NORMALIZATION-REPORT.md
LANGUAGE-GOVERNANCE-REPORT.md
REPOSITORY-SLIMMING-REPORT.md
DATA-SPILL-MIGRATION-REPORT.md
CONTRACT-GRAPH-REPORT.md
CODEX-REAL-HOST-HANDOFF.md
```

---

# 71. DeepSeek 最终 Done When

必须全部满足：

1. 本 TaskPack 已真实落仓并有 SHA-256。
2. `AGENTS.md` 指向唯一 current DeepSeek TaskPack。
3. 旧 TaskPack 权威关系已明确。
4. dirty worktree 已完成归属和冻结。
5. 所有 active 代码都能映射到任务。
6. 仓库目录只有一套 current 规范。
7. `.project-local` 成为 DESIGN-LAB 自有 runtime 唯一根。
8. 无活动 `.hermes` 项目写入。
9. 仓库体积有 before/after 实测。
10. 可安全删除的 cache/temp 已真正清理。
11. 外溢数据完成 census。
12. DESIGN-LAB-owned spill 已迁移或形成明确例外。
13. 删除动作均有 manifest / hash / rollback。
14. Python/TS/Host JS/Rust 语言边界已落地。
15. 依赖锁唯一。
16. Contract Graph 无未解释断链。
17. creative DB migration 已在副本完整演练。
18. Foundation state 文件已独立复核。
19. DTCG canonical 为 2025.10。
20. OTIO 不存在私造冲突语义。
21. C2PA contract 对齐 2.4。
22. Penpot validator 对齐 v3。
23. GLB validator JSON-safe 且覆盖矩阵 accessor。
24. QA 自动/模型/人工边界明确。
25. Rights Registry current。
26. H3 未绕过 Rights Gate。
27. Third-party source 只保留最小吸收或 lock。
28. current reports 绑定 exact subject。
29. clean clone 可以重现静态/测试层。
30. DeepSeek 没有冒充任何真实设计 Host E3/E4。
31. Codex handoff 已完整生成。
32. 工作树最终 clean，或剩余变化全部有 owner/task attribution。

---

# 72. DeepSeek 禁止宣称的完成项

即使本包全部完成，仍不得声称：

```text
DESIGN-LAB 产品全部完成
Photoshop integrated E3
Illustrator integrated E3
OpenDesign integrated E3
ComfyUI production ready
Blender integrated
MiniMax validated
professional design quality passed
Human Jury passed
release ready
```

这些要等 Codex / Human 后续验证。

---

# 73. 本包完成后的 Codex 起点

Codex 不需要再做：

* 仓库清理
* 语言规划
* DB Schema 重构
* 目录迁移
* 第三方源码清理
* 外溢数据清理
* 基础 Contract 修复

Codex 直接从：

```text
Real Host E2
→ Real Workflow E3
→ Independent / Human E4
```

开始。

---

# 74. 本包最终目标

DeepSeek 交付的不是“一个设计能力完整的软件”。

而是一个：

> **干净、规范、可维护、可回滚、低体积、无数据外溢、契约一致、语言边界稳定，并且已经为 Codex 真实专业设计执行准备完成的 DESIGN-LAB 工程底座。**

随后 Codex 只负责：

> **证明它真的可以控制专业软件、生成真实可编辑资产、读回、修改、重开、恢复并通过专业设计验收。**
