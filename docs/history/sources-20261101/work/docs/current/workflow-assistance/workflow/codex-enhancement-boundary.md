# Codex Enhancement Responsibility and Capability Boundary

> Contract ID: `workflow-assistance.codex-global-enhancement`
>
> Status: `BOUNDARY_CONTRACT`

## One-sentence definition

The Codex enhancement module is a **repository-controlled, secret-free user
overlay** for the official Codex configuration surface. It is not Codex
itself, not a provider gateway, not an agent runtime, and not a second project
control plane.

The machine-readable authority is:

```text
config/codex-enhancement-boundary.json
```

## Responsibility

The module owns only:

1. The managed Workflow Assistance block in the Codex user `AGENTS.md`.
2. One managed command policy file:
   `$CODEX_HOME/rules/workflow-assistance.rules`.
3. Fourteen explicitly named user Skills under `$HOME/.agents/skills`.
4. Three field-level defaults, only when absent:
   `approval_policy`, `sandbox_mode`, and `project_doc_max_bytes`.
5. Plan/apply/verify/rollback readback for those owned assets.
6. Read-only project-local opaque machine identity status and non-sensitive
   profile-digest comparison; this can produce a configuration review plan but
   cannot authorize or apply a configuration change.

The module must preserve all existing user-owned configuration and private
runtime state. If ownership is unclear, it stops rather than guessing.

## Capability matrix

| Operation | Status | Exact responsibility |
|---|---|---|
| Detect | `READ_ONLY` | Check executable availability, target paths, owned hashes, declared state, and redacted Git/Python/Markdown/performance evidence; never inspect credentials, private memory, prompts, responses, or session bodies. |
| Plan | `READ_ONLY` | Produce a redacted action plan, classify preserved fields, and fail closed on conflict or unsafe paths. |
| Apply | `USER_APPROVAL_REQUIRED` | Atomically update only the owned overlay, rules, Skills, and missing field-level defaults. |
| Verify | `READ_ONLY` | Parse entry points, verify markers/hashes/owned Skills, and prove idempotence. |
| Rollback | `OWNED_HASH_FENCED` | Remove or restore only content still matching the recorded ownership/hash. |
| Invoke | `NOT PROVIDED` | The module does not launch Codex tasks, call providers, or perform project work. |

## Explicitly preserved / forbidden surfaces

The module does **not** own or modify:

- provider, model, base URL, routing, quota, or billing;
- authentication, tokens, cookies, private keys, or credential stores;
- MCP servers, plugins, sessions, private memory including
  `$CODEX_HOME/memories`, Desktop state, or sandbox internals;
- project source files, project `AGENTS.md`, Task Ledger, Telemetry Ledger, or
  project Sidecar;
- Git commit, push, PR, merge, release, or external project writes;
- user data outside the declared Codex/Agents managed targets.
- machine identity, account identity, authentication state, hardware
  fingerprints, or device authorization.

The module cannot grant capabilities that Codex or the project does not already
have. A Skill is guidance, not authorization. Project-local `AGENTS.md` and
`.agents/skills` can narrow these rules, but cannot weaken credential safety or
invent evidence.

## Approval gates

| Side effect | Required gate |
|---|---|
| Repository read / local plan | Allowed read-only operation |
| User-home apply | Explicit user request for this exact configuration, reviewed current target-bound `plan_digest`, then CLI `apply --approved --approved-plan-digest <digest>`; the writer rechecks the digest before any write |
| Rollback | Explicit target scope plus ownership/hash fence |
| Git publish | Separate explicit approval; not implied by local apply |
| Live provider or external project write | Forbidden by this module |

## Required evidence

Every real-machine sync must retain only redacted evidence:

```text
plan: status=DRY_RUN
apply: managed field names only
verify: status=PASS, issues=[]
idempotent plan: actions=[], write_set_count=0
Windows: native C:/... path readback
```

Evidence must not contain configuration正文, credentials, tokens, session data,
provider secrets, prompt/response bodies, or private Desktop state.

## Operational rule

When a future request appears to add a new global Codex capability, first place
it into one of these categories:

- **Owned overlay** — may be added only with a contract/test update;
- **Preserved user surface** — observe and retain, never manage;
- **Project-local capability** — keep in project `AGENTS.md`/`.agents/skills`;
- **Forbidden/private surface** — reject and explain the boundary.

No new global capability is valid merely because a script can technically write
it. The JSON contract, tests, ownership mapping, and evidence requirements must
be updated first.

## Cross-machine identity boundary

A separately reviewed project-local workflow may create a random UUIDv4
`machine_id` in ignored project runtime state; this script only plans and
compares it with an explicitly reviewed project registry. This is an
installation label, not proof of the user, account, login, device ownership, or
authorization. It must not be derived from hardware identifiers, usernames,
paths, credentials, tokens, provider state, or private desktop/session state.

The only supported outcomes are read-only review states such as
`IDENTITY_NOT_INITIALIZED`, `NEW_MACHINE`, `KNOWN_MACHINE`, and
`CONFIGURATION_REVIEW_REQUIRED`. A new machine or changed profile may trigger
`plan/verify`, but never automatic `apply`, authentication changes, Reset/Repair,
provider routing changes, or writes to OBSERVE/SECRET fields. See
`docs/current/workflow-assistance/workflow/machine-identity-and-config-review.md` and
`services/authority/machine_identity.py`.
