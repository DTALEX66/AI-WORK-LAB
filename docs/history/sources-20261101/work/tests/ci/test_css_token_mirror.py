"""The CSS mirror guard must catch a real collision and must not invent one.

Written the day it was needed: `--radius-sm` was declared 4px in src/index.css and 12px in the pinned
skins/b10.css, in the same `:root` scope, and the cascade -- not the token records, not DESIGN.md, not the
contract test that compares DESIGN.md to index.css -- decided that every consumer renders 12px. Two
declarations of one name can also be the same colour spelled differently, which is why the comparison is
normalised and why a re-spelling is tested as a non-event.
"""
from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "verify_css_token_mirror", REPO / "scripts" / "ci" / "verify_css_token_mirror.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)  # type: ignore[attr-defined]

SHEETS = checker.SHEETS


def _runtime_root() -> Path:
    root = REPO / ".project-local" / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


class RealSheets(unittest.TestCase):
    def test_the_shipped_sheets_agree_in_every_theme_scope(self) -> None:
        found = checker.collect(REPO)
        bad = checker.collisions(found)
        self.assertEqual([], [(theme, name) for theme, name, _ in bad],
                         "a custom property carries two values in one theme; the cascade, not the token "
                         "record, decides what renders")

    def test_the_guard_actually_reads_the_sheets_it_claims(self) -> None:
        found = checker.collect(REPO)
        # measured on the shipped files: the pairs this round reconciled are still there to be seen, so an
        # empty or tiny parse means the walker stopped reading, not that the tree got cleaner
        self.assertGreater(len({name for _theme, name in found}), checker.MIN_NAMES,
                           f"only {len({name for _, name in found})} custom properties parsed")
        themed = [key for key in found if key[0] != "local"]
        self.assertGreater(len(themed), checker.MIN_SCOPED,
                           f"only {len(themed)} declarations landed in a theme scope")
        self.assertIn(("dark", "--radius-sm"), found)
        self.assertIn(("light", "--color-muted"), found)
        self.assertEqual([["12px"]],
                         [sorted({v for values in found[("dark", "--radius-sm")].values() for v in values})])

    def test_the_tool_exits_zero_on_the_committed_tree(self) -> None:
        self.assertEqual(0, checker.main([]))


class PlantedStates(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="css-mirror-", dir=str(_runtime_root())))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, rel: str, text: str) -> None:
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        self.assertEqual(text, path.read_text(encoding="utf-8"))

    def sheets(self, index: str = "", b10: str = "", shell: str = "") -> None:
        big = "\n".join(f"--n{name}: {name}px;" for name in range(checker.MIN_NAMES + 5))
        self.write(SHEETS[0], index or (":root{" + big + "}"))
        self.write(SHEETS[1], b10 or ":root{--bg:#050D16;}")
        self.write(SHEETS[2], shell or "html.light{--bg:#F4F7FA;}")

    def test_one_name_two_values_in_one_theme_is_a_collision(self) -> None:
        self.sheets(index=":root{--radius-sm: 4px;}", b10=":root{--radius-sm: 12px;}")
        found = checker.collect(self.dir)
        bad = checker.collisions(found)
        self.assertEqual(1, len(bad), f"expected the planted pair, got {bad}")
        theme, name, by_sheet = bad[0]
        self.assertEqual(("dark", "--radius-sm"), (theme, name))
        self.assertEqual({"4px", "12px"}, {v for values in by_sheet.values() for v in values})

    def test_the_same_colour_spelled_two_ways_is_not_drift(self) -> None:
        self.sheets(index=":root{--shadow: 0 20px 80px rgba(0, 0, 0, 0.35);}",
                    b10=":root{--shadow: 0 20px 80px rgba(0,0,0,.35);}")
        self.assertEqual([], checker.collisions(checker.collect(self.dir)),
                         "a formatting difference was reported as a value difference")

    def test_a_value_inside_a_comment_is_not_a_declaration(self) -> None:
        self.sheets(index=":root{--x: 8px;}\n/* --x: 9px; */", b10=":root{--x: 8px;}")
        self.assertEqual([], checker.collisions(checker.collect(self.dir)))

    def test_a_component_scope_override_is_not_compared_with_a_theme_token(self) -> None:
        self.sheets(index=":root{--x: 8px;}\n.card{--x: 2px;}", b10=":root{--x: 8px;}")
        self.assertEqual([], checker.collisions(checker.collect(self.dir)),
                         "a local override was treated as a second theme value for the same role")

    def test_a_media_block_still_belongs_to_its_theme(self) -> None:
        self.sheets(index=":root{--x: 8px;}",
                    b10="@media (min-width: 1px){:root{--x: 9px;}}")
        bad = checker.collisions(checker.collect(self.dir))
        self.assertEqual(1, len(bad), f"the scope walker lost a media-nested :root: {bad}")

    def test_a_run_that_parses_almost_nothing_refuses_to_pass(self) -> None:
        for rel in SHEETS:
            self.write(rel, "/* nothing here */")
        original = checker.repo_root
        try:
            checker.repo_root = lambda: self.dir
            self.assertEqual(1, checker.main([]))
        finally:
            checker.repo_root = original

    def test_a_walker_that_places_nothing_in_a_theme_scope_is_reported_not_clean(self) -> None:
        # the first version of this guard did exactly this: the selector was captured with its leading
        # newline, so `^:root` never matched, every declaration went to "local", and the run printed a
        # spotless collisions=0 over a real defect
        for rel in SHEETS:
            self.write(rel, ".whatever{--x: 1px;}")
        big = "\n".join(f"--n{index}: {index}px;" for index in range(checker.MIN_NAMES + 5))
        self.write(SHEETS[0], f".whatever{{{big}}}")
        original = checker.repo_root
        try:
            checker.repo_root = lambda: self.dir
            self.assertEqual(1, checker.main([]))
        finally:
            checker.repo_root = original


class Normalisation(unittest.TestCase):
    def test_numbers_are_rewritten_not_reformatted_into_nothing(self) -> None:
        self.assertEqual("0 20px 80px rgba(0,0,0,0.35)",
                         checker.normalise("0 20px 80px rgba(0, 0, 0, 0.35)"))
        self.assertEqual(checker.normalise("rgba(0,0,0,.35)"), checker.normalise("rgba(0,0,0,0.350)"))
        self.assertNotEqual(checker.normalise("rgba(0,0,0,.35)"), checker.normalise("rgba(0,0,0,0.5)"))
        self.assertEqual("#4a6172", checker.normalise("#4A6172"))

    def test_a_hex_colour_is_a_literal_and_is_never_rewritten(self) -> None:
        """Measured 2026-10-14: the number rewrite ate leading zeros inside hex, so `#050d16` normalised to
        `#50d16`. That is not a cosmetic bug in a debug string — it makes a VALID colour compare EQUAL to an
        invalid one, so a genuine collision between those two spellings would have been published as
        agreement by the very guard whose job is to catch it. The two must stay distinct.
        """
        self.assertEqual("#050d16", checker.normalise("#050d16"))
        self.assertNotEqual(checker.normalise("#050d16"), checker.normalise("#50d16"),
                            "a valid hex colour and an invalid one must never normalise together")
        self.assertNotEqual(checker.normalise("#081420"), checker.normalise("#81420"))
        self.assertNotEqual(checker.normalise("#07111c"), checker.normalise("#7111c"))
        self.assertEqual("#050d16", checker.normalise("#050D16"), "case is still folded")
        # The colours the shipped sheets really carry must survive, including the ones with leading zeros.
        for literal in ("#0b1018", "#f3f6fa", "#eaf0f6", "#cbd5e1", "#ff9aab"):
            self.assertEqual(literal, checker.normalise(literal), literal)
        # And the re-spelling this function exists to equate still equates.
        self.assertEqual(checker.normalise("rgba(5,13,22,0.35)"), checker.normalise("rgba(5, 13, 22, .35)"))


if __name__ == "__main__":
    unittest.main()
