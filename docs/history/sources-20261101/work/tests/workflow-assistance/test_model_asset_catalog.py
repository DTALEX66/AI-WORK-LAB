"""Contract tests for the model asset catalog (WL3-330 / MR-05)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

import model_asset_catalog as catalog


class ModelAssetCatalogTests(unittest.TestCase):
    def test_empty_library_yields_no_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(catalog.list_assets(Path(tmp)), [])

    def test_missing_library_yields_no_assets(self) -> None:
        self.assertEqual(catalog.list_assets(Path("/nonexistent-model-root-xyz")), [])

    def test_discovered_safetensors_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "models").mkdir()
            asset = root / "models" / "test.safetensors"
            asset.write_bytes(b"\x00" * 128)
            entries = catalog.list_assets(root)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["format"], "safetensors")
            self.assertEqual(entries[0]["size_bytes"], 128)
            self.assertEqual(entries[0]["identity_state"], "DISCOVERED")
            self.assertNotIn("\\", entries[0]["library_relative_path"])

    def test_non_model_files_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("no model", encoding="utf-8")
            (root / "data.txt").write_text("x", encoding="utf-8")
            self.assertEqual(catalog.list_assets(root), [])

    def test_path_containment_rejects_escapes(self) -> None:
        for bad in ("../escape.gguf", "C:/abs.gguf", "\\server\\share.gguf", "~/home.gguf", "/abs.gguf"):
            self.assertFalse(catalog.validate_path_containment(bad), bad)
        for good in ("models/test.gguf", "ComfyUI/vae/test.safetensors", "sub/dir/model.onnx"):
            self.assertTrue(catalog.validate_path_containment(good), good)

    def test_digest_cache_incremental_and_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            root.mkdir()
            cache = Path(tmp) / "cache"
            asset = root / "a.gguf"
            asset.write_bytes(b"content-v1")
            first = catalog.refresh_digests(root, cache)
            digest1 = first["a.gguf"]
            self.assertEqual(len(digest1), 64)
            # Unchanged -> cached (no recompute), same digest
            second = catalog.refresh_digests(root, cache)
            self.assertEqual(second["a.gguf"], digest1)
            # Changed -> recomputed
            asset.write_bytes(b"content-v2")
            third = catalog.refresh_digests(root, cache)
            self.assertNotEqual(third["a.gguf"], digest1)

    def test_snapshot_is_metadata_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "m.gguf").write_bytes(b"x" * 64)
            snap = catalog.snapshot(root)
            self.assertEqual(snap["asset_count"], 1)
            self.assertEqual(snap["assets"][0]["digest_state"], "UNAVAILABLE")
            self.assertEqual(snap["quality"], "metadata-only")
            self.assertEqual(snap["assets"][0]["evidence_state"], "OBSERVED")


if __name__ == "__main__":
    unittest.main()

