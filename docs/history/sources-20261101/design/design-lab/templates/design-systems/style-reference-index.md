# Design system style reference index

Use this as a local shortlist of open-source/official style references to guide Open Design generations. Do not clone large upstream repos by default; cite the target reference in prompts and selectively extract rules later.

## Product and SaaS UI

| Reference | Use for | Local prompt hint |
|---|---|---|
| Stripe | premium SaaS landing, pricing, docs | luminous surfaces, precise spacing, business polish |
| Linear | issue trackers, dashboards, devtools | dark/light app chrome, compact hierarchy, gradient restraint |
| Vercel | developer landing, platform docs | black/white clarity, product screenshots, sharp CTAs |
| Notion | knowledge/workspace apps | calm blocks, sidebars, document hierarchy |
| Raycast | command palettes, productivity apps | compact command-first UI, keyboard affordances |
| Material 3 | standard mobile/web apps | accessible components, state layers, theming |

## Graphic and social

| Reference | Use for | Local prompt hint |
|---|---|---|
| Xiaohongshu | Chinese social covers | big readable title, mobile-safe margins, visual hook |
| editorial / magazine | posters, decks, reports | grid, type contrast, intentional whitespace |
| brutalism / neobrutalism | bold campaigns | hard edges, visible structure, high contrast |

## HUD / industrial

| Reference | Use for | Local prompt hint |
|---|---|---|
| Nothing design language | industrial mobile/HUD | monochrome, dot-matrix, mechanical controls |
| Open Design official `hud` system | game/monitor UI | panels, telemetry, stateful overlays |
| Anomaly Monitor Dark | current project | CCTV-first, hardware console, danger states |

## Selection rule

Pick at most two references per task:

```text
base system: controls layout and typography
accent system: adds mood or visual edge
```

Never mash five brands together.
