---
name: agent-update-safety
description: "Use when checking Hermes/Codex upgrades and rule safety."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [hermes, codex, updates, configuration, skills, safety, audit]
---

# Agent Update Safety

Use this skill when a user asks whether an **official Hermes, Codex CLI, or Codex Desktop software update** can affect their configuration, skills, plugins, global instructions, or execution boundaries.

## Scope correction: vendor update vs workflow overlay

Treat “软件更新 / software update” as an update of the vendor application or CLI unless the user explicitly says they mean a repository installer, workflow overlay, setup script, or sync command.

Do **not** answer a vendor-update question with claims about a project deployment script. First state the distinction:

- **Vendor update:** application/CLI code, bundled capabilities, schemas, plugin APIs, Desktop state migrations.
- **Workflow overlay update:** a separately invoked repository deployment/sync operation.

A safety guarantee for one does not prove a guarantee for the other.

## Evidence model

Report each layer separately; never collapse these into “everything is restored”:

1. **Artifact existence** — the expected global rule, skill, plugin, or config file is present.
2. **Source equivalence** — a managed live artifact is byte/tree-identical to its reviewed authoritative source.
3. **Runtime enablement** — the active profile/CLI actually lists the skill or capability as enabled.
4. **Behavioral application** — only claim this after an appropriate live, low-risk execution check. A file existing alone does not prove a client loaded it.

If a user-owned global guidance file has no authoritative source snapshot, report it as **present but not historically comparable**. Never overwrite it merely to make hashes match.

## Read-only audit sequence

1. Read product documentation and use live `--help` / `--version` rather than assuming update behavior.
2. Resolve the active Hermes home/profile from the live CLI or `HERMES_HOME`; do not hardcode a profile path.
3. Record only safe metadata for config and global-instruction files: existence, path, size, modification time, and SHA-256. Do not print `.env`, auth stores, tokens, session databases, or provider settings.
4. For Hermes, inspect the active profile, `SOUL.md` if present, installed skills, and enabled/disabled status. Compare only declared managed skill roots to a reviewed source.
5. For Codex, inspect the existence/metadata of the global `AGENTS.md` and `config.toml`; do not read credentials or infer that a user-owned rule matches a repository template without an explicit authority mapping.
6. Classify every difference as one of: missing, user/custom drift, official/bundled drift, schema incompatibility, or unverified runtime application.
7. Stop before repair. A drifted user-owned file requires an explicit authority decision; a vendor update must never be “fixed” by recursively copying a whole profile or by setting user directories read-only.

## Safe conclusions

Use precise language:

- “Normally preserved” means program installation and user-data locations are distinct; it is not a universal promise that a future version cannot change semantics.
- An update may alter config-schema compatibility, bundled skills/plugins, plugin APIs, Desktop layout/state migrations, or rule-loading behavior without deleting a user config file.
- State what was verified on this machine, what was verified only from documentation, and what remains unverified.

## Evidence levels and extrapolation limits

Archive and audit conclusions must carry an evidence level; a single-machine
observation is never extrapolated to other machines, versions, or channels:

1. **Official issue ≠ official confirmation.** A GitHub issue (e.g. openai/codex
   #37927) is a report, not a vendor statement. Before citing it as root cause,
   verify author association, maintainer comments, assignee, milestone, fix PR,
   and release note. Unverified → label "community report, unconfirmed".
2. **Per-machine columns.** A successful readback on machine A proves nothing
   about machine B. Split evidence per machine/check surface (package/process/
   login/appearance/sandbox/config/overlay); never reuse A's results as B's truth.
3. **Handoff is a claim, not truth.** Re-read live state and the authority
   contract before correcting docs; an OBSERVE field differing from a doc is
   not necessarily drift.
4. **Update ≠ state write.** Package replacement (MSIX/Store update) and the
   app's own post-launch state writes are separate attribution classes; do not
   merge them into one "reset".
5. **Repair vs Reset.** Repair is lower-risk; Reset/uninstall/state deletion is
   destructive and needs separate authorization. Field-level recovery beats
   whole-file restore (preserve provider/model/network/unknown user fields).
6. **Verify twice around app restart.** Run plan/verify once with the Desktop
   fully closed, then verify again after relaunch — startup may re-introduce drift.

Local precedent: the 2026-08-12 "store update = inherent behavior" archive
(#72) was corrected on 2026-08-13 by a per-machine investigation (#77) that
reclassified the GitHub issue as unconfirmed and split the evidence into
per-machine columns. Lesson: archive conclusions with evidence levels.

## Rules and skills boundary checks

For a claimed global execution boundary, verify all applicable layers:

| Boundary | Minimum evidence |
|---|---|
| Hermes global persona/instructions | Rule file exists; compare to reviewed source if it is managed |
| Hermes managed workflow skills | Schema inventory exists, each live root exists, tree hash comparison, CLI enabled status |
| Codex global guidance | `$HOME/.codex/AGENTS.md` exists; only compare it if an explicit canonical source is known |
| Project rules | Project `AGENTS.md` exists; state that it applies to that project, not globally |

Do not treat an `AGENTS.md` inside a plugin, dependency, cache, backup, or temporary directory as a global rule.

## Dependency drift: pip vs uv version mismatch

Symptom: the Hermes/Codex backend fails to start with a version-mismatch
error (`pydantic 2.13.4 requires pydantic-core==2.46.4, found 2.48.0`), or an
`import` raises on a fast-import dependency after an upgrade/repair attempt.
FastAPI-based backends are the usual victim (they import pydantic at startup).

Root cause: the environment is **uv-managed** (`uv.lock` authoritative) but a
bare `pip install` ran — pip does not read `uv.lock` and installs the latest
PyPI release, overwriting a locked pin. pydantic pins `pydantic-core` with an
exact `==` (not `>=`), so any drift is a hard crash, not a soft mismatch.

Decisive diagnosis: read the lockfile pin (`uv.lock` → `version = "..."`),
then check `venv/Lib/site-packages/<pkg>.dist-info/INSTALLER` (one line: `uv`
or `pip`). **Mixed installers on one package family is the smoking gun** —
e.g. `pydantic` = uv while `pydantic_core` = pip. Cross-check the exact pin in
`<pkg>.dist-info/METADATA` (`Requires-Dist: pydantic-core==2.46.4`).

Fix: `uv sync` (preferred) or `uv pip install <pkg>==<locked>`. Never resolve
with a bare `pip install <pkg>` — it re-installs latest and re-drifts.

Full recipe and the "INSTALLER field records last installer, not current
health" caveat: `references/pip-uv-dependency-drift.md`.

## Post-update: managed overlay + native curator conflict

Applies when a repo declares a Hermes home directory (e.g. `HERMES_HOME/skills/**`) as a MANAGED unit deployed with whole-tree replacement, and the native Hermes curator also writes there (two writers, one directory). The managed guard then correctly refuses to publish live drift; the recurring fix is a fold-back policy.

- Update with `hermes update --yes --backup`: it drops a FULL backup (state.db, config, .env, auth) plus a code rollback ref that EXPIRES ~30 days. If the local clone has forked, the product resets to remote and leaves that ref — verify the ref name, and that the backup actually contains `state.db` before relying on it.
- Do NOT roll back on scary update logs. Check real state first (`gateway status`, process list) and separate a deliberate prior state from real breakage (stale-record false alarm: first `update` reports restart-failed, but the gateway was already down by user intent; re-running reports pending-restart-completed and starts nothing).
- A managed guard refusing to publish live drift is CORRECT — it protects repo content. Resolve the recurring curator↔managed conflict by FOLD-BACK, ranked: fold-back > suspend > drop-from-managed-set. Fold-back automation may only ADD: ADDED / EXTENDED / line-ending-only differences auto-fold; REMOVED / TRIMMED / REWRITTEN report NEEDS_REVIEW and are never auto-applied; the automation must never delete a repo file. Publishing stays behind the official syncer (never write Hermes Home directly).
- Post-update evidence is a checkable list, not a narrative: `doctor` exit 0 (version files consistent / config migrated / no deprecated keys / state.db / lock OK), a REAL desktop-entry launch (process count, main-window title, responding=True, zero after close), managed assets N/N CONVERGED, gates all PASS, managed fields + user model routing zero drift.
- Register backup gaps: a full backup may omit a managed asset (e.g. `SOUL.md`) — note it is rebuildable only from repo source + syncer.

## Reusable defect patterns (from a real Hermes update round)

1. Structured-success outranking a literal terminal error: `exit 0` + body containing "Billing/credits exhausted" + `structured{success:true}` was scored SUCCESS. Fix: check the literal terminal error modes BEFORE signing a structured success; only retract a success that was wrongly given, never invent one.
2. Flaky test racing a proxy condition: it waited on `calls >= 2` while the asserted value is assigned inside the function → the main thread asserts before the worker finishes. Fix: wait on the condition actually asserted; verify by running N times.
3. `eol=lf` violations that recur on every regeneration: the generator's `Path.write_text()` omitted `newline="\n"` → Windows text mode writes CRLF. Fix: add `newline="\n"` at every write site in the generator; deliberately do NOT "fix" normal `.py` CRLF under `text=auto` (that is normal behaviour, not a defect).
4. Stale hook/allowlist approval after the approved script changed (even one line): verify the new sha256 matches the recorded prior review, then REFRESH the approval (not revoke); back up the allowlist first; confirm `hooks doctor` is healthy and `hooks test` still blocks a real wire-shape.

Reference: WORK-LAB `taskpacks/current/HERMES-UPDATE-AND-FIXES-20260917.md` (checkable values + ZIP sha `71cd76b4…` + `curator_foldback.py`, fold-back policy = always fold back). See [references/hermes-update-managed-overlay.md](references/hermes-update-managed-overlay.md) for the full per-step evidence recipe.

## Client registry reconciliation (available-not-applied pattern)

A managed-client registry (`config/adapter-registry.json`, `config/client-evidence.json`)
records the **live readback** of each client (version, install method, paths). Two distinct
drift classes exist and must be handled in the change that discovers them:

- **Version drift** — upstream released a newer version, live install unchanged. Record as
  *available-not-applied*: `provenance.version` carries the live readback; `version_historical`
  gains the new release with a not-applied marker. Never install/upgrade as part of a registry
  fix; upgrades are separately authorized acts.
- **Path drift** — a repo restructure (directory convergence) moved the artifact a registry
  note references (e.g. a wrapper path `bin/codex` → `packages/client-neutral-core/bin/codex`).
  Reconcile the path in the same commit as any version drift touching that entry; a stale path
  in a note is itself a contract_drift defect.

Registry `provenance` blocks are closed schemas (`additionalProperties: false`): only use
existing keys (`version`, `version_historical`, `note`, …). Inventing a new key (e.g.
`version_basis`) makes the fail-closed verifier reject the whole file — put explanatory text
in `note` instead. After any registry edit, run the adapter-registry verifier plus the
relevant pytest subset before committing; register a `contract_drift` error-ledger entry when
the fix closed a real inconsistency.

## Safety boundaries

- Do not inspect or print `.env`, `auth.json`, OAuth/token stores, browser data, session databases, provider endpoints, or API keys.
- Do not change provider/model routing, VPN/proxy services, plugins, profiles, permissions, or layout databases during an audit.
- Do not directly edit Hermes `config.yaml`; use official CLI commands only after explicit user authorization.
- Do not use source-to-live overwrite to resolve drift before classifying ownership and obtaining explicit approval.

## Windows reference

See [references/windows-agent-update-audit.md](references/windows-agent-update-audit.md) for a safe evidence recipe and an example of how to report managed-skill drift without exposing configuration contents.
