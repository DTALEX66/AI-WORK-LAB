# 归档与删除波次交付记录（2026-10-19）

- **taskId / 血统**：owner 2026-10-19 两条指令的执行记录；权威包仍为
  `docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`（`DL-TP-20261019-DIRECTION-R1`）。
- **本文件取代的读数**：`docs/audits/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md` §7/§8 的闸门数字。
  那份是方向批次的 dated 记录，按 `reports/README.md` 的规则**不改写**；本文件是同一条指令链后续波次的
  dated 记录。当前真值仍以 `design-lab/config/capability-evidence-index.json`、
  `design-lab/config/capability-status.json` 与 `git rev-parse HEAD` 实读为准。

## 0. 结论与状态声明（先看这一节）

- **结论：`PARTIAL`**。本波次声明范围内的动作已落地：40 组 / 228 文件整目录移动（逐条按 blob
  SHA-1 与字节数复核，`bytesRewritten=0`）、83 份旧交接/提示词的"先汇总再移除"、被这些路径绑定的
  读侧消费者全部改指新位、六份权威钉值重钉并逐次记录理由（`AUTHORITY-PIN-CHANGE.json` 实测 8 条 revisions；2026-10-19 占 6 条：方向批次、归档波、删除波、手机端移出范围、AAOS 改为非依赖、AAOS 补进机器面）、投影再生成。
- **不写 `PASS` 的理由只剩一条**：owner 门外的边界（release / 安装态分发 / 真实宿主 E3 / 真人 E4 /
  AAOS 接收 / ComfyUI·H3）依旧不解锁，波次再干净也不解锁它们。**手机端不在这一列**——它已由 owner
  2026-10-19 定为排除项，不是待授权项。
  云端判定不再是理由：`c71e3d21` 那次确实红（`main` run 39287724318 的 `Python gate` 报
  `shard 3/3 tests=975 FAIL=1`，且同 SHA 在开发分支上的 39287715573 是 light gate——11 个 job 全
  `skipped`，那句"success"只描述编译与身份边界，不能当 CI 通过引用），红因已定位并修复（§5 末与
  §5.1）；此后 `72950ce2`、`b07a3906`、`6f4a89a4` 三个 head 的 `main` run 均 `OVERALL=success`
  （各 11 个真实 job success + light gate skipped）。当前 tip 的判定按 §5.2 的方式逐 job 读，不代读。
- **状态声明（`ACCEPTANCE.md` 第 10 项：六件事是不同状态）**：
  - 文档修订＝本波次这一份报告与五份登记件已完成；
  - 规划完成＝方向包 `DL-TP-20261019-DIRECTION-R1` 已闭环，`currentExecution` 34 项仍全部
    `FROZEN_DEFERRED`，解冻需要 owner 明确授权；
  - 代码实现＝归档/删除波本身不新增产品功能，改动只在登记、读侧路径解析与闸门；**同一条指令链后续两次提交确实加了可调用面**：`AssetAnalysis.derive` 的两条生产入口（CLI `design-lab analyze` 与 `POST …/assets/<img-ID>/analysis`）、`contract-bindings` 一行、以及侧栏边界修复与它的新闸门读数。这不解锁 `currentExecution` 34 项，也不构成新任务派工；
  - 真实运行＝**宿主侧未执行**（无真实宿主 E3）。已执行的是回路内受控运行：三条 live 测试真起 loopback 服务、真读资产字节、真拿回 RIR 并过 `validate_rir`；这是 E2 口径，不是 E3；
  - 人工验收＝未执行，且本文件不含任何人工签核，被删文档的"结论"字段是文档自己写的内容摘要，
    不等于有人接受过；
  - AAOS 接收＝未执行。
- **§5 的表**是同一轮实测的定向闸门读数，不是当前状态；复现请按 §2 的命令自读。

## 1. Owner 原话与本轮边界

1. 「任何旧的过时的冗余的陈旧的，不要再明面上，全部归档到该去汇总的地方，包括仓库目录文件夹整体搬走，
   要么压缩归档到历史里……按照规范化处理，防止再次索引路径到旧资料上」
2. 「旧交接和一些提示词的资料 汇总到一起归档后 就删除了吧」，追问后明确为
   「旧的都删除，但是要先审计后归档到一起形成汇总和追溯，并且有新的更新和替代」

本轮只动文档、登记与闸门；**未**执行 release、安装态分发、真实宿主 E3、真人 E4、手机端、AAOS 联调、
ComfyUI/H3（仍 `FROZEN_DEFERRED`，解冻需 owner 明确授权）；E 盘与私有数据边界不变；
账本 `tasks`/`evidence`/`source`/`taskpack`/`plan_path` 身份字段字节未改。

## 2. 基线怎么读（不抄本文件的数字）

```bash
git rev-parse HEAD
git ls-files | wc -l
python scripts/generate_current_reports.py --check   # PASS / STALE / DRIFT 三种读法不同
python scripts/verify_top_level_authority.py
```

本文出现的 SHA 只用于指认"当时测的那一次"，不是当前基线。

## 3. 做了什么（全部为实测数字）

| 动作 | 数量 | 证据 |
| --- | --- | --- |
| 移动归档 | 228 个跟踪文件 / 8,416,910 字节，40 组 | `docs/history/archive-2026-10-19/MANIFEST.json`；逐文件 `原路径→新路径→blob→字节`，移动前记录、移动后从 index 复验。当前读数为 **155 条仍在树上的行逐条复验一致＋73 条标 `status=REMOVED` 带 `restoreAt`**，改写字节 0；清单不再把已删行算作"从工作区可复验" |
| 汇总（删除前置） | 106 条登记（85 交接 + 6 提示词面 + 15 reports 面） | `HANDOFF-PROMPT-DIGEST.json` + `AGGREGATED-RECORD-2026-10-19.md`：每份的标题、自述、结论、取代关系、只有它记载的事实 |
| 删除 | 83 个文件 / 713,606 字节 | `REMOVALS.json`：blob sha1 + sha256 + crc32 + 字节 + `restoreAt`；每条由构建脚本用 `git show <restoreAt>:<path>` 实测后才登记 |
| 明面收敛 | `docs/` 下 0 个 `handoffs/plans/research/superpowers` 目录；`docs/taskpacks/` 14 个跟踪文件 | `git ls-files` 实读 |
| 投影再生 | 跟踪文件 3,806 → **3,724**；工作区 69.68 MiB；pack 241.69 MiB（>224 WARN，<256 硬预算） | `reports/current/REPO-CLASSIFICATION.json` 等；九类之和 = 3724 = 跟踪文件数 |
| 重钉 | AUTHORITY.md / authority-index.json / HISTORY-FREEZE-RULES.md 本轮两次改字节两次重钉 | `docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json` `revisions[-2..-1]` |

**故意不删**（删了是销毁输入或拆散 bundle，不是清理陈旧料）：
`handoffs/deepseek-r3-20260906/` 17 件 owner 随包提供的 R3 审计输入原件；
`next-agent-prompts/PROMPT-LINEAGE.json`（血统登记表）；按日期 bundle 目录内的交接成员；
authority-index 与账本仍点名的四份包体。

## 4. 防"再次索引旧路径"的机制

- 指引面（`AGENTS.md` / `README.md` / `AUTHORITY.md` / `docs/current/NEXT-AGENT-PROMPT.md`）
  不再出现任何已删文件的路径字面量；由 `verify_task_document_states.py:guidance-paths-resolve`
  与 `scripts/verify_path_refs.py` 双向看守。
- 允许继续点名旧路径的只有四类，且各有理由：被哈希钉死的账本证据行（字节不可改）、由这些行派生的投影索引、
  `authority-index.json` 的 `formerly` 标签、DeepSeek 链脚本里经 `archive_records.read_record()` 解析的
  stop-line 常量，以及 presence 测试里对 recovered 集合的精确 pin。
- 需要原件内容时不手写解析：`scripts/archive_records.py` 按 工作区 → 归档移动 → `REMOVALS.json`
  的 `restoreAt` 三层取字节并回写来源，三层都不到即 `RecordUnavailable`。

## 5. 命令、退出码与读数（本会话实测，均为定向闸口）

| 命令 | 退出码 | 读数 |
| --- | --- | --- |
| `python scripts/verify_path_refs.py` | 0 | `PATH_REF_GATE=PASS checks=10 failed=[]` |
| `python design-lab/scripts/verify_task_document_states.py` | 0 | `TASK_DOC_STATE_GATE=PASS checks=13 failed=none` |
| `python scripts/verify_top_level_authority.py` | 0 | `TOP_AUTHORITY_GATE=PASS checks=10 failed=none` |
| `python scripts/verify_authority_gates.py --zero-spill` | 0 | `AUTHORITY_GATES=PASS gates=7 failed=none` |
| `python scripts/record_import_verify.py --head` | 0 | `RECORD_VERIFY=OK blobs=HEAD`（rows=492，movedTo=3，evolved=9） |
| `python design-lab/scripts/verify_evidence_artifact_presence.py` | 0 | `WARN tracked_broken=0 tracked_drifted=60 recovered=4 relocated=0` |
| `python design-lab/scripts/verify_design_lab.py` | 0 | `VERIFY_DESIGN_LAB=OK total=76 failed=0` |
| `python scripts/run_structure_contracts.py` | 0 | `STRUCTURE_CONTRACTS=PASS tests=31 failures=0 errors=0` |
| `python design-lab/scripts/verify_task_ledger_contract.py` | 0 | `TASK_LEDGER_CONTRACT=OK` |
| `python design-lab/scripts/verify_library_index_consistency.py` | 0 | `PASS shared_inputs=4 shared_roots=2 assets=24` |
| `python design-lab/scripts/update_evidence_binding.py --check` | 0 | `UPDATE_EVIDENCE_BINDING=HISTORICAL_VALID`（非产品通过声明） |
| `python scripts/verify_clean_tree.py` | 0 | `CLEAN_TREE=CLEAN dirty=0 unattributed=0` |
| `python scripts/generate_current_reports.py --check` | 0 | `CURRENT_REPORTS=STALE`（绑定输入未变、HEAD 已前移；不等于产品通过） |
| `python packages/.../check_anti_slop.py design-lab/ --skip-prefixes …`（与 CI 同参） | 0 | `JURY_DETERMINISTIC=OK (human review still required)` |
| `python -m compileall -q design-lab/scripts` | 0 | — |
| `python scripts/verify_archive_record_register.py` | 0 | `RECORD_REGISTER_GATE=PASS`（把登记节反向解析回 git blob 逐条重算：5 行表格 + 5 条完整摘要 + 登记节点名的路径式 token 全部可解析）；**已接入 CI**——`.github/workflows/canonical-verify.yml` 的 `top-authority-gate` 作业第 5 步，`STRUCTURE_CONTRACTS=PASS tests=31` 的可达性合同就是要求它被点名，否则等于交付一个从来不会跑的闸 |
| `python scripts/generate_archive_record_register.py` | 0 | `records=5 ...`（重建登记节；小节清单与计数直接从报告正文读，不再手写，杜绝登记与报告脱节） |
| 三层取回探针（`scripts/archive_records.py:read_record`，样本取自两份记录自身：live / 移动前 / 移动后 / 已删首行 / 已删末行） | 0 | `checked=5 failures=0 removed_rows=83 move_rows=228`，其中 `reports/history/V4_HANDOFF_SUMMARY_20260807.md` 走 `removed-at:<sha>` 层取回 2,327 B |

| 定向 pytest（本会话逐次实跑，未跑全库分片） | 最终 0 | `test_record_import_fidelity + test_current_reporting + test_ledger_schema` → `1 failed, 86 passed`（修好后 fidelity 单独 `4 passed`）；`presence + readback` → `21 passed`；`subject-binding + gate-reachability` → `42 passed`；受影响模块全集 → `2 failed, 143 passed, 24 subtests`（两处失败见 §6.5，修后该模块 `5 passed`） |

### 5.1 后续两批（分析入口 + 侧栏边界）的实测读数

| 命令 | 退出码 | 读数 |
| --- | --- | --- |
| CI `main` run @ `c71e3d21`（全库分片） | 1 | `PYTHON_TESTS_SHARDS_START shards=3 expected_tests=3067`；shard1 `tests=1062 exit=0`、shard2 `tests=1030 exit=0`、shard3 `tests=975 FAIL=1`。CI 只发布计数不发布测试名，所以红因靠本地复现定位（见下） |
| `pytest design-lab/tests/test_contract_bindings.py` | 0 → 修前 1 | 修前 `AssertionError: 93 != 92 : one verdict line, one note per contract row, one per route row`（`test_verdict_line_is_what_the_aggregate_matches`）；把钉住的派工路由清单 59→60 并写明因由后 `35 passed`。账本实读 `route rows = 60`，与闸口自报 `routes=60 dispatched=60` 同向 |
| `pytest design-lab/tests/test_current_reporting.py design-lab/tests/test_projection_freshness.py` | 0 | `68 passed, 13 subtests passed in 237.24s` |
| `pytest design-lab/tests/test_asset_analysis.py` | 0 | `9 passed`（6 单元 + 3 条真起 loopback 服务的 HTTP 实跑） |
| `python design-lab/scripts/verify_browser_e2e_ran.py`（`E2E_REQUIRED=1`） | 0 | `BROWSER_E2E ran=9 skipped=0 failed=0`（加入交替主题那条后为 `ran=10`），六个模块逐个 `skipped=0`。**注意次序**：先在未提交的 bundle 上跑，`test_workbench_ui_audit_gate` 拒绝测量并报 `AUDIT_BLOCKED: apps/workbench/build differs from HEAD`——这是设计如此，提交后再跑才允许出数 |
| `python design-lab/tests/e2e/audit_workbench_overflow.mjs`（经 overflow 门） | 2 → 0 | 修前 `OV_NAV_EDGE_TIGHT 1440px/1280px/1920px: footer hairline 0px under the nav cut line, a group label is half-cut on it`；修后 `OV_OK`，证据 JSON 记 `gap=12 overflow=499 straddling=["nav-group"]` |
| `python scripts/design_debt_baseline.py --check` | 0 | `DESIGN_DEBT_BASELINE=PASS`；`literal_px=534` 在侧栏修复前后同值（新增的是 token 边距，不是字面量） |
| `python design-lab/scripts/verify_contract_bindings.py` | 0 | `VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=60 dispatched=60 bound=21 schema_less=39` |
| `python design-lab/scripts/verify_workbench_route_calls.py` | 0 | `VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=96 routes=58 matched=47 backend_only=11 dynamic=3 special=1` |

**关于全库分片的诚实说明**：本会话起过一次本地 `run_python_tests_all.py --shards 3`，跑到约 19 分钟时已被 CI 的
计数与本地定向复现共同指认到那一条红（`test_verdict_line_is_what_the_aggregate_matches`），于是停止该次运行、
改为按模块复现与验证——**没有**在本地跑完全库分片。全库分片的完整判定来自 CI 那一次（它就是红的来源），
修后判定见 §0 与下一条提交。

**未执行**：真实宿主、真人验收、发布/安装态一律未执行。**手机端不在这一列**——它是 owner
2026-10-19 定的排除项（不是"本轮还没做的冻结项"），把它写成"未执行"会把它留在待办面上。

### 5.2 第三批（桌面端打磨 + 独立全链路走查）的实测读数

| 动作 | 实测证据 |
| --- | --- |
| 侧栏边界缺陷（§6.7） | 修前 `OV_NAV_EDGE_TIGHT 1440/1280/1920 gap=0` 且三处都是分组标签被切在切割线上；修后 `OV_OK`，证据 JSON `gap=12 overflow=499 straddling=["nav-group"]` |
| 一条被测量否证的猜想 | 1440 截图里 8 字标签看似断行剩孤字；实为文本宽 150 px / 可用 211 px，且把 `.nav` 压到 96 px 后 22 项**无一换行**（flex 子项不缩到内容宽以下，失败模式是横向溢出，已由 `CLIPPED/STRAY` 覆盖）。见 §9 |
| 三条"桥没有生产调用方"的过期声明 | 分析入口落地后，plan 页提示已改，但渲染面 `producer`/`next` 与两处面板注释仍说无调用方；全部改述并**重新构建 + 1440 渲染核对**（截图同时独立确认了上面两行：标签单行、切线与页脚边框分离） |
| preflight 路由首次 live HTTP | 新增用例实测 `verdict=INCOMPLETE`（该 fixture 的 PSD 无法检查透明合并，服务不认证自己没打开过的字节）；跨项目读返回 **400**，而同族 export 路由对同一条件返回 **404**——分歧如实记录，不静默统一，因为状态码是页面分支依据 |
| 独立全链路首次单条走查 | 13 跳验收链 `project=201 asset=201 brief=201 direction=201 design-layer=200 analysis=201 jury-verdict=201 jury-readback=200 rights=201 rights-readback=200 candidate=201 review=200 candidate-readback=200`；4 跳交付链 `project=201 native=READBACK bundle=201 preflight=200`。 jury 判定**对着 asset 那一跳返回的 version_id/sha256** 落判，此前 jury fixture 自己往库 publish 版本，"导入的资产能长出一个可判的 version"从未被证明 |
| 走查写出来的两个链事实 | `native_tasks.py:94` 只接受字面量 scope `project-native-test`，所以交付段是受控 E2 而非真实宿主 E3；`NativeTaskError` 包装会吞掉原因，取 `__cause__` 才看到 `scoped caller authorization required` |
| 覆盖确认 | CI 自己的发现器：`total discovered 3071`，chain 模块 3 条全部在列（未被发现的测试等于不跑的测试）；与借体的 5 个模块同跑 `87 passed, 23 subtests` |
| 仍无入口的两段 | 提示词段（`prompt` 在 http_service/cli/shell.ts 三处 0 命中，无模块）与导出段（`export_payload`/`to_v1_projection` 在 `src/` 内 0 调用方，`outbound.transport` 硬编码 `NOT_CONNECTED`）。补它们是产品实施，属 owner 门，本轮不建 |

| 交替主题几何覆盖（补上的盲区） | 溢出审计是唯一只测一个主题的浏览器闸门（对比度测 design-lab/dark + ui2026/light，主题几何扫三种组合，而它握着 CLIPPED/STRAY/TINY/切割线/滚动提示）。播种否证证明这条新用例有牙而非重复：把 `.nav{margin-bottom:0}` 只作用到 `[data-palette=ui2026][data-scheme=light]`，默认主题那条仍 `ok`，新用例在三个宽度上全报 `OV_NAV_EDGE_TIGHT gap=0`——改之前这个 bug 会绿着发出去。恢复后两主题 `Ran 2 tests OK`，整表 `BROWSER_E2E ran=10 skipped=0 failed=0` |
| 云端判定（逐条实读，不替 CI 宣布） | `72950ce2`、`b07a3906`、`6f4a89a4` 三个 head 的 `main` run 均 `OVERALL=success`，各 11 个真实 job success、`Branch light gate` skipped；同 SHA 在开发分支上的 light-gate run 也是 success，但那是 11 job 全 skipped，只说明编译与身份边界，不能当"CI 通过"引用 |

**闸门 × 维度覆盖矩阵**（本轮逐条查 invocation 得出，不是读注释——溢出闸门的注释本来就写着"按主题分级"，而它实际只测一个）：

| 闸门 | 宽度 | 高度 | 主题 |
| --- | --- | --- | --- |
| `test_workbench_overflow_gate` | 1440/1280/1920 | 900（全套几何）+ 620（滚动提示与边界） | design-lab/dark **与** ui2026/light（本轮补） |
| `test_workbench_contrast_gate` | 1440/1920 | 900 | design-lab/dark **与** ui2026/light |
| `test_workbench_theme_geometry_gate` | 按组合 | 900 | 三种组合（design-lab/dark、ui2026/dark、ui2026/light） |
| `test_workbench_theme_affordance_gate` | 单宽 | 900 | 它本身就是"点主题按钮"，天然跨主题 |
| `test_workbench_ui_audit_gate` | 1280/1920 | 900 | **仅默认主题**——它测的溢出/对比/键盘可达/目标尺寸/命名/降级措辞/控制台噪声里，对比与几何已由上面两道按主题覆盖，键盘可达与命名不随色板变；因此本轮不加第二趟（代价约等于把这道 26 scope 的量测翻倍），而是把这条判断记在这里，免得下一轮重新查一遍再得出同样的结论 |

**高度维度本轮补上了**：溢出审计原先只在 900px 高下比几何，620px 那一趟只判滚动提示出不出。同一趟里导航与页脚都在屏幕上，所以顺手把边界也量了——实测 `gap620=12`（1440/1280/1920、两个主题一致，列表溢出 779px）。把阈值从 6 抬到 13 会让闸门 `OV_SPEC_BROKEN`，恢复后两主题重跑仍绿，所以这条比较是活的而不是装饰。**仍未按主题分的只剩 ui_audit 那道**（理由见上表），而 DESIGN.md 第 125 行要求的"尺寸档位逐个截图比较"仍由 `capture_workbench_screenshots.mjs` 的 `VIEWPORT_HEIGHT` 档位承担——截图是人看的，不是闸门判的。

### 5.3 第四批（接口层普查 + 链路收口）的实测读数

| 命令 | 退出码 | 读数 |
| --- | --- | --- |
| `gh run view 39310800333 --repo DTALEX66/DESIGN-LAB --json headBranch,event,conclusion,jobs` | 0 | `BRANCH=main EVENT=push CONC=success jobs=12`：11 个作业 `success`，只有 `Branch light gate` 是 `skipped`（它按设计只在开发分支跑）。这是 `fd5e426e` 的 exact-SHA 判定，也是独立链路那两条腿的收口证据——同一个 SHA 的分支 run 39310790208 是 light gate，不能拿它的"success"当 CI 通过 |
| `PYTHONPATH="design-lab/tests;src" python -m unittest -q test_standalone_chain_http test_contract_bindings` | 0 | `Ran 38 tests ... OK`，逐跳读数原样复现：`CHAIN_HOPS project=201 asset=201 brief=201 direction=201 design-layer=200 analysis=201 jury-verdict=201 jury-readback=200 rights=201 rights-readback=200 candidate=201 review=200 candidate-readback=200`（13 跳）与 `DELIVERY_HOPS project=201 native=READBACK bundle=201 preflight=200`（4 跳） |
| `grep -c "add_parser(" src/design_lab/cli.py` | 0 | 16（脚本/CLI 层实数） |
| `integrations/adapter-registry.json` 条目数 | 0 | 30（原生插件层实数，另有 `ADAPTER_REGISTRY=PASS`、`ADAPTER_MATRIX=PASS matrix=9`、`ADAPTER_LOCATOR_AUDIT=PASS`） |
| `grep -rniE "ui_automation\|controlled\.ui\|accessibility tree\|屏幕坐标" src/ \| wc -l` | 0 | 0——受控 UI 自动化层在 `src/` 内没有任何模块 |

这三条数是替 owner 那句「保留标准通用的接入接口」逐层实测出来的，结论按层分开写，不合并成一句"接入已可用"：官方 API/SDK 层有代码但等级以 E0/E1 为主（ComfyUI 的 E2/E3 证据属 2026-08，未在现树复验）；原生插件层与 CLI 层是实的；**MCP 层只有合同没有服务**（`INERT-CONTRACT-SURVEY-2026-10-08.md` 记 `state=NO_STATE_COUNTERPART`、`route_references=[]`、`table_readers=[]`、`table_writers=[]`）；**受控 UI 自动化层零模块**。后两层要补属产品实施，仍在 `currentExecution` 冻结内。普查结果就地写进 `docs/current/NEXT-AGENT-PROMPT.md` 的开放边界一节。

### 5.4 第五批（桌面端验收尺寸 + 定位句一致性）的实测读数

| 命令 | 退出码 | 读数 |
| --- | --- | --- |
| `powershell -File .project-local/task-runtime/screen-probe.ps1` | 0 | `SCREEN \\.\DISPLAY1 bounds=2048x1152 working=2048x1104 primary=True` + `APPLIED_DPI=120`。结论：浏览器拿到的 CSS 视口宽是 **2048**，2560 只是面板物理宽——验收尺寸因此按 2048 设，而不是按看起来更大的那个数 |
| `python scripts/audit_workbench_ui.py --widths 2560`、`--widths 2048` | 0 | 两档各一趟 `AUDIT_SCOPES 13 violations=0 ok=True`。服务日志里那条 503 与 `ConnectionAbortedError` 属 `disconnect-*` scope 自己注入的断连，不是缺陷 |
| `python -m unittest -q test_workbench_ui_audit_gate`（默认档改为 `1280,1920,2048` 后） | 首趟 1 → 次趟 0 | 首趟红在 `console-error: 1280 Failed to load resource: net::ERR_NO_BUFFER_SPACE`——本机连跑三趟浏览器工装后的套接字缓冲瞬时耗尽，不是产品问题；第二趟 `OK`。**没有给它加重试**：控制台报错就该红，这是闸门在做事 |
| `OV_HEIGHT=1100 / 900 / 750 OV_WIDTHS=1440 python -m unittest -q test_workbench_overflow_gate`（三趟） | 0 | `navEdge overflow` = **299 / 499 / 649**，`gap` 三趟都是 **12**，被切的元素 1100 与 900 是 `nav-group`、**750 是 `button`**。默认档重跑 `Ran 2 tests OK`（162s）。**这一行第一版写错了**：我当时写"clientHeight 由 CSS 定死、边界几何与视口高无关，所以不加第三档"，错因是把短档（620）那一趟的 `hiddenPx=779` 当成两趟的共同读数——而我覆盖的只有名义高度，短档根本没动，两次当然同值。重量之后正确的说法是：溢出量随视口高变化，恒定的只有发丝线与切割线的间距（固定 token 边距，620/750/900/1100 四档实测都是 12）；不加 1100 档是因为它与 900 档切同一个元素、判同一条不变量，而 750 会切到另一个元素，说明现有两档不是摆设 |
| `python -m unittest -q test_workbench_brand_asset` | 0 | `Ran 15 tests OK`，其中 3 条是本轮新增的定位句一致性 |
| `python .project-local/task-runtime/falsify_positioning_line.py` | 0 | `POSITIONING_FALSIFIER moved=4/4`：改掉权威句、少一份落地页副本、把品牌行后半改一个字、以及让 `.brand-line` 提取式失配，四种破坏各自让对应断言变红；第四种还先报"提取式已失效，不要用它下结论"而不是静默通过 |

**为什么补这三条断言**：定位句「专业视觉智能与可复用设计能力系统」同时出现在权威文本、落地页（`/workbench` 的 served 字节，页头与页脚各一次）与侧栏品牌块（为不断词而拆成的两行）三处，此前**没有任何东西把它们绑在一起**——改一处是免费的，产品可以在三个地方对自己说三种话。现在权威是源头、落地页测的是 `workbench.resource()` 真正吐出的字节（安装态 wheel 一并覆盖）、侧栏测两行拼回去是否仍是那句权威话。三处当前实测一致，这条补的是"下次不一致会红"。

### 5.5 第六批（把"文档说的 = 量出来的"补成一条闸门）

本轮两处过期数字都是人眼撞出来的：源码注释还在叙述"12 → 15"（表里已经 19 条），设计契约还写"导航 11 项需 587px、≤720 才溢出"（19 项，且任何桌面高度下都溢出）。仓库里已经有这个机制的先例（`design_debt_baseline.py --check` 就是"债的散文对回实测"），所以补的是同一条机制覆盖剩下没人管的计数。

| 命令 | 退出码 | 读数 |
| --- | --- | --- |
| `python scripts/verify_documented_counts.py --verbose` | 0 | `DOCUMENTED_COUNTS=PASS claims=4 route_views=19 cli=16 adapters=30 routes=58`。四条各有一个只读代码的测量式（`ROUTE_VIEWS` 条目数、`cli.py` 的 `add_parser(`、适配器注册表长度、`http_service.ROUTES` 长度），散文只提供句子，不参与测量 |
| `python -m unittest -q test_documented_counts` | 0 | `Ran 2 tests OK`。第二条把 `DESIGN.md` 的"导航 19 项"改成 18 再跑闸门，实读输出 `FAIL DESIGN.md: prose says ['18'], measurement says 19` 并退出 1；它同时拒绝一种退化情形——若模板已经匹配不到任何句子，测试自己先红（"the claim is unpinned and this falsifier is testing nothing"） |
| `python -m unittest -q test_gate_reachability` | 0 | `Ran 9 tests OK`：新脚本经测试模块进入 Python gate，不需要动工作流文件 |

三个提取式都写成"匹配不到就 `SystemExit`"，因为一个死掉的式子返回 0 会让闸门把"读不到"当成"没有差异"，那正是本轮 §6.3 那条缺陷的同一种错法。

### 5.6 第七批（2048 采集档、jury 读侧证据、计数闸门扩到六条）

| 命令 | 退出码 | 读数 |
| --- | --- | --- |
| `python scripts/capture_workbench_screenshots.py --widths 2048` | 0 | 23 张 @2048×1152。此前该宽度没有档位，会走 `w * 0.62` 兜底算出 1270——一个谁都没有的画幅；已在 `VIEWPORT_HEIGHT` 补上实测的 `2048:1152` |
| 2048 档人工查看 | — | 仪表盘与能力目录逐张看，并**当场否证了自己一次目测错判**：能力目录在宽屏下看着像"表头与单元格逐列错位"，读构造才知道那一屏是单个 `<table>`（表头是 `shell.ts:2563` 的 `TABLE_COLUMNS`，每格 `el('td', …)`），列宽由整列共享，结构上不可能逐行错位。结论：2048 档无缺陷（同档系统性检查已由 ui_audit 判 13 scope `violations=0`） |
| `python -m unittest -q test_standalone_chain_http` | 0 | `Ran 4 tests OK`，链上读数不变（13 跳 + 4 跳）。新增一条证明 `GET /projects/<id>/jury` 的 `reviewable_versions` 会给出 `version:<导入返回的 version_id>` 且 `artifact_sha256` 等于导入摘要——桌面 jury 面板的判定对象确实有来源；此前只证明过"拿导入响应里的 id 能 POST 判定"，那不等于界面列得出来 |
| `python scripts/verify_documented_counts.py --verbose` | 0 | `DOCUMENTED_COUNTS=PASS claims=6`：新增两条把提示词里的"**13 跳验收链** / **4 跳交付链**"对回测试方法体（`self.hop(` 调用数加手工 `hops.append(` 数）。跳数一变，句子立刻对不上——今天加 jury 那条时正是这个数最容易悄悄过期 |
| `python -m unittest -q test_documented_counts test_standalone_chain_http` | 0 | `Ran 6 tests OK`，播种反证仍然红（`prose says ['18'], measurement says 19`） |

### 5.7 第八批（无障碍复核：自动化看不见的部分，以及补上的一条断言）

| 检查 | 读数 | 判读 |
| --- | --- | --- |
| `grep -c "outline:none" apps/workbench/style.css` | 0 | 焦点环没有被抹掉 |
| `grep -c ":focus-visible" apps/workbench/style.css` | 10 | 焦点可见态是成体系的规则而不是零星几处 |
| `grep -c "prefers-reduced-motion"`（CSS / shell） | 1 / 3 | 动效有降级路径（CSS 4 处 `animation:`、20 处 `transition:` 都在其约束内） |
| toast 实现 | `el('div', { class: 'toast', role: 'status', id: 'toast' }, …)`（`shell.ts:5794`） | 播报走 `role="status"`，不是只有视觉变化 |
| 状态词 `lang` | 标签自带 `lang="en"`；`shell.ts:7085` 写明为何不再套一层 `en()`（外层会先被文字检查命中） | 与状态词合同一致，未翻译 |
| 表单标注 | `<label>` 72 处 / `aria-label` 44 处 | 以原生标注为主，ARIA 是补充 |
| **新增**：逐屏标题序列（溢出闸门 `out.headings`） | 23 条路由读数中跳级 **0** 处；唯一无标题的是落地路由 `workbench`（其 h1 在 `#route-view` 之外），作为具名例外 | axe 每屏拒评 9–71 个节点，标题顺序此前没有任何东西在看；现在由 `test_workbench_overflow_gate` 断言，且三条分支（跳级 / 无标题 / 覆盖数掉到 15 以下）都有播种反证证明会红 |
| 本轮人工未做 | 真实读屏软件下的措辞、键盘-only 主路径 | 记为待人工，不写成通过 |

结论：本轮无障碍侧**没有发现需要改产品的缺陷**；产出是一条原来缺失的覆盖（渲染出的标题顺序）与它自己的反证。

### 5.8 第九批（设计债复核：棘轮看不见的"种类"，以及它抓出的一次真回归）

基线闸门数的是"非令牌声明不许增长"，看不见**同一声明被重复多少次**、也看不见内联样式。按种类扫的结果：

| 项 | 实测 | 判读 |
| --- | --- | --- |
| `shell.ts` 内联 `style:` 站点 | 27 处，其中 `margin-top:16px` **14 次**、`display:grid;gap:8px` **6 次**、`display:grid;gap:10px` 2 次、其余 5 个各 1 次 | 20/27 是两个声明的重复，属于"该收成类"而不是"该登记的字面量" |
| 收成 | `.spaced-top{margin-top:var(--uif-space-4)}`、`.grid-stack{display:grid;gap:var(--uif-space-2)}`（style.css 830/831 行，各定义一次） | token 值 16px / 8px 与原内联逐字相同；`literal_px` 由 **534 → 514**，`--check` 立刻以"DESIGN.md §4 没有这句原话"为由拒绝，直到文档改成实测句为止——这正是这条闸门该有的行为 |
| `gap:10px` 那 2 处 | 保留内联 | 10px 不在间距档（4/8/12/16/24/32/40）上，改成 8px 是可见变化而不是重构；要归一需要先决定加哪个 token，那是 owner 侧的选择 |
| `!important` | 7 处，逐条看：`[hidden]`、reduced-motion 块内 3 条、`.error` 颜色（注释写明是 load-bearing） | 都是有意例外，不算债 |
| 色值字面量 | 26 处登记在 `ui-off-palette-colours.json`，`adjudication` 空 | 闸门自己报 `NOTICE PENDING-OWNER-ADJUDICATION`，代理不得填 |

**这次重构制造了一次真实回归，而且是像素比对抓到的**：`.quick-launch{margin-top:0}` 从来没生效过——它唯一的使用处一直挂着内联 `margin-top:16px`，内联优先级压过类规则；把内联换成 `.spaced-top` 之后，这条死声明按源码顺序（它定义在 1479 行，晚于 830 行）开始获胜，把仪表盘那张卡顶到 0。已删除该死声明并在原处写明它曾经是死的，免得有人把它当"面板自己的间距"加回来。

**同时暴露一条闸门灵敏度事实**：带着这个 16px 错位，`test_workbench_overflow_gate`、`test_workbench_ui_audit_gate`、`test_workbench_theme_geometry_gate`、`test_workbench_contrast_gate` 四道（8 个测试）**全绿**——它们看的是溢出、边界、对比度、控件尺寸与命名，不看"某张卡离上一张卡多远"。而像素比对在这里也分不开：数据屏每次采集都换播种项目名，`01-dashboard` 无论对比哪一对都有约 1700 px 差值，与噪声同量级。最终依据是级联本身：删掉那条之后，匹配 `div.panel.quick-launch.spaced-top` 且设置 `margin-top` 的规则只剩 `.spaced-top`，其 token 为 16px，与被替换的内联值逐字相等。修法与验证方式都记下来，是因为"四道浏览器闸门绿"并不能证明一次样式重构没有改变可见结果。

### 5.9 第十批（把层叠冲突做成闸门：同一形状的第二处回归）

§5.8 记了第一处（`.quick-launch{margin-top:0}`）。写闸门去防它复发时，同一形状的第二处当场被抓出来：

| 项 | 实测 |
| --- | --- |
| `.row-card` 的声明 | `display:flex; gap:12px`（style.css:885-897，与 `.list-item` 共用一条规则） |
| `.grid-stack` 的定义位置 | style.css:831 —— **早于** `.row-card`，同特异性 |
| 后果 | 6 张 `.row-card grid-stack` 卡片在折叠后按源码顺序变成 flex/12px，而它们折叠前是内联 grid/8px |
| 四道浏览器闸门 | 带着这处错位**全绿**（8 个测试）——它们不量卡片间距，也不看复合层叠 |
| 像素比对 | 分不开：数据屏任意两次采集都差约 1700 px（播种项目名带时间戳），16px 级别的位移淹没在噪声里 |
| 修法 | 加 `.row-card.grid-stack{display:grid;gap:var(--uif-space-2)}`（特异性 0-2-0，与文件顺序无关）。**没有**采用"把工具类挪到文件末尾"那种做法——那只是把下一次冲突推到更晚的位置 |
| 新闸门 | `scripts/verify_utility_class_conflicts.py`：读样式表与 `shell.ts` 里字面 `class:` 集合，工具类与同元素上的组件类共享属性即红，除非有复合规则显式解决。`UTILITY_CONFLICTS=PASS checked=20 utilities=['grid-stack','spaced-top']` |
| 反证 | `design-lab/tests/test_utility_class_conflicts.py` 三条：当前树绿；**删掉那条复合规则必须回红**并点名 gap 冲突；shell 里没有任何工具类时报 FAIL 而不是 PASS |

**这一批真正的产出不是那 20 处折叠，而是这条事实**：对本项目的工作台而言，"浏览器闸门全绿"不构成"布局未变"的证据。闸门量的是溢出、边界距离、对比度、控件尺寸与命名；卡片之间差 16px 不在任何一条断言里。要么按复合选择器把意图写死（现在这样做），要么给间距本身加断言——后者需要想清楚锚点集合，不在本轮里顺手做。

### 5.10 第十一批（层叠冲突的第二道闸门，以及它自己被抓到的盲区）

§5.9 的静态闸门只读源码，不看渲染结果。这一批补了浏览器里的那道：溢出审计对每个带工具类的元素读 `getComputedStyle`，与它该用的间距 token 逐一比对（`--uif-space-4`=16px、`--uif-space-2`=8px），python 侧断言 `bad == []` 且 token 确实解析出值。

**两道闸门各被种一次真实的 bug，结果不一样，这个差别就是要记的东西**：

| 播种 | 静态闸门 | 浏览器闸门 |
| --- | --- | --- |
| 把死声明 `.quick-launch{margin-top:0}` 追加回样式表末尾 | **红**：`FAIL shell.ts:877 class="panel quick-launch spaced-top": .spaced-top sets margin-top:var(--uif-space-4), but .quick-launch also sets margin-top:0` | **没红**——那张卡在测试 fixture 下不渲染。实读 `seen: {'spaced-top': 9}`，而 shell 里有 14 处 `spaced-top`，即 5 处本轮根本没上屏 |
| 把 `.three-col{margin-top:0}` 追加回末尾（仪表盘确实渲染的站点） | 红 | **红**：`design-lab/dark: 1280:dashboard: a utility class lost the cascade -- .spaced-top expected margin-top:16px but computed 0px alongside .three-col` |

结论写进现行面：**对这一类 bug，不依赖 fixture 数据的静态闸门是主承重的**，浏览器那道只保证"渲染出来的站点"算对了。它每次跑会打一行 `NOTE ... not rendered under this fixture: ['grid-stack']`，把盲区说出来而不是静默通过。播种后 `git diff` 对 `style.css` 为 0 行，两处注入都已还原。

### 5.11 三份信封补上 schema：契约补齐，以及一处被自己挪坏的指针

前几批把三段解冻面接完之后，留下的 named debt 是**三份自己写了 `schemaVersion`、却没有任何 schema 描述其形状的信封**：`GET /api/models`（`design-lab/model-catalog/v1`）、`GET …/model-selection`（`design-lab/model-selection-readback/v1`）、`GET …/knowledge-candidates/<id>/export`（当时只写 `status`，连版本都没有）。第三批那轮账本曾经试图把 v2 schema 直接绑到导出信封上，被闸门以 `ROUTE_VERSION_UNBOUND` 判红——v2 的 const 是 `…/candidate/v2`，绑上去就是在替一个没人检查的形状背书。这一批改的就是那一笔：先让信封写自己的版本（`knowledge_review.py` 新增 `EXPORT_VERSION`，导出体第一键变为 `"schemaVersion"`），再写 schema，再喂 live 载荷，账本三行同时翻成 `BOUND_SCHEMA`。三件事一次做完，因为"schema 存在但没人绑"与"账本说绑了但没载荷"都是这一面存在要拒绝的半态。

**实测读数**（定向闸门，全量由 CI 在同一 SHA 上重跑）：

| 面 | 改前 | 改后（同一提交内实测） |
| --- | --- | --- |
| 账本路由 kinds | `BOUND_SCHEMA` 23 / `SCHEMA_LESS` 43 | `BOUND_SCHEMA` 26 / `SCHEMA_LESS` 40（`routes=66` 未变） |
| 载荷闸门绑定 | `bindings=7` | `VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=10 failures=0` |
| 新增三条的比对量 | — | model-catalog `cases=1 locations=30`；model-selection-readback `cases=3 locations=9`；candidate-export `cases=1 locations=9` |
| 未付的版本债清单 | 7 条 | 5 条（`test_contract_bindings.py` 的钉死清单，逐项记日期与原因） |

30 这个数字是可核对的：根节点 1 + `sources`、`hardware`、`counts`、`counts.placement`、`join`、`selection`
六个容器节点 = 7，再加 14 条模型行与 9 条端点行。它同时也是"这份 schema 真的走进了每一行"的证据——
只比 `$` 一层的 schema 只会给出 1（`policy` 是字符串数组，不产生对象节点）。

**新绑定的两条播种，各自红在它该红的原因上**（写在 `design-lab/tests/test_route_payload_contracts.py`，不碰出厂文件）：

| 播种 | 结果 |
| --- | --- |
| 把 `counts.qualified_local` 保持 0，而把第一条模型行的 `radar_state` 改成 `QUALIFIED_LOCAL` | **红**：`SCHEMA_VIOLATION … models/0/radar_state`——目录的 fail-closed 计数不是散文，是断言。这条不变式是 `#/models` 那一页唯一的防呆：注册表没记合格，页面就不许长出合格的样子 |
| 从读回信封 schema 里删掉 `state`（closed 对象） | **红 ×3**：`UNDECLARED_BY_SCHEMA ['state']`，三个真实载荷各一次——路由发了 schema 不声明的字段 |

另外补了可达性断言：`$.selection#oneOf`、`$.history[0]`、`$.export`、`$.v1_projection`、`$.provenance` 必须真的被下探。这三份 schema 都刻意 `$ref` 记录本身（存下来的选择、v2 的 `$defs/export`、v1 投影）而不是重述形状，$ref 若没被跟进，"引用"就只是措辞。

**自己制造并被闸门当场抓住的一处**：插入 `EXPORT_VERSION` 让 `knowledge_review.py` 整体下移一行，账本里另一条**与本批无关**的读回行指针 `src/design_lab/knowledge_review.py:316` 于是指到了 `return {` 上，`VERIFY_CONTRACT_BINDINGS=FAIL` 原话是 `EMITTER_POINTER_NOT_THE_VERSION 'src/design_lab/knowledge_review.py:316' holds 'return {' … the line is decoration`。指针会随文档悄悄腐烂，这条闸门只读文件半边的指针、却要求行半边也认账，所以一次 +1 行的编辑就足够让它红。已重测为 `:317` 并重跑绿。

**一处刻意的收窄，写进 schema 的 `$comment` 而不是留成暗坑**：目录的 `placement` 只允许直方图真正计数的三个词（`local`/`huggingface`/`vendor`），而雷达自己的 schema 的 `source.kind` 枚举还多一个 `modelscope`。今天 14 条里没有该 kind，但一条 `modelscope` 记录会让 `counts.placement` 之和少于 `counts.models`，并让选择该模型时撞上一份 schema 的枚举。所以这个差被 `design-lab/tests/test_model_catalog.py:65`（每行的 placement 必须落在词表内）先抓住，扩词汇要求 catalog schema、`model-selection-v1.schema.json` 与状态库的 `CHECK` 三处一起动。

**仍未付的 5 条**：Adobe 两个 job-spec 债（`…/tasks/(native-job-…)/patch`、`…/native-plans`）与 rights / research / native-runtime 三份读回。`POST …/model-selection/choose` 留在 `SCHEMA_LESS` 是有意的：它回的是操作收据，收据本身不写版本，而里面的选择文档是被 `model-selection-v1.schema.json` 绑住的。

**上一条批次的 CI 红，是这一批顺手补的，也是本轮最该记的一条**：`b28aa57f` 在 main 上的 Canonical Verify 唯一失败项是 `test_backup_watches_written_tables.CoverageTests.test_every_written_table_is_watched_by_the_proof`，实读 `['model_selection'] != []`。上一批新增 `model_selection` 表时，本地 `VERIFY_DESIGN_LAB=OK total=76 failed=0` 与四条浏览器闸门全绿——**因为那 76 项是 `verify_*.py` 验证器，不含单元测试；这条断言住在测试里，只有 CI 的 "Python unit tests (sharded)" 那一步会跑**。修法按测试自己的指示来：把 `('model_selection', 'rowid')` 加进 `project_backup.py` 的 `COUNTER_QUERIES`（追加式选择表没有写者租约，静默证明看不见它就等于"备份窗口吞掉一次决定还宣称 PROVED_QUIESCENT"），并写明日期与理由；`WITHOUT ROWID` 那条同时复核——复合主键 `(project_id, revision)` 仍是 rowid 表，计数器可用。

这不是新缺陷，是同一类缺陷的**第二次**：那条测试的文件头就写着"一份人工判定在备份窗口里落地而无人看见，直到 601a6422；这道测试是为了让它不能再安静地发生"。这次它做到了——只是它说话的地方不在我这一轮的量法里。写下来的规则：**加表就是加消费者**，DDL 变化之后必须至少跑 `test_backup_watches_written_tables`，或直接跑分片全量；定向闸门绿不等于契约绿。播种核对：还原 `COUNTER_QUERIES` 那一行后该测试重新变红，读数仍是 `['model_selection']`。

### 5.12 「不使用」终于成为一个选项：两个编号的三态在浏览器里被看见

owner 那句话的前半句早就落地了——`#/knowledge` 的创建表单里一直有 `job_id` / `operation_id` 两个可填写位置，写入合同也早就把两件事分开：空白 400 并点名是哪个字段，字面量 `UNUSED` 被存下、读回报成 `EXPLICITLY_UNUSED`。缺的是后半句：**没有那个"选择用没用"的控件**，于是"这次确实没有编号"只能靠操作者背一个魔法字符串来表达。这一批改的就是那半句。

**做了什么**：两个编号各自先选「来处」——`我来填写` / `不使用（发送字面量 UNUSED）`，默认空，未选就本地拒绝并说明这是"没选"。选「不使用」时填写框**只禁用、不清空**；框里还有字时报自己的冲突（`… 冲突：已选择「不使用」，但填写框里还有内容…页面不会替你丢掉已经打进去的东西`），而不是静默丢弃。三个可达状态各一句话，没有一条是装饰。

**浏览器里的实测**（一次性 scratch 探针，真服务 + 真 Chromium + 已出厂的 bundle；探针脚本在 `.project-local/tmp/` 下，不入库）：

| 量 | 读数 |
| --- | --- |
| 两个新 select 的盒子 | `2048x1152` 视口内 `w=1598 h=42`，`overflowsParent=false`、`clippedByParent=false`、`fontSize=12px`（与同行其余控件同规格） |
| 可及名 | `labels=1` 各一条（`job_id 的来处` / `operation_id 的来处`），三个 option 文案原样上屏 |
| 选「不使用」后 | `#knowledge-operation` 变为 `disabled=true` 且 `value="op-keep-me"`——Playwright 拒绝往禁用框里写字，这本身就是"不清空"的证据 |
| 本地拒绝 | `未提交：job_id 为空：选了「我来填写」就得真的填；这次确实没有编号请改选「不使用」。服务端未写入任何候选。` |
| 真写入 | 一条候选落地：`已记录一条候选；它仍是 PENDING_HUMAN_APPROVAL…`，读回 `共 1 条候选 · 待裁决 1 … 不可导出`，出站仍是 `NOT_CONNECTED → ArcheAxis；sent_count=0` |
| 控制台 | `errors: []` |

**闸门侧**：`appshell.mjs` ㉒ 的本地拒绝序列从两条扩到六条（没选 / 填写却空 / 不使用却非空），并新增一段外发体断言——`source.operation_id === "UNUSED"` 且同一表单里填写中的 `job_id` 原样带走，证明字面量上线而不是界面装饰。UI 审计在 `1280/1920/2048` 三档 `Ran 1 test OK`（单跑 2048 时 `AUDIT_SCOPES 15 violations=0`），溢出 3 OK、对比度 3 OK、served-bundle 4 OK；bundle 重建为 432.31 kB 后一并提交——UI 审计在 `apps/workbench/build` 与 HEAD 不一致时直接 `AUDIT_BLOCKED` 拒绝测量，这个顺序本轮又被迫走对了一次。

**一处值得记的读法**：探针第一次跑炸在自己的 `node.options`（`<input>` 没有 `options`），第二次炸在 Playwright 拒绝填禁用框——两次"失败"都是功能在起作用，而不是缺陷。把禁用做成"锁住可见内容"而不是"清空并隐藏"，正是为了让操作者随时能改主意而不丢输入。

### 5.13 导出出口终于有人能按到，以及按下去之后发现的一个重名版本

§5.11 把导出信封绑上了 schema，但 `apps/workbench/shell.ts` 只调 knowledge-candidates 的读回、审阅与撤销——**没有导出**。也就是说"可寻址"停在 HTTP/CLI 两级，操作者手上那台界面还差一级。这一批补那一级：每条候选一行一个 `读回导出文档` 按钮，`export_ready=false` 的行是禁用的且按钮文字自己说明"本条被合同阻止"；面板渲染信封版本、两份投影、编号回显（`USER_SUPPLIED` / `EXPLICITLY_UNUSED` 分开）、freshness、出站三事实与 `does_not_say` 逐句。按钮文字带"不发送"三个字，因为一个只写「导出」的控件会被读成已经交付。

**浏览器实测**（真服务 + 真 Chromium + 出厂 bundle，2048×1152）：创建 → 具名批准 → 同一行的按钮从 `disabled:true` 变 `disabled:false`、文字从"本条被合同阻止"变"读回导出文档（不发送）"→ 点下去发的是 GET，面板读数原样为

```
CANDIDATE_EXPORT 信封 design-lab/assurance-knowledge-candidate-export-envelope/v1 · kc-ab21ca7f037708 · 第 2 版
v1 投影：design-lab/candidate-knowledge/v1 source_id job-export-probe:UNUSED
编号回显：job_id job-export-probe（USER_SUPPLIED）· operation_id UNUSED（EXPLICITLY_UNUSED）
出站：NOT_CONNECTED；sent_count=0；bytes=878
```

`errors: []`、`overflow: false`；UI 审计三档宽度 `AUDIT_SCOPES 45 violations=0`（第一次跑在 2048 撞到一个 `net::ERR_NO_BUFFER_SPACE` 控制台错误，与 §5.7 记过的那次同源，重跑单进程即绿）。

**这一屏顺带抓出一个 §5.11 自己造的缺陷**：信封的 `schemaVersion` 当时取名 `design-lab/assurance-knowledge-candidate-export/v1`——而那正是 `knowledge_feedback.EXPORT_VERSION` 从很久以前起就给**被包裹的那份 v2 导出文档**用的字符串。一个版本名，两种形状：读回顶层字段的人会把信封的合同套在被包文档上（键集合不同），反之亦然。闸门抓不到它，因为每一侧各自自洽；是渲染出来的面板把两个版本并排打在屏幕上才看出重名。修法是把**新的一方**改名（信封 → `...-export-envelope/v1`，文件与 `$id` 同改），因为被叫错的一方不能是已经出厂、被三处测试与 CLI 断言的那一个。

顺手把这类缺陷变成机器可见的：`test_contract_bindings.py` 新增一条清单式断言，扫全树 `schemaVersion` const（含 `$defs`），**同名不同形即红**，现存三对合法重名逐对写明理由（同一合同被自己的 `$defs` 与描述它的文件各说一次）。清单不是地板：新重名要红到有人说明为什么两者是同一份合同，说明完失效了也要从清单里删掉。

**上面那段浏览器证据是 scratch 探针，不能从克隆里重跑**——所以这一段现在住进了出厂链路：`design-lab/tests/e2e/browser_design_layer_e2e.mjs` 的链条多出第 13 段，创建→具名批准→断言按钮从 `disabled` 变可用→点下去→断言面板里同时出现 `…-export-envelope/v1`（信封）与 `…-export/v1`（被包的 v2 文档）与 `design-lab/candidate-knowledge/v1`（v1 投影）、`job-e2e-export:UNUSED`、`USER_SUPPLIED`/`EXPLICITLY_UNUSED`、`NOT_CONNECTED`/`sent_count=0`/`bytes=`，并且断言屏上**没有**「已发送 / 发送成功 / delivered」。这一段落进链路时自己撞了两次：先是在旧 DOM 上等 `visible`（按钮在重载前就在屏幕上，读到的是过期状态），再是把被包文档的版本号断言成了 `…/candidate/v2`——真实读数证明 `…-export/v1` 一直属于被包文档，重名的是我新加的信封那一侧。两次都是这条链该抓的东西，现在它每次都抓。

### 5.14 第十二批（外部审计包核验 + 现行面三处过期现状句）

owner 发来 `DESIGN-LAB_独立闭环审计包_20261021.zip`（19 成员，`sha256sum -c SHA256SUMS.txt` 全 OK，包内审计 SHA 与 live `main` 同号）。**8 条断言逐条对回当前字节，全部成立**，因此本批不重审、只修被它抓到的现状面：DL-01 `model.executed` 恒 false（`src/design_lab/prompt_intelligence.py:199`、`:312`）、DL-02 无 prompt/analysis/result 表（`grep CREATE TABLE src/design_lab/` 12 处命中里 0 处是结果表）且 `apps/workbench/shell.ts:8278` 自己写明"服务端不持久化这份文档"、DL-03 审阅只认 human（`src/design_lab/knowledge_review.py:426`）、DL-06 `shell.ts` 8975 行、IF-01 `schemas=32 binding=2 routes=66 bound=26 schema_less=40`、OSS-01 `records=6 mapped=2 consumed=0`。

**DL-05 是唯一一条"文档落后于代码"的，也就是本批的活**：`docs/current/PRODUCT_DEFINITION.md` 第 6 行仍写导出「2026-10-20 已落地，界面按钮仍未接」，而 `#/records` 的知识面板与每行读回按钮已在 §5.13 落地并进厂；`docs/current/ROADMAP.md` R2 仍写「已规划，未执行」，而验收链 18 跳 + 交付链 4 跳每一跳都有 live 入口。两处改成实测分轴读数，并把 owner 同日三条裁定写进现行面：**推理执行不接**（只做契约与错误路径）、**验收与外发都保持 human-only**（可以拆存储与状态词，不拆"谁能验收"）、**导出保持只读回**（按钮文字里的"不发送"是有意的）。

**自己撞出来的第二处过期句在本文件自己身上**：§9 那条"写进文档的数字现在有闸门了"还写着「当前 4 条」并举 `导航 19 项 / CLI 子命令 16 / HTTP 路由 58`。闸门看不见它——`verify_documented_counts.py` 比对的是它自己 CLAIMS 里的模板串，不是这句对白话的举例——所以它是**人眼复核撞出来的**，不是门抓出来的。现改写为实测 `claims=11`：`route_views=21`、`cli=24`、`adapters=30`、`routes=64`、18 跳 / 4 跳两条链、以及「其余 34 项仍 FROZEN_DEFERRED」这一句在五份权威件上的逐字复述。教训记成一句：**修正句本身也是新断言**，写之前先跑那条检查。

**批次序列实跑**（Record 那一步不是可选项）：`record_import_verify.py --head` 在改前只报两行 NOTE，改后如实报出 `WORKTREE-MISMATCH docs/current/PRODUCT_DEFINITION.md`（声明 `crc=efe38284 size=11466`，实测 `e3728ae2 / 12288`）与 `ROADMAP.md`（`4d2ef63b / 9564` 对 `33926668 / 9879`），走 `declare_record_evolution.py` 把两行绑到真实提交 `442cc71b`，回读 `RECORD_VERIFY=OK rows=492 worktree_verified=479 mapped_copies_verified=220 blob_eol_only=12`，单测 `test_record_import_fidelity` 4 项 OK。`DOCUMENTED_COUNTS=PASS claims=11`、`PATH_REF_GATE=PASS checks=10`。本批**没有**动产品代码、账本与 schema，所以 34 项 `FROZEN_DEFERRED` 与钉住的六份权威件字节一字未改。

**本批自己造成的缺陷，按 §6.8 同一条形状又犯了一次**：插入 §5.14 时把锚点定在下一节的标题行 `## 6. 本轮暴露并修掉的六个缺陷` 上，替换后那一行被吃掉，六个缺陷的正文变成无题悬空。当场用 `grep "^## 6"` 发现并补回，净差异回到 +12/−0。也就是说 §6.8 记过的教训（**never anchor an insert on the neighbour's own line prefix**）在这轮之前只是被写下、没被执行；本批把它当作插入纪律复检的一条固定动作：改 markdown 结构后必须 `git diff --numstat` 看删除数，删除数不为 0 而本意是纯新增，就是锚点吃掉了邻居。

### 5.15 第十三批（三份读回债付掉，以及我自己的 schema 被自己种的红）

`schema_less=40` 里的三条读回还清：GET `…/rights`、GET `…/research`、GET `…/native-runtime`。做法仍是那一条配方，不留半态——schema + live 载荷用例 + 账本行翻 `BOUND_SCHEMA` 并重测 emitter 行号 + 测试钉死清单同步。三条 envelope 都**先取真字节再写文档**：`rights` 用三个真项目（一份 APPROVED＝CLEARED、一份 APPROVED＋DENIED＝NOT_REVIEWED 且有真实 `unapproved_scopes`、一份没人填过），`research` 用一条被 supersede 的真链加一份空账本，`native-runtime` 用**同一路由读两次**——先在没有任何 native 表时读（五段全 ABSENT、五个计数全 null），再在播种一条持锁 attempt 链之后读（五段全 PRESENT 且各自带真行）。emitter 行号是从源文件重算出来的，不是抄的：`rights_review.py:101→48`、`research_review.py:94→40`、`native_runtime.py:31→31`，取的都是 `_READBACK_VERSION = '<version>'` 那一行。被包的记录一律 `$ref` 不重述：rights 决定引 `schemas/contracts/rights-decision.schema.json`，research 结论引 `schemas/research-finding.schema.json`；为此 `registry()` 现在第二轮装载 `contracts/`，且只登记没人占用的 `$id`（全库 127 个 `$id` 实测 0 冲突），所以既有绑定的解析结果一字未变。

**读数**：`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=13 failures=0`（rights 3 例 10 处对象位、research 2 例 5 处、runtime 2 例 14 处）；`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=66 dispatched=66 bound=29 schema_less=37`；单测 `test_contract_bindings` 36 项 OK、`test_route_payload_contracts` 26 项 OK。

**我自己种出来的第一条红，是真窟窿**。我给 runtime 的计数写成 `["integer","null"]` 就以为锁住了 absent/present；把 ABSENT 项目的 `hosts_held` 从 null 改成 0 种下去，闸门一声不响。也就是说这份 schema 当时允许"这台服务从没跑过原生 attempt"被读成"没有主机被占"——恰好是这条路由存在的理由。修法是八条 if/then 把每个计数段与其表的 `table` 值双向锁死（ABSENT ⇒ 该计数必须是 null，PRESENT ⇒ 必须是 integer），种的那条假话随即被 `SCHEMA_VIOLATION` 判红，并且这条播种现在常驻在出厂测试里，不再是我手下的临时探针。教训与 §6 那几条同形：**属性类型相同不等于关系被绑定**。

**第二条红是覆盖面的，不是产品的**：`test_every_family_is_covered_by_its_own_real_cases` 的 `expected` 字典只列出它当时想到的绑定，`brief-readback` 与 `evidence-projection` 从来不在清单里——我新增三条后把断言改成"清单必须与 `build_bindings()` 全集相等"，第一次跑就报出这两个历史缺口。一个只证明自己列举过的总体的闸门，加不加新面都一样绿；现在漏列即红。

**Adobe 两条为什么仍然挂着（不是忘了，是不肯用假付款换计数）**：`POST …/native-plans` 与 `POST …/tasks/(native-job-…)/patch` 声明的 `design-lab/photoshop-native-job/v1`、`design-lab/adobe-patch-job/v1`、`design-lab/photoshop-patch-job/v1` 都不是本服务写出的 envelope——实测 `POST …/native-plans` 的响应是 native_submission 读回，作业文档只在 adapter 内部构造（`photoshop_com.py:121-157` 手写键集、路径审批、画布预算、checkpoint 头校验）。因此补一份没人装载的 schema 文件正是这块账本点名要禁的事（同一账本对 `adobe-host-job/v1` 的判词就是"有文件但没有 src/ 模块读它，所以它不校验任何东西"）。诚实的付法是让那两个 adapter 边界装载 schema，属产品代码改动，且本机不做真实宿主 E3；记在此处而不是顺手改成 `BOUND_SCHEMA`。

### 5.16 第十四批（提示词结果落库：把"逐跳绿灯"改成"一条产物身份贯穿"）

审计闭环表里最硬的一条是"结果保存与版本＝缺关键一段"：两条提示词路由产出一份完整带版本文档之后就把它丢了，`apps/workbench/shell.ts:8278` 的现行注释自己写着"服务端不持久化这份文档"，所以 18 跳链证明的只是**同一台服务器上多个接口能顺序调用**，不是**同一份专业产物走过了分析→验收→留存**。本批补这一刀，全程不留半态。

**落了什么**（`git ls-files` 与 `grep` 实测，不是计划）：新表两张（`design-lab/schemas/state/design-lab-state-prompt-results-v1.sql`：`prompt_result` 追加式、`prompt_result_review` 追加式，`reviewer_kind` 在**表上**被 CHECK 钉成 `'human'`，并对 `(project_id, result_id)` 建复合外键——签名不能指向一条不存在或不属于本项目的结果，这不是约定而是不可表示）；两张表都拒绝 UPDATE/DELETE（触发器），与 model_selection/research/rights/jury 同一血统；`src/design_lab/prompt_results.py` 在写入前用 `interop.load_schema` 对三份新合同校验；`POST …/prompts` 与 `POST …/assets/<id>/prompt-reversal` 现在**先落库再回答**，落库失败就是这一跳的回答（代理不许返回 201 却什么都没留下）；新读回 `GET …/prompt-results` 与新签署 `POST …/prompt-results/<id>/review`。响应体一字未改——两份 prompt 合同是闭合键集，把"存了第几版"塞进去会让文档合同变成 envelope 的附件，存储事实改由读回路由披露。**记账与闸门同批跟上**：账本 `routes 66→68`、`bound 29→31`，两条新路由都是 BOUND_SCHEMA 且 emitter 行号从源文件重算；`verify_workbench_route_calls.py` 的 `BACKEND_ONLY` 收了两条带"应在面板落地时删除"的过期理由（本批不动界面，界面是下一刀）；`project_backup.COUNTER_QUERIES` 加两张表并由 `test_backup_watches_written_tables`（5 项 OK）证明写入面不再对它们失明。

**贯穿的证据**：`test_standalone_chain_http.py` 的验收链由 18 跳变 **20 跳**——新增 `prompt-results=200`（两份文档都在库里，存下的 `content_sha256` 等于产生它那一跳发布的 `document_sha256`，且新产物读回为 UNREVIEWED）与 `prompt-accept=201`（具名人工签署，签名引用的摘要=该行摘要）。第 17 跳的知识候选不再 `from test_knowledge_http import candidate` 原样搬运无关固定件：它的 `evidence_sha256` 取自本次被签署的组合，两个编号用字面量 `UNUSED`，导出段随之回显 `provenance.job_id=UNUSED / job_id_state=EXPLICITLY_UNUSED / v1_projection.source_id=UNUSED:UNUSED`。`test_prompt_results.py` 18 项把"存的就是给你看的字节"、同 id 不同摘要＝409 碰撞、`executed=true` 不可入库、无来源不可入库、Agent 签署 400 且理由里点名 2026-10-21 裁定、跨项目签名 404、直接 SQL 也改不动删不掉、以及"有一行读不出来"必须报 `unreadable_count` 而不是假装没有产物。

**读数**：`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=14 failures=0`（prompt-result-readback 3 例 91 处对象位——被包文档按 `$ref` 拉到自己的合同上比，不是在本文件里重述）；`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 routes=68 dispatched=68 bound=31 schema_less=37`；`VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=107 routes=66 matched=53 backend_only=13`；`DOCUMENTED_COUNTS=PASS claims=11 routes=66`（"20 跳验收链 / HTTP 路由 66 = 37 GET + 29 POST"两句现值由闸门对回代码）。单测定向全绿：prompt_results 18、standalone_chain 4、contract_bindings 36、route_payload 26、backup_watches 5。

**三件自己造出来的东西，都写在这里。** 第一件是**闸门的报错路径自己崩了**：`scripts/verify_documented_counts.py` 在发现某句过期时把模板当正则用，而 `'**{n} 跳验收链**'` 以 `**` 开头是非法模式——我把跳数从 18 改成 20 之前，它本该报"这句过期"，实际抛的是 `re.PatternError: nothing to repeat`。一个只在失败时崩的仪器等于把失败藏起来；现在先 `re.escape` 再替换转义后的占位符。第二件是**我差点把已经说对的行改错**：审计包正文把 PDF/UA-1 写成 "ISO 19005-1"（19005-1 是 PDF/A-1），而仓库登记件里写的本来就是正确的 `ISO 14289-1`——按审计去"修"就会把对的改成错的；已把这条差异记进项目记忆并保留 C 档未核验状态。第三件**是 §6.8 与 §5.14 已经点名过的那个形状，我在同一批里又犯了一次**：插入 §5.16 时 again 把锚点定在下一节标题行上，`## 6.` 再次被吃掉，`git diff --numstat` 报 `+14/−1` 才暴露。区别只在于这次是我明知故犯——§5.14 里我自己写了"改 markdown 结构后必须看删除数"，而这次我在写完 §5.16 后先去跑别的检查，没有立刻看 numstat。**教训的具体形状因此变了**：不是"要知道这条规则"，而是"结构编辑的下一步必须是 `grep '^## 6\.'` 与 numstat，不许插入别的动作"。补回后净差异 `+14/−0`。

**一件没做的事，说清楚为什么不做**：本机分片全量（`run_python_tests_all.py --shards 3 --jobs 1`）跑到一半被我主动停掉，不是失败——本仓库的既有记录写明本机沙箱跑不出干净聚合（safe-delete shim 中途 `SystemExit`、Windows 造不出锁的用例），而 `git commit` 会移动 HEAD，让 `test_projection_freshness` 在运行中报出我无法与真问题区分的红。权威判定由该精确 SHA 的 CI `PYTHON_TESTS_UNION` 给出；本批的本地信号是那五个定向套件与上面三道闸的实测读数。

**收尾序列里被闸门抓出的第三件事：我刷新了契约普查，却漏了契约图。** `verify_design_lab` 的 76 项里 `verify_projection_freshness` 报 `FRESHNESS-DRIFT reports/current/CONTRACT-GRAPH.json — fields changed since generation: ['declared_tables']`：两张新表进了 `declared_tables`，而 `scripts/generate_current_reports.py` 不生产那份投影，它由 `scripts/verify_contract_graph.py` 自己写。这条红是**闸门的正确判决**，不是噪声——工作树静止、聚合闸自跑、只有一项红，红里点名了变化的字段。修法是重跑该脚本（`CONTRACT_GRAPH=NO_BROKEN_LINK concepts=11 complete=11 breaks=0`，diff 里恰好是两行新表指向新的 state SQL），再重钉一次投影。教训形状：**普查与图是两份派生件，加表要各刷一次**，`generate_current_reports.py` 不代表所有派生面已经跟上。


### 5.17 第十五批（规范出处第二轮取证：两条仍取不到，一条被我自己写错过）

owner 的要求是"按网上最专业的先收入库里，落地我自行测试"，登记件的价值全在出处诚实。第二轮用只读子智能体重跑，每条记录实际 URL、HTTP 结果与页面原话。

**结论是两条仍是 UNKNOWN，而且这次把"为什么取不到"写成了可复算的清单。** PDF/UA-1：iso.org 的 `/standard/71374`、`/38369`、`/64599` 与 `/obp/ui` 一律 **403**（整站拦非浏览器客户端），pdfa.org 根页与三条子路径仍 403，本轮新试的三条国家标准渠道 `webstore.ansi.org` **403**、`knowledge.bsigroup.com` **404 "Product not found"**、DIN webstore 连接失败——版次不补、不猜，C 档保留。IEC 61966-2-1：`webstore.iec.ch/en/publication/78` 这轮直接读到页面自己印的 "CISPR 25:2008 … Withdrawn (2016-10-27) … Superseded by CISPR 25:2021"，确认那个编号从来不是 sRGB；IEC 检索面 404。新取到的可打开侧页是 ICC 的色彩编码登记 `registry.color.org/rgb-registry/srgb`，原话 Reference "sRGB"、Def "IEC 61966-2-1:1999"、"see Amendment 1"、"Updated April 2015"，并写明该国际标准"available through National Standards Bodies"——按**只可引用**登记，不当作 IEC 出版记录。

**三家设计语言的版本面本轮被实测否证了一次**：登记件第四节原先写着"Apple 的 `.../tutorials/data/design/human-interface-guidelines.json` 实测可用"，而那一族 JSON 现在**全部 404**；可打开的是纯 Markdown 姊妹页 `…/human-interface-guidelines.md`，它只给 frontmatter `"metadataVersion" : "0.1.0"` 与 "Copyright © 2026 Apple Inc."，**没有任何编辑日期**——0.1.0 是内容元数据的 schema 标记，登记里明确写了它不是 HIG 版本。Material 侧 `m3.material.io/sitemap.xml` 给出 `<lastmod>`（首页 2026-07-08、/blog 2026-10-06），登记为"站点最后修改日，不是规范版本"；Fluent 侧 /whats-new 404、/get-started/whatisnew 自述无带日期条目，页面上唯一版本串是 "DOMPurify version is 3.4.15"——那是随页打包的净化库，登记件里专门写了一行**不得把它当 Fluent 版本**，因为这类误认一旦写进登记就会被后来者当出处。

**顺带纠正一处外部误记，而不是照它改**：随包审计把 PDF/UA-1 写成 "ISO 19005-1"（19005-1 是 PDF/A-1），仓库这一行本来就是 `ISO 14289-1`。按审计措辞去"修"会把对的改成错的，所以只在登记里记下这个差异。`ACCESSIBILITY_BASELINE.md` 的 PDF/UA 那条也按审计要求处理清楚了：它是本项目自己的**做法**（分剖面记录 + 附校验器证据），不需要出版方出处；需要出处的是"符合 ISO 14289-1:YYYY"这类带版次断言——已在原位标注取证前不得这样写。

**本批只动 `packages/capabilities/standards/**` 与本登记件**，不碰产品代码，也**没有新增判据**：现行对比度判据仍是 WCAG 2.2 AA，APCA 仍是 B 档行业动向记录，改阈值要 owner 裁定。

### 5.18 第十六批（B3 桌面半：面板改成能签字，浏览器链把这件事写进回执）

§5.16 落了存储与路由，页面还写着"两条都不落库"。这批把桌面端接上：`apps/workbench/shell.ts` 新增结果面板（修订 / 类型 / 身份尾号 / 摘要尾号 / 生成时间 / 签署状态），`executed` 仍为真时单独点出，签字表单固定 `reviewer_kind:'human'`，裁决人没署名就在本页拒发，不发请求。owner 2026-10-21 的三条裁定都在界面上可见：不落模型执行、不外发、只读回。

实跑读数（本机，2026-10-21/22）：`npx tsc --noEmit` 无输出；`npm run test:unit` 出 "APPSHELL REGRESSION: all checks passed" 与 "shape-notice coverage: all bindings reported"；浏览器链 `E2E_REQUIRED=1` → `Ran 2 tests … OK`，回执 `"result": "PASS"`、`consoleErrors: 0`、`bundleSha256 10df5e3a01a713959914009adc06d3b83d9db9ee58b27d6145ec7a338e27ace7`。链里第 14 节走的是真页面：选中未被取代的 brief → 点生成 → 等 `option` 值匹配 `^(prompt|reversal)-[0-9a-f]{32}$` → 逐行断言"没人签过/UNREVIEWED" → 匿名签字被本地拒 → 署名后读回 ACCEPTED 与 `E2E Reviewer` → 面板不得出现 `已发送|发送成功|delivered|模型已执行`。

**这两轮把证据从 stdout 搬进了回执。** 子进程 stdout 被 Python 包装器在成功时吞掉，直接跑 mjs 又只会得到 `E2E_CONFIG_MISSING`，所以"链跑过第 14 节"原本只能靠人眼看日志。现在 `browser-e2e-summary.json` 的 `scenario` 里多一条 `prompt-result-compose-store-sign`，并带 `promptLoop`（本次实测 `{"resultId":"prompt-76f1ab5da4f7b5d28daacc40051cf6fc","unsignedRow":true,"signedRow":true,"reviewerShown":true,"overclaim":false}`），`E2E_REQUIRED=1` 时包装器直接断言这几项——跳过这一节的运行不可能再被读成 PASS。

自己造的三处红，都记下来：`selectOption({index:1})` 选中的是**已被取代的 v1 brief**，服务器按合同回 409 STALE_REVISION；改成按文本挑未取代的那条。第二个更坏——守卫写了 `/UNREVIEWED/`，而面板自己的说明文字里就有这个词，于是断言**为错误的原因变绿**（真因是 compose 还在飞，状态是"正在提交，等待读回"）；改成等 option 值本身，并逐行断言。第三处 `shape-notice-coverage.mjs` 拒绝新读回路径没有 `shapeNotice`：读回的字段缺失必须被说出来，不能用"未读回"糊过去。`verify_workbench_route_calls.py` 的 `CANDIDATES` 探测词表原本没有 prompt-result 的 id 形状，会让新 POST 被误报 `FRONTEND_ROUTE_UNSERVED`，有意扩了词表（不是扩产品面）。同批把 `test_contract_bindings.py` 里硬写的 `routes=66` 改成从台账派生——CI 在 81dc4fc2 就是被这行写红的（本地 35bddcfd 的主运行仍显示这一条为唯一 FAIL，见 §5.21）。提交 `6ca44f46`（状态：IMPL_LOCAL + TESTED_LOCAL；CI 读数见 §5.21）。

### 5.19 第十七批（B2b：Adobe 的作业契约，写出来就必须被读到）

`design-lab/tests/test_contract_bindings.py` 的欠账清单最后剩两条，都是 Adobe 作业形状：`POST …/tasks/<native-job>/patch` 声明 `design-lab/adobe-patch-job/v1`（与 `photoshop-patch-job/v1` 同一路由），`POST …/native-plans` 声明 `design-lab/photoshop-native-job/v1`。这三份 schema 逐条只重写适配器**已经在做**的手检：键集精确、`jobId`/`rirHash` 形状、`checkpointSha256` 64 hex、Illustrator 的 `operations` 常量表、Photoshop 的画布边长与输出名。没写的也不是摆设——画布**面积**上限、路径包含、checkpoint 字节、输出文件尚不存在，JSON Schema 看不见这些，reason 里逐条点名为仍然由手检负责。

关键一条：**schema 不能只写不读**。台账原句就是在定"声明了却没人读"这个罪，所以同批把装载接进 `illustrator_com.py` / `photoshop_com.py`：各自一个 `JOB_CONTRACTS` 版本表，`execute()` 在任何 COM 调用前按 body 里的版本取文件校验，取不到文件或不认识版本都是预检拒绝（`outcome_unknown=False`）。没动的 130 个既有 execute 调用点全绿：`test_illustrator_com_adapter.py` 10 项、`test_photoshop_com_adapter.py` 18 项、`test_native_tasks.py` 47 项、`test_native_quiescence.py` 3 项。

新增的牙齿有两条正向断言与两条种的红：装运夹具必须**通过**自己的契约（否则下一条红可能只是读不到文件），以及手检从未判过的字段现在被拒——`layers` 必须是列表、`artboard`/`authorization` 必须是对象。第三枚探针反而把我自己的假设照出来了：我给 Photoshop 原生作业种了 `layers=[['id','image']]`，它合法通过，因为**原生路径**根本不读 layers 的元素；`_photoshop_patch` 会逐个索引元素，所以"每项是对象"这条只在 patch 契约里写，探针也移到 patch 形状上。欠账清空后 `test_a_debt_row_cannot_be_laundered_by_deleting_the_version_line` 与 `test_schema_less_row_whose_debt_is_already_paid_is_red` 失去了天然的受害者（今天已无带版本的 SCHEMA_LESS 行），两者改为**把已付的 Adobe 行洗回去**作为种植方式，并在测试里写清牙齿搬到了哪两个文件。闸门实测：`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=68 dispatched=68 bound=33 schema_less=35`，`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=14 failures=0`，该模块 36 项 OK。提交 `ee46de6a`（IMPL_LOCAL + TESTED_LOCAL）。

### 5.20 第十八批（B5：第一条 CONSUMED 必须是"量出来的"，并且同一把扫描器要能判红）

`packages/capabilities/selected-sources.json` 的阶梯一直是 8 条 REGISTERED_ONLY + 2 条 MAPPED、0 条 CONSUMED。这批把 `SRC-T07-MOTION-COMPOSITED` 升为 CONSUMED，证据级别 E1 → E2，`capabilityState` 保持 `structural-pass`（受控运行时不是宿主级隔离运行）。判据原文只禁布局属性（`width/height/top/left/right/bottom/margin*/padding*`），所以新闸门的禁用集合与文本扫描器**完全一致**——`design-lab/tests/test_workbench_motion_gate.py` 里有一条对照断言：文本扫过 7 个 `appliesTo` 文件得出的条数必须等于浏览器读到的条数，两条闸门对同一字节只能给一个答案。

实跑读数（`MA_SUMMARY`）：21 个导航项 → 21 个不同 location、22 次扫描、9614 条 CSSOM 规则、88 个 `@keyframes`、154 个关键帧步进、8995 个渲染元素、布局动效 **0** 条；同一把扫描器先必须判出植入缺陷的 **3** 条（`@keyframes dlMotionPlant` 的 from/to + `.dl-motion-plant{transition:width}`）。刻意不判的两项写进回执而不是沉默：`transition: all` 132 处、`stroke-dashoffset` 等非布局动画 110 处——本闸门不自造比判据更严的标准，但把它看见的交出。回执绑定字节：`styleSha256`/`bundleSha256` 由测试与盘上文件对账。

自己造的坑，五个，全部记原样：① 第一版按 `rule.keyFrames` 识别关键帧，Chromium 用的是 `keyRules`（`cssRules` 为别名），于是 4 个 `@keyframes` 一个没读到；② 更坏的一版把分组判断写成 `if (rule.cssRules) { walk(); continue; }`，而 CSS 嵌套让**每条普通样式规则**都有了 `.cssRules`，结果 `styleRules=0` 而页面照样"零违规"——这正是"绿闸门读的是空输入"这一类，靠 `keyframeRules/styleRules` 覆盖率计数才被抓住；③ 植入用 `addStyleTag` 被产品的 CSP `style-src 'self'` 直接拒绝，改成 constructed stylesheet，不为过闸门而放宽产品策略；④ 该 Chromium 的 `document.styleSheets` **不含** `adoptedStyleSheets`（实测 `adopted=1, sheets=1`），扫描器改为两个集合都走，否则"页面用了构造式样式表"这种真实写法会扫成干净；⑤ 原有的 CONSUMED 种植测试把 proof 指向自己所在的文件，而那个文件为了新的正向断言开始引用规则名与标准名，于是"缺测试"这一条再也不响——种植改用 `design-lab/config/contract-bindings.json`，同时正向测试 `test_the_one_shipped_consumed_landing_is_a_browser_measurement` 把 consumed=1 的成立条件写成测试而非散文。另有一处依赖隐式值：种植原先假设 `evidenceLevel` 仍是 E1，现在必须自己降级。

新文件同时进了三处人口登记，否则会被"只证明自己列出的清单"放过：`verify_browser_e2e_ran.py` 的 `TEST_MODULES`（注册表是元组不是 glob，未登记的浏览器套件会永远跳过而无发现）、`test_gate_reachability.py` 认得到的 `.mjs` 名单、以及 `LICENSE_COVERAGE=OK` / `VERIFY_EXECUTION_PATH_GATE=PASS files=8` 两项卫生闸门。本轮没有在本机跑整条 no-skip 浏览器套件：机器上有 WORK-LAB 与 ArcheAxis 的并行作业在跑，全套浏览器闸口在竞争下极慢，而 CI 的 required 作业才是权威——本机只定向跑了新模块（1 项 OK）与 §5.18 的链。`SELECTED_SOURCES=OK records=6 registered_only=8 mapped=1 consumed=1 motion_deviations=0 citations=VERIFIED(13)/SKIPPED(0)`，该模块 39 项 OK。

### 5.21 CI 读数与本批边界（逐作业，绑定精确 SHA）

**`f4b727e15ccf551a0fb58b74d26f8b7bd94fc26a` 已推到 `main` 与 `qoder/designlab-backup-consistency-20261007`，主运行 39654042652 `conclusion=success`**，逐作业（照 artifact 原样转录，不重组判决）：Python gate success、DeepSeek authority gate chain success、Workbench strict-TS product gate success、MiniGame node gate (+drift) success、Generated-artifact clean-tree gate success、Clean wheel install + Workbench launch gate success、License & secret hygiene gate success、Open Design host adapter gate success、Top-level Authority consistency gate success、Workbench browser E2E (exact-SHA controlled-runtime, no-skip) success、CI artifact proof (H001) success；Branch light gate `skipped`——该作业按设计只在开发分支跑，不是缺失。备份分支上的轻量运行 39654053174 同样 success。

Python 闸门的计数回执：三个分片全 `exit=0`——`shard=1/3 tests=947 outcomes={'PASS': 945, 'SKIP': 2}`、`shard=2/3 tests=1143 outcomes={'PASS': 1127, 'SKIP': 16}`、`shard=3/3 tests=1057 outcomes={'PASS': 1053, 'SKIP': 4}`，`PYTHON_TESTS_UNION=OK expected=3147 distinct=3147 ran=3147 duplicates=0 missing=0 unexpected=0`。上一轮同一条是 `expected=3139` 且 shard=3/3 有 1 项 FAIL（`test_contract_bindings.GateTeethTests.test_verdict_line_is_what_the_aggregate_matches`）——**本批把它转绿了**，3139 → 3147 的 +8 就是本批新增的测试数（Illustrator 3、Photoshop 3、精选来源 1、motion 包装器 1）。CI 只出计数不出测试名，所以这句对照是按作业 id 与两次读数写的，不是从名字表里读的。

浏览器 no-skip 作业逐模块回执：`test_workbench_design_layer_e2e ran=2 skipped=0 failed=0`、`overflow_gate ran=3`、`contrast_gate ran=3`、`theme_geometry_gate ran=1`、`theme_affordance_gate ran=1`、`ui_audit_gate ran=1`、**`test_workbench_motion_gate ran=1 skipped=0 failed=0`**，合计 `BROWSER_E2E ran=12 skipped=0 failed=0` → `BROWSER_E2E: PASS (ran, no-skip, no-skip policy satisfied)`。这条对本批有分量：§5.20 那条 CONSUMED 的度量闸门在 CI 的 pinned playwright + chromium 下**没有跳过**，植入的 `adoptedStyleSheets` 缺陷在该浏览器构建里同样被判出——若那边的 Chromium 构建与我本机不同，`MA_SELF_TEST_INCONCLUSIVE` 会红，而不是把 0 违规当成通过。

状态分级（不要把上一级当成下一级）：B3 桌面半、B2b、B5 三条均为 **CI_VERIFIED_EXACT_SHA @ f4b727e1**（本地实跑在前，逐作业读数在后）。§5.17 那批（B4，`35bddcfd`）的内容闸门全绿，但它的主运行被同一行硬编码测试判为 failure，该红已由本批取代；因此 B4 的准确说法是 **BRANCH_PUBLISHED + 内容闸门绿 + 其唯一 FAIL 已在 f4b727e1 转绿**，不是"当时就 11/11 success"。仍未执行、也未因这次推送而改变的：release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3；`currentExecution` 34 项仍 `FROZEN_DEFERRED`；手机端仍是排除项。

### 5.22 第十九批（规范出处第三轮，以及我自己把登记件写红的两次）

**第一次是序列错误。** §5.21 把 CI 读数写进审计件之后，我推了 `26cb7975`，但没有重跑 `scripts/generate_archive_record_register.py`——而审计件本身就是登记件的第 5 行。CI 的 Top-level Authority 作业随即报 `RECORD_REGISTER_GATE=FAIL checks=5 problems=5`：`blob SHA-1 claim d1577174b595 vs f793d9d7e265`、`bytes claim 89,924 vs 92,342`、`SHA-256 prefix claim 8214ee17858b3735 vs fba2e65ac0fcbe5f`、`bullet disagrees with table (path or digest)`、`bullet 5: digest no longer matches the committed blob`。这条红是闸门的正确判决：我在"重测登记件"之后又改了同一个被登记的文件——最后一个写者就是它的所有人。修法是把**所有内容编辑放在重测之前**，再按原序列走：`f6af3825` 上四脚本本地复跑全绿（`TOP_AUTHORITY_GATE=PASS checks=10`、`PROJECT_DRIFT=PASS findings=0`、`PATH_REF_GATE=PASS checks=10`、`RECORD_REGISTER_GATE=PASS checks=5 problems=0`），聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`。

**第二次是本件自己写错的一句读数。** 第三轮取证用只读子智能体跑了八条以上新渠道，主会话再直连复核关键一条，结果**推翻的是我自己上一轮的登记**：`developer.apple.com/tutorials/data/design/human-interface-guidelines.json` 本轮 **200**（原样给 `"copyright": "Copyright © 2026 Apple Inc. All rights reserved."` 与 `"schemaVersion": {"major": 0, "minor": 3, "patch": 0}`，仍无任何编辑日期或规范版本），而 §5.17 与登记件第四节写的是"那一族 JSON 全部 404"。两轮读数不同就登记两次：不删旧读数、不把新读数说成"一直如此"，也不因为"现在能打开"就把它当版本证据。同轮另两条：Fluent 的 `learn.microsoft.com/en-us/windows/apps/design/` 在 HTML `<head>` 里服务端就给 `ms.date: 2026-10-07`、`updated_at: 2026-10-08T15:21`、`git_commit_id: a6d48a8e…`、`ms.update-cycle: 365-days`（登记为文档页编辑日期与提交号，**不是** Fluent 2 版本号）；Material 侧仍只有 `sitemap.xml` 的 `<lastmod>`，`/get-started` 与 `/blog` 的服务端 HTML 不出版本、日期与许可。

**两条 C 档欠账仍未结，渠道清单变长了。** PDF/UA-1：ISO 与 PDF Association 仍 403，NEN **503**，Beuth→DIN Media 301 后 **404**，EAN/TBS 与 Wayback 连接失败，BSI 产品页仍在 404 族——唯一新增是第三方索引对出版方页面的字段捕获（Edition 2 / Publication date 2014-12 / 17 页 / ISO/TC 171/SC 2 / 前版本 2012 已撤回），按捕获登记，**不升级为已核验版次**，`ACCESSIBILITY_BASELINE.md` 里带版次的符合性断言因此仍未解禁。IEC 61966-2-1：`webstore.iec.ch/en/publication/2960` 打开的是 "IEC 60695-4:2012 … Fire hazard testing"，把"换个编号猜"这条路堵死；`/en/search?q=…` 404、searchresults 与 preview PDF 连接失败、`sfs.fi`/`standard.no`/`nen.nl`/`sist.es`/`aenor.com` 无命中——出版记录仍 UNKNOWN。三者版本号一律 UNKNOWN 不变。

**这批不动判据**：现行对比度判据仍是 WCAG 2.2 AA，APCA 仍是 B 档行业动向记录。`INDUSTRY_SPEC_REGISTER.md` 是出处件，没有闸门给它出判决；同一目录里的 `MOTION_ACCESSIBILITY.md` 却由 `verify_selected_source_adaptation.py` 逐字核对 `ruleId` 是否出现在正文——**同目录两种强度**，改错文件时才分得出来。

### 5.23 第二十批（后端 A/B/C/D：把 Stitch 的 D01/D05/D07/D08 需要的字段先做成真的）

owner 的分工是"后端你按审计报告做，前端我交给 STITCH，做好再告诉你接入"。所以这批不动视觉、不动导航形状，只把设计稿要求、而 API 目前答不上来的字段做成能答的。

**A（D01 首页台账）**：`GET /api/projects` 原先只回 `{id, name, created_at}`，页面要么猜、要么每项目每资源各打一次。现在回 `design-lab/project-list/v1`：逐项目给 14 个表面的记录数、最晚时间戳、以及"还没人签"的两个数。**这批真正的合同是一条双向绑定**：某个计数为 null **当且仅当**该表面的表在此检出从未建过（并且表面名出现在 `absentSurfaces`）——0 是"表在、这个项目一条没有"。种的红两条方向各有测试：给未建表的表面报 0、把已报 absent 的表面写成有数，都被 schema 判红；`project_index.py` 在出口前自校合同，违反就是 500 `PROJECT_LIST_CONTRACT_VIOLATION`（测试用替换 `_one` 的方式把谎种进构造器，证明拒绝发生在服务端而不是纸面）。**没有第二套判定**：未签/已过期走 `prompt_results._state_of`（与读回同一函数，抽出后两处共用），候选侧直接取该资源自己读回的计数；漂移测试手工插一条引用了别的摘要的签名，要求读回与台账同时说 `NOT_CURRENT`、且 `accepted_count` 为 0、`unreviewed` 为 0——这是仓库里第一次真正构造出该状态。

**B（D05 能力库计数）**：`counts.qualified` 算的是"有资格判定记录的数量"，但字段名读起来是"合格数"；今天两者都是 0，所以这不是当前错误而是将来的错误。拆成 `qualificationVerdicts / qualifiedTrue / qualifiedFalse / qualificationNotAdjudicated` 四个数，schema 的 required 与 closed properties 同步，UI 那句话改成四个数并排，`contracts.ts` 与离线夹具一起换。测试里加了旧 schema 给不了的分区不变式：`total = verdicts + notAdjudicated`。

**C（D07 候选导出）不是缺口，实测后取消**：`KnowledgeReview.list` 每行已经带 `export_ready` 与 `export_blocked_by`，信封已有 `export_ready_count / pending_review_count / revoked_count / conflicts / head_sha / outbound`，而且 `test_knowledge_http.py:236 / :281` 正反两向早就断言过。所以本批给 C 的交付是这条实测记录，加上台账里的 `knowledgeCandidatesExportReady` 与读回数字必须一致（不一致就是两处各算一套的开端）。

**D（D08 记录与取消语义）也没有缺口，但有一句本批写错后当场改正**：任务记录已含 `state`、`updated_at` 与 `cancel.{requested, acknowledged}` 两个布尔——设计要的"取消已发"与"宿主确认已停"在数据上是两件事。**这一版原先写"`acknowledged` 目前没有通往 true 的宿主事件"，核对源码后不成立**：`job_store.acknowledge_cancel` 在 `CANCEL_REQUESTED` 之上把它置 1 并推到 `RECONCILING`，变更说明原文 "adapter acknowledged cancellation; readback still required"；`native_tasks._failed` 在派发前被拒（`effect_not_started`）的取消路径同样置 1。真正的限制因此是语义而不是可达性：它说的是**适配层已确认**，不是宿主已停手、也不是产物已核对——界面可以显示"已确认取消，仍需读回"，不得画成会自己变绿的进度。这条错句是"追正本身是新断言"的现场版：我把它写进登记件之前没有打开那两个函数看。给 `GET …/tasks` 补信封 schema（`surface` 判别、状态词汇取自 `design-lab/config/state-vocabularies.json` 一处、100 条上限与 `truncated`/`next_cursor` 同一表达式、`does_not_say` 点名上面那条语义）留下一批做，它顺带能付掉台账里那两行"recorded debt"——其中一行理由还引用了**不存在的文件** `design-lab/schemas/status-vocabulary`（实测无此路径；真正的词汇合同是 `design-lab/config/state-vocabularies.json`，由 `verify_state_vocabularies.py` 守），正是 §3 那一类"路径写错但读起来像出处"的旧账。

**闸门与实跑**：`VERIFY_CONTRACT_BINDINGS=PASS routes=68 dispatched=68 bound=34 schema_less=34`（A 把 `/api/projects` 从 SCHEMA_LESS 翻成 BOUND_SCHEMA，理由里点名 POST 半边仍未绑——一次 dispatch 两种载荷，不假装整行付清）；`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=15`，其中 project-list 用两条真实载荷：这条检出（表面被前面用例开过，计数是整数）与一个一次性新根（什么都没开过，全部 null 且被点名）。定向：`test_project_rollup` 6、`test_capability_library` 14、`test_contract_bindings` 36、`test_route_payload_contracts` 26、`test_service_http` 31、`test_prompt_results` 18、`test_design_layer_http` 20、`test_knowledge_http` 22 全 OK；`tsc --noEmit` 0、`npm run build` 0（bundle 446.18 kB / gzip 119.84 kB）、`npm run test:unit` 0（47 处 seam 形状告警覆盖不变）。聚合第一次报的单项红是我自己的序列错——改了 `capability_library.py` 却没刷 inert 普查，`inert_contract_survey.py` 重跑后（`productFiles` 219→220）`--check` 转绿；这条红与 §5.22 同一形状：**派生件必须在内容写完之后重测**。

**前端只做了两处文字**：能力库那句计数说明，和 `/api/projects` 读回的 seam 声明——`apiOrEmpty` 是拿离线模板与真实载荷对形状的，台账换了信封之后把模板写成页面真正读的 `{projects: []}`（`ProjectListView`），路由发出的其余字段由 `ProjectListResponse` 声明。把离线模板扩成新信封的第一版做法被自己的形状守卫连坐了两处夹具（"形状完整的响应不得出现形状告警"、"研究洞察没有读回 …/research"），那是断言在正确工作，收窄 seam 声明才是修法，改完两处夹具仍保留真实信封形状。

**状态**：IMPL_LOCAL + TESTED_LOCAL @ `de1bde57`；CI 逐作业读数见 §5.24（这一行写的"回填在本节末"没有做到——那批推上去后有两个作业红，我把读数写在下一节，并且不改动这里的原文）。边界不变：推理执行仍未接、`model.executed` 恒 false、签署与审核仍只接受具名 human、导出仍只读回；E3/E4/E5、ComfyUI/H3、`currentExecution` 34 项、手机端排除项一字未动。

### 5.24 第二十一批（后端 D：三条任务读回合成一份信封、付掉台账那两行 debt，并修掉 A 自己漏给 CI 的两条红）

owner 的分工没变（「现在你按照审计报告来做后端 前端我交给STITCH 做好了 再告诉给你接入」），本批仍只做后端。要做的两件事就是 §5.23 末尾留下的那两件：给 `GET …/tasks`、`GET …/tasks/<job>`、`GET …/tasks/<job>/events` 补信封 schema，并顺手把 `contract-bindings.json` 里那两行 "Recorded debt, not a clean boundary" 付掉。

**信封（`src/design_lab/task_queries.py`）**：三条读回共用一个版本 `design-lab/task-readback-v1`，`surface` 是判别字段（`list` / `task` / `events`），`design-lab/schemas/task-readback-v1.schema.json` 要求每个 surface 只带自己那一个载荷键、并明写禁止另外两个——一条路由不能在被要一条记录时回一个列表。分页事实由同一个表达式算出来：两条 SQL 都是 `LIMIT PAGE_LIMIT + 1`，`truncated` 与 `next_cursor` 来自同一次比较，所以载荷不可能一边说"到底了"一边还揣着游标；合同把这三条写死（`truncated=false ⇒ next_cursor=null`、`truncated=true ⇒ 游标非空`、`count=0 ⇒ truncated=false`）。状态词汇**不在这里重打一遍**：`attemptStates` 读自唯一拥有它的 `design-lab/config/state-vocabularies.json`（由 `verify_state_vocabularies.py` 守），读不到就是 503 拒绝而不是"少给一个字段"——页面拿到空词汇表会退回它上次构建时记住的那些词，那比报错更坏。作业级状态词没有命名集合，`operationStates.declaredAs` 就照实说"写在 `job_store.py` 的 `_op()` 落点里的行内字面量"，并回读本页实际出现过的词（`observedInThisPage`）。`does_not_say` 三条，第三条就是 §5.23 更正后的取消语义：`cancel.acknowledged` 是适配层确认，不是宿主已停手，也不是产物已核对。

**自己写错的一处，当场改掉**：`image_assets.ImageAssetError` 的构造只有 `(status, code)` 两个参数，我先按三个参数写了拒绝分支——那条路径真走到时抛的是 `TypeError`，不是一个具名拒绝。改成新的 `TaskReadbackError(status, code, detail)`，并在 `http_service.py` 的两条任务路由上把 detail 一起发出去："词汇文件读不到"和"这页声称到底了却还带游标"是两件不同的事，一张只有红色错误词的任务卡说不出该修哪一个。

**台账**：`GET …/tasks` 与 `GET …/tasks/<job>(/events)` 两行从 `SCHEMA_LESS` 翻成 `BOUND_SCHEMA`（emitter `src/design_lab/task_queries.py:24`），理由里同时更正两处过期说法——原文引用的 `design-lab/schemas/status-vocabulary` **这个路径不存在**（真正的词汇合同是上面那个 config），而"这两条读回由 native_execution_v1 表构建"也不对，行来自 `job / operation_intent / operation_state / attempt_state / attempt_resolution`。这正是 §3 那一类"路径写错但读起来像出处"的旧账，付债的时候一并清掉。

**A 批欠 CI 的两条红（逐作业读数 @ `95829383`，`MAIN=failure`）**：① `Python gate (V3 verifiers + unit tests)` 单条失败 `test_service_cli.ServiceCliTests.test_create_then_new_process_lists_persisted_project`——它断言"新建进程里列出的项目 == 创建时回显的那条记录"，而 A 把列表换成了台账信封；本地我从没跑过这个模块，三个分片的 union 仍是 `expected=3153 distinct=3153 missing=0`，缺的就是我这批改出来的新断言面。② `Clean wheel install + Workbench launch gate`。根因是 §D09 那一类的复发：`PROJECT_ROOT = Path(__file__).parents[3]` 在检出里是仓库根，在安装态是解释器自己的 `Lib`，于是 A 的 `ProjectIndex` 打不开它自己的合同文件，`/api/projects` 回 500，启动器打印 `status: ERROR`。**这条红是我自己造出来的，不是环境噪声**，而且它在源码检出里永远看不见——只有安装态会踩。

**修法与新的牙齿**：`project_index.py` 与 `task_queries.py` 都改走 `runtime/state_resources.repo_resource()`（打包优先、且只有当这个模块确实是检出里的那一份才允许回落到检出），`pyproject.toml` 的 `force-include` 加三行把 `project-list-v1.schema.json`、`task-readback-v1.schema.json`、`state-vocabularies.json` 装进 wheel。为这类缺陷补了一个闸门 `design-lab/tests/test_packaged_contract_resources.py`：**从磁盘枚举** `src/design_lab` 里所有 `repo_resource('…')` 字面量，逐条要求 pyproject 声明了对应打包路径、并且仓库里那个文件还在；第四条是手检——把 `project-list` 那行声明从 pyproject 文本里删掉，检查必须翻红，否则它什么都守不住。

**安装态实跑（不是推断）**：`uv build --wheel` → `uv venv` 干净环境 → `uv pip install <该 wheel>`，跑 CI 那条原话 `DL_LAUNCH_INSTALLED=1 python -m unittest design-lab.tests.test_workbench_launch`：**`Ran 3 tests` / `OK` / 输出里没有 `skipped`**，正是 CI 那三条 grep 要的形状。植入检查：把 `site-packages/design_lab/resources/repo/design-lab/schemas/project-list-v1.schema.json` 移走再跑，`'ERROR' != 'LISTENING'`、`FAILED (failures=1, errors=1)`，装回去复跑 `OK`——这条红能被这一行字节引起，说明绿线是被打包带住的。另外从装好的包里起一次真实服务读两条路由：`package=…/venv-clean/Lib/site-packages/design_lab`、`srcShadowed=False`、`project-list=design-lab/project-list/v1 surfaces=14 absent=13 waitingNulls=4`、`task-readback=design-lab/task-readback/v1 surface=list limit=100 truncated=False cursor=None attemptStates=9 doesNotSay=3`，wheel 成员 354 个。

**读数**：`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=68 dispatched=68 bound=36 schema_less=32`（A 把 `/api/projects` 翻正、D 把两条 tasks 翻正，34/34 → 36/32）；`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=17 failures=0`，其中 `task-readback-list` 与 `task-readback-detail` 各两条真实载荷：一条是什么都没记的页，一条是带着**已被适配层确认的取消**的页，后者走 `job_store.begin_attempt/transition/request_cancel/acknowledge_cancel` 而不是手写行。种子改用 `job_store.connect()` 而不是 `NativeTasks._connect()` 是被自己的用例逼出来的：后者会建 `native_execution_v1` 表，把 `native-runtime-readback` 那条"表还不存在时读到的 ABSENT"用例洗成 PRESENT——那是那条用例存在的唯一理由。`STATE_VOCABULARIES=OK attempt_states=9 errors=0`。定向：`test_task_readback_envelope` 10、`test_packaged_contract_resources` 4、`test_contract_bindings` + `test_route_payload_contracts` 72、`test_service_http`/`test_service_cli`/`test_project_rollup`/`test_native_tasks`/`test_native_submissions` 100 全 OK；全量 union 与聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0` 读数记在本节末（提交前重取）。

**没做与不宣称**：前端一行没动——`/tasks` 的界面仍读 `{tasks, next_cursor}`，信封的其余字段由后端发出、等 STITCH 的面板来接；`apps/workbench/contracts.ts` 把 `next_cursor` 写成 `string | null`，对事件页是**不精确的**（那里的游标是 `event_no` 整数），这是既有不精确、本批不偷偷扩界面，接入时连同 `TaskRecord` 一起按信封改正，写在下一轮提示词里。级别仍是 E1 结构合同 + E2 受控运行时：没有宿主参与，`cancel.acknowledged` 不等于宿主已停手，也不因为补了 schema 就变成 E3。**状态**：IMPL_LOCAL + TESTED_LOCAL；推到两个 ref 后按该精确 SHA 逐作业读的 CI 结果**回填在本节末尾**（不是另开一节，也不改上面任何一句旧读数）。

**CI 逐作业读数 @ `91186bc7`（两个 ref 同指这一枚；run `39800445236` = `completed success`，分支轻闸 run `39800431447` 也 success）**：11 个重作业全绿，逐条为 `CI artifact proof`、`Clean wheel install + Workbench launch gate`、`DeepSeek authority gate chain`、`Generated-artifact clean-tree gate`、`License & secret hygiene gate`、`MiniGame node gate (+ drift check)`、`Open Design host adapter gate`、`Python gate (V3 verifiers + unit tests)`、`Top-level Authority consistency gate`、`Workbench browser E2E (exact-SHA controlled-runtime, no-skip)`、`Workbench strict-TS product gate`；`Branch light gate` 按 D01 规则在 main 运行里 skipped。**§5.23 欠下的两条红这次都在原作业上转正**：`Python gate` 三个分片 `exit=0`，`PYTHON_TESTS_UNION=OK expected=3167 distinct=3167 ran=3167 duplicates=0 missing=0 unexpected=0`（本地同群体第一次跑 shard=1/3 时报过 2 个 ERROR——`test_capability_library_clean_install` 的两条安装态用例；把那 83 个模块 1105 条在同进程重跑是 `OK (skipped=2)`、单跑该模块也 OK，本机没能复现，**因此这条只记为"本地一次读数与 CI 不一致，以 CI 为准"**，不写成已解释的缺陷）；`Clean wheel install` 作业里 `Ran 3 tests in 1.816s` 且步骤的三条 grep 都过，也就是说 `/api/projects` 的读回在安装态第一次真的被跑到了。E2E 作业按 no-skip 政策实跑 `2 + 3 + 3` 条。

**装机面的债清单（同一根因，量出来才写，不靠先例推）**：在干净安装的 wheel 上逐条调用账本里的 37 条 `GET /api/…`。分母要说清：**只用一个真实项目 id 就能构造出 URL 的是 23 条**——14 条给 2xx、6 条给出它本该给的判决（`404 NOT_FOUND` 指向不存在的 id、`400 TASK_REQUIRED`、`403 SAME_ORIGIN_REQUIRED`），另外 **14 条需要真实资产/简报/方向 id，本轮没有调用，那是"没测"不是"没问题"**。三条**因为自己的合同文件走 `PROJECT_ROOT` 而在安装态读不到**——`GET /api/models` → `503 MODEL_CATALOG_UNAVAILABLE`、`GET …/prompt-results` → `500 PROMPT_RESULT_CONTRACT_UNREADABLE`、`GET …/design-layer` → `500 INTERNAL`。`GET /api/evidence-projection` 的 `503 EVIDENCE_LEDGER_ABSENT` **不算这一类**：那个临时根里确实没有台账，是它该有的判决。同一形状的路径表达式全仓还有 29 处、分布在 33 个模块里；本批只付了自己新加的两份，其余仍是装机态债，而源码检出里的任何测试都看不见它——上一版"PROJECT_ROOT 载入的合同不需要新 pyproject 条目"的判断就是这么来的：它拿 `model-selection` 当先例，而那个先例在安装态自己就是坏的。打包副本与检出字节一致（`state-vocabularies.json` 两侧同 `54460ab5…`，`task-readback-v1.schema.json` 两侧同 `df78e5db…`）。**状态**：CI_VERIFIED_EXACT_SHA @ `91186bc7`（分支与 main 两个 ref 同指此枚；本节之后的文字与投影重测另算一枚）。

### 5.25 第二十二批（后端 E：拿"装好的包"当准绳重度量，把整类装机面拒绝读路径付掉，并把这条验收钉进 CI）

owner 这句是「继续打磨后端」。既然 §5.24 量到的根因是"检出里看不见安装态"，这一批就不再用检出读法推定，而是**先把度量搬到安装包里**，再决定修什么。

**方法（两条，缺一不可）**：① 静态——从 `src/design_lab/http_service.py` 做 AST import 闭包（含函数内延迟 import），把闭包内所有由 `PROJECT_ROOT` 拼出来的仓库数据路径列出来，对照 `pyproject` 的 force-include：**18 条读取里 17 条没有声明行**，全部真实存在于检出。② 动态——用 `uv build --wheel` 出来的包装进干净 venv，把 `design-lab/tests/test_standalone_chain_http.py` 改成能 honour `DL_LAUNCH_INSTALLED=1`（沿用 `test_workbench_launch` 已有约定：置位时不把 `src/` 插到 sys.path，好让 `import design_lab` 真的落到 site-packages；`design-lab/tests` 仍要插，这个模块从兄弟测试借夹具，抽掉它会红在错的原因上），并在 `setUp` 里先验布局再跑跳：包路径必须含 `site-packages`，`/api/health` 的 `bundleOrigin` 必须是 `packaged`。
**①单独不够，这条是这批最该记住的一点**：静态扫认的是 `PROJECT_ROOT` 这个名字，而 `assurance/production_preflight.py`、`assurance/delivery_bom.py`、`governance/evidence_readback.py` 三处把同一个根拼成 `Path(__file__).resolve().parents[3]`——清单里看不见它们，是**安装态实跑**把它们抓出来的：`GET …/design-layer` → `500 INTERNAL`、`POST …/tasks/<job>/bundle` → `409 NATIVE_BUNDLE_UNVERIFIED`、`POST …/bundles/<id>/preflight` → `503 PROJECT_STORE_UNAVAILABLE`。第二条最坏：**一个缺失的打包文件伪装成了一条语义判决**（"这份产物没被核对"），而真实原因是"合同字节不在这里"；第三条则把矛头指到用户的数据库上。这两条都不是新缺陷，是 §3 那一类"读起来像结论"的形状第一次在安装包里被照出来。

**修了什么**：20 处读取改走 `runtime/state_resources.repo_resource()`（17 条静态 + 3 条动态），`pyproject` 的 wheel force-include 补 20 行。`design-lab/readiness` 用**目录行**而不是两条文件行：TOML 里同一个源键不能出现两次，而 `model-radar.json` 早已作为能力库的四个输入之一被打包在 `resources/capability-library/` 下——那条继续留着（库自己按那个根解析），新行服务 `repo_resource`。三处 provenance 字段原本是 `SCHEMA_PATH.relative_to(PROJECT_ROOT)` 现算的，改路径后会把 `ValueError` 顶上来，因此改为模块级字面量 `SCHEMA_REPOSITORY_PATH`，**值与今天逐字相同**（`design-lab/schemas/…`）。

**装机面复测（同一把尺子）**：账本里 37 条 `GET /api/…`，能用一个真实项目 id 构造的 23 条中 **2xx 从 14 条升到 17 条**，§5.24 点名的三条拒绝全部转正。`/api/evidence-projection` 仍回 `503 EVIDENCE_LEDGER_ABSENT`，**这条要在 §5.24 上做一处更正**：它并非"临时根没有台账"，detail 明写 `design-lab/config/task-ledger-r3.json is not in this checkout`，而它判的那个根是 `…/venv-clean/Lib`——判决本身仍然正确（安装的产品里确实没有治理台账），但它命名的不是项目根。§5.24 原文不改，按本条为准。
**验收链在装好的包上跑通**：4 条用例全绿，`CHAIN_HOPS project=201 asset=201 brief=201 direction=201 design-layer=200 analysis=201 catalog=200 model-choose=201 prompt-compose=201 prompt-reverse=201 prompt-results=200 prompt-accept=201 jury-verdict=201 jury-readback=200 rights=201 rights-readback=200 candidate=201 review=200 candidate-readback=200 export=200` 与 `DELIVERY_HOPS project=201 native=READBACK bundle=201 preflight=200`。植入检查：把 site-packages 里的 `resources/repo/design-lab/production/profiles` 整个移走，`design-lab/tests/test_standalone_chain_http.py` 立刻三条 ERROR，异常原文 `FileNotFoundError: packaged repository resource missing: production/profiles`——**拒绝发生在导入时，没有悄悄回落到检出**；移回来复跑绿。wheel 从 1,034,230 B 到 1,068,459 B（+34 KB，装进去的是合同字节，不是素材）。

**自己的闸门抓了自己一次**：改完源码后 `VERIFY_CONTRACT_BINDINGS=FAIL`，8 条 `EMITTER_POINTER_NOT_THE_VERSION`——我删了这些文件里的若干行，账本里 `path:line` 的发射器指针就落到了注释和别的语句上（§5.24 记过同类一次，这是第二次）。按当前行号重钉 8 条（`evidence_readback.py:29→30`、`design_layer.py:63→64`、`production_preflight.py:378→383`、`prompt_intelligence.py:184→48`、`:292→49`、`model_selection.py:228→39`、`prompt_results.py:46→45`、`:47→46`），转 PASS。**这条不是可选项**：`test_packaged_contract_resources.py` 从磁盘枚举 `repo_resource('…')` 字面量，所以本批新增的 18 个调用点若少一行声明就红；该测试的覆盖自陈也扩到 9 个具名读取（含 `production/profiles`、`schemas/bom.schema.json`、`readiness/model-radar.json`）。

**CI 里多了永久的一步**：`.github/workflows/canonical-verify.yml` 的 clean-wheel 作业追加 "Walk the acceptance chain against the installed package"——断言 `Ran [1-9][0-9]* tests`（**不钉死用例数**，上一批 `routes=66` 那种硬编码红过一次）、`^OK`、无 `skipped`，且 `CHAIN_HOPS` 与 `DELIVERY_HOPS` 两行都被打印。这一作业从此既是安装态冒烟也是全链回归。

**闸门与实跑**：`VERIFY_CONTRACT_BINDINGS=PASS routes=68 dispatched=68 bound=36 schema_less=32`（计数未变——这批改的是"从哪里读合同"，不是"哪条边界有没有合同"）、`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=17 failures=0`、`INERT_SURVEY=OK rows=30`、`STATE_VOCABULARIES=OK`、`WORKBENCH PACKAGING: all 5 … passed`；定向源码 `test_delivery_bom`+`test_evidence_readback_contract`+`test_production_preflight`+`test_artifact_preflight_ui_contract` 78 OK，`test_interop_dtcg`/`test_interop_provenance`/`test_readiness_host_matrix(_gate)`/`test_readiness_model_radar`/`test_assurance_jury`/`test_assurance_knowledge_feedback`/`test_brief_readback_contract`/`test_jury_http`/`test_knowledge_http`/`test_packaged_contract_resources` 218 OK，`test_standalone_chain_http` 源码模式 4 OK、安装模式 4 OK、`test_workbench_launch` 安装模式 `Ran 3 tests / OK`。**状态**：IMPL_LOCAL + TESTED_LOCAL（聚合与全量 union、CI 逐作业读数在本节末回填）。

**边界与级别**：这一批把"独立可运行"的主张从**源码检出**扩展到**安装好的包**，证据级别仍是 E2 受控运行时——同一台机器、合成夹具、无真实宿主、无真人验收；`preflight=200` 不等于产物可用，`export=200` 不等于已发送。E3/E4/E5、ComfyUI/H3、`currentExecution` 34 项、手机端排除项、字体与三方素材出范围，一字未动。

**第三步：把度量工具本身做成有正向对照的审计件**。上面两种读法各有一个盲区，所以把它们固化成 `design-lab/scripts/audit_repo_root_reads.py`：它从 `http_service.py` 走 import 闭包，用 AST 认出 `<根> / 'a' / 'b'` 的拼法，并逐条问 `pyproject` 是否把该路径装进 `design_lab/resources/repo/`（`repo_resource` 唯一会去读的目录下），同时支持"整目录声明覆盖其子文件"。写它的时候先犯了个真错：**检测器只认 `ast.Call`，而 `Path(__file__).resolve().parents[3]` 在 AST 里是 `Subscript`**——于是它对三处 parents 拼法全部视而不见，并给出一个漂亮的 "0 remaining"。这个"0"是假绿，被 `--control` 抓到：控制项从 git 取 `91186bc7` 的修复前字节喂给同一个 `scan()`，认不出病就等于检测器坏了。现在报告是 `REPO_ROOT_READS=REPORT paths=1 not_shipped_under_resources_repo=1`，那一条是 `adapters/photoshop_com.py` 的 Adobe 桥——它**本来就先读 `design_lab/resources/adobe/`**（另一个打包前缀，pyproject 有意如此），且只在真实宿主派发时打开，而派发冻结。工具的两条限制写在文件头并记在这里：① 先把根存进变量再拼的两步写法不追（修复前的 `delivery_bom.py`/`evidence_readback.py` 与 `illustrator_com.py` 都属于这类）；② 前缀不同的合法 packaged-first 读法会被报成 NOT-SHIPPED。**因此这句不是"静态证明干净"，而是"禁止新增同类读路径"**：`design-lab/tests/test_packaged_contract_resources.py` 里两条新用例把这条报告变成闸门——`--control` 必须 `CONTROL=OK`，`NOT_SHIPPED` 集合必须落在上面那条白名单内，且 `paths=0`（空群体）本身判红。装机面真正的主张由行为闸门扛：CI 的 clean-wheel 作业在安装包里跑 20+4 跳。

**两条本批自己量出来的尾巴，都按"看得见"而不是"吸收掉"处理**：① 证据台账的漂移清单涨了 4 对。`test_evidence_artifact_presence.py` 看守的是"哪条记录把它描述的代码当工件、而那段代码后来动了"——本批改的 `delivery_bom.py`、`design_layer.py`、`governance/evidence_readback.py`、`interop/dtcg.py` 各被一条 2026-10-08 的记录绑定，字节一变就到期。按该文件的既有做法：**旧记录一字不改**，在清单里加四条带日期的行并写明原因，总数从 60 钉到 64；这 4 对是用该测试自己的度量重新量出来的（actual 64 / pinned 60，差集恰好这四个名字），不是从上文抄的。
② 全量 union 在这台机器上稳定复现 2 条 ERROR，**原因这次拿到了 raise site**：`test_capability_library_clean_install` 的两条安装态用例要把 wheel 解包到临时根，而解出来的最深一条路径是
`…\.project-local\task-runtime\python-tests-shard-1\<32hex>\tmp\dl-t05-site-xxxx\design_lab\resources\repo\design-lab\domain-packs\uiux-design\benchmarks\ecommerce-pdp-checkout-golden\implementations`，
Windows 报 `[WinError 206] 文件名或扩展名太长`。上一批（本批之前）的本地 union 已经是同样这两条、同样位置，Linux 上三次 CI 全绿——**这是本机路径长度上限，不是代码缺陷，也不是本批引入**；`_installed_site()` 在检出内的 `.venv` 被判为"源码布局"而回落到解包，是它踩中的机制。修法要么给该用例一个更短的临时根，要么只解包它真正需要的成员；在拿到这两条之一的实测前，不把"CI 绿"写成"已解释"。级别不变：这两条本机红不改变 §5.25 上面任何一条装机面读数，那些是从 site-packages 真实解析（`site-packages` + `bundleOrigin=packaged`）跑出来的。

**本批最终读数**（回填完成）：CI 逐作业——代码枚 `2102ba8b`（打包修正）run `39821106405` 与本批尾枚 `f804af9f`（审计工具 + 两条闸门用例）run `39823168783` **均 `completed success`**，11 个重作业全绿、`Branch light gate` 按 D01 规则 skipped；`Clean wheel install + Workbench launch gate` 作业里新加的 **"Walk the acceptance chain against the installed package" 步骤为 `success`**（这一步按构造无法靠"没跑"变绿：它要求 `Ran [1-9][0-9]* tests`、`^OK`、无 `skipped`，并且 `CHAIN_HOPS` 与 `DELIVERY_HOPS` 两行都被打印）。Python 闸门：`2102ba8b` 为 `PYTHON_TESTS_UNION=OK expected=3167 distinct=3167 ran=3167 duplicates=0 missing=0 unexpected=0`（三分片 exit=0），尾枚 `f804af9f` 为 `expected=3169 distinct=3169 ran=3169 missing=0 unexpected=0`——多出的 2 条正是审计工具的两条用例。**状态：CI_VERIFIED_EXACT_SHA @ `f804af9f`**（main 与备份分支同指此枚；下面的文字/投影重绑另算一枚，不改上面任何读数）。本机全量 union 的 2 条 Windows 路径长度 ERROR 见本节末 ②。

**闸门计数不变的原因**：`VERIFY_CONTRACT_BINDINGS=PASS routes=68 bound=36 schema_less=32` 与 `VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=17` 一字未动——本批改的是"合同从哪里读"，不是"哪条边界有没有合同"；`INERT_SURVEY=OK rows=30`、`STATE_VOCABULARIES=OK`、`WORKBENCH PACKAGING: all 5 passed`、聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`（尾枚重跑同值）。wheel `1,068,459 B`。

### 5.26 第二十三批（后端 F：把装机面"没测"的那一半真测完，并修掉本机背了两批的路径超长红）

owner 这句还是「继续打磨后端」。§5.24 与 §5.25 各自留下一条明写的欠账——"14 条 GET 行没调用"和"本机两条安装态用例稳定红"——这一批就把这两条结清，不加新功能、不动前端。

**先更正我自己连写两轮的读数**：那两节写的是"账本 37 条 GET 行"。逐行数一遍是 **39 条**：我当时的过滤条件是 `route.startswith('/api/')`，把 `/workbench` 与 `workbench.ROUTES` 两行滤掉了却没说。分母写错不是无害的近似，它正是这批要修的毛病本身，所以原句保留不改，以本句为准。

**① 每一条 GET 都用真实对象调用一次**（`design-lab/tests/test_standalone_chain_http.py` 新增 `test_every_ledger_get_route_is_answered_in_this_layout`）：先用写入路由造出资产、简报、方向，再复用交付腿（`_deliver_to_preflight()` 从原来的交付用例里抽出来共用，不复制第二份）拿到交付项目、job、bundle 与 version id，然后把账本每行的 id 槽位换成**这台服务刚写进去的值**逐条调用。断言是双向的：每行必须在覆盖表里有一条读法，否则红——新增路由不能靠"没人加"溜过去；反过来，表里出现账本已不声明的路由也红。槽位缺值直接失败，不会把字面量 `{token}` 当路径发出去。5xx 只允许一张按布局分开的名单，而且**名单必须与实际发生的 5xx 完全相等**：不再发生的那条会让断言红，免得一个旧豁免悄悄给下一条 5xx 背书。
**读数**：源码布局 `routes=39 reads=39 answered=35 verdicts=4`，未点名 5xx 为 0；装好的 wheel 里 `routes=39 reads=38 answered=34 verdicts=4`，唯一被点名的 5xx 是 `/api/evidence-projection → 503 EVIDENCE_LEDGER_ABSENT`——安装的产品里没有可投影的治理检出，它点名缺哪个台账文件而不是给一张干净回执；同一条在源码检出里回 200，两侧名单互换即为红，所以这条不是被豁免掉的失败，是被读出来的差别。三条"仍然没读"逐条写明理由：`…/native-assets/<id>/verify` 需要先被登记的原生资产（交付腿注册的是 bundle 与版本，不是资产行）；`…/knowledge-candidates/<id>/export` 由同一布局里的验收链走到 `export=200`，本扫描不重复建候选；`workbench.ROUTES` 那行本来就不是 URL，是账本记的模块表名。**CI 的装机步现在额外要求日志里出现 `GET_SWEEP layout=installed`**——用例被重构空转时，作业不能照样绿。

**② 本机背了两批的那两条红**（`test_capability_library_clean_install`）：根因量清了——不是代码，是**这台机器的路径长度上限**：runner 把自己的临时根放在 `.project-local/task-runtime/python-tests-shard-1/<32hex>/tmp/`（133 字符），wheel 解包后最深的一条是 `…/design_lab/resources/repo/design-lab/domain-packs/uiux-design/benchmarks/<pack>-golden/implementations/<baseline|enhanced>.html`，377 个成员里正好 8 条超过 259 字符，**没有一条是探针要读的**。修法是逐成员解包 + **对"跳过了什么"下断言**：只允许 `resources/repo/design-lab/domain-packs/` 下的基准页被跳过，四个能力库输入若被跳过即红，其它任何成员跳不过；判据是**成员名而不是 errno**——同一台机器上同一类超长路径在 `makedirs` 处报 `WinError 206`、在 `open` 处报 `[Errno 2]`，我一开始按错误码过滤，实跑立刻不复现，这就是"按码过滤会悄悄再坏一次"的现场版。另加一条不对称用例 `test_an_unextractable_member_the_probe_needs_is_a_finding`，分别证明"需要的成员被跳过必须红"与"基准页被跳过必须放行"，否则这段豁免等于没测。
**验证**：在 runner 自己的深临时根下重跑该模块，`Ran 5 tests / OK / errors=0 failures=0 skipped=0`（此前稳定 2 ERROR）；植入仍然有效（把能力库输入从解包站点移走 → 探针必须拒绝，那条用例就在同一模块里）。这不是把测试关掉换来的绿。

**闸门与实跑**：定向 `test_standalone_chain_http` 源码 5 OK、装机 5 OK（两次都打印自己的分母），`test_capability_library_clean_install` 5 OK（含 runner 环境），`test_evidence_artifact_presence`/`test_packaged_contract_resources`/`test_route_payload_contracts`/`test_contract_bindings` 合计 78 OK；`VERIFY_CONTRACT_BINDINGS=PASS routes=68 dispatched=68 bound=36 schema_less=32`、`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=17 failures=0`（这批没改任何边界，只改了"有没有被读到"）。**状态**：IMPL_LOCAL + TESTED_LOCAL @ `74a461f4`；边界不变——E3/E4/E5、ComfyUI/H3、`currentExecution` 34 项、手机端排除项、字体与三方素材出范围、推理不接、签署与导出仍只本地具名 human，一字未动。级别仍是 E2：sweep 量的是"这台装好的服务答不答"，不是"产物好不好"。

**回填：CI 逐作业与本机绑定重跑（读数按精确 SHA）**
- 代码尾枚 `11e30625`（`74a461f4` 扫描 + `7b250581` 记录 + `5e621da3` 计数闸门跟进 + 投影重绑）run `39833406071` = **`completed success`**，11 个重作业全绿、`Branch light gate` 按 D01 规则 skipped。逐条：`CI artifact proof`、`Clean wheel install + Workbench launch gate`、`DeepSeek authority gate chain`、`Generated-artifact clean-tree gate`、`License & secret hygiene gate`、`MiniGame node gate`、`Open Design host adapter gate`、`Python gate`、`Top-level Authority consistency gate`、`Workbench browser E2E (no-skip)`、`Workbench strict-TS product gate`。
- **CI 那一步真的在安装包里扫完了全表**：作业步骤 `Walk the acceptance chain against the installed package` 为 `success`，其日志原文 `GET_SWEEP layout=installed routes=39 reads=38 answered=34 verdicts=4 unmeasured=3`，三条未读各自的原因也逐行打印（`UNCONSTRUCTED` / `COVERED-ELSEWHERE` / `NOT-A-PATH`）。步骤里有 `grep -q "GET_SWEEP layout=installed"`，所以这一步不能靠"没跑用例"变绿。
- `PYTHON_TESTS_UNION=OK expected=3171 distinct=3171 ran=3171 duplicates=0 missing=0 unexpected=0`（3169 → 3171 正是本批新增的两条用例：装机 GET 扫描与解包豁免的不对称用例）。
- **本机绑定重跑（②的关键证据，Linux CI 给不了）**：同一命令 `scripts/run_python_tests_all.py --shards 3 --jobs 1` 在这台机器上 `shard=1/3 exit=0 tests=1106 outcomes={'PASS': 1104, 'SKIP': 2}`、`shard=2/3 exit=0`、`shard=3/3 exit=0`、`PYTHON_TESTS_UNION=OK expected=3171`——上一批与这一批开头本机稳定复现的那 2 条 `[WinError 206]`/`[Errno 2]` ERROR **不再出现**，且不是靠跳过：同一分片用例数还多了 1 条。聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`（推送前重跑同值）。
- 一处自己被闸门抓住的记录：把交付腿的夹具抽成 `_deliver_to_preflight()` 后，`verify_documented_counts.py` 报 `the …_delivery_leg… hop labels extractor matched nothing`——它按**方法名**在方法体里数跳数，重构把跳数搬走了。闸门拒绝报数是正确行为，修法是让度量跟着委托链走（`5e621da3`），而不是把重构回退；"4 跳交付链"那句现在量的还是那 4 跳。
- 本轮之后：**状态 CI_VERIFIED_EXACT_SHA @ `11e30625`**（main 与备份分支同指此枚；下面的记录与投影重绑是纯文字＋派生件，另算一枚，不改上面任何读数）。

### 5.27 第二十四批（后端 G：把写侧也搬进"装好的包"里度量，并让播种的故障把一处误判顶出来）

owner 这句仍然是「继续打磨后端」。§5.26 把读侧量完了，写侧却没有对应的度量：每个 POST 路由各自有测试，但每份测试都从检出里给自己播种夹具，所以"这台装好的服务能不能写"从未被任何一次运行摊开过。这批只做这件事，不加功能、不动前端一行。

**① 写侧覆盖表**（`design-lab/tests/test_installed_write_surface.py`，`3f542016`）：账本里带 POST 的行共 **29 条**（含 `('GET+POST', '/api/projects')` 那条创建行），逐行按对象依赖顺序真写一次，并**每条都用 GET 读回**。断言与读侧同构且同样双向：账本每行必须在这张表里有一条走法或一条明写的豁免，否则红；表里出现账本已不声明的路由也红；同一路由重复登记也红。槽位由上一跳真实返回的 id 填，缺值即失败，不会把字面量 `{brief}` 发出去当请求（这一点单独有一条用例守着，因为它只会变成一个没人细看的 400）。5xx 名单按布局分开、并与实际发生**完全相等**：多一条即红，少一条——曾经豁免过而这次不再发生的——也红。播种用例有四条：账本里插一条没人走的行必须被点名为"未度量"；把整张表清空必须报出全部分母；豁免名单与实际拒绝互换必须两头都响；槽位替换与 DTCG 花括号必须分得开。
**读数（同一把尺子两侧各跑一遍）**：源码布局 `POST_SWEEP layout=source rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`；装好的 wheel 里 `POST_SWEEP layout=installed` 后面**一字不差相同**。两侧都没有未点名 5xx，所以本批没有新增"三件套"要付——这不是侥幸，是 §5.25 那批把读路径全部改走 `repo_resource` 之后，写路径第一次被真的走到时给出的确认。wheel 实测 1,073,608 字节——其中删掉下面那条重复包装之前是 1,073,668，两次都当场量过。
**一条不走的行**：`POST …/tasks/<job>/run` 的体就一个 `attempt_id`，本扫描手里就有——但 `native_workers.start()` 会 spawn 一个 `design_lab native-worker` 子进程去派发真实创意宿主。owner 2026-10-19/21 的冻结与本轮"不触发任何真实宿主/模型执行"都在，所以它登记为 `FROZEN-BY-POLICY` 而不是"构造不出合法体"：**能不能构造体**与**准不允许做这次写**是两件事，混成一件就会让下一个读的人以为那是技术缺口。原生腿本身照 §5.24 的边界走：`_dispatch` 被 patch、scope 用字面量 `project-native-test`，产物是真字节并按 id 登记——这仍是 E2 受控运行时，不是 E3。

**② 播种把一处误判顶了出来**（`8b83652d`）：为证明这张表在安装布局里不是空转，我把 wheel 里的三个合同文件挨个移走再复跑。两次都是整模块 ERROR，原因同一枚且诚实——`task_queries.py` 在 import 期就 `repo_resource('schemas/task-readback-v1.schema.json')`，文件不在则服务根本起不来（`FileNotFoundError: packaged repository resource missing: …`）。第三次移走 `config/state-vocabularies.json` 时露出的就不是"缺文件"而是**判决本身**：`POST …/tasks/<job>/bundle` 回 **400 INVALID_REQUEST**。机制是 `TaskReadbackError` 继承 `ValueError`，而 dispatch 的兜底子句把所有 `ValueError` 一律写成 400——读侧两条路由（`_list_tasks`、`_task_detail_or_events`）在批次 D 各自就地包过，写侧那几条（bundle/patch/cancel/native-plans）顺手建同一份信封却没包。后果是把一句"服务器的合同文件读不出来"发给调用者读成"你的请求不合法"，与 §5.25 记过的 `PROJECT_STORE_UNAVAILABLE` 指错方向是同一类缺陷的第二个实例。修法按 dispatch 既有的家规：在通用 `ValueError` 子句**之前**加一条 `except TaskReadbackError`，原样带出 `exc.status` 与该码自己的 detail，并补一条不对称用例（`test_a_write_route_that_builds_an_envelope_names_the_contract_not_the_request`）——把这条子句删掉该用例必须红、留着必须绿，四步实测：带子句 OK、删子句 FAILED、恢复、再 OK。**没有**新增打包侧债务：那个配置文件本来就在 wheel 里（批次 D 已 force-include），这批修的是状态映射，不是可见性。**随后把重复的那一半收掉**：`dispatch` 有了具名子句之后，批次 D 给两条读路由就地加的 `_answer_task_read` 包装产出的拒绝体与它**逐字节相同**，等于一个字节面有两个人管。包装已删，三条调用点直接 `send_json(200, …)`，拒绝映射只留 dispatch 一处；`test_task_readback_envelope`/`test_service_http`/本扫描/验收链合计 **52 tests OK**，重装 wheel 后两侧读数一字不变。

**③ 顺带更正三处没人看守的散文指针**：`docs/current/NEXT-AGENT-PROMPT.md` 里"路由清单以 `http_service.py:93` 的 `ROUTES` 为准"、以及第 1、2 段里的 `:191`（POST assets）与 `:195`（POST analysis）在 HEAD 上分别应为 **94 / 203 / 206**。这不是本批改行号改坏的——本批的插入在 470 行之后，三处都在它上面，是更早的批次改动留下的、且**没有任何闸门会读它们**。§5.25 记过账本发射器指针被自己的闸门抓住；散文里同形状的引用坏了不会响，所以更危险。已按当次实测改写，并写明"以 `ROUTES` 表为准、不要抄这里的数字"。同时那句"共 66 条 = 37 GET + 29 POST"现在补了口径：66 是 `http_service.ROUTES` 的条目数（`/api/projects` 在那里是 GET 与 POST 两枚 Route），而账本是 68 行 = 39 GET + 28 POST + 1 `GET+POST`，两侧扫描各自的分母因此不同（读侧 39、写侧 29）。
**闸门又抓了我自己的记录一次**（与 §5.25 同形状，第二次）：把 `ROUTES` 那句写成"为准（2026-10-22 复测：66 枚 Route = …）"之后，`verify_documented_counts.py` 报 `prose says nothing, measurement says 66 (expected the sentence "ROUTES` 为准，共 66 条")`。它按**逐字锚句**在文档里找那个数字，我把锚句拆开了，于是它拒绝让一句"看起来更像"的话冒充测量。正确修法是把锚句原样留下、把补充口径写在它后面，而不是把闸门放宽成模糊匹配（`5e621da3` 那次同理）。
**随后把这两个分母也变成被测量的句子**：`verify_documented_counts.py` 新增两条 CLAIMS——`账本 **{n} 条 POST 行**` 由 `contract-bindings.json` 现数，`其中 **{n} 行**逐行真写` 由扫描表自己的 `WRITES` 条目现数。两个数**必须**不同（差的就是那条政策豁免），所以一句把它们混起来写的散文不能自洽。播种实测：写 30 → `prose says ['30'], measurement says 29`；写 29 走 → `prose says ['29'], measurement says 28`；照实写 → `DOCUMENTED_COUNTS=PASS claims=13`，`test_documented_counts` 同模块 OK。

**闸门与实跑**：定向 `test_installed_write_surface` 源码 6 OK / 装机 6 OK（两侧都打印自己的分母）、`test_standalone_chain_http` 源码与装机各 5 OK、`test_task_readback_envelope`/`test_packaged_contract_resources`/`test_contract_bindings`/`test_service_http` 合计 OK；`VERIFY_CONTRACT_BINDINGS=PASS routes=68 dispatched=68 bound=36 schema_less=32`（本批没动任何边界，只动了一次错误映射）、`DOCUMENTED_COUNTS=PASS claims=11 routes=66`。**状态**：IMPL_LOCAL + TESTED_LOCAL @ `3f542016`。边界不变：E3/E4/E5、安装态分发、release、ComfyUI/H3、`currentExecution` 34 项、手机端排除项、字体与三方素材出范围、推理不接、签署与审核仍只接受具名 human、导出仍只读回，一字未动；级别仍是 E2——这张表量的是"这台装好的服务写不写得进、读不读得回"，不是"产物好不好"。

**回填：CI 逐作业、步骤级日志与本机绑定重跑（读数按精确 SHA）**
- 一枚被自己抓住的中间红：`1ff547bb` 的 main 作业 **failure**，唯一一条红是 `test_documented_counts.test_every_documented_count_matches_the_code`——就是上面"锚句被我拆开"那一条。机制值得记：`verify_design_lab.py --check` 那 76 项**既不含**计数闸门**也不含**单元测试（该脚本里 `documented_counts` 与 `run_python_tests` 各命中 0 次），所以我推送前跑的聚合绿并不覆盖散文面。修法不是放宽聚合，而是"改过受治散文后单独跑 `scripts/verify_documented_counts.py` 与分片套件"。同一枚上 `Walk every POST row against the installed package` 步骤已是 `success`——红在别的作业，不在这条断言。
- **最终枚 `fa0cf178`（main 与备份分支同指此枚）run `39850923993` = `completed success`**：11 个重作业全绿（`CI artifact proof`、`Clean wheel install + Workbench launch gate`、`DeepSeek authority gate chain`、`Generated-artifact clean-tree gate`、`License & secret hygiene gate`、`MiniGame node gate`、`Open Design host adapter gate`、`Python gate`、`Top-level Authority consistency gate`、`Workbench browser E2E (no-skip)`、`Workbench strict-TS product gate`），`Branch light gate` 按 D01 规则 skipped。
- **CI 在安装包里真的走完了写侧**：该作业步骤日志原文 `POST_SWEEP layout=installed rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`；同一枚读侧仍是 `GET_SWEEP layout=installed routes=39 reads=38 answered=34 verdicts=4 unmeasured=3`。步骤里有 `grep -q "POST_SWEEP layout=installed"`、`grep -q "POST_SWEEP_WRITTEN"`、`grep -q "POST_SWEEP_EXCLUDED"` 与 `! grep -q "unearned 5xx"`，所以用例被重构成空转时作业不能照绿。
- `PYTHON_TESTS_UNION=OK expected=3177 distinct=3177 ran=3177 duplicates=0 missing=0 unexpected=0`（上一批 3171 → 3177 正是本扫描 6 条用例进表：`PYTHON_TESTS_MODULE_ALL 4.050s tests=6 test_installed_write_surface`），三片各自 `exit=0`。
- **本机绑定重跑（Windows 那一半，Linux CI 给不了）**：`scripts/run_python_tests_all.py --shards 3 --jobs 1` 三片 `exit=0`——`shard=1/3 tests=977 {'PASS':976,'SKIP':1}`、`shard=2/3 tests=1127 {'PASS':1124,'SKIP':3}`、`shard=3/3 tests=1073 {'PASS':1072,'SKIP':1}`（该片本机 1534.497s 对 CI 455.817s）、`PYTHON_TESTS_UNION=OK expected=3177`，**零 ERROR**：§5.26 修掉的那两条本机 `[WinError 206]`/`[Errno 2]` 没有回来。边界照实写：这次本机跑从 `6a05e347` 起跑，最后两枚（`276ea88e` 计数口径与散文、`fa0cf178` 投影重绑）落在跑的过程中，所以本机这条覆盖的是"写侧扫描 + 信封拒绝映射"这棵代码树；**最终枚的全套读数以 CI 那一条为准**，本批新增的两条计数断言在推送前各自跑过（播种 30/29 皆红、照实写 `claims=13 PASS`，`test_documented_counts` 同模块 OK）。聚合在最终树重跑同值：`VERIFY_DESIGN_LAB=OK total=76 failed=0`、`VERIFY_RESULT=OK total=549 failed=0`。
- 本轮之后：**状态 CI_VERIFIED_EXACT_SHA @ `fa0cf178`**（下面这条记录本身与投影重绑是纯文字＋派生件，另算一枚，不改上面任何读数）。

### 5.28 第二十五批（后端 H：把读侧最后一条"没调用"换成真调用，并先证它量的是字节）

owner 这句还是「继续打磨后端」。§5.26 清了 14 条没调用的 GET 行，却留下一条以自己写的理由关闭的洞——`…/native-assets/<id>/verify` 登记为 `UNCONSTRUCTED: verifying needs a registered native asset id, and the delivered fixture registers a bundle and its versions, **not an asset row**`。这句话是**错的**，而且它错得很像样：交付腿确实注册 bundle，但它同时也注册了那一行原生资产。批次 G 的写侧扫描把 `GET /api/projects/<id>/native-assets` 的答案原样打印出来，洞自己就露出来了：`{"id": "native-b5553c…", "kind": "psd", "version_id": "v-47f897…", "verification": "METADATA_ONLY"}` 就在手里。**先更正旧句，再改代码**：登记理由不删，以本句为准。

**① 那条读法换成真调用**：`GET_READS` 里那一格改成 `/api/projects/{delivery_project}/native-assets/{native_asset}/verify`，槽位由交付腿自己的列表读回答；列表若空，扫描立刻红（`the delivery leg produced no native asset row to verify`），这样"这条又没人走了"不能靠一句注释重新溜进来。`native_asset` 也进缺槽即红的名单，不再多一处能吞下未填占位符的地方。分母随之移动，两侧各跑一遍：源码 `reads=39 answered=35 unmeasured=3` → `reads=40 answered=36 unmeasured=2`；装机 `reads=38 answered=34 unmeasured=3` → `reads=39 answered=35 unmeasured=2`。剩下 2 条不是洞而是判决：候选 export 在同一布局的验收链里走到 `export=200`（本扫描不重复建候选），`workbench.ROUTES` 那行本身不是 URL。

**② 判决的含义先用播种钉死**（新增 `test_the_native_asset_verify_route_re_reads_the_stored_bytes`）：这条路由与列表行的区别只在它自己那一次重算——列表 `verification=METADATA_ONLY`，verify 答 `HASH_VERIFIED`。要断言"它读的是字节"，就必须让字节动起来：从账本 `artifact` 行取该版本真正的落盘路径（`…/assets/versions/<32hex>/native.psd`），把它改成**等长**的字节——只比大小的检查照样过——判决必须变成 `409 NATIVE_ARTIFACT_UNVERIFIED`；写回原字节必须回到 `HASH_VERIFIED`；一个形状合法但从未登记过的 id 必须 `404 NATIVE_ASSET_NOT_FOUND`。三步都在同一个用例里，且 verify 前后不改写文件（断言字节原样）。
**仪器自己的牙齿也验过**：把 `native_assets.py` 那行摘要比较改成永假，这条用例必须红。实测四步——带比较 `OK`；去掉比较 `FAILED（409 != 200）`；恢复原文件 `OK`；再跑一次 `OK`。这条播种不是走过场：去掉比较后判决**仍然**答 `HASH_VERIFIED`，也就是说没有这一步，"它重算了摘要"这句话本身是没人能推翻的装饰。

**③ 没有新增打包面债务**：这条路由读的是项目自己的资产库字节，不是仓库里的合同/配置文件；源码与装机两侧同值（`NATIVE_VERIFY layout=installed clean=HASH_VERIFIED tampered=NATIVE_ARTIFACT_UNVERIFIED unknown=NATIVE_ASSET_NOT_FOUND`）就是证据，因此三件套这一批没有要付的账。CI 的装机步现要求这整串出现——它把三个判决一次钉死，只答 200 的空转实现不能过。写侧扫描读数一字未动（`rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`）。

**闸门与实跑**：`test_standalone_chain_http` 源码 6 OK / 装机 6 OK，`test_installed_write_surface` 装机 6 OK，两模块合跑 12 OK；`VERIFY_CONTRACT_BINDINGS=PASS routes=68 dispatched=68`；改过受治散文后按批次 G 学到的那条单独跑了 `DOCUMENTED_COUNTS`，并把这条闸门补齐到本节的两个读侧分母：`账本是 **{n} 条** GET 行` 由账本现数（39）、`仍有 **{n} 条**没被这条扫描读到` 由扫描表里带标记前缀的条目现数（2），`claims` 由 13 增至 15。两条都各自播种证伪：写 40 → `prose says ['40'], measurement says 39`；写 3 → `prose says ['3'], measurement says 2`；照实写 `PASS claims=15`。**状态**：IMPL_LOCAL + TESTED_LOCAL。边界不变：E3/E4/E5、安装态分发、release、ComfyUI/H3、`currentExecution` 34 项、手机端排除项、字体与三方素材出范围、推理不接、签署与审核仍只接受具名 human、导出仍只读回，一字未动；级别仍是 E2——这条路由证的是"存下的字节还是不是它自己"，不是"产物好不好"，也不因为能重算摘要就变成宿主读回。

**回填：CI 逐作业、步骤级日志与本机 Windows 证据（读数按精确 SHA）**
- **`d9976d0c`（main 与备份分支同指此枚）run `39859065304` = `completed success`**：11 个重作业全绿，`Branch light gate` 按 D01 规则 skipped。步骤级：`Walk the acceptance chain against the installed package` 与 `Walk every POST row against the installed package` 均 `success`，其日志原文一次给全三条读数——`GET_SWEEP layout=installed routes=39 reads=39 answered=35 verdicts=4 unmeasured=2`、`NATIVE_VERIFY layout=installed clean=HASH_VERIFIED tampered=NATIVE_ARTIFACT_UNVERIFIED unknown=NATIVE_ASSET_NOT_FOUND`、`POST_SWEEP layout=installed rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`（两模块各 `Ran 6 tests`）。CI 那一步现在把整串 `NATIVE_VERIFY …` 当作 grep 目标，所以"只答 200 的空实现"过不去。
- `PYTHON_TESTS_UNION=OK expected=3178 distinct=3178 ran=3178 duplicates=0 missing=0 unexpected=0`，三片 `exit=0`（3177 → 3178 正是这条新用例；`test_standalone_chain_http` 由 5 条变 6 条，`PYTHON_TESTS_MODULE_ALL 4.831s tests=6`）。
- **本机 Windows 那条只能在本机量的证据**：把三个模块放进取数器自己的深 TEMP（`.project-local/task-runtime/python-tests-shard-1/313d501449a54770ad3986c2a1ffdd82/tmp`，133+ 字符基底）跑，`Ran 17 tests / OK / exit=0`，无 `WinError 206`、无 `[Errno 2]`、无 skipped——§5.26 那处按成员名判定的解包豁免仍然成立，没有因为本批新增读法而回归。本机整轮 union 未跑完就被中止（该片在 Windows 上单片要 1500s 量级），**所以本枚的"全套通过"读数以 CI 那条为准，本机这条只覆盖 Windows 专有的路径长度面**，不写成全套。
- 一处自己差点留下的错，记下来：播种用的驱动把 `native_assets.py` 改坏再改回，它打印的 `restored identical: True` 比的是**解码后的文本**——那种比较看不见行尾改动，而本仓 `.gitattributes` 是 `*.py text eol=lf`。真正的对账是字节：工作树与 `HEAD` 同一 blob（`11c325be…`，5968 字节，0 个 CRLF），并且仓库自有的 `test_working_tree_line_endings` 在聚合里一直绿。**一条不会失败的校验不是校验**，它只是把事故改成了日志。聚合读数在最终树上：`VERIFY_RESULT=OK total=549 failed=0`、`VERIFY_DESIGN_LAB=OK total=76 failed=0`、`RECORD_REGISTER_GATE=PASS checks=5 problems=0`、`DOCUMENTED_COUNTS=PASS claims=13`。
- 本轮之后：**状态 CI_VERIFIED_EXACT_SHA @ `d9976d0c`**（下面这条记录本身与投影重绑是纯文字＋派生件，另算一枚，不改上面任何读数）。
- 补一枚读数，免得本节点名的 SHA 落后于树上那枚：把两个读侧分母交给闸门现数的那条（`32c78ac2`）与它的投影重绑（`51c14f10`，main 与备份分支现同指此枚）在 CI 上同样 `completed success`——run `39865099663`，12 个作业，无一条非绿（`Branch light gate` 仍按 D01 skipped）。其后若再有纯记录提交，按同一约定另算一枚，不改以上任何读数。

**批次 I 的收尾读数（写成这样，是因为它们各自来自不同的地方）**。CI 那枚是权威：`efa5a8afb7e9b04bd05c7b6ad96f9872d46e4823`
上 main 与备份分支同指，两次 push run `39943398842` / `39943381425` 均 completed success；12 个作业里除
「Branch light gate」按规则 skipped 之外全部 success，无失败作业。Python 作业三分片 exit=0，
`PYTHON_TESTS_UNION=OK expected=3183 distinct=3183 ran=3183 duplicates=0 missing=0 unexpected=0`
（PASS 3161、SKIP 22），同作业内 `VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=68
dispatched=68 bound=54 schema_less=14`、`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=35 failures=0`、
`VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=109 routes=66 matched=55 backend_only=11 dynamic=3 special=1`、
`VERIFY_DESIGN_LAB=OK total=76 failed=0`；清轮安装作业在同一枚上给全三行
`GET_SWEEP layout=installed routes=39 reads=39 answered=35 verdicts=4 unmeasured=2`、
`POST_SWEEP layout=installed rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`、
`NATIVE_VERIFY layout=installed clean=HASH_VERIFIED tampered=NATIVE_ARTIFACT_UNVERIFIED …`，
与本机 §5.29 前面那两组源码/装机读数逐字相同。

**本机整轮没有拿到同一条绿**，这一条必须点名而不是略过：本机三片跑完是 `union-exit=1`，shard 1/2 全绿，
shard 3 报 `outcomes={'ERROR': 1, 'FAIL': 59, 'PASS': 1007, 'SKIP': 6}`，红集中在
`test_reconstruction_evidence`、`test_verifier_internals`、`test_workbench_*_gate`、`test_service_cli`、
`test_ui_layering`、`test_spill_census_tracked_verdict` 这些读整棵树或要 node/浏览器的套件。
**归因未定**，因为那一轮与我往同一棵树里解包、落 20261023 方案包的时间重叠，而这些套件里多数带
snapshot/diff 或 tree-hash 断言——并发写会把自己的活动当成违规。手上有证据的只有一条：把其中两个模块
（`test_ui_layering`、`test_service_cli`）在静默树上单跑，`Ran 15 tests / OK`、`DRIVER failures=0 errors=0 skipped=0`，
所以它们不是本质上坏。结论按证据强度写：**"全套通过"这条只按 CI 那枚报**；本机那 60 项要在静默树上重跑三分片
才能 either 归零 or 升级为真缺陷，重跑结果进下一份读数，不在此处冒充。


### 5.30 第二十七批（规划轮 J0：一份 Record 投递包变成权威、账本与归档三面，而两处工具缺陷先红给我看）

owner 2026-10-23 原话：**「读取分析，按照这个执行（前端UI有新规划），并且归档到统一项目里，更新覆盖替换到权威和规划里」**
与 **「先分析拆解，加入到优先到任务台账里」**。这一批不落产品功能，只做三件事：把投递包逐字节归档并登记、
把权威与规划覆盖替换到新包、把新派工按优先级写进唯一账本。桌面 UI 从此进入当前派工面——批次 I 那句
「前端 0 文件」是 I 的边界，不是此后每轮的边界。

**先量再写（不是抄包里的数字）**。包内 `13_包内一致性核对.json` 自报 `requirementCount 66 / sourceCount 38 /
sectionCount 19`，`00_先读这里.md` 自报观察 `main@2d6ede51`。这些是作者时点，本批一律不引用为现状。本仓
落仓时实测的现状四条：`capability_library.py` 是只读投影（无写入面）、`prompt_intelligence.py` 不调用模型、
`prompt_results.py` 存储层要求 `executed=false`、`model_selection.py` 只记录选择——四条都由代码读回，
与本件 §5.24、§5.26 的旧读数一致，所以新包的"待开发"清单不是凭空列的。合同账本与闸门的读数取
`efa5a8af` 那枚：68 行 = BOUND_SCHEMA 54 + SCHEMA_LESS 14，live 载荷比对 35 条绑定，前端对账 calls=109，
`ROUTE_VIEWS` 21 条。

**归档的取证顺序**：`certutil` 先量两份投递原件（ZIP 70,319 B / `9fadae0ae12712c3…`，HTML 59,898 B /
`614b4a7c15bfb649…`）；解包后拿包内自带的 `SHA256SUMS.txt`（16 行）逐行重算其余 16 名成员，
**0 不匹配、0 缺失**才允许落地；17 名成员 `write_bytes` 落到 `docs/taskpacks/20261023-ui-kb/source/`
（155,573 B），每份落地后立刻回读比哈希。卷宗根下那份 HTML 与包内同名成员**同一 sha256**，
所以只留一份规范副本、另一处登记成别名（`aliases` + `deduplication.groups`），不复制第二份内容对象。
ZIP 原件按 AGENTS.md 既有规则留在 `.project-local/record-archive-2026-10-23/`（Git 忽略）并在两份 manifest
里写明"不随克隆走、迁移须按摘要补齐"。既往普查一律不改写：2026-10-09 的 101 份 / 180 成员、2026-10-11 的
DOT 清单、2026-10-19 的五件波次登记与它们 `summary` 里的计数，本节只追加、不并入（`RECORD-ARCHIVE-INDEX.md`
末节 + 生成器-owned 的五行登记表未动，`RECORD_REGISTER_GATE=PASS checks=5 pathish_named=30 problems=0`）。

**这条 PASS 读数后来跟着一个位移改过一次**：本节原先追加在五件登记表之后，而
`generate_archive_record_register.py` 从自己的标题改写到文件末尾，下一轮再生成直接把它删掉
（76,437 → 73,712 B，`grep -c` 该标题变成 0）；移到登记表之前、与 2026-10-11 / 2026-10-13 两节同侧之后，
再生成逐字节不变。代价是那条闸不再扫描本节的 pathish 引用，`pathish_named` 由 30 回到 21。
两个 `problems=0` 都是各自位置上的真读数，不是同一个扫描范围。


**第一处工具缺陷在我自己身上**：登记完之后 `verify_archive_record_register.py` 报 6 条
"unresolvable path"，其中四条点的是我刚落地的中文名成员。它拿 `git ls-files` 的文本按行切分建集合，
而 git porcelain 会把非 ASCII 路径八进制引用（`"docs/…\345\205\210…"`），于是**已入仓的文件在闸门眼里不存在**。
同一件事在 `.gitattributes` 与 `verify_task_document_states.py` 都用 `-z` 处理过，这条闸门是漏网的那一条。
改成 `git ls-files -z` 后四条同时消失；另外两条是真错——我在散文里给 schema 标识加了反引号
（`design-lab/taskpack-source-manifest/v1` 不是路径），改成不带反引号并写明原因。**这两条都要点名**：
一条是工具的假阳，一条是我的措辞。修完再跑 `git -c core.quotepath=false ls-files` 与 `cat-file blob :path`
逐份复核：**17/17 的 index blob 摘要等于登记摘要**，其中 03/04/05 三份 CSV 的 CRLF（67 / 39 / 10 对）
在 index blob 里原样保留——`.gitattributes` 已为这三棵子树写 `-text whitespace=cr-at-eol`，
否则 `* text=auto eol=lf` 会把登记摘要变成不可复现的机器绑定值（同一件事这件上已记过两次）。

**权威与规划的覆盖替换按 §17 走**：`AUTHORITY.md` 增 `DESKTOP-KB-20261023-R1` 采纳块，并把 2026-10-19 那句
「当前唯一 integrated TaskPack」标为**当日原文 + 更正括注**，不删；`authority-index.json` 的
`current` / `mandatoryAuditBootOrder` / `taskpackClassificationRule.currentIntegrated` 指向新包，方向包进
`lineage` 与 `historicalSpecific`（`SUPERSEDED_DISPATCH_ENTRY_LINEAGE`，replacement 指向新包），新增
`desktopKbAdoption` 机读块（派工段、冻结段未动、前端进派工、模型本轮不部署、手机排除、AAOS 未来合同、
stillFrozen 七项）；`task-document-states.json` 里方向包降 `SUPERSEDED/LINEAGE`、新包升
`CURRENT/DISPATCH_ENTRY`、新前缀规则 `docs/taskpacks/20261023-ui-kb/**`＝FROZEN/RECORD，
`NEXT-AGENT-PROMPT.md` 的 replacement 跟着换。两份被钉面字节变了就重钉：
`AUTHORITY.md 7cd2db03… -> 00126066…`、`authority-index.json fd01ce37… -> 9a0e1a58…`，
`AUTHORITY-PIN-CHANGE.json` 追加第 10 条 revision（意图/原因/被取代/影响/跑的闸），
`R2_RELEASE_HASHES` 其余四项一字未动。**闸数没减**：`TOP_AUTHORITY_GATE=PASS checks=10 failed=none`、
`TASK_DOC_STATE_GATE=PASS checks=13 failed=none`。

**台账加入的做法**：`currentExecution` 的 `validate()` 要求 `set(tasks) == set(definitions.tasks)`，
所以加派工只能换绑定义原件，不能只往账本里塞行。定义原件落在
`docs/history/taskpacks/20261023-adoption/TASK-DEFINITIONS.json`（89,864 B，`e54f55f324626392…`），
**逐字携带 20261009 那份的 34 条定义**再加 16 条新条目——旧原件在 `docs/history/**` 冻结家族里，
按 HISTORY-FREEZE-RULES 不得改写，所以它是被复制携带而不是被编辑；账本 `currentExecution.source` 只钉当前
绑定的这一份，`legacy_snapshot` 与被携带件的出处关系写在 `AGENTS.md` 与裁决件里。账本改前先证明
`json.dumps(..., ensure_ascii=False, indent=2) + '\n'` 与磁盘字节**逐字节相同**才动手（754,760 B →
50 行任务：`{'FROZEN_DEFERRED': 34, 'IN_PROGRESS': 1, 'NOT_STARTED': 15}`，198 条证据一行未增）。
`mobile` 仍是 schema `const FROZEN_DEFERRED`，一个字节没动。

**第二处过期是我自己的闸门**：`verify_documented_counts.py` 原先在**任何**一项离开 `FROZEN_DEFERRED`
时直接 `SystemExit` 拒绝报数，理由写在 docstring 里——解冻是 owner 决定。owner 今天把决定记下来了，
所以这条拒数变成"把新派工也当成谎"，它保护的句子（四处「其余 34 项仍」）其实仍然为真。改成
**两个分开的实测数**：仍冻结 34、当前派工 16，各自钉自己的句子（`claims` 18 → 20）。保护没变弱：
悄悄解冻任何旧行会改 34 这个数，四处句子同时红。播种复证两条都红——把 16 改成 17（界面面）与 15
（任务包）各红一次，把 34 改成 35 也红一次，恢复后逐字节相同（`BOTH_CLAIMS_FALSIFIED_AND_RESTORED`）。
顺带两处硬写数：`current_execution.py` 报告里「22父任务＋12UI子任务」与「本次归档不实施产品」按投影计数与
新边界改写；`test_current_execution.py` 的 `{'NOT_STARTED': 34}` 改成从账本自身取行数，
免得每加一条派工就有人来编辑测试。

**登记件与投影是两次提交**：本件被登记件量着（登记表第五行就是它），所以内容提交之后才跑
`scripts/generate_archive_record_register.py` 与 `scripts/generate_current_reports.py`，
`deepseek_authority_chain.py` 也要重写——新落地的 taskpack/decision/manifest 都进了它的 entries，
不改写就是 `AUTHORITY_CHAIN=DRIFT`。`.project/manifest.yaml` 的 taskpack 指针与账本
`currentExecution.taskpack` 本来就不一致（那条既有 drift 读数保留，不顺手抹平）。

**边界一条没松**：手机端仍是排除项（`mobile` 常量、`AGENTS.md`、`AUTHORITY.md` 三处未改词）；
字体与三方素材仍在范围外；模型不锁死但默认 fail-closed、`UNKNOWN` 不写成合格、云端须披露离开本机的数据，
且**本批不部署模型、不下载权重**；编号仍 `UNUSED`；签署与审核仍只接受具名 human；导出仍只读回；
AAOS 仍只是未来合同；E 盘不动；release / 安装态分发 / 真实宿主 E3 / 真人 E4 / ComfyUI / MiniMax H3
与旧 34 项继续冻结。**本批改动的字节面是权威、规划、登记、台账与三条闸门/一处测试断言，产品代码 0 文件、
前端 0 文件、模型 0 调用**——交付性质是 E1（结构与登记可证）加对既有 E2 读数的引用，不是 E3/E4/release。

---

**批次 J 的 CI 第一次是红的，红在我身上，而且红得准确。** `a8e802e4` 上 11 个作业里 Python 作业失败，
shard 1/3 三条红全在 `test_record_import_fidelity`：`test_every_repo_held_row_is_accounted_for`
（`475 != 479`）、`test_recorded_hashes_match_the_files_on_disk`、
`test_the_archive_still_equals_what_the_manifest_recorded`。原因是我为了覆盖替换而改写的四份文件
（`AUTHORITY.md`、`.project/governance/authority-index.json`、`docs/current/PRODUCT_DEFINITION.md`、
`docs/current/ROADMAP.md`）**同时也是 2026-10-08 Record 导入清单的 repo 侧持有行**——清单把它们钉在
"导入后仓库副本"的摘要上，我改了字节却没有声明演进，于是 leg 2 只能报 WORKTREE-MISMATCH，
把一次诚实的覆盖替换伪装成静默损坏的样子。修法不是放宽断言，而是走仓库自带的声明器
`scripts/declare_record_evolution.py`：它只写 `repoBytesAfterImport/repoCrc32AfterImport/repoSha256AfterImport`
与 `evolvedBy`（commit 由 `git log -1 -- <path>` 现读，不手填、不虚构），归档的 `sha256/crc32/bytes` 一个不动，
leg 1 仍对源 ZIP 可验。声明之后 `RECORD_VERIFY=OK blobs=HEAD`
（`rows=492 source_verified=492 worktree_verified=479 blob_verified=466 blob_eol_only=13 blob_absent=0 moved_rows=3 skipped=0`），
`test_record_import_fidelity` 本机 `Ran 4 tests / OK`。
**这条教训的形状值得单独记一句**：权威面不是自由字节。改一份被别的登记件量着的文件，必须同一轮里跑那个
登记件的声明器——`AGENTS.md` 不在清单里，`AUTHORITY-PIN-CHANGE.json` 也不在，唯独我改的四份在活动面上。
第一轮没跑它，是因为我把这四份当"权威"而不是当"被绑定件"看。

**本机整轮那 59 FAIL + 1 ERROR 现在有读数了，不是并发写、也不是代码。** `scripts/verify_spill_census.py`
在 `RuntimeTests.test_the_check_passes_reports_machine_state_and_writes_nothing` 里报
`AssertionError: 'INCOMPLETE' != 'PASS'`，报告体是 `rootCensus … truncated=true cappedAt=4096`；
本机现数 `.project-local/task-runtime` 有 **308,833** 条目、`.project-local/task-artifacts` **9,153**、
`.project-local/projects` **472**，全部是历轮运行与测试自己写出来的忽略根。也就是说这条闸今天在这台机器上
**量不出来**（它拒绝把截断当干净，正是它该有的行为），依赖该判定的套件跟着红；CI 是干净 checkout，
那些根本不存在，所以同一枚 CI 绿。两次静默复跑（`415.7s` / `414.4s`）失败模块与耗时一致，确认是确定性状态、
不是竞态。**处置也不是"删掉就好"**：`currentExecution` 的多数回执按 `artifact_sha256` 绑在
`.project-local/task-artifacts/**` 的字节上，删了就把证据面自己删了——要么按审计确认后再清、
要么由 owner 决定把上限调到能覆盖真实状态并同步那句话，两条都不是本轮可以顺手做的。

### 5.31 第二十八批（批次 K 第一刀：知识库从账本行变成能写、能搜、能读回的桌面纵切）

owner 的批次顺序是 K0 知识管理与中文检索 → 中立方案与目标档案/导出 → 一个方案助手模型的真实接入 →
内容方法与反馈。这一批落 K0 的第一刀，四个任务按派工顺序做完：DL-KB-02（写面）、DL-KB-04（中文检索）、
DL-KB-03（知识与提示词库屏）、DL-KB-06（三入口外壳）。验收判据不是"文件在不在"，而是真实前端 +
真实 API + 持久化 + 进程重启后读回 + 错误态；四项都按这个判据留了读数。

**① 写面是六条路由，不是一段说明。** `src/design_lab/knowledge_library.py` 落三张表
（`knowledge_entry`、`knowledge_entry_revision`、`knowledge_index_state`），`http_service.py` 加六条路由：
`GET /api/knowledge-entries/search`、`POST /api/knowledge-entries`、`POST /api/knowledge-entries/import`、
`POST /api/knowledge-entries/index-rebuild`、`GET /api/knowledge-entries/(kentry-…)`、
`POST /api/knowledge-entries/(kentry-…)/revisions`。HTTP 路由 66 → 72，合同账本 68 → 74 行
（`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=74 dispatched=74 bound=60
schema_less=14`：六条全进 BOUND_SCHEMA，SCHEMA_LESS 仍是 14）。四件套同一批付：`contract-bindings.json`
六行（emitter 指向真正写 `schemaVersion` 的那一行）、六份 schema 进 `design-lab/schemas/` 并进打包三件套、
`verify_route_payload_contracts.py` 的活载荷用例（bindings 35 → 41）、`verify_workbench_route_calls.py`
认得前端调用（`calls=117 routes=72 matched=61 backend_only=11 dynamic=3 special=1`）。
写侧扫描 `POST_SWEEP layout=source rows=33 walked=32 written=32 read_backs=39 refused=0 excluded=1`，
被排除的仍是 §5.27 那条 FROZEN-BY-POLICY 的 native 派发，不是新缺口。

**② 修订只追加，不覆盖。** `_write_revision()` 在同一个事务里删旧 FTS 行、插新修订、推进
`knowledge_index_state`；条目身份 `kentry-` 不变，修订号递增，旧修订留在表里。
`_fields()` 要求 title/summary/body，静默字段一律 `UNKNOWN`（不拿空串冒充"没有"）；
`_source()` 拒绝把 `VERIFIED` 与未知许可/已复核这两对矛盾写进去。`test_knowledge_library` 17 项 OK
（含"只准 trigram 的两字中文必须 miss"这条对照）、`test_packaged_contract_resources` 6 项 OK、
`test_backup_watches_written_tables` 5 项 OK、`test_installed_write_surface` 与
`test_standalone_chain_http` 各 6 项 OK——最后一条是进程内真写、真读、真回执，不是 mock。

**③ 中文检索的判据是「短词必须命中」，不是「英文能搜」。** FTS5 的 trigram 对两个汉字没有词元，所以
`分镜`/`粒子`/`品牌` 走 `SHORT_FALLBACK`（子串回退），`panasonic` 走 `TRIGRAM`；单元层先断言只准 trigram
时两字中文必须 miss，再断言回退命中——英文通过不算中文可用。1,000 条经真实回环 HTTP 播种后的读数
（`kb-search-http.log`，`KB_HTTP_PROBE_COMMIT=7f5e68d7…`）：四条查询 `"total": 1000` 全部命中；
零结果查询 `"total": 0` 并带解释「检索只匹配标题、摘要、正文、领域/任务标签和目标工具，不做近义词扩写，
也不推荐未命中的相关条目」。p95：单元 26.1 ms、HTTP 30.4 ms，预算 300 ms（各 30 次采样，1,000 条）。
阈值与读数在同一份日志里发布，不先写"很快"再补数字。

**④ 界面是按渲染结果改出来的，四处缺陷各有一条可复跑的检查。** 所有 PNG 都是真实 Chromium 对真实
回环服务的读回（bundle `apps/workbench/build/main.js` sha256 `6bbd86d9…`）：①「新增 / 导入 / 重建索引」
在 1440 下被挤成两行（`1a7b7a2b`）；② 零结果标题重复服务句子，屏上读成「没有命中的条目没有命中「…」的条目。」
（`2ac55ce1`）；③ 新增/导入表单打开后只能靠写入成功消失，改主意只能离开页面（`4ffa77b8`，行动区加「取消」，
探针真点击后断言表单从 DOM 移除）；④ 零结果时右侧仍挂着上一次选中的完整详情，读起来像本次命中
（`7f5e68d7`，加「右侧是上次选中的条目，不在本次检索结果里」并由 `apps/workbench/tests/appshell.mjs` ㉓ 断言）。
首屏 50 行、`加载更多（已显示 50 / 共 60）`、点击后 60 行且按钮消失；空库与零结果是两句不同的话，
都给出下一步，不编造示例条目。

**⑤ 导航是派生的，缩放是量的。** `ROUTE_VIEWS` 21 → 22，侧栏仍是
`ROUTE_VIEWS.filter(...).map(...)` 派生而不是手写清单；采集器把渲染出的按钮集与服务路由表逐项比对：
`CAP_NAV_SET rendered=21 expected=21 equal=1`，`CAP_ROUTE_COVERAGE routes=22 captured=24 of 22
pageEntries=26`。100%/125%/150% 三档（1920×1080 物理屏 → 1920/1536/1280 CSS 宽）用 Tab 实测：
三档都按 21 次到达「知识与提示词库」，焦点环 3px solid、`fullyInsideNav=true`；150% 时侧栏滚动 263px
把它带进视口（`navScrollTop` 0/17/263），三档 `scrollWidth == innerWidth`，无横向溢出。
侧栏四个分组标签「设计辅助 / 知识与提示词库 / 我的方案 / 设置与诊断」与右上角设置入口在回执里逐项可读；
没有 AAOS 入口、没有连接按钮、也没有"未连接"红灯。

**⑥ 这一批有三处红是我自己造的，形状都记下来。**
第一处是**日志的编码也是证据**：`unit-knowledge.log` 与 `test_standalone_chain_http.log` 是重定向的 Python
stdout，在这台机器上按 cp936 写出，`verify_identity_gate.py` 报 `IDENTITY_GATE=FAIL total=2 scanned=3219`
并给出具体字节位置——闸门是对的。改用 `PYTHONIOENCODING=utf-8` 重跑，单元 p95 由 24.7 变 26.1（同一套件、
同一台机器，重跑读数），所有被绑定的摘要跟着重算；`VISUAL-REVIEW.md` 里那句 p95 也随之改成
「24.7（首发）/ 26.1（UTF-8 重跑）」，两条绑它的视觉回执与 `evidence-index.json` 同步重绑
（`736d5eaae0fa…`），追记的是读数来源，不是重新测一遍。
第二处是**自引用工件**：`test_standalone_chain_http` 会打 `/api/evidence-projection`，而这条路由在运行中
重新哈希账本绑定的工件路径；一旦把 stdout 重定向到它自己那条已绑定的日志上，服务读到的就是"正在写的文件"，
返回 `500 EVIDENCE_LEDGER_REJECTED … current evidence artifact hash differs`。这不是产品缺陷也不是闸门缺陷，
而是测量顺序：改为先写临时文件、跑完再把最终字节装回工件路径、最后绑摘要，才自洽。
第三处是**投影比我诚实**：`VERIFY_PROJECTION_FRESHNESS` 指出 `CONTRACT-GRAPH.json` 的 `declared_tables`
少三张（42 → 45，正是这一族的三张表），`INERT-CONTRACT-SURVEY` 则是"从已经移动的代码上算的"；
两者在 `6d8ee5b5` 重新生成。修完 `VERIFY_DESIGN_LAB=OK total=76 failed=0`。

**⑦ 账本只说它量到的事。** `currentExecution` 50 行 = 34 `FROZEN_DEFERRED` + 1 `IN_PROGRESS`（DL-KB-01）
+ 4 `PARTIAL`（DL-KB-02/03/04/06）+ 11 `NOT_STARTED`；证据 198 → 216 条，18 条新回执全部绑
`7f5e68d7` 的产物。四条是 `PARTIAL` 不是 `DONE`：**真人验收没有发生**，本轮最高只到 E2（受控运行时），
不是 E3（真实工作流），更不是 release。证据包 `kb-20261023/` 共 48 个文件，其中 47 个（索引自身除外）
逐份登记在 `evidence-index.json`（字节 + sha256）；13 张截图（3 张空库、7 张播种、3 张缩放）各带许可
sidecar。这份清单在收尾时按磁盘字节重扫过一次：首版只覆盖当时的 35 个文件，并集修版轮新增的两份闸门
日志与十份 sidecar 原不在其中，条目数这才与目录里的文件数对齐（索引保留原 `commit: 7f5e68d7`，
因为它登记的是那一批产物，重扫只是重新哈希，没有重拍任何一张图）。

**⑧ 全量并集抓到的五处红：两处是钉死的测试没同改，两处是账没跟着 CSS 走，一处是真版式缺陷。**
`PYTHON_TESTS_UNION=OK expected=3200 distinct=3200 ran=3200 …` 之后 `FAIL=5`。
`test_route_payload_contracts` 的族清单没有六条知识路由（闸门原话：「a binding added here without being
listed below is a boundary this file silently stopped covering」），`test_workbench_css_single_definition`
仍钉 53 个 `.list` 容器而实测 59——新增的六个在注释里逐一具名（设置页的模型服务与备份诊断两个面板，
知识屏的条目字段 / 来源许可 / 修订历史 / 服务 `does_not_say` 四组；检索结果容器是原位替换，不计入）。
补上后两个模块各自 31 / 17 项全绿。`test_workbench_theme_geometry_gate` 单独复跑两次均绿，
暂记为并集里的环境性红，待重跑复核，不写成已解释。
真缺陷是 **390px 窄窗底栏**：`.nav-group` 在横向滚动条里没有 `flex`，默认 `0 1 auto` 把它压到
31.9px，四个字竖排成 121px，按钮跟着 `stretch` 到同一高度，整条底栏 138px，超过 E2E 的 120px 阈值
（`browser_design_layer_e2e.mjs` 的 `mobile appshell layout`，码 11）。分组标签自 `147e6dc9` 起就在
扁平导航里，本轮把组名换成更长的三入口名字后实测越线；旧包高没有回测，这里只断言当前字节的读数。
**没有放宽阈值**：同一个 `@media(max-width:760px)` 里给 `.nav-group` 加
`flex:0 0 auto; white-space:nowrap; align-self:center`，先证伪再修——隐藏标签 138→56，标签单行不收缩
同为 56，修后 E2E 两个用例通过。这条按桌面窄窗口自适应处理，不是手机端交付，也没有把手机端列为待办。
另两处红是账要跟着 CSS 走：`verify_asset_governance` 指出 `shots/seeded/knowledge-zoom-150.png`
（356 KiB）没有声明 bundle，已在 `large-assets.json` 增加 `kb-20261023/`（实测 3.11 MiB / 预算 4.0 MiB，
理由写明账本摘要直接绑定这些字节，不能挪进 Git 忽略目录）；`design_debt_baseline` 因新增一条规则把
字面 px 从 514 变 516，`DESIGN.md` §4 的那句同改。两处完成后 `VERIFY_PROJECTION_FRESHNESS=OK`、
`ASSET_GOVERNANCE=OK`、`VERIFY_DESIGN_LAB=OK total=76 failed=0`。

**边界一条没松**：手机端仍是排除项（本轮只在 1920/1536/1280 的桌面 CSS 宽上量）；
字体与三方素材仍不在本项目范围内；模型不锁死但默认 fail-closed，本批不部署模型、不下载权重；
编号仍是字面量 `UNUSED`；签署与验收仍只接受具名 human；导出仍只读回；AAOS 仍只是未来合同；
E 盘不动；release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 与旧 34 项继续冻结。

**仍然未证（写在这里，不留到下一轮才发现）**：真实中文知识语料只有探针合成的 2 + 58 条，
不含 owner 的实际条目；写入路径的逐屏截图只覆盖新增，修改与导入靠单元/接口层测试；
1920 只截了空库；1280×800 首屏侧栏只露出第一个分组（有滚动提示，150% 的 Tab 实测证明可达，
本轮未改版式）；详情徽章同时显示「最新 r1」与「非推荐版本 r1」，语义正确但可读性一般，留给版式轮次。

## 6. 本轮暴露并修掉的六个缺陷

1. **分类聚合按目录贴标签**：`bundle_key()` 把一个顶层目录收成一个 bundle，于是 `docs/` 里第一个文件的类别
   给整个目录命名，`planning` 从投影里消失。改为逐文件计数，并核对九类之和 = 跟踪文件数。
2. **钉死文件的行尾被工具改写**：Windows `Path.write_text` 把 `\n` 写成 `\r\n`，三个 `binary` 文件因此
   真实字节变化——而我照着重钉了哈希，于是所有闸门全绿地放过了一个非本意的改写。已按原像恢复并重钉。
3. **降级检查被静默关闭**：`verify_top_level_authority.py` 的 `handoff-demoted` 仍查归档前的旧路径，
   找不到文件就 `PASS — absent; nothing to demote`。现经 `archive_records` 三层解析读回原件字节；
   把 UCR 条目的 `restoreAt` 改成假 SHA 后该门 `FAIL` 且退出 1（已实测）。
4. **钉死文件被浅克隆读不到**：上一缺陷修好后，CI 仍红——该 job 用默认 `fetch-depth: 1`，
   没有 `restoreAt` 那个 commit，本地全历史却看不见这个差异。补 `fetch-depth: 0`，并改掉步骤注释里
   已经失效的"只读工作树"说法。
5. **recovered 不能变成免检通道**：删档后证据测试的漂移清单少了一项、篡改测试挑中被删工件从而"什么也没测"。
   漂移计数按实测 delta（+1，正是被本轮改动的闸门模块自己老化了它绑定的记录）改为 60 并写明因由；
   篡改测试改选仍在树上的工件；新增精确 pin 的 recovered 断言（藏掉 `REMOVALS.json` 即回退为
   `tracked_broken=4`）。
6. **一条已关闭的债留在开放清单**：`CLEAN-TREE-REPORT.json` 的 `subject_sha` 已在本轮一次有意的生成器
   运行中绑定真实 commit，`REPORT-DEBT-CLOSED-NOT-REMOVED` 拒绝让记账落后于事实；按登记簿自己的机制
   移入 `resolved_2026_10_19`，并写明该运行连带 re-base 了 `DLDS-I020` 引用的证据。

## 6.5 第七个缺陷（本次复核自己发现的）

7. **清单把自己的删除也算清楚了**：`MANIFEST.json` 原写 "228/228 复验一致"，删除波之后这句话就过了——73 条已不在树上，再生成器也会直接 SystemExit（下次谁再跑它就是一颗地雷）。现在已删行带 `status=REMOVED` 与 `restoreAt`，`summary` 分列 `byteIdentityVerified=155` / `removedSinceThisPass=73`，并与 `REMOVALS.json` 的 blob/字节互相对账后才落盘。

## 6.6 第八个缺陷（owner 追问「还有没做完的吗」时暴露）

登记节把 `MANIFEST.json` / `REMOVALS.json` / 汇总登记的产出方式写成 `.project-local/task-runtime/*.py` 三条命令，并把它叫「生成命令」。实测该根下 40 个脚本**全部被 Git 忽略**（`git check-ignore` 逐条为真），所以这些命令只在这台机器上跑得通：一个新克隆按登记节去复现，会得到「找不到脚本」，而我上一轮还把它们说成「可复用的自审工具」——那是过诺。

处置不是补一句免责声明，而是把**复现路径**变成受审面：`scripts/verify_archive_record_register.py`（只读，把登记节反向解析后逐条对 `git cat-file blob HEAD:` 重算，任何不一致即 `FAIL` 并退出 1）与 `scripts/generate_archive_record_register.py`（重建本节，小节清单与计数直接从报告正文里读，不再手写枚举）入库，登记节改引这两条。那三个一次性波次工装仍留在 `.project-local/`，并写明「不在 Git 里、本节数字不需要它们也能复现」——它们的写侧会改 `docs/history/**` 冻结件，不该做成常备命令。

## 6.7 第九个缺陷（UI 对齐走查发现，先量化再修）

侧栏导航是唯一滚动区，身份页脚紧贴其下。列表在底部边缘必然把某一项切一半，而页脚的 1px 上边框正好压在那条切割线上——读起来像有人给半个分组标签画了下划线。上一轮我只在 1440 下用眼睛看到它，没量化，所以当时按"未测量"记成了待裁定项；本轮先测再说：`OV_NAV_EDGE_TIGHT 1440/1280/1920 gap=0`，且三个宽度上被切的那一项都是 `nav-group` 分组标签。

任何 CLIPPED 检查都看不见它：元素在自己的盒子里是完整的，盒子只是被滚动了。修法是给导航一个 token 级下边距（`--uif-space-3`，实测 `gap=12`），让切割线与边框分开——滚动列表躲不开切项，但可以把切项离线。同时把这条边界做成闸门：溢出审计现在逐宽度量导航底边与页脚边框的距离，切割线 6px 内出现边框即 `OV_NAV_EDGE_TIGHT` 退出 2（先以未修字节实跑为红，再以修后字节实跑为绿，不是推定）。

## 6.8 第十个缺陷（写现行面时删掉了邻居的冻结条目）

给 `docs/current/NEXT-AGENT-PROMPT.md` 追加接口层普查那条时，`old_string` 只取了既有条目的**第一行**。编辑工具按整段匹配替换，于是连带把「ComfyUI/H3、外部服务、跨仓库写入、数据外发、E 盘访问：全部冻结/需授权」整条删掉，并把它的 AAOS 续句并进了我的新条目——一次自以为是"纯追加"的写入实际做了一次改写。删掉的这条是范围边界条款，在"现行面"上把它抹掉，等于对下一个会话放宽 owner 边界，比写错数字更严重。

发现靠的是把写回读回来，而不是靠 diff 看着顺眼：编辑后立即读该区域，看到两条被合成一条，再按"这条改动应当是若干行新增、零行删除"去验——`git diff --stat` 报 7 行新增却同时有删除，就是断言不成立的信号。修法是重新拆成两条，并确认提交的 diff 为 `1 file changed, 7 insertions(+)` 且**零删除行**。既有那条「往满行条目里追加时锚点要取完整边界」的教训在文档面同样成立，这次是它的一次复发，因此记进报告而不只记进记忆。

## 7. 回滚方法

- 单文件还原：`git checkout <restoreAt> -- <path>`（`REMOVALS.json` 每行都带 `restoreAt` 与 blob）。
- 整批还原：`git revert` 删除提交与归档提交（两者都只动路径/登记，不改任何被钉的原件字节）。
- 重钉回退：`AUTHORITY-PIN-CHANGE.json` 每条 revision 都保留 `from` 摘要，可据此把
  `R2_RELEASE_HASHES` 指回前一版并同步还原文件。

## 8. 风险与下一步

- `recovered` 只证明"字节还在对象库里"，不证明"内容仍与记录一致"——被删工件无法再做内容漂移比对。
  这是删除的固有代价，已在测试与注释里说明，不用放宽断言来掩盖。
- 账本 `tasks`/`evidence` 仍指向 `docs/handoffs/…` 的 sealed 路径：只要 `REMOVALS.json` 与 blob 在，
  读回成立；若将来做 history rewrite 或浅克隆依赖，这条会立刻变红，而不是悄悄变绿。
- 下一刀不在本轮范围：release / E3 / E4 / AAOS 接收 仍等 owner 授权；手机端不是"等授权"，是 owner 2026-10-19 已定的排除项（§6 冲突矩阵第 5 行）。
  `docs/taskpacks/` 剩余四份包体只有在 owner 允许改被钉索引时才能再搬。

## 9. 技能走查记录：量到了什么，量不到什么

owner 点名要"调用技能插件辅助执行"，本轮实际用了三类，各自能证明的东西不一样，写清楚免得下一轮把它们当成同等证据。

**能用的**：仓库自有合同（状态词不翻译、空态必须区分"没有数据"与"没读到"、界面不得宣称服务发不出的判定）逐条对照渲染结果，加上 `design-review:ui-alignment-review` 的走查框架，产出了 §6.7 那条真实缺陷——它先被记为"未测量、待裁定"，量化之后才确认成立并修掉。流程是对的：走查框架负责把问题问出来，闸门负责把数字钉住。

**量不到的，三处，都写下来而不是假装通过**：

1. **跨轮视觉回归不可用**。没有播种的 fixture（数据、时间、随机源都不冻结），两次截图的差值里混着真实数据变化，diff 比例没有解释力。所以本轮的视觉判断依据是 1440 下逐张人工查看加几何断言（`OV_*`、对比度、主题几何），不是像素回归；要做像素回归得先有一个冻结 fixture 的基线面，那是另一件事。
2. **插件自带的 debt 扫描与仓库自有基线口径不同**。它按自己的规则集计数，`scripts/design_debt_baseline.py` 按登记簿逐处对账，两个数字不可互换。本轮以仓库自有基线为准（`DESIGN_DEBT_BASELINE=PASS`，literal_px=534 未增），插件结果只作参考，不进闸门读数。
3. **没有批准的视觉参照物**。仓库里没有 Figma frame 或经批准的基线截图作为设计目标，所以 alignment 的对照面只能是自家权威文本（定位句、状态词、空态合同）。这意味着本轮修的是"界面与已声明合同是否一致"，不是"界面是否符合某个视觉稿"——后者要 owner 先给参照物，不能由 agent 代拟。

**没有做的**：`product-design:flow-web` / `design-review:ui-designer` 一类会**新画界面**的技能未调用。当前 `currentExecution` 34 项全部冻结、本轮明令"不实施产品功能"，生成新屏等于绕过解冻门；要新屏需 owner 明确授权。

**一条被测量否证的猜想**（写下来防止下一轮重追）：1440 全页截图里 "制作记录与待继续" 看起来像断行成两行、末行剩一个孤字。实测否证：该标签文本宽 150 px、可用 211 px；把 `.nav` 强行压到 96 px 后 22 个导航项**没有一个**发生换行（flex 子项默认 `min-width:auto`，不缩到内容宽以下，所以这条构造的失败模式是横向溢出，而那正是溢出闸门 `CLIPPED/STRAY` 已经覆盖的）。三次仪器失误也记在这里，因为它们的错法各不相同：用盒高÷行高会把带 padding 的按钮读成两行；对元素建 Range 得到的 `getClientRects()` 数目是**行内盒**数（图标 span 也算一条），两者都会凭空造出 18/22 条 "WRAPS"。只有对最深文本节点取矩形高度除以 `line-height`，再配一个"压窄容器必须看到换行"的播种对照，才敢用它说"没换行"——本条结论正是那个对照说"仪器是瞎的"之后才敢下的。

## 10. 像素回归实跑（§9.1 那条判断这轮被自己验了一遍）

上面第 1 条说"跨轮视觉回归不可用，因为 fixture 不冻结"。这句话本身是个断言，所以本轮用仓库自有工装（`scripts/capture_workbench_screenshots.py --widths 1440`）重采了 23 张，与改动前的基线逐张比对，产物全部落在 gitignore 的 `.project-local/task-runtime/ui-capture/` 下，没有覆盖任何基线，也没有动跟踪文件。

结论：**没有发现属于本轮三处可见改动之外的布局回归**；同时 §9.1 成立——整页 diff 比例在这套 fixture 下没有解释力。按布局带分开看：

| 带 | 变化 | 判读 |
| --- | --- | --- |
| 品牌块（x<300, y<140） | 23 张全部 **0 px** | 48×48 图块与首行没有动，这是本轮唯一直接改到该区域的改动，未产生意外位移 |
| 导航带（x<300, y≥140） | 每张 48–52 px | 取最干净的一对（`10-collaboration`，其内容带只差 2 px）逐行落位：7 行各 4 px 落在 `x=35..40`（每个导航点的左右边缘列，x 范围与行号与基线完全一致，只是边缘像素振幅差 10/255），另有 4 行各 2 px 落在 y=816/817/849/850——那正是 `b5e57911` 把页脚发丝线推下 12 px 的位置。前者是同一几何下的亚像素边缘差，不是位移，更不是换色 token |
| 内容带（x≥300） | 合计 260,539 px，但高度集中：`21-records` 106,666、`18-intake` 46,854、`15-domain-detail` 28,483，而 `10-collaboration` 只有 2 px、`05-brand-systems` 49 px | 直接并排看了 `21-records` 两张：基线是"制作记录 (0)"配空态句"空列表是读回结果，不是失败"，新图是"制作记录 (1)"配一条真实 `RECEIPTED` 作业行（`job-857a8ee…`、`att-4028758e…`），项目下拉里是 `Closeout 1792433865945` 对 `Closeout 1792439576861`。版式、间距、字号、徽标一致，差的全是播种数据与时间戳 |

两个仪器教训值得记：整页 `getbbox()` 在有活数据的页面上毫无用处——一个十六进制字符变了就能把框拉到 `x=1411`，所以第一版脚本输出的框全是"整页"，必须改成按带计数才看得见结构；以及"两张图差多少像素"这个问题问错了对象，该问的是"差在哪个带、几何有没有动"。

**基线没有被更新**：按回归评审自己的规矩，基线只能在 owner 认可实现结果后重制，owner 本轮未看这批图，所以旧基线原样留着。要让像素回归成为可用闸门，缺的不是阈值而是**一个冻结 fixture 的采集面**（播种项目名、冻结时间、固定作业行），那属产品工装，等授权再动。

### 5.29 第二十六批（后端 I：设计层这一族从"账本记 SCHEMA_LESS"改成了有合同，而守卫第一个判红的是我自己的补丁）

owner 这句仍是「继续打磨后端」。§5.27/§5.28 把两侧都搬进了"装好的包"里度量，但账本里 `SCHEMA_LESS`
还剩 32 行，其中 **20 行属于设计层这一族**（brief / direction / design-layer / design-system-tokens），
18 行没有合同。这一族不是边角：它是 `#/brief`、`#/direction`、`#/system` 三块面板的读回面，也是
`CHAIN_HOPS … brief=201 direction=201 design-layer=200` 那两跳走过的地方。这一批改的就是那 17 行。

**① 开局现数，不抄任何提示词里的数字**（全部当场打出）：账本 68 行 = 39 GET + 28 POST + 1
`GET+POST`，`BOUND_SCHEMA` 36 / `SCHEMA_LESS` 32；这一族按路由名第一轮量成 20 行 = 3 已绑 + 17 未绑，改用**账本的 handler 落在 `design_layer` 的哪几个方法上**重量得 21 行 = 3 已绑 + 18 未绑——漏掉的是 `GET /api/design-systems`：它的行形状已经被 `design-layer-rollup-v1.schema.json` 的 `$defs.design_system` 绑住，而它自己的信封不带版本，留它就是留一个半态，所以一并付掉；载荷闸门
`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=17 failures=0`；界面调用面
`VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=109 routes=66 matched=55 backend_only=11 dynamic=3 special=1`
——未绑的 17 行里 7 行是 `backend_only`（单读简报、方向列表与单读、四条 lineage 中的两条、
两条 id 域 revisions），也就是说它们没被界面读过，但**被两侧扫描真写过真读过**，付款的依据是那两个
扫描的字节，不是面板。

**② 文档是先量字节再写的，不是先写再对着代码看**。用一次性服务把这一族每条路由的回答打出来
（`.project-local/scratch/g/probe5.py` 打 11 读 6 写的键集与形状，`probe6.py` 补 id 前缀、目录
evidence 档位、可选字段全缺时的 null、被超版链与 `active_binding` 非空那一支）。量出来的东西决定了
四条判据：token 文档 id 前缀是 `tokdoc-`；目录行的 `evidence_level` 今天是 `E0`/`E2`（因此
pattern 写成 E0–E5 阶梯而不是某个值）；`style_notes/color_mood/typography_mood/actor/actor_kind`
按 `design-lab/schemas/state/design-lab-state-design-layer-v1.sql` 的 NOT NULL 与否定可空性，
`actor_kind` 直接钉成 `human|agent|null`（表上 CHECK 就这三个）；`token_count` 的 `minimum: 1`
是从 `design-lab/schemas/state/design-lab-state-design-layer-v4.sql` 的 CHECK 抄来的，不是我给的。

**③ 四份信封合同，形状一律 `$ref` 不重述**（"一份合同只有一个主人"）：
`design-lab/schemas/design-record-v1.schema.json`（`design-lab/design-record/v1`，一条记录的信封，
读写共用，`record_kind` 判别，brief 引 `brief-readback.schema.json#/$defs/brief`，direction/binding
在此首次做主人）、`design-collection-v1.schema.json`（`design-lab/design-collection/v1`，
`collection` 判别；方向页必须有 `next_cursor`、token 页**禁止**有，因为读侧真的没有分页）、
`design-lineage-v1.schema.json`（`design-lab/design-lineage/v1`，`subject_kind` 判别）、
`design-layer-rollup-v1.schema.json`（`design-lab/design-layer-rollup/v1`，`chosen_direction` 与
`active_binding` 只能是 `null` 或一条真记录——P0-02/P0-D 那两个"不许回落"的规矩从此不只是注释）。
DTCG 文档引 `interop-dtcg-document.schema.json`，因为那份文件才是它的主人。

**④ 服务侧每次都判，而且第一个受害者是我**。`_check_design_record` / `_check_design_collection` /
`_check_design_lineage` / `_check_design_rollup` 装载自己的合同，先比 `schemaVersion` const 再校验，
不符就 500 带字段路径（`DESIGN_RECORD_CONTRACT_VIOLATION` 等四个具名码，沿用
`BRIEF_CONTRACT_VIOLATION` 的形状）。我按下第一条守卫的地方就是我自己写的补丁：`get_design_layer`
被我包成了 `{design_layer: {design_layer: {…}}}`，实跑立刻
`500 DESIGN_LAYER_ROLLUP_CONTRACT_VIOLATION`，detail 七条
（`'briefs' is a required property` ×6 + `Additional properties are not allowed ('design_layer' was unexpected)`），
抛出点在 `src/design_lab/design_layer.py` 的信封函数里——先红的是我的编辑，不是产品，也不是闸门。
emitter 行号从源文件重算：`:104/:105/:106/:107` 四个版本常量，`BRIEF_READBACK` 的 `:64` 一字未动
（新常量全插在它下面，就是为了不动那条已被账本钉住的指针）。

**⑤ 点名更正一条我自己写错的断言**：账本 brief 链那行的旧 reason 写着这条文档是
"superseded_by 链**加 design_layer_event 行**"。实测字节里没有事件行：`_chain()` 读
`design_layer_event` 只是用 `*-revised` 载荷里的 `new_id→old_id` 找回父行，交出的仍是记录本身。
新的 reason 按实测改写，并把事件 kinds 的归属写明白——仍由 `EVENT_KINDS`（`design_layer.py`）与表
CHECK 管，不由这份 schema 管。旧读数在本节保留原文以便对照，不删。

**⑥ 载荷闸门只变大不变松**：17 条绑定 → 35 条，新增的 18 条里 17 条各两例真实载荷（目录那一行一例，`catalog()` 没有空分支可给）——活梢与被超版、
有内容与空项目、追加（201）与同一幂等键的重放（200），没有一条用一个载荷冒充多个边界。
`design-lab/tests/test_route_payload_contracts.py` 的绑定清单钉同步扩到 35 项（这条钉本身就是"加了
绑定却没进清单"的红），并新增五条只针对这一族的种红：判别器说谎（brief 体配 `record_kind=direction`
同时触发 `SCHEMA_VIOLATION`/`MISSING_FROM_EMITTER`/`UNDECLARED_BY_SCHEMA`）、链丢 `root_id`、
token 列表凭空长出游标、`{}` 冒充"没有选择"、追加与重放键集必须一致。该模块 31 项 OK。

**⑦ 打包三件套，并证它会红**：四个新读取点全走 `runtime/state_resources.repo_resource()`，
`pyproject` 补四行 force-include，`design-lab/tests/test_packaged_contract_resources.py` 从磁盘枚举
调用点（42 项含 `test_contract_bindings` 全 OK）。植入检查：把装好的 wheel 里
`design_lab/resources/repo/design-lab/schemas/design-layer-rollup-v1.schema.json` 移走，装机扫描
`Ran 6 tests in 0.099s / FAILED (errors=6)`，traceback 落在
`design_layer.py:114 → state_resources.py:101 FileNotFoundError: packaged repository resource missing:
schemas/design-layer-rollup-v1.schema.json`——拒绝发生在**导入期**，比路由 500 更早、更硬，与既有
`BRIEF_READBACK_SCHEMA_PATH` 同一个形状，不是新引入的风险类；装回即 `Ran 6 tests / OK`。
wheel 从 1,073,608 字节到 1,082,262 字节，成员 354 → 381。

**⑧ 两侧扫描的语义与读数一字未动**，这是"不改扫描来迁就合同"的可复核部分：源码
`GET_SWEEP layout=source routes=39 reads=40 answered=36 verdicts=4 unmeasured=2`、
`POST_SWEEP layout=source rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`、
`NATIVE_VERIFY layout=source clean=HASH_VERIFIED tampered=NATIVE_ARTIFACT_UNVERIFIED unknown=NATIVE_ASSET_NOT_FOUND`；
装机 `GET_SWEEP layout=installed routes=39 reads=39 answered=35 verdicts=4 unmeasured=2`、
`POST_SWEEP layout=installed rows=29 walked=28 written=28 read_backs=34 refused=0 excluded=1`、
`NATIVE_VERIFY layout=installed` 同串，`CHAIN_HOPS … design-layer=200 … export=200` 与
`DELIVERY_HOPS project=201 native=READBACK bundle=201 preflight=200` 照旧。信封是加在回答**上**的。

**⑨ 受治散文的数字全部交闸门现数**：`scripts/verify_documented_counts.py` 加三条测量
（这一族付掉的行数、账本还剩多少行没有合同、载荷闸门现有多少条绑定），claims 15 → 18，
`DOCUMENTED_COUNTS=PASS claims=18`；三条各自播种皆红且报出句名（16/14/33 三枚，逐条
`FAIL … prose says ['16'], measurement says 17`，恢复即 PASS），并且本批改写了两处过期数字
（"余下 32 条 SCHEMA_LESS"改为带日期的读数并指向现值；"当前 11 条读数"改为只以闸门自己输出的
`claims=<n>` 为准）。现状面新增"后端 I"整块，旧读数不删。

**闸门与实跑**：`VERIFY_CONTRACT_BINDINGS=PASS routes=68 dispatched=68 bound=54 schema_less=14`
（36+18 / 32−18，两个方向都对得上）、`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=35 failures=0`、
`VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=109 routes=66 matched=55 backend_only=11 dynamic=3 special=1`
（本批没碰界面调用面）、`DOCUMENTED_COUNTS=PASS claims=18`；定向
`test_standalone_chain_http`+`test_installed_write_surface` 源码 12 OK / 装机 12 OK、
`test_route_payload_contracts` 31 OK、`test_contract_bindings`+`test_packaged_contract_resources` 42 OK。
前端 0 文件。本机整轮 union 与聚合读数见下一条回填。

**边界不变**：宿主 E3、真人 E4、release、安装态分发、ComfyUI / MiniMax H3、`currentExecution`
34 项 `FROZEN_DEFERRED` 继续冻结；手机端仍是排除项，不是待办；字体与三方素材不在本项目范围内；
模型不锁死但默认 fail-closed，显式选择只是被记录的动作；编号仍用字面量 `UNUSED`，代理不自造标识；
签署与审核仍只接受具名 human；导出仍只读回；E 盘不动。级别仍是 E2——这一批改的是"信封自己说的
是不是真的"，不是产物好不好。

### 5.32 CI 读数（批次 K 第一刀；本地并集与远端逐作业都绑 `cf77b2c2`）

**本地并集先在安静树上跑完。** `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe
scripts/run_python_tests_all.py --shards 3 --jobs 1`，工作树 `HEAD cf77b2c2`、除未跟踪的
`.codebuddy/` 与 `.cursor/` 外无改动：shard 1/3 `exit=0 tests=1102 wall=1578.375s`
（PASS 1101 / SKIP 1）、shard 2/3 `exit=0 tests=1006 wall=126.719s`（PASS 1004 / SKIP 2）、
shard 3/3 `exit=0 tests=1092 wall=386.918s`（PASS 1090 / SKIP 2）；
`PYTHON_TESTS_UNION=OK expected=3200 distinct=3200 ran=3200 duplicates=0 missing=0
unexpected=0`，合计 PASS 3195 / SKIP 5，`UNION_EXIT=0`。上一轮同一口径是 FAIL 5，这次是 0。
⑧ 里那条"暂记为环境性红、不写成已解释"的 `test_workbench_theme_geometry_gate` 在这轮并集里通过；
它依然没有得到解释，只多了一条重跑读数。

**推送是 fast-forward，两个引用同一 SHA。** `git push origin cf77b2c2:main` 与
`git push origin cf77b2c2:qoder/designlab-backup-consistency-20261007` 都报 `d5444cb3..cf77b2c2`；
`git ls-remote` 读到两个 ref 都是 `cf77b2c2`。没有 force，没有合并以外的历史改写。

**远端 CI：run `40009897564`，`Canonical Verify`，SHA `cf77b2c2`，conclusion `success`。**
12 个作业里 11 个 success，`Branch light gate` 按设计在 main 上 skipped。逐作业的关键步骤：
- `Python gate (V3 verifiers + unit tests)`：18 个实质步骤全部 success，含 unified verify、
  boundTree freshness、R5 账本闸、证据工件存在性、分片单元测试（与本地并集同一套件）。
- `Top-level Authority consistency gate`：4 步全绿，含 archive-wave record register。
- `DeepSeek authority gate chain`：2 步全绿。
- `Workbench strict-TS product gate`：typecheck、Vite build、node smoke、静态验证，以及
  `No-drift: rebuilt bundle is byte-identical to committed`。
- `Workbench browser E2E (exact-SHA controlled-runtime, no-skip)`：
  `Browser E2E must RUN and PASS` 成功，证据工件已上传。
- `Clean wheel install + Workbench launch gate`：建 wheel、干净环境安装、启动读回、
  20 跳验收链、全部 POST 行逐行走查，5 步全绿。
- `Generated-artifact clean-tree gate`：重建产物无漂移 + 全树干净。
- `License & secret hygiene gate`：8 步全绿（许可覆盖、SBOM、秘密史扫描、CRLF 检查）。
- `MiniGame node gate`、`Open Design host adapter gate`（表面未变，安装/闸门步骤按条件 skipped）、
  `CI artifact proof` 均 success。
- `Branch light gate`：main 上 skipped，不是失败。

**这一轮之后仍未证的事一条没变**：真人验收没有发生，最高级别仍是 E2；产物没有发布，
没有安装态分发，没有真实宿主 E3。**边界不变**：手机端仍是排除项；字体与三方素材不在范围内；
模型不锁死但默认 fail-closed，本轮不部署模型、不下载权重；编号仍是 `UNUSED`；导出仍只读回；
AAOS 仍只是未来合同；E 盘不动；旧 34 项继续冻结。

### 5.33 收尾提交与逐作业读数（`48a7e030` → `d9a8412b`）

回填这份 5.32 的提交是 `48a7e030`（审计、交接提示词、`large-assets.json`、证据索引四件）；
随后在 `48a7e030` 上重生成三份投影（`records=5 bytes 77253->77192`、
`AUTHORITY_CHAIN=WRITTEN entries=146`、`CURRENT_REPORTS=PASS mode=generate`），三个 `--check`
全绿后提交 `d9a8412b`（12 个投影文件，53 增 53 删）。两个提交一起 fast-forward 推送，
所以两个 ref 的 CI 读数都在 `d9a8412b`：

- **main**：run `40013185833`，`Canonical Verify`，`success`，`19:39:56Z → 19:55:25Z`。
  12 个作业 11 个 success；逐步骤扫描 `conclusion` 非 success/skipped 的步骤为 0 条；
  `Branch light gate` 在 main 上 skipped（设计如此）。
- **分支**：run `40013198844`，同一 SHA，`success`；`Branch light gate` success（8 步），
  其余 11 个作业按设计 skipped。两个运行的覆盖面互补，合起来没有未跑的作业。
- `GitHub Actions` 另有一条 runner 标签迁移提示（ubuntu-latest → Ubuntu 26，2026-10-19 起），
  不影响本次结论。

这次只改了一处代码：`scripts/generate_archive_record_register.py` 的「工作树里有 N 份被还原成 CRLF」
原来把**任何**工作树与 blob 的字节差都归因成 CRLF。回填本节时审计文件有未提交编辑，生成器就把那
1,267 B 写成「被还原成 CRLF」，并把这个错误归因写进了索引。修复是先把工作树按 `\r\n→\n` 归一化再
与 blob 比，只有归一化后相等才算行尾差异；反证是同一个带未提交编辑的工作树，修复前报 2 份
（`MANIFEST.json` 1,867 B + 审计 1,267 B），修复后报 1 份（只有真的 `MANIFEST.json`）。
CI 从 `cf77b2c2` 的 `success` 推进到 `d9a8412b` 的 `success`，中间没有出现红。

### 5.34 第二轮打磨与设计审查入库（`967d3eed` → `3c6ca491`）

**这一轮没有新功能，只把第一刀留下的可见缺陷与证据账收干净。** 三个缺陷在
`967d3eed` 上修好并逐屏复读：

1. 列表行把修订号印两遍（`r1` + `推荐 r1`）。现在推荐且最新只印一个
   `最新 r1 · 推荐版本`，非推荐行印 `r1` + `无推荐版本`；`apps/workbench/tests/appshell.mjs`
   同时断言合并文案存在、`推荐 r2` 不存在、`r2` 只出现一次。
2. 详情头同样重复。推荐条目详情现在只出现一次合并徽章。
3. 窄视口下当前导航项不在侧栏视口内。`sync(view)` 里加了 `scrollIntoView({block:'nearest'})`，
   E2E 新场景 `desktop-nav-active-visible` 要求 `scrollTop>0` 且按钮矩形落在导航视口内，
   不满足就退出码 13；实测 `scrollTop=751`、按钮 593.5–640.5 落在 124.5–641。

另有一处注释错误：`browser_design_layer_e2e.mjs` 说「ROUTE_VIEWS has 22 entries」，而该文件
数的是 `.app-nav-item`（22 项，含走空 hash 的工作台）；B10 侧栏是 21 个按钮。`DESIGN.md` 的
「导航 22 项（侧栏 21 个按钮）」本来就是对的，错的是注释，已在 `8e27a95c` 改回 21 并说明两种计数。

**证据与账本。** 19 条新回执全部绑 `967d3eed`，写入 `currentExecution` 后共 235 条；
任务状态从「3 PARTIAL + 1 IN_PROGRESS + 1 NOT_STARTED」变为：
`DL-KB-03/04/06 = DONE`（三条轴各有 PASS 回执），`DL-KB-01/02/05 = PARTIAL`，
`DL-KB-07…16 = NOT_STARTED`，旧 34 项仍 `FROZEN_DEFERRED`（直方图
`FROZEN_DEFERRED 34 / DONE 3 / PARTIAL 3 / NOT_STARTED 10`）。三条 PARTIAL 缺的都不是
"再跑一次绿"，而是尚未存在的断言或路由，逐条写在回执 `command` 里：

- `DL-KB-01`：本地九门只证明这一棵树；干净克隆与 EOL 复现要干净 checkout，等本轮推送后的
  CI 作业读数回填，回执写明这是它停在 PARTIAL 的原因。
- `DL-KB-02`：A5「模型服务关闭时仍可写入、检索、编辑与复制」没有直接断言。
- `DL-KB-05`：A2 已实测（追加、旧摘要不变、409 冲突带修订号、重启读回一致），
  D5「回退推荐版本后旧方案仍可读、失效来源可标记并替换」既没有回退路由也没有
  失效来源字段，依赖尚未开工的 `DL-KB-07`。

**门禁。** 更新账本前后各跑一次九门，全部 exit 0：`TOP_AUTHORITY_GATE` 10 项、
`TASK_DOC_STATE_GATE` 13 项、`DOCUMENTED_COUNTS`（claims=20、route_views=22、cli=24、
adapters=30、routes=72）、`RECORD_REGISTER_GATE` 5 项、账本合同、上下文完整性、
投影新鲜度（records=14 / verified=21 / findings=0）、证据工件存在性、账本主题绑定。
`EVIDENCE_ARTIFACTS` 行如实保留 `tracked_drifted=64`——那是历史可变源文件的预期漂移，
不是新回执；新回执 19/19 都在盘上且摘要吻合。

**并集首跑不是全绿，两处红灯都已定位并修复。** `run_python_tests_all.py --shards 6` 在
`967d3eed` 的树上：shard 1/2/3/5/6 `exit=0`，shard 4 `exit=1 tests=476 {'FAIL': 2, 'PASS': 473, 'SKIP': 1}`，
失败项是 `test_verifier_internals.AggregateChainTests.test_aggregate_verify_runs` 与
`OpenDesignAssistanceTests.test_boundary_pass`。第一条是根因，第二条是它的下游：
新入库的 `design-lab/scripts/knowledge_revision_probe.py` 缺 SPDX 头，
`verify_license_coverage.py` 报 `MISSING SPDX`，连带 Open Design host verifier 与
`verify_design_lab.py` 的聚合红。补上 SPDX 后第二条转绿，第一条仍红，暴露出第二个真问题：
`kb-05-implementation-revisions.log` 是 Windows cp936 stdout 写出的日志（第 513 字节
`0xb7` 起是中文标题），`verify_identity_gate.py` 以 `IDENTITY_GATE=FAIL total=1 scanned=3241`
判它不可读。修法是按 cp936 解码再以 UTF-8 写回，先证明文本逐字符不变（`b.decode('cp936')`
与重编码后的 `decode('utf-8')` 相等）再落盘，并在同一个提交里把账本那条回执的
`artifact_sha256` 重钉为 `b58d862ef24ddfc579fbe45bb208ebe28f6a3dc1ccfad6d454a81f79b2e0c659`
（1,348 → 1,366 B，内容不变、编码改变）。修复后 `IDENTITY_GATE=OK total=0 scanned=3241`、
`LICENSE_COVERAGE=OK`，两条失败测试按定向重跑各自通过
（`test_aggregate_verify_runs` 118.34s、`test_boundary_pass` 1.16s）。
这次的内容没有变，但**证据文件的编码也是证据的一部分**：一份二进制上不可读的日志
会让整个聚合链红，而它看起来只是"一份日志"。

**并集复跑全绿（同一棵树，`60e40773`）。** `run_python_tests_all.py --shards 6` 六片全部
`exit=0`：1/6 `tests=626 {'PASS':626}` 1310.396s、2/6 `626 {'PASS':625,'SKIP':1}` 75.221s、
3/6 `562 {'PASS':561,'SKIP':1}` 265.913s、4/6 `476 {'PASS':475,'SKIP':1}` 182.048s
（r2 红的那两条就在这一片）、5/6 `380 {'PASS':379,'SKIP':1}` 48.001s、
6/6 `530 {'PASS':529,'SKIP':1}` 126.230s；`PYTHON_TESTS_UNION=OK expected=3200 distinct=3200
ran=3200 duplicates=0 missing=0 unexpected=0`，`UNION_RUNNER_EXIT=0`，合计 PASS 3195 / SKIP 5。
r2（红）与 r3（绿）两份日志都入库，不删不改：红的那份记录的是修复前的事实。
本机读数永远不是 CI 读数，最终判据仍是推送后逐作业读到的结果。

**CI 读数：干净检出复现成功（`3c6ca491`）。** 推送后 `main` 的 run `40036696250` 在 `3c6ca491`
上 `success`：12 个作业位里 11 个 `success`、`Branch light gate` 按规则 `skipped`；同一 SHA 的分支
run `40036704582` 也 `success`（只跑 Branch light，其余跳过）。逐行读数（本次从作业日志读出，
原样存入 `kb-01-delivery-ci-clean-checkout-20261024.log`）：`TOP_AUTHORITY_GATE=PASS checks=10
failed=none`、`RECORD_REGISTER_GATE=PASS checks=5 pathish_named=21 problems=0`、
`VERIFY_RESULT=OK total=549 failed=0`、`VERIFY_DESIGN_LAB=OK total=76 failed=0`；三片
`shard=1/3 exit=0 tests=1102 {'PASS':1089,'SKIP':13}`、`2/3 exit=0 tests=1006
{'PASS':1002,'SKIP':4}`、`3/3 exit=0 tests=1092 {'PASS':1087,'SKIP':5}`，
`PYTHON_TESTS_UNION=OK expected=3200 distinct=3200 ran=3200 duplicates=0 missing=0 unexpected=0`。
这是全新 Linux checkout：登记册的五个 blob 摘要被原样复算通过，EOL 没有被规范化改写，
`DL-KB-01` 的第二条验收（干净克隆复现）由此落地。

**上一枚是红的，红在登记册。** `f75c6909` 的 run `40036507654` 只有 `Top-level Authority` 作业失败，
其余 11 个成功：§5.34 这份 append 改写了登记册第 5 件（交付报告本身）的已提交字节，而
`docs/RECORD-ARCHIVE-INDEX.md` 还钉着旧 blob（`8d95f14263ab` / 193,302 B），所以
`RECORD_REGISTER_GATE` 拒绝。修法不是改闸门，是 `3c6ca491` 重新生成登记册（第 5 行改钉
`e0028440f230` / 200,089 B），并顺手修了生成器里那句错话——旧模板把"最后改写提交"写成了"首次读自"。
哈希绑定的记录改写天然要两次提交，这正是登记册设计里写明的那条，不是流程事故。

**`DL-KB-01` 收口。** 三条验收逐条落地：四条闸门在 `3c6ca491` 上同绿（两条由 CI 作业读出，
`TASK_DOC_STATE_GATE` 在那次 CI 的统一校验里 PASS；`DOCUMENTED_COUNTS` 不在 CI 里，本机在收口树
实测 `claims=20 route_views=22 cli=24 adapters=30 routes=72`，它计量的每个量——路由数、子命令数、
adapter 数、两跳链、冻结/派工两个分母——都不受本轮改动影响）；干净克隆复现由上面这次 CI 读数证明；
旧 34 项仍全部 `FROZEN_DEFERRED`，本轮没有解冻任何一项，规划没有被写成实施证据。回执
`kb-01-delivery-ci-clean-checkout-20261024`（axis `delivery`）绑的就是这份日志；账本状态
`PARTIAL → DONE` 后直方图为 `FROZEN_DEFERRED 34 / DONE 4 / PARTIAL 2 / NOT_STARTED 10`，
证据 236 条。

**设计审查插件第一次跑全。** `design-review` 插件对 `design.qa.yaml` 的 26 个屏幕
（22 条桌面路由 + 4 个 390×844 窄窗探针）跑出：

- a11y：26 次扫描、0 findings、`ok=true`。这是自动扫描，不是 WCAG 认证，也不是真人验收。
- design debt：713 findings、`ok=false`、10 个文件、27 个 token 值。分布
  px-magic 630 / hard-coded-color 38 / functional-color 14 / custom-shadow 28 /
  tailwind-arbitrary 3；severity minor 630 / major 52 / debt 31。按文件：
  `style.css` 683、`shell.ts` 28、`workbench.ts` 2。

这条按**未关闭的登记**入账，不按通过。`style.css` 同时是 token 声明处与组件规则所在地，
原始值里有一部分就是 token 定义；`shell.ts` 的 28 条里 17 条是注释命中，非注释的 11 条中
`5985` 是 token 预览样例 JSON、`9273` 是资源 ID 正则、`workbench.ts:377` 是路由正则，均为误报；
真实内联样式是 `5475/5477` 与 `6856/6860/6870` 五处，`6418/6692` 是 760/840px 断点常量。
清理属于版式轮次，本轮不把阈值调低，也不写"设计债已清零"。

**`evidence-index.json` 只覆盖第一刀。** 它仍然绑 `7f5e68d7` 的 47 份首刀件；
第一刀之后的 20 份新件（第二轮 19 份 + 第三轮 1 份 delivery 回执）由账本 `artifact_sha256`
逐条绑定，不并入那个索引。读证据时以账本为准，
不要把索引当成"证据包全量清单"。

### 5.35 第四刀 K3：方案对象与设计辅助（`2d9372fb` 实现 → `103a6680` 收口）

**落地形状。** 实现提交 `2d9372fb` 新增六条路由：`GET /api/assistance-plan-output-types`、
`GET /api/projects/(id)/assistance-plans`、`GET /api/projects/(id)/assistance-plans/(aplan-…)`、
`POST /api/projects/(id)/assistance-plans`、`POST …/assistance-plans/(aplan-…)/revisions`、
`POST …/assistance-plans/(aplan-…)/choose`。实测 ROUTES 72 → **78**（42 GET + 36 POST）；合同账本
74 → **80 行**（BOUND_SCHEMA 66 / SCHEMA_LESS 14；方法分布 44 GET + 35 POST + 1 GET+POST）；live
载荷绑定 41 → **47**（`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=47 failures=0`）；`ROUTE_VIEWS`
22 → **23**，`DESIGN.md` 导航 22 → 23。新增五份 plan schema（plan / write / readback / list /
output-types）与一张 94 行的 state 表。

**`DL-KB-07`（中立方案对象 + 一份创意意图）收口。** `test_assistance_plan` 18 项：
"已保存／方案已提供／用户选用／外部未验证"是四条独立读回路径，复制不写任何一条；修订追加、
不改旧链；带过期 `expected_revision` 的写被拒并点名实际版本；只有具名真人能做选用；未接回执的
选用保持 `LINKED_ONLY`，直到存储里出现反转；缺号一律 `UNUSED` 字面量。路由注册、合同行与 wheel
打包由 77 项（`test_route_payload_contracts`、`test_ledger_schema`、
`test_packaged_contract_resources`）复核。

**`DL-KB-08`（设计辅助初始态 + 方案详情屏）收口。** 浏览器实跑 `result PASS`、`consoleErrors 0`：
保存后 `saved=true` 而 `providedAfterSave`／`chosenAfterSave`／`externalVerified` 全为 `false`；
复制成功且 `copyCarriedHonesty`、`copyWroteNothing`、`copyChoseNothing` 均为 `true`——复制既不改状态、
也不代替选用；空目标被拒（`emptyObjectiveRefused`）；手工补创意可行（`suppliedCreative`）；
`providerPrimary` 是 `as-choose`，选用后 `chosen=true` 且 `chosenActorShown=true`；`revisionRows=2`；
重载读回一致（`reloadReadback`）；无聊天面（`noChatSurface`）。工作台 node 30 项（含
`㉔ B10_NAV` 从 `ROUTE_VIEWS` 派生）与 Python 44 项同绿。

**视觉与闸门。** 截图 manifest 绑 `2d9372fb`：81 张（assistant 在 1280/1440/1920），
视觉复核另存四张（`detail@1440-saved` 378,639 B、`detail@1440-chosen` 455,730 B、
`detail@1280-chosen` 437,580 B、`list@1280` 214,538 B），逐张 sha256 在收据里。UI audit
`ok=true`、`violations=[]`；溢出量 1100/900/750/620 四档；对比度 3 项双 palette；设计审查插件
第一次覆盖 `#/assistant`：27 屏 axe 扫描 0 findings（自动扫描，不是 WCAG 认证），设计债
713 条（630 minor / 52 major / 31 debt）与助手屏出现前条数、严重度与文件分布相同，
`(file, rule, severity)` 的 713 条多重集完全一致；差异是 28 条行号随 `shell.ts` 增长而位移，
不是新增债务。新界面没有新增字面 px 或硬编码颜色。收口树九门 `VERIFY_DESIGN_LAB=OK total=76 failed=0`，并带
`VERIFY_RESULT 549` / `VERIFY_PRODUCT_MANIFEST_V3 493` / `VERIFY_RUNTIME_CONTRACTS_V3 239` /
`VERIFY_VISUAL_SCORING_V3 10`；投影新鲜度 0 findings；authority gates 7 项 PASS。账本追加 13 条
回执（KB-07 两条、KB-08 十一条）后共 **249** 条全部 PASS，直方图
`FROZEN_DEFERRED 34 / DONE 6 / PARTIAL 2 / NOT_STARTED 8`。本目录现有 86 个受跟踪文件：
索引仍只覆盖第一刀 47 份，其余 39 份（本轮新增 15 份）由账本 `artifact_sha256` 逐条绑定。

**CI 第一次读数与修复。** PR #277 的首个完整矩阵（run `40048178001`，SHA `142e7efe`）是 9 个作业
success、Python gate 红，`Branch light` 与 `CI artifact proof` 按规则跳过。shard 3/3 共 1026 项里
唯一失败是 `test_backup_watches_written_tables.CoverageTests.test_every_written_table_is_watched_by_the_proof`：
KB-07 新增的 `assistance_plan`、`assistance_plan_revision`、`assistance_plan_choice` 三张表由 store
直接提交、不持写锁，却没有进 `project_backup.py` 的 `COUNTER_QUERIES`——备份窗口吞掉一次修订或一次
选用，仍会报 `PROVED_QUIESCENT`。这条规则住在单元测试里，`verify_design_lab.py` 的 76 项不含单元测试，
所以本机九门全绿也没拦住它。修复是在 `COUNTER_QUERIES` 追加三行 `rowid` 计数并写明理由；复验是
`test_backup_watches_written_tables` 5 项、`test_project_backup` 加 `test_evidence_artifact_presence`
48 项（1 skip），本机三 shard 并集 `3213 PASS / 5 SKIP / 0 FAIL`（shard 1108/1084/1026 项，
用时 408.5 / 1487.1 / 140.4 秒）。同一条并集在 CI 上的分布是 `3195 PASS / 22 SKIP / 1 FAIL`——两边总数
同为 3218，SKIP 差 17 项来自 runner 与本机的宿主环境差异，不是同一批用例被换掉。修复提交 `dbdee924`
的复跑 run `40076707359`：见本节末尾的逐作业读数。

**未证与未修。** `1440×900` 与 `1280×800` 下详情屏的主操作落在首屏折叠线以下
（`1920×1080` 可见）；它不违反任何验收句，但属体验缺陷，留给版式轮次，本轮不为此重排布局——
重排会让整条刚量好的证据链失效。收据里的选用人写作「示例审阅人」，是**示例**不是真人验收；
E2E 自己的 `subjectSha` 写的是 `local`，工件身份靠 bundle sha 与截图 manifest 的 commit 绑定，
账本回执里照实写明。a11y 的 0 是自动扫描。`DL-KB-02` 的 A5 仍无直接断言；`DL-KB-05` 的 D5
在 KB-07 收口后需要重新量，不能因依赖项 DONE 就写成已证。下一刀是 K4：
`DL-KB-09`（目标档案：软件×模型×入口）与 `DL-KB-10`（目标组合选择面板屏）。

**复跑逐作业读数（run `40076707359`，`dbdee924`）。** 10 个作业 success，`Branch light` 与
`CI artifact proof` 按规则跳过——前者只在非 main 的 push 上跑，后者只在 main 的 push 上跑，所以 PR 上
本来就不该出现它们。三个 shard 分别是 1108 项 `1103 PASS / 5 SKIP`、1084 项 `1071 PASS / 13 SKIP`、
1026 项 `1022 PASS / 4 SKIP`，合计 `3196 PASS / 22 SKIP / 0 FAIL`；与本机并集同为 3218 项，FAIL 归零，
`test_every_written_table_is_watched_by_the_proof` 这次在两张表都计数的代码上绿。

### 5.36 第五刀 K4／K5／K6：材料、目标、反馈与复用闭成一条链（实现 `36addfd5`）

**这一刀把七段链接上了。** 真实需求与参考 → 可编辑方案（DL-KB-07/08 已有）→ 按需生成或编辑材料 →
按材料选择目标 → 实际复制或导出 → 用户自愿记录外部使用反馈 → 方案与适用经验再次查找复用。本轮新增的
是后四段：`src/design_lab/plan_export.py` 用**一个** `_intent()` 构建器渲染 markdown／txt／json／分镜
CSV 四种形态，CSV 的转义是在吐出的字节上证的（引号、逗号、换行各一条），没有镜头行的方案**拒绝**出
CSV 而不是吐一张空表；`src/design_lab/target_profile.py` 把软件×模型×入口做成五条路由加一份
`design-lab/config/target-profiles.json`，未知入口保留 UNKNOWN、校验永不发放执行权；
`src/design_lab/plan_feedback.py` 记自愿的外部结果反馈，写完方案的四个状态一个字都不动、修订历史
仍在、结论词由服务给出；「我的方案」这一面补了页内检索与筛选（说明句写清"筛选只在这 M 条里做，
不是全库搜索"）、两份**真实修订**的逐字段对照、由服务铸号的复制一份，以及一份活过重载的未完成编辑
（本机存储、24 小时过期、超长不写、结构不对就当没有、保存成功即清除）。路由面从 86 涨到 **87**
（48 GET + 39 POST），写侧扫描表 `rows=39 walked=38 written=38 read_backs=47 refused=0 excluded=1`。

**两道闸门被这一刀量出两个真缺陷，都是先红给我看才改的。** 对比度闸报过一条 `1.31:1` 的
`p.view-hint`，查下去是**假失败**：闭合的 `<details>` 在 Chromium 里仍保留真实布局盒
（`::details-content` 是 `content-visibility: hidden`），`display`/`visibility`/`opacity`/矩形四道
过滤都放行，于是"没人看得见的那行字"被按它像素位置上那块兄弟面板的颜色判了分。修法是量之前先把
所有 `<details>` 展开，并把带进来的行数报成 `collapsedOpened`，同时埋一条**闭合的**白底白字对照件
——只有真的展开了它才会被报出，所以这条修正不可能悄悄变成少量。同一轮还暴露 `oklab(...)`
（`color-mix(in oklab, …)` 的序列化形式）这道闸读不懂，按它自己的家规"扩解析器而不是降阈值"补上，
并且用 CSS Color 4 规范里那四组 sRGB↔OKLab 对照值判分，不是用文件里另一个函数自证。改完两档主题各
量 50 个面、`checked=14002`、`belowAA=0`、`collapsedOpened=6228`、`unparsable=0`、`colourBad=0`，
最紧的一对是 4.11:1（深色）与 4.14:1（浅色）。截图闸的等待条件也错过一次：它要求每条
`[role="status"]` 都有文字，而材料回执那句在人不点"复制"时**本就该是空的**，于是方案详情三档宽度
全部 `settle-timeout`；改成只等"没有还在读回"，内容由脚手架自己的读回断言保证。

**一处真实超标，所以 `DL-KB-13` 是 PARTIAL。** 交付方案 §14 写的是"首屏 JavaScript gzip 不超过
150KB"，本轮实测 `apps/workbench/build/main.js` 原始 593,796 字节、gzip **155,787** 字节，超过上限；
样式表 110,904／gzip 40,530，远程引用 0。不能靠改构建解决：`vite.config.ts` 顶上的合同写明这个包
**故意不压缩**，因为原生 UI 契约测试要读顶层函数名与界面文字，压缩会让契约静默失效；也不该为凑数字
删必要内容或换栈（同一节的原话）。搜索与操作延迟达标且余量很大：1,000 条按真实结构生成的样本、
30 次查询，`search p95=28.89ms`、`create p95=8.14ms`、`detail p95=8.94ms`（阈值分别是 300ms 与
100ms），推理延迟单独报、不混进界面指标。几何面这轮补了 1536 CSS px——1920 物理屏在 Windows 125%
下的宽度，100/125/150 三档里此前**没人量过中间那一档**，现在溢出闸扫 `1440,1280,1536,1920`。
§14 还要求"安排至少 3 位目标用户做无指导任务"，那不是我能替的验收，所以这一行停在 PARTIAL。

**账本读数（`36addfd5` 上现测，21 条新回执，`kb-20261024` 目录）。** `DL-KB-09`、`DL-KB-10`、
`DL-KB-11`、`DL-KB-12`、`DL-KB-14` 记 DONE（各自 `evidence_requirements` 的轴都有 PASS 回执）；
`DL-KB-13` PARTIAL（体积超标 + 真人无指导任务未做）；`DL-KB-16` PARTIAL（实现与单元都 PASS，
`human_review` 只认具名真人，代理不签）；`DL-KB-15` 仍 NOT_STARTED，它的前置是"用户在本机实际可用的
推理服务与硬件余量"，本轮不部署模型、不自行下载权重。全量门禁 `VERIFY_DESIGN_LAB=OK total=76
failed=0`，UI 审计闸与截图采集（带合成方案种子）都是 0 退出，受影响的十个 Python 模块单独跑全绿。

**这一轮自己追正的一处：上面那段"留给下一轮的覆盖洞"已经在本轮补掉了。** 写下它之后紧接着就动手了：
几何闸与 UI 审计闸现在都在量之前先展开闭合的 `<details>`，并各自报出展开了多少个面板——几何闸在 112
个路由量测里展开 **1200** 个（单路由最多 98 个，在 research／capability／capabilities 那三面），UI 审计闸
在 54 个 scope 里展开 **324** 个。两道闸的包装各加一条断言：这个计数为 0 就红，所以"展开这一步被删掉"
不可能悄悄变成一次绿色。改完两道闸都全绿——**没有新增任何一条几何或可读性违规**，也就是说这些折叠面板
打开后的版式本来就是好的，此前那句"数说的是布局盒不是像素"是断言范围的问题，不是被掩盖的缺陷。剩下的
真问题反过来：闭合态自己的裁剪行为现在不再被这两道闸声称，谁要声称得另立一把尺。另两处未闭环的账不变：
`DL-KB-02` 的 A5 仍无直接断言，`DL-KB-05` 的 D5 需要重新量（回退要事件表，本轮没有加）。

边界不变：桌面端 only，手机端仍是排除项；不部署模型、不宣称推理已验证；导出与复制是**读回**不是
发送，页面上那句"这只是把材料交出去，不是选用，也不是发送"是服务给的词；编号仍由人填或显式选
UNUSED；三方素材与字库在范围外；E 盘不动；旧 34 项仍 `FROZEN_DEFERRED`；release、装机分发、真实宿主
E3、真人 E4、ComfyUI、MiniMax H3 与外部软件自动操作继续冻结。

**CI 把本机量不到的四件事顶了出来（逐提交读数）。** 收口提交 `d33b8e1c`/`64ad6f9b` 的首轮矩阵红了三个
作业，逐个查因，没有一条靠改断言糊过去：
① `test_gate_reachability` 报 `measure_workbench_weight.py` 声明了 `--check` 却没有任何表、链条或测试
调用它——这正是"闸门可达性"家规该抓的东西，已把它作为一步接进 Workbench 作业（`7a6ab695`）：它现在
守的是"不许有远程引用"这半条已经成立的规则，体积那半条只发布读数不判分；
② 21 条新回执绑进账本之后 `AUTHORITY_CHAIN=DRIFT`，因为那份记录钉的就是账本自己的字节，重生成
`reports/current/DEEPSEEK-AUTHORITY-CHAIN.json` 才是对的（同一提交内付清）；
③ 登记册第 5 行钉的审计件字节因 §5.36 而变，按 `git cat-file` 重钉，不手抄；
④ 几何闸在 CI 上判 `1440:capabilities`"这一屏一个标题都没有"，本地怎么都复现不出来——真相是它按固定
1 秒 sleep 量路由，把"还在读回"当成了"没有标题"。现在先等 `#route-view` 的占位消失再量，等不到就进
`OV_INTERACTION_UNMEASURED` 红（`9cba9f11`）。同一类问题在方案对照用例里又抓到一次：等待条件只看
"选用"徽章，而被比较的修订数与反馈数来自两次独立读回，CI 读到 `feedback: 0` 就误判"复制动了源"——
修订数没变恰恰说明产品是对的，错的是等待（`7925efca`）。
**最终 `7925efca` 的 PR 矩阵 `completed success`**：11 个作业里 Branch light 与 CI artifact proof 按规则
跳过（前者只在非 main 的 push 上跑，后者只在 main 上跑），其余全绿。这一串的价值不在"最后绿了"，
在于这四条只有换一台机器才会暴露——本机此前全绿了整整一天。

### 5.37 第六刀 K2 补口：DL-KB-05 D5 的判断存储（实现 `52961f49`，收口同轮）

**这一刀补的是什么。** `currentExecution` 里 DL-KB-05 的验收第三条写着
「回退知识推荐版本后旧方案仍可读；失效来源可标记并替换」。上一轮实测的结论是这句话**说不出来**：
`knowledge_entry_revision.recommended` 是随版本一起写入的、被 append-only 触发器锁死的字段，
所以推荐要么永远等于写入那一刻，要么就得改那个字段——改它就等于拆掉这个条目全部历史的保证。
没有路由、没有字段、没有界面，状态只能停在 PARTIAL。

**现在的形状。** 判断是它自己的一行，追加进 `knowledge_judgement`
（`design-lab/schemas/state/design-lab-state-knowledge-judgement-v1.sql`）：同一条目同一 `kind`
的最新一行是答案，下面的行是"答案是怎么走到这里的"。`POST /api/knowledge-entries/{id}/judgements`
回答的是条目自己的 readback（`recommendation_basis`／`recommendation_judgement`／`source_state`／
`judgements` 四个字段是这一轮加进 `knowledge-entry-readback-v1` 的），所以调用者看到的是被挪动后的
那个数，而不是一张回执。写入面拒绝的四件事各有其代码：`recorded_by_kind != 'HUMAN'` →
`KNOWLEDGE_HUMAN_JUDGEMENT_REQUIRED`（owner 2026-10-21：本机验收只接受具名真人）；没有 `reason` →
`REASON_REQUIRED`；推荐了一个没存过的修订 → `KNOWLEDGE_REVISION_NOT_FOUND`；标记失效却没给出
**库里真的存在的**替代条目 → `KNOWLEDGE_SOURCE_REPLACEMENT_REQUIRED`／`_SELF`／`_UNKNOWN`，
而 `replaced_by` 同时是外键，绕过写入面直接 INSERT 也一样进不来。`recorded_at` 由服务盖，不接受调用方自填。

**为什么这句话现在成立了。** 13 条单元测试里最关键的一条是
`test_moving_the_recommendation_rewrites_no_stored_bytes`：推荐从 r2 挪回 r1 之后，逐条比对
`detail()['revisions']` 的 `content_sha256` 与 `created_at`，**一个字节都没动**。这正是
"旧方案仍可读"的机制面——方案钉住的是修订号与摘要，摘要不变，读到的就是当初那份。重启后同一份判断
还在（`test_a_judgement_survives_a_restart_and_still_outranks_the_written_flag`），所以没有第二张
真值表，也没有引入第二张修订表：`latest_revision` 与写入标记仍只从 `knowledge_entry_revision` 算。

**同一刀里必须说的另一半。** 界面跟着落了：条目详情里"判断与来源状态"这一块带轨迹与两个表单
（`apps/workbench/shell.ts` 的 `kbJudgementPanel`），缺理由与缺记录人都在本地拒绝、不发请求，
`recorded_at` 不在请求体里。`apps/workbench/tests/appshell.mjs` 用**出货的那份 bundle** 走完了两个
表单、两次本地拒绝与写后重搜＋重读回。

**这条验收还差什么，所以行不升 DONE。** `src/design_lab/assistance_plan.py` 的
`REFERENCE_KINDS = ('ASSET','BRIEF','DIRECTION','PROMPT_RESULT')` 里**没有 KNOWLEDGE**：
方案今天无法钉住一个知识条目，所以"旧方案仍可读"只能在条目层面被证明（字节与摘要不变），
产品里并不存在一条"从方案读某条知识某个修订"的路径。补这一格要动方案 schema 的 `kind` 枚举、
`_resolve_references()` 那个以 `else: # PROMPT_RESULT` 收尾的分支、导出材料如何呈现引用，
以及读回里 `verification` 的取值——是一次独立的改动，登记成缺口而不是顺手糊过去。

**本轮门禁读数（都取自己那行输出）。** `VERIFY_CONTRACT_BINDINGS=PASS schemas=32 routes=90
dispatched=90 bound=76`；`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=57 failures=0`，其中
`knowledge-entry-judgement cases=2 object locations compared=22` 是两条真判断经真 socket 比过合同；
`VERIFY_WORKBENCH_ROUTE_CALLS=PASS calls=138 routes=88 matched=77 backend_only=11`（新增这一条路由
是被界面真的调用到的，不是又一条 BACKEND_ONLY）；`DOCUMENTED_COUNTS=PASS claims=20 route_views=24
routes=88`；写侧扫描 `POST_SWEEP layout=source rows=40 walked=39 written=39 read_backs=48 refused=0
excluded=1`，`knowledge-judgement` 在 written 名单里；浏览器侧对比度 50 个面 `checked=14002
belowAA=0 unparsable=0`、几何 112 个面（1440/1280/1536/1920）`docOverflowX=0 clipped=0 stray=0
detailsExpanded=1200`，两者都绑在 bundle `sha256 4df788c3…`（602,549 B）上。

**顺带修掉的两个自己的缺陷。** 一是 `contract-bindings.json` 里六条 emitter 行号被这次插入挪走，
`EMITTER_POINTER_NOT_THE_VERSION` 逐条点名——行号会烂，闸门会喊，别抄数字；二是新界面上线后
`el('ul', { class: 'list'` 的存量从 72 变 73，这一条按老规矩写明新增的是哪一个容器再动数字。
重量：bundle gzip 从上一轮记录的 155,787 B 到本轮 `WORKBENCH_WEIGHT_GATE=OK remote=0
bundle_gzip=157739`（同一把尺、同一份文件），KB-13 的 150 KB 预算仍然是 owner 的决定，本轮不代做。
### 5.38 第一次真点开一条知识条目：两个一直存在的表单缺陷（`38bb48d8`）

**为什么要做这一刀。** §5.37 记下了一条边界：没有任何浏览器门禁点开过一条知识条目。这条边界不是
"细节没顾上"，它意味着**整个条目详情面从来没被真实浏览器画过**，而详情面背后的新增／修订表单同样
没有——`apps/workbench/tests/appshell.mjs` 那个 DOM 桩件走得很细，但它的 fixture 把该填的格子都
填了、把许可状态也选了，所以它绿着，而真用户不一定走得通。

**真点一次，立刻红两次。** 新加的这一步（`design-lab/tests/e2e/browser_design_layer_e2e.mjs` 的
`knowledge detail and judgement walk`）在真 Chromium 里点「新增条目」，故意**不填**「适用场景」和
「边界与反例」，然后提交：

1. 服务答 `400 INVALID_PROJECT_FIELDS`。`collect()` 里写的是
   `applicability: value.trim() || undefined`，空串被 `JSON.stringify` 直接丢键；而
   `POST /api/knowledge-entries` 与 `…/revisions` 要的是**精确键集合**（`http_service.py` 的
   `body(fields=…)`：少一个键就拒，多一个键也拒）。界面把两个看起来可选的格子当成可省略的字段，
   服务却要求它们必须在。用户看到的是一句读不懂的代码，而且**只要不填这两格就永远写不进去**。
   修法是键永远在，值留空串——存储本来就把空串写成字面量 `UNKNOWN`（`knowledge_library._text`）。
2. 补完第一条再点，服务答 `400 KNOWLEDGE_LICENSE_UNKNOWN_CONTRADICTION`。许可状态那个 `select`
   没有"未选"这一档，选项来自服务词表、**第一项默认中选**，而本机词表第一项是 `reviewed`：
   一张谁都没碰过的新表单，打开就在替用户声明"这份许可被审过了"，同时许可格子还是空的。存储的
   规则（`license == UNKNOWN` 时状态必须是 `unknown`）是对的，错的是界面把词表顺序当成了默认值。
   现在空表单默认落在 `unknown`，也就是"没人看过"这句实话。

**这条闸现在长什么样。** 走查断言八件事，全部要真值：条目写进去并按编号读回、两格留空仍存成
`UNKNOWN`、空轨迹说的是"还没有人记下"、缺理由与缺记录人各自被本地拒绝且**一个请求都没发**
（按阶段计数的 `posts.afterReasonClick/afterNameClick/afterJudgeClick/afterSourceClick`，
读数 `[0,0,1,1]`）、判断只发一次、屏上的轨迹行数与 POST 返回的 readback 逐字段对得上、
来源失效没替代条目时不发请求。两条表单缺陷另外在 `appshell.mjs` 里各有一条**不需要浏览器**的断言
（新表单默认必须是 `unknown`；修订清空两格后键仍在），两条都在修之前的字节上红过。

**顺带说清一件事。** DOM 桩件不是浏览器的替身：这次是桩件全绿、真浏览器连红两次。反过也一样成立——
所以两边各留了什么断言，写在这段里，别拿一边的绿去声称另一边。
### 5.39 方案终于能引用知识条目：D5 的方案侧补齐（`2c47e359`）

**为什么上一轮只能停在 PARTIAL。** §5.37 把判断存储建起来了，但验收那句话的主语是**旧方案**，而
`src/design_lab/assistance_plan.py` 的 `REFERENCE_KINDS` 只有
`('ASSET','BRIEF','DIRECTION','PROMPT_RESULT')`——方案根本引用不了知识条目，
所以"回退推荐版本后旧方案仍可读"在产品里没有一条走得通的路。上一轮把它登记成缺口，这一轮补。

**加了什么。** `KNOWLEDGE` 成为可引用类型：id 形状用条目自己的 `^kentry-[0-9a-f]{32}$`，
钉的是**该条目当前最大修订**与那一行的 `content_sha256`（不是推荐版本——推荐是另一个答案），
并且因为知识库是全局的、`knowledge_entry` 没有 `project_id` 列，跨项目检查这一支改为**每个分支各自
写明 owner**：知识分支显式写 `owner = None` 并说明为什么，而不是"列不存在就跳过检查"——
后者会让下一个新增类型悄悄关掉一道安全闸。四个 schema 里的 kind 枚举与 Python 那个元组现在由
`test_the_reference_kind_list_is_one_list_across_the_schemas` 钉在一起；在此之前，
只往一边加词不是任何人的失败。

**顺手拆掉的一个真缺陷。** 表单原来把引用存成**光 id**，提交时一律贴回 `kind: 'ASSET'`。
于是一份引用了 brief 或知识条目的方案，一旦在界面上点"修订"，就会把自己原来的引用改标成 ASSET
交给服务，得到 `ASSISTANCE_PLAN_REFERENCE_ID_MALFORMED`——**这类方案在界面上根本改不动**。
现在选择器带类型（一个控件、两组 `<optgroup>`：本工作区素材 / 知识与提示词库），
列表每行显示它是哪一类，选择器给不出的类型在修订时**原样保留**而不是被改名。

**量到什么。** `design-lab/tests/test_assistance_plan.py` 34 条全过，其中
`test_moving_the_recommendation_back_leaves_the_cited_plan_reading_the_same_bytes`
是真 HTTP 路由上的整条链：建条目 r1 → 修订出 r2 → 方案引用（钉住 r2 与它的摘要）→
记一条真人判断把推荐退回 r1 → 再读方案，`references[0]` 与判断之前**逐字段相同**，
`reference_status[0].state` 仍是 `CURRENT`。另有一条写 r3 的用例量的是相反方向：
链接变 `CHANGED`、摘要与钉住的修订号不动。浏览器那侧走查从 8 件加到 **10 件全真**，
新增的两件是 `pickerOffersBothSources` 与 `planCitesTheKnowledgeEntry`。
途中被服务正确拒过一次 `ASSISTANCE_PLAN_SHOTS_NOT_APPLICABLE`（表单里留着上一段的分镜行，
而我选了平面类型）——那是走查自己的错，拒得对，改成 `STORYBOARD` 后通过，没有动服务的规则。

**于是这一行升到 DONE。** `currentExecution` 直方图从 `DONE 11／PARTIAL 4` 到
**`DONE 12／PARTIAL 3`／`NOT_STARTED 1`**，`evidence` 277 条。升的依据是定义里三条验收
（A2、D5、重启一致且不引入第二张修订表）都各有实测回执，`evidence_requirements` 要的两个轴
（implementation／unit）都 PASS，另加 browser 轴两条。没做的仍然写着：
`DL-KB-13` 的体积裁定与 3 位真人无指导任务、`DL-KB-16` 的具名真人签字、`DL-KB-15` 的本机推理前置，
以及 `DL-KB-02` 的 A5 直接断言——那几条不是工程缺口，是要 owner 或真人点头的账。

### 5.40 A5 直接量一遍，顺手补上那条一直缺失的复制（`72710b7f`）

**上一轮欠的是什么。** `DL-KB-02` 的 A5 那句话有四个动词——写入、检索、编辑、复制。前三个在
`test_knowledge_library.py`／`test_knowledge_http.py` 里各有真路由回执；第四个没有，因为
**条目详情里根本没有复制这个控件**：正文读得回、显示得出，用户要带走只能自己选中再抄。
上一轮把这格留着不写，是对的——留着是欠账，写成"离线可复制"就是假账。这一轮先补控件，再补断言。

**"模型关闭"怎么量才算数。** 只写一句"这条测试没配模型"不够：模块可能在 import 时就把
provider 拉起来了，而测试恰好没走到那支。所以 `test_knowledge_library.py` 里加的是一个
**读 AST 的扫描**：`MODEL_FACING` 是一串模型／供应商／网络方向的模块名，
`_reached_names()` 把 `knowledge_library` 模块（含它自己的 import 图）里出现的名字取出来，
`_model_facing_hits()` 按**点号分段**比对——`openai.chat` 这种写法要能被抓住，只比首段就漏了。
紧接着 `test_the_offline_scanner_notices_a_model_import` 往源码里种一条假的 `import`，
要求扫描器必须报出来，同时留一个负对照：种回原字节后必须报 0。
**一把量不出错的尺不能当证据**，这条规则也适用于它自己。
最后一条 `test_writing_searching_editing_and_copying_answer_with_no_model_configured`
先断言 `model_selection` 表**行数为 0**（"没配"而不是"配了没用"），再依次建条目、检索、修订、
读回，并钉 `revised['body'] == detail['current']['body']`。

**界面上加的那一格。** `kb-copy-body` 按钮 + `kb-copy-status` 说明；有
`navigator.clipboard` 就直接写，被拒（非安全上下文／用户没给权限）时退化成**一段只读且已全选**
的 `as-copy-fallback` 文本框，配一句"浏览器拒绝写入剪贴板，请手动复制"——两条路给的都是
**服务答应的同一批字节**，页面不自己拼引用、标题或格式。为了让退化那支在 DOM 桩件里也可测，
补了桩件缺的三个能力（`navigator`、`focus()`、`select()`）：**桩件缺能力不是测试的失败，
是产品的盲区**——那一支代码本来每天都在真浏览器里跑，只是没人能在离线桩件里点它。

**浏览器走查到 11 件。** 新增 `clipboardHoldsTheServedBody`：Chromium 拿到剪贴板权限后点
复制，再读回剪贴板，和**创建路由的应答**逐字节比，而不是和走查自己打的字符串比。
各阶段发请求数仍是 `[0,0,1,1]`：两次"没填理由／没填记录人"的本地拒答**没有真的发出请求**。

**两把静态尺为什么读数一模一样。** 这一轮 `build/main.js` 从 603,048 涨到 605,670 字节，
但对比度仍是 `checked=14002 belowAA=0 unparsable=0 controlMisses=0`（两套主题各 50 个面）、
几何仍是 112 个面 `docOverflowX=0 clipped=0 stray=0`。这不是尺坏了：两把尺的路由清单里
都有 `#/knowledge`（`audit_workbench_contrast.mjs:68`、`audit_workbench_overflow.mjs:106`），
**但它们只走到列表，从不点开一条条目**，新控件在详情面板里，落在它们的行走路径之外。
所以这块界面的证据来自走查和 `appshell`，不来自这两把尺——这句话写下来，是为了下一轮
不要把"读数没变"误读成"改动没被量到所以没风险"。

**于是这一行升到 DONE。** 新增 2 条回执（unit／browser，逐条绑 `72710b7f04b9` 与 bundle
sha256 `3fdb4f636b5c`），`currentExecution.evidence` 277→**279**，直方图
**`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**。剩下的两格仍然不是工程缺口：`DL-KB-13` 要 owner
对 150 KB 上限表态（同一把尺现在读 gzip **158,722** 字节），`DL-KB-16` 要具名真人；
`DL-KB-15` 的前置是本机可用的推理服务，本轮不部署、不自行下载权重。

**已经看清的下一刀。** 方案的参考选择器现在只给得出 5 种类型里的 2 种（`ASSET`、`KNOWLEDGE`），
`BRIEF`／`DIRECTION`／`PROMPT_RESULT` 服务收得下、界面上选不到。三条读路由
（`/api/projects/<id>/briefs`、`/directions`、`/prompt-results`）都已经存在且各有合同行，
所以这一刀不需要新路由，只把选择器补全并把"这一页读到几条、还有更早的没读到"说清楚。
### 5.41 选择器补齐五种类型：闭环的第一环在界面上接上了（`f6ec0fa0`＋`e172e33e`）

**缺口是怎么留在那里的。** 上一轮写完 §5.40 的"下一刀"就动手做了。做完发现这件事的形状很典型：
服务收五种 `REFERENCE_KINDS`，三份 schema 的四个枚举位置都写着五种，解析器五种都会钉版本与摘要，
三条读路由存在、各有合同行、也各有载荷比对——**只有选择器只列了两组**。
每一侧各自都自洽，所以没有任何一条单元测试能看出中间断了一截：这是**跨侧缺口**，
不是某一侧的缺陷。

**补了什么。** `loadProjectChoices()` 一次 `Promise.all` 读三条项目内清单，
选择器从两组变成五组 `<optgroup>`：本工作区素材／需求 Brief／方向／提示词结果／知识与提示词库。
`result_id` 在服务里按修订存多行，所以清单里一个编号只列一次（取最大修订那一行）。
分页不诚实就是页面替服务说话，所以 `next_cursor` 不是 null 时明说
"这一页之后还有更早的需求 Brief、方向没有读到"。换工作区时 `refreshAssets()` 改名
`refreshReferenceSources()`——它现在重读的是"这份方案能引用什么"，不只是素材。
**一条读失败会怎样**：`apiOrEmpty` 在被拒时是**拒**，不是退回空载荷（只有没 token 的开发态才给空），
所以 `Promise.all` 的失败走到调用方已有的那个 `catch`，屏上说"工作区读数失败：…"。
它不会把一次被拒的读写成"这个工作区还没有需求 Brief"——那句是关于库的断言，不是关于失败的。

**顺手修掉一个一直存在的悬挂 promise。** 首屏那行
`void (async () => { await loadKnowledgeChoices(); })()` 没有 `catch`：库的路由一旦被拒，
这里就是一个未处理的 rejection，而选择器还挂着"库里还没有条目"那句话——同样是把失败说成了关于库的事实。
现在它把拒接住写成 `库未读回：<服务的理由>` 再重画一次。§5.40 已经立过这条规则
（"空的回答是'库里还没有'，被拒的回答是'没读回'"），当时漏掉的是**发起读的那一行**。

**闸门自己报了一次自己的旧账。** 删掉 `verify_workbench_route_calls.py` 里
`GET .../directions` 的 `BACKEND_ONLY` 豁免，不是我改口：门禁先判红
`STALE_BACKEND_ONLY … the frontend now calls it; the exemption is no longer true`。
那句话原先是真的（界面确实只从 design-layer 投影里取方向），现在界面真的分页调它了，
豁免就成了假账，所以删的是豁免而不是断言。

**加了什么牙齿。** `test_the_workbench_picker_labels_exactly_the_kinds_the_store_accepts`
把界面上 `REFERENCE_KIND_LABELS` 的键与 `REFERENCE_KINDS` 逐一比对，并要求每种都有一个
`referenceGroup('KIND', …)`。这条测试如果上一轮就存在，KNOWLEDGE 那一刀不会留下这个缺口——
**它不是给已经修好的东西补分数，是把上一轮真正踩到的那类断裂写进闸门口子**。
浏览器走查 11 件→**12 件**：`pickerOffersBothSources` 改名 `pickerOffersAllFiveKinds`，
另加 `planCitesEveryKind`——走查在同一次保存里挂上 KNOWLEDGE／BRIEF／DIRECTION／PROMPT_RESULT
四种引用，要求**服务**回一个 `revision >= 1` 与一条摘要（页面只发类型和编号，
任何一种钉不住就是这里红，而不是悄悄存一条没法核对的引用）。
§5.39 与第七轮读数里出现的 `pickerOffersBothSources` 是当时的状态名，随断言加宽在本轮改名。

**三把尺与"读数没变"。** 收口 bundle 609,452 字节 / gzip **159,775**（同一把尺，第八轮记录 158,722）。对比度仍
`checked=14002 belowAA=0 unparsable=0 controlMisses=0`（50 个面），几何仍 112 个面
`docOverflowX=0 clipped=0 stray=0 tiny=0`。这次读数不变的原因和上一轮不同，也更该写清楚：
**`<option>` 的文字不是被画的文本 run**——`<select>` 收起时只画当前一项，所以五组选项不会新增
对比度样本；界面真正新增可见文字的是引用列表里每一行的类型标签，而那要先有引用才画得出来，
这条路径由走查覆盖（`citedRow` 断言含"知识条目"），不由这两把尺覆盖。
路由级 UI 审计在提交后的字节上重跑：`ok=true violations=0`，宽度 `1280,1920,2048`，
它的 `environment.commit` 字段直接记了 `e172e33e964b`——**这一条回执绑的是提交号本身**，
不是靠旁边的文件推断。

**账本动了两格记录，没动状态。** `DL-KB-08` 仍是 DONE，回执 11→13（unit／browser，
逐条绑 `e172e33e`）；`currentExecution.evidence` 279→**281**。直方图仍是
**`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**——本轮没有可升的行：剩下两格 `DL-KB-13`（体积上限裁定＋
3 位真人无指导任务）与 `DL-KB-16`（具名真人签字）要的是 owner 与真人点头，`DL-KB-15` 要的是
本机可用的推理前置，本轮不部署模型、不自行下载权重，也不把"选了模型"写成"推理已验证"。

### 5.42 CI 抓到一次我自己的红：证据清单在本地根本不执行（PR run `40140337003`）

**读数。** 推送 `5041b8f5` 之后：push run `40140333553` success（light gate），
同 SHA 的 pull_request run `40140337003` **failure**，逐作业看只有一个红——
`Workbench browser E2E (exact-SHA controlled-runtime, no-skip)`，其余 10 个作业 success
（`gh api …/runs/40140337003/jobs`）。红的那条断言是：

```
AssertionError: Lists differ: ['bla…', 'clipboardHoldsTheServedBody', 'emptyTrail…]',
                            != ['bla…', 'emptyTrailSaidNotAskedAndAnswered', …, '…ody']
```

**根因不是产品，是我写的断言。** `assertEqual(sorted(kb_states), [字面表])` 里那张字面表
是我按浏览器驱动的**写入顺序**抄的，`clipboardHoldsTheServedBody` 被我加在末尾——
左边永远是字母序，右边不是，**两边不可能相等**。这一条从它被提交的那一刻起就只有一种结果。

**为什么本地看不见。** `test_workbench_design_layer_e2e.py` 的整段证据断言包在
`if os.environ.get('E2E_REQUIRED') == '1':` 里，那个变量只有 CI 的 no-skip 作业设。
本地跑的是同一个测试、真的启动了同一个 Chromium、真的重写了同一份 summary，
`Ran 2 tests / OK` 也是真的——**但它验的是驱动自己那条 `E2E_OK`，那十二件事实的清单比较一次都没执行**。
所以我把"本地浏览器走查全绿"当成过这一条的凭据，而它当时并不能为这句话作证。

**两边都补了，不是把断言删掉。** `b90aaf66`：
① 条件改为 `E2E_REQUIRED == '1' or summary.is_file()`——走到这一行的运行必然有工具链，
驱动失败会以非零退出先红，所以**只要 summary 存在就把它验掉**；required 而没有 summary 仍然是硬失败。
② 两张清单（六态与十二件）都包进 `sorted(...)`，把"顺序打错"从一种可写出来的错误改成写不出来的。
③ 牙齿按老规矩双向验：改完之后本地跑 `Ran 2 tests / OK`；再往清单里种一个 `'bogusStateName'`，
**本地立刻** `AssertionError: Lists differ … 'bogusStateName'`——同一种错，这次不用等 CI。
种完即还原（`git checkout --` 只还原了这个文件，还原前它没有别的未提交改动；
我随后重放的两处 `sorted()` 包裹也是当场补回来的）。

**这条要给下一轮的口径。** 本地 `test_workbench_design_layer_e2e … OK` 这句话**不再**等于
"清单事实已验"，它的含义由本段起改变：现在它确实包含那十二件，因为条件不再只认 CI。
在它之前写的每一句"本地浏览器走查全绿"，验的是驱动侧的 `E2E_OK` 与 summary 里的
`allAsserted`，**不是** Python 侧的清单比对——这两件事以前不是一回事，以后才是。

### 5.43 尺子开进详情面板，第一件事就是量出一个真的 AA 缺陷（`a7c43891`）

**为什么这一刀值得做。** §5.40 与 §5.41 连着两轮写了同一句话：两把静态尺走到 `#/knowledge`
就停了，从不点开一条条目，所以判断轨迹的小字、两个判断表单、剪贴板被拒时的退化框
**从来没被对比度与几何量过**——只被走查点过，而走查断言的是"话有没有说对"，不是"这行字够不够黑"。
一句被写两次的覆盖盲区，就是下一刀。

**做法照已有的先例。** 方案详情早就是这张尺的一个具名状态（`assistant+plan-detail`：先用服务
写一条合成方案，再点开，等镜头表与材料格式读回来才量）。这一轮给知识条目做了同一件事：
`seedKnowledgeEntryForAudit()` 走真路由 POST 一条合成条目（`created_by` 写明"合成，不是真人"，
随临时状态目录一起丢），点开 `.kb-open`，等 `kb-copy-body`、判断表单与正文都画上（20s 上限，
**没装配完就说"无人认领"，不量空壳**），量成 `knowledge+entry-detail`。对比度与几何两侧都加，
两份闸门的测试各自要求这个状态在**每个宽度**都出现在报告里——不然"少量一块面板"会变成一次安静的绿。

**它第一次跑就量到一个缺陷。** 逐字读数（控制跑，改动前的样式表、同一个 bundle、同一份种子）：

```
LOWCONTRAST 1440:knowledge+entry-detail 4.08:1 need>=4.5:1 16px bold opacity=1
  fg=rgb(49, 108, 255) :: strong :: 镜头拆解三步法（合成）
```

**为什么列表屏从没报过它**：这行字是 `.kb-open:hover` 的色——鼠标停在哪儿，哪儿才换色。
点开详情时指针正好还压在刚点开那一行的标题上，于是量到的就是 hover 态。`--accent` 是品牌蓝
`#316CFF`，在这块表面上只有 **4.08:1**，16px 粗体按 AA 要 4.5:1，深色与浅色两套主题各红一次
（那一轮 `Ran 3 tests … FAILED (failures=2)`）。这条控制与修复后的对照都进了回执：
`kb-03-contrast-prefix-control.log`。

**改的是字色选择，不是品牌。** 三条 hover 墨色（`.kb-open:hover`、`.as-plan-open:hover`、
`.capability-chip-x:hover`）改用 `--secondary`——这个 token 正是本项目为"小号有色文字"准备的
按主题走的那一支（`ui2026/light` 的覆盖块就是重指它，"而不是让浅色主题带着读不清的小标签上线"）。
`--accent` 本体一个字没动：品牌蓝能不能承载正文级白字仍是要 owner 裁的账，
**闸门量出一个缺陷不等于拿到了改品牌的许可**。

**量的面确实变大了。** 对比度 50→**52** 个面、`checked` 14,002→**14,278** 条文本 run，
`belowAA=0 unparsable=0 controlMisses=0`；几何 112→**116** 个面，
`docOverflowX=0 clipped=0 stray=0 tiny=0`，四个宽度的条目详情都报到 `state=read`。
**计数上升就是"伸手够得更远"的证据**，这不是把阈值放宽换来的一次绿。

**账本。** `DL-KB-03`（知识与提示词库界面）加一条 `visual_review` 回执，
10→11 条，状态仍 DONE；`currentExecution.evidence` 281→**282**。
本轮没有行需要升：可机器证明的面上一轮已经升完，剩下的 `DL-KB-13`／`DL-KB-16`／`DL-KB-15`
仍是 owner、真人与本机推理前置的账。

### 5.44 几何尺也开进方案详情：先量到"报了但没算"这个洞（`7d97ac8d`）

**不对称在哪里。** §5.43 给知识条目补了几何之后，剩下的形状就看清楚了：对比度尺**早就**会点开一份
方案（`assistant+plan-detail`，先经服务写一条合成方案），而几何尺从来不点。也就是说
**镜头表、导出面板、反馈块**这几块界面，在 1280／1536／1920 三个宽度上从来没有几何断言——
一条长中文需求会不会把面板顶宽、镜头表会不会在窄一侧挤断，没人量过。

**照先例做，但先掉进自己的坑。** 第一版把两个面板行塞进 `report.routes` 就结束了。看起来是对的：
报告里有这两行，测试也要求它们出现。**但闸门累计量的那几行（`clippedTotal` 等）与
`occluded → specProblems` 只在路由循环和原有的交互态分支里做**，我新加的行既没进计数器也没进
失败清单——**面板一旦被点开，它的 clip／stray／occlusion 是打印出来给人看、然后被忽略的**。
这正是"报了"与"算了"不是一件事。改成一个 `absorbPanel(key, m)` 单入口（和对比度尺里 `absorb`
同一句话：两处累计会让同一批计数有两个主人），并给测试加一条硬断言：
`OV_SUMMARY interactions=` 的数量**必须等于**报告里带 `+` 的行数。少一行就是红。

**第二个洞是这把尺自己的措辞。** 新行进来之后 `occluded=3`：顶栏的设置／工作区／搜索三个入口
"被遮住"。逐字读数是 `by:"elementFromPoint returned null"`，rect 的 `top≈-1814`、视口高 900——
它们不在"被什么东西盖住"，它们在**视口上方 1.8k 像素处**：设计辅助这一屏很长，点开方案详情时
浏览器把整份文档滚了下去。而这个探测块自己的注释写着"不在屏上"与"被盖住"是两件事，
代码却没遵守——`!r.width || !r.height` 只挡住了没有盒子的情况。现在多加一个 `notInView` 桶，
带上中心点、视口尺寸与 `top`／`bottom`，`occluded` 只留给真的被别的元素盖住的情况
（那仍然会进 `specProblems` 把闸门判红）。

**要不要把顶栏吸顶？** 查了采纳包：`02_完整产品方案.md` 只在"玻璃用在哪儿"这一句里提到顶栏，
**没有任何一条要求它常驻可见**。所以这一条按"实测到的现象＋留给 owner 的打磨问题"记账，
不擅自加 `position:sticky` 去补一个规格里没有的要求——那是替 owner 做设计决定。
`notInView` 现在 12 条（3 个入口 × 4 个宽度），全部来自 `assistant+plan-detail` 这四行。

**读数。** 几何尺这一提交 116→**120** 个面（四个宽度各加一行方案详情；§5.43 已经把 112 加到 116，
对比度尺停在 52 面／14,278 run），
`docOverflowX=0 clipped=0 stray=0 tiny=0 occluded=0`；四个宽度的方案详情都落到 `state=read`、
`detailsExpanded=6`。账本加 1 条 browser 回执（`DL-KB-08` 13→14 条，状态仍 DONE），
`currentExecution.evidence` 282→**283**。直方图不变：**`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`**。

**剩下还没被尺子碰过的面**（下一刀的清单，都是"点开才有"的那一类）：目标组合面板的展开态、
我的方案里两条方案的对照态、以及反馈块写入后的读回态。做法已经现成：种子 → 点开 → 等真实状态
→ 量成具名行 → **进同一个 single-sink 计数**，再补一条"报了必须等于算了"的断言。

### 5.45 目标组合：量"选中之后"那一态，这次没有新缺陷（`b4a807fb`）

**为什么这一态才是要量的。** `#/target-profiles` 一直在两把尺的清单里，但量到的永远是**没选目标**
的那一屏：`08_STITCH完整提示词.txt` 第 13 行给这一面的话是"先选软件／Agent，再看到该入口可用的
模型／模式……显示官方支持与本项目未测试的区别"，而两栏真相与四档 `support_state` 药丸**是选了之后
才画出来的**。没选的那一屏再干净，也不替选中那一态说话。

**用什么当"到位"的判据。** 不用"有字了"，用界面自己写的状态位：`#tp-combination` 带
`data-mode = unspecified | partial | plan-only | target`，只有真的解析到一份档案才成 `target`。
探测器按 `tp-software → tp-agent → tp-entry → tp-model → tp-task-mode` 依次选第一个可选项
（没有得选或已有值就跳过），然后等这个位。**等状态而不是等可见性**——一次诚实的空回答同样"有字"。

**读数。** 对比度 52→**54** 面、`checked` 14,278→**14,764** 条文本 run，`belowAA=0`；
几何 120→**124** 面，四个宽度的组合态都落 `state=read`，
`docOverflowX=0 clipped=0 stray=0 tiny=0 occluded=0`，`notInView=0`——
这条也顺手把 §5.44 那个观察的边界说清了：顶栏被推走是**长设计辅助屏**特有的，不是全站现象。
**这一刀没有量出新缺陷**，所以它只留一条 browser 回执与覆盖面数字，不写"修好了什么"。
`DL-KB-10` 回执 3→4 条（状态仍 DONE），`currentExecution.evidence` 283→**284**，
直方图 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`** 不变。

**这套做法现在有四处成型**（条目详情、方案详情、目标组合、以及原有的全局搜索与证据投影）：
种子／选择 → 等界面自己写的状态位 → 量成具名行 → 过同一个计数入口 → 测试要求"每宽度都在"且
"报了＝算了"。剩下还没被尺子开进去的面：**我的方案的两案对照态**与**反馈块写入后的读回态**。

### 5.46 两案对照真的被量到了：写第二份修订，才有那一态

**这一态此前不存在于任何尺子里。** `DL-KB-12` 的验收写的是"对照页比的是两份**真实修订**"，
而那块面板要满足两件事才会画出来：这份方案**得有第二个修订**，而且有人按下"对照"。
两把尺以前既不写第二版也不按按钮，所以十二行并排的内容从未被量过——
**此前它没被量过，也就谈不上通过**。

**怎么让它存在。** 种子在原来那条创建之后，**走界面用的同一条路由**
`POST …/assistance-plans/<id>/revisions`（带 `expected_revision: 1`，只改需求句）写第二版；
然后打开 `#as-compare`、把两个下拉选到 r1／r2、点"对照"。等待判据是面板自己的两句话：
`#as-compare-body` 里 ≥12 行，且 `#as-compare-status` 不再是"正在读回…"也不是失败——
**状态位取自那行文字，不是硬写 `read`**（写死的话，将来一次读回失败也会被判成"已读回"）。

**读数。** 对比度 54→**56** 面、文本 run 14,764→**15,270**，`belowAA=0`；
几何 124→**128** 面，四个宽度的对照态都落 `state=read`，
`clipped=0 stray=0 tiny=0 occluded=0 docOverflowX=0`——**1280 那一档也干净**，
这是这块并排面板最值得问的一句话（两栏长中文最容易在窄一侧挤断）。
`notInView=3` 又出现了，原因与 §5.44 同一条：设计辅助屏很长，滚到详情时顶栏被推上视口之外；
这条继续按"实测现象＋留给 owner 的吸顶问题"记账，不动布局。

**账。** `DL-KB-12` 加 1 条 browser 回执（2→3 条，仍 DONE），`evidence` 284→**285**。
直方图 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`** 不变。
"点开／选中才量"这套做法到这里覆盖了 条目详情、方案详情、两案对照、目标组合、全局搜索、证据投影
六处具名面板态；剩下的同类缺口只有一个：**反馈块写入后的读回态**（它也在方案详情里，
需要一个 POST 才有内容）。

### 5.47 反馈块写入之后才有那一态；顺手把一次"闸门自己崩了"记账

**最后一块"点开才量"的面。** 闭环的最后一环是「用户自愿记录外部使用反馈」，
而两把尺以前走到方案详情就停——反馈历史那行、`相同/未说明` 那几个格子、结果词的词表着色，
**都要先写一条才有内容**。这一轮把它们量进去了。

**写的是什么，怎么写得不越界。** 结果词从服务给的那一份里取第一个（页面不抄第二份词表），
两条必填填闸门文案，**记录人写「审计脚手架（合成，不是真人签署）」**——
这一格将来会出现在历史里，绝不能读起来像一次真人签署。等待判据仍是界面自己的话：
`#as-fb-history` 出现行、`#as-fb-status` 不再说"正在读回"也不是失败；
`state` 字段从这行文字**读出来**，不是硬写 `read`。

**一次崩溃被记成账，而不是被"跑绿"盖过去。** 这批改动落地前，有一次整模块跑在 `w=1536` 死了：
`locator.click: Timeout 30000ms exceeded`，等的是 `#as-list .as-plan-open`——
那一屏的方案清单当时没有可点开的行，而闸门**没有把这件事说出来，直接把进程弄崩了**。
现在这一步先数行、数不到就把 `#as-list-meta` 的原话引用进 `interactionMissing` 再往下走。
**之后两次完整跑都干净，所以这不叫"修好了"**：原因没有确定，改的是"下一次它会自报"。
这条按事实记在这里，不给它编一个原因。

**读数。** 对比度 56→**58** 面、文本 run 15,270→**15,772**、`belowAA=0`；
几何 128→**132** 面，四宽度反馈态全 `state=read`，`clipped/stray/tiny/occluded/docOverflowX=0`
（`notInView=3` 与前两节同因）。六类"点开才有"的面至此都有具名行：
条目详情、方案详情、两案对照、反馈读回、目标组合、全局搜索、证据投影。
`DL-KB-16` 加 1 条 browser 回执（3→4 条，状态仍 `PARTIAL`——差的仍是具名真人，不是界面），
`evidence` 285→**286**，直方图 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`** 不变。

### 5.48 把 STITCH 的六个值做成第三套色板：它第一次量就把自己量红了

**这是 owner 那句"一比一复刻 STITCH 界面设计"的第一件实物。** `08_STITCH完整提示词.txt` 的视觉段
逐字给了六个值：单一低饱和强调色 `#356B92`、正文 `#17212B`、次级 `#566472`、背景 `#F4F6F8`、
内容 `#FFFFFF`、边界 `#D8DFE5`。按既有裁定，**新任务包配色不覆盖既有配色**，所以它落成第三套
可选色板 `?palette=stitch`，默认那套一字节没动（`test_workbench_stitch_palette.py` 逐条钉住
`--color-bg #060A14`／`--color-primary #316CFF`／`--color-text #F5F7FC` 还在默认 `:root` 里）。
**只做浅色一侧**：包里没写暗色值，自造一份暗色就是把"复刻"变成"照着自己的口味猜"。

**第一次量，闸门就把这套颜色判红了。** 珍珠白画布上，`warn/success/error` 药丸的填充是淡底，
而我沿用深色主题的白墨——12px 粗体的状态词实测 **1.83:1 / 2.2:1**，
`UNRESOLVED / VERIFIED / E0 / BLOCKED / NOT_ACCEPTED …` 这些词一个不落，
`LOWCONTRAST` 共 **405** 行，闸门 exit 1。控制跑逐字留在
`kb-06-stitch-pill-ink-control.log`，同 bundle、同种子、只改那两行角色。
**修的是角色，不是阈值**：`--tag-ink` 取包自己声明的正文色，info 药丸保持中性淡底
（这套基线要的是"单一"强调色，把 info 填成深色再压白字，是同一个错换了一处犯）。
修完同一条尺 `CT_OK`：stitch/light 下 **58** 个面、**15772** 条文本 run，`belowAA=0 unparsable=0
controlMisses=0`；几何 **132** 个面，`clipped/stray/tiny/occluded/docOverflowX` 全 0。

**顺手挖出一个可达性缺陷，形状很眼熟。** `readThemeChoice()` 判断色板用的是硬写的
`urlParam('palette') === 'ui2026' ? 'ui2026' : 'design-lab'`——
于是第三套色板在菜单里、在 CSS 里、就是**进不去**：URL 与 `data-palette` 属性都被折回两套之一。
现在统一问 `PALETTES` 这张表，并留一条测试专门判这个写法回潮。
**"表里加了东西，读表的地方还在抄枚举"是同一类错的第 N 次出现**，这轮的账记在这条上。

**账与边界。** `DL-KB-06` 加 1 条 `visual_review` 回执（12→13 条，状态仍 DONE），
`evidence` 286→**287**，直方图 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`** 不变。
体积：bundle 609,452→**609,950** 字节、gzip 159,775→**160,052**（+277），
`DL-KB-13` 的 150 KB 上限裁定仍在 owner 手上，本轮不靠删内容凑数。
这是**量**，不是**批**：设计批准仍等 owner 真机测试，`DESIGN.md` 不进已批准状态，
也没有拿 VLM 或像素差当签字。

### 5.49 包里的数字规则进入尺子：119 处 11px、23 处半透明列表底、474 个超带半径。

**这一段做的是什么。** 20261023 包写视觉规则用的是数字：`09_DESIGN.md` 给正文 14–16px、元数据至少
12px、控件高度约 36–40px、圆角输入/按钮 6–10px、临时面板 12–16px；`08_STITCH完整提示词.txt` 给
玻璃只给顶栏／导航／临时面板、长文字与列表实底。上一轮把六枚颜色做成可选主题之后，"一比一复刻"
剩下的部分就是这几句话，而它们能不能成为断言，取决于能不能在**已渲染的文档**上量出来。静态 grep
答不了：`.eyebrow` 在前段写 10px、在后段抬回 12px，只有算完层叠才知道人读到的是几号字。所以这一刀
把尺子加进对比度闸门（`CT_SPEC` 段），跟 AA 用同一次渲染、同一批面。

**第一次量出来的债**（修复前那次扫描是 width 1440 **单宽度**；下面"改完之后"那一段是 1440+1920
**双宽度**，两处分母不同，不能互换）：小于 12px 的文本 run
**119** 处，最小 **11px**，来源是 `--uif-font-micro` 与五处硬写 11px（导航分组标签、页脚、连接状态行、
KPI 注脚、badge）；列表行与文字按钮压在半透明白上 **23** 处（`li.list-item` 的 74／100 与
`button.ghost-btn` 的 62／100）；表单控件圆角超过 10px **474** 个。玻璃这条一测就过：全 UI 只有
`aside#app-sidebar.sidebar blur(18px) + header.topbar blur(18px)` 两处 `backdrop-filter`，正好是包允许的对象，所以这条不改样式，改成把名单钉住。

**改的是哪些，以及为什么这样切。** 12px 地板全局抬（不动颜色，也不动 `--accent-hover`、
`--border-strong` 这类已实测的地板值）；实底与半径按 owner 裁定只做加法——写在
`[data-palette="stitch"][data-scheme="light"]` 的作用域里，默认炭黑一字节不动。半径取带内上限 10px，
适用对象是这句话的字面对象（input／select／textarea 与四类动作按钮，实测 **1002** 个，1440+1920
两个宽度合计，单宽度那次是 501 个）；另外
**1818** 个 painted 控件（同一双宽度扫描）是列表行、导航项与药丸，同一句把面板写成 12–16px，而包自己的 HTML 用
`border-radius:20px` 的 `.status`，所以它们保持各自半径、只在直方图里登记。控件高度写的是「约 36–40px」，
主动作实测 **41–47px**（比包里的目标更高），同样只登记不断言。这几处取舍写在测试的 docstring 里，
不靠尺子的沉默。

**改完之后的同一条尺**（stitch／light，widths 1440+1920）：

```
CT_SUMMARY checked=15772 belowAA=0 pseudoLayers=5250 coveredForeign=0 obscured=4 unparsable=0 collapsedOpened=6248 controlMisses=0 strict=1 mathChecks=4 mathBad=0 colourChecks=4 colourBad=0
CT_SPEC_ENFORCED below12=0 translucentTextHosts=0 unparsableAlpha=0 glassOffAllowlist=0 formRadiusOver10=0 formControls=1002 formBelow36px=14（控件高度写的是「约36–40px」，实测读数只登记不断言：本 UI 的主动作在 41–47px，比包里的目标更高，不在 6–10px 那条带子一样的强制范围里）
```

几何尺量同一份 CSS：

```
OV_SUMMARY clipped=0 stray=0 tiny=0 interactions=28 [1440:evidence+projection-read=read,1440:capabilities+global-search=read,1440:knowledge+entry-detail=read,1440:assistant+plan-detail=read,1440:assistant+plan-compare=read,1440:assistant+plan-feedback=read,1440:target-profiles+combination=read,1280:evidence+projection-read=read,1280:capabilities+global-search=read,1280:knowledge+entry-detail=read,1280:assistant+plan-detail=read,1280:assistant+plan-compare=read,1280:assistant+plan-feedback=read,1280:target-profiles+combination=read,1536:evidence+projection-read=read,1536:capabilities+global-search=read,1536:knowledge+entry-detail=read,1536:assistant+plan-detail=read,1536:assistant+plan-compare=read,1536:assistant+plan-feedback=read,1536:target-profiles+combination=read,1920:evidence+projection-read=read,1920:capabilities+global-search=read,1920:knowledge+entry-detail=read,1920:assistant+plan-detail=read,1920:assistant+plan-compare=read,1920:assistant+plan-feedback=read,1920:target-profiles+combination=read] brand=4 navEdge=4 spec=0 theme=stitch/light
```

字号直方图（各面合并）：12px x 6476 13px x 5274 13.3px x 464 14px x 122 15px x 192 16px x 2882 17px x 56 19px x 22 21px x 16 24px x 6 26px x 2 32px x 52 35px x 38。

**这条断言会咬。** 同一条 enforce 在默认配色下必须红：
`test_the_pack_number_assertion_refuses_a_theme_it_was_not_applied_to` 跑 design-lab／dark，断言出现
`SPEC-VIOLATION 长文字与列表实底`，并断言该配色 `below12=0`——后半句证明 12px 是全局抬的、不是只在
珍珠白里改，前半句证明这条尺不是摆设。

**账与边界。** `DL-KB-06` 加 1 条 `visual_review` 回执（13→14 条，状态仍 DONE），
`evidence` 287→**288**，直方图 **`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`** 不变；本轮没改 TS，
bundle 字节不动。下一刀的对象已经指名：包还要「单一低饱和强调色」与「避免大面积渐变」，而
`.primary-btn` 现在是两停 brand 渐变，`--brand-gradient-*` 在珍珠白下仍是那对更深的蓝，不是平涂的
#356B92；这条要连 AA 一起重测之后才好说，本轮不拿算出来的比值当通过。仍未裁的两件照旧记账不代做：
`DL-KB-13` 的 150 KB 上限，与长屏上顶栏是否吸顶。

### 5.50 包的「避免大面积渐变」变成一条面积读数：42 个面板级渐变面被压平。

**这一条为什么能量。** 上一段把包的数字规则接进对比度尺之后，还剩一句没有对象：
`08_STITCH完整提示词.txt` 的「避免大面积渐变」。「大面积」不写清就是空话，所以这条尺把对象定为
**同一屏上看得见的渐变面积**：一个 painted 元素的 `background-image` 含渐变，且它与视口的可见交集
超过 25% 就计入。用可见面积而不是布局面积，是因为长列表卡片的布局高度可以量到视口的 90 倍，
照布局算会把一条 24px 高、95% 已经滚出屏幕的高光判成违规——那是把尺子指向自己造出来的错误。
阈值取 25%：一个按钮、药丸或细进度条不可能到，一整块内容底或整屏装饰一定到。

**第一次量的债**（stitch／light，width 1440，单宽度）：渐变 painted run **656** 条，其中可见面积过阈值
**42** 处，来源是三类：`.panel` 的底（`linear-gradient(180deg, surface 82%, surface 94%)`，单卡实测可见
占比 28–75%）、`.panel::before` 的整卡高光、`.grid-bg` 的 `inset:0` 装饰网格（opacity .22 加径向 mask，
整屏 100%）。

**改法是包自己的参照物给的**，不是我挑的：包里那份 `DESIGN-LAB_今日完整需求与可行性方案_20261023.html`
的卡片写成 `section{background:#fff;border:1px solid var(--line)}`——平涂白卡压 `#f3f5f7` 画布，卡内没有
渐变也没有高光层。于是在 `[data-palette="stitch"][data-scheme="light"]` 作用域里把 `.panel` 改平涂、
`.panel::before` 的高光关掉、`.grid-bg` 不画；默认炭黑一字节不动（owner 裁定：新包的值做成可选主题，
不覆盖既有配色）。这一处顺带把上一段那条「长文字与列表实底」做得更彻底——面板底与卡内高光本来就是
正文底下的两层可变底。

**改完的读数**（同一条尺，stitch／light）：

```
CT_SUMMARY checked=15772 belowAA=0 pseudoLayers=0 coveredForeign=0 obscured=4 unparsable=0 collapsedOpened=6248 controlMisses=0 strict=1 mathChecks=4 mathBad=0 colourChecks=4 colourBad=0
CT_SPEC_ENFORCED below12=0 translucentTextHosts=0 unparsableAlpha=0 glassOffAllowlist=0 formRadiusOver10=0 bigOver25pct=0 formControls=1002 formBelow36px=14（控件高度写的是「约36–40px」，实测读数只登记不断言：本 UI 的主动作在 41–47px，比包里的目标更高，不在 6–10px 那条带子一样的强制范围里）
```

渐变 painted run 在同一条单宽度扫描上 656→**489**，可见面积过阈值 42→**0**；那份单宽度复测的原文留在
`design-lab/evidence/current-execution/task-artifacts/kb-20261025/kb-06-gradient-single-width-remeasure-20261025.log`，
这样 656→489 的比较是同一分母上的比较。上面那条 `CT_SUMMARY/CT_SPEC_ENFORCED` 来自回执所绑的
1440+1920 双宽度那次，分母不同（渐变 run 978、过阈值 0），两个数各记各的，不互换。AA 仍是 `belowAA=0`
（这不是"应该没影响"的推测，是这条尺重跑之后的读数）。几何尺量同一份 CSS：

```
OV_SUMMARY clipped=0 stray=0 tiny=0 interactions=28 [1440:evidence+projection-read=read,1440:capabilities+global-search=read,1440:knowledge+entry-detail=read,1440:assistant+plan-detail=read,1440:assistant+plan-compare=read,1440:assistant+plan-feedback=read,1440:target-profiles+combination=read,1280:evidence+projection-read=read,1280:capabilities+global-search=read,1280:knowledge+entry-detail=read,1280:assistant+plan-detail=read,1280:assistant+plan-compare=read,1280:assistant+plan-feedback=read,1280:target-profiles+combination=read,1536:evidence+projection-read=read,1536:capabilities+global-search=read,1536:knowledge+entry-detail=read,1536:assistant+plan-detail=read,1536:assistant+plan-compare=read,1536:assistant+plan-feedback=read,1536:target-profiles+combination=read,1920:evidence+projection-read=read,1920:capabilities+global-search=read,1920:knowledge+entry-detail=read,1920:assistant+plan-detail=read,1920:assistant+plan-compare=read,1920:assistant+plan-feedback=read,1920:target-profiles+combination=read] brand=4 navEdge=4 spec=0 theme=stitch/light
```

**这条也会咬。** 默认炭黑配色在同一条 enforce 下现在报两条红：`长文字与列表实底` 与 `避免大面积渐变`。
`test_the_pack_number_assertion_refuses_a_theme_it_was_not_applied_to` 断言这两句同时出现在红里，
所以"珍珠白下为 0"不是靠把默认配色一起改掉换来的。

**账与边界。** `DL-KB-06` 加第 15 条 `visual_review` 回执（带 `-r2` 的新文件，上一份一字不动），
`evidence` 288→**289**。包里剩下的句子按能量化的顺序排队：「单一低饱和强调色」与「避免霓虹」——
主按钮现在仍是两停 brand 渐变，珍珠白下不是平涂的 `#356B92`，这条必须连 AA 一起重测才好说；
「字段密度」与「标题层级」要先定分母（按哪一列算密度）才好写成数。owner 未裁的两件继续记账不代做：
`DL-KB-13` 的 150 KB 上限，与长屏上顶栏是否吸顶。

### 5.51 包里那句「单一低饱和强调色」被拆成一支可数的第二色，然后归零。

**这条量的是什么。** `08_STITCH完整提示词.txt` 写的是一句正面断言——「单一低饱和强调色 #356B92」，
它的反面是可数的：界面里还有没有第二支蓝。答案是有，而且是成对的两停：`--brand-gradient-from #1D4FC4`
与 `--brand-gradient-to #2A63D8`（style.css:23-25，2026-10-06 为了让白字过 AA 从 `#316CFF` 加深来的，
那次实测记录就在同一行上方）。尺子读的是**已渲染的色**，不是样式表里的 token：把 painted 元素的
`background-color`／`background-image`／`border-top-color` 里出现 `rgb(29,79,196)` 或 `rgb(42,99,216)`
的算一处，所以 token 从哪条规则流过来都一样会被数到。

**第一次量（stitch／light，width 1440）**：珍珠白下 **21 处** painted 面仍是那对深蓝——
`button.primary-btn`（能力详情里的「使用此能力」）、`#research-submit`、`#preflight-run`、`#jury-submit`
这些主动作。压平到包里那一支之后为 **0**。

**这一刀自己带回来一个已经量掉的缺陷，尺子当场拦下。** 压平的第一版没排除禁用态：我的规则特异性
压过了 `button:disabled`（style.css:303，2026-10-09 那次实测把禁用的「使用此能力」从 2.31:1 改成
平涂次级底＋虚线边＋可读次级墨），于是 13px 的次级墨被压在强调色底上报出 **1.06:1**，产品级红 **29** 条。
加上 `:not(:disabled)` 之后这三处只在可点状态下翻成强调色，禁用态继续用它自己的非文字线索。
**「高特异性规则顺手覆盖掉一个为无障碍而写的状态」是这一轮的根因**，不是我改错了色值。

**顺手修了尺子自己的账。** `belowAA` 以前按 `failCount - control.reported` 扣植入控制，
而 `control.reported` 是「每个 id 至少被报过一次」的布尔计数（它证明解析器还认得那串颜色序列化，
这个作用不变）；一个长页面会植入多枚同名折叠控制，多出来的行就被算成了产品债。现在按
**实际控制行数**扣，产品债与测试台自己的道具第一次分开，`controlMisses=0` 仍然要求每枚控制都被报出。

**改完的读数**（同一条尺，stitch／light，widths 1440+1920）：

```
CT_SUMMARY checked=15772 belowAA=0 pseudoLayers=0 coveredForeign=0 obscured=4 unparsable=0 collapsedOpened=6248 controlMisses=0 strict=1 mathChecks=4 mathBad=0 colourChecks=4 colourBad=0
CT_SPEC_ENFORCED below12=0 translucentTextHosts=0 unparsableAlpha=0 glassOffAllowlist=0 formRadiusOver10=0 bigOver25pct=0 brandBluePaints=0 formControls=1002 formBelow36px=14（控件高度写的是「约36–40px」，实测读数只登记不断言：本 UI 的主动作在 41–47px，比包里的目标更高，不在 6–10px 那条带子一样的强制范围里）
```

几何尺量同一份 CSS：

```
OV_SUMMARY clipped=0 stray=0 tiny=0 interactions=28 [1440:evidence+projection-read=read,1440:capabilities+global-search=read,1440:knowledge+entry-detail=read,1440:assistant+plan-detail=read,1440:assistant+plan-compare=read,1440:assistant+plan-feedback=read,1440:target-profiles+combination=read,1280:evidence+projection-read=read,1280:capabilities+global-search=read,1280:knowledge+entry-detail=read,1280:assistant+plan-detail=read,1280:assistant+plan-compare=read,1280:assistant+plan-feedback=read,1280:target-profiles+combination=read,1536:evidence+projection-read=read,1536:capabilities+global-search=read,1536:knowledge+entry-detail=read,1536:assistant+plan-detail=read,1536:assistant+plan-compare=read,1536:assistant+plan-feedback=read,1536:target-profiles+combination=read,1920:evidence+projection-read=read,1920:capabilities+global-search=read,1920:knowledge+entry-detail=read,1920:assistant+plan-detail=read,1920:assistant+plan-compare=read,1920:assistant+plan-feedback=read,1920:target-profiles+combination=read] brand=4 navEdge=4 spec=0 theme=stitch/light
```

**这条同样会咬。** 默认炭黑在同一条 enforce 下现在报 **三条**红：`长文字与列表实底`、
`避免大面积渐变`、`单一低饱和强调色`（21 处深蓝正是它的读数），
`test_the_pack_number_assertion_refuses_a_theme_it_was_not_applied_to` 断言这三句同时出现——
珍珠白的 0 不是把默认配色一起改掉换来的。

**账与边界。** `DL-KB-06` 加第 16 条 `visual_review` 回执，`evidence` 289→**290**，直方图
**`DONE 13`／`PARTIAL 2`／`NOT_STARTED 1`** 不变；TS 未改，bundle 字节不动。
包里的句子还剩两句没落成数：「字段密度」与「标题层级」要先定分母；`苹果式克制玻璃感` 已经用玻璃名单钉住，
`.app-nav button:hover` 这类 **hover 态**读同一对 brand token，但对比度尺目前只量静息态 painted 面，
所以那处不改也不宣称已合规——要改得先决定 hover 的墨色跟不跟着翻，这是一条需要 owner 拍的设计裁定，
不是我能替包猜的。owner 未裁的两件照旧记账：`DL-KB-13` 的 150 KB 上限，与长屏顶栏是否吸顶。

### 5.52 单一强调色这一条被撤回为「已测量、未满足」，证据是 CI 自己的读数。

**发生了什么。** 上一段的收口在本地（Windows + Chromium）是全绿的：珍珠白下压平三处 brand 渐变之后
`brandBluePaints=0`、`belowAA=0`。同一提交推到 CI，`Workbench browser E2E (exact-SHA controlled-runtime,
no-skip)` 在 Linux runner 上报 **2 条真红**，逐字是：

```
LOWCONTRAST 1920:target-profiles+combination 2.86:1 need>=4.5:1 16px opacity=1
  fg=rgb(222, 224, 227) :: button#tp-validate.primary-btn :: 按新目标重新校验
```

**为什么不是把色值再猜一次。** 那枚按钮的墨色是 `rgb(222,224,227)`（浅灰白，不是 `#fff`）。按 2.86:1
反推，它那一刻落到眼睛上的底比 `#356B92` 更亮（L≈0.23），而白字压那种底也只有约 3.79:1——也就是说
"改成平涂单一强调色"并没有把这一处带到 AA 之上，而我手上只有一次远程读数、没有 Linux 复现环境。
**在这种情况下继续调一个本地验证不了的色值，就是把绿灯建立在猜上**，所以处理是：三处渐变恢复原状，
`brandBluePaints` 从 enforce 断言里移出、继续作为登记的债打印，测试里换成"这条仍在测量、且非零"的断言，
并把平台差异写进注释（`:not(:disabled)` 那条修复保留——它抓回的是另一个已被量掉的缺陷，两平台一致）。

**现在包里这句话的真实状态**：`单一低饱和强调色 #356B92` 在珍珠白下**未满足**，实测 21 处 brand 深蓝仍在
（本地与 CI 同一次扫描的 `brandBluePaints` 读数一致）；要满足它需要一次配色裁定，两个方向都有代价——
同一 hue 的深阶当填充（保持单一色相，但要重测白字），或者按钮文字改深色并放弃"强调色当填充"。
这与 `品牌蓝压不住白字` 那条既有项目问题是同一类：不是新缺陷，是同一个约束在第三套配色上重新出现。

**流程上的账（本轮真正的收获）。** 三条 CI 红里，两条来自我本地只跑了 76 项聚合门禁、没跑单元套件与
权威链：`AUTHORITY_CHAIN=DRIFT`（账本加行后没重生成链）与 `--uif-font-micro` 抬到 12px 撞上 20261009 包
登记的 11——后者用这条尺自带的 `DOCUMENTED_DEVIATIONS` 正式登记，不删检查、不偷偷对齐。**闸门包不等于
测试套件**，这两条已经写进本轮收尾清单。

**账与边界。** 本轮只改样式与尺子的断言，`evidence` 仍 **290**、直方图 **`DONE 13`／`PARTIAL 2`／
`NOT_STARTED 1`** 不变；上一段那份 `kb-06-browser-single-accent-20261025` 回执**一字不动**（它记的是
它那次测量的事实，撤回发生在它之后，不能被改写），本段就是它的取代说明。`.app-nav button:hover` 仍读同一对
brand token 且不在尺子的静息态测量范围内，继续记为未测。owner 未裁的两件照旧：`DL-KB-13` 的 150 KB 上限，
与长屏顶栏是否吸顶。

### 5.53 「标题层级」与「标签位置」第一次有数：494 个带标签控件里 416 个标签在上方，层级不是单调阶梯。

**这一刀只做两件事：把尺子架对，把读数留下来。** 包里两句还没有对象——`09_DESIGN.md` 的
「标签放输入上方；错误紧邻字段」与「（标题）层级」。两者都是位置/阶梯类要求，可以在已渲染文档上量：
标签用 `caption 文本节点的 Range 联合框` 与控件盒子比较（在上方且水平重叠），标题读每个 painted
`h1..h6` 的 px/weight/line-height。

**尺子先错过一次，而且是会让人误信的那种。** 界面普遍写成 `<label>{显示标题 + 控件}</label>`——
label 是 wrapper。直接量 label 的盒子时，它的底边在控件之下，于是 247 个正确标注的字段里只有 7 个被判为
「标签在上方」，看起来像巨大的不合规；改成只量标签自己的文本节点之后是 208（单宽度那次 208/247）。
**"闸门报出一条大债"和"闸门的对象选错了"用同一个数字长得一模一样**，这条已写进注释。

**读数（stitch/light，widths 1440+1920 同一次扫描）**：带标签控件 **494**，标签在上方
**416**，其余 **78** 处逐条可点名，全部落在复选框／单选行与一个紧凑选择器上：
  `LABEL-SIDEBY 1440:tools label.project-picker vs select#创作工具-project.project-select dy=-8px`
  `LABEL-SIDEBY 1440:preflight label vs input#jury-approve dy=-17px`
  `LABEL-SIDEBY 1440:preflight label vs input#jury-reject dy=-17px`
  `LABEL-SIDEBY 1440:preflight label vs input#rights-decision-APPROVED dy=-17px`
包那句话针对的是「输入」，而勾选框把标签放在框旁是常规写法，所以本轮**只登记不断言**，
要不要把勾选类也纳入是同一次裁定里的一条。

**「错误紧邻字段」这条没测到，不能记成通过**：`errorNodes=0`——静息态与这轮打开的所有面板里
没有一条已渲染的错误／提示实例，因为错误只在真实失败时出现。要量它必须先让闸门制造一次真失败态
（保存失败、目标不兼容、模型不可用三种里有两种是可造的），这是下一刀的前置，不是本轮的绿灯。

**标题层级是量出来的未满足**：同一次扫描读到 10 个不同的
`(级别, 字号, 字重)` 组合 —— `h1 26px/700/lh0 | h2 21px/700/lh0 | h1 17px/700/lh19.6 | h2 32px/700/lh0 | h3 15px/700/lh0 | h3 13px/700/lh0 | h2 24px/700/lh0 | h3 16px/700/lh0 | h4 16px/700/lh0 | h4 14px/700/lh0`。其中 `h1` 同时是 26px 与 17px，`h3` 有 13/15/16px 而 `h4` 是
14/16px：**第三级比第四级更小**，层级不是单调阶梯。包里没写具体 px，参照文档给的是 42/27/19，
所以收敛成一套阶梯需要一次设计裁定（照参照文档、还是把现有三套界面族各自归一），本轮不替包猜；
另外打印里 `lh0` 表示计算值是 `normal`（我的格式化把 normal 转成 0，读数没错但表达有歧义，下一轮改）。

**本轮加的两条断言是覆盖断言，不是合格断言**：`labelled>=200`、`headingLadder>=5`。
它们防的是"选择器坏掉 → 0 违规 → 被读成通过"这一类假绿，而不是宣称界面已合规。
账：`evidence` 仍 290，直方图不变，本轮只改尺子与测试，未动样式；卷宗与本节的数字全部取自
`workbench-contrast-gate-stitch-light.log` 的同一次扫描。

### 5.54 一条只在远端出现的 AA：同一个控件被点名三次，我的三次处理各改变一次读数。

**事实，按时间排。** ① `1.37:1`（stitch/light，1920，`fg=rgb(180,190,199)`）与 `3.59:1`（ui2026/light）
→ 我判断是 `.seg button:disabled{opacity:.45}` 把字与控件一起压淡，撤掉 opacity（`ffb26abc`）。
② 同一条元素变成 `2.11:1`（stitch，`fg=rgb(203,210,216)`）→ 我把禁用态墨色从 `--muted` 改取 `--text`（`8e17aa85`）。
③ 再变成 `1.06:1`（stitch，`fg=rgb(157,161,165)`）与 `2.6:1`（ui2026，`fg=rgb(209,213,217)`）→ 我用 id 级声明
分别钉住两种状态的底与字（`b5b59927`）。**每一次我改什么，远端读数就跟着变**——所以这条不是幻觉、也不是
阈值问题：那个 CTA 的字色确实被某条我还没定位到的规则接管，而它的底随状态在 brand 渐变与平涂次级底之间切换。

**为什么本地看不见。** 本地这条尺跑不出该态：`target-profiles+combination` 面板在本地扫描里停在"已校验"，
远端停在"目标已切换、待重校验"（`validate.textContent` 的两分支里后一条），也就是这个 pairing 只在远端那条
数据路径上出现。**我没有把它压绿**：没有改阈值、没有放宽断言、没有跳过该面；相反，我把这一轮新加的
`ROWCOUNT`/产品行独立返回用上了，所以现在每条红都点名到元素与比值。

**这条债现在的真实状态**：远端仍红，`Workbench browser E2E` 一个作业失败（Python 单元套件与权威链两条绿）。
下一刀的正确顺序已经清楚，不需要再猜色：① 让这条尺在本地也进入"待重校验"态（选目标→改目标→等 stale 文案出现，
再量），② 在真实 DOM 上打印该按钮的 `getComputedStyle().color` 与胜出规则，③ 按胜出者改那一条规则，
而不是再在外面叠一层声明。**在未定位之前，珍珠白与 20261009 两套主题的 AA 声明只对已扫到的状态成立**，
这一句必须与它们各自的回执一起读。

**账。** `evidence` 仍 290，直方图不变；本节只记录事实与下一步，不新增通过声明。owner 未裁项不变：
150 KB 上限、顶栏吸顶、标题阶梯、勾选框标签是否纳入「标签在上方」。

### 5.55 那条只在远端出现的 AA 定位了：闸门量到的是补间的中间帧，不是任何规则里写过的颜色。

**先更正前提。** 交接写"分支尖端红"，我读 CI 实况时尖端已经绿了：PR run `40170639181`（head_sha
`13df2a9e`）`Workbench browser E2E` 通过，`BROWSER_E2E ran=15 skipped=0 failed=0`，其中
`test_workbench_contrast_gate ran=5 failed=0`；红的是更早的 `40168878523`（head_sha `b5b59927`，
作业 `121095476953`）。**所以本轮不是把一条红拧成绿**：同一条代码路径红过两次、绿过一次，
差别只在采样时刻落不落在那 200ms 里。绿的一次没有修掉任何东西，下一轮照样可能再红——本轮删的是那 200ms。

**根因是量出来的。** 四类动作按钮的共享规则写 `transition:.2s ease`，简写不带属性表就等于
`transition-property:all`，于是启用↔禁用切换时 `color` 与 `background-color` 一起补间。rAF 逐帧
采样器（1920 / stitch-light，一帧一行）读到墨色
`rgb(23,33,43) → 118,124,130 → 187,190,193 → 226,227,228 → 251,251,252 → 255,255,255`，
同一时刻背景色从实白褪到 `rgba(255,255,255,0)` 压在 brand 渐变上；把 `rgb(187,190,193)` 与
`rgba(255,255,255,.294)` 覆盖的 `rgb(29,79,196)` 按闸门自己的合成算法算出来是 **1.97:1**。

**两次远端读数与插值逐通道吻合。** 按通道反解线性插值参数：stitch/light 的 `rgb(157,161,165)` 对
`#fff ↔ #17212b` 解出 `t = 0.422 / 0.423 / 0.425`，ui2026/light 的 `rgb(209,213,217)` 对
`#fff ↔ #152b3d` 解出 `t = 0.197 / 0.198 / 0.196`（残差是 8-bit 取整）。同时枚举
`document.styleSheets`，匹配该元素的 `color` 声明只有三条，全部写白字。**那条红量的不是任何规则
里的颜色。** §5.54 问"为什么我改什么远端读数就跟着变"也一并有了答案：那三次改的（撤 opacity、
`--muted`→`--text`、id 级钉色）都是这条补间的端点，端点一动中间帧跟着动。

**改的只有"补间哪些属性"。** `transition` 限定为 `transform, border-color, box-shadow`，时长与缓动
一字节未动，两个端点值仍是 §5.54 之后那一套。没改阈值、没放宽断言、没跳过该面、没关 enforce、
没猜新色值。motion 尺抓不到这一类：`color`／`background` 不是布局属性，它只打印
`transitionAllCount` 并拒绝定罪——所以这是对比度尺的责任，也由它先咬到。

**第二件事：本应走到该态的循环是空转的。** 旧 `openStaleValidationState` 要求每个下拉至少三个
`<option>`；组合解析成功之后 `tp-agent` 只剩空选项，`tp-entry`／`tp-model`／`tp-task-mode` 各只剩
一个可用值，五个轴一条都不满足，所以"换目标"从未发生，本地 `STALEROW` 才一直打印洁净文案——
交接里"本地不可复现"是真的，但不是状态不可达，是闸门根本没去换。判据现在改成页面自己写的
「唯一对应档案 <key>」：实测 `flux2--api--image-generation → elevenlabs--web-app--music` 且
`dataset.mode` 仍为 `target`，脏文案「按新目标重新校验」升级为必须出现的断言，走不到就进
`controlBad` 让闸门 exit 1（进不去是红，不是跳过）。

**修复后的实测。** 三套配色双宽度：default `checked=8129`、stitch/light `16258`、ui2026/light `16258`，
三者 `belowAA=0 controlMisses=0 unparsable=0`；三处 `STALEROW` 一致
`color=rgb(255,255,255)`、`transition-property=transform, border-color, box-shadow`，
`STALEOWNER` 三条规则全白。还原成不带属性表的简写做反证：静态守卫点名 `all` 变红，同一态下采样器
重新量到 **7 个**不同墨色，修复后只剩 **1 个**——两枚日志逐字节存在
`design-lab/evidence/current-execution/task-artifacts/kb-20261025/kb-06-action-button-ink-ramp-{before,after}-fix-20261025.log`。
`python -m unittest test_workbench_contrast_gate` 6 条 `261.082s OK`。

**包里仍未满足的五句，只登记不交付。**
① 「单一低饱和强调色 #356B92」：`brandBluePaints` 本轮 stitch/light 双宽度 **44 处**（§5.52 的 21 处
是单宽度读数，两个数字不可互换），仍等 owner 二选一。
② 标题层级：仍是 10 个 `(级别,字号,字重)` 组合，`h1` 同时 26px 与 17px、`h3` 可小于 `h4`，收敛成一套
阶梯要一次裁定（包参照文档 42/27/19px），本轮不替包编 px。
③ 「错误紧邻字段」：`errorNodes=0` 是因为闸门还没制造任何一次真实失败态——这一句既不能记为满足，
也不能记为"已测量"。下一刀的前置是先造一次真失败（保存失败／目标不兼容／模型不可用）。
④ 勾选框／单选行的标签位置：带标签控件从 §5.53 的 494 增至 **532**、在上方从 416 增至 **434**、
旁置从 78 增至 **98**。增量已核到行，不是猜测：新量的 `combination-after-change` 在 1440 与 1920 上
各读到 `labelled=19 / labelAbove=9 / 旁置=10`，两处合计 +38 / +18 / +20。另注：打印的
`LABEL-SIDEBY` 样例上限是 10 条，98 这个数来自 `labelled − labelAbove`，不是数样例。
⑤ hover 态仍不在静息尺的测量对象内（`.app-nav button:hover` 读同一对 brand token），未测即不称合规。

**账。** `evidence` 290 → **291**（新行 `kb-06-browser-remote-only-aa-root-cause-20261025`，
`subject_sha=7f7a2946`，回执 18216 字节、`sha256=ba200ec0…`，append 前已证明 JSON 往返逐字节相同）；
`currentExecution` 50 项直方图不变（34 `FROZEN_DEFERRED` / 13 `DONE` / 2 `PARTIAL` / 1 `NOT_STARTED`），
`DL-KB-06` 状态未动，旧 34 项一项未解冻。owner 未裁项不变：150 KB 上限、顶栏吸顶、标题阶梯、
勾选框标签是否纳入「标签在上方」、hover 墨色跟不跟着翻。

### 5.56 「吸收未落地」按职责判定：落地六件、删 25 个死 token、把普查闸的人口补全

**判据被 owner 纠正过一次，纠正本身改变了结论。** 我起初用「有没有引用」判有用没用，被指出
**「有用没用的判定不是有没有引用，是对项目还有没有用」**。改成按职责判：去掉它，项目能证明的
或能对外的承诺会不会变少。变少就是有用，哪怕零引用；既不证明也不承诺、且已有别的主人，才谈得上删。
这条纠正不是修辞——按旧判据我会删掉 `model_radar.resolve()`，而它是 AGENTS.md 那句「零 checksum、
许可冲突、模型不存在或硬件不足时 runtime resolver 必须 fail closed」的唯一承担者。

**落地六件，每件都有改前/改后实测。**
① `GET /api/projects/<32hex>` 未知 id 改前实测 `http.client.RemoteDisconnected`——连接无响应被关闭，
在 `fetch` 眼里与"服务挂了"同形。原 handler 只有 `if project is not None` 一条分支。现在 404
`PROJECT_NOT_FOUND`，与 7 个兄弟模块同词；两种 404 分开钉（畸形 id 由路由模式拒、合法但不存在由
handler 拒），因为把它们混成一条期望会让"对一切返回 404 的 handler"也过关。
② `drain_body` 注释承诺"任何失败在这里都被忽略"，代码里没有 `try`；读超时在 `except` 处理器内再次
抛出，逃出到 `handle_one_request`——恰好重现这个 helper 存在的目的就是要消除的 10053。
③ `MAX_QUERY = 200` 声明在模块作用域、没有任何代码读它，所以界只存在于源码文本里：调用方可以把
一份文档当查询粘进来，而本方法会为它在每个字段的每个已存修订上做 contains 扫描。现真拒绝
`KNOWLEDGE_QUERY_TOO_LONG`，且恰好 200 字符合法——界不是墙。
④ `KNOWLEDGE_OFFSET_INVALID` 与 `KNOWLEDGE_LIMIT_INVALID` 被这个路由自己的合同行承诺，**全仓零测试**。
承诺了却没被测的拒绝码不是合同。三条一起钉住，各按触发值类（负数／非整／bool／超上限）。
⑤ `test_workbench_preflight_handoff_e2e` 存在、本地 2.039s 通过，却既不在 no-skip 注册表也不被任何
workflow 步骤点名：**CI 从没执行过这把浏览器尺**，而该注册表的注释写的正是"未登记的浏览器套件会
永远静默 skip 而没有 finding"。登记前先把它自带的 `_browser()`——只 glob `$HOME/AppData/Local/ms-playwright`
的 `chrome-win*/chrome.exe`，Linux 上返回 None——换成其余七把尺共用的跨平台发现函数；登记之所以安全，
是因为注册表自己会 `setdefault('E2E_NODE_MODULES', apps/workbench)`。复跑 `BROWSER_E2E ran=17 skipped=0 failed=0`。
⑥ `test:unit` 直跑已提交的 `build/main.js`，所以改完 `shell.ts` 在本地跑测试，绿的是改前字节。现在
脚本内先 `vite build`（pnpm 在本仓不跑 pre/post 钩子，写成 `pretest:unit` 等于没写）。重建后 bundle
**零漂移**，node 三套测试全过。
⑦ 另两处"说了没做"：`verify_fresh_clone.py` 刚问完 `shutil.which('uv')` 并把结果印在同一行，下一句
就无条件写 `uv is absent`；聚合链用 `sys.executable` 派生子进程，所以同一提交在 `.venv` 下 `failed=0`、
在裸解释器下 `failed=29`——29 条凭空捏造的产品回归。后者现在拒绝并点名解释器与不可导入的声明依赖，
需要哪些依赖仍从 `pyproject.toml` 读，不在这里重复一份。

**删与迁：先补机制，再删东西。** 清扫出 **25 个**无任何 `var()` 读、也无产品源码／闸门／测试／schema／
包内按名断言的自定义属性（`--blur --bp-{desktop,tablet,mobile} --density-* --error --info --font-*
--motion-emphasis --radius-{sm,xl} --space-* --color-info`），27 行声明、593 字节，
`style.css` 121,964 → 121,371。它们残余的出现处只有两处：它来源的 B07 参考语料，和一份**记录它们
没被用**的债清单——把这两类当消费者，是我只删到 14 个的原因。
真正防复发的是把普查闸的**人口**补全：既有 CONSUMPTION 检查只看包点名的 `--uif-*` 字段，所以整族死
声明一直在它视野外——**覆盖率闸永远只证明它自己携带的那张表**。新规则枚举全部声明属性，例外交给已有
的 `SPEC_PROVENANCE` 判定，不手抄 allowlist（那等于给同一事实配第二个主人）。
无界列表路由同样从"打印一个数"升级成"钉一张登记面"：18 条带列表的 GET 路由里 **9 条无界**，逐条写
理由与代价；新增第十条即红，**绑好了却不摘牌也即红**（静默修好的洞，下一个人会原样继承）。

**分页不是附件那条的修法，这条要写清楚以免被当成偷懒。** 实测 200 张 47,160 B 附件时服务端 199.59 ms，
其中 **59.0% 是逐行 `checked_path`+`stat`、30.5% 是两次图像解码、只有 2.4% 是哈希**。成本来自每行重校验，
不来自行数；而 `width/height/media_type` 没有落库，真正的修法是在写入时物化它们——那是带迁移、precheck
与合同行的 state-schema 改动。用切片把列表截断看着像进步，毫秒数一毫秒不会少，还会让"附件多于 N 张"
在界面上不可见。

**保留但零引用、删了就丢承诺的，点名记账。** `model_radar.resolve()/radar_report()`（fail-closed 承诺的
承担者；零生产消费者只说明本机没有加载模型的 runtime，而模型部署是冻结项）；`workflow_provider` /
`remote_provider` / `audio_provider` / `comfy_*` / `packages/capabilities/reconstruction/*`（对外版本化公共
合同面，且被 verify 链守着）；`vendor/` 39 件 manifest 与 `docs/history/**`（AGENTS.md 定为惰性资料，
职责是出处与对标基线）；8 个未被 UI 读的 `--uif-*`（由 `SPEC_PROVENANCE` 承担包值出处职责）。
**该并但本轮没并**：五份手写 CSS 花括号扫描器——功能重复，但每份的豁免清单与断言面不同，合并必须逐个
证明输出集不丢，不是改名就能并。

**我自己的仪器错误四条，如实入账。** ① 清扫第一遍把文档/证据里的名字当消费者，只删 14 个；
② 普查闸初版复用 `declarations()`（正则只匹配 `--uif-*`），对任何其它名字恒返回空 = **恒真即假断言**，
植一个 `--space-dead-99` 当场暴露；③ 404 测试连错两次 id 形状（64 位十六进制、`p-` 前缀都不匹配
`([0-9a-f]{32})`），差点把"兄弟模块用词不一致"当成结论；④ 登记预检套件时锚点行没重出，等于把
`test_workbench_motion_gate` 从元组里删掉，靠 `git diff` 只显示「+1 条、0 删除」才发现，并用 AST 复核
元组=8 项、前 7 项俱在。另外：删掉 `--info` 会让它作为唯一读者的身份消失，`--color-info` 随之成孤儿，
所以清扫必须**迭代到不动点**（第 2、3 遍各 0 删除）；而我为"理由必须实质"写的 40 字规则，逮到了我自己
写的填充条目 `_list_research`（31 字）——规则能咬到作者，说明它不是装饰。

**账。** `evidence` 291 → **292**（新行 `kb-13-loop-closure-and-css-token-register-20261025`，
`subject_sha=b8ac53dc`，回执 8,593 字节、`sha256=d7f863ac…`，append 前已证明 JSON 往返逐字节相同）；
`currentExecution` 50 项直方图不变（34 `FROZEN_DEFERRED` / 13 `DONE` / 2 `PARTIAL` / 1 `NOT_STARTED`）。
**`DL-KB-13` 仍 `PARTIAL`，且两处都不是工程缺口**：150 KB 上限要 owner 裁定，无指导真人任务要真人。
复测：聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`（清扫后与登记后各一次）；CSS 清扫后对比度复跑
`checked=16258 belowAA=0 controlMisses=0 unparsable=0`；单元 44+110+21+19+21+9 OK，
`TEST_SELF_SUFFICIENCY=OK modules=259 violations=0`；`KNOWLEDGE_SEARCH_P95_MS=34.7 budget=300`。
owner 未裁项不变：150 KB 上限、顶栏吸顶、标题阶梯、勾选框标签、hover 墨色，新增一件：
`_list_prompt_results` 是否套用仓内已有的 `PAGE_LIMIT=100` 信封（它是最接近能直接落地的一条）。

### 5.57 CI 抓到我自己造的一次红：一把尺的依赖面不能大于它所在作业的装机面

**红在远端，本地全绿。** 推送 `1d86e877` 后 `Workbench strict-TS product gate` 失败，步骤是
`python3 scripts/measure_workbench_weight.py --check`，逐字读数
`MEASURE_SOURCE_MOVED cannot import the route table: ModuleNotFoundError: No module named 'PIL'`
（run `40187301910`，job `121150712090`，head `1d86e877`）。**造成者是我本轮加的 DL-KB-13 读数**：它为了拿
`ROUTES` 去 `from design_lab.http_service import ROUTES`，而这条 import 链到达 `image_assets`、需要 Pillow——
strict-TS 是 **node 作业，不装任何 Python 第三方包**（workflow 里那个 job 只有 setup-node/pnpm 步骤）。
本机 `.venv` 有 Pillow，所以同一条命令本地绿、远端红。这与今天早些时候那条"只在远端出现的 AA"是同一类
错误：**测量工具的依赖面大于它所在环境的装机面**，于是它的"绿"只代表"我这台机器"。

**修法不是给 CI 加安装，也不是动 workflow。** 本脚本早就带着一套 AST 静态读取机器（`parse` /
`module_tables`，用来解常量与页大小），拿路由表本来就该走它——改回复用之后，`--check` 回到纯标准库。
同时拆开一个字段干两件事的错误通道：`readerError` 只代表"读不到路由表"（致命）；新增 `callSiteError`
代表"规范匹配器不可用"（它确实需要产品依赖），**如实报缺失、绝不当成 0**。此前 `frontend_calls=0`
会被这把尺自己当成致命错，那等于把"这列没测"报成"路由表形状变了"——一次假红与一次假绿之间只隔着
一个字段名。

**兼容性靠契约而不是猜。** 解析出的路由对象要交给规范匹配器 `verify_workbench_route_calls.route_matches`，
它会调 `route.accepts(match)`，所以轻量对象必须实现它。带 `when=` 的路由无法从源码文本求值，答 `True`
就是静默过匹配——现抛 `ValueError`，而调用方本来就 `except ValueError` 记成 "dynamic call shape"。
实测全表只有一条路由带 `when=`（`_task_detail_or_events`），且它不是列表路由。

**三把防复发的闸。** ① 结构闸：函数体之外不得模块级 import 任何非标准库模块——这把"我本地能跑"和
"这个作业能跑"绑成同一件事；② 客户端列若因缺依赖不可用，测试必须失败并点名，不许把 0 读成"页面没要东西"；
③ `when=` 路由必须拒绝求值。

**用 CI 的真实条件复验，而不是用我自己的 venv 复验。** 无 Pillow 的裸解释器：
`LISTROWS list_routes=18 bounded=9 without_limit=9 frontend_call_sites_scanned=0`、NOTE 点名缺失的匹配器、
`WORKBENCH_WEIGHT_GATE=OK remote=0 bundle_gzip=160052`、**exit 0**；venv 下同样三个核心数，另加
`frontend_call_sites_scanned=142`。两套读数核心一致，缺的那列被明确标注为"缺失而非零"。
`tests.test_workbench_weight` 22 条 OK；聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`。

**账。** 代码提交 `31862800`；`evidence` 292 → **293**（新行 `kb-13-gate-toolchain-coupling-20261025`，
轴 `browser`，`subject_sha=31862800`，回执 2,757 字节、`sha256=f2a5f254…`；append 前再次证明 JSON 往返
逐字节相同，哈希从写入字节读回）。`currentExecution` 50 项直方图不变
（34 `FROZEN_DEFERRED` / 13 `DONE` / 2 `PARTIAL` / 1 `NOT_STARTED`），`DL-KB-13` 仍 PARTIAL。
**远端是否转绿以推送后 exact-SHA 的作业为准，不以本地 exit 0 代替。**

### 5.58 第二次远端红：账本绑定纪律真抓到了一次"记录变老"，而它该被抓

**红在哪。** 再次推送 `d8962779` 后 `Python gate` 分片 1/3 报一条 FAIL：
`test_evidence_artifact_presence...test_tracked_artefacts_of_the_real_ledger_all_read_back`，
`outcomes={'FAIL': 1, 'PASS': 1018, 'SKIP': 14}`。同一矩阵里
**`Workbench browser E2E` 绿**——说明上一轮两个修复（`--check` 回到纯标准库、预检浏览器套件登记）在 Linux 上成立。

**为什么这不是产品回归。** 本轮给 `test_design_layer_http.py` 加了 404 测试，而**冻结记录
`r5-workbench-http-native-ui-reobserved-20261006` 把那个模块当自己的工件哈希**——那条 2026-10-06 的观察
现在描述的是比它命名文件更旧的字节。这把闸钉的是"漂移清单双向精确"，所以新增一对必须被当成 finding。

**处置顺序决定诚实与否。** 先把活清单从闸自身重算、与钉住的集合**双向 diff**，再动文件：
钉 30 对 / 64，活 31 对 / 65，唯一差异就是这一对；**无计数位移、无消失、broken=0**。
然后按本文件既有惯例把这一对带日期理由加进期望集合，总数 pin 64→65 写进变更日志
（沿用 59→60、60→64 的记法），**旧记录一字不改**——它仍是它当时的观察。
不诚实的做法是两种：把那条从账本里删掉，或取消精确性检查。

**一个自指情形要点明。** 编辑这个测试模块本身，本应让它自己绑定的记录也变老；实测改完后
钉 65 == 活 65，`new/count_moves/vanished` 全空——因为绑定 `test_evidence_artifact_presence.py`
的记录**早已在清单里**（2026-10-19 那条注释讲的正是这种"闸门模块让自己的绑定记录变老"的情形）。
这不是巧合，是那次把自老化写进名单换来的可预测性。

**账。** 代码 `9d4a17ca`；`evidence` 293 → **294**（`kb-13-drift-inventory-repin-20261025`，轴 `unit`，
`subject_sha=9d4a17ca`，回执 2,577 字节、`sha256=8bc5e031…`）；直方图不变
（34/13/2/1），`DL-KB-13` 仍 PARTIAL。远端仍以再次推送后的 exact-SHA 作业为准。

### 5.59 品牌件流水线有、消费者没有：把 owner 的矢量标接上界面，并顺手结清一笔欠账

**owner 的要求是一句话：把项目 LOGO 换上去（名称 DESIGN），来源 `D:/All projects/矢量LOGO`。**
查下来的真实缺口不是"图不对"，而是**这条流水线没有消费者**：`design-lab-mark.png` 只被它自己的生成脚本
和二进制清单引用；AppShell 导航头是纯文字 `DESIGN-LAB`；CSS 里给了 48px 的 `.brand-mark`，但它挂在
`shell.ts:9606` 那段**被注释掉的旧版侧栏**里，实测 `rect` 是 0×0；唯一真在画的槽位是旧版页头那枚 52px
`.mark`。所以"换 logo"必须同时做四件事：素材入库、导航槽位挂上、浅色主题翻墨色、**以及把守着位图
管线的闸门一起改**——最后这件最容易漏，漏了就留下一把永远校验废弃资产的死闸。

**切带不能手解路径，两次失败都在这。** ① 正则抓 `d="..."` 把 17 条抓成 **18** 条（多一条空路径），
于是"单标"只剩那条空的；② 按坐标奇偶配对 x/y 在 Illustrator 混合绝对/相对命令、每条命令参数个数不同
的前提下毫无意义，第一版因此产出 `viewBox` 4×4 的**不可见图形**——而数字看起来完全正常。改成让
Chromium 解析源文件、逐条读 `getBBox()`：17 条非退化路径，在 **20.97px** 的垂直间隙处切开 → 单标 2 条
（D + 星芒，框 `76.41,26.96 → 232.63,178.93`，160.22×155.97）、文字带 15 条。第三个错是 `viewBox`
平移符号写反（把 `(left,top)` 移到原点的 min-x 应是 `left-pad`，我写成 `-left+pad`，内容被推到视口外）
——**同样是靠渲染暴露的，不是靠读数字**。

**接法与两处如实的未验证。** 导航头在文字左侧加 22px 单标，文字仍是可访问名、图形 `aria-hidden`。
`--brand-mark` 改成同一矢量的两枚编码（`paper #EEF2F5` 给炭黑默认，`ink #17212B` 给 `ui2026/light`
与 `stitch/light`），因为 `background-image` 不吃 `currentColor`，而 CSP 是 `img-src data:` 且
`workbench.py` 只服务固定三条路径——开资源路由要同时放宽两者，那是 owner 的安全决定，不是便利。
未验证的两件写清楚：应用自身的**主题控制器会在启动后重写 `data-palette`**（探针注入的值被改回
`design-lab`），且落地视图上**没找到可点的主题控件**（`clicked=null`）。所以"浅色翻转渲染正确"已证
（强制属性后 nav 底 `rgb(255,255,255)`、字色 `rgb(53,107,146)`、深墨标压白底），
"**用户从当前视图一步切到珍珠白**"未证——那是 STITCH 施工单里主题入口的活，不由本条冒充完成。

**闸门跟着素材走，并且它先冤枉了一次好人。** `render_brand_asset.py --check` 改为校验矢量真值
（digest、两枚 fill、路径条数、默认变体、两个浅色是否都 opt-in）。它第一次运行报
`only 1 light palette(s) opt into the ink glyph`——读回 CSS 才发现是**检查器多减了 1**，样式表是对的。
修检查器，不修被它冤枉的 CSS。

**又一次"我改的东西让别的记录变旧"。** `verify_projection_freshness` 抓到：新规则带来 4 个字面 px
（`22/22/8/-4`），于是 `DESIGN.md` §4 那句债读数 517 → **521** 必须跟着改；字面色值那一栏工具明写
「an agent must not fill this field」，未动。

**结清一笔欠账。** 上一轮我说 `bdaf4883` 的全绿先不单独写档、并入这一轮，这就是结清：
run `40191207017`（head `bdaf4883`）`conclusion=success`，逐字
`BROWSER_E2E ran=17 skipped=0 failed=0`（含 `test_workbench_contrast_gate ran=6` 与
`test_workbench_preflight_handoff_e2e ran=1`）、三分片 `exit=0` 且 `FAIL` 为 0、
`PYTHON_TESTS_UNION=OK expected=3352 distinct=3352 ran=3352 duplicates=0 missing=0 unexpected=0`；
`Workbench strict-TS product gate` 与 `Python gate` 均 success——前两轮那两条红（PIL 依赖、漂移清单）
都确认消失。

**账。** 代码 `e297f967`；`evidence` 294 → **295**（`kb-06-brand-mark-on-interface-20261025`，
轴 `implementation`，`subject_sha=e297f967`，回执 6,001 字节、`sha256=86f58f50…`）；
`LOGO.ai` 只按哈希登记不入库（仓库已过体积警戒线，且从 `.ai` 导出需驱动 Illustrator＝冻结项）；
`DESIGN.md` 债句更新；聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`；node 三套与 42 条 CSS 相关
python 全过；`LICENSE_COVERAGE=OK`、`BRAND_ASSET=OK paths=2 encodings=2 light_flips=2`。
`currentExecution` 直方图不变（34/13/2/1）。

### 5.60 包内那句动效第一次成了尺子：全站 20 条补间量出 16 条越界，动效层则默认关着。

**这一段做两件事，方向相反。** 一是**收**：把 `apps/workbench/style.css` 里每一条补间都放进包自己写的那条带；
二是**放**：按 owner 的新裁定叠一层增强动效，但它默认不生效。新裁定逐字是：
「界面去找动效交互 STITCH 更多是静态页面 一比一复刻完成后 找牛逼的组件库 加入更多动画动效粒子等UI组件库」。
归属先说清：这条**新增**一个动效层，**不放松任何既有边界**——包内静态面的规则
（`docs/taskpacks/20261023-ui-kb/source/09_DESIGN.md:5`「动效强度约 1/10」、`:21`
「仅必要的120–180ms opacity/transform 过渡；减少动态效果时移除」）对静态复刻面继续成立，
动效层是叠加的、默认关闭的。

**先量，再改（2026-10-25 本机实测）。** `apps/workbench/style.css` 共 **20** 条 `transition` 声明、
**16 条越界**。越界构成：**10 条没有属性表**（简写不带属性表就等于 `transition-property:all`）；
被补间的非允许属性有 `background`、`border-color`、`box-shadow`、`filter` 和 SVG 几何属性 `r`；
越时长读数是 220ms×4、200ms×2、280ms×2、550ms×1。带那三个数不是抄规范，是从样式表自身定义读出来的：
`--motion-fast=120ms`、`--motion-base=180ms`、`--motion-slow=280ms`——尺子解析 token 之后判数字，
不判字符串。

**为什么这条与 §5.55 同源。** `transition:all` 会连墨色一起补间；那次 CI-only 的 AA 红
（`1920:target-profiles+combination button#tp-validate.primary-btn 1.06:1(stitch)/2.6:1(ui2026)`）
量的就是一帧任何规则里都不存在的中间态灰。§5.55 只修了那四类动作按钮，本轮把这条缺陷类
**放到整个样式表范围内**关掉——只要还留着越界声明，下一次动端点颜色时就还可能再红一次。

**改的是补间属性表与时长，不是内容。** 14 条改为只补间 `transform`（其中 toast 是 `opacity,transform`，
drawer 保留 `visibility 0s linear` 作为无障碍树离场的离散伴侣），时长统一落到带内 token；
5 处颜色/几何补间被删除：`button` 的底色、`.stage-nav-btn` 的边框底色、`.version-ring-node` 的 `r`、
`.seg button` 的 `all`、`.graph-stage circle.node-dot` 的 `all`（后者保留 transform 180ms）。
drawer 由 .28s、`.review-inner` 由 .55s 收到 `--motion-base`（180ms）。这一刀的边界要说清：
包内「不能为了轻量化删除必要内容」那条**不受影响**——动的是补间哪些属性、补多久，不是删界面；
动效强度由 owner 的新裁定重新解释，它不再是砍内容的理由。

**三条例外是具名登记，不是跳过。** `.ui-motion-fast` / `.ui-motion-base` / `.ui-motion-slow`
（都是 `all`，其中 slow=280ms 越带）留在原子的理由是两条：① 它们是 B07 UIKIT 的对外导出件，
其 `0.28s` 被
`docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/evidence/W02-UTILITY-VERIFY.json`
钉住（原文读数 `"ui-motion-slow = 0.28s (--motion-slow)"`）；② 实测在本产品里**零消费者**——
`apps/workbench/build/main.js`、全部 8 个 `apps/workbench/*.ts` 源文件、`apps/workbench/index.html`
各自 grep `ui-motion` 均为 0 命中。所以改它们等于替 UIKIT 改合同，不在本产品的动效范围内。
登记是双向的：第四条越界声明会被判红，登记项若在 CSS 里消失也会被判红。

**新尺的位置，和它自己的反证。** `design-lab/tests/test_workbench_contrast_gate.py` 新增类
`MotionBandFollowsThePack`，3 个用例：带内断言 / 三枚植入缺陷 / `all` 与墨色属性全站禁用。
植入的三枚是 `background-color 400ms ease`、`.5s ease`（裸简写）、`transform 90ms ease`（低于带下界），
全部被同一把尺抓到，所以"零违规"不是空输入。它与既有 `SRC-T07-MOTION-COMPOSITED`
（`design-lab/tests/test_workbench_motion_gate.py` + `design-lab/tests/e2e/audit_workbench_motion.mjs`）
是两把不同的尺：那把只禁会重排的补间，并且**主动发布 `transitionAllCount` 而拒绝判红**，谁也不顶谁。

**增强动效层落地，而且是委托实现的。** 新增源文件 `apps/workbench/motion.ts`，由 `main.ts` 引入，
Vite 打进同一个 `build/main.js`——因此不新增任何被服务的路径，也不动 CSP 白名单。四个原语全部只写
`transform`（磁吸 ≤3px、双轴倾斜 ≤4deg、入场只位移**不用 opacity**、数字滚动最终逐字落回页面已发布的原值）。
一个 `pointermove` + 一个 `pointerleave` 的**委托**实现：shell 会重渲染路由视图，boot 时逐元素绑监听
会在下一次导航静默失效。默认 **static**：只有 URL `?motion=enhanced` 才启用，且
`prefers-reduced-motion: reduce` 一律退回 static（与 `style.css` 里那条 `transition:none!important` 同向）。
粒子层本轮**未引入**，等库调研结论。

**构建与读数。** `vite build` 成功，`build/main.js` **610,364 → 615,430 字节**；同一 gzip 档（level 9）
**160,246 → 161,916 字节**（+1,670）。vite 自己打印的是 **164.50 kB**——那是另一个刻度（kB=1000 且它
用的压缩设置不同），本段的每一个 delta 都用 level 9 同档前后对照，不混用。`tsc --noEmit` 干净；三个
node 侧套件 `tests/unit.mjs`（含"bundle 在 vm 下可执行、零顶层 import/export"）、`tests/appshell.mjs`、
`tests/shape-notice-coverage.mjs`（61 个 seam 读数）全绿；聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`。

**`animation:` 是这轮第二把新尺，因为它原本是盲区。** 收完补间之后复查发现：`style.css` 还有 **4 条
`animation` 声明，全部 `infinite`**，而两把动效尺都只看 `transition:`——`SRC-T07-MOTION-COMPOSITED` 看
CSSOM 里的布局属性，新带尺看补间属性表，**谁都不读 `animation` 的时长与循环次数**。按"能不能画出来"分
（选择器的每个 class 都要在 bundle 里作为整词出现才算有消费者；只用子串会把散文里的
"DESIGN-LAB design **core**" 当成 `.core` 的消费者，第一版就是这么误判的）：
**live=1** —— `.ambient` 的 `floatGlow 12s infinite`，而 `.ambient` 是每条路由都挂的（shell.ts 里
`el('div', {class: 'ambient'})`），也就是说包里「无持续循环、自动播放和浮动装饰」在默认界面上一直被违反，
只是没有任何尺能看见；现在它只在 `:root[data-motion="enhanced"]` 下运行。
**dead=3** —— `dashMove`（`.flow-svg path`）、`pulse`（`.graph-stage .core`）、`scanSweep`
（`.scan-line::after`）：宿主选择器在产品里零消费者，所以它们是死 CSS 而不是违规，登记在
`DEAD_LOOPS` 里双向钉住——某天真被挂载，它就从"死"变成"live 无限循环"，必须作用域化或具名登记。

**渲染证据（不是构建绿代替验收）。** 真服务 + 真 Chromium，`#/assistant`，1440×900，两面对照：
默认面 `html[data-motion]=null`、`.ambient` computed `animation-name: none`、`animation-iteration-count: 1`；
`?motion=enhanced` 面 `data-motion=enhanced`、`animation-name: floatGlow`、`iteration-count: infinite`。
指针探针落在可见控件「设计辅助」上（`page.$` 第一次抓到的是折叠面板里的零尺寸元素，指针落不到东西上，
所以按 rect 挑了一个真的）：静止 `transform: none`；默认面 hover 得到 `matrix(1,0,0,1,2.99,0)`——那是
既有的 CSS `translateX(3px)` hover 规则，不是 JS；增强面 hover 得到 `matrix(1,0,0,1,0.96,0.82)`——那是
委托磁吸写出来的按指针位置的小数值。两面的墨色都是 `rgb(245,247,252)`，**hover 不改字色**。
该路由上磁吸宿主 **34** 个、倾斜宿主 **10** 个。截图在 `.project-local/task-runtime/motion-probe/shots/`
（gitignored 证据根）。**仍未取的**：真人视觉验收——测量与截图不等于 owner 说一句"像样"。

**一条自己造出来的新风险，写在交付的同一段里。** 增强面那个 12s 浮动是把 `blur(80px)`、`opacity:.45`
的光斑在文字底下移动，而列表卡片的底是半透明的（`color-mix(...surface2 74%...)`），所以光斑位置会改变
文字底下的合成背色——这正是 §5.55 那一族"任何规则里都不存在的一帧"。默认面已经干净（`animation-name:
none`），但**增强面的对比度至今没有量过**：要把 `?motion=enhanced` 灌进对比度闸门并做逐帧采样，才能把
这句从"风险"改成"已证"。在那之前，粒子/氛围层不得算 E2 交付。

**挂起项如实写。** ① 粒子/氛围层**未选型未接入**（两份调研回来了：GSAP 3.13 全插件免费但许可是
GreenSock License 非 MIT、gzip 27.2KB；canvas-confetti ISC 4.3KB；@tsparticles/slim MIT 30.5KB；
pixi.js 226KB 与 lottie-web 76.8KB 因体积/维护不引入；react-bits 与 magicui 是 React+Tailwind，
按 owner 既有的"参考它的结构源代码进行复制"裁法抄源码而不是装库）——本轮没有新增依赖，理由写在这里：
在 JS 单口径已经超包内 150KB 的情况下再加 30KB 级 gzip，等于用别的界面少东西来换这里的动效；
② `150KB` 上限的裁定仍在 owner 手上——`scripts/measure_workbench_weight.py` 自述不发明预算，实测
`budgetDeclared=False`，本轮 gzip +1,670 字节使 JS 单口径离那句 150KB 更远，关键路径合计 gzip
（bundle+stylesheet+document，level 9）实测 **206,956 字节 = 202.1 KiB**；行业那句是
「critical file size budget < 170Kb gzipped」且覆盖的是**整条关键路径**，包里 150KB 只管 JS、且没有写
设备/网络画像与目标指标。真人验收、模型推理、release、真实宿主 E3 全部仍冻结不变。

**这条断言会咬在哪里。** 它咬的是此后**任何人**在 `style.css` 里新写的一条 `transition`：简写不带属性表、
补间 `background`/`border-color`/`box-shadow`/`filter`/`r`、时长落在 120–180ms 带外，
三把用例里的任意一把都会在 `test_workbench_contrast_gate` 上直接红；UIKIT 那三枚被"登记项消失即红"咬住，
`motion.ts` 被默认 static 与 reduced-motion 退回咬住——谁把它改成默认开启、或让入场原语用上 `opacity`，
重蹈的就是 §5.55 那帧谁都没写过的中间态灰。
### 5.61 我把上一轮的"绿"报早了：换 logo 的那次改动在精确 SHA 的 PR 跑里是红的，红在两处同源的工具债

**先追正自己的一条断言。** §5.59 末尾我写了"run `40191207017`（head `bdaf4883`）`conclusion=success`"
来结上一轮欠的 CI 账。那个 SHA 是**换 logo 之前**的提交。真正的 logo 提交是 `e297f967`，它落进
`54931d74` 之后，`pull_request` 事件的那一趟跑的是 **两个作业红**：`Python gate`（分片 3/3，
`outcomes={'ERROR': 1, 'FAIL': 3, 'PASS': 1118, 'SKIP': 3}`，点名 4 条
`test_workbench_brand_asset.*`）与 `Workbench browser E2E`（逐字
`OV_BRAND_BROKEN 1440/1280/1536/1920: the mark decoded as no-data-uri, not 144x144`）。
拿前一个 SHA 的绿当后一个变更的结论，是断言错位，不是笔误——所以这一节先把它写死：**换 logo 那一轮
当时没有 CI 证据。**

**两条红的根因是同一次半途迁移。** 素材从 144×144 的 PNG 镂空件换成 owner 的矢量件之后，仍有三处
尺子按位图真值断言：`design-lab/tests/test_workbench_brand_asset.py`（4 个用例：找
`data:image/png;base64`、要 `naturalWidth×naturalHeight == 144x144`、要白字、要四边留白、要
`var(--glow)` 的光晕）、`design-lab/tests/e2e/audit_workbench_overflow.mjs` 的品牌探针，以及
`design-lab/tests/test_workbench_overflow_gate.py:315` 的 python 侧读者——**一条规则在两个 realm 各写
了一份**，所以一次红变成两个作业红。本地没抓到的原因很具体：那个测试模块**不在 76 门聚合的名单里**，
`VERIFY_DESIGN_LAB=OK` 从来不代表它跑过。

**修法是把断言指向现在真在画的东西，而且是更严不是更松。** 位图那三条职责（是图形不是矩形、只有一种
油墨、几何没被重新解释）由矢量这组承担：data URI 能在浏览器里解码成图、是 `<svg` 文档、`<path>` 条数
恰好 **2**（单标 = D + 星芒；第三条意味着切分图形色带与文字色带的那一刀动了）、两枚编码各自只带
**一种**品牌墨（默认 paper `#EEF2F5`，浅色翻 ink `#17212B`）且**除 fill 之外逐字节相同**、`viewBox`
与被跟踪文件相同、`--brand-mark` 默认必须是 paper、图形旁边的字标仍是文本 `DESIGN-LAB`、图形自身
`aria-hidden=true` 且不带文字、盒子是声明的 **22×22**（收起的轨道 0 尺寸合法，跳过）。

**顺手抓到两处"为错误的原因而红/绿"的断言形状**，这两条比表面更值得记：
① `render_brand_asset.py --check` 的素材路径是函数内硬编码的，测试 monkeypatch 的是模块常量
`PNG_PATH`——也就是说 `test_a_missing_asset_is_a_failure_not_a_pass` 测的**根本不是"素材缺失"**，
它把没人读的那个常量指向了不存在的文件，于是 `--check` 照旧读磁盘上的真件并 exit 0。现在
`MARK_PATH` 提成模块级可注入常量，`_check` 把检查器实际读的三个路径一起换。
② `test_a_stale_digest_claim_is_caught` 把**已退役的 PNG** 当被验对象喂进去——它也 exit 1，
但理由是"css 声称的摘要不是这个 png 的"，而不是它名字说的"摘要声明过期"。为错误原因通过的断言
比失败的断言更危险，因为它会一直绿到被验对象消失。
③ 该模块不再 `import numpy / PIL`：矢量真值不需要位图解码，顺手把它的依赖面缩回标准库
（§5.57 那条教训的反向应用——尺子的依赖面不能大于它所在作业的装机面）。

**本轮实测读数。** 改前：`test_workbench_brand_asset` 15 条里 **4 条红**（本机复现，与 CI 同形，
所以这次不需要等远端）。改后：**16 条 OK**（净增 1 条，即新增的"两枚编码除 fill 外相同"那把）。
`test_workbench_overflow_gate` 本机全量 **4 条 OK**，耗时 389.7s，四宽度（1440/1280/1536/1920）的品牌
读数是 `{'loads': True, 'svg': True, 'paths': 2, 'fills': ['#EEF2F5']}`，`uriChars` 与 22×22 盒同样过；
`ConnectionAbortedError WinError 10053` 是那条**已知的**服务侧读中断（`drain_body` 那一族，§5.56 已处理）
在 unittest 输出里的回显，不参与判定。聚合 `VERIFY_DESIGN_LAB=OK total=76 failed=0`。
`expected_tests` 不是钉住的常数（`run_python_tests_all.py:126` 从发现的 id 集合现算），所以本轮用例
净增一条不需要动任何计数钉。

**这条断言会咬在哪里。** 三个 realm 现在各自读同一种真值：若有人再把素材换形状（svg→png、或
`--brand-mark` 重新去吃 `currentColor`），node 探针与 python 读者会**同时**红，不再是一个绿一个红；
若有人把 `MARK_PATH` 再改回函数内硬编码，缺失件那条会立刻从"能红"退回"恒绿"，而这次有名字可以查。

**仍未结清的账（不写成已结）。** `54931d74` 那一趟 PR 跑的 3352 并集与 17 门浏览器清单，覆盖的是
**换 logo 之后、本轮修复之前**的字节；本轮 `14959a3d` 推上去之后要按精确 SHA 重读一次矩阵，
读到什么写什么，不拿本机绿代替云端绿。
### 5.62 精确 SHA 的矩阵终于全绿，而它顺手抓到一把尺在量空集：`errors=0` 不是通过，是没测到

**先把上一节欠的账结清，并且结在正确的对象上。** §5.61 承认了"拿 `bdaf4883` 的绿当换 logo
那轮的结论"是断言错位。本轮把品牌尺迁到矢量真值（`14959a3d`）与权威链重录（`f9683930`）推上去之后，
**run 40211581088（PR 跑，head 逐字 `f9683930a7189bacb2e5d0a0c42d8acb927b2806`）`conclusion=success`**，
10 个非 skipped 作业全绿；逐字读数：
`PYTHON_TESTS_UNION=OK expected=3363 distinct=3363 ran=3363 duplicates=0 missing=0 unexpected=0`，
三分片各自 `exit=0`（1/3 tests=1043 PASS 1029 SKIP 14；2/3 tests=1194 PASS 1186 SKIP 8；
3/3 tests=1126 PASS 1123 SKIP 3），`BROWSER_E2E ran=27 skipped=0 failed=0`。
并集从 3352 涨到 3363 是本轮新增动效尺用例的正常增量，`expected_tests` 由发现的 id 集合现算
（`scripts/run_python_tests_all.py:126`），没有计数钉要改。

**增强面的"自造风险"从"未量"变成已证。** §5.60 交付时写下：`?motion=enhanced` 的 12s 浮动光斑在
半透明卡片底下移动，等于改变文字下方的合成背色，属 §5.55 那一族，而**增强面对比度从未量过**。
本轮不是推理它安不安全，是把动画**冻在关键帧的每一档**再量：`floatGlow` 只有三个停靠点
（0%、100% 恒等，50% `translateY(20px) translateX(12px) scale(1.06)`），所以取 0/3000/6000/9000/12000ms
五个冻结姿态，用**同一个 `MEASURE` 谓词**、同一次渲染、同一批面逐档量。读数：
`CT_MOTION_PASS poses=5 routes=24 checked=34170 belowAA=0 distinctTransforms=4`——
4 个不同合成变换而不是 5 个，正因为 0% 与 100% 同点，这本身就是尺子在动而不是在原地重取样；
`checked=34170` 说明这一路真的扫到了文字 run，不是空输入。**没有为此调高任何阈值。**

**这一轮最值钱的一条：`errors=0` 是空集，而空集有两个不同的成因，先分清再修。**
包写的是「错误紧邻字段」（`docs/taskpacks/20261023-ui-kb/source/09_DESIGN.md:13`），闸门那段循环的
选择器是 `.error, [role=alert], .field-note, .refusal`。**归因先纠正一次**：我一度把这条写成
"选择器错了"，实测不成立——`#as-form-error` 就是 `p.error[role=alert]`（shell.ts:4708），
选择器本来就覆盖它，**真正缺的是"从来没有人让界面拒绝一次"**：闸门走过的每条路由读盘都成功，
拒绝行一直是空的，所以 0 描述的是"没造出状态"。同时**确实还有第二类拒绝被漏掉**：知识/评审/权利/研究
四条线的本地拒绝写进 **`p.view-hint`**（`#knowledge-outcome` 等，如
`未提交：标题为空。服务端未写入任何候选。`），既没有 `role=alert`（读屏也不播报，那是可及性缺口不是
测试缺口），也不在选择器里。两类各自修：
① 选择器覆盖 `view-hint`，但不是整族收进来（view-hint 也写普通说明），而是按**产品自己的拒绝前缀**判；
前缀从 `apps/workbench/shell.ts` 现数得到 6 个：`未提交`、`未签署`、`未记录`、`未选择方向版本`、
`未选择简报`、`未选择资产`，经 `CT_REFUSAL_WORDS` 传给闸门，**空列表时闸门直接拒绝开跑**——
因为"没给词"和"没有拒绝"这两种 0 必须能分开。② 新增 `openRefusalState` 去**真的点一次**：主刀是 `#/assistant` 的
`#as-submit`（清空 `#as-objective` 后提交 → `#as-form-error` 写
`请先写下要完成的设计目标…`），因为它落在闸门必走的默认路由上；第二刀是 `#/knowledge` 的
`#knowledge-create-submit`（清空标题 → `#knowledge-outcome` 写 `未提交：标题为空。…`），
专门覆盖 view-hint 那一族。两者都作为命名行 `+refusal` 进回执，并打印各自的 `role=`，
让"有 role 的那族"和"没有 role 的那族"在读数里就能分开。
新断言 `RefusalPopulationIsGraded` 三条：前缀数 ≥3 且三个已知词必须在；闸门源码必须含
`CT_REFUSAL_WORDS is empty` 的拒绝与 `.view-hint` 的选择；回执里必须有 `+refusal` 行且 `errors>=1`。
第三条在它该红的时候红过：先跑的那次用的是**改前留下的旧回执**，它逐字报
`AssertionError: [] is not true : the receipt has no knowledge+refusal row`——这把尺不是摆设。

**动效层按"有没有渲染"重扫一遍，抓到 `.soft-btn` 是零渲染样式。** 新增
`EnhancedMotionLayerStaysComposited.test_every_wired_surface_is_actually_rendered`：把三张宿主名单里
每个 class token 拿到**全部 `apps/workbench/*.ts` 与 `index.html`** 里找整词，找不到即红；
并允许"片段拼装的类名"（形如 `class: <code>-btn`）作为有渲染者的旁证，以免把拼接的类当成死类——
这条自我约束是因为**差点错判**：`.seg button`、`.review-card`、`[data-motion="count"]` 第一次都只
在 bundle 里出现 1 次，而那 1 次就是本层自己写的选择器字符串；`.soft-btn` 经 shell/workbench/design/
ui-primitives/main/index.html 逐个 grep 全为 0，判定为**样式表有定义、产品从不构建**。
处置：从动效宿主里摘掉（不接线一个不存在的表面），CSS 那一条**保留不删**并作为发现记账——
它同时服务 UIKIT 的对外合同，删它是另一个判定。数字滚动也一并摘掉：shell 已有
`animateKpiCount` 驱动 `strong[data-count]`，再加一个动画器就是把同一个数跑两遍。
重建后 `build/main.js` 615,430 → **614,144 字节**（gzip level 9 161,916 → **161,478**，净减 438 字节——
本轮清死码反而变小），`tsc --noEmit` 干净，node 三套 rc=0。

**两条被我上一轮写进台账、本轮被实测推翻的"待办"，按证据改写而不是照做。**
① 「唯一强调色 `#356B92` 待落」：**早已在仓**——`style.css` 的
`:root[data-palette="stitch"][data-scheme="light"]` 块里 `--color-primary`、`--accent`、
`--color-secondary`、`--secondary` 四个都写 `#356B92`，且带日期注释说明"单一低饱和强调色同时担任
action/focus/selection/info"。这一条不该再占施工单位。
② 「`_list_prompt_results` 套 `PAGE_LIMIT` 信封是最成熟的一刀」：子代理实测**否掉**——
`design-lab/schemas/prompt-result-readback-v1.schema.json` 是 `additionalProperties:false` 加 13 键
固定集，喂 `limit/next_cursor/truncated` 会被自家校验判 500（逐字
`Additional properties are not allowed ('limit', 'next_cursor', 'truncated' were unexpected)`），
而兄弟先例 `knowledge-library-readback-v1.schema.json` 的 `required` 里就有
`total/offset/limit/returned/next_offset`——即"加界"必然要改 **schema 文件**、路由模式（现不带查询串）、
合同行拒绝词、以及 `test_workbench_weight.py` 的 `UNBOUNDED_REGISTER` 摘牌，是一整刀带迁移的活，
不是顺手一刀。它按授权面**停手未改任何文件**，基线复验仍绿
（`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=90 dispatched=90 bound=76`、
`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=57 failures=0`、`Ran 41 tests / OK`）。

**150KB 那句的调研结论，一并写在这里，因为它决定后面每一刀的取舍。** 行业那族是
「critical file size budget < 170Kb gzipped」，出处是 2018 前端性能检查表第 07 条并被 web.dev 的
code-splitting codelab 沿用；它由两条依据**反推**得出（$200 Android + 3G、400ms RTT、约 400kb/s、
TTI<5s；170KB gzip 解压 0.8–1MB 在普通手机上约 1 秒解析编译），而且覆盖的是**整条关键路径**
（HTML+CSS+JS 合计）。包里 150KB 只管 JS、单口径更严，却没写画像、指标与推导。本项目实测
（gzip level 9，本行落笔时从磁盘现取）：bundle 616351/162258、
stylesheet 121330/41645、document 10144/3857，
**关键路径合计 207760 字节 = 202.9 KiB**；同时 `transferSize` 实测就是全额 610,364（**回环服务不
gzip**），`responseEnd` 4ms、冷启动 `load` 93ms、**0 个 long task**、堆 2.3MB、DOM 436 节点。
结论：这条传输预算量的是本部署形态下**不发生的传输**；对 127.0.0.1 的桌面 UI，规范化的等价物是
CPU 预算（解析+编译+执行、无 >50ms 长任务、可交互 ≤1s），而我们在 CPU 侧有约 40 倍余量。
`scripts/measure_workbench_weight.py` 自述不发明预算、实测 `budgetDeclared=False`，所以**上限怎么改
仍是 owner 的决定**，本轮不擅自换数也不为凑数删内容。

**仍未做（不写成已做）。** 粒子/氛围层的 canvas 需要样式表那条定位规则与重建后的测量，另起 §5.63；
`?motion=enhanced` 的真人视觉验收没有；勾选框标签是否违反「标签放输入上方」（实测
`labelSideBySideExamples` 里有 `1440:preflight label vs input#jury-approve dy=-17px` 这类同排）
仍待 owner；`_list_prompt_results` 那一刀等 schema 迁移授权；release、安装态分发、真实宿主 E3、
真人 E4、模型推理、ComfyUI/MiniMax H3、AAOS 联调、E 盘、手机端（排除项）一律不变。
### 5.63 粒子层照"抄结构不引依赖"落地：画在文字之下的一层 canvas，并且用可冻帧的方式被量过

**做了什么。** Owner 要的是"更多动画动效粒子"。调研回来的可装库各有代价：GSAP 3.13 gzip 27.2KB
但许可是 GreenSock License（非 MIT，要过权利登记）；@tsparticles/slim MIT 30.5KB；canvas-confetti
ISC 4.3KB；pixi.js 226KB、lottie-web 76.8KB 因体积与维护不引入；react-bits/magicui 是
React+Tailwind。owner 既有的裁法是「吸收融入不了的 可以参考它的结构架构源代码等进行复制啊」，
所以这一层**不装任何依赖**：照 canvas-confetti 的结构（一次性发射、速度+衰减、自动停）自写，
24 颗粒子、只用两种品牌墨（`#EEF2F5` / `#17212B`）、alpha 0.10–0.22，
挂在 `--layer-canvas-ambient` 那一层（`.app` 的第一个子节点、`pointer-events:none`、
`aria-hidden="true"`），**永远在面板与文字之下**，不覆盖任何字形。

**可测性是先设计进去的，不是事后补的。** `?motion=enhanced&particles=static` 画**一帧确定图**并停下：
位置由固定种子函数 `seeded(i)` 生成，同一台机器与不同机器都是同一画面。这不是为测试开的后门，
它同时是包里那条降级要求的落点（`09_DESIGN.md:9`「低性能或系统关闭透明时回退实底」）；
`particles=live` 才用 rAF 动。`prefers-reduced-motion: reduce` 时整层不挂载，
默认（不带 `?motion=enhanced`）也不挂载。

**本轮实测读数（逐字，跑这次门时现取）。** 产品自己写的属性：
`CT_MOTION_WIRED {"dataMotion": "enhanced", "canvas": true, "canvasAriaHidden": "true", "canvasZ": "-2"}`——注意 `data-motion` 现在来自
`motion.ts` 而不是注入，这是"用户从 URL 一步进得来"的证据，而不是"样式表面对"的证据。
逐姿态对比度：`poses=[0, 3000, 6000, 9000, 12000]` `routes=24`
`checked=34170` `belowAA=0`
`distinctTransforms=4`。
被造出来的拒绝态行：["1440:assistant+refusal"]；
`errors=4`、`errorAdjacent=0`。
体积（gzip level 9，同档前后对照）：`build/main.js` 616351 字节 / gzip 162258；
`style.css` 121330 / 41645；`index.html` 10144 / 3857；
**关键路径合计 gzip 207760 字节 = 202.9 KiB**。

**这条断言会咬在哪里。** 闸门现在会**因为粒子层没挂上而红**
（`?motion=enhanced&particles=static did not mount an aria-hidden particle canvas`），
也会因为产品不再自己写 `data-motion` 而红。也就是说：这一层要么真的可达并被量，要么把门卡住，
不存在"代码在界面上看不见却全绿"的第三种结局。

**未做（不写成已做）。** `particles=live` 的**动画过程**未做逐帧对比度认证——本轮量的是它与
0% 一致的确定首帧；氛围层默认关闭，尚未有人从界面内一键进入（主题入口那把闸只点色板，不点 motion）；
真人视觉验收没有；GSAP/tsparticles 的引入与权利登记没有发生。
### 5.64 主题点击路径上有一个真缺陷：切色板时带的是旧色板的明暗侧，珍珠白因此永远点不出来

**这条不是样式表问题，也不是测试问题，是产品问题。** 20261023 包的 STITCH 基线只给了珍珠白那一侧的值
（`09_DESIGN.md:9`），所以 `PALETTES` 表里 `stitch` 只声明 `schemes: ['light']`。而色板按钮的旧写法是
`{ ...readThemeChoice(), palette: cyclePalette(...) }`——**scheme 从旧色板继承**。从只声明 dark 的面
切到 stitch 时，继承来的 `dark` 让 `applyTheme()` 走 `removeAttribute('data-scheme')` 那一支，
`:root[data-palette="stitch"][data-scheme="light"]` 因此永不匹配：屏幕上画的还是默认炭黑面，
而 URL 已经写成 `?palette=stitch`。**属性和界面在同一个时刻互相矛盾**，且只有点击路径断，
直链是好的（`?palette=stitch&scheme=light` 返 200 且落对属性）。

**这是被"走完整个色板表"的闸抓出来的，不是被注入属性的闸。** 前一版主题闸只点一步、只到 `ui2026`，
所以 `stitch` 从来没有在点击路径上被验过——CSS 面由对比度闸用 `addInitScript` 注入属性量得干干净净，
产品自己的按钮却到不了那一面。修法按职责分两侧：**产品侧** `shell.ts` 的色板按钮改为按
**目标色板自己声明的那一侧**解析 scheme（`spec.schemes.includes(now.scheme) ? now.scheme :
 spec.schemes[0]`），并把 `palette` 与 `scheme` 两个查询参数一起写回 URL，让属性、界面、URL 三者一致；
**闸门侧**（`audit_workbench_theme_affordance.mjs` + `test_workbench_theme_affordance_gate.py`）
色板表由两侧各自独立从 `shell.ts` 现读（不硬编码），断言①跳数必须等于表长（少一跳即红）、
②**每一跳都必须真的改变被画的墨色**（只改属性不改颜色的 D13 缺陷从此按跳而不是按首次检查）、
③最后一跳必须回到起点、④`?palette=stitch&scheme=light` 直链 200 且画出的不是默认面。

**改前改后的逐跳读数。** 改前（同一台机、同一 bundle）：
`HOP 1 ui2026/(absent) ink=rgb(159,177,195) over=rgb(8,14,22) ratio=8.81 moved=yes`、
`HOP 2 stitch/(absent) ink=rgb(154,163,184) over=rgb(6,10,20) ratio=7.83 moved=yes`、
`HOP 3 design-lab/light ink=rgb(154,163,184) over=rgb(6,10,20) ratio=7.83 moved=NO`——
第 2 跳"看起来变了"是因为它从 ui2026 的暗面换到另一套暗值，**珍珠白根本没出现**；
第 3 跳属性换了、颜色一动不动，就是 D13 那一形状。
改后本轮实测：[{"hop": 1, "palette": "ui2026", "scheme": "(absent)", "url": "?palette=ui2026&scheme=dark", "probeText": "设计辅助", "ink": "rgb(159, 177, 195)", "backdrop": "rgb(8, 14, 22)", "bgChain": ["span=rgba(0, 0, 0, 0)", "nav=rgba(0, 0, 0, 0)", "aside#app-sidebar=rgba(0, 0, 0, 0)", "div#b10-app=rgba(0, 0, 0, 0)", "body=rgb(8, 14, 22)"], "changeRatio": 8.81, "ratioBasis": "opaque rgb() ink over opaque rgb() backdrop", "moved": true, "paletteMoved": true, "paint": "rgb(159, 177, 195) on span=rgba(0, 0, 0, 0) | nav=rgba(0, 0, 0, 0) | aside#app-sidebar=rgba(0, 0, 0, 0) | div#b10-app=rgba(0, 0, 0, 0) | body=rgb(8, 14, 22)"}, {"hop": 2, "palette": "stitch", "scheme": "light", "url": "?palette=stitch&scheme=light", "probeText": "设计辅助", "ink": "rgb(86, 100, 114)", "backdrop": "rgb(244, 246, 248)", "bgChain": ["span=rgba(0, 0, 0, 0)", "nav=rgba(0, 0, 0, 0)", "aside#app-sidebar=rgba(0, 0, 0, 0)", "div#b10-app=rgba(0, 0, 0, 0)", "body=rgb(244, 246, 248)"], "changeRatio": 5.6, "ratioBasis": "opaque rgb() ink over opaque rgb() backdrop", "moved": true, "paletteMoved": true, "paint": "rgb(86, 100, 114) on span=rgba(0, 0, 0, 0) | nav=rgba(0, 0, 0, 0) | aside#app-sidebar=rgba(0, 0, 0, 0) | div#b10-app=rgba(0, 0, 0, 0) | body=rgb(244, 246, 248)"}, {"hop": 3, "palette": "design-lab", "scheme": "(absent)", "url": "?palette=design-lab&scheme=dark", "probeText": "设计辅助", "ink": "rgb(154, 163, 184)", "backdrop": "rgb(6, 10, 20)", "bgChain": ["span=rgba(0, 0, 0, 0)", "nav=rgba(0, 0, 0, 0)", "aside#app-sidebar=rgba(0, 0, 0, 0)", "div#b10-app=rgba(0, 0, 0, 0)", "body=rgb(6, 10, 20)"], "changeRatio": 7.83, "ratioBasis": "opaque rgb() ink over opaque rgb() backdrop", "moved": true, "paletteMoved": true, "paint": "rgb(154, 163, 184) on span=rgba(0, 0, 0, 0) | nav=rgba(0, 0, 0, 0) | aside#app-sidebar=rgba(0, 0, 0, 0) | div#b10-app=rgba(0, 0, 0, 0) | body=rgb(6, 10, 20)"}]
直链：{"asked": "palette=stitch&scheme=light", "status": 200, "palette": "stitch", "scheme": "light", "ink": "rgb(86, 100, 114)", "backdrop": "rgb(244, 246, 248)", "bgChain": ["span=rgba(0, 0, 0, 0)", "nav=rgba(0, 0, 0, 0)", "aside#app-sidebar=rgba(0, 0, 0, 0)", "div#b10-app=rgba(0, 0, 0, 0)", "body=rgb(244, 246, 248)"], "paintsLikeDefault": false}；色板表现读：[{"id": "design-lab", "schemes": ["dark"]}, {"id": "ui2026", "schemes": ["dark", "light"]}, {"id": "stitch", "schemes": ["light"]}]。

**这些数字的权威边界，写在读数旁边而不是事后解释。** 每跳的比值是**变化探测器**，不是 AA 结论：
该探针只在"墨色与祖先链全为不透明 `rgb()`"时给数，否则 `changeRatio=null` 退回原始色串比。
仓库里唯一的对比度主人是 `audit_workbench_contrast.mjs`，`stitch` 浅色侧是否过 AA 由
`test_workbench_contrast_gate.py` 以 `UI_PALETTE=stitch` 逐路由回答，本闸不越权也不重复认领。

**体积（gzip level 9）。** `build/main.js` 616351 / 162258；`style.css` 121330 / 41645。

**未做（不写成已做）。** `audit_workbench_theme_geometry.mjs:56` 那份**硬编码**色板表仍缺 `stitch`，
本轮没动它（改了要把几何结论一起重读）；主题不写 localStorage 是既有裁决（`shell.ts:10140`），
没有为"记住珍珠白"新开键；勾选框标签是否违反「标签放输入上方」仍待 owner；真人视觉验收没有。
### 5.65 造出拒绝态的下一步就抓到一支不达标的红字：珍珠白的错误墨色默认继承 #F05252，压白底只有 3.48:1

**这条是上一节的直接后果，不是新话题。** 闸门第一次让界面真的拒绝了一次（清空目标后点
`#as-submit`，`p#as-form-error.error[role=alert]` 显示
「请先写下要完成的设计目标：保存的是一条方案记录，不是一次运行。」），珍珠白面立刻报红，逐字：
`LOWCONTRAST 1440:assistant+refusal 3.48:1 need>=4.5:1 13px opacity=1 fg=rgb(240, 82, 82) :: p#as-form-error.error`，
同一条在 1920 与 plan-detail/plan-compare/plan-feedback 各自复用，合计 `CT_FAIL: 8 text run(s) below WCAG 2.1 AA contrast`。
**为什么以前从不红**：这行文字在此之前**没有任何界面会显示**——所有路由的读盘都成功，
`errors=0` 一直是空集。一个永远不会出现的状态当然永远不会失败。

**根因是一处作用域漏配，不是品牌决定。** `:root` 定义 `--color-error:#F05252`（为炭黑默认面选的，
压深色面过 AA）；ui2026/light 早在本文件里就把 `--color-error` 重指为 `var(--uif-light-danger)`
（style.css:1770），而 `stitch/light` 那一块**没有重指**，于是珍珠白继承了给深色面设计的红。

**取既有已实测值，不新造一支红。** 20261023 包只逐字给了六个值（强调/正文/次级/背景/内容/边界），
**没有给错误色**，所以自造一支红就是冒充包的规定。这里重指到同仓已存在的
`--uif-light-danger:#ab384d`，用闸门自己的合成算法算：压白 **6.17:1**、压珍珠白 `#F4F6F8` **5.69:1**、
压浅色 elevate **5.20:1**，三档都在 4.5 以上；默认炭黑面**一字节不动**，仍是 `#F05252`。
`--color-success`/`--color-warning` 未被改动：同一闸门在珍珠白逐路由量过全部被画文字，
只有这一支在拒绝态出现时不达标，其余没有实测证据支持动它们。

**改后同一把尺的读数（本轮现取，不是引用改前）。**
`CT_SUMMARY`：{"checked": "42381", "belowAA": "0", "pseudoLayers": "32209", "coveredForeign": "0", "obscured": "6", "unparsable": "0", "collapsedOpened": "6317", "controlMisses": "0", "strict": "1", "mathChecks": "4", "mathBad": "0", "colourChecks": "4", "colourBad": "0"}；
改后仍低于 AA 的 `assistant+refusal` 行数：**0**；
本轮跑过 `Ran 20 tests in 367.012s`，判定 ["OK", "OK"]；
被造出的拒绝态：proved 1 条
（roles=["alert"]）、
未落地的族 1 条。
体积：`build/main.js` 616351 / gzip9 162258；
`style.css` 121330 / gzip9 41645。

**这条断言会咬在哪里。** 拒绝态现在是必造状态：`RefusalPopulationIsGraded` 要求回执里存在
`+refusal` 行且 `errors>=1`，而 `CT_FAIL: the assistant intake form never showed its refusal line…`
会在没人让界面拒绝一次时直接红——**"没有错误可量"不再是绿，是红**。
珍珠白若有人再把 `--color-error` 改回亮红，下一跳的对比度闸会按每条路由把它报回来。

**一处需要承认的仪器形状问题（顺手改掉）。** 拒绝态植入最初被推进 `controlBad` 那一个列表，
于是"某个表单不在这次走到的状态上"被报成
`CT_FAIL: the white-on-color(srgb) control was not reported as a failure` ——一个列表服务两个含义，
失败信息就指错了仪器。现在拒绝态有自己的一对
`refusalProved/refusalAbsent`、自己的一行 `CT_REFUSAL_PROVED count=… absent=…`，
并且 `assistant` 那一族**必须**被造出来（造不出即红），`knowledge` 那一族落在没有该面板的状态时
如实写成 `CT_REFUSAL_ABSENT`，不再伪装成颜色解析器的失职。
### 5.66 那一条"最接近可落地"的登记被实测推翻后，这一轮把它真做完了：提示词读回现在是**有界的一页**

**先接上一段没做完的。** §5.62 记下了"套 `PAGE_LIMIT` 信封是最成熟一刀"这个说法被子代理实测推翻：
`prompt-result-readback-v1.schema.json` 是 `additionalProperties:false` 的 13 键闭集，直接加
`limit/next_cursor/truncated` 会被自家校验判 500。推翻不等于不做——它只是说明这刀**必须带上 schema**，
于是本轮按本仓已有的两个先例（`/api/knowledge-entries/search` 与 assistance-plan 列表）把它做完了。
`contracts.ts` 里没有这支读回的类型（grep `PromptResultReadback` 零命中），所以这次改动**不需要**动前端形状，
这一点是在动手前查的，不是事后补的。

**改的是四处，一次带齐。** ① `prompt_results.py`：`PROMPT_RESULT_LIMIT=100`、
`MAX_PROMPT_RESULT_LIMIT=200`，`readback(project_id, offset=0, limit=…)` 先校验再取数；
② **信封字段全部在切片之前取**：`total_readable` 是可读出来的全部、`result_count` 仍是数据库行数
（含解析不了的）、`newest`/`state`/`accepted_count`/`reviews` 都按全量算，只有 `results` 是这一页——
分页因此**不可能**把 400 条提示词读成 100 条；`reviews` 明确不翻页，因为截断签收记录就是隐藏决定。
③ 路由声明 `path_only=True`，`offset/limit` 在 handler 里用 `urlsplit + parse_qsl` 解析（与
task-preflight、知识检索同一写法），非法值回**具名 400**而不是 404：
`PROMPT_RESULT_FILTER_MALFORMED`、`PROMPT_RESULT_OFFSET_INVALID`、`PROMPT_RESULT_LIMIT_INVALID`；
④ 合同行的 `reason` 记下这个界与三个拒绝词，`test_workbench_weight.py` 的
`UNBOUNDED_REGISTER` **同轮摘牌**（9→8），摘牌的那条断言同时要求仪器不再把它算作无界——
登记与现状不许朝任何一个方向漂。

**仪器自己的现读（不是引用上面的话）。** `LISTROWS list_routes=18 bounded=10 without_limit=8 frontend_call_sites_scanned=142`
`LISTROWS _list_prompt_results           initial_rows= 100 kind=page-limit    at=prompt_results.py:51(PROMPT_RESULT_LIMIT) max_rows=   - client_calls=2 client_limits=- client_without_limit=2`

**这条断言会咬在哪里。** 三条新用例都是路由级：默认页必须报出 100 与 `truncated=False/next_offset=None`；
两行数据用 `?limit=1` 翻页时，第一页必须仍说"共 2 条、还有下文、next_offset=1"，第二页必须
`truncated=False` 且 `next_offset=None`，且 `state/newest/reviews` 与全量逐字节相等；
`?limit=0`、`?limit=201`、`?limit=ten`、`?offset=-1` 必须各回自己那个码——**一个无名 400 就是
让参数变成谜**。加上摘牌那条，把界悄悄改回无界、或把 `returned` 当成总数，都会红。

**未做（不写成已做）。** 前端调用点仍不传 `limit/offset`（默认页就是当前答案），界面要不要显式翻页是
UI 那一刀的活，本轮没动任何 `.ts`；其余 **8** 条无界路由不套同一修法，理由各自不同并已逐条登记
（`_list_or_read_assets` 成本在每行重校验而非行数，`_list_projects` 是逐项目汇总，
`_list_design_systems` 由四名注册表天然有界，`_list_rights/_list_knowledge_candidates`
是 Human Gate 与读回面——截断即隐藏决定，`_list_jury` 与 `_list_research` 只登记了"未测量"，
`_list_token_documents` 空值语义须保列表）。
### 5.67 几何那把尺的色板表不再是手抄的：珍珠白第一次被量的同时，它证明了自己没改布局

**接着 §5.64 的那条尾巴做。** 那一节记下「`audit_workbench_theme_geometry.mjs` 的色板表是硬编码的，
仍缺 stitch」。这不是小事：一个几何门的覆盖面写成三字面量，就意味着包里那套珍珠白**从来没被这道
门量过**——而它恰好是最容易被"顺手改一下布局"伤到的一套。

**改法是取消第二份真相。** 变体表现在从 `apps/workbench/shell.ts` 的 `PALETTES` 现读（mjs 与 python
各自独立解析同一份声明），断言是"渲染出的变体集合必须等于产品声明的集合"，所以第四套色板进了产品
就自动进这道门，**解析不出来就直接红**（`declared_variants()` 在少于 4 项时抛 `AssertionError`，
另有一枚把 `schemes: [` 遮掉的植入用例证明这条拒绝真的会响——第一版的植入是错的：它只改了表名、
条目还在，因此什么都没证明，被自己的断言当场抓出来后才改成遮 `schemes`）。

**珍珠白用什么当基准，这里要说清。** 包里 `09_DESIGN.md:9` 给的是**六个颜色值**，没有给导航轨宽度；
所以本仓不能凭空写一个数字当期望，那等于把发明说成规范。断言因此是**等值**：`stitch/light` 的每一
几何读数（`railRect / railComputed / marginLeft / paddingRight`）必须与默认面逐位相同，
不同即 `PALETTE_MOVES_GEOMETRY`——它同时跑在窄屏分支上，因为"浅色主题把 min-width 漏进窄布局"
正是未授权的移动端改动形状（手机端是排除项）。

**现读结果。** 宽度 ["1200", "1920", "700", "768", "960"]，
变体 ["design-lab/dark", "stitch/light", "ui2026/dark", "ui2026/light"]；
`stitch/light` 的轨宽 {"700": 700, "768": 168, "960": 168, "1200": 168, "1920": 168}，
默认面 `design-lab/dark` 同项 {"700": 700, "768": 168, "960": 168, "1200": 168, "1920": 168}——**逐位相同**，
`report.findings` 为空，闸门在本机现跑一遍原话是 `Ran 3 tests in 3.972s OK`（含那枚植入用例）。

**这条断言会咬在哪里。** 有人给珍珠白加一条 `min-width`/改 rail 宽，等值断言当场红；
有人把 `PALETTES` 里的某一侧删掉，覆盖面断言红；有人把这道门的表又抄回字面量，
python 与 mjs 两realm 的推导会先于任何断言炸在"少于 4 项"上。

**未做（不写成已做）。** 这道门量的是几何，不是颜色——珍珠白的 AA 归对比度门，
它的点击可达性归主题入口门（§5.64 修的那一刀）；界面上的翻页线索仍未做。
### 5.68 包里那支单一强调色，第一次在"它被画成什么"上有了数：两个方向只有一个达标

**这是 §5.52 欠下的那一半。** 那一节把「单一低饱和强调色 `#356B92`」判成**已测量、未满足**，并把 owner
要裁的两条路摆出来：要么"同一色相的深阶当填充（保持单一色相，但要重测白字）"，要么"按钮文字改深色并
放弃强调色当填充"。当时**第二个方向有数、第一个没有**，所以那条裁定一直是"代价未知"，不结算是不诚实的。

**先说结构：强调色在样式表里从来不是字墨。** 现读 `apps/workbench/style.css`，消费 `var(--accent*)`
的属性是 {"background": 3, "border-left": 2, "box-shadow": 2, "outline": 1, "border-color": 3, "stroke": 1, "fill": 1, "border-right": 1, "border-bottom": 1}，其中 `color:` 有 **0** 处。
也就是说 WCAG 1.4.3 只在"墨压在强调色底上"这一层咬它——把它当字色来测，测的是一个本仓没实现的形状。
被强调色当底的规则有 **3** 条，三条 shipped 的都写着 `color:#fff`。

**四个读数（同一把 WCAG 算式，不是猜的）：** 纸白墨压 `#356B92` = **5.72:1**；
压它的 hover 阶 `#2558DB` = **6.0:1**；深墨 `#17212B` 压 `#356B92`
= **2.85:1（不达 AA 的 4.5）**；而强调色如果哪天被当字墨压在珍珠白 `#EEF2F5` 上，
是 **5.08:1**（达标，但它现在没被这样画）。今天那 106 处 brand 深蓝实际 painted
的填充是 `rgb(29, 79, 196)`=`#1D4FC4`，白字压它是 **7.08:1**。

**结论只有一句，但它把裁定的代价变成了已知：** §5.52 摆的两个方向里，
**"同色相深阶当填充 + 纸白墨"实测达标（5.72/6.0），
"保留强调色底、文字改深色"实测 2.85:1 不达标**。所以这不是"两个都有代价"，
而是"其中一个会直接造出 AA 违规"。包给的值 `#356B92` 一字未动，enforce 阈值一字未动，106 处 brand
深蓝照旧是登记债——要不要收敛成一支、收敛到哪一支，仍是 owner 的设计判断，只是从此不必猜。

**珍珠白那两面现在的实测面：** {"stitch/light": {"pairs": 182, "brandBluePaints_summed_over_pairs": 106, "productFails": 0, "motion": {"poses": [0, 3000, 6000, 9000, 12000], "routes": 24, "checked": 34170, "belowAA": 0, "distinctTransforms": 4}}, "ui2026/light": {"pairs": 182, "brandBluePaints_summed_over_pairs": 106, "productFails": 0, "motion": {"poses": [0, 3000, 6000, 9000, 12000], "routes": 24, "checked": 34170, "belowAA": 0, "distinctTransforms": 4}}}。
分母要说清：`brandBluePaints` 这里按 `(宽度 × 路由)` 的 182 个对累加，
所以它和 §5.52 那个 21 **不是同一分母**，不能读成"深蓝变多了五倍"；两处的原始读数都在各自的件里。

**这条断言会咬在哪里。** 有人把某条强调色底规则的墨改成深色（`2.85:1` 当场红）；
有人新写一条 `color:var(--accent)`（"强调色从不作为字墨"这条结构前提当场红，而它是整节算式的依据）；
植入用例把 `color:#fff` 换成深墨后必须被点到名字，否则这道门只会守着空集。

**未做（不写成已做）。** 不改品牌蓝本身，不动 `#356B92`，不做翻页线索，不做真人验收；
`.app-nav button:hover` 那类伪态仍按 §5.52 的口径另计，本节的算式覆盖的是规则里写死的字面值。
### 5.69 「错误紧邻字段」量错了对象：那条 1199px 一半是尺子的错，一半是真的

**§5.62 把人口补全之后，读数并没有变好，它只是开始说实话。** 珍珠白那两件里
`errors=8`、`errorAdjacent=8`，
最远的例子逐字是 `（无）`。
0 邻接听起来像"产品把错误信息扔在别处"，但那个 `dy` 是**怎么算的**要先问：
审计取的是 `host.querySelector('input…')`——宿主里**第一个**控件。方案表单有二十来个字段，
提示节点写在表单末尾，于是它被拿去跟最上面的「需求」文本域比距离，`dy=1199px` 是这两点之间的
真实距离，也是**这条规则从没被正确度量过**的证据。

**两处都得改，不是只改尺子。** 尺子这边：拒绝语现在通过 `data-for` 说出它讲的是哪个字段，
审计按那个字段量距离；没有 `data-for` 的消息另记为 `errorUnowned`，仍按"最近的控件"打印，
但**不混进被断言的那个数**——把人口重新分类来让数字变好，是这条线不能踩的地方。
产品这边：`showFieldRefusal(control, message)` 把同一个 `p.error[role=alert]` **移到**该字段所在
`.field-row` 之后（共享 `.as-row` 的字段插到整行之后，避免把一个 `<p>` 塞进两个 label 中间），
并聚焦该控件；清空时节点回到原来的槽位，所以**没有拒绝的静态版面一字节未动**。
五处字段级拒绝（需求／记录人／输出类型／外部步骤／镜头行）现在都走这道门，工作区读数失败也点名 `#as-workspace`。

**现读结果（同一次跑出来的件）：** `errors=8`、
`errorAdjacent=8`、`errorNamed=8`、
`errorUnowned=0`；被逐个造出来的字段拒绝
[{"key": "1440:assistant#case1", "field": "as-objective", "dy": 24, "besideRow": true, "text": "请先写下要完成的设计目标：保存的是一条方案记录，不是一次运行。"}, {"key": "1440:assistant#case2", "field": "as-author", "dy": 24, "besideRow": false, "text": "记录人不能为空：方案要写明是谁写的。"}, {"key": "1440:assistant#case3", "field": "as-output-type", "dy": 24, "besideRow": false, "text": "输出类型未读回，暂时无法保存；这个选择来自服务，页面不手抄一份词表。"}]——**每条都贴在它点名的字段旁边**，闸门原话 `Ran 4 tests in 77.915s OK`。
两个要说清的读数：`dy` 三次都正好是 **24px**，那正是 `.field-row` 自己的下边距，也就是消息与字段
之间只剩这一行本该有的间距；第三例落在 `as-output-type` 而不是预期的外部步骤，因为这份合成工作区
里输出类型没有可读回的选项，`更多设置` 里的步骤行与镜头行两条本轮**没有**被造出来。

**人口本身在这一轮两次跑里不相等，这条要说出来。** {"this_run": {"errors": 8, "named": 8, "unowned": 0}, "predecessor_run_on_disk": {"errors": 8, "named": 8, "unowned": 0}}：
本次跑记到 **8** 个 `p.error`，脚本启动时盘上那一份记的是
**8** 个。
差别在方案详情／对比／反馈那三个面板态里那条提示**还在不在屏上**——`startEditing` 这一路现在会清空
提示节点并把它收回原来的槽位，空节点没有盒可量，于是不再计入。两种人口下等式都成立
（8=8），因为被断言的从来不是计数，
而是"每一个被计上的消息都贴在自己点名的字段旁"加上"至少三条逐个造出来的字段拒绝"。
**不稳定性登记为下一刀的活**：让每个态自己造一次拒绝，而不是依赖前一个态遗留的消息。

**三条里只有第一条 `besideRow` 为真。** `记录人` 与 `输出类型` 共用一个 `.as-row`，消息按设计落在
整行之后——落在两个 label 中间会把那一行的栅格拆开。所以 `besideRow` 在这份件里是**读数**，
判据是那 24px 的距离；把它当判据会把一个正确的设计选择判成缺陷。

**这条断言会咬在哪里。** 有人把某条拒绝写回 `formError.textContent = '…'` 而不点名字段：
源头的"每条字段级拒绝都走这道门"当场红；有人移动节点时忘了把 `data-for` 一起设上：
审计按 `errorNamed>=1` 与逐条 `data-for` 红；有人把消息留在表单末尾：植入行 1199px 的对照用例
（`test_the_rule_convicts_a_row_that_is_far_from_its_field`）证明这种形状确实会被判违规。

**仍未做，也不写成做了。** `knowledge+refusal` 那一族在这次走查里仍然是 `absent`
（`#knowledge-create-submit` 不在被走的态上），这条和改之前一样被打印出来、没有被藏进通过数；
本节的逐个造只跑在 1440 一个宽度上，量的是同一表单内部的相对距离；没有加 `scrollIntoView`，
因为那是界面自己决定要不要滚动，不属于这条规则的证据。

**顺手量到的一件别处的债（本轮不修，只登记）。** 为了确认这次改动有没有把文档里的行号指针挪歪，
写了一把通用尺子，它先把**自己**暴露了：卷宗里的 `<file>:<N>` 有相当一部分写的是裸基名
（`style.css`、`prompt_results.py`），按仓库相对路径解析根本找不到文件；而能解析的那些里，
`shell.ts:5794` 指 toast 节点，现读 `id: 'toast'` 在 **9857** 行——**差 4063 行**，这是历史累积，
不是本轮 `+29` 行造成的。仓库里**不存在任何行号指针闸门**（`ls scripts` 无 pointer/anchor 类脚本）。
结论：行号指针已经腐到不能靠一次性重写来救，需要先有一张"指针→判据片段"的显式表；本节的 §5.69
正文因此**只写符号名与实测数字，不写新的行号指针**。
### 5.70 「错误紧邻字段」的第二族不是没做，是闸门一直在点一个不存在的东西

**§5.62 修了人口，§5.69 修了对象，这一节修的是入口。** 知识那一族的拒绝态从被要求那天起就一直在报
`absent`，而我上一轮把它写成"仍造不出来、已登记"。真相更好笑也更典型：闸门点名的
`#knowledge-title`、`#knowledge-create-submit`、`#knowledge-outcome`**在这个路由上根本不存在**。
`knowledgeFormPanel` 的 create 前缀是 `kb-new`，字段真名是 `kb-new-title` 一族；
而它的提交按钮与状态区**连 id 都没写**（`el('button', {type:'button', class:'primary-btn'}, …)`、
`el('div', {role:'status', 'aria-live':'polite'})`）。所以"揭示失败"从来不是产品没渲染——
表单渲染了，我查的是不存在的名字。

**改法两处，都在闸门侧。** `openRefusalState` 从"id 参数"改成"选择器参数"（那两个元素没有 id，
按 id 的探针永远够不到），知识那一族先用路由自己的 `#kb-new` 把表单揭示出来，再按结构定位：
线是 `#kb-form [role=status]`、清空字段是 `#kb-new-title`、触发是 `#kb-form .primary-btn`。
**没有把 `[role=status]` 加进被判的人口**：那条拒绝本来就写成 `p.error`，已经在人口里，
加进来会把同一个句子数两遍。

**现读结果（本次跑写的件）。** `CT_REFUSAL_PROVED count=4`，被造出的族是
["assistant+refusal", "knowledge+refusal"]（改之前只有 assistant 一族、count=2）；
计数到的拒绝消息从 **8 条变成 12 条**，其中**点名对象的 8 条全部贴在字段上**
（`errorNamed=8`＝`errorNamedAdjacent=8`），
剩下 **4 条是没主人的复合消息**：知识表单那句一次点名三个字段
（"标题、一句话用途和正文都必须填写…"），因此谈不上"贴在哪一个字段旁"，
实测离最近的控件是 `"1440:knowledge+refusal p.error -> nearest dy=82px"`。

**这里有一处必须说清的取舍，不是把断言调松。** 上一版的断言是 `errors == errorAdjacent`。
它在当时成立，只因为人口里**还没有**无主消息；如果把知识那 4 条从计数里去掉，它照样"绿"。
所以定罪面挪到包真正说的那一对——**消息与它点名的字段**——同时新加一条反向断言：
`errors` 必须**大于** `errorNamed`，即那 4 条复合消息必须还在被数到，
哪天它们从人口里消失，闸门直接红并把距离留在 `errorFarExamples` 里点名。
**这条规则的满足状态因此是：字段级拒绝已达标并被判；表级复合拒绝未达标、已量出距离、已登记。**

**顺带修掉我自己造的一次崩。** 无主消息取"最近控件"时我把 `reduce` 的种子写成 `null`，
于是宿主里没有可画控件的第一个元素就让整个跑炸在
`TypeError: Cannot read properties of null (reading 'getBoundingClientRect')`——
非空集合才 reduce。这条不是"测试太严"，是尺子自己会死在边界上。

**未做（不写成已做）。** 知识那句仍是"一句管三个字段"；要真做到每个字段旁各说各话，
得让校验器按字段返回问题，那是产品形态的一刀，本轮不替它猜形状。
`.view-hint` 那一族仍不带 `role=alert`（§5.62 记的无障碍缺口），本节的修没有触碰它。
### 5.71 owner 审计 7 条逐条对回字节：第 1 条（P1 源码包不能重建安装包）确证，而且比审计说的更大

**审计说的是什么。** owner 于 2026-10-26 在版本 `7671ec70` 上发来 7 条，第 1 条 P1：
"pyproject.toml 的 sdist 遗漏 wheel 所需资源，实测 sdist → wheel 因缺 domain-packs 失败"，
验收要求"从源码发行包开始，在干净目录构建 wheel、安装，再验证 GET/POST 接口；不能只测直接从仓库构建"。

**先把审计自己说的话坐实。** 本轮现场重跑复现，报错逐字是
`FileNotFoundError: Forced include not found: …/design-lab/domain-packs`。
但审计低估了规模：`[tool.hatch.build.targets.wheel.force-include]` 声明 **71** 条仓内路径，
旧的 sdist `only-include` 只覆盖其中 **17** 条——**54 条**在源码包里根本不存在
（`design-lab/schemas` 50 条、`config` 3 条、`domain-packs`、`production/profiles`、
`readiness`、`scripts/verify_domain_pack_v2.py` 等）。CI 一直绿，是因为那个作业
`uv build --wheel` 直接从 checkout 造 wheel，**从没碰过它自己发布出去的源码包**。

**改法两处。** ① `only-include` 从"逐条抄 wheel 的清单"换成覆盖全部 force-include 源的**目录根**，
并保留 2026-09-21 那条约束（`apps/workbench` 仍只列被服务的三个文件，node_modules 不进包）；
`design-lab/tests` 也进包，因为验收用的三段链测试就住在那里——一个不能从自身跑验证的源码包不是源码包。
② 新增 `design-lab/scripts/verify_sdist_packaging.py`：从 pyproject 自己重推"wheel 要的每条源都必须
被 sdist 的某个根覆盖"，三种失败形状各自点名（wheel 指向仓库里没有的路径、sdist 列了不存在的根、
列了又被 exclude 吃掉），另有 `--build` 模式真跑一遍 sdist→解包→wheel。这把闸进聚合。
③ CI 的 `Clean wheel install + Workbench launch gate` 第一步改成
**先造 sdist、解包、从解包树里造 wheel、装那个 wheel**，并把两个来源的 wheel 摘要当场比对。

**本轮实测读数（这份 receipt 就是这次跑出来的）。** 源码包 `design_lab-0.1.0a0.tar.gz` 3,980,242 B；
从源码包重建的 wheel **1,244,991 B、413 个成员、内容摘要 34e9969dd470d1e0**，
从仓库直接造的 wheel **1,242,808 B、413 个成员、内容摘要 34e9969dd470d1e0**——
**成员与每个成员的字节完全一致**，所以"从源码重建"不是第二次不同的构建。
一句自我修正写在这里：我最初把断言写成"两个 .whl 文件的 sha256 必须相同"，实测**容器字节确实不同**
（`c2382b42…` 对 `a9c86329…`），但逐成员比下来成员集合、每个成员的内容、zip 元数据全都一致——
差的是压缩器的输出流。那条断言测的是"第二次构建用的 deflate 参数"，不是发行物，
所以判据换成成员集合 + 内容摘要；这既没放松要求（内容照样逐成员比），也不再要求一个与语义无关的字节相等。
闸的读数：`SDIST_PACKAGING=OK wheel_sources=71 covered=71 missing=0 sdist_roots=17 mode=static`；`SDIST_PACKAGING=OK wheel_sources=71 covered=71 missing=0 sdist_roots=17 mode=build`；`test_sdist_packaging` 九条用例 `Ran 9 tests in 0.092s OK`
（其中四条是植入：删掉一个 sdist 根、wheel 指向不存在的路径、sdist 列了不存在的根、exclude 吃掉列出的源）。
按验收口径对**已安装布局**的三段独立跑（现装现跑，读数直接来自这三段自己的输出）：
{"test_workbench_launch": "Ran 3 tests in 1.935s OK", "test_standalone_chain_http": "Ran 6 tests in 5.926s OK | GET_SWEEP layout=installed routes=50 reads=54 answered=49 verdicts=5 unmeasured=2", "test_installed_write_surface": "Ran 6 tests in 4.888s OK | POST_SWEEP layout=installed rows=40 walked=39 written=39 read_backs=48 refused=0 excluded=1"}。

**我自己在这条上踩到的一次假红，写下来免得下一轮误判。** 第一次我把三段合在**一条** `python -m unittest` 里跑，
结果 12 条红——逐字是 `AssertionError: 'site-packages' not found in (…'src', 'design_lab', '__init__.py')`。
那不是产品问题：`test_workbench_launch` 会把 checkout 的 `src` 放进 `sys.path`，
后面两个模块的"必须跑在已安装布局"守卫因此正确地拒了。**CI 是把三段各跑一步的**，分开跑本机也全绿。
一次调用方式造成的红，不能报成"修好了 12 条缺陷"。

**其余六条的核验状态（未做完的不写成做完）。**
第 2 条（supersedes 可分叉）读码确证：创建路径在 `knowledge_library.py:541-546` 以
`KNOWLEDGE_SUPERSESSION_CONFLICT` 拒绝第二个后继，导入路径 `:647-658` 只做格式与存在性校验后无条件
`INSERT`；库层无 UNIQUE/CHECK（`…knowledge-library-v1.sql:32-39`）；投影响应
`superseded_by` 是 `string|null` 且 `setdefault` 取**第一条**（`:402-405`）；全仓无任何测试提到
`KNOWLEDGE_SUPERSESSION_CONFLICT`。第 6 条确证：对比度闸的植入反例用例不带 `CT_OUT`，与基线共用
`workbench-contrast-gate.json`（`test_workbench_contrast_gate.py:130/:449`），而 mjs 在失败退出前
就 `writeFileSync`（`audit_workbench_contrast.mjs:1695` 早于 `:1800/:1848`），且报告里没有 mode/版本
身份字段——归档到的可能就是那枚故意红的件。第 7 条的"打印路径崩"确证于
`scripts/audit_workbench_ui.py:171`（`relative_to(REPO)` 对仓外目录抛 ValueError），
同样形状还在 `scripts/run_design_review_plugin.py:279/:161`。
第 3、4、5 条**本轮尚未复现**，不在此声明完成。

**边界。** 旧 34 项状态一字未改：本行证据挂在语义主人 `DL-FINAL-T05`（"能力库安装资源与干净wheel核心链"）下，
它的 `state` 仍是 `FROZEN_DEFERRED`——**owner 这份审计授权的是修这一处缺陷，不是把那张任务重新派工**；
要改状态需要另一次明确授权。审计里"不能把本地 3294 通过／54 失败合并成全量复测通过"这条也照写在此：
那 54 条失败本轮没有一并复现，本轮只声称上面点名的读数。
### 5.72 owner 审计第 4 条（`doctor --task` 确定性崩溃）已修，并且把这一类缺陷做成了一把全仓的尺

**复现先于修改。** 修复前两条输入都崩，逐字是
`UnboundLocalError: cannot access local variable 'resolve_paths' where it is not associated with a value`
（`src/design_lab/runtime/doctor.py:161`），**有效 id 与无效 id 一模一样地崩**——审计用"确定性"这个词是准的。

**根因是一行局部 import 的作用域语义。** `main()` 的 `--paths` 分支里写着
`from .paths import PathPolicyError, resolve_paths`；Python 的局部绑定是**整个函数级**的，
于是排在前面的 `--task` 分支读 `resolve_paths` 时读的是一个尚未绑定的局部名。
修法就是把 `PathPolicyError` 提到模块级那行 import（第 14 行本来就已经导入 `resolve_paths`），
函数里那行局部 import 删掉。**为什么它一路绿着进仓**：`test_doctor.py` 原来只测 `probe_tools()`，
没有任何用例走过 `--task` 分支。

**约定格式现在有三条钉住。** 无效 id → `TASK_PREFLIGHT_FAIL` 且 `reason` 明写期望形状
`'<TASKPACK>::<TASK_KEY>'`、退出码 2；有效 id → 返回合同封套
`schemaVersion=design-lab/task-resource-preflight/v1`（这个封套**没有** `status` 字段，
`status` 只属于拒绝路径——我第一版测试就是照这个假设写错而红了一次）；`--paths` 照旧可解。

**比修这一处更值钱的是第二把尺。** 新增 `test_local_import_shadowing.py`：枚举 `git ls-files` 里的
受版本控制 Python 文件，判"同名在**同一函数作用域**内被后面的局部 import 重新绑定、而前面已被读取"，
且该名字在模块层已有绑定——正是这枚缺陷的形状。三条边界写死以免变成噪声机器：
嵌套函数/lambda 里的读取**不定罪**（那里的名字在调用时才解析，是另一个问题）、
形参不算（它本来就是局部名）、人口从 git 索引现数而不是手抄清单。
**它不是恒真的**：对修复前的 `doctor.py` 定罪 `[[161, "main", "resolve_paths", 186]]`，
对修复后的文件返回 `[]`；
全仓现有命中 **0**。样本植入还额外证明"读在前、绑在后"这个方向性成立。

**本轮实测。** `test_doctor.py: Ran 5 tests in 0.206s OK`、`test_local_import_shadowing.py: Ran 4 tests in 1.216s OK`；
`test_doctor_evidence` 9、`test_doctor_tool_bindings` 12、`test_migration_preview` 11、
`test_model_manifest` 22（本机 1 skip）、`test_model_selection` 8 全部 OK；
聚合 `VERIFY_DESIGN_LAB=OK total=77 failed=0`；投影新鲜度 25 条 OK。

**审计摄入进度（写清楚哪些还没做）。** 第 1 条（sdist）见 §5.71；第 4 条本节；
第 **2、6、7(b)** 条已对回字节确证但**未修**（引用点在 §5.71 末段）；
第 **3** 条（workbench.ts 响应头之后就清计时器，慢正文越过 750ms）与第 **5** 条
（知识表单把多个字段的问题合成一句）**本轮尚未复现**，不作完成声明。
旧 34 项状态一字未改：本行证据挂在语义主人 `DL-FINAL-T04`「机器配置、生成器、校验和CI同步」下，
它的 `state` 仍是 `FROZEN_DEFERRED`——审计授权的是修这处缺陷，不是把那张任务重新派工。
### 5.73 owner 审计第 2、3、5、6、7(b) 条：五处已修，每处都先在旧字节上红过一遍

本轮把审计里工程可完成的五条做完，每条的验收方式都是同一件事：**修改前的字节必须被同一套用例判红**。
一条从来只在修好之后跑绿的测试，什么也没证明。

**第 2 条 · 知识 supersedes 可以分叉。** 复现属实，且不对称的位置很具体：`create()` 检查
"这条是否已被替代"，`import_entry()` 只检查 id 形状与存在性，然后直接 INSERT——于是 UI 拦得住的分叉，
导入路线一条就能写进去。读侧再把痕迹藏起来：`_statuses()` 用 `dict.setdefault` 配一条**无序**扫描，
库里两条后继时它显示先回来的那一条。修法分四层：两条路线改调用同一个
`_supersedes_guard()`（拒绝话术一致，并点名"已被哪一条替代"）；检查与写入包在
`BEGIN IMMEDIATE` 里——读后再判的锁外检查只是"可能性"，并发用例在旧字节上跑出的正是
`['wrote','wrote']`；状态 SQL 里加 `knowledge_entry_one_successor` 触发器，让**绕过应用层的写入者**
也被数据库拒绝（该用例直接 INSERT，故意不走那两条路线）；扫描改成 `ORDER BY created_at, entry_id`，
这样历史库里已有的分叉仍然可读，但每次读都给出同一个后继，而不是随 SQLite 心情。
本轮实测：`test_knowledge_library.py: Ran 26 tests in 5.483s OK`；对修复前提交 `71aff01b` 的同一套用例判红
`Ran 5 tests in 0.579s FAILED (failures=5)`。

**第 3 条 · 请求超时与取消管不到正文。** `api()` 的 `finally` 在响应头到达时就 `clearTimeout`
并摘掉两把取消监听，所以"答得快、正文慢慢滴"可以无限越过预算，切页也无法取消，写丢了正文落进一条
无类错误。现在头部与正文在同一个 try 里，三种结局仍然可辨且各自动作不同：慢正文→读取超时（无副作用，
可重试）；正文期切页→页面已切换；写丢了正文→`outcomeUnknown`「结果待核对」，禁止不看读回就重发。
三条用例都带**看门狗**：无人管辖的实现要判红，而不是把测试挂死——挂死既测不出回归，也会被 CI
当成环境噪声。第一条反证跑原本报 `rc=0`，那是**我自己的跑法在谎报**：`run_appshell()` 硬编码返回 0
而从子进程取码，同时脚本没有断言"换源码这件事真的改了 bundle"。补上"bundle 摘要必须变化"与
"只有修复版才有的那句话必须消失"两道见证之后（本轮：5cd4cc19598a -> bd048fe282c3 and it lost "答复在读取过程中被取消"），
旧 bundle 判红 `PROVED: all 3 body-phase cases are non-vacuous -- each one is red on the pre-fix bytes and green on the fixed ones.`。

**第 5 条 · 知识表单把多个字段的问题合成一句。** 原句「标题、一句话用途和正文都必须填写」一次说三个框，
填掉两个之后屏上仍是同一句话，而且它写在面板末尾、离任何输入框都有半屏；导入路线把
「来源 ID」和「来源版本」也同样合成一句。现在一个空字段一条说明，`data-for` 点名自己的字段、
`aria-describedby` 让读屏进框就听见原因、光标交给第一条。位置不是"行之后"而是**行之内**：
`.field-row` 是单列 grid，而表单容器 `.two-col` 是**两列** grid——插在行之后就落进右边那一格，
变成挂在别人家字段旁边的错误。浏览器尺 `walkKnowledgeFieldRefusals()` 把这一族按画布上量：
`errors=28 named=24 namedAdjacent=24`，
案例 `4` 条知识 + `3` 条助手，`bad=0`，
知识族每条 `dy` 实测 [18, 18, 18, 18]。
**同时把测试自身的一处缺陷改掉**：`FieldRefusalsLandOnTheFieldTheyName` 原先断言
`errors > errorNamed`，那是在**要求不具名的合并提示继续存在**——把它修好反而会让闸门变红。
现在守的是人口不许缩小（具名数不少于被激发的案例数、具名是不具名的子集），不再守住缺陷的形状。

**第 6 条 · 审计回执被反证覆写。** 基准跑与"故意判红"的反证跑共用同一个
`workbench-contrast-gate.json`，而 CI 的 `Upload E2 evidence artifact` 是 `if: always()` 整目录上传，
谁最后写谁就是归档件——归档里可能是那条刻意的红。反证跑现在写自己的
`workbench-contrast-gate-enforce-red.json`，两份回执各自带上 `report.run`
（`{"palette": "design-lab", "scheme": "dark", "widths": "1440,1920", "specEnforce": false, "gitSha": "022c5a9bd989bc4f1b57af7936167cb8656bf009", "productFails": 0, "plantedControls": 368}`），
断言两边互不相同：基准 `specEnforce=false`、反证 `specEnforce=true widths=1440`。
另外把规则本身做成可判红的尺：任何改了配置（主题/宽度/enforce）却没写自己文件名的
`_run_gate` 调用都会定罪，删掉反证那一行 `CT_OUT` 的植入样本必须被它抓住。
诚实边界：**这一类覆写全仓只此一处**，但人口不是用我第一版写的那条 grep 数的——
`grep "assertNotEqual(code, 0)"` 匹配不到跨行调用（对比闸那条就写成
`assertNotEqual(code, 0,\n ...)`，命中的反而是无关的 `test_release_preflight.py`）。
可复现的探针对是 `grep -rnE "assertNotEqual\(.*,\s*0" design-lab/tests/*.py`：**11 处断言、跨 8 个模块**，
其中只有对比闸的反证会把回执写进 CI 上传的 evidence 目录（`test_capability_library_clean_install.py:247`
与 `test_release_preflight.py:470` 判的是子进程退出码，不落回执）。
motion / theme-affordance / theme-geometry 三个闸门共用"单一路径"的形状但**没有第二个写入者**
（`design-lab/tests/test_workbench_motion_gate.py:100`、`design-lab/tests/test_workbench_theme_affordance_gate.py:106`、`design-lab/tests/test_workbench_theme_geometry_gate.py:103`——三处各自现读到那一行写的就是`report_path = evidence / '<本闸门自己的报告名>.json'`，逐字核过才算点名到路径），
本轮不改动它们，只登记。**教训记进记忆**：一条匹配不到的探针给出的"0/1 命中"不是证据，
只是探针自己在说空话——这与 §5.71 那条"外部工具零发现不等于证明"同源。

**第 7(b) 条 · 审计脚本在打印自己路径时崩。** `audit_workbench_ui.py` 扫完、写完 JSON，再对打印行做
`out_path.relative_to(REPO)`，`--out`（或 `E2E_EVIDENCE_DIR`）指向仓外任何目录都在**成功测量之后**
抛 ValueError；`run_design_review_plugin.py` 里同样的写法有两处。`display_path()` 在仓内仍给相对形式
（现有钉住的读数不受影响），仓外给绝对形式，永不抛。`test_report_path_display.py: Ran 6 tests in 0.009s OK`，其中一条用例复现原式确实抛
ValueError，另有一条把旧写法植入回去证明守卫会定罪。

**顺带修好的一处测试基建（不改产品行为，但决定上面几条能不能被证伪）。**
`apps/workbench/tests/appshell.mjs` 的替身此前没有 `parentNode` / `nextSibling` / `insertBefore` /
`closest` / `getAttribute` / `id` 存取器。`closest()` 缺位会让 `control.closest('.field-row') ?? control`
悄悄退化成"贴到输入框自己身上"，`id` 缺位让 `if (control.id)` 在替身里永远走 false 分支——
也就是说"按字段拒绝"这一族在 DOM 测试里只能证明"放了个节点"，证不了"放在哪个字段里"。
补上之后 `WORKBENCH SMOKE: all checks passed`、`APPSHELL REGRESSION: all checks passed`。

**本轮实测汇总。** `test_knowledge_library.py: Ran 26 tests in 5.483s OK`、`test_report_path_display.py: Ran 6 tests in 0.009s OK`、`test_local_import_shadowing.py: Ran 4 tests in 2.344s OK`；
node 三套 `WORKBENCH SMOKE: all checks passed` / `APPSHELL REGRESSION: all checks passed`；
对比闸门 `7 条按字段案例 bad=0`，激发成功的拒绝家族
`["1440:knowledge+refusal", "1440:assistant+refusal", "1920:knowledge+refusal", "1920:assistant+refusal"]`；
`HEAD=022c5a9b`。

**仍未做完的（不作完成声明）。** 第 7 条前半（兼容 Python API 的会话关联响应与持久化来源是否 UI/HTTP
可达）本轮只完成定位、未见结论（这一句由 §5.74 取代）；第 7 条后半的**容量**两项：本轮现数 `src/design_lab/http_service.py`
里有 **17 个 `_list_*` 处理器**，其中哪几个真正无界、以及各被界面调用几次，读数在 **§5.66** 那张
`LISTROWS` 现读表里（`list_routes=18 bounded=10 without_limit=8`，逐路由给 `client_calls` 与不封页的
理由；本节没有重测那份表，故不在此复述为"本轮实测"）；原图读取同样是容量风险。
**CSV 安全模式属于待决策项**，不是工程缺口，等 owner 的一句话而不是我的实现。
旧 34 项 `FROZEN_DEFERRED` 一字未改：本轮证据分别挂在语义主人 `DL-KB-02`（知识可写面）、
`DL-KB-06`（三主入口外壳）与 `DL-FINAL-T04`（机器配置、生成器、校验和 CI 同步）下，
它们的 `state` 不因审计授权修缺陷而解冻。
### 5.74 owner 审计第 7 条前半（会话关联的响应与持久化来源）：缺陷成立，位置确定，今天无人可达

§5.73 末段写的是"本轮只完成定位、未见结论"——本节就是那个结论。

**分叉是真的，而且成因很窄。** `link_session()` 命中已有链接时返回的是**调用参数** `source_system`，
而那一行是**写一次**的：没有 `UPDATE` 语句，`UNIQUE(job_id, session_ref)` 又让第二次 INSERT 进不来
（`design-lab/schemas/state/design-lab-state-creative-v1.sql:116-124`）。于是"用另一个来源重新链接同一对"
会把答复写成新来源，库里仍留着旧来源——响应与持久化就此对"这条作业是谁关联的"给出两个答案。
修法两处：答复改读**那一行记的值**；与库里记的值相矛盾的重新链接**直接拒绝**并点名两侧来源，
因为这类调用者是问错了出处，而不是做了一次幂等空操作。

**可达性用断言记下来，而不是用我的话记下来。** 人口从 `git ls-files` 现数：服务模块
（`src/design_lab/**` 全部 `.py`，只排除 `session_link.py` 自身与 creative 包的再导出）、
工作台源码（`apps/workbench/**` 的 `.ts`/`.html`）、以及工作流文件——共 **126 个文件**，
其中**没有一个**提到 `session_link` 或 `link_session`。另有 15 份文件在**文字或清单里出现**这个模块名——
`reports/current/**` 的投影、`design-lab/config/current-report-index.json` 这类登记索引、
`scripts/deepseek_test_gate_report.py` 与 `scripts/deepseek_worktree_reconciliation.py` 两份 CI 记账、
它自己的测试与迁移普查、以及 `docs/history/**` 的历史快照——它们是**关于**这个模块的记载，不是**通向**它的通路：
只列名字、列迁移表、做账，谁也不会因此调用 `link_session`。所以这处缺陷是**未接线面上的潜在缺陷**，
本轮证据等级是模块级 E2，
不是真实产品流程的 E3；接线那天这条测试变红，欠读回的是那个人，不是替我把我的断言继承过去。

**本轮实测。** 修复前 `Ran 10 tests in 1.107s FAILED (failures=1)`，失败原因逐字 `AssertionError: CreativeError not raised`；
修复后 `Ran 10 tests in 0.997s OK`。反证走的是同一套用例打在 `022c5a9b` 的 worktree 上，跑完按 sha 还原。
### 5.75 本轮的 CI 账：在承载这些字节的提交上读回，而不是借用前一次的绿

**run 40334885313（event=pull_request，head `768f3fac`）conclusion=success。**
非 skipped 的作业全部 success（10 个），逐字读数取作业自己的日志：

```
PYTHON_TESTS_SHARDS_START shards=3 expected_tests=3412 plan=none (index %% n)
PYTHON_TESTS_SHARD_RESULT shard=1/3 exit=0 tests=1092 wall_seconds=555.422 outcomes={'PASS': 1080, 'SKIP': 12}
PYTHON_TESTS_SHARD_RESULT shard=2/3 exit=0 tests=1100 wall_seconds=79.843 outcomes={'PASS': 1090, 'SKIP': 10}
PYTHON_TESTS_SHARD_RESULT shard=3/3 exit=0 tests=1220 wall_seconds=374.739 outcomes={'PASS': 1215, 'SKIP': 5}
PYTHON_TESTS_UNION=OK expected=3412 distinct=3412 ran=3412 duplicates=0 missing=0 unexpected=0
BROWSER_E2E ran=44 skipped=0 failed=0
```

`PYTHON_TESTS_UNION` 那条把"分片跑过的集合＝发现集合"钉住：`expected=3412`；相对本会话在
run 40315188651（head `5d603fe6`，就是那条漂移登记红里读出来的同一行）读到的 **3397**，
本轮净增 **15 条**（知识分叉、对比闸静态尺、报告路径显示、会话关联四组），
所以这些用例在 CI 里被执行过，不是只在我本机跑过。浏览器套件
`BROWSER_E2E ran=44 skipped=0`——no-skip 是
`verify_browser_e2e_ran.py` 的硬条件，任何 skipped 直接把作业判红，所以这一行的 skipped=0 才是
"按字段拒绝那三条断言真的在真 Chromium 里量过"的证明。

**为什么这一节值得单独写。** 本仓库 §5.59 曾经"CI 已绿"引的是变更**之前**的 SHA，被 §5.61 追正。
本轮同样差点重犯：`83448333` 的 PR run 在我推最终 head 时被 cancel-in-progress 取消，
而它的 push run 其实只跑了轻闸（11 个重作业全是 `skipped`）——**push run success 不等于套件通过**。
所以结清的对象只能是 `fc9c8b0d`→`768f3fac` 这条 PR run。

**第一次全量尝试是红的，红在我自己的测试里。** run `40331019135`（head `fc9c8b0d`）
`conclusion=failure`：分片 1/3 与 3/3 绿，2/3 两条 FAIL，
逐字 `PYTHON_TESTS_SHARD_RESULT shard=2/3 exit=1 tests=1100 wall_seconds=79.637 outcomes={'FAIL': 2, 'PASS': 1088, 'SKIP': 10}`，命中的用例是
`test_report_path_display.ReportPathDisplayTests.test_an_out_of_repo_path_is_printed_absolutely_and_does_not_raise, test_report_path_display.ReportPathDisplayTests.test_the_expression_that_crashed_still_crashes_on_the_same_input`；并集本身仍然完整：`PYTHON_TESTS_UNION=OK expected=3412 distinct=3412 ran=3412 duplicates=0 missing=0 unexpected=0`。
成因不是产品：the two cases built their "outside the repository" path with `tempfile.TemporaryDirectory()`. The runner sets TMPDIR inside the workspace, so the fixture landed under the checkout, `display_path` correctly answered a relative path and the raw `relative_to` correctly did not raise. The product was right and the test premise about its environment was unverified.
本地用 `TMPDIR=<仓内目录>` 复现出同样的两条红，修法是让"仓外路径"从 checkout 自己的位置推出来
并把前提写进断言（前提一旦被环境破坏就在 setup 处响亮失败）；顺带把那句"有没有漏回仓库前缀"
从**子串**比较改成**路径分量**比较——旧写法会被任何以仓库目录名开头的兄弟目录骗过，
这正是一个能被拼写骗过的检查不该继续存在的理由。修后两种 TMPDIR 下都 `Ran 6 tests OK`。
**同一 head 上的 browser E2E 作业是 `success`**，verify_browser_e2e_ran.py returns 1 on ANY skipped test and on any module that discovers 0 tests, so that job being green at the same head is proof that the contrast gate -- including walkKnowledgeFieldRefusals and the two new static guards -- ran with skipped=0 on the Linux runner, not that it quietly sat out.
DOM 那一侧同样不是在 Windows 上自说自话：`canonical-verify.yml:260 runs `pnpm --filter @design-lab/workbench test:unit`, i.e. `vite build && node tests/unit.mjs && node tests/appshell.mjs && node tests/shape-notice-coverage.mjs`, inside job `workbench-gate` (display name "Workbench strict-TS product gate"). That is where the three body-phase watchdog cases and the per-field knowledge assertions execute off Windows.`
该作业在同一 head 也是 `success`。

**那一次红同时反过来证明了一件事：本轮新增的 15 条用例确实被 CI 跑到过。**
`PYTHON_TESTS_UNION=OK expected=3412 distinct=3412 ran=3412 duplicates=0 missing=0 unexpected=0`，而本会话早先在同一条作业读到的上一次并集是 **3397**
（run 40315188651，head `5d603fe6`，就是那条红里读出来的同一行）——差额 **15** 正好等于
知识分叉 5 + 报告路径 6 + 对比闸静态尺 2 + 会话关联 2。也就是说除那两条之外，
其余 13 条（含 `BEGIN IMMEDIATE` 双写者并发、`git ls-files` 枚举出的"无人可达"断言、
以及触发器绕过应用层直插）在 **Linux runner** 上也已经过一次绿，
不只是我这台 Windows 机器上的读数。

**自查出来的一处小不一致，登记而不是顺手改。** 同一条"一个条目只能有一个后继"的规则现在有两句话术：
应用层共用校验（`src/design_lab/knowledge_library.py:516`）会**点名**当前那个后继编号，而给抢锁失败者的
兜底（`:592`，把触发器的 `IntegrityError` 翻译成同一个 409）只说"已被另一条替代"、没把编号带出来。
状态码与 code 一致，差别只在后者少一个可操作信息。本轮**不在这趟推送里改产品字节**——§5.75 记的是
已经过 CI 的那个 head，往里塞未验证的改动就是 §5.59 那次"引了变更之前的 SHA"的重演。
下一刀：兜底路径补一次查询把后继写进 `detail`，并加一条真的抢锁输一次的用例。
### 5.76 收口脚本自己造出的红：回执写进了账本，文件却没进提交

**CI 是唯一的见证人，这本身就是缺陷。** run 40338742258（head `4dc59349`）红两个作业步骤，逐字是
`VERIFY_ROUTE_PAYLOAD_CONTRACTS=FAIL bindings=57 failures=1`、
`ERROR: evidence-projection: NOTHING_TO_COMPARE … ROUTE_REFUSED /api/evidence-projection -> 500
{'error': 'EVIDENCE_LEDGER_REJECTED', 'detail': ["[Errno 2] No such file or directory:
'/home/runner/work/DESIGN-LAB/DESIGN-LAB/design-lab/evidence/current-execution/task-artifacts/
kb-20261026/dl-final-t04-exact-sha-ci-matrix-20261026.json'"]}`、
`CURRENT_EXECUTION=FAIL [Errno 2] …` 与 `VERIFY_DESIGN_LAB=FAIL total=77 failed=2`。

**成因在工具，不在数据。** §5.75 那枚回执由收尾脚本与账本行同一次写出，但脚本暂存的是
`git status` 里 ` M` 的路径——**新文件是 `??`**，于是账本行进仓、它指的文件留在工作树。
本地永远看不出问题（文件就在盘上），干净 checkout 里它不存在。这条正是本仓闸门自己的读法：
它们按账本重算 tracked 工件的摘要。修法三层：
① 把 `??` 纳入收尾脚本的暂存集，并在推送前加一道"账本里每一条非 `.project-local` 工件必须
在 git 索引里"的硬检查（本轮 316 条现数全在）；
② 把这条检查落进测试：`test_evidence_artifact_presence` 新增两条——全量扫一遍账本、外加一枚
植入（指一个不在索引里的工件路径必须被定罪，同时 `.project-local/**` 的豁免不许扩大成红）；
③ 回执本身补提交在 `53cdc7eb`。**为什么不在本地先发现**：因为"存在"与"被交付"是两个不同的
谓词，而我此前只测了前者。

**本轮实测。** `Ran 7 tests in 5.662s OK`；聚合在最终字节上重跑见 §5.75 之后那一次推送的结论。
### 5.77 §5.76 里我自己登记的那条小不一致已修：兜底拒绝也点名后继

规则「一条条目最多只有一个后继」现在有两句完全一致的拒绝话术。共用一个格式化函数
`_superseded_detail()`，应用层校验与 `sqlite3.IntegrityError` 兜底都走它；此前兜底只说
"已被另一条替代"，把最有用的那件东西——**是哪一条**——留给了守门的那句。最需要编号的恰恰是抢锁输掉的那个
调用者，因为它以为自己还是第一个。

**用例是刻意走到兜底的，不是等竞速等来的**：把 `_supersedes_guard` 临时置空再写第二次，让数据库触发器成为
唯一拦得住它的东西；断言里既要求 409/code 一致，也要求 `detail` 出现那条后继 id，还要求两条话术逐字相等，
最后回读库里仍然只有一个后继。**反证**：同一用例打在修改前的 `ac97cc71` 上判红
（`AssertionError: … not found in … already superseded by another entry`），在修复后的字节上
`Ran 27 tests in 3.246s OK`。

这一条不新增尺子，只把上节自己记下的债还掉；容量项与 CSV 安全模式仍按 §5.73 的说法归 owner
（那句"待决策"写在 §5.73 的「仍未做完的」段里，§5.76 谈的是回执未提交，没有做过这项归属）。

### 5.78 收口面自己被人审了一遍：三处指错的节号、一个在散文里腐烂的数，和一次仪器冤枉无辜脚本

**这轮新写的三处交叉引用全都指错了地方，全部按"读目标"改正（提交 `f493ad2f`）——其中一处是上一轮那次
"已验证"的改正本身。** §5.73 把逐路由 `LISTROWS` 现读表写成在 §5.67，实际在 **§5.66**：那节正文就是
`LISTROWS list_routes=18 bounded=10 without_limit=8` 加每条路由的 `client_calls`，而 §5.67 是几何那把尺的
色板表；接续提示词抄了同一个错数。上一轮那条提交信息写着「Verified by reading the target: 5.67 holds the
table」，**它读的是另一节**——凭印象的"已核验"比没有核验更危险，因为它让下一个读者不再检查。§5.75 把上一次
并集读数写成"§5.72 那次记下的 3397"，而 §5.72 全文没有这个数；真实出处在 run 40315188651（head `5d603fe6`）
Python gate 作业日志里逐字的 `PYTHON_TESTS_UNION=OK expected=3397 distinct=3397 ran=3397`，也正是同一次作业里
`test_evidence_artifact_presence…test_tracked_artefacts_of_the_real_ledger_all_read_back` 定罪漂移钉 65→66 的
那一次，所以现在引用点名到 run，不再挂在一节没有说过的话上。§5.77 把"容量项与 CSV 归 owner"推给 §5.76，
而 §5.76 讲的是回执没提交，那句归属只在 §5.73 的「仍未做完的」段里。

**一个数在散文里腐烂，而登记面对它的条目一直是对的。** `UNBOUNDED_REGISTER` 现在 8 条，仪器也报
`without_limit=8`（`test_the_unbounded_set_is_exactly_the_register` 钉住这个等式），但 §5.66 与接续提示词都还
写"其余 7 条"，`test_workbench_weight.py` 的类文档写"Nine of eighteen"——`_list_prompt_results` 套上信封那一刻，
这三句就被留在原地，而**没有任何一把尺读这三句**。修法不是把 7 改成 8 了事：给
`scripts/verify_documented_counts.py` 加 `unbounded_routes()`，用文本切 `UNBOUNDED_REGISTER = {` 到闭合 `}`
之间的一级键（不 import——这条闸在 node 作业的步骤里跑，那里没有 Pillow，约束是 §5.57 那次红留下的），
再加一条 CLAIMS，让提示词那句必须逐字等于 `**8 条无界路由**`。**先红后绿**：claim 加上、散文还说 7 的时候
`DOCUMENTED_COUNTS=FAIL claims=21 failed=1`，定罪行逐字
`FAIL docs/current/NEXT-AGENT-PROMPT.md: prose says nothing, measurement says 8`；散文跟上之后
`DOCUMENTED_COUNTS=PASS claims=21 route_views=24 cli=24 adapters=30 routes=88`。类文档那句数字被删掉而不是
改成 8——一个由闸负责现数的量，不需要第二份没人看的副本。复验：`Ran 22 tests in 2.821s OK`（weight 模块）、
`Ran 6 tests in 4.987s OK`（claim honesty 闸）。

**顺带纠了一处"把邻居的理由抄给这一条"。** §5.66 原来写 `_list_rights/_list_jury/_list_knowledge_candidates`
"是 Human Gate 与读回面——截断即隐藏决定"，但登记面自己给 `_list_jury` 的理由只是
`no bound and no measurement yet`：Human Gate 那句只属于 `_list_rights`，读回那句只属于
`_list_knowledge_candidates`。**改写一张理由表要逐行回表，不能照邻居的措辞。**

**owner 决策与工程项，这次按登记面逐条分开（提交 `2048cf2e`）。** 之前接续提示词把第 7 条剩余两项一句话推成
"未结且不是工程缺口"，等于把混合面整块交给 owner。按 `UNBOUNDED_REGISTER` 的原文分：`_list_design_systems`
由四名注册表天然有界（**没有活**）；`_list_or_read_assets` 成本在每行重校验（实测 199.59 ms 里 path+stat 59.0%、
两次图像解码 30.5%、hash 2.4%），**分页修不了**，真修法是写入时物化 `width/height/media_type`，属带迁移＋
precheck＋合同行的 state-schema 单独一刀；`_list_projects`（逐项目汇总）与 `_list_token_documents`
（空值语义须保列表）是**修法各不同的工程项**；`_list_jury`、`_list_research` 标着 `NOT MEASURED`，
**先补数再谈修法**；只有 `_list_rights`（分页即隐藏 Human Gate 决定）与 `_list_knowledge_candidates`
（导出是读回，截断即误报曾经 offered 过什么）真的要 owner 裁"封不封页"。CSV 安全模式继续是待决策项，与容量无关。

**仪器冤枉了一次无辜脚本，方向值得记。** 我在聚合闸（77 项）还在跑的时候编辑了同一份提示词，
`verify_projection_freshness` 用"跑前跑后各取一次哈希"的比较看到字节变了，就把罪名给了它最后运行的那支脚本，
逐字 `FRESHNESS-CHECK-WROTE scripts/deepseek_registry_ssot.py --check modified
docs/current/NEXT-AGENT-PROMPT.md`。树静止后单独重跑同一把闸：
`VERIFY_PROJECTION_FRESHNESS=OK records=14 verified=21 receipts=7 excluded=0 findings=0`，且跑完 `git status`
干净——既不是写侧缺陷也不是数据问题，是我在同一棵树上边跑边改，而**这把闸的归因方式（"最后跑的那支"）
不足以定罪**。边界写清楚：并发期间看到的任何红都是未归因的，先让树静止再重测那一项。

**§5.76 末句那个前指现在有了名字。** run 40346676032（event=pull_request，head `5580f184`）
**conclusion=success**，逐字取作业自己的日志：

```
PYTHON_TESTS_SHARDS_START shards=3 expected_tests=3415 plan=none (index %% n)
PYTHON_TESTS_SHARD_RESULT shard=1/3 exit=0 tests=1094 wall_seconds=412.772 outcomes={'PASS': 1082, 'SKIP': 12}
PYTHON_TESTS_SHARD_RESULT shard=2/3 exit=0 tests=1101 wall_seconds=63.216 outcomes={'PASS': 1091, 'SKIP': 10}
PYTHON_TESTS_SHARD_RESULT shard=3/3 exit=0 tests=1220 wall_seconds=298.104 outcomes={'PASS': 1215, 'SKIP': 5}
PYTHON_TESTS_UNION=OK expected=3415 distinct=3415 ran=3415 duplicates=0 missing=0 unexpected=0
VERIFY_DESIGN_LAB=OK total=77 failed=0
BROWSER_E2E ran=44 skipped=0 failed=0
```

相对 §5.75 记下的 3412 净增 **3** 条，逐条对得上：`53cdc7eb` 给"工件必须在 git 索引里"加了两条，
`7b9a4f37` 给兜底话术加了一条。同一 head 的 push run 40346664251 是 success，但它只跑轻闸（11 个重作业
`skipped`），所以本节只能引那条 PR run。**边界**：这条 run 承载到 `5580f184`，`2048cf2e` 的计数闸与本节的
字节在它之后——那一段的结论按同一条规矩由下一轮读回，本节不替它宣称绿。

**owner 点名要读的那两个 run（`83448333`）也已逐字节读完，答案与"有没有红"不同。** push run 40328665473
success（只有轻闸）；PR run 40328675340 **cancelled**——8 个重作业已 success，但 `Python gate`、
`Workbench browser E2E` 与 `CI artifact proof` 三个作业被后来的推送取消。按本仓自己的规矩（cancelled／skipped
的必要作业不能算通过），**那个 head 上从来没有过套间结论**，不存在"就地修到它绿"这一步；结论只能在承载字节的
后续 head 上补读，就是上面那条 `5580f184`。

**收口面现数（不是引用）。** `currentExecution.evidence` 318 条（本节这条之前），其中 20261026 日期 21 条；
21 条里每条 `artifact_path` 都在 git 索引里，且 `artifact_sha256` 与 HEAD blob 逐字节相等（不匹配 0 条）；
`reports/current/DEEPSEEK-AUTHORITY-CHAIN.json` 现publish `evidence_receipts: 318`；直方图
`34 FROZEN_DEFERRED / 13 DONE / 2 PARTIAL / 1 NOT_STARTED`，旧 34 项一字未动；
`src/design_lab/http_service.py` 现数 `17` 个 `_list_*` 处理器（§5.73 引的就是这个数）。审计 7 条的六枚回执
（`kb-02-supersedes-fork-refused-on-both-routes`、`kb-06-body-phase-deadline-and-cancel`、
`kb-06-knowledge-form-one-refusal-per-field`、`dl-final-t04-receipt-identity-and-separation`、
`dl-final-t04-report-path-outside-repo`、`dl-final-t04-session-link-source-answered-from-the-row`）
逐条对回 `022c5a9b`／`f12931bf` 的 subject，全部 PASS。

**本节写下之后，承载它的 head 也已经读回了。** run 40350069509（event=pull_request，head `8190527d`）
**conclusion=success**，10 个作业全绿，逐字 `PYTHON_TESTS_SHARDS_START shards=3 expected_tests=3415`、
`PYTHON_TESTS_UNION=OK expected=3415 distinct=3415 ran=3415 duplicates=0 missing=0 unexpected=0`、
`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=44 skipped=0 failed=0`；同 head 的 push run
40350057037 success，但只跑轻闸。**用例数与 `5580f184` 相同（3415）是预期而不是巧合**：这几提交加的是登记件、
回执与散文，没有新增断言——所以这两条 run 的差别只在字节身份，不在测试人口。**同一条规矩对本句继续成立**：
本节这一段所在的那个 head 的 run 不在本节里，由下一轮读回；`main` 无分支保护
（`gh api .../branches/main/protection` → `Branch not protected`），所以合不合入完全是 owner 的决定，本轮没有合。

### 5.79 §5.78 刚读回绿，同一条浏览器尺在下一个 head 上自己红了一次：它在读一个还没渲染出来的状态

**红在哪，不在哪。** run 40352855984（event=pull_request，head `cf30ee05`）`conclusion=failure`，唯一红作业是
`Workbench browser E2E`，逐字 `BROWSER_E2E ran=44 skipped=0 failed=1`，红的那条是
`test_workbench_design_layer_e2e.WorkbenchDesignLayerE2ETests.test_design_layer_slice_in_real_browser`；
同一次跑的 `Python gate` 是 success。**产品字节一个都没动**：`8190527d → cf30ee05` 之间只有卷宗、接续提示词、
登记件与投影；同一把闸在 `8190527d` 上读到的是 `BROWSER_E2E[test_workbench_design_layer_e2e] ran=2 skipped=0 failed=0`。

**成因写在它自己的失败行里。** 逐字
`E2E_ASSISTANT_PLAN_DUPLICATE: status="以上内容取自 aplan-bbec54… 的 r2：保存会新建一条方案（编号由服务铸造）…"
answer={"revision":1,"id":"aplan-b5d27f…"} writes=5/5`——服务已经返回新方案与 r1，写入计数也确实进了一位
（`5/5`），**可被读出来的是提交前的提示语**。`apps/workbench/shell.ts:6236` 那句确认文案由 `afterWrite()` 写，
而它在页面自己的 POST promise settle 之后才跑；闸用 `waitForResponse(/assistance-plans$/)` 拿到响应就
`innerText()`，读到的是渲染还没跟上的一帧。与 §5.55 那次"CI 在补间中间帧里读到一帧谁都不存在的颜色"同族：
**量的是一页还没进入的状态**。

**修法只把"读"变严，不把"判"变松。** `design-lab/tests/e2e/browser_design_layer_e2e.mjs` 现在先等它该看到的
那句话——谓词要求 `#as-form-status` 同时含 `已复制为新的方案` 与那个 plan id（**与断言原本的两个条件逐字相同**），
25 s 到不了就把 `copySettled=false` 交回断言；定罪行多带一个 `confirmationRendered=`，让下一个读者一眼分得开
"确认从来没写出来"与"写出来了但没等到"。**这条闸仍然会红**：UI 若不写确认，等待超时 → `copySettled` 假 →
`copyWritten` 假 → `abort(..., 15)`。

**本机复测，以及本机证明不了的那一半。** `Ran 2 tests in 22.235s OK`，同一次跑写出的
`.project-local/task-artifacts/browser-e2e/browser-e2e-summary.json` 为 `result=PASS consoleErrors=0`；
`node --check` 干净，仓内自带的 `test_e2e_script_is_lint_clean` 过；`verify_evidence_artifact_presence`
的 7 条也过（改这个 `.mjs` 没有让漂移钉的 66 对变成 67 或 65）。**如实写**：本机这份 summary 里没有
`assistant` 字段，所以"四态那一段在本机被走过"不能由这份工件证明——它证明的是文件合规与本机不红，
逐段结论仍要从 CI 自己的 `E2E step:` 序列里读。

**承载这次闸改动的 head 已经读回：`751df4a0`。** PR run 40357134311 `conclusion=success`，12 个作业里
10 个 success、2 个 skipped（`Branch light gate` 与 `CI artifact proof`，都不属于本事件应有的作业），
逐字 `PYTHON_TESTS_SHARD_RESULT shard=1/3 exit=0 tests=1094 wall_seconds=558.435`、`shard=2/3 exit=0
tests=1101`、`shard=3/3 exit=0 tests=1220`、`PYTHON_TESTS_UNION=OK expected=3415 distinct=3415 ran=3415
duplicates=0 missing=0 unexpected=0`、`VERIFY_DESIGN_LAB=OK total=77 failed=0`、
`BROWSER_E2E[test_workbench_design_layer_e2e] ran=2 skipped=0 failed=0`、`BROWSER_E2E ran=44 skipped=0
failed=0`；同 head push run 40357121752 success 但 11 个重作业 skipped。**"四态那一段在这一跑里走过"
怎么证的**：绿跑不会打印 `E2E step:` 序列（包装脚本只在失败时回显子进程 stdout），但这条尺的每一步失败
都 `abort(..., 15)`，而 Python 侧断言的是子进程 0 退出与 `result=PASS` 摘要——所以这一段跑到末尾本身就是
"逐步没有红"的证明，不需要我看不到的一行标记。**留给下一轮的边界照旧**：本节这几句所在的 head 不在
`751df4a0` 那条 run 里，按同一条规矩由下一轮读回。

**§5.73／§5.74 里的每一处 `path:line` 也被逐条回读了一遍（这是 owner 收口点名要核对的那两节）。**
探针只扫这两节的正文、只从 `git ls-files` 解析文件名（从 `.` 起扫会走进 `.venv` 与 `node_modules`，
第一版就是这么挂住的）：6 处指针，**越界 0 处、无法解析 2 处**——那两处写成
`..._theme_affordance_gate.py:106` 与 `..._theme_geometry_gate.py:103`，用省略号开头的指针没法被任何机器
认，所以已展开成全路径并逐字读到那一行（三处都正好是 `report_path = evidence / '<本闸门自己的报告名>.json'`，
与那句话描述的"单一路径形状"对得上）。展开后重跑：**checked=6 unresolved=0 out_of_range=0**。
`§5.74` 引用的 `design-lab/schemas/state/design-lab-state-creative-v1.sql:116-124` 也回读过：那 9 行正是
`worklab_session_link` 的建表与 `UNIQUE (job_id, session_ref)`，也就是"写一次"的出处。
### 5.80 对抗性审计本轮自己：把刚修好的那把闸打回红一次，再把本轮写下的每条断言逐条反问

**为什么要这一节。** owner 的判据是"别把文档修订写成功能完成"；这一轮的反面风险是"别把修好了写成修好了"。
所以这一节不新增功能，只攻击本轮自己留下的断言。

**① 植入实验：证明 §5.79 那把闸不是被我改空的。** 把 `apps/workbench/shell.ts:6236` 的确认措辞
`已复制为新的方案 ` 改成 `复制完成 `（服务侧一字不动），`vite build` 后跑同一条浏览器尺：
`Ran 2 tests in 31.842s FAILED (failures=1)`，定罪行逐字带
`E2E_ASSISTANT_PLAN_DUPLICATE: status="…保存会新建一条方案…" answer={"revision":1,"id":"aplan-ddb0c767…"}
writes=5/5 confirmationRendered=false`。这一次实验同时钉住两件事：**闸仍能定罪**（真缺确认时它红，且烧掉
那 25 s 预算——31.8 s 对复原本地跑的 10.7 s 就是这个差），以及 **cf30ee05 那次红的形态与植入形态逐字同形**，
差别只在"等没等"——这正是 §5.79 归因的独立复现，不是我对那条日志的事后解释。复原不走 `git checkout`：
从改前的两份拷贝按 sha256 还原并校验（`shell.ts` `a3febac0…`、`build/main.js` `5cd4cc19…`，后者与 CI 自己
打印的 `bundleSha256` 同值），还原后 `Ran 2 tests in 10.741s OK`，`git status --porcelain` 无跟踪改动。

**② 指针回读到字节，不只是"行号没越界"。** §5.73／§5.74 的 6 处 `path:line` 现在每处都读到过内容：
`test_capability_library_clean_install.py:247` → `self.assertNotEqual(result.returncode, 0,`（正是 §5.73
更正段说的跨行调用形状）、`test_release_preflight.py:470` → `self.assertNotEqual(code, 0)`（那句"判的是
子进程退出码、不落回执"成立）、三条 `report_path = evidence / '<各自闸门名>.json'`（那句"单一路径形状、
没有第二个写入者"成立）、`design-lab-state-creative-v1.sql:116-124` → `CREATE TABLE worklab_session_link`
含 `UNIQUE (job_id, session_ref)`（§5.74 的"写一次"出处成立）。接续提示词里的 **36 个 `§5.NN` 引用全部
解析到真标题，悬挂 0**；§5.66 的标题确为"提示词读回现在是有界的一页"、§5.67 为几何色板表，与本轮改正
后的指向一致。

**③ 本轮写下的人话数字被反证过。** "3415 相对 3412 净增 3 条，来自 `53cdc7eb` 两条与 `7b9a4f37` 一条"——
用 `git show` 数新增的 `def test_` 行数：`53cdc7eb` = 2，`7b9a4f37` = 1，差值吻合。**没有把一次算术当作证据**：
先测人口再写原因。

**④ 收口面复数（把 §5.78 的读数推前，不让它悄悄过期）。** 账本 `currentExecution.evidence` 现数 **319**
（§5.78 写 318 是当时的读数，本节说明它为什么动），20261026 日期 **22** 条（原 21 条＋本轮那枚收口回执），
22 条的 `artifact_path` 全部在 git 索引且 `artifact_sha256` 与 HEAD blob 逐字节相等（不匹配 0 条）；
投影 `DEEPSEEK-AUTHORITY-CHAIN.json` 现publish `evidence_receipts: 319`；登记件行 5 由自家闸现读
`RECORD_REGISTER_GATE=PASS checks=5 problems=0`；直方图仍 `34 FROZEN_DEFERRED / 13 DONE / 2 PARTIAL /
1 NOT_STARTED`；`scripts/verify_current_execution.py` 在最终树上 `CURRENT_EXECUTION=PASS tasks=50`。

**⑤ 一处必须写下来的自我纠正（本轮我自己的跑法缺陷）。** 提交 `c46ef4b6` 的信息里宣称
`RECORD_REGISTER_GATE=PASS checks=5 problems=0`，而**当时那条命令并没有跑成**：它被写成
`python … | tail -1`，管道把退出码换成了 `tail` 的 0，于是 `&&` 链带着一条没跑过的闸继续走。
不加管道重跑之后 `REGISTER_EXIT=0` 且同一行读数成立，所以那句声明现在是测量而不是断言——
但成因如实记在这里：**管道吃掉退出码**这条教训本仓记忆里早已有一条（[[feedback-pipeline-exit-codes]]），
这一轮我又踩了一次，而且踩在了"用来自证一句话"的那条命令上。

**⑥ 新加的那把计数闸也被反证过人口方向，不只是散文方向。** 把一枚假的
`'_list_planted_probe'` 加进 `UNBOUNDED_REGISTER`（登记面 8→9，提示词那句一字未动），
`scripts/verify_documented_counts.py` 立刻 `exit=1`、`DOCUMENTED_COUNTS=FAIL claims=21 failed=1`；
按 sha256 还原那份测试文件后再跑 `exit=0`、`PASS claims=21 route_views=24 cli=24 adapters=30 routes=88`，
`git status --porcelain` 无跟踪改动。也就是说这条 claim 咬的是**人口**而不是我抄的那句话——
把界悄悄改回无界、或新加一条无界路由而不改散文，两侧都会红。

**⑦ 这一节没有证明的东西。** 本机 `browser-e2e-summary.json` 里没有 `assistant` 字段，所以四态那一段
"在 Windows 本机被走过"不由该工件证明（§5.79 已写）；植入实验证明的是**这把闸的读法**，不是真实宿主
E3、也不是真人 E4——两者仍是冻结项；`_list_rights` 与 `_list_knowledge_candidates` 封不封页、CSV 安全
模式、初始界 50 还是 100、150 KB 上限、`DESIGN.md` 批准与合格模型裁定仍归 owner；本轮没有发现需要
撤回的产品断言，撤回的只有我自己那句被管道掩过的自证与两处不可解析的指针写法。
**承载本节全部字节的 head 已读回：`0331b68f`。** PR run 40365602992 `conclusion=success`、push run 40365593987 `success`（只跑轻闸），逐字取作业自己的日志：
`PYTHON_TESTS_UNION=OK expected=3415 distinct=3415 ran=3415 duplicates=0 missing=0 unexpected=0`、`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=44 skipped=0 failed=0`、`EVIDENCE_ARTIFACTS=WARN tracked_broken=0`（漂移钉仍 66 对，改 `.mjs` 没有让它多出或少出一对）。
在它之前，`751df4a0`（第一次带这个闸修复的 head）的 PR run 40357134311 也已单独读回为 success（§5.79），所以代码字节被两条 run 各覆盖一次，不是借用。**唯一仍按规矩交给下一轮的**，是把这段读数写进文件的那次文档／登记件／投影提交本身——它是 derived-only，人口与判据都不会因它变化。
### 5.81 STITCH 画板包到了三天没人登记；登记之后，左栏与屏幕一第一次是照画板改的

**这条缺陷是 owner 问出来的，不是我查出来的。** 2026-10-27 owner 问「为什么还是网页的？不是让你一比一复刻 STITCH 界面吗？」，我先答"包里只有提示词文本，画板从未进仓"——**那句是错的**。包在 `D:\All projects\Record\stitch_design_lab.zip`：5,115,919 B，sha256 `ae76e90307bfcc429b5b11e13502e2a739ad69f7a3bc96a5a86f0cdc941eee03`，2026-10-24 19:31 投递，**14 块画板**（每块 `code.html` + `screen.png`）另加 `obsidian_studio/DESIGN.md`，解包 31 个文件 / 5,678,932 B。两处独立失误叠在一起：

- **资料到了没登记。** owner 2026-10-23 的规矩要求"来源、hash、版本/定态、别名和 canonical 位置，并更新固定资料索引"；这一包三天里没有 manifest 行、没有索引条目，于是它对项目不可见——任何下一位 Agent 都只能看见 08 那份提示词文本。
- **我的检索面漏了投递目录。** 我只搜了项目目录与两个资产目录就下"从未进仓"的结论。同一份卷宗里 §5.73 刚因为"探针匹配不到已知成员"被追正过，这次是我自己把"我没搜到"写成"它不存在"。**How to apply：** 断言某资料不存在之前，先证明探针覆盖了投递的规范入口（本项目就是 `D:\All projects\Record` 与 `docs/RECORD-ARCHIVE-INDEX.md` 两处），否则结论只是探针的空集。

**登记已补。** `docs/history/record-archive-2026-10-27-stitch-boards/ARCHIVE-MANIFEST.json` 逐成员记 name/bytes/CRC32/SHA-256（摘要从 ZIP 内的字节算，不从一份已解开的副本算）；原件与解包副本的 canonical 位置是 `.project-local/record-archive-2026-10-27/`，不随 Git 克隆，迁移须按摘要补齐。固定资料索引 `docs/RECORD-ARCHIVE-INDEX.md` 加 2026-10-27 日期节，**插在生成登记件那节的标题之前**——那节标题到 EOF 归生成器所有，追加在尾巴上会在下一次重绑时被吃掉（这条坑本仓早有记录，这次是照规则躲开的，不是又踩一遍）。

**以画板为基准量的第一条差异是骨架，不是配色。** 14/14 块画板的左栏都是「设计辅助／知识与提示词库／我的方案」三项加左下角设置；现界面是 24 项 4 组。08 原文逐字要求「只保留三个日常导航」。所以 owner 那句「你是不是又混合了旧版界面啊」是对的，而且错在整块外壳，不在细节。

**左栏收口（提交 `cbaee463`，PR run 40509435322 `conclusion=success`）。** 默认只露那三项 + 设置沉底，折叠时隐藏组标题，加「全部功能／收起次要入口」开关。**一条路由都没删**：`.app-nav-item` 的条数是浏览器 E2E 与 DESIGN.md 那句「导航 N 项」的现数对象，所以折叠只改显示——24 项仍在 DOM、`#/…` 仍可直达；当前路由若被折叠则自动展开，"侧栏保持活动路由可见"那条断言继续成立。

**屏幕一补了三处本地事实。** 需求框下加「清空 · N 字」与「Shift+Return 换行」；参考行加「已关联 N 项参考」。两个计数都在 `renderReferences()` 里重算，**不是只挂 `input` 监听**：载入已存方案与保存后清空都是程序改 `value`，不触发 input 事件，只挂监听会一直显示上一段文字的字数——与 §5.79 那条"等状态而不是等事件"同源。

**两处我没照画板抄，理由写在这。** ① 画板写「2 / 8 附件」，合同里没有 8 这个上限，报成 `N / 8` 就是让界面宣称一个不存在的产品约束；② 画板标题「这次想设计什么？」、主按钮「整理设计方向」与 08 原话「你想完成什么设计？」「整理方案」不一致——**以包内文本为权威**：画板是那次生成的产物，不是规格的第二份真值，而本仓反复判红的正是"把生成物当规格"。

**验证（本机，全部改完之后再跑）。** `tsc --noEmit` 干净；`npm run test:unit` exit 0（appshell 仍数到全部导航项）；债闸 9/9 OK——左栏那几条带来 4 处字面 px，DESIGN.md §4 是**按闸自己的读数重钉 521→525**（先红，报出它要的那句原话，再改文档，不手点数字），屏幕一这一片只用既有令牌，px 数没再动；对比闸 31/31 OK（新墨色 `--muted` + `--uif-font-micro`，珍珠白与炭黑两侧都量过）；主题几何闸 3/3 OK；溢出闸 4/4 OK（`Ran 4 tests in 390.858s`）；设计层浏览器 E2E 2/2 OK（四态与"复制为新的方案"那条链仍走通）。

**本节没有做的，别当已做。** 交付类型 chips（画板 5 枚；现控件是由服务读回填的 `<select>`，把同一个值做成第二个控件之前要先定"谁是状态主人"，否则就是本仓反复判红的第二台账）；附件 tile 的名称与大小（`references` 只有 kind+id，要联 `assets` 的元数据）；**缩略图**要开静态资源路由并放宽 CSP，那是 owner 的安全决定；画板顶栏那三个 Windows 窗口控制按钮在浏览器标签里没有真实现，**不画装饰件**——要真窗口壳就是交付形态变更，需要 owner 解除 release／安装态分发冻结。

### 5.82 折叠改了几何却没改提示：UI 审计闸抓到的第二条，与交付类型胶囊落地

**读数（本机，2026-10-27）。** 承载 `3a2b6565` 的那批慢闸里，溢出 4/4、对比 31/31、动效 1/1 都是绿的，
只有 UI 审计闸红，报三条：

```
nav-overflow: short: 1217px of nav hidden with no cue
nav-overflow: short: cue claims false but paints content=none at static
nav-drawer: narrow: 873px of drawer nav hidden with no cue
```

**根因是 §5.81 那条折叠的第二条后果，不是画板改动本身。** 提示（`.nav.has-scroll-more::after`）由
`syncNavCue()` 算，它只挂在 `scroll` 与 `resize` 两个事件上；折叠开合改变的是 `scrollHeight`，
**既不发 scroll 也不发 resize**，于是 `sync()` 把导航展开到 23 项之后，类名还停在折叠态算出来的
"下面没有东西"。1280x500 量到 1217px 被藏、380x844 抽屉里量到 873px 被藏——两条都是这一句
"提示说没有，其实有一屏"。这条缺陷在折叠之前不可能出现：那时 `scrollHeight` 只在挂载和窗口变化时变。

**修法**：`apps/workbench/shell.ts` 的 `setSidebarFold()` 末尾自己调一次 `syncNavCue()`，
并把 `syncNavCue` 从 `const` 箭头改成函数声明——挂载时那次 `setSidebarFold(false)` 发生在
定义之前，箭头会撞 temporal dead zone。两条都在代码注释里写明为什么是这个形状。

**这条红是有用的，别只当它被修好了。** 它证明 UI 审计闸确实量的是**看得见**的那条侧栏：
§5.81 把折叠挪到 `#app-sidebar .nav` 之前，这条闸在旧字节上是绿的（旧状态下折叠项全部露出，
提示与几何一致）。同一把闸先绿后红，说明它跟着真实几何走，不是跟着类名走。

**新增的守卫与它的反证。** `design-lab/tests/e2e/browser_design_layer_e2e.mjs` 加了
`the rail users actually see is the folded one` 一步，量 `#app-sidebar .nav` 的可见按钮数、
开合两次、并断言 `.app-nav` 在路由页仍然不可见。绿的时候的读数：

```
E2E_NAV_FOLD: {"total":23,"closedFirst":4,"opened":23,"closed":4,"hasFold":true,
 "legacyVisible":false,"groupsShown":0}
```

这一步自己先错过两次：前两次跑在窄视口（上一步是手机布局）与空 hash 的旧工作台视图上，
量到 `closedFirst:0`——`offsetParent` 在离屏抽屉里就是 null。那是**测量的前置条件**，不是产品缺陷，
所以这一步现在自己把视口设成 1280x800、把 hash 设成 `#/knowledge`、并等 `knowledge` 那颗按钮真的可见。
把折叠改成"什么都不隐藏"（`is-folded` 永远 false）之后，这一步按预期变红：

```
E2E_NAV_FOLD_INERT: folding hides nothing, or 全部功能 does not restore every route:
 {"total":23,"closedFirst":23,"opened":23,"closed":23,"hasFold":true,"legacyVisible":false,"groupsShown":0}
```

还原后同一把闸回到上面那条绿读数。守卫不是"跑过了"，是**能打回的**。

**交付类型胶囊（§5.81 留下的第一条）。** 画板 `design_lab_2` 把这一排画成胶囊，
标题是「希望准备的材料（多选胶囊，非强制全部）」；08 第 9 行的原话是「输出类型选择」。
两条不冲突——胶囊就是"选择"的一种控件形态——所以按画板做。冲突的是**基数**：合同里
`output_type` 是单值，画板那排是多选。改成多选要么一次提交发 N 个请求，要么动那份闭合的读回
schema，两件都不是页面能自己决定的，所以这里是一组 `radio`（一组选一个），并把画板那句
"多选"留在本节而不是实现里。§5.81 问的"谁是状态主人"就此回答：**DOM 里被勾选的那颗 radio 是唯一的
状态主人**，`<select>` 整个删掉，不留第二台账。词表仍全部来自服务：一条都没读回时一个胶囊都不画，
只写「输出类型未读回」，主按钮照旧禁用；读回后一个都不预选。控件用真 `input[type=radio]`
而不是可点的 `div`：键盘方向、无障碍名、以及触控目标尺寸闸量的都是这个原生元素。

**跟着改的断言。** `#as-output-type` 从 `select` 变成 `radiogroup`，E2E 里所有
`selectOption(...)` 改成勾选对应胶囊；首屏形状那条从"三个 select"改成"两个 select + 一组六个胶囊、
`role=radiogroup`、预选数 0"——这条断言原来就是 08 那句"只展开本次必要字段"的渲染形状，
改的是形状不是意图。

**胶囊落地后的读数（本机 `0e3e5b5f`）。** 五把浏览器闸一次跑完：设计层 E2E `Ran 2 tests OK`、
UI 审计 `OK`、对比 31/31、溢出 4/4、主题几何 3/3，全部 EXIT=0。首屏形状这一步现在把**它接受的那个形状**
打出来，绿跑不再只留一个 OK：

```
E2E_ASSISTANT_INITIAL: {"selects":["as-workspace","as-reference-select"],"toolish":[],
 "chips":["IMAGE","UI","MOTION","STORYBOARD","AUDIO","CAMPAIGN"],"chipGroup":"radiogroup",
 "preselected":0,"canvases":0,"logs":0}
```

`preselected` 这一条不是装饰：在挂载处补一句"默认选第一项"（一个看起来很合理的改动）之后，
同一步按预期变红，读数里是 `"preselected":1`。也就是说"一个都不预选"是**能被反证的断言**，
不是一句写在注释里的愿望。词表那六个值也是这一次量出来的：它们来自服务读回，页面一个都没抄。

**顺手清掉的一处旧注释**：`syncNavCue` 上面那段本来写着"ROUTE_VIEWS 里的 21 个目的地"，
而同一段下一句就说"这里故意不写数字，任何手点的数字都会变成假装是实测的旧读数"。
真实条数由路由闸现数（`route_views=24`），注释里那个 21 已经不对，所以把它去掉而不是改成 24。

**胶囊落地后又被自己的眼睛推翻的一次：`0e3e5b5f` 的胶囊是坏的。** 那五把闸（E2E、UI 审计、对比、
溢出、主题几何）在胶囊落地后全部 EXIT=0，于是把界面**渲染出来看了一张图**：六个标签里四个被压成
**一字一行的竖条**（chip 盒子 `56x90`，行顶只有两个不同值），因为 `.as-chip` 是 flex 项又没有
`white-space:nowrap`，标签被挤窄后按字断行。所有闸都看不见它——盒子仍然装得下、颜色仍然过 AA、
容器仍然不溢出。**这是"绿色不等于对"的又一次实测**，也是本仓那条"文本换行不是裁切，要数行框"
规矩的第三次应验。修法两处：`.as-chip{white-space:nowrap;flex:0 0 auto}`（`9e739f82`），
以及把**行框计数**写进首屏那一步的断言里：

```
E2E_ASSISTANT_INITIAL_SURFACE: {..., "preselected":0, "multiLineLabels":4, ...}   ← 修复前的字节，红
E2E_ASSISTANT_INITIAL: {..., "preselected":0, "multiLineLabels":0, ...}           ← 修复后，绿
```

先在新断言下跑**旧字节**拿到 `multiLineLabels:4` 的红，再改 CSS 拿绿——这条控制不是走过场：
没有它，"我加了个断言"和"那个断言能看见这个缺陷"是两件事。修完再截图确认一次，六个胶囊
两行排开、每个一行字。**渲染一次是这一轮最便宜的闸**，后续每一片新界面都要付这个成本。

**CI 账（读回的，不是推断的）。** `9b376ac4`（登记画板包那一轮）的 PR run 40513197163
`conclusion=success`，10 个非 skipped 作业全绿。`5388b62f` 的 PR run 40526168978 在跑的过程中
被 `9e739f82`（胶囊换行修复）取代——**这不是取消，是自己认下那一版字节是坏的**：承载坏字节的 run
就算绿也不该当作交付读数，所以本轮的 Canonical Verify 只在 `9e739f82` 及之后读。
中间那几个 head（`3a2b6565`…`5e52fa97`）没有各自推送过，因此没有各自的 run；
它们的字节由最终 head 的那一条 run 覆盖，这一点在接续提示词里也照这样写，不写成"每个 SHA 都验过"。

**本节没有做的，别当已做。** 附件 tile 的名称与大小这一步**不是"没有数据"**：库里 `f.path` 与 `f.byte_size`
都在（`src/design_lab/native_assets.py:25,37` 就 SELECT 了它们），是 workbench 读的那一行
`AssetRecord`（`apps/workbench/contracts.ts:37-47`）没带出来。所以这一步的真实形状是
"加宽那份读回投影 + 补它的路由合同行"，而不是"再发一次请求去联表"；在投影加宽之前，
tile 只能显示 `media_type · W×H`，画板那行「2.4 MB · 字体排印样张」不能照抄——照抄就是让界面
宣称一个它没读到的事实。缩略图（要开静态资源路由并放宽 CSP，owner 的安全决定）、
画板首屏的两栏版式（「最近编辑的方案」现在在首屏，但是在表单下方而不是右栏）、
以及画板顶栏那三个 Windows 窗口控制件（浏览器标签里没有真实现，不画装饰件）
仍是上一节就写明的边界，本节没有推进，也没有宣称推进。

### 5.83 一条 CI 红里其实有两个缺陷：登记件被我自己写旧了，复制方案的种子在慢机器上追不上提交

`5388b62f` 的 PR run 40526168978 **completed failure**，四个作业红。本节把两条根因分开写，
因为它们不是同一件事，修法也不是同一处。

**其一：归档登记件（row 5）过期——这是流程缺陷，不是内容缺陷。** CI 逐字：

```
RECORD_REGISTER_GATE=FAIL checks=5 pathish_named=21 problems=5
PROBLEM row 5: blob SHA-1 claim e2987b2f3331 vs 2663e461782b
PROBLEM row 5: bytes claim 419,586 vs 425,392
PROBLEM row 5: SHA-256 prefix claim 6a24555e8a67c18f vs f6280583c8a0bc5b
```

登记件钉的是**卷宗在 HEAD 上的 blob**，而我在同一个提交里把 §5.82 写了进去却没有重生成登记件。
本地那次 `RECORD_REGISTER_GATE=PASS` 是真的跑过，但它跑在**卷宗被改动之前**——我引用的是"我改文档前
的那次读数"，不是"承载这些字节的提交"的读数。这一类缺陷本仓已经记过一次（§5.80 的"绿闸覆盖的是偶然字节"），
这次是它的镜像：**绿闸覆盖的是旧字节**。规矩要改成一句可执行的话：**登记件的重生成必须是收口的最后一步，
而且要在提交之后再跑一次闸**，否则它验的永远是上一个提交的字节。

**其二：`E2E_ASSISTANT_PLAN_DUPLICATE` 在 CI 上红、在本地绿——这是测试自己的竞态。** CI 的读数是
`writes=5/5 … confirmationRendered=false`，状态格里是**种子提示**那句
「以上内容取自 aplan-… 的 r2：保存会新建一条方案」，而不是保存后的确认句。
下载下来的 `fail.png` 显示新方案确实建出来了（详情面板在屏、r1、记录人 E2E Copier）。
把代码对上就清楚了：`#as-duplicate` 的点击走 `startDuplicating()`，那是**一次异步读**，读完才由
`openFormFor()` 把内容灌进表单并写状态（`shell.ts:6139`）；而测试在点击之后**立刻**填记录人、点提交。
本机种子赶得上，CI 慢一点，提交先落地、种子后落笔——确认句被自己前面的提示盖掉，
断言等的那句话于是永远不出现。**产品没有写错，测试在拿一个还没成形的表单去提交。**

**修法**：点击之后先等"表单里真的有源方案的内容、状态格里真的有那句种子提示"，再提交
（`E2E_ASSISTANT_DUPLICATE_NOT_SEEDED` 是等不到时的独立失败名，不把它算成复制成功）。
同一族的守卫在修订那条路上早就有（先等按钮变成「保存为新修订」再提交，`browser_design_layer_e2e.mjs:1094`），
复制这条路是漏掉的那一条——**同一个等待语义，两处只写了一处**。

**顺带记一张图**：CI 的 `fail.png` 里所有中文都是豆腐块（□□□），因为 runner 上没装 CJK 字体。
这不影响断言（断言读的是 DOM 文本，不是像素），但它说明**CI 截图不能当视觉验收的证据**，
也不能反过来用本机截图替 CI 作证——两边量的是不同的东西。

**还有一处 LOGO 是真的没有：浏览器标签页。** 把三个面都渲染出来量了一遍（`.project-local/task-runtime/nav5-brand.txt`）：
冷启动页 `.app-nav-mark` 22x22 在画、路由页 `.brand-mark` 48x48 在画，两处的字标都是文本 `DESIGN-LAB`；
但三个面的 `link[rel~="icon"]` 读数都是 `NONE`——**标签页上没有任何图标**，只有 `tab:"DESIGN-LAB · 工作台"` 这行标题。
这一条不在"画板与现界面的差异"里，因为画板是桌面壳、根本没有标签页；它是**交付形态是浏览器**才暴露出来的缺口。

**为什么这一轮没有顺手补上**：图标必须自己带一份图形字节。仓库里那枚字标是 `style.css` 中按
`brand-mark:begin sha256=…` 钉住的两份编码，同步由 `render_brand_asset.py --check` 这一把闸管着
（`test_workbench_brand_asset.py` 的文档串写明"若哪天加了资产路由，这把闸要说话"）。
标签图标要么再嵌一份 SVG（第二份字节的出处与漂移检查得并进同一把闸），要么开静态资源路由
（正是那把闸现在会拒绝的方向，且与缩略图同一族：要动 CSP 与 `workbench.py` 的三路径白名单）。
两条都能做，但都需要先把"第二份图形字节"的规矩定下来，**不该在一轮收口的尾巴上先塞进去再补闸**。
下一步按第一条做：由 `render_brand_asset.py` 从同一份被跟踪的矢量派生 favicon 的字节、
用同样的 `begin sha256=` 记号钉进 `index.html`，`--check` 同时覆盖 CSS 与 favicon 两处。

**同一条 CI 里还有第三个绑定被我的落账动作挪动了：权威链记录。** `DeepSeek authority gate chain`
作业红在本机可复现，逐字是 `AUTHORITY_CHAIN=DRIFT entries changed since generation:
['design-lab/config/task-ledger-r3.json']`；把存的那条与现生成的那条逐键对比，动的只有
`ledger.evidence_receipts = 321 -> 322`——**回执条数本身就是链记录的一个字段**，所以每落一条回执，
链记录就必须重生成一次。`--check` 只豁免 `mutable_state` 条目的 `bytes`/`sha256` 两个键，
嵌套的 `ledger` 子对象是逐字比的，这不是豁免漏了，而是"回执数"确实是一句要重新说的话。
重生成后 `AUTHORITY_GATES=PASS gates=7 failed=none`。

**这一轮因此把收口顺序钉成一句话**（写进接续提示词，不再靠记）：
**卷宗/提示词改完先提交 → 重生成归档登记件 → 重生成权威链记录 → 重生成现行投影 → 跑闸 → 再提交 → 推送 → 读 CI**。
登记件、权威链、投影三样都是**被绑定字节的派生物**，任何一处文档或账本动过，三样都要按这个次序重算；
顺序错了就会像本轮一样：本地每个闸都各自绿过，CI 在承载全部字节的 head 上把它们一次跑红。

### 5.84 承载全部字节的 head 上，CI 一次跑绿：逐字读数与"哪两条红是同一个根"

**`19ffd0d1` 的 PR run 40537819918 `conclusion=success`**，10 个非 skipped 作业全绿
（`Branch light gate` 与 `CI artifact proof` 按设计 skipped）。逐字：

```
PYTHON_TESTS_UNION=OK expected=3415 distinct=3415 ran=3415 duplicates=0 missing=0 unexpected=0
VERIFY_DESIGN_LAB=OK total=77 failed=0
BROWSER_E2E ran=44 skipped=0 failed=0
  BROWSER_E2E[test_workbench_design_layer_e2e] ran=2 skipped=0 failed=0
  BROWSER_E2E[test_workbench_ui_audit_gate]    ran=1 skipped=0 failed=0
  BROWSER_E2E[test_workbench_overflow_gate]    ran=4 skipped=0 failed=0
  BROWSER_E2E[test_workbench_contrast_gate]    ran=31 skipped=0 failed=0
```

**四条红其实只有两个根，而且三个是同一个自己造成的类。** `5388b62f` 那次四作业红里：
登记件旧（§5.83 其一）、权威链旧（§5.83 其二，从测试面看就是
`test_language_boundary_check_mode.ChainEncodingTests.test_the_chain_completes_on_a_gbk_console_and_writes_no_tracked_file`
这条红——**同一个陈旧派生物从两个面各报一次**）、Python 作业红也是同一条链记录；
只有浏览器 E2E 那条是真的产品测试竞态（复制种子），它在 `924af2fb` 上单独转绿——
那两个 head 之间该作业唯一变化的就是这一处等待，所以**修复被 CI 自己证明了，不是我说的**。

****这条 run 之后还有两条同码的收口 run，也都读回了。** `28a14b93`（第 323 行回执 + 三份派生物重绑）
的 PR run 40542844974 `conclusion=success`，逐字 `PYTHON_TESTS_UNION=OK expected=3415 … ran=3415`、
`VERIFY_DESIGN_LAB=OK total=77 failed=0`、`BROWSER_E2E ran=44 skipped=0 failed=0`；
它之后的 `c5c77889` 只动接续提示词里那一句"待 owner 裁"的清单。
`c5c77889`（只动"待 owner 裁"那一句清单）的 PR run 40546651758 同样 `conclusion=success`。
**留给下一轮的第一件事**：读 `cf5b0203` 之后那一条 run——本轮已经把能读的都读回并写在这里，
而某条 run 的结论不可能住进它自己承载的那段字节里，这是这套绑定方式的固有形状，不是欠账。

回执 `dl-final-t04-closed-head-read-and-three-bindings-rebound-20261027`（账本第 323 行）**
钉的就是这一轮读回所依据的字节。它同时把"哪些不是本轮交付"写进 `not_claimed`：
`3a2b6565`…`5e52fa97` 没有各自推送过，因此没有各自的 run——它们的字节由 `924af2fb` 与 `19ffd0d1`
两条 run 覆盖，这句话不许被读成"每个 SHA 都单独验过"。
