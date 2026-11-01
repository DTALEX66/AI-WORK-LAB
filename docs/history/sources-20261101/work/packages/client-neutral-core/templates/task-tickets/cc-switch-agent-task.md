# CC Switch / Coding Agent Task Ticket

## Task Name

<short task name>

## Mode

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
auth.json
.git/
node_modules/
.venv/
user data folders
```

## Source Docs to Read First

```text
README.md
AGENTS.md
SECURITY.md
DESIGN.md
<project-specific docs>
```

## Requirements

1. <requirement>
2. <requirement>
3. <requirement>

## Verification Commands

```bash
<exact commands>
```

## Run / Delivery Identity

```text
run_id
task_id
status: pending|running|completed|failed|blocked|cancelled
baseline_tree
result_tree
reviewed_tree
release_tree
remote_ref
required_workflows
release_commit
exact_sha_ci_urls
verification_exit_code
output_path
log_path
```

## Execution / Review Boundary

- Writer: `<Hermes / Codex / other>`; exactly one writer owns the checkout.
- Review backend: `<Hermes / Codex native review>`; review the exact frozen tree `<git write-tree>`.
- Codex review, when selected: first run `codex --version`, then `codex exec --help`, and only use
  flags confirmed by the current help output; require read-only sandbox, ephemeral execution and
  structured output before launching `codex exec`. Preserve user config, rules and plugin discovery;
  do not use `--ignore-user-config` or `--ignore-rules`. Use an exact-tree prompt and temporary JSON
  output schema; no sandbox or approval bypass is permitted. Any finding is fail-closed as NO-GO.
- Route evidence: record only listener/transport status; do not copy proxy URLs, subscriptions,
  OAuth files, tokens or route databases.
- No automatic commit, push, PR, merge, or CI trigger unless the ticket explicitly selects `publish`.
- Publish requires the exact staged tree, exact release tree, explicit remote ref, non-empty required
  workflow names, release commit SHA, branch containment, and exact-SHA CI run URLs.
- Missing evidence is `blocked` or `failed`, never `completed`.

## Output Contract

Return:

- files changed
- verification output
- risks
- rollback notes
- next recommended task
