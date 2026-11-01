# DESIGN-LAB V3 Phase2+ Handoff

- Date: 2026-08-05 08:09 +0800
- Repository: `DTALEX66/DESIGN-LAB`
- Base HEAD before apply: `efb31ff`
- Reviewed staging candidate tree before this handoff file: `9cc8c7b2f49099114714ecd0c1174bfe29a276af`
- Candidate scope before this handoff file: 219 changed files
- Runtime evidence root: `.hermes/task-artifacts/open-design-v3/` (ignored, not uploaded)

## Goal

Convert the repository from a DESIGN/minigame-heavy helper bundle into an Open Design-first, Agent-compatible commercial design intelligence and visual-quality enhancement layer, while keeping evidence levels explicit and avoiding false runtime/commercial claims.

## Implemented scope

1. Product definition and public entrypoints
   - Added V3 project definition and architecture docs.
   - Updated root and `design-lab/` README entries so the Open Design-first positioning and V3 verification commands are visible.

2. Machine-readable product contracts
   - Added `design-lab/config/product-manifest.json`.
   - Added `design-lab/config/capability-status.json`.
   - Added schema coverage for product manifest, capability status, project state and provenance.

3. Open Design capability surface
   - Added TaskPack V3 atoms, bundles, scenarios, profiles, rubrics, knowledge and research records.
   - Upgraded legacy plugin manifests with compatibility/evidence metadata through the scaffolded manifest convention.

4. Runtime and evidence gates
   - Added `verify_product_manifest_v3.py` for product-manifest/capability evidence convergence.
   - Added `verify_runtime_contracts_v3.py` for scenario/atom/bundle runtime contracts and isolated provenance/state smoke records.
   - Added `verify_visual_scoring_v3.py` for visual score, critique score and visual-iteration regression behavior.
   - Integrated the new verifiers into `verify_open_design_assistance.py`.

5. Visual quality scoring hardening
   - Reworked visual score, design critique score and iteration comparison scripts so hard gates, missing evidence and regressions fail closed instead of being hidden by high numeric scores.

## Verification evidence

Staging gates before main apply:

```text
VERIFY_PRODUCT_MANIFEST_V3=OK total=203 failed=0
VERIFY_RUNTIME_CONTRACTS_V3=OK total=223 failed=0
VERIFY_VISUAL_SCORING_V3=OK total=10 failed=0
VERIFY_RESULT=OK total=456 failed=0
VERIFY_V2_PROTOCOLS=OK
VERIFY_VISUAL_QUALITY_V21=OK
STAGE_GATES_OK
```

Main apply identity check:

```text
stage_tree=9cc8c7b2f49099114714ecd0c1174bfe29a276af
applied_tree=9cc8c7b2f49099114714ecd0c1174bfe29a276af
APPLY_REVIEWED_CANDIDATE_OK
```

Read-only review before local apply:

```text
outside_allowed_roots=[]
secret_name_hits=[]
secret_value_hits=[]
diff_check_exit=0
main_status_count=0
decision=GO_FOR_USER_AUTHORIZED_LOCAL_APPLY
```

## Boundaries and non-claims

- This handoff does not claim E3 live Open Design runtime availability for every new capability; E3 still requires current daemon/API registration, task execution and artifact/provenance read-back.
- This handoff does not claim E4 release or E5 commercial proof; those require exact-SHA CI/remote read-back and external acceptance.
- Runtime evidence and smoke artifacts remain in ignored `.hermes/task-artifacts/open-design-v3/` and are intentionally not uploaded.
- No credentials, local auth state, `.env`, private keys, cookies or runtime secrets are part of the tracked candidate.

## Next dependency-safe steps

1. Run the full gate on the main working tree after this handoff file is staged.
2. Commit the exact staged tree.
3. Push to GitHub.
4. Read back the remote branch SHA and, if CI is configured, bind any CI results to the uploaded exact SHA.
5. Continue later with E3 live Open Design runtime registration and task/read-back evidence.
