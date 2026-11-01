# MAIN Merge Readiness — `codex/deepseek-authority-r1` → `main`

TaskPack: `DL-TP-20260917-BRANCH-CONVERGENCE-R1` (§18 V1–V10, §28, §30, §45)
Candidate SHA: `cbc0463e9e6a0faa2bcd61b9a4aee3aa4808dea8` (codex/deepseek-authority-r1)
Main SHA:      `c4dccd58331bc4561eb89265283d924b7630d113` (main) — pure ancestor of candidate (main+118)

> 措辞遵循任务包 §30：本报告只使用 PASS / FAIL / BLOCKED / DEFERRED / NOT_VERIFIED。
> 本报告**不**使用 "MAIN ready / release ready / 零 residual / E3 verified / 全分支已合并"。
> 结论是分项的，整体状态 = **PARTIALLY READY**（3 项 B12 前置未满足，见 "Overall verdict"）。

## Overall verdict

状态 = **PARTIALLY READY / NOT_YET_MERGED**

- 结构性 + 权威链 + acceptance-truth：**PASS**（可进入 PR 的结构面已就绪）
- 但 §18 "same candidate SHA all structural gates pass + Python full suite + packaging smoke + actual HTTP preflight" 有 3 项未在同一 SHA 上闭合：
  1. **V5 worktree clean = FAIL**（当前 dirty=12，需先把 B10 修复 commit 成 candidate SHA 才能做 "same-SHA" 全量验证；`commit` 属 manifest `requiresExplicitAuthorization`）
  2. **V6 asset rights/expiry = FAIL (BLOCKED)**（C-03：4 个 H3 证据 sidecar 已于 2026-09-16 过期，需 Codex/Human rights 重裁，任务包 §8 禁止我改 expiresAt / 禁 gate / 删证据）
  3. **V1 / V8 / V9 = NOT_VERIFIED**（本机无 uv、无 installed-wheel、无真实 HTTP endpoint 可达，非产品失败，属 ENVIRONMENT 限制）

按任务包 §40：以上均为"只读/报告/测试"范畴可继续；但 B12 的 "same-SHA 全量验证" 与 B15 "PR → main" 的 destructive step 需要**用户授权**（commit B10 形成 candidate SHA + C-03 rights 裁决）。

## B10 CI blocker 修复（已在 candidate 工作区落地，未 commit）

| 项 | 内容 | 验收证据 | 状态 |
|---|---|---|---|
| C-01 | re-export `reconstruction.evidence.RenderError` + `design_lab.runtime.job_store.request_hash` | `test_reconstruction_evidence` RenderError 用例 1/1 PASS；`test_runtime_attempt_safety` 23/23 PASS | **PASS (targeted)** |
| C-02 | Authority Gate CLI `--modules` 协议对齐 + `bound_run` fail-safe（空 stdout 不再 IndexError、保留 stderr/returncode/timeout） | 原失败调用形态 `--modules a b` 现 29/29 OK；门链无 aggregator traceback | **PASS** |
| C-04 | authority-chain projection 漂移（3 个 docs/taskpacks 分类入 REFERENCE） | `deepseek_authority_chain.py` regenerate + `--check` PASS（41 entries） | **PASS** |
| WAVE-C4 | `worktree_digest.py` 切 NUL-delimited v2 `-z`（原始 UTF-8 路径，去 `unicode_escape` 有损解析） | 全谱验证 M/D/R/U/non-ASCII + digest 重算稳定 + 门链 7/7 | **PASS** |
| C-03 | H3 资产时间例外过期 | `verify_asset_governance.py` = `ASSET_GOVERNANCE=FAIL`（4 sidecar 过期 2026-09-16） | **BLOCKED**（需 rights 重裁） |

改动集（5 tracked 文件）：`packages/capabilities/reconstruction/evidence.py`、`src/design_lab/runtime/job_store.py`、`scripts/run_bound_test_suite.py`、`scripts/verify_authority_gates.py`、`src/design_lab/governance/worktree_digest.py`。

## V1–V10 same-SHA 验证矩阵（§18）

| V | 项目 | verdict | 证据 / 备注 |
|---|---|---|---|
| V1 | Install (`uv sync --locked` / canonical install path) | **NOT_VERIFIED** | 本机无 uv；非产品失败，ENVIRONMENT 限制 |
| V2 | Structural verifiers all PASS | **PASS** | 门链 7/7：authority-ledger / authority-chain / source-lock / contract-graph / language-boundary / test-gate / zero-spill |
| V3 | Python full suite (run/skipped/failures/errors/duration) | **DEFERRED (full) / PASS (targeted)** | targeted：C-01 两个模块 24 用例全 PASS；full 1392 suite 与 3-order stress 未在本机跑（test-gate 走 history 一致性分支） |
| V4 | Critical order tests (3-order stress, 与 full suite 分开记录) | **DEFERRED** | 未在本机跑 3-order；门链 test-gate 记录 order/repetition 一致性 PASS |
| V5 | Worktree clean（generated artifacts 不污染） | **FAIL** | `verify_clean_tree.py` = UNATTRIBUTED dirty=12（5 B10 修复 + 5 再生报告 + 2 新交付物）；需 commit B10 后 clean |
| V6 | Asset rights / license / expiry / retention all current | **FAIL → BLOCKED** | C-03：4 个 H3 证据 sidecar 过期（comfyui/minimax-h3 各 prod mp4 + test webp），需 rights 重裁 |
| V7 | Authority chain / taskpack classification / ledger current | **PASS** | authority-chain `--check` PASS（41 entries，含 3 REFERENCE taskpacks）；ledger 58 tasks PASS |
| V8 | Packaging installed-wheel smoke | **NOT_VERIFIED** | 需 installed wheel 在 checkout 外跑 smoke，未执行 |
| V9 | HTTP actual endpoint (`/api/task-preflight`) | **NOT_VERIFIED** | 需真实 endpoint 可达，未执行（WAVE-C8 范围） |
| V10 | Branch residual = 0（UXP / R4 / directory-convergence） | **PASS** | UXP=SUPERSEDED(0 residual)；R4=PARTIAL_ABSORBED(22/22 classified by domain)；dir=SUPERSEDED(31/31 by intent)；唯一残留 C-03 已 explicitly deferred（owner=Codex/Human rights） |

## B11 acceptance-truth（§45 "current acceptance truth fixed"）

- `verify_no_overclaim.py` = **PASS**（claims=4, unsupported=0, qualified=4）
- `verify_evidence_levels.py` = **PASS**（overclaims=0, historical_evidence_kept=4, declared_non_claims=3）
- 两份审计报告已刷新（原 09-13 陈旧 `subject_sha=""` 已重生成）
- 无 "phantom KPI"、无 "历史 E3 冒充当前 E3"、无 "本地跟踪引用冒充 CI/发布"

## B14 之前必须满足（§20 MAIN PR 创建条件）

Coherent convergence state = 当前候选 + Branch Residual + CI Fix + Authority Fix 四者齐备。当前：
- CI Fix（C-01/02/04 + WAVE-C4）：**已落地（candidate 工作区）**
- Branch Residual（§9/§10/§11 三条高风险）：**已判定**（UXP SUPERSEDED / R4 PARTIAL_ABSORBED / dir SUPERSEDED）
- Authority Fix（C-04）：**已落地**
- 未满足：V5 clean（需 commit B10）、V6 rights（需 C-03 重裁）

因此**不得**创建 PR / merge / delete / release（§12/§20/§31/§40 destructive step 需用户授权）。

## 待授权项（fail-closed，§40 STOP）

1. **commit B10 修复 → 形成 new candidate SHA**（manifest `requiresExplicitAuthorization`；提交后 B12 "same SHA" 才能 V5 clean + V3 full）
2. **C-03 H3 资产 rights 重裁**（renew / archive / quarantine / remove from current acceptance —— Codex/Human 决策）
3. **B15 PR → main / B17 delete branches**（§12/§24/§31 8 项 gate 全满足 + 用户授权后）

## 交付物清单（§28）

| 文件 | 状态 |
|---|---|
| `reports/current/BRANCH-CONVERGENCE-SNAPSHOT.json` | GENERATED (B1) |
| `reports/current/BRANCH-SEMANTIC-DISPOSITION.json` | GENERATED (B2, 30/30) |
| `reports/current/BRANCH-UNIQUE-ANALYSIS.json` | GENERATED (B2) |
| `reports/current/BRANCH-RESIDUAL-MATRIX.json` | GENERATED (B13, §PHASE C) |
| `reports/current/BRANCH-CLEANUP-CANDIDATES.json` | GENERATED (B13, §12/§24/§31) |
| `reports/current/BRANCH-CONVERGENCE-VALIDATION.json` | GENERATED (B13, V1–V10 verdicts) |
| `reports/current/MAIN-MERGE-READINESS.md` | THIS FILE |
| `reports/current/POST-MERGE-MAIN-VALIDATION.json` | DEFERRED (post-merge, §23) |
| `reports/current/POST-MERGE-BRANCH-CLEANUP.json` | DEFERRED (post-cleanup, §24) |
