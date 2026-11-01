# External Artifact Overflow — Cleanup & Root-Cause Fix（2026-08-12）

> 追总 D:\All projects 各项目（CLO / WORK-LAB / Open Design）产生的数据溢出；
> 已清理 493.4MB 可再生溢出，已实施三层防复发修复。本文为 tracked 归档（云端可见），
> 详细审计与恢复清单见 `.hermes/task-artifacts/external-recovery-20260812/HANDOFF.md`（ignored，本机保留）。

## 1. 发现与清理（12 项 → 删 9 项 / 保留 2 项）

| 类别 | 路径 | 大小 | 处置 |
|---|---|---|---|
| CLO pytest 溢出 | `D:\clo-v050-tests` / `D:\clo-pytest-product` / `D:\clo-pytest-full` | 各 156.7MB | ✅ 删（quiescent ≥89h，可再生） |
| CLO pytest/release 溢出 | `D:\clo-pytest` / `D:\clo-release-tests` | 各 6.5MB | ✅ 删 |
| 空残留 | `D:\clo-rc-review-pQqjRU` | 0 | ✅ 删 |
| tempfile 残留 | `D:\a` | ~0 | ✅ 删 |
| CLO smoke temp 镜像 | `C:\c`（Users/ALEX/AppData/Temp/a0-frozen-…） | 8.0MB | ✅ 删 |
| 临时残留 | `C:\tmp` | 2.4MB | ✅ 删 |
| **CLO smoke 现场+备份** | `D:\tmp`（mfx-browser-smoke：cognitive_os.sqlite + pre_migration 恢复备份 + 锁 08-12 活跃；master_wrapped.md=OP 任务书副本） | 24.4MB | 🔴 保留 |
| **Workflow-assistance 旧 checkout** | `C:\wa-review-short-704`（remote=DTALEX66/Workflow-assistance，+1874 行 WIP） | 67.3MB | 🔴 保留（补丁已存档） |

回收合计 **493.4MB**；删除前全部 quiescence 复查（≥8h 无写入），删除后逐项复扫确认。

## 2. 根因

- pytest 溢出：**非 repo 脚本**（CLO / OS-config / WORK-LAB 三仓 grep 零引用）——agent/CI 直接
  `--basetemp=D:\clo-*` 的产物，绕过了项目边界。
- `C:\wa-review-short-704`：2026-07-30 旧 review 工作流在 C:\ 根建 checkout（已废弃）。
- `D:\tmp`：CLO desktop smoke 运行时映射未锁定项目内。

## 3. 防复发修复（三层）

### ① Hermes terminal gate（全局硬约束）
- `config.yaml` hooks → `hermes-project-terminal-guard.py`（matcher=terminal，08-06 批准，医生健康）
- 每个 terminal 调用强制 Git-project workdir + 单 wrapper 通道 → 阻断裸 `--basetemp` 类命令。
- 无需重启（当前进程已注册）。

### ② CLO AGENTS.md 边界规则（Codex 文档级）
新增：测试/CI 临时根必须落 `<repo>/.hermes/task-runtime/tmp/`；禁止 basetemp/TMPDIR 指向仓库外
（历史溢出清单：`D:\clo-*`、`D:\tmp`、`C:\tmp`、`C:\c`、单字母根）；测试经 `scripts/ci/run_tests.sh`。

### ③ CLO 项目内测试入口（`scripts/ci/run_tests.sh`，已验证）
- basetemp 固定 `.hermes/task-runtime/tmp/pytest-<ts>/`；TMP/TEMP/TMPDIR/PYTHONPYCACHEPREFIX 全部项目内
- 支持 `--full`（tests + knowledge_base/tests）与参数透传
- 实测修复两坑：MSYS `/d/...` 路径（`pwd -W`）→ Windows 程序失效；bash 前导 `--` 透传 → pytest 误判文件路径

验证：`run_tests.sh` 收集 186 / 1077 tests（basetemp 项目内）· 外部根复扫无新溢出 ✅

## 4. 归档（本机 `.hermes/task-artifacts/external-recovery-20260812/`，ignored 不 push）

```text
HANDOFF.md                                 审计/恢复清单（删除证据、留存原因、根因、防复发）
wa-review-short-704-WIP-20260730.patch     Workflow-assistance WIP 补丁（121KB，吸收判定前不删 checkout）
wa-review-short-704-HEAD.txt               checkout 身份
clo-boundary-fix-20260812.patch            CLO AGENTS.md + run_tests.sh 改动补丁（CLO 仓库提交待用户/并行会话）
```

## 5. 待办

- [ ] `C:\wa-review-short-704`：补丁吸收判定后删除（67MB）
- [ ] `D:\tmp`：CLO smoke 确认停止后拆分处理（备份保留）
- [ ] CLO 仓库提交 AGENTS.md 规则 + run_tests.sh（当前分支有并行会话改动，未擅自提交）
