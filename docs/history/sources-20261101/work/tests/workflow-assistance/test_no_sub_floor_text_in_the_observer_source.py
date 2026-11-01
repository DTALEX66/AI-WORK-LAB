"""Gate: the 12px type floor holds in the source, not only in the lanes the browser happened to render.

`scripts/audit/text_legibility_via_cdp.py` measures the shipped bundle, but one page load paints the
active lanes of one view. The floor it enforces was set by DESIGN.md for every screen, and 125
`text-[9px]/[10px]/[11px]` utilities once sat across 30 files, most of them behind navigation. This
guard is the cheap half: no browser, every file, run in the canonical gate.

The pinned skin is the one place a sub-12px declaration may survive — `b10.css` is verbatim by
decision D-11 and cannot be edited. It is therefore not exempt: each such declaration must be
overridden by name in `l10b-shell.css` at or above the floor, so "we cannot change it" can never
quietly become "so nobody did".
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "apps" / "observer" / "frontend" / "src"
FLOOR_PX = 12.0

ARBITRARY_TEXT = re.compile(r"\btext-\[([\d.]+)px\]")
CSS_FONT_SIZE = re.compile(r"font-size:\s*([\d.]+)px")
BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")
COMMENT = re.compile(r"/\*.*?\*/", re.S)


def sources(patterns: tuple[str, ...]) -> list[Path]:
    return sorted({p for glob in patterns for p in SRC.rglob(glob)})


def sheet(name: str) -> str:
    """The sheet's declarations, with comments removed. These comments quote the numbers they fix —
    `b10 pins .brand small{font-size:10px}` — and an explanation is not a style rule."""
    return COMMENT.sub("", (SRC / name).read_text(encoding="utf-8"))


def sub_floor_matches(text: str) -> list[tuple[str, float]]:
    return [(m.group(1), float(m.group(1))) for m in ARBITRARY_TEXT.finditer(text)
            if float(m.group(1)) < FLOOR_PX]


def rule_selectors(css: str) -> list[tuple[str, str]]:
    return [(selector.strip(), body) for selector, body in BLOCK.findall(css)]


def font_sizes_in(selector_body: str) -> list[float]:
    return [float(m.group(1)) for m in CSS_FONT_SIZE.finditer(selector_body)]


class ArbitraryTextUtilityTests(unittest.TestCase):
    def test_no_component_writes_a_sub_floor_text_utility(self) -> None:
        offenders = []
        for path in sources(("*.tsx", "*.ts")):
            for value, size in sub_floor_matches(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(ROOT)}: text-[{value}px] ({size})")
        self.assertEqual(offenders, [], "text below the DESIGN.md floor: " + "; ".join(offenders[:12]))

    def test_the_census_is_not_empty(self) -> None:
        """A guard over zero files passes forever. The sweep touched 30 of them, so counting is cheap
        insurance against a path change that silently shrinks the scanned set to nothing."""
        scanned = sources(("*.tsx", "*.ts"))
        self.assertGreaterEqual(len(scanned), 60, f"only {len(scanned)} frontend source files scanned")
        with_floor = sum(1 for p in scanned if ARBITRARY_TEXT.search(p.read_text(encoding="utf-8")))
        self.assertGreaterEqual(with_floor, 5, "no `text-[Npx]` utility found anywhere — wrong tree?")


class StyleSheetFloorTests(unittest.TestCase):
    def test_the_shell_and_theme_layers_declare_nothing_below_the_floor(self) -> None:
        offenders = []
        for name in ("index.css", "skins/l10b-shell.css"):
            for selector, body in rule_selectors(sheet(name)):
                for size in font_sizes_in(body):
                    if size < FLOOR_PX:
                        offenders.append(f"{name}: {selector[:60]} -> {size}px")
        self.assertEqual(offenders, [], "sub-floor declarations in editable sheets: "
                         + "; ".join(offenders))

    def test_every_pinned_skin_sub_floor_declaration_is_overridden_by_name(self) -> None:
        b10 = sheet("skins/b10.css")
        shell_selectors = [selector for selector, _ in rule_selectors(sheet("skins/l10b-shell.css"))]
        pinned = [(selector, size) for selector, body in rule_selectors(b10)
                  for size in font_sizes_in(body) if size < FLOOR_PX]
        self.assertTrue(pinned, "b10.css no longer carries a sub-floor rule; this test's premise "
                                "changed and it should be retired deliberately, not by accident")
        for selector, size in pinned:
            self.assertTrue(any(selector in candidate for candidate in shell_selectors),
                            f"b10 pins {selector!r} at {size}px and no rule in l10b-shell.css names "
                            f"it, so the pinned value is what renders")

    def test_the_pinned_override_is_a_rule_not_a_wish(self) -> None:
        """`.brand small` is the only sub-floor declaration b10 pins, so the shell rule that raises it
        is small enough to read here. It exists because the instrument measured 10px on screen; if the
        override is ever deleted this file goes red and the rendered page is the second witness."""
        override = [body for selector, body in rule_selectors(sheet("skins/l10b-shell.css"))
                    if ".brand small" in selector]
        self.assertTrue(override, "l10b-shell.css no longer restates .brand small")
        sizes = [size for body in override for size in font_sizes_in(body)]
        self.assertTrue(any(size >= FLOOR_PX for size in sizes),
                        f"the .brand small override sets {sizes}, below the {FLOOR_PX}px floor")


if __name__ == "__main__":
    unittest.main()
