# 12 — 项目瘦身 / 外溢追踪 / 运行时清理审计（2026-10-06）

授权：owner 指令「项目瘦身，追踪外溢数据，审计清理」，并对 Tier-2 逐项勾选。
所有数字用 `du -sm` 复核过；**第一遍用 Python 遍历得到的 1268 MiB 是虚高的**
（`.project-local` 内有 junction/硬链接被重复计数），下文一律采用 `du` 值。

## 一、体积构成（清理前）

| 层 | 实测 | 能否瘦身 |
|---|---|---|
| `.git`（3 packs / 16681 objects / garbage=0 / prune-packable=0） | **223.8 MiB** | ❌ 唯一手段是重写历史，Authority §17 禁止；`git gc` 无收益 |
| tracked 工作树（2907 文件） | **44.7 MiB** | 受门保护；`pack_mib=216.0 / hard_budget_mib=256`，余量 ~40 MiB |
| `.venv/` | 207 MiB | 环境，非项目数据 |
| `node_modules/` | 61 MiB | `pnpm install` 可重建 |
| `.project-local/` | **903 MiB** | ✅ 本次主战场 |

## 二、已执行清理（合计回收 427 MiB；`.project-local` 903 → 476 MiB）

### Tier-1 纯可再生缓存（无需授权即删，零信息损失）
`runs/cache/npm`（npm `_cacache`/`_npx`/`_logs`）、`runs/cache/pnpm`、`runs/pycache`、
`runs/tmp`、`.pytest_cache`。
删前确认：tracked 代码零引用；浏览器 E2E 探针实际找的是
`task-runtime/playwright/npm-cache/_npx`（**未动**），故本地 E2E 不会退化为 skip。

### Tier-2（owner 逐项勾选）
| 项 | 回收 | 处置 |
|---|---|---|
| `task-artifacts/` 未被账本绑定的部分 | 144.9 MiB / 2399 文件 | 删；**保留** 2 个仍被绑定的文件（`W00-EVIDENCE-SCAN.json`、`PROJECT-SURVEY-2026-09-27.md`）与前次 spill 审计件（`spill-cleanup-report.md`、`spill-audit-cd-20260916.md`、两个 tier 脚本） |
| `b10-1to1-handoff/`（从 `UI套件` 入站拷贝） | 65.8 MiB / 1013 文件 | 删 |
| `task-runtime/` 临时根 | ~23 MiB | 删；**保留** `playwright`（50.7 MiB，E2E 探针依赖）与 `lint-tools`（25.7 MiB，前次审计标 ACTIVE） |
| `worktrees/github-delivery-repair` | 47 MiB | `git worktree remove`；该分支已核实 SUPERSEDED，**远端分支未删**（owner 项） |

### 删前归档（可追溯性）
`runtime-cleanup-inventory-20261006.jsonl.gz`（本目录，119 KB）：
**3412 行**，每行 `{分组, 路径, 字节, sha256, mtime}`；
明文 sha256 = `579e649cd032979729d7ab2b245a1536f8a48875a2029848ef463fd855b32d7d`。
即被删内容虽不在盘上，其身份与大小仍可被任何一份备份逐条验证。

## 三、与前次（2026-09-16）保留规则的两处冲突 —— 如实记录

前次报告 `.project-local/task-artifacts/spill-cleanup-report.md` 定过 RETAIN/KEEP 规则，
本次两条与它相冲：

1. **`task-runtime/service` 前次标 `RUNTIME_STATE, RETAIN`**。实测该路径由测试自建：
   `test_service_cli.py:39`、`test_runtime_explicit_project.py:35` 都在**临时项目根内**
   创建 `task-runtime/service/state.db`。删除后立刻跑这两个模块：
   `Ran 7 tests ... OK`，且 `.project-local/task-runtime` 自行回长（77→79 MiB）。
   结论：可自我重建，前次的 RETAIN 判断对该路径过于保守。
2. **`task-artifacts` 前次标 `KEEP_EVIDENCE`**。本次只删**已无任何账本绑定**的部分，
   保留 2 个绑定件与前次审计本体；且删前落盘 3412 行清单。
   注意：前次审计时该目录 622 MiB，本次仅 144.9 MiB —— 中间已有人清过，
   而账本里 **254 条前继产物引用因此变成死链**（见下节）。

## 四、外溢追踪结论

1. **本会话零外溢**：四个声明外置根 + `UI套件`/`Record`/`Design Projects` 最近 3 天
   DESIGN-LAB 写入计数为 **0**（`OS External Configuration` 的 1115 个新文件是
   Rust cargo 缓存，属另一条工作线；`Design Projects` 166 个亦非本项目）。
2. `.hermes/` **为空** ✓（AGENTS 声明它不是活跃写入根，实测一致）。
3. **历史外溢两处（真问题）**：
   - `Design External Configuration/toolchains/comfyui/.../ComfyUI/output/nebula_*`
     （2026-08-27）：设计生成物落在**第三方工具链自己的 output 目录**，
     仓内 `docs/projects/nebula-tech-culture-wall/assets/*.png` 是其副本，
     两处无读回链，生成现场不可复现。
   - `UI套件` → `.project-local/b10-1to1-handoff/` 入站拷贝（本次已删，清单留档）：
     跨项目素材未走 §12 的 `ABSORBED/REFERENCE_ONLY/REJECTED/DEFERRED` 归类。
4. **代码内硬编码机器路径，违反「机器路径唯一入口 `.project/paths.json`」**：
   `packages/capabilities/reconstruction/providers/registry.py:40-41`、
   `packages/capabilities/reconstruction/pipeline.py:52`（resvg.exe）、
   `design-lab/tests/host_fixtures/prepare_real_poster.py:38`（vtracer.exe）。
   均为只读发现路径、Linux 上落空，但绕过了单一入口，换机即漂移。
5. `D:\tmp\oh/` 等前次报告点名的非本项目归属目录，本次仍未触碰（不在授权范围）。

## 五、证据可读回性（新门首跑读数）

`design-lab/scripts/verify_evidence_artifact_presence.py`：

```
DRIFTED r5-workbench-strict-ts-build-truth-20260927 -> apps/workbench/build/main.js (HASH_MOVED_SINCE_OBSERVATION)
RUNTIME-MISSING r5-comfy-http-model-free-live-20260909 -> .project-local/task-artifacts/comfy-http-live-…/result.json
EVIDENCE_ARTIFACTS=WARN tracked_broken=0 tracked_drifted=1 runtime_present=33 runtime_missing=1
```

- 门刻意分三级：**tracked 缺失 = FAIL**（证明被销毁）；
  **tracked 哈希漂移 = WARN**（该"产物"其实是可变源文件，一改就衰减，
  若判红会让门永久红）；**runtime 缺失 = WARN**（`.project-local` 本就 gitignored，
  clean checkout 上必然全缺）。`--strict-runtime` 供本地升级判红。
- 已接入 CI `python-gate`（WARN 语义，不会假红也不会假绿）。
- 4 项测试钉住三级语义，其中一项**断言当前那条已知漂移记录**，
  把"用可变源文件当产物"这个反模式固定成可见事实而不是暗伤。
- 结构性结论：**前继 R3 账本 254 条产物引用已全部死链**，
  当前 R5 也有 1 条不可读回。把 E2/E3 现场产物写在 gitignored 运行根里，
  等于承诺了不可兑现的证明。本次截图那批改为**入仓提交**（PNG + sidecar + manifest）
  就是正确形态；后续任何要长期主张的证据都应走这条路。

## 六、剩余可回收量（未动，需再授权）

| 项 | 实测 | 为什么没动 |
|---|---|---|
| `.project-local/projects/` | **342 MiB / 12 项目**（含 6 份 `native-plans/*/checkpoint.psd`） | 真实项目状态与前次 `UNPROVEN, 不动`；任务书 C7.4 明写不得删用户项目 |
| `.project-local/cache/vendor/` | 39 MiB | 需先确认是否被 research/quarantine 引用 |
| `task-runtime/playwright` + `lint-tools` | 76 MiB | 删了本地浏览器 E2E 会退化为 skip、lint 门需重下；CI 自带 |
| `.git` 223.8 MiB | — | 只能靠重写历史，禁止 |
