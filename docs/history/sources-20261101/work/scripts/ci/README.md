# CI and boundary checks

`classify_paths.py` maps changed files to modules. `aggregate_gate.py` is an
always-running required gate: failed, cancelled, missing, or skipped required
jobs fail the aggregate result. CI must run from exact module paths and must not
silently waive cross-contract changes.
