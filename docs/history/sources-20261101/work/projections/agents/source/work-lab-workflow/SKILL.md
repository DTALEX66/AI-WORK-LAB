---
name: work-lab-workflow
description: "Use for WORK-LAB workflow tasks; follow the project ledger, module, and verification boundaries."
version: 1.2.0
---

# WORK-LAB Workflow Contract

Use this skill only inside the WORK-LAB Git repository.

## What this product is

WORK-LAB is a client-neutral workflow management, governance, runtime monitoring and problem closed-loop
system for a personal AI environment. It connects managed agents, developer tools, workflow software, model
services and plugins; it discovers and groups problems, produces advice or Agent repair task packages,
tracks verification, and turns proven fixes into reusable maintenance solutions. It is not an agent, not an
agent runtime, not a model gateway, not a generic chat client, and not a professional auditor for every
project; external software executes the actual work. The repository is an auditable portable source, and
Hermes, Codex, CC Switch, GitHub, OpenHuman and Open Design are replaceable Adapters behind one contract,
not the product itself.

## Three projects, one boundary each

- WORK-LAB: general workflow governance, runtime monitoring, issue aggregation, repair coordination,
  reusable maintenance solutions and generic receipts. It is not a mandatory total dispatcher and does not
  replace Codex, Claude Code, Qoder or WorkBuddy for actual repair.
- ArcheAxis-Knowledge-OS (AAOS): full knowledge lifecycle, human knowledge work, research and learning, AI
  learning assets, bidirectional learning and long-term project memory.
- DESIGN-LAB: professional design of all types, native assets, the design-specific execution core and
  professional acceptance.

Machine authority: `.project/governance/three-project-boundary.json`. A task in one project grants no write
access to another. Design capability is neither collected nor managed here.

## Ownership

- Module roots are exactly two (`.project/governance/module-ownership.json`): `packages/client-neutral-core`
  (Task Ledger, Telemetry Ledger, sidecar, adapters, delivery gates) and `apps/observer` (read-only
  projection). `services/`, `integrations/`, `config/`, `apps/token-monitor/` and `scripts/` are active
  supporting surfaces, not module roots.
- `apps/observer` is read-only. It may read Workflow-owned projections but must not execute, approve, retry,
  apply, rollback, change task state, or write the Telemetry Ledger.
- Retired module paths must not be restored.

## Desktop scope

The product surface is the desktop Observer window plus the existing desktop floating HUD. Mobile is out of
scope: it is not built, not queued, and not recorded as a deferred or frozen task.

## Truth discipline

- Unknown is never padded to zero, and an absent field is not an empty one; report PROJECTED, NULL_FIELD and
  SOURCE_GAP as different origins.
- A lost connection is not a stopped subject, and a `turn_end` signal is not the completion of a project.
- Demo and fixture data never enter production code paths.
- A colour or layout proposal from an inbound task pack becomes an opt-in theme
  (`?palette=master`) and never overwrites the shipped default values.

## Problem loop

Discovery, duplicate/related grouping, issue summary, matching prior solutions, advice or an Agent repair
package, user/policy handoff, actual repair, tests and runtime readback, closure, solution solidification,
and AAOS knowledge candidates are separate states. Agent self-report, HTTP 200, a single exit code, a
document edit or a submitted candidate never proves repair, verification or AAOS acceptance.

## Writer boundary

- One writer owns a checkout; parallel writers require separate worktrees.
- Do not edit a checkout concurrently with another writer or reviewer.
- Do not commit, push, publish, create a PR, merge, install software, or modify global client configuration
  unless the user explicitly authorizes that exact side effect.
- Whether an external client is actually deployed is recorded as unverified unless it was read back in this
  session; an unverified claim is written as unverified, not as satisfied.

## Runtime and evidence

- Keep temporary files, caches, logs, test environments, Task Ledger state and generated evidence under the
  project `.project-local/` directory (`runs/` for transient state, `artifacts/` for evidence).
- Never read, print, copy, commit or upload credentials, `.env` files, auth stores, private keys, browser
  data, tokens, prompt bodies or response bodies.
- Never access `E:\` or `F:\` — read or write — without explicit per-path, per-operation authorization
  (`.project/governance/project-data-boundary.json`).

## Verification

Run checks from the exact module path and scope them to the changed surface. The canonical full gate is:

```text
python services/orchestration/run_quality_gate.py verify
```

Do not run the full local governance suite as the default judge; the current rule is change-scoped local
gates and exact-SHA CI as the final judge. Distinguish structural checks, local runtime checks, exact-SHA CI,
and release evidence. A local test pass is not proof of exact-SHA CI or publication. A render or measurement
receipt must name the bytes it looked at.

## Task execution

Before changing code, read the relevant `AGENTS.md`, inspect the project task contract, and locate the symbol
or configuration owner. The single live task register is `taskpacks/current/OPEN-TASK-REGISTER.md`. The
current taskpack is `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md`; every other row
in the register is FROZEN_20261019 and must not be dispatched, status-rewritten or closed without evidence.
The first real minimal loop `WORK-LAB-MINIMAL-LOOP-001` was delivered on 2026-10-19 under the user's
explicit Task Grant; its implementation card and `SOLUTION-001` are under
`docs/current/authority-convergence-20261019/`. Further loops or capabilities still need a new explicit
user Task Grant; future capability states are in `docs/current/authority-convergence-20261019/ROADMAP.md`.
Use the Workflow-owned Task Ledger for durable task state when the task contract requires it. Observer
projections are read-only and are never a second source of truth.

## Scoped references

Read repository-relative `docs/current/workflow-assistance/skill-references/observer.md` only for Observer
delivery, or `docs/current/workflow-assistance/skill-references/external-clients.md` for Open Design /
OpenHuman boundary work. Generic debugging or testing advice is not a separate required workflow.
