# SPDX-License-Identifier: MIT
"""DL-V2 P2-G/H/I: review surface, provider SPI, intake pipeline tests."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class ReviewSurfaceTests(unittest.TestCase):
    def test_generator_emits_all_sections(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_review_surface.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("REVIEW_SURFACE=PASS", r.stdout, r.stdout + r.stderr)


class ProviderSPITests(unittest.TestCase):
    def test_provider_spi_verifier(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_provider_spi.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("PROVIDER_SPI=PASS", r.stdout, r.stdout + r.stderr)


class CollectionPipelineTests(unittest.TestCase):
    def test_collection_pipeline_verifier(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_collection_pipeline.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("COLLECTION_PIPELINE=PASS", r.stdout, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
