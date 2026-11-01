# Architecture V2

```text
External brief/assets/references
        ↓
Source Intake Gate + Brief Normalizer
        ↓
Commercial Design Router
        ↓
Domain Scenario
        ↓
Research + Reference DNA + Strategy
        ↓
Three Directions + Human Decision
        ↓
DESIGN.md + DTCG Tokens + Project State
        ↓
Multi-artifact Generation
        ↓
Domain Quality Jury + Devloop
        ↓
Production Preflight
        ↓
Commercial Handoff + Provenance/BOM
        ↓
Benchmark Case + Capability Evidence
```

## Separation of concerns

- `atoms/`: bounded, machine-testable capabilities.
- `scenarios/`: ordered pipelines with human decision surfaces.
- `schemas/`: contracts between stages and agents.
- `knowledge/`: source-grounded professional rules.
- `profiles/`: deterministic production check sets.
- `evals/`: rubrics, baselines and regression cases.
- `adapters/`: external tools and standards; large dependencies stay outside core.
- `research/global-absorption/`: source, license and promotion registry.
