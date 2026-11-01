# NX-510 — Design Production & Quality Evidence Adaptation

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Minimal-set adapters for design production evidence: tool capability probes,
SVG safety preflight, SPDX/REUSE manifest, and fixture closures that stay
`WAITING_HUMAN_CALIBRATION` until human-calibrated. No heavy tool stacking.

## Deliverables

1. **`10-workflow/workflow-assistance/scripts/workflow/production_evidence.py`**
   - `probe_tools()`: Playwright/axe-core/SVGO/PptxGenJS/Vega-Lite capability
     probes → `available`/`unavailable` (never fake success).
   - `svg_preflight()`: local SVG safety + production preflight (rejects inline
     script / foreignObject / event handlers / javascript:).
   - `spdx_manifest()`: SPDX/REUSE third-party source manifest (reuse-compliant).
   - `run_fixture_closures()`: 3 fixtures (brand/exhibition/minigame-hud); auto
     score used only for consistency/regression, stays `WAITING_HUMAN_CALIBRATION`
     until human calibrates.

2. **`verify_production_evidence.py`** — tool probes + SVG safety + fixture probe.

3. **`tests/test_production_evidence.py`** (9 tests).

4. **`run_quality_gate.py`** — `production-evidence` gate; wired into CI.

## Verification

```text
PRODUCTION_EVIDENCE_PASS tools_probed=5 fixtures=3 svg_safe=true calibration=WAITING_HUMAN_CALIBRATION
test_production_evidence: Ran 9 tests OK
QUALITY_GATE_PASS gates=production-evidence
```

## Honesty

- External tools report `unavailable` if not installed; no fabricated success.
- Automatic score is never authoritative — `WAITING_HUMAN_CALIBRATION` shown
  until a human calibrates.
- Local SVG/SPDX implementations; no heavy dependency install.

## Rollback

Remove `production_evidence.py`, `verify_production_evidence.py`,
`test_production_evidence.py`, the gate + CI step. No runtime dependency.
