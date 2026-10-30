# Capability index

Generated from `design-lab/config/product-manifest.json` (single source of truth).

> Actual per-capability evidence level (E0-E5, bound to tree SHA) lives in
> `design-lab/config/capability-evidence-index.json`, validated by
> `design-lab/scripts/verify_capability_evidence_v4.py`.

| Capability | Title | Min evidence | Domain | Owner | Paths |
|---|---|---|---|---|---|
| `design-intelligence` | Brief, direction, design system and critique intelligence | E2 | all | DTALEX66 | `research/candidates/, packages/capabilities/atoms/brief-normalizer/, packages/capabilities/atoms/source-intake-gate/` |
| `professional-visual-domains` | Brand, graphic, UIUX, ecommerce, editorial, packaging, spatial, exhibition, 3D, motion, video, game visual | E2 | all | DTALEX66 | `design-lab/domain-packs/, packages/capabilities/scenarios/, design-lab/profiles/` |
| `visual-quality` | Visual quality, design feeling and anti-AI-slop engine | E2 | all | DTALEX66 | `packages/capabilities/quality/, packages/capabilities/bundles/visual-quality-core/, design-lab/evals/rubrics/visual-quality-core.rubric.json, design-lab/research/visual-quality/, design-lab/scripts/score_visual_quality.py, design-lab/scripts/score_design_critique.py, design-lab/scripts/compare_visual_iterations.py, design-lab/scripts/verify_visual_scoring_v3.py` |
| `creative-toolchain` | Host / agent / creative-tool adapters | E1 | all | DTALEX66 | `integrations/` |
| `production-handoff` | Production preflight and editable delivery | E2 | all | DTALEX66 | `design-lab/production/, packages/capabilities/atoms/commercial-preflight/, packages/capabilities/atoms/delivery-packager/, design-lab/schemas/preflight.schema.json, design-lab/schemas/design-handoff.schema.json, design-lab/schemas/provenance.schema.json` |
| `research-evidence` | Research, evidence and benchmarks | E1 | governance | DTALEX66 | `vendor/, design-lab/research/, design-lab/evals/, design-lab/scripts/verify_source_registry.py` |
| `release-evidence` | Review, exact-SHA CI and release evidence | E4 | governance | DTALEX66 | `.github/workflows/, design-lab/evals/, design-lab/config/capability-status.json, design-lab/schemas/release-evidence.schema.json, design-lab/scripts/verify_release_evidence.py` |
