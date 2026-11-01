# Open-source absorption candidates

Purpose: track open-source plugins, skills, DESIGN.md systems, and templates that can strengthen Open Design through this assistance repo without vendoring large upstream repositories.

## Rules

- Absorb capability patterns, prompt structure, QA gates, template taxonomy, and references first.
- Do not bulk-copy third-party repos or generated media.
- Keep source attribution and license notes.
- Prefer small Markdown templates under `design-lab/templates/`.
- Promote only proven patterns into Open Design plugins.

## P0: absorb now

| Source | License observed | Why it matters | Absorb as |
|---|---:|---|---|
| `nexu-io/open-design` official `plugins/spec` and docs | project upstream | canonical plugin shape, publishing, registry, install flow | plugin install/publishing notes, plugin scaffold conventions |
| `nexu-io/open-design` `design-templates` | project upstream | dashboard, SaaS landing, mobile, poster, critique, deck templates | local layout/graphic/deck template taxonomy |
| `Nutlope/hallmark` | MIT | anti-AI-slop design gates, theme variation, pre-emit self-critique | `templates/qa/anti-ai-slop-checklist.md` |
| `VoltAgent/awesome-design-md` | MIT | brand DESIGN.md references for developer/SaaS UI | style reference index, future DESIGN.md refs |
| `dominikmartn/nothing-design-skill` | MIT | monochrome industrial UI, dot matrix, mechanical controls | HUD/console rules, dark industrial variants |

## P1: absorb next

| Source | License observed | Why it matters | Absorb as |
|---|---:|---|---|
| `JimLiu/baoyu-design` | MIT | portable high-fidelity HTML design skill; mockups, dashboards, decks | prototype/deck generation workflow |
| `bitjaru/styleseed` | MIT | design judgment, brand skins, component and motion rules | component-patterns and motion templates |
| `hamen/material-3-skill` | MIT | Material 3 tokens/components/audit | standard UI component checklist |
| `google-labs-code/stitch-skills` | Apache-2.0 | Agent Skills open structure and marketplace patterns | agent skill compatibility note |
| `kzhrknt/awesome-design-md-jp` | MIT | CJK typography and line-breaking rules | `templates/typography/cjk-ui-typography.md` |

## P2: later

| Source | Why later | Possible local output |
|---|---|---|
| `m-roberts/deploy-to-cloudflare-pages` | side-effecting publishing flow; needs confirmation UX | `plugins/deploy-preview/` |
| `VaqueroGroup/reusable-workflow-author` | useful scaffold idea but needs local validation | `scripts/scaffold_open_design_plugin.py` |
| `lefarcen/pitch-deck-bootstrap` | deck-focused; lower priority than UI/UX now | `templates/decks/pitch-deck.md` |
| `lefarcen/brief-to-slide-outline` | content structuring; can follow deck work | brief-to-outline template |
| `dominikmartn/hue` | brand extraction may need website/screenshot tooling | `plugins/brand-to-packages/design-system/` |

## First absorption batch landed locally

```text
design-lab/templates/qa/anti-ai-slop-checklist.md
design-lab/templates/layouts/landing-page.md
design-lab/templates/layouts/dashboard.md
design-lab/templates/layouts/mobile-menu.md
design-lab/templates/layouts/settings-panel.md
design-lab/templates/layouts/pricing-page.md
design-lab/templates/layouts/product-page.md
design-lab/templates/graphic/poster-cover.md
design-lab/templates/graphic/social-card.md
design-lab/templates/decks/pitch-deck.md
design-lab/templates/motion/motion-system.md
design-lab/templates/brand/brand-identity-system.md
design-lab/templates/spatial/culture-wall.md
design-lab/templates/spatial/exhibition-hall.md
design-lab/templates/visual/art-direction.md
design-lab/templates/visual/2d-design.md
design-lab/templates/visual/3d-design.md
design-lab/templates/typography/cjk-ui-typography.md
design-lab/templates/design-systems/style-reference-index.md
```

These templates intentionally encode reusable design judgment rather than third-party code.

## Promotion path

1. Capture pattern as Markdown template.
2. Use it inside Open Design prompts/plugins.
3. Run `design-qa-critic` after generation.
4. If it repeatedly works, promote the pattern into a plugin SKILL.md.
5. If it becomes a full visual language, promote it into `design-systems/`.
