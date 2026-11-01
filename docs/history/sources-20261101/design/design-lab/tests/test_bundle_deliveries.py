# SPDX-License-Identifier: MIT
"""Tests for the project bundle/delivery list (native_assets.Bundles).

Written FIRST, and they immediately earned their keep: the first implementation filtered on
asset_kind='design-bundle', which the asset table's CHECK constraint rejects outright --
'design-bundle' is not a legal asset_kind. The real predicate, read from the source, is
asset_kind='other' AND asset_id LIKE 'bundle-%' (native_bundles.py:73 registers
'bundle-'+<native asset id> with kind 'other'; the 'design-bundle' string there is a
return/statement label).

The fixture inserts rows with SQL instead of driving a real export, because exporting a
bundle needs a real native host. Column lists come from the live schema (PRAGMA table_info),
not from assumptions.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from design_lab.image_assets import ImageAssetError  # noqa: E402
from design_lab.native_assets import Bundles  # noqa: E402
from design_lab.service import ProjectService  # noqa: E402

UNKNOWN_PROJECT = "0" * 32
BUNDLE_ID = "bundle-native-" + "b" * 64


class BundlesListTest(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".project-local" / "task-runtime" / "bundle-list-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=parent)
        root = Path(self._tmp.name)
        (root / "AGENTS.md").write_text("# synthetic bundles-list fixture\n", encoding="utf-8")
        self._env = patch.dict(os.environ, {"PROJECT_LOCAL_ROOT": str(root / ".project-local")})
        self._env.start()
        self.service = ProjectService(str(root))
        self.project = self.service.create_project("bundles fixture")["id"]
        self.db = self.service.paths.database_path(self.service.database)

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def _insert(self, asset_id, kind, *, version_no=1, state="ACTIVE"):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT OR IGNORE INTO asset VALUES (?,?,?,?)",
                         (asset_id, self.project, kind, "2026-01-01T00:00:00Z"))
            conn.execute("INSERT INTO asset_version VALUES (?,?,?,?,?,?)",
                         (f"v-{asset_id}-{version_no}", asset_id, version_no,
                          f"sha256:aa{version_no}", state, "2026-01-01T00:00:00Z"))
            conn.execute("INSERT INTO artifact VALUES (?,?,?,?,?,?)",
                         (f"a-{asset_id}-{version_no}", f"v-{asset_id}-{version_no}", "p",
                          "sha256:bb", 1, "primary"))
            conn.commit()

    def test_empty_project_returns_empty_list_not_404(self):
        self.assertEqual(Bundles(self.service).list(self.project), {"bundles": []})

    def test_unknown_project_fails_closed(self):
        with self.assertRaises(ImageAssetError) as ctx:
            Bundles(self.service).list(UNKNOWN_PROJECT)
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(ctx.exception.code, "PROJECT_NOT_FOUND")

    def test_only_bundle_prefixed_assets_are_returned(self):
        # A raster is what /assets already returns; a plain 'other' asset with no bundle-
        # prefix must ALSO not appear -- that is what proves the prefix filter works and the
        # list is not simply "every asset of kind other".
        self._insert("img-" + "a" * 64, "raster")
        self._insert("native-" + "e" * 64, "other")
        self._insert(BUNDLE_ID, "other")
        out = Bundles(self.service).list(self.project)["bundles"]
        self.assertEqual([b["id"] for b in out], [BUNDLE_ID])
        self.assertEqual(out[0]["kind"], "design-bundle")
        self.assertEqual(out[0]["rights"], "NOT_REVIEWED")
        self.assertEqual(out[0]["verification"], "METADATA_ONLY")
        self.assertTrue(out[0]["sha256"].startswith("sha256:"))
        self.assertNotIn("sha256:sha256:", out[0]["sha256"])

    def test_latest_active_version_wins(self):
        self._insert(BUNDLE_ID, "other", version_no=1, state="SUPERSEDED")
        self._insert(BUNDLE_ID, "other", version_no=2, state="ACTIVE")
        out = Bundles(self.service).list(self.project)["bundles"]
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["version_no"], 2)

    def test_other_project_bundle_is_not_readable(self):
        other = self.service.create_project("other")["id"]
        self._insert(BUNDLE_ID, "other")
        self.assertEqual(Bundles(self.service).list(other), {"bundles": []})


if __name__ == "__main__":
    unittest.main()
