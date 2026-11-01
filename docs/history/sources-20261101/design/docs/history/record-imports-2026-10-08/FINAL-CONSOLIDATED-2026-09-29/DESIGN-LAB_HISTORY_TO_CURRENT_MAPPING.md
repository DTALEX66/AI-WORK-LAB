# 历史到当前映射

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。

原始 crosswalk 保留 **1450 条 occurrence**，按原字段完整附带；527 个 original_id 不等于独立当前任务。必须使用 occurrence_key、source_sha256、source_record_ids、locator 和 context_sha256 一起消歧。该CSV原有 current_targets/candidate_targets 是9/4历史映射，不会因附在本包就升级为当前指令。


| 历史能力/包 | 当前入口 | 观察 | 处置 | 当前任务挂接建议 |
| --- | --- | --- | --- | --- |
| Global Absorption | source registry / quarantine | 162原始记录保留；6active目标旧路径失效 | INTEGRATED结构 / BLOCKED资格 | DL-R5-023 |
| Visual Quality V2.1 | research/visual-quality + capabilities | 87byte-identical；33待语义diff | INTEGRATED；E1非E4 | DL-R5-014 |
| 专业设计Method/Domain | capability packs | 长期能力未删除；当前索引仅5不是全域运行 | CURRENT/DEFERRED | DL-R5-013/023 |
| 轻量前端工作台 | apps/workbench | 真实项目/Brief/资产/方向绑定已接入 | CURRENT E2子集 | DL-R5-010 |
| 品牌/设计系统 | DTCG + design-layer | 格式和绑定已有，版本编辑闭环未完成 | CURRENT / 未完成 | DL-R5-005/010 |
| Adobe生产 | host adapters | 结构与受控测试；当前实机证据未闭合 | HOST_ADAPTER | DL-R5-011/012 |
| Comfy/H3 | providers / qualification | 模型free历史工作流不同于H3模型推理 | SIDECAR/MODEL_PROVIDER | DL-R5-008/018 |
| Editable handoff | native_delivery / native_bundles | create/content已有，list class未接route；rights仍未review | CURRENT / 未完成 | DL-R5-005/010/014 |
| Open Design绑定 | optional host adapter | 从核心依赖移出 | HOST_ADAPTER | DL-R5-021 |
| 三项目联动 | boundary + KnowledgeCandidate | 经rights与human gate后才外发 | CURRENT边界 / 可选集成 | DL-R5-021/023 |
| MiniGame | fixture / game visual | 节点CI不是商业游戏生产证明 | CURRENT fixture | DL-R5-027 |
| 旧taskpacks | authority-index / crosswalk | 保留源ID碰撞，不直接dispatch | 历史 | DL-R5-001/023 |

## 不可直接映射的来源

未恢复原始完整对话中的需求只能标“待原件”，不可从当前计划反向生成历史需求。跨项目任务、旧路径cleanup、旧release编号都必须先确认scope。当前28项machine任务快照随附，每项后续只在原账本更新，不创建新的实时status表。
