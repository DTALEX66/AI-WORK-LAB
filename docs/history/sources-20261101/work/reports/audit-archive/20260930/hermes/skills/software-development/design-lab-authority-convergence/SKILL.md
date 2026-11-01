---
name: design-lab-authority-convergence
description: "Use to converge the DESIGN-LAB top-level Authority and land UI/design-system slices (kit absorption, reskin, token contracts)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [DESIGN-LAB, authority, anti-drift, git, github, ci]
    related_skills: [audited-project-delivery, github-pr-workflow, project-data-boundary]
---

# DESIGN-LAB Authority Convergence

Converge the single top-level Authority for DESIGN-LAB (`D:/All projects/DESIGN-LAB`,
remote `DTALEX66/DESIGN-LAB`) so that every future GPT/Codex/DeepSeek/Hermes/CI
audit starts from live code, not from memory, chat, handoffs, old TaskPacks, or
branch names.

This is a **recurring class**, not a one-off: the Authority is versioned
(`DL-AUTHORITY-YYYY-MM-DD-R<n>`). When the user says "continue authority
convergence", "land R<n>", or "establish top-level authority", start here.

## Standing principles (always on)

- `REUSE-FIRST / OPEN-SOURCE-FIRST / PLUGIN-FIRST / LOCAL-FIRST WHEN POSSIBLE`.
- Do **not** redesign DESIGN-LAB, add a 2nd Backend/Runtime/Ledger, revive an old
  architecture, or do a language/framework rewrite for looks.
- A branch named `FINAL` / `AUTHORITY` / `R4` / `MIGRATION` carries **no** authority
  just because of the name. `main` is the only long-lived code truth.
- Never batch-delete history. Mark it `HISTORICAL` / `SUPERSEDED`; move to
  `docs/history/` only after confirming replacement, active callers, hashes,
  history value, and rollback.
- Destructive actions (merge, remote-branch delete, force-push, release,
  irreversible asset deletion, license acceptance) stay owner-authorized even when
  the user says "go ahead" — the user's standing intent covers building the
  Authority and its gates, not deleting branches. Scope this correctly: merging a
  GREEN PR through the normal gate flow inside the authorized program is not a
  destructive act (the user's standing 「没问题就可以合并」 covers it), so do not stall
  on a merge you already proved green — branch deletion, rewriting pushed history,
  executing a release and accepting a license are what stay owner-gated.

## Procedure (in order)

### 0. Read the live remote FIRST; produce a DELTA, not a plan

Do not trust the baseline written in the handoff/prompt. Re-read everything and
compare to the stated baseline; if different, the live remote wins and you act on
the delta only.

```bash
git fetch origin
git rev-parse origin/main            # exact main SHA
git log --oneline -15 origin/main
gh pr list --state open --json number,headRefName,mergeable
gh api repos/DTALEX66/DESIGN-LAB/branches/main/protection   # required checks + enforce_admins
gh run list --branch main --limit 8 # latest Canonical Verify + artifact count
```

Also pull the current `AGENTS.md`, `docs/architecture/*`, the active taskpack,
and `reports/current/**` from `origin/main:` (not the dirty working tree).

### 1. Verify the versioned package byte-exactly before landing it

The package ships as a zip with a `MANIFEST.json` (sha256 + byte count per file).
Never hand-type the authority files. Extract the **payload** files byte-exact and
re-check each against the manifest:

```python
import zipfile, hashlib, json
z = zipfile.ZipFile(pkg_zip); m = json.loads(z.read(prefix+"MANIFEST.json").decode())
for rel, meta in m.items():
    data = z.read(prefix+rel)
    assert hashlib.sha256(data).hexdigest() == meta["sha256"]
    assert len(data) == meta["bytes"]
```

Land only the payload files (`AUTHORITY.md`, `authority-index.json`, the
`HISTORY-FREEZE-RULES.md`, the final integrated TaskPack) into the repo. Do **not**
land the package's own meta files (`AGENTS-REQUIRED-PATCH.md`,
`APPLY-INSTRUCTIONS.md`, `VALIDATION-REPORT.md`, `MANIFEST.json`,
`PACKAGE-VALIDATION.json`) into the repo — they are the packaging wrapper, not repo
content.

**Pitfall — hash-pinned release files are the unit of integrity.** A consistency
gate that re-hashes the landed release files must treat them as immutable input.
If your new verifier false-positives on a path that is *by design* both a
`lineage`/frozen-product reference and live under a historical glob (e.g. the R5
`tasks.json` under `docs/history/`), **exempt the designated `lineage` set in the
gate**, do NOT edit the hash-pinned release files to make the gate pass (that
breaks release integrity).
**Landed docs move the projection rebind too.** A PR that adds `docs/*.md`
(reports, audit files, decision records) shifts
`reports/current/TASK_PROGRESS.json` / `PROJECT_STATUS.md` and the
`current-report-index`, so run `python scripts/generate_current_reports.py`
(no `--check`) on the branch and stage the regenerated `reports/current/**`
+ index in the same PR, or the CI no-drift gate goes red. Same rebind
discipline applies whenever the R5 ledger (`task-ledger-r3.json`) changes.
**Landed docs move the projection rebind too.** A PR that adds `docs/*.md`
(reports, audit files, decision records) shifts
`reports/current/TASK_PROGRESS.json` / `PROJECT_STATUS.md` and the
`current-report-index`, so run `python scripts/generate_current_reports.py`
(no `--check`) on the branch and stage the regenerated `reports/current/**`
+ index in the same PR, or the CI no-drift gate goes red. Same rebind
discipline applies whenever the R5 ledger (`task-ledger-r3.json`) changes.

### 2. Demote the conflicting records (banner, never delete)

- Root `AGENTS.md`: add a `## TOP-LEVEL AUTHORITY — MUST READ FIRST` block at the top
  that names the authority ID + `/AUTHORITY.md`, and demotes the old DeepSeek
  authority pack to `STRUCTURAL_PREDECESSOR` / execution lineage and the R5 pack to
  `PRODUCT LINEAGE`. Point the current-entry line at the new final integrated
  TaskPack. Keep all historical entries; reclassify, don't remove.
- The UCR handoff (and any handoff that calls itself a "tracked 权威交接"): add a
  first-line banner `HISTORICAL_EXECUTION_RECORD / NON_AUTHORITATIVE` + `CURRENT →
  /AUTHORITY.md`. Its branch count / main SHA / open-PR / CI are all point-in-time
  snapshots and must not be cited as current truth. Preserve the body.
- Stale single-wording (e.g. a leftover `DECLARED_NOT_ENFORCED` when the single
  fact is `CONFIGURED_NOT_ENFORCED`): fix only that stale sentence. Do not reopen a
  language migration or an already-closed P0 just to make a doc prettier.

### 3. Add the deterministic top-level Authority consistency verifier

Match repo conventions: MIT header, a `DLDS-`/`DL-AUTHORITY-…` task-key prefix,
stdlib-only, writes its run record under `.project-local/task-artifacts/` (ignored),
exit 0/1. It should check: `AUTHORITY.md` exists; `authority-index.json` parses and
its `authorityId` matches `AUTHORITY.md`; every `current` path exists; a `current`
path cannot also be `HISTORICAL` (lineage-references exempt); the current
integrated TaskPack exists; root `AGENTS.md` is Authority-first; the demoted
handoff carries the historical banner; the single Ruff fact; and the hash-pinned
release files byte-match the published MANIFEST. Intentionally **do not** freeze
dynamic state (branch counts, CI numbers, SHA) in the gate — those must be
live-read on every audit.

Wire it into `Canonical Verify` (`.github/workflows/canonical-verify.yml`) as a new
job (a pinned-hash checkout + one stdlib-only `python` step — no untrusted input
interpolation in `run:`).

### 4. Rebind — don't delete — the predecessor gate chain

DESIGN-LAB already has a *predecessor* gate
(`scripts/verify_authority_gates.py` = the DeepSeek authority chain, plus its
`authority-gate` CI job). The new top-level gate is a **distinct successor**, not a
replacement. After your edits, the predecessor's snapshot
(`reports/current/DEEPSEEK-AUTHORITY-CHAIN.json`) will go `DRIFT` because you
changed `AGENTS.md` and added a TaskPack. Reconcile it the way the repo does:
**regenerate** the chain so it absorbs the new surface:

```bash
python scripts/deepseek_authority_chain.py            # rewrites the snapshot
python scripts/verify_authority_gates.py --zero-spill  # predecessor chain must PASS
python scripts/verify_top_level_authority.py           # your new gate must PASS
```

A chain `DRIFT` after your own edit is expected and fixed by regeneration — it is
not a signal to delete the predecessor chain or skip it.

### 5. Commit, PR, CI, merge, promote to required checks, read back

- Preserve any in-flight WIP first: `git add -A` + an honest
  `WIP(<phase>): … (in-flight, NOT closed)` commit on that branch so branch
  surgery can't lose it.
- `git checkout -b feat/dl-authority-convergence-r<n> origin/main`; commit the
  authority batch (write the message to a file and use `git commit -F <file>` —
  the project wrapper rejects a quoted multi-line `-m "…"` as shell
  chaining, and a file also sidesteps CRLF noise); `git push`;
  `gh pr create --base main --body-file <file>` (write the PR body to a file the
  same way; a quoted multi-line `--body "…"` is rejected identically).
- Wait for the **exact** merge-commit Canonical Verify to go fully green
  (`gh pr checks <pr>` / `gh run watch`). CI green on a candidate head does NOT
  count — the gate binds the merged SHA.
- Merge (`gh pr merge <n> --merge`). Then, only after the merge-commit CI is green,
  promote the new gate to branch protection — **add on top of the existing
  required checks; never weaken or drop an existing one.** Read back to confirm
  every prior context is still present plus the new one.
- **Merging under `strict=true` protection.** The repo requires branches to be up to
  date, so an open PR flips to `BEHIND` the moment another PR merges and then
  `gh pr merge` refuses. Sequence: `gh pr update-branch <n>` (GitHub merges main into the
  PR branch, which RE-RUNS every check on the new head) → wait for green on that NEW head
  → merge. `gh pr merge --auto` is unavailable here (`Auto merge is not allowed for this
  repository (enablePullRequestAutoMerge)`), so either arm a background
  `gh pr checks <n> --watch --interval 30` with a completion notification or re-poll —
  never merge on a green that belongs to the pre-update head.
- **Base the next branch on the freshly merged main, not on the previous feature head.**
  After a merge: `git fetch origin` then `git switch -c <next> origin/main`. Uncommitted
  work rides across cleanly when the trees are identical, the new PR then contains only
  its own commits, and you skip the `update-branch` round trip; branching from the old
  feature head instead makes the PR show `BEHIND` and re-uses already-merged commits as
  context.
- Read back from `origin/main:` that `AUTHORITY.md`, `authority-index.json`, the
  freeze-rules doc, the final TaskPack, and the verifier all exist on main.

## Adding a vertical-slice entity (Project → Brief → Direction → DesignSystem …)

Class task when the user says "推进切片 / vertical slice / 新实体到仓" (standing goal 
"授权全部推进（除去实操软件任务环节）" covers E-slices; only real host runs and Human
Jury E4 stay excluded). The whole slice — persistence + API + UI + test — must land
in ONE branch so `Workbench / API / Contract / Persistence / Version / Readback /
Evidence` all coexist; a backend-only landing is not a finished slice.

1. **Schema = additive migration, never ALTER on frozen tables.** New `design-lab/
   schemas/state/design-lab-state-<name>-v1.sql`; register in BOTH the
   `state_resources` name whitelist and the owning store's guarded-migration chain
   (creative store: `GUARDED_MIGRATIONS`, applied AFTER the creative family so
   `operation_intent` + `project` FKs exist). Reuse `operation_intent` idempotency;
   tables carry `version` + `superseded_by` for the Version element. DB-level
   invariant enforcement (e.g. a single-choice partial unique index) lands as a
   second additive versioned migration (`-v2.sql`) that CREATEs the index, with
   a fail-closed pre-check that ENUMERATES any pre-existing violation (list the
   offending briefs) and refuses to proceed — it never auto-picks a winner. The
   guarded-migration loop is extended to tolerate an optional 4th entry element
   (the pre-check callable) without changing existing 3-element entries; the
   application-transaction de-selection stays the PRIMARY mechanism, the index
   is the safety net.
2. **Single-writer module** (e.g. `design_layer.py`) — the only code writing its
   tables; it opens the DB through the existing creative-store `connect()` and
   reuses `record_intent`. Catalog-style inputs (design systems) are read-only,
   packaged manifest packages — never rebuild them as a 2nd runtime.
3. **Pitfalls discovered the hard way (DESIGN-LAB creative-store idiom):**
   - `hash_document()`/`request_hash` ALREADY return a `sha256:`-prefixed digest.
     The repo convention is store bare hex (check a neighboring store, e.g.
     native assets stores bare + prefixes on read). Double-prefixing corrupts the
     digest silently — verify output shape once, grep the readback side.
   - A write connection's `row_factory` is not what you assume (not preserved from
     a prior read-connection close). Set `conn.row_factory = sqlite3.Row` inside
     each write transaction BEFORE the first `fetchone()`, or rows come back as
     tuples and `.dict()` / key access explode.
   - Idempotency conflict (same key, different content): the shared store raises
     `CreativeError` (a `RuntimeError`), which the HTTP service's `ValueError`
     except-chain does NOT catch → opaque 500. Fail closed at your module
     boundary: wrap `record_intent` and re-raise as your `…Error(409,
     'IDEMPOTENCY_CONFLICT')` subclass of `ValueError`; register that class in
     the HTTP dispatch before the generic handlers.
   - New UUID id shape is 32 hex (`prefix-` + `uuid4().hex`); the native/job ids
     are 64. Grep the generator before writing route regexes — a `{64}` route
     regex silently 404s every request.
   - In-process loopback tests: `resolve_paths` REQUIRES an `AGENTS.md` marker in
     the project root, so a bare tmpdir is not a project. Seed a marker + set the
     state-root env var to an ignored dir. Test discovery is
     `unittest.discover` under `design-lab/tests/` — new `test_*.py` files are
     auto-picked-up; no manual CI registration. License gate already exempts
     generated workbench bundles.
   - Adding a new `design-lab/schemas/state/*.sql` with `CREATE TABLE` drifts the
     PREDECESSOR gate `contract-graph` (the DeepSeek authority chain's
     `verify_contract_graph.py` snapshots `declared_tables` from every state SQL
     into `reports/current/CONTRACT-GRAPH.json`, tracked in-repo). On the PR it
     fails ONLY that one of the 7 predecessor sub-gates with
     `CONTRACT_GRAPH=DRIFT fields changed since generation: ['declared_tables']`.
     Fix it the way the repo does — ABSORB, don't bypass: run
     `python scripts/verify_contract_graph.py` (no `--check`) to regenerate the
     snapshot, `git add` it, then confirm `verify_authority_gates.py --zero-spill`
     reports `AUTHORITY_GATES=PASS gates=7 failed=none` before pushing. The
     regenerated diff must be EXACTLY your new tables + the generation-time
     timestamp — anything else means the diff touched an unrelated concept and
     must not be committed. The `--check` mode compares the whole document except
     `generated_at`/`subject_sha`, so committing the regenerated snapshot is safe.
     Prove the diagnosis before re-recording: `grep -c <new_table>
     reports/current/CONTRACT-GRAPH.json` returning 0 shows the committed snapshot
     predates your table — quote that count in the commit message rather than asserting
     the cause, so a reader can re-run it.
     This is distinct from (and must be done IN ADDITION TO) the top-level
     Authority gate: a predecessor-chain DRIFT after your own schema change is
     expected and fixed by regeneration, never by weakening or deleting the gate.
   - A read path that opens its OWN bare `sqlite3.connect(mode=ro)` skips the
     guarded migration chain: the new tables exist in the database only after
     the first write went through the guarded `connect()`. A fresh project's
     read then raises `no such table`, and the HTTP layer maps that
     `sqlite3.Error` to 503. Route EVERY read through the same guarded
     `connect()` the write path uses (migrations are apply-once, idempotent).
   - An error response sent before the request body is consumed (401/404/400
     raised in `guard()`/routing before the body read) leaves unread bytes in
     the socket; the server's close resets the connection and the client sees
     `ConnectionAbortedError` (WinError 10053) instead of the 4xx body. Drain
     the unread request body (up to the declared `Content-Length`) before
     sending any 4xx/5xx — deterministic error surfaces beat load-dependent RSTs.
4. **UI**: add the entities as first-class plain-user flows in the workbench
   (forms → API), TS contract types for every payload; advanced/raw JSON stays in
   the existing Advanced section. `style.css` + `index.html` + `main.ts` in the
   same commit.
5. **Bundle sync**: if `main.ts` changed, run a final Vite build and commit the
   `build/` output — the CI gate is a no-drift `git diff --exit-code` after a
   fresh build. Verify locally: fresh build, grep the bundle for your handler
   names, measure real bytes (Vite's "kB" line rounds).
6. **Tests = one contract test class proving the full slice through real loopback
   HTTP**: create → direction → choose → bind → full readback; idempotent retry
   returns the SAME identity; 409 on key/content conflict; 400/404/401 fails
   closed; catalog read-only; owner-scoped reads. The full Python suite is slow
   (>420s locally, times out a foreground terminal) — run it background with a
   completion notification, not blocking waits; and prefer the exact-SHA CI
   `Python gate` (same suite, fresh clone) as the stronger evidence over a local
   re-run — a background local child can be killed by the host, and exit
   `1073807364` (DBG_TERMINATE_PROCESS) is that kill, not a test failure, so do
   not re-run the suite locally when CI already ran it at the delivered SHA. Prove transport fixes
   POSITIVELY: a stress script must assert the expected status distribution
   (per path, N requests × expected code), not just `errors == 0` — a script
   that crashed before attempting any connection also reports zero errors
   (vacuous green). Keep in-flight concurrency at or under a single-threaded
   `HTTPServer`'s listen backlog so the proof mirrors the serial CI suite.
7. **Browser E2E (the P0 `browser E2E` AUTHORITY item) — the right closing
   evidence for a slice, and the pattern to follow.** The static
   `workbench-gate` CI job's comment explicitly delegates browser-level E2E to
   the E-slice gate ("owned by the E-slice gate, not this static node gate; it
   is NOT silently dropped"). So a browser E2E lives under `design-lab/tests/`
   (auto-discovered by `run_python_tests.py`), NOT as a new browser-install step
   in the static workbench-gate node job. The shape that works, and why each
   part is load-bearing:
   - **Reuse the existing same-origin self-server — no 2nd runtime, no separate
     static server.** `http_service.make_server(service, token)` already serves
     `/workbench` (index.html), the committed `build/main.js`, and the whole API
     under ONE origin, with `CSP: connect-src 'self'`. The E2E navigates
     `http://127.0.0.1:<port>/workbench` in a real Chromium and the page's own
     `fetch('/api/…')` is same-origin and passes `guard()` with zero special
     handling. Driving the committed bundle is the point (Build Output Truth:
     the browser runs the exact artifact CI no-drift-checks).
   - **Python shell + Node driver split.** The `test_*.py` shell spins the real
     loopback service on an OS-chosen port (mirror the design-layer contract
     test harness: fresh synthetic project + in-memory `secrets.token_hex(32)`
     + `make_server(service, token, port=0)` + a background `serve_forever`
     thread), then runs a Node Playwright driver via `subprocess`. The driver:
     connect (fill `#token`, submit `#connect-form`) → create project → refresh
     → drive each 05 design-layer form (persist brief, raise direction, click
     the per-direction "选为方向" button, bind design system) → assert the
     PERSISTED DOM readback (`#design-briefs` / `#design-directions` /
     `#design-bindings` / `#design-binding-active`), not just that no error was
     thrown. Claim the evidence level honestly: this lands at **E2
     CONTROLLED_RUNTIME** (a real browser ran the slice) and does not by itself
     become E3 REAL_WORKFLOW (no host run) or E4 (no human jury); say so in the
     report so it is never misread as a host/acceptance proof.
   - **Probe-driven HONEST SKIP — never a fake pass and never a forced install.**
     The in-repo Playwright npm-cache
     (`.project-local/task-runtime/playwright/npm-cache/_npx/<hash>/node_modules`)
     is gitignored, and the per-user `ms-playwright` Chromium revisions may not
     match the in-repo playwright build's expected revision — so a clean CI
     checkout has NEITHER. The shell must probe for (a) `node` on PATH, (b) that
     npm-cache dir, (c) a locally installed Chromium revision; if all three are
     present it runs the real browser, otherwise `self.skipTest('<exact
     reason>')`. Do NOT add a `playwright install` step to CI — the network the
     user's environment blocks makes that a flaky forced download.
   - **Zero-download launch via `executablePath`.** When driving a pre-installed
     Chromium, pass `launch({ executablePath: <chromium exe> })` so playwright
     skips its revision lookup entirely (an installed revision that differs from
     the build's expected one otherwise triggers "run `playwright install`").
     Resolve the `playwright` package from the repo cache with
     `createRequire(nmDir + '/noop.js')` + `require('playwright')` so the import
     resolves against the repo npm-cache, not the script's own directory.
   - **Async DOM settle: wait for the specific `<option>`/row to ATTACH, not for
     the container to be visible.** After a create/refresh round-trip the
     repopulated `<select>` is still being appended by an in-flight API response;
     waiting for `#project` to be *visible* — or reading `allInnerTexts()`
     immediately — sees only the pre-create placeholder. Wait for the new
     `<option>` (or list row) to reach `attached` state via a `hasText` match,
     THEN `selectOption({ label })` / click.

8. **Revision and lineage: content immutable + events append-only (`Brief v1 → v2`).**
   A table carrying `version` + `superseded_by` where every write inserts `version=1` and
   `superseded_by` stays NULL is *version-ready*, not versioned — never describe that as
   complete versioning. A real revision is: INSERT a new content row at
   `version = parent + 1`, move ONLY `superseded_by` on the parent (comment it as the one
   column a revision may touch, and assert the content columns — JSON payloads and
   `spec_sha256` included — byte-identical), and append one typed event in the SAME
   transaction. History belongs in an append-only DDL table, not in mutable rows:
   `BEFORE UPDATE` / `BEFORE DELETE` triggers `RAISE(ABORT)` and the module appends with a
   plain INSERT (no `OR REPLACE` / `OR IGNORE`) so a repeated `event_id` fails closed
   instead of overwriting history. Register the new state SQL in `state_resources._NAMES`
   and after the previous version in the store's `GUARDED_MIGRATIONS`, and prove the
   upgrade of a POPULATED database (with its pre-migration backup), not just a fresh one.
   Keep one source of truth per fact: `chosen` stays MATERIALIZED state while the choice
   itself is an event, and an append-only binding row belongs to the version it was bound
   to — so revising a chosen direction carries the choice to the new version (record
   `chosen_moved` in the payload) and leaves `active_binding` null until rebound. Read the
   chain through `lineage_*` helpers that resolve it from the event edges (any member
   returns root/live/versions oldest-first), and fail closed on a stale target
   (409 `STALE_REVISION`) rather than forking the chain. The new state SQL drifts the
   predecessor contract graph's `declared_tables` by construction — re-record it (see the
   predecessor-chain bullet in item 3).

## Branch cleanup (P1) — identify without deleting

Class task when the user says 分支整理/清理 or the standing goal reaches the
P1 branch-cleanup item. Standing user preference: clean ONLY proven-useless
or regenerable items, first cross-check branches/PRs/schedules/WIP, and
report per-item 保留/删除/阻塞 status — never announce a cache-cleanup as a
directory-delete. Remote branch deletion stays owner-authorized even after
you have classified the candidates (see Standing principles).

1. `git fetch origin` first — branch counts are live-only (rule 18), never
   from a handoff.
2. `git branch -r` (full inventory, one wrapper call; the wrapper blocks
   `| grep` pipes, so run `git branch -r --merged origin/main` as its own
   second call and filter the intersection yourself, or batch in
   `execute_code`).
3. Merged set = deletion candidates: they add nothing to `origin/main`
   (verify with `git log --oneline origin/main..origin/<branch>` = empty).
   Do NOT delete — present the exact candidate list for owner sign-off; each
   name is classified by CONTENT, and a branch named FINAL/AUTHORITY/R4/
   MIGRATION/SUPERSEDED carries no authority or safety either way.
4. Unmerged set = preserved by default: classify per-branch, one at a time
   (ABSORBED / PARTIAL_ABSORBED / REIMPLEMENT / SUPERSEDED /
   HISTORICAL_ONLY / REJECTED / ACTIVE_RESIDUAL, per Authority §10) using
   `git log --oneline origin/main..origin/<branch>` divergence — never
   batch-classify, never whole-merge an old governance/migration branch on
   unique-commit count alone.
5. Report as a status table: merged→候选删除(owner-gated), active WIP→保留,
   blocked items→阻塞原因. That table is the deliverable; deletion is a separate owner-authorized act.
6. **Owner-approved execution (delete + freeze), once the disposition list is authorized:**
   - Remote-delete a branch ONLY after tagging its tip locally AND pushing the tag
     (`superseded-tip/<branch>` + `git push origin <tag>`) — the tag is the rollback point,
     and because GitHub is the second machine's only sync channel, a local-only tag gives
     no rollback there.
   - Delete local branches with `git branch -d` (merged-only semantics) for absorbed/residual
     branches; a non-merged branch being KEPT is the "freeze" disposition — leave it in place
     and record it in the ledger, never `-D` it without a tip tag + owner sign-off.
   - Remove any `.hermes/w/` worktree with `git worktree remove --force` BEFORE deleting its
     branch; then `git remote prune origin` to drop stale tracking refs of deleted branches.
   - Pure-residual local-branch sweep: `git branch --merged origin/main` → batch `git branch -d`
     (their content is already in main — zero loss) — separate from the 9-unique-commit
     disposition list, which needs per-branch evidence.
   - Land a tracked disposition-ledger doc via PR: one row per branch — judgment
     (合并/冻结/删除) + the reproducible evidence commands (`merge-base --is-ancestor`,
     `log main..<branch>` blob checks). Disposition without the ledger is an unreviewable
     destructive act.
   separate owner-authorized act.

## Session wrap-up: tracked convergence handoff (second-machine sync)

Class task when the user says 总结/收口/“总结和上传” at the end of a multi-slice
session, or when a handoff must reach the user's **second machine** — for that
machine GitHub is the ONLY sync channel, so a chat-only summary never lands; the
record must be a tracked doc that survives `git pull`. Standing user preference:
handoff docs are tracked in-repo (never left in `.hermes/`), evidence is graded
with real SHAs, and the doc is not a new Authority.

1. **Landed slice of content, in `docs/decisions/`** (the repo's dated-record
   convention, e.g. `<TOPIC>-<YYYY-MM-DD>.md`). Banner it
   `SESSION_CONVERGENCE_RECORD / EXECUTION` and point at `/AUTHORITY.md` as the
   live authority — a handoff is never above the Authority (rule 4).
2. **Content shape** (distill, don't narrate the incident): a table of each
   landed slice (PR → merge SHA → evidence level E1/E2/…), the real root-cause
   fixes by MECHANISM (drain_body / guarded connect / snapshot-absorb /
   executablePath…), the P0 convergence verdict against AUTHORITY §15, and the
   owner-gated remainder (branch-delete candidates, Ruff-enforce decision, the
   excluded host E3/E4 layer).
3. **A docs-only commit carries ONLY the new `.md`.** The local verifiers
   rewrite `reports/current/LANGUAGE-BOUNDARY-SCAN.json` on every run, and its
   regenerated diff can bundle UNRELATED accumulated surface drift (new node
   manifests/lockfiles, file counts) that predates your doc. Before staging,
   `git checkout -- reports/current/LANGUAGE-BOUNDARY-SCAN.json` (and any other
   regenerated snapshot you did not intentionally change) so the diff is
   exactly your one file — never let a regenerated snapshot leak into a docs
   commit, and never regenerate it as part of a docs-only change.
   **Exception: a reports REBIND is a deliberate docs+snapshot commit.** When
   the batch landed code on the same feature branch, the final commit stages
   the regenerated `reports/current/**` + `design-lab/config/current-report-index.json`
   together (that IS the rebind, `CURRENT_REPORTS=PASS mode=generate`), and
   only THEN does the docs-only commit carry the handoff `.md` alone.

   **External-spill audit (the user's 整理/清理瘦身/追踪外溢收尾请求).** Before
   declaring a session clean: (a) `git status` → working tree clean on the
   branch; (b) `git ls-files .hermes/task-runtime` and `git ls-files
   .project-local` both return EMPTY (the guard keeps runtime/evidence in
   gitignored dirs — a non-empty result means a runtime file was committed and
   must be de-tracked); (c) confirm the `.gitignore` lines that cover those
   dirs still exist (DESIGN-LAB: `.hermes/` + `**/.hermes/` + `.project-local/`)
   — ignore rules can be lost in a rebase; (d) delete this session's scratch
   files (spec/commit-msg/PR-body written under `.hermes/task-runtime/`) — they
   are gitignored so deletion is zero-risk; tracked-tree additions must all sit
   under source/docs paths, never under the runtime dirs.
4. **Then the normal step-5 flow**: PR → wait for the merge-commit Canonical
   Verify to read `success`/`completed` (gate binds the merged SHA, not the
   watch stream) → merge → read the file back on `origin/main`. Only after the
   merge has it landed where the second machine can pull it.

## VERIFY-THEN-PATCH: 先验证再修补缺口（任务书对账流程）

Class task when the user provides a task pack / spec (调研方案 / 成熟化方案 / TaskPack) with many items, some of which may already be implemented on main. The strategy is **VERIFY → REGRESSION GUARD → PATCH ONLY IF MISSING → EXACT-SHA PROOF**, NOT "re-implement everything from scratch". Re-implementing already-merged work creates a second state semantic and is the #1 drift source.

1. **Baseline freeze first.** `git fetch origin` → record `START_SHA = git rev-parse origin/main`. Every test/wheel/browser artifact/state report binds to this SHA. If main moves mid-task, do NOT mix evidence from different SHAs — re-freeze and re-verify.
2. **Per-item code-read verification, not memory.** For each task-pack item: grep the source tree for the implementation (the function, the test, the schema), read the actual code, and confirm the invariant holds. "The handoff says it's done" is NOT evidence — the code is. When an item IS implemented: write a one-line regression note (test file + test name + what it pins). When it is NOT: write the spec for the missing piece and implement it.
3. **Deliverable shape = gap-only.** The PR body opens with a VERIFY-THEN-PATCH reconciliation table (item → status: 已实现/缺失/部分 → evidence: test file + commit). Only the missing/partial items get new code. The table IS the deliverable — it proves the agent did not blindly re-implement.
4. **Do NOT skip the gap items because "the task pack is old".** A task pack may be 3 weeks old; main may have moved. The reconciliation table reconciles the task pack's claims against CURRENT main — items that are now done get marked "已实现 (commit X)" without re-work; items still missing get implemented. The table is the bridge between the old spec and the new reality.
5. **For DESIGN-LAB specifically, the gate chain is the final proof:** after all patches, run `verify_design_lab.py` (aggregator), `verify_authority_gates.py --zero-spill`, and `generate_current_reports.py` — all three must PASS before the PR is pushed. The aggregator total goes UP by the number of new verifiers added (e.g. 50→51 when a new matrix verifier lands in SCRIPTS).

## Building capability/service surfaces without operating them (P1-CONTROL-SPIKE class)

Class task when the standing goal says 「服务和操控的能力全部搭建好，真实操控交给其他模型/软件，不在 Hermes 做」 — deliver the CONTRACTS, not the runs.

1. **A capability/declared-routing matrix is a declaration, never a proof.** The deliverable shape: a tracked `config/<name>-matrix.json` + a draft-2020-12 schema under `design-lab/schemas/` + a pure-stdlib fail-closed verifier in `design-lab/scripts/` + parametrized negative-control tests + one-line fold into `design-lab/scripts/verify_design_lab.py`'s `SCRIPTS` (total +1) with a comment explaining why the new verifier is in-script (like F-4's, a tracked declaration validates on a clean checkout → PASS/exit 0, and only turns red when someone commits a declaration that violates the rules).
2. **Evidence floor: `supported=true` must carry `evidence_level>=E2` + a `qualified_sha`.** A capability claim without an exact-SHA locator is un-auditable — reject it. All unverifiable hosts stay `supported=false/E0` honestly; never flip a value to green to "complete" the batch. The verifier must assert this rule, not the matrix author's goodwill.
3. **Layering red line (task-book verbatim): Computer-Use 负责 reachability；Host-native readback / artifact rehash 负责 truth；DESIGN-LAB State/Evidence 层负责 provenance.** The verifier enforces: a host with `reachability_model=computer-use` must have a non-`none` `truth_model` — "能点软件 ≠ 解决集成". Also enforce `no_bypass_license=true` on every host (never design a path that bypasses vendor licensing) and coverage of at least the two declared adapter-route hosts.
4. **Negative-control fixtures go under `.project-local/task-artifacts/<topic>/` (gitignored)** — a bad-matrix file written there proves the FAIL path without polluting the tracked tree (same convention as F-4's host-e3 records).
5. **Test-class delegation without inheritance bloat.** New recovery/replay test files that reuse an existing P0 HTTP harness: inherit plain `unittest.TestCase`, call `ExistingHarness.setUp(self)` in your own `setUp`, and bind the helpers by name (`request = ExistingHarness.request`, …). Inheriting the harness class re-runs every one of its test methods inside your module — `unittest discover -p` then runs the P0 suite TWICE per file (41 tests instead of 23) and your `sys.path` import of the sibling module must precede the class body or the base-class reference `NameError`s.
6. **Idempotency scope is per-URL.** `choose` is scoped `choose:<direction_id>`: same key + different direction = different intent = legitimate new request (NOT a 409); same key + different payload on the SAME direction (different actor) = 409 `IDEMPOTENCY_CONFLICT`. Write the recovery test to match the actual scope, not the intuition that "same key always conflicts".

## Post-convergence maintenance: closing §15 items, removing index drift, realigning evidence vocabulary

Run after an Authority release is merged and the user drives the next P1 sweep (report lines like "§15 still lists completed items", "index lists a drift that no longer exists", "evidence vocabulary lags the Authority"):

1. **Close §15 items from commit evidence, not from memory.** Each §15 line gets a status: `CLOSED_WITH_REGRESSION_GUARD <commit/pr> <gate>`, `ACCURATE_RESIDUAL <exact residual>`, or `REMAINS_OPEN <reason>`. Never delete a §15 line wholesale (governance history) and never mark closed without a regression guard that re-fails if the fact regresses. Editing AUTHORITY.md is §17-compliant Authority modification: owner intent + reason + superseded item + impact note + the accompanying pinned-hash update below. An item that claims a gate is a **required check** closes only from the live branch-protection contexts — `gh api repos/DTALEX66/DESIGN-LAB/branches/main/protection --jq '.required_status_checks.contexts'` — matched against the job's `name:` string: the required context IS the job name (e.g. `Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)`), so a job merely existing in the workflow YAML, or its job id, proves nothing about required-check status. Conversely, before assuming a red gate blocks the merge, check whether it is in that list at all — a non-required job can fail while the PR stays mergeable, which is a reason to fix it, never to merge past it.
2. **Removing an authority-index drift entry is a pinned-hash flow, not a doc fix.** The index is one of the four SHA-256-pinned release files inside `scripts/verify_top_level_authority.py` (`R2_RELEASE_HASHES`). After editing `AUTHORITY.md` and/or `.project/governance/authority-index.json`, recompute `sha256` for the changed files, update the pinned entries, and add a short `# P… closed <date>: re-pinned after <change> (supersedes <old-hash12>)` comment in the dict. This is NOT weakening the gate — it is the hash-pinning flow the gate was built for; weakening would be deleting the check or the dict entry.
3. **Evidence-ladder realignment touches the human-semantic layer only.** `capability-status.json` / `capability-evidence-index.json` hold `evidenceLevels` (id E0–E5 + free-form `label`/`claim`/`proof`) plus a separate machine enum `capabilityStates` (`release-verified` / `commercially-proven` / …). Realigning E-ladder semantics to a new Authority release = rewrite `label`/`claim`/`proof` only. The machine enums, `promotionRules`, `hardRules` and state lists are verifier-pinned exact values (`verify_product_manifest_v3` asserts the literal enum list and hard-rule phrases) — changing them cascades across config, data records and verifiers. Check which side already carries the new vocabulary before touching anything: the manifest schema often converges first and only the status file lags. After any capability-status change, re-run `python design-lab/scripts/verify_design_lab.py` (49-item aggregator, includes manifest v3 + capability-evidence v4 + host-adapter) and keep the run OK before committing.

4. **A predecessor-chain `DRIFT` after your own edit is expected — re-record with the file's OWN generator, never hand-edit.** Every sub-gate compares the live tree against a snapshot generated earlier, so any legitimate change lands as `DRIFT`: a new state SQL drifts `declared_tables`, and adding KEYS to `reports/current/*.json` (e.g. a provenance envelope `projection`/`subjectSha`/`fresh`/`generatedBy` written across all reports) drifts the contract graph's field set with `fields changed since generation: [...]` even though no table changed. Recover by running the owning generator WITHOUT its verify flag — `python scripts/verify_contract_graph.py`, `python scripts/deepseek_test_gate_report.py`, `python scripts/generate_current_reports.py` — then require `python scripts/verify_authority_gates.py --zero-spill` to read `AUTHORITY_GATES=PASS gates=7 failed=none`.
   **Pitfall — chain projection treats mutable ledgers' bytes/sha256 as a stability claim.** `deepseek_authority_chain.py --check` only excludes `bytes`/`sha256` for entries carrying a `mutable_state` marker; the marker was previously applied to the DeepSeek authority ledger only. The R5 product ledger (`design-lab/config/task-ledger-r3.json`) is also rewritten at the close of every task, yet its digest was still compared verbatim — so any ledger update made the chain `DRIFT` on that file even after regeneration, and re-regeneration in the same commit did not help (the projection still contained the old bytes). Fix (already landed in `508d54b`): `build()` now marks BOTH `AUTHORITY_LEDGER` and `LEDGER` with `mutable_state`, and the `--check` projection skips bytes/sha256 for any entry with that marker. If you see `AUTHORITY_CHAIN=DRIFT entries changed since generation: ['design-lab/config/task-ledger-r3.json']` after a fresh regeneration of the chain, the root cause is the entry missing its `mutable_state` flag, not another generation pass. Confirm the fix is in place before assuming further drift: `python scripts/deepseek_authority_chain.py --check` should print `mutable ledger digest recorded at generation was …` listing 2 mutable entries. When you add NEW mutable files to the chain's candidates set, extend the same `if rel in (AUTHORITY_LEDGER, LEDGER, …)` set — never special-case them ad hoc in `--check`.
5. **Find the file's OWNER before giving it new fields.** Each `reports/current/*.json` is written by one generator, and that generator's format wins: `LANGUAGE-BOUNDARY-SCAN.json` is rewritten by `verify_language_boundary.py`, which emits no provenance envelope, so an envelope added by hand (or by a report-wide script) is stripped on the next chain run and the file silently returns to its own shape. Add fields only through the owning generator, and expect a stale committed copy of such a snapshot to carry surface drift that predates your change (file counts, newly-detected manifests/lockfiles) — that drift is real state to re-record, not noise to revert.
6. **Local `DRIFT` is not always CI `DRIFT` — read the CI job log to see which sub-gates actually failed.** `test-gate` compares against `.project-local/task-artifacts/test-run/history.jsonl`, which exists only in a local checkout, so it reports `TEST_GATE=DRIFT results changed since generation` as soon as your own runs advance that history; a fresh CI checkout has no history and instead EXECUTES the critical 220-test set (three orders + a repeat) and passes. `contract-graph` drift, by contrast, reproduces deterministically in CI and is the one you must re-record. Pull the per-gate verdicts from the failed job's log (per-job steps + full log via the jobs API — see the CI-triage skill) and bind them to the exact subject SHA before changing anything.
7. **`generate_current_reports.py --check` compares tracked content AND the recorded git observation.** Two independent triggers: (a) any change to tracked content (a new doc, a re-recorded snapshot, your own fix commit) drifts the 9 bound outputs + the report index; (b) the index stores a `gitObservation` sha and the check re-generates from that STORED snapshot, requiring it to still be an ancestor of HEAD (`governance/reporting.py` substitutes the stored observation as the snapshot and calls `git merge-base --is-ancestor`), so a **rebase or `--amend` that rewrites the branch DRIFTs even when the tree content is byte-identical** — the recorded SHA simply drops out of history. The routine operational version of trigger (b): landing even ONE new
   PR onto main re-orphanates the committed `reports/current/**` projections (their
   recorded `gitObservation` is no longer an ancestor of the new tip), so a projection
   rebind is expected bookkeeping after ANY merge batch — not only after your own rebase —
   and the rebind commit itself lands as `STALE`. Rebind by running the generator without
   `--check`; after a rebase commit that rebind as a **NEW commit, never `--amend`**, because an amend rewrites the very SHA the rebind just recorded and re-breaks ancestry. Re-run `--check` after the commit to prove the report bind and the gate snapshots do not oscillate against each other (a rebind that flips back on the next chain run is an ownership error, not a flaky check). Expect **`STALE`, not `PASS`, as the terminal
   state** once the rebind itself is committed: HEAD has advanced past the recorded
   observation and the check prints `CURRENT_REPORTS=STALE … byte-stable against a subject
   HEAD has advanced past; rebind required - not a product-pass claim`. That is the
   self-referential steady state (rebinding again only adds another commit and another
   `STALE`), so do not chase it, do not report it as a pass, and never hand-edit the index
   to force `PASS`.

## Adding a qualification gate (fail-closed tri-state)

Class task when a gate must prove something that cannot be proven locally (a
published release, a host run, an external readback). The gate's job is to be
HONEST under failure, not to be green.

1. **Three outcomes, never two.** `PASS` (exit 0) / `BLOCKED` (a contradiction —
   the facts disagree, non-zero) / `INCOMPLETE` (a check that could not run: no
   token, no network, an artifact that will not download, no reference digest).
   `INCOMPLETE` is never PASS and is never absorbed into one. Prove it on the REAL
   default path: run the script with no token in the env and quote the contract
   line with its exit code (`RELEASE_PREFLIGHT=INCOMPLETE checks=0`, exit 3).
2. **A gate needing a tag/token/network does NOT join the daily aggregate.**
   `verify_design_lab.py`'s 49 items are an EXPLICIT list (`SCRIPTS` +
   `EXTRA_CHECKS`), so a new `verify_*.py` is not auto-discovered — which is what
   you want, because appending a verifier whose unprovable outcome is non-zero
   converts an unsatisfiable condition into a permanently red daily gate. Leave it
   out and record the decision in a comment beside the existing `RELEASE_VERIFIER`
   exclusion; invoke it from its own workflow step instead.
3. **Wire it in additively.** Append a tag-only step (`if: startsWith(github.ref,
   'refs/tags/')`) to `release-gate.yml` with `env: GITHUB_TOKEN: ${{ github.token }}`
   and values from GitHub's trusted default env vars (`GITHUB_REF_NAME`,
   `GITHUB_SHA`, `GITHUB_REPOSITORY`, `GITHUB_RUN_ID`), never an expression
   interpolated into the `run:` body. The diff must be insertions-only: quote
   `git diff --stat` showing 0 deletions as the proof that no existing step was
   relaxed, reordered or removed.
4. **The downloader is a credential surface.** Network access goes through ONE
   injectable `fetch()` (so the tests can exercise the whole PASS path without a
   socket), the token comes from the environment only (never a CLI argument), and
   because the API redirects an archive to a signed URL on ANOTHER host the fetcher
   must drop the `Authorization` header whenever the host changes. Read that code
   before trusting a gate that claims to "query and download", and require a test
   that fails if the token were forwarded. **GitHub API legs must send
   `Accept: application/vnd.github+json`** — a request that omits it (or sends
   `application/octet-stream`) makes the artifacts / release-asset endpoints return
   HTTP 415 "Must accept 'application/json'" instead of the payload. That 415 is a
   protocol bug, not a permissions or network failure: read the body of the error
   before triaging a gate as BLOCKED/INCOMPLETE, because the fix is a one-line
   header on the JSON-parsing leg (the true binary download leg keeps
   `octet-stream`). A gate that silently treats the 415 as INCOMPLETE hides the
   header bug forever — pin the expected status (200 + digest match) so the real
   payload is what the proof binds to.
5. **A same-run value comparison is a red flag, not a check.** If a step compares
   two values its OWN run produced (e.g. `github.sha` against a subject SHA that run
   wrote), it proves a declaration is self-consistent and NOTHING about artifact
   identity; the audit-grade version queries the API, DOWNLOADS the artifact,
   re-hashes the bytes and compares the digest. A step named for an external
   readback that never calls the API is a name-only gate — grep the step body for
   the mechanism before trusting the name, and say so in the finding rather than
   counting it as coverage.

## Delegated (parallel subagent) work in DESIGN-LAB

Class task when the user asks for 实时并行智能体调用 / parallel subagents in this
repo (standing preference: parallel推进, 嫌串行慢).

1. **A child's summary is a CLAIM, never evidence.** Verify on the mainline before
   believing it: `git status --short` must list exactly the files it claims (and no
   forbidden path); re-run its headline command yourself and compare the pass lines
   byte-for-byte. Two real failures of this kind: a child that reported a completed
   P1 task with ZERO files on disk, and a child that reported pinning an action "to a
   fixed SHA" where the SHA did not exist. Either kind invalidates the whole batch.
   **Run the cross-cutting gates on the mainline too** — the aggregate verifier
   (`design-lab/scripts/verify_design_lab.py`, 49 items), the authority chain
   (`scripts/verify_authority_gates.py --zero-spill`) and
   `scripts/generate_current_reports.py --check`. A child can pass every test it wrote
   while leaving a gate it never ran drifting (contract-graph, the report bind), so the
   spec must NAME those gates as required verification and the mainline must re-run them
   before believing the batch. Read the child's diff as well, not just its output: the
   strongest claims to falsify are "the pre-existing test was strengthened, not weakened"
   and "content columns were not modified" — check the assertion text and the UPDATE
   statement, and confirm a regression guard exists that would fail if the old behaviour
   came back.
2. **Keep the delegate payload small.** Write the spec to
   `.hermes/task-runtime/<x>_spec.md` and let the child read it; a large inline
   payload can die in delivery as `stream timed out before it could be delivered`.
3. **Children share the working tree.** Assign disjoint file domains by
   instruction, and keep `reports/current/**`, the pinned release files, `docs/` and
   `AUTHORITY.md` on the mainline: concurrent regeneration of the same snapshots by
   a child and the mainline produces interleaved writes nobody can attribute.
4. **Rate limits are per account, not per child**: a batch killed by HTTP 429 at
   ~130s will die again if re-dispatched identically — finish those items on the
   mainline in order instead of re-sending the same batch.
5. **Tell a child explicitly not to commit/stash/push**, and to leave the change
   in the working tree; the mainline commits it in its own evidence-bearing
   commits (the child's report then feeds the commit message's provenance).
6. **A child's honest `incomplete` list is a feature, not a failure** — it surfaces
   the cross-zone side effect (e.g. "the index edit made reports/current stale, but
   reports/ is my forbidden zone") that the mainline must finish itself.
7. **Require spec-silent decisions to be surfaced, and review them.** A capable child
   resolves cases the spec never named (which status code a stale target returns, which
   side keeps a materialized pointer, whether a binding follows a revision). Ask for them
   explicitly (the output schema's `incomplete` field, or a review-only notes list), then
   read the docstring and the test that pins each one and either accept it in the PR body
   as a reviewed decision or change it before merge. An unlisted behavioural choice
   shipping unreviewed is the failure mode — not the extra behaviour itself.
8. **Do not parallelise across an unfrozen contract.** Two children run together only when
   their file domains are disjoint AND the interface between them already exists. A UI
   child that consumes an API child's not-yet-written endpoints is not parallel work —
   sequence it (backend merged to main first, then the UI branch based on the new main),
   or freeze the endpoint contract in the spec before either starts. Fill the wait instead:
   while a child runs or CI is in flight, write the NEXT batch's spec file — that is the
   parallelism the user actually feels, and it removes the idle turn entirely.
9. **Full-audit dispatch: read-only, domain-split, mixed toolsets.** When the class is a full-scope AUDIT (the deliverable is findings + a TaskPack, NOT a PR), split children by DISJOINT domains and mix two toolsets: **repo-audit children** (authority/state, frontend+browser-E2E, packaging+CI+branch) are read-only, each is handed the frozen main SHA, scratch ONLY in its own `.hermes/task-runtime/<domain>/` subdir (spec at `..._<domain>_spec.md`; build/venv go there too), and stay OFF `reports/current/**` / pinned release files / `docs/` / `AUTHORITY.md` (mainline owns those, item 3). **Pure-web-research children** (the 官方事实核验 layer — a vendor/SDK capability matrix, a local-provider API contract) use ONLY web_search/web_extract, need no project wrapper and no repo access, and run alongside the repo children because they share no files — they feed the repo children's conclusions without colliding. Give EVERY child a structured JSON `output_schema` (`summary` + per-domain findings + `evidence_refs` + `blocked`) so results re-enter cleanly and the mainline re-runs the `evidence_refs`, not the prose; a child's `blocked`/non-green items are the re-verify signal (item 1). The main thread ALONE owns the frozen baseline SHA (fetch + `rev-parse` BEFORE dispatch), the cross-cutting gate re-run, and the assembly skeleton — children only produce evidence.

## Ingesting an external/cloud audit doc (对比分析 → docs/audits/ + follow-up tasks)

Class task when the user pastes an external audit report (cloud GPT full-repo audit, third-
party review) and asks 对比分析 / 加入本项目文档 / 列出后续任务. Deliverable = TWO tracked
docs + rebind projections in ONE PR. You list the audit's proposed tasks; you do NOT
execute its task list in the same PR, and the doc itself is never a task source of truth.

0. **Dedup guard — confirm the pasted audit is NEW before archiving.** Users routinely
   re-paste the same cloud report or an export of one already ingested. Before building
   the fact table, probe the existing `docs/audits/*-RAW.md` set: compare body byte-size /
   line count and grep a couple of distinctive probe strings (plus the source sha256)
   against each archived RAW's body. If one matches, do NOT re-ingest — point at the
   existing RAW and, only if live state has moved since, add a new CROSSWALK row; skip the
   rest. Proceed to the fact-check step below ONLY when no existing RAW matches.

1. **Fact-check the doc's self-declared "verified" facts against live state BEFORE
   archiving anything.** Build the fact table (claim | measured | verdict) in the
   crosswalk doc. Re-verify each one:
   - claimed baseline SHA: `git cat-file -t <sha>` — an audit that claims it read
     "main HEAD live" may have recorded a **tree object ID as a commit SHA** (a tree
     belongs to some commit; attribute it with `git log --all --format='%H %T'`).
   - claimed HEAD commit message: `git log --all --grep="<msg>"` — empty = that commit
     does not exist in this repo's history; the doc's timeline may come from another
     environment (or be fabricated). Never inherit its time line.
   - protection state: live `gh api …/branches/main/protection` (+ `/enforce_admins`,
     `/required_status_checks.contexts`) and `gh api …/license` — the doc's snapshot
     may be stale or wrong (a doc claiming license=null / enforce_admins=false against
     a repo that actually has license=MIT / enforce_admins=true is the tell).
   - "unspecified" claims about the repo's authority doc are checked against the root
     (`AUTHORITY.md` + governance index) first — external auditors frequently fail to
     read the in-repo authority chain and mark things "未指定" that are pinned.
   Adopt ONLY the doc's framework content (risk matrices, schema shapes, decision
   tables, process diagrams). Replace its entire fact layer with measured values; its
   "已验证" wording is not inherited.
2. **Classification: external audits are NON_AUTHORITATIVE inert material** (anti-drift
   rules 1–3: cloud GPT audits must live-read + report the exact SHA; a doc whose SHA
   is mis-recorded or unverifiable is demoted further — evidence material, not task
   source). Its proposed tasks enter as **candidates**.
3. **Landing shape (two tracked files + rebind, one PR):**
   - `docs/audits/<TOPIC>-<date>-RAW.md` — byte-exact original with a leading
     HTML-comment provenance banner (source, paste time, channel, NON_AUTHORITATIVE
     classification, pointer to the crosswalk). No edits to the body. **Copy it
   byte-exact via a binary copy (`shutil.copyfile`) and pin the source's
   sha256 in the crosswalk** — a text-mode rewrite silently re-normalizes
   newlines (CRLF↔LF) and corrupts the byte-exactness, detectable only as a
   byte-count/hash mismatch after the fact. Exception: when the source is a
   Hermes-app attachment OUTSIDE the project root (the wrapper's path
   boundary blocks any binary copy across the boundary), the text-tool route
   is the only option: `read_file` the attachment, strip its `N|` line-number
   prefix, `write_file` the RAW. That route re-normalizes CRLF→LF, so the RAW
   is content-exact, not byte-exact — pin BOTH hashes (source sha256 +
   landed-RAW sha256) in the banner/crosswalk and say "newline-normalized
   copy" explicitly, so a later audit does not misread the mismatch as
corruption. PUA codepoints that render
     invisibly in the derived CROSSWALK are stripped there; the RAW archive
     keeps the source bytes as-is (proven identical to the source by hash), so
     do not strip inside the RAW file.
   - `docs/audits/<TOPIC>-<date>-CROSSWALK.md` — §1 fact table (step 1 with verdicts),
     §2 per-domain verdict table (仓内已闭合 / 真实 gap / owner-gated — cite the
     in-repo gate or config that already closes the claim), §3 risk-matrix adoption,
     §4 follow-up tasks tiered: **A** already closed (this crosswalk IS the evidence),
     **B** agent-executable structural (E1/E2), **C** owner-gated operational (doc-only,
     per the standing 实操不执行 rule), **D** governance notes. B/C items note they
     must map through the final TaskPack `depends_on` crosswalk before execution.
   **Naming: keep the `-CROSSWALK` suffix.** The sweep flow and later audits
   look up "the newest crosswalk B/C tier" by that name; a sibling doc with a
   different suffix (e.g. `-RECONCILIATION.md`) drops out of that
   discoverability chain even when it carries equivalent content — if you
   genuinely need a different doc type, add it AND leave the crosswalk doc in
   place pointing at it.
   4. **Ad-hoc broken-link probes are leads, not verdicts.** A home-rolled
      markdown-link scan resolves relative targets from the scanning doc's
      directory, so quoted paths inside backticked code spans (a table cell
      quoting another doc's link) read as phantom relative links — and the target
      file may exist fine under `docs/taskpacks/`. Before acting on any
      probe-reported broken link: confirm the target's real location
      (`git ls-files` / `ls`) and re-run the official `verify_path_refs` gate
      (`PATH_REF_GATE`); a PASS there with a live target means the probe
      mis-parsed a quote, not a defect — record the pin-down in the ledger,
      commit nothing.
   5. **New `.md` files move the language-boundary scan + current projections, so run
      `python scripts/generate_current_reports.py` (no `--check`) before committing and
     stage the rebound `reports/current/**` + `design-lab/config/` index in the SAME
     PR, or the CI no-drift gate goes red. Before staging, revert any regenerated
     snapshot whose diff is only a `generated_at` refresh you did not intend. The new `.md` also feeds the execution-path gate: grep the RAW + CROSSWALK for install / download tokens (curl, wget, clone, `npm`/`pip install`, machine paths) — if any are present, pin that file to `design-lab/config/execution-path-allowlist.json` in the SAME PR, or CI's C gate (`verify_execution_path_gate.py`) reports a NEW-VIOLATION.
   - Then the standard PR + background merge-poll flow (BLOCKED = wait under strict
     required checks).
4. **Full execution of the crosswalk (the 拆解后续任务 + 全量执行 extension).**
   Default scope when the user says 全量执行 after a crosswalk landed = every
   B-tier (agent-executable structural) item; C-tier stays doc-only
   (owner-gated 实操不执行 rule); the D-tier notes get reclassified against live
   reality, not inherited. Execution discipline:
   - **Fact-check the doc's fact layer FIRST; replace, don't inherit.** External
     audits routinely record branch tables, PR identities, or gate claims from a
     different environment (or none): verify every claimed SHA with
     `git cat-file -e <sha>` (an error does NOT prove the commit is absent — a
     real SHA can also error on a shallow/partial clone; re-fetch before
     concluding) and every claimed branch against the live `git branch -r` list
     BEFORE writing the crosswalk. A branch table that matches zero live
     branches means the doc's whole fact layer is suspect — adopt only its
     framework (risk matrices, decision tables), re-derive every fact.
   - **Zero-match evidence needs a real grep root.** A claim of "feature X
     missing" proven by grepping a directory that does not exist (repo layout
     guessed: `apps/workbench/src/` when the workbench is flat `apps/workbench/
     main.ts`) is a FALSE NEGATIVE — greping a nonexistent path prints the same
     empty result as a genuinely absent feature. Confirm the file/directory
     exists (`git ls-files <path>` / `os.path.exists`) before interpreting any
     0-match as absence.
   - **UI-expansion audit claims get a route-table check.** Before proposing
     "build panel Y", grep the HTTP service's route table for the `/api` source
     Y would bind. No endpoint ⇒ do not build the panel (phantom-KPI iron
     law); record the item REJECTED with the reason in the crosswalk instead of
     shipping an endpoint-less view.
   - **Bundling and CI hygiene for the execution batch:** bundle related items
     into ONE PR when they share a gate/policy/CI-wiring surface (a shared
     verifier + policy file + one workflow edit + tests); never let two open PRs
     edit the same workflow file. Land each item: aggregator PASS + new unit
     tests green + the new gate's own fail-closed self-check before push (a
     freshly-written "gate is wired to CI" check FAILs by design before the
     same PR's wiring step — that is expected bootstrapping, not a regression).
   - **Fill the CI wait:** while one PR's checks are in flight, start the next
     item on a fresh branch cut from main (disjoint files), never on the
     in-flight PR's head.
   - **Closing ledger PR (docs-only):** after the last B item merges, open one
     final PR that updates the CROSSWALK with the actual PR numbers + merge
     SHAs + a terminal 执行账 table, and CORRECTS any misjudged fact in the
     original crosswalk in the same file (fix the row, don't append "UPDATE:
     actually…"). Rebind `reports/current/**` with `generate_current_reports.py
     ` in that same PR.
   - **Executing a gate-contracted refactor (minimal agent slice of an
     owner-gated handoff).** When a gate's inventory/docstring declares a
     refactor as "the owner-gated TaskPack handoff this inventory defines" and
     the user grants a full sweep, execute the *minimal root-cause slice*, not
     the whole product surface: (a) remove the hardcoded default; (b) one shared
     fail-closed locator module (env var → PATH → None; no download/clone/
     install, zero side effects, a receipt naming every checked location);
     (c) add the new module to the gate's scan-scope list (an intentional
     gate-scope change, reviewed in the PR); (d) re-triage the inventory
     entries: un-pin and rewrite their classification — the gate reports STALE
     for a pinned entry that is no longer live, and that STALE is the drift
     signal you must resolve, never bypass; (e) hermetic tests that monkeypatch
     env/`shutil.which` to prove priority order, fail-closed on miss, and zero
     side effects. The larger surface (full tool-resolution contract,
     install-authorization receipts, registry probes) stays owner-gated and is
     *named as such* in the crosswalk — never silently executed, never claimed
     done.
     **Pitfall — the locator gate scans docstring lines, not just `#`
     comments.** A machine-path literal or a registry-API literal written in a
     docstring of the refactored function or the new reference module shows up
     as a NEW untriaged violation and fails the gate. Keep docstrings of
     refactored + new modules literal-free (say "the previous owner-machine
     default", not the path), and run the gate immediately after each edit to
     catch the new fingerprint.

## Enumerating remaining work for external-model dispatch (GEMINI / other executor)

Class task when the user asks 列出所有未完成任务 适合 <model> 跑的 / what to hand the next
executor. The list is evidence-derived, never from memory:

1. **Reconcile three sources before tiering:** (a) `design-lab/config/task-ledger-r3.json`
   — per task read `axes` state (`PARTIAL` with empty `evidence` = structural-only, host_live
   unproven); the pack's `baseline_sha` is historical, not current; (b) the current FINAL
   TaskPack (`docs/taskpacks/...-CONVERGENCE-TASKPACK-*.md`) sections A–O — which sections are
   closed vs open; (c) the newest `docs/audits/*-CROSSWALK.md` B/C tiers. Spot-check reality
   (grep the route table, list the files) before declaring an item done — "11 of 12 routes
   present" is a different claim than "all present".
2. **Tiering rule**: structural E1/E2 work (scanners, schemas + verifiers, path audits,
   fixtures, CI jobs, doc registries) is dispatchable to an external coding model, one
   self-contained PR per item; operational E3 (real host execution/qualification), license
   unlock, and E5 release/tag stay owner-gated doc-only — the standing instruction is
   实际操作和自动化操控不执行、保留任务文档. P2 expansion domains are gated on core
   stability and are excluded from dispatch lists, not skipped silently.
3. **Dispatch handoff notes (always attached to the list)**: base SHA (`rev-parse` at
   dispatch time), the required read chain (AGENTS.md → AUTHORITY.md → authority-index →
   current TaskPack → newest crosswalk), per-task PRs must pass ALL required checks, project
   data writes go only under `.project-local/`, no phantom KPIs (UI/records bind to real
   endpoints or are labelled source-less), and any unestablishable evidence field is written
   INCOMPLETE/UNKNOWN, never PASS.
4. **Never re-list CLOSED items as open work** (rule 7): closed items without regression
   evidence stays closed; cite them only as regression guards.

## Full structural sweep (all agent-closable items, one docs branch)

Class task when the user says 全量收口 / 跑完所有非自动化操作的任务 / "run all
non-operational structural tasks". Distinct from a single crosswalk execution:
the sweep covers ALL lanes (A–O + R5 ledger + close-out ledgers), not just items
from one audit.

1. **Live-reconstruct the full task list from authority sources, not memory.**
   Read the FINAL TaskPack (A–O lanes), the R5 task ledger
   (`design-lab/config/task-ledger-r3.json`), the newest crosswalk B/C tiers,
   and the newest close-out ledger. For each lane, run a live probe
   (`git branch -r`, `gh pr list`, `gh api …/protection`, grep the route
   table) to confirm its CURRENT state. Most "remaining" items are already
   closed by prior PRs — the probe confirms which truly remain.

2. **Classify: agent-executable structural vs owner-gated operational.**
   Structural (scanners, schemas, docs, CI-wiring, verifiers, projections)
   is agent-closable. Operational (real host E3, Human Jury E4, real model
   runs, license acceptance, release/tag) stays doc-only per the standing
   实操不执行 rule. The classification table IS the deliverable's §A–§E.

3. **Execute structural items on ONE docs branch**
   (`docs/full-sweep-closure-<date>`). Each item lands as a tracked file:
   governance doc fixes, decision records, close-out ledgers. Rebind
   `reports/current/**` + `design-lab/config/current-report-index.json` via
   `generate_current_reports.py` in the same branch. Commit, push, open PR.

4. **CI verify + merge**: poll the 9 required gates on the PR head (see the
   check-state poller pitfall above). After green, squash-merge, read back
   the new files on `origin/main`.

5. **Report the structural-vs-operational split**: the terminal state is
   "all agent-closable structural work done; remaining lanes are owner-gated
   operational (named in the ledger, NOT executed)." Never claim operational
   closure without host run / human jury evidence.
6. **Terminal closeout ledger = fixed section shape.** When a sweep ends, the
   tracked closeout ledger (`docs/audits/<topic>-close-out-ledger-<date>.md`)
carries: §A the executed instruction + owner boundary; §B merges performed
   (PR → merge SHA + 9-gate verdict + merge-state readback);
   §C slimming/reclaim record (before/after bytes, kept-roots + why kept);
   §D stash/tag hygiene (backup tag + content verdict per stash);
   §E the tool-layer error log — a (failure → fix) table, each row distilled
   to a rule, not an incident narrative; §F terminal state (main SHA, open
   PRs, named owner-gated remainder). §E is a standing user-requested
   closeout deliverable (「错误记录」), not an optional appendix — omitting it
   makes the ledger re-askable at the next sweep.
7. **Terminal ledger when the goal includes cloud auditability (「全部上传，确保能被
   网页GPT审计到」).** Web GPT can only read `origin/main`, so the closeout PR
   must itself land on main (9-gate decisive readback → squash merge, open PR
   back to 0, remote branches back to main-only) and the ledger gains a
   cloud-reachability section: (a) the audit entry sequence (AUTHORITY →
   authority-index → AGENTS → ledger chain → `reports/current`), (b) the
   rollback tag inventory, and (c) an explicit note that the post-merge
   projection `STALE` is the documented self-referential steady state
   (binding is judged by the exact recorded SHA, never by generation time)
   — writing that note into the ledger is what prevents the NEXT cloud audit
   from re-flagging the STALE check as a defect. Stale-snapshot judgment
   always goes through the owning gate (`generate_current_reports.py --check`),
   not a hand read of the JSON.

## Reclaim audit of `.project-local` / runtime surfaces (瘦身清理 class)

Class task when the user authorizes cleanup of the project's ignored runtime
data (「瘦身清理，全部授权，严格审计后自行清理迁移合并」). Standing preference:
clean ONLY proven-regenerable items, prove zero tracked loss first, and leave a
tracked manifest so the reclaim is reviewable after the fact.

1. **Audit before touching anything.** One read-only pass that classifies every
   top-level entry of `.project-local/` by tracked status (`git ls-files` must
   return EMPTY for every root you plan to prune — the guard keeps runtime
   data in gitignored dirs), newest-mtime age, and regenerability
   (CI-reproducible artifacts, session-scoped evidence roots, empty
   placeholder trees). Never prune from a snapshot — the list is rebuilt per
   run.
2. **Prune with a manifest.** Delete only stale session evidence roots
   (subdir-newest-mtime threshold) and reproducible build roots, and write a
   `.project-local/prune-manifest-<date>.json` listing removed roots with their
   byte counts plus an explicit `kept` list with reasons — the manifest is the
   §C record the closeout ledger quotes, and it makes the reclaim re-auditable
   after the removed data is gone.
3. **Stash hygiene = verify → back up → drop, in that order.** For each old
   stash: diff its changed files against main and prove each is main-superset
   or identical (dropping then loses nothing main lacks), tag the stash
   commit object with `git rev-parse "stash@{i}"` and push that tag as the
   rollback point, only then `git stash drop`. Two mechanical traps: `git
   stash create` backs up the CURRENT clean tree, not an existing stash —
   resolve the real object with `rev-parse` instead; and dropping a stash
   shifts the indices of the rest, so after each drop re-list and resolve
   by label, never by the index you recorded at loop start.
4. **Empty placeholder trees:** `os.rmdir` dies on a dir that still holds
   empty subdirs (WinError 145) — confirm the whole subtree is file-empty
   first, then `shutil.rmtree`.
5. **Session scratch cleanup belongs in the closeout, not the PR.** The
   probe/poller/commit-msg scripts written under `.project-local/` during the
   work are gitignored run data: delete them after the merge readback so the
   next session starts clean — but never before the merge, while pollers may
   still be live.

## Reporting

Every execution ends with the fixed DESIGN-LAB report format — one line per field,
exact SHA, evidence level, and no hedged words (no "基本好了 / 大概完成 / 全部
完成"). Fields: Authority ID / Observed main SHA / Active PR-head / Branch
protection / Current task / Historical predecessor / Frontend / Backend / Host /
Tests-CI / Actions artifact / Evidence level / Human Gate / Rights / Open blockers /
Closed-regression checks / Rollback / Worktree-branch / Next.

## Anti-drift hard rules (permanent)

1. GPT cloud audits must live-read the repo first.
2. Must read `AUTHORITY.md`.
3. Must report the exact SHA.
4. A handoff is never above the Authority.
5. History only via the authority-index.
6. Old TaskPacks do not auto-resurrect.
7. Closed items without regression evidence are not redone.
8. Never sum completion across separate ledgers.
9. Never claim E1 as E3.
10. Never claim a VLM as Human Jury E4.
11. Branch/commit counts do not equal capability.
12. No 2nd Runtime/Backend/Ledger.
13. Never restore an old Architecture.
14. No unreasoned language/framework swap.
15. No new governance layer to solve a governance-layer problem.
16. User-visible design capability must keep advancing.
17. REUSE-FIRST means real absorption, not registry entries.
18. Branch/PR/CI counts are always live-read, never from a handoff.
19. `main` is the post-merge code truth.
20. Dynamic state is never frozen into a permanent Authority.
21. One vertical slice lands its persistence + API + UI + tests in ONE branch;
    backend-only landings are not product-complete. **When a slice EXTENSION is too large
    for one branch, split it into (a) persistence + API + tests and (b) the user-facing
    flow, and say the split out loud**: the first PR body must state that it does not
    claim product-completeness and must name the UI half as an open follow-up with its own
    spec file. The rule forbids calling a backend-only landing complete; it does not
    forbid an explicitly-labelled two-step landing — what it forbids is a split remembered
    later as "the feature shipped".
22. Idempotency conflicts fail closed (409), never as opaque 500s or silent
    identity reuse.
23. Additive schema migrations only; frozen v1 tables are never altered.

- **Governance/projection scripts need the repo's `.venv` interpreter, not the system `python`.**
  `generate_current_reports.py` and the `verify_*` gate chain import third-party
  packages (jsonschema) that exist only inside the project venv; the system
  `python` dies at import (`ModuleNotFoundError: No module named 'jsonschema'`)
  and `uv` is NOT on the wrapper's PATH. Invoke the venv directly:
  `.venv/Scripts/python.exe <script>` (Windows; `.venv/bin/python` elsewhere).
  A probe script that shells out to bare `python scripts/generate_current_reports.py`
  reports a false repo defect that is only a wrong interpreter.
  Audit-side corollary: when you run the top-level authority gate or the contract
  graph check DURING an audit, those verifiers rewrite the tracked
  `reports/current/` snapshots (`generated_at`, `tracked_files_scanned`, …) into
  the working tree — before declaring the audit state clean, `git checkout --` the
  regenerated snapshots whose diff is only a timestamp/scan-count refresh (the
  rebind you intentionally commit is the exception), or the final state reads
  dirty for reasons your audit did not cause.

## Pitfalls that cost time (attach to the step above)

- Landing authority files by hand instead of byte-exact from the package → integrity
  hash mismatch. Always land from the verified zip payload.
- Running terminal commands without the project wrapper → `PROJECT DATA BOUNDARY
  BLOCKED`. In DESIGN-LAB every `terminal` call is
  `python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <one command>`
  with `workdir` = the repo; the wrapper forbids shell chaining/`&&`/`;`/pipes in
  that single call, so batch multi-command logic into `execute_code` instead.
- Quoted multi-line arguments are rejected the same way: `git commit -m
  "line1\nline2"` and `gh pr create --body "…"` both trip `PROJECT DATA BOUNDARY
  BLOCKED` (the newline/quotes read as chaining/redirection). Write the text to a
  file and pass it — `git commit -F <file>`, `gh pr create … --body-file <file>`
  — so each call stays a single clean command with no multi-line args.
- **`/dev/null` redirects are blocked by the wrapper's path-boundary check** (an absolute POSIX path outside the Git project): drop the redirect or point the output at a project-local file.
- A wrapper argument that LOOKS like shell expansion is rejected before it runs:
  `PROJECT DATA BOUNDARY BLOCKED: shell expansion before wrapper execution is
  forbidden`. A `grep` pattern containing `$` (e.g. `"[$]schema"` / `"\$schema"` /
  `"$schema"`) trips it, and the failure is easy to misread — the pattern-bearing
  call comes back blocked or empty, which reads exactly like "no consumer of this
  key exists anywhere". Anchor the search on a `$`-free token (a sibling key such as
  `schemaVersion`) or read the file, instead of fighting the quoting — a key you
  cannot grep is a key whose ownership you have not actually established.
- `gh api …/protection/required_status_checks/contexts -X POST` with `-f key=val`
  → 422 "missing required key: contexts". It needs a **JSON body** (`--input
  file.json` with `{"contexts": ["<exact name>"]}`).
- Treating a predecessor chain `DRIFT` as a failure to skip around → regenerate
  (`deepseek_authority_chain.py`) and re-run both gate chains; both must PASS.
- Quoting a handoff's branch count / main SHA / open-PR / CI as current truth →
  those are point-in-time; live-read every time.
- gh pr checks <pr> --watch and gh run watch can exit 1 on a TRANSIENT
  GraphQL/API error even when no check is actually red. On a non-zero watch
  exit, re-poll with plain gh pr checks <pr> or gh run list: if the only
  non-green item is the API call itself, restart the watch. Count a real
  failure only when a NAMED gate reports a red conclusion — a watch crash on
  a still-pending slowest gate is a retry, not a regression. A ZERO exit is
  equally not proof of green: the stream can end truncated on runner
  deprecation noise, so before declaring the merge-commit CI green confirm
  `gh run view <runId> --json conclusion,status` reads `success`/`completed`
  (the gate binds the merged SHA, never the watch output).
- The wrapper --zero-spill flag firing on .hermes/secret-new.json inside an
  isolated runner temp root is usually a pre-existing self-test fixture (the
  internals self-test drops a throwaway secret to prove it cleans up), not
  your diff. Check whether the spilled path sits under the runner temp root
  and whether the producing test pre-dates your commit; only treat it as your
  regression if your commit caused it. Never weaken the gate to make a
  fixture spill disappear.
- Running local verifiers rewrites tracked reports/current/*.json snapshots
  (CONTRACT-GRAPH, DEEPSEEK-AUTHORITY-CHAIN, LANGUAGE-BOUNDARY-SCAN) into
  your working tree, which blocks a clean git merge --ff-only and a clean
  git add -A stage. Restore locally-dirtied snapshots with
  git checkout -- reports/current/… before merging, then confirm the staged
  diff is only your intended commit set.
- Judging an Authority §15 wording/doc item open by grepping the stale term:
  the term is legitimately quoted by AUTHORITY.md itself, the taskpack, and
  the verifier's check logic, so a repo-wide grep always over-reports. The
  item's closure is the GATE CHECK it feeds — live-run that check (e.g.
  `verify_top_level_authority.py` → `single-ruff-fact` for the Ruff wording)
  before touching anything; PASS means the item already closed and must not
  be redone (rule 7), FAIL names the exact stale file to fix.
- Browser E2E that "passes" by faking it when the toolchain is absent, or by
  forcing a `playwright install` in CI: both are wrong. A clean checkout has
  no gitignored in-repo Playwright cache and no matching Chromium, so the shell
  must SKIP with the exact missing-tool reason; and it must launch a locally
  installed Chromium via `executablePath` (zero download) rather than let
  playwright try to fetch a revision its build expects. Prove the browser
  readback, don't just assert no-exception.
- Pinning a GitHub Action by a SHA nobody resolved: an agent (or a memory) can
  hand back a plausible 40-hex SHA whose middle differs from the real tag. GitHub
  then fails the WHOLE job at `Set up job` in ~2s with `Unable to resolve action
  ...`, before any step runs, while every other job stays green — and the same
  fabricated pin gets copy-pasted across workflow files. Treat a ~2s job failure
  as an action-resolution problem, not a test failure: list the job's steps via
  `gh api repos/<o>/<r>/actions/jobs/<id> --jq '.steps[]|"\(.number) \(.name)
  \(.conclusion)"'` (reading `1 | Set up job | failure` is the tell), resolve the
  real SHA from `gh api repos/<owner>/<repo>/tags --jq '.[]|"\(.name)
  \(.commit.sha)"'`, then grep EVERY workflow file for the same pin. Note the tag
  listing is the authoritative map — a near-identical SHA is exactly how this bug
  hides.
- Fetching a failed job log via `gh api .../jobs/<id>/logs` can be refused with
  `the response contains terminal escape sequences; pass --allow-escape-sequences`:
  add the flag instead of abandoning the log, and prefer `--log-failed` once the run
  itself has completed.
- `gh pr checks <n> --watch` cut off by the terminal's own ceiling (~420s) says
  nothing about CI: re-poll with plain `gh pr checks <n>`, or run the watch as a
  background process with a completion notification, and only then merge.
- Reading a just-mutated `<select>`/list immediately after a create/refresh
round-trip: the repopulated options are appended by an in-flight API response,
so a `visible` wait on the container or an immediate `allInnerTexts()` sees
only the pre-mutation placeholder. Wait for the specific new `<option>`/row to
reach `attached` state (via `hasText`), then `selectOption`/click.
- Landing a document attached from the Hermes app into the tracked repo: the
  attachment carries app-private reference tokens in Private-Use-Area
  codepoints (PUA `\ue200`–`\ue201` sequences wrapping turn/file/line cites)
  that render invisibly. Strip the PUA-runs (and their inner tokens) before
  landing, keeping prose, tables and external citations byte-intact; detect
  them by scanning for PUA codepoints (a quick Python round-trip or
  `unicodedata` category check), not by reading the raw text. Tracked files
  must never carry unrenderable private-use bytes.
- The environment's content-search tool silently returns 0 results on regex
  alternation/hyphen patterns (and hard-errors on unbalanced parens), so a
  0-match answer is NOT proof that no consumer of a string exists. Before
  concluding "no verifier hard-codes X", re-prove with single-word searches
  and/or wrapper `grep -rn <word>` per token; the mismatch between "searched
  and got 0" and "grep found 6" nearly caused a broken commit in the
  evidence-ladder realignment.
- Auto-detecting the repo root by listing parent directories: when the user
  names a project in chat, set `terminal`'s `workdir` to its KNOWN path and use
  the project wrapper directly. A bare terminal call that touches project paths
  without a declared Git-project workdir is blocked (`PROJECT DATA BOUNDARY
  BLOCKED`) BEFORE it runs, so you cannot 'find' the repo that way — you must
  already know its path to set the workdir that makes the call valid.
- Multi-line Python via `run -- python -c "<heredoc>"` is blocked (`PROJECT DATA
  BOUNDARY BLOCKED: shell chaining/redirection is forbidden; invoke one wrapper
  command only`). Write the script to the project's ignored runtime root (`.hermes/task-runtime/<name>.py`; in DESIGN-LAB use `.project-local/` since `.hermes` is not an active write path) with
  `write_file`, then a SINGLE wrapper call: `python "$HERMES_HOME/bin/
  hermes-project-data.py" --project . run -- python .hermes/task-runtime/<name>.py`
  with `workdir` = the repo root. Same pattern for any `zipfile`/`json`/loop logic
  that would otherwise chain `&&` or `|` — the wrapper allows exactly ONE command
  per call.
  - `git branch --format=%(refname:short)` as the wrapper's single command dies in bash before
    git runs (`syntax error near unexpected token '('` — MSYS bash word-splits the paren).
    Use plain `git branch` for inventory, or batch a formatted listing through `execute_code`
    subprocess.
- **Merge-polling under DESIGN-LAB's strict 9-check protection: `BLOCKED` is the
  WAITING state, never a failure.** The reliable close-out pattern: a background
  poller script (written to `.project-local/tmp-commit-msgs/`, regenerated for the
  next PR by string-replacing the PR number) that polls
  `gh pr view <N> --json state,mergedAt,mergeStateStatus --jq '.'` every ~30s and
  parses with `json.loads` (text-splitting crashes on field-order changes);
  `BLOCKED` → keep waiting, `BEHIND` → `gh pr update-branch` then keep waiting
  (strict re-runs all checks on the new head), `CLEAN` → `gh pr merge <N>
 --squash --delete-branch`, `DIRTY` → abort and report; `UNSTABLE` → verify before deciding. Under strict protection UNSTABLE means a NON-REQUIRED check is red while every required gate is green — GitHub still merges that PR. If all required gate names report SUCCESS on the PR head's `event=pull_request` runs and the only red check is a known by-design advisory (the main-only artifact read-back gate, which structurally cannot pass on PR runs), tolerate UNSTABLE and merge; abort only when a REQUIRED gate or an unknown check is red. Two
 poller semantics that cost time: (a) **pending is a WAITING state, never a
 failure** — a background poller loops until ALL required checks are green
 and exits 0 only then; a real red conclusion on a NAMED gate exits 1; and
 `BEHIND` → `gh pr update-branch` then keep waiting. A poller that treats
 pending as FAIL exits early and the CI window is lost. (b) **Guard against
 the PR already being merged:** `gh pr checks <N>` on a merged PR lists
 ZERO checks, so a stale poller spins to its timeout printing
 "present=0/9 missing=9" — check the PR state first and terminate immediately
 when `state == MERGED`. Two failure
  reads that cost time: (a) `gh pr merge` printing `Not possible to fast-forward`
  is the LOCAL ref-sync step, not proof the merge failed — verify via
  `gh pr view <N> --json mergedAt`; if set, the merge landed server-side, sync
  with `git reset --hard origin/main` and delete the (now-gone) head branch, do
  NOT retry the merge; (b) an unknown `--json` field name makes gh print its
  full valid-field list and exit 1 — retry with fields from that list
  (`potentialMergeCommit`, not `mergeCommitSha`). (c) `gh pr merge` printing
  `not mergeable: the base branch policy prohibits the merge` while ALL
  required checks are green is a protection-state registration lag, not a
  failing check: wait 20–60s and retry the same merge; do NOT amend, re-push,
  or re-run checks. (d) **Inline CI waits inside `execute_code` die at the
  300s kernel cap** (the whole kernel and its persistent state are killed, not
  just the cell): a `time.sleep` polling loop burns the budget and loses your
  variables — the CI wait is the background poller with a completion
  notification; inline polling is only for a final bounded check under ~4 min.
  (e) **Aggregator `SCRIPTS` union conflicts.** When two open PRs each append a
  different verifier to the same aggregator list (`verify_design_lab.py`'s
  `SCRIPTS`), merging main into the later PR conflicts textually at the same
  lines. Resolve by UNION — keep every appended entry, run the aggregator
  locally to prove each new verifier is still green, and state in the commit
  that no gate was dropped. Never resolve with `--ours`/`--theirs`: each
  verifier is an independent fail-closed gate and taking one side silently
  weakens the suite.
- Subprocessing pnpm from Python on Windows: `subprocess.run([...pnpm...])` fails
  because pnpm resolves to `pnpm.cmd`. Use `shell=True` for pnpm invocations from
  in-repo scripts (commands are hardcoded literals, no user-input interpolation —
  state that explicitly in a comment so the security lint passes); node/python can
  stay non-shell.
- **Check-state poller must match the 9 required gate names, not all returned checks.**
  `gh pr checks <N>` returns every check on the PR, including main-only advisory gates
  (H001 `CI artifact proof (main-run upload readback)`) that report FAILURE on
  `event=pull_request` BY DESIGN — they read back main-run artifact uploads, which a
  PR head cannot produce. A poller that counts "all green" will never reach PASS.
  Query the exact required names from
  `gh api repos/DTALEX66/DESIGN-LAB/branches/main/protection --jq
  '.required_status_checks.contexts'`, track ONLY those in the poller, and bind each
  to `event=pull_request` (not `push`) so main-run residue doesn't inflate the
  count. The verify script must re-confirm all 9 on the exact PR head SHA.
  - **`gh pr checks --json` field availability varies with the installed gh version.** On this host reliably request ONLY `name,state,event`; adding `completedAt`, `run`, `conclusion`, or `commit` can make the whole call return EMPTY output (json.loads fails on nothing). The response also mixes `event=pull_request` and `event=push` entries, so filter to `pull_request`. On a merged PR the checks list is empty — confirm state via `gh pr view` first.

## Absorbing an external UI suite / design kit (UI-slice class)

Class task when the user points at an external UI suite (e.g. `D:\All projects\UI套件`,
the 3-project UI master pack) and says 检索 DESIGN-LAB UI 内容 → 审计 → 放入本项目,
or 优先做 UI 前端开发设计. Standing order: the UI slice is the primary frontend work;
other queued tasks defer to a backlog section.

Full procedure, authority-layer reading order, reskin rules, gate-safety proof,
vm-unit-smoke guards, scope-gutter pattern, browser-E2E regression chain, and
2026-09 pitfalls (string-splice scope, strict-TS SVG helper typing, wrapper vs
execute_code external-reference read, `.bin` shim failure mode) live in
`references/ui-kit-absorption.md` — load it for any UI-kit work.
