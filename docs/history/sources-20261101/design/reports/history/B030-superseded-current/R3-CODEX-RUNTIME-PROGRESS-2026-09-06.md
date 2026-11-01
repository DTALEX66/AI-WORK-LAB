# R3 Codex 运行时修复进展 — 2026-09-06

> **SUPERSEDED（历史快照）**：本报告为 B030 阶段的 superseded 历史检查点，
> 不作为 current 任务入口；当前唯一入口见 `AGENTS.md` 与
> `.project/governance/authority-index.json`。

> 历史检查点：以下状态与测试数保留原观察范围。后续 R3-01 已完成本地验收，
> R3-05 的依赖已满足，R3-02 路径切片已有新增验证。当前状态请以
> [生成账本投影](PROJECT_STATUS.md) 为准，不将本快照重新解释为新实机测试。

状态：`IMPLEMENTED_LOCAL` / `TESTED_LOCAL`，R3-05 与 R3-06 整体仍为 `PARTIAL`。
分支：`codex/r3-runtime-correctness`；基线 SHA：`c4dccd58331bc4561eb89265283d924b7630d113`。
本报告是本轮代码与验证快照，不替代当前任务包或单一任务 ledger。

## 已实现

- R3-05：稳定请求身份、哈希规范化、显式编号重试、原子派发 claim、
  未知副作用核对、取消请求/确认/读回、成功回执绑定、终态不可改写、
  v1→v2 事务迁移与备份、进程崩溃恢复。
- R3-06：独立 artifact ID、版本/产物原子事务、同名文件不可变版本、
  租约/续租/接管/fencing、暂存校验与原子发布、失败 journal 和隔离恢复。
- 审阅补强：旧库多 Job 归属冲突、历史取消/成功冲突、重复取消确认、
  损坏租约到期值、Windows 非法文件名在 journal 写入前拒绝。

实现及回退说明：[运行状态与恢复约定](../../docs/decisions/R3-RUNTIME-RECOVERY-2026-09-06.md)。

## 验证记录

解释器：本仓 `.venv/Scripts/python.exe`，Python 3.13.14；必需模块导入通过。
项目当前不存在全局规则提到的 `scripts/workflow/execution_preflight.py`，因此先
直接核对解释器、依赖与项目根，再运行测试。没有因此安装或替换系统环境。

- 第一冻结候选：`scripts/run_python_tests.py`，618 tests，OK，无 skips；
  约 1050.5 秒。随后统一校验 49 个子门全部通过；manifest、runtime contracts、
  license 检查退出码均为 0。执行期间受测文件哈希未变。
- 其后新增 7 项审阅回归，先 RED 后修复。最终候选的全部 5 个受影响测试模块：
  **60 tests，OK，无 skips**（约 2.5 秒）。
- 最终静态/统一门的记录在 `final-results.json`；应核对每条命令退出码及
  `sourceUnchanged`，不要以本文件更新时间代替测试结果。
- 未在最后 7 项局部补强之后再次运行整套 Python；618 的结果仅绑定前一冻结
  候选。最终差异由完整运行时定向测试及重新执行的核心门覆盖。
- 真实子进程分别在“完成文件写入、尚未回执”和“rename 后、DB commit 前”退出，
  测试通过读回现存文件/DB 验证，不依赖只构造 mock 成功结果。

本地证据目录（Git 忽略）：`.project-local/task-artifacts/r3-execution/`。
`gate-results.json` 与 `final-results.json` 分别保存两个候选的文件 SHA-256、
解释器、命令、用时和退出码；同目录保留全部日志。

## 尚未闭环

- 包内字段为 `depends_on`。R3-05 依赖 R3-01；R3-06 依赖 R3-02 和 R3-05。
  R3-01 当前入口/账本与 R3-02 全项目路径解析器尚未完成，故两项不能标整体 DONE。
- 当前文件发布根限制在本项目 `.project-local/` 子目录。全作品库方案和多入口
  实际写入追踪仍属 R3-02；服务对接属 R3-09。
- Adobe/GPU/独立 UI/模型推理未执行；本轮只验证合成 fixture 的真实本地进程、
  SQLite 和文件行为，不对应宿主 E3 或产品可用性验收。
- 没有迁移用户实际 DB，没有发布或推送；云端没有验证这批未提交代码。
- 自动化版本降级、机器断电恢复与最终人审/rights/release 仍需后续任务。

下一阶段：R3-01 → R3-02，随后 R3-04/07/08，再进入服务、工作台与生成入口。
已确认 R3-01 的具体问题：`generate_current_reports.py` 列出了
PROJECT_STATUS.json/md，却没有实际生成这两份报告。

## 执行错误保留

首次门禁辅助脚本取错一层父路径，在 Git 检查失败前误建空目录
`D:/All projects/.project-local/task-runtime/r3-gate`。已修正并添加“先确认 Git 根，
再 mkdir”的断言；正确运行的数据均在 DESIGN-LAB 内。该空目录的精确清理被
自动安全策略拒绝（仅提供 blocked by policy），没有尝试其他删除方式；只读检查
确认其无文件。待单独处置，不能写成已清理。
