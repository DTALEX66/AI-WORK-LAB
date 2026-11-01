---
name: project-gap-analysis
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/project-gap-analysis/SKILL.md
---

---
name: project-gap-analysis
description: "Evaluate a codebase's current state against its own design specifications — read design docs, audit source code + tests, cross-reference acceptance criteria, produce prioritized gap analysis with actionable roadmap."
version: 1.3.1
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [project-audit, gap-analysis, design-review, code-review, roadmap, planning]
    related_skills: [plan, codebase-inspection, systematic-debugging]
---

# Project Gap Analysis (Design vs Implementation)

A structured workflow for evaluating how much of a project's design/spec has actually been built. Produces a prioritized roadmap of what's still needed.

## When to Use

- User asks "分析后续列表" / "分析项目现状" / "gap analysis" / "what's next"
- A project has design docs (GAME_DESIGN.md, SPEC.md, ARCHITECTURE.md, etc.) and you need to see what's been implemented vs what's only designed
- Before starting a new feature — establish a baseline of what's done vs not done
- After cloning a new repo — understand its maturity at a glance
- User asks "有可用开源项目吗" / "搜集可用的" — search existing solutions before coding (see Step 5)

## Workflow

### Step 1: Read Design / Specification Documents

#### Large attachment completeness gate

When the user supplies a large Markdown/TaskPack attachment, do not infer that it was fully read from a rendered preview or a truncated tool result. Read the canonical project-local file directly, record byte size and line count, enumerate all headings/task IDs, and verify that the final section is present before producing the analysis. If a high-level reader labels UTF-8 Markdown as binary or the response is interrupted, use a read-only UTF-8 byte decode and structural scan (headings, task IDs, final decision section) as the recovery path. Do not claim completion from the first half; resume from the exact unread boundary and deliver one complete analysis. Treat the attachment as an execution input, not proof that any task is implemented.

#### Canonical project positioning and external-boundary freeze

Before auditing or publishing, freeze the canonical repository root, allowed module roots, branch/HEAD, remotes and current status. Re-read the root README and AGENTS/project rules before acting. Treat a user correction such as “重新载入项目定位” or “项目飘逸” as a hard reset of scope: reconcile every proposed artifact against the canonical project identity and non-goals before editing or pushing.

Keep external platform/runtime repositories separate from the project. An external Hermes source checkout, Hermes Home, Gateway, credentials, sessions, cron, provider state, skills/plugins and caches are not automatically project content. Do not publish them to the project's remote merely because the current debugging task used them. If a user asks to “撤回官方推送、推送到本项目仓库”, first verify whether an official push actually exists; a local external commit is not evidence of a remote push. Publish only project-owned tracked changes, then verify exact remote SHA, default branch and exact-SHA CI.

Identify and read the project's authoritative design files:

```text
Common names:
  README.md          — project overview, goals, acceptance criteria
  GAME_DESIGN.md     — game/product design spec
  PROJECT_CONTEXT.md — single source of truth for direction/constraints
  WORKFLOW.md        — dev process and rules
  ARCHITECTURE.md    — technical architecture
  SPEC.md / SPECS/   — feature specifications
```

Use `search_files(target='files')` with patterns like `*DESIGN*`, `*SPEC*`, `*CONTEXT*`, `*ARCH*` to find them.

### Step 2: Audit Source Code

Read all source files to understand actual implementation:

```text
Sources to check:
  src/ or lib/      — core logic
  index.html, App.* — entry points
  styles.css, *.css  — styling
  tests/ or __tests__/ — test coverage
  README.md / platform README / handoff docs — public entrypoints and operator instructions
```

Key questions for each source or doc file:
- What does this module or document actually do?
- What's hardcoded vs configurable?
- What edge cases are handled?
- Do public docs mention the current verified commands/features, or are they stale?
- Are release/publishing instructions separated from development verification so placeholders do not block local work?
- Does a runtime registry snapshot configuration at module import, making later configuration/skin loading ineffective?
- Do all claimed platform runtimes actually import storage, analytics, ads and lifecycle services, or only the browser entry?

#### Read-only audit discipline

**Prerequisite: Verify checkout integrity before any audit step.** Confirm `.git/` exists, `git rev-parse HEAD` succeeds, and source files are present (`.py`, entry HTML/JS, or project-declared key files). If only `.hermes/` runtime data remains with no `.git/` and no source tree, the checkout has been destroyed — block immediately rather than producing a baseline from phantom state.

**Resuming from blocked state**: When the audit starts after a previous actor left `state.json` in `mode=blocked` with `stop_reason` claiming `project_checkout_destroyed`, do **not** accept that claim without independent verification. Previous cron cycles or agent sessions can produce false positives — their `stat()`/`os.listdir()` calls can return phantom negatives under path-resolution races, MSYS/WSL path-prefix mismatches, or a workdir that made `.git/` invisible. Always run `git rev-parse --git-dir` and check key source files yourself. If those succeed, the blocked state was a false positive; record the correction and continue. A verifiably intact checkout voids the preceding cycle's blocking claim, not the project data.

When the user forbids modifications, do not assume `test`, `verify`, `inspect`, or `release:check` is read-only. Before running repository commands:

1. Capture branch, HEAD and `git status --short`.
2. Inspect package scripts and relevant tests for build invocations, `writeFile`, generated outputs, temp directories and cleanup behavior.
3. Prefer genuinely read-only checks. Use an isolated copy/worktree and temporary data root for commands that rebuild tracked artifacts or write repository-local SQLite databases, vector indexes, task ledgers, caches, or reports—even when tests later clean up their own rows.
4. Re-check `git status`, `git diff --stat`, and HEAD after every command batch.
5. Restore only changes proven to have been caused by the audit and verify the final tree matches the baseline.
6. If files appear or change concurrently, do not touch, read, execute, or attribute them to the audit. Classify every capability as **committed HEAD**, **uncommitted/concurrent WIP**, or **missing**. An untracked file that appears mid-audit is not stable implementation evidence and must not be reported as already absorbed/released. Continue against the frozen commit/tree object; explicitly name the concurrent path in the report, but do not use it to design or validate the baseline unless the user separately authorizes review of that WIP.
7. Gate results belong to the exact tree on which they ran. If concurrent edits follow a green lint/test result, rerun the read-only gate or label the earlier result as baseline-only.
8. Distinguish a Git **tree object** from a commit before using “Exact-SHA CI” language. `git write-tree` may identify an exact staged snapshot, but a tree has no branch, author, parent, or CI run. A tree-only snapshot can be audited with `git show <tree>:<path>` and `git grep <tree>`, but it cannot have commit-addressed GitHub Actions evidence until it is committed.
9. For a staged-tree audit, capture `git write-tree` at both start and finish. If the value changes during the audit, treat that as concurrent index drift, compare the two trees read-only, and continue reporting only against the originally requested tree. Never reset or restage to recover the baseline.
10. Prefer read-only execution directly from the Git object when possible—for example `git show <tree>:path/to/app.js | node --check`. This validates the requested object without checking it out or trusting a concurrently changing working tree.
11. Once concurrent WIP appears, derive all baseline metadata from the frozen object as well as baseline file contents: hash `git show <commit>:<path>` rather than the live path, parse versions/lock metadata from that stream, and keep worktree hashes only as explicitly labelled WIP evidence. A clean status captured at task start does not make later worktree reads baseline-safe.

A validation command that regenerates bundles, initializes schemas, or writes runtime data is still a mutating command. In a strict no-write audit, static code/test inspection may be the strongest safe evidence; state explicitly that tests were not executed rather than creating caches, databases, reports, logs, or media artifacts. Leftover pytest databases, cache directories, or test-named temporary files prove only that a test started; without command, exit code, summary, and exact object identity, they do not prove a green gate.

### Network-backed capture and verification completeness

When an audit tool fetches a page plus linked stylesheets/assets, separate **transport success** from **evidence completeness**. A successful HTML fetch with one failed stylesheet, a Playwright page that timed out during navigation, or a report generated from only inline CSS is partial evidence—not a clean pass.

Use this reusable sequence:

1. Inventory every linked/secondary resource before interpreting the result; keep `failed`, `skipped`, and `loaded` handles separately.
2. Make the default path fail closed when any required resource fails. Do not silently continue and emit a normal-looking screenshot, token file, or drift report.
3. If partial operation is genuinely useful, require an explicit opt-in flag such as `--allow-partial`, mark the output metadata/status as incomplete, list failed resources, and prevent that artifact from satisfying a release or current-truth gate.
4. For browser capture, close the browser/context on navigation failure before raising; otherwise a failed page can leave both misleading artifacts and leaked processes.
5. Add negative-control tests for: page succeeds + linked resource fails, default command exits non-zero with no misleading output, explicit partial mode records incompleteness, and browser navigation failure closes resources.
6. Re-run the exact project test launcher and update documented test baselines when the new regressions change counts. Keep structural/test evidence separate from real browser/runtime or human acceptance evidence.

The compact implementation/test pattern is in [`references/network-backed-evidence-boundaries.md`](references/network-backed-evidence-boundaries.md).

### Step 3: Cross-Reference Acceptance Criteria

Extract explicit or implicit acceptance criteria from the design docs. Create a checklist:

#### TaskPack identity gate before implementation

When a repository has a task matrix, reconciliation document, handoff, and one or more local task-pack archives, do not trust matching task IDs or prose labels as sufficient identity. Before coding against a task ID:

1. Confirm the claimed authority archive exists at the referenced path; if it is absent, mark the authority unresolved rather than substituting the nearest ZIP.
2. Hash the archive and inspect its manifest/version/task graph without executing or broadly extracting its contents.
3. Read the machine-readable task cards and compare the task ID's title, acceptance, allowed paths, forbidden paths, and status with the tracked matrix/reconciliation.
4. Record contradictions as a task-pack identity blocker. Do not implement against the convenient label, silently rename IDs, or infer that a stale historical matrix defines the current task.
5. Keep the audit evidence under the project's ignored `.hermes/task-artifacts/` boundary; do not upload local attachment paths or private workstation details.

A clean Git tree and green historical gates do not resolve a task-pack identity contradiction. Resolve the authoritative archive/manifest first, then select the first dependency-safe implementation slice.

#### Workflow module task-ID reconciliation

For a monorepo audit where a module matrix names `WA-*` (or similar) tasks, treat the matrix as a navigation aid until task identity is proven. First verify the exact requested HEAD and applicable root/module `AGENTS.md`; then check the referenced authority archive and ignored machine-readable assessment. If the archive or assessment is absent, stale, or names a different HEAD/graph, record the authority as unresolved and do not present the task ID's prose acceptance as canonical. Search the frozen source tree for the exact ID: an ID found only in a status matrix is declarative evidence, not an implementation contract.

When the user requests a no-write audit, inventory tests statically (for example, AST-count test methods and inspect fixture/default data roots) but do not run tests that create repository-local runtime directories, caches, ledgers, SQLite/vector stores, browser profiles, or reports. Report the test inventory separately from execution evidence. Freeze concurrent worktree state: an untracked file outside the target module is WIP evidence, not part of the requested HEAD, and a `git write-tree` value is a tree identity—not a commit SHA.

For the first dependency-safe product slice, prefer a local contract boundary that needs no user policy decision: e.g. deterministic candidate intake → validation/classification → project-local quarantine/readback. Keep approval, promotion, live deployment, Git/GitHub delivery, external providers, and release evidence as later slices. Recommend RED→GREEN tests for valid intake, missing fields, digest mismatch, path containment, idempotency/conflict, no external calls, and explicit non-promotion; do not claim the slice is implemented when the repository only contains schemas or fake adapters.

```markdown
| Criteria (from spec) | Status | Evidence | Confidence |
|---|---|---|---|
| Players can see console state | ✅ verified | exercised UI/test output | high |
| Players can click buttons to change state | ⚠️ partial | code present; not exercised | medium |
| At least 5 anomaly types trigger | ❌ gap | only 3 implementations found | high |
```

#### Evidence hierarchy and claim discipline

Use the strongest available evidence and label weaker forms explicitly:

1. **Verified execution** — test/build/runtime output or read-back of a side effect.
2. **Implementation evidence** — actual code path plus usages, not filenames.
3. **Artifact evidence** — generated file/schema exists and is internally consistent.
4. **Declarative evidence** — README, status field, checklist or manually written percentage.

Declarative evidence alone never proves completion. Separate dimensions that can diverge—for example structure, source coverage, processing coverage, accuracy, external verification and human review. Do not collapse them into one "completion percentage". Sampling must be reported as sampling, including exact files/pages/duration.

#### Detailed evidence-surface consistency gate

A top-level capability index or aggregate verifier is not sufficient evidence of a truthful project state. Before closing a gap audit, enumerate the detailed evidence surfaces that feed the same claim: per-case JSON/Markdown records, adapter evidence directories, manifests, status ledgers, generated summaries, and release-gate inputs. Cross-check each declared level against the capability's actual level and current runtime state. A detailed record marked E3 while the capability index says E1 is an active contradiction even if the aggregate verifier passes.

Use this fail-closed rule for every E3/current-runtime claim:

1. Require a full 40-character SHA bound to the audited checkout (not a short SHA or a historical handoff).
2. Require runtime/task identity, artifact provenance, and read-back evidence; implementation text, file existence, or a manifest flag is not runtime proof.
3. Mark old records explicitly as `historical`/`invalidated` and ensure their wording cannot be mistaken for current readiness.
4. Make the canonical verifier scan the detailed evidence directories, not only the index; add a known-overclaim regression fixture/test so the audit catches future drift.
4. Re-run the verifier after commit and after push. Treat a bound ancestor as historical evidence until the exact current commit has its own CI result; record a current exact-SHA CI run separately from prior baseline evidence.

#### Historical-report boundary sweep

Do not protect only a hand-picked list of known report filenames. Scan the complete current report root (normally `reports/*.md`, excluding its boundary README) for E3/E4/E5, runtime-complete, or release-ready wording. Any historical report containing such claims must carry explicit `HISTORICAL SNAPSHOT` and `NOT CURRENT EVIDENCE` markers; otherwise the verifier must fail closed. Add a negative-control regression fixture with arbitrary report filenames so the rule cannot regress into a filename allowlist. Preserve ordinary license/BOM/planning reports that contain no evidence-level or runtime claims. After modifying binary-looking/CJK Markdown, use a byte-preserving first-line insertion or another narrowly scoped edit, then run the boundary audit, targeted verifier tests, aggregate gate, `git diff --check`, exact-SHA CI, and remote SHA readback.

Likewise, when a handoff mentions an expected task graph or document that is absent from the live tree, search for active references before creating anything. If no authoritative file or active reference exists, record the missing authority boundary and use only the live roadmap/manifest/index; never infer or fabricate a task graph from compressed history.

#### Quick evidence verification (3-layer protocol for completed-state claims)

When resuming from a `state.json` that says `mode=completed` (whether from sleep-mode, a previous audit, or a handoff doc), do not accept the claim at face value. Run this 3-layer verification *before* deciding whether work remains:

**Layer 1 — File existence.** Confirm the claimed artifact files actually exist on disk with non-trivial sizes. Use `ls -la` or `git show <tree>:path` for frozen-object audits.

**Layer 2 — Test execution.** Run the *targeted* tests for the claimed tasks, not just the full suite. A full suite may hide regressions behind old cached results or mask uncollected test files. A targeted run proves the evidence is current and the code path is actually exercisable. If pytest collects 0 items on a named test file, check whether it is a standalone script (run via `python tests/test_*.py`, not `pytest`).

**Layer 3 — State consistency.** Verify HEAD, tree, controlled dirty WIP, and baseline values all match the claimed state. No drift means no concurrent intervention: `git rev-parse HEAD` and `git write-tree` must match the recorded baseline.

Only after all three layers pass should you accept `completed` as truthful. If any layer fails — files missing, tests failing/not collecting, HEAD drifted, WIP list mismatched — the claim is stale or overwritten and you must re-audit from scratch.

Pitfall: **pytest collection is not test inventory.** A file named `test_*.py` may be a standalone script (run via `python test.py`, not `pytest test.py`). Running `pytest test.py —collect-only` and seeing 0 items does not mean the file is empty — check the entrypoint convention with `head -5`. A standalone lifecycle/integration script is legitimate test evidence but must be executed directly, not through pytest.

Pitfall: **documented pre-existing failures ≠ regression.** When verifying completed state, if the only failing tests are optional-engine gaps (e.g. markitdown not installed, trafilatura unavailable) that were documented in the original completion evidence, they are not evidence of regression — they are known environmental constraints. Document them, exclude them from the regression count, and confirm the gap count matches the original evidence.

### Registry-backed open-source absorption audits

When the project maintains an open-source registry and the user asks for a **read-only** absorption/provenance design, do not scan, clone, install, or execute candidate projects. Treat the registry as candidate metadata rather than proof of implementation. Build a separate, one-record-per-raw-ID absorption ledger whose actual status is grounded in local code, declared dependencies, adapters, tests, source hashes, and explicit review evidence. Preserve duplicate raw IDs as migration provenance and record canonical aliases only in a view layer. Load [`references/open-source-absorption-ledger.md`](references/open-source-absorption-ledger.md) for the status semantics, required ledger fields, and static validation rules.

#### R0 registry-truth minimum audit

For a bounded R0 audit of two machine-readable registries/ledgers, inspect the **actual JSON shape** before relying on a named schema or documentation claim. Record top-level keys, per-record field union/presence, count, unique raw IDs, ID-set differences, shared-field equality, status distributions, duplicate names, and evidence-path existence. A pair can have perfect one-to-one raw-ID coverage while still having a provenance/schema gap; do not use equal counts as proof of truth. Non-contiguous numeric IDs are not missing records when both sides share the same unique ID set, and duplicate names must remain separate raw records unless an explicit alias/view layer exists.

Keep three dimensions separate: (1) raw identity coverage, (2) governance/provenance field completeness, and (3) implementation evidence. If an existing profile schema describes a different object shape, report the contract mismatch rather than force-mapping fields or calling the data schema-validated. In a no-network/no-install phase, only add fields deterministically derivable from local bytes or existing records—schema version, record count, snapshot hash, uniform empty evidence arrays, and explicit identity cross-checks. Do not infer repository URLs, revisions, licenses, security risk, fixtures, or rollback handles from names or prose; those require external or human evidence.

Use RED→GREEN for the first safe slice: add focused assertions for metadata, ID-set equality, shared-field parity, status parity, unique IDs, duplicate-name preservation, uniform evidence shape, and local evidence-path existence; confirm the new assertions fail against the baseline, then make the smallest data/contract change and rerun them. Under strict read-only rules, inspect these tests and classify them as planned/static evidence when execution would write caches, databases, reports, or other runtime state. For rollback, restore only the audited JSON/schema/test/doc paths from pre-change byte snapshots and verify unrelated concurrent WIP remains untouched.

If the requested local checkout is unavailable but the repository is public, a **remote HEAD static audit** is an acceptable fallback: resolve and state the exact branch commit, fetch only the registry, design matrix, dependency manifests, relevant implementation files, and tests from that revision, then label the result as a remote-source audit rather than a local-worktree audit. Do not clone or create a checkout for a no-modification request. Use the procedure in [`references/remote-open-source-audit.md`](references/remote-open-source-audit.md): exact HEAD → metadata/license chain → manifests/submodules → security and runtime boundaries → release/CI/activity → absorption classification. Keep README marketing claims separate from implementation evidence, and evaluate every transitive candidate's license independently before recommending code absorption.

For every candidate, classify evidence independently:

| Classification | Minimum evidence |
|---|---|
| truly absorbed | declared dependency **and** a reachable real code path; tests strengthen confidence |
| partial / dormant | code path exists but dependency, contract, or test is missing; or dependency exists but is never invoked |
| registry-only gap | registry/matrix mention only; no dependency and no reachable implementation |
| stale or misleading adapter | adapter name/contract claims the project but returns placeholders, delegates to another engine, or cannot be imported from the runtime package boundary |

Never call an optional import or fallback ordering “absorbed” merely because the source file mentions a library. Check the actual import/call, dependency group, public entrypoint reachability, output contract, and focused tests. A module loaded only by a test via `importlib.util.spec_from_file_location`, a monkeypatched provider, or a direct file path is **test-reachable**, not product-reachable; search non-test source for the adapter import/call and trace the real application entrypoint separately. Also detect misleading adapters whose filename names provider X but whose body delegates to provider Y or a generic fallback; classify the named provider as unimplemented and the delegated provider independently. Report duplicate registry records once in the user-facing capability table while preserving their raw IDs in provenance. For each gap, recommend a minimal typed request/result contract, exact implementation path, and a test that proves both success and explicit-unavailable/fallback behavior.

Before executing a focused test in a strict read-only audit, inspect its fixtures and the default data root. A test that invokes migrations, `drop`, `rebuild`, or defaults to a repository-local SQLite/vector index is mutating even if it cleans up. Do not run it in place: report it as static test evidence and recommend an isolated `tmp_path`/temporary-data-root version. If the supplied audit target is an exported snapshot without `.git`, say that commit/working-tree identity is unavailable rather than inventing a baseline.

### Open Design scenario/bundle/atom contract reachability audit

When a repository exposes Open Design-style `scenario`, `bundle`, and `atom` manifests, audit the executable resource path rather than treating JSON presence or a passing manifest checker as runtime reachability. Freeze the requested commit/tree and classify concurrent WIP separately before reading live files. Build this contract graph:

```text
public bundle/entrypoint
  → context.skills / context.atoms / context.assets / schemas
  → installer resource registry and source-closure copier
  → host registration/read-back
  → scenario pipeline stage
  → atom input contract
  → emitted output schema
  → handoff/preflight gate
```

Compare every manifest reference with the installer’s actual managed resource set and copied roots. A bundle that names a scenario which the installer never copies or registers is an unresolved runtime dependency even when local files exist. Require `manifest.name == parent-directory name`, unique IDs, and real file/path checks for local assets; basename-derived atom IDs and symbolic refs alone are insufficient. Check scenario `context` refs separately from pipeline stage refs, because a validator may only validate the latter.

Cross-check atom `inputs` against the required fields and exact names of the output schema consumed by the next boundary. Optional or renamed inputs, or an unvalidated output object, can make an apparently reachable atom produce an unusable handoff. Trace the canonical verifier’s call list and confirm it actually invokes preflight/handoff validators; a synthetic sample with `SKIPPED_OPTIONAL` is not coverage of that path.

Use local-only negative controls without a real Host: in-memory manifest mutation for unknown context refs, missing asset files, duplicate/path-mismatched names, and malformed unreferenced atom JSON; use an isolated temporary handoff fixture for empty files, stale BOM hashes, and schema-invalid records. If the existing verifier stays green, report a false-green validator gap rather than claiming a production failure. Keep static/E1 evidence, isolated synthetic evidence, and real Host/E3 read-back as separate rows.

See [`references/open-design-contract-reachability.md`](references/open-design-contract-reachability.md) for the compact checklist and repro patterns.

### Backend capability audit addendum

For backend-only gap audits spanning contracts, migration, ingestion, Research, Knowledge/Learning/Mastery/Machine Knowledge, runtime/planner, worker/outbox, sync, provider/agent/MCP, observability, and release, use the dependency-ordered evidence model in [`references/backend-capability-queue-audit.md`](references/backend-capability-queue-audit.md).

Record source existence, product/API reachability, persistence/readback, supervised runtime wiring, and release/distribution truth as separate dimensions. A tested `dispatch_once()` is not a connected Worker; a provider contract with an empty route registry is not provider activation; an installer smoke is not a public release. Build stages in dependency order: contracts/migrations → ingestion → Research provenance → governance closed loop → runtime/planner → supervised worker/outbox → provider/agent/MCP → observability → sync → release. Under a no-edit request, inspect test and CI side effects first and report unexecuted gates as unexecuted rather than creating runtime state merely to obtain a result. Every stage must name exact files, missing wiring versus missing code, and a real failure/restart/rollback/readback gate.

### Workspace-shell / local-product audit addendum

When the requested scope includes a browser/desktop Workspace shell, router/service UI contracts, and release truth, audit **product reachability** rather than treating source-file existence as completion:

1. Freeze the requested Git object first (`HEAD`, `git write-tree`, clean/dirty state) and take all completion claims from that object. In a strict read-only review, run only non-writing checks such as `node --check` after inspecting test side effects; do not run migrations, browser smokes, or pytest in place when they create runtime data, SQLite files, caches, reports, or artifacts.
2. Compare navigation inventory with rendered page inventory. A large nav list is not a product surface: enumerate `data-page`/route identifiers and actual `page-*` sections, then trace unknown/hash routing to its fallback. Report unavailable placeholders as intentional information architecture, not delivered functionality.
3. Trace every UI fetch/action to the router and service boundary. Distinguish an API that is technically callable from a usable normal-user contract. If commands require persistence IDs (`package_id`, `unit_id`, `artifact_id`, `command_id`) or return payload/internal event IDs, the missing slice is a server-owned product projection plus scoped opaque action reference—not a frontend that reads SQLite or exposes the IDs.
4. Check runtime reachability independently from module and unit-test evidence. A dispatcher/consumer may have well-tested `dispatch_once()`/handler code but remain dormant if no CLI, lifespan, supervised loop, or desktop startup path imports and runs it. Classify this as **implemented but not product-wired**, preserving a truthful `not_implemented` release capability until lifecycle, recovery, and product verification exist.
6. Reconcile README, status/handoff docs, prototype docs, manifest capability values, package version, CI gates, wheel contents, and desktop installer smoke. A document may be stale in either direction: it can claim absent code is available, or call tested-but-unwired code wholly absent. State which dimension each source proves. For homepage/product-positioning audits, treat a direct contradiction inside one public README (for example, “CI green” beside “Windows gate pending”) as a product-truth P0 until the wording is split into exact dimensions.
7. For exact-SHA claims, query the live CI provider for the current `HEAD` and record `headSha`, overall status/conclusion, and per-job status. Never use a successful run on an older SHA as proof that the current HEAD is green. If an older successful SHA is relevant, compare `git diff --stat <successful-sha>..HEAD` and label it explicitly as prior-SHA evidence; a current `in_progress` run is not green evidence even when all completed jobs are successful.
8. Split capability truth into at least five dimensions: source/module exists, reachable product route, on-demand/manual operation, continuously supervised worker/runtime wiring, and public release/distribution. Reconcile these dimensions across implementation code, service component projections, UI actions, release manifest, and docs. In particular, distinguish an on-demand Outbox dispatcher from a connected asynchronous Worker, and a CI-built NSIS artifact from a public installer/release. Do not report a capability as wholly missing when the narrower on-demand path is real; report the actual missing runtime or release boundary instead.
9. Use `git log -1` per authoritative status/manifest/UI file to identify documentation freshness, but do not treat file age alone as proof of staleness. The decisive evidence is a live contradiction between the document and current code/manifest/CI behavior.
10. Produce a dependency order that starts with a user-safe contract, then the smallest real vertical UI path, then runtime wiring, then docs/manifest truth. Do not recommend filling every navigation placeholder or adding SSE/remote queues merely to make a shell look complete.

#### Runtime/Profile/platform documentation drift

When sequential merges change the Python support floor, configuration Profile layering, or Windows/Linux/WSL evidence, audit the merge sequence rather than only the final prose. Query every cited CI run's live `headSha` and distinguish current-HEAD push evidence from prior PR-head evidence; check which Python versions apply to the test matrix versus lint/wheel/browser lanes; trace configuration precedence from the loader and package data; and keep native Windows, hosted Ubuntu, and local WSL reproduction as separate evidence axes. Validate claimed evidence paths before presenting them as repository assets, and phrase volatile machine observations as “at verification time.” Report direct contradictions, release-proof drift, and omissions separately. See [`references/runtime-profile-platform-doc-drift.md`](references/runtime-profile-platform-doc-drift.md).

### Real browser vertical-slice addendum

When adding a real Chromium/Playwright path to an existing smoke that also uses route mocks, isolate the real path in a fresh page or browser context. Do not reuse a page that still has mock routes, modal state, or prior failure fixtures. The real slice must call the real HTTP endpoint, persist into the same isolated SQLite data root, exercise the user-visible action, assert the durable projection, reload without restarting the process, and assert the persisted result again. Keep failure/retry/replay, Tauri WebView clicks, and public release claims as separate slices unless they are independently exercised.

For Windows + Git Bash runs, pass an explicit native absolute `COGNITIVE_DATA_DIR` (for example `D:/project/.hermes/task-runtime/browser-smoke`) or the CI-native runner path. Do not assume `$PWD` survives MSYS-to-Python path conversion unchanged; verify the resolved database path and remove the same path before reruns, otherwise stale SQLite state can masquerade as a binding or idempotency defect. Keep all generated data under the project-local ignored runtime boundary for local work.

Use RED→GREEN for the gate itself: first wire the call so the missing vertical slice fails, then add the smallest real implementation and run it with a fresh data root. Before repository upload, run the full test suite plus the exact browser command and static syntax/convention gates. A passing browser job is only one evidence layer; do not merge or report the phase as CI-complete until the run is `completed/success`, its `headSha` equals the candidate commit, and every required job—including Windows desktop—has finished. See [`references/real-chromium-delivery-gate.md`](references/real-chromium-delivery-gate.md).

### Public release / installer asset-chain audit addendum


When reviewing Windows desktop bundles, NSIS installers, release manifests, and CI together, separate three evidence dimensions instead of treating a green build as a public release:

1. **Build evidence** — the workflow creates the executable/installer and checks expected files.
2. **Installer lifecycle evidence** — the installer is exercised on Windows: install, bundled runtime selection, startup/readiness, graceful and forced shutdown, bytecode/resource immutability, and uninstall cleanup.
3. **Public distribution evidence** — a tag-only release path injects exact commit/tree/CI identity into a separate release artifact, produces checksum/signature/SBOM or provenance, uploads the installer, creates a release, and reads the published assets back.

Classify the first two as build/test gates only when the workflow has no release upload/publication step. Inspect `on` triggers and permissions, not just job names: branch/PR triggers plus `contents: read` cannot prove publication. Search the exact workflow and tracked scripts for artifact upload, release creation, signing, checksum/provenance, and post-publish read-back. A source manifest with `unreleased/public=false` and unavailable source identity may be the correct source truth; do not mutate it during an audit. Look for an explicit temporary staging/injection step that preserves the tracked source manifest and validates the injected manifest from the final wheel/installer.

Treat NSIS smoke as partial for release truth if it only checks local installation behavior or a hard-coded product version. It must not be credited for source identity, signature, checksum, or public availability. Static tests that assert workflow strings prove repository contracts only; they do not prove that CI executed or published the behavior. Historical handoff notes naming an older SHA are prior-SHA evidence, never current-HEAD release evidence.

For a bounded remediation, recommend one tag-only release slice: gate on the same-SHA aggregate checks, build in an isolated temporary staging tree, inject identity into a separate artifact manifest, require signature/checksum/provenance, publish only after all gates and protected approval, then read back the exact release assets. Keep portable data-mode, product-feature, and other roadmap work out of this slice. See [`references/public-release-asset-chain-audit.md`](references/public-release-asset-chain-audit.md).

### Canvas / mini-game Runtime event-chain addendum

For H5/微信/抖音 Canvas games, distinguish content/engine existence from player-reachable Runtime wiring. Trace the chain in dependency order: content schema → initial state/clone/rollback → post-teaching scheduler → real action exits (identity/classification/high-risk) → progress/history/flags → contamination and next-shift consequences → debrief → regenerated platform Bundles. A passing isolated `eventChainEngine` test is not product evidence if the scheduler never reads the chain or the Canvas Runtime never calls the advance function.

Use RED→GREEN tests for teaching dormancy, first-step content binding, three-step progress/completion, wrong flags, contamination, next-shift modifiers, and debrief history. When the engine returns a chain object or a `consequences` array, preserve that contract at the scheduler boundary. If runtime keeps both global history and per-chain history, update them from the same returned progress so `stepIndex` cannot remain stale. Rebuild all generated platform Bundles and run the strict package gate before claiming the released player path is wired. Keep project execution boundaries in a project-local document; do not modify Hermes global configuration or other repositories as part of a project audit.

See [`references/canvas-runtime-event-chain.md`](references/canvas-runtime-event-chain.md) for the compact checklist and failure patterns.

**Runtime reachability hard gate:** A scheduler that installs `currentShift` is not enough. Trace the next boundary to the player-visible pending inspection and click callback: every scheduled shift must create/open the inspection consumed by the renderer, and every visible button must route to the semantic decision handler (not a generic action dispatcher with an unknown ID). Specifically inspect the `quick`/normal decision button metadata and the `onDecision` versus `onAction` branch. Test the real sequence `schedule -> openInspection -> render buttons -> click -> action exit -> advance`, not only direct scheduler/engine calls. A transition patch that advances the chain while installing the first post-tutorial shift can skip step zero; verify whether the tutorial handoff should schedule the first step or advance an already-played step.

**Chain state versus consequence state:** Keep event-chain flags separate from next-shift modifiers. Ending selectors should receive the flags emitted by the chain; modifiers require a separate consumer that changes the following shift and then marks them consumed. A modifier array that is merely stored, copied through high-risk state, or passed to debrief is not an applied consequence. When a requested file/module is absent, report the actual module boundary and imports rather than inferring a missing implementation from the filename.

**Dirty-tree/bundle gate:** If the working tree contains an uncommitted runtime patch, compare it with the frozen HEAD and with every tracked generated bundle. Do not credit the WIP path as released, and do not credit a bundle as current if it still contains the HEAD implementation. Record both identities and audit the exact requested tree; static bundle content injection equality does not prove runtime reachability.

### Local-first desktop usage-monitor audit addendum

For Tauri/Rust/Vite token or provider-usage monitors, audit the data contract and user-visible semantics as one vertical slice. A parser unit test or successful desktop build is not enough. Verify: explicit usage fields only; `exact` versus `unknown`; parent-summary versus nested usage de-duplication; event identity that preserves identical legitimate JSONL lines; provider hints before model/path heuristics; model aggregation keyed by provider plus model; overlapping multi-source roots normalized and covered once; historical versus live baseline semantics; truncate/rotation/deletion fail-closed behavior; and tray/window lifecycle separately from rendering.

Use a project-local synthetic JSONL fixture with no prompts, responses, credentials, or real logs. Include: two identical usage events on distinct lines, the same model under two explicit providers, a parent summary containing nested usage, an unknown line, and a multi-source parent/child overlap. RED→GREEN regression tests must assert request count, totals, provider/model buckets, and no duplicate source contribution. For the UI, verify initial no-read consent, start-only scanning, refresh-without-start behavior, history/live labels, source-change baseline reset, rotation pause/restart notice, keyboard focus/ARIA status, and last successful scan feedback. Keep compile/build, native launch, fixture interaction, tray persistence, and process exit as separate evidence layers. See [`references/desktop-usage-monitor-gap-audit.md`](references/desktop-usage-monitor-gap-audit.md).

Do not call a full-directory polling snapshot an offset/inode incremental watcher. If the implementation cannot prove file identity/offset continuity, either label it as full rescan or fail closed on size shrink/replacement; never silently subtract snapshots across rotation and claim accurate live usage. Similarly, a tray menu in Rust source is implementation evidence only until close-to-tray, restore, and explicit exit are exercised on the packaged Windows app.

### Retired-module residue audit

When an authority file narrows a repository to a fixed active-module set, audit more than direct module names. Freeze the exact HEAD/index and treat concurrent working-tree changes separately, then scan current governance, workflow contracts/docs/tests, knowledge entrypoints, and active task-pack summaries for these semantic residue classes:

- Adapter identity or support level (architecture diagrams, adapter tables, registry entries, governance assertions).
- Model/task taxonomy (for example, an enum that still routes a retired domain task class).
- Gates and metrics (required/skipped gate IDs, aggregate verifiers, calibration or product-specific score requirements).
- Current capability lists, release prefixes, contract consumers, module counts, and generated current-state fields.

Exclude archive roots and files explicitly classified as historical handoffs, migration records, or fixtures, but do not exclude a current normative catalog merely because the stale entry points to an archive contract. Use the authoritative active-module registry as the discriminator: a consumer, release prefix, gate, or capability identity absent from that registry is a finding unless explicitly typed as external/history-only.

For generated state, report the generated `path:line` and trace the value back to its generator or canonical input so the minimal repair is durable; never recommend editing generated output alone. Direct contradictions inside one current document are high severity—for example, “no longer an Adapter” beside an architecture diagram that still lists it. A governance test that asserts stale wording raises the severity because it actively prevents cleanup.

Report each finding as `path:line`, severity, residue class, and smallest durable fix. Also record clean exclusions (correct transfer boundaries, explicit fixtures, historical ledgers) so keyword hits are not mistaken for active residue. Do not run in-place gates during a strict read-only audit unless their side effects were first proven absent.

**Namespace-residue scans are case-sensitive by design.** After an identity migration (`opendesign-assistance` → `design-lab`), scan BOTH case variants before bulk-replacing. Observed 2026-08-14: 21 active-path hits of lowercase `work-lab` (schema `$id` URIs, benchmark briefs, evidence-card registry — genuine identity drift) coexisted with 4 uppercase `WORK-LAB` hits (inheritance matrix "WORK-LAB fully cut over", a historical handoff glob in CI, "Canonical sources inside WORK-LAB" in a SOURCE_OF_TRUTH doc — legitimate historical facts). Blindly replacing case-insensitively would corrupt the historical records; blindly replacing only one case leaves drift. Triage by path class: schema `$id`/manifest/registry namespaces must be migrated; inheritance/handoff/migration-record references stay. Verify the residue gate afterwards with a case-sensitive scan of active paths only.

### Step 4: Identify Gaps and Organize by Priority

Group missing items into priority tiers:

| Tier | Label | Criteria |
|---|---|---|
| P0 | 核心功能 | Breaks core workflow / blocks basic usage |
| P1 | 健壮性 | Reliability, logging, testing, dependency hygiene |
| P2 | 扩展能力 | Feature expansion, new integrations, new pipelines |
| P3 | 工程化 | CI/CD, Docker, tooling, long-term maintainability |

### Step 5: Search Existing Open-Source Solutions FIRST (mandatory)

**Before recommending custom code for any gap, search for existing open-source projects that can fill it.** The user's workflow is: collect → evaluate → integrate → only then code.

For each gap above P0 threshold:
1. Check the project's own absorption registry (`shared-contracts/registries/`, `docs/*/吸收总库.md`, etc.) — the project may already have catalogued relevant projects.
2. Do web searches across the relevant category (document parsing, vector DB, web crawling, agent frameworks, logging, etc.).
3. Add newly discovered projects to the project registry (JSON + CSV) and absorption doc.
4. Cross-reference: which discovered projects directly solve which gaps?
5. Present: "these N projects exist and can solve gap X — install them first, code only the glue."

Categories to search for AI/engineering projects:
```
文档解析 | 向量/图数据库 | 网页采集 | Agent框架 | LLM观测/评估
RAG方案 | 工作流编排 | 日志/监控 | DB迁移 | 知识图谱/记忆
```

When the user says "搜集可用的" or "有可用开源项目吗", this means: exhaust the search space BEFORE writing custom code. See `references/open-source-search-workflow.md` for the detailed search-and-register pattern.

### Step 6: Produce Structured Output

Format the analysis as:

1. **Baseline and scope** — exact repo/data roots, branch/status, authoritative specs and excluded areas.
2. **✅ Verified complete** — only criteria backed by execution/read-back evidence.
3. **⚠️ Partial / declarative only** — implementation or status claims that have not been exercised.
4. **❌ Gaps** — P0/P1/P2/P3 with evidence, impact and acceptance test.
5. **Contradictions and metric drift** — conflicting counts/statuses across docs, code and runtime.
6. **💡 Remediation order** — reversible fixes first; state what cannot honestly be completed in the current run.

### Full absorption / multi-project roadmap audits

When the user asks to absorb all open-source, knowledge-base, PKM, or adapter candidates into a project and update the future stages, treat this as a **portfolio audit plus dependency-ordered roadmap**, not as permission to install every candidate.

1. Freeze `HEAD`, branch, dirty state, and remote SHA before auditing. Read the machine-readable source registry and absorption ledger, then independently count entries and execution states. If a human document says a different total, report the contradiction and make the machine ledger authoritative for current counts.
2. Classify every candidate into the project's closed execution states (for example `implemented`, `adapter_contract_pending`, `deferred_review`, `reference_only`). Require reachable code path + focused test evidence before calling anything implemented. Registry presence, an optional import, a README claim, or a historical absorption note is not implementation evidence.
3. Keep all candidates in the roadmap, but map them to one of four actions: direct toolchain use, explicit Adapter, design-only reference, or deferred/high-risk review. Do not let product platforms, agent frameworks, graph/vector stores, or external sync systems replace the project's core contracts, database owner, permissions, or governance without an independently approved migration.
4. Build stages in dependency order. At minimum separate: registry truth; current product/runtime closeout; ingestion/Research adapters; Knowledge/search/graph/memory; Obsidian/PKM compatibility; evaluation/observability/providers; runtime/agent/workflow; Workspace frontend/API projections/desktop; and release/installer/distribution. For every stage list backend, frontend, data/migration, desktop/ops, tests, failure/recovery, rollback, and exact-SHA exit gates.
5. For Obsidian or other PKM systems, distinguish Markdown import, Vault semantics, attachments/links, plugin syntax, one-way projection, incremental sync, conflict handling, and bidirectional write-back. Never label ordinary Markdown passthrough or a projection renderer as full compatibility.
6. Record calendar dates only when an approved TaskPack or release plan actually defines them. Otherwise use dependency gates (`R0 → A0 → ...`) and explicitly state that no date is committed; do not fabricate a completion month or release version.
7. When the user wants the roadmap updated, save a durable project-local plan with exact paths, candidate mappings, TaskPack seeds, and verification commands. Keep external clones/installs and shared-checkout writes out of the audit unless a later TaskPack explicitly authorizes them.

### Step 6.5: Convert a Blueprint into Execution

When the user supplies a multi-stage blueprint and says “全面执行 / 全部开始 / 修复后继续所有任务”, do not stop at an audit report, but also do not claim that a multi-release roadmap was completed in one pass.

For a historical decision archive or conversation export, use [`references/historical-decision-archive-execution.md`](references/historical-decision-archive-execution.md): treat the archive as a dated input, reconcile every claim against the live repository/CI/release provider, classify it as verified/partial/pending/superseded/blocked/conflicting, then execute only the first dependency-safe slice in an isolated worktree and PR. A failed release gate is evidence of a correct stop, not permission to rerun or rewrite the same tag; fix the root packaging/provenance defect, create a new commit and new remediation tag, and repeat exact-SHA → draft → readback → publish gates.

For an A0/product-truth slice, load [`references/truth-baseline-release-manifests.md`](references/truth-baseline-release-manifests.md). Treat hard-coded dashboard counts, percentages, service health, model status, jobs and progress as false until backed by a safe live API. Preserve unimplemented information architecture with explicit empty states, not sample business data. A tracked Release Manifest must not claim its own containing commit SHA; source distributions should mark exact source/CI identity unavailable and inject it only into verified release artifacts.

1. Reconcile every blueprint premise against the current code and exact tree; mark stale findings as already delivered instead of reimplementing them.
2. Convert the blueprint into a dependency-ordered queue with an explicit current release slice and later product stages.
3. Preserve an already-frozen high-risk candidate: finish its exact-tree review and cloud release before mixing unrelated roadmap edits into it.
4. Start the first executable slice immediately—usually truth/document/UI cleanup or the shortest missing vertical path—and carry it through tests, review and publication.
5. Parallel agents may audit independent facets, but implementation writers require isolated checkouts and feed one integrating release train.
6. For each stage, require its own real input, persistence, failure/recovery, restart, UI, packaging and exact-SHA evidence; keep later stages pending until prerequisites are actually green.
7. Persist the roadmap and continuation state so another session or workstation resumes the same next task without reconstructing the audit.

The deliverable is therefore both a truthful gap matrix **and** a running execution queue with the first verified artifact—not a static recommendation list or a fabricated “all done”.

When the user says “继续 / 全部执行 / 全面推进”, a milestone summary is a checkpoint, not a stopping condition. Continue into the next dependency-safe action without asking for another confirmation: close review findings, publish the exact tree, verify exact-SHA CI, merge, update the queue, and start the next stage. If an asynchronous reviewer is the only dependency, keep doing independent read-only verification or next-stage discovery; once its result arrives, resume the release chain automatically. End a turn early only for a real external blocker, safety decision, or runtime tool limit, and preserve the exact tree/branch/gate state so continuation does not reconstruct the audit.

#### When "no gap remains" is declared, re-audit four directions before stopping

A long autonomous session can honestly believe it is done while real gaps remain. When the user repeats the same full-speed directive (e.g. "全量推进直到无任务可做") after a declared-exhaustion report, re-audit in these four directions (validated across 15+ extra rounds in one 2026-08-15 session on ArcheAxis-Knowledge-OS — every round found real work):

1. **Promise→evidence gap audit.** Every shipped claim ("verifiable backup", "resumable batch", "safe restore") is a promise needing a proving test, not just a happy path: checksum/tamper negative control (mutate a payload file → verify MUST fail), real non-dry-run restore (data loss → recover → byte-identical readback), safety-negative control (no flag → refuse AND assert the protected data is untouched). A claim with only a happy-path test is a gap.
2. **Symmetric-feature audit.** After covering one feature, check its sibling for the same test classes: backup↔exchange, export↔verify, status↔control endpoints, dry-run↔real. Mirror the TEST SHAPE, but read each side's real constants/messages before asserting (exchange root `data/exchange/`, manifest `manifest.json`, message `hash mismatch`; backup root `data/backups/`, manifest `backup-manifest.json`, message `corrupted` — guessing either side's literals costs a debug cycle).
3. **Error-semantics matrix enumeration.** If the API documents codes (400/404/409/422), list them and diff against existing tests one code at a time; enumerate per-endpoint (status vs each control action) and per-parameter-branch (dry_run True vs False, overwrite True vs False).
4. **Historical-conclusion re-adjudication.** Re-examine earlier conclusions with new evidence: a "scheduler skipped the tick" claim was retracted by cross-checking commit timestamp timezone vs Actions page display vs cron UTC (LOG-161); "workflow never ran" was explained by the file's first-add git timestamp vs tick timeline (LOG-162); a benchmark report was self-contradictory because only the measurement table was updated (grep the doc for old numbers after any dataset change). Each retraction/explanation is real delivered value.

Only after these four pass with zero findings is "无任务可做" an honest terminal state — and then the report should enumerate exactly what remains Owner-gated and why.

#### Post-merge truth synchronization

After a product or release PR merges, do not treat successful code/CI delivery as the end of the continuation chain. Re-audit the live `origin/main` docs, README, project status, architecture/status handoffs, release manifest, changelog, and public release metadata for contradictory prior-state claims. Separate dimensions explicitly: source version/manifest truth, public artifact/release truth, runtime capability evidence, and still-deferred UI/desktop/ASR/provider capabilities. Repair only current normative docs that contradict verified merge-SHA or release readback; preserve historical handoffs and immutable tags. Use a fresh isolated worktree based on the exact remote main SHA, selective edits, `git diff --check`, a docs-only/selective CI route when applicable, then exact-head PR CI, merge-SHA main CI, and remote SHA readback. Never edit the canonical dirty WIP checkout to perform this synchronization.

When pushing from a detached isolated worktree, use a fully qualified refspec (`HEAD:refs/heads/<branch>`); a short `HEAD:<branch>` may fail because Git cannot infer the source ref. Treat that as a refspec correction, not a code or repository failure.

#### Autonomous continuation / no-progress-report mode

When the user explicitly says “后续不要汇报” / “继续自主进行” / “不要逐步汇报”, treat that as a communication-mode contract for the current execution chain:

1. Do not send milestone narration, intentions, or repeated status summaries between tool calls. Continue the work directly.
2. Keep internal TODOs and evidence records, but surface them only in the final response or when a real external blocker, safety decision, destructive action, or tool limit requires user attention.
3. Do not stop after an audit, plan, compile, or single successful test when the request includes repair and delivery. Continue through the next dependency-safe slice: repair → focused test → full gate → runtime/UI proof → exact diff/tree review → commit/push/CI when authorized.
4. A successful build is not a stopping condition for a desktop product. Continue to native cold launch, actual interaction/state readback, lifecycle/close-to-tray verification, and clean process shutdown when those are in scope.
5. If the tool-call budget ends, return one final evidence summary that clearly separates completed, unverified, and blocked work; never imply that the remaining queue was completed.
6. Do not create a cron job merely to avoid reporting. Durable scheduling is a separate user-requested action, not a substitute for continuing the current task.

#### Overlay staging candidate-tree freeze

When applying a TaskPack/overlay in staging, do not freeze a candidate tree before staging created files. `git write-tree` reads the index, so an overlay that creates only untracked files can produce a false baseline-equal tree. Stage the intended allowed roots, run `git diff --cached --check`, freeze `candidate_tree`, then rollback with `git reset --hard` plus `git clean -fd -- <allowed-roots>`, reapply, restage, and require `reapplied_tree == candidate_tree`. Use `references/taskpack-overlay-staging-candidate-tree.md` for the full recipe and evidence shape.

### TaskPack + original-backlog release-scope reconciliation

When the user defines a new version as **all attached TaskPacks plus all pre-existing unfinished work**, treat that as a release-scope contract, not a request for another CI/release remediation. Build one joined matrix with these separate sections:

```text
original unfinished backlog
+ each TaskPack item
+ research/Registry candidates
+ release and installer gates
```

For every row record at least: task ID, source revision, repository URL, license snapshot where external material is involved, allowed/forbidden paths, dependency predecessor, implementation path, exact commit, focused tests, integration tests, browser/runtime/Tauri evidence, Registry record, rollback handle, and status. Use `missing`, `planned`, `in-progress`, `blocked`, `implemented-unverified`, `verified`, and `release-integrated`; never collapse these into one completion percentage.

Apply this release truth rule:

```text
release/CI/installer repair ≠ product-task completion
TaskPack declaration ≠ implementation evidence
source file ≠ reachable product path
unit test ≠ browser/Tauri/runtime proof
public Release ≠ completion of the next product scope
```

An existing public release remains historical/baseline evidence unless its artifact tree independently satisfies the newly defined scope. Do not retag, rewrite, or retroactively relabel it as a TaskPack-complete release. Keep the new release gate closed until every original-backlog row and every TaskPack row is either verified with its required evidence or explicitly removed by the user. Resolve TaskPack identity first (archive hash, internal root, manifest, baseline SHA); then reconcile the pack's planned/frozen markers against the live tree. The correct execution order is dependency-driven: source/Registry truth → backend/public DTO and action contracts → smallest real UI vertical slice → runtime/browser/Tauri evidence → remaining domain backlog → exact-SHA release chain.

When summarizing the result, lead with the scope correction and explicitly state what the latest release did **not** complete. A long task list is not sufficient: include a release-admission checklist whose final rows are original backlog, every TaskPack, Registry evidence, runtime E2E, installer lifecycle, exact-SHA CI, and public readback.

### Historical archive + TaskPack + research-pool joint audits

When a user supplies a historical decision archive together with one or more TaskPack/research ZIPs, treat them as three different evidence classes rather than one specification:

1. **Decision archive** — dated product direction and prior claims; useful for intent, never proof of current implementation.
2. **TaskPack** — execution boundaries and acceptance contracts; validate its baseline SHA, allowed paths, prohibited actions, rollback rules, and whether the recommended order still matches current dependencies.
3. **Research pool** — candidate registration data; never equate registered, researched, benchmarked, adapter-contract, implemented, runtime-enabled, or commercially usable.

Use this sequence:

1. Hash every supplied file and record exact sizes/member counts. For each ZIP, inspect members before extraction; reject absolute paths, `..` traversal, symlinks, encrypted members, and unexpected nested executables. Extract only into the current project's ignored `.hermes/task-runtime/<audit-id>/` directory. Do not execute scripts, package scripts, installers, crawlers, or nested archives.
2. If the TaskPack embeds copies of the archive/decision files, hash the embedded bytes and compare them to the external inputs. A match proves input identity, not task completion; a mismatch creates two baselines that must be reported separately.
3. Parse machine-readable research data independently of prose counts. Report field presence, missing-field rates, priority distributions, registry flags, license/revision/evidence availability, duplicate project names, and whether each record is merely a candidate. A count like “369 projects” is not evidence of license audit, source revision pinning, integration, or commercial readiness.
4. Cross-reference every completion statement with live repository HEAD/tree, current CI, runtime/API reachability, and release-provider readback. Mark stale snapshot SHAs and historical counts as prior-SHA evidence.
5. Build a contradiction table. Explicitly record when TaskPack order conflicts with current dependency order, when a historical “completed” claim is only an artifact/design claim, and when later explicit user authorization supersedes an earlier TaskPack stop rule. Do not silently choose one source.
6. Produce one durable matrix with `verified`, `partial`, `pending`, `superseded`, `blocked`, and `conflicting` states, plus exact evidence and the next dependency-safe action. Execute only the first safe slice in an isolated branch/PR; do not claim the multi-stage blueprint is complete in one pass.

For this pattern, use [`references/historical-inputs-joint-audit.md`](references/historical-inputs-joint-audit.md) for the reusable report shape, ZIP safety checks, and Registry-vs-candidate field checklist.

### Canonical project-positioning freeze and external-tool boundary

When an audit or continuation session touches both a canonical project repository and an external tool/runtime checkout, freeze the project identity before executing delivery actions. Read the repository's `AGENTS.md`, root `README.md`, module allowlist, and task-pack summary, then record:

- canonical Git root and remote;
- authoritative delivery modules and forbidden roots;
- whether the repository is a control plane, a product, or a multi-module workspace;
- external runtimes/tools that must remain outside the repository (for example Hermes Home, credentials, sessions, caches, and a separate upstream source checkout);
- the exact commit/tree and remote ref being audited.

Treat an external fix as evidence or a separate upstream artifact, not as a project change, unless the current project has an explicit task-pack contract defining the target path and absorption boundary. Never infer that a user saying “continue” or “upload” authorizes copying an external source tree into the canonical project. Before any push, confirm the destination repository and branch; if the external repository is upstream or official, fail closed rather than publishing there by accident.

When the user corrects positioning or says the agent has drifted, stop the current release narrative and reload the live project docs. Reconcile every previous claim against the canonical root, exact tree, task-pack scope, and allowed paths. Report external-tool commits separately from project commits, and do not call a project release complete merely because an external tool was built or locally committed.

For “all upload” requests, enumerate the canonical working tree and remote divergence first. Upload only tracked, project-owned changes that pass the project gates. Preserve external platform state, source checkouts, credentials, sessions, and caches outside the project boundary. Verify `HEAD == origin/<branch>` and exact-SHA CI after the push; distinguish pushed, merged, released, and publicly read back.

### Post-merge documentation truth reconciliation

After a feature or release PR merges, perform a second, live documentation audit before declaring the delivery fully closed. Historical handoff files and the canonical README/status pages are different evidence classes; do not bulk-rewrite every stale-looking document.

1. Query the live remote `origin/main` SHA, the merged PR SHA, the merge-SHA CI conclusion, the current release/tag metadata, and the source release manifest. Do not audit a detached pre-merge worktree as if it were current main.
2. Compare current normative entrypoints (`README.md`, `docs/PROJECT_STATUS.md`, current architecture/index docs, and active `workspace/intake/` contracts) against the live provider. A source manifest with `unreleased/public=false` can be correct even when a separately injected public artifact is already released; report these as two dimensions, not a contradiction.
3. Repair only active normative text that contradicts verified live evidence. Preserve historical handoffs, dated audit snapshots, immutable tags, release assets, user WIP, and unrelated current worktree changes.
4. Keep residual limitations explicit: a successful backend/Chromium/installer gate does not prove Tauri WebView click evidence, signature, ASR, generic Planner, or complete Job Center interaction. Never “close” a gap by replacing it with a broad completion claim.
5. Deliver documentation fixes in an isolated worktree and selective commit. Run `git diff --check`, create a PR, verify exact-head selective CI, squash-merge only when mergeability and checks agree, then verify the new merge-SHA main CI and remote `origin/main`.
6. If a docs change is blocked by a stale base or detached worktree, re-read the exact file and compare against `origin/main` before retrying; use the full refspec `HEAD:refs/heads/<branch>` when pushing from detached HEAD.

This pattern is reusable for any post-merge truth drift, especially release identity, installer evidence, platform readiness, capability matrices, and generated/current-state documentation.

### Documentation upload and source/cloud divergence

When a user asks to upload a summary or gap ledger while the canonical checkout is dirty or the local development branch diverges from its remote, separate documentation synchronization from code synchronization. Freeze local/remote SHAs and protected WIP first; create an isolated documentation branch from the intended cloud base (normally `origin/main`); stage only the scoped tracked document; exclude `.hermes/`, real source materials, credentials, WIP, and unreviewed local commits. Push with an explicit refspec and use a PR. Verify the exact PR head checks, distinguishing `PASS`, `SKIPPED`, and `PENDING`, then read the remote document back and compare SHA-256 with the local candidate. Report `documentation aligned` and `source branch aligned` as separate dimensions. A docs PR never proves product, TaskPack, installer, or public-release completion, and historical failures/blockers must remain visible in the ledger.

### Step 7: Save / Upload Analysis

If the analysis is substantial, save it to the project for reference:

```text
.hmres/plans/YYYY-MM-DD_gap-analysis.md
```

When the user says “上传” after a roadmap / 后续列表 / gap analysis, treat it as a request to make the artifact durable in the repo, not merely reprint it:

1. Write the roadmap to a stable project doc such as `docs/NEXT_TASKS.md` or `docs/<topic>_ROADMAP.md`.
2. Link it from the public entrypoint (`README.md` or the relevant platform handoff doc) when appropriate.
3. Run the project’s lightweight doc/test gate (or full `npm run verify` if that is the established gate).
4. Commit and push with a conventional `docs:` commit.
5. Report the file path, commit SHA, push status, and real verification output.

## Example Sessions

- `references/minigame-gap-analysis.md` — historical real-world game project example; treat its completion claims as dated rather than authoritative.
- `references/minigame-product-audit-checklist.md` — reusable checks for platform claims, zero-code skins, core-play loops, IAA reachability, cross-run state, runtime parity, and read-only audits.
- `references/dynamic-import-audit-pattern.md` — probing adapter capability at runtime (import checks, `shutil.which`, four-state classification) rather than trusting configuration or `pip list`; essential for adapter-layer audits.
- `references/entrypoint-doc-drift.md` — README/platform handoff drift as an implementation gap.
- `references/homepage-product-truth-audit.md` — exact-HEAD CI checks and capability-layer reconciliation for README/status/manifest/Workspace product-truth audits.
- `references/nine-dimension-analysis.md` — full 9-dimension evaluation template with P0-P3 prioritization.
- `references/cross-project-absorption.md` — workflow for absorbing utilities from sibling projects into a monorepo (`diff -rq`, adapt, test, commit).
- `references/open-source-search-workflow.md` — mandatory "search first, code second" workflow: search→register→cross-reference→install→only then code.
- `references/auditor-negative-controls.md` — known-broken fixtures, stable snapshots, exact CI gates and claim reconciliation for validating the audit itself.
- `references/truth-baseline-release-manifests.md` — A0/product-truth workflow for removing pseudo-data, designing safe aggregate status APIs, validating complete migration registries, and proving manifests/UI from a fresh installed wheel.
- `references/archeaxis-a0-truth-baseline-2026-07.md` — session-specific ArcheAxis/Cognitive-Loop-OS A0 case, including UI/API/doc drift, nine-owner manifest validation, real browser evidence, and the wheel build-chain pitfall.
- `references/backend-fastapi-audit-pattern.md` — FastAPI route-surface verification, product DTO/wire-boundary checks, bounded upload reads, complete receipt→Job→Outbox replay validation, mounted-app counting, auth smoke, and security heuristics.
- `references/ci-release-gate-audit.md` — exact-commit audit pattern for JS, real-browser, Windows, fresh-wheel, packaged-static-resource, and backup/restore failure-boundary gates; includes false-gate detection and dependency-ordered remediation.
- `references/minigame-security-release-audit.md` — H5/mini-game/Android WebView security and release checks for rewarded-ad failure paths, cross-run state, generated-artifact drift, CI/local gate mismatch, path containment, skin validation, and release-vs-debug evidence.
- `references/douyin-readonly-release-audit.md` — 抖音小游戏官方文档限定的只读发布审计：当前产物、包体、隐私/适龄、文案素材、门禁假绿及代码/资料/账号后台阻断分层。
- `references/sbom-audit-pattern.md` — SBOM/dependency-metadata completeness audit: check for CycloneDX/SPDX files, inventory existing SSOT/pins, report gaps, recommend lightweight generation.
- `references/completed-mode-cron-contradiction.md` — handling state.json `completed` mode when instructions list tasks: verify evidence layers before deciding if work remains; applies when gap-analysis starts while a previous sleep-mode cycle left `completed` state.

## Portable workflow deployment audits

For repositories that combine a project-data wrapper, portable verifier, repo-to-live sync, TaskPack/release orchestrator, quality-gate runner, and workflow YAML, load [`references/portable-workflow-governance-audit.md`](references/portable-workflow-governance-audit.md). It adds the required non-empty-target sentinel negative control, public-entrypoint-versus-leaf-helper check, argv-level wrapper-hook validation, gate side-effect containment, deployed-`bin/` compile coverage, and fake-test-versus-real exact-SHA delivery distinction.

Under a strict read-only request, classify every gate's writes before execution. Use `PYTHONDONTWRITEBYTECODE=1` for in-place non-writing unit/static checks. For a full gate that writes caches, reports, bytecode, or ignored artifacts, run the exact source in an isolated temporary copy; if context-pack or similar code requires Git metadata, initialize only the temporary copy as a synthetic local Git repository and label that identity separately from the requested commit and live CI. A green source-string governance test or isolated gate does not prove a current GitHub run, public release, or wrapper enforcement.

For Windows/Git-Bash hooks, substring regexes are not sufficient evidence that the wrapper actually ran: test text-only mentions and fake executable prefixes as negative controls. When implementation, tests, skills, and docs disagree on a project-local subdirectory such as the Kanban root, report contract drift even if the path remains within the project.

For Windows/Tauri/portable desktop release audits, load [`references/windows-tauri-portable-release-audit.md`](references/windows-tauri-portable-release-audit.md) for the exact-SHA, installer data-boundary, portable-mode, and build-vs-public-release checklist.

For a staged read-only audit covering frontend reachability, API projections, real Chromium interaction, Tauri WebView2, portable data, NSIS, upgrade/recovery, and public release, load [`references/frontend-tauri-installer-stage-matrix.md`](references/frontend-tauri-installer-stage-matrix.md). Use its fixed four-field output for every stage: existing evidence, gap, gate, and exact paths. Keep browser HTTP evidence, Tauri click evidence, installer lifecycle evidence, and public publication evidence separate.

When auditing a portable Hermes workflow package, distinguish the repository source, the global Hermes Home destination, and a Git-ignored project-local `.hermes/` runtime. Trace setup scripts through the public sync CLI, not merely its internal helper functions. A temporary-empty-home verifier is meaningful only when it rejects non-empty supplied targets, invokes the real deployment entrypoint, asserts no credential/session propagation, and labels its result structural rather than provider/runtime proof. For the full read-only method and test matrix, load [`references/portable-hermes-home-migration-audit.md`](references/portable-hermes-home-migration-audit.md).

### Dirty-index selective delivery

When an implementation task runs in a checkout containing staged, unstaged, or untracked user WIP, treat the index as protected state—not as an empty staging area. Before adding agent files, capture `git status --short --branch`, `git diff --cached --name-status`, and `git diff --name-status`. A later `git add <agent-paths>` does not remove pre-existing staged WIP, and a normal `git commit` will include every staged path.

If an accidental mixed commit occurs, stop immediately: preserve it as recovery evidence; do not amend, reset, clean, or force-push. Save remaining unstaged/untracked WIP with a named stash or patch, create a clean candidate branch from `origin/main`, extract only the declared agent paths from the recovery object, stage and verify the clean candidate file list, run gates, and create the PR from that branch. Restore the original branch and WIP afterward. `git commit --only` can isolate tracked files, but it does not automatically include new untracked files; never follow it with a broad normal commit while user paths remain staged. Prove scope with `git diff <base>..<candidate> --name-status` and the commit stat, not exit code alone.

## Windows read-only path and evidence handling

On Windows repositories whose path contains spaces, keep the audit root in one canonical form per tool: use the native absolute path (`D:/...`) for `read_file`/`search_files`, and quote the MSYS path (`/d/...`) only inside `terminal` commands. If a high-level file search reports the root as missing while a quoted terminal command can resolve Git and source files, treat that as a path-form mismatch first; run one diagnostic root check before retrying, then continue with the working path form rather than repeating the same failing search.

For a strict no-modification audit, do not execute the repository's test suite in place merely because it is named as the formal gate. First inspect fixtures and commands for migrations, SQLite/vector writes, generated fixtures, caches, browser profiles, subprocesses, and cleanup. Record the tests as static evidence (`test exists`, target and assertions) and report runtime evidence as missing when execution would mutate the requested checkout. Never infer a green result from stale handoff output, cache directories, old CI, or a test file that was not run against the exact current HEAD.

## Desktop observer audit: LIVE truth and runtime reachability

For a read-only web/desktop observer that claims `LIVE` data, do not accept a green static/UI contract as proof of live product truth. Trace the packaged entrypoint all the way to its data producer:

1. Identify the actual projection function used by the runtime store/server, not merely a newer authority function that exists in the same source file. If multiple projection functions or schemas coexist, record which one is reachable from the documented entrypoint.
2. For a Tauri/static bundle, verify whether `/api/*` is backed by a bundled sidecar, native command, local service, or only an external development server. If no producer is packaged, a failed fetch followed by a bundled JSON fallback is a snapshot/replay path, not LIVE.
3. Require explicit mode semantics: `LIVE`, `SNAPSHOT`/`REPLAY`, and `FIXTURE` must be distinguishable in both data and UI. A bundled last-good snapshot must expose provenance, generated time, freshness/expiry, and source references; never label it LIVE merely because it is the preferred fallback.
4. Audit every UI surface independently. Full and compact views may render different badges or stale hard-coded labels even when the shared projection is correct. Add a regression test that renders each mode in each view and asserts the visible mode label matches the data mode.
5. Separate evidence layers: local EXE existence is local build evidence; source contracts and Python tests are implementation evidence; cloud CI is exact-SHA gate evidence; Windows cold launch/WebView2/tray interaction is runtime evidence; a GitHub Release asset and checksum readback are public distribution evidence. None substitutes for another.
6. Check whether CI runs the product's UI/desktop contracts. A green backend/governance aggregate that omits Node UI tests, Rust/Tauri build, Windows packaging, or lifecycle smoke must not be reported as desktop release proof.

For observer products, treat a duplicate legacy server/UI plus a newer static/Tauri UI as a contract-drift finding until one is explicitly marked legacy or both are wired to the same versioned projection. See `references/observer-live-truth-audit.md` for the concise evidence table and checks.

When the user asks which Observer modules should be retained or removed, audit **producer reachability**, not renderer completeness. Trace each UI field through normalization, projection builder, runtime composition root, canonical table, and a non-test producer. Classify producers as continuously supervised, manual/on-demand, fixture/test-only, or absent. Only a continuously supervised producer with freshness and stable identity supports a normal `LIVE` surface. In particular, detect standalone active-project scanners that are never scheduled, execution/CI/collector-health tables with no product writer, snapshot helper arguments omitted by the reachable composition root, random usage sample IDs that inflate cumulative totals, and local-only Git facts rendered as three-way mismatch. Hide fixture-backed/defaulted/internal-ID modules from the normal UI. Use `references/observer-capability-retention-audit.md` for the retain/refactor/remove matrix and static probes.

**Evidence-retention hard gate before UI removal:** Producer reachability decides whether a field may claim `LIVE`; it does **not** decide whether an evidence-backed product surface should exist. Before deleting any observer/dashboard section, classify it as current observation, historical fact, planning/approval baseline, deterministic derivation, or unsupported pseudo-live metric. Remove or relabel only the unsupported live claim. Preserve TaskPacks, generated current-state baselines, approval boundaries, error/history ledgers, and deterministic gap views with explicit non-live provenance. If the truth audit leaves only connection health plus one project/Git card and large blank space, stop: the audit has likely erased the product rather than corrected its claims. Add RED contracts for retained blueprint/task/history sections before the next UI edit. When sources conflict or a “completed” detail names untouched/skipped components, show `PARTIAL`/`RECONCILE_REQUIRED` instead of selecting the optimistic status. Load `references/observer-evidence-layering-recovery.md` for the source-to-field matrix, redesign sequence, conflict rules, and regression shape.

### Transferred-scope residue audit

When a module/product has been transferred out of a monorepo and may remain only as history or archive material, do not stop at checking that its old directory is absent. Audit **runtime reachability and transitive CI execution**:

1. Search ordinary push/PR workflows for direct retired gates, pilots and validators, then follow imports/calls from every active regression, benchmark and aggregate gate. Removing a named workflow step is insufficient when another report imports and benchmarks the same pilot.
2. Compute static invocation multiplicity when benchmark loops or verifier-plus-test duplication make the retired path run repeatedly. Report the call chain and practical CI impact, not just the matching filename.
3. Distinguish harmless migration pointers and negative guards from active residue. `SUPERSEDED_MOVED`, archive manifests and checks that retired trees are absent may remain; fixtures imported by active tests, product fallback data, positive assertions for retired project IDs, and benchmark inputs are **not archive-only**.
4. Trace every Observer projection and GET endpoint independently. A clean main dashboard does not prove retired scope is hidden if `/api/projects`, legacy projections, compact/full views, or fallback fixtures still expose arbitrary historical `projectId` values.
5. Inspect tests as runtime contracts. A test that injects a retired project and positively asserts it is returned proves current product reachability, even if README prose says the project is no longer read or displayed.
6. Minimal remediation should remove retired gates from ordinary CI, sever transitive imports from active regression reports, move historical fixtures under an explicitly archival boundary, and add negative tests across every user-visible projection/view. Preserve historical bytes only when no ordinary CI or product entrypoint consumes them.

Report each finding as `path:line`, direct/transitive call chain, ordinary-CI or UI impact, and the smallest boundary-preserving repair. Freeze HEAD/index/worktree first and identify whether each finding belongs to committed HEAD or concurrent WIP.

For a combined governance audit spanning active-module projections, generated `CURRENT_STATE` freshness, required-gate reachability, Stage/TaskPack terminal closure, handoff evidence drift, and public UI/internal-ID boundaries, load [`references/governance-projection-taskgraph-audit.md`](references/governance-projection-taskgraph-audit.md).

When repairing this class of gap, use the validated remediation sequence in `references/observer-live-truth-remediation.md`: red tests for the exact mode/view symptom → one authority projection → explicit LIVE/SNAPSHOT/FIXTURE semantics → same-origin/loopback GET fallback with bounded timeouts → Full/Compact mode assertions → separate source, local build, desktop runtime, exact-SHA CI, and public-release evidence. A loopback service that must be started separately is not a self-contained live portable app; preserve that residual boundary in the final report. On Windows, verify JavaScript with the real module test runner when an edit helper emits a malformed `D:\\d\\...` `MODULE_NOT_FOUND` path.

For audits that jointly reconcile a parsed TaskPack/approval package, generated `CURRENT_STATE`, concurrent Observer/Tauri WIP, and LIVE producer wiring, use `references/observer-taskpack-current-state-consistency.md`. It adds the generated-state input-coverage gate, historical-vs-current SHA typing, status-document internal-contradiction sweep, parser-propagated stale-data check, and LIVE-gate caller/type verification.

## Pitfalls

1. **Don't assume design docs are complete** — cross-check multiple docs (README might say something different from GAME_DESIGN.md)
2. **Read actual code, not just file names** — a file called `events.js` might only implement 2 of 8 designed events
3. **Prioritize by impact, not effort** — P0 should be things that break the experience if missing, not things that are easy
4. **Test files are evidence too** — if a test covers an edge case, the implementation is more robust than one without
5. **Respect the project's own workflow doc** — if `WORKFLOW.md` says "only Codex writes code", don't suggest manual edits
6. **Do not trust completion fields or aggregate counts without provenance** — manually written `100%`, file size, generated page count, or “URL present” are declarative signals; trace to file-level/runtime evidence
7. **Audit before repair, and keep the repair reversible** — preserve a baseline, archive originals before bulk rewrites, then rerun the same audit; do not let an audit script mutate the target
8. **When counts conflict, report the conflict instead of selecting the convenient number** — define separate denominators (source packages, logical items, local vs external items, active vs archived)
9. **Audit the auditor with negative controls** — create at least one known-broken fixture/path and confirm the audit detects it; permissive basename/stem fallback, broad exclusions or mutable snapshots can produce a convincing false zero
10. **Run the repository's exact gates, not a substitute** — inspect CI/workflow files and execute the same working directory, command and scope; a narrow test subset cannot justify “all tests pass”
11. **Separate repair completion from domain-work completion** — structural cleanup, links and CI may be complete while physical processing, accuracy measurement or human review remain open
12. **Do not confuse source truth with distributable truth** — a green source test, package-data declaration, or locally readable manifest does not prove the fresh wheel contains and serves the artifact. Validate the complete migration registry and ledger steps, then install the wheel outside the checkout with an empty `PYTHONPATH`; see `references/truth-baseline-release-manifests.md`.
13. **Stop dependent shell chains after artifact creation fails** — never let an empty wheel/archive path trigger misleading secondary install/import errors. Verify the artifact handle immediately, switch to the repository's canonical locked builder when needed, and only then continue package smoke.
14. **Checkout destruction voids all prior claims** — when the project directory has no `.git/` and no source files (only `.hermes/` runtime data remains), every `state.json` completion claim (`last_evidence`, `last_head`, test passes, E2E results) is **unverifiable phantom data**. Do not report, retry, or extend evidence that references a destroyed codebase. Set mode to `blocked`, clear all evidence fields, move queue tasks to `blocked_tasks`, and stop — the user must restore the Git checkout before any audit or task can proceed.

15. **False-positive checkout-destruction detection** — a previous `state.json` `stop_reason` claiming `project_checkout_destroyed` does not prove the checkout is actually gone. A `git rev-parse HEAD` that succeeds from the correct workdir takes priority over a stale log from a session that used a different root, path-prefix, or filesystem state. Do not propagate a false blocked state without live verification. See the "Resuming from blocked state" paragraph in the Read-only audit discipline section.

16. **Don't trust user task lists over live evidence** — when the user supplies a task queue (e.g. "current first task is X, then Y") but the live project state shows `mode=completed` with verified evidence, the evidence wins, not the instruction. Verify at least 3 evidence layers (HTML → JS → Router → Service → DB/Test → E2E) before deciding if work genuinely remains. Cron prompts especially carry forward stale instructions. See `references/completed-mode-cron-contradiction.md`.

17. **Shadow-rebuild verify must check live source, not self-consistency** — when auditing or implementing a candidate→activate→rollback lifecycle for any derived index (FTS, vector, graph, materialised views), the verify step must compare the candidate against the **live active source tables**, not just against frozen metadata. Self-consistency alone cannot detect source drift between build and activation time. See `references/shadow-rebuild-verify-against-source.md`.

18. **Architecture guard false positives for redaction/pattern strings** — When running a project's static analysis (e.g. `check_architecture.py`), `forbidden-absolute-path` or path-detection rules may flag regex patterns that intentionally match path-like substrings (e.g. `/home/...`, `C:\\Users\\...`, `/vault/...`) for content redaction. These are legitimate false positives: the regex operates on user content, not the filesystem. Distinguish them from true hardcoded runtime paths by checking whether the flagged string is:
    - Used inside `re.sub()`, `re.compile()`, or a regex pattern list (e.g. a named constant like `_REDACT_PATTERNS`);
    - A match pattern, not a file-open/read/write path;
    - Applied conditionally via a policy flag like `redact_paths` or `redact_api_keys`.
    If all three hold, classify as a false positive and report the count separately from real architecture violations. Do not treat every flagged line as a blocker — but do report the false-positive count transparently so the audit trail is accurate.
