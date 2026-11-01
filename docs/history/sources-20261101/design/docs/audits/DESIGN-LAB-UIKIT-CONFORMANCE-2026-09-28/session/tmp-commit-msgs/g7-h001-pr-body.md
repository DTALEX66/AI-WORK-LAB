# G-7 / H001：main-branch CI artifact proof gate（真实 API 回读）

对应 FINAL TaskPack section H / **H001**：
> "main run #182 artifacts=0。如要求 artifact proof，必须真实 `upload -> GitHub API query -> identity -> download/readback -> hash -> run/SHA binding`。"

## 为什么
release 层（`release-gate.yml`，tag-only，E5，owner-gated）已有完整真实回读链
（`verify_release_preflight.py`），但**只覆盖 tag 发布**，覆盖不了 main 分支
日常 run：canonical verify 现上传 2 个 artifact（`secret-history-report` +
`workbench-e2-<sha>`），却无任何 step 证明它们真落到 GitHub、字节一致、
且绑定到精确 run/SHA。H001 补的就是 main 侧这条腿。

## 交付（REUSE-FIRST：compose 既有 `verify_release_preflight` 网络基元）
- **`design-lab/scripts/verify_ci_artifact_proof.py`**（新增，纯 stdlib，sibling-load 复用）
  - 四段证：run/SHA identity → `/actions/runs/{id}/artifacts` 查询 → 下载 → sha256 重算 vs API digest
  - **三态 fail-closed**：`PASS`(0) / `BLOCKED`(2，矛盾) / `INCOMPLETE`(3，无 token / 未索引 / 不可达)——未索引**绝不假 PASS**
  - 索引延迟（H001 的常态）：一次定拍 re-query（默认 20s，可注入 `sleep` 测试）；BLOCKED 结果不 re-query（终态）
  - run/SHA 绑定 proof record 落盘 `.project-local/`（gitignored）
  - **诚实边界**：第 4 段比对的是两个 API 产出的事实（下载字节 digest vs GitHub 自记 digest）= download round-trip proof；独立的 asset-set + checksum 绑定仍属 release 层，本 PR 不重造
- **`.github/workflows/canonical-verify.yml`**：新增**非 required** job `ci-artifact-proof`
  - `needs: [license-secret-gate, workbench-browser-e2e]` + `if: always()`（两个 uploader 都 `if: always()` 上传，红 run 也要证）
  - `GITHUB_TOKEN` 经 `env: ${{ github.token }}`（可信）注入，`run:` 体纯静态、无事件插值
  - **additive，不动既有 required checks**；晋级 required check 属 H003/owner 步骤，不在本次范围
- **`design-lab/scripts/verify_design_lab.py`**：记录 H001 排除日聚合链的决策注释（与 F-3 同款先例）
- **`design-lab/tests/test_ci_artifact_proof.py`**：16 项 hermetic（注入 fake fetch/sleep，零 socket）
- **报告 rebind**：`generate_current_reports.py` 重生成 10 快照（diff 全为 G-7 surface：新文件登记 + tests 1584→1626 + subjectSha 重绑，无无关漂移）

## 验证
- `python -m unittest design-lab.tests.test_ci_artifact_proof` = **16/16 OK**
- 默认无 token 路径实跑 = `CI_ARTIFACT_PROOF=INCOMPLETE checks=0`（exit 3，**不假 PASS**）
- YAML 校验通过（job `name` 含 `:` 已加引号）

## 证据分级
本 PR 交付的是**结构门 + 回读机制**（E1/E2）；真实 CI 回读在 main run 上跑 `ci-artifact-proof` job 后产生。晋级 required check（H003）与 tag-time release E5 均 owner-gated。

## 回滚
revert 本 PR 即完全还原（job 非 required、新文件独立、注释 additive）；`verify_design_lab.py` 只多了排除注释，无行为变化。