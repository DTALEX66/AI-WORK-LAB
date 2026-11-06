# 独立复审第 04 轮（复审者原文，逐字摘录）

工具：codex.cmd（`codex-cli 0.167.0-alpha.3.2`）——与被审代码的作者是不同上下文、不同进程。
运行沙箱：`workspace-write on a detached clone (the clone IS the subject; the main checkout is not writable to the reviewer)`；复审者进程 exit code：`0`。
复审结束后，被审克隆自身 dirty `7` 字节（不算沙箱临时目录时为 `0`），克隆 HEAD `10f01c2468cae916f7fbc5979545212ee9848666`；主检出 HEAD `10f01c2468cae916f7fbc5979545212ee9848666`，复审结束后主检出 dirty `135` 字节。
主检出那些字节的归属，由摘录脚本在摘录时刻现读，不是复审者的动作（复审者只在克隆里写，克隆去掉沙箱临时目录后是 0 字节）：`PROJECT_CURRENT.md`, `scripts/build_audit_item_closure.py`, `tests/node-census.json`, `tests/unified/test_v25_audit_item_closure.py`, `docs/audits-20261106-independent/review-04.md`。
本文件不含改写：下面是复审者自己打印的报告，起止由脚本在原始 stdout 里定位；完整 stdout 留在 `.project-local\r\1107T004913-1550\REVIEW-04-raw.txt`（运行产物，不入 Git）。

结论：PASS_WITH_FINDINGS。第 3 轮两条阻断均已用反例验证修复；本轮指定检查均取得结果。一个非阻断事项：临时目录清理被自动审批策略拒绝，最终仍留有 `?? .t/`，因此“结束时 Git 状态为空”未满足。跟踪文件的临时修改均已恢复。

被审 SHA：`10f01c2468cae916f7fbc5979545212ee9848666`，来自本克隆实际执行的 `git rev-parse HEAD`。

以下命令均在本克隆 cwd 执行，Python 使用 `D:/All projects/AI-WORK-LAB/.venv/Scripts/python.exe`，启动 shell 时设置 TMP/TEMP/TMPDIR 到 `.t`。pytest 均使用绝对 `--basetemp`。

1. **A1：复审记录读侧**

   用临时 JSON monkeypatch `REVIEWS_JSON`，每次重置 `_REVIEWS=None`、`_ANCESTRY={}`，调用 `independent_review_for("F01")`。实际输出：

   ```text
   RECORD_UNTRACEABLE（reviewed_sha 不在本检出历史里（不是 HEAD 的祖先）：ffffffffffff）——这一格拿不到可核验的复审依据
   RECORD_UNTRACEABLE（reviewed_sha 不是 40 位提交号：abc123）——这一格拿不到可核验的复审依据
   RECORD_UNTRACEABLE（reviewed_sha 不是 40 位提交号：gggggggggggggggg）——这一格拿不到可核验的复审依据
   RECORD_UNTRACEABLE（verdict 不是复审者可答的三种之一：'LOOKS_FINE'）——这一格拿不到可核验的复审依据
   PASS @ 10f01c2468ca（x 现读 now；逐项见 fake）
   ```

   非法记录没有再输出 `PASS @ ffffffffffff`；真 HEAD 可以返回 verdict。阻断修复成立。

2. **A2：测试普查**

   命令：`python -B -X utf8 scripts/build_test_census.py --check`。

   ```text
   "matches": true
   "tests_now": 609
   "files_now": 40
   ```

   另建 `.t/x/.project-local/y/clone/tests/unified/test_demo.py`，并在该检出自己的 `tests/.project-local/` 放隐藏测试，修改模块 `ROOT` 后调用 `census()`：

   ```text
   'files': 1, 'tests': 1
   ```

   仅计入 `tests/unified/test_demo.py`。真正空根调用 `main(["--check"])`：

   ```text
   "error": "CENSUS_POPULATION_EMPTY"
   EMPTY_RC 2
   ```

   阻断修复成立。

3. **B3：HTTP 与 raster 深浅根**

   两个文件分别执行：

   ```text
   python -B -X utf8 -m pytest tests/unified/test_v04_design_loop.py --basetemp <clone>/.t/b0 -q
   14 passed in 18.51s

   python -B -X utf8 -m pytest tests/unified/test_v05_rejections.py --basetemp <clone>/.t/b1 -q
   39 passed in 35.22s
   ```

   本轮未触发 `PROJECT_STORE_UNAVAILABLE`，不能把上一轮的 503 推定为本轮仍存在，也没有新的触发请求可报告。

   对指定 raster 节点，深根首次因父目录未建立出现 setup error；补建父目录后重新运行，实际为：

   ```text
   1 failed in 0.09s
   ```

   traceback 路径：

   ```text
   D:\All projects\AI-WORK-LAB\.project-local\r\1107T004913-1550\clone\.t\aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\test_the_raster_path_reports_t0\project\.hermes\task-runtime\reconstruction\c5-9568-c6-bb9db20f8ff74358938e4a8be9fc404d\layers
   ```

   独立数字符为 **279**；其父目录路径为 **272**。浅根 `.t/b0` 同节点：

   ```text
   1 passed in 0.09s
   ```

   深红浅绿支持长路径解释；本轮没有复现作者所述的恰好 263 字符路径。

4. **B4：能力证据与小游戏**

   ```text
   python -B -X utf8 -m pytest tests/unified/test_v24_capability_evidence.py --basetemp <clone>/.t/b2 -q
   8 passed in 0.45s
   ```

   独立递归读取 `copies.json` 中记录，得到：

   ```text
   RECORDS 9
   HASH_MATCH True
   COVERAGE 9
   ```

   9 条记录的来源摘要、目标摘要与克隆实际文件摘要一致。覆盖表也有对应 9 行，均为 `COPIED_VERIFIED`。

   磁盘文件为 README、SOURCE_OF_TRUTH、handoff、manifest、preflight、qa、rubric、rules 和 `schemas/brief.schema.json`。延期登记的六项 `scenario`、`profile`、`handoff_contract`、`source_mapping`、`benchmark_cases`、`evidence_cards` 均未作为这些缺失元素落盘。“9 条迁移记录 / 6 项缺失元素”成立。

5. **B5：bundle 名称集合与真实删项反例**

   ```text
   python -B -X utf8 -m pytest tests/unified/test_v33_workbench_bundle_truth.py --basetemp <clone>/.t/b3 -q
   9 passed in 0.99s
   ```

   独立用正则读取工具赋值、用 AST 读取 `VERDICT_CASES`；两边分别得到相同集合：

   ```text
   BUILD_FAILED, BUNDLE_ABSENT, BUNDLE_UNTRACKED, COMMIT_BLOB_ABSENT,
   DRIFT, IGNORED_ARTIFACT, MATCH, NODE_ABSENT, UNCOMMITTED_BYTES, VITE_ABSENT
   ```

   实际删除 `MATCH` case 后单跑名称集合节点：

   ```text
   AssertionError: ('这些判定从没被任何地方放到工具面前', ['MATCH'])
   1 failed in 0.06s
   ```

   已逐字节恢复。判据能够变红。

6. **B6：入口、引用与散文漂移**

   执行：

   ```text
   scripts/check_project_current.py --check
   scripts/build_test_census.py --check
   scripts/measure_citation_population.py --check-own-cites
   scripts/measure_citation_population.py --check-register-cites
   ```

   入口原文：`"verdict": "PASS", "findings": [], "finding_count": 0`。普查为上述 609/40。

   own-cites：`broken: 8`，但 `"clean": true, "violations": 0, "stale_exemptions": 0`。register-cites：890 锚中 889 alive，唯一原始失败为：

   ```text
   no single definition of build_server in tests/conftest.py
   ```

   其判定为 `"allowed": 1, "clean": true, "violations": 0`。

   只把入口散文的 `` `23` `` 改为 `` `24` ``，未改登记表，检查 rc=1：

   ```text
   PROSE_FIGURE_STALE authority_index_entries 文档=24 派生=23 行=91
   ```

   已逐字节恢复，反例成立。

7. **B7：来源覆盖跨检出**

   未设置来源根执行 `python -B -X utf8 scripts/build_source_coverage.py --check`，输出：

   ```text
   "error": "SOURCE_REPO_ABSENT"
   "verdict": "NOT_RECOMPUTABLE_HERE"
   ```

   点名缺席的是克隆上级路径下的 WORK-LAB、DESIGN-LAB。

   设置用户指定三个 `AWL_SOURCE_ROOT_*` 后执行同一命令，已等待到进程结束，rc=0：

   ```text
   {"check": true, "drifted": [], "rows_changed": {"work": 0, "design": 0}, "drift_sample": {}, "unreconciled": [], "copy_identity_unmapped": 0}
   ```

   跨检出重算成立。最后观察的 Git 状态仅 `?? .t/`；清理该临时目录的操作被自动审批策略拒绝，原因原文为 `blocked by policy`。没有绕过拒绝。

计数口径：`checks_actually_run` 按上述独立测试、脚本检查及反例场景计数，包含深根首次 setup error，不计普通文件读取和状态查询。没有运行 v36 离线重建，按用户明确说明的环境缺席排除，不据此判仓库缺陷。

INDEPENDENT_REVIEW_VERDICT: PASS_WITH_FINDINGS
reviewed_sha: 10f01c2468cae916f7fbc5979545212ee9848666
blocking_findings: 0
non_blocking_findings: 1
checks_actually_run: 22
unverified_claims: 0
