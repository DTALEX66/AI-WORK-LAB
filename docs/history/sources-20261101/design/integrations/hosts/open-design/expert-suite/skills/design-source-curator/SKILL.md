---
name: design-source-curator
description: |
  设计资料来源、许可和证据审查专家。用于大师、博物馆、奖项、开源设计系统、论文和素材的
  可信分级、许可核对、引用策略与隔离决策，防止未经验证的内容进入个人设计体系。
triggers:
  - "设计资料来源"
  - "许可审查"
  - "大师资料可信度"
  - "source curation"
  - "设计研究证据"
od:
  mode: design-system
  category: design-research
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# 设计来源与证据审查

## 当前来源库

- 134 个已注册来源：95 个 A 级、32 个 B 级、7 个 C 级。
- 119 个已核验许可；15 个未核验来源继续隔离或只作研究候选。
- 来源包括 AIGA、AGI、MoMA、Vignelli Center、Bauhaus-Archiv、HfG Ulm、JAGDA、DNP/GGG、TDC、Cooper Hewitt、W3C 与经许可开源项目。

## 决策规则

1. `reference`：只引用和独立总结，不复制文章、图片、视频、年鉴或作品集。
2. `derive`：允许独立实现方法，不复制原文或代码。
3. `adapter`：仅在接口、许可、安全和版本边界通过后接入。
4. `vendor-adapt`：保留许可与归属，并固定版本。
5. `quarantine` / `review-required`：不得进入运行时生成上下文。

## 输出合同

- 来源 ID、URL、等级、许可状态和复核日期；
- 可吸收内容、明确限制和集成模式；
- 事实/观察/推断分离；
- 对个人体系的接纳、隔离或拒绝结论；
- 需要保留的归属和版本信息。

## 仓库依据

- `design-lab/research/visual-quality/SOURCE_REGISTRY_VISUAL_V21.json`
- `design-lab/research/global-absorption/SOURCE_REGISTRY.json`
- `design-lab/schemas/source-registry.schema.json`
- `packages/capabilities/atoms/source-intake-gate/SKILL.md`
- `packages/capabilities/atoms/master-evidence-auditor/SKILL.md`
