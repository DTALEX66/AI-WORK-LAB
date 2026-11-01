# AGENTS.md — AIWORKLAB / AI-WORK-LAB 项目级执行规则

本文件只管**融合后的这一个项目**。它不覆盖用户级通用核心
（`C:\Users\ALEX\.qoder-cn\agents.md` 里的 UNIVERSAL_AGENT_CORE），也不覆盖
[INTEGRATION_POLICY.md](INTEGRATION_POLICY.md) 里的执行边界；它负责的是：先读什么、
在哪更新、什么已经不再是现行规则。

## 0. 项目身份（不要重新推导这件事）

WORK-LAB 与 DESIGN-LAB **已合并**为 AIWORKLAB / AI-WORK-LAB。旧名称只用于历史追溯与迁移兼容。

> 警告（真实踩过的坑）：本工作区可能把 `D:\All projects\DESIGN-LAB`、`D:\All projects\WORK-LAB`
> 作为附加目录一起挂载，于是会话会自动载入**来源仓自己的** `agents.md`。那份文件里的
> 「唯一 integrated TaskPack」「DL-KB-01…16」「currentExecution 34 项 FROZEN_DEFERRED」
> 「手机端是排除项」等，是**来源仓的历史规则**，不是本仓的现行派工。
> 在本仓工作时，以本文件和 [PROJECT_CURRENT.md](PROJECT_CURRENT.md) 为准；
> 来源仓内容只作迁移线索，不在来源仓里继续分别维护。

## 1. 必读顺序（按序号读，不要跳）

1. [PROJECT_CURRENT.md](PROJECT_CURRENT.md) — 根入口（顶层权威只有那一份）：现在成立什么、还差什么、下一步。
2. [INTEGRATION_POLICY.md](INTEGRATION_POLICY.md) — 执行边界与授权沿革（含 §6 的首次上传放行）。
3. [docs/CODEX-AUDIT-ENTRY.md](docs/CODEX-AUDIT-ENTRY.md) — 独立复审入口、逐轮实测与**收回记录**。
4. `docs/AUDIT-STATE.json` — 哪一个提交被审过、审出什么、上传事实（机器可读）。
5. 与任务相关的**现行寄存器**（唯一维护位置见 §3），不要凭记忆报数字。
6. 历史只通过上面的入口进：`AI-WORK-LAB_HANDOFF_20261029/`、
   [docs/CODEX_REWORK_ITEMS_F01-F10.md](docs/CODEX_REWORK_ITEMS_F01-F10.md)、
   `migration/source-coverage-work.csv` / `migration/source-coverage-design.csv`。

任何旧任务包、旧报告、旧提示词、上一次会话的结论、分支名和提交数，**都不是 Authority**；
它们和寄存器冲突时，一律以寄存器为准。

## 2. 开工前确认（每次）

```bash
git rev-parse HEAD              # 当前真实 SHA 自己读，别抄文档里的数字
git status --porcelain=v1       # 保护已有改动；发现别人的未提交内容先弄清再动
.venv/Scripts/python.exe -B -X utf8 scripts/check_project_current.py --check
```

`.venv/Scripts/python.exe` 是本仓可用解释器；不要假设 `python` 在 PATH 里。

## 3. 更新责任：一个内容只有一个维护位置

项目定位、能力、迁移去向、实现或验收状态**发生变化**时，必须同步更新下表对应的位置，
并且**只**更新那一处；其他文件改为链接或引用，不复制第二份状态。

| 内容 | 唯一维护位置 | 其他文件 |
|---|---|---|
| 项目身份与当前结论 | `PROJECT_CURRENT.md` | 引用 |
| 能力族与验证状态 | `migration/capability-family-register.csv`（由 `scripts/build_requirement_traceability.py` 生成） | 链接 |
| 验收子句逐条结论 | `migration/task-acceptance.csv`（`scripts/build_task_acceptance_register.py`） | 链接 |
| 来源文件去向 | `migration/source-coverage-work.csv`、`migration/source-coverage-design.csv`（`scripts/build_source_coverage.py`）、`migration/copies.json` | 链接 |
| 阻断与延期 | `config/blocker-register.json`（`scripts/build_blocker_register.py`）、`migration/deferral-register.json` | 链接 |
| 端点面实测 | `migration/route-surface.csv`（`scripts/probe_full_surface.py`） | 链接 |
| 审计项闭环与逐轮实测 | `docs/CODEX-AUDIT-ENTRY.md`（追加小节，**不改写历史**） | 追加 |
| 执行边界与授权 | `INTEGRATION_POLICY.md`（定点放行，不整份重写） | 追加 |

规则：

- **数字不手抄。** 登记表由生成器现算；改完内容就重跑对应 `scripts/build_*.py`，
  再用它的 `--check`（比较模式，只写不比对的那台除外：`build_requirement_traceability.py` 无 `--check`，
  由 `tests/unified/test_v16_traceability.py` 守）。
- **状态与验证分开。** 「实现未验证」「待迁移」「等价替代」「重复合并」「明确废弃」「未来能力」
  「冲突待裁决」是不同结论，不许合并成"已完成"。文档登记和延期不是能力交付。
- **PARTIAL 必须写明缺什么**，不能只标 PARTIAL。
- **不许用 mock、合成回执或模型自报补成"全通过"**；真实宿主往返、模型推理、真人专业签字
  按 `NOT_RUN/BLOCKED/DEFERRED` 如实记录。
- **顶层入口改动后要过防漂移检查**：`scripts/check_project_current.py --check` 必须 rc=0。
  它的数字来自 `--print-block` 现算，不靠人肉维护。

## 4. 验证要求（按改动面选，不无限全量）

| 改了什么 | 至少跑 |
|---|---|
| 顶层入口 / 寄存器结构 | `scripts/check_project_current.py --check` + 对应 `build_*.py --check` |
| 后端路由或内核 | 受影响的 `tests/unified/` 对应 `test_v*` 文件 + `scripts/boot_probe.py` |
| 迁移脚本与台账 | `tests/unified/test_v07_migration.py` + `scripts/migrate_sources.py --plan`（`unmanaged` 必须为 0） |
| 交付级结论（新证据、改绑收据） | 全量 `tests/unified tests/legacy`，然后重新取收据并改绑登记表 |

红了就修根因。**不删测试、不降低断言、不用 skip 换绿**；绕不过去的限制写进
`config/blocker-register.json`，让验收门如实挡住，而不是把结论改软。

## 5. 边界（不可协商，逐条来自 INTEGRATION_POLICY.md）

- 本地执行为默认。提交、推送、合并、发布、远程 CI、上传数据各自需要 owner 的明确授权；
  一次授权不自动延伸到下一次。
- 两个来源仓与本仓的 `D:\All projects\Project Archiving` 一律**只读**；不反向清理归档。
- 真实凭证、私有会话、原生认证库、用户作品不入 Git、不复制、不打印明文。
- 运行产物只落 `.project-local/`（Git 不跟踪），E:/F: 盘需精确路径授权。
- pre-push hook 不用 `--no-verify` 绕过。

## 6. 下一轮怎么接

从 `PROJECT_CURRENT.md` §五「下一步」取第一项，再到对应寄存器确认现值；
不要从上一轮的提示词或聊天摘要里推断当前状态。
