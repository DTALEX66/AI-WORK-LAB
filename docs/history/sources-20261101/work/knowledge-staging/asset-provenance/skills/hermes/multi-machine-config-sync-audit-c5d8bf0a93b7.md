---
name: multi-machine-config-sync-audit
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/multi-machine-config-sync-audit/SKILL.md
---

---
name: multi-machine-config-sync-audit
description: "Use when verifying another machine's config/skills sync."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [config-sync, multi-machine, github, sso-timestamp, audit, evidence]
---

# Multi-machine config sync audit

Use when the user says something like "我在另一台电脑上更新了规则/配置/技能，本机都有了吗？" or asks whether cloud config matches local. The user expects **iron-clad evidence**, not "everything is synced". If the user replies "你确定吗？", that is a demand for a deeper, cross-verified audit — never restate the same single-point check.

## Core principle: separate the two sync channels

| Channel | What travels | How to verify |
|---|---|---|
| **Repo config** (rules, skills, workflow config in a git repo) | GitHub → any machine via fetch | git refs + GitHub API timestamps |
| **Machine-local config** (`~/.codex`, `$HERMES_HOME`, `~/.agents/skills` live copies) | only by explicit sync/apply on this machine | content hashes + mtime against the repo |

A repo being in sync does NOT mean machine-local live copies are; and machine-local edits on another PC never arrive by themselves. State which channel you are claiming.

## Audit sequence (iron-clad evidence, in order)

1. **Authoritative SSOT timestamp**: `gh api repos/<owner>/<repo> --jq .pushed_at`. This records the last push to ANY ref of the repo. Compare against your local HEAD's merge/commit time (`git log -1 --format='%ci %h %s'`). If pushed_at == your last known merge, there is nothing newer — this is proof, not an assumption.
2. **Fetch everything**: `git fetch origin '+refs/heads/*:refs/remotes/origin/*' --prune` (heads only, see pitfall 1), then compare `git rev-parse refs/remotes/origin/main` vs local `main`. Check `git log --oneline main..origin/main`.
3. **Other refs**: `gh pr list --state open` (no open PRs = no unmerged pushes), `git branch -r --no-merged main` (new branches), `git tag --sort=-creatordate | head`, `git remote -v` (a second remote means the user may have pushed to a different URL).
4. **Sibling repos**: `gh repo list <owner> --limit 40 --json name,updatedAt,defaultBranchRef` sorted by updatedAt — the "other machine's update" may live in a DIFFERENT repo (e.g. a renamed project repo) that the user loosely calls "the project". Check the most recently updated repos' commit lists before concluding "nothing new".
5. **Machine-local live copies**: for each managed artifact (rules file, each skill dir, guidance file, config fields) compare repo hash vs live hash — per-file tree-hash, plus mtime. Remember your own sync/apply writes timestamps too; a fresh mtime is often YOUR apply, not an external sync.
6. **If nothing exists upstream**: state the conclusion with the timestamps as evidence, then ask whether the other machine's push actually succeeded. Give the user the exact commands to run there: `git status -sb` (ahead of origin?), `git remote -v` (right URL?), `git push` (what error?). A failed/never-run push is the usual explanation when the user is certain they pushed but the SSOT timestamp shows nothing.

## Handing off: reload prompt for the other side

After verifying sync, when the user wants the OTHER project / second PC to actually reload the global config, send the self-contained prompt in [`templates/global-config-reload-prompt.md`](templates/global-config-reload-prompt.md) (verbatim; fill in the current main SHA). It covers Codex overlay verify/plan/apply + new-task requirement, Hermes runtime-read (no restart), boundary-guard check, and the PASS/PARTIAL/FAIL reporting contract. Related pitfalls are embedded: machine-level config repos (`OS External Configuration`) are NOT the WORK-LAB global layer; deployment-layer hook PASS ≠ execution-layer PASS.

## User-facing reporting

- Report per-channel: git refs (repo channel) vs live file hashes (local channel) vs timestamps.
- A single `sync verify PASS` or `git status clean` is NOT enough when the user asks "都有了吗" — show pushed_at, HEAD hash, per-skill hashes, and the open-PR/branch/tag sweep.
- Distinguish "repo synced" from "live deployed" from "other machine's push confirmed on GitHub".

## Pitfalls (each cost a false conclusion)

1. **`git fetch origin '+refs/*:refs/remotes/origin/*'` breaks `origin/main` resolution** — after a full-refs fetch, `git rev-parse origin/main` can fail with "unknown revision". Repair with the standard heads-only refspec: `git fetch origin '+refs/heads/*:refs/remotes/origin/*' --prune`, then re-verify `refs/remotes/origin/main`.
2. **Guessed marker names**: when checking a managed block's presence, grep the script's exact constants (e.g. `GUIDANCE_BEGIN` = `<!-- BEGIN WORKFLOW-ASSISTANCE MANAGED CODEX OVERLAY -->`), never a guessed substring like `WORK-LAB` — false "MISSING" sends you down a phantom repair path. Trust `plan`/`verify` reporting zero actions over your own grep.
3. **Regex with quote assumptions**: integer config values have no quotes (`project_doc_max_bytes = 65536`); a regex expecting `"..."` reports MISSING for valid ints. Match `= (\d+)$` or parse with tomllib.
4. **Docs claims vs live state**: sibling/parallel sessions may edit tracked docs to claim values that don't match live (a doc said `reasoning_effort=low` while live was `medium`). Trust the live measurement over any document claim; align docs to live, keep historical PR-description lines intact.
