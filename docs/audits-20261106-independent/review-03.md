# 独立复审第 03 轮（复审者原文，逐字摘录）

工具：codex.cmd（`codex-cli 0.167.0-alpha.3.2`）——与被审代码的作者是不同上下文、不同进程。
运行沙箱：`workspace-write on a detached clone (the clone IS the subject; the main checkout is not writable to the reviewer)`；复审者进程 exit code：`0`。
复审结束后，被审克隆自身 dirty `17` 字节（不算 `.sandbox-tmp` 沙箱临时地时为 `0`），克隆 HEAD `ccd07812268d12607d51ddfe0b38e074432f6920`；主检出 HEAD `ccd07812268d12607d51ddfe0b38e074432f6920`，复审结束后主检出 dirty `0` 字节。
本文件不含改写：下面是复审者自己打印的报告，起止由脚本在原始 stdout 里定位；完整 stdout 留在 `.project-local\edits-20261106a\REVIEW-03-raw.txt`（运行产物，不入 Git）。

结论：FAIL。已发现两个阻断问题；本轮仍有未完成验证，不能据此声明全部复审完成。

被审 SHA：`ccd07812268d12607d51ddfe0b38e074432f6920`，由本克隆 `git rev-parse HEAD` 现读。

1. **HTTP 与能力测试**：执行指定六个测试文件的组合 pytest，结果 **76 passed、7 failed，53.98s**。五个设计资产测试返回 `PROJECT_STORE_UNAVAILABLE`（503）；一个 raster 测试因克隆内长路径 `FileNotFoundError` 失败；一个真实离线构建测试因预期的 `VITE_ABSENT` 失败。后者记为环境不具备，不算仓库缺陷。staleness 回执确实调用 `binding_rules.staleness_assessment`，`STALE` 仍追加 `RESULT_STALE`。小游戏元素与九条复制记录的独立对账未完成。

2. **非法复审记录——阻断**：在 `.sandbox-tmp/illegal.json` 写入 `reviewed_sha = ffffffffffffffffffffffffffffffffffffffff`，直接调用 `independent_review_for('F01')`，实际输出：
   ```
   ILLEGAL_RESULT: PASS @ ffffffffffff（planted 现读 now；逐项见 fake）
   ```
   函数接受了非法历史 SHA，没有拒绝或具名报错。

3. **workbench**：正确执行 `scripts/check_workbench_bundle_drift.py`，得到 `VITE_ABSENT`，没有 traceback。工具现算提交摘要与登记期望均为 `1a2d735c338da30d40a95f9aef5b5760882f654d6abbd8305dba26fe00b7ac12`。临时将 `COMMIT_BLOB_ABSENT` 改为 `DRIFT` 后，v33 实测 **2 failed、7 passed**，对应行为节点与名称集合节点均变红；已逐字节恢复。十种判定逐支覆盖核对未完成。

4. **入口与寄存器**：`check_project_current.py --check` 为 PASS、findings 0。两个 citation 检查均 `clean: true`、violations 0；原始命中分别为 broken 8、登记失效锚 1，均落入允许声明。

5. **census——阻断**：`build_test_census.py --check` 返回 rc=1，发布 **605 tests / 40 files**，现算 **0 / 0**。源码使用完整绝对路径的 `path.parts` 判断 `.project-local` 排除目录，因此这份嵌套克隆的所有测试被排除。不能把该检查报成通过。散文漂移与三节点逐个反例尚未完成。

6. **来源覆盖可移植性**：未设置来源根时实际输出：
   ```
   {"error": "SOURCE_REPO_ABSENT", "absent": [{"label": "work", "root": "D:\\All projects\\AI-WORK-LAB\\.project-local\\review-03\\run-20261106T234533-374\\WORK-LAB"}, {"label": "design", "root": "D:\\All projects\\AI-WORK-LAB\\.project-local\\review-03\\run-20261106T234533-374\\DESIGN-LAB"}], "verdict": "NOT_RECOMPUTABLE_HERE", "check": true, "note": "run this builder where WORK-LAB and DESIGN-LAB are present; the tracked registers remain the record of the run that could read them"}
   ```
   设置三个指定来源根后的进程已启动，但尚未取得完成读数，故第二腿未核实。即使第二腿通过，也只能证明这台机器具备来源根时可在该克隆重算，不能证明任意机器都能重算。

最终已观察到的 Git 状态只有 `?? .sandbox-tmp/`；被测脚本修改已恢复。`checks_actually_run` 按已取得结果的命令调用计数，包含一次误传 `--check` 的工具调用，不将它算成功验证。

INDEPENDENT_REVIEW_VERDICT: FAIL
reviewed_sha: ccd07812268d12607d51ddfe0b38e074432f6920
blocking_findings: 2
non_blocking_findings: 0
checks_actually_run: 10
unverified_claims: 7
