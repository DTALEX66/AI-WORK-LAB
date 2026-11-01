# WORK-LAB 蓝图同步审计快照

由 `python scripts/ci/record_blueprint_audit_snapshot.py --write` 生成；所有标识、远端 SHA、摘要与退出码均为运行时观察值，不转录自旧报告。本文件不含自身摘要。

## 现场身份

```json
{
  "observedAt": "2026-10-07T01:55:14+0800",
  "remote": "git@github.com:DTALEX66/WORK-LAB.git",
  "branch": "task-decomposition/atlas-gap-archive-20261001",
  "localHead": "1d3b20d03ac2fa5c2adb92b95ffdf878336f169d",
  "baseSha": "cd4daa83e107afab8438c0e85f63a10e75314d5a",
  "dirtyFiles": [
    ".project/governance/generated/CURRENT_STATE.json",
    ".project/governance/generated/CURRENT_STATE.md",
    "apps/observer/parity-matrix-u03.md"
  ],
  "statusRecords": 4,
  "liveMainSha": "cd4daa83e107afab8438c0e85f63a10e75314d5a",
  "liveBranchSha": "1d3b20d03ac2fa5c2adb92b95ffdf878336f169d"
}
```

脏文件计数按 `git diff --name-only` 计算：git 状态列会把行尾过滤器改写报成modified，而 `git diff` 无内容差异，因此以 diff 为准（ERR-105 的同一机制）。`liveBranchSha` 为 `NOT-PUSHED` 时表示交付分支尚未同步到远端，不能声称双端完成。

## PR #162 读回

```json
{
  "baseRefName": "main",
  "headRefOid": "1d3b20d03ac2fa5c2adb92b95ffdf878336f169d",
  "mergeable": "MERGEABLE",
  "state": "OPEN",
  "url": "https://github.com/DTALEX66/WORK-LAB/pull/162"
}
```

更正记录：蓝图原文记载 PR #162 head 为 `6f323a318a9db1c3a3ed4429bab0d4eff129876c`；本次实时读回是其自身的观察值，两者不同则以上方读回为准，原文值保留为历史观察，不改写。原文记载的 `origin/main = cd4daa83…` 与本次读回一致。

## GitHub About（Git 外元数据）

```json
{
  "before": "Client-neutral AI-agent control plane: user global config overlay for Hermes/Codex/DSH/GitHub/Open Design/OpenHuman via one adapter contract (CC Switch observe-only). Modules: client-neutral-core (task/telemetry ledger, sidecar), services (orchestration/policy/receipts), read-only observer. Authority chain + exact-SHA CI gates.",
  "target": "Client-neutral workflow governance, control and delivery: portable rules, native client adapters, task coordination, permissions and evidence-based completion. Ongoing.",
  "readBackNow": "Client-neutral workflow governance, control and delivery: portable rules, native client adapters, task coordination, permissions and evidence-based completion. Ongoing.",
  "matchesTarget": true,
  "homepageUrl": "(empty — no site claimed)",
  "topicsChanged": false
}
```

About 不属于仓库内容，提交 README 不等于改过 About；此处单独记录 before → target → 现场读回。homepageUrl 与 topics 未改动（无真实站点依据，不编造）。

## exact-SHA CI（PR #162 checks，绑定推送后的 head）

```json
{
  "headSha": "1d3b20d03ac2fa5c2adb92b95ffdf878336f169d",
  "count": 21,
  "buckets": {
    "pending": 12,
    "pass": 9
  },
  "pendingOrFailing": [
    {
      "name": "wlr060-aggregate",
      "bucket": "pending"
    },
    {
      "name": "observer",
      "bucket": "pending"
    },
    {
      "name": "token-monitor",
      "bucket": "pending"
    },
    {
      "name": "workflow-assistance",
      "bucket": "pending"
    },
    {
      "name": "integration",
      "bucket": "pending"
    },
    {
      "name": "supply-chain-security",
      "bucket": "pending"
    },
    {
      "name": "observer",
      "bucket": "pending"
    },
    {
      "name": "token-monitor",
      "bucket": "pending"
    },
    {
      "name": "workflow-assistance",
      "bucket": "pending"
    },
    {
      "name": "supply-chain-security",
      "bucket": "pending"
    },
    {
      "name": "integration",
      "bucket": "pending"
    },
    {
      "name": "config-compiler",
      "bucket": "pending"
    }
  ]
}
```

本地通过不称为 CI 绿；CI 绿也不宣告产品发布或本机 full gate 通过。

## 输入与摘要

```json
{
  "blueprintDocx": {
    "path": "D:\\All projects\\Record\\02_WORK-LAB_完整项目描述与未来蓝图_20261006.docx",
    "exists": true,
    "sha256": "f3784a9950adce06e8d87015a0ecb39d1ed4fdb3b93d5ccd3c9b40398bea3440",
    "declaredInPrompt": "f3784a9950adce06e8d87015a0ecb39d1ed4fdb3b93d5ccd3c9b40398bea3440",
    "match": true
  },
  "executionPrompt": {
    "path": "D:\\All projects\\Record\\02_WORK-LAB_权威修复_双端描述同步_可审计执行提示词_20261006.txt",
    "exists": true,
    "sha256": "8d4a48185357aeadb99d9a2760a9ba05e6ab4fc744c0e3cb48a12904cf565247",
    "declaredInPrompt": null
  }
}
```

## 在册主张现场读回

下面每个字段都从拥有它的文件里现场解析（U19 状态取唯一 open register 的状态列，台账状态取 `error-ledger.json` 的 `status_after`，候选池覆盖取注册表与 §16 行键的集合差，被目测的产物按其构建期凭据重算），不是从上一版报告转录。缺口清单是静态文字，会过期，所以可核验的部分一律改读真文件。

```json
{
  "u19RegisterStatus": "PASS (owner-observed desktop surface 2026-10-07)",
  "ledgerStatusAfter": {
    "ERR-103": "PASS",
    "ERR-104": "PASS",
    "ERR-105": "PASS",
    "ERR-106": "PASS",
    "ERR-107": "FAIL",
    "ERR-110": "PASS",
    "ERR-111": "PASS"
  },
  "ledgerEntries": 117,
  "candidatePool": {
    "candidates": 21,
    "sourceRows": 19,
    "claimedRows": 19,
    "unclaimed": [],
    "claimsToUnknownRow": []
  },
  "observedArtifact": {
    "schema": "work-lab/artifact-input-receipt/v1",
    "inputsRecorded": 12,
    "gitHeadAtBuild": "307d90b",
    "exeSha256Prefix": "6f73c14eb542f1a7",
    "bytesNowOnDisk": 9850368,
    "binaryMatchesReceiptOnDisk": true,
    "inputDriftSinceBuild": []
  }
}
```

## 检查命令与退出码（本次运行）

| 命令 | 退出码 | 末行结果 |
|---|---|---|
| `scripts/ci/verify_project_authority_reference.py` | 0 | AUTHORITY_REFERENCE_PASS top=WORK-LAB-AUTHORITY.md current=WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918 register=OPEN-TASK-REGISTER.md |
| `scripts/ci/verify_error_ledger.py` | 0 | ERROR_LEDGER_PASS entries=117 classifications=13 raw_sensitive_data=false counts_consistent=true |
| `scripts/ci/verify_blueprint_coverage.py` | 0 | BLUEPRINT_COVERAGE_PASS rows=87 kinds={'chapter': 19, 'appendix': 1, 'closed-loop-task': 9, 'owner-default': 5, 'input-source': 11, 'atlas-gap': 20, 'register-row': 22} status_vocabulary=reused dispositions=owner_prompt_ |
| `scripts/ci/verify_future_candidate_registry.py` | 0 | FUTURE_CANDIDATE_REGISTRY_PASS candidates=21 blueprint_rows=19 claimed_rows=19 |
| `scripts/ci/verify_project_data_boundary.py` | 0 | PROJECT_DATA_BOUNDARY_PASS runtime=.project-local/runs evidence=.project-local/artifacts |
| `scripts/ci/verify_model_registry_integrity.py` | 0 | MODEL_REGISTRY_INTEGRITY_PASS providers=9 models=10 runtimes=3 processLibraries=2 externalAssets=0 served_bindings=0 |
| `scripts/ci/failfast_group.py --group observer-web-contracts` | 0 | FAILFAST_GROUP_PASS group=observer-web-contracts commands=10 all_exit_0 |
| `scripts/ci/failfast_group.py --group observer-python-skeleton` | 0 | OK |

## 产物摘要

| 路径 | 字节 | SHA-256 |
|---|---|---|
| `docs/future/WORK-LAB-BLUEPRINT-20261006.md` | 21789 | `1e647ecd09ce4ac7f062884a04e43412bfcde5bcd5bdba3f91b3b8e610c9abd3` |
| `docs/future/WORK-LAB-BLUEPRINT-COVERAGE.md` | 35759 | `ba729d9d73f6a33406bb471e25f2aa838d1ab8c3234513309bec562bd5613d18` |
| `.project/governance/blueprint-coverage.json` | 31821 | `31bc834a266edbcd181e23d24705e1b61fed953d6e145a46a19b1a03efee5a08` |
| `.project/governance/future-candidate-registry.json` | 23479 | `627a8cb389c77aac4ea195ee04d20647370bce8f31254328bbe3f5dad8d9927e` |
| `scripts/ci/verify_blueprint_coverage.py` | 13822 | `9ded1cd312df28866bd0f5915cf8e1efde120b7725b70463822bbfb2a34ee8f4` |
| `scripts/ci/verify_future_candidate_registry.py` | 7974 | `1220c5d97438975672df3545190fa3365652f18791d1561e303b5cb2224397ba` |
| `apps/observer/scripts/write_artifact_receipt.py` | 6389 | `807f5102eeb35e0b8df1e3b85c5f37067487a0c53880b20d42d637531bea364f` |
| `apps/observer/scripts/u19_webview_e2e.py` | 57122 | `a922e0cca20400a5786b2cddf667633b18b52087d8ba2fbf12d1c8e4a45c3ab0` |
| `apps/observer/tests/test_artifact_freshness.py` | 26172 | `1a1f8a7369cc6c1ee694ecb11201738da3a977e9a0f1b30182fd13056d3aba8e` |

## 范围与未决缺口

- AG-19 / T07: the original WORK-LAB long conversation, WORK-LAB-SUMMARY and the 2026-09-28 startup/final attachments remain inaccessible (SOURCE_MISSING).
- P0 product gaps still open in the register: U02/U03/U08 partial; P1 AG-09 needs the owner to pick a project and two executors; AG-10/11/15/14/12/13/20 unstarted or partial; P2 AG-16/17/18.
- Merge to main, release, install, global configuration and other-project writes remain unauthorized and were not performed; the four old branches are not retired.
- Instrument coverage, not product truth: no automated path in this repository can capture a WebView2 DirectComposition surface (GDI is structurally blind, ERR-104; the CDP port accepts TCP and answers nothing, ERR-107), so Windows.Graphics.Capture stays unwired and a pixel-only regression would need another owner observation.
- Source-side defects kept as the source has them: the blueprint has no AG-14 row, merges AG-16/AG-17 into one line, omits AG-01..AG-08 and W09, cites OD03/OD04 jointly, and §16 rows 16.16/16.17/16.19 enumerate their members with 等, so the candidate list is not exhaustive at the source.
- Candidate registrations are not assessments: identity, license, version and Windows support are NOT_VERIFIED for every §16 row, and a pilot still needs an individually authorized task card.
- The desktop artifact the owner observed carries a v1 build receipt, so its frontend chain is attested only by the content-evidence rule; a v2 receipt arrives with the next build. The v1 receipt was deliberately not rewritten for the current binary — writing it after the fact would attest the tree to itself.

## 双端同步状态定义

- 本地文件与提交：本报告生成后即成立（读回见上）。
- 远端分支：需推送后以 `git ls-remote` 读回，未读回前一律记 `未验证`。
- GitHub About：Git 外元数据，单独记录 before→after 与读回，不能以提交 README 代替。
- exact-SHA CI：以推送后 PR 的检查读回为准；本地通过不称为 CI 绿。
- 默认分支 main：本轮不合并，故记为未更新。

