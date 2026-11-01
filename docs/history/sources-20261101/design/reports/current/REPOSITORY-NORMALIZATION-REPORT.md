# Repository Normalization Report

Subject: `15b3b6838af52cf7376b2d78fa5dc4389c709d8a`

## Repository Normalization Report

Repository directory scheme audited: CONFORM 14, DEVIATION 1 (design-lab dual scheme), EMPTY_DIR 1 (services), EXTRA 3 (git-ignored local directories).
Legacy path scan: active legacy usage 0; the remaining hits are historical records and guard markers that keep the refusal vocabulary.
Single writer for task status is design-lab/config/task-ledger-r3.json; the machine authority ledger has one writer script and `verify` passes for all 58 tasks.
current/ and history/ are separated: superseded packs live under docs/history/ and are classified as HISTORY or ACTIVE_PRODUCT_PACK, never as a dispatch entry.
Project status projections bind subject type, worktree digest and taskpack identity, and refuse to present a dirty tree as a commit.
