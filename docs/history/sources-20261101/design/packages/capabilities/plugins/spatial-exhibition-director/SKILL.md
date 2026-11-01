---
name: spatial-exhibition-director
zh_name: "文化墙与展厅空间导演"
description: "Generate culture wall, exhibition hall, showroom, brand center, and spatial 2D/3D design briefs for Open Design."
triggers:
  - "文化墙"
  - "展厅"
  - "展馆"
  - "showroom"
  - "3D space"
---

# Spatial Exhibition Director

Use this skill inside Open Design for culture walls, exhibition halls, showroom concepts, brand centers, public-space displays, lobby walls, and physical installation visuals.

## Inputs to collect

- `space`: culture wall, corridor, exhibition hall, showroom, lobby, booth, or installation.
- `scale`: wall size, floor area, or approximate ratio.
- `audience`: visitors, employees, clients, students, government/public audience.
- `content`: values, history, product, honors, timeline, data, people, future vision.
- `output`: 2D elevation, 3D render prompt, zone plan, material board, production brief.

## Design rules

1. Start with visitor path, viewing distance, and physical scale.
2. Separate far-read, mid-read, and close-read information.
3. Use material/lighting constraints: acrylic, metal, LED, print panel, projection, model, glass.
4. Culture wall is not a poster collage; exhibition is not every wall filled with text.
5. Every zone needs a thesis, visual anchor, and production note.

## Local template references

```text
design-lab/templates/spatial/culture-wall.md
design-lab/templates/spatial/exhibition-hall.md
design-lab/templates/visual/2d-design.md
design-lab/templates/visual/3d-design.md
design-lab/templates/visual/art-direction.md
design-lab/templates/typography/cjk-ui-typography.md
```

## Output contract

```text
1. Spatial narrative
2. Visitor/viewing path
3. Zone/elevation plan
4. 2D design prompt
5. 3D render prompt
6. Material and lighting palette
7. Production risk notes
8. Design QA gates
```
