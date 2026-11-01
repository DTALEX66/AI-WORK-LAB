# SPDX-License-Identifier: MIT
"""The Workbench stacking order is a declared table, and the table is the stylesheet.

DESIGN.md §2 recorded "12 z-index 处且无层级表 → 新增层层必须先进表再使用" and nothing checked
it, so the rule was a sentence: a new layer could appear anywhere with nobody naming it. The
verifier derives values and selectors from `style.css` and refuses a bare number, an undeclared
token, a table row that no longer matches the rule carrying it, and a layer nobody explains.

These tests exist because a check nobody can make fail is not a check: each branch is fed a
planted defect, and the comment-prose case is the one that would otherwise inflate the count
(the historical "12" counts declarations, not the `z-index:65` in a note).
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "design-lab" / "scripts" / "verify_ui_layering.py"
CSS = ROOT / "apps" / "workbench" / "style.css"
TABLE = ROOT / "design-lab" / "config" / "ui-layering.json"

sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))

import verify_ui_layering as v  # noqa: E402

BASE_CSS = """
:root{--layer-topbar:50;--layer-scrim:90}
header{position:relative;z-index:var(--layer-topbar)}
.overlay{z-index:var(--layer-scrim)}
"""
BASE_TABLE = {"layers": [
    {"token": "--layer-topbar", "value": 50, "selectors": ["header"], "purpose": "顶栏"},
    {"token": "--layer-scrim", "value": 90, "selectors": [".overlay"], "purpose": "遮罩"},
]}


class UiLayeringTests(unittest.TestCase):
    def test_the_shipped_stylesheet_passes(self) -> None:
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("UI_LAYERING=PASS", proc.stdout)
        self.assertNotIn("UI_LAYERING=FAIL", proc.stdout)

    def test_the_census_is_declarations_not_prose(self) -> None:
        """The comment block in the shell section names `z-index:65` and `z-index:20`."""
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("z-index:65", css,
                      "the prose case this test guards disappeared; update the test")
        rows = v.measure(v.strip_comments(css))
        self.assertGreaterEqual(len(rows), 10)
        self.assertEqual([r for r in rows if r["literal"] is not None], [],
                         "a bare number survived: the table is not the only source of layers")
        self.assertEqual(len(rows), len(v.measure(css)),
                         "comments are being read as declarations")

    def test_a_bare_number_is_refused(self) -> None:
        css = v.strip_comments(BASE_CSS + "\n.newthing{z-index:70}\n")
        problems = v.check(css, {"layers": BASE_TABLE["layers"] + [
            {"token": "--layer-something", "value": 70, "selectors": [".newthing"],
             "purpose": "未登记"}]})
        self.assertTrue(any(p.startswith("LITERAL-ZINDEX .newthing") for p in problems), problems)

    def test_a_token_nobody_declared_is_refused(self) -> None:
        css = v.strip_comments("main{z-index:var(--layer-phantom)}\n")
        problems = v.check(css, BASE_TABLE)
        self.assertTrue(any(p.startswith("UNDECLARED-TOKEN") for p in problems), problems)

    def test_a_table_that_drifted_from_the_css_is_refused(self) -> None:
        drifted = {"layers": [dict(BASE_TABLE["layers"][0], value=40), BASE_TABLE["layers"][1]]}
        problems = v.check(v.strip_comments(BASE_CSS), drifted)
        self.assertTrue(any(p.startswith("TABLE-VALUE-DRIFT --layer-topbar: 50")
                            for p in problems), problems)

    def test_a_row_for_a_rule_that_no_longer_exists_is_refused(self) -> None:
        stale = {"layers": BASE_TABLE["layers"] + [
            {"token": "--layer-gone", "value": 30, "selectors": [".removed"], "purpose": "旧层"}]}
        problems = v.check(v.strip_comments(BASE_CSS), stale)
        self.assertTrue(any(p.startswith("TABLE-STALE-LAYER --layer-gone")
                            for p in problems), problems)

    def test_selector_attribution_has_to_match_the_rule(self) -> None:
        """A row that names the wrong selector is a wrong map, not a harmless typo."""
        mislabelled = {"layers": [dict(BASE_TABLE["layers"][0], selectors=[".not-the-header"]),
                                  BASE_TABLE["layers"][1]]}
        problems = v.check(v.strip_comments(BASE_CSS), mislabelled)
        self.assertTrue(any(p.startswith("TABLE-SELECTOR-DRIFT --layer-topbar")
                            for p in problems), problems)

    def test_a_layer_nobody_explains_is_refused(self) -> None:
        blank = {"layers": [dict(BASE_TABLE["layers"][0], purpose="  "),
                            BASE_TABLE["layers"][1]]}
        problems = v.check(v.strip_comments(BASE_CSS), blank)
        self.assertTrue(any(p.startswith("UNDOCUMENTED-LAYER --layer-topbar")
                            for p in problems), problems)

    def test_packed_and_per_line_token_declarations_mean_the_same(self) -> None:
        """Both layouts appear in real stylesheets; the first draft of this parser matched
        only one and invented 'stale row' findings for the other."""
        packed = v.declared_tokens(v.strip_comments(BASE_CSS))
        per_line = v.declared_tokens(":root{\n  --layer-topbar:50;\n  --layer-scrim:90;\n}\n")
        self.assertEqual(packed, per_line)
        self.assertEqual(packed, {"--layer-topbar": "50", "--layer-scrim": "90"})

    def test_the_clean_case_actually_passes(self) -> None:
        """Positive control: the planted defects above need a baseline with zero findings."""
        self.assertEqual(v.check(v.strip_comments(BASE_CSS), BASE_TABLE), [])

    def test_the_shipped_table_is_generated_from_the_shipped_css(self) -> None:
        rows = v.measure(v.strip_comments(CSS.read_text(encoding="utf-8")))
        tokens = v.declared_tokens(v.strip_comments(CSS.read_text(encoding="utf-8")))
        rebuilt = v.build_table(rows, tokens, {"layers": []})
        self.assertEqual(len(rebuilt["layers"]), len(tokens),
                         "a declared layer token is missing from the table")
        self.assertEqual({l["token"]: l["selectors"] for l in rebuilt["layers"]},
                         {l["token"]: l["selectors"] for l in
                          v.load_table(TABLE)["layers"]},
                         "the committed table's selector attribution is not what the "
                         "stylesheet says")


if __name__ == "__main__":
    unittest.main()
