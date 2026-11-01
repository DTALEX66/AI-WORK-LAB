---
name: culture-wall-designer
description: |
  Design corporate culture walls and exhibition spaces with structured intent extraction,
  brand binding, lighting standards (GB 50034/CIE 157), material specifications, and
  accessibility compliance (WCAG 2.1 AA). Outputs production-ready visualizations.
  Trigger keywords: "culture wall", "exhibition design", "corporate lobby", "文化墙", "展厅设计".
triggers:
  - "culture wall"
  - "exhibition design"
  - "corporate lobby"
  - "文化墙"
  - "展厅设计"
od:
  mode: design-system
  category: spatial-design
  platform: desktop
  scenario: production
  design_system:
    requires: true
    generates: false
  inputs:
    - name: brief
      type: string
      required: true
      description: "Design brief or natural language description"
    - name: brand_spec
      type: string
      required: false
      description: "URL, PDF, or screenshot of brand guidelines"
    - name: dimensions
      type: string
      required: false
      description: "Wall dimensions (e.g., '12m x 3.6m')"
    - name: lighting
      type: string
      required: false
      description: "Ambient lighting conditions (lux, CRI)"
  outputs:
    primary: culture-wall-design.html
    secondary: material-board.png
  capabilities_required:
    - file_write
    - web_fetch
---

# Culture Wall Designer Skill

Design corporate culture walls that feel intentional, brand-accurate, and production-ready.
Follow this workflow exactly.

## Pre-flight (read BEFORE writing any code)

1. Read active DESIGN.md from the project root or `design-systems/<name>/DESIGN.md`
2. If a `brand-spec.md` exists in the project root, read it
3. Read this skill's references:
   - `references/checklist.md` (P0/P1/P2 quality gates)
   - `references/lighting.md` (GB 50034 + CIE 157 standards)
   - `references/materials.md` (material specifications)
   - `references/accessibility.md` (WCAG 2.1 AA for exhibitions)
4. If neither DESIGN.md nor brand-spec exists, ask the user for brand assets before proceeding

## Design Brief Resolution

If the user provides a vague brief ("make it professional", "modern Chinese style"),
resolve it into explicit dimensions using this mapping:

| Vague phrase | Resolved dimension | Default value |
|---|---|---|
| "professional" | Mood | Engineering-trustworthy, restrained |
| "modern" | Style | Minimal, no ornamentation |
| "Chinese traditional" | Heritage | Extract from brand palette, no cliché red/gold |
| "tech feel" | Direction | Linear/Verbal-style, mono accents |
| "warm" | Temperature | Neutral-warm oklch, NOT beige/cream |
| "luxury" | Material | Matte metals, no glossy gradients |
| "spacious" | Density | Section gap 96px, information density ≤ 40% |
| "information-rich" | Density | Section gap 64px, information density ≤ 60% |

## P0 Quality Gates (MUST all pass)

Before emitting any artifact, verify:

- [ ] **Brand accuracy:** All colors within ΔE ≤ 3 of brand spec (or DESIGN.md palette)
- [ ] **Information hierarchy:** Three levels defined (far/mid/near viewing distances)
- [ ] **Lighting uniformity:** ≥ 0.7 ratio (min/avg illuminance per GB 50034-2024)
- [ ] **Information density:** Wall surface text/graphics ≤ 40% of total area
- [ ] **Wheelchair accessibility:** Core content at 0.9–1.2m height (WCAG 2.1)
- [ ] **Color contrast:** All text meets 4.5:1 against background (WCAG AA)
- [ ] **No AI slop:** Passes anti-slop checklist (no purple gradients, no emoji icons, no left-border cards)
- [ ] **Typography:** Display ≠ Body family; no Inter/Roboto as display face

## P1 Quality Gates (should pass)

- [ ] Material callouts specify finish type (matte/brushed/polished) not just color
- [ ] Lighting design specifies CRI ≥ 95 for color-critical zones
- [ ] Wayfinding integrates with building architecture (not a floating sign)
- [ ] Content has clear owner/contact for future updates
- [ ] Installation method is specified (wall-mounted/stand-alone/suspended)

## P2 Quality Gates (nice to have)

- [ ] Night-mode lighting scenario provided
- [ ] Material samples linked to physical swatches
- [ ] Cost estimate range provided
- [ ] Maintenance schedule documented

## 5-Dimensional Self-Critique

Rate each dimension 1-5 before emitting:

1. **Philosophy:** Does this feel like a culture wall for THIS brand, or could it be any corporate lobby?
2. **Hierarchy:** Does the eye land on the company name first, then values, then details?
3. **Execution:** Are letters properly kerned? No AI-garbled text? No melting edges?
4. **Specificity:** Every word specific to THIS company? No "Feature One / Feature Two"?
5. **Restraint:** One accent used at most twice per zone? No competing flourishes?

**Minimum: 3/5 on all dimensions. Fix any < 3 before emitting.**

## Output Specification

The artifact must be a single self-contained HTML file with:

1. **Hero visualization** — The wall as a human would see it (perspective-correct, not flat)
2. **Detail callouts** — Material specifications, lighting zones, typography scale
3. **Day/night modes** — Toggle between ambient-lit and spotlight-lit scenarios
4. **Installation notes** — Mounting method, material thickness, lighting angles
5. **Accessibility statement** — Viewing distances, height compliance, contrast ratios

## Anti-Slop Rules (from Open Design craft/anti-ai-slop.md)

NEVER in the output:
- Purple/violet gradient backgrounds
- Emoji as feature icons (✨🚀🎯)
- Rounded cards with left colored border
- Hand-drawn SVG humans/faces
- Inter/Roboto as display face
- Invented metrics without source
- Filler copy ("Feature One", "Feature Two")
- Gradient on every background
- Warm beige/cream/peach/pink backgrounds (unless brand requires)

## Reference Standards

- **GB 50034-2024:** Lighting design standard (300/200/250 lux for corridors/exhibits/offices)
- **CIE 157:** Museum and gallery lighting (CRI ≥ 95, UV filtration)
- **WCAG 2.1 AA:** Accessibility (contrast, height, readable distances)
- **ISO 21542:** Accessibility of built environment (reach ranges, tactile elements)

---

*Part of DESIGN-LAB culture wall design system*
*Integrates with Open Design skill protocol*
