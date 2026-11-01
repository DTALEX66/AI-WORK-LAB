<!-- freshness: sourceCommit=0da75536f9e0c329fd4881af33b5fa2c091fdcc4 sourceTree=36947bdf1b0e110bd301224d37927fedea6e82e5 generatedAt=2026-08-20T23:59:00Z evidenceLevel=E0 expiry=2026-08-27T16:19:43Z status=CURRENT -->
# WORK-LAB 开源组件评估报告（WL-OSS-001~008 · TP-20260819 §10）

> 状态：评估 + 适配判定（PoC 待人工批准后执行）。所有项目先 PoC 再进入正式依赖；GPL/AGPL 特殊许可证需 Rights Review。

| 任务 | 组件 | 定位 | 许可证 | 判定 | 说明 |
|---|---|---|---|---|---|
| WL-OSS-001 | chezmoi | 配置模板/Diff/Apply | MIT | ADAPTER（评估）| 吸收跨机器模板能力；不退化为 dotfiles 管理器；不成为产品身份；未预览不 apply |
| WL-OSS-002 | SOPS | Secret 加密 | MPL-2.0 | ADAPTER（待 PoC）| YAML/JSON/ENV；内存解密；Git 只存加密/SecRef；密钥轮换验证 |
| WL-OSS-003 | OPA | 策略引擎 | Apache-2.0 | ADAPTER（待 PoC）| 三类规则（Observer 禁写/高风险审批/安全字段禁覆盖）；与旧引擎双跑对比，不一致阻断 |
| WL-OSS-004 | OpenTelemetry | 可观测性 | Apache-2.0 | ADAPTER（评估）| 统一 Trace/Metric/Log Envelope；Observer 只读；敏感字段过滤；correlationId 贯穿 |
| WL-OSS-005 | Langfuse | LLM 观测 | MIT | OPTIONAL | 只发 metadata/token/latency/cost；默认不发正文；本地不可用降级标准事件 |
| WL-OSS-006 | Dagger | CI/CD | Apache-2.0 | OPTIONAL | Exact-SHA 构建测试；桌面设计任务不强行容器化 |
| WL-OSS-007 | Renovate | 依赖更新 | AGPL-3.0 | REPORT-ONLY | 默认只建报告/待批准；禁止 automerge；AGPL 保持外部服务；不自动升 Compatibility Baseline |
| WL-OSS-008 | 拒绝整体替代 | — | — | POLICY | Backstage/Temporal/Kestra/Dagger/n8n 只做子系统，不整体替换 WORK-LAB |

## 结论

- 全部 8 项为评估/PoC 状态，**未实际安装任何组件**（遵守 §16：安装系统级软件需人工批准）
- 优先 PoC：SOPS（Secret 安全）+ OPA（策略门禁）
- 禁止项：Renovate automerge、整体替代、未 PoC 进正式依赖