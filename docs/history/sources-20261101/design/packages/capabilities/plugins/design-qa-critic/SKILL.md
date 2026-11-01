---
name: design-qa-critic
zh_name: "设计质量审查器"
description: "Critique Open Design outputs for visual taste, usability, hierarchy, accessibility, and implementation realism."
triggers:
  - "设计审查"
  - "UI 评审"
  - "视觉验收"
  - "design QA"
  - "make it better"
---

# Design QA Critic

Use this skill inside Open Design after a visual artifact is generated. It is a critic, not a generator. It should be direct, strict, and actionable.

## Scoring dimensions

Score 1-5 for each:

1. Visual hierarchy
2. Typography and spacing
3. Layout clarity
4. UI/UX usability
5. Brand/style consistency
6. Responsiveness/mobile fit
7. Accessibility/readability
8. Implementation realism
9. Menu/navigation clarity
10. Originality and polish

## Required output

```text
Overall score: N/50
Keep:
- ...
Fix now:
- ...
Cut:
- ...
Next Open Design prompt:
"..."
Implementation risk:
- ...
```

## Hard rejections

Reject outputs that look like:

- survey forms when the task is game/product UI
- generic SaaS dashboards with no visual concept
- decorative gradients without hierarchy
- long copy pasted into tiny cards
- menus with no grouping or active state
- mobile layouts that bury the primary action
- fake HUDs where decoration blocks actual controls

Be concise but ruthless. Prefer fewer, stronger changes over broad vague feedback.

## Local template references

Use these local templates as review gates:

```text
design-lab/templates/qa/anti-ai-slop-checklist.md
design-lab/templates/layouts/landing-page.md
design-lab/templates/layouts/dashboard.md
design-lab/templates/layouts/mobile-menu.md
design-lab/templates/layouts/settings-panel.md
design-lab/templates/layouts/pricing-page.md
design-lab/templates/layouts/product-page.md
design-lab/templates/graphic/poster-cover.md
design-lab/templates/graphic/social-card.md
design-lab/templates/brand/brand-identity-system.md
design-lab/templates/spatial/culture-wall.md
design-lab/templates/spatial/exhibition-hall.md
design-lab/templates/visual/art-direction.md
design-lab/templates/visual/2d-design.md
design-lab/templates/visual/3d-design.md
design-lab/templates/motion/motion-system.md
```
