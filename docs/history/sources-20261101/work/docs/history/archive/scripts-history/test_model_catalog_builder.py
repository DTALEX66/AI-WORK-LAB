"""Contract tests for model catalog builder (WL3-330 / MR-02+05 ext).

Verifies the live Ollama catalog maps installed models to logical roles
and never fabricates entries.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

import model_catalog_builder as builder


class ModelCatalogBuilderTests(unittest.TestCase):
    def test_role_map_covers_all_known_models(self) -> None:
        # qwen2.5vl / qwen3 / qwen3-coder / qwen3-embedding must all map
        self.assertIn("qwen3:8b", builder._ROLE_MAP)
        self.assertIn("qwen2.5vl:7b", builder._ROLE_MAP)
        self.assertIn("qwen3-coder:30b-a3b-q4_K_M", builder._ROLE_MAP)
        self.assertIn("qwen3-embedding:0.6b", builder._ROLE_MAP)

    @mock.patch("model_catalog_builder._ollama_tags", return_value={
        "models": [
            {"name": "qwen3:8b", "size": 1000, "details": {"family": "qwen3", "quantization_level": "Q4_K_M"}},
            {"name": "unknown-model:1b", "size": 500, "details": {"family": "x"}},
        ]})
    def test_unknown_models_skipped(self, _tags) -> None:
        catalog = builder.build_catalog()
        self.assertEqual(catalog["model_count"], 1)
        self.assertIn("qwen3:8b", catalog["models"])
        self.assertNotIn("unknown-model:1b", catalog["models"])

    @mock.patch("model_catalog_builder._ollama_tags", return_value={"models": []})
    def test_empty_ollama_yields_empty_catalog(self, _tags) -> None:
        catalog = builder.build_catalog()
        self.assertEqual(catalog["model_count"], 0)
        self.assertEqual(catalog["models"], {})

    @mock.patch("model_catalog_builder._ollama_tags", return_value={
        "models": [{"name": "qwen2.5vl:7b", "size": 100, "details": {"family": "qwen25vl"}}]})
    def test_role_assignment(self, _tags) -> None:
        catalog = builder.build_catalog()
        self.assertEqual(catalog["models"]["qwen2.5vl:7b"]["role"], "local.vision.ocr")
        self.assertEqual(catalog["models"]["qwen2.5vl:7b"]["modality"], ["vision", "text"])
        self.assertEqual(catalog["models"]["qwen2.5vl:7b"]["runtime_candidates"], ["ollama"])
        self.assertTrue(catalog["models"]["qwen2.5vl:7b"]["ui_frozen"])


if __name__ == "__main__":
    unittest.main()
