---
name: brand-visual-director
zh_name: "品牌与视觉设计导演"
description: "Generate brand identity, visual design, key visual, 2D graphic, and art-direction systems for Open Design."
triggers:
  - "品牌设计"
  - "视觉设计"
  - "VI"
  - "logo direction"
  - "2D design"
---

# Brand Visual Director

Use this skill inside Open Design for brand identity, VI direction, visual systems, key visuals, 2D graphic systems, social/print campaigns, and design-system starting points.

## Inputs to collect

- `brand`: name, category, existing assets.
- `audience`: users, buyers, visitors, internal team, public audience.
- `tone`: premium, official, tech, playful, cultural, industrial, editorial.
- `applications`: website, app, social, culture wall, exhibition, poster, deck, signage.
- `constraints`: colors, logo, language, format, production, legal/competitor avoid list.

## Design rules

1. Brand design must produce application rules, not only mood words.
2. Visual design needs one thesis, one focal system, and explicit typography hierarchy.
3. 2D work needs grid, shape language, stroke/type rules, and export specs.
4. Chinese and English typography must both be handled when relevant.
5. Avoid direct imitation of reference brands; borrow discipline, not identity.

## Local template references

```text
design-lab/templates/brand/brand-identity-system.md
design-lab/templates/visual/art-direction.md
design-lab/templates/visual/2d-design.md
design-lab/templates/graphic/poster-cover.md
design-lab/templates/graphic/social-card.md
design-lab/templates/design-systems/style-reference-index.md
design-lab/templates/typography/cjk-ui-typography.md
```

## Output contract

```text
1. Brand/visual thesis
2. Three visual territories
3. Token and typography system
4. Logo/mark direction notes
5. 2D graphic rules
6. Application examples
7. Open Design generation prompt
8. Do/don't QA gates
```
