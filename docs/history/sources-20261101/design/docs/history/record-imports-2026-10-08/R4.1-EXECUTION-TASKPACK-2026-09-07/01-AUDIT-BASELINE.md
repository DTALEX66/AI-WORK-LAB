# 2026-09-07 冻结审计基线

## 云端事实

| 项目 | 结果 |
|---|---|
| main | `c4dccd58331bc4561eb89265283d924b7630d113` |
| 相比 2026-09-06 | **无代码漂移** |
| 开放 PR | 0 |
| 受保护门 | Python、MiniGame、生成物清洁、许可证/秘密、Open Design host 共 5 项 |
| 最近运行 | `34009291219`，success；云端 Python 580 tests、skipped=6 |
| 产品版本 | `0.1.0-alpha.0`，未发布 |

基线通过 CI，不代表用户可用。云端检查主要证明结构、约束和单元测试；没有 Windows Adobe、Comfy、H3、Premiere 或 Blender 的本机 E2E 证据。

## 已完成并应保留的成果

- 单一活动身份为 `DESIGN-LAB / 设计实验室 / design-lab`；旧 `OPEN-DESIGN-Assistance` 仅历史归档。
- 依赖由 `pyproject.toml` / `uv.lock` 管理；主分支受保护。
- 第三方候选源码已移出 Git，仓库内保留来源、许可和锁定记录。
- 多项 Schema、manifest 门、重建封存/回滚、测试隔离和能力证据结构已实现。
- 重建主链的一部分已转为 `.project-local`。

## 不可结案的事实

| 范围 | 真实状态 |
|---|---|
| 58 项原正式任务 | 并未完成；当前进度文件只为其中 34 项给出状态：20 DONE_VERIFIED、4 PARTIAL、5 SCHEMA_DRAFT、3 REGISTER_ONLY、2 BLOCKED_RUNTIME。后续波次仍未形成用户交付。 |
| 多媒体 T01—T18 | 仅 T01/T18 完成、T05/T06/T09 为结构层；AI/PS、前端、音频、Premiere、OpenDesign/MiniMax协作待实机，H3 被门禁阻塞，Blender 未装。 |
| 前端 / 服务 | 没有已验证的独立工作台、可安装产品服务或 TypeScript 前端。现有 React 文档和游戏夹具不等于产品前端。 |
| Illustrator / Photoshop | Illustrator 适配器只创建画布；Photoshop 入口返回 `NOT_EXECUTED`。均未制作/保存/重开真实 AI/PSD。 |
| `.hermes` | 核心重建路径已部分迁移，但 Adobe、Comfy、H3、外部资产策略和 evidence 索引仍有活跃 `.hermes` 路径。 |
| 状态源 | `TASKPACK_PROGRESS`、旧 job ledger、能力状态和机器盘点的时间/结论未完全一致；例如历史 Comfy/H3 E3 与当前“未装/阻塞”并存。 |
| 语言迁移 | 选择已作出，迁移未完成：Python 产品包仍 `package=false`；TypeScript 工作台不存在；Adobe 侧仅 JS/JSX 骨架。 |

## 已复现的代码问题

1. `effect_not_started` 经过 reconcile 被记录为 `SUCCEEDED`，需要可控重试而不是成功。
2. 资产同名输出的下一版本可触发唯一键错误，并遗留没有产物的 ACTIVE 版本。
3. 同一 idempotency key 但不同 request hash 没有被拒绝；失败后缺少显式新 attempt。
4. ProfileResolver 忽略 `rights=DENIED` 与 `installed=false` 仍能选中 Photoshop。
5. 只有 `config.json` 的模型缓存可被判 READY；缓存存在、完整权重、实际加载、推理成功被混为一层。
6. Comfy 结构回执接受相对越界形式路径和伪指纹；取消不等待适配器确认。

这些问题均应在引入真实软件控制前修复。`evidence/reproduced-findings-20260907.json` 保存了本次复查结果。

## 同行结论与研究边界

OpenDesign 适合作为本地工作台和 Agent 接入的局部供体，不替代 AI / PSD 原生可编辑闭环。Illustrator 官方 MCP 目前为 Beta；用于资格赛，不成为现有稳定版的默认路径。ComfyUI 已有正式 REST / WebSocket 服务接口，当前应完成真实适配而非继续设计抽象协议。

因此，不再进行“全网收集所有设计 Agent”的广泛调研。仅保留下列准入研究：稳定版 AI/PS 桥接、H3 许可/资源、MiniMax Design 真实桌面自动化能力、OpenDesign 单个可复用前端切片。每项在开始集成前完成；无明确入口/版本/许可时不进入默认栈。
