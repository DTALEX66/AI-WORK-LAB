# Absorption-ledger reconciliation (verify user-submitted projects)

The user repeatedly provides "可并入" (absorbable) open-source projects and expects
them tracked in the project's absorption ledger. **Do NOT assume user-submitted
projects were registered** — the ledger can stall or drift. Always reconcile
against the authoritative source before answering "are all open-source projects
absorbed?".

## Authoritative sources (Cognitive-Loop-OS)

- Ledger (machine truth): `inspiration_research/resources/open_source_absorption_ledger.json`
- Registry (parallel source): `inspiration_research/resources/open_source_project_registry.json`
- Doc matrix: `docs/ABSORPTION_EXECUTION_MATRIX.md`
- Statuses: `implemented` / `adapter_contract_pending` / `deferred_review` / `reference_only`

## Reconciliation steps

1. **Field name is `execution_state`, not `status`.** Naively counting `status`
   returns all-unknown:
   ```python
   from collections import Counter
   import json
   d = json.load(open('<ledger>', encoding='utf-8'))
   items = d['projects'] if 'projects' in d else d
   print(Counter(x.get('execution_state', '?') for x in items))
   ```
2. **Read the same counts from the registry.** The two files can drift — a real
   case was ledger `implemented=8` while registry reported `implemented=0`.
3. **Check the ledger's last git touch**:
   `git log --oneline -1 -- <ledger>`. If it hasn't changed since an old PR,
   later user-provided projects were NOT registered. That is a gap, not "all done".
4. `implemented` must bind to a real code path + test. Do not promote on README/
   registry listing alone.
5. Report the honest counts + the registry-vs-ledger drift. The matrix's R0 phase
   exists to eliminate this drift — say it's open, don't claim it's resolved.

## Reporting rule

When the user asks "are all open-source projects absorbed?" and the ledger is
stale or drifted, answer with the real numbers and the drift, and offer to do the
reconciliation — do not assert completion. This is a governance/inventory concern,
distinct from the per-lib adapter implementation covered in the main SKILL.md.
