---
name: runtime-continuity-governance
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/runtime-continuity-governance/SKILL.md
---

---
name: runtime-continuity-governance
description: "Use when validating live runtime continuity and recovery."
version: 1.2.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [runtime, desktop, handoff, recovery, updater, plugins, verification]
    related_skills: [agent-workflow-fortress, project-data-boundary, windows-development-environment]
---

# Runtime Continuity Governance

## Use when

Use for live application runtimes that must remain recoverable while repairing a
Desktop launcher, source checkout, updater path, bundled plugin inventory,
shortcut, or storage footprint. It applies across products; it is not a
product-specific migration recipe.

## Core rule

A handoff is historical evidence, not authority over the current machine. Before
any write, re-resolve the current runtime topology and let current filesystem,
process, Git, and UI evidence override old path names and earlier conclusions.

## Read-only preflight

For Windows shortcut/Git-Bash quoting and a compact non-secret command recipe,
see [Windows live-runtime revalidation](references/windows-live-runtime-revalidation.md).

1. Resolve the Desktop shortcut target, working directory, icon resource, active
   executable, canonical source/runtime root, and required resource files.
2. Confirm whether the canonical root is a Git checkout. Capture only safe Git
   metadata: branch, remote identity, `status --short --branch`, ahead/behind,
   dirty-file names, and relevant diff statistics. Never print credentials.
3. Determine whether older launchers, rebuild directories, or transition copies
   are still present. An absent path may be a completed migration, not a missing
   dependency.
4. Inventory running processes and active writers without killing them. Treat
   state databases, current logs, venvs, cache directories, installers, and
   recovery snapshots as in-use until owner, lock, recovery, and regenerability
   evidence proves otherwise.
5. Validate plugins with the official plugin inventory. Bundled plugins belong
   in the canonical runtime tree; absence from a user-home plugin override
   directory is not evidence of absence or breakage.

## Dirty or diverged source roots

If a live runtime checkout is dirty, ahead, behind, or both:

- Do **not** run update, reset, clean, rebase, replace, delete, or copy Git
  metadata into another runtime.
- First identify the owner and intent of every dirty file, preserve a rollback
  point, and establish single-writer ownership.
- Wait for a normal Desktop shutdown before changes that can conflict with the
  active backend, renderer, venv, or session state.
- After reconciliation, perform a normal relaunch and prove backend startup,
  updater behavior, settings/appearance rendering, chat, and required plugin
  availability with fresh evidence.

## Interrupted updater or relaunch reconciliation

A lost terminal/session handle, interrupted wait, missing process handle, or Desktop disappearance makes the update outcome **unknown**. It is not evidence of failure and not permission to rerun the updater.

1. Before any retry, reconcile the current process tree and updater command line, the canonical checkout `HEAD` versus fetched upstream, worktree cleanliness/stash/worktree count, installed version, dependency integrity, and updater/build stamp timestamps.
2. Treat `process/session not found` as “the observer lost its handle,” not as an updater exit status. If the original stdout/exit code is unavailable, derive only what current independent evidence proves.
3. A GUI that reappears proves renderer availability at that instant. It does **not** prove the update completed, that post-update migration succeeded, or that the earlier exit root cause is fixed. Verify the backend executable path, exact checkout, data readback, and official update-check result separately.
4. Do not restart an updater while any updater/build process or unsettled stamp is present. Require a quiet interval and stable identities before deciding whether a retry is necessary.
5. Artifacts that regenerate after a clean restart—such as official backup state files, staging roots, runtime caches, or app-server copies—are active lifecycle assets, not stale debris. Reclassify them from observed regeneration instead of repeatedly deleting them by name.
6. When an Electron close button only hides the window, use the product's official Exit path or a non-forcing OS lifecycle mechanism, then prove the entire exact owned process tree is gone before cleanup or cold-start claims.

See [`references/interrupted-updater-reconciliation.md`](references/interrupted-updater-reconciliation.md) for the evidence matrix and report wording.

## Handoff maintenance

When current topology supersedes a tracked repair handoff, add a dated **Current
state** section that names the canonical root and explicitly retires obsolete
paths. Keep former steps only as historical recovery context. Do not delegate a
handoff that instructs an agent to recreate or invoke paths that no longer
exist.

## Cleanup boundary

Large does not mean redundant. Preserve shared session DBs, active logs,
recovery snapshots, source backups, runtime dependencies, and current installers
until their restore purpose, process references, and reproducibility have been
verified. Prefer official session retention and narrow, project-local cache
cleanup over broad deletion.

## Live restart readback

A normal restart is part of acceptance, not an optional smoke test. For a loopback desktop runtime:

1. Close only the exact owned native shell/window and wait for its backend to stop; do not terminate unrelated WebView2 or workflow processes.
2. Verify the old backend endpoint is unavailable after shutdown.
3. Relaunch once and discover the new dynamic backend port from the owned child process/readiness signal instead of reusing the old port.
4. Read back persisted jobs, outbox state, receipts, and the WebView2 `--user-data-dir` from the new process tree; require the data root to remain inside the approved project boundary.
5. Re-open the UI and use UIAutomation snapshots after actions to prove the rendered state matches the backend. If an embedded CUA session has expired, declare a fresh driver session through the installed driver CLI; do not downgrade the result to a build-only claim.

## Backend worker and sidecar continuity reviews

For SQLite-backed collectors, supervised worker threads, source coverage, LIVE/FRESH semantics, SSE revision continuity, idempotent ingestion, and durable retry budgets, use [`references/backend-worker-continuity-review.md`](references/backend-worker-continuity-review.md). It also defines how to preserve an exact read-only verdict when another writer stages or commits the candidate during review.

For embedded web assets, final-binary provenance, last-good OFFLINE precedence, same-PID WebView recovery, and typed Windows PID liveness, use [`references/exact-artifact-runtime-truth.md`](references/exact-artifact-runtime-truth.md). Rebuild and rerun acceptance after the final embedded-asset edit; evidence from an intermediate executable does not transfer to the final hash.

For frontend polling plus SSE/WebSocket state machines, same-revision races, permanently closed transports, source-generation resets, and API-origin URL binding, use [`references/frontend-transport-race-review.md`](references/frontend-transport-race-review.md). Require executable completion-order probes rather than callback-registration assertions.

## Verification checklist

- [ ] Current shortcut and canonical root verified
- [ ] Git cleanliness/divergence captured before writes
- [ ] Active process / writer ownership checked
- [ ] Producer continuity sampled across at least one configured tick plus margin; sub-tick silence is labelled `INSUFFICIENT_WINDOW`, not failure
- [ ] Writer watermark, heartbeat and SSE revision advance while intended app/sidecar PIDs and artifact identity remain stable
- [ ] Idempotent fact rows remain stable while health/run counters advance
- [ ] Bundled vs override plugin location distinguished
- [ ] Historic handoff reconciled with live topology
- [ ] Normal restart and UI acceptance demonstrated after a repair
- [ ] Cleanup candidates proven regenerable and unreferenced
