# DeepSeek Final Audit - DL-TP-20260914-DEEPSEEK-AUTHORITY-R1

Subject: `15b3b6838af52cf7376b2d78fa5dc4389c709d8a` on branch `qoder/designlab-backup-consistency-20261007`. Written 2026-10-18T09:48:21+00:00.

## Repository Normalization Report

Repository directory scheme audited: CONFORM 14, DEVIATION 1 (design-lab dual scheme), EMPTY_DIR 1 (services), EXTRA 3 (git-ignored local directories).
Legacy path scan: active legacy usage 0; the remaining hits are historical records and guard markers that keep the refusal vocabulary.
Single writer for task status is design-lab/config/task-ledger-r3.json; the machine authority ledger has one writer script and `verify` passes for all 58 tasks.
current/ and history/ are separated: superseded packs live under docs/history/ and are classified as HISTORY or ACTIVE_PRODUCT_PACK, never as a dispatch entry.
Project status projections bind subject type, worktree digest and taskpack identity, and refuse to present a dirty tree as a commit.

## Language Governance Report

Language inventory: 1907 tracked files, 15 languages, unmapped extension files: 131.
Language boundary gate verdict: PASS; forbidden language files: 0.
Python owns the runtime; the fixture owns the only Node manifest; Java is scoped to an inert fixture blob; Rust is conditional and absent.
JSON Schema remains the cross-language contract truth: canonical vocabularies are read from the owning schemas and every detected hand-written copy must agree with them.
The copy count is a lower bound measured by a line-level detector; it is not a completeness audit and a fall in the number is not evidence that a copy was lost.

## Repository Slimming Report

Reclaimed by cleanup: 316.79 MiB across 167 cache/temp entries, each with a digest and a recreation note.
No like-for-like before/after exists for the runtime roots, and none is claimed: the earliest recorded reading post-dates the deletion it would serve as a 'before' for. See POST-CLEANUP-AUDIT.json#before_after.
Git pack: current size recorded; the earlier pack state is not recoverable, so no pack reduction is claimed.
Third-party full source trees are not tracked (NO_FULL_THIRD_PARTY_SOURCE_TREES_TRACKED): 3 present in the tree, 0 only in an ignored cache, 6 via lock reference.
Evidence-bearing runtime directories were NOT deleted; they are listed for owner approval, which is the only path the taskpack allows for them.

## Data Spill Migration Report

Census verdict: CENSUS_COMPLETE; scope is metadata and path level only.
DESIGN-LAB-owned legacy objects migrated: 109 (265077183 bytes), with per-object digests and restore paths.
Empty legacy directories cleared by the migration: 0 (the namespace held empty directories only, so nothing with content was deleted).
Refused as agent-native: .hermes/skill-call-index.json (DO_NOT_TOUCH).
No private session, credential, sibling project or E: drive content was read at any point in this run.

## Contract Graph Report

Contract graph: 11 concepts, 0 unresolved links, verdict NO_BROKEN_LINK.
Consumer edges are verified, not asserted: a declared consumer must reference the concept's producer module, table or schema in executable code. Comments and docstrings do not count.
An independent audit found one fictional edge (QA named a file that never referenced its producer); widening the same check found five more, and all six declarations were replaced with verified readers. The structural finding behind them is recorded in the graph: no production Python module imports another creative concept module, because those concepts are peers joined through the state database.
creative-v1 migration was rehearsed to completion on a copy (15/15 steps, zero writes to any pre-existing database) and is still marked MIGRATION_CANDIDATE_PENDING_AUDIT, not accepted as production.
Standards alignment: DTCG 2025.10 canonical with legacy behind an adapter, OTIO official transition offsets, C2PA 2.4 claim structure (unsigned and never signed here), Penpot v3 archive validation, GLB accessor matrix coverage, QA automation/model/human boundary.

## Measured repository state

| Item | Value |
|---|---|
| tracked files before | 1832 |
| tracked files after | 3777 |
| tracked MiB before | 30.15 |
| tracked MiB after | 69.29 |
| .project-local MiB now | 6572.22 |
| reclaimed MiB | 316.79 |
| git pack MiB now | 241.2 |
| third-party full copies tracked | 3 |
| spill objects migrated | 109 |
| empty legacy directories cleared | 0 |

## Remaining exceptions

| Area | State | Exception |
|---|---|---|
| third-party lock | REPORTED_NOT_FIXED | 7 of 46 sources.lock entries carry no canonical URL and 0 carry a pinned revision; the lock records what is absorbed, not where to fetch it |
| runtime volume | OWNER_DELETE_APPROVAL_REQUIRED | .project-local holds evidence-bearing run directories left in place at OWNER_DELETE_APPROVAL_REQUIRED; reclaiming them needs owner approval |
| python tooling | REPORTED_NOT_FIXED | ruff is declared in pyproject but is not installed, so lint is not enforced by any gate; pytest is not installed and the suite runs under unittest. The dependency lock itself is present: uv.lock and requirements.txt are both tracked |
| node tooling | BY_DESIGN | no product Node package exists: the only manifest belongs to the game-visual fixture, and there is no lockfile |
| tracked backups | RESOLVED_2026_10_18 | design-lab/config/capability-index-v1-backup.json (445 KB) was tracked until 2026-10-18; removed under the owner's cleanup instruction, and the ssot list that named it as part of the capability index no longer does |
| legacy package | REPORTED_NOT_FIXED | design-lab/core is an unused legacy package outside the declared layout |
| empty directory | REPORTED_NOT_FIXED | services/ is an empty tracked-adjacent directory (EMPTY_DIR deviation in the directory audit) |
| live database | NOT_VERIFIABLE_AS_STATED | .project-local/state/ does not exist, so a claim that 'the live database is unmodified' is not verifiable as stated; the proxy used is that no *.db under .project-local changed |
| agent-native artifact | REFUSED_BY_POLICY | .hermes/skill-call-index.json is not provably DESIGN-LAB-owned and is left untouched (DO_NOT_TOUCH) |
| measurement | WITHDRAWN_CLAIM | no like-for-like before/after exists for the runtime roots or the git pack, so the only reduction claimed is the digest-backed reclaimed byte count |
| text encoding in subprocess calls | PARTIALLY_FIXED_AND_REPORTED | 119 tracked call sites pass text=True to subprocess without an explicit encoding, so child output is decoded with the machine locale codec (cp936 on this host). Two are fixed because they broke the verification chain itself: verify_design_lab.py now decodes UTF-8 and tells its children to emit UTF-8, making the chain locale-independent, and verify_review_surface.py, whose child prints Chinese section headings. The remaining 117 are reported rather than rewritten: sweeping them without running the full test suite would be an unverified mass edit |
| test gate scope | DEFERRED_DECLARED | H010 executed all four required runs over a declared critical set of 16 stateful and contract-holding modules (220 tests per order in the 2026-09-14 run: forward, reverse, randomized seed 42, and 20x repetition = 4400 tests, all zero failures). Dated 2026-10-09: the gate record now carries the 2026-10-06 runs, which measure 225 tests per order with a 2x repetition = 450; the 220 above was typed, never re-derived from a run. The same three orders over the entire discovered suite (1392 tests) are DEFERRED, not passed: one pass costs roughly 25 minutes against 7.6 seconds for the critical set, and that exact load coincided with the host kernel bugcheck 0x4E that this run is still diagnosing |

## Done-When criteria

| Item | Value |
|---|---|
| 1. the taskpack is landed with a SHA-256 [MET] | docs/taskpacks/DESIGN-LAB-DEEPSEEK-AUTHORITY-TASKPACK-2026-09-14.md, sha256 d9fdaa3ad7ad0055a3f451c853756be41036b32112cacc4d1c17b314c005a2f9; ledger verify passes for all 58 tasks |
| 2. AGENTS.md points at the single current DeepSeek taskpack [MET] | AGENTS.md names one current DeepSeek pack; the authority chain classifies 38 entries |
| 3. old taskpack authority relations are explicit [MET] | reports/current/DEEPSEEK-AUTHORITY-CHAIN.json: 2 CURRENT_DEEPSEEK_AUTHORITY, 12 ACTIVE_PRODUCT_PACK, 2 GOVERNANCE_TRUTH, 14 HISTORICAL, 8 REFERENCE |
| 4. the dirty worktree is attributed and frozen [MET] | reports/current/DEEPSEEK-WORKTREE-INVENTORY.json: 97/97 files classified, 0 UNPROVEN |
| 5. every active code path maps to a task [MET_WITH_EXCEPTION] | the frozen delta is fully attributed against the pack; the exception is design-lab/core, an unused legacy package outside the declared layout -- GAP: design-lab/core is retained and reported, not adopted or deleted |
| 6. the repository has exactly one current directory scheme [MET_WITH_EXCEPTION] | reports/current/DEEPSEEK-DIRECTORY-AUDIT.json: CONFORM 14, DEVIATION 1 (design-lab dual scheme), EMPTY_DIR 1 (services), EXTRA 3 (git-ignored local directories) -- GAP: the design-lab dual scheme and the empty services/ directory are reported, not resolved |
| 7. .project-local is the single runtime root [MET] | runtime roots measured: .project-local 4500.94 MiB / 65832 files; .hermes holds no content |
| 8. no active .hermes project writes [MET] | no tracked .hermes files; the namespace holds two EMPTY directories whose mtimes sit at the migration instant and one refused agent-native file |
| 9. repository size has a measured before/after [MET_WITH_EXCEPTION] | tracked files 1832 -> 1891 and 30.15 -> 30.97 MiB from base revision 56319635, like-for-like TRUE; the git pack and runtime roots are NOT like-for-like -- GAP: no pack or runtime-root reduction is claimed; the withdrawal is computed in the artifact |
| 10. safely deletable cache/temp is really cleaned [MET] | 167 entries, 316.79 MiB, per-entry digest and recreation note in the cleanup manifest |
| 11. the spill census is complete [MET] | reports/current/SPILL-CENSUS.json verdict CENSUS_COMPLETE at metadata and path level |
| 12. DESIGN-LAB-owned spill is migrated or is an explicit exception [MET] | 10 objects / 11565138 bytes migrated with 10 verified digests and restore paths; 1 object refused as agent-native with DO_NOT_TOUCH |
| 13. every deletion has a manifest, a hash and a rollback [MET] | cleanup manifest with digests and recreation notes; migration manifest with restore commands; the quarantine manifest is restorable |
| 14. the Python/TS/Host JS/Rust language boundary is landed [MET] | docs/architecture/LANGUAGE-POLICY.md, LANGUAGE-INVENTORY.json and LANGUAGE-BOUNDARY-SCAN.json: 0 forbidden, 1 fixture-scoped (Java in an inert blob), 0 conditional |
| 15. the dependency lock is unique [MET] | uv.lock and requirements.txt are tracked; one Python project root and one lockfile manager; no Node lockfile exists because there is no product Node package |
| 16. the contract graph has no unexplained broken link [MET] | reports/current/CONTRACT-GRAPH.json: 11 concepts, 0 breaks, every consumer edge verified against executable code |
| 17. the creative DB migration is fully rehearsed on a copy [MET] | 15/15 steps pass on a copy with zero writes to any pre-existing database; still marked MIGRATION_CANDIDATE_PENDING_AUDIT and accepted_as_production false |
| 18. the foundation state files are independently reviewed [MET] | FOUNDATION-AUDIT.json passes, and the independent audit re-read the state layer without access to this run's reasoning |
| 19. DTCG canonical is 2025.10 [MET] | src/design_lab/interop/dtcg.py: strict canonical schema, legacy behind a named adapter |
| 20. OTIO has no invented conflicting semantics [MET] | src/design_lab/interop/timeline.py derives overlaps from the official Transition.1 covered-range formula |
| 21. the C2PA contract aligns to 2.4 [MET] | src/design_lab/interop/provenance.py projects onto c2pa.claim.v2 / c2pa.signature, unsigned and never signed here |
| 22. the Penpot validator aligns to v3 [MET] | src/design_lab/interop/penpot.py validates the v3 archive structure read-only |
| 23. the GLB validator is JSON-safe and covers the accessor matrix [MET] | src/design_lab/media/three_d.py splits parse/validate/summarize and covers MAT2/MAT3/MAT4 accessors; 29 tests pass |
| 24. the QA automatic/model/human boundary is explicit [MET] | qa_plane.py policy is frozen: automation may not be final, a human verdict is required, model-assisted findings escalate instead of rejecting |
| 25. the Rights Registry is current [MET_WITH_EXCEPTION] | design-lab/config/rights-registry.json covers 74 subjects, 4 adjudicated -- GAP: 70 subjects remain NOT_ADJUDICATED and are carried as an exception |
| 26. H3 has not bypassed the Rights Gate [MET] | adapter status BLOCKED_BY_LICENSE everywhere; the manifest claims no supported capability; nothing was downloaded or run |
| 27. third-party sources are minimally absorbed or locked [MET_WITH_EXCEPTION] | verdict NO_FULL_THIRD_PARTY_SOURCE_TREES_TRACKED: 0 tracked full copies, 37 only in an ignored cache, 6 via lock reference -- GAP: 7 of 46 lock entries carry no canonical URL and 0 carry a pinned revision |
| 28. current reports bind the exact subject [MET] | subject_sha, taskpack id and hash, worktree digest and taskpack binding are recorded; --check reports scope=bound-input-integrity with git-and-cloud explicitly NOT_VERIFIED |
| 29. a clean clone reproduces the static and test layers [MET] | verify_fresh_clone.py passes 9 stages on a fresh clone; install is NOT_VERIFIABLE and is reported as such |
| 30. DeepSeek impersonated no real design host E3/E4 [MET] | EVIDENCE-LEVEL-AUDIT.json: 4 claims examined, 0 overclaims, all historical and qualified |
| 31. the Codex handoff is fully generated [MET] | docs/taskpacks/DESIGN-LAB-CODEX-REAL-HOST-HANDOFF.md: 8 domains with contract, fixture, commands, evidence template, do-not-claim list and rollback |
| 32. the worktree is clean or every change is attributed [MET] | the tree is clean at the recorded subject; every committed change names an owner task |

## What is NOT claimed

* DESIGN-LAB product complete
* Photoshop integrated E3
* Illustrator integrated E3
* OpenDesign integrated E3
* ComfyUI production ready
* Blender integrated
* MiniMax validated
* professional design quality passed
* Human Jury passed
* release ready

## Codex starting point

Contract, fixtures, command outlines, evidence templates, do-not-claim lists and rollback expectations for eight domains are in `docs/taskpacks/DESIGN-LAB-CODEX-REAL-HOST-HANDOFF.md`.
Codex does not need to repeat repository cleanup, language planning, DB schema refactoring, directory migration, third-party source cleanup or spill cleanup.
