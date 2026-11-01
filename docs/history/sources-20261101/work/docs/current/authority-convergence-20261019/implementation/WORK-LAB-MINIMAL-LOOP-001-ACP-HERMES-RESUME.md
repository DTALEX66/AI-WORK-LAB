# WORK-LAB-MINIMAL-LOOP-001 — Hermes advertised `resume` without an executable resume

**Status:** EXECUTED / VERIFIED (see §6). Parent: `WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019`.
**Date:** 2026-10-19
**Grant:** user directive 2026-10-19 — “执行所有未完成的任务，按照最新发你的任务包”.
This is the concrete Task Grant required by the parent taskpack §4/§6/§10; the problem selected is
the one reproduced and handed back on 2026-10-19.

## 1. Problem (real, connected, in-repo)

The tracked AG-06 verifier `scripts/ci/verify_acp_adapter_honesty.py` fails on the live tree:

```text
ACP_HONESTY_FAIL DECLARED_CAPABILITY_WITHOUT_IMPLEMENTATION hermes advertises execution
capability 'resume' but resume() produced no real effect (probe=NOT_IMPLEMENTED,
overridden=False); the declaration is a false success surface
```

`HermesAdapter.capabilities()["supports"]` listed `resume`; `HermesAdapter` does not override
`resume()`, so the inherited operation returns `NOT_IMPLEMENTED`. The declaration is a false
success surface, not a crash. No process is started and no network call is made.

## 2. Root cause and historical match

- `services/execution-federation/hermes_adapter.py:108` declared `acp.Capability.RESUME` whenever
  the CLI was launchable.
- `services/execution-federation/acp_adapter.py:179-186` returns `NOT_IMPLEMENTED` whenever
  `RESUME` is declared.
- The same defect was fixed for Codex and OpenHands on 2026-10-01 (`codex_adapter.py:86-90`,
  `openhands_adapter.py:80-82`): omit the declaration until a real native resume exists.
- Negative controls in `tests/workflow-assistance/nf22_registry_and_acp_honesty_gates.py`
  already prove the verifier fails closed on an over-claim.

## 3. Change scope

One product file only: `services/execution-federation/hermes_adapter.py`.

- Remove the `acp.Capability.RESUME,` declaration.
- Record the AG-06 reason beside the capability set, matching the two precedent adapters.

Not changed: `new()`, `prompt()`, `cancel()`, `fork()`, registration, runtime probing, the four
protected parallel-writer files, DESIGN-LAB, AAOS, and every other product surface.

## 4. Acceptance / readback

| # | Command (repo root) | Expected |
| --- | --- | --- |
| 1 | `.project-local/toolchains/wl-py311/Scripts/python.exe scripts/ci/verify_acp_adapter_honesty.py` | exit 0, `ACP_HONESTY_PASS` |
| 2 | `.project-local/toolchains/wl-py311/Scripts/python.exe tests/workflow-assistance/test_execution_federation.py` | `Ran 12 tests`, `OK` |
| 3 | `.project-local/toolchains/wl-py311/Scripts/python.exe tests/workflow-assistance/nf22_registry_and_acp_honesty_gates.py` | `Ran 49 tests`, `OK` |
| 4 | static scan of `services/execution-federation/hermes_adapter.py` | no `acp.Capability.RESUME,` declaration line (the explanatory comment still names `Capability.RESUME`, so the scan matches the declaration exactly, not the substring) |
| 5 | adapter readback with a fake launchable binary | `resume` absent; policy/evidence/trace/budget/handoff/acceptance still present |

## 5. Rollback

Restore the single removed line in `hermes_adapter.py`; no state, data or configuration is
involved. The verifier returns to the measured pre-repair red.

## 6. State separation

| Stage | State |
| --- | --- |
| Discovery / issue summary / historical match / handback | DELIVERED before this card (2026-10-19 candidate receipt) |
| Agent repair | EXECUTED (one-line product change) |
| Test and runtime readback | EXECUTED (verifier + adapter readback + exact test suites) |
| Close or continue | CLOSED for this problem; no second issue opened |
| Solution solidification | DELIVERED — `docs/current/authority-convergence-20261019/solutions/SOLUTION-001-ACP-HERMES-RESUME.md` |
| AAOS candidate | NOT SUBMITTED — no connected AAOS API; AAOS keeps formal review and acceptance |
