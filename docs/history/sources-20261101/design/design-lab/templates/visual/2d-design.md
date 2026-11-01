# 2D design template

Use for flat graphics, icon systems, infographics, diagrams, illustrated UI, posters, signage elevations, and 2D assets.

## 2D modes

```text
flat-vector: simple shapes, strong silhouette, scalable
editorial-layout: typography and grid first
infographic: data hierarchy and labels
icon-system: consistent stroke/fill/grid
wall-elevation: physical panel layout in 2D
sprite-sheet: game/animation assets
```

## Rules

- Define grid before style.
- Use limited shape vocabulary.
- Keep stroke weights consistent.
- Use semantic color; avoid decorating every object.
- If output is for production, include bleed/safe area/export size.
- For wall/signage, include real dimensions and viewing distance.

## Output contract

```text
1. 2D mode
2. Canvas size / physical size
3. Grid and alignment system
4. Shape/stroke/icon rules
5. Color/type rules
6. Export specs
7. Open Design prompt
```

## Open Design prompt add-on

```text
Create a 2D design system with explicit grid, shape language, stroke rules, color semantics, typography, and export/production specs. Avoid decorative inconsistency and unscalable detail.
```
