"""Gate: the handle-latency instrument must be able to say "I did not measure that".

`scripts/audit/handle_block_visibility_via_cdp.py` spent a round reporting a 3,225 ms median for the
artifact-handle block that was entirely its own `sleep()`: the poll began ~3.2 s after navigation, so the
first DOM look already found the rows and the number described the instrument's wake-up time. The convergence
report repeated that figure as "the 3.26 s is almost all page-side" until a clean re-measurement put the same
page's rows at ~208 ms (`.project-local/artifacts/wl02-and-handle-20261021/handle-latency-attribution-v2.json`).

So the assertions here are not about the page being fast. They are about the instrument never again turning a
missing measurement into a number:

* a segment that is absent or negative is convicted by name, because a negative commit segment is exactly
  what mis-paired boundaries produced during this fix;
* the recorded moment must PREDATE the read-back, which is the shape of the original bug;
* "visible" is decided from the rows element's own rect, and a below-the-fold commit that reports a 0 ms
  scroll segment is a contradiction;
* a receipt that names no bundle bytes cannot be quoted for any build;
* the segment names the guard checks are read out of the instrument's own READBACK text, so renaming one on
  the page side without updating the verdict is convicted here rather than silently unchecked.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTRUMENT = ROOT / "scripts" / "audit" / "handle_block_visibility_via_cdp.py"


def _load():
    spec = importlib.util.spec_from_file_location("handle_latency", INSTRUMENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


instrument = _load()


def good_sample(**over) -> dict:
    """The shape the shipped instrument actually produces on this host (bundle 8e793275…, 2026-10-21)."""
    sample = {
        "instrumented": True,
        "readbackAtMs": 3535,
        "rowsAtMs": 208,
        "rowCount": 200,
        "snapshotHandleRows": 200,
        "rowsRect": {"top": 884, "bottom": 23940, "height": 23056},
        "viewport": {"width": 1262, "height": 668},
        "belowFoldAtCommit": True,
        "visibleAfterScroll": True,
        "scrollOutcome": "NOW_VISIBLE",
        "servedBundle": {"files": [{"path": "assets/index.js", "sha256": "8e793275"}]},
        "segments": {"A_snapshotParseMs": 150, "B_reactCommitMs": 59,
                     "C_rowsToVisibleMs": 54, "totalNavToVisibleMs": 208},
    }
    sample.update(over)
    return sample


class SegmentPopulationTests(unittest.TestCase):
    def test_every_required_segment_is_produced_by_the_page_expression(self) -> None:
        produced = set(re.findall(r"^\s*([A-Za-z0-9_]+Ms):", instrument.READBACK, re.M))
        produced |= set(re.findall(r"^\s*([A-Z]_[A-Za-z0-9_]+Ms):", instrument.READBACK, re.M))
        missing = [name for name in instrument.SEGMENTS if name not in produced]
        self.assertEqual([], missing,
                         "the guard checks segment names the page no longer reports — a green run here "
                         "would mean nothing")

    def test_the_recorder_is_installed_before_navigation(self) -> None:
        # The whole fix rests on the recorder existing at navigationStart; the old instrument evaluated
        # after the page had already settled, which is what made its first look 3.2 s late.
        source = INSTRUMENT.read_text(encoding="utf-8")
        self.assertIn("Page.addScriptToEvaluateOnNewDocument", source)
        self.assertLess(source.index("addScriptToEvaluateOnNewDocument"), source.index("Page.navigate"),
                        "navigating before installing the recorder means the recorder missed the navigation")

    def test_the_instrument_no_longer_polls_from_the_read_back(self) -> None:
        source = INSTRUMENT.read_text(encoding="utf-8")
        self.assertNotIn("CFG.pollMs", source,
                        "a 20 ms poll started from the evaluation moment is the defect this replaced")


class ProblemsTests(unittest.TestCase):
    def test_a_healthy_sample_is_not_convicted(self) -> None:
        self.assertEqual([], instrument.problems(good_sample(), None))

    def test_an_uninstalled_recorder_reports_one_missing_measurement(self) -> None:
        found = instrument.problems(good_sample(instrumented=False, instrumentError="null documentElement"),
                                    None)
        self.assertEqual(1, len(found))
        self.assertIn("never installed", found[0])
        self.assertIn("missing measurement", found[0])

    def test_rows_never_appearing_is_a_missing_number_not_a_slow_one(self) -> None:
        sample = good_sample(rowsAtMs=None)
        sample["segments"] = dict(sample["segments"], totalNavToVisibleMs=None)
        found = instrument.problems(sample, None)
        self.assertTrue(any("never entered the DOM" in p for p in found), str(found))
        self.assertTrue(any("totalNavToVisibleMs is unmeasurable" in p for p in found), str(found))

    def test_a_late_look_is_convicted_by_name(self) -> None:
        # rowsAt recorded at the same instant the instrument read the page back: no observation happened.
        found = instrument.problems(good_sample(rowsAtMs=3535, readbackAtMs=3535), None)
        self.assertTrue(any("recorded at read time" in p for p in found), str(found))

    def test_a_negative_segment_is_convicted_as_an_instrument_fault(self) -> None:
        sample = good_sample()
        sample["segments"]["B_reactCommitMs"] = -3
        found = instrument.problems(sample, None)
        self.assertTrue(any("B_reactCommitMs = -3 ms is negative" in p for p in found), str(found))
        self.assertTrue(any("this instrument, not the page" in p for p in found), str(found))

    def test_each_absent_segment_is_named(self) -> None:
        for name in instrument.SEGMENTS:
            with self.subTest(segment=name):
                sample = good_sample()
                sample["segments"][name] = None
                found = instrument.problems(sample, None)
                self.assertTrue(any(name in p and "unmeasurable" in p for p in found), str(found))

    def test_below_fold_with_a_zero_scroll_segment_is_a_contradiction(self) -> None:
        sample = good_sample()
        sample["segments"]["C_rowsToVisibleMs"] = 0
        found = instrument.problems(sample, None)
        self.assertTrue(any("nobody scrolled" in p for p in found), str(found))

    def test_a_scroll_that_does_not_bring_the_rows_on_screen_is_convicted(self) -> None:
        found = instrument.problems(good_sample(visibleAfterScroll=False), None)
        self.assertTrue(any("did not bring the rows on screen" in p for p in found), str(found))

    def test_a_receipt_without_bundle_bytes_cannot_be_quoted(self) -> None:
        for bundle in ({}, {"files": []}):
            with self.subTest(bundle=bundle):
                found = instrument.problems(good_sample(servedBundle=bundle), None)
                self.assertTrue(any("names no bundle bytes" in p for p in found), str(found))

    def test_the_stated_budget_bites(self) -> None:
        found = instrument.problems(good_sample(), 200)
        self.assertTrue(any("exceeds the stated budget 200 ms" in p for p in found), str(found))
        self.assertEqual([], instrument.problems(good_sample(), 1000))

    def test_rows_without_a_snapshot_denominator_are_convicted(self) -> None:
        found = instrument.problems(good_sample(snapshotHandleRows=None), None)
        self.assertEqual(1, len(found), str(found))
        self.assertIn("no denominator", found[0])

    def test_more_dom_rows_than_the_snapshot_served_is_a_fabrication(self) -> None:
        found = instrument.problems(good_sample(rowCount=240), None)
        self.assertEqual(1, len(found), str(found))
        self.assertIn("invented", found[0])
        self.assertIn("240 rows while the snapshot served 200", found[0])

    def test_a_taller_than_the_viewport_list_that_was_never_scrolled_is_convicted(self) -> None:
        found = instrument.problems(good_sample(scrollOutcome="NO_SCROLL_HOOK", visibleAfterScroll=None),
                                    None)
        self.assertEqual(1, len(found), str(found))
        self.assertIn("23056px inside a 668px viewport", found[0])
        self.assertIn("34.5", found[0], "the receipt must say how many screens of rows it is talking about")

    def test_a_short_list_needs_no_scroll_evidence(self) -> None:
        # The conviction is about an un-windowed tail nobody reached, not about rects in general: a list that
        # fits the viewport is fully on screen at commit, and demanding a scroll for it would be a false red.
        sample = good_sample(rowsRect={"top": 20, "bottom": 500, "height": 480},
                             scrollOutcome="NO_SCROLL_HOOK", visibleAfterScroll=None,
                             belowFoldAtCommit=False)
        self.assertEqual([], instrument.problems(sample, None))


class GeometryIsPrintedTests(unittest.TestCase):
    """The 23,056px figure may only live in a receipt that computed it."""

    def test_the_report_carries_the_geometry_of_every_sample(self) -> None:
        source = INSTRUMENT.read_text(encoding="utf-8")
        self.assertIn('"handleGeometry": [handle_geometry(s) for s in samples]', source,
                      "a receipt without the row count, the list height and the viewport height cannot back "
                      "a claim about an un-windowed list")

    def test_the_printed_line_names_the_numbers_a_reader_needs(self) -> None:
        source = INSTRUMENT.read_text(encoding="utf-8")
        for token in ("listPx", "viewportPx", "pxPerRow", "screens", "servedRows", "domRows"):
            self.assertIn(token, source, f"the summary line dropped {token}, so the geometry is only in the JSON")

    def test_handle_geometry_divides_by_real_numbers_and_not_by_assumptions(self) -> None:
        self.assertEqual({"rowsInDom": 200, "rowsServedBySnapshot": 200, "listHeightPx": 23056,
                          "viewportHeightPx": 668, "pxPerRow": 115.3, "viewportsOfScrolling": 34.5},
                         instrument.handle_geometry(good_sample()))
        empty = instrument.handle_geometry(good_sample(rowCount=0, rowsRect=None))
        self.assertIsNone(empty["pxPerRow"], "a division by zero would invent a per-row cost")


class CallSiteNameTests(unittest.TestCase):
    """A helper that unit tests reach directly and the real call site cannot is the worst kind of green.

    The shipped instrument crashed on its own report line because `main()` rebinds the name `geometry` to
    the imported harness module; the guard suite stayed green because it only ever called the function.
    """

    def test_no_module_level_helper_is_shadowed_by_a_local_in_main(self) -> None:
        tree = ast.parse(INSTRUMENT.read_text(encoding="utf-8"))
        helpers = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        main = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "main")
        bound = {target.id for node in ast.walk(main) for target in ast.walk(node)
                 if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store)}
        bound |= {arg.arg for arg in main.args.args}
        self.assertEqual(set(), helpers & bound,
                         f"main() rebinds {sorted(helpers & bound)}, so a call to that name inside main() "
                         "resolves to something else than the module-level helper")


class AggregateTests(unittest.TestCase):
    def test_median_and_worst_come_only_from_measured_samples(self) -> None:
        samples = [good_sample(), good_sample(), good_sample()]
        for index, value in enumerate((10, 30, 20)):
            samples[index]["segments"]["totalNavToVisibleMs"] = value
        got = instrument.aggregate(samples, "totalNavToVisibleMs")
        self.assertEqual({"n": 3, "median": 20, "worst": 30}, got)

    def test_unmeasurable_samples_are_counted_as_missing_not_as_zero(self) -> None:
        samples = [good_sample(), good_sample()]
        samples[0]["segments"]["totalNavToVisibleMs"] = None
        samples[1]["segments"]["totalNavToVisibleMs"] = 222
        got = instrument.aggregate(samples, "totalNavToVisibleMs")
        self.assertEqual(1, got["n"])
        self.assertEqual(222, got["median"])
        self.assertNotIn(0, (got["median"], got["worst"]))


if __name__ == "__main__":
    unittest.main()
