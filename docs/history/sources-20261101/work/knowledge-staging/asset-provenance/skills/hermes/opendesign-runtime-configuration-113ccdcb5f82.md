---
name: opendesign-runtime-configuration
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/opendesign-runtime-configuration/SKILL.md
---

---
name: opendesign-runtime-configuration
description: Install/verify Open Design desktop skills/plugins/systems.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [opendesign, runtime, desktop, skills, plugins, design-systems, daemon]
    related_skills: [runtime-deployment-audit, multi-machine-config-sync-audit, project-data-boundary]
---

# Open Design runtime configuration

## When to Use

The user asks to install/configure the OPEN-DESIGN-Assistance repo assets (Personal Skills, expert plugins, bundles, Personal Design Systems) into the running **Open Design desktop app**, or reports "我的体系/技能/插件还是没有啊" after an install. Open Design is the reference host for the `OPEN-DESIGN-Assistance` repo. This is a recurring class of task (fresh machines, re-created runtimes).

## Golden rule: verify in the running app, never from installer output alone

The user's hard correction (verbatim): **"详细审计下，别老犯这种低级错误，一会说装好了，一会我看又没有"** — NEVER claim "配置完成" because the installer printed `OP_EXPERT_SUITE_INSTALL=OK`. The installer succeeds at the daemon layer while the live UI/daemon index still shows nothing. Prove visibility in the actual running app before reporting done.

## Canonical installer (do NOT hand-roll CLI plugin commands)

Use the repo's official installer, not ad-hoc `od plugin install` / `marketplace add`:

```bash
python opendesign-assistance/scripts/install_op_expert_suite.py --dry-run   # read-only plan
python opendesign-assistance/scripts/install_op_expert_suite.py             # real install
```

- It auto-discovers the daemon URL (from the Web sidecar log), selects the Personal Workspace, and handles the workspace auth headers for skills/design-systems/plugins.
- Idempotent: re-running shows `skills skipped: 15`, `design systems updated: 3`, `expert resources installed/bound: 10`.
- Success markers: `EXPERT_RESOURCE_READBACK=PASS`, `USER_CONFIG_PRESERVED=PASS`, `OP_EXPERT_SUITE_INSTALL=OK`.

## Critical traps (each produced a false conclusion)

1. **Daemon port is dynamic per restart — never hardcode it.** The app's daemon URL (e.g. `127.0.0.1:57119`, later `65289`) changes every launch. `install_op_expert_suite.py` discovers it; you should too, from the installer's own dry-run output. Do NOT start your own daemon on a fixed port (7456) as a proxy — that is a separate process and its plugin catalog is NOT the app's.

2. **You MUST restart the Open Design app for the daemon's design-systems index to refresh.** The user's fix (verbatim): **"重启就好了"**. Installer writes skills/plugins/design-systems to disk (`data/skills/`, `data/plugins/`, `data/design-systems/`) immediately, but the daemon's design-systems list is rebuilt on startup. Before restart: UI「设计体系 → 你的体系」shows "还没有设计体系" even though the installer reports 3 created. **Restart the app, then re-verify.** A GUI app the user is actively running cannot be killed by an agent (access denied) — ask the user to close/reopen it, or confirm they did.

3. **The daemon `design-systems`/`skills` API requires the FULL workspace header set.** Bare `curl /api/design-systems` returns 0–1 user systems; passing only `x-od-workspace-id` returns 0. The complete set (from `select_workspace` in the installer):
   ```
   x-od-workspace-id, x-od-workspace-member-id, x-od-workspace-type: personal,
   x-od-workspace-role, x-od-workspace-member-status: active,
   x-od-workspace-lifecycle-state: active
   ```
   With all six headers you see all 3 user design-systems. A missing header ⇒ false "missing" ⇒ you waste time investigating a phantom gap.

4. **Skills and Design Systems are separate UI surfaces.** Skills appear under **插件 → 技能** (filter 「个人的」); Design Systems under **设计体系 → 你的体系**. All 15 skills can be visible in the 插件 tab while the 设计体系 tab shows empty — these are independent evidence surfaces. Do not conclude "全部没有" from one tab.

5. **The daemon rejects cross-origin HTTP from the UI** ("Cross-origin requests are not allowed"). The Electron UI talks to the daemon via internal IPC, not plain HTTP — so your curl probes and what the UI renders can diverge. Trust daemon-API-with-full-headers + app.sqlite + disk for data presence, then confirm UI visibility after restart.

## Verification checklist (after any install/restart)

- [ ] Installer re-run idempotent: `skills skipped: 15`, `design systems updated: 3`, resources `10`, `OP_EXPERT_SUITE_INSTALL=OK`
- [ ] `app.sqlite` (read-only `mode=ro`) `installed_plugins WHERE source_kind!='bundled'` = 10 entries (`source_kind=local, trust=trusted`)
- [ ] Disk `data/design-systems/` has the 3 system dirs; `data/skills/` has 15; `data/plugins/` has 10
- [ ] Daemon `/api/design-systems` with FULL workspace headers returns 3 `user:` systems (status=published, workspaceId=wlkqamq...)
- [ ] Daemon `/api/skills` with full headers returns 15 `source=user` skills
- [ ] `doctor_open_design_windows.py` → `DOCTOR_RESULT=OK` (model baseline `gpt-5.6-luna`, CODEX_BIN exists)
- [ ] Main verifier `verify_open_design_assistance.py` → `VERIFY_RESULT=OK total=467 failed=0`
- [ ] **UI (after app restart)**: 插件→技能 shows all 15 personal skills; 设计体系→你的体系 shows the 3 design systems

## Model/Codex config facts

- Default model baseline `gpt-5.6-luna` (official). The doctor script's `DEFAULT_MODEL` must match live — a stale expected model (`gpt-5.5`/`gpt-5.6-terra`) produces a false FAIL; update the script + its regression test together.
- `CODEX_BIN` in app-config points to a versioned dir under `%LOCALAPPDATA%\OpenAI\Codex\bin\<commit>\codex.exe`. A configured path can go stale after a Codex update (old commit dir removed). The doctor's `find_codex_bin` should verify existence and fall back to globbing `*/codex.exe`; update app-config CODEX_BIN to the real existing exe.

## Evidence-level discipline

Data presence in disk + app.sqlite + daemon-API = E1/E2. Live UI visibility after restart = display evidence. Only exact-SHA PR/CI/merge/main-readback = E4 release. Keep these separate; never report E4 from local daemon checks.

## See also

- `references/daemon-verification-probes.md` — concrete curl probes (workspace headers, design-systems, skills, app.sqlite) plus the false-negative traps and the runtime-identity confusion (Hermes headless backend vs Open Design daemon).
- `runtime-deployment-audit` — third-party desktop app runtime E3 evidence (read-only SQLite, provenance files, multi-source version reconciliation).
- `multi-machine-config-sync-audit` — when the question is whether cloud/other-machine config reached this machine.
