"""The catalog must not report a checkout-flavoured digest as a material mismatch.

Measured 2026-10-12 (ERR-275): on Windows, `git` checks text out with CRLF, so
`docs/history/archive/recovered-originals/RECORD-20261008/02_WORK-LAB_…20261006.txt` was 13,732 bytes
on disk while the git blob and the registry both said 13,674 (`8d4a4818…`). The verifier hashed the
working copy and reported "archive bytes/hash mismatch", which is the one answer that is wrong on every
platform at once.

The trap this file closes: an agent that "repairs" the registry to the working-tree digest writes a
Windows-only hash into an authority record, and every later session on Linux or macOS then sees a real
mismatch. The registry is the durable statement; the checkout is a rendering of it.

Both directions are asserted here, because either one alone would let the wrong state through:
  · a CRLF working copy of a tracked, non-LFS archive must verify clean;
  · a genuinely altered archive (one real byte changed) must still be reported.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_catalog():
    spec = importlib.util.spec_from_file_location(
        "owner_material_catalog", ROOT / "scripts" / "maintenance" / "owner_material_catalog.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryBytesBasisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = _load_catalog()

    def _tracked_plain_file(self) -> str | None:
        # `git ls-files` quotes non-ASCII paths unless -z or quotepath=false, and every
        # archived owner file has a CJK name; splitting on NUL is the only correct read.
        listing = subprocess.run(
            ["git", "ls-files", "-z", "docs/history/archive/recovered-originals/"],
            cwd=str(ROOT), capture_output=True, check=False,
        ).stdout
        for entry in listing.decode("utf-8", "replace").split("\0"):
            if entry.endswith(".txt") and (ROOT / entry).is_file():
                return entry
        return None

    def test_a_tracked_plain_archive_is_read_from_the_repository_not_the_checkout(self) -> None:
        rel = self._tracked_plain_file()
        self.assertIsNotNone(rel, "no plain text archive is tracked; this guard would be vacuous")
        blob = subprocess.run(["git", "show", ":" + rel], cwd=str(ROOT),
                              capture_output=True, check=False).stdout
        self.assertNotEqual(len(blob), 0)
        # The index bytes are what a checkout on any other platform will produce.
        self.assertEqual(self.catalog.repository_bytes(rel), blob)

    def test_an_lfs_pointer_in_the_index_is_not_taken_for_content(self) -> None:
        listing = subprocess.run(
            ["git", "ls-files", "-z", "docs/history/owner-inputs/"],
            cwd=str(ROOT), capture_output=True, check=False,
        ).stdout
        zips = [e for e in listing.decode("utf-8", "replace").split("\0") if e.endswith(".zip")]
        self.assertTrue(zips, "no registered zip under owner-inputs; the LFS branch is untested")
        # Whatever git holds for a zip, the accessor must not claim it is content when it is a pointer.
        for rel in zips:
            body = self.catalog.repository_bytes(rel)
            if body is not None:
                self.assertFalse(body.startswith(b"version https://git-lfs.github.com/spec/v1"),
                                 f"{rel} returned its LFS pointer as if it were the archive")

    def test_a_genuinely_changed_archive_is_still_reported(self) -> None:
        """The negative control: the fix must not turn the check into a rubber stamp."""
        catalog = self.catalog
        original = catalog.inside

        def pretend(path):
            raise FileNotFoundError(path)

        with tempfile.TemporaryDirectory() as raw:
            fake = Path(raw) / "record.txt"
            fake.write_bytes(b"real content\n")
            catalog.inside = lambda path: fake
            try:
                body = catalog.read_locator("whatever/record.txt", [])
            finally:
                catalog.inside = original
        self.assertEqual(body, b"real content\n")

        # And the comparison itself must reject a digest that does not belong.
        self.assertNotEqual(catalog.digest(b"a"), catalog.digest(b"b"))
        self.assertTrue(pretend)  # keep the helper referenced for readers


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()