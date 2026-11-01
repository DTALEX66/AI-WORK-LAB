# SPDX-License-Identifier: MIT
"""DL-GV-003: MiniGame game-visual fixture boundary gate.

Fail-closed: active paths in fixtures/domains/game-visual must NOT re-introduce
launch-game / IAA / adSlots / release / monetization / nextContentPack /
platform-operations semantics. History docs under docs/history/ are exempt.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MINIGAME = REPO / "fixtures/domains/game-visual"

# Active paths (exclude docs/history/ which is immutable history)
ACTIVE_ROOTS = [
    MINIGAME / "README.md",
    MINIGAME / "AGENTS.md",
    MINIGAME / "games",
    MINIGAME / "src",
    MINIGAME / "platform",
    MINIGAME / "scripts",
    MINIGAME / "build.js",
    MINIGAME / "package.json",
]

FORBIDDEN_PATTERNS = [
    (r"platformRole\s*:\s*[\"']launch-game", "platformRole launch-game"),
    (r"\"monetization\"", "monetization field"),
    (r"\"adSlots\"", "adSlots field"),
    (r"\"nextContentPackCandidate\"", "nextContentPackCandidate"),
    (r"\"model\"\s*:\s*[\"']IAA", "IAA model"),
    (r"激励广告", "rewarded ad (cn)"),
    (r"合集平台", "collection platform (cn)"),
    (r"变现", "monetization (cn)"),
    (r"发布门禁", "release gate (cn)"),
    (r"小游戏合集平台的首发", "collection-platform launch claim"),
]


def _iter_active_files():
    for root in ACTIVE_ROOTS:
        if root.is_file():
            yield root
        elif root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file() and "node_modules" not in p.parts and p.suffix in (
                    ".md", ".json", ".js", ".ts", ".html", ".css",
                ):
                    yield p


class MiniGameVisualFixtureBoundaryTest(unittest.TestCase):
    def test_game_manifest_is_fixture_reference(self) -> None:
        manifest = MINIGAME / "games/find-anomaly/elevator-console/game.manifest.json"
        self.assertTrue(manifest.exists(), "elevator-console manifest missing")
        text = manifest.read_text(encoding="utf-8")
        self.assertIn("fixtureRole", text)
        self.assertIn("game-visual-design-reference", text)
        self.assertNotIn("launch-game", text)
        self.assertNotIn("monetization", text)
        self.assertNotIn("adSlots", text)
        self.assertNotIn("nextContentPackCandidate", text)

    def test_no_platform_product_semantics_in_active_paths(self) -> None:
        hits: list[str] = []
        for p in _iter_active_files():
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern, label in FORBIDDEN_PATTERNS:
                if re.search(pattern, text):
                    rel = p.relative_to(REPO)
                    # Exempt prohibition/history context lines (禁止/不是/历史/不可执行/Forbidden/PR that re-introduces)
                    if any(w in text for w in ["禁止", "不是", "历史", "不可执行", "Forbidden", "FORBIDDEN", "re-introduces"]):
                        continue
                    hits.append(f"{rel}: {label}")
        self.assertEqual([], hits, "forbidden product semantics found:\n" + "\n".join(hits[:20]))

    def test_readme_declares_fixture_contract(self) -> None:
        readme = MINIGAME / "README.md"
        text = readme.read_text(encoding="utf-8")
        self.assertIn("Game Visual Design Fixture", text)
        self.assertIn("禁止", text)

    def test_agents_md_frozen_boundary(self) -> None:
        agents = MINIGAME / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        self.assertIn("frozen game visual design fixture", text.lower())
        self.assertIn("not an independent game product", text.lower())

if __name__ == "__main__":
    unittest.main()
