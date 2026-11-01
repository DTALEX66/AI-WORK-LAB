---
name: workflow-assistance-update-safety
description: "Use when auditing or deploying a declared agent configuration overlay."
---

# Overlay update safety

Separate vendor runtime updates from owned overlay updates. Resolve current native
interfaces and the project's field-ownership contract. Preserve provider, model,
reasoning, auth, unknown fields and unrelated user state.

For WORK-LAB Codex assets, use `integrations/executors/codex/sync_codex_global_assets.py`:
plan -> review target-bound digest -> apply within the task grant -> verify ->
idempotent plan. Back up the owned changed assets first. Use `--skills-only` when
the authorized scope is skills: it preserves global guidance, config and rules and
does not rebaseline their ownership hashes. This mode requires existing ownership.
Changed/unowned skill content remains a conflict; preserve it and resolve the exact
diff before repair. Restore a reviewed skill backup for skills-only recovery.

Distinguish file presence, source equivalence, runtime discovery and behavioral use.
Restart/new-chat discovery must be checked after deployment; the active conversation
may retain its old skill catalogue. Do not infer performance benefit from hashes.
Never copy a vendor executable into internal plugin bridges as a generic fix.
Use the official update interface for the detected install channel.

For explicit skill maintenance, inventory the declared skill roots, compare source
and live hashes, narrow triggers and move conditional material to references.
Missing usage telemetry means UNKNOWN usage, not unused. Archive before retirement;
never auto-delete repository-owned or user-modified skills on an age threshold.
