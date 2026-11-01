# 多 Agent 并行协作优化方案（2026-08-23 调研）

> 问题：全局单写者 + 只读并行拖慢 Codex（两个大项目并行时互相阻塞/冲突）。
> 状态：**提案，未部署**（用户确认后再改全局规则）。

## 1. 调研结论（行业 2026 专门方案）

| 工具/方案 | 思路 | 来源 |
|---|---|---|
| **mainline**（recallnet）| git worktree landing 变**串行化持久队列**（防 clobber main）| github.com/recallnet/mainline |
| **gwtree** | worktree 管理（多 agent 并行不同分支）| github.com/ahmadawais/gwtree |
| **agentlocks** | **advisory file locks**（多 agent 共享工作树，文件级锁）| github.com/simke9445/agentlocks |
| **agent-claim-mcp** | agent 声明（claim）要改的文件 | npm @vk0/agent-claim-mcp |
| parallel-agent-worktree-skill | 并行 agent worktree skill | TheAhmadOsman |

## 2. WORK-LAB 现状问题

- 全局单写者：任一 agent 写时，其他 agent 不能 commit/push（互相等待）
- 只读并行：非写者只能看（读不写——耽误 Codex 落地）
- 实际冲突：多 agent 同时推 main → merge 冲突（CURRENT_STATE 等生成文件）

## 3. 方案：路径所有权 + 独立 worktree + 串行化落地

### 3.1 文件/路径级所有权（agentlocks 式）

```text
写前认领：agent 在 .hermes/agent-claims.json 认领要改的路径
  { path: "10-workflow/...", owner: "codex", claimedAt, expiresAt }
不同路径 → 并行写（互不阻塞）
同路径 → 排队/等待（只有真正重叠才串行）
→ 替代全局单写者：只在【文件重叠】时串行，日常完全并行
```

### 3.2 独立 worktree（gwtree/mainline 式）

```text
每个 agent 一个 worktree + 分支（codex-projA / dsh-wlr / hermes-upd）
→ 互不干扰的工作副本，无共享 checkout 锁
→ 提交在各自分支，不直接动 main
```

### 3.3 串行化落地队列（mainline 式）

```text
合并走队列：CI 绿后按顺序合并（分支 → main）
→ 不互相 clobber，冲突由队列串行消解
→ 生成文件（CURRENT_STATE 等）由队列自动处理（last-wins 或 merge）
```

## 4. 对 Codex 的好处

- 两个大项目：各自路径认领 + 独立 worktree → **完全并行，互不等待**
- 落地：CI 绿即入队合并（不再被单写者/只读规则卡住）
- 冲突：仅重叠文件需协调（低概率，路径分区后更少）

## 5. 实施步骤（待批准）

1. 建 agent-claims 认领机制（.hermes/agent-claims.json + 认领/释放脚本）
2. Codex/DSH/Hermes 各建独立 worktree（gwtree 管理）
3. 落地队列（mainline 或简化版：CI 绿后脚本顺序合并）
4. AGENTS.md 规则更新（单写者 → 路径级所有权 + worktree + 队列）
5. 试点（Codex 两个大项目）→ 验证无阻塞 → 全量

## 6. 边界与风险

- 认领是 advisory（agent 自觉遵守；不强制锁——保持灵活性）
- worktree 磁盘开销（每个 ~1-2GB）——机器容量 OK（之前迁出释放过空间）
- 队列落地需 CI 稳定（当前已全绿）
- 先不部署全局：试点验证后再改 AGENTS.md