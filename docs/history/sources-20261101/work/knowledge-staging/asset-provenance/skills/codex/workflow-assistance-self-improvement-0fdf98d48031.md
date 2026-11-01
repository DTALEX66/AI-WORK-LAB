---
name: workflow-assistance-self-improvement
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-self-improvement/SKILL.md
---

---
name: workflow-assistance-self-improvement
description: "Use when maintaining or growing the skill collection."
---

# Self-improvement (skill lifecycle)

## What this is

A client-neutral skill lifecycle: skills are usage-tracked, reviewed, and
archived-with-recovery instead of accumulating forever or being deleted. It
mirrors the auto-growth pattern personal agents use (usage sidecar,
active/stale/archived states, pin opt-out, archive-not-delete, backup before
transitions, provenance filter) without depending on any agent runtime.

## When to use

- A skill has not been used in a long time and the collection is growing.
- You created a skill during work and want it to persist across machines.
- You are reviewing which skills to keep, archive, pin, or fold into the module.

## Managed set (provenance filter)

Only skills with `created_by: agent` in SKILL.md frontmatter are managed.
Repository-owned, bundled, and manually authored skills are off-limits. The
module's own `workflow-assistance-*` skills are repository-owned: they are
never auto-archived.

## Lifecycle

- `active` → `stale`: no activity for `stale_after_days` (30);
- `stale` → `archived`: no activity for `archive_after_days` (90); moved to
  `.archive/` (recoverable) after a backup to `.backups/`;
- `pinned`: opt-out from all auto-transitions;
- archive is never delete.

## Running it (deterministic part)

```bash
python scripts/workflow/skill_lifecycle.py --root <skills-root> status
python scripts/workflow/skill_lifecycle.py --root <root> record <name> use
python scripts/workflow/skill_lifecycle.py --root <root> run --dry-run
python scripts/workflow/skill_lifecycle.py --root <root> archive <name>
python scripts/workflow/skill_lifecycle.py --root <root> restore <name>
python scripts/workflow/skill_lifecycle.py --root <root> pin <name>
python scripts/workflow/skill_lifecycle.py --root <root> backup <name>
```

## Review procedure (the judgment step)

1. Every cycle (e.g. weekly), list candidates from `status`: stale / archived.
2. For each candidate decide: **patch** (fold in new lessons), **pin**
   (still load-bearing), **consolidate** (merge into an umbrella skill), or
   leave archived (recoverable).
3. Patch with the module's skill-authoring standards: `description` ≤ 60
   chars, modern section order, scripts under `scripts/`, tests under
   `tests/`.
4. Fold durable lessons back into repository-owned module skills so they
   survive machine changes — the repo is the cross-machine persistent store.

## Cross-machine persistence

- The module repo carries the skills and this lifecycle tool; `sync` deploys
  them to any machine.
- Auto-grown knowledge persists by promoting it into the module's
  `codex-assets` skills (via PR) — never only in a machine-local sidecar.

## User environment preservation

Beyond skills, preserve the user's Hermes/Codex configuration and skill lists
in neutral, secret-free form so a machine change does not start from zero:

- Export: `python scripts/workflow/user_profile_export.py` — read-only against
  user homes; writes `config/user-environment-profile.json` (tracked) with
  non-secret config values, `.env` key names only, and skill inventories
  (Hermes skills, Codex `~/.agents/skills`).
- Redaction is fail-closed: any value matching a secret pattern is
  `[REDACTED]`; an unredacted value makes the export refuse to write.
- Restore: see `docs/workflow/user-environment-profile.md` — `sync` deploys
  the module skills; the profile tells you which config keys exist and which
  secrets must be re-entered on the new machine.
- The profile is a snapshot: re-run the exporter after meaningful config or
  skill changes and commit the refresh.

## Config-contract vs live-machine comparison ("载入项目定位/本机配置/要不要覆盖")

When the user asks to compare project positioning / ownership contracts against
the live machine and decide whether an overlay is needed ("看看有什么区别，需不需要配置覆盖"),
do a FIELD-LEVEL comparison, never a whole-file diff or a "looks fine" judgement:

1. Load the ownership contract (`config/config-ownership.json` — layers + 50
   fields with MANAGE/OBSERVE/IGNORE/FORBIDDEN + `preserve_unknown` rules) and
   the enhancement boundary (`config/codex-enhancement-boundary.json`), plus
   `00-governance/PROJECT_POSITIONING.md` for two-tier module claims.
2. Walk the LIVE configs field-by-field (tomllib for `config.toml`, PyYAML for
   `config.yaml`) and **redact every value whose path contains
   key/token/secret/password/auth/credential/api** — print field names and
   non-sensitive values only.
3. Classify each live field against the contract:
   - contract `MANAGE` field + live value within contract default → ✅ 一致,
     nothing to do;
   - contract `OBSERVE` field (e.g. `codex.model.*`, `mcp_servers.*`,
     `plugins`, `hooks.*`, `memory`) + live user value → ✅ 保留用户值 (this is
     `preserve_unknown` working, NOT drift);
   - contract `SECRET` / `FORBIDDEN` → ✅ 未触碰 (never read, never print);
   - managed assets (rules file, AGENTS.md managed block, skill roots) → diff
     against repo source (`md5sum`/`diff`), report MATCH vs DIFFER.
4. **Handoff docs are claims, not truth — verify against the live machine.**
   If a handoff/summary doc says `reasoning_effort=medium` but live config is
   `low`, the DOC is wrong and the LIVE value wins. Also check whether the
   field is even in the managed list: a non-managed field (like
   `reasoning_effort`) must NOT be force-overwritten to match a doc's claim —
   that would violate `preserve_unknown`. The fix is correcting the doc, not
   the config. (User's standing rule: 交接摘要不能用文档冒充.)
5. Verdict template: list every contract MANAGE field vs live value (table),
   list the OBSERVE-preserved fields, state "不需要配置覆盖" only when all
   managed fields match and preserve_unknown is respected, and separate
   "documentation claim is wrong" (fix doc) from "config drift" (fix config).

### Desktop update / re-login triage

When a Codex Desktop update is followed by re-login, appearance changes,
missing projects, permission fallback, or config drift, do not call it one
"reset". Separate authentication cache, Desktop UI/global state, project
index, per-thread permissions, user `config.toml`, AppX package state, and
provider routing. Compare machines in separate columns and collect the same
read-only evidence before repair.

- A GitHub issue in `openai/codex` is a public report, not maintainer
  confirmation. Check author association, maintainer comments, assignee,
  milestone, linked fix, and release note.
- Never read credential bodies or private session/state contents. Metadata and
  allowlisted non-secret fields are enough for first-pass triage.
- Run overlay `plan` and `verify` while Desktop is fully closed, then repeat
  `verify` after restart. Apply only when owned fields or roots drift.
- Repair and Reset are different risk levels. Reset, uninstall, deleting
  `.codex`, whole-file restore, and permanent route changes require explicit
  scope and loss acknowledgement.
- Store/MSIX delivery and the app's later state write are separate causal
  events. Timing alone does not establish which writer changed a file.

### Multi-software baseline audit ("官方标准+用户配置 你检查下所有软件")

When the user says to check whether a tool (or ALL workflow tools: Hermes /
Codex / CC Switch / OpenHuman / Open Design) complies with "官方标准+用户配置",
do not run ONE verifier and generalize — run the same 5-dimension baseline
per tool and report a table:

1. **Contract introspection ≠ live compliance.** `verify_config_ownership.py`
   prints `CONFIG_OWNERSHIP_PASS layers=8 modes=4 fields=50 forbidden=5` — that
   validates the CONTRACT FILE itself, proving nothing about the machine.
   The authoritative live check is `sync_codex_global_assets.py plan`
   (`write_set_count=0` + `preserved_user_config_fields` == managed fields)
   plus a field-level walk of each client's live config.
2. **Per-tool 5-dimension table** (baseline §6 of managed-software-and-assets.md):
   - 入口唯一: count desktop `.lnk` per tool (`ls Desktop | grep -i <tool>`);
     1 = pass, 2+ = violation.
   - 桌面可达: `Test-Path` the `.lnk` TargetPath chain.
   - 官方标准+用户配置: contract MANAGE fields vs live values; OBSERVE fields
     with user values = preserve_unknown working, NOT drift.
   - 无阻塞: skills size/count vs the repo's current source (docs may be stale —
     e.g. doc says "11 skills" while repo actually has 12 after an absorption PR;
     verify against `sync ... verify` output, not the doc).
   - 模型满血: reasoning_effort / provider routing — live value wins over doc.
3. **Not-installed tools are "不适用", not violations.** If OpenHuman has no
   install dir / no desktop entry / no process, record it as not-applicable
   (skill-only observation source), not as a baseline failure.
4. **Doc drift is a finding.** When the baseline doc table claims
   `reasoning_effort=medium` or "11 skills" but the live machine differs,
   list it as "documentation claim wrong" (fix the doc in a PR), separate from
   genuine config drift (fix the config).

## Pitfalls

- Archiving a repository-owned skill (the provenance filter blocks it —
  `created_by: agent` only).
- Deleting instead of archiving (archiving keeps recovery).
- Trusting a machine-local sidecar as durable storage (promote to the repo).
- Skipping the backup step before a transition.

## Verification

- `status` shows the expected state/pinned flags and the managed/repo-owned
  split.
- `run --dry-run` reports what would transition without moving anything.
- An archived skill restores byte-identical via `restore`.
