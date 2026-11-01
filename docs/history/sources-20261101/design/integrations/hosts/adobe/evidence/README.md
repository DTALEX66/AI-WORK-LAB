# adobe — 取证目录

- **任务**：DL-ADB-PS-001
- **当前**：此处保留历史证据入口；正式 R3-11/12 状态来自根任务账本，不由本 README 的历史声明决定
- **E3**：绑定代码、适配器、宿主版本、OS、fixture/产物 hash 和授权；真实可编辑工程保存重开、结构读回、失败与回滚，不能只记录退出码
- **生成物**：运行文件写入项目 `.project-local/task-runtime/`，审计证据写入 `.project-local/task-artifacts/`，持久作品走资产服务；以根 `.project/paths.json` 解析结果为准。`.hermes/` 与 `80-evidence/` 只作历史位置，不新写、不据此迁移或删除
- **人工门**：质量、rights、production 和 release 独立验收；自动测试不能代签
