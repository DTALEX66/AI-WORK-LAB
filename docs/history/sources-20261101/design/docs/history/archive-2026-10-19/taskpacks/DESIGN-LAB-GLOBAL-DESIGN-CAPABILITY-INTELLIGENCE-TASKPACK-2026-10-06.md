# DESIGN-LAB 全球设计能力资产采集 · 知识化 · 评级 · 中立部署 TaskPack（已受理请求）

- **状态**：`REQUESTED` —— **不是当前 Authority**。
- **当前权威任务包仍为**：`docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md`
  （`DL-TP-20260918-FINAL-AUTHORITY-CONVERGENCE-R2`，被 `AUTHORITY.md` 与 authority-index 引用且按 SHA-256 钉死）。
  本文件在被 owner 显式采纳并写入 authority-index 之前，**不得作为派工入口**。
- **来源**：owner 于 2026-10-06 提供的任务书全文（本文件为其归档 + 实仓核对结果）。
- **唯一可变账本不变**：`design-lab/config/task-ledger-r3.json`。本文件不新增第二账本。

## 1. 任务书要点（原文口径，未改写）

目标不是"插件收藏夹"，而是建立可持续运行的 **Design Capability Intelligence &
Deployment Layer**：

`发现 → 登记 → 去重 → 分类 → 权利审查 → 安全审查 → 知识提炼 → Benchmark → 中立能力化 →
Adapter/Projection → Host 部署 → 读回 → 评价 → 更新/失效`

硬约束（原文）：产品身份锁死 AI-native / Agent-platform-neutral / Host-native；禁止指定任何
默认 Agent、默认 Host、默认审美、默认 UI 体系；禁止第二套 runtime / 插件市场 / 知识真值 /
Task Ledger / Adapter Registry / Visual Quality；禁止把第三方整仓源码塞进 Git；禁止未审查就
把第三方 `SKILL.md` 送进 Agent 上下文。核心原则：`POPULARITY ≠ QUALITY`、`STAR ≠ DESIGN TASTE`、
`INSTALLED ≠ VERIFIED`、`FILE EXISTS ≠ INTEGRATED`、`E1 ≠ E3`。

交付要求：≥120 canonical candidates 的多轴分类、饱和说明（`searchSaturationReason`，
不得写"搜遍全网"）、Adoption 与 Design Quality 分离、`canonicalUpstream` 回溯（禁止 star
laundering）、Tier S/A/B/C/R/Q/X（与现有 disposition 兼容）、知识压缩为
MethodCard/Rubric/Benchmark/Adapter 等、以及最终 A–L 十二段报告。

## 2. 实仓核对（本会话实测，取代任务书里的路径快照）

任务书按记忆列出多条路径；以下是**当前仓内真实存在**的对象模型，实施必须挂在这些之上：

| 对象 | 实测位置 | 关键事实 |
|---|---|---|
| 候选登记 | `research/candidates/`（README + 本目录） | CONDITIONAL_POC 索引区；源码**不进 Git**，在 `.project-local/cache/vendor/<id>` |
| 已审源 | `design-lab/research/global-absorption/SOURCE_REGISTRY.json` | `design-lab/source-registry/v3`，6 条，全部 vendor-adapt/active |
| 隔离区 | `design-lab/research/global-absorption/QUARANTINE_REGISTRY.json` | 162 源 |
| 源锁 | `vendor/sources.lock.json` | 23 KB |
| 校验器 | `design-lab/scripts/verify_source_registry.py` | 强制 `reviewedBy`/`reviewedAt` 为**人工责任字段**（DL-KNW-001）；status ∈ {active, reference-only, review-required} |
| 候选知识单元 | `design-lab/schemas/candidate-knowledge.schema.json` | 8 字段：candidate_id/source_id/knowledge_type/content_hash/state/compiled_ref/… |
| 能力目录 | `packages/capabilities/**` | atoms / bundles / plugins / quality / reconstruction / scenarios / skills / standards / typography / production / governance |
| 域包 | `design-lab/domain-packs/` | 13 个目录：audio, brand, ecommerce, graphic, minigame, motion, packaging, product-ui, spatial, three-d, uiux + `DOMAIN_PACK_SPEC_V2.md` |
| 域包校验 | `design-lab/scripts/verify_domain_pack_v2.py`、`design-lab/schemas/domain-pack.schema.json` | 已存在，禁止另建平行产品分类 |

结论：任务书 §24 的警告是对的——旧引用（`design-lab/knowledge/**`）已不是活动真值。
**实施一律复用上表对象，不新建第二 SSOT。**

## 3. 本会话已交付的骨架（可验证，非报告孤岛）

1. `design-lab/schemas/candidate-taxonomy.schema.json`
   —— 多轴分类对象模型（sourceType / capabilityLayers L0–L9 / domains / artifactTypes /
   styleArchetypes / referenceLineages / aestheticAxes / adoption / designQuality / tier /
   disposition / rights / risk / benchmarkStatus / evidenceLevel / removalPath /
   reviewedBy / reviewedAt / humanApprovalRef）。
2. `research/candidates/CANDIDATE-TAXONOMY.json`
   —— 投影，**只**用 `research/candidates/README.md` 已记录的事实播种（7 条 CONDITIONAL_POC；
   URL/许可/裁决/缓存键），其余每一轴一律 `null`。未测轴不写数字。
3. `design-lab/scripts/verify_candidate_taxonomy.py` + CI 步骤
   —— 把任务书的规则变成机器门：schema 校验；domain 必须映射到**存在**的 domain-packs 目录；
   非 null 的评分必须带 `evidenceRef`；tier S/A 必须有 benchmark；`parentRepoStars` 必须与
   `skillSpecificSignal` 分开（反 star laundering）；无许可不得越过 DISCOVERED/QUARANTINE/
   REFERENCE_ONLY；ABSORBED/BENCHMARKED 需 E2+ 与 partial/complete 基准；`reviewedBy/reviewedAt`
   必须有 `humanApprovalRef`（代理不得自签复核）；占位域名直接拒绝。

**该门经过证伪测试**：注入 5 类违规（tier S 无 benchmark、无 evidenceRef 的评分、
152k parentRepoStars 冒充自身、平行 domain、代理自签 reviewedBy）→ 报 7 条 error 且退出 1；
恢复后 OK。首次注入还暴露了校验器自身缺陷（字符串评分导致 `AttributeError` 崩溃而非 fail
closed），已修。

## 4. 尚未执行的部分（不粉饰）

### 4.1 一次真实发现尝试，以及为什么它没有产出条目（2026-10-06）

本会话执行了两次公开检索（"Agent Skills repository design taste UI quality 2026"、
"anthropics skills github repository frontend-design webapp-testing license"），
结果**全部是镜像/聚合站**：同一个 `anthropics/skills` 被同一站点以 4 个语言路径重复托管
（`tool.lu/{es_ES,vi_VN,ru_RU,ja_JP}/skill/g19RQAS`），其余为 CSDN/segmentfault/头条等
二手转述，标题里出现的"8.2 万 Star"没有任何可回溯的 canonical 归属。

按任务书 §14/§35/§58 的口径，这类结果**只能算 Discovery Source，不得当作 upstream**，
因此**一条候选都没有登记**——把它们写成候选，正是任务书要防的 star laundering 与镜像冒充上游。
这次尝试本身是一个可用发现，已记为下一次发现任务的输入：

- 检索面被镜像农场污染；**必须**能直接解析到 `github.com/<owner>/<repo>` 才能登记，
  且 license 要来自 canonical 仓库自身的 LICENSE 文件，不是转述；
- 需要一个带 API 凭证的检索通道（GitHub API / npm registry / PyPI JSON）来拿
  `stars / license / updated_at / default_branch` 等**带 observedAt 的原始事实**；
  纯自然语言搜索返回的是二手叙事，不满足 §15 的 "指标必须有来源与观测时间"；
- 在拿到该通道前，`CANDIDATE-TAXONOMY.json` 保持只有 7 条仓内既有事实，
  `searchSaturationReason` **不予声明**（未饱和，也未开始）。

### 4.2 其余未执行项

- **≥120 canonical candidates 的全球发现未做**：见 §4.1。未做，也未用假行填充。
- **Adoption 指标全部为 null**：`observedAt`/来源缺失时不得填数（§15）。
- **本机候选源码未核验**：`.project-local/cache/vendor/<id>` 为 ignored 缓存，本会话未逐仓
  读取其 LICENSE/SKILL.md，故未做 §18 的 prompt-injection/供应链审计。
- 未做：任何 ABSORB 判定、任何 Host 部署、任何 Skill 全局安装（§40 明确本轮只到
  Deployment Ready）。

## 5. 执行约束（后续会话必须遵守）

- 任何修改前按 §0 顺序读 live：`AUTHORITY.md` → authority-index → `AGENTS.md` → 当前 TaskPack
  → 唯一 ledger → live main/PR/CI → `reports/current/**` → `research/candidates/**` →
  global-absorption → `vendor/sources.lock.json` → capabilities → domain-packs → evals → integrations。
- 独立分支作业（§54）：不 merge、不 release、不删分支、不 force push、不做全局软件部署。
- 第三方整仓源码只进 `.project-local/cache/vendor/`；Git 内只存 source record / provenance /
  派生知识 / 最小适配能力 / 测试 / 基准 / 许可与归属 / 证据。
- 品牌风格只做 `Reference → Style DNA → Abstract Rules → Style Vector/Rubric`，禁止 clone 品牌；
  品牌名只作 `referenceLineages`，不得成为全局默认 style id。
- 遇到不完整信息：保守登记（null）；许可不明：Quarantine；指标无公开数据：null；
  优秀但不适合直接运行：DERIVE；优秀外部工具：ADAPTER。

## 6. 验收（完成时必须给出）

A Executive Summary / B Top S·A / C Existing vs New / D Duplication Matrix / E Aesthetic Map /
F Capability Map / G Domain Map / H Knowledge Conversion / I Deployment Readiness / J Evidence
(E0–E5) / K Blockers（许可、权限、Host、OAuth、付费 API、缺人工复核）/ L Exact Git State
（before SHA、after SHA、branch、PR、tests、CI）。
