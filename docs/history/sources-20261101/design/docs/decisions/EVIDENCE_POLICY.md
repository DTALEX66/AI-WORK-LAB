# EVIDENCE_POLICY — 证据政策

- 版本：`1.0`｜状态：`ACTIVE`｜SSOT 角色：证据契约
- 权威：本文件 + `product-manifest.json` 的 `evidencePolicy` 一致

## 证据等级

| 等级 | 含义 |
|---|---|
| E0 | 声明/合同级：仅有契约、清单、无执行 |
| E1 | 只读验证：静态检查、schema 校验、hash 一致 |
| E2 | 本地执行：单元测试、确定性生成器、本地回路 |
| E3 | 真实运行时：宿主/工具实际执行、读回、回滚证据 |
| E4 | 发布级：exact-SHA CI、artifact、人工审批 |
| E5 | 生产验收：客户/生产环境验证与长期读回 |

## 证据结构（DL-EVD-002：三分模型）

1. **Capability Claim Index**（`config/capability-evidence-index.json` records）：能力声明 + 最低证据要求，不声称绑定当前 HEAD。
2. **Evidence Attestation**（`schemas/evidence-attestation.schema.json`）：主体-SHA 证明书，必须包含
   `subjectCommitSha + subjectTreeSha + producer + environment + command + exitCode + artifactDigests + createdAt + reviewer + evidenceLevel`。
3. **Release Evidence**：由 CI 运行时生成，存储为 GitHub Actions Artifact / Release Asset / GitHub Attestation；
   不作为必须预先存在于被证明提交中的文件。

自引用禁令：若 Evidence 被提交进 Git，提交 N+1 可以证明提交 N；不得声称证明 N+1 自身。

## 绑定新鲜度（DL-EVD-003）

- `CURRENT_EXACT`：绑定 == 当前 HEAD tree；仅此状态支持当前发布（且只能来自 CI 运行时 attestation）。
- `HISTORICAL_VALID`：绑定为祖先提交的 tree；`requiresRequalification=true`，不得支持当前发布。
- `STALE` / `UNRESOLVABLE`：失效；必须重新绑定。
- 禁止逻辑：绑定 SHA 是 HEAD 祖先 ≠ current/fresh。

## 证据晋级（DL-EVD-004）

E0 声明 → E1 静态结构 → E2 隔离运行 → E3 真实 Host/Tool 运行与 Artifact 回读 →
E4 精确 SHA、独立复审、人工验收和发布证据 → E5 外部真实商业验收。
每次晋级必须具有**同一能力**的累计证据链，不得跨能力借证据（见 `verify_capability_evidence_v4.py` PROMOTION 表）。

## 证据记录要求

每条 EvidenceRecord / Attestation 必须包含：
`E 等级 + subjectCommitSha + subjectTreeSha + 责任人 + 时间 + 执行命令/环境 + exitCode + 输入/产物 hash + 结果 + 人工审核人`

## 铁律

- 未达 E3 不得写"已集成"；
- 单张 AI 生成图不得作为通过证据；
- 静态文件/schema 通过/VLM 自评不得冒充运行可用；
- 历史证据绑定旧树 SHA 时不得复用于新树；
- 祖先绑定只能作为 HISTORICAL_VALID（requiresRequalification=true），不得冒充 current/fresh。
