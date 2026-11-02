
## 共享铁律（四个 spec 全部适用）
repo: D:/All projects/WORK-LAB（git-bash；terminal 调用必须 workdir='D:/All projects/WORK-LAB'，
wrapper 形式: python "C:/Users/ALEX/AppData/Local/hermes/bin/hermes-project-data.py" --project . run -- <单命令>；
多命令用 execute_code + subprocess(list args, 无 shell)）。
前端目录: apps/observer/frontend（React18+Vite5+Tailwind3+vitest，node_modules 已装好）。
UI 设计权威（已入项目，gitignored）: .ui-reference/WORK-LAB/
  - 10_B10_最终版高保真可部署UI/  = 视觉最高权威
  - 07_B07_前端开发规范_L7/       = 路由/权限/组件契约/治理规范
  - 04_B04_组件系统与DesignTokens_L4/WORK-LAB_design_tokens.json
  - 06_B06_交互状态系统_L6/WORK-LAB_interaction_tokens.json
  - _meta/WORK-LAB_CODEX_prompt.md = CODEX 任务包（产品定位/视觉硬约束/验收）
## 权威 Design Tokens（B10=L4=L7 三处一致，唯一真值，全部 CSS 变量化）
dark(默认): --color-bg:#050D16 --color-sidebar:#07111C --color-panel:#081420
  --color-panel2:#0C1B2A --color-border:#17435D --color-ink:#EEF6FC --color-muted:#8EABBC
  primary #2A91FF (rgb 42 145 255) / secondary #20CDE1 (rgb 32 205 225)
  success #22C55E / warning #F59E0B / error #EF4444 / info #3882F6
  radius sm4/md10/lg16/xl22 / shadow 0 20px 80px rgba(0,0,0,.35) / blur 18px
  motion fast120 base180 modal220 drawer280 slow(强调)420 pressed80 scale .99
  density comfortable68/default56/compact44
light(由 SPEC-A 定义翻转; 对比度>=4.5:1, primary 加深保对比)
## 视觉硬约束（CODEX 提示词）
深海军蓝控制台质感；禁暖橙/米金/杂志风；禁紫色（现有 index.css secondary=#7C6CF0 是违规残留，
SPEC-A 换成 #20CDE1 cyan）；禁三项目混色；连线可做慢速虚线流动/脉冲；尊重 prefers-reduced-motion。
## 数据契约铁律（现有代码已建立，不得破坏）
快照类型 src/types.ts SnapshotV3：backend 只有 transport/coverage/governance/workspace/projects/
executions/tasks/tokenSummary/git/ci/sourceRefs/software。没有 rules[]/approvals[]/integrations[]/
audit[] 数组 → 相关新页面必须渲染**诚实的 EMPTY/UNKNOWN 态**（页面标题+说明+真实可用数据如
governance family 状态、ci runs、sourceRefs、workspace.plan），禁止编造 KPI/数据。
## 依赖铁律（冻结 scope，不动 lockfile）
不新增任何 npm 依赖（react-router 禁止！沿用现有 ?view= 参数路由机制 + viewRegistry；
recharts/cva/clsx/tailwind-merge/lucide-react 已可依赖）。package.json/package-lock.json 一律不动。
## 验证铁律
每个 spec 完成必须: cd apps/observer/frontend && node node_modules/typescript/bin/tsc --noEmit
(禁用 tsc -b, 避免 tsbuildinfo 并发冲突) 通过 + 自己的 vitest 测试通过
(npx vitest run <你自己的测试文件>)。不要跑 vite build（mainline 最后统一跑）。
## 边界
只改自己 spec 列出的文件；git add 仅限自己新增/修改的文件；不 commit 不 push 不切分支。

# SPEC D — App Shell + Command Palette 接线 + 交互/动效
你独占: apps/observer/frontend/src/components/layout/Sidebar.tsx, TopStatusBar.tsx,
src/App.tsx（三处修改）。
任务:
1. Sidebar.tsx: 260px↔72px 可折叠（现有 App 有 layout 参数? 折叠用本地 state + 顶部按钮;
   72px 时只显示图标 tooltip; 移动端(<768)隐藏为 overlay Sheet — 简单 media query 实现, 无新依赖）;
   现有 Sidebar 读 VIEW_REGISTRY, 新增 5 lane 自动出现; 分组: 概览/执行(agents,executions,task-packs,
   approvals)/洞察(monitoring,audit,software,trust)/治理(rules-policy,integrations,models,memory,tools,
   delivery,settings) — 分组可折叠。
2. TopStatusBar.tsx: 加全局搜索框(点击=打开 CommandPalette, 显示 "搜索或命令…  Ctrl+K") +
   通知=transport state(LIVE/STALE/OFFLINE 现有) + 保持现有 revision 显示。
3. App.tsx: 引入 SPEC-B 的 CommandPalette + useToast(若已装 B 的文件): 全局 keydown Ctrl/Cmd+K 切换,
   items = VIEW_REGISTRY 所有 view(跳转=setView)+ 主题/布局切换动作; 不改变现有 ?view= 深链机制。
   KPI count-up 已存在则保留; hover 过渡类统一 120-180ms（只加 className 不动逻辑）。
   所有 overlay(Esc 关闭)与 prefers-reduced-motion 已由 CSS 层处理。
约束: 不碰 viewRegistry.ts（SPEC-C 独占）、不碰 ui/ 组件（SPEC-B 独占）、不碰 index.css/tailwind
（SPEC-A 独占）。若 SPEC-B 的 command-palette.tsx 还没落地（并行执行中），按约定 API 写
 （import { CommandPalette, type PaletteItem } from '@/components/ui/command-palette'）并
 在你的验证里加一个 mock fallback: 若 import 失败则 typecheck 会报错 → 此时等待后重跑 tsc
 （mainline 会在所有 spec 完成后统一 tsc/build, 你本地 tsc 若因并行未落地而失败, 记录到报告
 open_decisions_for_mainline 并注明是跨 spec 时序, 不算你的缺陷）。
验证: tsc --noEmit（同上时序容忍）; 你负责 App 冒烟: 新建 src/App.smoke.test.tsx 渲染 <App/>
（vi.mock useLiveSnapshot 返回最小 snap）断言 Sidebar 含"审计"分组与 Ctrl+K 提示文本 → vitest 通过。
