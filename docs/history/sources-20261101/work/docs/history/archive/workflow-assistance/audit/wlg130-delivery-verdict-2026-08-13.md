# WLG-130 交付裁决 — WORK-LAB Global Config Governance DeDup

> TaskPack: WORK-LAB_Global_Config_Governance_DeDup_TaskPack_2026-08-13
> 日期：2026-08-13

## 1. Authority Matrix（权威矩阵）

| 问题 | 权威 | 实现 |
|---|---|---|
| 由 WORK-LAB 发起的全局任务：谁能执行/writer/批准 | WORK-LAB（不覆盖项目 CI/owner） | `run_taskpack_agent.py` + Task Ledger |
| 项目发生了什么、CI/PR/SHA 状态 | GitHub / 项目真实产物（WORK-LAB 只读投影） | Observer（`observation_only: true`） |
| 外部项目应跑哪些业务测试 | 外部项目 project profile | `project-profiles.json`（只读端点） |
| 事实是否成立、来源 | 外部项目 Evidence Authority | 不在 WORK-LAB 复制 |
| 用户/模型/认证如何配置 | 各客户端官方配置 + 用户 overlay | `config-ownership.json` |
| 是否发布项目制品 | 项目 owner + 项目 Release workflow | 不跨仓发布 |
| 字段级配置所有权 | `config-ownership.json`（`single_authority: true`） | WLG-000 |
| 全局 tier 词汇 | `gate_vocabulary.py`（TARGETED/STAGE/NIGHTLY/RC/RELEASE） | WLG-030 |
| 全局 hash 预算 | `hash_budget.py` | WLG-060 |
| 审计触发 | `audit_triggers.py` | WLG-070 |
| Apply 安全链 | `apply_safety.py` | WLG-100 |

## 2. Active / Superseded / Archive 清单

- Active：`docs/current/workflow-assistance/workflow/active-authority-index.md` 第 1 节列表。
- Superseded：嵌套 `governance.yml` → `docs/current/workflow-assistance/workflow/examples/governance.yml.example`（WLG-080）。
- Archive：90-archive-manifests → `docs/history/archive-manifests/`、docs/handoffs → `docs/history/archive/workflow-assistance/handoffs/`、docs/audit → `docs/history/archive/workflow-assistance/audit/`、50-taskpacks → `taskpacks/history/` 历史记录。

## 3. ArcheAxis 外部端点 pointer（仅地址 + 协议元数据）

登记于 `config/project-profiles.json`（WLG-020，WL-PR-A）：
- `project_id: archeaxis-knowledge-os`
- repo：`DTALEX66/ArcheAxis-Knowledge-OS`
- workflow：`CI`；aggregate job：`a0-gates`；release：`Release`
- 仅保存地址/协议元数据，不收纳项目内容、业务规则、测试命令或制品。

## 4. Runner 行为测试

- WLG-040：low-risk publish 仅验证 remote sync（`require_ci=False`），exact-SHA CI 保留给 RC/RELEASE。
- 测试：`test_taskpack_agent_runner.py` 28/28、`test_gate_vocabulary.py` 5/5、`test_hash_budget.py` 6/6、
  `test_audit_triggers.py` 3/3、`test_apply_safety.py` 4/4、`test_active_authority_index.py` 5/5、
  `test_cross_project_contracts.py` 10/10、observer tests 22/22。

## 5. CI tier 对照

| Tier | WORK-LAB 验证 |
|---|---|
| TARGETED / STAGE | changed-file tests/compile，30–90 秒 |
| checkpoint | 模块定向 gate，不 push |
| NIGHTLY | portable install、客户端 conformance、供应链 |
| RC / RELEASE | WORK-LAB 自身 exact-SHA、包哈希、安装/回滚 |

## 6. Observer read-only 证明

- `module-profile.json`：`externalMutationDefault: false`。
- `verify_observer_skeleton.py`：禁止 subprocess/shell/POST/PUT/PATCH/DELETE + runtime 写标记 + unknown 语义检查。
- `resolve_profile`：work-lab observer `observation_only` 强制校验。

## 7. 未执行的用户配置 apply

- 未修改用户真实 provider/model/auth/Desktop 状态。
- `open-design.global_configuration`：`apply_supported: false`，不写本机。
- `memory.growth_policy`：模块自管字段，本机 Hermes 配置无落点（符合设计）。

## 8. GO / NO-GO

| 批次 | PR | 状态 |
|---|---|---|
| WL-PR-A（WLG-000~030,050） | #81 | CI 验证中 |
| WL-PR-B（WLG-040,060~080） | #82 | CI 全绿，可合并 |
| WL-PR-C（WLG-090~130） | 待开 | 本地测试全绿 |

**裁决：GO**（待 WL-PR-A CI 转绿、WL-PR-B 合并后 rebase WL-PR-C）。
