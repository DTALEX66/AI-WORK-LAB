---
name: uiux-layout-director
zh_name: "UI/UX 与网站布局导演"
description: "Generate polished app, menu, dashboard, and website layouts with strong hierarchy and usable responsive structure."
triggers:
  - "UI/UX"
  - "网站布局"
  - "菜单布局"
  - "dashboard layout"
  - "navigation design"
---

# UI/UX Layout Director

Use this skill inside Open Design for app screens, website pages, navigation systems, menus, landing pages, dashboards, and information architecture.

## Taste baseline

Prefer design quality comparable to Linear, Vercel, Stripe, Raycast, Framer, Notion, and Figma depending on the brief. Do not imitate logos or copyrighted assets; borrow layout discipline, spacing quality, typography hierarchy, and component clarity.

## Layout checklist

1. Start with user intent and primary action.
2. Define page/screen regions: hero/main canvas, navigation, secondary rail, content modules, action area, footer/status.
3. Establish one dominant visual hierarchy; do not make every card equal.
4. Keep navigation shallow, named, and scannable.
5. Menus should be short, grouped, and stateful: active, hover, disabled, danger.
6. Use responsive breakpoints: mobile first, tablet split, desktop enhanced.
7. Avoid generic filler cards, dashboard clutter, and paragraph-heavy UI.

## Output contract

```text
1. User goal and information architecture
2. Layout wireframe in words
3. Navigation/menu model
4. Component inventory
5. Responsive behavior
6. Visual style tokens
7. Accessibility and usability checks
8. Open Design generation prompt
```

## Menu/site special rules

- Menus must show priority: primary, secondary, destructive, utility.
- Website sections should have rhythm: hero → proof/value → feature depth → CTA.
- Complex tools should use command palette / compact rail / contextual inspector rather than giant top menus.

## Local template references

Use the closest local template before generating:

```text
design-lab/templates/layouts/landing-page.md
design-lab/templates/layouts/dashboard.md
design-lab/templates/layouts/mobile-menu.md
design-lab/templates/layouts/settings-panel.md
design-lab/templates/layouts/pricing-page.md
design-lab/templates/layouts/product-page.md
design-lab/templates/spatial/culture-wall.md
design-lab/templates/spatial/exhibition-hall.md
design-lab/templates/visual/2d-design.md
design-lab/templates/visual/3d-design.md
design-lab/templates/typography/cjk-ui-typography.md
design-lab/templates/design-systems/style-reference-index.md
```
