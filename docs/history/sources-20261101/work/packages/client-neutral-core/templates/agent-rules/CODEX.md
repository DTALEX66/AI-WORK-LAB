# CODEX.md — Coding Agent Start Rules

## Start Here

1. Read `AGENTS.md` and project orientation docs.
2. Read `SECURITY.md` before touching scripts, network calls, credentials, or third-party prompts.
3. Read `DESIGN.md` before UI work.
4. Identify the project verification command from docs/package files.

## Change Rules

- Prefer small patches over rewrites.
- If two patches in the same region fail, re-read the file and rewrite the complete small function/file.
- Add or update tests when behavior changes.
- Keep Windows path/encoding issues in mind: UTF-8, LF in repo, no PowerShell-only assumptions unless documented.
- For commands that create temporary files, test environments, caches, logs or artifacts, first use `python "$HERMES_HOME/bin/hermes-project-data.py" --project . check`, then invoke `... run -- <command>`. The project `.hermes/` root must be Git-ignored; never use user-home, desktop, global Hermes or sibling-project paths for task output.

## Output Contract

Return:

- files changed
- commands run
- test/build result
- risks or follow-up work
- whether the working tree is clean
