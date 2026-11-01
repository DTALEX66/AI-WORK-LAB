# 模型/API 中立 Agent Harness 吸收审计（2026-07）

## 固定来源

- 上游仓库：https://github.com/xai-org/grok-build
- 审阅提交：[98c3b2438aa922fbbe6178a5c0a4c48f85edc8ce](https://github.com/xai-org/grok-build/tree/98c3b2438aa922fbbe6178a5c0a4c48f85edc8ce)
- 上游 `SOURCE_REV`：`124d85bc5dc6e7805560215fcc6d5413944920e1`
- 上游许可：Apache-2.0
- 机器可读清单：`docs/audit/model-neutral-agent-harness-absorption-2026-07.yaml`
- 吸收方式：文档、任务模板与治理测试；不复制上游运行时

本轮只吸收不依赖特定模型、付费接口或外部运行时的通用机制。Hermes 继续是唯一编排器；本仓库不增加新的模型路线、Provider、凭据或网络服务。

## 上游证据映射

| 方法 | 固定提交中的上游路径 | 本地落点 |
|---|---|---|
| 完成信号与有界恢复 | `crates/codegen/xai-grok-agent/src/config.rs`、`agent.rs` | 模型中立任务模板 |
| 结构化运行状态 | `docs/user-guide/14-headless-mode.md`、`20-background-tasks.md` | 模板中的 Run State Contract |
| 权限与负控 | `10-hooks.md`、`16-subagents.md`、`18-sandbox.md`、`19-plan-mode.md`、`22-permissions-and-safety.md` | fortress reference + 任务模板 |
| worktree 隔离方法 | `crates/codegen/xai-fast-worktree/src/api.rs`、`16-subagents.md` | 单写者与隔离工作树规则 |

完整仓库相对路径及本地文件范围以机器可读清单为准。

## 已吸收

| 方法 | 落地位置 | 治理要求 |
|---|---|---|
| 完成信号与有界恢复 | `templates/task-tickets/model-neutral-agent-task.md` | 没有真实证据时只能失败或阻塞，不能假完成 |
| 结构化运行状态 | 同上 | 记录状态、时间、进程句柄、树身份、命令与退出码 |
| 终态单调性 | 同上 | 迟到进程不得覆盖失败、阻塞或取消状态 |
| 单写者与隔离工作树 | 模板 + fortress reference | 写任务使用独立 worktree/clone；这不是安全 sandbox |
| Fail-closed 契约 | 模板 + reference | 必须记录真实外部执行机制、tool deny、OS 支持和负控结果 |
| Exact-tree 证据 | 模板 + reference | 复审绑定 `git write-tree`，树变化后 verdict 失效 |
| 安全负控清单 | reference | 要求验证链式命令、shell 写入、子 Agent 越权和伪只读 sandbox |

以上均是**契约要求，不是运行时隔离证明**。模板、plan、hook、路径声明或 worktree 本身都不构成安全边界；没有外层强制机制及真实负控证据时必须返回 `blocked`。

## 明确排除

- 任何模型名称、模型目录、模型路由或模型专用提示；
- 任何订阅、计量服务、付费接口或托管推理端点；
- 外部认证、凭据文件、云存储、遥测、trace/session 上传；
- 上游二进制、安装器、自动更新器和大型源码 vendoring；
- 与 Hermes 重复的 memory、MCP、skills、cron、session store 和 TUI；
- 在 Windows 上把未验证的模式名称当作内核隔离证明。

## 当前状态

**未安装外部执行器，未发起模型请求，未配置网络 API。**

机器可读清单将本轮本地落点限制在 README、审计文档、既有 fortress skill/reference、任务模板和治理测试；`runtime_assets` 为空，并禁止把本轮吸收落入 `config/`、`scripts/` 或 `bin/`。

## 验证

```bash
python tests/test_workflow_governance.py -v
python scripts/security/scan_agent_rules.py templates skills docs scripts
python -m py_compile scripts/workflow/*.py scripts/security/*.py
```
