# SPDX-License-Identifier: MIT
"""Internal consistency of the external-assets index, without touching the root.

`scripts/inventory_model_library.py` walks a shared root that exists on one machine.
Nothing here may assert that a path exists or that a size matches, because CI has no
`D:/All projects/Model library` -- a test that reached outside the repo would either
fail on every runner or, worse, be written to pass by skipping everything and then
prove nothing. What is checked is the record's own structure: identity, uniqueness,
declaration, and the two properties that make the inventory trustworthy rather than a
list someone typed -- every discovered entry says who owns it and whether a licence was
adjudicated, and nothing is registered from the scratch area.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "design-lab" / "config" / "external-assets-index.json"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RESIDUE_PREFIX = "runtimes-tmp/"


class IndexShape(unittest.TestCase):
    def setUp(self) -> None:
        self.index = json.loads(INDEX.read_text(encoding="utf-8"))
        self.assets = self.index["assets"]

    def test_positive_control_the_index_is_not_empty(self) -> None:
        # The pre-inventory index had 5 assets while the root holds 24 model files; an
        # accidental rewrite that drops entries must fail here, not silently shrink it.
        self.assertGreater(len(self.assets), 5,
                           f"only {len(self.assets)} assets listed -- the inventory was "
                           "truncated or the walk was run without the shared root")

    def test_every_shared_root_reference_is_declared(self) -> None:
        declared = set(self.index["shared_roots"])
        for asset in self.assets:
            self.assertIn(asset["shared_root"], declared,
                          f"{asset['id']} points at an undeclared root")

    def test_ids_are_well_formed_and_unique(self) -> None:
        ids = [a["id"] for a in self.assets]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate ids: {sorted(set(i for i in ids if ids.count(i) > 1))}")
        for asset in self.assets:
            self.assertRegex(asset["id"], ID_PATTERN, asset["id"])

    def test_paths_are_relative_and_cannot_escape_the_root(self) -> None:
        for asset in self.assets:
            relative = asset["relative_path"]
            self.assertNotIn(":", relative, f"{asset['id']} carries a drive letter")
            self.assertFalse(relative.startswith("/"), f"{asset['id']} is absolute")
            self.assertNotIn("..", Path(relative).parts, f"{asset['id']} escapes the root")
            self.assertFalse((ROOT / relative).exists(),
                             f"{asset['id']} resolves inside the repository, so it is not "
                             "an external asset")

    def test_nothing_is_registered_from_the_scratch_area(self) -> None:
        residue = [a["id"] for a in self.assets
                   if a["relative_path"].startswith(RESIDUE_PREFIX)]
        self.assertEqual(residue, [],
                         "runtimes-tmp is a download scratch area, not an owned asset")


class OwnershipAndRights(unittest.TestCase):
    def setUp(self) -> None:
        self.assets = json.loads(INDEX.read_text(encoding="utf-8"))["assets"]

    def test_ownership_is_never_inferred_from_a_directory(self) -> None:
        """A file sitting in ComfyUI/ is not DESIGN-LAB's; only the pre-existing,
        hand-curated entries may claim ownership."""
        for asset in self.assets:
            if "discovered by scripts/inventory_model_library.py" not in asset.get("note", ""):
                continue
            self.assertEqual(asset["owned_by"], "unattributed",
                             f"{asset['id']} claims ownership from a walk alone")
            self.assertEqual(asset["status"], "review-required",
                             f"{asset['id']} was discovered, not adjudicated")

    def test_every_discovered_asset_states_the_licence_state(self) -> None:
        for asset in self.assets:
            if "discovered by scripts/inventory_model_library.py" in asset.get("note", ""):
                self.assertIn("licence not adjudicated", asset["note"],
                              f"{asset['id']} has no recorded rights position")


if __name__ == "__main__":
    unittest.main()
