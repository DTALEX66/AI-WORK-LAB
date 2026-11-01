# WORK-LAB ATLAS GAP REMEDIATION — SUBORDINATE TASK CARD (2026-10-01)

**Card ID:** `WORK-LAB-ATLAS-GAP-REMEDIATION-TASKCARD-20261001`
**Card class:** subordinate current task card (planning + verified-gap record)
**Parent authority:** `WORK-LAB-AUTHORITY.md`
**Current TaskPack:** `WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918` (unchanged, still the only CURRENT)
**Single live register:** `taskpacks/current/OPEN-TASK-REGISTER.md`

> This card is a **subordinate planning record**. It is **not** a second CURRENT taskpack, and
> it **does not authorize** execution, push, merge, release, deployment, global configuration
> writes, tool installs, model downloads, paid calls, or changes to the other two projects.
> Execution of any row below stays **individually authorized** by the user per operation, and
> every row is **not executed** until that authorization exists. Authority continues to flow only
> from `WORK-LAB-AUTHORITY.md` through `project-authority-index.json` and the single CURRENT
> TaskPack; this card adds no authority of its own.

## 0. Provenance and verification basis

| Item | Value |
|---|---|
| Live `origin/main` commit (this card) | `cd4daa83e107afab8438c0e85f63a10e75314d5a` |
| Live `origin/main` tree | `a36e97ecbcb951e53a4c877e14244aa626d70fc8` |
| Card working branch | `task-decomposition/atlas-gap-archive-20261001` (off `ec275a39cf1d078691bfb6ced640ddae7ba4841c`) |
| Research snapshot | `WORK-LAB_MASTER_ATLAS_2026-09-29.zip` (extracted read-only, never overlaid onto the repo) |
| Snapshot reference main | `3a98384a14c8af65e3360e2d6e85a3fe3bca3c35` / tree `45067cd8ac4f1f381c82e3036f22e0b2f95566f5` |
| Snapshot vs live delta | **3 commits ahead**: `660b294` (#160 external audit package), `d424236` (#159 GitHub delivery fail-closed), `cd4daa8` (#161 delivery-identity incident) |
| Snapshot target-file identity | `model_capability_resolver.py`, `acp_adapter.py`, `provider-registry.json`, `runtime-registry.json`, `model-registry.json`, `config/adapter-registry.json` are **byte-identical** between snapshot and live (verified via git object store, not filesystem hashing) |
| Historical completeness | **PARTIAL** — original long conversation, project Summary, and the 9/28 two named files remain unavailable; "not found" is **not** evidence of "deleted" |

The snapshot is a research snapshot. Its *proposed* next taskpack
(`WORK-LAB_NEXT_EXECUTION_TASKPACK.md`, AT-00..AT-10) was **never adopted** by
`taskpack-authority-index.json`. This card therefore re-labels those candidate lanes onto the
**existing** authority surface (the `U*` rows of the CURRENT TaskPack + this card) instead of
promoting a new taskpack.

## 1. Snapshot-vs-live delta table (required disposition)

| ID | Prio | Snapshot status | Live re-check (2026-10-01, `cd4daa8`) | Disposition |
|---|---|---|---|---|
| G01 | P0 | BLOCKED | Still unavailable in any authorized source | **STILL EXISTS** — blocked, not deleted |
| G02 | P0 | REPRODUCED_SYNTHETIC | **REPRODUCED IN LIVE CODE** — `model_capability_resolver.py:72-88`; after an explicit pick succeeds, control falls through into the overlay loop and can overwrite `selected` | **STILL EXISTS** |
| G03 | P0 | REPRODUCED_SYNTHETIC | **REPRODUCED IN LIVE CODE** — `_usable()` (`:125-137`) never inspects `required_capabilities`; the explicit path (`:74`) and the overlay path (`:85`) both bypass the capability gate that only the scan path (`:96`) applies | **STILL EXISTS** |
| G04 | P1 | REPRODUCED_SYNTHETIC | **REPRODUCED IN LIVE CODE** — `_session_affinity()` (`:152-154`) uses builtin `hash()`, which is salted per process | **STILL EXISTS** |
| G05 | P0 | STATIC_CONFLICT | **CONFIRMED** — `providers[6].binds_to_model = "qwen2.5vl-7b"` while active model id is `qwen2.5-vl-7b-instruct` (`previous_entry.id` holds the stale name only); `local.fast.legacy` / `local.code.default` carry `operationalStatus: "OPERATIONAL 2026-09-29"` while their `status_note`/`standby_reason` describe weights that are NOT served; ASR/standby sha256 values are truncated prose, not full digests | **STILL EXISTS** |
| G06 | P1 | CODE_PRESENT_NOT_NATIVE | **CONFIRMED** — `acp_adapter.py` base implements NEW/RESUME/PROMPT/CANCEL/FORK as `NOT_IMPLEMENTED` (`:169-209`); among `codex_adapter.py`, `dsh_adapter.py`, `hermes_adapter.py` **only** `hermes_adapter.py:128` overrides `new`, and it calls `super().new()` (i.e. it inherits the `NOT_IMPLEMENTED` result and only tags a session id when `res.ok`) | **STILL EXISTS** |
| G07 | P1 | BLOCKED | No new evidence in the 3 delta commits | **STILL EXISTS** |
| G08 | P1 | BLOCKED | No new evidence in the 3 delta commits; MSVC/Rust toolchain still absent locally | **STILL EXISTS** |
| G09 | P1 | PLANNED | Card `WORK-LAB-PRODUCT-UI-CONTROL-SURFACE-TASKCARD-20260925` still a planning record | **STILL EXISTS** |
| G10 | P1 | BLOCKED | `MODEL-RUNTIME-HANDOFF-20260929.md` §1 still records router/consumer as BLOCKED | **STILL EXISTS** |
| G11 | P1 | PARTIAL | Rerank remains binary-only (LM Studio has no `/v1/rerank`, no logprobs) | **STILL EXISTS** |
| G12 | P1 | PARTIAL | OCR matrix single-page only; ASR not re-tested this round | **STILL EXISTS** |
| G13 | P2 | UNKNOWN | Unchanged | **STILL EXISTS** |
| G14 | P1 | STATIC_DRIFT | Unchanged in the 3 delta commits | **STILL EXISTS — NEEDS RE-VERIFY at fix time** |
| G15 | P1 | STATIC_DRIFT | `config/adapter-registry.json` unchanged; Hermes registry version vs live `0.21.5+3115.g10938a7` drift unresolved | **STILL EXISTS** |
| G16 | P2 | UNKNOWN | Unchanged | **STILL EXISTS** |
| G17 | P2 | DEFERRED | Unchanged | **STILL EXISTS (deferred)** |
| G18 | P2 | OWNER_DECISION_NEEDED | Unchanged | **STILL EXISTS (owner decision)** |
| G19 | P2 | OWNER_DECISION_NEEDED | Unchanged; weight/artifact deletion still unauthorized | **STILL EXISTS (owner decision)** |
| G20 | P1 | NOT_RELEASED_CURRENT_SHA | Unchanged | **STILL EXISTS** |
| G21 | P2 | UNKNOWN | `d424236` (#159) hardened GitHub delivery helpers fail-closed, but the user's own Windows push health was not re-tested | **PARTIALLY ADDRESSED — user-side still UNVERIFIED** |

**Superseded by upstream:** none of the listed defects were fixed by the 3 delta commits. The
delta commits touched GitHub delivery scripts, the external audit package, LESSONS_LEARNED, the
error ledger, and `tests/workflow-assistance/test_github_delivery.py` — **no overlap** with the
P0/P1 defect files, which are byte-identical to the snapshot.

## 2. Work breakdown (execution lanes)

Each lane lists: scope, files, acceptance, rollback, and the **evidence level this card claims**
(never higher than what has actually been produced). This card produces **PLAN** only.

### Lane A — Contract & pure-function repair (no network, no install, no config write)

| Task | Prio | Scope / files | Acceptance (fail-closed) | Evidence now |
|---|---|---|---|---|
| **AG-01** Explicit-choice precedence | P0 | `packages/client-neutral-core/scripts/model_capability_resolver.py` — make an explicit user pick terminal: on success return immediately; never fall through to the overlay loop | A test where explicit pick ≠ overlay pick asserts `selected.candidate == explicit`; overlay must not overwrite; rejection of an unusable explicit pick still returns `BLOCKED` with the specific reason and **no** silent substitution | PLANNED |
| **AG-02** Unified capability gate | P0 | same file — apply `required_capabilities`, privacy, and availability checks on **every** entry path (explicit, overlay, scan) | Explicit OCR request against a text-only model returns `BLOCKED` + `MISSING_CAPABILITY`; overlay candidate missing a required capability is rejected with a reason code, not silently chosen; `code.write` non-primary rejection still holds on all paths | PLANNED |
| **AG-03** Stable session affinity | P1 | same file — replace builtin `hash()` with a documented stable digest (e.g. `hashlib.sha256`) over `(task_family, model_id)` | Affinity identical across `PYTHONHASHSEED=0/1/2/3` and across separate processes; regression test spawns subprocesses with differing seeds and asserts equality | PLANNED |
| **AG-04** Health/resource gate truth | P1 | same file — `runtime_health` / `resource` are currently accepted in `__init__` but never consulted; either implement the gate or declare the parameters explicitly unsupported | Either a real health/resource gate with tests, or an explicit documented statement that these inputs are advisory-only. No dead parameter may imply a gate that does not exist | PLANNED |
| **AG-05** Registry foreign-key closure | P0 | `.project/governance/provider-registry.json` (+ `model-registry.json` if needed) — reconcile `local.ocr.default.binds_to_model` to the live model id; resolve the `operationalStatus` vs `status_note` contradiction for `local.fast.legacy` / `local.code.default`; replace truncated sha256 prose with either a full 64-hex digest or an explicit `sha256: null` + reason; express the faster-whisper / sherpa-onnx **process-library** runtimes distinctly from HTTP servers | Every `binds_to_model` resolves to an existing model id; no field simultaneously claims OPERATIONAL and NOT-served; every sha256 is 64-hex or explicitly null with a stated reason; a validator test enforces each rule and **triggers no download and no global config write** | PLANNED |
| **AG-06** Adapter honesty matrix | P1 | `services/execution-federation/acp_adapter.py` + `codex_adapter.py`, `dsh_adapter.py`, `hermes_adapter.py` + `config/adapter-registry.json` | Each of the 5 ACP operations reports per-executor `declared / implemented / probed / native_verified` separately; an `unsupported` operation **never** returns success; `hermes.new` no longer counts as native execution while it delegates to the base `NOT_IMPLEMENTED` | PLANNED |
| **AG-07** Registry drift closure | P1 | `config/adapter-registry.json` — add `verified_version` / `declared_range` / `source` / `observed_at` per client | Hermes entry reflects the live `0.21.5+3115.g10938a7` with a source handle; DSH entry distinguishes official Harness vs community Desktop vs user entry point; no field silently upgrades an UNVERIFIED detection | PLANNED |

### Lane B — Environment preflight (read-only, zero modification)

| Task | Prio | Scope | Acceptance | Evidence now |
|---|---|---|---|---|
| **AG-08** Windows toolchain read-only preflight | P1 | Detect and record existing Node / Python / Rust / MSVC / WebView2 / Git / `gh`, actual paths and versions; separately diagnose Git identity, remote, credential availability, network, permissions | Detection results match real command paths; missing tools produce a **minimal** gap list; **nothing is installed**; credentials are never printed | PARTIALLY DONE in this session (see §4) |

### Lane C — Real execution & consumer acceptance (authorization-gated)

| Task | Prio | Blocker / prerequisite | Acceptance | Evidence now |
|---|---|---|---|---|
| **AG-09** Real dual-executor golden chain | P1 | Needs user-selected project + two executors + existing authorization; corresponds to existing open row **U18** | Two executors each produce a **native** receipt; revision / cancel / restart / receipt / completion on one task chain; cancel writes nothing further; restart does not duplicate side effects | NOT_RUN (blocked) |
| **AG-10** Model consumer acceptance | P1 | Needs a named real consumer with permission; corresponds to existing open rows **U18/U19** and handoff §7 | FAST / DEEP / embedding / rerank / OCR / ASR each invoked from a real consumer, recording input hash, requested vs resolved model, runtime, quality, latency, usage | NOT_RUN (blocked) |
| **AG-11** Full OCR / ASR matrix | P1 | Weights already present; no download authorized or needed | zh / en / mixed / PDF / scanned / table / page-order for OCR; real audio with timestamps for ASR | NOT_RUN |
| **AG-12** Rerank quality decision | P1 | **OWNER DECISION NEEDED (OD03)** — is binary filtering sufficient, or are continuous scores required? | If scores required, the retained llama.cpp path is used on demand; LM Studio stays the main path; no re-install | NOT_RUN (needs owner) |
| **AG-13** Unattended / not-logged-in service | P2 | **OWNER DECISION NEEDED (OD04)** — is logon-time long-running enough, or is a true session-0 service required? | Only if required: native Windows verification with a deployment plan; current logon-based recovery must not be described as a service | NOT_RUN (needs owner) |

### Lane D — Formal UI & super entry

| Task | Prio | Scope / files | Acceptance | Evidence now |
|---|---|---|---|---|
| **AG-14** Product UI convergence | P1 | `apps/observer/frontend` (React/TS) + `apps/observer/src-tauri` — reuse existing tokens/components and the 7-group IA; do **not** create a second frontend system | Real Windows launch; empty / failed / unknown / long-text / cancelled / recovering states; keyboard & a11y; navigation persistence; wires to real data and **controlled** actions | **B10 1:1 replication COMPLETE AND MERGED** (PR #143 `612d5aa` + PR #144 `9ffb0c5`); `skins/b10.css` + `skins/l10b-shell.css` imported; pixel layer VERIFIED per the merged `VISUAL_QA_REPORT`. Local re-run 2026-10-01: tsc 0, vitest 72/72, vite build 0. **Still NOT_RUN:** native Windows/Tauri desktop E2E. Remaining real gap is **backend projection** (`approvals[]`, `software[]`, `workspace.plan.tasks`), not UI wiring — see `reports/FRONTEND-AUDIT-20260926.md` §0 |
| **AG-15** Control Surface (thin shell) | P1 | Separate controlled-action API; Observer stays strictly read-only | Every execute / approve / retry / cancel / apply / rollback action goes through the approved control plane; Observer exposes none | PLANNED (card `...-PRODUCT-UI-CONTROL-SURFACE-TASKCARD-20260925`, feature scope frozen) |
| **AG-16** Super-entry first chain | P2 | ContextEnvelope → PlanningCandidate → check/authorize → user-selected executor → Receipt | Planning output never auto-authorizes execution; context / permission / hash closure; bad candidates fail closed | PLANNED |
| **AG-17** Web-GPT transport decision | P2 | **OWNER DECISION NEEDED (OD02)** — structured manual handoff first, official Remote MCP later | Manual structured handoff may be verified now; no DOM scraping, cookie reuse, or private-session forwarding; remote auth must not copy the loopback unauthenticated model | NOT_RUN (needs owner) |
| **AG-18** WORK-LAB thin entry vs DESIGN-LAB Launcher | P2 | **OWNER DECISION NEEDED** — boundary between the WORK-LAB thin entry and the DESIGN-LAB Launcher | Recorded conflict only; WORK-LAB must not absorb the design workbench | NOT_RUN (needs owner) |

### Lane E — History recovery (independent, never blocks Lane A)

| Task | Prio | Scope | Acceptance | Evidence now |
|---|---|---|---|---|
| **AG-19** Missing originals recovery | P0 (historical) | Seek: `WORK-LAB完整项目对话与时间线汇报.md` (15,558,839 B / 432,344 lines), `WORK-LAB-SUMMARY.md`, the 9/28 startup prompt and final execution doc. Search by content keywords and renamed copies inside prompts, chat bodies, pasted text, attachments and archives — not by formal filename only | Each recovered item verified by bytes / lines / hash against the historical manifest; incremental extraction only; no concluded rewriting | PARTIAL — this session has **no ChatGPT history access**; not claimed as searched there |
| **AG-20** Source registry increments | P1 | Record each new source's path, time, hash, original location, and coverage relation | New sources appended without mutating frozen historical records | PLANNED |

## 3. Explicit non-goals (this card grants nothing)

Three-repo merge; shared business database; modifying the other two projects' truth files;
bulk tool re-installation; Ollama re-installation; automatic model download; deleting history or
old weights; global Codex/Hermes/DSH configuration rewrite; making Orca or Mission Control the
default host; forcing Hermes as the primary executor; private web-session bridging; default paid
models; automatic release. Each of those, if ever wanted, requires its own specific
authorization with impact and rollback.

## 4. Read-only environment facts already observed in this session

AG-08 is **complete** as a read-only sweep; nothing was installed. Note the three-way
distinction that a PATH check alone gets wrong: *on PATH*, *off PATH but working*, and
*broken/partial*.

| Fact | Observed value | Note |
|---|---|---|
| Repo root | `D:\All projects\WORK-LAB` | single checkout; no second copy in the working tree |
| Remote | `git@github.com:DTALEX66/WORK-LAB.git` (SSH, scp-style) | `git ls-remote` and a real `git fetch origin --prune` both succeed |
| Live `origin/main` | `cd4daa83e107afab8438c0e85f63a10e75314d5a` | matches local `main`, `0 / 0` ahead/behind |
| Git identity | `DTALEX66` + GitHub noreply email | set at BOTH global and local layers |
| Git credential | only `credential.helper=manager` at the **system** layer (GCM) | irrelevant to an SSH URL; global/local helpers empty; `GIT_ASKPASS` and `SSH_AUTH_SOCK` empty and `ssh-agent` stopped, yet fetch works |
| Git network | DNS `github.com` → `20.205.243.166`; TCP 22 reachable on `github.com` and `ssh.github.com` | read route proven; **write permission UNVERIFIED** (no push attempted) |
| On PATH | `git` 2.54.0.windows.1 (`C:\Program Files\Git\cmd\git.exe`), `gh` 2.98.0 | |
| Off PATH but working | Rust **GNU** toolchain `rustc`/`cargo` **1.97.1** (`~/.rustup/toolchains/stable-x86_64-pc-windows-gnu/bin`, both exit 0); Node **v24.21.0** (DSH-bundled) and v24.19.0 (codex-runtime); project Python `.project-local/toolchains/wl-py311` (3.11.15 + `yaml 6.0.3` + `jsonschema 4.26.0`) | the declared Python toolchain satisfies the canonical gate contract; use it, never the bare bundled runtime |
| Broken / partial | Rust **MSVC** toolchain has `cargo 1.98.1` but **no `rustc.exe`**; **no Visual Studio and no VC tools** (`vswhere` returns nothing, no `VC\Tools\MSVC`); `~/.cargo/bin` absent; shared `venv312`/`venv313` trampolines broken | the MSVC toolchain cannot compile, and with no VC tools it would have no linker even if complete |
| Absent | `npm`, `pnpm`, `yarn`, `cmake`, `ninja`, `msbuild`, `dotnet`, `python`/`py` on PATH | |
| Rust build blocker | `cargo check --offline` in `apps/observer/src-tauri` fails: `no matching package named 'tauri-plugin-log' found` | the shared CARGO_HOME registry (`…\10-toolchains\rust\cargo`) does not carry every locked dependency; a Rust build needs an approved network fetch or a vendored cache |
| Frontend gates | **runnable without npm** against the existing `node_modules` | `tsc --noEmit` exit 0, `vitest run` **72/72**, `vite build` exit 0 (`dist/` is gitignored; tree stayed clean). "No npm" blocks *installing* deps, not *running* the gates |
| Shared library roots | present | `external-libraries-index.json` registers `os-external-toolchains` → `D:\All projects\OS External Configuration\10-toolchains` plus a `uv-cache` |
| WebView2 runtime | 154.0.4258.37 | the render engine for the Tauri shell |
| Uncommitted user work | 4 modified files + 1 untracked path | preserved untouched — see §5 |

## 5. Working-tree protection notice

At card-creation time the checkout carried user changes that this card **does not touch**:

- modified: `.project/governance/generated/CURRENT_STATE.json`, `.project/governance/generated/CURRENT_STATE.md` (regenerated timestamp only)
- modified: `apps/observer/frontend/src/App.tsx`, `apps/observer/frontend/src/components/layout/Sidebar.tsx` (comment-only additions referencing a frontend taskpack)
- untracked: `docs/future/WORK-LAB-SUPER-ENTRY-COMMAND-CENTER-LAB-ROUTER-2026-09-27.md` — deliberately untracked (its JWT/OAuth2/Vault section conflicts with the no-auth rule)

No `reset --hard`, no `clean`, no branch switch away from a dirty tree.

## 6. Reporting contract per executed row

`task_id`, `project_id`, `authority_snapshot`, `base/head SHA`, `executor identity/version`,
`requested/resolved model` (where applicable), `scope/permission/budget`, `changed paths`,
`test commands/results`, `evidence level`, `native handles/readback`, `CI exact SHA`,
`remaining gaps`, `rollback handle`, `owner decisions`. Never record API keys, secrets, or
private session bodies.

Status vocabulary stays strict and separate:
`PLAN` ≠ `CODE_IMPLEMENTED` ≠ `TEST_PASS` ≠ `EXACT_SHA_CI` ≠ `NATIVE_RUN` ≠ `USER_ACCEPTED` ≠ `RELEASED`.
Anything not performed is written `NOT_RUN` / `UNKNOWN` / `BLOCKED` — never as a completed item,
even when CI is fully green.

## 7. Rollback

This card is an additive documentation record. Rollback for this card is a single `git revert`
of its commit (card + the register row + the `currentTaskCards[]` entry) — no runtime, model,
global-config, or data side effects exist to unwind.
