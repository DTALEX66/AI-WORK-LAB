# Official baseline + user overlay configuration standard

Status: current configuration layering guidance, subordinate to WORK-LAB-AUTHORITY.md and config/config-ownership.json. The dated filename is a stable reference, not a fixed runtime baseline. This document does not authorize a live global apply.

## 1. Control-plane boundary

WORK-LAB has one writer, `workflow-assistance`, and one read-only consumer,
`work-lab-observer`. Hermes, Codex, CC Switch and GitHub remain external actors.
OpenHuman is an optional candidate-evidence source. Open Design is an external
client; DESIGN-LAB is the independent owner of design capabilities. Declared
client overlays follow the current adapter/ownership contract; unsupported apply
stays unsupported. None of them becomes a third WORK-LAB module.

The target layering is:

1. `UPSTREAM_OFFICIAL`: discover the installed client's current schema,
   capabilities, defaults and config roots read-only. Do not copy an installation
   tree or freeze an old official config as a private fork.
2. `USER_OVERLAY`: version only the user's portable Rules, Skills, observed
   plugin declarations, boundaries and explicit preferences.
3. `PROJECT_OVERLAY`: keep project `AGENTS.md`, rules, skills, profiles and gates
   in the project that owns them. WORK-LAB may observe this layer for an explicit
   project task, but no global synchronizer may apply or replace it.
4. `TASK_EPHEMERAL`: keep leases, checkpoints and temporary task context in the
   Workflow-owned canonical SQLite database; expire them instead of promoting
   them silently.

`config/config-ownership.json` is the only field-level authority. The older
`config/managed-config-schema.yaml` is an isolated-empty-home compatibility
recipe, not a live deployment policy.

## 2. Recommended ownership by product

| Product | Official/native owner | WORK-LAB owns | Must not cross the boundary |
|---|---|---|---|
| Codex | `~/.codex/config.toml`, native auth, sandbox and runtime; each project owns its trusted project config, `AGENTS.md`, rules and Skills | global user `AGENTS.md` managed block, one user rules file, five declared user Skills, and missing field-level defaults only | auth files, private sessions, generated local memories, caches, Desktop internal state, or any project-local rules/Skills |
| Hermes | native Hermes Home 的 config.yaml, `.env`, `auth.json`, native `SOUL.md`, `MEMORY.md`, `USER.md`, session search and runtime | portable Rules/Skills package, explicit non-secret preferences and project execution boundaries; an explicitly approved model switch uses only `hermes config get/set/unset` | credentials, raw conversations, memory bodies, logs, cache, automatic cross-client memory import |
| CC Switch | its `~/.cc-switch` provider catalog, supported-client routing and local proxy state | desired routing policy for the clients it officially controls and secret-free observations | owning Hermes' independent native model selection; Codex/Hermes prompt, Skill, session or memory synchronization; credentials/database copies |
| GitHub | repository, branch protection, Actions and native `GITHUB_TOKEN` | desired workflows, gates and exact-SHA evidence contracts | broad write tokens, unpinned third-party Actions, fabricated check conclusions |
| ChatGPT | ChatGPT web memory and connected-app state | only explicit user-authored portable rules that are separately versioned | treating ChatGPT web memory as Codex local memory or mandatory project policy |
| OpenHuman | its local workspace/runtime plus its current managed sign-in/routing/search/OAuth services | sanitized, provenance-labelled candidate findings only | `.openhuman` keys, users, logs, memory/workspace bodies; any assumption that current Early Beta is fully offline |
| Open Design | independent local-first design workspace and its own CLI/MCP | an approved read-only external capability reference | vendoring it back into WORK-LAB, MINIGAME scope, or enabling mutation without a separate ActionPlan |

The Codex precedence chain must remain native: command-line overrides, the
nearest trusted project config, profile, user config, system config and built-in
defaults. Instruction discovery must also remain native: global override or
global `AGENTS.md`, then repository root toward the current directory, with the
closest file taking precedence. Mandatory durable policy belongs in
`AGENTS.md`/repository documentation, not in ChatGPT web memory.

Official references:

- [Codex config basics](https://learn.chatgpt.com/docs/config-file/config-basic)
- [Codex AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Codex rules](https://learn.chatgpt.com/docs/agent-configuration/rules)
- [Codex sandbox and approvals](https://learn.chatgpt.com/docs/sandboxing)
- [Codex GitHub integration](https://learn.chatgpt.com/docs/third-party/github)
- [ChatGPT and Codex memory boundaries](https://learn.chatgpt.com/docs/customization/memories)
- [Hermes configuration](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/configuration.md)
- [Hermes Skills](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md)
- [Hermes memory](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md)
- [Hermes security boundary](https://github.com/NousResearch/hermes-agent/security)
- [CC Switch settings and data](https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/en/1-getting-started/1.5-settings.md)
- [CC Switch provider switching](https://github.com/farion1231/cc-switch-website/blob/main/public/docs/en/2-providers/2.2-switch.md)
- [CC Switch routing](https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/en/4-proxy/4.2-routing.md)
- [OpenHuman](https://github.com/tinyhumansai/openhuman)
- [OpenHuman Skills runtime](https://github.com/tinyhumansai/openhuman-skills)
- [Open Design](https://github.com/nexu-io/open-design)

## 3. Safe linkage sequence

1. Discover executable identity, real path, version, config root, profile and
   duplicate installations. An ambiguous identity blocks apply but not other
   read-only work.
2. Read the official schema/capabilities from the discovered installation. Do
   not assume a model, version, port or install path. Core CI must not install a
   pinned Agent merely to satisfy an optional Adapter test; run that test only
   when the capability is already present.
3. Three-way compare the previous official baseline, new official baseline and
   user overlay. Unknown fields are `OBSERVE + QUARANTINE`.
4. Produce a secret-free diff and ActionPlan. A requested approval does not make
   an unimplemented Adapter operation real.
5. After approval, apply only through a stable official interface and only for
   fields owned by the registry. Before writing: backup and hash-fence the exact
   target. After writing: read back and compare. On mismatch: stop and offer the
   recorded rollback.
6. Restart only the product whose official documentation requires it. Re-run
   identity discovery and readback; never infer success from a UI badge.
7. Record normalized facts in Workflow `canonical.sqlite`. Observer reads the
   same database with SQLite `mode=ro` and receives deltas through persistent
   loopback SSE. Loopback services should bind an OS-assigned port and advertise
   the actual endpoint; clients must not guess a fixed port.

Open Design should default to its read-only loopback MCP/CLI surface. Installing
an integration with `od mcp install <agent>` is a separate approved external
action. OpenHuman should remain optional until its Early Beta and managed-service
dependencies satisfy the user's privacy/offline requirements.

## 4. GitHub and delivery defaults

- Grant the workflow-level `GITHUB_TOKEN` only the minimum permissions required;
  default verification is `contents: read`.
- Pin third-party Actions to a full commit SHA.
- Use workflow-and-ref concurrency with `cancel-in-progress` to avoid stale
  duplicate runs.
- Cache only declared dependency-manager data and never treat a cache hit as
  test evidence.
- A tracked current-state file must not claim the SHA of the commit containing
  itself. Tracked state says `RUNTIME_REQUIRED`; ignored runtime attestation binds
  checkout HEAD/tree, remote main, dirty classification, writer identity and
  exact-SHA CI evidence.

Official references: [workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
[dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching),
and [`GITHUB_TOKEN` security](https://docs.github.com/en/actions/concepts/security/github_token).

## 5. Failure patterns and required response

| Symptom | Root cause to test first | Required response |
|---|---|---|
| Codex login and CC Switch badge disagree | separate auth/config roots or stale process | discover both roots, validate native Codex login and routing independently, then restart only as documented |
| Two Codex/Hermes entries behave differently | dual installation, alias or profile split | resolve executable real paths and effective config roots; block apply while ambiguous |
| Official upgrade erased user behavior | user content was written into an official baseline/install tree | restore the user overlay from backup and rebase it on a newly discovered read-only baseline |
| A Skill works in one client but not another | client-specific discovery path or incompatible runtime | keep one portable source plus per-client adapters; never make CC Switch the Skill source of truth |
| Memory changes are missing mid-session | Hermes memory is frozen at session start or ChatGPT/Codex stores differ | start a new native session when required; keep mandatory policy in versioned instructions |
| Observer says `LIVE`, `running`, `0` or `exact` without evidence | fixture/hardcoded fallback or second store | downgrade to `SNAPSHOT`, `OFFLINE` or `UNKNOWN`; render unknown numeric data as null/dash |
| SSE connects and immediately closes | finite response with `Content-Length` | use long-lived `text/event-stream`, cursor replay, heartbeat and bounded slow-consumer handling |
| Token fields are rejected as secrets | broad substring filter treats usage counters as auth tokens | allow only normalized usage counter names; continue rejecting auth/credential fields |
| Adapter reports `APPLIED` after approval but changed nothing | approval gate substituted for implementation | report `UNSUPPORTED`; conformance must reject fake apply/rollback success |
| Quality gate emits hundreds of failures | declared Python validator dependency missing | run dependency preflight once and install the checked-in requirements in CI/local environment |
| Core CI installs or pins one Agent version | optional Adapter runtime check was mixed into the client-neutral default Gate | keep structural verification in the default Gate; capability-discover the installed Agent and run its isolated runtime check separately |
| Real-project canary is missing or scans the wrong drive | the gate guessed workstation-specific project roots | accept discovered/registered roots or explicit `WORKLAB_CANARY_PROJECT_ROOTS`; otherwise report the canary as pending |
| Tracked user profile contains paths, provider/model or full client config | a redacted machine snapshot was mistaken for a portable overlay | delete excluded state; export only field-level `MANAGE` allowlisted preferences, default plan-only, and preserve all unmanaged client content |
| Observer shows a model price after the vendor changed it | a concrete model/version and price snapshot was embedded in projection code | accept only provenance-labelled, unexpired pricing facts from Workflow canonical storage; otherwise show unknown/stale and no USD total |

This standard intentionally leaves live global apply, paid smoke tests, external
project writes, agent installation and Open Design mutation in
`WAITING_APPROVAL`/`UNSUPPORTED` until separately authorized and implemented.

> 2026-10-05 技能收敛：本机全局个性化规则使用 personal-guidance.md 的单一文件；只更新技能时运行同步器 --skills-only，保留 config/AGENTS/rules。普通全量 overlay 不应重建已由用户替换的旧 managed block。项目专属说明见 docs/current/workflow-assistance/skill-references/。历史运行记录不代表本次部署。

## 6. Software and model neutral deployment invariants

The machine ownership contract and current native discovery determine the deployment set. Skill counts, software names, model IDs, provider routes, reasoning levels and historical installation paths are snapshots, not universal defaults. Future clients use the same adapter/ownership/evidence boundary rather than copying another client's layout.

Keep one user-global preference and safety source, project-owned differences, native adapters and on-demand specialized skills. A global AGENTS file is a carrier of personal rules, not a competing authority. Do not append a second equivalent policy to a personalized file. Ordinary work does not require forced skill loading, design approval, repeated confirmation, auxiliary paid review or full testing unless the current task/risk/project contract actually requires them.

Before an update or deployment, discover official native configuration and skill/plugin loading surfaces and supported schemas/APIs. Preserve the user's model/provider/reasoning/auth and unknown fields. Choose an overlay by concrete workflow benefit, precise trigger, measured failure coverage and maintenance cost. Generic scaffolding is a merge/retirement candidate; deterministic receipts, ownership and safe transactions remain separate implementation responsibilities. Missing use telemetry means UNKNOWN, never zero use.

Review upstream changes for affected fields, interfaces, loading precedence and behavioral compatibility. Use a narrow plan bound to the actual target and source, back up only the authorized owned assets without collecting credentials or private sessions, apply through the existing adapter, then native readback and an idempotent plan. Runtime/file existence, source equivalence, discovery and behavioral use are separate evidence layers. Unsupported operations stay UNSUPPORTED; skip does not mean supported.

Project guidance stays in its project. Conditional detail stays in references. Retired skills leave active discovery roots after source callers, manifests, provenance and sync ownership have been reconciled. Preserve recoverable originals; user-modified content remains a conflict. Plugin enable/disable/uninstall uses the product's native supported management interface, within explicit user scope; no blanket deletion of caches or internal runtime bridges.

Test the affected migration and failure paths, including preservation of unrelated config, path isolation, concurrent edits, negative controls, backup and readback. Use real/disposable task comparisons to assess success, unnecessary prompts, context and elapsed time. New models may justify simpler prompts; they do not remove permission, data, ownership or evidence boundaries. Never invent a global skill-count ceiling or declare an improvement from a smaller file alone.

The 2026-10-05 event record is `docs/history/archive/workflow-convergence-20261005.md` (non-normative). Read current source/contracts first; use that record only for the explicitly relevant repair, rationale or recovery question. It grants no future native write, paid call or publish permission.