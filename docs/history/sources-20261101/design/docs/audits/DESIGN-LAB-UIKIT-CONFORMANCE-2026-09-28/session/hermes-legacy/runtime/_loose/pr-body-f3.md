## 范围

**Batch F-3：release-preflight 强化（真实 API 回读，fail-closed）**。2 新 + 2 改，基线 `8b2f49f`（如已在 F-2b 之后，则为其后的 main）。

## 为什么需要它（缺口实证）

`release-gate.yml` 中名为 **"API readback consistency check"** 的既有步骤**不调用任何 GitHub API**，只是把 `github.sha` 与 attestation 的 `subjectCommitSha` 做**同一次运行内产生的两个值**之间的字符串比对 —— 它无法证明 artifact 身份。审计 P1-CI 要求：需要 artifact proof 时必须 **真实 upload/query/download/hash**；发布纪律要求 asset / identity / checksum / installer / public readback 全部完成才算发布。

## 交付内容

**新增 `design-lab/scripts/verify_release_preflight.py`**（stdlib only；全部网络访问集中在一个可注入的 `fetch()`）
- 输出契约：`RELEASE_PREFLIGHT=<PASS|BLOCKED|INCOMPLETE> checks=N findings=[...]`；退出码 `PASS=0 / BLOCKED=2 / INCOMPLETE=3`
- 检查项：
  a. **identity**：`tag → commit SHA`（annotated tag 会二次解引用 `/git/tags`）
  b. **CI**：该精确 SHA 的 Canonical Verify run 结论必须为 `success`
  c. **artifact 真实回读**：经 API 定位 artifact → **下载** `archive_download_url` → 重算 sha256 与 API digest 或 `--expect-artifact-sha256` 比对
  d. **release assets**：tag 无 release → `RELEASE_NOT_PUBLISHED`；有则名称集合与 `--expect-assets`（支持 glob）相等
  e. **checksum**：每个已发布资产下载并比对本地 `artifacts.sha256`（未登记的资产 → BLOCKED）
- **fail-closed**：无 token / 无网络 / 下载不到 → `INCOMPLETE`（exit 3），**绝不当 PASS**
- **凭据卫生**：token 只从 `GITHUB_TOKEN`/`GH_TOKEN` 读取，**绝不接受命令行参数**；重定向处理器在**跨主机跳转时丢弃 `Authorization`**（防止 token 泄漏到签名 URL 主机）

**`release-gate.yml`：纯追加 +32/-0**（既有 74 行逐字节未动），新步骤仅 `if: startsWith(github.ref, 'refs/tags/')` 执行，token 走 `${{ github.token }}`，参数取自 GitHub 可信默认环境变量，**脚本体无表达式插值**（防注入）

**`design-lab/scripts/verify_design_lab.py`：仅 +7 行注释**（无逻辑改动），记录"为何**不**把新脚本并入 49 项聚合"——它需要 tag + token + 网络，且不可证明时返回非 0，并入日常链会把"无法证明的发布"变成红灯；沿用既有 `RELEASE_VERIFIER` 的排除先例

**测试 `design-lab/tests/test_release_preflight.py`：47 个注入式 fake-fetch 用例，全程不建 socket**（含 `test_full_pass_never_touches_urllib` 与 `test_no_token_opens_no_connection`）

## 验证证据（主线独立重跑）

```
design-lab/tests/test_release_preflight.py                      Ran 47 tests  OK
verify_release_preflight.py --tag v0.0.0-test （无 token）
  RELEASE_PREFLIGHT=INCOMPLETE checks=0 findings=["NO-GITHUB-TOKEN (…never PASS)"]   exit 3   ← 真实默认路径上证明不谎报
verify_design_lab.py                                            VERIFY_DESIGN_LAB=OK total=49 failed=0
git diff --stat -- release-gate.yml verify_design_lab.py        39 insertions(+), 0 deletions
```

## 诚实标注（未证明的部分）

1. **默认真实网络路径未被任何测试覆盖**：本环境无 `GITHUB_TOKEN`、无网络，只有注入 fake 路径被证明（`test_full_pass_never_touches_urllib` 证明全 PASS 路径不碰 socket）。真实 GitHub 行为只能在**真实 tag 运行**中确认 —— 而那是 **owner 授权**范畴，本 PR 不创建 tag、不执行发布。
2. **Actions artifact 索引有延迟**：新步骤从**自身 run**（`--run-id $GITHUB_RUN_ID`）查询 artifact；若上传尚未被索引，会报 `ARTIFACT-MISSING` 并保持红灯（已在 workflow 注释中说明：应重跑 job，**不得**削弱门禁）。未加 retry 循环（超出本批范围）。
3. **`--expect-assets artifacts.sha256,attestation-*.json` 是对"发布必须携带哪些文件"的假设**，无真实 release 无法验证；若实际发布资产集合不同，该步骤会 BLOCK 直到期望被更新 —— 这是有意的收紧，不是缺陷。
