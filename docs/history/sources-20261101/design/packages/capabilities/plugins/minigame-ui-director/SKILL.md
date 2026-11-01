---
name: minigame-ui-director
zh_name: "小游戏设计导演"
description: "Design complete minigames from core loop and rules through levels, UX/UI, economy, platform adaptation, validation, and production handoff."
triggers:
  - "小游戏设计"
  - "游戏策划"
  - "核心循环"
  - "关卡设计"
  - "小游戏 UI"
  - "游戏 HUD"
  - "小游戏商业化"
  - "minigame design"
---

# Minigame Design Director

Use this skill inside Open Design to turn a game brief or rough idea into a coherent, testable and production-ready minigame. The installed ID remains `minigame-ui-director` as a **保留兼容 ID**, but the capability is no longer limited to interface styling.

## Inputs to ask for

- `platform`: `h5`, `wechat`, `douyin`, `android-webview`, desktop browser, or generic mobile.
- `genre`: auto from brief, or 益智、动作、模拟、放置、合成、塔防、节奏、派对、跑酷、经营、卡牌、找物、解谜、混合玩法。
- `session`: target session length, control scheme and orientation.
- `visualDirection`: derive from audience, fantasy, genre and platform; never force a stored theme.
- `monetization`: derive from product intent; `none` is valid and rewarded ads are not mandatory.

## Capability pipeline

1. Define audience, fantasy, platform, session and success metric.
2. Design the core loop, verbs, rules, state machine, win/loss and risk/reward.
3. Design first-session teaching, difficulty curve, level/content templates and replay progression.
4. Select the correct game surface: board, world, arena, lane, stage, cards, merge grid, simulation scene, HUD or hybrid.
5. Design UX/UI, feedback, controls, accessibility and responsive/safe-area behavior.
6. Design economy and commercialisation only when justified by the brief.
7. Produce a prototype contract, content schema, telemetry plan, performance budget, test matrix and implementation handoff.

## Visual rules

- The playable surface and player decisions must dominate; avoid form/SaaS composition.
- Match visual language to the genre: tactile board, playful toy, expressive character world, clean puzzle field, kinetic action arena, cosy simulation, etc.
- HUD and console styling are optional tools, not the definition of “game feel”.
- Load `anomaly-monitor-hud` or `anomaly-monitor-dark` only when the brief explicitly calls for surveillance/control-console aesthetics.

## Repository context

Use these as optional implementation evidence, not as universal product memory:

```text
design-lab/domain-packs/minigame-design/
fixtures/domains/game-visual/
design-lab/design-systems/anomaly-monitor-dark/DESIGN.md  # optional CCTV case
```

## Output contract

Return a concise design package:

```text
1. Product and player hypothesis
2. Core loop, verbs, rules and state model
3. First session, difficulty and content/level system
4. UX flow, playable surface, controls and feedback
5. Visual direction and asset/content production plan
6. Economy, monetisation and telemetry where applicable
7. Platform/performance/accessibility constraints
8. Prototype, test matrix and implementation handoff
```

If producing HTML, make it a self-contained playable interaction prototype rather than a static screen mockup whenever feasible.

## Local template references

Use these local references before generating:

```text
design-lab/templates/layouts/mobile-menu.md
design-lab/templates/layouts/settings-panel.md
design-lab/templates/graphic/social-card.md
design-lab/templates/motion/motion-system.md
design-lab/templates/qa/anti-ai-slop-checklist.md
```
