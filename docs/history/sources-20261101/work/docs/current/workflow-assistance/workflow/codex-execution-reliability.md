# Codex 执行可靠性与证据转译

## 目的

本规范把跨项目可复用的执行故障处理纳入 Workflow Assistance，但不把
具体项目源码、Task Ledger、状态日志或私有 Codex 状态提升为全局资产。

适用范围：

- Windows 路径、PowerShell、文件锁、ACL、ANSI 输出；
- Python 解释器和可选依赖预检；
- 当前分支、upstream、main、PR、squash merge 与 exact-SHA CI；
- Markdown 相对链接；
- 规划、实现、测试、CI、合并、安装态运行的状态转译；
- Codex 性能分段和低回合数执行。

不适用范围：

- 读取 `$CODEX_HOME/memories/**`、auth、session、keychain、cookie、
  prompt/response body；
- 自动修改 provider、model、sandbox、approval、MCP、plugin 或 project
  trust；
- 替项目修改源码、状态日志、分支或发布状态；
- 通过提权、ACL 改写或强杀共享进程绕过文件权限。

## 所有权分类

| 问题 | 全局能力 | 项目动作 |
|---|---|---|
| 私有 memory 读取被拒 | 规定 fail-closed 边界 | 改用 tracked truth 或用户脱敏摘要 |
| 忽略目录删除失败 | 精确路径 cleanup、postcondition、阻塞分类 | 诊断并仅删除授权的 runtime residue |
| PowerShell 返回码误导 | `-ErrorAction Stop` + `Test-Path` 规则和扫描器 | 重新执行精确命令并回读目标 |
| Python 可选依赖缺失 | 解释器/模块预检 | 使用项目权威 venv 跑目标测试 |
| 当前分支与 main 混淆 | 结构化 Git identity report | 选择项目授权的基线或隔离 worktree |
| squash merge SHA 不同 | PR mergeCommit 与 exact-SHA CI 规则 | 修正项目状态日志 |
| Markdown 相对链接错误 | 从文档目录解析的链接检查 | 修改实际失效链接 |
| 规划/实现/发布混称 | 七层 lifecycle taxonomy | 对每个项目能力逐层填状态 |
| ANSI 颜色码 | 解析前去控制字符 | 不把终端颜色误报为仓库乱码 |
| Codex 执行慢 | 分段时间线、matched A/B、持续 writer | 按项目风险策略减少回合和门禁 |

## 只读执行预检

入口：

```text
packages/client-neutral-core/scripts/execution_preflight.py
```

示例：

```bash
python packages/client-neutral-core/scripts/execution_preflight.py \
  --project D:/All-projects/Target \
  --main-ref origin/main \
  --compare-ref origin/feature \
  --require-module pdfminer \
  --require-module pdfplumber \
  --markdown docs/truth/handoff.md
```

输出 `workflow/execution-preflight/v1` JSON，明确包含：

- 当前 branch、HEAD、tree 和 dirty count；
- upstream ref/SHA 及是否与 HEAD 相同；
- explicit main ref/SHA/tree、HEAD 与 main 的 ahead/behind；
- 额外比较分支；
- 精确 Python executable、版本、venv 和模块能力；
- 从每个 Markdown 文档目录解析的相对链接问题。

该工具不 fetch、不切分支、不写项目、不读取私有配置正文，也不输出 dirty
文件路径或 prompt/response 内容。缺失 main ref、缺失要求的模块或失效链接会
返回 `BLOCKED`。

## Windows 精确清理

首选项目数据入口：

```bash
python packages/client-neutral-core/bin/hermes-project-data.py --project D:/All-projects/Target \
  cleanup-path audit-residue-name
```

约束：

1. target 必须是 `.project-local/runs/` 下的相对路径；
2. 绝对路径、`..` 逃逸、symlink/junction/reparse traversal 一律拒绝；
3. 只删除一个精确 target，不执行 broad clean；
4. PermissionError/文件锁转为 `BLOCKED_RUNTIME_CLEANUP`；
5. 不提权、不改 ACL、不杀进程、不自动重复递归删除；
6. 成功必须再次确认 target 不存在。

如果必须使用 PowerShell：

```powershell
$ErrorActionPreference = 'Stop'
$target = 'D:\exact project\.hermes\task-runtime\one-residue'
Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
if (Test-Path -LiteralPath $target) {
    throw "cleanup postcondition failed: $target"
}
```

`Remove-Item` 的 stderr 和进程退出码不是最终证据；文件系统 postcondition 才是。
失败后先诊断：

- target 是否 exact/contained；
- reparse 状态；
- read-only/system 属性；
- ACL 是否允许当前用户删除；
- 是否有进程持有 handle；
- 命令是否在可控 timeout 内返回。

未确定占用者时保持 `BLOCKED`，不要把 ignored 目录存在误报为 Git 污染。

## Python 测试环境

在执行可选格式或重依赖测试前：

1. 从项目 `pyproject.toml`、lockfile 和测试邻接代码确定权威环境；
2. 记录实际 `sys.executable`、Python 版本和 venv；
3. 对目标模块做 import capability preflight；
4. 缺模块时标记 `ENVIRONMENT_FAIL`，不得标记产品测试失败；
5. 切换到项目权威解释器后重新运行同一测试节点；
6. 报告第一次环境型失败和第二次产品测试结果，两者不得互相覆盖。

## Git 与 squash merge 证据

禁止使用没有对象的“本地与云端一致”。必须分别报告：

```text
current HEAD/tree
current upstream ref/SHA
origin/main SHA/tree
HEAD...origin/main current_only/main_only
feature PR state/headRefOid
PR mergeCommit
CI headSha/conclusion/url
```

普通 merge 可以补充祖先关系，但 squash merge 会生成新的 main commit。判断
squash merge 应使用：

1. PR `state=MERGED`；
2. PR `mergeCommit`；
3. 该 mergeCommit 位于 main；
4. required CI 的 `headSha` 等于 mergeCommit。

不能因为 PR head SHA 不是 main 祖先就宣布“未合并”。

## Markdown 路径转译

相对链接必须从当前文档的父目录解析：

```text
<project>/docs/truth/handoff.md + ../taskpacks/task.md
→ <project>/docs/taskpacks/task.md
```

不能从 shell cwd 或仓库根解析。对已知 handoff/status 文件使用 preflight 的
`--markdown` 参数，修改后确认所有目标存在；不要全仓机械替换相似字符串。

## 状态语义

每项能力分别标记：

| 层 | 仅在何时成立 |
|---|---|
| `PLANNED` | 蓝图或 TaskPack 已形成 |
| `BRANCH_PUBLISHED` | 精确 branch SHA 已上传并回读 |
| `IMPLEMENTED_LOCAL` | 代码/文档已在明确 tree 中实现 |
| `TESTED_LOCAL` | 目标测试在该 tree 通过 |
| `CI_VERIFIED_EXACT_SHA` | required CI 在同一 SHA 通过 |
| `MERGED_MAIN` | main 包含明确 merge SHA/tree |
| `INSTALLED_RUNTIME_VERIFIED` | 安装态或 live runtime 已重启并回读 |

高层不由低层自动推出。任务包发布不等于代码实现；本地测试不等于 CI；merge
不等于安装态运行。

## Codex 性能执行规则

性能诊断必须遵循 `codex-performance-diagnosis.md`：

- 分开 process/context startup、model turn、approval、tool、test 和 CI wait；
- 相同目录、模型、prompt、warmup 和样本数做 matched A/B；
- 至少报告 median 与离散度，单样本只作探索；
- timeout 是等待上限，不是实际耗时；
- WebSocket capability、trust、sandbox、approval 字段名不是性能证据；
- 默认保留官方 Windows sandbox；
- 一个 TaskPack 使用一个持续 writer；
- 独立读取/搜索/状态检查批量执行；
- 开发中跑定向测试，最终 aggregate tree 跑一次完整 gate。

## 最小验收

```text
private memory/auth/session access: NOT ATTEMPTED
execution preflight: PASS or named blocker
runtime cleanup: REMOVED/ABSENT or BLOCKED_RUNTIME_CLEANUP
Markdown relative links: PASS
Python module preflight: PASS
local targeted tests: PASS/FAIL with exact interpreter
Git current/upstream/main: separately reported
PR merge and exact-SHA CI: separately reported
lifecycle layers: no promotion by implication
full gate: PASS or explicitly NOT EXECUTED by project risk policy
```
