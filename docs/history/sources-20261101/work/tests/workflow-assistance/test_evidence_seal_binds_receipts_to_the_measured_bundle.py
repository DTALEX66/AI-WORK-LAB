"""The evidence seal must be able to tell a stale receipt from a live one -- and to be proved unable to lie.

Why this exists: on 2026-10-10 the Observer `dist` was rebuilt after every screenshot, geometry, legibility,
DPI and keyboard receipt in `.project-local/artifacts/wui-20261009` had already been written. Nothing in the
tree noticed, and nothing could have: a render receipt named no bundle, so "measured" and "measured against
bytes that a rebuild replaced an hour later" were the same shape on disk. `scripts/audit/seal_wui_evidence.py`
now classifies every artifact BOUND / STALE / UNBOUND against the build that exists right now.

A classifier that cannot fail is decoration, so the load-bearing assertions here are the negative ones: the
seal must refuse a receipt that names a different build, must refuse one that names nothing at all, and must
not seal a picture whose parent receipt went stale. Everything runs against synthetic trees in a temp dir --
this test does not need the real `dist`, so it stays checkout-verifiable on a CI runner.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provenance = _load("bundle_provenance_under_test", "scripts/audit/bundle_provenance.py")
seal = _load("seal_wui_evidence_under_test", "scripts/audit/seal_wui_evidence.py")


def make_tree(root: Path) -> Path:
    """A fixture repo with a built front end: index.html plus two chunks the page can load."""
    dist = root / "apps" / "observer" / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<script src="./assets/index-AAA.js"></script>', encoding="utf-8")
    (dist / "assets" / "index-AAA.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "assets" / "window-BBB.js").write_text("console.log(2)", encoding="utf-8")
    return dist


class BundleProvenanceTests(unittest.TestCase):
    def test_the_digest_moves_when_a_loadable_chunk_moves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dist = make_tree(Path(tmp))
            before = provenance.describe(Path(tmp))["bundleDigest"]
            (dist / "assets" / "window-BBB.js").write_text("console.log(3)", encoding="utf-8")
            after = provenance.describe(Path(tmp))["bundleDigest"]
            self.assertNotEqual(before, after,
                                "a change to a dynamically imported chunk left the digest alone, so the "
                                "identity does not describe what the browser can load")

    def test_every_asset_file_is_named_with_its_own_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(Path(tmp))
            report = provenance.describe(Path(tmp))
            self.assertEqual(sorted(f["path"] for f in report["files"]),
                             ["assets/index-AAA.js", "assets/window-BBB.js", "index.html"],
                             "the manifest must list the entry, the chunk and the html, not a count")
            self.assertTrue(all(len(f["sha256"]) == 64 for f in report["files"]))

    def test_a_missing_build_refuses_rather_than_describing_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                provenance.describe(Path(tmp))


class SealClassificationTests(unittest.TestCase):
    def _digest(self, tmp: Path) -> tuple[str, str]:
        report = provenance.describe(tmp)
        index_sha = next(f["sha256"] for f in report["files"] if f["path"] == "index.html")
        return report["bundleDigest"], index_sha

    def test_a_receipt_naming_the_current_build_is_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            digest, index_sha = self._digest(root)
            path = root / "geometry.json"
            path.write_text(json.dumps([{"view": "full", "servedBundle": {"bundleDigest": digest}}]),
                            encoding="utf-8")
            state, detail = seal.binding_of(path, digest, index_sha)
            self.assertEqual(state, "BOUND", detail)

    def test_a_receipt_naming_a_different_build_is_stale_not_bound(self) -> None:
        # The load-bearing case: this is what the rebuild silently produced, and a seal that called it
        # BOUND would be worse than no seal at all.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = make_tree(root)
            digest, index_sha = self._digest(root)
            (dist / "assets" / "index-AAA.js").write_text("console.log(9)", encoding="utf-8")
            stale_digest = self._digest(root)[0]
            self.assertNotEqual(stale_digest, digest, "the fixture rebuild did not move the digest")
            path = root / "receipt.json"
            # `digest` is what the receipt recorded at capture time; the build on disk is now `stale_digest`.
            path.write_text(json.dumps({"servedBundle": {"bundleDigest": digest}}), encoding="utf-8")
            state, detail = seal.binding_of(path, stale_digest, self._digest(root)[1])
            self.assertEqual(state, "STALE", detail)
            self.assertIn(digest[:16], detail, "STALE must name the build the receipt actually measured")

    def test_a_staged_only_native_receipt_is_not_read_as_a_render_claim(self) -> None:
        # u19_keyboard_focus_cdp hashes dist/index.html as a stage 0 precondition, but the release binary it
        # launches paints the bundle EMBEDDED in its own bytes. A seal that called that BOUND would let a
        # receipt claim authorship of pixels it never loaded.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            digest, index_sha = self._digest(root)
            path = root / "keyboard.json"
            path.write_text(json.dumps({"distBundle": {"sha256": index_sha}}), encoding="utf-8")
            state, detail = seal.binding_of(path, digest, index_sha)
            self.assertEqual(state, "BOUND_STAGED", detail)
            self.assertNotEqual(state, "BOUND")
            self.assertIn("staged", detail)

    def test_a_staged_receipt_from_a_gone_build_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = make_tree(root)
            _, index_sha = self._digest(root)
            (dist / "index.html").write_text("<script src='./index-AAA.js'></script><!--moved-->",
                                             encoding="utf-8")
            path = root / "keyboard.json"
            path.write_text(json.dumps({"distBundle": {"sha256": index_sha}}), encoding="utf-8")
            state, _ = seal.binding_of(path, self._digest(root)[0], self._digest(root)[1])
            self.assertEqual(state, "STALE")

    def test_a_receipt_with_no_identity_is_unbound_not_passing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            digest, index_sha = self._digest(root)
            path = root / "old.json"
            path.write_text(json.dumps({"verdict": {"passed": True}}), encoding="utf-8")
            state, detail = seal.binding_of(path, digest, index_sha)
            self.assertEqual(state, "UNBOUND", detail)

    def test_the_walker_reaches_rows_nested_in_lists(self) -> None:
        # geometry and legibility emit a LIST of per-view rows; a walker that only reads a top-level dict
        # would call every one of them UNBOUND and the seal would be crying wolf.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            digest, index_sha = self._digest(root)
            path = root / "rows.json"
            path.write_text(json.dumps([{"view": "full"}, {"view": "floor",
                                                             "servedBundle": {"bundleDigest": digest}}]),
                            encoding="utf-8")
            self.assertEqual(seal.binding_of(path, digest, index_sha)[0], "BOUND")

    def test_a_picture_is_sealed_only_through_a_receipt_that_is_itself_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = make_tree(root)
            digest, _ = self._digest(root)
            receipt = root / "evidence-receipt.json"
            shot = root / "01-main-dark.png"
            shot.write_bytes(b"not a png")
            receipt.write_text(json.dumps({"servedBundle": {"bundleDigest": digest},
                                           "shots": [{"screenshot": str(shot)}]}), encoding="utf-8")
            bound = seal.pictures_bound_by([receipt], digest)
            self.assertEqual(bound.get("01-main-dark.png"), digest,
                             "a picture named by a bound receipt must inherit its binding")

            (dist / "assets" / "index-AAA.js").write_text("console.log(0)", encoding="utf-8")
            after = seal.pictures_bound_by([receipt], self._digest(root)[0])
            self.assertEqual(after, {},
                             "the build moved but the picture was still sealed to it -- that is the exact "
                             "failure this whole gate exists to catch")


if __name__ == "__main__":
    unittest.main()
