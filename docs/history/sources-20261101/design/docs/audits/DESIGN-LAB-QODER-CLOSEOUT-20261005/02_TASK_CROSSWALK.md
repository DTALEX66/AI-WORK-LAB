# 02 — C1 Ledger / Reports 真值收口与任务交叉核对

分支：`qoder/designlab-m1-closeout-20261005`（基线 `origin/main` = `1acbfa1`）

## 发现的真实故障（不是投影过期，是投影器被卡死）

`main` 自 `1acbfa1`（2026-09-29，PR #212 账本记录）起，唯一 mutable ledger
**违反它自己的 R5 合同**，导致 `scripts/generate_current_reports.py` 直接抛错：

| # | 故障 | 证据 |
|---|---|---|
| L1 | `evidence[36]`（`r5-bundle-list-route-http-ui-20260929`）`artifacts: []`，而 schema 要求 `minItems: 1` | `CURRENT_REPORTS=FAIL invalid R5 ledger contract at evidence/36/artifacts` |
| L2 | `DL-R5-010` 声明 `implementation=IMPLEMENTED_LOCAL` / `unit=PASS`，但 `reassessment=PENDING_EVIDENCE_REVIEW` | `R5_contract.py:100` → `R5 completion requires explicit evidence reassessment` |
| L3 | CI 从未运行 `generate_current_reports.py --check`，所以 L1/L2 落地 6 天无人发现 | `canonical-verify.yml` 全文无该步骤（本次已补） |

后果：`reports/current/**` 停在 `4c9f1849` / `2026-09-28T14:26:43Z`，
`TASK_PROGRESS.fresh=false`，28 项全 `PARTIAL` —— 任务书所述“陈旧投影”根因即此。

## 修复

1. **L1**：给该 evidence 补真实留存产物
   `design-lab/tests/test_service_http.py`（sha256 `3dc8dae6…`，与 `subject_files` 同值，
   本机 2026-10-05 复跑 27 用例 OK）。未新增任何不存在的产物。
2. **L2**：`DL-R5-010.reassessment → REVIEWED`，理由见下节；未改任何 axis 声明值。
3. **L3**：`canonical-verify.yml` python-gate 增加
   `Task ledger contract gate (R5)`（`verify_task_ledger_contract.py`）。
   注：第一版接的是 `generate_current_reports.py --check`，CI 立刻红——
   且红得正确，因为投影绑定生成时 git 快照，clean checkout 永远复现不了。
   已换成不依赖快照的合同门，并用测试钉住 L1/L2 两类缺陷。
4. `ledger.updated_at → 2026-10-05T15:40:15Z`，重生成 9 份 current 投影，
   `--check` 由 `DRIFT` 变 `PASS`（scope=bound-input-integrity，
   `current-git-and-cloud=NOT_VERIFIED` —— 生成时工作树含未提交改动，如实记录）。
   **限定**：该 `PASS` 只在「生成之后、尚未提交」的那一刻成立。把报告提交进去以后，
   `--check` 必然返回 `STALE ... rebind required`（它拿 `stored_subject` 和
   `current_head` 比，任何提交都会让 HEAD 前进）。因此本轮**没有**把这个 check 接进 CI，
   而是接了不依赖 git 快照的 `design-lab/scripts/verify_task_ledger_contract.py`。
   详见 `10_REMAINING_BLOCKERS.md` 的 C8。

## DL-R5-010 复核记录（谁审、审了什么、没审什么）

- 审阅对象：`r5-workbench-native-task-ui-tests-20260927`、
  `r5-bundle-list-route-http-ui-20260929` 两条 evidence。
- 两条 `kind=local_test`、`outcome=PARTIAL`。其 note 明确 `PARTIAL` 指
  **证据覆盖面**（E2 受控运行，不含宿主 E3 / rights E4 / 人工 Jury），
  不是“测试跑挂”。所绑命令记录为 `Ran 27 tests, OK` 与全量 `Ran 1762 tests, OK`。
- 本次独立复跑：`test_service_http` + `test_design_layer_http` = 47 tests OK；
  全量 1762 套件在 UI 分支重跑（结果见 `00_FINAL_STATUS.md`）。
- **未做**：未在 `main` 的 exact SHA 上重跑绑定测试。
- 因此只把 `reassessment` 置为 `REVIEWED`（表示“已复核且复核人认可声明值”），
  当时**没有**抬升任何 axis，也没有用旧证据冒充当前能力；
  投影器按自身规则把 010 的 implementation/unit 判为
  `UNVERIFIED`（`STALE_SUBJECT_SHA`），这是设计上的证据衰减，不是回归。
- **随后补做 PASS 级重观测**（同日）：把 node 加入 PATH 让 14 个 native-UI 用例真正执行，
  `test_service_http` + `test_design_layer_http` + `test_workbench_native_ui`
  = **61 tests, OK, skipped=0**，绑定 exact SHA `5fb8878d` 与 6 个所测文件的字节哈希，
  以 `kind=local_test` / `outcome=PASS` 追加为新 evidence 并挂到两轴。
  重生成后投影读回 `IMPLEMENTED_LOCAL` / `PASS`，而 `host_live` / `delivery` 仍 `PARTIAL`，
  因此任务整体保持 `PARTIAL`。边界不变：只声明 E2 受控运行时，不含宿主、rights、人工验收。

## 11 项交叉核对任务的当前真值（按产品轴）

投影后读数（`reports/current/PROJECT_STATUS.md`，绑定 `c3e43ea`）：

| Task | 轴读数 | 结论 |
|---|---|---|
| DL-R5-001 | implementation/unit/host_live/delivery 全 PARTIAL | `PARTIAL` |
| DL-R5-003 | 全 PARTIAL | `PARTIAL` |
| DL-R5-004 | 全 PARTIAL | `PARTIAL` |
| DL-R5-005 | 全 PARTIAL | `PARTIAL` |
| DL-R5-009 | 全 PARTIAL | `PARTIAL` |
| DL-R5-010 | implementation=`IMPLEMENTED_LOCAL`、unit=`PASS`（**已由 PASS 级 evidence 验证**），host_live/delivery PARTIAL → 任务整体仍 `PARTIAL` | `PARTIAL` |
| DL-R5-011 | 全 PARTIAL，`host_live` 证据为空 | `PARTIAL`（宿主 E3 未成立） |
| DL-R5-012 | 同上 | `PARTIAL`（宿主 E3 未成立） |
| DL-R5-013 | 全 PARTIAL | `PARTIAL`（本次补上 Plan→RIR 接缝，见 `04`） |
| DL-R5-014 | 全 PARTIAL | `PARTIAL` |
| DL-R5-015 | 全 PARTIAL | `PARTIAL`（M1 未成立） |
| DL-R5-023 | 全 PARTIAL | `PARTIAL` |

**没有任何一项被提升为 DONE/PASS**，也没有引入第二 ledger、第二 runtime。
`design-lab/config/capability-evidence-current.json` 仍是 2026-09-04 的
`DL-TP-R2-014` 投影（`bound_sha` 全 null、`supported_current` 全 false）：
它是**过期投影而非账本**，本次未伪造刷新，列为遗留项（见 `10_REMAINING_BLOCKERS.md`）。

## 唯一账本原则复核

本次只写：`design-lab/config/task-ledger-r3.json`（schema `design-lab/task-ledger/r5-v1`）
与其派生投影。未创建 `task-ledger-r6.json` / `W-ledger.json` / `qoder-ledger.json`。
`docs/audits/DESIGN-LAB-QODER-CLOSEOUT-20261005/*` 全部是只读报告，不作派工入口。
