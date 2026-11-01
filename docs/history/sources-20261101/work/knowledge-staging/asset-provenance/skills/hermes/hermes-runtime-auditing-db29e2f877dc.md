---
name: hermes-runtime-auditing
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/autonomous-ai-agents/hermes-runtime-auditing/SKILL.md
---

---
name: hermes-runtime-auditing
description: "Use when auditing Hermes runtime state safely and read-only."
version: 1.1.0
author: Hermes Agent
created_by: agent
---

# Hermes Runtime Auditing

Use when a user asks for a global Hermes health, inventory, security, or runtime audit and requires a **read-only**, **non-secret** assessment. This covers sessions, cron, gateway, plugins, MCP, skills, tools, hooks, and configuration structure.

## Operating contract

1. Restate the safety boundary in the result: no writes, no starts/stops/restarts, no deletion, and any explicitly excluded drives/paths are not accessed.
2. Do **not** directly open, print, hash, copy, or enumerate the contents of secret-bearing files such as `config.yaml`, `.env`, `auth.json`, cookies, credentials, tokens, or private keys.
3. Prefer official status commands that return aggregate health or boolean/structural status. Do not repeat provider credential names or secret-presence matrices in the report.
4. Treat commands that can execute configured code as non-read-only even if named "doctor" or "test". In particular, `hermes hooks doctor` and `hermes hooks test` can synthetically invoke hooks; omit them under a no-execution audit and record the coverage limitation.
5. Do not call `hermes mcp test` when the scope is read-only/no-external-side-effects. `hermes mcp list` plus `hermes doctor` provides configuration/load and static-security status, not live connectivity.
6. Never run mutating flags such as `--fix`, nor gateway/cron/plugin/MCP enablement, installation, restart, cleanup, prune, or migration commands.

## Cloud-update suitability audit

Use this extension when a repository has advanced on `origin/main` and the question is whether the update is safe for the current machine. Keep three states separate: remote source tree, local Git checkout, and active Hermes/Codex runtime.

1. Fetch remote refs and record the local worktree status, current `HEAD`, `origin/main`, divergence counts, merge SHA, changed paths, and required workflow/check evidence. Do not overwrite a dirty checkout.
2. Review the remote diff before integration. Classify repository-controlled files, generated/runtime artifacts, profile-live-only skills, global instruction files, hooks, and provider state separately.
3. Verify the remote tree in an isolated, short-path worktree inside the project’s ignored runtime. On Windows, pre-create `tmp/cache/logs/artifacts` before raw tests; remove the temporary worktree after verification. Prefer the project’s canonical quality gate over a bare test command.
4. Only after the tree is suitable, fast-forward a clean local branch with `git merge --ff-only origin/main`. A green remote workflow proves the remote tree, not live-profile compatibility.
5. Run provenance as a separate read-only check against the active live root. Report repository-controlled hash drift as a candidate for scoped repo→live deployment; preserve `profile-live-only` skills and never rewrite the manifest just to make drift disappear.
6. Treat repo→live deployment, Codex Home writes, hook revocation/re-approval, provider changes, and credential/config changes as separate mutations. Require dry-run, scoped backup, rollback evidence, and explicit authorization. A changed hook must be explicitly revoked and re-approved; never silently bypass trust.
7. Report exact remote/local SHAs, workflow/run URLs and attempts, local gate artifacts, live provenance status, and all intentionally unperformed global writes. A local source-tree PASS and a live-runtime PASS are different claims.

### Official updater closure under a moving upstream

Treat updater process completion, checkout identity, live overlay integrity, and Desktop usability as four independent evidence classes. `Code updated!` or a still-responsive GUI does not prove the updater exited successfully; require the updater's final exit code and terminal completion marker. After exit, fetch every configured remote alias that may point at the canonical repository, then record `HEAD`, each relevant `*/main`, divergence, worktree status, worktree count, branches, and stashes. Remote aliases maintain independent refs even when their URLs are identical.

An official repository may advance or force-push during a long build. Use the official updater rather than a hand-written destructive reset, allow at most a bounded rerun when a new commit is already known, and freeze the accepted SHA with a timestamp once `HEAD` and the fetched authoritative refs agree. Future upstream movement does not retroactively invalidate that acceptance snapshot; it creates a new update candidate. Do not chase an actively moving remote forever or rewrite the report as if the earlier updater failed.

After the final updater run, execute the portable package's canonical gate under the updated managed runtime and recheck live provenance/exact managed inventories. An updater may intentionally preserve user-modified bundled skills; classify each preserved identity against the overlay ownership schema before resetting anything. Keep provider-key failures, stopped/stale Gateway state, session-storage optimization, and deliberate Desktop cold restart as separate follow-ups—never auto-fix routing, credentials, services, or protected session data merely to make Doctor visually green.

See `references/official-updater-moving-upstream.md` for the evidence matrix and bounded closure recipe.

Detailed evidence fields and the Windows short-worktree/runtime preparation recipe are in `references/cloud-update-suitability.md`.

## Audit sequence

### 1. Establish runtime and structural health
Run, without `--fix`:

```bash
hermes --version
hermes config check
hermes doctor
```

Report only durable, non-secret conclusions: config schema/version validity, deprecated-key status, active advisories, static MCP warnings, runtime package/dependency status, and tool availability. `config check`/`doctor` may load configuration internally; describe this accurately as **official structural validation**, not direct secret-content inspection.

### 2. Inventory scheduled/runtime surfaces

```bash
hermes sessions stats
hermes cron list --all
hermes cron status
hermes gateway status
hermes profile list
hermes webhook list
```

For a Windows service/task presence check, use query-only commands:

```bash
schtasks.exe /query /fo csv /nh
```

Use process/port inspection only to corroborate gateway status; do not infer that every Hermes/Electron/Python process is a gateway. A lack of matching listening ports is useful corroboration, not sole proof.

### 3. Inventory extension surfaces

```bash
hermes plugins list
hermes mcp list
hermes skills list
hermes tools list
hermes hooks --help
```

When plugin output is too large, calculate and report only safe aggregates (status counts, enabled names, bundled vs non-bundled count) rather than dumping descriptions. Count only after capturing the command output; do not modify plugin state.

### 3a. Profile-scoped skill governance

When the audit covers global rules, skills, plugins, frontmatter, or profile scope, follow [`references/skill-governance-audit.md`](references/skill-governance-audit.md). Reconcile the active profile's recursive `SKILL.md` tree against `hermes -p <profile> skills list --enabled-only` and source-specific lists; do not treat a historical managed-skill count as authoritative without a current manifest. Parse `metadata.hermes.related_skills` and flag top-level relationship fields, unresolved names, directory/name drift, and on-disk-versus-CLI inventory mismatches.

When the audit finds repo↔live skill drift and the user authorizes repair, follow [`references/skill-drift-reconciliation.md`](references/skill-drift-reconciliation.md): hash-compare the full SKILL.md tree with CRLF normalization, determine direction per skill (line count, version, unique-content diff), merge bidirectional splits with `difflib.SequenceMatcher`, sync both ways, and update `skill-provenance.yaml` hashes + versions before re-running the gate.

For fail-closed claims, distinguish documentation, executable-path existence, active registration, and behavioral proof. Under a no-execution audit, `hermes hooks list` is acceptable structural evidence, but `hermes hooks doctor` and `hermes hooks test` are not: they can invoke configured/synthetic hooks. Static gates that claim "only wrapper X may pass" must validate command structure/argv rather than merely matching a wrapper filename substring. External executors outside the audited workspace remain unresolved; do not traverse sibling projects to make the claim look proven.

"Active registration" is itself surface-specific: a `pre_tool_call` shell hook can be registered in CLI/gateway sessions yet silently skipped in the desktop `serve` backend, because `_prepare_agent_startup` (hermes_cli/main.py) registers hooks only for `_AGENT_COMMANDS = {None, "chat", "acp", "rl"}` plus `cron`/`gateway`/`mcp` subcommands — `serve`/`dashboard` are absent. When a hook is "registered but not firing", trace `resolve_pre_tool_block` (the live entry point, NOT the deprecated `get_pre_tool_call_directive`) AND the `register_from_config` call sites, then check the launch command's membership in `_AGENT_COMMANDS`. Do not accept "emission missing" from a report that grepped only the deprecated symbol. See `references/pre-tool-hook-not-firing.md` for the corrected diagnostic and the empirical `_make_callback` probe.

### 4. Metadata-only filesystem corroboration
Use directory and file metadata only under the Hermes home. Avoid sensitive-file names and content. Safe checks include directory existence, directory/file counts, size, timestamp, permissions, and reparse-point/symlink metadata. For cron or session residuals, report them as **candidates**, never as orphaned data without reading enough safe evidence.

## Cross-project data-boundary audits

A project-local wrapper and `cwd=<repo>` do not prove global containment. Audit every execution surface separately: Hermes terminal and TaskPack subprocesses, Codex CLI, CC Switch/model-switch subprocesses, Desktop/Tauri, Gateway/cron/delegation workers, and direct Python/Node/Rust commands. Verify canonical project root, explicit cwd, injected project-local `TMP`/`TEMP`/cache/log/artifact variables, and rejection of absolute paths outside the project. Report bypassed surfaces as uncovered or `uncontained_external_process`, not PASS.

Before moving or deleting an external handoff/review/temp file, prove ownership using content, Git worktree, executor/process, command, timestamp, and generation path. A project name in a filename or prompt is not proof. Preserve unresolved files and mark them for human ownership review. Distinguish project-owned outputs from Hermes/Codex/CC Switch/Workflow-assistance session, delegation, cron, Kanban, and review infrastructure.

**Outside-project path operations need an explicit nature check before any write/delete** (user-mandated boundary discipline, 2026-08-13): classify the path first — (a) a Git project, (b) the project's own external-dependency store if one exists (e.g. `OS External Configuration` — the single allowed outside-project path for that project), (c) leftover/legacy residue of a completed migration, or (d) unrelated/unknown. Only after the nature is declared may the smallest-scope action proceed, followed by a no-breakage verification of the active environment. Deleting "regenerable cache" without declaring the path's nature first is a boundary violation even when authorized — authorization confirms scope, it does not replace the classification step. Also verify whether an outside-project cleanup target is still referenced (env vars, docs, scripts, CI) and still actively written before declaring it residue.

When auditing a portable pack, compare repository source skill, deployed live skill, and loaded profile content separately; repo-to-live sync can restore an older rule after a live-only patch. Include negative controls for wrapper bypass, system-temp writes, symlink/junction escape, protected paths, two adjacent projects, source/live drift, and structural checks mislabeled as real integration checks. The reusable matrix is in `references/project-boundary-enforcement-audit.md`.

When asked "did this project ever access E:\ / a protected path?", run the four-layer sweep (working tree / git history / runtime traces / session logs) in `references/protected-path-access-tracing.md`; the decisive SQLite `state.db` query (group-by-role → group-by-tool_name → sample → anchored negatives) is in `references/state-db-access-query.md` — it distinguishes defensive mentions (ban text, test fixtures, user environment descriptions in transcripts) from real tool-call access, and states whether compliance is rule-based or mechanism-enforced.

## Cross-tool delivery and reviewer audits

When the scope spans Hermes + Codex CLI + CC Switch + GitHub delivery, add these checks:

1. **Reviewer authority is executable, not prompt-based.** Inspect the actual reviewer command/toolset/sandbox. A Hermes reviewer with write-capable `terminal`/`file` tools is not read-only even if its prompt says “never edit”. Codex release review should use `exec --sandbox read-only --ephemeral` and, when supported, `--ignore-user-config --ignore-rules`. Git snapshots do not detect global, external, or edit-then-revert side effects.
2. **Canonical cwd/runtime.** Resolve the requested repo with `git rev-parse --show-toplevel`; require writer, reviewer, Git, and smoke subprocesses to use the same canonical root. Check `.hermes/task-runtime/` is Git-ignored before creating it and route temp/cache/artifact variables through the project boundary helper. A subprocess `cwd` argument alone is not containment.
3. **Secret boundary.** Model switchers/doctors must not parse `.env`, `auth.json`, Codex config, CC Switch databases, cookies, or credential stores. Prefer official aggregate/status commands and redacted summaries. Do not print raw `base_url` values because URL userinfo can evade token-oriented redactors.
4. **Exact-tree CI identity.** Require an explicit remote ref and one or more required workflow names. Verify release `HEAD^{tree}` equals the reviewer-approved `git write-tree`, query CI by commit SHA, explicitly validate returned `headSha`, and retain the selected workflow/run ID/attempt/URL/SHA. A successful query with no durable identity evidence is incomplete.
5. **Task-ticket enforcement.** Templates should include allowed/forbidden paths, baseline/result/review/release trees, reviewer permissions, remote ref, required workflows, exact-SHA URLs, rollback, protected-drive and runtime rules. Do not treat template fields as enforcement unless the runner parses or validates them.
6. **Static versus live checks.** Default doctor/audit mode should be static and non-networking. MCP connectivity, curl/proxy checks, provider markers, OAuth and model calls belong behind explicit live/network flags. Do not use `|| true` to hide a required structural or release-gate failure.
7. **Wrapper trust and version drift.** A regex that only matches a wrapper basename is bypassable. Parse argv and require the canonical deployed wrapper path; sensitive gates should also record approved hash/version and actual Codex execution identity. Portable skills must not hardcode a user's home path or stale CLI version.

The session-specific matrix and evidence fields are in `references/cross-tool-boundary-audit.md`; the broader project containment matrix remains in `references/project-boundary-enforcement-audit.md`.

## Codex Desktop persistence and installation audits

When login, Windows sandbox/approval state, bundled plugins, appearance, executable resolution, or a simultaneous Hermes update is under investigation, follow [`references/codex-desktop-persistence-audit.md`](references/codex-desktop-persistence-audit.md). Keep Store package, CLI wrappers, Codex Home, Chromium profile, Windows sandbox, marketplace, project wrappers and Hermes managed Git as separate state layers. Require normal Quit → zero processes → cold launch → reconcile settle → second-cycle persistence; compare final semantic state rather than a transient file hash. A listening router with zero models, stale `profile.exit_type`, one passing Doctor retry, or timing correlation without writer evidence cannot close the gate.

## Windows network / VPN performance triage

Use this **only when the user reports lag, buffering, slow model calls, or suspected Hermes bandwidth use**. It is a minimally intrusive diagnostic extension, not a substitute for inspecting VPN credentials or configuration.

1. State the boundary: do not open proxy/VPN config, reveal endpoints or credentials, switch nodes, alter split-tunnel rules, close browsers, or stop running agents without explicit permission. **Even with repair authorization, never force-kill a local proxy core merely to refresh connections or test a theory**: its GUI parent may not supervise respawn, which can strand every system-proxied application offline. Prefer the product's native reconnect control; before any disruptive action, establish the recovery/rollback path and state the interruption risk.
2. Capture a short adapter-rate sample with `typeperf` and a bounded network-quality sample: several ICMP pings plus at most a small (for example 1 MiB) HTTPS transfer. Report that the transfer itself is a short-lived probe, not evidence of background traffic.
3. Sample CPU and memory over a real interval with `psutil`; include browser/Electron/agent processes when present. Video stutter can be a render/decode contention even when aggregate network is not saturated.
4. Use `netstat -ano` only to establish connection ownership and proxy fan-out. A local proxy can own both local client sockets and remote sockets, so its connection count does **not** prove which application consumes bandwidth; Windows' basic netstat output has no per-process byte counters.
5. Attribute conservatively: a low adapter rate plus slow bounded transfer points to path/exit/server throughput rather than Hermes saturating the NIC. Stable latency with zero loss does not guarantee sufficient streaming throughput.
6. If domestic media is slow while overseas agent endpoints require a VPN, recommend user-approved rule-based split routing (domestic media direct; required overseas domains proxied) rather than disabling protection globally. Do not modify routes or nodes until the user chooses the scope.

## CC Switch API Router / API-model cost boundary

When attaching Hermes API models to CC Switch, treat the network proxy and API Router as separate surfaces. Verify the candidate Router with secret-free GETs to `/health` and `/v1/models`; a healthy process with an empty model list is not a usable route and must fail closed. Do not guess ports, read CC Switch databases, or use admin APIs to manipulate providers. Keep `openai-codex` OAuth independent, configure Kimi/Moonshot in the CC Switch UI first, confirm a non-empty `/v1/models`, then point only the selected Hermes API lane at the verified `<router>/v1`. Existing sessions freeze provider/model, so cost incidents require checking the current non-secret provider/model and resetting or starting a new session. See `references/cc-switch-api-router-verification.md`.

## Interpretation rules

- **Live statistics can differ.** `hermes doctor` and `hermes sessions stats` may use distinct counting semantics or observe concurrent writes. Report snapshot values with a low-risk consistency candidate; do not diagnose database corruption from count mismatch alone. Recheck only when the session store is quiescent if the user authorizes it.
- **Enabled is not necessarily operational.** A toolset may be enabled while Doctor reports an unmet system dependency or provider prerequisite. Classify this as functional-availability mismatch, usually medium operational risk, rather than a security defect.
- **Stopped gateway is contextual.** If cron has no active jobs and webhook is disabled, a stopped gateway is normally informational, not a failure.
- **Empty runtime directories are contextual.** A zero-job cron inventory plus residual directories/files is a low-risk cleanup candidate only; do not remove it in an audit.
- **MCP static safety is not liveness.** “No suspicious stdio command” does not prove a server is reachable.

## Risk labels

Use these consistently:

- **High:** active exposure, suspicious command, security advisory, or a verified unsafe configuration. Do not invent one from missing optional dependencies.
- **Medium:** storage pressure, configured-but-unavailable tool capabilities, or operational inconsistency with user impact.
- **Low:** stopped-but-unused services, static residual artifacts, metric-definition mismatch, or deliberate coverage limits.
- **Informational:** healthy state, optional feature not configured, or user-intended disabled service.

## Required report shape

Write in the user’s requested language and include:

1. Scope/boundary statement, including whether official structural validation was used.
2. A table: surface, status/evidence, duplicate-or-stale candidate, risk level.
3. A short list of exact evidence commands, clearly marked read-only.
4. A separate "not performed" list for checks intentionally excluded because they would run code, connect externally, alter state, or inspect secrets.
5. Distinguish facts from candidates and do not prescribe mutating remediation unless the user asks.

## Reference

- `references/windows-nonsecret-runtime-audit.md` — validated Windows command set and interpretation notes for read-only Hermes runtime audits.
- `references/windows-local-proxy-recovery.md` — bounded path comparison and safe recovery rules for Windows local proxy / accelerator incidents.
- `references/official-updater-moving-upstream.md` — updater exit, remote-ref races, accepted-SHA freeze, and post-update overlay revalidation.
