# WORK-LAB 跨客户端上下文控制面（Context Control Plane）设计方案

> 状态：DESIGN_PROPOSAL · 2026-08-16 · 归属：workflow-assistance（增强模块）
> 依据：模型控制面任务包 §12（上下文/缓存/低消耗高命中）+ 各客户端官方机制调研
> 原则：客户端中立、模型中立；压缩不丢理解、防漂移；不以"更短"冒充"更高效"

## 1. 问题与目标

### 1.1 问题
- 长对话/长任务中，历史消息、工具输出、重复指令占大量 token，费用高、上下文窗口易满；
- 各客户端（Hermes/Codex/DSH）各有官方压缩机制，但互不统一、参数未按本项目优化；
- 压缩不当会丢失关键事实（目标/约束/SHA/验收）导致模型漂移，或破坏缓存前缀反而更贵。

### 1.2 目标
- 建立 WORK-LAB 统一的**客户端中立上下文组装 + 压缩 + 缓存优化**能力；
- 所有受管客户端（Hermes/Codex/CC Switch/GitHub/OpenHuman/Open Design/DSH）可消费；
- 压缩保留理解必需事实、防漂移；提升 DeepSeek/Codex 服务端缓存命中率、降 token 成本；
- 不接管客户端私有状态、不改 UI、不写 prompt/response 正文到持久层。

## 2. 各客户端官方机制调研（2026-08）

| 客户端 | 官方机制 | 关键能力 | 本项目可消费点 |
|---|---|---|---|
| DSH | compaction-basic + tool-result-pruner + command-compact | `<compacted-summary>` 标记、原始事件保留、KV 前缀复用（`x-deepseek-harness-compact:1`） | 调 thresholdRatio/retainRatio；确认 pruner 生效 |
| Hermes | context_compressor.py + protect_first_n | 头部 N 条消息钉住、focus topic 优先、per-model 阈值 | 配置 protect_first_n；对齐头部钉住策略 |
| Codex | config.toml auto-compact + 官方 prompt caching | 静态内容前置缓存；激进剪枝反贵（TokenPilot 2848 次实测） | auto-compact 配置；静态前缀对齐 |
| CC Switch | 无上下文机制（纯路由切换） | — | OBSERVE 不碰 |
| GitHub/Copilot | AGENTS.md 指令 token 效率 | 静态指令前置 | 指令优化参考 |
| OpenHuman / Open Design | 无公开上下文机制 | — | OBSERVE/外部不碰 |

**调研共识（防漂移铁律）**：
1. 静态内容前置最大化缓存命中（static content first）；
2. 激进剪枝破坏前缀反而更贵——压缩不得改变稳定前缀；
3. 头部关键指令永远保留（protect_first_n）；
4. 原始事件保留 + 摘要呈现——理解靠摘要、核对靠日志。

## 3. 架构设计

```
Context Control Plane（workflow-assistance 增强）
│
├─ L1 Stable Prefix 组装器（context_bundle.py 升级）
│   ├─ 组装顺序（§12.1）：
│   │   1 系统边界 → 2 工具 schema（确定性排序）→ 3 全局规则引用
│   │   → 4 项目规则版本化摘要 → 5 证据块 → 6 tree/SHA/diff → 7 本轮临时态
│   ├─ volatile 剥离（已有）：时间戳/随机ID/临时路径/无序JSON/进度噪声
│   └─ 完整 manifest（§12.2）：schema_version/global_rules_revision/project_id/
│       project_rules_revision/base_tree/evidence_selectors/ordered_stable_block_ids/
│       volatile_block_ids/token_estimate_source/data_classification/redaction_result/
│       expires_at
│
├─ L2 缓存命中反馈（接 model_usage_mapper.py）
│   ├─ DeepSeek：读 prompt_cache_hit/miss_tokens → 命中率仅 OBSERVED 且分母>0 时算
│   ├─ Codex：null + source=UNAVAILABLE（不伪 0）
│   └─ 本地 KV：运行时无指标则 null；命中率不成为质量 gate
│
├─ L3 防漂移契约（context_drift_guard.py 新增）
│   └─ 压缩必须保留 8 项（§12.6）：
│       用户目标/非目标/allowed-forbidden paths/数据边界/当前 base SHA-tree/
│       已知失败/验收命令/回滚方法 —— 缺任一 fail-closed
│
└─ L4 客户端适配（per-client 配置建议）
    ├─ DSH：cordis.patch.yml 调 thresholdRatio=0.7/retainRatio=0.10/maxTokens 提高
    ├─ Hermes：protect_first_n 配置（钉住项目规则/边界指令）
    ├─ Codex：config.toml auto-compact 对齐静态前缀
    └─ CC Switch/GitHub/OpenHuman/Open Design：OBSERVE，不修改
```

## 4. 数据流

```
任务入口 → Context Control Plane
  ├─ 组装稳定前缀（L1）→ 返回 canonical bundle manifest
  ├─ 读取历史缓存命中（L2）→ 反馈前缀稳定性
  ├─ 校验压缩保留项（L3）→ 缺项 fail-closed
  └─ 输出客户端适配建议（L4）
        ↓
  Hermes/Codex/DSH 按各自官方机制消费（配置层面）
        ↓
  观测：usage → model_usage_mapper → Telemetry（无正文）
```

## 5. 防漂移设计决策

- **原始数据永删但可压缩**：压缩进摘要，原始事件留 Evidence/Session Log（可回放核对）；
- **压缩保留项验证器**：缺目标/边界/SHA/验收任一 → 拒绝压缩（fail-closed）；
- **头部钉住**：全局规则/项目定位/边界指令在每次压缩中保留（对齐 Hermes protect_first_n）；
- **前缀稳定性**：任何压缩不得改变稳定前缀的字节序（保证 DeepSeek/Codex 缓存命中）；
- **缓存命中 ≠ 质量**：命中率只观测，不成为 gate（§12.3）；
- **正文不落持久层**：prompt/response 只在任务受控内存或忽略临时边界（§12.2）。

## 6. 落地步骤（3 文件 + 测试 + gate）

| 步骤 | 内容 | 类型 |
|---|---|---|
| 1 | context_bundle.py 升级：完整 manifest + 组装顺序校验 + 头部钉住 | 修改 |
| 2 | context_control_plane.py：编排层（任务→前缀+缓存预期+压缩决策+客户端建议） | 新增 |
| 3 | context_drift_guard.py：§12.6 必保留项验证器 | 新增 |
| 4 | 测试：前缀确定性/缓存仅 OBSERVED/保留必选项/头部钉住/项目隔离 | 新增 |
| 5 | run_quality_gate.py 注册 context-control-plane gate + CI | 修改 |
| 6 | 客户端配置建议文档（DSH/Hermes/Codex 参数） | 文档 |

## 7. 验证与验收

- 同一输入两次 → byte-identical 稳定前缀（已有 MR-10 测试延伸）；
- 压缩后缓存命中率可观测（hit/miss OBSERVED 时），不伪 0；
- §12.6 必保留 8 项缺一 → 压缩拒绝；
- A 项目上下文不进 B 项目（memory_isolation 已有）；
- QUALITY_GATE_PASS 新增 gate 全绿；
- 客户端配置仅 OBSERVE 层面，不改 UI/不写正文。

## 8. 边界与不做什么

- 不做：接管客户端私有状态、改 UI、写 prompt/response 正文、伪造缓存指标、把命中率当质量 gate；
- CC Switch/GitHub/OpenHuman/Open Design：无上下文机制，保持 OBSERVE；
- 该能力是 workflow-assistance 增强，不建第二个控制平面、不写第二业务数据库。
