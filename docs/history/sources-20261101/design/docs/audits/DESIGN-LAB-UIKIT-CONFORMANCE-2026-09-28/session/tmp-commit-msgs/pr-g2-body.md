# G-2 / B2：SBOM 扩 lockfile 级绑定

对应 `docs/audits/DESIGN-LAB-CLOUD-AUDIT-2026-09-23-CROSSWALK.md` 的 **B2（R13）**。

## 为什么
`design-lab/config/sbom-v42.spdx.json` 只列 64 个 package 条目（PNG 二进制 +
第三方声明），**不覆盖真实依赖树**：`pnpm-lock.yaml` / `uv.lock` /
`requirements.txt` 里锁定的依赖版本与哈希都不在 SBOM 范围。CI 旧门只
`test -f` 查 SBOM 存在性，不校验内容。

本 PR 把三个锁文件提升为 lockfile 级 SBOM 绑定，并把 CI 门从"存在性"
升级为"真校验"。

## 设计（纯 stdlib）
CI 的 python venv 无 PyYAML，所以不引第三方解析器：

| 锁文件 | 解析方式 | 绑定内容 |
|---|---|---|
| `pnpm-lock.yaml` | 正则，严格限定 `packages:` 段（到 `snapshots:` 止）| 每条 `resolution.integrity` sha512 digest |
| `uv.lock` | `tomllib`（Py3.11+）| 每包 sdist/wheel hash |
| `requirements.txt` | 递归顶层 `-r` include | pinned spec |

绑定写入 SBOM 的 `lockfileBindings` 段（sha256 + 解析清单）。校验逻辑
fail-closed：锁文件 sha256 失配、或 manifest/pins 漂移，即 `check()` 报警。

## 捕获到的真实缺陷（审计价值）
初版解析器把 `packages:` 段抓到文件尾，把 `snapshots:` 段也并进来——
snapshots 段按 key 重新列依赖但**不带** `resolution.integrity`，于是 dict
按行序赋值时**用无 digest 的 snapshot 条目覆盖了 packages 段的 66 条 digest**，
造成 `integrityCount=0` 的虚假"lockfile 级保证"。修复后 pnpm 绑定
`integrityCount=66/66`，并用回归单测（`test_scoped_to_packages_section_only` /
`test_digests_captured_not_overwritten`）锁死。这正是审计要防的 phantom KPI。

## 改动
- `design-lab/scripts/verify_sbom.py`：新增 pnpm/uv/requirements 解析器 +
  `build_lockfile_bindings` + `_verify_lockfile_bindings`；`check()` 追加
  lockfile 完整性校验。
- `design-lab/config/sbom-v42.spdx.json`：写入 `lockfileBindings`
  （pnpm 66 条 / uv 20 包 / requirements 6 pins）。
- `scripts/generate_sbom_lockfiles.py`：幂等生成器。改锁文件后必须重跑，
  否则 CI 门红（sha256 fail-closed）。
- `design-lab/tests/test_sbom_lockfiles.py`：14 项 hermetic 单测，含
  fail-closed 负测试 + snapshot-overwrite 回归守卫。
- `.github/workflows/canonical-verify.yml`：`license-secret-gate` 把
  "SPDX SBOM present" 升级为 "SPDX SBOM verify"
  （`python design-lab/scripts/verify_sbom.py`，exit 1 = FAIL）。

## 实证（本机 B2 分支）
- `python design-lab/scripts/verify_sbom.py` → `VERIFY_SBOM=OK`，exit 0
  （CI 口径 bare python，无需 uv sync）。
- `test_sbom_lockfiles` 14/14；`test_evidence_helpers` 11/11（含既有
  `VerifySbomTests` 实跑改后的 `check()`，无回归）；`test_core_gates` 13/13。
