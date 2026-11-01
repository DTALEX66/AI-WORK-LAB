# OP Personal Design System Inventory

## Purpose

This inventory maps the design-enhancement SSOT in `DESIGN-LAB` to Open Design 0.19 personal-resource types. It distinguishes executable personal capability from reference-only research. The repository is canonical; Open Design holds an officially installed, editable runtime mirror.

## Installed-object target

| Layer | Repository source | Count | OP carrier | Runtime policy |
|---|---|---:|---|---|
| Personal design systems | `design-lab/design-systems/*/DESIGN.md` | 3 | Editable user design system (`source=user`) | Create/update through `/api/design-systems`; Personal Workspace scope |
| Personal expert skills | `integrations/hosts/open-design/expert-suite/skills/*/SKILL.md` | 15 | User skill (`source=user`) | Install through `/api/skills/install` |
| Atomic capabilities | `packages/capabilities/atoms/*/SKILL.md` | 21 | Local trusted plugin resource | Official plugin install; dependency-first |
| Expert directors | `packages/capabilities/plugins/*/open-design.json` | 7 | Local trusted expert plugin | Official plugin install after atoms |
| Expert bundles | `packages/capabilities/bundles/*/open-design.json` | 3 | Local trusted bundle | Official plugin install after experts |

## Personal design systems

1. **Personal Design Intelligence** — master-method translation, style-lineage composition, evidence governance, personal principles, visual quality and production gates.
2. **UIUX Commercial Light** — commercial UI/UX, responsive behavior, accessibility, components and five golden-case patterns.
3. **Anomaly Monitor Dark** — CCTV/anomaly narrative, mobile minigame HUD, control-console hierarchy and game-state language.

## Personal expert skills

### Research and governance

- `master-method-translator`
- `style-lineage-composer`
- `design-source-curator`

### Visual, brand, spatial and production

- `visual-art-direction-director`
- `brand-identity-director`
- `spatial-exhibition-designer`
- `minigame-hud-designer`
- `visual-quality-critic`
- `production-handoff-specialist`

### UI/UX golden methods

- `mobile-task-flow-designer`
- `b2b-backoffice-designer`
- `ecommerce-pdp-designer`
- `settings-accessibility-designer`
- `responsive-content-designer`
- `uiux-commercial-light-system`

## Master and lineage research conversion

| Source | Inventory | Eligibility | Personal-system conversion |
|---|---:|---|---|
| `MASTER_REGISTRY.json` | 497 designers/studios | 77 translated-methods-only; 420 research-only | Discovery index; names never become direct style prompts |
| `ANCHOR_METHOD_CARDS.json` | 77 method cards | Curated synthesis drafts | Evidence → decision logic → anonymous project directives |
| `STYLE_LINEAGES.json` | 47 lineages | Research grammar | One primary + at most two supporting lineages; influence cap 30% |
| `STYLE_ANALYSIS_CARDS.json` | 47 analysis cards | Curated local synthesis | Problems, decisions, craft grammar, applications, quality signals and failure modes |
| Visual/global source registries | 134 sources | 119 license-verified; 15 unverified | Reference/derive/adapter/vendor-adapt/quarantine policy |

### Conversion rules

1. Names and movements remain in research notes only.
2. Final generation uses anonymous, project-specific decisions: structure, reading path, typography, color area, imagery, material, motion, spatial behavior and production.
3. At least two sources are required for master research, including one institutional/primary source, with at least three projects or periods compared.
4. Observation, inference and project translation are recorded separately.
5. Signature compositions, marks, motifs, proprietary type, protected images and copied text are excluded.
6. The 420 unverified seeds cannot enter generation until a method card and evidence record exist.

## Reference and validation assets

| Asset class | Count | OP use |
|---|---:|---|
| Design templates | 21 Markdown templates | On-demand skill references, not standalone catalog clutter |
| Domain Packs | 2 | Expert workflow evidence and scenario contracts |
| Golden benchmark cases | 5 | UI/UX method examples and regression baselines |
| Visual packs | 1 | Manifest-controlled project imagery; no unlicensed bulk ingestion |
| Evaluation rubrics | 19 | Preflight, critique and acceptance gates |
| Knowledge files | 28 | On-demand reference context |

## Source-governance decision

- `reference`: cite and independently summarize; do not copy essays, images, videos or portfolios.
- `derive`: independently implement methods; do not copy source wording/code.
- `adapter`: integrate only after interface, version, license and security review.
- `vendor-adapt`: preserve attribution and version pinning.
- `quarantine` or `review-required`: do not enter runtime generation context.

## Official-install boundary

Allowed:

- `/api/design-systems` create/update for editable personal design systems.
- `/api/skills/install` and official skill deletion for user skills.
- Official local/trusted plugin install/uninstall/reinstall.
- Read-only SQLite verification.

Forbidden:

- `INSERT`, `UPDATE` or `DELETE` against `app.sqlite`.
- Fabricated `workspace_resources` rows or forced workspace bindings.
- Runtime staging as the canonical source.
- Hard-coded daemon/Web ports.
- Direct master-style imitation or unlicensed source ingestion.

## Verification contract

The installation is complete only when all three user design systems and all 15 user skills are returned by official APIs, the 31 plugin resources are local/trusted, the three bundles apply, seven expert manifests validate, Codex connection succeeds, Personal Workspace UI visibly lists the resources, and repository canonical/Python/npm/visual checks pass.
