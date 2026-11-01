# DESIGN-LAB Deep Audit — Child B：Workbench 前端 + Browser E2E + Design System UI

你是 DESIGN-LAB 的前端审计工程师。仓库：`D:/All projects/DESIGN-LAB`。冻结基线 main SHA = `6a16c40b7a48f72757a0327ec07462d23449bb11`。

## 硬性规则
- **只读**：禁止 commit/stash/push/改 tracked 文件。scratch 只写 `.hermes/task-runtime/dl-ad-frontend-e2e/`。
- terminal 走包装器：`python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单条命令>`（workdir = `D:/All projects/DESIGN-LAB`）；读文件优先 read_file/search_files。
- 中文输出；证据=文件路径:行号。

## 任务 1：apps/workbench 完整审计
读 `apps/workbench/**`、package.json、pnpm-workspace.yaml、pnpm-lock.yaml、tsconfig、vite config、build 产物（committed build/）。
回答：
1. Workbench 是「产品 UI」还是「debug/form shell」？列出实际存在的页面/panel（逐项：Project / Asset / Reference / Brief / Direction / Choice / DesignSystem / DesignIR / Host Execution / Readback / Revision / Evidence UI 各自是否存在、成熟度）。
2. TypeScript strict 开启与否；TS contract 类型是否覆盖每个 API payload。
3. API client、error states、loading states、empty states、asset picker、reference picker、state refresh、browser testability（可定位的 DOM id）现状。
4. committed build 与 main.ts 是否同步（CI no-drift 机制）。
5. 判断：是否需要框架迁移（React 重写）？只有真实工程理由才建议；否则明确「Vanilla TS + Vite 继续」+ 必须修的清单 vs 以后可做的清单。

## 任务 2：Browser E2E 现状（LOCAL E2 vs EXACT-SHA CI E2）
- 找 `design-lab/tests/` 下 browser E2E 测试文件（test_*browser* 或类似）：shell 逻辑、probe skip 条件（node/npm-cache/Chromium 三探）、executablePath 零下载启动、persisted DOM readback 断言。
- 读 `.github/workflows/` 中 canonical-verify.yml（及其引用的 job）确认 browser E2E 在 CI 中如何运行：CI 上是否有 Chromium？实际是 RUN 还是 SKIP？CI 里 skip 算不算 green？
- 最新 main run（35546749035, success）中该 job 的结论：用 `gh api repos/DTALEX66/DESIGN-LAB/actions/runs/35546749035/jobs` 读 job 级 conclusion，找出 browser E2E 相关 job 是 success/skipped/failed。
- 判定：EXACT-SHA CI E2 当前 = 真跑（RUNTIME_VERIFIED）还是 skip（SKIP_NOT_PASS）？给出证据。
- 给出「Browser E2E exact-SHA CI 成熟方案」缺口清单（checkout exact SHA / pnpm frozen / Playwright browser 安装策略 / service health / failure artifact 上传 trace+截图+DB 去敏快照 / 缓存边界：pnpm+playwright+uv 可缓存，runtime DB/user assets/token 禁止缓存）。

## 任务 3：Design Systems 前端与资源通路
- 读 `design-lab/design-systems/**`、manifests、loader、catalog、package-resource access（importlib.resources 还是 git checkout 相对路径？）。
- 判断：源码 checkout 可用 ≠ wheel 安装后可用 —— 安装态（离开 repo CWD）能否 load catalog？（若 Child C 负责 wheel 实证，你只给代码级判断 + 所需证据类型，并标注依赖 Child C 结果）

## 输出格式（最终答案必须是该 JSON）
{"summary": "<10行内中文核心结论：Workbench 成熟度判定 + Browser E2E 当前真实状态 + 最大前端缺口>",
 "workbench_assessment": {"product_ui_or_shell":"...", "panels": ["..."], "ts_strict":"...", "must_fix": ["..."], "later": ["..."], "framework_migrate":"..."},
 "browser_e2e": {"local_e2":"...", "ci_exact_sha":"...", "ci_job_evidence":"...", "gap_to_mature": ["..."]},
 "defects": ["[P0/P1/P2] ...（file:line 证据）", ...],
 "evidence_refs": ["...", ...],
 "blocked": ["...", ...]}
