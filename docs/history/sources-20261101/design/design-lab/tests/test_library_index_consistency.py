# SPDX-License-Identifier: MIT
"""P1-3: library index 4-file consistency guard (cross-file invariants).

E1 STRUCTURAL: verifies the four library/index documents agree with each other
and that every declared shared root sits on the local ``D:`` drive (the red
line: ``E:`` is protected, ``C:`` is not the declared library drive). No
external path is probed, no model is loaded, no network.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DESIGN_LAB = REPO / "design-lab"
SCRIPT = DESIGN_LAB / "scripts" / "verify_library_index_consistency.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("verify_library_index_consistency", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONSISTENT_PATHS = {
    "shared_inputs": {
        "model-library": "D:/All projects/Model library",
        "design-assets": "D:/All projects/Design assets",
        "os-toolchain": "D:/All projects/OS External Configuration",
        "design-toolchain": "D:/All projects/Design External Configuration",
    }
}
CONSISTENT_ASSETS = {
    "shared_roots": {
        "model-library": "D:\\All projects\\Model library",
        "design-assets": "D:\\All projects\\Design assets",
    },
    "assets": [
        {"id": "h3-diffusion-model", "shared_root": "model-library", "relative_path": "a", "kind": "model-weight", "owned_by": "DESIGN-LAB"},
        {"id": "h3-text-encoder", "shared_root": "model-library", "relative_path": "b", "kind": "model-weight", "owned_by": "DESIGN-LAB"},
        {"id": "h3-video-vae", "shared_root": "model-library", "relative_path": "c", "kind": "model-weight", "owned_by": "DESIGN-LAB"},
        {"id": "h3-audio-vae", "shared_root": "model-library", "relative_path": "d", "kind": "model-weight", "owned_by": "DESIGN-LAB"},
        {"id": "ai-product-os-frontend-quarantine", "shared_root": "design-assets", "relative_path": "quarantine/", "kind": "quarantine", "owned_by": "DESIGN-LAB"},
    ],
}
CONSISTENT_RADAR = {
    "entries": [
        {"model_id": "minimax-h3-diffusion", "asset_index_ids": ["h3-diffusion-model"]},
        {"model_id": "whisper-large-v3-turbo", "asset_index_ids": []},
        {"model_id": "omniparser", "asset_index_ids": []},
    ]
}
CONSISTENT_TASKS = {
    "resources": {
        "model-library": {"kind": "model", "path": "declared in .project/paths.json shared_inputs.model-library", "licence": "UNKNOWN"},
        "design-assets": {"kind": "external", "path": "declared in .project/paths.json shared_inputs.design-assets", "note": "DECLARED_NOT_PROBED"},
        "uv": {"kind": "tool", "name": "uv", "version": ">=0.4", "source": "PATH search scope"},
        "git": {"kind": "tool", "name": "git", "version": ">=2.40", "source": "PATH search scope"},
        "python-project-venv": {"kind": "tool", "name": "python", "version": ">=3.11", "source": "project .venv"},
    },
    "tasks": {
        "DL::X": ["python-project-venv", "git", "uv"],
        "DL::Y": ["design-assets"],
    },
}


class GuardInvariants(unittest.TestCase):
    def setUp(self):
        self.mod = _load_script()

    def test_released_files_are_consistent(self):
        # The committed 4-file set must pass.
        errors = self.mod.check(CONSISTENT_PATHS, CONSISTENT_ASSETS, CONSISTENT_RADAR, CONSISTENT_TASKS)
        self.assertEqual(errors, [])

    def test_released_files_actually_pass(self):
        # Not just a synthetic set: the checked-in files themselves must be consistent.
        paths = json.loads((REPO / ".project" / "paths.json").read_text(encoding="utf-8"))
        assets = json.loads((REPO / "design-lab/config/external-assets-index.json").read_text(encoding="utf-8"))
        radar = json.loads((REPO / "design-lab/readiness/model-radar.json").read_text(encoding="utf-8"))
        self.assertEqual(self.mod.check(paths, assets, radar), [])

    def test_non_drive_root_is_rejected(self):
        bad = json.loads(json.dumps(CONSISTENT_PATHS))
        bad["shared_inputs"]["model-library"] = "C:/libs/model"
        errors = self.mod.check(bad, CONSISTENT_ASSETS, CONSISTENT_RADAR)
        self.assertTrue(any("shared_inputs.model-library" in e for e in errors))

    def test_root_disagreement_between_paths_and_assets_is_detected(self):
        # external-assets shared_roots value must agree with paths.json (normalized).
        paths = json.loads(json.dumps(CONSISTENT_PATHS))
        assets = json.loads(json.dumps(CONSISTENT_ASSETS))
        assets["shared_roots"]["design-assets"] = "D:/All projects/OTHER"
        errors = self.mod.check(paths, assets, CONSISTENT_RADAR)
        self.assertTrue(any("disagrees with" in e for e in errors))

    def test_slash_backslash_roots_compare_equal(self):
        # D:\a\b and D:/a/b are the same root; must NOT be flagged.
        self.assertEqual(self.mod.check(CONSISTENT_PATHS, CONSISTENT_ASSETS, CONSISTENT_RADAR), [])

    def test_dangling_radar_asset_index_id_is_detected(self):
        radar = json.loads(json.dumps(CONSISTENT_RADAR))
        radar["entries"][0]["asset_index_ids"] = ["no-such-asset"]
        errors = self.mod.check(CONSISTENT_PATHS, CONSISTENT_ASSETS, radar)
        self.assertTrue(any("no-such-asset" in e for e in errors))

    def test_empty_asset_index_ids_is_legal(self):
        errors = self.mod.check(CONSISTENT_PATHS, CONSISTENT_ASSETS, CONSISTENT_RADAR)
        self.assertEqual(errors, [])

    def test_undeclared_task_resource_reference_is_detected(self):
        tasks = json.loads(json.dumps(CONSISTENT_TASKS))
        tasks["resources"]["design-assets"]["path"] = "declared in .project/paths.json shared_inputs.ghost-root"
        errors = self.mod.check(CONSISTENT_PATHS, CONSISTENT_ASSETS, CONSISTENT_RADAR, tasks)
        self.assertTrue(any("ghost-root" in e for e in errors))

    def test_tasks_reference_undeclared_resource_is_detected(self):
        tasks = json.loads(json.dumps(CONSISTENT_TASKS))
        tasks["tasks"]["DL::X"] = ["ghost-resource"]
        errors = self.mod.check(CONSISTENT_PATHS, CONSISTENT_ASSETS, CONSISTENT_RADAR, tasks)
        self.assertTrue(any("ghost-resource" in e for e in errors))

    def test_missing_tasks_file_is_legal(self):
        errors = self.mod.check(CONSISTENT_PATHS, CONSISTENT_ASSETS, CONSISTENT_RADAR, None)
        self.assertEqual(errors, [])

    def test_asset_unknown_shared_root_is_detected(self):
        assets = json.loads(json.dumps(CONSISTENT_ASSETS))
        assets["assets"][0]["shared_root"] = "nowhere"
        errors = self.mod.check(CONSISTENT_PATHS, assets, CONSISTENT_RADAR)
        self.assertTrue(any("nowhere" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
