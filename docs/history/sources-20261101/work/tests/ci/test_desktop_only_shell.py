"""Gate: the Observer shell is desktop-only, and the pinned skin was overridden rather than edited.

Owner instruction 2026-10-07: 优先跑通全量执行桌面端电脑端 UI，先删除手机端其他端. The mobile
drawer (hamburger, overlay, its state and its props) is deleted, the rail is the only navigation
surface, and the main window can no longer be resized into a phone shape.

jsdom applies no media queries, so the width-and-configuration half of that contract cannot be
proved by the frontend suite and is proved here instead, against the files that carry it. Two
non-obvious constraints are pinned on purpose:

  * b10.css stays verbatim (decision D-11). Deleting the phone layout from the pinned skin would be
    a skin forgery, so the shell layer overrides it — and the override only works while the pinned
    rule is still there, which is what `test_pinned_skin_is_overridden_not_edited` proves.
  * the palette lives in exactly one module (src/theme/tokens.ts). A component that restates a hex
    silently survives a theme or brand calibration.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "apps" / "observer" / "frontend"
SRC = FRONT / "src"
SHELL = SRC / "skins" / "l10b-shell.css"
B10 = SRC / "skins" / "b10.css"
TAURI = ROOT / "apps" / "observer" / "src-tauri" / "tauri.conf.json"

MOBILE_TRACE = re.compile(
    r"mobile-nav|topbar-mobile|mobileOpen|onCloseMobile|onOpenMobileNav|mobileNavOpen|onAfterSelect")
PALETTE = ("#2A91FF", "#20CDE1", "#F59E0B", "#22C55E", "#EF4444", "#3882F6",
           "#050D16", "#07111C", "#081420", "#0C1B2A", "#17435D", "#EEF6FC", "#8EABBC")


def sources(patterns=(".ts", ".tsx", ".css")) -> list[Path]:
    return sorted(p for p in SRC.rglob("*") if p.suffix in patterns and p.is_file())


def has(text: str, pattern: str, why: str) -> None:
    """unittest's assertRegex takes `msg` as its third positional argument, so a flags argument
    passed that way is silently swallowed and `^`/`$` stop meaning per-line. This helper compiles
    MULTILINE itself and reports the reason it pinned the rule."""
    if re.search(pattern, text, re.MULTILINE) is None:
        raise AssertionError(f"{why}: {pattern!r} not found")


def has_not(text: str, pattern: str, why: str) -> None:
    if re.search(pattern, text, re.MULTILINE) is not None:
        raise AssertionError(f"{why}: {pattern!r} is present")


class DesktopOnlyShellGate(unittest.TestCase):
    def test_no_mobile_drawer_trace_survives_in_production_source(self) -> None:
        # Test files may name the deleted classes in order to forbid them — that is what
        # desktopShell.contract.test.ts does — so they are excluded, exactly as the citation
        # audit had to exclude its own output to stop quoting itself.
        offenders = []
        for path in sources():
            if ".test." in path.name:
                continue
            if MOBILE_TRACE.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(path.relative_to(SRC).as_posix())
        self.assertEqual(offenders, [])

    def test_the_rail_and_the_two_track_grid_are_stated_outside_any_width_query(self) -> None:
        css = SHELL.read_text(encoding="utf-8")
        has(css, r"^\.sidebar-slot \{ display: flex; flex-direction: column; \}$", "rail is unconditional")
        has_not(css, r"^\s*@media \(min-width: 841px\)", "a width query gates the shell again")
        has(css, r"^\.app \{ grid-template-columns: clamp\(", "two-track grid stated at column zero")
        has(css, r"^\.app\.app-compact \{ grid-template-columns: minmax\(0, 1fr\); \}$",
            "the HUD owns a single track")

    def test_pinned_skin_is_overridden_not_edited(self) -> None:
        b10 = B10.read_text(encoding="utf-8")
        self.assertIn("@media (max-width:840px)", b10)
        self.assertIn(".sidebar{display:none}", b10)
        shell = SHELL.read_text(encoding="utf-8")
        # The override needs two classes: b10's single-class rule is less specific and earlier.
        has(shell, r"@media \(max-width: 840px\) \{\s*\.sidebar\.sidebar-slot \{ display: flex",
            "the shell does not re-show the rail inside the pinned query")

    def test_the_daily_surfaces_mask_the_real_mark(self) -> None:
        """CL-15's brand gate mounted only the professional shell, so the desktop window's own surfaces could
        draw a generic glyph and the suite stayed green. This anchors each daily class to the mask that paints
        the shipped mark inside the same rule body -- a bare class name with no rule would satisfy a substring
        search and guard nothing.
        """
        css = SHELL.read_text(encoding="utf-8")
        for cls in ("daily-brand-mark", "daily-rail-brand"):
            has(css, rf"^\.{cls} \{{", f".{cls} is declared at column zero")
            has(css, rf"\.{cls}::before[,\s][^}}]*mask: url\(\"\.\./assets/brand/work-lab-mark\.png\"\)",
                f".{cls} paints the shipped mark rather than a placeholder")

    def test_the_main_window_has_a_desktop_floor_and_the_hud_stays_declared(self) -> None:
        conf = json.loads(TAURI.read_text(encoding="utf-8"))
        windows = {w["label"]: w for w in conf["app"]["windows"]}
        self.assertGreaterEqual(windows["main"]["minWidth"], 900,
                                "a 320px main window is the phone shape this round removed")
        self.assertGreaterEqual(windows["main"]["minHeight"], 600)
        self.assertEqual(windows["panel"], {**windows["panel"], "width": 440, "height": 680,
                                           "resizable": False})

    def test_the_palette_lives_in_one_module(self) -> None:
        offenders = []
        for path in sources((".ts", ".tsx")):
            name = path.relative_to(SRC).as_posix()
            if name == "theme/tokens.ts" or ".test." in path.name:
                continue
            upper = path.read_text(encoding="utf-8", errors="replace").upper()
            if any(hex_code.upper() in upper for hex_code in PALETTE):
                offenders.append(name)
        self.assertEqual(offenders, [])

    # ---------------- negative controls
    def test_the_mobile_sweep_is_not_vacuous(self) -> None:
        self.assertGreaterEqual(len(sources()), 50)
        for token in ("mobile-nav", "topbar-mobile", "onOpenMobileNav"):
            self.assertTrue(MOBILE_TRACE.search(f'class="{token}" {token}'), token)

    def test_the_palette_sweep_is_not_vacuous(self) -> None:
        tokens = (SRC / "theme" / "tokens.ts").read_text(encoding="utf-8").upper()
        self.assertTrue(all(hex_code.upper() in tokens for hex_code in PALETTE),
                        "PALETTE no longer describes the module it guards")

    def test_the_absence_detector_can_see(self) -> None:
        # A `has_not` that can never fire is worse than no assertion at all.
        probe = "x\n@media (min-width: 841px) {\n  .sidebar-slot { display: flex; }\n}\n"
        with self.assertRaises(AssertionError):
            has_not(probe, r"^\s*@media \(min-width: 841px\)", "detector is blind")
        with self.assertRaises(AssertionError):
            has(probe, r"^\.sidebar-slot \{ display: none; \}$", "pattern never matches")


if __name__ == "__main__":
    unittest.main(verbosity=2)
