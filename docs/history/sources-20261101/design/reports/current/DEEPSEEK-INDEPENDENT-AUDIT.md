# DeepSeek Authority R1 — Independent Audit

**Verdict: `CLAIMS_PARTLY_SUPPORTED`**

- **Auditor**: independent worker (different context from the implementer)
- **Audited at**: `2026-09-14T00:46:53+08:00` (RFC3339)
- **Subject SHA at audit close**: `e7c03bf7134c6e64b187d8bff66602f19798cb2b`
- **Subject SHA at audit open**: `2cf76413ad1a27af8767037058dc38a8c5ce6d56`
- **Ledger**: `reports/current/DEEPSEEK-AUTHORITY-LEDGER-2026-09-14.json`, sha256 `a4dd0e05abb524facfe623084d674a8faf6fca2d2802cc7a1680d130881dd0a0`, updated_at `2026-09-13T16:46:47+00:00`

> **The subject moved while it was being audited.** The implementer committed Wave 7 during this
> audit (`2cf76413` → `a65b22d` → `e7c03bf`) and rewrote the ledger twice (DONE 43/58 → 50/58).
> Every hash below is therefore point-in-time, and a re-run may legitimately differ.

---

## 1. Contradictions (read these first)

| # | Contradiction | Evidence line |
|---|---|---|
| 1 | **The authority-reconciliation artifact fails its own `--check`.** | `AUTHORITY_CHAIN=DRIFT entries changed since generation` (exit 1) — reproduced on the byte-exact committed file. Stored entries record `.project/manifest.yaml` at 573 bytes and the ledger at 17736 bytes; they are 809 and ~39718 now. |
| 2 | **The cleanup manifest labels its deleted set as evidence-bearing.** | All **167** records under `RUNTIME-CLEANUP-MANIFEST.json["deleted"]` carry `"classification": "EVIDENCE_BEARING"` and `"reason": "...owner approval required"`, yet **166/167 are absent from disk** and `bytes_reclaimed=332173158`. The path set equals `RUNTIME-CLEANUP-PLAN.json["temp_cache"]` (167/167) and overlaps the plan's 15 `evidence_bearing` members by **0**. Ledger DLDS-D030 says the deleted set was 167 **TEMP_CACHE** entries. |
| 3 | **The supply-chain secret scan can swallow a real credential.** | `is_synthetic('design-lab/tests/test_runtime_asset_safety.py', 'AKIA3XJ7QZ2LMN4PQRST')` → `True`. Blanket path rule (`fixtures/`, `design-lab/tests/`, `tests/`) exemption plus substring markers including `<` and `xxxx`. |
| 4 | **DLDS-E050's recorded post-cleanup PASS is not reproducible.** | `POST-CLEANUP-AUDIT.json` verdict `PASS` with stage `CURRENT_REPORTS=PASS mode=check`; the same command now emits `CURRENT_REPORTS=DRIFT reports/current/PROJECT_STATUS.json, ... design-lab/config/current-report-index.json` (exit 1, 9 projections). |
| 5 | **Two stored gate artifacts are already stale.** | `LANGUAGE_INVENTORY=DRIFT` (exit 1); `EVIDENCE_LEVELS=DRIFT` (exit 1) — the stored artifact records `claims_examined=4` against a fresh **8**. |
| 6 | **A declared contract-graph consumer edge does not exist in the code.** | `CONTRACT-GRAPH.json` declares `QA.consumers = ['src/design_lab/assurance/human_jury.py']`, but that file never references `qa_plane` — only comments at lines 11 and 68. |
| 7 | **An unsourced "before" figure in the ledger.** | DLDS-D030: `Measured .project-local 4557.7 -> 4241.0 MiB`. `4557.7` appears in no readable artifact; measurements give `4241.03` and `4257.23`. |
| 8 | **The spill self-test exercised a failing command.** | `task under test: python.exe generate_current_reports.py --check exit=1` inside the self-test that reported `ZERO_SPILL=NO_SPILL_DETECTED spill=0`; `self_test()` never inspects `result.returncode`. |

## 2. Area findings

### Authority — `PARTIAL`
- Taskpack sha256 `d9fdaa3ad7ad0055a3f451c853756be41036b32112cacc4d1c17b314c005a2f9` equals the ledger's recorded value — **CONFIRMED**.
- `LEDGER=PASS tasks=58 taskpack_sha256_ok=true` (exit 0) — **CONFIRMED**.
- `AGENTS.md` line 96 is the only line naming a current DeepSeek taskpack (线 97 names the R5 *product* pack, not a second DeepSeek pack) — **CONFIRMED**.
- **Contradiction 1**: `deepseek_authority_chain.py --check` → DRIFT.

### Worktree attribution — `CONFIRMED`
97 entries; `{'KEEP_WITH_FIX': 87, 'OUT_OF_PACK': 7, 'KEEP': 3}`; `unproven_paths: []`; no `UNATTRIBUTED` entry; 0 duplicate paths. Spot-checks: `src/design_lab/readiness/vector_provider.py` is `OUT_OF_PACK` **and absent from the tree**, with an exact-hash quarantine copy; `design-lab/readiness/model-radar.json` is `KEEP_WITH_FIX` on disk with a matching sha256. `DELETE-MANIFEST.json` holds exactly those 7 paths: **7/7 quarantine copies digest-ok, 0 missing**, sources removed, `restore_command` present.
*Caveats*: the recorded digests are a 16:16 snapshot — `current-report-index.json` and `assurance-jury-record-v2.schema.json` no longer match; and `current-report-index.json` is `KEEP_WITH_FIX` while its own `producer`/`consumer` fields say `unattributed`.

### Cleanup — `PARTIAL`
- **Migration CONFIRMED**: 10 records summing to exactly **11,565,138** bytes; all 10 archive targets present with matching file counts (287/287, 192/192, …); single-file digests match; all sources gone from `.hermes`; per-record restore text plus `restore_command`; `refused=[{"path": ".hermes/skill-call-index.json", "reason": "agent-native artifact, DO_NOT_TOUCH"}]`.
- `.hermes` now holds **exactly one file**: `skill-call-index.json`, 13638 bytes, mtime `2026-08-24 00:02:11` — untouched, as claimed. `task-runtime`/`task-artifacts` remain as **empty** directories.
- **Contradiction 2**: the deleted-set labels. Also, the "restore path" for a cache is a *recreation note* (`{'__pycache__', 'tmp', '.pytest_cache', 'pip-cache', '.cache'}`) and a `--restore` mode that states outright no file copy can restore a cache.

### Contract graph — `PARTIAL`
`CONTRACT_GRAPH=PASS`; artifact `NO_BROKEN_LINK`, `counts {'concepts': 11, 'complete': 11, 'breaks': 0}`.
Hand-check 1 — **Job → `requirement_ledger.py`: real** (`from .store import ... require_job`, `require_job(conn, job_id)` at lines 65/137).
Hand-check 2 — **QA → `human_jury.py`: not real** (contradiction 6).
The gate's `complete` is `not missing_files and not missing_tables and bool(spec["models"])` — an **existence** test over a hand-written declaration table; no consumer edge is ever resolved, and `--check` compares only `counts`.

### Migration — `CONFIRMED`
`MIGRATION_REHEARSAL=PASS steps=15 status=REHEARSED_PASS_PENDING_ACCEPTANCE` (exit 0, 0.3 s); all 15 steps ok. DB snapshot diff across the run: **`DB changed: []  DB new: []  DB gone: []`** over 13 pre-existing `*.db` files.
*NOT_VERIFIABLE as literally stated*: `.project-local/state/` **does not exist**, so the live database named by `store.py` (`.project-local/state/design-lab.db`) cannot have its mtime compared. The substitution above is the strongest available proxy. Leftover `legacy.db` in `task-runtime/creative-migration-rehearsal/tmptpoi00zq/` shows temp cleanup is not reliable on Windows.

### Spill — `PARTIAL`
`ZERO_SPILL=NO_SPILL_DETECTED spill=0 repo_new=19 repo_changed=17` (exit 0). The probe **does** compare snapshots: 37,500 repo entries and 401 agent entries stored as `[size, mtime]` maps; `diff()` computes `new`/`removed`/`changed` by set difference and flags a new path as spill only outside `ALLOWED_ROOTS` — which is why 19 new and 17 changed paths inside `.project-local` correctly scored `spill=0`. Diff file: `.project-local/task-artifacts/zero-spill/self-test-before-diff.json`.
*Contradiction 8*: the wrapped command exited 1 and the return code is never checked.

### Language — `PARTIAL`
`LANGUAGE_BOUNDARY=PASS files=1886 forbidden=0 fixture_scoped=1 conditional=0 python_roots=1 node_manifests=1 lockfiles=0 vocab_copies=13 disagreeing=0` (exit 0). The one scoped file is the Java `MainActivity.java` in the game-visual fixture.
Two discrepancies: fresh `vocab_copies=13` vs the committed artifact's **14** and the DLDS-C050 note's **14**; and `LANGUAGE_INVENTORY=DRIFT` (exit 1).

### Size — `PARTIAL`
`REPOSITORY_SIZE=CHECK_PASS pack_mib=210.40 status=OK` (exit 0). `before_measurement_source` cites `reports/current/UNTRACKED-RUNTIME.json (DLDS-D000, measured before the cleanup)` and that artifact really does contain `total_mib = 4448.46` — the citation is accurate. Reclaimed bytes re-derived independently: **167 records, digest on 167/167, sum 332,173,158 bytes, 166/167 paths now absent**.
But the pair is not like-for-like: `UNTRACKED-RUNTIME.json` was measured `16:26:39`, **10 s after** `deleted_at 16:26:29`, so the "before" is post-deletion; it is a **four-root** total (`.project-local` 4241.03 + `.hermes` 11.04 + `.venv` 196.33 + `.pytest_cache` 0.06) while the "after" is `.project-local`-only. Hence `4448.46 − 316.79 = 4131.67 ≠ 4257.23` (125.56 MiB unexplained), and `.project-local` **grew** 16.20 MiB during the window. Contradiction 7 covers the unsourced `4557.7`.

### Evidence overclaim — `CONFIRMED`
Fresh classification: **8 claims, all `HISTORICAL_EVIDENCE_KEPT`, 0 `OVERCLAIM`, 0 `REVIEW`**; `EVIDENCE_LEVEL_SELF_TEST=PASS` (the classifier is not vacuous). My own case-sensitive `\bE[34]\b` grep over `docs/handoffs/DEEPSEEK-*` (14 hits) and `reports/current/DEEPSEEK-*` (6 hits), judged one by one: `DEEPSEEK-OPEN-DESIGN-E3-READINESS-2026-09-13.md` **refuses** the claim (`| E3 REAL_WORKFLOW | ... | **not met** |`, `delivery | NOT_DELIVERED |`); `DEEPSEEK-DEEP-ADAPTATION-EXECUTION-2026-09-13.md:112` only names the task id; the H3 lines concern MiniMax H3 (not a forbidden host) and say the run was `**not** promoted to current capability`; the `reports/current` hits are paths, the ledger's note about *fixing* the H3 over-claim, and the gate description.
*Caveat*: `EVIDENCE_LEVELS=DRIFT`, and the gate's surface is narrow (out of scope: `docs/history/`, `reports/history/`, `docs/taskpacks/`).

### Supply chain — `PARTIAL`
`SUPPLY_CHAIN=PASS` (exit 0); the report contains **exactly 9 checks, all `ok=true`** (`G000_sources_lock`, `G010_adapter_status`, `G030_h3_blocked`, `G040_license_audit`, `G040_secret_scan`, `G040_lockfile_audit`, `G040_generated_artifacts`, `G040_binary_inventory`, `G040_third_party_sources`), secret scan `hit_count: 0`, `synthetic_values_exempted: 1` — **CONFIRMED**.
The exemption claim is **CONTRADICTED** (contradiction 3): two escape hatches, no entropy check, no exact-value allowlist, and no counter that fails the gate when the exemption count grows.

## 3. Could not verify from here (`NOT_VERIFIABLE_FROM_HERE`)

1. **The live state database.** `.project-local/state/` does not exist, so "the live database was not modified" cannot be checked as stated. Proxy used: no pre-existing `*.db` under `.project-local` changed size or mtime (13 files, 0 changed).
2. **The frozen delta `9f34b53..5631963`.** I re-hashed four current paths only; two recorded digests are already stale. Whether all 97 matched at 16:16 needs a historical checkout.
3. **That all 316.79 MiB deleted was genuinely recreatable.** Paths are cache-shaped and the set equals the plan's `temp_cache` bucket; per-byte regenerability is not provable from here.
4. **Cloud/CI state, host launches, GPU inference, any E3/E4 workflow** — outside this checkout; not attempted.
5. **The correctness of the Wave 7 commits made during the audit** (H000/H020/H040, I000/I010/I020, J000) — not audited; the ledger's DONE count moved 43 → 50 while I worked.
6. **DRIFT-vs-concurrency separation.** HEAD moved twice during the audit, so I cannot fully separate "the artifact was stale" from "the tree changed under me".

## 4. Limitations

An auditor inside this checkout can verify that declared files exist, that hashes and digests agree,
that recorded numbers sum correctly, and that tools reproduce their own verdicts on the current tree.
It cannot decide whether a recorded decision was the right one, whether a "before" measurement was
taken at the right moment, whether cache data was truly recreatable, or whether a passing local gate
corresponds to any external outcome. Evidence levels above E2 are not reachable from here.

**Disclosure of writes.** Three artifacts were rewritten by the blessed tools this audit was instructed
to run — `DEEPSEEK-AUTHORITY-CHAIN.json`, `CREATIVE-MIGRATION-REHEARSAL.json` and
`LANGUAGE-BOUNDARY-SCAN.json`. All three were restored to the exact state found (`git status` clean for
each; `LANGUAGE-BOUNDARY-SCAN.json` re-hashed equal to its pre-audit value
`0101b3198da9aebe169c30a130a2c2d66d0916537f3eb91d83b3efcc71391b67`). The only files this audit leaves
behind are `reports/current/DEEPSEEK-INDEPENDENT-AUDIT.json` and `reports/current/DEEPSEEK-INDEPENDENT-AUDIT.md`.
