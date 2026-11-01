# CLOUD_BASELINE + EXACT_SHA_VERIFICATION（TP-20260819 DL-P0-003/001/004）

- **Exact SHA**：`70a857f93945a4f3afd1e1584311c309c21250d2`（本地 == 云端 main，SSH 回读一致）
- **验证链**：VERIFY_DESIGN_LAB=OK total=33；Python 248/248
- **P0-001 身份中立化**：核验通过——活动身份统一 design-lab；README/.gitignore 为可选宿主/历史注释引用（合规）；FIGMA_PLATFORM_RULES 已加中立性勘误（Open Design 非默认绑定）；verify_identity_gate 持续防漂移
- **P0-004 MiniGame 边界**：minigame-runtime 保留为游戏视觉 fixture（DL-AST-003/1382e2c 已移除广告/IA语义，300/300 测试），未恢复独立产品；边界由 anti-drift 测试保障
- **P0-003 证据状态**（当前 Exact SHA）：Adapter Registry 23 项（E0-E3 混合）/ Evidence Cards 12（待人工校准）/ Open Design E2（G2 真实作品）/ PS Smoke 已验（可编辑 PSD）/ ComfyUI-H3 E3（纯测试产物）/ MiniGame fixture 300 / QUARANTINE 162 / 包体积 199.8MiB（预算 256）
- **人工门（REMAINING_HUMAN_GATES）**：A1 Jury、A2 复审+Attestation、A3 162 条来源补全、B3 分支保护
