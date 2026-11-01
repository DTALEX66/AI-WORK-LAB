# Execution reliability intake and two-lane delivery

Use this reference when a user supplies an execution-error summary and asks for both reusable Codex/WORK-LAB hardening and a project-specific TaskPack.

## Fast sequence

1. Inspect the original repository/runtime sources that are available. Conversation summaries are secondary evidence; do not invent truncated error rows, branch names, paths, or SHAs.
2. Classify each item before editing:
   - reusable, secret-free and cross-project → global guidance/rules/skills/scripts/tests;
   - project path, source, branch, log or test → project TaskPack only;
   - user/provider/auth/session/private memory → preserved or forbidden, never adopted;
   - Windows/provider/model runtime → measured external condition, not automatically a repository bug.
3. As soon as the project facts are sufficient, write the transferable TaskPack under ignored `.hermes/task-artifacts/` and give its path to the user. Continue the global implementation afterward; do not hold the requested artifact behind a full quality gate.
4. For global changes, update the ownership contract before or with the implementation. Add RED→GREEN tests for executable behavior, then update guidance and class-level skills.
5. Run targeted regression first, then one canonical gate after the final edit. Report local source integration, live user-overlay sync, commit, push, CI and merge separately.

## Reusable reliability rules

- A denied read of `$CODEX_HOME/memories/**`, auth or session state is a correct boundary signal. Use tracked truth or a user-provided redacted summary; do not elevate.
- PowerShell cleanup is not proven by exit code alone. Use an exact contained path, `-LiteralPath`, terminating error semantics, and a filesystem postcondition. Diagnose lock/ACL/attribute/reparse state before retrying; never broaden the delete.
- A preflight report should separate current branch, upstream, explicit main, divergence, exact Python interpreter/modules, and Markdown links resolved from each document's directory.
- Squash merge creates a new main SHA. Prove merge with PR state + merge commit + main containment + exact-SHA CI, not PR-head ancestry alone.
- Keep `PLANNED`, `BRANCH_PUBLISHED`, `IMPLEMENTED_LOCAL`, `TESTED_LOCAL`, `CI_VERIFIED_EXACT_SHA`, `MERGED_MAIN`, and `INSTALLED_RUNTIME_VERIFIED` independent.
- Strip ANSI control bytes before parsing terminal evidence; do not diagnose them as repository encoding damage.
- Performance claims need matched timed samples. Timeout values, trust, sandbox names, approval modes and WebSocket capability fields are not latency measurements. Prefer a persistent writer, batched independent reads, targeted development checks and one final full gate.

## TaskPack minimum shape

- exact target repository and one-writer/worktree rule;
- forbidden private and cross-project surfaces;
- direct-source baseline refs/SHAs and status;
- exact allowed write set;
- one work item per project issue with reproduction, evidence state, acceptance, stop condition and rollback;
- lifecycle-separated final report;
- no commit/push/PR/merge unless that side effect was explicitly authorized.

## Communication rule

For evidence-driven users, lead with the artifact or completed phase. Avoid narrating every search, skill load and intermediate check. Send a progress message only for a real blocker or a meaningful phase boundary.
