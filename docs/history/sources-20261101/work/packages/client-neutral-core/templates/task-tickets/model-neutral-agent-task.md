# Model-Neutral Local Agent Task Ticket

## Task Name

<short task name>

## Mode

- [ ] inspect
- [ ] plan
- [ ] implement
- [ ] verify
- [ ] review

## Allowed Paths

```text
<project-relative paths>
```

## Forbidden Paths

```text
.env
**/.env
**/auth.json
.git/
credentials/
user data folders
```

## Completion Contract

- Completion signal: `<exact signal or tool result>`
- Maximum recovery attempts: `<integer>`
- Required artifacts: `<paths or none>`
- A prose-only answer is not completion.
- Missing evidence ends as `blocked` or `failed`, never `completed`.

## Run State Contract

Publish these fields for background work:

```text
run_id
task_id
status: pending|running|completed|failed|blocked|cancelled
started_at
updated_at
finished_at
process_handle
baseline_tree
result_tree
reviewed_tree
release_tree
remote_ref
required_workflows
release_commit
exact_sha_ci_urls
verification_command
verification_exit_code
output_path
log_path
```

Terminal states are monotonic. A late process must not overwrite `failed`, `blocked`, or `cancelled` with `completed`.

## Isolation and Permissions

- Read access: `<paths>`
- Write access: `<paths or none>`
- Execute access: `<commands or none>`
- Network access: `disabled` unless a free, explicitly approved source is required
- One checkout has one writer.
- Write-capable work uses a dedicated worktree or clone.
- Declaring `plan` or `review` does not enforce read-only behavior.
- Enforcement mechanism: `<external sandbox/container/VM plus path and tool policy>`
- Tool deny list: `<edit, shell, redirection, child-worker and other denied capabilities>`
- Sandbox support verified: `<OS, command, result, or no>`
- Negative-control command/result: `<prove shell writes, chained commands and child writes are denied>`
- If enforcement or a negative control is unavailable, the task is `blocked`; do not claim read-only execution.
- Policy checks fail closed on errors, timeouts, malformed output, or uninspectable input.

## Source Docs to Read First

```text
README.md
AGENTS.md
SECURITY.md
<project-specific docs>
```

## Requirements

1. <required behavior>
2. <required behavior>
3. <required behavior>

## Verification Evidence

```text
<exact commands>
<required read-back or artifact checks>
```

Record:

- focused RED/GREEN evidence when behavior changes;
- full relevant gate output;
- changed paths;
- exact staged tree from `git write-tree` when release review is required;
- exact release tree from `git rev-parse HEAD^{tree}` and proof it equals the reviewed tree;
- remote ref, required workflow names, release commit SHA and exact-SHA CI run URLs when published;
- rollback procedure.

## Cost and Network Boundary

- Use only local, open-source, or genuinely free tooling already available in the environment.
- Do not add model selection, hosted inference, subscriptions, metered APIs, credentials, telemetry, trace uploads, or cloud storage.
- If the task cannot run within this boundary, return `blocked` with the exact missing prerequisite.

## Output Contract

Return:

- final status;
- completion signal;
- files changed;
- verification command and real exit code;
- baseline/result tree identity when applicable;
- risks and rollback notes;
- output/log paths for background work.
