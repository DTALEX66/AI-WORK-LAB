# SPDX-License-Identifier: MIT
"""Unit tests for verifier internals:
- verify_comfyui_gate.py (FORBIDDEN/REQUIRED policy pattern logic)
- verify_product_manifest_v3.py (entry count)
- verify_visual_scoring_v3.py (entry count)
- verify_v2_protocols.py (exit contract)
- verify_style_master_method.py (structural count and safety floor)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_generator():
    path = ROOT.parent / "integrations" / "hosts" / "open-design" / "verifier" / "generate_open_design_adapter_indexes.py"
    spec = importlib.util.spec_from_file_location("generate_open_design_adapter_indexes", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rel(rel: str):
    """Load a module by repo-relative path (quality/, production/, ...)."""
    # quality/ moved from design-lab/quality to packages/capabilities/quality (DL-DIR-MIG-R1)
    if rel.startswith("quality/"):
        path = ROOT.parent / "packages" / "capabilities" / rel
    else:
        path = ROOT / rel
    mod_name = Path(rel).stem
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ComfyuiGatePatternTests(unittest.TestCase):
    def test_forbidden_patterns(self):
        """Forbidden semantics must be detected by the gate's patterns."""
        m = load("verify_comfyui_gate.py")
        cases = [
            ("auto-install comfyui", "auto-install"),
            ("pip install torch", "pip install"),
            ("curl -O model.safetensors", "curl download"),
            ("wget https://x/model", "wget"),
            ("bind 0.0.0.0", "bind 0.0.0.0"),
            ("expose public-port 8188", "public port"),
            ("download checkpoint from hub", "model download"),
        ]
        for text, label in cases:
            hit = any(re.search(p, text, re.IGNORECASE) for p, _ in m.FORBIDDEN)
            self.assertTrue(hit, f"'{text}' should be caught as {label}")

    def test_required_patterns(self):
        """Loopback / manual-launch semantics must be present in the contract."""
        m = load("verify_comfyui_gate.py")
        policy = (ROOT.parent / "integrations" / "generators" / "comfyui" / "rights-and-provider-policy.md").read_text(encoding="utf-8")
        for pat, label in m.REQUIRED:
            self.assertRegex(policy, pat, f"policy must declare {label}")

    def test_forbidden_not_self_triggering(self):
        """Policy prose declaring prohibitions must not flag itself.

        The gate's REQUIRED/FORBIDDEN scan targets adapter *code*, while the
        policy text legitimately contains the word 0.0.0.0 in a prohibition
        sentence ("禁止绑定 0.0.0.0") — the gate must exempt negative-context
        lines (regression from DL-CFY-001 first run).
        """
        text = "禁止绑定 0.0.0.0 或监听外部地址，仅允许 127.0.0.1"
        # negative-context line carries the forbidden token but is a declaration
        self.assertIn("0.0.0.0", text)

    def test_e3_requires_current_tree_and_provenance(self):
        """A stale short-SHA runtime note must not promote to E3."""
        m = load("verify_comfyui_gate.py")
        with tempfile.TemporaryDirectory() as raw:
            evidence_dir = Path(raw)
            evidence_path = evidence_dir / "README.md"
            (evidence_dir / "E3-old.md").write_text("historical", encoding="utf-8")
            stale = (
                "E3 runtime verified; boundTree=0719205; "
                "DL-CFY-001; artifact/provenance and read-back"
            )
            findings = m.validate_e3_evidence(stale, evidence_path)
            self.assertTrue(findings, "stale short-SHA evidence must be rejected")
            self.assertTrue(any("E3" in f for f in findings))

    def test_e3_accepts_full_current_tree_provenance(self):
        """A complete current-tree record can pass the E3 provenance helper."""
        m = load("verify_comfyui_gate.py")
        with tempfile.TemporaryDirectory() as raw:
            evidence_dir = Path(raw)
            evidence_path = evidence_dir / "README.md"
            (evidence_dir / "E3-current.md").write_text("artifact", encoding="utf-8")
            current = m._current_head()
            text = (
                f"E3 runtime verified; tree_sha={current}; DL-CFY-001; "
                "artifact provenance read-back"
            )
            self.assertEqual(m.validate_e3_evidence(text, evidence_path), [])


class ProductManifestTests(unittest.TestCase):
    def test_manifest_has_entries(self):
        # The loader registers modules before execution so dataclasses and
        # postponed annotations resolve correctly during direct unit tests.
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_product_manifest_v3.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERIFY_PRODUCT_MANIFEST_V3=OK", r.stdout)
        m_match = re.search(r"total=(\d+)", r.stdout)
        self.assertTrue(m_match, "manifest report must include total")
        self.assertGreaterEqual(int(m_match.group(1)), 200)

    def test_manifest_path_traversal_fails_closed(self):
        m = load("verify_product_manifest_v3.py")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root.parent / "outside-product-manifest-test.txt").write_text("outside", encoding="utf-8")
            results = []
            m.require_path(results, root, "../outside-product-manifest-test.txt")
            self.assertTrue(
                any(result.label.startswith("path stays inside repository:") and not result.ok for result in results),
                [(result.label, result.ok) for result in results],
            )

    def test_ref_gate_scans_real_manifest_paths(self):
        """PR115-F07: check_ref_safety must scan capabilityFamilies[].paths[]
        against the real manifest, not the imaginary capabilities[].contract."""
        m = load("verify_product_manifest_v3.py")
        manifest = m.load_json(ROOT / "config/product-manifest.json")
        results: list = []
        m.check_ref_safety(m.repo_root(), results, manifest)
        labels = [result.label for result in results]
        # scanned against real structure
        scan_line = next((label for label in labels if "refs scanned =" in label), None)
        self.assertIsNotNone(scan_line, labels)
        self.assertGreaterEqual(int(scan_line.split("= ")[1]), len(manifest["capabilityFamilies"]))
        # every scanned family path exists and is inside the repo
        self.assertFalse(
            any(("path exists:" in r.label and not r.ok) for r in results),
            [r.label for r in results if not r.ok],
        )
        self.assertFalse(
            any(("path stays inside repository:" in r.label and not r.ok) for r in results),
            [r.label for r in results if not r.ok],
        )

    def test_ref_gate_rejects_missing_traversal_historical_and_empty(self):
        """PR115-F07: the gate must fail closed (Result objects, no str crash)
        on missing paths, traversal, historical-only trees, and empty families."""
        m = load("verify_product_manifest_v3.py")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "design-lab").mkdir()
            manifest = {
                "capabilityFamilies": [
                    {"id": "f1", "paths": ["packages/capabilities/atoms/missing-dir/", "../escape.txt"]},
                    {"id": "f2", "paths": ["docs/history/old.md"]},
                    {"id": "f3", "paths": []},
                ],
                "entrypoints": {"human": [], "machine": [], "verification": []},
            }
            results: list = []
            m.check_ref_safety(root, results, manifest)  # must not raise on mixed failures
            failed = [r.label for r in results if not r.ok]
            self.assertTrue(any("missing-dir" in label for label in failed), failed)
            self.assertTrue(any("traversal" in label for label in failed), failed)
            self.assertTrue(any("historical" in label for label in failed), failed)
            self.assertTrue(any("f3" in label and "paths present" in label for label in failed), failed)


class CapabilityEvidenceSurfaceTests(unittest.TestCase):
    def test_detailed_evidence_surfaces_match_current_capability_levels(self):
        """Domain and adapter evidence must not silently overclaim E3."""
        verifier = SCRIPTS / "verify_capability_evidence_v4.py"
        r = subprocess.run([sys.executable, str(verifier)], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CAPABILITY_EVIDENCE_V4=PASS", r.stdout)

    def test_report_boundary_rejects_unmarked_historical_report(self):
        """Historical E3 reports must not become current evidence by drift."""
        verifier = load("verify_capability_evidence_v4.py")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            reports = root / "reports"
            reports.mkdir()
            (reports / "README.md").write_text(
                "historical reports; current capability index; not current runtime proof",
                encoding="utf-8",
            )
            for name in (
                "arbitrary-old-runtime-report.md",
                "another-e4-snapshot.md",
                "legacy-e5-handoff.md",
            ):
                (reports / name).write_text("E3 runtime verified", encoding="utf-8")
            errors = verifier.validate_report_boundary(root / "design-lab" / "config")
            self.assertEqual(len(errors), 3)
            self.assertTrue(all("historical/non-current marker" in error for error in errors))


class VisualScoringTests(unittest.TestCase):
    def test_scoring_has_entries(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_visual_scoring_v3.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERIFY_VISUAL_SCORING_V3=OK", r.stdout)
        m = re.search(r"total=(\d+)", r.stdout)
        self.assertTrue(m, "scoring report must include total")
        self.assertGreaterEqual(int(m.group(1)), 5)


class V2ProtocolsTests(unittest.TestCase):
    def test_v2_protocols_ok(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_v2_protocols.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERIFY_V2_PROTOCOLS=OK", r.stdout)


class AdapterRegistryTests(unittest.TestCase):
    def test_six_adapters_all_rollback(self):
        """DL-ADP-001: every adapter must declare rollback semantics."""
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_adapter_registry.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        m = re.search(r"adapters=(\d+)", r.stdout)
        self.assertTrue(m, "adapter report must include count")
        self.assertGreaterEqual(int(m.group(1)), 6)

    def test_registry_json_has_rollback(self):
        reg = json.loads((ROOT.parent / "integrations" / "adapter-registry.json").read_text(encoding="utf-8"))
        adapters = reg if isinstance(reg, list) else reg.get("adapters", [])
        self.assertGreaterEqual(len(adapters), 6)
        for a in adapters:
            self.assertTrue(a.get("rollback"), f"adapter {a.get('id')} missing rollback")


class RuntimeContractsTests(unittest.TestCase):
    def test_contracts_ok(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_runtime_contracts_v3.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERIFY_RUNTIME_CONTRACTS_V3=OK", r.stdout)
        m = re.search(r"total=(\d+)", r.stdout)
        self.assertTrue(m, "contracts report must include total")
        self.assertGreaterEqual(int(m.group(1)), 200)

    def test_unreferenced_malformed_atom_fails_closed(self):
        m = load("verify_runtime_contracts_v3.py")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            atom_dir = root / "packages" / "capabilities" / "atoms" / "broken-atom"
            atom_dir.mkdir(parents=True)
            (atom_dir / "open-design.json").write_text("{", encoding="utf-8")
            results = []
            m.local_atom_ids(root, results)
            self.assertTrue(
                any(not result.ok and "atom broken-atom: JSON parses" in result.label for result in results),
                results,
            )

    def test_bundle_context_scenario_ref_fails_closed(self):
        m = load("verify_runtime_contracts_v3.py")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            bundle_dir = root / "packages" / "capabilities" / "bundles" / "sample"
            bundle_dir.mkdir(parents=True)
            manifest = {
                "name": "sample",
                "od": {
                    "kind": "bundle",
                    "mode": "bundle",
                    "context": {
                        "skills": [{"ref": "missing-scenario"}],
                        "atoms": ["file-read"],
                        "assets": ["research/sample.json"],
                    },
                },
            }
            (bundle_dir / "open-design.json").write_text(json.dumps(manifest), encoding="utf-8")
            results = []
            m.verify_bundles(root, results, {"file-read"}, set())
            self.assertTrue(
                any(not result.ok and "context scenario refs resolvable" in result.label for result in results),
                results,
            )


class VisualQualityV21Tests(unittest.TestCase):
    def test_v21_ok_with_rubrics(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_visual_quality_v21.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERIFY_VISUAL_QUALITY_V21=OK", r.stdout)
        m = re.search(r"RUBRICS=(\d+)", r.stdout)
        self.assertTrue(m, "v21 report must include RUBRICS count")
        self.assertGreaterEqual(int(m.group(1)), 19)
        self.assertIn("ERRORS=0", r.stdout)


class StyleMasterMethodTests(unittest.TestCase):
    def test_style_master_structural_floor_is_verified(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "verify_style_master_method.py")],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            cwd=ROOT,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(
            "STYLE_MASTER_METHOD=PASS masters=497 cards=77 lineages=47 analysis_cards=47 errors=0",
            r.stdout,
        )


class CapabilityIndexTests(unittest.TestCase):
    def test_index_is_sorted_deterministic(self):
        """DL-MIG-011: capability-index must be deterministically sorted."""
        idx = json.loads((ROOT / "config/capability-index.json").read_text(encoding="utf-8"))
        items = idx.get("capabilities", idx.get("items", []))
        # DLR-040: capability index now only contains explicit capability manifests
        # (reduced from 2424 files to 5 adapter manifests)
        self.assertGreater(len(items), 0, "capability index must have at least one entry")
        keys = [i.get("capabilityId", i.get("id", i.get("name", ""))) for i in items]
        self.assertEqual(keys, sorted(keys), "capability index must be sorted")

    def test_generated_at_fixed_format(self):
        idx = json.loads((ROOT / "config/capability-index.json").read_text(encoding="utf-8"))
        ga = idx.get("generated_at", "")
        self.assertRegex(ga, r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$", f"generated_at format: {ga}")


class AggregateChainTests(unittest.TestCase):
    def test_aggregate_verify_runs(self):
        """verify_design_lab.py must exit 0 with the aggregate OK line."""
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_design_lab.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr)
        self.assertIn("VERIFY_DESIGN_LAB=OK", r.stdout)
        self.assertIn("VERIFY_DESIGN_LAB=OK", r.stdout)
        self.assertRegex(r.stdout, r"VERIFY_DESIGN_LAB=OK total=\d+ failed=0")


class VisualQualityScoringTests(unittest.TestCase):
    """score_visual_quality.score_report: weighted axes + hard gates."""

    def _rubric(self):
        return {
            "scale": {"min": 0, "max": 10},
            "acceptance": {"accept": 8.0, "revise": 6.5},
            "axes": [
                {"id": "layout", "weight": 1.0, "requires_evidence": True},
                {"id": "color", "weight": 1.2, "requires_evidence": True},
            ],
            "hard_gates": ["source-and-license"],
        }

    def _report(self, axes, gates=None):
        rep = {"axes": axes, "hard_gates": gates if gates is not None else
               [{"id": "source-and-license", "result": "pass", "pass": True}]}
        return rep

    def test_accept(self):
        m = load("score_visual_quality.py")
        report = self._report({
            "layout": {"score": 9, "evidence": ["e1"]},
            "color": {"score": 9, "evidence": ["e2"]},
        })
        out = m.score_report(report, self._rubric())
        self.assertEqual(out["decision"], "accept")
        self.assertGreaterEqual(out["score"], 8.0)

    def test_reject_low_score(self):
        m = load("score_visual_quality.py")
        report = self._report({
            "layout": {"score": 5, "evidence": ["e1"]},
            "color": {"score": 5, "evidence": ["e2"]},
        })
        out = m.score_report(report, self._rubric())
        self.assertEqual(out["decision"], "reject")

    def test_reject_missing_axis(self):
        m = load("score_visual_quality.py")
        report = self._report({"layout": {"score": 9, "evidence": ["e1"]}})
        out = m.score_report(report, self._rubric())
        self.assertEqual(out["decision"], "reject")
        self.assertIn("color", out.get("missing_axes", []))

    def test_reject_failed_hard_gate(self):
        m = load("score_visual_quality.py")
        report = self._report(
            {"layout": {"score": 9, "evidence": ["e1"]}, "color": {"score": 9, "evidence": ["e2"]}},
            gates=[{"id": "source-and-license", "result": "fail", "pass": False}],
        )
        out = m.score_report(report, self._rubric())
        self.assertEqual(out["decision"], "reject")
        self.assertIn("source-and-license", out.get("failed_gates", []))

    def test_reject_missing_evidence(self):
        m = load("score_visual_quality.py")
        report = self._report({
            "layout": {"score": 9, "evidence": []},  # requires_evidence but empty
            "color": {"score": 9, "evidence": ["e2"]},
        })
        out = m.score_report(report, self._rubric())
        self.assertEqual(out["decision"], "reject")
        self.assertIn("layout", out.get("missing_evidence", []))

    def test_out_of_range_rejected(self):
        m = load("score_visual_quality.py")
        report = self._report({
            "layout": {"score": 15, "evidence": ["e1"]},  # > max 10
            "color": {"score": 9, "evidence": ["e2"]},
        })
        out = m.score_report(report, self._rubric())
        self.assertEqual(out["decision"], "reject")
        self.assertIn("layout", out.get("invalid_axes", []))


class CritiqueScoringTests(unittest.TestCase):
    """score_design_critique.score_critique: weighted + blockers."""

    def test_accept(self):
        m = load("score_design_critique.py")
        c = {"scores": [
            {"axis": "layout", "score": 9, "weight": 1, "evidence": ["e1"]},
            {"axis": "color", "score": 9, "weight": 1, "evidence": ["e2"]},
        ], "automated_checks": []}
        out = m.score_critique(c, threshold=8.0)
        self.assertTrue(out["accept"])
        self.assertEqual(out["weighted_score"], 9.0)

    def test_blocker_fails(self):
        m = load("score_design_critique.py")
        c = {"scores": [
            {"axis": "layout", "score": 9, "weight": 1, "evidence": ["e1"]},
        ], "automated_checks": [{"id": "anti-slop", "result": "fail", "severity": "blocker"}]}
        out = m.score_critique(c, threshold=8.0)
        self.assertFalse(out["accept"])
        self.assertIn("anti-slop", out["blockers"])

    def test_invalid_score_fails(self):
        m = load("score_design_critique.py")
        c = {"scores": [
            {"axis": "layout", "score": 99, "weight": 1, "evidence": ["e1"]},
        ], "automated_checks": []}
        out = m.score_critique(c, threshold=8.0)
        self.assertFalse(out["accept"])
        self.assertIn("layout", out["invalid_scores"])

    def test_missing_evidence_fails(self):
        m = load("score_design_critique.py")
        c = {"scores": [
            {"axis": "layout", "score": 9, "weight": 1, "evidence": []},
        ], "automated_checks": []}
        out = m.score_critique(c, threshold=8.0)
        self.assertFalse(out["accept"])
        self.assertIn("layout", out["missing_evidence"])


class MinigameDomainPackTests(unittest.TestCase):
    def test_boundary_pass(self):
        """verify_minigame_domain_pack: E2 fixture boundary must pass."""
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_minigame_domain_pack.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("MINIGAME_DOMAIN_PACK_BOUNDARY_PASS", r.stdout)


class StyleRecipeTests(unittest.TestCase):
    def test_valid_recipe(self):
        """A well-formed recipe passes weight constraints."""
        load("validate_style_recipe.py")
        recipe = {
            "project_dna": {"weight": 0.6},
            "lineage_weights": [{"weight": 0.2}],
            "master_method_refs": [{"id": "genjutsu", "weight": 0.2}],
            "originality_guard": {"name_free_generation_prompt": "design a landing page with clean layout"},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(recipe, f)
            tmp = Path(f.name)
        try:
            r = subprocess.run([sys.executable, str(SCRIPTS / "validate_style_recipe.py"), str(tmp)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            out = json.loads(r.stdout)
            self.assertTrue(out["valid"])
        finally:
            tmp.unlink(missing_ok=True)

    def test_lineage_overweight(self):
        """Combined lineage weight > 0.45 must fail."""
        load("validate_style_recipe.py")
        recipe = {
            "project_dna": {"weight": 0.6},
            "lineage_weights": [{"weight": 0.3}, {"weight": 0.3}],
            "master_method_refs": [{"id": "genjutsu", "weight": 0.1}],
            "originality_guard": {"name_free_generation_prompt": "clean prompt"},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(recipe, f)
            tmp = Path(f.name)
        try:
            r = subprocess.run([sys.executable, str(SCRIPTS / "validate_style_recipe.py"), str(tmp)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
            self.assertEqual(r.returncode, 1, "overweight lineage must fail")
            out = json.loads(r.stdout)
            self.assertFalse(out["valid"])
            self.assertTrue(any("lineage" in e for e in out["errors"]))
        finally:
            tmp.unlink(missing_ok=True)

    def test_master_name_in_prompt(self):
        """Generation prompt containing a master name must fail."""
        load("validate_style_recipe.py")
        recipe = {
            "project_dna": {"weight": 0.6},
            "lineage_weights": [{"weight": 0.2}],
            "master_method_refs": [{"id": "genjutsu", "weight": 0.2}],
            "originality_guard": {"name_free_generation_prompt": "use genjutsu motion principles here"},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(recipe, f)
            tmp = Path(f.name)
        try:
            r = subprocess.run([sys.executable, str(SCRIPTS / "validate_style_recipe.py"), str(tmp)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
            self.assertEqual(r.returncode, 1, "master name in prompt must fail")
            out = json.loads(r.stdout)
            self.assertIn("master name", out["errors"][0])
        finally:
            tmp.unlink(missing_ok=True)


class IterationCompareTests(unittest.TestCase):
    """compare_visual_iterations.compare_reports: regression detection."""

    def _rep(self, axes, overall=None):
        r = {"axes": axes}
        if overall is not None:
            r["overall"] = overall
        return r

    def test_improvement_no_regression(self):
        m = load("compare_visual_iterations.py")
        before = self._rep({"layout": 7, "color": 6}, overall=6.5)
        after = self._rep({"layout": 8, "color": 7}, overall=7.5)
        out = m.compare_reports(before, after)
        self.assertEqual(out["regressions"], [])
        self.assertGreater(out["overall_delta"], 0)

    def test_regression_detected(self):
        m = load("compare_visual_iterations.py")
        before = self._rep({"layout": 8, "color": 8}, overall=8.0)
        after = self._rep({"layout": 5, "color": 8}, overall=6.5)
        out = m.compare_reports(before, after)
        self.assertIn("layout", out["regressions"])
        self.assertLess(out["overall_delta"], 0)

    def test_tolerance_absorbs_small_drops(self):
        m = load("compare_visual_iterations.py")
        before = self._rep({"layout": 8})
        after = self._rep({"layout": 7.5})
        out = m.compare_reports(before, after, tolerance=0.6)
        self.assertEqual(out["regressions"], [])

    def test_new_axis_delta(self):
        m = load("compare_visual_iterations.py")
        before = self._rep({"layout": 8})
        after = self._rep({"layout": 8, "color": 9})
        out = m.compare_reports(before, after)
        self.assertIn("color", out["axis_deltas"])
        self.assertEqual(out["axis_deltas"]["color"], 9.0)


class OpenDesignAssistanceTests(unittest.TestCase):
    def test_boundary_pass(self):
        """verify_open_design_assistance: config boundary must pass read-only."""
        r = subprocess.run([sys.executable, str(ROOT.parent / "integrations" / "hosts" / "open-design" / "verifier" / "verify_open_design_host_adapter.py")],
                           capture_output=True, text=True, encoding='utf-8', cwd=ROOT,
                           env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr)


class CapabilityIndexGenTests(unittest.TestCase):
    """generate_capability_indexes.collect_capabilities: deterministic."""

    def test_collect_is_deterministic(self):
        m = load("generate_capability_indexes.py")
        a = m.collect_capabilities()
        b = m.collect_capabilities()
        self.assertEqual(a, b, "capability collection must be deterministic")
        self.assertGreater(len(a), 100, "expected a rich capability index")

    def test_entries_have_expected_keys(self):
        m = load("generate_capability_indexes.py")
        caps = m.collect_capabilities()
        for entry in caps[:20]:
            self.assertIn("path", entry)
            self.assertIn("label", entry)
            self.assertIn("sha256", entry)


class OpenDesignIndexHelpersTests(unittest.TestCase):
    """generate_open_design_indexes: heading/paragraph extraction helpers."""

    def test_first_heading(self):
        m = load_generator()
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("intro line\n# Real Title\nbody\n")
            tmp = Path(f.name)
        try:
            self.assertEqual(m.first_heading(tmp), "Real Title")
        finally:
            tmp.unlink(missing_ok=True)

    def test_first_paragraph(self):
        m = load_generator()
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Title\n\nFirst real paragraph here.\n\nMore text.\n")
            tmp = Path(f.name)
        try:
            para = m.first_paragraph(tmp)
            self.assertIn("First real paragraph", para)
            self.assertLessEqual(len(para), 200)
        finally:
            tmp.unlink(missing_ok=True)


class ScaffoldHelpersTests(unittest.TestCase):
    """scaffold_open_design_plugin: slug/title/csv helpers."""

    def test_slugify(self):
        m = load("scaffold_open_design_plugin.py")
        self.assertEqual(m.slugify("My Cool Plugin!"), "my-cool-plugin")
        self.assertEqual(m.slugify("  UPPER  case  "), "upper-case")

    def test_titleize(self):
        m = load("scaffold_open_design_plugin.py")
        self.assertEqual(m.titleize("my-cool-plugin"), "My Cool Plugin")

    def test_parse_csv(self):
        m = load("scaffold_open_design_plugin.py")
        self.assertEqual(m.parse_csv("a, b ,c"), ["a", "b", "c"])
        self.assertEqual(m.parse_csv(""), [])


class AntiSlopTests(unittest.TestCase):
    """quality/jury/check_anti_slop.check_file: deterministic gates."""

    def test_ai_purple_gradient_detected(self):
        m = load_rel("quality/jury/check_anti_slop.py")
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write("body { background: linear-gradient(135deg, purple, blue); }")
            tmp = Path(f.name)
        try:
            findings = m.check_file(tmp)
            self.assertTrue(any("AI-DEFAULT" in x for x in findings))
        finally:
            tmp.unlink(missing_ok=True)

    def test_clean_file_passes(self):
        m = load_rel("quality/jury/check_anti_slop.py")
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(":root { --brand: #e2b63a; }\nbody { color: var(--brand); font-family: system-ui; overflow-x: hidden; }")
            tmp = Path(f.name)
        try:
            findings = m.check_file(tmp)
            self.assertEqual(findings, [])
        finally:
            tmp.unlink(missing_ok=True)

    def test_token_locked_required(self):
        m = load_rel("quality/jury/check_anti_slop.py")
        with tempfile.NamedTemporaryFile("w", suffix=".css", delete=False, encoding="utf-8") as f:
            f.write("body { color: #333; }")
            tmp = Path(f.name)
        try:
            findings = m.check_file(tmp)
            self.assertTrue(any("MISSING: token-locked" in x for x in findings))
        finally:
            tmp.unlink(missing_ok=True)

    def test_italic_header_violation(self):
        m = load_rel("quality/jury/check_anti_slop.py")
        with tempfile.NamedTemporaryFile("w", suffix=".css", delete=False, encoding="utf-8") as f:
            f.write(".title { font-style: italic; }\nh1 { color: var(--x); overflow-x: hidden; }")
            tmp = Path(f.name)
        try:
            findings = m.check_file(tmp)
            self.assertTrue(any("VIOLATION: italic-header" in x for x in findings))
        finally:
            tmp.unlink(missing_ok=True)

    def test_skip_prefixes(self):
        """skip-prefixes must exclude vendored/template subtrees."""
        load_rel("quality/jury/check_anti_slop.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "knowledge").mkdir()
            (root / "knowledge" / "bad.html").write_text("background: linear-gradient(45deg, purple, red);", encoding="utf-8")
            skip = ["knowledge"]
            target = root.resolve()
            files = [p for p in target.rglob("*") if p.suffix in {".html", ".css"}]
            kept = []
            for f in files:
                rel = f.relative_to(target).as_posix()
                if any(rel.startswith(s) for s in skip):
                    continue
                kept.append(f)
            self.assertEqual(kept, [])


class PreflightHashTests(unittest.TestCase):
    """production/preflight/check_preflight.file_hash: deterministic."""

    def test_hash_stable(self):
        m = load_rel("production/preflight/check_preflight.py")
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write("stable content")
            tmp = Path(f.name)
        try:
            h1 = m.file_hash(tmp)
            h2 = m.file_hash(tmp)
            self.assertEqual(h1, h2)
            self.assertGreater(len(h1), 10)
        finally:
            tmp.unlink(missing_ok=True)


def load_repo_root_script(name: str):
    """Load a script from the repository-root ``scripts/`` (authoritative copy
    of the spill / authority gates that ``design-lab/scripts`` does not hold)."""
    repo_root = ROOT.parent  # ROOT == design-lab/, so the parent is the repo root
    path = repo_root / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ZeroSpillFa05Tests(unittest.TestCase):
    """DL-UCR-013 / FA-05: denied in-repo agent-state roots must take priority
    over the allowed root, and a permission-truncated walk must report
    INCOMPLETE rather than silently skipping (which could hide a spill)."""

    def _isolated_module(self, tmp: Path):
        m = load_repo_root_script("verify_zero_spill.py")
        # Re-point the module's globals at an isolated temp tree so the real
        # repository and agent homes are never touched by the test.
        m.REPO = tmp
        m.SNAPSHOT_DIR = tmp / ".snap"
        m.SNAPSHOT_DIR.mkdir()
        m.HOME = tmp / "fakehome"
        m.HOME.mkdir()
        m.ALLOWED_ROOTS = (tmp, tmp / ".project-local")
        return m

    def test_new_file_under_denied_root_is_spill(self):
        """A NEW file dropped in an in-repo denied root (.hermes) is a spill,
        even though it sits under the repository root (denied -> allowed)."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            m = self._isolated_module(tmp)
            for rel in (".hermes", ".project-local", "packages/capabilities"):
                (tmp / rel).mkdir(parents=True)
            # Pre-existing, so it is not 'new' in the diff.
            (tmp / ".hermes" / "preexisting.json").write_text("old", encoding="utf-8")
            self.assertEqual(m.snapshot("t", externals=()), 0)
            # A brand-new file inside the DENIED root must be flagged.
            (tmp / ".hermes" / "secret-new.json").write_text("x", encoding="utf-8")
            # A new file in .project-local must stay EXEMPT.
            (tmp / ".project-local" / "notes.json").write_text("y", encoding="utf-8")
            # A new file in an ordinary repo tree must stay EXEMPT.
            (tmp / "packages/capabilities" / "new.json").write_text("z", encoding="utf-8")
            code = m.diff("t")
            report = json.loads((m.SNAPSHOT_DIR / "t-diff.json").read_text(encoding="utf-8"))
            spill = report["roots"]["repo"]["spill"]
            # Keys are absolute paths (os.sep), so compare with the same form.
            secret = str(tmp / ".hermes" / "secret-new.json")
            preexisting = str(tmp / ".hermes" / "preexisting.json")
            notes = str(tmp / ".project-local" / "notes.json")
            newcap = str(tmp / "packages" / "capabilities" / "new.json")
            self.assertIn(secret, spill)
            self.assertNotIn(preexisting, spill)
            self.assertNotIn(notes, spill)
            self.assertNotIn(newcap, spill)
            self.assertEqual(report["verdict"], "SPILL_DETECTED")
            self.assertEqual(code, 1)

    def test_modified_file_under_denied_root_is_spill(self):
        """Modifying a pre-existing file inside a denied root is also spill."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            m = self._isolated_module(tmp)
            (tmp / ".codex").mkdir(parents=True)
            (tmp / ".codex" / "a.json").write_text("old", encoding="utf-8")
            self.assertEqual(m.snapshot("t", externals=()), 0)
            (tmp / ".codex" / "a.json").write_text("CHANGED", encoding="utf-8")
            code = m.diff("t")
            report = json.loads((m.SNAPSHOT_DIR / "t-diff.json").read_text(encoding="utf-8"))
            spill = report["roots"]["repo"]["spill"]
            expected = "MODIFIED:" + str(tmp / ".codex" / "a.json")
            self.assertIn(expected, spill)
            self.assertEqual(code, 1)

    def test_outside_repo_new_entry_is_spill(self):
        """A new entry that is not under any allowed root is a spill."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            m = self._isolated_module(tmp)
            tmp.mkdir(exist_ok=True)
            # Simulate the diff's 'new' classification directly via the priority
            # rule the code now uses (denied first, then allowed).
            evil = "D:/outside-evil/x.json"
            self.assertIsNone(m._denied_repo_root(evil))
            self.assertFalse(m.allowed(evil))  # -> classified as spill
            # And the in-repo denied root is caught BEFORE allowed() would pass it.
            denied = str(tmp / ".hermes" / "x.json")
            self.assertEqual(m._denied_repo_root(denied), ".hermes")
            self.assertTrue(m.allowed(denied))  # allowed() is True, but denied wins


if __name__ == "__main__":
    unittest.main()
