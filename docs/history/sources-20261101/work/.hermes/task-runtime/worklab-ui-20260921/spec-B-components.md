
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

# SPEC B — 组件系统 shared-ui-core（新建 ui 组件）
你独占目录: apps/observer/frontend/src/components/ui/（可新增文件；badge.tsx/card.tsx 已存在，
只允许在它们缺失能力时按既有 API 补充，不得破坏现有导出）。
新建组件（全部用 SPEC-A 的 CSS 变量；无新依赖；cva+clsx+tailwind-merge 已有）:
1. button.tsx: Button(variant: primary|secondary|ghost|danger, size: sm|md|lg, disabled, iconLeft?:LucideIcon)
   hover 120-180ms; pressed scale(.99) 80ms; focus-visible ring 2px var(--color-primary) offset 2px
2. input.tsx: Input + SearchInput(带 lucide Search 图标前缀) + Select(原生, 样式化)
3. tag.tsx: Tag/Badge 状态色(success/warning/error/info/neutral) — 已有 badge.tsx 则扩展复用
4. modal.tsx: Modal(open,onClose,title,children,footer?) 220ms; Esc 关闭; focus 移入; aria-modal;
   backdrop 0.62
5. drawer.tsx: Drawer(side='right'|'left',open,onClose,title,children) 280ms cubic-bezier(.2,0,0,1)
6. toast.tsx: useToast()+Toaster: 4s 默认, 堆叠 gap 12, success/error/info
7. states.tsx: EmptyState(title,description,action?), LoadingSkeleton(rows?), ErrorState(message,retry?),
   OfflineState() —— 对应 L7 五态契约
8. command-palette.tsx: CommandPalette({items:{id,label,icon?,group?,run()}[],open,onClose}):
   Ctrl/Cmd+K 打开, Esc 关闭, 上下箭头+Enter 选择, 模糊过滤(简单 includes 即可, 无依赖),
   role=dialog aria。
验证: tsc --noEmit 通过; 新建 src/components/ui/components.test.tsx (vitest+@testing-library/react
已装): 至少测试 Modal Esc 关闭+aria, CommandPalette 键盘导航(输入过滤+Enter 触发 run),
EmptyState 渲染 title → 全绿。
