# Batch F-3 规格：release-preflight 强化（真实 API 回读，fail-closed）

## 背景（事实，先读代码再动）
- `.github/workflows/release-gate.yml`（仅 `workflow_dispatch`）当前链：checkout 精确树 → `uv sync --locked` → `verify_design_lab.py` → `verify_capability_evidence_v4.py` → `verify_release_gate.py` → 生成 runtime Evidence Attestation（exact SHA）+ `sha256sum`（attestation / SBOM / capability-index）→ 上传 artifact → 名为 "API readback consistency check" 的一步。
- **缺口**：那一步**并未调用 GitHub API**，只是把 `github.sha` 与 attestation 的 `subjectCommitSha` 做字符串比对。审计要求（报告 P1-CI）：需要 artifact proof 时必须**真实** upload/query/download/hash；不能拿没有 artifact 的 run 冒充 artifact 回读。发布纪律要求 **asset / identity / checksum / installer / public readback** 全部完成才算发布。

## 交付物
1. 新增 `design-lab/scripts/verify_release_preflight.py`（**stdlib only**，网络访问集中在一个可注入的 `fetch` 函数上以便测试）
   - 参数：`--tag <tag>`、可选 `--sha <sha>`（默认 `git rev-parse HEAD`）、`--repo <owner/name>`（默认从 git remote 解析）、token 取自 env `GITHUB_TOKEN`
   - 检查项（逐项 finding；不可达/不匹配一律 fail-closed）：
     a. **identity**：`GET /repos/{repo}/git/ref/tags/{tag}` 解出的 commit SHA == 目标 SHA（annotated tag 需二次解引用）
     b. **CI**：`GET /repos/{repo}/actions/runs?head_sha={sha}` 中 Canonical Verify 的 `conclusion == success`（缺失/非 success → finding）
     c. **artifact 真实回读**：该 run 的 artifacts 列表存在期望 artifact，取 `archive_download_url` 下载并算 sha256 与期望值比对
     d. **release assets（若 release 已存在）**：`GET /repos/{repo}/releases/tags/{tag}` 的 assets 名称集合与期望集合一致；tag 存在但 release 缺失 → `RELEASE_NOT_PUBLISHED`
     e. **checksum**：发布资产（若有）sha256 与本地 `artifacts.sha256` 比对
   - 输出契约：`RELEASE_PREFLIGHT=<PASS|BLOCKED|INCOMPLETE> checks=N findings=[...]`
     - 无 token / 无网络 / 无法下载 → **`INCOMPLETE`** 并列出缺什么，**绝不当 PASS**
     - 退出码：PASS=0；BLOCKED/INCOMPLETE=非 0（fail-closed）
2. 接入 `release-gate.yml`：在既有步骤**之后**追加一步运行该脚本（`if:` 条件写清，仅当 ref 为 tag 时），打印 findings。**不得**放宽或删除任何既有步骤。
3. 新增测试 `design-lab/tests/test_release_preflight.py`（unittest，注入 fake fetch，**不发真实网络请求**）：
   - tag SHA 匹配 / 不匹配；annotated tag 解引用
   - CI 非 success → BLOCKED；run 缺失 → BLOCKED
   - artifact 存在但 sha256 不匹配 → BLOCKED；下载不可达 → INCOMPLETE
   - tag 存在但 release 未发布 → 对应 finding（不谎报 PASS）
   - 无 token → INCOMPLETE（**不得** PASS）
4. 确认 `verify_design_lab.py` 的 49 项聚合**是否会自动发现**新脚本：若会，必须保证聚合仍 `OK total=49 failed=0`（如冲突，选择不破坏既有聚合的接入方式并说明）。**不得**削弱既有门禁。
5. **不做**：不执行真实 release、不创建/推送 tag、不改 `reports/`、`AUTHORITY.md`、`.project/`、`docs/`、`AGENTS.md`、`design-lab/config/**`、`apps/workbench/**`（另一子代理的域）。

## 验证（贴原始输出）
- `.venv/Scripts/python.exe design-lab/tests/test_release_preflight.py` 全绿
- **无 token 实跑**：`verify_release_preflight.py --tag v0.0.0-test` → 必须得到 `INCOMPLETE`（证明不谎报）
- `.venv/Scripts/python.exe design-lab/scripts/verify_design_lab.py` → `VERIFY_DESIGN_LAB=OK total=49 failed=0`
- **不要运行** `scripts/verify_authority_gates.py`（另一子代理也在跑同一工作区，主线会在两路都结束后统一运行，避免并发重写同一快照）
- `git status --short`、`git diff --stat`

## 命令纪律
- wrapper 单命令：`python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单命令>`，workdir=`D:/All projects/DESIGN-LAB`；禁 shell 串联。
- 不 commit / stash / push / 建分支；不装依赖；**测试中不得发真实网络请求**。
