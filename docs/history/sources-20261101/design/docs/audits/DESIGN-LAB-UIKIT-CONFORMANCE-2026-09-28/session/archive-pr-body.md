## What

Archives the complete UI-kit conformance round **in-repo** (223 files, ~2.7 MB), so the work no longer exists only inside the gitignored `.project-local` tree.

```
docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/
  00-INDEX.md        provenance, SHAs, layout, reproduction, exclusions
  pack/              owner-supplied pack documents, verbatim
  findings/          W00 / W01 / W02 / W03 / W14 deliverables
  evidence/          raw harness outputs (W02-LEAK-SWEEP.txt, *-VERIFY, *-PROBE)
  harness/           the runnable audit tooling that produced evidence/
  session/           commit/PR drafts + superseded revisions (traceability only)
  ui-originals/      extracted B04/B07/B10 originals, incl. the 17 B04 design sheets
docs/handoffs/DESIGN-LAB-UIKIT-CONFORMANCE-ROUND-2026-09-28.md
```

`ui-originals/` now lives in-repo, so future conformance work no longer depends on the external `D:\All projects\UI套件` archives.

## Result recorded in the archive

Deleting every unscoped, element-only legacy rule through the CSSOM and diffing **all** computed longhands of every `.app` element across all 12 routes plus the default and login screens (328 elements):

| Scope | Before | After |
|---|---|---|
| **inside `.app`** (the B10 1:1 subject) | 8 | **0** (fixed in #183) |
| outside `.app` (login, `#workspace`, `nav.app-nav`) | 1923 | 1923 |

The 1923 out-of-`.app` bindings are the reason the legacy element rules **cannot** be blanket-scoped to `body > …` — an earlier plan in this round to do exactly that would have broken the login and workspace screens. That boundary is recorded in both the index and the handover.

## Placement and gate compliance

- Placed under `docs/audits/`, **deliberately not** `docs/taskpacks/`: `docs/taskpacks/**` is scanned by the authority-chain and context-integrity gates, so an archive there risks being misclassified as a historical taskpack or read as an authority claim.
- Archived `.py/.mjs/.js` carry `SPDX-License-Identifier`; the 17 binary design sheets carry `.license` sidecars — both required by the **License & secret hygiene gate**.
- Every text file is valid UTF-8. The **identity gate** reads all tracked text and **fails closed** on an unreadable file — it caught this archive's own first sweep output, which a PowerShell `*>` redirect had written as UTF-16LE. Evidence is now written as explicit UTF-8.

Verified locally before committing:

| Gate | Result |
|---|---|
| `verify_license_coverage.py` | `LICENSE_COVERAGE=OK` |
| `verify_identity_gate.py` | `IDENTITY_GATE=OK total=0` |
| `verify_top_level_authority.py` | `TOP_AUTHORITY_GATE=PASS checks=10 failed=none` |
| `verify_context_integrity.py` | `PASS` |

## State

Docs/evidence only — **no capability-axis promotion is claimed**. `host_live` (1/28) and `delivery` (0/28) still require real host hardware. `docs/audits/**` is not an authority surface; the index and handover both carry an explicit HISTORICAL banner.
