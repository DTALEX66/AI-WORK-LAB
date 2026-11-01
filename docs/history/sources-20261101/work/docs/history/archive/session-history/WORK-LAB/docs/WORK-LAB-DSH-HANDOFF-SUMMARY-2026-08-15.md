# WORK-LAB 交接摘要 · 给 DeepSeek Harness（2026-08-19）

> 完整交接见 `50-taskpacks/WORK-LAB-DSH-HANDOFF-2026-08-19.md`（**最新权威**，含自动维护系统 + 颜色彻底修复 + 插件治理 + 鲸吟皮肤）。
> 历史：`WORK-LAB-DSH-HANDOFF-2026-08-18.md`（迁移 + 桌面版修复）、`WORK-LAB-DSH-HANDOFF-2026-08-15.md`（基线）。本文件是快速上手摘要。

## 接手什么

`D:/All projects/WORK-LAB`（GitHub `DTALEX66/WORK-LAB`）—— 客户端中立工作流控制面，管理 6 个 AI 客户端（Hermes / Codex / CC Switch / GitHub / OpenHuman / Open Design）+ 未来 AI 软件的 USER_GLOBAL 期望态。两活动模块：`10-workflow/workflow-assistance`（唯一 Writer）、`30-observer`（只读投影）。

## 当前状态（3 行）

1. `main` HEAD = `ad10333`（control-plane 系列；5 件 DSH adapter 交付物已 #118 merge）。
2. **DSH 已迁移 `D:\All projects\DSH`** + 桌面版图标/颜色修复（08-18，见旧摘要）+ **自动维护系统上线**（08-19）：`dsh-maintain.js` + 桌面壳启动钩子——**打开桌面 DSH 自动执行**颜色补丁/obsidian 修复/二进制检查/插件增量更新/重启/健康验证，日志 `dsh-maintain.log`。
3. **颜色彻底修复**（08-19）：根因 = update-checker 按钮用 `brand-primary` 做背景 + 硬编码 `#fff`；修复 = 官方语义变量 `button-primary-fill` + `label-primary-foreground`（任何皮肤可读，鲸吟下实测深蓝底白字）；maintain 自动重打。**鲸吟皮肤已生效**；31 插件全最新（除 remote-web-ui）；obsidian-memory 0.3.2 已装（vault 用户自填）。

## 下一步（按优先级）

1. **提交交接文档**：08-18 + 08-19 + SUMMARY 更新（共 3 文件）→ 申请 commit/push（每动作需批准）。
2. **主体升级 rc.5 → rc.7**（SOP §2；先 dry-run；消除新插件 peer soft-incompatible——credentials 需 rc.6+）。
3. **obsidian-memory vault 配置**（用户自填：侧边栏 Obsidian Memory 面板 / cordis.patch.yml / OBSIDIAN_VAULT_PATH）。
4. **remote-web-ui 更新**（cloudflared 下载网络通后重试）。
5. 历史挂起：WL3-100/110 收编、WL-DSH-040 付费 smoke（用户填 key）、SQLite 执行核心、frontend F2/F3、WL3-820。
6. 可选插件：`dsh-free-search`（搜索）、`dsh-vision-fallback`（视觉增强）。

## 不可违反的边界

- **E:\ 盘**：无逐路径逐操作授权禁止访问。
- **秘密/凭据**：不读不打印不复制不提交（含 DSH key，用户在 UI 填，Agent 不读）。
- **防外溢**：一切运行数据只在 `.hermes/task-runtime/`。
- **不 commit/push/PR/merge/release** 除非用户逐动作批准；禁止 destructive reset/clean/force-push。
- **Observer 只读**；**DSH 不是 Hermes 替代品**、不接管真实客户端配置、不写 Task Ledger 状态。
- **旧位置 DSH（`.hermes/task-runtime/deepseek-harness/`）保留不删**（回滚/对照基线）。

## 必读文件

- `AGENTS.md`（执行规则）→ `50-taskpacks/TASKPACK_SUMMARY.md` → `WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md` → 完整交接文档（08-18 版权威）。

## 关键工具命令

- 测试铁律：`env -u PYTHONPATH uv run --frozen --group ci --group ci-adapters pytest`
- 质量门：`python 10-workflow/workflow-assistance/scripts/workflow/run_quality_gate.py verify`
- terminal 必须经 `hermes-project-data.py --project . run -- <单命令>`（禁 chaining/重定向/外部路径）。
- pnpm 逐次 pin：`node .hermes/task-runtime/run-pnpm.js <cwd> <args>`。
- DSH CLI（新位置）：`node .hermes/task-runtime/run-dsh.js "D:\All projects\DSH\deepseek-harness\source" "D:\All projects\DSH\deepseek-harness\dsh-home" <dsh命令>`。
- DSH 桌面构建：`powershell -File "D:\All projects\DSH\dsh-desktop\build-x.ps1"`（前置：SUBST `X:` → `D:\All projects\DSH\dsh-desktop` + rust GNU toolchain；`~/.cargo/config.toml` 已修转义，**不得再写未转义反斜杠**）。

## 建议执行顺序

读 AGENTS.md + 交接文档 → review DSH 交付物 → 申请 commit → 体积膨胀（等批准）→ WL3-100/110 → DSH-040（批准后）→ 其余 WL3。每步外部变更前列出精确动作等批准，不自我授权。
