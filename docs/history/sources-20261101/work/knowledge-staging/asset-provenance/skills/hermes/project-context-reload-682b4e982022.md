---
name: project-context-reload
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/project-context-reload/SKILL.md
---

---
name: project-context-reload
description: "Reload global, project, and positioning configs before work."
version: 1.0.0
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [config-reload, project-context, global-config, naming-contract, sync-verification]
---

# Project Context Reload（三层配置载入）

## When to use

- User asks to "重新载入项目定位/项目配置/全局配置" or "载入项目配置/全局配置" (often mentioning 有更新/减重/去冗余, or 稍后发减重更新包).
- **SCOPE GUARD（用户 2026-08-14 纠正，最高优先）**: "载入全局配置/项目配置/项目定位" 指**当前活跃项目**的三层。Layer 4（WORK-LAB Codex/Hermes overlay）**仅在用户明说 Global Config Reload / WORK-LAB overlay、或当前项目就是 WORK-LAB 时才执行**。在 DESIGN-LAB 会话里说"载入全局配置/云端有更新" = DESIGN-LAB 三层（README + manifest + PRODUCT_DEFINITION/BOUNDARY_CONTRACT + identity gate + 双端同步），**禁止**顺手去修 ~/.codex overlay 或 HERMES_HOME——一次真实漂移被用户当场怒斥（"你特么是不是又漂移了，你不是DESIGN-LAB项目吗"）。不确定当前活跃项目时先问，不要猜。
- **"双端"= 本地工作树 vs 云端 GitHub，不是两个项目仓库（validated 2026-08-15）**：用户说"双端/双端一致/双端同步"时，指 `git fetch origin <branch>` 后 `HEAD` 与 `origin/<branch>` SHA 相等 = 一致；修复在本地、云端未推 = 本地领先。把"双端"误解为 WORK-LAB vs DESIGN-LAB、并在交接/总结里混入另一仓库，被用户怒斥"我说的双端指的是本地和云端，别特么老混这WORK LAB啊"——双端检查永远只对**当前活跃项目**的 local↔origin 做。

- Starting a new phase of work where configs may have been changed by parallel sessions, migration tasks, or an incoming update pack.
- Verifying a repo is still in sync with origin before acting (the "reload then work" ritual).

## The three layers (load in order)

### Layer 1 — 全局配置 (environment root)
The global config root is usually its OWN Git repo (e.g. `D:/All projects/OS External Configuration`) containing EXTERNAL_DEPENDENCIES.md, toolchains, uv-cache, venvs.

1. Confirm the root and that it is a Git repo (`git status -sb`, `git log --oneline -3`).
2. **Check uncommitted diff** — `git diff --stat` + `git diff`. When the user says "有更新/减重/去冗余", the diff IS the update: report it (paths renamed, new sections added) but **do NOT auto-commit** — it may be a parallel session's WIP or waiting for the user's update pack.
3. Read EXTERNAL_DEPENDENCIES.md (or equivalent): env vars (UV_CACHE_DIR, UV_PROJECT_ENVIRONMENT, TESSDATA_PREFIX), toolchain paths (ffmpeg, tesseract), venv name.
4. **Detect doc-vs-environment drift**: compare every path the doc names against the real filesystem. Common state: doc already points to a NEW venv name/path while the OLD directory still exists on disk ("文档先行、环境未同步"). Report it explicitly; do NOT rename/rebuild on your own — the user may fold it into the update pack.

### Layer 2 — 项目配置 (project config)
1. `pyproject.toml` / product manifest: name, version, requires-python, ruff target.
2. `AGENTS.md`: safety rules (protected drives, test temp root constraint, secrets policy), config category table.
3. Git state: `git status -sb` (clean worktree?) + **dual-end sync check**: `git fetch origin <branch>` then `git rev-parse HEAD origin/<branch>` — equal SHAs = in sync.
4. **fetch SSL failure ≠ out of sync**: a `schannel: failed to receive handshake` fetch error is transient network; the remote-tracking ref may already be current, so `rev-parse HEAD origin/main` still proves sync. Don't treat the fetch error as a sync failure.
5. When the user says "稍后发你减重更新包": load the current state as-is, wait for the pack, make no preemptive changes.

### Layer 3 — 项目定位 (positioning / identity)
1. Locate the BINDING contract (e.g. `docs/truth/NAMING_CONTRACT_V2.md`, marked "binding 不可漂移") — read its fixed naming table; it is the single authority over product/tech identity.
2. Identify SUPERSEDED docs (banner at top) — read-only history, do not treat as current truth.
3. Read identity/capability docs (PRODUCT_IDENTITY_V2, CAPABILITY_ATLAS) for status-machine semantics (not_scoped → … → released).

### Layer 4 — WORK-LAB 全局配置（Hermes + Codex overlay 重载）

When the user says "载入全局配置" / "Global Config Reload" and means the WORK-LAB-managed overlay, the authority is **NOT** OS External Configuration — it is the WORK-LAB repo (`10-workflow/workflow-assistance/`), which pushes HERMES-side assets to `HERMES_HOME` and Codex-side assets to `~/.codex` + `~/.agents`. Codex is a SEPARATE software: its private config (provider/model/auth/Desktop/sandbox) is preserved, never touched.

Strict order (see `references/work-lab-global-config-reload.md` for full commands):
1. **Pull the source**: `git fetch origin main && git checkout main && git pull --ff-only origin main` in WORK-LAB; confirm HEAD == expected baseline SHA.
2. **Codex side**: `sync_codex_global_assets.py verify --codex-home "C:/Users/ALEX/.codex" --agent-home "C:/Users/ALEX/.agents"` (read-only). If drift → `plan`, review write set, `apply` with `--approved`.
3. **Hermes side**: verify managed fields in `HERMES_HOME/config.yaml` (`display.language=zh`, `display.busy_input_mode=queue`, `display.skin=purple-gemstone`); run `sync_hermes_workflow_assets.py --home <HERMES_HOME>` dry-run to detect managed-skill hash drift; review the write set (should contain ONLY `replace_managed_asset` skill steps + backup-before-publish rollback), then `--apply --approved`; re-run dry-run to confirm **0 drift**.
4. **Data-boundary guard check** (mandatory): E-drive ban in AGENTS.md; `bin/hermes-project-data.py` + `bin/hermes-project-terminal-guard.py` exist and hash-match the repo; `config.yaml` `pre_tool_call` hook (matcher: terminal) points at the guard.
5. **Report PASS/PARTIAL/FAIL** with the exact drift items and actions taken; never claim "已载入" when any step failed.

## Pitfalls

- **Doc-first vs env-drift**: report, don't auto-fix. Renaming/rebuilding a venv or moving toolchains without instruction is a destructive surprise.
- **Do not commit the global-config repo's uncommitted diff** unless the user explicitly asks (parallel-session WIP risk).
- **NEVER `git add -A` in a config/toolchain repo** (OS External Configuration, WORK-LAB): toolchain binaries (vs-build-tools 3.4G, scoop trees) are often NOT covered by .gitignore — a blanket add staged 14,812 files in one commit. Always `git add <specific files>`; if a bad commit was created, `git reset --mixed HEAD~1` immediately, then re-commit only the intended files, and extend .gitignore with every toolchain subdir.
- **git-bash `$HOME` breaks Python scripts**: passing `$HOME/.codex` (i.e. `/c/Users/ALEX/.codex`) to a Python CLI makes it resolve `C:\c\Users\...` → config not found → false `config_invalid`/FAIL. Always pass Windows-native paths (`C:/Users/ALEX/...`).
- **verify FAIL is often a path bug, not real drift**: when `verify` reports `config_invalid` + `state_missing` but direct `tomllib` parse of config.toml and the state JSON both succeed, suspect path translation before believing the drift.
- **Codex Desktop 重写 config.toml 用 CRLF → 受管块 hash 漂移死锁**（validated 2026-08-14）：`sync_codex_global_assets.py` 的 `_block_hash` 对 `\r\n` 与 `\n` 产生不同 hash。Codex Desktop 重登录/运行时重写 config.toml 会 (1) 把行尾改成 CRLF、(2) 剥掉受管块 `# ` 注释前缀——两者都使 `managed config block changed after apply` 死锁（state 记录 LF 块 hash，文件变 CRLF 或丢 `#`）。症状：plan/rollback 都 BLOCK，但手动 `_validate_existing_ownership` 却通过（hash 恰好匹配时）。诊断：`raw.count(b'\r\n')` + 用脚本自身 `_managed_block`/`_block_hash` 提取对比；修复：`cfg.write_bytes(raw.replace(b'\r\n', b'\n'))` 转 LF（或恢复 `# ` 前缀），立即 plan→apply（Codex 可能在几秒内再次重写，需快速执行）。Codex 进程运行中 config.toml 会周期性重写——修复要趁窗口。
- **Codex overlay 死锁恢复路径**：state phase=applied 但受管块被外部破坏时，rollback 需 phase∈{applying,rolling_back}（recovering=True）才放行——applied 状态死锁。恢复 = 手动重建受管块到与 state hash 完全一致（用脚本 `_expected_config_block`/`_expected_guidance_block` 渲染，`_managed_block` 提取校验），再 plan→apply。先备份 config.toml/AGENTS.md。
- **verify 与 plan 的检查面不同**：verify 报 `config_drift`/`config_managed_block_missing_or_duplicate` 而 plan 报 `managed config block changed after apply`——两者走不同路径（verify 用 `_load_state` + 字段比对，plan 用 `_validate_existing_ownership` + block hash 精确比对）。修 block hash 才是 plan 的硬门槛。
- **项目定位（positioning）检查**：DESIGN-LAB 的 identity gate（`verify_identity_gate.py`）扫描 legacy 名称（OPEN-DESIGN-Assistance）——reload 后必须重跑确认 0 违规；README/PRODUCT_DEFINITION 中的旧名引用需确认属于"允许出现"上下文（历史归档/迁移说明/检测脚本自身/测试 fixture）。
- **审计报告会过期——先对照当前树核实再行动（validated 2026-08-14）**：用户贴来的审计报告（如"本次云端更新审计"）常基于**旧提交**（例：报告审计 efee84c/#77，而当前 main 已到 c2f1b2f/#80，中间 PR 修复了报告的大部分 P0）。**不要复述或直接执行报告的每一项**——先逐条对照当前代码核实：CI workflow 是否已条件化 open-design gate（grep `if: steps.changes`）、schema `required` 是否已含 licenseStatus/version、verifier 是否已增强（grep 校验逻辑）、.license 版权声明抽样（区分第三方真实权利人 vs 自产 DTALEX66）、capability-index 是否已排除 quarantine（JSON walk）、boundTree 是否落后于 HEAD。核实后把报告项重分类为"已修复/仍成立"，只对仍成立的动手（本例 4 项 P0 中 3 项已被后续 PR 修复，报告结论"尚未审计闭环"部分过时）。报告"只读审计未改动"——这是待核实的声明，不是已执行的事实。
- **任务上下文给的简化路径 ≠ 仓库真实路径（validated 2026-08-15）**: 任务/子代理上下文里写 `config/adapter-registry.json`、`schemas/workflow/*.json` 这类路径时，它们通常不在仓库根——WORK-LAB 治理资产的 canonical 路径全部在 `10-workflow/workflow-assistance/` 下。先读 `00-governance/config-authority-index.json` 解析 canonical_source 再行动；做 WL3-xxx 能力矩阵/身份模型等治理研究前，先对照该索引并复测 manifest↔registry 已知漂移（见 `references/worklab-governance-taskpack-research.md`）。
- **Binding contract wins over historical docs**: NAMING_CONTRACT_V2 supersedes V1 and PRODUCT_STAGE; treat V1/STAGE as legacy context only.
- **环境能力负面断言会过期——reload 后实测复核（validated 2026-08-15）**: 项目 reference 曾写 "Local Rust full builds impossible (no MSVC SDK Lib)"，实际 cargo/rustc 位于 `OS External Configuration/toolchains/rust/rustup/toolchains/1.88.0-x86_64-pc-windows-msvc/bin`（wrapper PATH 不含），MSVC 环境 `toolchains/vs-build-tools/VC/Auxiliary/Build/vcvars64.bat`——`cargo check --all-targets` + `cargo test --lib` 16/16 全过。载入 Layer 1 时若 reference/文档含 "cannot/impossible/缺失" 类断言，先按 `host_inventory.py`（OS External Configuration/scripts/，R1 新增）或真实命令复核再行动——负面断言会硬化成自我拒绝。详见 windows-development-environment "Cargo/Rust builds on this host"。
- **User preference: 减重去冗余** — config docs should be lean; when reloading, flag redundant/stale sections as candidates for the next 减重 pass instead of silently keeping them.
- Project-specific paths, doc names, and exact check commands belong in `references/<project>.md`, not in this umbrella.

## Verification

- Report a compact three-section summary: global (drift found or not), project (sync SHA + worktree), positioning (binding doc + superseded set).
- State clearly what is 待办 (e.g. venv rename pending, doc not committed) so the user can fold it into the update pack.
- For WORK-LAB reloads: report per-step PASS/FAIL (Codex verify, Hermes fields+skills, guard files, hook) with SHAs/hashes as evidence.

## References

- `references/archeaxis-knowledge-os.md` — ArcheAxis-Knowledge-OS / OS External Configuration specifics (paths, docs, commands, known drift state).
- `references/archeaxis-taskpack-final-architecture.md` — Final Architecture TaskPack 2026-08-14 durable key values (six spaces, main UI layout, four profiles, release filenames, handshake contract, §18 pause conditions, §19 acceptance status) — the TaskPack original is a chat attachment, NOT on disk; consult this instead of re-searching session history.
- `references/design-lab.md` — DESIGN-LAB three-layer reload specifics: no AGENTS.md, PRODUCT_DEFINITION/BOUNDARY_CONTRACT identity, identity gate, cloud description check, verification baseline, and the explicit boundary that DESIGN-LAB reload does NOT touch the WORK-LAB Codex/Hermes overlay (validated 2026-08-14).
- `references/codex-desktop-config-overwrite-upstream.md` — Codex Desktop 重写 config.toml 的上游已知 issue 族（#36465/#37768/#36844 等）：先查上游再报，勿新建重复 issue（validated 2026-08-14）。
- `references/work-lab-global-config-reload.md` — full WORK-LAB Global Config Reload procedure: exact commands, managed field values, guard-hash checks, expected states, the git-bash path pitfall, AND §6 Codex-side failure diagnosis (expected skill drift vs real managed-block-loss anomaly, state file location, rollback discipline — validated 2026-08-14).
- `references/worklab-governance-taskpack-research.md` — WORK-LAB 治理任务包（WL3-xxx）只读研究：config-authority-index 规范源地图（canonical 路径全在 `10-workflow/workflow-assistance/` 下）、六客户端能力矩阵数据源（manifest/registry/ownership/real_adapters）、已确认漂移清单（registry 缺 openhuman/open-design、source_ref 索引 -1 偏移、Open Design 迁出、schema $id 冲突、CC Switch 契约矛盾、WL3-620 备注过时）、关键语义（deep≠有写能力）、身份模型构件（platform_identity 9 态、task-ledger、project-profiles、machine_id）、入口唯一性/五维基线（WL3-710 侧：检测面<分类面、Codex 多副本 wrapper 收敛、Hermes vbs 在 live Home、dual-entry-install 矩阵）与只读输出约定（`.hermes/task-runtime/`、guard 拦截时用 read_file/search_files、wrapper 调用法）。
