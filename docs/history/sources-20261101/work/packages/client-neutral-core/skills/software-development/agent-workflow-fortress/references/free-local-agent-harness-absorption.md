# Free, local, model-neutral agent-harness absorption

## Source and scope

Source studied: https://github.com/xai-org/grok-build

Absorb patterns only. Do not vendor the upstream runtime, install its binary, configure hosted inference, select a model, copy credentials, or add any paid network dependency. This reference is deliberately executor-neutral so Hermes remains the sole orchestrator and the workflow stays usable with local and free tools.

## Absorbed patterns

### Completion contract

A worker is not complete merely because it emitted prose. Every task declares a terminal completion signal and the evidence required before that signal is accepted. Missing evidence produces a bounded retry or an explicit blocked result; it never becomes a false success.

Required fields:

- completion signal name;
- maximum recovery attempts;
- required test or read-back evidence;
- final changed-path list;
- rollback information.

### Structured run state

Long-running work publishes a machine-readable state with:

- run ID and task ID;
- `pending`, `running`, `completed`, `failed`, `blocked`, or `cancelled` status;
- start/update/end timestamps;
- process handle when a real process exists;
- baseline and result commit/tree identity when Git is involved;
- verification command and exit code;
- output and log paths.

State transitions must be monotonic. Completion and cancellation use compare-and-swap or an equivalent single-owner rule so a late worker cannot overwrite a terminal state.

### Fail-closed safety

Safety checks that crash, time out, return malformed output, or cannot inspect a command must deny or block the action. A prompt, plan mode, or hook is not a security boundary. External isolation and explicit tool/path allowlists remain authoritative.

Negative controls must cover:

- chained shell commands where a safe prefix hides a write or destructive suffix;
- shell redirection during an allegedly read-only phase;
- write-capable child workers escaping a parent planning gate;
- unsupported OS sandbox claims;
- missing or timed-out policy hooks;
- hidden uploads, telemetry, credentials, or remote configuration.

### Single writer

One checkout has one writer. Read-only workers may share a frozen tree; write-capable workers use dedicated worktrees or clones. A child defaults to no write access and no shared-checkout execution unless its ticket explicitly grants both.

### Exact-tree evidence

Reviews, verification, and release decisions bind to an exact candidate tree. Record `git write-tree` after staging intended files. Any edit, rebase, generated-file change, rebuild that modifies tracked content, or amend invalidates the verdict and requires a new freeze and review.

## Excluded capabilities

Do not absorb:

- model catalogs, model identifiers, routing logic, or model-specific prompts;
- hosted inference endpoints, subscriptions, metered services, or paid APIs;
- upstream authentication, credential stores, telemetry, trace upload, session upload, or cloud storage;
- duplicate memory, MCP, skills, cron, session database, or TUI implementations already supplied by Hermes;
- upstream binaries, heavyweight source trees, installers, or auto-updaters.

## Adoption procedure

1. Copy the model-neutral ticket from `templates/task-tickets/model-neutral-agent-task.md`.
2. Declare read/write/execute/network scope before dispatch.
3. Use local or already-installed free tooling only; otherwise mark the task blocked.
4. Publish structured state for background work.
5. Require the declared completion signal and verification evidence.
6. Freeze and independently review the exact tree before any release action.
