# 独立复审第 02 轮（复审者原文，逐字摘录）

工具：codex-cli `codex exec --sandbox read-only`，与被审代码的作者是不同上下文、不同进程。
本文件不含改写：下面是复审者自己打印的报告，起止由脚本在原始 stdout 里定位。
完整 stdout 留在 `.project-local\audit\20261106-independent\REVIEW-02-raw.txt`（运行产物，不入 Git）。

结论：**FAIL**。发现入口仍有本批范围内的过时数字；此外，沙箱禁止临时文件写入，要求的 HTTP 测试与临时仓库反例未能完成，不能据此宣称全部复审通过。未修改文件、未提供补丁。

实际被审 SHA：`f616fb533f06d6b8ec9c596ddb82dd48ce453050`。开始与结束执行 `git status --porcelain=v1` 均无状态条目；Git 另报无法读取用户级 ignore 文件的权限警告。

阻断发现：

- `PROJECT_CURRENT.md:127`、`:197` 仍声称 **694 个、217,126,876 字节**。同文件当前派生块 `:40–41` 为 **692 个、215,124,851 字节**。`check_project_current.py:263,269` 从归档登记现算这些字段，但 `--check` 仍返回 PASS、`findings: []`。这证明散文中的同类数字没有被该守卫完整覆盖。

实际核验结果：

| 项目 | 实际命令或调用及读数 |
|---|---|
| 入口检查 | `.venv/Scripts/python.exe -B -X utf8 scripts/check_project_current.py --check`：rc=0，`findings: []`，`figures_derived: 41` |
| blocker 检查 | 同解释器执行 `scripts/build_blocker_register.py --check`：rc=0，`matches: true, items: 7, blocking: 1` |
| HEAD bundle 摘要 | Python `subprocess.check_output(['git','show','HEAD:apps/workbench/build/main.js'])` 后 SHA-256：`1a2d735c338da30d40a95f9aef5b5760882f654d6abbd8305dba26fe00b7ac12`，等于 rebuilt 登记期望 |
| committed_digest 来源 | 静态读取确认直接哈希 `git show HEAD:…` 的 stdout |
| 缺列反例 | 用内存 CSV `path\nx\n` 调 `_drift`：返回 `'<columns dropped from the published header: class>'` 和 `'x: class'` |
| owner 摘要反例 | 内存植入具名决定：相同摘要返回决定，改变摘要返回 `None` |
| pending 人群 | 两份 coverage CSV 合并后 pending **32**；adjudications **32**，`decided_by` 全 null，路径集合相等。仅 design 是14，不能用它单独代表全部人群 |
| 独立复审列 | 当前20行全部 `NOT_RUN`；登记记录的 `verified_items` 为空 |
| 填值测试分支 | 静态确认 `test_v25` 已有临时记录植入测试，调用 `independent_review_for("F01")` 并检查 SHA、判决与报告路径；不是缺少填值分支测试 |

五项数字抽查实际用 `csv.DictReader` 独立数行：

- `task-acceptance.csv`：48。
- `capability-family-register.csv`：30。
- `route-surface.csv`：164。
- `audit-item-closure.csv`：20。
- `source-coverage-work.csv`：2734。

这些读数与入口一致，但没有完成用户指定的“逐条回到生成器或测试”的全部追溯，因此不能把这五次数行提升为生成器正确性证明。

未能核实的五组声明及实际尝试：

1. **七类可达性与 COPIED_REBUILT**：已读判定代码。直接调用 `_copied_row` 的相对路径夹具在正确和错误期望摘要下都返回 `COPIED_TARGET_DIFFERS`；该夹具未成功进入 rebuilt 分支，不能据此认定生产缺陷，也不能认定要求的回落反例已证明。
2. **真实 HTTP 五态**：执行  
   `.venv/Scripts/python.exe -B -X utf8 -m pytest -p no:cacheprovider tests/unified/test_v04_design_loop.py tests/unified/test_v05_rejections.py tests/unified/test_v24_capability_evidence.py tests/unified/test_v25_audit_item_closure.py -q`  
   rc=1，在收集前报 `No usable temporary directory found`。静态仍见 `binding.py:266–267` 对 STALE 添加 `RESULT_STALE`，`v1.py:1047–1048` 的201回执携带 staleness；HTTP 行为未验证。
3. **owner 完整通道**：集合和摘要反例已核；未独立实跑 L10#0 的 PARTIAL/REFUSED 全链路。
4. **真人延后项与9条迁移记录**：`test_v24` 被上述环境错误阻断，磁盘元素与9/18计数未完成核验。
5. **复审记录历史与反例**：填值测试源码已读，但未执行，也未构造临时副本证明非法历史 SHA 能被拒绝。

没有写入 `review-02.md`：本轮明确要求只读，且环境禁止文件写入。以下检查数按实际执行的 shell 调用计数，包含失败尝试；不代表通过数。

```text
INDEPENDENT_REVIEW_VERDICT: FAIL
reviewed_sha: f616fb533f06d6b8ec9c596ddb82dd48ce453050
blocking_findings: 1
non_blocking_findings: 0
checks_actually_run: 9
unverified_claims: 5
```
