# T1 账本逐任务复核 · 第三项：DL-R5-003

**复核对象**：`design-lab/config/task-ledger-r3.json` → `DL-R5-003`「CI 与验证环境补齐」
**观测 exact SHA**：`main` = `cd0d303ecb`（`gh api commits/main` 实读）
**观察窗口**：2026-10-06T18:41Z–18:43Z
**结论**：A1、A2、A4 成立；A3 在复核时**不成立**，其修复在 PR #240 里；
**`delivery` 轴零证据且属 required_axes → 本任务不可能 PASS。**

| 轴 | 现状 | 证据 | required |
|---|---|---|---|
| `implementation` | PARTIAL | `r5-ci-required-checks-live-20260927` | 是 |
| `unit` | PARTIAL | `r5-003-static-unit-20260928` | 是 |
| `host_live` | PARTIAL | 空 | 否 |
| `delivery` | PARTIAL | **空** | **是** |

---

## A1「干净锁定环境可运行报告 check」— 成立（本机直测）

```
python scripts/verify_fresh_clone.py
  → FRESH_CLONE=PASS stages=9 failures=[] unverifiable=['install']   exit 0
     PASS  reports_generate  CURRENT_REPORTS=PASS mode=generate
     PASS  reports_check     CURRENT_REPORTS=PASS mode=check scope=bound-input-integrity …
     PASS  path_boundaries   local_root …\task-runtime\fresh-clone\.project
     NOT_VERIFIABLE  install  CI runs 'uv sync --locked'; uv present; no install attempted
```

要点与边界：

1. 这是在**克隆**里跑的，不是主检出，所以它证明的是"干净树 + 无本地状态时生成器不崩且字节自等"。
2. `reports_check` 在克隆里给 `PASS` 而非 `STALE`，因为克隆的 HEAD 就是被检出的提交；
   这条不能推广成"投影永远新鲜"—— 它自己的 scope 串写明 `not current Git or cloud freshness`。
3. `install` 阶段**本机不可验证**（未尝试安装），这不是失败，但意味着 A1 的"锁定环境"这一半
   在本机只有间接证据，直接证据在 CI（见 A2）。

## A2「wheel 非仓库目录运行」— 成立（但**不是**靠本地 venv）

这里我差点误判，记录全过程：

- 我先在 `C:\Users\ALEX` 下用 `.venv\Scripts\python.exe -I -B -c "import design_lab"`，
  得到 `file: D:\All projects\DESIGN-LAB\src\design_lab\__init__.py`，即**源码路径**，
  一度以为"安装态隔离"是假的。
- **该结论不成立**：`.venv` 是可编辑开发安装，本地解析到 `src/` 是**应有行为**，
  不能用来判断 wheel 布局。
- 真正的证据是两条：
  1. `design-lab/tests/test_installed_state_resources.py` 把 `src/design_lab` **复制**进临时
     stage 目录、`sys.path.insert(0, stage)` 并用 `-I -B` 运行，因此仓库树不在路径上；
     第三个用例故意 `cwd=ROOT` 运行，断言
     `installed package silently borrowed a source checkout` —— 即它**自带证伪**。
  2. required context `Clean wheel install + Workbench launch gate` 在 exact SHA 上跑真 wheel
     安装，并断言 `Ran 3 tests`、`^OK$`、且 `! grep -q skipped`。

**所以 A2 由"资源隔离测试 + CI 真装 wheel 作业"共同支撑，不由本地 venv 支撑。**

## A3「不因缺依赖误报代码故障」— 复核时**不成立**，修复在 #240

全仓检索结果：没有任何机制区分"依赖缺失"与"代码坏了"。
`ModuleNotFoundError` 在 `src/` 下只出现一处（`design_layer.py:62`），为无关用途。

已实测的失败形状（本会话踩过）：解释器缺 `scikit-image` 时
`packages/capabilities/reconstruction/metrics.py` 导入失败，unittest 报成
`unittest.loader._FailedTest`，输出 `Ran 1734 — FAILED (failures=11, errors=43)`，
而包装器仍可能 exit 0；唯一线索是测试总数从 1807 掉到 1734。

PR #240 新增 `design-lab/tests/test_test_environment_guard.py`：
依赖清单**从 `pyproject.toml` 解析**（不抄写，映射表被断言覆盖全部声明项），
缺失时报 `ENVIRONMENT_INCOMPLETE (not a product defect)` 并列出包名与解释器路径。
双向验证：正常 venv `Ran 3 tests OK`；同 venv 加 `-S` 后点名 5 个缺失包。
其证伪用例还抓到作者自己的 bug（`resolve_module` 未把 `-` 转 `_`）。

**A3 在 #240 合并前仍应记为不成立。**

## A4「每项结果绑定 SHA」— 成立

账本 39 条证据记录**全部**带 `subject_sha`；`generate_current_reports.py` 的
`qualify_check_verdict` 明确禁止把"绑定了 HEAD 已越过的 subject"的字节稳定记录洗成 PASS
（`STALE` + exit 0，措辞保留 `current-git-and-cloud=NOT_VERIFIED`）。
但 003 自己的两条证据绑在 `634071f3`(09-27) 与 `4c9f1849`(09-28)，
**历史证据不自动提升当前 SHA**（AUTHORITY §6）。

---

## 为什么仍然不抬升任何轴

1. **`delivery` 属 `required_axes` 且证据为空**。本任务的交付语义要真实交付物/发布态证据，
   而本轮目标明确**不发布**（无 tag/release），所以这条轴在本轮**不可能**取得合法证据。
2. A3 的修复尚未合并；合并前"不因缺依赖误报"仍不成立。
3. 本会话**未在当前 SHA 重跑套件**，因此 `unit` 也没有当期证据。
4. 把当期证据绑到 `.project-local/**` 会复制既有坏路（活动账本已有 3 例；
   冻结前继 215 例全中）。新证据的 `artifact_hashes` 必须只绑 tracked 路径。

## 抬升 003 所需的最小动作（按序）

1. 合 #240（补上 A3 的机制）；
2. 在合并后的 exact main SHA 上重跑套件，取 `commands_and_exit_codes` + `environment_versions`；
3. 新证据只绑 tracked 工件（本报告、账本、`verify_fresh_clone.py` 的输出快照）；
4. `delivery` 轴**保持 PARTIAL 并写明缺的是发布态证据**，不用 `host_live`/`delivery` 的空证据
   冒充已验证（契约也禁止非 implementation 轴写 `IMPLEMENTED_LOCAL`）。
