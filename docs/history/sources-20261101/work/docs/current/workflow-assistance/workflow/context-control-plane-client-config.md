# 上下文控制面 — 客户端配置建议（Context Control Plane per-client）

> 2026-08-16 · 依据：Context Control Plane 设计 + 各客户端官方机制调研
> 原则：只调官方配置项，不接管客户端私有状态；CC Switch/GitHub/OpenHuman/Open Design 无上下文机制，保持 OBSERVE。

## 1. DSH（DeepSeek Harness）

官方机制：compaction-basic（摘要+KV复用）+ tool-result-pruner（工具结果剪枝）+ command-compact。

建议参数（写入 web profile 的 cordis.patch.yml，项目内 git-ignored）：

```yaml
- id: compaction-basic
  name: '@deepseek-ai/dsh-compaction-basic'
  config:
    thresholdRatio: 0.7      # 默认 0.8，更早触发压缩
    retainRatio: 0.10        # 默认 0.16，保留更少原文（更多进摘要）
    maxTokens: 12288         # 摘要生成上限（保留更多事实）
- id: tool-result-pruner
  name: '@deepseek-ai/dsh-compaction-tool-result-pruner'
  config:
    thresholdChars: 8192     # 工具结果 >8K 字符剪枝
    headChars: 4096
    tailChars: 1024
```

要点：DSH 的 <compacted-summary> 标记 + 原始事件保留已满足防漂移；调参只影响压缩触发时机，不破坏前缀。

## 2. Hermes

官方机制：context_compressor.py + protect_first_n（头部消息钉住）+ focus topic 优先。

建议：
- 配置 protect_first_n >= 3：钉住系统指令 + 项目定位 + 边界规则；
- focus topic 保持为当前任务主题，压缩器优先保留相关事实；
- 依赖官方配置面（hermes config），不直接改压缩器代码。

## 3. Codex

官方机制：config.toml 的 auto-compact + 官方 prompt caching（静态内容前置）。

建议：
- 开启 auto-compact（长会话自动压缩）；
- 静态内容（AGENTS.md 规则、工具 schema、项目定位）前置，最大化 prompt cache 命中；
- 避免激进剪枝：压缩不得改变稳定前缀（TokenPilot 实测：激进剪枝破坏缓存反而更贵）。

## 4. CC Switch / GitHub / OpenHuman / Open Design

无官方上下文机制（路由切换 / 指令效率 / 只读观测）。保持 OBSERVE，不配置。

## 5. 统一协调（WORK-LAB Context Control Plane）

- L1 stable prefix：各客户端共享同一组装顺序（系统边界→工具schema→全局规则→项目规则→证据→tree/SHA→临时态）；
- L2 缓存真值：DeepSeek hit/miss 仅 OBSERVED 时算率；Codex null 不伪 0；
- L3 防漂移：压缩必保留 9 项（目标/非目标/paths/边界/SHA/失败/验收/回滚），缺一拒绝；
- 验证：python services/orchestration/run_quality_gate.py context-control-plane
