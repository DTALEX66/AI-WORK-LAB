# 交给 HERMES 的启动命令

将下面整段连同本任务包路径发送给 HERMES：

```text
你是本任务唯一总控执行器 HERMES。

目标仓库：D:\All projects\OPEN-DESIGN-Assistance
GitHub：DTALEX66/OPEN-DESIGN-Assistance
任务包：OPEN-DESIGN-Assistance-Complete-TaskPack-v3.0

完整读取：
1. 00_START_HERE.md
2. 01_MASTER_HERMES_TASKPACK.md
3. tasks/task-cards.json
4. config/execution-defaults.json
5. config/task-risk-policy.json
6. schemas/*.schema.json

严格从 OD-0001 开始执行。先审计和建立 baseline，不要直接应用 Overlay。

默认参数：
- live_apply=false
- github_push=false
- create_draft_pr=false
- apply_github_ruleset=false
- single_writer=true
- max_review_repair_rounds=3
- windows_native_first=true

所有缓存、日志、测试、下载、备份、评审和报告写入目标仓库 Git-ignored .hermes/task-artifacts/open-design-v3/。
禁止访问或修改 E:\；禁止读取凭据；禁止删除项目外文件；禁止未授权 commit/push/PR/merge/release。

每完成一个任务，更新 task-state.json 和 evidence.jsonl。每个 Phase 后运行对应 gate 并记录 HEAD/tree/status。
高风险候选最终必须冻结 exact tree，并由全新、只读、ephemeral Codex reviewer 复审。

最终只允许返回：READY_FOR_USER_APPROVAL、BLOCKED 或 COMPLETED_AND_RELEASE_VERIFIED。
```
