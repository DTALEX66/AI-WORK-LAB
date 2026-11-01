---
name: agent-update-safety
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/agent-update-safety/SKILL.md
---

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

## Safety boundaries

- Do not inspect or print `.env`, `auth.json`, OAuth/token stores, browser data, session databases, provider endpoints, or API keys.
- Do not change provider/model routing, VPN/proxy services, plugins, profiles, permissions, or layout databases during an audit.
- Do not directly edit Hermes `config.yaml`; use official CLI commands only after explicit user authorization.
- Do not use source-to-live overwrite to resolve drift before classifying ownership and obtaining explicit approval.

## Windows reference

See [references/windows-agent-update-audit.md](references/windows-agent-update-audit.md) for a safe evidence recipe and an example of how to report managed-skill drift without exposing configuration contents.
