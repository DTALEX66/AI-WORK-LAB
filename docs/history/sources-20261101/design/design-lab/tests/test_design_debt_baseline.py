# SPDX-License-Identifier: MIT
"""DESIGN.md §4's debt stock must be the number a rule produces, not a hand count.

The contract's存量 line was hand-counted (`18 / 360 / 9`, recorded in
`docs/audits/DESIGNLAB-LAUNCH-REVIEW-PREFLIGHT-2026-10-08.md` §36.4) and no rule reproduces
it. The external design-review plugin, first run on 2026-10-08, produced a third set of
numbers (`44 / 602 / 26`) over the same bytes, because it counts matches inside comments and
grades a `box-shadow:none` reset as a value. A contract about to become an acceptance standard
cannot carry an unrestorable figure, so the measurement lives in
`scripts/design_debt_baseline.py`, this test keeps the prose and the measurement equal, and the
per-site colour register keeps the "may not grow" clause enforceable instead of aspirational.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "design_debt_baseline.py"

sys.path.insert(0, str(ROOT))

from scripts import design_debt_baseline as db  # noqa: E402


def naive_counts() -> dict:
    """The same regexes with every exclusion turned off, to prove the exclusions work."""
    px = shadows = 0
    for rel in db.SCOPE:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        px += sum(len(db.PX.findall(line)) for line in text.splitlines())
        shadows += sum(len(db.SHADOW.findall(line)) for line in text.splitlines())
    return {"literalPx": px, "shadowDeclarations": shadows}


class DesignDebtBaselineTests(unittest.TestCase):
    def runScript(self, *flags: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *flags], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")

    def test_the_contract_states_the_measured_stock(self) -> None:
        result = self.runScript("--check")
        self.assertEqual(result.returncode, 0,
                         "DESIGN.md §4 or the colour register no longer matches the "
                         "measurement:\n" + result.stdout + result.stderr)
        self.assertIn("DESIGN_DEBT_BASELINE=PASS", result.stdout)

    def test_the_measurement_is_a_population_not_a_zero(self) -> None:
        # Positive control: a broken scope or regex would satisfy the equality check
        # against a document that says zero. The real stock is large.
        values = db.measure()
        self.assertGreater(values["literalPx"], 200, values)
        self.assertGreater(values["literalColors"], 10, values)
        self.assertGreaterEqual(values["shadowDeclarations"], 10, values)

    def test_comments_token_lines_and_resets_actually_leave_the_count(self) -> None:
        """The exclusions must be doing work, not decorating the raw match count.

        Without this, the rule could silently degrade into "count every match" -- which is
        what the external tool does -- and the contract would still read PASS.
        """
        blanked = db.strip_comments("/* sizing is 13px and #316CFF */\n.a{width:13px}\n"
                                    "// a note about 21px\n")
        self.assertNotIn("13px and", blanked)
        self.assertNotIn("21px", blanked)
        self.assertIn(".a{width:13px}", blanked)

        values = db.measure()
        naive = naive_counts()
        self.assertLess(values["literalPx"], naive["literalPx"],
                        "comment and token-line skipping removes nothing")
        self.assertGreaterEqual(naive["shadowDeclarations"],
                                values["shadowDeclarations"] + values["shadowResetsSkipped"],
                                "the shadow count exceeds the raw `box-shadow:` count")
        self.assertGreater(values["shadowResetsSkipped"], 0,
                           "no reset was ever found, so the exclusion is untested")
        # The exclusion mechanism itself, asserted rather than inferred from a total.
        self.assertTrue(db.RESET_VALUE.match("none"))
        self.assertTrue(db.RESET_VALUE.match(" inherit"))
        self.assertFalse(db.RESET_VALUE.match("0 4px 18px rgba(0,0,0,.35)"))

    def test_a_neutral_alpha_is_not_reported_as_a_new_hue(self) -> None:
        self.assertEqual(db.classify("rgba(0,0,0,.25)"), "neutral-alpha")
        self.assertEqual(db.classify("rgba(255, 255, 255, .02)"), "neutral-alpha")
        self.assertEqual(db.classify("#1D4FC4"), "chromatic")
        values = db.measure()
        self.assertEqual(values["chromaticLiterals"] + values["neutralAlphaLiterals"],
                         values["literalColors"])

    def test_a_new_literal_site_is_a_failure_not_a_notice(self) -> None:
        """The register's whole purpose: growth is red, a pending ruling is not."""
        values = db.measure()
        values["sites"].append({"value": "#ff00aa", "file": "apps/workbench/style.css",
                              "line": 1, "kind": "chromatic", "occurrence": 99,
                              "declaration": ".planted{color:#ff00aa}"})
        problems, notices = db.check_register(values)
        self.assertTrue(any("UNREGISTERED-LITERAL" in p and "#ff00aa" in p
                            for p in problems), problems)

    def test_a_removed_literal_leaves_a_stale_row(self) -> None:
        values = {"sites": [s for s in db.measure()["sites"]
                            if s["kind"] != "chromatic"]}
        problems, _ = db.check_register(values)
        self.assertTrue(any(p.startswith("STALE-REGISTER-ENTRY") for p in problems),
                        problems[:3])

    def test_an_adjudication_without_a_named_human_is_refused(self) -> None:
        document = json.loads(db.REGISTER.read_text(encoding="utf-8"))
        entry = document["entries"][0]
        entry["adjudication"] = "keep it"
        entry["adjudicatedBy"] = None
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "register.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            original = db.REGISTER
            try:
                db.REGISTER = path
                problems, _ = db.check_register(db.measure())
            finally:
                db.REGISTER = original
        self.assertTrue(any("UNSIGNABLE-ADJUDICATION" in p for p in problems), problems[:3])

    def test_rewriting_the_register_preserves_a_ruling_and_a_moved_line(self) -> None:
        """Owner input is not the script's to overwrite, and a shifted line is not new debt."""
        values = db.measure()
        first = dict(values["sites"][0])
        first["adjudication"] = "replace with var(--color-primary)"
        first["adjudicatedBy"] = "DTALEX66"
        first["adjudicatedOn"] = "2026-10-09"
        document = {"schemaVersion": "design-lab/ui-off-palette-colours/v1", "entries": [first]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "register.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            original = db.REGISTER
            try:
                db.REGISTER = path
                db.write_register(values)
                written = json.loads(path.read_text(encoding="utf-8"))
                row = {db.site_key(e): e for e in written["entries"]}[db.site_key(first)]
                # the same key with a different line number must still resolve to the row
                moved = dict(first)
                moved["line"] = first["line"] + 400
                self.assertEqual(row["adjudicatedBy"], "DTALEX66")
                self.assertEqual(db.site_key(moved), db.site_key(first))
                problems, notices = db.check_register(values)
            finally:
                db.REGISTER = original
        self.assertEqual(problems, [])
        self.assertTrue(any("PENDING-OWNER-ADJUDICATION" in n for n in notices), notices)

    def test_drift_is_caught(self) -> None:
        wrong = db.measure()
        wrong["literalPx"] += 1
        stated, _ = db.contract_statement(wrong)
        self.assertFalse(stated,
                         "the check passes even when the document disagrees by one px")


if __name__ == "__main__":
    unittest.main()
