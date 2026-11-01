# DL-V2 — 后续方向调研结论（2026-08-16）

> 综合：真实仓库现状 + V2 架构任务包 + 历史规划（ROADMAP J0–J5 / 13 对象 / 9 适配器 / 边界与中立契约）。
> 纪律：延续 R4 fail-closed；未指定不猜测（RULE 9）。

## 一、三个输入校准后的真实图景

| 输入 | 结论 |
|---|---|
| 真实仓库 | **契约/治理/证据驱动**：35 个 schema、config 注册表、30+ 验证器、E0–E5 证据。core/ 仅 README（空）；intelligence/ 是 vendored 第三方技能；domain-packs/ 仅 2 域 |
| V2 任务包 | 方向正确（唯一内核、六契约、三层体系、渐进不重写），但**读取层级错**：把 design-lab/ 子目录当仓库根，假设 core/intelligence 有代码可迁、10 领域已建——均非事实 |
| 历史规划 | 已定骨架：不重写、契约优先、领域不绑定工具、Provider 中立、证据等级诚实（J0–J5；13 对象；9 适配器全 E0 合同） |

## 二、13 对象契约覆盖情况（schema 层）

已有：Brief/Direction/DesignSystem/DomainPack/Artifact/ToolRun/Preflight/Handoff/Evidence/DesignProjectState/ReferenceSet/ResearchFinding/MethodCard/JuryRecord/Critique。

**真实缺口（V2 六契约对齐）**：

| 缺口 | 严重度 | 说明 |
|---|---|---|
| DesignMemory / MemoryRecord | 高 | 静态 knowledge 升级为可计算记忆（semantic/procedural/episodic/visual/failure） |
| DesignCommand / ExecutionResult | 高 | 运行时命令/结果契约（tool-run 只记录，非命令） |
| QualityGate policy | 高 | jury 有评分，无 hard-gate/blocking 策略 schema |
| DeliveryManifest | 中 | handoff/bom 近似，缺独立交付清单 |
| Provider SPI（能力描述层） | 中 | 中立性靠 policy，无 capability 声明 schema |

## 三、后续总方针（明确结论）

1. **不重写、不大迁移目录**——core 到 kernel 迁移无码可迁（core 空）；保留 design-lab/ 契约优先布局。
2. **Kernel 落成轻量状态机 + 契约，而非第二 Agent runtime**（BOUNDARY_CONTRACT 禁止重运行时）。DesignState 已有 schema，补 command/result 契约即可。
3. **最高优先补 Design Memory**——唯一真实增量：把设计经验从聊天历史变成可检索、可溯源、经验证的 memory record。
4. **次优先 Quality Gate 运行时**——jury/rubric 升级为分层评分 + hard gates + FalsePassRate 校准。
5. **再打通 Reference E2E**——用已证明的 ComfyUI/H3 E3 + Mock adapter，跑通 brief 到 deliverable 全链（CI 可复现）。
6. **战略冻结三层体系**：WORK-LAB(控制面)/DESIGN-LAB(能力面)/ArcheAxis(证据面)，写入 ARCHITECTURE/BOUNDARY。
7. **明确不做**：10 领域一次铺开（先 1–2 域做规范样本）、模型网关、重运行时、Provider 硬编码。

## 四、重排后的可执行路线

- P0-A 契约补全：新增 design-memory / design-command / execution-result / quality-gate / delivery-manifest schema（版本化 + 正负 fixture + 验证器）。
- P0-B Design Memory：memory schema + 摄入/去重/evidence/validation 规则 + verifier（fail-closed）。
- P0-C Quality Gate：quality-profile + hard-gate policy + blocker fixtures（已知坏样本 100% 阻断）。
- P1-D Reference E2E：ecommerce.hero 或 commercial.poster 全链 workflow，Mock adapter + H3 真实能力，CI 可跑。
- P1-E Domain 规范化样本：1 个职业领域做 domain.yaml + capability 声明（延续 DOMAIN_PACK_SPEC_V2）。
- P2-F Provider SPI 最薄层 + Adobe PS E3（真实运行时取证）。

## 五、与历史规划的关系

- 延续 ROADMAP J4（适配器 E3 取证）到 J5（E4/E5 发布链），不另起炉灶。
- V2 = 在 J4/J5 之间插入契约收敛 + Memory + Quality Gate 的收窄动作，而非目录洗牌。
- 里程碑不变：提交专业 brief 生成显式状态，经 capability contract 工具执行产出可编辑 artifact，过可解释 Quality Gate 与 preflight，交付带 manifest/证据/provenance 的成品，经验回写 Memory，全程不依赖特定模型或特定 Adobe 应用。
