# DESIGN-LAB 只读形态 × CI 可见面：哪些 `--check` 真的被跑到（实测 2026-10-09）

范围：`scripts/` 与 `design-lab/scripts/` 下的 30 个声明了只读形态（`--check` / `--self-test` / `--verify`）
的脚本，对 4 个 invocation 表 + workflow 行做可达性测量。测量脚本
`.project-local/task-runtime/measure_check_mode_reach.py`（AST 读表 + workflow 行解析），落盘副本
`.project-local/task-runtime/measure_check_mode_reach.json`。两棵树：主工作树与
`.project-local/worktrees/vendorhead`（detached，同一提交 `af8f1b9e`，porcelain 前后 0）。

## 0. 为什么"门被不被命名"不够

原有的 `design-lab/tests/test_gate_reachability.py` 问的是：有没有 workflow 步骤或测试模块**提到**这个
脚本。它看不见**形态**。`deepseek_hermes_migration.py --verify` 就是被这一点藏住的：脚本本身有名字，
它的只读形态在 2026-10-09 之前没有任何表调用过，而它在两棵树里都打印 FAIL——一个永远红、又没人读的
检查，和红到没人看是同一件事。因此本轮加了 `ReadOnlyModeTests`：声明只读形态 ⇒ 该形态必须被调用，
否则必须在册并写明实测判定。

## 1. 实测计数

| 项 | 数量 |
|---|---|
| 声明只读形态的脚本 | 30 |
| 其中该形态确实被 CI 面调用 | 21 |
| 在册（写明实测判定，暂不能强制） | 10 |

被调用的 21 个形态，按调用它的那一步归类：

| 调用者（CI 步骤） | 形态 |
|---|---|
| `python-gate: python design-lab/scripts/verify_design_lab.py` → 聚合门 → `verify_projection_freshness.py` 的 `ENTRIES` | `deepseek_foundation_audit` `deepseek_language_inventory` `deepseek_registry_ssot` `generate_rights_registry` `classify_repo` `verify_contract_graph` `verify_evidence_levels` `verify_language_boundary` `verify_no_overclaim` `verify_supply_chain` `generate_machine_inventory` `verify_recovery_safety` `deepseek_test_gate_report` `deepseek_spill_census` 各 `--check`（14 条记录） |
| 同上，新增的 `RECEIPT_CHECKS` | `deepseek_hermes_migration --verify`、`verify_vendor_manifests --check`、`design_debt_baseline --check`、`inert_contract_survey --check`（4 条） |
| `authority-gate: python scripts/verify_authority_gates.py --zero-spill` | `deepseek_authority_chain --check`、`verify_source_lock --check`、`verify_contract_graph --check`、`verify_language_boundary --check`、`deepseek_test_gate_report --check`（`deepseek_authority_ledger verify` 是位置参数形态，非 flag） |
| `python-gate` 直接步骤 | `update_evidence_binding --check`、`classify_repo --check` |

注：`verify_contract_graph.py` / `verify_language_boundary.py` / `deepseek_test_gate_report.py` /
`classify_repo.py` 被两条路各调一次——重复执行不等于重复断言，但**同一形态被两个入口调用**也让"哪个
步骤红了"变得含糊；这是聚合的代价，见 §4。

聚合门里 `SCRIPTS` 是 72 个**裸调用**（`run_child([sys.executable, str(script)])`，一个参数都不传）。
本轮实测：整条聚合跑完 `git status --porcelain` 为 0，即这 72 个裸形态在这次运行里没有重写任何被跟踪
投影。这是一次行为证据，不是结构证明——结构证明现在由 `RECEIPT_CHECKS` + `ReadOnlyModeTests` 接管：
`verify_vendor_manifests.py` 之前只以裸名出现在 `SCRIPTS`（它的默认形态恰好就是 checker），现在
`--check` 被显式命名，并享受与每条只读入口同样的"跑完前后各取一次 porcelain"守卫。

## 2. 在册的 10 条，逐条给实测判定与关闭条件

| 脚本 | 实测判定（两棵树一致，除注明） | 要什么才能强制 |
|---|---|---|
| `build_candidate_taxonomy.py --check` | rc=2，`the following arguments are required: --observation` | 给 observation 一个 tracked 默认值，或撤掉这个 flag——形态存在但调不动 |
| `deepseek_content_audit.py --check` | `CONTENT_AUDIT=DRIFT ['THIRD-PARTY-SOURCE-AUDIT.json', 'DUPLICATE-CONTENT-AUDIT.json']` | 用它自己的 writer 重发这两份派生审计，然后接进 `RECEIPT_CHECKS` |
| `deepseek_directory_audit.py --check` | `DIRECTORY_AUDIT=FAIL` | 原因未诊断；诊断后再决定接或撤 |
| `deepseek_final_closeout.py --check` | `FINAL_CLOSEOUT=FAIL` | 它读的账本状态自 2026-09-14 已移动；先诊断 |
| `deepseek_size_audit.py --check` | `SIZE_AUDIT=PASS` | 输入是本机 `.git` pack（2026-10-08 实测 236 MiB）；runner 的 clone 形状会改这个数，先给出机器无关判据 |
| `deepseek_worktree_reconciliation.py --check` | `WORKTREE_INVENTORY=PASS` | 比对本机登记的 worktree；CI 只有一个，不是仓库属性 |
| `generate_current_reports.py --check` | 本机 `CURRENT_REPORTS=DRIFT` 3 份；干净检出 9 份 | 投影停止嵌 `testRunId` / 本机缺件——owner 项（任务表 #20）；之后这是真门 |
| `generate_ssot_projections.py --check` | `SSOT_PROJECTIONS=DRIFT CAPABILITY_INDEX.json / EVIDENCE_INDEX.json` | 重发索引，或写明哪一侧是权威 |
| `render_brand_asset.py --check` | `BRAND_ASSET=OK png=4953B inlined=4953B` | 它是资产管线步骤而非记录校验；强制它会把 renderer 变成 CI 依赖 |
| `verify_zero_spill.py --self-test` | `ZERO_SPILL_SELF_TEST=FAIL`，原因是它的自检驱动 `generate_current_reports.py --check` 并继承其 DRIFT | 自检必须用一条天然绿色的命令，不能借用一条 currently owed 的 |

## 3. 本轮改了什么

1. `deepseek_hermes_migration.py --verify` 拆成两半（提交 `af8f1b9e`）：manifest 从
   `reports/history/destructive-receipts-2026-09-13/MIGRATION-MANIFEST.json`（tracked，字节与本机副本相同）
   读；两版本记录互相对账——缺失的归档对象必须被 `prune-manifest-2026-09-26.json` 点名，prune 记录点名的
   对象必须有对应迁移记录；本机是否还持有该归档只报不判（`archive=MEASURED_ON_THIS_MACHINE` /
   `ABSENT_ON_THIS_MACHINE`）。实测：本机 `PASS objects=109 recorded_removals=1 archive=MEASURED_ON_THIS_MACHINE`，
   干净检出同一行且 `ABSENT_ON_THIS_MACHINE`；把归档目录清空后打印 108 条 `missing target`，且已记录的那一条
   不计入——这条 join 是唯一能同时抓住"解释过的删除"和"没解释的丢失"的形状。
2. `verify_projection_freshness.py` 增加 `RECEIPT_CHECKS` 表；verdict 行现在
   `records=14 verified=18 receipts=4 excluded=0 findings=0`（两棵树逐字相同，耗时 27 s）。
3. `test_gate_reachability.py` 增加 `ReadOnlyModeTests`（两个方向钉住集合 + 三个埋点方向已被证伪：
   删一行真在册 → 红；给一个没有该形态的脚本加一行 → 红；把已被调用的形态留在册 → 红；不动 → 绿）。

两个我自己的仪器缺陷也记下来，因为它们比结果更有用：

* 第一版判定"名字与 flag 在三行内共现"，于是它匹配到了**豁免表自己的散文**——8 条在册记录被误判为
  "已调用"。现在 4 个 invocation 表按 Python 对象解析，测试模块只认同一行里的
  `"x.py", [argv]` 调用形状，并有一条埋点断言"散文提及不得算调用"。
* 那个 helper 我叫 `test_module_calls`——以 `test_` 开头即被 unittest 当成用例收集，报
  `TypeError: missing 1 required positional argument`。已改名 `call_sites_in`。

## 4. 需要 owner 拍板的部分（我不能改被 SHA-256 pin 的工作流）

实测事实：18 条只读形态**已经在 CI 里跑**，全部包在 `python-gate` 的一个步骤
（`python design-lab/scripts/verify_design_lab.py`）里。同一 job 内的步骤不重新 checkout，所以把它们拆成
独立步骤的成本只有命令本身：整个 freshness 门 18 条形态合计 27 s，其中新加的 4 条 receipts 各
0–1 s（实测 `verify_vendor_manifests.py --check` 123 ms、`deepseek_hermes_migration.py --verify`
135 ms、`design_debt_baseline.py --check` ≈0 s、`inert_contract_survey.py --check` ≈1 s）。

1. **是否给 `verify_projection_freshness.py` 一个自己的命名步骤。** 现在它红了只会显示
   `VERIFY_DESIGN_LAB=FAIL`，具体哪条记录要翻聚合输出。加一行：

   ```yaml
       - name: Projection and receipt freshness (14 records + 4 receipt checks)
         run: python design-lab/scripts/verify_projection_freshness.py
   ```

   代价：聚合门里它仍会跑一次（约 25 s 重复）。若不想重复，需要 owner 同意从 `SCRIPTS` 摘掉它——那要改
   `verify_design_lab.py`，我可以做，但这是"谁负责这条断言"的裁决。
2. **被 pin 的工作流注释里有一个过期数字。** 第 112 行附近写着 the test gate executes the
   `220-test critical set`；实测该 critical set 现在每条顺序记的是 **225** 个测试（复跑 450）。注释不在
   任何门里，只有 owner 改得动。
3. **`--observation` 那条**（`build_candidate_taxonomy.py --check` 调不动）要不要我按 §2 的方式修形；
   以及 §2 里两条 `FAIL` 是否要我逐个诊断——它们都是已入账缺陷，不是新问题。

## 5. 复现

```
python -X utf8 -B .project-local/task-runtime/measure_check_mode_reach.py
python -X utf8 -B scripts/deepseek_hermes_migration.py --verify
python -X utf8 -B design-lab/scripts/verify_projection_freshness.py --list
python -X utf8 -B -m unittest design-lab.tests.test_gate_reachability design-lab.tests.test_projection_freshness \
    design-lab.tests.test_hermes_migration_verify
python -X utf8 -B .project-local/task-runtime/falsify_mode_guard.py
```
