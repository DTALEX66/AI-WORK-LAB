# Hermes 记忆压缩与优化归档（2026-08-13）

## 目的

Hermes 侧记忆（MEMORY.md + user.md）接近容量上限，本轮执行压缩优化，并将优化后的记忆能力**存入本项目**（tracked），供未来会话、跨机同步与审计参考。

## 压缩前状态

| 存储 | 压缩前 | 条数 |
|---|---|---|
| MEMORY.md | 94%（2,084/2,200） | 18 |
| user.md | 100%（1,375/1,375） | 12 |

## 压缩策略（18 → 19 条，净增 1 条高价值经验）

### 合并同类项

1. **官方基准 + 五维基线** → 合成一条：`用户五维运行时基线（强制，已写入 AGENTS.md+受管清单）：软件入口唯一、桌面可达、官方标准+用户配置、配置不过重无阻塞感、模型满血。增强模块只管理声明的overlay字段，不覆盖用户 provider/model/auth/Desktop/sandbox 状态；排查先核对云端SSOT和项目记忆，避免概念漂移。`
2. **USER 侧直接执行 + 证据收尾** → 合成一条：`用户偏好直接执行、真实证据和闭环验证，不接受只说明保留配置；中文、直接、证据驱动收尾，区分 PASS/PARTIAL/NOT EXECUTED/阻塞。WORK-LAB 增强模块必须实际接入 Codex 项目级规则、技能和执行边界；不得覆盖 Codex 私有 provider、认证、Desktop 状态、会话或用户 MCP。`

### 精简冗长

| 条目 | 精简点 |
|---|---|
| 测试边界（272→~200） | 删计时、删 toolchains 明细括号 |
| 命名V2（148→~120） | 删 "对外=ArcheAxis Knowledge"、junction 细节 |
| 铁律（166→~130） | 压缩各条款措辞 |
| 并行会话（132→~115） | 删"仅参考宿主"冗余 |

### 新增高价值经验（本次 WLG TaskPack 沉淀）

```
Windows/Git 陷阱: CRLF 文件 hash 须规范化(\r\n→\n); rebase force-push 后 CI push-run 因 before-sha 失效误报失败看 pull_request run; 多分支共享工作树须 stash+--no-verify 精确提交
```

```
网络/认证: github push 走 7890 代理, api.github.com 直连; gh CLI 已卸载, git credential helper 须指 manager, 匿名 API 限流 60/hr 用 credential fill 取 token; HF 超时走 7890; 禁强杀 FlClashCore
```

## 压缩后状态

| 存储 | 压缩后 | 条数 | 释放/净变化 |
|---|---|---|---|
| MEMORY.md | 96%（2,113/2,200） | 19 | 净增 1 条经验，内容更优 |
| user.md | 96%（1,320/1,375） | 11 | 释放 55 字符 |

## 记忆治理规则（固化）

1. 记忆只存**跨会话稳定事实**（用户偏好、环境事实、工具陷阱），不存任务进度/完成日志（用 session_search 回溯）。
2. 新增经验前先查重——同类主题合并，不重复存储。
3. 详细知识归档到本项目 `docs/workflow/error-fixes-*.md` 与 `active-authority-index.md`，记忆只留指针级摘要。
4. 达到 95% 时执行压缩：合并同类 → 精简措辞 → 归档到项目。
5. 高价值执行经验（CLI 卸载、CI 陷阱、CRLF）优先存记忆 + skill 双写（skill 见 windows-development-environment）。

## 全局配置影响

本次仅整理 Hermes 内部记忆（MEMORY.md / user.md），**不涉及** Hermes config.yaml、Codex overlay、skills 或任何受管配置——**无需重新配置全局**。记忆优化不触发 sync/apply。
