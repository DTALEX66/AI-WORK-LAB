# DESIGN-LAB Project Definition V3

## One-line definition

DESIGN-LAB is an **Agent-platform-neutral design capability and visual quality enhancement layer** (current reference host: Open Design), with model-neutral, style-neutral, domain-neutral, platform-neutral, rights-safe design intelligence, professional production, and editable delivery.

It helps Open Design and compatible agents move from “can generate a design-looking artifact” to “can reason with professional design judgment, source and rights boundaries, style lineage, master-method research, quality gates, production constraints, and delivery evidence.”

## Separation of concerns

| Layer | Owner | Responsibility |
|---|---|---|
| Open Design runtime | Open Design app/daemon | Project UI, Studio/canvas, Agent launch, plugin/scenario registration, preview, artifact export, stage events, provenance hooks. |
| Agent execution | Hermes / Codex / compatible agents | Reasoning, file operations, bounded implementation, review, runtime smoke, evidence capture. |
| Assistance repository | This repo | Design protocols, prompts, schemas, rubrics, knowledge, source registry, scenarios/atoms/bundles, preflight, delivery contracts, benchmark cases, verification scripts. |
| Example runtimes | `fixtures/domains/game-visual/`, `packages/design-system/`, exports | Reference and regression material only; not the primary product surface. |

## Core product loop

```text
Brief / files / images / references
→ source intake + rights gate
→ brief normalization and commercial routing
→ research / competitors / reference DNA
→ style lineage + anonymous master-method translation
→ three structurally distinct directions + human lock
→ DESIGN.md / DTCG tokens / components / asset contracts
→ image / HTML / deck / PDF / motion / 3D / spatial generation
→ domain jury + visual quality jury + deterministic checks
→ bounded refinement loop
→ digital / print / packaging / spatial / motion / 3D preflight
→ editable handoff + BOM + provenance + rollback
→ benchmark case + human review + capability evidence
```

## Evidence levels

| Level | Meaning | Allowed claim |
|---|---|---|
| E0 declared | Doc or plan exists. | Intent only. |
| E1 structural | Files, JSON, schemas, manifests, references and static validation pass. | Structurally available. |
| E2 isolated runtime | Staging or isolated command succeeds with read-back evidence. | Locally executable in isolation. |
| E3 live runtime | Current Open Design/Agent runtime registers and runs the capability. | Runtime available. |
| E4 release | Reviewed tree, commit, push, exact-SHA CI and remote read-back pass. | Release verified. |
| E5 commercial | Client/developer/production acceptance exists. | Commercially proven. |

No file, manifest, screenshot, or declarative status may be upgraded beyond the evidence it actually has.

## Non-goals

- Do not replace Open Design’s app, daemon, Studio/canvas, model routing or artifact runtime.
- Do not become a “master style generator” or tool for copying protected signature works.
- Do not vendor entire third-party repositories, model weights, fonts, asset packs, installers, credentials or private runtime state.
- Do not use template count, prompt length, source count, or name count as a proxy for capability maturity.
- Do not mark a capability as commercially usable without production preflight and external/human acceptance.

## V3 maturity target

The repository should move in dependency order:

1. trustworthy substrate and source registry;
2. isolated overlay application and rollback;
3. product manifest and evidence-index truth;
4. compatibility upgrade for the seven existing plugins;
5. Scenario/Atom/Bundle runtime contracts;
6. visual quality and master-method engine;
7. domain-specific commercial design pipelines;
8. production preflight and editable handoff;
9. benchmark cases, regression evidence and runtime integration;
10. independent review and user-authorized release.

## Safety boundaries

- No access to `E:\`.
- No credential/auth/token/cookie/private key reads.
- No project-external writes unless explicitly authorized.
- No commit, push, PR, merge, ruleset or release without explicit user authorization.
- Same checkout has one writer at a time; high-risk candidate trees require independent read-only review.
