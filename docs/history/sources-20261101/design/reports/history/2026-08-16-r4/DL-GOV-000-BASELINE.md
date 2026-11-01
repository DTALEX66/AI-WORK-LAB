# DL-GOV-000 — 云端与本地基线冻结（R4）

- 任务包：DESIGN-LAB Governance Closure & Anti-Drift R4
- 审计基线：`9e7f433ada62f7be42c41ea935a1847a64fb2635`（2026-08-15）
- 采集时间：2026-08-16T01:07:01.399Z（本地 DSH 会话）
- 数据源：git（本地）+ GitHub REST API 实时回读（run 31896923033）

## 状态总览

| 项 | 值 |
|---|---|
| 当前分支 | `main` |
| HEAD commit | `b9f69acd13f589d80edec321bf7e9e8f2eaa3e9d` |
| HEAD tree | `bc4f7fef1761c93dc0e0c787cb4447f23974fbd4` |
| origin/main（本地 ref） | `b9f69acd13f589d80edec321bf7e9e8f2eaa3e9d` |
| origin/main（实时回读） | `b9f69acd13f589d80edec321bf7e9e8f2eaa3e9d` |
| 双端一致 | ✅ 是 |
| worktree | clean (## main...origin/main, 0 ahead / 0 behind) |
| tracked 文件数 | 2902 |
| 仓库 pack 大小 | 198.19 MiB |
| >5 MiB 文件 | 无 |
| 开放 PR | 0 |
| 开放 Issue | 0 |
| Actions Run 总数 | 445 |

## 当前 Actions Run（HEAD 精确 SHA）

| SHA | Workflow | 结论 | Run ID |
|---|---|---|---|
| b9f69acd13f589d80edec321bf7e9e8f2eaa3e9d | Canonical Verify (V4) | **failure** | 31896923033 |
| 35b5f9af0a6624ddc4e470975ab96746a4a395c2 | Canonical Verify (V4) | failure | 31896444357 |
| 9e7f433ada62f7be42c41ea935a1847a64fb2635 | Canonical Verify (V4) | success | 31852374631 |

> ⚠️ **当前 HEAD CI 失败（诚实记录）**：HEAD b9f69ac 的 Canonical Verify (V4) 为 failure。失败步骤：`DESIGN-LAB unified verify` → `verify_open_design_assistance.py` 20 项失败（7 个 cctv-*/texture-* 视觉包陈旧引用 + 13 个 script compiles 检查）。本地已复现（`verify_design_lab.py` → VERIFY_DESIGN_LAB=FAIL failed=1）。此为 R4 阶段 F 与回归测试的修复对象，不作为通过证据。

## 远端分支（实时 ls-remote，21 个 head）

- `docs/bundle-readme`
- `docs/core-readme`
- `docs/lessons-ledger`
- `docs/oda4-0803-audit`
- `docs/oda4-1101-gate`
- `docs/oda4-1104-report`
- `docs/roadmap-sync`
- `feat/adapter-contracts-e0`
- `feat/minimax-h3-e3`
- `feat/oda4-0118-1005-0807`
- `feat/score-sheet-template`
- `fix/aggregate-14`
- `fix/codex-review-r1`
- `fix/quarantine-evidence`
- `fix/registry-categories`
- `fix/verify-all-skins`
- `fix/verify-all-toolchain`
- `main`
- `migration/work-lab-minigame-cutover-20260807`
- `test/evidence-helpers`
- `test/jury-preflight`

## 本地分支

- `main`
- `docs/lessons-ledger`
- `docs/oda4-0803-audit`
- `docs/oda4-1101-gate`
- `docs/oda4-1104-report`
- `feat/comfyui-e3`
- `feat/minimax-h3-e3`
- `feat/oda4-0118-1005-0807`
- `fix/codex-review-r1`
- `fix/registry-categories`
- `fix/registry-quarantine-sync`

## 备注

- 当前 HEAD 的 Canonical Verify (V4) CI 为 failure：verify_open_design_assistance.py 报告 20 项失败（7 个 cctv-*/texture-* 视觉包陈旧引用 + 13 个 script compiles 检查），为既有缺陷，R4 阶段 F 修复。
- 本地复现：python design-lab/scripts/verify_design_lab.py → VERIFY_DESIGN_LAB=FAIL failed=1 (verify_open_design_assistance.py)。
- GitHub 云端读取方式：git -c http.sslBackend=openssl ls-remote（schannel TLS 凭据缺失）+ GitHub REST API via python urllib（relaxed TLS）。
- 审计基线 9e7f433 为任务包给定基线；当前 HEAD 高于基线 3 个提交（1382e2c → 35b5f9a → b9f69ac）。

## 采集方法

- git：HEAD/tree/origin/main SHA、status、tracked 计数、pack 大小、`git -c http.sslBackend=openssl ls-remote --heads origin`
- GitHub API：`repos/DTALEX66/DESIGN-LAB`、`actions/runs`、`pulls`、`issues`（python urllib，relaxed TLS；schannel 凭据缺失，git 默认后端不可用）
