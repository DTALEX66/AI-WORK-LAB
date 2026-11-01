# SPDX-License-Identifier: MIT
"""DL-TP-R2-015: ProfileResolver Golden-case tests."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
SRC = Path(__file__).resolve().parents[2] / 'src'
sys.path.insert(0, str(SRC))


class ProfileResolverTests(unittest.TestCase):
    def setUp(self):
        from design_lab.runtime.profile_resolver import resolve
        self.resolve = resolve

    def test_unverified_cdr_must_not_select(self):
        r = self.resolve({"format": "cdr", "offline": True, "editable": True})
        self.assertIsNone(r["selected"])

    def test_psd_to_photoshop(self):
        r = self.resolve({"format": "psd", "offline": True, "editable": True})
        self.assertIsNone(r["selected"])

    def test_cloud_offline_rejects_figma(self):
        r = self.resolve({"format": "svg", "offline": True, "editable": True})
        self.assertIsNone(r["selected"])

    def test_h3_missing_evidence_not_permanent_license_denial(self):
        r = self.resolve({"format": "mp4", "offline": True, "editable": False})
        h3 = [x for x in r["rejected"] if x["profile"] == "minimax-h3"]
        self.assertTrue(h3 and any("EVIDENCE_MISSING" in s for s in h3[0]["reasons"]))

    def test_deterministic(self):
        a = self.resolve({"format": "psd", "offline": True, "editable": True})
        b = self.resolve({"format": "psd", "offline": True, "editable": True})
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
