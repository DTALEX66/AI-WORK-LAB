---
name: open-design-integration
description: Open Design integration for professional visual output.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [design, design-system, open-design, anti-slop, quality, brand, tokens, ui, ux]
    related_skills: [claude-design, popular-web-designs, design-md]
triggers:
  - open design
  - design system
  - anti-slop
  - brand extraction
  - design quality
  - professional design
  - corporate branding
  - exhibition design
  - culture wall
  - DESIGN.md
  - design tokens
  - visual identity
---

# Open Design Integration

Use this skill when the user needs production-grade visual design output and generic
AI-generated "slop" is unacceptable. Open Design (open-design.ai) is an open-source,
local-first design studio that connects to coding agents (Claude Code, Codex, Cursor,
Hermes, etc.) and enforces professional quality through a structured prompt stack.

## When to Use

- User needs corporate branding, marketing surfaces, or product UIs
- User complains about generic/purple-gradient/emoji-heavy AI output
- User wants consistent visual identity across multiple artifacts
- User asks for DESIGN.md, design tokens, or a design system spec
- User needs exhibition/culture wall/wayfinding design
- User wants to integrate with Open Design's skill/design-system ecosystem

## The Six-Layer Anti-Slop Engine

Open Design enforces quality through six layers. Apply these when generating any
professional design artifact:

| Layer | Name | What It Does |
|---|---|---|
| 1 | Discovery Form | Before generating, lock the brief: audience, tone, brand, scale, constraints |
| 2 | Brand Extraction | If user provides URL/PDF/screenshot, extract real brand values (don't guess) |
| 3 | 5-Dim Self-Critique | Rate output on Philosophy, Hierarchy, Execution, Specificity, Restraint (min 3/5 each) |
| 4 | P0/P1/P2 Checklist | Priority-gated quality checklist — P0 must all pass before emitting |
| 5 | Hard-coded Blacklist | Forbidden patterns: purple gradients, emoji icons, left-border cards, etc. |
| 6 | Honest Placeholders | Grey blocks instead of invented metrics ("10x faster", "99.9% uptime") |

## DESIGN.md 9-Section Schema

Open Design's design system format. Each DESIGN.md combines YAML frontmatter (tokens)
with Markdown body (rationale). The 9 sections:

1. **Visual Theme & Atmosphere** — Mood, feel, references
2. **Color Palette & Roles** — Background, surface, text, accent (OKLch preferred)
3. **Typography Rules** — Display + Body + Mono stacks, scale, weights
4. **Component Stylings** — Buttons, cards, inputs, dividers
5. **Layout Principles** — Max width, grid, section spacing, content padding
6. **Depth & Elevation** — Shadows (sparse), borders, focus rings
7. **Do's and Don'ts** — Explicit permissions and prohibitions
8. **Responsive Behavior** — Breakpoints, mobile/tablet/desktop rules
9. **Agent Prompt Guide** — Additional constraints for the AI agent

**Key insight**: Tokens (hex values, font names) explain only ~1/3 of brand character.
The other 2/3 comes from prose constraints: where accent appears, what to avoid, voice rules.

## Anti-Slop Blacklist (Hard-coded)

NEVER in professional output:

- Purple/violet/indigo gradient backgrounds
- Emoji as feature icons (✨🚀🎯🌟💡)
- Rounded cards with left colored border accent
- Hand-drawn SVG humans/faces/landscapes
- Inter/Roboto/Arial as a **display** face (body is fine)
- Invented metrics without a source citation
- Filler copy ("Feature One", "Feature Two", lorem ipsum)
- Icon next to every heading
- Gradient on every background
- Warm beige/cream/peach/pink/orange-brown backgrounds (unless brand requires)
- Exposed designer settings, viewport selectors, "demo controls" as UI

## 5-Dimensional Self-Critique Framework

Rate each dimension 1-5 before emitting. Minimum: 3/5 on all.

| Dimension | Question |
|---|---|
| **Philosophy** | Does the visual posture match what was asked, or did it drift to defaults? |
| **Hierarchy** | Does the eye land in one obvious place per screen, or is everything competing? |
| **Execution** | Typography, spacing, alignment, contrast — correct or just close? |
| **Specificity** | Every word/number/image specific to THIS brief, or filler/generic stats? |
| **Restraint** | One accent used at most twice per screen, or three competing flourishes? |

## Skill × Design-System Orchestration

Open Design's power comes from composable skills + design systems:

- **Skills** (137+): Tell the agent *how* to build specific artifacts (landing, deck, brand kit, etc.)
- **Design Systems** (151+): Tell the agent *how it should look* (Linear, Stripe, Vercel, Apple, etc.)
- **Craft** (12): Universal design rules (anti-slop, typography, color, accessibility)
- **Templates** (200+): Ready-to-render HTML templates

When the user needs a specific look, pick a matching design system first. When they need
a specific artifact type, pick a matching skill. The agent reads both and generates
constrained output.

## Discovery Form Pattern

When the brief is vague ("make it professional", "modern Chinese style"), resolve it
into explicit dimensions before generating:

| Vague phrase | Resolved dimension | Default value |
|---|---|---|
| "professional" | Mood | Engineering-trustworthy, restrained |
| "modern" | Style | Minimal, no ornamentation |
| "tech feel" | Direction | Linear/Vercel-style, mono accents |
| "warm" | Temperature | Neutral-warm oklch, NOT beige/cream |
| "luxury" | Material | Matte metals, no glossy gradients |
| "spacious" | Density | Section gap 96px, info density ≤ 40% |
| "information-rich" | Density | Section gap 64px, info density ≤ 60% |

## Workflow: Professional Design Output

1. **Gather context** — Read brand docs, existing product screenshots, repo components
2. **Lock the brief** — Resolve vague language into explicit dimensions (see above)
3. **Bind design system** — Pick or create a DESIGN.md with tokens + prose constraints
4. **Pre-flight** — Read active DESIGN.md + skill assets before writing any code
5. **Generate** — Build the artifact using bound tokens (no color invention)
6. **Self-critique** — Run 5-dim critique, fix any dimension < 3/5
7. **Checklist** — Verify P0 items all pass
8. **Anti-slop audit** — Scan against the blacklist
9. **Emit** — Output the artifact with verification status

## Pitfalls

- **Don't skip the discovery form.** Vague briefs produce generic output. 30 seconds of
  radios beats 30 minutes of redirects.
- **Don't rely on tokens alone.** Tokens explain 1/3 of brand character. Prose constraints
  (where accent appears, what to avoid) explain the other 2/3.
- **Don't freestyle the look.** Always bind a DESIGN.md or pick a direction from the
  curated library. The agent's default taste pushes everything toward a mean.
- **Don't ignore the anti-slop blacklist.** Purple gradients and emoji icons are the #1
  tell of AI-generated design.
- **Don't use the same font family for display and body.** Pair a display face with a
  quieter body face. Never use Inter/Roboto as a display face in professional work.
- **Don't invent metrics.** Use honest placeholders (grey blocks, "—", "[source needed]")
  instead of fake statistics.

## Reference Files

- `references/anti-slop-checklist.md` — Full anti-slop checklist for self-auditing
- `references/desgn-md-examples.md` — Example DESIGN.md files for common brand types
- `references/design-system-catalog.md` — Curated catalog of 151+ design systems by category
- `references/skill-catalog.md` — Curated catalog of 137+ skills by category

---

*Part of DESIGN-LAB's design quality assurance toolkit*
*Integrates with Open Design v0.21.0+ protocol*
