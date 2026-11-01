# 前端基线验证契约（2026-09-30 执行）

适用于观察者前端（`apps/observer/frontend`，React + Vite + Tailwind + Tauri 2）的首次接管验证。

## 必查项（真实工具输出，不编造 PASS）

| 检查 | 命令 / 方法 | 本轮结果 |
|---|---|---|
| node 版本 | `node --version`（PATH shim `v26.7.0`；`C:\Program Files\nodejs\node.EXE` 是真实二进制） | OK |
| typecheck | `.bin/tsc.cmd -p tsconfig.json --noEmit`（不通过 `.cmd` 解析坑：直接调用 `.cmd`，不通过 `subprocess.run([node, cmd_path])`） | PASS rc=0 |
| vitest | `.bin/vitest.cmd run`（同上；72 测试 / 11 文件 / 2.27s） | PASS |
| 前端契约文件存在 | `package.json` + `vite.config.ts` + `tsconfig.json` + `index.html` + `src/lib/viewRegistry.ts`（22 lanes）+ `src/App.tsx`（deep-link/theme/layout/compact/full/palette/drawer/toast） | OK |
| Tauri 契约 | `tauri.conf.json`（v2 schema，main 1280×820、panel 440×780、CSP 固定、icons 列表、bundle targets=all） | OK |
| 工具链缺失 | `pnpm` MISSING（不强制安装）；`cargo`/`rustc`/`clippy` MISSING（TAURI_BUILD BLOCKED，真实外部阻塞） | 真实 BLOCKED |

## 关键坑（已在技能 SKILL.md 记录为 pitfall 30/31）

- `.cmd` 二进制（`tsc.cmd`、`vitest.cmd`、`npm.cmd`）不能通过 `subprocess.run([node, "...vitest.cmd"])` 执行——`node` 把 `.cmd` 当 JS 文件解析，抛 `SyntaxError: missing ) after argument list`（`.cmd` 是批处理脚本，不是 JS）。正确做法：直接调用 `.cmd` 路径（`[str(cmd_file), ...]`），不加 `node` 前缀。
- `node.EXE` 的真实路径（`C:\Program Files\nodejs\node.EXE`）与 PATH shim（`C:\Users\ALEX\AppData\Local\hermes\tools\node-26.7.0-win32-x64\node.EXE`）不同——写脚本时不要假设一个固定绝对路径，使用 `shutil.which("node")` 获取运行时解析的路径。
- 当 `cargo` 缺失时，Tauri 打包（`bundle targets=all`、`frontendDist: ../frontend/dist`、Windows `.exe` 候选、真实 WebView2 层）只能标记 `BLOCKED`，不能编造为 `PASS`（与规范质量门禁 `TAURI_WINDOWS_PENDING` 一致）。
- 前端基线验证完成后，UI 编辑必须在独立分支执行（`main` 不直接修改），并在每次编辑后重新跑 `typecheck` + `vitest` + `vite build` 确认无回归。

## 证据位置（本项目，非提交）

- `.project-local/runs/frontend-baseline.json`（验证结果 JSON）
- `.project-local/runs/frontend-vitest-output.txt`（72 PASS 文本）
- `.project-local/artifacts/handoff-stage-e-20260930.md`（阶段 E 手动交接，含授权请求清单）
- `skills/software-development/windows-development-environment/references/g15-registry-reconciliation.md`（G15 相关）
