#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W00 — code-level evidence scan for all 28 R5 ledger tasks.

For each ledger task: list candidate implementing modules / test modules / docs,
VERIFY each exists in this checkout, and report how many are test modules (a
proxy for evidence strength). Also reports which axes already carry a bound
evidence receipt.

Honesty rules applied:
  * every path printed is existence-checked; missing ones are listed explicitly
  * "evidence exists" != "task complete": no axis state is changed here
  * the candidate list is a curated mapping, not an automatic keyword match, so
    it is reproducible and reviewable
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
LEDGER = ROOT / "design-lab/config/task-ledger-r3.json"

# Curated candidate map: task id -> (modules, tests, docs)
M: dict[str, dict[str, list[str]]] = {
    "DL-R5-001": {"mod": [".project/manifest.yaml"], "test": [
        "design-lab/tests/test_r5_migration.py", "design-lab/tests/test_r5_intake.py",
        "design-lab/tests/test_current_reporting.py"], "doc": [
        "docs/history/taskpacks/r3-ledger-pre-r5-20260909.json",
        "design-lab/config/task-ledger-r3.json"]},
    "DL-R5-002": {"mod": [".project/paths.json", ".project/governance/data-ownership.yaml",
                          "design-lab/scripts/context_capsule.py"], "test": [
        "design-lab/tests/test_project_paths.py", "design-lab/tests/test_path_ref_gate.py"],
        "doc": [".project/governance/path-ref-policy.json", ".project/governance/path-risk.yaml"]},
    "DL-R5-003": {"mod": ["scripts/run_python_tests.py"], "test": [
        "design-lab/tests/test_core_gates.py", "design-lab/tests/test_effective_evidence.py",
        "design-lab/tests/test_test_entry_environment.py", "design-lab/tests/test_ci_artifact_proof.py"],
        "doc": [".github/workflows/canonical-verify.yml", ".github/workflows/release-gate.yml"]},
    "DL-R5-004": {"mod": ["src/design_lab/native_tasks.py", "src/design_lab/task_queries.py",
                          "src/design_lab/native_workers.py"], "test": [
        "design-lab/tests/test_native_recovery_lock.py", "design-lab/tests/test_native_quiescence.py",
        "design-lab/tests/test_runtime_attempt_safety.py", "design-lab/tests/test_operation_coordinator.py"],
        "doc": ["docs/architecture/ARCHITECTURE.md"]},
    "DL-R5-005": {"mod": ["src/design_lab/native_assets.py", "src/design_lab/native_bundles.py",
                          "src/design_lab/image_assets.py"], "test": [
        "design-lab/tests/test_asset_store.py", "design-lab/tests/test_bundle_store.py",
        "design-lab/tests/test_image_import_recovery.py", "design-lab/tests/test_runtime_asset_safety.py"],
        "doc": ["docs/decisions/EVIDENCE_POLICY.md"]},
    "DL-R5-006": {"mod": ["src/design_lab/readiness/"], "test": [
        "design-lab/tests/test_model_manifest.py", "design-lab/tests/test_model_cache.py",
        "design-lab/tests/test_profile_resolver.py", "design-lab/tests/test_readiness_model_radar.py"],
        "doc": ["docs/LOCAL_ENVIRONMENT.md"]},
    "DL-R5-007": {"mod": ["src/design_lab/cli.py", "src/design_lab/service.py"], "test": [
        "design-lab/tests/test_doctor.py", "design-lab/tests/test_doctor_evidence.py",
        "design-lab/tests/test_service_cli.py"], "doc": ["docs/LOCAL_ENVIRONMENT.md"]},
    "DL-R5-008": {"mod": ["src/design_lab/generators/"], "test": [
        "design-lab/tests/test_comfy_http.py", "design-lab/tests/test_comfy_task_protocol.py",
        "design-lab/tests/test_creative_generative.py"],
        "doc": ["integrations/generators/comfyui/adapter.manifest.json",
                "integrations/generators/comfyui/evidence/E3-20260816-end-to-end-generation.md"]},
    "DL-R5-009": {"mod": ["src/design_lab/reconstruction/"], "test": [
        "design-lab/tests/test_installed_state_resources.py", "design-lab/tests/test_rir_source_import.py",
        "design-lab/tests/test_reconstruction_contracts.py"],
        "doc": ["pyproject.toml", "design-lab/schemas/reconstruction/reconstruction-evidence.schema.json"]},
    "DL-R5-010": {"mod": ["apps/workbench/workbench.ts", "apps/workbench/shell.ts",
                          "src/design_lab/workbench.py"], "test": [
        "design-lab/tests/test_workbench_native_ui.py", "design-lab/tests/test_workbench_design_layer_e2e.py",
        "apps/workbench/tests/unit.mjs", "apps/workbench/tests/appshell.mjs"],
        "doc": ["apps/workbench/index.html"]},
    "DL-R5-011": {"mod": ["integrations/hosts/adobe/illustrator/"], "test": [
        "design-lab/tests/test_illustrator_com_adapter.py", "design-lab/tests/test_illustrator_bridge_paths.py",
        "design-lab/tests/test_illustrator_text_readback.py", "design-lab/tests/test_illustrator_local_patch.py",
        "design-lab/tests/test_illustrator_job_validation.py", "design-lab/tests/test_illustrator_patch_preflight.py"],
        "doc": ["integrations/hosts/adobe/illustrator/ASSEMBLY-CONTRACT.md",
                "integrations/hosts/adobe/reconstruction-operator-guide.md"]},
    "DL-R5-012": {"mod": ["integrations/hosts/adobe/"], "test": [
        "design-lab/tests/test_photoshop_com_adapter.py", "design-lab/tests/test_photoshop_readback_scaling.py",
        "design-lab/tests/test_photoshop_patch_plan.py", "design-lab/tests/test_photoshop_runtime_entry.py",
        "design-lab/tests/test_photoshop_legacy_native.py"],
        "doc": ["integrations/hosts/adobe/E3_FIXTURE_PROTOCOL.md",
                "design-lab/schemas/adapter-contract.schema.json"]},
    "DL-R5-013": {"mod": ["src/design_lab/reconstruction/", "src/design_lab/native_plan.py"], "test": [
        "design-lab/tests/test_ocr_object_plan.py", "design-lab/tests/test_planar_decomposition.py",
        "design-lab/tests/test_reconstruction_layers.py", "design-lab/tests/test_design_ir.py",
        "design-lab/tests/test_reconstruction_fusion.py"],
        "doc": ["design-lab/schemas/reconstruction/reconstruction-evidence.schema.json"]},
    "DL-R5-014": {"mod": ["src/design_lab/assurance/", "packages/capabilities/quality/jury/"], "test": [
        "design-lab/tests/test_assurance_jury.py", "design-lab/tests/test_assurance_quality_record.py",
        "design-lab/tests/test_assurance_qa_plane.py", "design-lab/tests/test_production_preflight.py",
        "design-lab/tests/test_quality_gate.py", "design-lab/tests/test_quality_pipeline.py"],
        "doc": ["design-lab/config/RELEASE_EVIDENCE_CONTRACT.md"]},
    "DL-R5-015": {"mod": ["design-lab/config/product-manifest.json"], "test": [
        "design-lab/tests/test_release_gate.py", "design-lab/tests/test_release_gate_effective.py",
        "design-lab/tests/test_release_preflight.py", "design-lab/tests/test_handoff_readiness.py"],
        "doc": ["reports/current/RELEASE_READINESS.json"]},
    "DL-R5-016": {"mod": ["src/design_lab/interop/"], "test": ["design-lab/tests/test_media_audio.py"],
                  "doc": ["design-lab/schemas/media-video-boundary.schema.json"]},
    "DL-R5-017": {"mod": ["src/design_lab/interop/"], "test": ["design-lab/tests/test_media_audio.py"],
                  "doc": ["design-lab/schemas/media-video-boundary.schema.json"]},
    "DL-R5-018": {"mod": ["integrations/generators/minimax-h3/"], "test": [
        "design-lab/tests/test_creative_generative.py"],
        "doc": ["integrations/generators/minimax-h3/adapter.manifest.json",
                "integrations/generators/minimax-h3/evidence/E3-20260816-end-to-end-generation.md"]},
    "DL-R5-019": {"mod": ["src/design_lab/interop/"], "test": ["design-lab/tests/test_interop_timeline.py"],
                  "doc": ["design-lab/schemas/media-video-boundary.schema.json"]},
    "DL-R5-020": {"mod": ["src/design_lab/interop/"], "test": ["design-lab/tests/test_media_three_d.py"],
                  "doc": ["design-lab/schemas/media-three-d-adapter.schema.json"]},
    "DL-R5-021": {"mod": ["integrations/executors/agents/", "integrations/hosts/open-design/",
                          "integrations/adapter-registry.json"], "test": [
        "design-lab/tests/test_open_design_host_adapter_neutrality.py",
        "design-lab/tests/test_federation_e2e.py", "design-lab/tests/test_federation_review.py",
        "design-lab/tests/test_adapter_spi.py"], "doc": ["docs/decisions/NEUTRALITY_POLICY.md",
                                                          "docs/decisions/ADAPTER_POLICY.md"]},
    "DL-R5-022": {"mod": ["src/design_lab/interop/"], "test": [
        "design-lab/tests/test_interop_provenance.py", "design-lab/tests/test_interop_dtcg.py"],
        "doc": ["design-lab/schemas/interop-penpot-adapter.schema.json"]},
    "DL-R5-023": {"mod": ["scripts/generate_current_reports.py"], "test": [
        "design-lab/tests/test_history_baseline_retrieval.py", "design-lab/tests/test_migration_preview.py",
        "design-lab/tests/test_release_preflight.py"], "doc": ["reports/history-baseline.json"]},
    "DL-R5-024": {"mod": ["src/design_lab/adapters/"], "test": [
        "design-lab/tests/test_control_capability_matrix.py", "design-lab/tests/test_adapter_locator_audit.py"],
        "doc": ["design-lab/config/adapter-locator-inventory.json"]},
    "DL-R5-025": {"mod": ["src/design_lab/generators/"], "test": [
        "design-lab/tests/test_comfy_task_protocol.py"],
        "doc": ["integrations/generators/comfyui/adapter.manifest.json"]},
    "DL-R5-026": {"mod": ["src/design_lab/generators/"], "test": [
        "design-lab/tests/test_comfy_http.py"],
        "doc": ["integrations/generators/comfyui/evidence/README.md"]},
    "DL-R5-027": {"mod": ["fixtures/domains/game-visual/"], "test": [
        "design-lab/tests/test_minigame_visual_fixture_boundary.py"],
        "doc": ["fixtures/domains/game-visual/docs/PROJECT_EXECUTION_BOUNDARY.md"]},
    "DL-R5-028": {"mod": ["apps/workbench/tsconfig.json", "apps/workbench/package.json",
                          "apps/workbench/vite.config.ts"], "test": [
        "design-lab/tests/test_workbench_native_ui.py", "apps/workbench/tests/unit.mjs"],
        "doc": ["docs/architecture/LANGUAGE-POLICY.md", "reports/current/LANGUAGE-BOUNDARY-SCAN.json"]},
}

ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
tasks = ledger["tasks"]
titles = {t["id"]: t["title"] for t in tasks}
bound = {t["id"]: sorted(a for a, v in t["axes"].items() if v["evidence"]) for t in tasks}

print("=" * 100)
print("W00  CODE-LEVEL EVIDENCE SCAN  (all paths existence-checked)")
print("=" * 100)

rows = []
total_missing = 0
for t in tasks:
    tid = t["id"]
    spec = M.get(tid, {"mod": [], "test": [], "doc": []})
    counts, missing = {}, []
    for kind in ("mod", "test", "doc"):
        ok = 0
        for p in spec[kind]:
            if (ROOT / p).exists():
                ok += 1
            else:
                missing.append(p)
        counts[kind] = ok
    total_missing += len(missing)
    rows.append((tid, titles[tid], counts, missing, bound[tid]))

print(f"\n{'R5':<12}{'title':<28}{'mod':>4}{'test':>6}{'doc':>5}  {'bound axes':<16}missing")
for tid, title, c, missing, b in rows:
    print(f"{tid:<12}{title[:26]:<28}{c['mod']:>4}{c['test']:>6}{c['doc']:>5}  "
          f"{(','.join(b) or '-'):<16}{len(missing)}")

print(f"\nTOTAL missing candidate paths: {total_missing}")
if total_missing:
    print("  missing list:")
    for tid, title, c, missing, b in rows:
        for p in missing:
            print(f"    {tid}  {p}")

zero = [r[0] for r in rows if sum(r[2].values()) == 0]
print(f"\ntasks with NO verified candidate at all: {zero or 'none'}")
print(f"tasks with >=1 test module            : "
      f"{sum(1 for r in rows if r[2]['test'] > 0)}/28")
print(f"tasks with a bound evidence receipt   : "
      f"{sum(1 for r in rows if r[4])}/28  -> "
      f"{[r[0] for r in rows if r[4]]}")

dst = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/W00-EVIDENCE-SCAN.json"
dst.write_text(json.dumps({
    "provenance": "curated candidate map, every path existence-checked in this checkout; "
                  "'evidence exists' != 'task complete'; no axis state changed",
    "sha": "d116b14995fcdbba1b165ec5bc3124f5daed3d15",
    "rows": [{"task": t, "title": ti, "counts": c, "missing": m, "bound_axes": b,
              "paths": M.get(t, {"mod": [], "test": [], "doc": []})}
             for t, ti, c, m, b in rows],
    "totals": {"missing_paths": total_missing, "tasks_with_no_candidate": zero,
               "tasks_with_test": sum(1 for r in rows if r[2]['test'] > 0),
               "tasks_with_receipt": sum(1 for r in rows if r[4])},
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {dst}")
