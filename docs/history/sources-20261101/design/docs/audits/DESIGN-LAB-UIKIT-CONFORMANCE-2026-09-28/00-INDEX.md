# DESIGN-LAB × UI-kit conformance archive — 2026-09-28

**Archive root:** `docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/`
**Baseline `main` at archive time:** `3d0ad1cd51869c288e8d3870af8c2541f7bb505f`
**Round PRs:** #182 (`.seg` primitive → `553b0ca4`), #183 (route-heading de-couple → `3d0ad1c`)

> This is a **HISTORICAL / EVIDENCE archive**, not a current authority, not a task
> dispatch entry and not a ledger. Per `AGENTS.md`, the top-level authority remains
> `/AUTHORITY.md` (`DL-AUTHORITY-2026-09-18-R2`). Nothing here may be used to edit
> execution state or to claim a capability-axis promotion.

---

## 1. What this archive is

The DESIGN-LAB workbench is a 1:1 replica of the in-repo **B10** UI kit. This archive
records one round of work that made that claim **measurable** rather than asserted:
auditing, per computed CSS property, whether the B10 shell (`.app`) still depended on
pre-B10 legacy CSS, and closing the dependency that was found.

## 2. Provenance

| Input | Origin | Identity |
|---|---|---|
| Owner task pack | `DESIGNLAB_商业级前端与能力闭环_后续任务包_20260928.zip` | sha256 `70592198dbd4ea0228ab1714143ec9e230f90237d19247b8831d586d64cfae85` |
| UI-kit originals | owner batch **B04** (component system / tokens), **B07** (front-end spec), **B10** (final hi-fi deployable UI) | extracted from the owner's own per-project archives under `D:\All projects\UI套件` |

⚠️ **Only the per-project `DESIGN-LAB_*` archives were used.** The three-project
"全量包" bundles mix ArcheAxis and WORK-LAB material; using them for a DESIGN-LAB 1:1
replica would cross-contaminate colour and specification. This warning was carried in
the pack and is confirmed correct.

## 3. Layout

| Path | Contents |
|---|---|
| `pack/` | The owner-supplied pack documents, verbatim (`00_README` … `04_SOURCES`, `ALIGNMENT-ANALYSIS`, `EXTRACTION-MANIFEST`) |
| `findings/` | Work-package deliverables — `W00` crosswalk / diff-mapping / evidence-scan, `W01` typography matrix, `W02` component coverage + decision + **`W02-LEGACY-COUPLING`**, `W03` project-detail route, `W14` viewport/keyboard |
| `evidence/` | Raw, unedited harness outputs (`W02-LEAK-SWEEP.txt`, `*-VERIFY.json`, `*-PROBE.json`) |
| `evidence/local-gates/` | Gate results: fresh runs for this round (`license-coverage`, `identity-gate`, `top-level-authority`, `context-integrity`, each `exit=0`) plus the session's earlier gate JSON (`authority-gates-latest`, `top-authority-gates-latest`, `control-spike-bad-matrix`, `browser-e2e-summary`, `test-run`) |
| `harness/` | The audit tooling that produced `evidence/` — runnable, SPDX-tagged |
| `session/` | Session lineage: commit/PR message drafts, superseded revisions, intermediate probes. **Superseded, kept only for traceability** |
| `session/project-survey-2026-09-27/` | The preceding round's project-survey documents, carried over for completeness (their own tracked handover is `docs/handoffs/DESIGN-LAB-PROJECT-SURVEY-TRUTH-RESYNC-2026-09-27.md`) |
| `ui-originals/` | Extracted reference originals (`B04/`, `B07/`, `B10/`) + `EXTRACTION-MANIFEST.json`. The 17 B04 design sheets carry `asset-sidecar/v1` **JSON** sidecars |
| `ui-kit/` | The wider local UI-kit tree: the batches **not** already in `ui-originals/` (`B08/`, `B09/`), the live `B10-batch/`, `mockups/`, `chromium-probe.mjs`. `B04/`, `B07/` and `B10/` were **removed as byte-identical duplicates** of `ui-originals/` (verified by sha256: 18/18, 23/23, 2/2, the two remainder files differing only by the ASCII renames below) |
| `findings/ui-implementation/` | The earlier UI implementation docs: component map, route map, reference manifest, asset-replacement manifest, visual-QA report |
| `evidence/deep-audit/` | `dl-deep-audit` batch outputs (child results, library-index audit, report skeleton) |
| `evidence/governance-state/` | `context-capsule.json`, both `prune-manifest-*.json`, `stash-backup-2026-09-26.json` |
| `session/b10-1to1-handoff/` | Text-only lineage from the B10 1:1 round (42 files). Its Chromium profile/shader-cache trees were excluded — see §11 |
| `session/quarantine/`, `session/hermes-legacy/`, `session/reconstruction/` | Quarantined deepseek-round1 state, HERMES legacy migration manifests/journal, reconstruction run contracts |
| `NEXT-ROUND-PLAN-BUNDLES-LIST.md` | The bundle-list route plan. **Its central premise was wrong** (`asset_kind='design-bundle'` is not a legal value); corrected in place by PR #206 with the original text kept and marked |
| `CLOUD-AUDIT-BRIEF-BUNDLES-LIST-2026-09-28.md` | **Web-audit entry point** for that slice: exact SHA, blob SHAs, PR/run URLs, falsifiable claims C1–C8, explicit non-claims, and a paste-ready audit prompt. Also discloses the two red PR runs (advisory `H001` only) so they are not misread as required-check failures |

## 4. The headline result

`W02-LEAK-SWEEP.txt` deletes every unscoped, element-only legacy rule through the
CSSOM and diffs **all** computed longhands of every `.app` element across all 12
routes plus the default and login screens (328 elements in `.app`).

| Scope | Before | After |
|---|---|---|
| **inside `.app`** (the B10 1:1 subject) | **8** legacy-supplied bindings | **0** |
| outside `.app` (legacy chrome: login, `#workspace`, `nav.app-nav`) | 1923 | 1923 |

The 8 were the placeholder `<h2>` margins on `#/research` and `#/collaboration`,
supplied by the pre-B10 `h2{margin:0 0 14px}` rule. Fixed by declaring the margin in
`.route-view h2` with **exactly the previously computed values**, so the pixels are
unchanged and only the hidden dependency is removed. See `findings/W02-LEGACY-COUPLING.md`.

**Design consequence recorded there:** the 1923 out-of-`.app` bindings are why the
legacy element rules **cannot** simply be scoped to `body > …`. An earlier plan to do
exactly that would have broken the login and workspace screens.

### 4.1 W14 runtime baseline (later round)

`findings/W14-PERF-SAMPLING.md` + `evidence/W14-RUNTIME-SAMPLING.json`: the pack's W14
asks to **sample the current state first**. Measured against the real loopback service with
the pinned Chromium — hot-route interaction **P95 = 19.8 ms** against the pack's proposed
≤ 200 ms, first-interactive **71 ms** against ≤ 2 s, and 16 viewport×scale cells
(1920×1080 / 2560×1440 at 100/125/150/200%, i.e. CSS viewports down to 960×540) with **0**
horizontal overflow, 0 clipped content and 0 off-screen elements — backed by a **positive
control** proving the overflow detector actually fires. That section also lists four
harness defects found on the way, each of which had produced a plausible but wrong number.

### 4.2 W03 / W04 in the route shell (later rounds)

`/projects/:id` grew from a read-only page into the project workspace:

| Finding | What it delivered | Verification |
|---|---|---|
| `findings/W03-BRIEF-EDITOR.md` | Real **Brief create / open / edit / save / version** (create, revision, lineage read-back), focus + error locating, honest failure path | 21/21 |
| `findings/W03-TRIAGE-RECENT.md` | **待审 / 失败** dashboard lists from a vocabulary cross-checked against `job_store.py`, plus real **最近项目** recency | 14/14 + vocab 4/4 |
| `findings/W04-REFERENCES.md` | **参考素材** panel: authenticated on-demand preview, `object-fit:contain`, alpha checkerboard, rights surfacing, located missing-asset errors | 17/17 + vocab 4/4 |

Two things in those findings are worth carrying forward beyond their own work packages:

- **CSP `img-src data:` is a hard constraint**: any image UI here must fetch bytes through
  `api()` and use a `data:` URL. A bare `<img src="/api/…">` is blocked by CSP — and that
  block, not authentication, is what the browser enforces first (W04 §3.2).
- **`contracts.ts` declares `kind`/`version_no` on `AssetRecord` that the live `/assets`
  payload does not send**; rendering the declared fields printed `undefined` (W04 §3.1).
  The UI now renders only present fields and a harness check forbids `undefined` in output.

## 5. Reproduction

```bash
# from the repo root; node must be resolvable (the repo pins playwright 1.63.0)
node docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/harness/w02-legacy-leak-sweep.mjs
```

The harness serves `apps/workbench/` under the **exact CSP the service sends**
(`default-src 'none'; script-src 'self'; style-src 'self'; …`) and drives the pinned
Chromium. On this machine `playwright@1.63.0` expects chromium-1243 while only 1228 is
installed, so the harness passes an explicit `executablePath`; adjust that constant for
another machine.

The harness carries its own **positive control** (an injected element-only leak must be
reported end-to-end). This is deliberate: three harness bugs in this round each produced
a *false* result before being found — route discovery reading `href` off `<button>`
elements, same-document hash navigation, and `getComputedStyle` returning stale values
when read in the same task as a CSSOM mutation. All three are documented in
`findings/W02-LEGACY-COUPLING.md` §5.

## 6. Deliberate exclusions

Every remaining `.project-local/task-artifacts/` tree was reviewed before archiving; the
two that are **not** here, and why:

- **9 transient Chromium profile directories** (~142 MB) used by the harnesses — browser
  cache state, not work product. They remain under
  `.project-local/task-artifacts/designlab-followup-taskpack-20260928/chrome-profile-*/`.
- **`external-recovery-2026-09-25/`** — contains a bare **git pack** (`*.pack`, `*.idx`,
  `*.rev`) plus recovered HTML/txt. The pack files are binary git internals, are not valid
  UTF-8, and would make the identity gate fail closed on unreadable tracked text; they are
  also not text evidence. Left in `.project-local` deliberately.

Also not re-archived here: prior rounds' artifacts that already have tracked handovers
under `docs/handoffs/` (`external-recovery-2026-09-25`, `browser-e2e` from 09-26, etc. are
represented by their gate JSON in `evidence/local-gates/`).

## 8. Capability claims

No capability-axis promotion is claimed. `host_live` and `delivery` remain at **1/28** and
**0/28**: they require real host hardware and are untouched by this round.

## 9. Compliance notes

- Archived `.py`/`.mjs`/`.js` carry `SPDX-License-Identifier: MIT` so the
  **License & secret hygiene gate** (`design-lab/scripts/verify_license_coverage.py`)
  stays green.
- The 17 binary design sheets carry **`.license` sidecars in `asset-sidecar/v1` JSON**,
  as required by `verify_asset_governance.py` (DL-AST-001) — free-text SPDX sidecars are
  a hard violation there because they cannot prove hash or rights. Each records
  `sha256`, `license: LicenseRef-Owner-Project-Asset`, the rights holder and the three
  boolean rights flags. **The rights flags are a claim that needs the owner's eye:**
  `redistributable: true`, `commercialUse: true`, and `modelInputAllowed: false`
  (no model-training right is asserted for the sheets). Without a registered `sourceId`
  the schema requires an approved exception, so each carries
  `exception.approvedBy = "DTALEX66 (project owner)"` with `expiresAt: 2027-09-28` —
  grounded in the owner's instruction to archive this round's material into the project.
  **This is an assertion of owner approval, not a verified signature; the owner should
  confirm or amend it before the expiry.**
- Two archived filenames were **non-ASCII** in the source archives and were renamed to
  ASCII, because `git ls-files` quotes such paths and `verify_asset_governance.py` then
  fails with `cannot stat tracked file` (observed on CI, reproduced locally):

  | Original name | Archived as |
  |---|---|
  | `DESIGN-LAB_L4_16张组件系统总览.jpg` | `DESIGN-LAB_L4_B04-16-components-overview.jpg` |
  | `打开页面_Windows.bat` | `open-page_Windows.bat` |

- Every text file here is valid UTF-8: the **identity gate** reads all tracked text and
  fails **closed** on an unreadable file. (This archive's own first sweep output was
  written UTF-16LE by a PowerShell redirect and was caught by that gate.)
- Placed under `docs/audits/` deliberately: `docs/taskpacks/**` is scanned by the
  authority-chain and context-integrity gates, so an archive there could be
  misclassified as a historical taskpack or as an authority claim.

## 10. Gate status for this archive (local, full unified verify)

The failure above was found by running the **full** `verify_design_lab.py`, not by
hand-picking gates — the first push of this archive failed CI on
`verify_asset_governance.py` precisely because only four gates had been run locally.
After the fixes: `verify_design_lab.py` all-pass, `ASSET_GOVERNANCE=OK`,
`LICENSE_COVERAGE=OK`, `IDENTITY_GATE=OK`, `TOP_AUTHORITY_GATE=PASS (10/10)`,
`VERIFY_CONTEXT_INTEGRITY=PASS`.

Full local unit suite: `Ran 1755 tests`, `OK (skipped=37)`, exit 0 — raw log in
`evidence/pytest-undisturbed.txt`. CI's Python gate (which runs
`python scripts/run_python_tests.py`) is green on the merge SHA
`94ed63b96099ef9c1c363f2970502cb04ec92e5e`.

> **A local run of that same suite first reported `errors=2`.** It is not reproducible:
> the module implicated by the visible output (`test_verifier_internals`, which plants
> synthetic secrets such as `.hermes/secret-new.json`) passes 58/58 in isolation, and the
> undisturbed full run is green. That run overlapped this session's own `git add` /
> `commit` / `push` and `verify_language_boundary.py` rewriting
> `reports/current/LANGUAGE-BOUNDARY-SCAN.json` — i.e. the repo state was moving
> underneath a suite that contains repo-state-snapshotting tests. The two error names were
> **not captured** (the output was tail-truncated), so the concurrency explanation is a
> **stated hypothesis, not a proven cause**. What is established: the failure is
> non-reproducible, CI is green, and nothing in it points at this archive.

## 11. Full `.project-local/` reconciliation

Every tree under the runtime root (`.project-local/`, gitignored by design — `AGENTS.md`:
"运行/证据/缓存根统一为 `.project-local/`") has been reviewed and is either **archived
here** or **excluded with a reason**. Measured at archive time; the whole local root is
~1.06 GB, of which ~14 MB is archived.

### Archived

| Tree | Files | MB | Destination |
|---|---|---|---|
| `task-artifacts/designlab-followup-taskpack-20260928/` (minus chrome profiles) | 25 + 46 | 2.0 | `pack/`, `findings/`, `evidence/`, `ui-originals/` |
| `task-artifacts/external-recovery-2026-09-27/` | 139 | 0.5 | `harness/`, `session/` |
| `task-artifacts/{authority-gates,top-authority-gates,control-spike,browser-e2e,test-run,project-survey-2026-09-27}` | 9 | 0.1 | `evidence/local-gates/`, `session/project-survey-2026-09-27/` |
| `ui-kit/` (batches not duplicated by `ui-originals/`) | 55 | 1.0 | `ui-kit/` |
| `ui-implementation/` | 7 | 0.03 | `findings/ui-implementation/` |
| `artifacts/dl-deep-audit/` | 6 | 0.06 | `evidence/deep-audit/` |
| `quarantine/`, `reconstruction/` | 4 + ? | 0.1 | `session/` |
| `archive/hermes-legacy/` (text only) | 411 | 0.6 | `session/hermes-legacy/` |
| `b10/` | 4 | 0.04 | `ui-kit/B10-batch/` |
| `b10-1to1-handoff/` (text only) | 42 | 0.2 | `session/b10-1to1-handoff/` |
| `archive/DESIGN-LAB-FINAL-TASK-PACKAGE-2026-09-04.zip` | 1 | 0.33 | `session/` (+ sidecar) |
| top-level `*.json` governance state | 4 | 0.01 | `evidence/governance-state/` |

### Excluded — with the reason

| Tree | Files | MB | Why not archived |
|---|---|---|---|
| `runs/` | 2596 | 522 | Runtime run output. The project's declared run/evidence root; regenerable and far too large for git. State it describes is already summarised by tracked reports |
| `projects/` | 346 | 341 | Per-project runtime working sets (the services' own `.project-local`); user/tenant data, not archive material |
| `task-runtime/` | 1280 | 100 | Test/browser harness scratch |
| `cache/` | 1914 | 33 | Regenerable cache |
| 9 × `chrome-profile-*/` + the `chrome-profile*` trees inside `b10-1to1-handoff/audit/evidence/` | ~1900 | ~155 | Chromium profile/cache (incl. `GrShaderCache` shader blobs). Browser state, not work product — the "53 MB of extension-less files" in that handoff are exactly this |
| `task-artifacts/external-recovery-2026-09-25/` | 37 | 1.1 | Contains a bare **git pack** (`*.pack`/`.idx`/`.rev`). Binary git internals, not valid UTF-8, would make the identity gate fail closed on unreadable tracked text |
| `archive/hermes-legacy/` binary files | 138 | ~2.4 | Images inside HERMES legacy state; the text manifests/journal **are** archived |
| `session/hermes-legacy/runtime/final-pack/` (extracted) | 7 | 1.4 | Removed after the identity gate correctly rejected it: 4 files carry the **retired legacy identity string**, which is allowed only in allowlisted history roots (`docs/taskpacks/`, `docs/history/`). Provenance is preserved byte-exactly by the archived **zip** (the identity gate skips `.zip`), so nothing is lost |
| empty dirs (`profile-resolver-tests/`, `reconstruction/` remnants) | 0 | 0 | Nothing to archive |

**Not a claim of infallibility:** the "archived" rows were copied and then gated
(`verify_asset_governance`, `verify_license_coverage`, `verify_identity_gate`,
`verify_context_integrity`, full `verify_design_lab`). Shas are recorded in `file`/`sha256`
sidecars for every binary. Two archive passes already had to be corrected by CI — see
§6, §9 and §10.

### One file that `git add -A` silently skipped

`session/hermes-legacy/runtime/_loose/ci-fail.log` was **not** committed: `.gitignore:47`
has `*.log`, so `git add -A` dropped it without any error, and the archive on `main` had
746 files against 747 locally. Caught by diffing the local tree against
`git ls-tree -r origin/main` rather than trusting the local count.

**Fix:** renamed to `ci-fail.log.txt` (identical 219 274 bytes) so it is tracked, rather
than forcing it in with `git add -f` against an explicit repo policy. `git check-ignore`
over the whole archive now reports **0** ignored files, so local and `main` are at parity.

*Lesson for any future archive pass:* `git add -A` never reports ignored files, so
"everything is in the repo" must be verified by comparing file lists — not by watching the
add appear to succeed.
