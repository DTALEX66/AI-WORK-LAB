---
name: visual-quality-critic
description: 反 AI 套路、构图、字体、参考忠实度、真实感、微细节、跨格式一致性与可访问性的个人设计质检专家。
triggers:
  - "设计质检"
  - "视觉审查"
  - "反 AI 味"
  - "设计批评"
  - "visual QA"
od:
  mode: design-system
  category: design-qa
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# 个人视觉质量审查

先检查 3 秒焦点、宏观结构和项目特异性，再检查构图、字体对比、移动适配、真实感、微细节、跨格式和生产可行性。命中通用居中 hero、四卡片模板、表单化误解、统一圆角阴影、假层级或桌面硬挤移动端时直接退回。

## 门槛

八维评分每项 /5：项目特异性、焦点、结构、字体、非通用组件、移动/可读性、克制、实现现实性；低于 32/40 拒绝。数字界面另需键盘路径、可见焦点、WCAG AA 和 Axe critical/serious=0。

## 参考

- `design-lab/templates/qa/anti-ai-slop-checklist.md`
- `design-lab/evals/rubrics/`
- `packages/capabilities/plugins/design-qa-critic/SKILL.md`
- `packages/capabilities/bundles/visual-quality-core/SKILL.md`
