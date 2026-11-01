# 模型路由客户端接入建议（WLR-410 后续）

> WORK-LAB 只出路由决策（InvocationPlan），真实调用由客户端完成。客户端侧可选接入点：

## 已就绪（服务端）

- model_router.route() → InvocationPlan（lane/model_ref/budget/cache_policy）
- WorkUnit.create 自动路由（goal→lane/modelRef）
- 零模型调用（规则路由），隐私→D/视觉→C/复杂→B/日常→A + 预算降级

## 客户端接入建议（按需，非阻塞）

| 客户端 | 接入点 | 效果 |
|---|---|---|
| Hermes | pre_tool_call hook 读 WorkUnit.model_lane → 选 model_ref | Agent 按任务自动选模型 |
| Codex | 项目 AGENTS.md 注 model_ref（人工/脚本）| 复杂项目用强推理 |
| DSH | 会话 meta 带 lane（工作区字段）| 路由决策可见 |

## 边界

- WORK-LAB 不代理凭据/请求正文（客户端执行）
- 路由决策可被客户端覆盖（客户端最终控制）
- 预算降级仅建议（不强制）

## 状态

- 服务端路由 ✅ 完成（已接入 work_unit）
- 客户端接入：**待用户决定**（每个客户端都是独立改动，不影响当前执行）