# WORK-LAB Hermes / DeepSeek Handoff — 2026-08-11

**Status:** `HERMES_GLOBAL_ASSETS_DEPLOYED / CODEX_TAURI_GIT_GATES_PENDING`

## Objective

Hand off the remaining WORK-LAB delivery gates to Hermes using DeepSeek while
preserving the single-writer, credential-safety, project-data and evidence
boundaries. This file is an execution packet, not proof that global apply,
native packaging, Git publication or release has occurred.

## Frozen checkout identity

- Repository: `D:\All projects\WORK-LAB`
- Branch: `main`
- Base HEAD: `881f3e3d25e6b95b025b014e2ab9941310448ed7`
- Checkout: dirty by design; it contains the Stage 3 reconciliation and local
  deployment work. Do not reset, restore, clean, reformat or silently replace
  any dirty path.
- One writer owns this checkout. Hermes/DeepSeek must not edit concurrently
  with Codex or another agent.

## Completed local work

- Workflow standard collectors are connected to the durable-worker CLI.
- Workflow Sidecar watches the canonical SQLite store and publishes real SSE
  deltas from cross-process writes.
- Observer uses a read-only Windows PID query, validated loopback-only
  dashboard/SSE endpoints and truthful LIVE/SNAPSHOT semantics.
- Local runtime is deployed under `.hermes/task-runtime/` with dynamic
  loopback endpoint descriptors.
- Verification:
  - Workflow focused tests: `6 + 3 PASS`.
  - Workflow canonical quality gate: `PASS`.
  - Observer Python: `47/47 PASS`.
  - Observer Node UI/component: `44/44 PASS`.
  - Runtime readback: Sidecar `ok/LIVE`, canonical integrity `ok`, Observer
    `ok/readOnly/LIVE`, one registered project.
  - Ten Observer GETs did not change canonical SQLite/WAL size or last-write
    metadata.
  - Root CI contract suite: `71/72 PARTIAL`; only the exact-clean-tree
    publication test fails while the checkout is uncommitted.

## Hermes global deployment — completed

Owner script:

`10-workflow/workflow-assistance/scripts/workflow/sync_hermes_workflow_assets.py`

Intended target:

`C:\Users\admin\AppData\Local\hermes`

The script deploys only contract-owned skill roots, launcher binaries,
`SOUL.md` and `.env.template`, using staging, backup, atomic replacement and
post-apply readback. It calls `deploy_portable(..., include_config=False)` and
therefore skips the mixed-ownership `config.yaml`; it must not read or modify
provider routing, authentication, sessions, credentials, tokens, logs, prompt
bodies or response bodies.

The platform safety reviewer required this exact additional authorization
before the real Home could be planned; the user supplied it on 2026-08-11:

> I explicitly authorize Codex to read hashes/metadata and write the
> Workflow-Assistance-managed `skills`, `bin`, `SOUL.md`, `.env.template`,
> backup and synchronization-state targets under
> `C:\Users\admin\AppData\Local\hermes`. I do not authorize reading or
> modifying `config.yaml` contents, auth, sessions, credentials, tokens, logs,
> prompt bodies or response bodies.

The following commands were then executed in order from
`10-workflow/workflow-assistance`:

```powershell
python scripts/workflow/sync_hermes_workflow_assets.py `
  --repo "D:\All projects\WORK-LAB\10-workflow\workflow-assistance" `
  --home "C:\Users\admin\AppData\Local\hermes" `
  --plan-json "D:\All projects\WORK-LAB\10-workflow\workflow-assistance\.hermes\task-artifacts\hermes-global-sync-plan-2026-08-11.json"

python scripts/workflow/sync_hermes_workflow_assets.py `
  --repo "D:\All projects\WORK-LAB\10-workflow\workflow-assistance" `
  --home "C:\Users\admin\AppData\Local\hermes" `
  --apply --approved
```

Deployment result:

- `PASS`: ActionPlan written to ignored project evidence at
  `.hermes/task-artifacts/hermes-global-sync-plan-2026-08-11.json`.
- `PASS`: atomic apply returned `ACTION_PLAN_READBACK_PASS`.
- `PASS`: independent SHA-256 readback matched all six managed binaries,
  `SOUL.md` and `.env.template`.
- `PASS`: both managed project helper scripts loaded from the live Hermes Home;
  the terminal guard failed closed when invoked without a valid JSON hook
  payload, as designed.
- `PASS`: no `.wa-stg-*` staging directories remained.
- Rollback backup preserved at
  `C:\Users\admin\AppData\Local\hermes\backups\workflow-assistance-sync-20260811-155201-538524`.
- Retention cleanup removed the prior stale backup
  `workflow-assistance-sync-20260728-173512-869604`; that old backup is not
  recoverable from this task.
- `config.yaml`, auth, sessions, credentials, tokens, logs and prompt/response
  bodies were excluded from the deployment.

## Codex user overlay — handoff task

This has not been applied. The dry-run write set is:

1. Managed block in `C:\Users\admin\.codex\AGENTS.md`.
2. `C:\Users\admin\.codex\rules\workflow-assistance.rules`.
3. Managed skill directories under `C:\Users\admin\.agents\skills`:
   - `workflow-assistance-evidence-verification`
   - `workflow-assistance-github-delivery`
   - `workflow-assistance-openhuman-integration`
   - `workflow-assistance-project-data-boundary`
   - `workflow-assistance-python-testing`
   - `workflow-assistance-self-improvement`
   - `workflow-assistance-windows-development`

The overlay must preserve existing Codex config/provider/auth/session fields.
It requires separate exact write authorization. After authorization:

```powershell
python 10-workflow/workflow-assistance/scripts/workflow/sync_codex_global_assets.py plan `
  --codex-home "C:\Users\admin\.codex" `
  --agent-home "C:\Users\admin\.agents"

python 10-workflow/workflow-assistance/scripts/workflow/sync_codex_global_assets.py apply `
  --codex-home "C:\Users\admin\.codex" `
  --agent-home "C:\Users\admin\.agents"

python 10-workflow/workflow-assistance/scripts/workflow/sync_codex_global_assets.py verify `
  --codex-home "C:\Users\admin\.codex" `
  --agent-home "C:\Users\admin\.agents"
```

Do not touch Codex auth stores, sessions, browser data, tokens, prompt/response
bodies or unrelated user skills.

## Native Observer packaging — handoff task

Source exists at `30-observer/work-lab-observer/src-tauri`; bundled windows now
start UNKNOWN and accept only a validated process-scoped loopback Observer API.
Native build is `NOT EXECUTED` because this machine exposes neither Rust/Cargo
nor MSVC Build Tools.

Before installing anything, report exact package versions, official sources,
system/project scope, disk impact and rollback. Do not modify PATH, PowerShell
profiles, registry or global environment without explicit approval. The Rust
contract is:

- Rust toolchain: `1.77.2`.
- Tauri: `2.11.3`.
- tauri-build: `2.6.3`.
- Build target/cache must remain under ignored project runtime state, for
  example `.hermes/task-runtime/cargo-target/`.

After approved prerequisites are available, run the native tests/build from
the owning module and report native compilation separately from Node contract
tests. Do not claim a portable EXE until the actual artifact is built and
read back.

## Git, CI and release — handoff task

No commit, push, PR, merge, release or publication is authorized by this
handoff. Before any of those actions:

1. Run `git diff --check`, `git diff --stat`, and `git status --short`.
2. Run the canonical Workflow gate and complete Observer suites.
3. Obtain explicit target remote/branch and commit/push authorization.
4. Stage only intended paths; never use `git add .`.
5. Record the staged tree and commit SHA.
6. Push without force and read back the remote SHA.
7. Treat CI as valid only when every required job passes for that exact SHA.

The root `test_exact_tree_review` is expected to remain red until a reviewed,
committed, clean tree exists. Do not weaken or skip it.

## DeepSeek execution instruction

Use DeepSeek only as the model executing this bounded task packet. Provider
selection, account credentials and model routing are user-owned Hermes state;
do not inspect, print, copy or rewrite them. Re-read root/module `AGENTS.md`,
preserve the current dirty worktree, keep runtime/evidence under project
`.hermes/`, execute one gate at a time, and finish with `PASS`, `PARTIAL`,
`NOT EXECUTED` or `BLOCKED` evidence for each layer.

## Recovery

- Hermes sync: use the synchronization script's generated backup/readback and
  its documented rollback boundary; do not manually remove unknown paths.
- Codex overlay: use `sync_codex_global_assets.py rollback` only after exact
  authorization and state inspection.
- Local runtime: stop only the exact PIDs recorded in project runtime
  descriptors.
- Git: do not use reset/clean/restore on this dirty checkout.
