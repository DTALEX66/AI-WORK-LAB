# Agent Rules

## Scope

- Work only inside the current repository unless the user explicitly directs otherwise.
- Read relevant files and project instructions before editing.
- Keep changes minimal, verify them with relevant tests, and report concrete results.

## Boundaries

- Do not read or print secrets: `.env`, `auth.json`, `*.pem`, SSH keys, browser cookies, credential stores.
- Do not delete or move user data unless explicitly instructed.
- Do not run destructive git commands (`reset --hard`, `clean -fd`) without explicit user approval.
- Keep generated artifacts out of git unless they are intentional deliverables.
- Keep task temporary files, caches, logs, test environments and generated review artifacts in the current Git project's ignored `.hermes/task-runtime/` or `.hermes/task-artifacts/`; never spill them into `%TEMP%`, the user home, desktop, Hermes Home, or another project.
- Hermes' terminal pre-tool hook rejects raw terminal commands. Every terminal call must declare the current Git project as `workdir` and invoke `python "$HERMES_HOME/bin/hermes-project-data.py" --project . <subcommand>`; shell chaining is prohibited.
- Before a command that can create runtime data, run `python "$HERMES_HOME/bin/hermes-project-data.py" --project . check`; run the command through `... run -- <command>` so standard temp/cache variables are project-local. Reject explicit output/cache/log paths outside the project root.
- `E:\` is a protected user-data zone: do not enumerate, read, copy, write, move, rename, or delete anything there unless the user explicitly authorizes the exact path and operation in the current request. Read permission never authorizes writes or deletion.
- After a successful task, preserve durable evidence in `.hermes/task-artifacts/`, then run `python "$HERMES_HOME/bin/hermes-project-data.py" --project . cleanup`. Failed tasks retain project-local evidence until reviewed.

## Quality Bar

A task is not done until the requested artifact exists and has been exercised by a real command or inspection.
