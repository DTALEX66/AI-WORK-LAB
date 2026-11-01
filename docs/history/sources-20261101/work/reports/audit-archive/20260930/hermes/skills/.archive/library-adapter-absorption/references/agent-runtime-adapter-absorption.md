# Absorbing an agent runtime (not a data-conversion lib) into an adapter contract

Use this when absorbing an **agent runtime / external executor** (e.g. DeepSeek
Harness, or any future CLI/Web UI agent workbench) into a project's existing
adapter contract — a different class from `library-adapter-absorption`, which
covers data-conversion libraries (OCR/ASR/PDF) behind an `AdapterCapability`
framework. An agent runtime has no config `apply` authority and no content
conversion; it executes bounded tasks in an isolated worktree.

## 1. Read-only discovery FIRST (fail-closed pre-flight)

Before writing any delivery file, run only read-only checks and record a
PLAN_ONLY report. The taskpack's pre-flight list is the contract:

- **writer lease**: confirm no active writer (e.g. no `ledger.json` / no live
  task instance). You are the single writer or you stop.
- **upstream immutable pin**: `git ls-remote <repo> refs/heads/master` for the
  full commit SHA; also read the upstream `package.json` (raw.githubusercontent
  at that SHA) for `engines`, `packageManager`, `license`, `version`. Never float
  `master` — record the SHA as `UPSTREAM_PIN`.
- **toolchain**: detect `node`/`corepack`/`pnpm`/`git` versions WITHOUT installing.
- **target runtime dir**: confirm `.hermes/task-runtime/<name>/` does not exist
  (clean), and `.gitignore` excludes `.hermes/`.
- **secrets**: do not read any `.env`/key/auth store; key entry is deferred to
  the user in the runtime's own UI.

Emit a discovery report and STOP if any check fails (BLOCKED) — produce only a
diagnostic + rollback plan, no writes.

## 2. Path-mapping PLAN_ONLY when the taskpack's assumed layout is wrong

A taskpack/spec often assumes a delivery path that does not exist in the real
repo (e.g. `config/runtime-adapters/` when the repo actually uses a flat
`config/adapter-registry.json` + `scripts/workflow/*_adapter.py`). Do NOT guess
and write anyway. Produce a PLAN_ONLY mapping table (assumed → actual → action)
and WAIT for review. The real repo's existing registry/schema/test layout wins
over the taskpack's assumed layout.

## 3. Strict registry schema: new `kind` fields go in a SEPARATE schema

If the adapter registry schema is `additionalProperties: false` (common for
provenance registries), you cannot add a new `kind: agent_runtime` field or
`install_mode`/`network`/`workspace_scope` onto the registry entry — validation
rejects extra properties. Do NOT weaken the registry schema. Instead:

- Registry entry carries only the base fields the existing schema allows
  (`id`, `display_name`, `support_level`, `operations`, `detection`, `provenance`).
  A runtime gets `support_level: experimental`, `operations: [detect, capabilities,
  observe]` (no apply/invoke), `status: quarantined`.
- The runtime-specific contract (kind / install_mode / network / workspace_scope /
  secrets / execution_authority / external_mutation / plugin_policy /
  upgrade_policy / rollback) lives in a **separate** `agent-runtime-adapter.schema.json`
  plus the adapter module's constants + `contract()` method.
- Add a test that validates `adapter.contract()` against that separate schema
  with `jsonschema`, so the schema is actually exercised, not dead.

## 4. Runtime contract invariants to encode (fail-closed)

- `network: loopback_only` — validate host ∈ {127.0.0.1, localhost, ::1} ONLY.
  Reject public AND private/LAN addresses (a first cut that accepts RFC1918
  private IPs as "safe" is wrong — loopback_only means loopback, not "not-public").
- `workspace_scope: task_scoped_git_worktree_only` — workspace must be a real
  `.git` worktree under the project, never the project root, never the user home,
  never a drive root.
- `secrets: runtime_secret_only` — receipt/config-dump validation rejects any
  field whose key contains api_key/secret/token/password/credential/prompt/
  response/session_id.
- `execution_authority: execute_only_no_task_completion_authority` — the runtime
  can execute, but never marks a Task Ledger task complete.
- `apply` default `UNSUPPORTED` (even with an approved flag it returns BLOCKED —
  install is a separate approval-gated phase).

## 5. Rejection-path tests (the acceptance bar)

Test each fail-closed branch, not just the happy path: public/private host
rejected; commit drift vs pin rejected; workspace scope escape rejected; secret
field in receipt/config-dump rejected; apply-without-approval returns UNSUPPORTED;
capabilities do NOT expose apply/invoke. Assert the contract field set and
schema-validate it.

## 6. Windows toolchain detection: `.cmd` shims don't spawn directly

Node/npm/npx/corepack on a Windows machine are `.cmd` shims. `subprocess.run(
["npx", ...])` raises `FileNotFoundError` (WinError 2) — the shim is not a
directly-spawnable executable. `node --version` succeeds while `npx --version`
"fails" only because of this. Detect presence with `shutil.which(...)`
(`npx` → `npx.CMD`) and invoke shims via `cmd.exe /c` (or PowerShell), never a
bare spawn. A missing package manager (e.g. `pnpm`) is a separate, real absence.

## 7. Approval checklist for the install/run phases

List every external/paid action as a separate approval item and do NOT start it
implicitly: package-manager acquisition (prefer per-invocation `corepack
pnpm@X` so the global toolchain is NOT mutated — `corepack enable` writes a shim
into the toolchain dir and needs explicit approval), clone+checkout of the pin,
frozen-lockfile install, typecheck/build, profile init + config dump (redacted),
loopback server start, user key entry (agent never reads/displays), and any
paid-provider smoke call (default `LOCAL_SMOKE_ONLY`).

## Evidence of the pattern

`WL-DSH-001` (DeepSeek Harness) followed this: WL-DSH-010 read-only discovery
(pinned `deepseek-ai/deepseek-harness@47f94385…`, `pnpm@11.7.0`, `node ^22.19`),
WL-DSH-020 contract + rejection tests (10/10) with a separate
`agent-runtime-adapter.schema.json`, registry entry added without weakening the
registry schema, and install/run left as a gated checklist.
