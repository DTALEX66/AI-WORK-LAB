"""WLG-110: active authority index contract tests.

Every rule has exactly one canonical source. README may link only active
authority files (per docs/workflow/active-authority-index.md), never
superseded/archive records as normative sources.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ActiveAuthorityIndexTests(unittest.TestCase):
    def test_index_exists_and_covers_active_domains(self):
        index = ROOT / "docs/current/workflow-assistance/workflow/active-authority-index.md"
        self.assertTrue(index.is_file(), "active-authority-index.md missing")
        text = index.read_text(encoding="utf-8")
        for expected in (
            "config-ownership.json",
            "project-profiles.json",
            "run_taskpack_agent.py",
            "task_ledger.py",
            "gate_vocabulary.py",
            "hash_budget.py",
            "audit_triggers.py",
            "apply_safety.py",
        ):
            self.assertIn(expected, text, f"index missing active authority: {expected}")

    def test_index_defines_three_categories(self):
        text = (ROOT / "docs/current/workflow-assistance/workflow/active-authority-index.md").read_text(encoding="utf-8")
        for category in ("活跃权威", "兼容/参考", "已取代/历史"):
            self.assertIn(category, text)

    def test_archive_records_are_not_normative(self):
        text = (ROOT / "docs/current/workflow-assistance/workflow/active-authority-index.md").read_text(encoding="utf-8")
        self.assertIn("不构成当前规范", text)
        self.assertIn("仅作归档", text)

    def test_readme_links_authority_files(self):
        readme = (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8")
        self.assertIn("active-authority-index.md", readme)

    def test_historical_handoffs_are_listed_as_archive(self):
        index = (ROOT / "docs/current/workflow-assistance/workflow/active-authority-index.md").read_text(encoding="utf-8")
        self.assertIn("docs/handoffs/", index)
        self.assertIn("docs/audit/", index)


if __name__ == "__main__":
    unittest.main()
