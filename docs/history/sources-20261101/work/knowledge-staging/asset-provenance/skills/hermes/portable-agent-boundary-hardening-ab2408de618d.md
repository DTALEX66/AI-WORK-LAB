---
name: portable-agent-boundary-hardening
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/portable-agent-boundary-hardening/SKILL.md
---

---
name: portable-agent-boundary-hardening
description: Use when portable agent boundaries fail.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [portable-workflow, project-boundary, subprocess-containment, exact-tree, exact-sha, fail-closed]
    related_skills: [agent-workflow-fortress, project-data-boundary, test-driven-development, github-pr-workflow]
---

# Portable Agent Boundary Hardening

## When to use

Use this class-level skill when a portable Hermes/Codex/CC Switch/GitHub workflow must keep project-owned data inside its owning project, prevent reviewer or wrapper bypasses, prove source/live deployment parity, or close a real release with exact-tree and exact-SHA evidence.

This skill complements `agent-workflow-fortress` and `project-data-boundary`; it does not replace their general orchestration or ownership rules. It is specifically for implementing and proving fail-closed boundaries across subprocesses and deployment entry points.

## Non-negotiable delivery contract

A request such as “全部修复” means continue through the next real RED→GREEN slice, not merely return an audit or partial patch. Do not claim completion until the latest tree has passed targeted tests, the canonical local quality gate, commit/push, and the required exact-SHA CI workflows. If execution is interrupted, preserve the active task list and report the result as incomplete.

Never read, print, stage, or persist credentials, private provider configuration, OAuth stores, cookies, `.env` values, credential files, or connection strings. Never access a protected drive or unrelated project merely to locate a suspected artifact. Determine data ownership before choosing a path; filename or prompt text is not ownership evidence.

## RED→GREEN workflow

1. Inspect live Git status, branch, remote, manifests, relevant source, and existing tests.
2. Write one behavior-level negative control before production code.
3. Run that test and confirm it fails for the intended reason, not because of a test typo.
4. Implement the smallest boundary change.
5. Re-run the targeted test, then the neighboring test module.
6. Refactor only after GREEN; preserve the negative control.
7. At the end of a coherent batch, run the canonical quality gate and inspect generated paths.

For containment work, source-string assertions are supplemental only. Prefer a real subprocess fixture that writes through `tempfile`, observes `TMP/TEMP/TMPDIR` and cache variables, and records actual output paths.

## Project execution context

Every write-capable controlled subprocess should receive a project-owned environment derived from a canonical Git root. At minimum provide project paths for:

- `TMP`, `TEMP`, `TMPDIR`
- Python bytecode/cache
- pip/uv/npm/yarn/Playwright/Rust/tool caches as applicable
- project runtime, logs, and artifacts
- the project Kanban root

Use `cwd` plus environment injection; `cwd` alone does not contain Python tempfile, Node caches, Hermes state, or tool-specific caches. Reject a non-Git root and reject output/cache/log parameters resolving outside the owning project. Keep workflow-platform data in its workflow-owned directory rather than migrating it into a business project.

## Negative controls that must exist

Add regression coverage for:

- non-empty portable deployment home, including an unchanged sentinel;
- fake wrapper text such as `echo wrapper --project .`;
- `python fake.py wrapper --project .`;
- direct subprocess execution without the project context;
- two project roots and cross-project output;
- no-Git directories;
- symlink/junction escape;
- protected-drive paths;
- a fake Hermes/Codex child that uses `tempfile` and cache variables;
- reviewer modification or external-state writes;
- source/live/profile drift and unresolved related-skill references.

## Wrapper and reviewer rules

A terminal guard must parse structured argv and validate the actual executable/canonical wrapper path, not merely search a command string for a wrapper name. Reject shell chaining and ambiguous layouts. A reviewer must be independently read-only and ephemeral: use a read-only sandbox/clone/worktree and freeze the exact staged tree before review. A prompt saying “do not edit” is not an enforcement boundary.

Portable verifiers must reject non-empty explicit homes before any write and must exercise the same public deployment orchestration as the real installer. Do not test leaf copy helpers while production uses a different orchestration path.

**Reload semantics differ by layer.** A `pre_tool_call` shell-hook *script* (e.g. `hermes-project-terminal-guard.py`) is spawned fresh by `shell_hooks._spawn` on every matching tool call, so editing the script takes effect on the next call — no restart, no manual reload (verify by firing the target command immediately after editing). By contrast, the code that *registers* the hook (e.g. a `register_from_config()` call added to `web_server.start_server()`) only runs at process startup, so THAT change needs a backend restart to take effect. When a guard edit "doesn't seem to work", first distinguish which layer you touched before restarting anything.

## Raw command parser edge cases

For terminal guards that inspect a command before wrapper execution, test the raw command string before shell tokenization. `shlex.split(posix=True)` can strip Windows UNC backslashes, so checking only parsed argv is insufficient. Cover Windows drive paths, UNC paths, POSIX paths, and embedded forms such as `--output=/tmp/x`, `--output:/tmp/x`, `open(/tmp/x)`, `--output=C:/x`, and `--output=\\server\\share\\x`; also reject shell redirection/chaining. Treat any raw double-backslash UNC prefix as hostile before tokenization, including when embedded inside a function-like child expression. On POSIX, treat foreign Windows absolute paths as external; on Windows, compare normalized drive/UNC paths to the canonical Git root. Re-run these negative controls after every review finding and after every tree supersession.

Two concrete bypasses validated 2026-08-14 (fixed in `hermes-project-terminal-guard.py`):

1. **Parent-traversal lookbehind misses mid-path `../`.** A regex like `(?<=[\s"'=<>:([{])\.[\\/]` only fires when the `..` is preceded by whitespace/quote/bracket, so `cat scripts/../../secret.txt`, `./../x`, and a bare `ls ..` / `cat ..` (no trailing slash) all slip through and escape the project. Detect traversal with NO lookbehind — `\.\.(?:[\\/]|(?=[\s"']|$))` — so `../`, `..\`, and a standalone `..` (followed by whitespace/quote/EOL) are caught at any position. A bare `..` followed by a letter is a legit filename fragment (`git log A..B`, `foo..bar`) and must NOT be blocked.

2. **Space-containing absolute paths are false-blocked by `[^\s"']+` truncation.** A drive-path regex ending in `[^\s"']+` stops at the first space, turning `"D:/All projects/WORK-LAB/x.py"` into `D:/All` (and `/All` via a POSIX-path regex), which is then misclassified as outside the project. Fix: when the truncated candidate is a *character prefix* of the canonical root, skip the raw-regex check and let `shlex`'s full token decide via `Path.resolve().is_relative_to(root)`. Critically, use `str.startswith` (character-level), NOT `Path.is_relative_to` — the latter compares path *segments*, so `D:/All` (segment `All`) is not a parent of `D:/All projects` (segment `All projects`) and returns False when you need True.


Bind release evidence to the exact candidate:

- staged tree ID before review;
- frozen/reviewed tree ID;
- release commit SHA;
- remote ref and remote SHA;
- required workflow names, run IDs, attempts, URLs, `headSha`, status, and conclusion;
- branch containment proof;
- clean worktree after push.

Any edit, rebase, amend, rebuild, or regenerated artifact invalidates the previous review and requires a new frozen-tree review.

## Skill/profile provenance

For portable skill packs, maintain a manifest with source path, live path, SHA-256, version, trust, enabled state, permissions, and profile scope. Validate frontmatter names, metadata, related-skill closure, unknown references, and source/live/profile hash parity. When the same text is checked on Windows and Linux, canonicalize text line endings (`CRLF`/`LF`) before SHA-256; raw-byte hashes create false drift. Keep session-specific audit counts and file evidence in `references/`, not in the core skill.

## Security-safe GitHub workflow

Prefer `gh auth status`, `gh api`, and the official interactive login/setup flow. Never extract tokens from `.env`, credential files, remotes, or shell history; never embed them in remote URLs or command arguments. Stage explicit intended paths only; never use `git add .` in a delivery recipe. Pin CI actions to commit SHAs and dependencies to verified versions/hashes where available.

## Verification checklist

- [ ] Ownership classified before path selection
- [ ] Project execution environment injected into every controlled writer/reviewer/quality-gate subprocess
- [ ] Real subprocess and negative-control tests exist and were observed RED
- [ ] Portable verifier rejects non-empty homes without writing
- [ ] Public deployment orchestration is exercised
- [ ] Reviewer is read-only, ephemeral, and bound to frozen exact tree
- [ ] Source/live/profile provenance is checked
- [ ] GitHub recipes do not read or extract credentials
- [ ] Local quality gate passes on the latest tree
- [ ] Exact-SHA Linux/Windows CI passes after the final push

See `references/audit-negative-controls.md` for the reusable boundary test matrix and evidence fields.
