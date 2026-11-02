# DESIGN-LAB 云端更新审计：PR #115

审计日期：2026-09-05。结论：**REQUEST_CHANGES；当前不应合并或认定 Wave 0/1 已验收完成。** 本报告为只读审计，没有提交代码、评论、审批或修改云端仓库。

## 1. 审计对象与结论边界

| 项目 | 核实结果 |
|---|---|
| 仓库 | DTALEX66/DESIGN-LAB |
| main / 上次基线 | `2aca27f69b1909251640382ed3b4195cf9accd9b`，本轮读取仍未变化 |
| 更新所在 | [PR #115](https://github.com/DTALEX66/DESIGN-LAB/pull/115)，`feat/r0-freeze-baseline` |
| 审计 head | `3dd0a13c95f3baf1280cb23b566498c59db37b73` |
| 增量 | 19 commits，67 个变更文件，+3523 / -67；head 共 1418 个 tracked files |
| PR 状态 | open，mergeable=true，mergeable_state=blocked；无合并冲突不等于可验收 |
| 最新 PR CI | [33931983324](https://github.com/DTALEX66/DESIGN-LAB/actions/runs/33931983324)：failure |
| 同 head push CI | [33898661448](https://github.com/DTALEX66/DESIGN-LAB/actions/runs/33898661448)：failure，同样失败于 Python unit tests |
| 上次主线 CI | [33789540128](https://github.com/DTALEX66/DESIGN-LAB/actions/runs/33789540128)：success，不能用于证明当前 PR 通过 |
| 当前任务包完整性 | 仓内任务包 SHA-256=`7432d53bdebb14f21f62390a422268a575e95d97f2fe979ac5dda731434dcadb`，与上一轮交付一致 |

本轮逐项检查变更清单、变更代码、30 个新增 Schema、执行进度文件、任务包相关 DoD、现存消费路径及 GitHub CI 日志；在独立 clone 上使用仓内 uv.lock 建立审计环境，执行针对性复现。未操作真实 Windows、Adobe/Corel、GPU 或 H3；未重跑完整耗时测试套件，完整套件结果来自本次 head 对应的云端日志。结束前再次回读 PR，head 未变化。

根 AGENTS.md 已读取。其“当前任务包”和“Open Design 主宿主”仍与本会话已确定的 standalone-first 决策冲突，列入问题，不将旧指令误当成新任务包已被撤销。

## 2. 已确认的实质进展

- v1.4 任务包和 YAML 台账已进入仓库，任务包内容哈希正确。
- 新增 standalone-first ADR、个人研究用途的 Rights Decision、治理文档、CODEOWNERS、pyproject.toml 与 uv.lock。
- 多个 Adapter 的 `supported` 改为 false，H3 被标记为许可证阻断；撤回历史能力的方向正确。
- 修正报告生成器的 Adapter Registry 路径；迁移了两个脚本及 release workflow 的部分 `.hermes` 路径。
- 新增 30 个 Schema 文件与 Adapter 抽象接口骨架；新增的两项 SPI 单测通过。

这些应保留。但声明、文件存在、接口骨架、部分正向测试，均不能替代任务包规定的行为验收。

## 3. 发现与修复建议

### F01 · P1 · Registry 新状态破坏现行 Schema，CI 已真实失败

位置：[integrations/adapter-registry.json](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/integrations/adapter-registry.json#L243)，现有 `design-lab/schemas/adapter-contract.schema.json`，`test_oda4_0206_adapters.py`。

H3 的 `status` 改为 `BLOCKED_BY_LICENSE`，但消费它的 Adapter Contract 只接受 `declared/structural/runtime/missing/unsupported`。云端 509 tests 中 1 error、6 skipped，错误是该枚举不合法。本地单独运行同一模块，也得到 8 tests / 1 error。

修复：明确区分安装/结构状态、当前能力等级和许可准入状态；可增加独立准入字段及 reason，或一致升级 Registry Schema 与全部消费者。不能删除许可证阻断、放宽为任意字符串或跳过失败测试来恢复绿灯。加入“受阻状态可以合法存储，但绝不允许执行”的正反测试。

关联任务：R0-006、R0-007、R1-003。

### F02 · P1 · JobSpec 的本地 `$ref` 无目标，正常输入无法验证

位置：[job-spec.schema.json](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/design-lab/schemas/contracts/job-spec.schema.json#L20)。

`operation_intent` 引用 `#/$defs/operationIntentRef`，文件却没有 `$defs`。包含全部 required 字段的最小实例验证时抛出 `PointerToNowhere`。JSON 解析成功或 Schema 自身形式检查不能代替实际实例验证。

修复：定义真实的 intent 引用合同，或用已登记的 OperationIntent Schema；固定离线引用注册表。每个 Schema 至少提供一个正例、一个反例，并验证所有 `$ref` 可解析。实例还应明确 Job 与 Operation、Attempt 的不同身份职责，不能仅消除报错。

关联任务：R2-001。

### F03 · P1 · 新 Schema 无法表达既定审计、授权与副作用合同

位置：`design-lab/schemas/contracts/`，尤其 [job-attempt](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/design-lab/schemas/contracts/job-attempt.schema.json)、[capability-evidence](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/design-lab/schemas/contracts/capability-evidence.schema.json)、[asset-ref](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/design-lab/schemas/contracts/asset-ref.schema.json)。

- JobAttempt 没有 `attempt_id`，但 OperationReceipt 必须引用它；`additionalProperties:false` 还拒绝补入该字段。
- CapabilityEvidence 只接收 ID、level、bound_sha 等少数字段，允许 E5；缺失 host/plugin/OS/fixture/artifact/readback/rollback/TTL 等证据绑定。实测：空 ID、全零 SHA 的 E5 声明通过；增加 `artifact_hash` 或 `host_version` 反而被拒绝。
- AssetRef 无 rights/runtime binding 引用；AssetManifest 的 items 只要求 object，`assets:[{}]` 通过。
- RightsDecision 的 decision/use_scope、OperationReceipt 的 status 是任意字符串。实测任意 decision 和 `made_up_success` 均通过。
- ExecutionEnvelope 的 payload 是开放 object，不能独自承担受限可执行合同。

这是合同完整性问题；未证明已有执行器被这些输入实际攻破，因为相关新执行器尚未提交。

修复：按 v1.4 任务卡补齐可关联身份、引用、枚举、非空/hash/范围限制和版本策略；Schema 与运行时语义校验分工明确。拒绝状态需测试，必要有效证据也必须能通过。E5 与当前 E0–E4 能力模型差异需要明确迁移，不能无说明混用。正式冻结前增加跨对象/未来 Python–TypeScript 合同测试。

关联任务：R2-001、R2-006、R2-009、R2-010、R2-014、R2-019～021。

### F04 · P1 · uv 锁定环境不能运行现有重建功能，CI 仍绕过新锁

位置：[pyproject.toml](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/pyproject.toml)、`uv.lock`、`requirements.txt`、`packages/capabilities/reconstruction/requirements-core.in`、`.github/workflows/canonical-verify.yml`。

`uv sync --locked` 本地成功，但项目依赖仅 jsonschema。既有 requirements 还包含 Pillow、numpy、scikit-image、defusedxml；这四类模块在新锁定环境中均不存在。CI 继续执行 `pip install -r requirements.txt`，不能证明新锁可复现现有测试/功能。

修复：把现行 core 依赖完整纳入 pyproject 的依赖或明确默认安装的 extra/group，重新生成锁；CI 与本地使用同一 locked 安装入口。若要做最小核心 profile，须同时定义 profile 的入口/测试范围，不能继续声称一个当前锁支持全套。CLI 的包装/安装可保留后续任务，但应维持 PARTIAL，不能从 `src/` 存在推断可安装 CLI。

关联任务：R1-001、R1-003、R2-002。

### F05 · P1 · “sealed bundle 原子回滚修复”没有进入生产路径

位置：[verify_reconstruction_bundle.py](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/design-lab/scripts/verify_reconstruction_bundle.py#L161)。

新增 `check_sealed()` 位于 `raise SystemExit(main())` 之后；以 CLI 执行时不会定义该函数。全仓引用扫描仅找到它自己的定义，调用数为 0。真正负责 promotion 的 `packages/capabilities/reconstruction/evidence.py` 与基线逐字相同。本次没有新增任务包要求的 before_swap/after_backup/after_promote 故障测试。

修复：在真实构建/验证/封存/提升路径接入检查，校验真实内容 hash 和封存状态，并提供所有故障点的旧包恢复、残留及 Receipt 证据。辅助函数有三个键名不能证明原子性；不要为关闭任务号而给不可达函数补一个表面单测。

关联任务：R0-004；该任务应回到未验收状态。

### F06 · P1 · `.project-local` 迁移漏掉重建主链，R0-003 不能 DONE

位置：[reconstruction/contracts.py](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/packages/capabilities/reconstruction/contracts.py#L131)、`intake.py:25/426`、`render.py:31`、`evidence.py:472/1481`、`state.py:1502`；另有 `upgrade_asset_sidecars.py:79`。

重建合同仍生成 `.hermes/task-runtime/reconstruction/...` 和 `.hermes/task-artifacts/reconstruction/...`；intake、render、evidence、rollback 仍以这些目录作为实际边界。测试 Fixture `_create_contract()` 也创建旧目录。PR 迁移的两个脚本不覆盖这些主链。

修复：集中实现 runtime root resolver，再同步合同生成、读取、写入、回滚、清理、Fixture、workflow；旧证据采用显式只读迁移规则。补根覆盖参数、旧路径拒写和无残留验证；不要只在扫描器里忽略 `.hermes`。

关联任务：R0-003、R0-005、R2-016。

### F07 · P1 · 新 manifest 引用门读取错误结构，错误结果还会导致崩溃

位置：[verify_product_manifest_v3.py](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/design-lab/scripts/verify_product_manifest_v3.py#L286)。

新函数遍历 `capabilityFamilies[].capabilities[]`，而当前 7 个 family 均以 `paths[]` 表达路径，没有任何 `capabilities` 子项，因此实际新检查遍历 0 个引用。即便构造其预期形状，不存在的路径也不会产生错误，因为它不检查 exists。它把失败记录追加为 str，而 `print_results()` 按 `Result.ok` 读取，实测 history 反例触发 `AttributeError`。

注意：旧的 `require_path()` 已有部分存在性和边界保护，本发现不表示整个旧验证器完全失效；问题在于本次声称补齐的覆盖与稳定错误结果未实现。

修复：从实际权威结构提取引用，统一已有 Result/check/require_path 机制；正确解析当前与历史权威性，并覆盖 manifest、taskpack、script、schema、artifact 的具体字段。测试真实结构的缺失、history、穿越、symlink 和正确引用。

关联任务：R0-002。

### F08 · P2 · CI 新触发项只加到 push，新增 `src/**` 也未纳入

位置：[canonical-verify.yml](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/.github/workflows/canonical-verify.yml#L3)。

`.project/**`、`integrations/**`、`pyproject.toml`、`uv.lock`、`packages/capabilities/**` 只加入 push；pull_request 的 paths 未同步。`src/**` 在两类事件中都缺失。因此未来只修改这些路径的 PR/提交可能跳过所需事件的检查；本次因为同时修改 design-lab/docs，才触发了 CI。

修复：对齐权威路径覆盖，优先去掉工作流级 paths 限制，或以 always-run 调度 job 加内部差异判定保证 required checks 总有明确结果。为 src-only、integration-only、lock-only、manifest-only 变更设置触发 Fixture。不要依赖一次大型混合 PR 的绿灯证明路径覆盖正确。

关联任务：R1-003。

### F09 · P2 · 历史基线只保存哈希，当前入口也未统一

位置：[reports/history-baseline.json](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/reports/history-baseline.json)、[AGENTS.md](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/AGENTS.md#L90)。

已导入的 taskpack hash 正确；但历史 manifest 与 crosswalk 的两份 CSV 在该提交树中均不存在。history-baseline 只有哈希与一句 sourceSet 描述，无可恢复位置、完整对话 hash/字节/行/段数和逐项检索实现。不能凭两个哈希宣称 clone 后可检索 1450 条历史 occurrence。

根 AGENTS.md 仍指向 8 月旧任务包，仍称 Open Design 为正式主宿主/主界面；新增 ADR 则要求 DESIGN 自有 Local Runtime，外项目默认关闭。当前有效入口因此仍有冲突。

修复：保留已封存历史文件原样；小型索引可纳入受控历史目录，大型/敏感原档使用授权的外部归档地址、对象 ID、hash 和恢复流程，不默认上传私人对话到公开 GitHub。增加 occurrence/旧 ID/hash/conversation 检索 Fixture，补齐基线统计与只追加规则。同步 AGENTS、manifest、README/current 入口与 superseded 标记。

这表示本次云端提交尚未接通历史恢复链，不表示先前交付的历史记录已丢失。

关联任务：R0-001、R0-008、R1-002、R5-003。

### F10 · P2 · PR 完成量与提交、台账、验收结果不一致

位置：[PR 描述](https://github.com/DTALEX66/DESIGN-LAB/pull/115)、[TASKPACK_PROGRESS](https://github.com/DTALEX66/DESIGN-LAB/blob/3dd0a13c95f3baf1280cb23b566498c59db37b73/reports/current/TASKPACK_PROGRESS-2026-09-04.json)、仓内 YAML ledger。

可核实差异：

| 声称/状态 | 实际提交证据 |
|---|---|
| PR：31/58 完成 | progress 仅有 29 条具体记录：21 DONE、1 PARTIAL、2 BLOCKED_RUNTIME、5 REGISTER_ONLY；21 DONE 仍有上述未达 DoD 项 |
| PR：15 new tests | 同目录 AST 统计 507→509，净新增 2 个 test 方法，均为 SPI 常量/类型测试 |
| PR：SQLite state store / evidence index / profile resolver / operation coordinator / doctor / MCP contract | 本次 `src/design_lab` 仅 `__init__.py` 和 59 行 `adapters/spi.py`；未提交所述新运行模块。既有 Open Design doctor 不等于本任务包的 Portable Workspace Doctor |
| R0-005 DONE：49-chain green | 最新全套 509 tests 失败；无固定/倒序/随机三种顺序、重复 20 次隔离证明 |
| R2-004 DONE | 抽象方法和两个常量/类型测试；无 mock/replay 幂等、取消、超时、恢复、readback/rollback 合同验收 |
| R1-006/007 DONE | 7 行协议/策略文档各一份，未展示并行隔离 Fixture、路径租约检查或依赖提升/回滚实现 |
| 当前执行台账 | YAML 仍为 NOT_READY / BLOCKED_BY_READINESS，后续仍登记；JSON 又声明 Wave 0/1 DONE，且全局 waves1_4 仍 REGISTER_ONLY |

修复：先更正 PR 描述及任务证据，将“文档已登记”“Schema 草案”“代码骨架”“验收通过”分开。以规范任务事件与提交/测试证据生成进度，不手工维护互相矛盾的 JSON/YAML。缺失实现标未提交或 PARTIAL；无需为凑完成数字盲目扩展功能。

同一分支汇总了多任务，尚未看到符合一任务一 worktree 的隔离证明；不能仅凭最终聚合 PR 推断从未使用独立 worktree，但必须提供任务级 owned paths/base/validation 记录才能认定 R1-006 验收通过。

关联任务：R0-001、R0-005、R1-006/007、R2-004 及进度治理。

## 4. 验证记录

| 验证 | 结果 |
|---|---|
| GitHub PR CI，全套 Python | 509 tests；1 error；6 skipped；FAILED |
| GitHub 其余 4 个 job | job 状态 success；其中 Open Design 结构检查 step 实际 skipped，不能算真实宿主通过 |
| 本地 `uv sync --locked` | 安装成功，jsonschema 4.26.0；缺 Pillow/numpy/scikit-image/defusedxml |
| 本地 Adapter Registry 测试 | 8 tests；1 error，与云端枚举错误一致 |
| 本地新增 SPI 测试 | 2 tests；PASS，仅证明常量/类型，不证明生命周期行为 |
| JobSpec 正常实例 | PointerToNowhere，无法解析 `$defs` |
| Schema 负例 | 空 Asset、任意 Rights decision、任意 Receipt status、无真实 artifact 的 E5 均被接受 |
| CapabilityEvidence 正常扩展 | 加 host_version/artifact_hash 被 additionalProperties 拒绝 |
| 新引用门 | 实际 family shape 扫描 0 项；missing 反例不报错；history 反例结果渲染崩溃 |
| sealed 函数调用静态核查 | 0 调用，CLI 定义不可达；生产 evidence.py 未变化 |
| 历史恢复文件定位 | 两份历史 CSV 均未进入本提交树 |
| 本地源代码状态 | `git status --short` 干净；依赖仅位于 ignored `.project-local/audit-venv` |

本地复现入口（仓库根，安装过程为环境准备）：

```bash
UV_PROJECT_ENVIRONMENT=.project-local/audit-venv uv sync --locked
.project-local/audit-venv/bin/python -m unittest discover -s design-lab/tests -p test_oda4_0206_adapters.py -v
.project-local/audit-venv/bin/python -m unittest discover -s design-lab/tests -p test_adapter_spi.py -v
```

JobSpec 最小复现：

```python
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schema = json.loads(Path('design-lab/schemas/contracts/job-spec.schema.json').read_text())
Draft202012Validator(schema).validate({
    'schemaVersion': 'design-lab/job-spec/v1',
    'job_id': 'j', 'operation_intent': 'op', 'attempt_no': 1,
})
```

## 5. 明确修复顺序

1. **恢复可信进度**：更正 31/58、15 tests 和未提交模块声明；R0-001～005、R0-007/008 等按实际证据重定状态，保留已完成子工作，禁止整体伪 DONE。
2. **修复明确断点**：Registry 状态/Schema 与 JobSpec 引用；建立完整 locked 依赖及两类事件的 CI 路径覆盖。
3. **闭合 Wave 0**：统一 `.project-local` 主链，接入真实封存/回滚、修复引用门，补测试隔离与历史恢复、入口一致性验收。
4. **补 Wave 1 行为证据**：可复现安装、报告生成/漂移、并行工作区隔离、依赖生命周期。未实现的策略维持 PARTIAL。
5. **再冻结 Wave 2 合同**：补齐对象关系和安全边界，用真实正反例验证 30 个 Schema；SPI 做一个 mock/replay 适配器，跑完整生命周期后再标 DONE。
6. **在修订后的 exact head 重验**：完整 canonical CI、相关反例、clean tree、历史查询和任务状态一致性均通过后再评估合并。真实 Windows/宿主/GPU 仍单独标 NOT_RUN，不能由 Linux/mock 代替。

本次修复无需推翻 v1.4 架构，也无需继续引入更多软件。应先把当前已承诺的基础工作做实，再开发可日常使用的设计运行闭环。
