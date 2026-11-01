# WLOSS-100 / WLOSS-300 / WLOSS-510 决策记录

日期：2026-08-14
性质：REFERENCE / DERIVE 处理决定（不进入核心执行链，除非后续显式评审）

## WLOSS-100 — Policy-as-Code（OPA / Conftest）

**决定：REFERENCE（候选，不默认集成）**

- 现有分层已经工作：JSON Schema（数据形状）→ `config-ownership.json` + `config_coordinator.py` + `action_plan`（跨状态 Python Gate）→ 审批门（Human Gate）。
- OPA/Rego 的价值是把跨文件/跨状态规则**声明式化**，但引入需下载 Rego 二进制（Windows 支持好但增加本机依赖）。
- **不替换现有 JSON Schema 和 Python Gate**（任务包也明确"OPA 不取代 JSON Schema"）。
- 触发条件：出现跨文件/跨状态规则无法用现有 Python Gate 表达（例如多仓库 writer 所有权矩阵），届时按 WLOSS-000 流程从 REFERENCE 升级。
- 对应 source-ledger 条目：`opa`、`conftest`（freshness=review-required，未进执行链）。

## WLOSS-300 — Evidence Attestation（in-toto / Cosign）

**决定：DERIVE（模型）+ REFERENCE（签名工具，Release 层才启用）**

- 采用 in-toto **provenance 模型**（链路：SBOM → Evidence Manifest → in-toto predicate → exact-SHA 校验）作为现有 evidence 体系的规范化描述。
- Cosign/Sigstore 签名**仅在真实 Release 时启用**（个人项目发布频率低；Cosign 依赖 Sigstore 生态/网络）。
- Evidence 字段白名单已有（hash/version/tool/test result/artifact identity/timestamp/source revision）；prompt/response/credential 永久禁止（`execution_evidence.py` + `canonical_store` 强制执行）。
- 对应 source-ledger：`in-toto`（DERIVE）、`cosign`（REFERENCE review-required）。

## WLOSS-510 — Skill Distillation & Evaluation（Superpowers 方法 / Promptfoo）

**决定：方法吸收（文档/skill）+ Promptfoo REFERENCE（可选本地 eval，不默认集成）**

- 吸收 Superpowers 纪律：先观察 Agent 失败 → 创建 Skill → 重跑同任务 → 对比 → 回归。作为 skill 写作规范写入 WORK-LAB skills 开发流程（见 `hermes-agent-skill-authoring`）。
- Promptfoo：本地 eval/red-team 有价值但依赖重（Node）；默认不集成，需要时作为可选本地 harness 启用，且**不开启远端生成/共享路径**（任务包安全说明）。
- 评测维度（task completion/tool correctness/policy violation/unnecessary action/token/latency/recovery/evidence correctness）在启用 eval 时作为指标集。
- 对应 source-ledger：`superpowers`（REFERENCE）、`promptfoo`（REFERENCE review-required）。

## 共同约束

- 以上全部为 REFERENCE/DERIVE，未进入任何执行链（WLOSS-000 验收：License + Revision Review 完成前不得进入执行链）。
- 任何升级必须：更新 source-ledger 对应条目 → 本文件追加评审记录 → 通过现有质量门禁。
