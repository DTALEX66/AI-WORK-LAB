# DESIGN-LAB UI 商业级 Workbench — HOST_UI_MATRIX（宿主 / UI 能力矩阵）
任务包：DESIGN-LAB_UI_FRONTEND_TASKPACK_20260930 · 分支 feat/ui-commercial-workbench-20260930

状态词表：`IMPLEMENTED`（有真实读回）/ `UNKNOWN`（无后端路由，诚实占位）/
`BLOCKED`（缺依赖，显式标注）/ `PLANNED`（未来能力，登记接入点）。
**本矩阵不触发任何宿主实操；全部为 UI 层只读回 + 状态标注。**

| 宿主 / 能力 | 路由槽位 | 状态 | 来源 / 依据 | 未来接入点 | 下一动作 |
|---|---|---|---|---|---|
| Illustrator / AI（宿主驱动任务台账） | #/tools · 项目高级区 | IMPLEMENTED（读回）/ UNKNOWN（在线） | /api/projects/:id/tasks（PR #211 同族合同）；宿主在线无路由 | 宿主 adapter 探测读回路由 | 官方插件/CLI/MCP 接入后替换 UNKNOWN |
| Photoshop / PSD | 同上 | 同上 | 同上 | 同上 | 同上 |
| Figma | #/tools 能力卡 | PLANNED | 官方插件 adapter 合同（Open Design 宿主层） | adapter 层路由 | 立项 |
| Penpot | #/tools 能力卡 | PLANNED | Open Design 宿主 adapter | 同上 | 立项 |
| ComfyUI | #/tools 能力卡 | PLANNED | ComfyUI 0.33.1 本机（LOCAL_ENVIRONMENT 登记） | adapter 路由 | 立项 |
| Blender | #/tools 能力卡 | PLANNED | Blender 4.2.0 本机登记 | adapter 路由 | 立项 |
| MiniMax H3（本地模型） | 能力卡（model-radar） | PLANNED | model-radar.json（未校验模型 defaultEnabled:false） | runtime resolver 校验后启用 | 先过校验门 |
| MCP 诊断 | #/tools | BLOCKED | 无后端 MCP 路由 | GET /api/mcp/… | 后端路由提供后 UI 接入 |
| 研究洞察 | #/research | PLANNED | 无研究结论持久化路由 | GET /api/research/… | 建模型 + 路由 |
| 设计领域模型 | #/domains | PLANNED | Domain Pack 文档承载，无独立后端 | GET /api/domains/… | 建路由 |
| 团队协作 | #/collaboration | PLANNED | 单用户模型，无协作路由 | 协作模型立项 | 立项 |
| 共享输入（E 盘/外部根） | 仪表盘 + #/tools | IMPLEMENTED（读回） | /api/environment shared_inputs（status 真实） | — | 已闭环 |
| 任务资源预检 | #/preflight | IMPLEMENTED（读回） | /api/task-preflight（verdict/blocked 真实） | — | 已闭环 |
| 交付包 readback | #/deliverables · 项目页 | IMPLEMENTED | /api/projects/:id/bundles（PR #211）+ 下载 hash fail-closed | — | 已闭环 |

## 诚实性约定（全矩阵通用）
1. `UNKNOWN` ≠ 0 且 ≠ 可用：无读回就写「未读回」，不渲染假 0。
2. `BLOCKED` 必须给出缺什么（路由 / 运行时 / 权限）与下一动作。
3. `PLANNED` 必须给未来路由 + 合同引用（指向现有 schema/文档，不发明）。
4. 宿主实操（打开软件 / 驱动 UI / 出图）一律不在本矩阵执行；
   提交 / 运行 / 取消仍由工作台高级区 + 宿主官方入口承担。
