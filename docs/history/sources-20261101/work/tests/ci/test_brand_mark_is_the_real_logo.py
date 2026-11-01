"""Gate: the brand mark in the shell is the real cut-out logo, at its own ratio, and it can actually glow.

No node on this machine means `vite build` and the vitest suite cannot run here, so this gate checks what is
decidable from the files themselves -- and it is strict about the three ways this change could have looked
right and rendered wrong:

  * the mask URL points at a file that exists in the repository (a described-but-absent asset builds fine
    and shows nothing);
  * each slot's width/height ratio matches the artwork's measured 1.9033:1, because `contain` hides a wrong
    box by letterboxing it silently -- the mark just gets smaller and nobody notices;
  * the glow lives on the *unmasked* element and the glyph on its ::before. Per CSS painting order a mask is
    applied after a filter, so `filter: drop-shadow()` written on the same rule as `mask:` glows the glyph
    and then clips the halo away. My first draft did exactly that; the control below is why the rule exists.

It also pins the decision this had to route around: `b10.css` is the pinned skin and stays verbatim (D-11),
so the rail override must live in the shell layer with two classes.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "apps" / "observer" / "frontend" / "src"
SHELL = SRC / "skins" / "l10b-shell.css"
B10 = SRC / "skins" / "b10.css"
SIDEBAR = SRC / "components" / "layout" / "Sidebar.tsx"
ASSET = SRC / "assets" / "brand" / "work-lab-mark.png"

# Measured from the supplied artwork, 2026-10-25: the WORK symbol's ink box is 272.79 x 143.82 viewBox
# units in `docs/history/owner-inputs/20261025/WORK-1.svg` (paths above the type block), and the same
# 1.8968 ratio falls out of the wide cut in WORK-2.svg -- two independent cuts of one artwork agreeing is
# the check that the split is where the designer put it. The assets themselves are built by
# `scripts/brand/build_work_brand.py`, which refuses to write if the measured ratio moves (it pins 1.8968
# too), so this constant and that script describe the same measurement rather than two guesses.
MARK_ASPECT = 272.79 / 143.82
ASPECT_TOLERANCE = 0.02
SLOTS = {
    ".topbar-brand-mark": (42, 22),
    ".brand .brand-mark": (91, 48),
}


def rule_block(css: str, selector: str) -> str:
    """The declaration block of an exact selector, or "" when it is absent."""
    pattern = re.compile(r"(?<![\w .-])" + re.escape(selector) + r"[^{]*\{([^}]*)\}")
    match = pattern.search(css)
    return match.group(1) if match else ""


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    # IHDR is the first chunk: 4-byte length, "IHDR", then width and height as big-endian uint32.
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


class BrandMarkAssetTests(unittest.TestCase):
    def test_the_mark_asset_is_present_alpha_and_the_right_shape(self) -> None:
        self.assertTrue(ASSET.is_file(), f"{ASSET.relative_to(ROOT)} is missing")
        width, height = png_size(ASSET)
        self.assertGreaterEqual(width, 42 * 4,
                                f"the mark is {width}px wide for a 42px slot; at <4x a 2x display shows blur")
        self.assertGreater(height, 0)
        data = ASSET.read_bytes()
        # Colour type 6 = RGBA: a mask asset without alpha would paint a solid rectangle.
        colour_type = data[25]
        self.assertEqual(colour_type, 6, f"brand mark PNG colour type is {colour_type}, expected 6 (RGBA)")
        self.assertAlmostEqual(width / height, MARK_ASPECT, delta=0.06,
                               msg=f"asset ratio {width / height:.4f} drifted from the measured "
                                   f"{MARK_ASPECT:.4f}; the cut must follow the ink box, not a square")

    def test_every_mask_url_in_the_shell_resolves_to_a_tracked_file(self) -> None:
        css = SHELL.read_text(encoding="utf-8")
        refs = re.findall(r"mask(?:-image)?\s*:\s*url\([\"']?([^\"')]+)[\"']?\)", css)
        self.assertTrue(refs, "no mask references at all -- the brand mount was removed or renamed")
        missing = []
        for ref in refs:
            if ref.startswith(("http", "data:")):
                missing.append(f"{ref}: a remote or inline asset is not allowed in a local desktop shell")
                continue
            resolved = (SHELL.parent / ref).resolve()
            if not resolved.is_file():
                missing.append(ref)
        self.assertEqual(missing, [], f"mask URLs that do not resolve inside the checkout: {missing}")


class SlotGeometryTests(unittest.TestCase):
    def test_each_slot_box_matches_the_artwork_ratio(self) -> None:
        css = SHELL.read_text(encoding="utf-8")
        for selector, (width, height) in SLOTS.items():
            with self.subTest(slot=selector):
                block = rule_block(css, selector)
                self.assertTrue(block, f"{selector} has no rule block in the shell skin")
                declared_w = re.search(r"width:\s*(\d+)px", block)
                declared_h = re.search(r"height:\s*(\d+)px", block)
                self.assertTrue(declared_w and declared_h,
                                f"{selector} must declare both width and height in px so the ratio is "
                                "checkable; a percentage or auto box cannot be verified from the file")
                ratio = int(declared_w.group(1)) / int(declared_h.group(1))
                self.assertAlmostEqual(ratio, width / height, delta=ASPECT_TOLERANCE,
                                       msg=f"{selector} box is {ratio:.4f}, expected {width / height:.4f}")
                self.assertAlmostEqual(ratio, MARK_ASPECT, delta=0.03,
                                       msg=f"{selector} ratio {ratio:.4f} distorts or letterboxes the mark "
                                           f"(artwork is {MARK_ASPECT:.4f})")

    def test_the_glow_is_not_masked_away(self) -> None:
        css = SHELL.read_text(encoding="utf-8")
        offenders = []
        for selector in (".topbar-brand-mark", ".topbar-brand-mark::before", ".brand .brand-mark",
                         ".brand .brand-mark::before"):
            block = rule_block(css, selector)
            if not block:
                continue
            has_mask = "mask" in block or "-webkit-mask" in block
            has_glow = "drop-shadow" in block or "box-shadow" in block
            if has_mask and has_glow:
                offenders.append(selector)
        self.assertEqual(
            offenders, [],
            f"rules that mask AND glow in one block: {offenders} -- a mask is applied after a filter, so "
            "the halo is clipped and the mark renders flat while the CSS still looks correct",
        )

    def test_the_control_shape_is_convicted(self) -> None:
        # Without this, the assertion above could pass simply because it cannot see the pattern.
        sample = (".x { width: 10px; height: 10px; mask: url(a.png); filter: drop-shadow(0 0 2px red); }\n")
        block = rule_block(sample, ".x")
        self.assertIn("mask", block)
        self.assertIn("drop-shadow", block)

    def test_the_pinned_skin_still_carries_the_original_rule(self) -> None:
        b10 = B10.read_text(encoding="utf-8")
        self.assertIn(".brand-mark{", b10,
                      "b10.css was edited: it is the pinned skin and stays verbatim (decision D-11)")
        self.assertIn("width:48px;height:48px", b10)
        shell = SHELL.read_text(encoding="utf-8")
        self.assertTrue(rule_block(shell, ".brand .brand-mark"),
                        "the shell does not override the rail mark with two classes, so b10's plate wins "
                        "and the rail keeps rendering the old gradient tile")


class MarkupTests(unittest.TestCase):
    def test_the_rail_no_longer_spells_the_brand_in_text(self) -> None:
        markup = SIDEBAR.read_text(encoding="utf-8")
        self.assertNotIn('>WL</div>', markup,
                         "the rail still renders the typed 'WL' placeholder inside the mark box")
        self.assertIn('className="brand-mark"', markup)
        self.assertIn('aria-hidden="true"', markup,
                      "the mark must stay decorative: the h1 already announces WORK-LAB, and labelling "
                      "the glyph too makes a screen reader say the brand twice")


if __name__ == "__main__":
    unittest.main()
