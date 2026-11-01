# SPDX-License-Identifier: MIT
"""ODA4-0302: plugin/bundle manifest compatibility gate.

V42-0302: manifest contracts align with the upstream Open Design plugin
contract (marketplace field spectrum captured from the installed
open-design resources/plugins/registry at interface discovery time).
"""
from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OFFICIAL_SCHEMA = "https://open-design.ai/schemas/plugin.v1.json"

# Upstream contract core fields (observed in the bundled official
# marketplace: name/title/version/description/tags/license are 414/414).
UPSTREAM_CORE_FIELDS = {"name", "title", "version", "description", "tags", "license"}

# Upstream taskKind enum (observed in daemon manifest validation) and the
# daemon's built-in atom vocabulary (FIRST_PARTY_ATOMS in the installed
# daemon). V42-0303: bundle context.atoms must reference built-in atoms,
# not locally-installed custom atom plugins.
UPSTREAM_TASK_KINDS = {"new-generation", "code-migration", "figma-migration", "tune-collab"}
BUILTIN_ATOMS = {
    "discovery-question-form", "direction-picker", "todo-write", "file-read",
    "file-write", "file-edit", "research-search", "media-image", "media-video",
    "media-audio", "live-artifact", "connector", "critique-theater",
    "code-import", "design-extract", "figma-extract", "token-map",
    "rewrite-plan", "patch-edit", "build-test", "diff-review", "handoff",
}


class ManifestCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.manifests = (
            list((REPO / "packages" / "capabilities" / "plugins").glob("*/open-design.json"))
            + list((REPO / "packages" / "capabilities" / "bundles").glob("*/open-design.json"))
        )

    def test_all_manifests_valid_json_and_official_schema(self):
        self.assertTrue(len(self.manifests) >= 3, "expected at least 3 bundles/plugins")
        for m in self.manifests:
            d = json.loads(m.read_text(encoding="utf-8"))
            self.assertTrue(d["$schema"].startswith(OFFICIAL_SCHEMA), f"{m} wrong schema")
            self.assertTrue(d.get("license"), f"{m} missing license")
            self.assertTrue(d.get("name"), f"{m} missing name")
            self.assertTrue(d.get("version"), f"{m} missing version")

    def test_upstream_core_fields_present_in_all(self):
        # V42-0302: align with upstream contract core field spectrum.
        for m in self.manifests:
            d = json.loads(m.read_text(encoding="utf-8"))
            for field in UPSTREAM_CORE_FIELDS:
                self.assertTrue(d.get(field), f"{m} missing upstream core field {field!r}")

    def test_od_block_present_with_kind(self):
        for m in self.manifests:
            d = json.loads(m.read_text(encoding="utf-8"))
            od = d.get("od")
            self.assertIsInstance(od, dict, f"{m} missing od block")
            self.assertTrue(od.get("kind"), f"{m} od.kind missing")
            self.assertTrue(od.get("capabilities"), f"{m} od.capabilities missing")

    def test_task_kind_present_for_bundles(self):
        # Bundles declare an upstream-style taskKind; skills declare
        # new-generation. Aligns with upstream taskKind (402/414).
        for m in (REPO / "packages" / "capabilities" / "bundles").glob("*/open-design.json"):
            d = json.loads(m.read_text(encoding="utf-8"))
            self.assertTrue(d.get("od", {}).get("taskKind"), f"{m} od.taskKind missing")

    def test_task_kind_in_upstream_enum(self):
        # V42-0303 (live discovery): daemon manifest validation rejects any
        # taskKind outside the four-value upstream enum.
        for m in (REPO / "packages" / "capabilities" / "bundles").glob("*/open-design.json"):
            d = json.loads(m.read_text(encoding="utf-8"))
            self.assertIn(d["od"]["taskKind"], UPSTREAM_TASK_KINDS, f"{m} invalid taskKind")

    def test_bundle_context_atoms_are_builtin(self):
        # V42-0303 (live discovery): daemon doctor raises atom.unknown errors
        # for any context.atoms id outside the built-in FIRST_PARTY_ATOMS set.
        # Bundles may reference local custom atoms only via context.assets.
        for m in (REPO / "packages" / "capabilities" / "bundles").glob("*/open-design.json"):
            d = json.loads(m.read_text(encoding="utf-8"))
            atoms = d.get("od", {}).get("context", {}).get("atoms", [])
            for atom in atoms:
                self.assertIn(atom, BUILTIN_ATOMS, f"{m} references non-builtin atom {atom!r}")

    def test_three_public_bundles_present(self):
        bundle_names = {m.parent.name for m in (REPO / "packages" / "capabilities" / "bundles").glob("*/open-design.json")}
        self.assertIn("commercial-design-core", bundle_names)
        self.assertIn("visual-quality-core", bundle_names)
        self.assertIn("production-handoff", bundle_names)

    def test_no_fabricated_cli_parsed_from_manifest(self):
        # Manifests must not embed invented CLI arg strings; daemon CLI is
        # verified live in ODA4-0303, not declared here.
        for m in self.manifests:
            text = m.read_text(encoding="utf-8")
            self.assertNotIn("--daemon", text)
            self.assertNotIn("cli_args", text)

    def test_visual_pack_checks_removed(self):
        """verify_visual_packs was removed with the minigame visual-pack mechanism
        (DL-AST-003 / 1382e2c). Path-traversal protection is still covered by
        plugin and design-system manifest tests below.
        """
        script = REPO / "integrations" / "hosts" / "open-design" / "verifier" / "verify_open_design_host_adapter.py"
        spec = importlib.util.spec_from_file_location("verify_open_design_host_adapter_no_visual_packs", script)
        verifier = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = verifier
        spec.loader.exec_module(verifier)
        self.assertFalse(hasattr(verifier, "verify_visual_packs"), "removed function must not be re-introduced")

    def test_plugin_agent_skill_rejects_path_traversal(self):
        script = REPO / "integrations" / "hosts" / "open-design" / "verifier" / "verify_open_design_host_adapter.py"
        spec = importlib.util.spec_from_file_location("verify_open_design_host_adapter_plugin_traversal_test", script)
        verifier = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = verifier
        spec.loader.exec_module(verifier)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plugin = root / "packages" / "capabilities" / "plugins" / "test-plugin"
            plugin.mkdir(parents=True)
            (root / "design-lab" / "config").mkdir(parents=True)
            (root / "design-lab" / "config" / "product-manifest.json").write_text(
                json.dumps({"capabilityFamilies": [{"id": "design-intelligence"}]}), encoding="utf-8"
            )
            (root / "design-lab" / "outside.md").write_text("outside", encoding="utf-8")
            (plugin / "SKILL.md").write_text("skill", encoding="utf-8")
            (plugin / "README.md").write_text("readme", encoding="utf-8")
            manifest = {
                "$schema": OFFICIAL_SCHEMA,
                "specVersion": "1.0.0",
                "name": "test-plugin",
                "version": "1.0.0",
                "entry": "SKILL.md",
                "od": {
                    "kind": "skill",
                    "mode": "compat-plugin",
                    "capabilities": ["prompt:inject"],
                    "categories": ["design"],
                    "suggestedInputs": ["brief"],
                    "productFamilies": ["design-intelligence"],
                    "v3": {
                        "evidence": {"level": "E2", "state": "PASS"},
                        "runtime": {"status": "pending-e3", "requires": ["artifact and provenance read-back"]},
                    },
                },
                "compat": {"agentSkills": [{"path": "../../outside.md"}]},
            }
            (plugin / "open-design.json").write_text(json.dumps(manifest), encoding="utf-8")
            results = []
            verifier.verify_plugin_manifests(root, results)
            self.assertTrue(
                any("compat agent skill path stays inside plugin" in result.label and not result.ok for result in results),
                [(result.label, result.ok) for result in results],
            )

    def test_design_system_manifest_rejects_path_traversal(self):
        script = REPO / "integrations" / "hosts" / "open-design" / "verifier" / "verify_open_design_host_adapter.py"
        spec = importlib.util.spec_from_file_location("verify_open_design_host_adapter_system_traversal_test", script)
        verifier = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = verifier
        spec.loader.exec_module(verifier)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / "design-lab" / "design-systems" / "anomaly-monitor-dark"
            base.mkdir(parents=True)
            (root / "design-lab" / "outside.md").write_text("outside", encoding="utf-8")
            (base / "design-tokens.json").write_text("{}", encoding="utf-8")
            (base / "components.manifest.json").write_text("{}", encoding="utf-8")
            (base / "manifest.json").write_text(json.dumps({"files": ["../../outside.md"]}), encoding="utf-8")
            results = []
            verifier.verify_design_systems(root, results)
            self.assertTrue(
                any("design system file stays inside system" in result.label and not result.ok for result in results),
                [(result.label, result.ok) for result in results],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
