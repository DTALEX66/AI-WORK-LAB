# SPDX-License-Identifier: MIT
"""DL C3: experience corpus tests."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class ExperienceCorpusTests(unittest.TestCase):
    def test_corpus_verifier_passes(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_experience_corpus.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("EXPERIENCE_CORPUS=PASS", r.stdout, r.stdout + r.stderr)

    def test_sample_refs_memory(self):
        import json
        s = json.loads((SCRIPTS.parent / "evals/experience-corpus/sample-hero.json").read_text(encoding="utf-8"))
        self.assertEqual(s["schemaVersion"], "design-lab/experience-record/v1")
        self.assertTrue(s["memory_refs"])


if __name__ == "__main__":
    unittest.main()
