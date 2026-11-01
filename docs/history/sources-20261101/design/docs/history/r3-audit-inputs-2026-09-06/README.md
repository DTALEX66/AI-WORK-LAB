# R3 历史审计输入与恢复入口

这两个文件于 2026-09-07 从用户提供的 `DESIGN-LAB-CLOUD-REAUDIT-TASKPACK-2026-09-06.zip` 恢复，保留原始字节。它们是公开元数据索引，不是历史原文，也不是新的执行指令。

| 本地文件 | ZIP 精确 member | bytes | SHA256 |
|---|---|---:|---|
| [history-current-tree-coverage.json](history-current-tree-coverage.json) | `evidence/history-current-tree-coverage.json` | 262249 | `46e2504f51caa61e7287b201da2977946f28324a38f7bc40cf9ebd386489ff96` |
| [old-new-crosswalk.csv](old-new-crosswalk.csv) | `old-new-crosswalk.csv`（ZIP 根，不是 history/） | 3152 | `a52e0a01e3cd3c89ea6dcc7d818e221676bdea5619a9acfe353dd2df7a942eea` |

`.gitattributes` 对这两项禁用文本转换。原 536 条历史 manifest、1450 条 occurrence crosswalk、history-baseline.json 与 DP V1/V2 均保持不变。

## 当前逐条恢复结果：PARTIAL

以下为首轮 [公开候选复核清单](../r3-recovery-2026-09-07-public-complete.json) 的冻结观察。它追加继承了 [首轮范围较窄的清单](../r3-recovery-2026-09-07.json)，不删除旧观察。后续结果见下方追加定位，不回写这些快照。

- **272 条**：从 136 个公开 Git blob 实际读取内容，大小及 SHA256 与原 manifest 一致。每条保留原 ID、重复组及 canonical_record，并给出 commit、path、blob OID；不是仅检查路径存在。
- **4 条**：TRANSPORT_PLACEHOLDER，单独列出。空文件与 `.gitkeep` 同 hash 不能算原文已恢复。
- **260 条**：UNRESOLVED，保留每条元数据、声明的 archive/member、期望大小/hash和未查范围。尚未搜索旧提交、原始历史归档或私人正文；不能宣称内容丢失，也不能宣称历史完整。
- 本轮读取的是已经列出的公开项目文件（design-lab 和 packages 下）。第三方 SKILL 只作为 inert 文档字节校验，不执行、安装或加载为根指令。

`history_complete=false`。本文件名中的 public-complete 仅指 136 个已给出的公开候选全部检查，不代表全部历史恢复。

## 后续公开 Git 检索：累计 289 / 4 / 243

[追加定位](../r3-public-history-locators-2026-09-07.json) 新增 9 个公开 Git blob，覆盖原先未解决的 17 条记录。每项绑定精确 commit、path、blob OID、原始 size/hash；原文不另复制。与首轮冻结清单合并后：**289 条可取回、4 条占位、243 条未解决**，仍为 PARTIAL。

[独立验证](../../../.project-local/task-artifacts/history-public-git/verified-20260906T190724230216Z/results.json) 实际读回 3 个提交树、145 个 blob，884 项检查通过；原始 536 条 manifest、1450 条 occurrence 与 baseline 字节不变。检索仅限本地 Git 的公开项目路径，排除凭据/会话/prompt 等私有类别；没有访问私人归档或外置盘。未找到不代表原件已丢失，剩余来源仍需按授权范围继续定位。

## 复核与边界

定向命令：`.venv/Scripts/python.exe -B -m unittest discover -s design-lab/tests -p test_history_baseline_retrieval.py -v`。测试覆盖冻结字节、536 个身份、28 条旧任务映射、占位与未解决状态，以及 Git locator 的真实字节读回。缺少该历史提交的浅克隆应报证据不足，不能伪造 blob。

原始操作证据位于 `.project-local/task-artifacts/normalization-20260907/history-recovery/`；属于 ignored 本地数据，换机缺失应显示 MISSING。公开索引与恢复 manifest 属于仓库资料，但本轮未提交或上传。

剩余 243 条应按授权范围继续检索公开旧 Git/历史文件；私人对话、凭据、Agent 私有数据不读取，不从摘要重建原文。知识迁移继续延后。本次资料恢复不升级任何软件/模型的运行资格。
