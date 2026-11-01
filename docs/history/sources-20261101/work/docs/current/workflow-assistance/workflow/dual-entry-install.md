# 双入口与安装路径对账（Dual-entry install matrix）

## 背景

WORK-LAB 增强模块存在多套安装/同步入口，历史上被批准清单列为「双入口/双安装卸载或配置迁移」。本文档对账各入口的职责、适用范围与迁移关系，消除重复入口歧义。

## 入口矩阵

| 入口 | 目标运行时 | 角色 | 何时使用 |
|---|---|---|---|
| `scripts/setup-workflow.sh` / `scripts/setup-workflow.ps1` | Hermes | plan-first 安装入口 | 新机器部署 Hermes 侧增强；默认只生成 ActionPlan，显式 `--apply`/`-Apply` 才写 live Home |
| `integrations/executors/hermes/sync_hermes_workflow_assets.py` | Hermes | **Hermes 侧 canonical 同步器** | 仓库 → live Hermes Home 的单向同步（managed skill 根、launcher/guard、.env.template）；setup 脚本最终调用它 |
| `integrations/executors/codex/sync_codex_global_assets.py` | Codex | **Codex 侧 canonical 同步器** | plan/apply/verify/rollback Codex overlay（AGENTS.md 块、3 个 config 缺省字段、rules、5 个 skill 根） |
| `integrations/executors/codex/install_codex_global_guidance.py` | Codex | **legacy 最小引导（bootstrap）** | 仅在公开目标**完全不存在**时原子发布缺失的 `AGENTS.md`；有同名文件/override/竞态则 fail-closed |

## 职责边界（无冲突）

- `install_codex_global_guidance.py` 只做「目标不存在时的最小 AGENTS.md 引导」，**不管理** config 字段、rules、skills —— 这些由 canonical `sync_codex_global_assets.py` 负责；
- 两台安装器互不覆盖：legacy bootstrap 遇到任何已存在内容即 fail-closed，不会与 canonical 的 managed block 打架；
- Hermes 侧与 Codex 侧入口目标运行时不同，互不干扰。

## 迁移关系

- 新安装统一走 canonical：Hermes 侧 `scripts/setup-workflow.sh|ps1 → sync_hermes_workflow_assets`；Codex 侧直接 `sync_codex_global_assets.py plan/apply/verify`；
- `install_codex_global_guidance.py` 保留为历史/边缘场景（公开目标从未初始化的全新 Codex Home）的最小引导，不视为并行安装面；
- 无「双安装卸载」问题：两套入口写同一组受管表面（managed block/字段/rules/skills），verify 回读统一以 `sync_codex_global_assets.py verify` 为准。

## 验证

```text
sync_codex_global_assets.py plan/apply/verify   当前受管集合为 5 skills；逐机结果以 plan/verify readback 为准
scripts/setup-workflow.sh                      bash -n 门禁 PASS
scripts/setup-workflow.ps1                     PowerShell AST 门禁 PASS
install_codex_global_guidance.py                边缘引导，目标存在时 fail-closed（由治理测试覆盖）
```

> 2026-10-05 技能收敛：本机全局个性化规则使用 personal-guidance.md 的单一文件；只更新技能时运行同步器 --skills-only，保留 config/AGENTS/rules。普通全量 overlay 不应重建已由用户替换的旧 managed block。项目专属说明见 docs/current/workflow-assistance/skill-references/。历史运行记录不代表本次部署。
