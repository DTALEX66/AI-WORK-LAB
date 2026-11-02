
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

# SPEC A — Design Tokens + 主题系统（UI_TOKENS）
你独占文件: apps/observer/frontend/src/index.css, tailwind.config.js, index.html
任务:
1. 重写 index.css 的 :root 与 html.light 变量块为上面"权威 Design Tokens"精确值：
   - 现有机制保留: Tailwind 走 rgb(var(--X-rgb) / <alpha-value>) 通道形式
   - 新增变量: --color-sidebar, --color-muted, --info-rgb, --radius-sm/md/lg/xl,
     --shadow, --blur, --motion-fast/base/modal/drawer/emphasis/pressed, --density-*
   - 颜色以 RGB 通道形式写: --primary-rgb: 42 145 255; --secondary-rgb: 32 205 225;
     --success-rgb: 34 197 94; --warning-rgb: 245 158 11; --error-rgb: 239 68 68; --info-rgb: 56 130 246
   - light 主题: bg #F4F7FA / panel #FFFFFF / panel2 #EAF0F6 / border #D5E2EC / ink #0B1420 /
     muted #5A7184 / sidebar #E4EBF2 / primary #1B7FE6 / secondary #0E93A5 / success #15803D /
     warning #B45309 / error #B91C1C / info #1D4ED8 （全部保证文字对比度>=4.5:1）
   - 保留 html.light 的 zinc-* 翻转块与 compact-hud 块与 prefers-reduced-motion 块
   - .panel/.panel2 圆角改 var(--radius-md)
2. tailwind.config.js: colors.extend 增加 sidebar:'var(--color-sidebar)', muted:'var(--color-muted)',
   info:'rgb(var(--info-rgb) / <alpha-value>)'; borderRadius extend sm:'4px' md:'10px' lg:'16px' xl:'22px';
   boxShadow extend glow/shadow; transitionDuration extend fast:120 base:180 modal:220 drawer:280 emphasis:420;
   fontSize 对齐 L4 typography(caption14/body18/h322/h228/h136/display48) 可选 extend。
3. index.html: 保留 pre-render 脚本机制（?theme= 驱动），不动结构。
验证: tsc --noEmit（CSS 不影响，跑一遍确认不炸）+ 自己写 1 个 vitest
 tests: 新建 src/index.css.test.ts 不行(vitest 对 css import 受限) → 改为写
 src/theme/tokens.test.ts: import 一个纯 TS 的 token 常量文件 src/theme/tokens.ts
 （你新建: 导出 DARK/LIGHT 两套精确值 + 断言 secondary dark==='32 205 225' 或 '#20CDE1'、
 primary==='42 145 255'，断言不含任何紫色 #7C6CF0/124 108 240 残留）→ vitest run 通过。
index.css 里的变量值与 tokens.ts 必须同值（tokens.ts 是 CI 可验证的单一源）。
