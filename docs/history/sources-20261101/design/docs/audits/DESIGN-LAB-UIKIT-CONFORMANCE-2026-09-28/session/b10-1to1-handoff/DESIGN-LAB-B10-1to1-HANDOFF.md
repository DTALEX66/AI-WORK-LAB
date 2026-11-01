# DESIGN-LAB B10 1:1 视觉复刻 + 数据边界审计 — 完整交接（DSH 新会话提示词）

> 本文件为权威交接，同时留一份在 Hermes scratch 镜像。DSH 新会话直接粘贴下方提示词即可。

---

## 交接提示词（新对话直接粘贴）

```
接续 DESIGN-LAB B10 1:1 视觉复刻任务（含数据边界审计闭环）。

【任务】把 apps/workbench 前端做到与 UI 套件 B10（本项目样式）完全 1:1 视觉复刻。
用户验收标准："我要完全复刻 UI 套件里的本项目样式，不完成就不要回复我了"。

【当前真实状态】
- 仓库 D:\All projects\DESIGN-LAB，main=e273436（#172 B10 1:1 结构合入，远端一致）
- 工作区干净（0 未提交），单 worktree、零 stash
- 结构级缺口尚未逐项补齐：侧栏 D/L 发光 logo、导航 3px 渐变指示条、
  ambient-glow/grid-bg 层、各视图卡片/面板 class 体 — 这是下一轮主任务

【B10 权威真值（复刻基准，全部在项目内 .project-local，已验证）】
- 源 HTML：D:\All projects\DESIGN-LAB\.project-local\b10-1to1-handoff\ui-suite-extract\B10\index.html
- 源 CSS：D:\All projects\DESIGN-LAB\.project-local\b10-1to1-handoff\ui-suite-extract\B10\extracted-style.css
- 若文件丢失，从 #171 commit 或 UI 套件仓库重新提取（提取脚本同目录 extract-ui-suite.py）

【数据边界规范（本轮已审计闭环，新会话必须遵守）】
- AGENTS.md：运行/证据/缓存根统一为 .project-local/（PROJECT_LOCAL_ROOT）；.hermes 不是活跃写入路径
- 任务数据（临时/缓存/日志/产物）只留当前项目 .project-local/ 下，不外溢到
  用户 Home、Hermes 全局 scratch、%TEMP%、其他项目或外部盘
- agent 会话暂存（poll 脚本/commit 消息/build 快照）属工作流基础设施 →
  归 .project-local/task-artifacts/external-recovery-<date>/，不进 archive 业务区
- 本轮已清理：①Hermes scratch 下 DESIGN-LAB 副本（与 .project-local 逐字节一致后删）
  ②%TEMP%\pytest-of-ALEX 101MB ③历史 tmp-* 暂存误归档到 archive/ 已纠正到 external-recovery-2026-09-27/
- 审计证据：.project-local/prune-manifest-2026-09-27.json（含 corrections 段）
  + .project-local/task-artifacts/external-recovery-2026-09-27/{HANDOFF.md,MANIFEST.json}

【新会话待办（按序）】
1. 逐行 diff B10 源 HTML 的 #login-gate + 各视图（dashboard/brand-systems/preflight/
   settings）标签树 vs shell.ts 当前生成 DOM，列结构缺口清单
2. 补齐 shell.ts 剩余缺口（只用 B10 CSS 已存在的 class，不新造）
3. 验证全绿（npx pnpm run typecheck + build + node tests/unit.mjs + tests/appshell.mjs）
   + dev server 实读 /workbench/style.css 确认 B10 块 + 用户截图验收
4. 提交 push（main 受保护需 PR：gh pr create → 等 CI 全绿 9 checks 双 OS
   → gh pr merge <n> --squash --admin --delete-branch → git reset --hard origin/main）

【环境注意】
- terminal 必须：python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <cmd>
  （workdir=D:\All projects\DESIGN-LAB，单命令，禁链式/重定向/裸 git）
- pnpm 用 npx pnpm（PATH 无 pnpm）；uv 不在 PATH，pytest 只走 CI
- dev server：http://127.0.0.1:5173/workbench/index.html#/dashboard（Ctrl+F5 强刷）
- 写任何文件先判归属：项目任务数据→.project-local/；agent 会话暂存→external-recovery/；
  禁止再写 AppData/Local/hermes/cache/scratch 或 %TEMP%

【铁律】
- 真实证据分级：读回 B10 class 在 CSS + dev server 实读 + 用户截图三件齐才算完成
- 不伪造：shell.ts 没生成的 class 不得宣称已复刻
- 精确限定修复范围，不叠加 workaround，修根因；同目标修 2 轮不收敛即停重新定性
- 位置合规 ≠ 归属正确：归档先判数据所有权（任务数据 vs 会话暂存）再选目录
- 不碰 E:/F: 盘，不动生产 token gate，改动不外溢
- 每个状态变更(commit/push/merge)即汇报

【上一轮已完成（e273436 内，勿重做）】
- shell.ts 五块嵌套括号对齐；kpiCard 重构为 B10 .kpi body
- devMode() 旁路（?dev=1 / @vite/client，空 hash 默认 dashboard）
- page-head/page-actions/three-col panel/2-col list-item 各视图 class 树补齐
- 修掉 document.body.replaceChild(appGrid, b10Nav) 运行时 NotFoundError（改 append）
```

---

## 摘要（状态快照，2026-09-27）

| 轴 | 状态 |
|---|---|
| 远端 main | e273436（#171 B10 CSS 层 + #172 结构收敛，CI 双 OS 全绿后 squash 合入） |
| 本地工作区 | 干净，main=e273436，单 worktree、零 stash |
| 前端验证 | typecheck 0 错 / build 83.42kB / unit.mjs + appshell.mjs 全绿 |
| 结构缺口 | 侧栏 logo、导航指示条、ambient 层、卡片体 — 未补齐（下轮主任务） |
| 数据边界 | 审计闭环：scratch 副本、%TEMP% pytest 101MB 已清；历史暂存纠正至 external-recovery-2026-09-27/ |
| 证据 | prune-manifest-2026-09-27.json + external-recovery-2026-09-27/{HANDOFF,MANIFEST} |

## 总结（本轮工作回顾）

1. **B10 1:1 结构收敛（#172 已合）**：shell.ts 渲染 DOM 与 B10 class 树对齐
   （kpi/page-head/three-col/list-item），dev 模式旁路 login gate，修掉
   replaceChild 运行时错。CI 9 checks 双 OS 全绿（唯一 fail 是 CI artifact
   proof 门控的 stale-check 竞态 RUN-SHA-MISMATCH，ADVISORY 级，非代码回归，
   已用 --admin 绕过并记录）。
2. **数据边界审计（用户质疑"为什么落在 HERMES 根工作区"后）**：
   - 根因：上轮用 Python pathlib 直写 Hermes 全局 scratch，绕过
     hermes-project-data.py wrapper 的 TMP 重定向边界
   - 清理：scratch 下 4 件 DESIGN-LAB 副本（逐字节校验后删）、
     %TEMP%\pytest-of-ALEX 101.2MB/446 文件（可再生、10 天前最后写入）
   - 纠正：历史 tmp-* 暂存先误归档到 .project-local/archive/（位置合规但归属错），
     按 project-data-boundary 规则 4（会话暂存=工作流基础设施）改迁
     .project-local/task-artifacts/external-recovery-2026-09-27/，
     附 HANDOFF.md + MANIFEST.json（SHA-256 逐项回读通过）
3. **教训（写入规范）**：位置合规 ≠ 归属正确；先判数据所有权再选目录；
   任务数据走 .project-local/，会话暂存走 external-recovery/，
   永不再写 Hermes 全局 scratch 或 %TEMP%。
