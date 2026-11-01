"""The README's history links must be labelled, and the check must be shown refusing a real fault.

Two failures this encodes:
  * the written rule was flat ("README links authority files only") while the tree carried 14 history
    links, so the rule enforced nothing and was silently false;
  * the first decidable version of the checker searched each line for the word `archive`, and every path
    it polices contains `docs/history/archive/` -- it matched its own URL and reported 14/14 clean,
    including the one line that delegated a current recovery procedure to a 2026-08-13 handoff.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import verify_readme_history_labels as gate  # noqa: E402

PATH = "docs/history/archive/workflow-assistance/handoffs/some-round-2026-08-13.md"


class TheRealReadme(unittest.TestCase):
    def test_every_history_link_is_labelled(self) -> None:
        lines = gate.README.read_text(encoding="utf-8").split("\n")
        links = [l for l in lines if gate.HISTORY_LINK.search(l)]
        self.assertGreaterEqual(len(links), 10,
                                "the README stopped carrying history links; this test needs a re-think, "
                                "not a green")
        found = gate.violations(lines)
        self.assertEqual([], [(n, e) for n, e in found],
                         f"unlabelled history links: {[n for n, _ in found]}")

    def test_the_gate_command_passes_and_names_its_count(self) -> None:
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "ci" /
                                                      "verify_readme_history_labels.py")],
                              cwd=REPO, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("all_labelled_by_prose_or_heading", proc.stdout)


class TheCheckRefusesWhatItClaims(unittest.TestCase):
    def test_a_path_alone_is_not_a_label(self) -> None:
        """The vacuity regression: `archive` inside the URL must not satisfy the rule."""
        hostile = [f"今日恢复流程见 [`{PATH}`]({PATH})。"]
        self.assertEqual(1, len(gate.violations(hostile)),
                         "the checker let an unlabelled link through because the path spells 'archive'")

    def test_prose_that_marks_the_record_as_past_is_enough(self) -> None:
        ok = [f"那一轮（2026-08-13）的记录仅作归档参考，见 [`{PATH}`]({PATH})。"]
        self.assertEqual([], gate.violations(ok))

    def test_a_heading_that_declares_an_archive_section_is_enough(self) -> None:
        lines = ["## 文档和审计（历史归档）", "", f"- [`{PATH}`]({PATH})：某一轮交接"]
        self.assertEqual([], gate.violations(lines))

    def test_an_index_heading_without_a_label_still_fails(self) -> None:
        lines = ["## 操作手册", "", f"- [`{PATH}`]({PATH})：当前流程"]
        found = gate.violations(lines)
        self.assertEqual(1, len(found), f"expected one violation, got {found}")
        self.assertEqual(3, found[0][0], "the reported line number is not the link line")

    def test_stripping_leaves_the_human_words(self) -> None:
        stripped = gate.prose_of(f"see [`{PATH}`]({PATH}) for the round record")
        self.assertNotIn("history", stripped)
        self.assertIn("round record", stripped)


if __name__ == "__main__":
    unittest.main()
