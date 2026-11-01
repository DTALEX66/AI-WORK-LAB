# WORK-LAB 全面审计与清理门禁

审计批次：2026-08-05
目标：D:\\All projects\\WORK-LAB

## 已完成且已验证

- 云端 WORK-LAB 目标 tree 与迁移 staging tree 一致：`1b3cad619addc86161ac14dbefdf35f7566f6183`
- `.gitignore` 已移除宽泛 `*token*` / `*oauth*` / `*cookie*` / `*credentials*` 规则；改为 `.hermes/` 隔离和精确凭据文件规则。
- 被错误 ignore 的 Token Monitor、Design Token、Component Token 文件已按云端 blob 一致性恢复到本地 index。
- Workflow boundary tests：147 passed，5 skipped，22 subtests passed。
- Token Monitor tests：5 passed。
- Token Monitor `npm ci` 与 Vite build：通过。
- MINIGAME：318 passed，0 failed，0 skipped；测试结束后 tracked `douyin-minigame/project.config.json` 保持 clean。
- security path check：PASS；contract tests：2 passed；agent rule scan：OK。
- 三个旧云端仓库已 archived；旧本地 checkout 和历史归档仍保留。
- 未读取或迁移凭据、认证、cookies、session、全局 config 内容。

## 全局边界结论

- Hermes 全局 skills/config/auth/sessions/cron/backups 属于平台状态，不纳入 WORK-LAB。
- Workflow portable skills 中 9 个与全局同 hash，4 个为项目定制版；它们由 `workflow-manifest.yaml` 声明为 portable source，不能按重复文件删除。
- `C:\\Users\\ALEX\\AppData\\Local\\hermes\\d\\All projects\\Workflow-assistance` 仅有空目录、0 文件、0 bytes，有项目名外溢迹象但无有效数据。
- 全局 tmp 为空但属于全局运行时根，不删除。
- 全局 backups 具备保护/恢复价值，不删除：包括 config-history、pre-update、protected-state、workflow-assistance-sync 等。
- 当前 scheduler 未发现指向 WORK-LAB 或三个旧项目的活动任务。

## 待批准的不可逆操作

### CLEAN-001（建议批准）
删除空的项目名外溢目录：
`C:\\Users\\ALEX\\AppData\\Local\\hermes\\d\\All projects\\Workflow-assistance`

前提：删除前再次确认 0 文件、0 link、无活动进程持有；只删除该精确目录，不删除父目录、不删除 Hermes 全局状态。

### CLEAN-002（暂不建议批准）
移动三个旧本地 checkout 到本轮归档的 `source-checkouts`。
当前被 Windows 进程锁阻塞；不强杀、不覆盖、不删除。

### CLEAN-003（暂不建议批准）
删除三个旧本地 checkout。
必须等待 CLEAN-002 完成、WORK-LAB 提交/远端回读/恢复演练完成后另行批准。

### CLEAN-004（明确保留）
不得删除 Hermes 全局 config、auth、sessions、cron、skills、plugins、tmp 根、backups，也不得删除 WORK-LAB-ARCHIVE 或 staging。

## 当前 Git 状态

变更已 staged，尚未 commit/push；未提交内容包括规则修复、被错误 ignore 的合法文件恢复、边界测试修复和 MINIGAME 测试隔离修复。`.hermes/`、node_modules、构建缓存仍在项目运行态并被忽略。
