# Open Design 真实运行集成

## 静态兼容不等于运行可用

必须分别记录：

- Manifest/Schema 可解析；
- 本地插件目录被发现；
- Open Design runtime 注册；
- Apply 结果正确；
- Agent 实际运行；
- Artifact、Stage event、GenUI 和 provenance 正确；
- 真实项目完成。

## 当前 Manifest 目标

支持：

- `od.kind`: skill / atom / scenario / bundle；
- `taskKind`: new-generation / code-migration / figma-migration / tune-collab；
- `compat.agentSkills`；
- `od.context`：skills、design system、craft、assets、MCP、atoms；
- `od.pipeline.stages`：repeat、until、onFailure；
- `od.genui.surfaces`；
- typed inputs、preview、exampleOutputs、capabilities 和 connectors。

## 真实验证顺序

1. 现场发现本机 Open Design/od 版本和支持命令；
2. 运行插件 doctor/validator；
3. 安装或链接 staging 插件源；
4. 查询 runtime registry；
5. apply 一个最小 Atom；
6. 运行一个 Scenario；
7. 验证事件、状态、产物和恢复；
8. Codex 与 Hermes 各运行一次；
9. 记录版本、命令、exit code、项目 ID、artifact hash 和结果。

端口、API 和命令必须以当前 `--help`/官方运行时为准，不使用历史端口或猜测接口。
