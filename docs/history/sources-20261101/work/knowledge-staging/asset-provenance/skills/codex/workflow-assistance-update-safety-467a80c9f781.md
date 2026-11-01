---
name: workflow-assistance-update-safety
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-update-safety/SKILL.md
---

---
name: workflow-assistance-update-safety
description: "Use when checking agent/runtime updates, config drift, or overlay safety."
---

# Update & drift safety (WORK-LAB overlay)

Absorbs the proven safety model from agent-update-safety and
hermes-codex-config-drift into the Workflow Assistance overlay. Use whenever
a software update, config reset, overlay re-apply, or drift report needs a
fail-closed check before any repair.

## Scope: vendor update vs workflow overlay

- **Vendor update**: application/CLI code, bundled schemas, plugin APIs,
  Desktop state migrations (Hermes, Codex CLI/Desktop).
- **Workflow overlay update**: this module's own sync/deploy of
  `codex-assets/skills`, managed `config.toml` block, rules, launchers.

A guarantee for one never proves the other. Always state the distinction.

## Four-layer evidence model (never collapse)

1. **Existence** — expected rule/skill/config file is present.
2. **Source equivalence** — managed live artifact is byte-identical to the
   reviewed repo source (`sync ... verify` proves it in one command).
3. **Runtime enablement** — active CLI/profile actually lists the skill or
   capability as enabled.
4. **Behavioral application** — only claim after a live, low-risk check
   (e.g. cross-project rule-quote probe; harmless new-session marker).

Report each layer separately. A file existing alone is not "restored".

## Ownership map (diagnose before changing)

| Layer | Authority | Example |
|---|---|---|
| Vendor baseline | official install/bundled assets | schema defaults, migrations |
| User overlay | user-owned config | provider/model/auth, desktop state, sandbox |
| Enhancement overlay | this module's declared fields | managed block, `workflow-assistance-*` skills |
| Project rules | per-repo AGENTS.md | applies to that project only |

Never use a Hermes value to explain a Codex symptom. An enhancement module
manages only its declared fields (`config-ownership.json`,
`preserve_unknown: true`) and never overwrites user-owned state. Do not
recursively copy a vendor profile or make user directories read-only.

## Read-only audit sequence

1. Resolve live roots (`$HERMES_HOME` / active profile, `$HOME/.codex`).
2. Query safe metadata only: version, existence, size, mtime, hash,
   non-secret settings. Never read auth stores, tokens, session DBs.
3. Hermes: `hermes config check`/`doctor`; Codex: `codex --version` and
   non-secret `config.toml` fields (model, provider, sandbox, approval).
4. Overlay: run `sync_codex_global_assets.py verify` — managed-block hashes,
   managed fields, rules hash, skill inventory in one command; check overlay
   state version and `preserved_user_config_fields`.
5. Classify every difference: missing / user drift / vendor drift / schema
   incompatibility / unverified application.
6. Stop before repair. A drifted user-owned file needs explicit authority.

## Parallel-session race (active risk)

A sibling Hermes/Codex session can rewrite tracked config and merge
opposite-direction PRs while you work. The write tool warning
"modified by sibling subagent '<id>' ... after this agent's last read" is an
ACTIVE race signal: re-read before patching, re-grep your markers after the
write, and re-verify `git branch --show-current` + HEAD after every git op.

## Managed-block recovery

If `verify` reports `config_managed_block_missing_or_duplicate` (Codex
Desktop rewrote `~/.codex/config.toml`): do not hand-edit the file and do
not expect `rollback` to rescue it — re-establish through the sync script's
own legacy-migration path, then re-run `verify` until PASS.

## Integration with skill lifecycle

After any update, run `skill_lifecycle.py status` to confirm the managed set
is intact: `workflow-assistance-*` skills are repository-owned and must
never be auto-archived (provenance filter blocks it); fold new durable
lessons back into repo skills via PR — the repo is the cross-machine store,
never a machine-local sidecar.

## Pitfalls

- Treating an update as "safe" because the installer ran (no evidence of
  user state preservation).
- Collapsing "file exists" into "behaviorally applied".
- Explaining one client's symptom with another client's config.
- Repairing drift before classifying ownership.
- Forgetting to re-verify after a parallel session touched the checkout.

## Verification

- `sync ... verify` PASS with expected skill count.
- Four-layer claims stated separately in any update/drift report.
- No credential values printed; sensitive values `[REDACTED]` fail-closed.
