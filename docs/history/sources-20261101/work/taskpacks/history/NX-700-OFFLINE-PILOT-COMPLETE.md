# NX-700 — Three-Branch Offline Pilot

**Status:** `COMPLETED`
**Task pack:** `WORK-LAB-STAGE-2-ABSORPTION-INTEROP`
**Date:** 2026-08-08

## Goal

Close the three required offline pilot loops using the existing WORK-LAB
modules, without adding a fourth product, second task runtime, provider call,
or external mutation.

## Pilot A — Workflow / Agent

- Hermes and Codex capability negotiation through the existing ACP adapter;
- Qwen ACP fixture explicitly unavailable when not installed;
- usage event normalized to `work-lab/observer-event/v2`;
- duplicate webhook replay validated through the existing Task Ledger replay;
- credentials and Prompt/Response bodies not read.

## Pilot B — Observer

- mixed task/usage fixtures projected through existing usage rollup;
- duplicate ingestion is idempotent;
- restart rebuild recomputes the same stable projection fields;
- corrupt fixture is isolated instead of entering rollup;
- offline viewing is represented and mutation surface is empty.

## Pilot C — Open Design

- structured brief → method/token contract → safe SVG preflight → readback;
- brand-layout and MINIGAME-HUD fixture IDs are included;
- automatic score remains regression-only;
- visual quality remains `HUMAN_PENDING` and both fixtures remain
  `WAITING_HUMAN_CALIBRATION`.

## Deliverables

1. **`scripts/ci/offline_pilot.py`** — deterministic composition of existing
   ACP, usage, replay, rollup, design-contract, and production-evidence modules.
2. **`scripts/ci/verify_offline_pilot.py`** — verifies all three branches and
   all live/external/human boundaries.
3. **`tests/ci/test_offline_pilot.py`** — 5 tests.
4. Integration CI wiring.

## Verification

```text
OFFLINE_PILOT_PASS pilots=3 offline_verified=True external_writes=false credentials=false live_claims=none human_calibration=pending
Ran 5 tests in 0.000s — OK
```

## Evidence boundary

This is an offline fixture pilot, not a claim of real provider execution,
production deployment, paid smoke, external agent control, or completed human
visual calibration. Those remain `UNKNOWN_NOT_RUN` / `HUMAN_PENDING`.

## Rollback

Remove the pilot module, verifier, tests, CI steps, this handoff, and ledger
entry. Existing component gates remain independently usable.
