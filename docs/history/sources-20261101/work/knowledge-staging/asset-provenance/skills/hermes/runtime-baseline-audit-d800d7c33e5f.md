---
name: runtime-baseline-audit
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/runtime-baseline-audit/SKILL.md
---

---
name: runtime-baseline-audit
description: "Use when auditing software entry, launch, or model power."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [audit, runtime, entrypoint, desktop, model, reasoning, wrapper, provider]
    related_skills: [checkout-ownership-reconciliation, codex-surface-recovery, hermes-codex-config-drift, windows-development-environment]
---

# Runtime Baseline Audit (five dimensions)

Audit every managed software surface (Hermes, Codex, CC Switch, GitHub,
OpenHuman, Open Design, …) against five dimensions. The user treats these as a
MANDATORY baseline: when the user says 检查入口/桌面/满血/阻塞感/配置 or asks
"是否都能从桌面快捷方式打开 / 是否模型满血 / 是否配置过重", this skill governs the
audit, and the baseline must be written into the project bottom layer
(AGENTS.md / managed-assets ledger) so future audits have a fixed reference.
When a dimension regresses, fix at the root and record in the error ledger
before merging.

## The five dimensions

1. **Unique entry per software** — one canonical launch path per tool; wrapper
   candidates resolve to exactly one runtime.
2. **Desktop entry** — every GUI tool opens from its desktop shortcut; the
   shortcut target chain resolves end-to-end.
3. **Official standard + user configuration** — official baselines win; the
   enhancement layer only manages declared overlay fields and never overrides
   user provider/model/auth/desktop state.
4. **No blocking overhead** — global rules/skills/guidance stay lean and load
   on demand; wrappers never stall on missing candidates.
5. **Full-power model** — no rate limits, no cost caps, no degraded reasoning;
   reasoning effort at official default or higher.

## Dimension 1 — unique entry

- Enumerate every launch path: desktop shortcuts, Start Menu, `PATH`
  (`which -a <tool>`), wrapper scripts, Store/AppX copies, per-user versioned
  install dirs.
- For a CLI with both bash and Windows wrappers (e.g. Codex `bin/codex` +
  `bin/codex.cmd`), the two MUST resolve identically. A wrapper that was fixed
  in bash but left stale in cmd is an entry inconsistency (2026-08-11:
  `codex.cmd` still had a dead fixed path while bash globbed
  `bin/<commit>/codex.exe`). Fix both, hash-verify repo==live
  (`sha256`), and stage immediately.
- Codex CLI installs live under versioned dirs
  `%LOCALAPPDATA%/OpenAI/Codex/bin/<commit>/codex.exe`; wrappers must glob
  these (newest wins), never pin `bin/codex.exe`. Old version dirs can remain
  as empty shells after an update — harmless, ignore.
- `CODEX_CLI_PATH` in `~/.codex/config.toml` reflects the current versioned
  install — check it matches the resolved wrapper candidate.

## Dimension 2 — desktop entry

- List shortcuts: `Get-ChildItem "$env:USERPROFILE\Desktop", "C:\Users\Public\Desktop" -Filter *.lnk`.
- Resolve each target via WScript.Shell and `Test-Path`:
  ```powershell
  $s=New-Object -ComObject WScript.Shell
  $l=$s.CreateShortcut("$env:USERPROFILE\Desktop\X.lnk")
  "$($l.TargetPath) | $($l.Arguments) | $(Test-Path $l.TargetPath)"
  ```
- Follow chains: a shortcut to `wscript.exe` with `Arguments` pointing at a
  `.vbs` launcher (Hermes pattern) — verify BOTH the wscript target AND the
  `.vbs` file exist. `Test-Path` on wscript alone is not enough.
- CLI-only tools (Codex has no GUI) legitimately have no desktop shortcut —
  record "no GUI, official CLI form" instead of fabricating one.

## Dimension 3 — official standard + user configuration

- Field-level ownership contract (e.g. `config-ownership.json`): managed
  fields are declared, `preserve_unknown: true` on adapters, user
  provider/model/auth/desktop state never written.
- Distinguish layers: active clients (deep), observe-only platforms,
  manifest-only future clients, and the enhancement module itself. Each
  adapter default carries layer+mode; verify fields stay within their declared
  mode (MANAGE / OBSERVE / IGNORE / FORBIDDEN).
- Secrets are FORBIDDEN everywhere — never collect/copy/hash.

## Dimension 4 — no blocking overhead

- Measure rule/skill/guidance weight:
  `du -sh <skills-dir>/*` and `wc -c <guidance> <rules>`.
  Working budget observed: each skill ~<10KB, guidance+rules <20KB total.
- Skills load on demand (description matching), not all injected; ~17–18k
  tokens per Codex exec is normal system context, not bloat.
- Wrappers must not stall on missing candidates (test `--version` under both
  bash and cmd entry points).
- `approval_policy=on-request` and `[windows] sandbox=elevated` are SECURITY
  baseline items (Codex Desktop writes `[windows]` itself) — do not strip them
  to chase "smoothness"; document them as intentional.

### "配置减重" (config slimming) is TWO layers — never report only one

The user's "减重/配置减重" spans two distinct surfaces; answering with only
one is a correction-worthy miss (validated 2026-08-15: answered "repo bloat
only", user corrected "还有所管理的全局配置减重和本项目内容内部配置减重"):

1. **Managed global config slimming (六客户端 USER_GLOBAL)** — a CONTINUOUS
   CONSTRAINT, not a one-shot task: each skill ~<10KB, guidance+rules <20KB
   total, load-on-demand. Enforcement lives in the `context-pack` gate
   (`build_context_pack.py`: DEFAULT_MAX_CHARS=12000, HARD_MAX_CHARS=30000,
   skill count + hash budgets, idempotency) which runs in CI, plus
   Growth/Memory quarantine rules (never auto-pollute global skills, never
   sync client A's raw memory to client B). Audit status = "gate exists and
   CI-runs" ≠ "numeric budget verified": measure actual context-pack char
   count, per-skill byte sizes, and hash budgets before claiming closed.
2. **Internal project config/rule slimming** — one-shot dedup work:
   collapse duplicate gate-selection rules to ONE authority (profile
   `gates:` consumed by impact_planner + emit_gate_plan; local convenience
   tables annotated as non-authoritative), and track repo SIZE bloat against
   a recorded baseline (tracked files + bytes; fail when +>10% or over byte
   budget without an approval record).

### Report task status from the TASKPACK's authoritative definitions, not session memory

When asked "任务 X 做完了吗 / 减重都是什么", read the taskpack's task
definition table FIRST (R6 attachment: the per-WL3-id table + the
capability→task mapping rows), because a single task ID can bundle a
one-shot delivery AND a continuous constraint. In WORK-LAB the authoritative
table lives in the R6 execution taskpack (`.hermes/desktop-attachments/`
`WORK-LAB-FINAL-MASTER-EXECUTION-TASKPACK-R6-2026-08-15.md`, lines ~49-59
capability mapping, ~600-615 per-task rows) plus the tracked
`WORK-LAB-STAGE-3-TASK-GRAPH.json` (ids/waves/deps only). Note that
file may read as binary through read_file — use grep/search_files for it.

## Dimension 5 — full-power model

- **Hermes reasoning effort**: `agent.reasoning_effort` in
  `%LOCALAPPDATA%/hermes/config.yaml`. Official default is EMPTY = medium;
  valid: none, minimal, low, medium, high, xhigh, max, ultra. A configured
  `low` is a silent reasoning downgrade (2026-08-11: found `low`, fixed via
  `hermes config set agent.reasoning_effort medium`, verified live).
  Per-session `/reasoning` overrides are fine; the GLOBAL default must stay
  official-or-higher.
- **Provider caps**: read CC Switch's store read-only
  (`sqlite3` with `file:...?mode=ro` on `~/.cc-switch/cc-switch.db`):
  - `providers` table: `is_current`, `cost_multiplier` (1.0 = no markup),
    `limit_daily_usd`/`limit_monthly_usd` (NULL = no cap).
  - `proxy_config` table: `enabled`, timeouts (streaming first-byte ~90s,
    non-streaming ~600s = loose, non-blocking), no rate-limit columns.
  - Never read `auth`/`apiKey`/token columns — redact in the query output.
- **Codex model routing**: `~/.codex/config.toml` top-level
  `model_provider` (no top-level `model` when a router like CC Switch decides
  the model); `[windows] sandbox=elevated` is Desktop-automatic, not managed.
- End-to-end proof: run one ephemeral exec on a DIFFERENT project and confirm
  provider/model line (e.g. `provider: cc-switch-official`, `model:
  gpt-5.6-sol`) plus a successful marker reply.

## Writing the baseline into the project bottom layer

- AGENTS.md: a "Five-dimension runtime baseline (mandatory, audited)" section
  listing the five dimensions + the regression rule (fix at root, record in
  error ledger before merging).
- Managed-assets ledger: a snapshot table (per-software × per-dimension) plus
  the audit commands used.
- Keep the baseline referenced from the repo's execution rules so future
  sessions audit against the same fixed reference.

## Pitfalls

- `reasoning_effort` is easy to miss: it is in `agent:` in config.yaml, not the
  `model:` block; also present empty in `delegation:` (leave that one empty).
- `hermes config set` prints a "Did you mean:" suggestion but still applies —
  verify with `grep` afterwards, don't trust the notice.
- PYTHONPATH on Windows is split on `;` even when the shell is Git Bash; CI
  uses `:` on Linux. Run local tests with
  `PYTHONPATH='src;scripts;...'` (quoted semicolons).
- CC Switch `settings.json` may show `enableLocalProxy: false` while the
  provider proxy is still listening — the per-app `proxy_config.enabled` is
  the real gate, not the global toggle.
- Redact aggressively when inspecting router DBs/configs: any column matching
  key/token/secret/auth is replaced with `[REDACTED]` before printing.

See `references/audit-commands-windows.md` for the full copy-paste command
sequence (desktop shortcuts, wrapper checks, config greps, CC Switch SQLite,
model reasoning verification).

To prove an Electron desktop app (e.g. Open Design) can **execute** — not just
launch — drive its bundled daemon via `ELECTRON_RUN_AS_NODE=1 "<app>.exe"
daemon-cli.mjs <cmd>` and confirm it returns live data; see
`references/electron-execution-probe.md`. A window snapshot proves entry, not
backend capability; a doctor/configure FAIL may be the diagnostic's stale
expectation (dead `CODEX_BIN`, outdated model name) rather than a real app fault.
