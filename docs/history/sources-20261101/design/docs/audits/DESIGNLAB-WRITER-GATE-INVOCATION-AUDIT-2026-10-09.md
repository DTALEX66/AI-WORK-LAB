# DESIGN-LAB 会写被跟踪文件的门，以及谁用它们的写模式调用它们（2026-10-09）

本文每张表都由脚本按第 1 节写明的规则量出来再生成（生成脚本放在被 ignore 的
`.project-local/runs/writer-sweep/write_audit.py`，是本轮的临时工具，不是仓内资产——所以规则本身
写在下面，读者不需要那个脚本也能自己复算）。范围：`scripts/*.py` 与 `design-lab/scripts/*.py`
里把**被跟踪路径**作为写入目标的脚本，以及三个调用面（测试、权威链、workflow）。

## 0. 为什么这算一个缺陷类

一道门如果同时是写手，用裸参数调它就是在改被跟踪文件。测试里这样调，全套每次跑都会重写投影（上一回合在 `test_claim_honesty_gates.py` 上量到并改掉，三份投影因此不再被测试改写）；**CI 里这样调**，除了污染树还有一个更坏的效果：记录每次都被刷新，于是没人能看出它的内容与它自己的判断已经脱节。本轮量到的实例：`LANGUAGE-BOUNDARY-SCAN.json` 的判断仍然对（`verdict=PASS`、`failures=[]`），但它记的 `tracked_files_scanned=3360`，而同一提交在干净检出里重算出来是 **3412**——差 52 个文件，一直没人看见，因为每次链跑都把它重写一遍。

## 1. 会写被跟踪路径的脚本（实测 25 个）

判定规则（也写在生成脚本里）：某常量的字面量是被跟踪路径**或**被跟踪目录，且该常量出现在带 `.write_text(` 的那一行，才算这个脚本在写它——两种真实形态都要认：`OUT = REPO / "reports/current/X.json"` 配 `OUT.write_text(...)`，以及 `OUT = REPO / "reports/current"` 配 `(OUT / name).write_text(...)`（后者一份脚本发多份记录，所以目标写成"该目录内逐份"，不去冒充精确文件名）。只看"脚本里提到这个路径"会把只读它的脚本误判成写手——本轮就是靠这条区分否证了我自己上一轮的一句断言。

| 脚本 | 写的被跟踪文件 | 有只读形态？ | write_text 调用数 |
|---|---|---|---|
| `design-lab/scripts/inventory_binaries.py` | `reports/ (该目录内逐份)` | **无** | 1 |
| `design-lab/scripts/migrate_source_registry_v3.py` | `reports/ (该目录内逐份)` | **无** | 3 |
| `design-lab/scripts/update_evidence_binding.py` | `design-lab/ (该目录内逐份)` | **无** | 2 |
| `scripts/classify_repo.py` | `reports/ (该目录内逐份)` | `--check` | 1 |
| `scripts/deepseek_foundation_audit.py` | `reports/current/FOUNDATION-AUDIT.json` | `--check` | 1 |
| `scripts/deepseek_language_inventory.py` | `reports/current/LANGUAGE-INVENTORY.json` | `--check` | 1 |
| `scripts/deepseek_migration_rehearsal.py` | `reports/current/CREATIVE-MIGRATION-REHEARSAL.json` | **无** | 1 |
| `scripts/deepseek_post_cleanup_audit.py` | `reports/current/POST-CLEANUP-AUDIT.json` | **无** | 1 |
| `scripts/deepseek_registry_ssot.py` | `reports/current/DEEPSEEK-REGISTRY-SSOT.json` | `--check` | 1 |
| `scripts/deepseek_runtime_cleanup.py` | `reports/current/RUNTIME-CLEANUP-PLAN.json` | **无** | 3 |
| `scripts/deepseek_spill_census.py` | `reports/current/SPILL-CENSUS.json` | `--check` | 1 |
| `scripts/deepseek_test_gate_report.py` | `reports/current/DEEPSEEK-FINAL-TEST-GATE.json` | `--check` | 1 |
| `scripts/generate_branch_cleanup_candidates.py` | `design-lab/ (该目录内逐份)` | **无** | 1 |
| `scripts/generate_branch_inventory.py` | `reports/ (该目录内逐份)` | **无** | 1 |
| `scripts/generate_machine_inventory.py` | `reports/ (该目录内逐份)` | `--check` | 1 |
| `scripts/generate_repository_size_report.py` | `design-lab/ (该目录内逐份)` | **无** | 1 |
| `scripts/generate_rights_registry.py` | `design-lab/config/rights-registry.json` | `--check` | 1 |
| `scripts/verify_clean_tree.py` | `reports/current/CLEAN-TREE-REPORT.json` | **无** | 1 |
| `scripts/verify_contract_graph.py` | `reports/current/CONTRACT-GRAPH.json` | `--check` | 1 |
| `scripts/verify_evidence_levels.py` | `reports/current/EVIDENCE-LEVEL-AUDIT.json` | `--check`、`--self-test` | 1 |
| `scripts/verify_fresh_clone.py` | `reports/current/FRESH-CLONE-VERIFICATION.json` | **无** | 1 |
| `scripts/verify_language_boundary.py` | `reports/current/LANGUAGE-BOUNDARY-SCAN.json` | `--check` | 1 |
| `scripts/verify_no_overclaim.py` | `reports/current/NO-OVERCLAIM-AUDIT.json` | `--check` | 1 |
| `scripts/verify_recovery_safety.py` | `reports/current/RECOVERY-SAFETY.json` | `--check` | 1 |
| `scripts/verify_supply_chain.py` | `reports/current/SUPPLY-CHAIN-REPORT.json` | `--check`、`--self-test` | 1 |

没有只读形态的 11 个：`design-lab/scripts/inventory_binaries.py`、`design-lab/scripts/migrate_source_registry_v3.py`、`design-lab/scripts/update_evidence_binding.py`、`scripts/deepseek_migration_rehearsal.py`、`scripts/deepseek_post_cleanup_audit.py`、`scripts/deepseek_runtime_cleanup.py`、`scripts/generate_branch_cleanup_candidates.py`、`scripts/generate_branch_inventory.py`、`scripts/generate_repository_size_report.py`、`scripts/verify_clean_tree.py`、`scripts/verify_fresh_clone.py`。这些里绝大多数是**一次性历史审计**（`test_gate_reachability.py` 的 MANUAL_GATES 已逐条声明为 one-off），给它们补 `--check` 是在造没人调用的接口，所以本轮只给`verify_language_boundary.py` 补——它是唯一被 CI 链以写模式实际调用的那个。

## 2. 权威链（CI 走的那条）的子调用 argv

| 链条目 | 子脚本 | argv |
|---|---|---|
| authority-ledger | `scripts/deepseek_authority_ledger.py` | `verify` |
| authority-chain | `scripts/deepseek_authority_chain.py` | `--check` |
| source-lock | `scripts/verify_source_lock.py` | `--check` |
| contract-graph | `scripts/verify_contract_graph.py` | `--check` |
| language-boundary | `scripts/verify_language_boundary.py` | `--check` |

实测裸调用条目：0 个（已全部改掉）。本轮之前的那一个是 `language-boundary`，同一列表里其他四条都带 `--check`/`verify`，只有它是空的——所以这不是风格问题，是链条里唯一一处"检查器位置上放了写手"。

## 3. workflow 直接调的脚本（逐行读数）

- `canonical-verify.yml:41` — `run: python design-lab/scripts/verify_identity_gate.py`
- `canonical-verify.yml:43` — `run: python design-lab/scripts/verify_design_lab.py`
- `canonical-verify.yml:45` — `run: python design-lab/scripts/verify_adapter_matrix.py`
- `canonical-verify.yml:55` — `run: python design-lab/scripts/verify_task_ledger_contract.py`
- `canonical-verify.yml:62` — `run: python design-lab/scripts/verify_evidence_artifact_presence.py`
- `canonical-verify.yml:68` — `run: python design-lab/scripts/verify_candidate_taxonomy.py`
- `canonical-verify.yml:70` — `run: python design-lab/scripts/verify_state_vocabularies.py`
- `canonical-verify.yml:87` — `run: python design-lab/scripts/verify_library_index_consistency.py`
- `canonical-verify.yml:118` — `run: python scripts/verify_authority_gates.py --zero-spill`
- `canonical-verify.yml:142` — `run: python scripts/verify_top_level_authority.py`
- `canonical-verify.yml:147` — `run: python design-lab/scripts/verify_project_drift.py`
- `canonical-verify.yml:153` — `run: python scripts/verify_path_refs.py`
- `canonical-verify.yml:202` — `run: python3 design-lab/scripts/verify_workbench_packaging.py`
- `canonical-verify.yml:338` — `run: python design-lab/scripts/verify_license_coverage.py`
- `canonical-verify.yml:346` — `run: python design-lab/scripts/verify_sbom.py`
- `canonical-verify.yml:358` — `run: python scripts/verify_secret_history.py --max-blobs 0`
- `release-gate.yml:46` — `run: python design-lab/scripts/verify_design_lab.py`
- `release-gate.yml:52` — `run: python design-lab/scripts/verify_release_gate.py`

`canonical-verify.yml` 被四个 SHA-256 pin 之一保护（`scripts/verify_top_level_authority.py` 校验），所以这一轮我一行没动它。第 118 行走的是权威链脚本，链内部现在只做检查；第 142 行 `verify_top_level_authority.py` 不写被跟踪文件（不在上面那张表里），所以那两处都不是写模式。

## 4. 本轮改了什么（以及没改什么）

- `scripts/verify_language_boundary.py` 增加只读 `--check`：只比**判断**（`verdict` 与 `failures` 集合，双向），描述性计数（`tracked_files_scanned`）只报 NOTICE 不判红——把它钉死就等于要求每次提交都重写记录，那正是这个缺陷的形状。`subject_sha` 故意不比：在册的九条历史空值由 `design-lab/config/report-subject-debt.json` 管，门已经在那儿数着。
- `scripts/verify_authority_gates.py` 的 GATES 第 5 条 argv 由 `[]` 改为 `["--check"]`。
- 新增守卫 `design-lab/tests/test_language_boundary_check_mode.py`（13 例）：其中一条把规则写成对整个 GATES 列表的 AST 检查——**任何不带 argv 却写被跟踪路径的子调用直接红**。我用修复前的链字节反证过：该守卫准确报出 `[('language-boundary', 'scripts/verify_language_boundary.py')]`，也就是它确实能抓到被抓到的那个缺陷，不是一条永远为真的断言。
- 修完整条链时又量出一处**只在非 UTF-8 控制台才现形**的缺陷：`verify_authority_gates.py` 用
  `encoding="utf-8", errors="replace"` 读子进程输出，而子进程（`verify_language_boundary.py`）
  在自己的 cp936 控制台上打印中文注解 → 父进程把非 ASCII 字节全变成 U+FFFD → 再打印回同一个
  codepage 时 `UnicodeEncodeError`，整条链在第一行报告上崩掉（实测 `CHAIN_EXIT=1`，traceback 在
  `print(f"{status:10s} ...")`）。Linux runner 用的是 UTF-8，永远撞不到，所以它能活到今天。
  修法分两层：给每个子进程显式 `PYTHONIOENCODING=utf-8`（根因），并对回显那一行做
  `safe_text()`（不让一条报告行决定整条链能不能跑完）——只处理回显，退出码、判断与写出的记录
  一律不动，所以它藏不了任何失败。
- 修完实测：`AUTHORITY_GATES=PASS gates=7 failed=none`，其中
  `language-boundary LANGUAGE_BOUNDARY=PASS mode=check judgement_agrees=yes descriptive_drift=1`；
  跑完 `git status --porcelain` 前后逐字相同，即整条链不再写任何被跟踪文件。测试里带一条
  以 `PYTHONIOENCODING=gbk` 复现该崩法并断言链跑完且树不动的回归例。
- 没改：九条在册记录一条都没重跑（它们都被 DONE 任务当证据引用，见任务册理由）；workflow 没动；`deepseek_*` 一次性审计没加接口。

## 5. 我上一轮写错的一句（带日期更正）

我在 2026-10-09 的交接与提示词里把 `verify_authority_gates.py` 说成"CI 里的写手，会重写 `DEEPSEEK-FINAL-TEST-GATE.json`"。读代码后否证：该脚本只在 `TEST_GATE_OUT` **存在时读它**，写那份记录的是 `deepseek_test_gate_report.py`，而且链里对它的调用本来就是 `--check`；只有在本地 bound 历史缺失的全新检出里，它才故意先跑关键 220 例再生成一次，并把理由写在 `run_test_gate()` 的 note 里。真正被我抓住的是同列表里的另一条（language-boundary）。错因：我把"脚本里出现了那个路径常量"读成"它写那个路径"，没看赋值之外的用法。

## 6. 复现命令

```
python scripts/verify_language_boundary.py --check       # 判断一致则 exit 0，且不写盘
python design-lab/tests/test_language_boundary_check_mode.py
python .project-local/runs/writer-sweep/read_call_statements.py   # 本表的原始读数
```

生成时间 2026-10-08T21:37:02+00:00；表内脚本数 25、无只读形态 11、链内裸调用 0、workflow 直接调用行 18。

## 7. 同日追加：把"只读形态"逐个跑完后，新门 `verify_projection_freshness.py`

把上面那张表里**有只读形态的 15 个**逐条实跑（主树一次、干净 worktree 一次），结果分成三类：

| 类别 | 数量 | 实测 |
|---|---|---|
| 两棵树都通过 → 进新门 | 11 | foundation-audit、language-inventory、registry-ssot、rights-registry、classify-repo、contract-graph、evidence-levels、language-boundary、no-overclaim、supply-chain、machine-inventory |
| 只在生成机上通过，干净检出报 DRIFT → 明确排除并写理由 | 3 | SPILL-CENSUS、DEEPSEEK-FINAL-TEST-GATE（`--check` 去读被 ignore 的 `test-run/history.jsonl`）、RECOVERY-SAFETY |
| 无只读形态 | 其余 | 见第 1 节加粗"无"；不为它们现造接口 |

`VERIFY_PROJECTION_FRESHNESS=OK records=11 verified=11 excluded=3 findings=0`，注册进聚合
（SCRIPTS 71 → 72 条，聚合打印 total 72 → 73；数字由 ast 数两个 blob 得到）。三处实测副产品：

1. **`deepseek_language_inventory.py --check` 红了几个星期，没人知道**：它把"提交里记的每种语言
   文件数"与当前树对比，而任何一次新增文件都必然让它红——所以它只能永远红。实测它记 1,776
   个映射文件 vs 现在 3,028，且完全没有 SVG 行（现存 47 个）。它既不在 workflow、也不在聚合、
   也没有测试调用，脚本名又不匹配可达性模式的候选，所以"一道永远失败的门"同时是"一道没人在跑的门"。
   现在 `--check` 改成校验快照自身能证明的东西：行内算术（`mapped + unmapped == tracked_files_total`、
   `nonblank <= total`、`code_nonblank_lines` 与行值一致、`code_languages` 有行、policy 四个字段非空、
   `subject_sha` 是 40 位十六进制），并把树移动了多少写成 NOTICE（13 行变化）。判断口径变了，
   阈值没放松：这些都是"记录自己是否自相矛盾"，不是"记录是否刚好等于今天的树"。
2. 新门**自己检查自己**：每个入口跑完前后各取一次 `git status --porcelain`，被改动就报
   `FRESHNESS-CHECK-WROTE`——因为我这次遇到一个说不清来源的 FOUNDATION-AUDIT.json 被重写（subject
   被刷成当时的 HEAD），逐子进程排查又都干净；与其继续追一次性的事，不如让这个条件永久可检。
   一个会重写记录的"检查器"永远不会与记录不一致，那是最坏的假绿。
3. 两道守卫各自抓到一个我自己写的 bug：入口表第一版写 `if argv and argv[0] not in READ_ONLY_FLAGS`
   ——空 argv（写模式）被短路放过，正是这道守卫存在的唯一理由；埋一个假入口就把它照出来了。
   另一处是测试里 `cls.run = subprocess.run(...)` 覆盖了 `TestCase.run`，整类用例直接
   TypeError。还有可达性门的"过期豁免"规则把我这个新门变成了一次真实变化：
   `deepseek_foundation_audit.py` 原被登记为 one-off，现在它被新门调用，豁免必须撤（撤的理由写在
   测试里，断言本身一条没删）。

## 8. 同日再追加：那三条"只在生成它的那台机器上成立"的检查，逐条改成从 tracked 状态回答

先测原因，再改代码。两棵树都是同一提交 `d6ba107f`，工作区干净（porcelain 0），测量脚本
`.project-local/task-runtime/measure_excluded_gate_drift.py`（只读：import 生成器、按
`--check` 自己那句比较重算，并把记录里每个被比字段与重算值逐条对照，不落盘）。

| 门 | `--check` 原来比的字段 | 本机值 | 干净检出重算值 | 输入性质 | 现在的判据 | 机器态词表 |
|---|---|---|---|---|---|---|
| `SPILL-CENSUS` | `repository_totals_bytes` | `{"UNKNOWN": 13638}` | `{}`（`.hermes/` ABSENT） | 仓内 ignored 目录 + 仓外 agent home | 路径规则、算术、spill 前提、隐私声明 | `MATCHES_RECORDED_TOTALS` / `DIFFERS_FROM_RECORDED_TOTALS` / `NOTHING_ON_THIS_MACHINE` |
| `RECOVERY-SAFETY` | `verdict` | `PASS` | `FAIL`（三份回执 ABSENT；`I010` 两棵树都 `ok=True`） | 3 份 ignored 回执 + tracked `src/` | 归档回执 + 生产工具源码 + 状态机 | `MATCHES_ARCHIVED_COPY` / `LIVE_COPY_ABSENT` / `DIFFERS_FROM_ARCHIVED_COPY` |
| `DEEPSEEK-FINAL-TEST-GATE` | 除 `generated_at`/`subject_sha` 外全部字段 | 全部一致（4 条匹配运行） | 整份不同（匹配运行 0 条） | `history.jsonl`（ignored） | 记录自身派生一致性 + 16 个模块作为版本化文件存在 | `MATCHES_LOCAL_HISTORY` / `DIFFERS_FROM_LOCAL_HISTORY` / `HISTORY_ABSENT` |

三条在 `d6ba107f` 的干净检出上原样打印 `SPILL_CENSUS=DRIFT`、`RECOVERY_SAFETY=DRIFT`、
`TEST_GATE=DRIFT results changed since generation`。`DRIFT` 这个词本身就是断言错误：没有任何东西
改变，只是那台机器上没有可比的输入。

### 8.1 RECOVERY-SAFETY：把回执从"一台机器的临时目录"变成仓库里的证据

`I000` 的判据是"每次破坏性操作都留了 plan→候选清单→备份/摘要→验证→回滚→回执"。它的证据就是那
三份 manifest，而 manifest 住在 `.project-local/`——所以这条主张的可验证寿命等于那台机器不重装的
寿命。归档不是新增证据，是把已有证据放到它声称描述的位置上：
`reports/history/destructive-receipts-2026-09-13/`，逐字节复制（sha256 前缀
`8cdfcbfa42dc1623` RUNTIME-CLEANUP 73203 B / `044f02b896883e27` DELETE 3162 B /
`5088e4766929b68f` MIGRATION 55071 B，三处副本与原件一致）。

一条我自己的探针假警报值得记下来：我先用 `grep -c $'\r' file` 数 CR，三行都报"每行都匹配"（60/1584/1110
= 行数），我据此以为原件是 CRLF、需要给这个子树加 `-text` 免正规化。真测是
`tr -dc '\r' <file | wc -c` = 0——文件本来就是 LF，Git Bash 里以 CR 作 pattern 的 grep 匹配所有行。
`.gitattributes` 一个字没动，这就是"先怀疑新仪器"的又一次兑现。

`--check` 同时变严了：以前只比 `verdict` 一个字段，现在比整份判断（时间戳与 `subject_sha` 之外），
所以改过的回执会被抓住，而不只是被翻掉的那个词。

新的绑定检查顺手证明我第一版写的不变量是错的。我假设回执带本门自己的 `DLDS-I000/I010`；实测它们
带的是**执行该操作的工具**自己的 id（`DLDS-D030` / `DLDS-A040` / `DLDS-E020..E040`，三个工具声明的
id 互不相交——`grep -c` 交叉验证：A040 出现在 runtime_cleanup 里 0 次，反之亦然）。所以 join 改成
"回执里的 id ⊆ 生产工具源码声明的 id"，另加"必须在顶层权威包内"和"路径必须仓内相对"。埋一个假
回执（把 A040 换成 D030）现在必红。

副作用诚实记账：这次改动**必须**重写 `RECOVERY-SAFETY.json`（schemaVersion v2，形状变了），于是它的
`subject_sha` 从空变成 `d6ba107f`，`report-subject-debt.json` 的那一行被"债已闭合"规则判红。
删行是如实登记（字段确实绑到了提交），不是替 owner 拍板：`thisRound.rebasedOn` 写清了这次运行发生在
哪个 head、为什么必须重跑、以及"绑定运行记的是运行结束时的 HEAD"这个仍然悬着的 owner 问题没有因此
被决定。登记表从 9 行变 8 行，#18 的可选项少了一个。

### 8.2 DEEPSEEK-FINAL-TEST-GATE：运行不可从仓库重放，那就只判仓库能答的部分

运行本身在 CI 里由权威链执行（`local_history_present()` 分支——有历史就 `--check`，没有就跑三序加一次
复跑），这个脚本从不跑测试。改后 `--check` 判：声明的 16 个模块逐个存在于
`design-lab/tests/<name>.py`（实测 16/16，且每个恰好一份）、写历史的那个 runner 是版本化内容且被
`source` 字段指名、三条顺序与 requirements 对得上、`identical_counts` /
`zero_failures_in_every_order` / `ORDER_INDEPENDENT` / 顶层 `PASS` 全部由记录自己的数字推出、
1392 全套的 DEFERRED 仍带着 scope、实测理由与 `not_a_claim`。

顺手抓到一条"手写数字"：`executed_scope.tests_per_order` 一直是字面量 220，而这份记录引用的
2026-10-06 三条运行各自记的是 **225**（复跑行 450 = 225×2）。也就是说这个数字从没被从任何地方读过。
现在它由运行派生，并被 `--check` 比对。散文里重复 220 的地方按性质分别处理：描述当前事实的
（`verify_authority_gates.py` 四处、本门 docstring 一处）直接改口径；描述 2026-09-14 那次运行的
（`deepseek_final_closeout.py`）保留原数并加带日期的更正，因为那次确实是 220 与 4400。

### 8.3 SPILL-CENSUS：记录没重写，只有检查被重写

判据全部只读记录字段与 git：`classify()` 对其记的每条路径应给出记下的类别与理由；`delete_policy`
与 `recreatable` 应由"类别 + 是否空目录"这条规则推出；仓库对象必须有 digest（回滚无法验证的
restore 计划不是计划）；totals 与 MiB 必须对其自己的对象求和成立；两个对象不得声明同一个归档目标
（写侧那条 "两棵树都有一个叫 reconstruction 的子目录" 的碰撞规则，第一次变成可检的）；
`UNPROVEN` 对象不得被提出触碰、移动，不得出现在 `.hermes/` 之外；spill 前提本身——每条
`source_path` 必须**没有**被 git 版本化，否则 `.hermes` 内容是仓库内容而不是残渣；隐私声明必须还在
（`content_read` 为假、每个 home 有 scope note、`never_touched` 含 `E:\`、`not_read` 非空）；
`verdict` 仍是 `CENSUS_COMPLETE`。

这条最值得记的是它照出的另一面：同一个 `--check` 在**生成了它的那棵树**里放行了一份已经过时的记录——
`agent_homes.*.native_entries_seen` 记的是 3/83/0，本机实测 0/91/9，三项全错而它打印 PASS，因为 totals
是它唯一看的字段。只比一个字段的"检查"在两个方向上都是盲的。

机器态只报不判：`local_state=` 三值。记录本身**故意没重写**——规则读的字段现存记录都带着，所以这
一条不需要 regeneration，`subject_sha` 保持为空并留在登记表里；这一条的 owner 问题一点没被我推进。

顺带量到一条建议 owner 决定的事实（我没有动它）：`reports/current/SPILL-CENSUS.json` 里
`agent_homes.*.path` 记录的是本机 agent home 的绝对路径（含用户名），`design_lab_owned[]` 记录条目名。
它们已经提交并推送过了，所以现在改不能收回既成事实；要不要把这类字段脱敏成 `~/.codex` 形式，或把整段
移出 tracked 投影，是 owner 的判断。

### 8.4 登记表现在为空，以及两棵树的逐字输出

`verify_projection_freshness.py`：本机 `VERIFY_PROJECTION_FRESHNESS=OK records=14 verified=14
excluded=0 findings=0`；干净检出（同一提交、无 `.project-local`）同一行逐字相同，porcelain 前后 0。
三条门在干净检出上分别打印 `SPILL_CENSUS=PASS objects=1 rules=0 local_state=NOTHING_ON_THIS_MACHINE`、
`RECOVERY_SAFETY=PASS receipts audited from tracked state LIVE_COPY_ABSENT=3`、
`TEST_GATE=PASS modules=16 verdict=PASS findings=0 local_history=HISTORY_ABSENT matching_runs=0`。
本机则是 `MATCHES_RECORDED_TOTALS` / `MATCHES_ARCHIVED_COPY=3` / `MATCHES_LOCAL_HISTORY matching_runs=4`。
权威链 `AUTHORITY_GATES=PASS gates=6 failed=none`（test-gate 走 `--check` 分支），聚合门
`VERIFY_DESIGN_LAB=OK total=73 failed=0`。

EXCLUDED 保留为空 dict 而不是删掉机制：它是"不可复核的投影必须交代为什么"的那个位置，
`test_projection_freshness.py` 现在钉住它为空，同时埋一条假豁免证明它仍会以 NOTICE 出现而**不**算
finding（登记表空了不能让它的报告路径变成未测试代码）。

新增测试：`test_recovery_safety_tracked_verdict.py` 15、`test_final_test_gate_tracked_verdict.py` 16、
`test_spill_census_tracked_verdict.py` 22，全部含埋缺陷分支；机器无关性用"把走盘函数换成 raise
仍必须判干净"这种形式证明，而不是靠我相信我没读盘。

复现：
```
python -X utf8 -B .project-local/task-runtime/measure_excluded_gate_drift.py --tree "D:/All projects/DESIGN-LAB"
python -X utf8 -B .project-local/task-runtime/measure_excluded_gate_drift.py --tree "<worktree>"
python -X utf8 -B scripts/verify_recovery_safety.py --check
python -X utf8 -B scripts/deepseek_test_gate_report.py --check
python -X utf8 -B scripts/deepseek_spill_census.py --check
python -X utf8 -B design-lab/scripts/verify_projection_freshness.py
```

