# DESIGN-LAB Deep Audit — Child C：Packaging / CI 全景 / reports-current / Branch 审计 / Release Gate

你是 DESIGN-LAB 的 Packaging & CI/CD 审计工程师。仓库：`D:/All projects/DESIGN-LAB`，remote `DTALEX66/DESIGN-LAB`。冻结基线 main SHA = `6a16c40b7a48f72757a0327ec07462d23449bb11`。

## 硬性规则
- **只读**：禁止 commit/stash/push/改 tracked 文件；禁止构建产物写进 repo（scratch 与 venv 只放 `.hermes/task-runtime/dl-ad-pkg-ci/`）。
- terminal 走包装器：`python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单条命令>`（workdir = `D:/All projects/DESIGN-LAB`）；批量逻辑用 execute_code。
- 中文输出；证据=文件:行 + run/job ID + SHA。

## 任务 1：Packaging 全量（pyproject / wheel / resources）
- 完整读 `pyproject.toml`（及 setup.py 若有）：wheel 构建配置、force-include/package-data、build backend、uv 使用情况。
- 判定 H6：Design System manifests（`design-lab/design-systems/**`）是否进 wheel？读配置逐项给证据。
- 本地实证（在 `.hermes/task-runtime/dl-ad-pkg-ci/` 内）：
  1. 构建 wheel（按仓库实际工具：uv build 或 python -m build；先查 docs/README 真实命令，不得伪造）
  2. `python -m zipfile -l dist/*.whl` 列 inventory：逐项标 应包含（Python package / Workbench build / DB schema SQL / design-system manifests / adapter scripts）vs 实际缺失 vs 不应包含（.project-local / .git / credentials / cache / logs / test artifacts / node_modules / Playwright browsers / 用户资产）
  3. isolated install smoke：新建 venv → pip install wheel → cd 到 repo 外 → `python -I -c "import design_lab; ..."` 验证 import + load catalog + 建 Project/Brief/Direction/choose/bind/readback（用最小脚本，DB 放临时目录）
  4. 如实报告：哪一步失败、失败输出（完整保留关键行）
- 给出可复制命令集（真实命令）+ 缺失修复方案（优先 importlib.resources，禁止 PROJECT_ROOT/git 路径）
- 给出 GitHub Actions `wheel-smoke` job YAML（按仓库实际 package manager；含 checkout / setup-python / build / inspect / isolated install / cd repo 外 smoke / 上传日志；禁伪 YAML）

## 任务 2：CI 全景（.github/workflows/**）
- 列出全部 workflow 文件与 job 清单；重点读 canonical-verify.yml、release-gate.yml 及任何 browser/packaging 相关。
- 读最新 main run `35546749035`（success）的 jobs（gh api .../actions/runs/35546749035/jobs）：逐 job 列 name + conclusion，标哪些是 skip/非 required。
- branch protection：`gh api repos/DTALEX66/DESIGN-LAB/branches/main/protection`（403 就写 403 PERMISSION_DENIED，不得引用旧文本）。
- Release Gate 现状：无 release（gh release list 空）；读 release-gate.yml 的触发条件（tag-only?）与 gate 项；requiresRequalification / effective evidence 门如何阻止旧 E3 直接到 E5。
- 给出 Browser E2E exact-SHA CI 与 wheel-smoke 的缺口清单（与 Child B 结论交叉时标注）。

## 任务 3：reports/current 逐文件新鲜度
- 每个 `reports/current/*.json`：读 subjectSha/generatedAt（或 gitObservation）与 6a16c40 比对 → LIVE_STATE / LAST_GENERATED_PROJECTION / STALE + 建议（STALE 必须显式标）。
- `design-lab/config/current-report-index.json` 的 rebind 状态（注意 steady-state=STALE 是自我引用正常态，不算缺陷，如实标注）。

## 任务 4：Branch 全量语义审计（35 分支）
- `git branch -r` + 对每个分支：`git rev-list --left-right --count origin/main...origin/<branch>`（ahead/behind）
- 合并分支验证：`git log --oneline origin/main..origin/<branch>` 为空 = MERGED_CLEANUP_CANDIDATE（只列候选，禁止建议删除）
- 未合并分支逐个按内容分类（不看名字）：MERGED_CLEANUP_CANDIDATE / DOC_RESIDUAL / SEMANTICALLY_ABSORBED / PARTIAL_RESIDUAL / HISTORICAL / ACTIVE / DO_NOT_MERGE_WHOLE。特别审计：docs/e-slice-session-summary-20260919、codex/deepseek-authority-r1、migration/dl-directory-convergence-r1、fix/r4-h3-prod-e3、feat/minimax-h3-e3、feat/f4-host-e3-harness、fix/quarantine-evidence、test/jury-preflight。
- 输出表：branch | head SHA | ahead | behind | unique commits | semantic status | recommended action（保留/owner-gated 删除候选/不整体合并+原因）

## 输出格式（最终答案必须是该 JSON）
{"summary": "<10行内中文核心结论：wheel 现状（含 H6 判定）/ CI 真实覆盖 / reports 新鲜度 / branch 卫生 / release gate 状态>",
 "packaging": {"h6_wheel_design_systems":"...", "build_cmd":"...", "inventory_missing":[...], "inventory_should_not_include":[...], "isolated_smoke":"PASS/FAIL + 关键输出", "fix_plan":[...], "wheel_smoke_yaml":"<YAML 代码块>"},
 "ci": {"workflows":["..."], "latest_run_jobs":["name=conclusion", ...], "branch_protection":".../403", "release_gate":"...", "gaps":[...]},
 "reports_current": ["file: subjectSha=X vs main=Y → STATUS", ...],
 "branches": ["branch: ahead/behind → CLASS → action", ...],
 "defects": ["[P0/P1/P2] ...（证据）", ...],
 "evidence_refs": ["run/job/file 引用", ...],
 "blocked": ["...", ...]}
