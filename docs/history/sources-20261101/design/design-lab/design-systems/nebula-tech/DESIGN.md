# Nebula Tech (星云科技) Design System

> Based on Open Design 9-section DESIGN.md schema
> Referenced design systems: linear-app, vercel, stripe, cursor
> Created: 2026-08-29

---

## 1. Visual Theme & Atmosphere

- **Mood:** Engineering-trustworthy, humanistic, quietly confident
- **Feel:** Deep space precision meets warm human craft. Not a hotel lobby. Not a generic AI dashboard. A technology company that values clarity over decoration.
- **References:** Linear (information density), Stripe (restrained trust), Bosch industrial signage (wayfinding clarity), museum exhibition lighting (CIE 157)

**Anti-references (never emulate):** Generic purple-gradient AI templates, SaaS landing pages with floating cards and gradient backgrounds, hotel lobby signage systems.

---

## 2. Color Palette & Roles

All colors in OKLch for perceptual uniformity when algorithmic adjustment is needed.

| Role | OKLch | Hex | Usage |
|---|---|---|---|
| Background | `oklch(0.98 0.01 250)` | `#F5F7FA` | Page/canvas background |
| Surface | `oklch(1.0 0.0 0)` | `#FFFFFF` | Cards, panels, elevated surfaces |
| Text primary | `oklch(0.2 0.02 250)` | `#1A2233` | Headlines, body text |
| Text secondary | `oklch(0.45 0.02 250)` | `#5C6B7F` | Captions, metadata, labels |
| Border | `oklch(0.88 0.01 250)` | `#DDE1E7` | Dividers, card borders |
| Accent | `oklch(0.55 0.18 250)` | `#2D62D4` | CTAs, key highlights, links |
| Accent hover | `oklch(0.45 0.18 250)` | `#1E4FB0` | Hover state for interactive accent |
| Gold accent | `oklch(0.75 0.12 85)` | `#C8A44E` | Award highlights, premium markers (use ≤ 2× per viewport) |
| Success | `oklch(0.6 0.15 145)` | `#2E8B4F` | Positive status |
| Warning | `oklch(0.7 0.15 75)` | `#D49A2D` | Caution status |
| Error | `oklch(0.55 0.18 25)` | `#D4382D` | Error status |

**Color rules:**
- Background is NEVER pure white (`#FFFFFF`) — the `oklch(0.98)` background reduces eye strain in exhibition lighting
- Gold accent appears at most 2× per viewport zone (day/night/transition)
- Accent blue appears at most 3× per viewport
- All interactive elements have `:focus-visible` outline in accent blue

---

## 3. Typography Rules

### 3.1 Font stacks

| Role | Primary | Fallback | Weight | Size |
|---|---|---|---|---|
| Display | Source Han Sans SC Heavy | `system-ui, sans-serif` | 800 | `clamp(2rem, 4vw, 3.5rem)` |
| Display EN | Montserrat Bold | `system-ui, sans-serif` | 700 | `clamp(2rem, 4vw, 3.5rem)` |
| Body | Source Han Sans SC Regular | `system-ui, sans-serif` | 400 | `1rem / 1.6` |
| Body EN | Montserrat Regular | `system-ui, sans-serif` | 400 | `1rem / 1.6` |
| Mono | JetBrains Mono | `ui-monospace, monospace` | 400 | `0.875rem / 1.5` |
| Caption | Source Han Sans SC Medium | `system-ui, sans-serif` | 500 | `0.75rem / 1.4` |

### 3.2 Typography rules

- Body text minimum: 14px (WCAG), preferred 16px
- Display/body must be different families — never use the same weight of Montserrat for both
- Line height for display: 1.1; for body: 1.6; for captions: 1.4
- Max line length: 75ch (Chinese: 35 characters per line)
- Heading hierarchy: H1 (3.5rem) → H2 (2rem) → H3 (1.5rem) → H4 (1.25rem) → Body (1rem) → Caption (0.75rem)

---

## 4. Component Stylings

| Component | Specification |
|---|---|
| Buttons | `rounded-md` (4px), accent bg, white text, `padding: 8px 16px`, `transition: background 150ms` |
| Buttons:hover | `oklch(0.45 0.18 250)` background |
| Buttons:focus-visible | `2px solid accent, 2px offset outline` |
| Cards | Surface bg (`#FFFFFF`), `border: 1px solid oklch(0.88)`, `border-radius: 8px`, `padding: 24px` |
| Inputs | `border: 1px solid oklch(0.88)`, `border-radius: 4px`, `padding: 8px 12px`, focus: `2px solid accent` |
| Dividers | `1px solid oklch(0.88)`, no drop shadows |
| Tags/Pills | `rounded-full`, `padding: 4px 12px`, `background: oklch(0.95 0.02 250)`, `color: oklch(0.3 0.02 250)` |

---

## 5. Layout Principles

| Property | Value |
|---|---|
| Max width | 1280px (desktop), 100% (mobile) |
| Grid | 12-column, 24px gutters, `grid-template-columns: repeat(12, 1fr)` |
| Section spacing | 96px (major), 64px (standard), 32px (minor) |
| Content padding | 24px (desktop), 16px (mobile) |
| Container padding | 48px (desktop), 24px (tablet), 16px (mobile) |

---

## 6. Depth & Elevation

| Level | Usage | Shadow |
|---|---|---|
| Ground | Base canvas | None |
| Surface | Cards, panels | None (border only) |
| Elevated | Dropdowns, popovers | `0 2px 8px oklch(0.2 0.02 250 / 0.08)` |
| Overlay | Modals, dialogs | `0 8px 24px oklch(0.2 0.02 250 / 0.12)` |
| Focus | Focus ring | `0 0 0 2px accent` |

**Rule:** No drop shadows on cards. Borders only. Shadows reserved for floating/overlay elements.

---

## 7. Do's and Don'ts

### DO

- [ ] Use ONLY colors from this palette (no invented hex values)
- [ ] Maintain consistent 8px grid spacing (multiples of 8: 8, 16, 24, 32, 48, 64, 96)
- [ ] Meet WCAG 2.1 AA contrast (4.5:1 for text, 3:1 for large text and UI components)
- [ ] Keep display/body as distinct font families
- [ ] Use accent blue for interactive elements only
- [ ] Keep gold accent to ≤ 2× per viewport zone

### DON'T

- [ ] NO purple/violet gradients (`linear-gradient` with `#6366F1` or similar)
- [ ] NO emoji as icons (✨🚀🎯🌟💡)
- [ ] NO rounded cards with left colored border accent
- [ ] NO hand-drawn SVG illustrations of people/faces/landscapes
- [ ] NO Inter, Roboto, or Arial as a **display** face (body is fine)
- [ ] NO invented metrics without a source citation
- [ ] NO filler copy ("Feature One", "Feature Two", lorem ipsum)
- [ ] NO icon next to every heading
- [ ] NO gradient on every background
- [ ] NO warm beige/cream/peach/pink/orange-brown backgrounds
- [ ] NO designer settings, viewport selectors, or "demo controls" exposed as UI

---

## 8. Responsive Behavior

| Breakpoint | Width | Behavior |
|---|---|---|
| Mobile | `< 640px` | Single column, stack vertically, 16px padding |
| Tablet | `640–1024px` | 2-column feature grids, 24px padding |
| Desktop | `1024–1280px` | Full 12-column layout, 48px padding |
| Wide | `> 1280px` | Max-width 1280px, centered |

**Image rules:** Fluid (`max-width: 100%`), maintain aspect ratio, `object-fit: cover` for hero images.

---

## 9. Agent Prompt Guide

When generating artifacts for Nebula Tech, the AI agent MUST:

1. **Bind tokens first:** Copy the `:root` CSS variables from Section 2 and 3 into the artifact before writing any HTML.
2. **No color invention:** Every color value must come from Section 2. No hex values outside the palette.
3. **No gradient backgrounds:** Backgrounds use solid colors from the palette only.
4. **Font pairing:** Display (Montserrat Bold / Source Han Sans Heavy) + Body (Montserrat Regular / Source Han Sans Regular). Never use the same family for both.
5. **Accent discipline:** Accent blue appears at most 3× per viewport. Gold at most 2×.
6. **Real content only:** No filler copy, no fake statistics. If data is unknown, use a grey placeholder with a label (e.g., `[Metric: source needed]`).
7. **WCAG compliance:** All text meets 4.5:1 contrast ratio against its background.
8. **Focus states:** All interactive elements have visible `:focus-visible` outlines.
9. **Self-critique:** Before emitting, run the 5-dim critique (Philosophy, Hierarchy, Execution, Specificity, Restraint). Fix any dimension scoring < 3/5.

---

*DESIGN.md v1.0 — Nebula Tech Culture Wall Project*
*Based on Open Design 9-section schema + anti-AI-slop rules*
*Referenced: linear-app, vercel, stripe, cursor design systems*
