# WORK-LAB Local Deployment Smoothness — 2026-08-11

**Status:** `LOCAL_RUNTIME_DEPLOYED / NATIVE_AND_GLOBAL_GATES_PENDING`

## Objective

Complete the project-local runtime wiring needed for a quiet, truthful and
repeatable WORK-LAB load experience: Workflow remains the single canonical
writer; the Sidecar publishes real canonical changes; Observer remains a
strictly read-only consumer; Windows process probes do not signal or interfere
with unrelated console processes; bundled desktop entry points never claim
LIVE without a discovered live source.

## Ownership and boundaries

- Writer: the current Codex task; one writer owns this checkout.
- This is an explicit cross-module task for the root control plane,
  `10-workflow/workflow-assistance`, and the read-only
  `30-observer/work-lab-observer` presentation surface.
- Observer must not execute, approve, retry, apply, roll back, mutate task
  state, or write the Telemetry Ledger.
- Runtime state and build output belong under ignored `.hermes/task-runtime/`
  or `.hermes/task-artifacts/` paths.
- No E-drive access, global Codex/Hermes apply, dependency installation,
  commit, push, publication or release is authorized by this task card.

## Allowed source paths

- `10-workflow/workflow-assistance/scripts/workflow/durable_worker.py`
- `10-workflow/workflow-assistance/scripts/workflow/sidecar.py`
- `10-workflow/workflow-assistance/tests/test_durable_worker.py`
- `10-workflow/workflow-assistance/tests/test_sidecar.py`
- `30-observer/work-lab-observer/scripts/observer_dashboard.py`
- `30-observer/work-lab-observer/tests/test_observer_dashboard.py`
- `30-observer/work-lab-observer/src-tauri/tauri.conf.json`
- `30-observer/work-lab-observer/src-tauri/src/lib.rs`
- `30-observer/work-lab-observer/web/scripts/api.js`
- `30-observer/work-lab-observer/web/scripts/app.js`
- `30-observer/work-lab-observer/tests/`
- `50-taskpacks/TASKPACK_SUMMARY.md`
- this task pack

Any additional tracked path requires an amendment here before it is edited.

## Verification contract

- Add focused regressions for every behavioral fix.
- Prove the worker CLI persists the standard collectors for an explicit
  project root and project identity.
- Prove a second canonical-store writer produces a same-session Sidecar event
  and that LIVE is used only while the watcher is active.
- Prove Windows PID liveness uses a read-only process handle instead of
  `os.kill(pid, 0)`.
- Prove bundled Tauri URLs do not hard-code LIVE and the read-only frontend can
  use only a validated loopback dashboard endpoint.
- Deploy the local project runtime, read back Workflow and Observer health,
  verify Observer reads do not mutate canonical storage, and run the exact
  module/root gates plus final diff/status inspection.

## Recovery

Recovery is limited to stopping the exact task-owned runtime PIDs and reverting
this task-owned diff after reviewing it. No reset, clean, destructive delete or
overwrite of unknown work is permitted.

## Implemented result

- The durable worker CLI now requires an explicit project root, registers the
  project and runs all five standard collectors instead of silently starting
  with an empty collector list.
- The production Sidecar starts a bounded canonical-store watcher, reports
  LIVE only while that watcher is active, and publishes external worker writes
  to existing SSE subscribers.
- Observer PID discovery uses a read-only Windows process handle rather than a
  console-control signal. The dashboard accepts the Tauri local origin but
  rejects origin lookalikes and non-loopback endpoints.
- Tauri bundled windows start UNKNOWN. A process-scoped
  `WORK_LAB_OBSERVER_API_URL` may inject only an HTTP loopback
  `/api/dashboard` endpoint; the frontend preserves that endpoint across view
  changes and honors the server-declared mode instead of forcing LIVE.
- The local canonical store contains the registered `work-lab` project and
  standard collector facts. Sidecar and Observer are running on dynamic
  loopback ports recorded under ignored `.hermes/task-runtime/` state.

## Verification result

- `PASS`: Workflow focused regressions, 6 durable-worker tests and 3 Sidecar
  tests.
- `PASS`: canonical Workflow quality gate returned exit 0 with every required
  gate passing.
- `PASS`: Observer Python suite, 47/47 tests.
- `PASS`: Observer UI/component suite, 44/44 tests.
- `PASS`: live readback reports Sidecar `ok/LIVE`, canonical integrity `ok`,
  Observer `ok/readOnly/LIVE`, one registered project and discovered transport.
- `PASS`: ten consecutive Observer projection GETs left canonical SQLite and
  WAL length and last-write metadata unchanged.
- `PARTIAL`: root CI contract suite ran 72 tests; 71 passed and the
  publication-only exact-tree test correctly rejected the uncommitted dirty
  checkout.
- `NOT EXECUTED`: native Tauri compile/package. This machine exposes neither
  Rust/Cargo nor MSVC Build Tools; Node desktop contracts are not treated as a
  substitute for a native build.
- `BLOCKED`: global Codex/Hermes apply remains outside the project-local
  boundary and requires exact path-level authorization. Commit, push,
  exact-SHA CI, publication and release remain separate approval gates.
