# ADR: WORK-LAB Language Architecture

**Status:** ACCEPTED
**Date:** 2026-09-21
**Deciders:** WORK-LAB control-plane owners
**Task:** U15 (WORK-LAB-AUDIT-CONVERGENCE-…-20260919) — Language architecture freeze

## Context

WORK-LAB spans three languages across several subsystems. Their boundaries were
implicit and had drifted: parts of the control plane were in Python, the desktop
shells in Rust/Tauri, the user-facing Observer/UI in React/TypeScript, and the
cross-language contracts in JSON Schema. This ADR freezes that split explicitly
so future work does not re-open it with a big-bang rewrite.

## Decision

### 1. UI — React + TypeScript

- All operator-facing UI (WORK-LAB Observer, Token Monitor, web dashboard) is
  **React + TypeScript**.
- The Tauri desktop surface embeds the React build (`frontendDist → dist`).
- The legacy static `web/` front is **deprecated as a production surface**; it is
  kept only because the 80 Observer UI/desktop contract tests still guard it.
  It is retired (not deleted) ahead of production convergence and requires
  explicit authorization to remove (test-guarded deletion).
- **No phantom data contract:** UI reads the real v3 snapshot projection only
  (U07 front-truth discipline). No frontend price / FX / quota / resource
  fabrication.

### 2. Desktop native — Rust + Tauri

- Tauri 2.x is the desktop shell. The per-app crate lives under
  `apps/<app>/src-tauri` (e.g. `observer`, `token-monitor`).
- Rust owns: the window/process lifecycle, validated loopback endpoint injection
  into the front-end (`validated_observer_api`), native readback of installed
  software identity, and any OS-level effect that JS cannot perform.
- **No second Update Authority** in Rust. Software-location truth is projected
  from the Python control plane / installation-identity contract (U17/P0-07).
- **No big-bang Rust rewrite** of the control plane.

### 3. Control plane / adapters / orchestration — Python

- The canonical store, collectors, sidecar (v3 snapshot + SSE), config
  transactions, receipts, durable inbox/outbox, and cross-project isolation all
  stay in **Python** (`packages/client-neutral-core`, `services/**`,
  `integrations/**`).
- Python is the **single writer** for canonical state (§ single-writer rule).
- The native readback for "did the config actually change" is Python, not Rust.

### 4. Cross-language contracts — JSON Schema SSOT

- The single source of truth for every shape that crosses a language boundary
  (RuntimeDescriptor, Snapshot v3, Execution, Usage, Receipt, Task, Evidence,
  Project, Software installation-identity, software-update pre/postflight) is a
  **JSON Schema** under `packages/contracts/schemas/**`.
- **No second contract authority.** Rust and TS types are *generated / projected*
  from these schemas, never hand-forked. (U16 tracks the generated-type
  conformance.)
- The Python side validates against the schema; TS/Rust generated types must
  stay conformed (see `scripts/ci/verify_contract_ssot.py` when added, U16).

### 5. Bootstrap / glue — minimal shell

- Bootstrapping stays minimal: a thin shell / cmd entry (`start-observer.cmd`,
  `start-observer.ps1`) that injects the validated `?api=` descriptor and runs
  the sidecar. No shell script is a source of truth for any contract or state.

## Consequences

- New UI work → React/TS. New native capability → Rust/Tauri. New control-plane
  logic → Python (single writer). New cross-language shape → JSON Schema first,
  then generated TS/Rust.
- Any proposal to rewrite the control plane in Rust, or to hand-maintain parallel
  TS/Rust contract copies, or to add a second Update Authority, is **rejected
  by this ADR** and must be re-opened here, not done silently.
- The legacy `web/` static front is a known, bounded, test-guarded debt, not a
  live production surface.

## Alternatives considered

- **All-Rust rewrite** — rejected: control plane is Python and single-writer by
  governance; a big-bang rewrite breaks the receipt/ledger authority and the
  observed-user-state truth chain.
- **All-TS front-end authority for costs/locations** — rejected: violates U07
  front-truth discipline and the no-second-Update-Authority rule.
- **Per-app hand-written TS/Rust contract types** — rejected: drifts from the
  JSON Schema SSOT; use generated types instead (U16).
