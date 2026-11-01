# Figma Files Guide

> Every project needs a set of Figma files created at specific stages of the workflow.
> This guide tells you exactly which files to create, what goes in each, and in what order.

---

## Overview — Files to Create

| # | File Name | When | Purpose |
|---|-----------|------|---------|
| 1 | **User Flows** (FigJam) | Step 6 | Visual journey maps — Claude creates via Figma MCP |
| 2 | **Brand Guidelines** | Step 10 | Visual identity document → export as PDF |
| 3 | **Design System** | Step 11 | Component library + local variables |
| 4 | **UI Screens** | Step 17 | html.to.design import → dev-ready Figma file |
| 5 | **Cover Thumbnail** | Gumroad/Portfolio | Product card image for selling/sharing your work |
| 6 | **Links Directory** | Gumroad/Portfolio | Navigation page linking all Figma files |

---

## File 1 — User Flows (FigJam)

**When:** Phase 2, Step 6  
**Tool:** FigJam (via Figma MCP with Claude)  
**Format:** FigJam file (`.jam`)

### What to include

```
FigJam Page: Cover
  → Title, project name, designer name, date

FigJam Page: Onboarding Flow
  → App launch → registration → onboarding → home
  → Color code: green = happy path, orange = alt path, red = error

FigJam Page: [Core Feature] Flow
  → Entry → main journey → success state
  → Label each step with screen name

FigJam Page: Edge Cases
  → Network failure, invalid input, empty states, permissions denied
```

### Prompt for Claude (with Figma MCP)
```
I have a FigJam file open at [URL].
Create user flow diagrams for [AppName] using the personas and brief in this project.
Use sticky notes for annotations, shapes for screens, arrows for navigation paths.
Group each flow in its own section. Colour code: green happy path, orange alt, red error.
```

---

## File 2 — Brand Guidelines

**When:** Phase 3, Step 10  
**Tool:** Figma Design file  
**Format:** Figma file → exported as PDF

### Page Structure

```
Page 1: 📋 Cover
  → Logo centred on brand colour, project name, tagline, version, date

Page 2: 🔤 Logo
  → Wordmark (light bg)
  → Wordmark (dark bg)
  → Icon only
  → Minimum size rule
  → Clearspace diagram (= half the x-height on all sides)
  → Don'ts: stretch, recolor, add effects, use on busy backgrounds

Page 3: 🎨 Colour Palette
  → Primary, secondary, neutral, semantic colours
  → Each swatch: colour name, HEX, RGB, HSL
  → Usage rule for each (when to use / not use)
  → Accessibility note (contrast ratio against white/black)

Page 4: ✍️ Typography
  → Font name + specimen (ABCDEFG / abcdefg / 0123456789)
  → Type scale: Display / H1 / H2 / H3 / Body / Caption / Label
  → Each size: px, weight, line-height, letter-spacing, use case

Page 5: 🔷 Iconography
  → Icon set name (e.g. Phosphor Icons)
  → Size grid: 16, 20, 24, 32px
  → Usage: when to use regular vs bold vs fill weight
  → 12 sample icons in context

Page 6: 📸 Photography / Imagery
  → 3–4 approved image examples
  → 3–4 "don't use" examples
  → Mood description (warm/cool, candid/staged, etc.)
  → Overlay and treatment rules

Page 7: 💬 Voice & Tone
  → 3 brand personality adjectives
  → Example: button labels, error messages, success messages, onboarding copy
  → Words to use, words to avoid
  → Reading level target

Page 8: 📐 Spacing & Grid
  → Base unit (4px or 8px)
  → Screen margins (horizontal padding)
  → Component spacing rules
  → Responsive grid (if web)

Page 9: 📱 UI Preview
  → 2–3 key screens showing the brand in context
  → "This is how it all comes together"
```

**Export:** File → Export → PDF (all pages)  
**Save to:** `docs/brand-guidelines.pdf`  
**Upload to:** Claude Project

---

## File 3 — Design System

**When:** Phase 3, Step 11  
**Tool:** Figma Design file (separate from Brand Guidelines)  
**Format:** Figma component library file

### Structure

```
Page 1: 🗂 Cover + Index
  → Design system name, version, last updated
  → Table of contents with jump links

Page 2: 🎨 Foundations
  → Local Colour Variables (all T.* tokens)
  → Typography Styles (all text sizes/weights)
  → Shadow Styles (xs, sm, md, lg)
  → Border Radius guide

Page 3: ⚛️ Atoms
  → Button: Primary, Secondary, Outline, Destructive, Disabled
  → Input: Default, Focus, Error, Disabled
  → Badge / Chip: all variants
  → Avatar: Small, Medium, Large (image + initials)
  → Icon frame (20, 24, 32px)
  → Toggle / Switch
  → Checkbox
  → Radio

Page 4: 🧬 Molecules
  → TopBar: with back / without back / with right action
  → BottomNav: all 5 tab states
  → Card: Default, Pressable, With image, List item
  → Search Bar
  → Empty State
  → Toast / Snackbar
  → Bottom Sheet (handle + content)
  → Loading / Skeleton

Page 5: 🧱 Organisms
  → Modal / Dialog: confirmation, alert, form
  → Form group (label + input + error)
  → Screen template (TopBar + scroll area + BottomNav)
  → List view (multiple list items)
  → Grid view (card grid)

Page 6: 📱 Screen Templates
  → Blank screen with TopBar + BottomNav
  → Blank screen with TopBar only
  → Full-bleed screen (no nav)
  → Modal overlay screen
  → Bottom sheet overlay

Page 7: ✅ Do / Don't
  → Common mistakes to avoid with this system
  → Side-by-side comparisons
```

**Tip:** Publish this as a Figma Library so it's available across all project files.

---

## File 4 — UI Screens (Dev Handoff)

**When:** Phase 6, Steps 17–18  
**Tool:** Figma Design file (created via html.to.design import)  
**Format:** Figma file with prototype links + Dev Mode annotations

### Page Structure (after html.to.design import)

```
Page 1: 📋 Cover
  → App name, version, designer, date, Vercel preview URL

Page 2: 🗺 User Flows
  → Connector diagram linking all screens by flow
  → Named flows: "Onboarding", "Core Feature", "Profile", etc.

Page 3: 📱 Onboarding Screens
  → All onboarding screens in flow order
  → Annotated with navigation triggers

Page 4: 📱 Core Feature Screens
  → Main app screens, grouped by feature

Page 5: 📱 Settings & Profile

Page 6: 🔗 Prototype
  → Prototype connections wired between all screens
  → Starting frame: Splash / Launcher
  → Overlay connections for sheets and dialogs

Page 7: 🧩 Component Map
  → Which components from the Design System appear in each screen
  → Good for developer reference
```

**In Figma Dev Mode:**
- Mark all frames "Ready for Dev"
- Ensure all colours link to Variables
- Ensure all text links to Text Styles

---

## File 5 — Cover Thumbnail Kit

**When:** When selling/sharing your work (Gumroad, Dribbble, Behance, Twitter)  
**Tool:** Figma Design file  
**Format:** Export as PNG / JPG at 2× resolution

### Frames to Create

```
📐 Gumroad Cover (1280×720px)
  → Product name + tagline + key feature pills + mock screenshot
  → Dark background version
  → Light background version

📐 Gumroad Thumbnail (600×600px)
  → Square format for product card grid
  → App icon or logo centred on brand colour
  → Short product name only

📐 Dribbble Shot (800×600px)
  → 1–2 key screens on brand-coloured background
  → Product name in corner

📐 Twitter/X Card (1200×628px)
  → "Just shipped: [AppName]" format
  → 3 screens in a row or single hero screen
  → CTA: "Link in bio"

📐 Behance Cover (1400×700px)
  → Wide hero with all screens arranged
  → Project name + discipline tags

📐 Case Study Header (2560×1440px)
  → Full-width hero for portfolio
  → Device mockup with key screen
  → Project title, year, discipline

📐 LinkedIn Post (1200×627px)
  → Professional announcement format
  → "New project: [AppName]" + 1 screen + your name
```

**Export checklist:**
- [ ] PNG at 2× resolution (Retina)
- [ ] JPEG at 90% quality for social (smaller file)
- [ ] Use exact brand colours from your colour variables
- [ ] No lorem ipsum — real copy only
- [ ] Test at small size — does it read at 300px wide?

---

## File 6 — Links Directory Page

**When:** When the project has 3+ Figma files  
**Tool:** Add as a page inside any existing Figma file (usually the Design System)  
**Format:** A single "links" page with cards for each file

### What to Include

Create a simple grid of link cards. Each card:

```
┌─────────────────────────────┐
│  🗺 User Flows              │
│  FigJam file                │
│  Last updated: [date]       │
│  → Open file                │
└─────────────────────────────┘
```

Files to link:
- User Flows (FigJam)
- Brand Guidelines
- Design System (this file)
- UI Screens / Dev Handoff
- Prototype (Figma prototype link)
- Live prototype URL (Vercel)
- GitHub repo (if applicable)
- Gumroad / portfolio link

**Tip:** Add a "Buy me a coffee" or "Hire me" card at the bottom if this is a portfolio piece.

---

## Optional Files

### A. Moodboard File
Create before brand guidelines. A free-form collection of visual inspiration.
- One frame per direction (A, B, C, D)
- Each frame: colour swatches, font specimens, texture, photo examples
- Mark your chosen direction with a ⭐

### B. Wireframe File  
If you need to validate layout before going high-fidelity.
- Grayscale only
- Use 8×8pt grid
- Focus on hierarchy and structure, not visual design

### C. Prototype Testing File
For user testing sessions.
- Remove all dev annotations
- Set up a clean prototype flow for the test task
- Use a "presenter mode" cover page with the task description

### D. Changelog / Version History
If iterating over multiple weeks.
- One page per version
- Note what changed, what was removed, and why

---

## Figma File Naming Convention

Use a consistent naming pattern across all files:

```
[ProjectName] — [File Type] — v[version]

Examples:
MyApp — User Flows — v1
MyApp — Brand Guidelines — v2
MyApp — Design System — v1
MyApp — UI Screens — v3 (Handoff)
MyApp — Cover Thumbnails
```

---

## Tips for Keeping Figma Files Tidy

- **One file per purpose** — don't cram everything into one giant file
- **Version in the filename** — don't overwrite, increment the version
- **Archive old pages** — prefix with `_archive_` and move to the bottom
- **Always have a Cover page** — makes the file browser readable
- **Use Figma sections** — group related frames, add section labels
- **Publish the Design System as a Library** — so components stay in sync across files
- **Share view-only links** — never give clients edit access to working files
