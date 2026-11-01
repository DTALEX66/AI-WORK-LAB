# INTEGRATED-TASKPACK-20260916 · NF-03 外溢定点收尾回执

- 生成：2026-09-16 · 执行者：Hermes
- 范围：仅 WORK-LAB **本轮**新产生的缓存/构建/临时/证据的定点核验；E 盘、其他项目、官方软件原生数据根（`~/.hermes`/`~/.dsh`/`~/.codex`、共享模型库）一律按原授权，**不扫描、不迁移、不删除**。
- 边界依据：`.project/governance/project-data-boundary.json`（runtimeRoot=`.project-local/runs`，taskArtifacts=`.project-local/artifacts`，`E:/` forbidden/deny）+ `.project/governance/external-libraries-index.json`（共享库只登记链接，不传内容）。

## 1. 本轮新增产物全部在批准边界内（只读核验）

| 产物 | 位置 | 边界 | 状态 |
|---|---|---|---|
| 隔离 gate venv `gate-venv/` | `.project-local/runs/gate-venv` | runtimeRoot ✅ | 被 `.gitignore` 的 `.project-local/` 覆盖，不入 Git；**未**用 `--require-hashes`/未碰 Hermes 运行时 venv 与全局 Python |
| CI 原始日志 `ci-34993528858-workflow-assistance.log` | `.project-local/runs/` | runtimeRoot ✅ | NF-02 证据 |
| 全量 pytest 结果 `pytest-full-wa.txt` | `.project-local/runs/` | runtimeRoot ✅ | 1255 全绿回执 |
| 任务包解包 `integrated-taskpack-20260916/` | `.project-local/runs/` | runtimeRoot ✅ | ZIP 6/6 SHA256SUMS OK |
| `p0-new-sha.txt` / `NF-00-baseline-receipt-20260916.json` | `.project-local/runs/` | runtimeRoot ✅ | P0 回执（不入 Git） |

核验结果：
- 上述全部位于 `runtimeRoot`，**无一经 git 跟踪区**（`git status` 干净，`.project-local/` 在 `.gitignore`）。
- `gate-venv` 无越界副本（`C:\Users\ALEX\gate-venv`、`Desktop\gate-venv` 均不存在）。
- 生成件 `CURRENT_STATE.json/.md`：本地 dirty 仅时间戳 churn（source/content digest 未变，`volatile` 归一），已 `git checkout` 还原；`generate_current_state.py --check-current` 本地 PASS，P0 改动 30 个 `CANONICAL_FILES` 源集外，不喂 digest、不失配。

## 2. 工具链发现（不重新下载/错装）
- 本轮 gate 复现所需依赖经 `packages/client-neutral-core/requirements.lock` 装入**项目内**隔离 venv（`.project-local/runs/gate-venv`），来源是仓库既有 lock，非新造常驻发现服务、未安装到 C 盘或全局。
- 共享库（ollama/whisper/comfyui-h3 等）按 `external-libraries-index.json` 仍指向 `D:\All projects\Model library` 等原生数据根，**未搬迁入仓库**（NF-03 do_not ③：不搬坏官方软件原生安装/数据根）。

## 3. 处置回执（限定路径）
- 归属/校验/无活跃占用/授权删除四要素：本轮无需要删除的外溢（全部产物应保留于 runtimeRoot 作为证据，且均 gitignore、可随时清理而不触及项目源码）。
- 未授权项清楚保留：E 盘、其他项目、原生 `.hermes`/`.dsh`/`.codex` 数据根、共享模型库——**未扫描、未迁移、未删除**。

## 验收核对
- 受影响构建/测试只写批准位置（runtimeRoot）✅；E 盘拒绝测试仍有效（未触碰）✅
- 入口能发现已存在工具、不重复下载/错装 ✅（复用 requirements.lock）
- 外溢删除有归属/校验/无占用/授权；未授权项保留 ✅

## 剩余与阻塞
- 无新增阻塞。NF-03 的"工具链当前实际位置未由云端实测"一项：本轮在**本地**项目内核验通过；若需云端/精确 SHA 的工具链指纹复核，属额外授权，不在本回执范围。
- 下一张可独立继续的卡：**NF-04**（可解释的轻量配置变更闭环）或 **NF-05**（各客户端原生接口最小适配）。
