# SPDX-License-Identifier: MIT
"""The Record archive must keep equaling what its manifest says it copied.

Task DL-REC-29 landed 259 files from the external `Record` volume and recorded every
one of them (source path, size, CRC32, sha256, target, state) in
`docs/history/record-imports-2026-10-08/RECORD-IMPORT-MANIFEST.json`. A manifest that
nobody re-checks is a claim, not evidence: two ways this archive can silently rot are
(a) someone edits a "frozen" original in place, and (b) git's `* text=auto eol=lf`
normalises a CRLF original at add time, so the worktree looks right while the stored
blob is different. Defect (b) really happened to `06_AUDIT_COVERAGE.csv` during the
import and was caught only because the verifier compares three layers.

This module also makes `scripts/record_import_verify.py` reachable: `canonical-verify.yml`
enumerates gates by name, and `test_gate_reachability` fails any verification script that
no workflow or test invokes.

The external-volume leg runs only where the volume exists; without it the test still
proves the repository's own bytes equal the recorded hashes, and says which leg it ran.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "record_import_verify.py"
MANIFEST_REL = "docs/history/record-imports-2026-10-08/RECORD-IMPORT-MANIFEST.json"
MANIFEST = ROOT / MANIFEST_REL
VOLUME = Path(r"D:\All projects\Record")
IMPORT_PREFIXES = ("docs/history/record-imports-2026-10-08/", "docs/history/archive-2026-10-19/taskpacks/03_DESIGN-LAB_")
REPO_HELD_ACTIONS = ("LANDED", "ALREADY-IN-REPO")


def run_verifier(*flags: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *flags], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def _verifier_module():
    """Load scripts/record_import_verify.py so this test shares its predicates."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("record_import_verify", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def held_path(row: dict, moves: dict[str, str]) -> str:
    """Where a repo-held row's bytes must be found today.

    An archive pass may relocate a landed original without touching a byte. The row then
    declares `movedTo`, and that declaration is only accepted if the archive manifest
    records exactly that pair -- so a stale pointer gets proven or rejected, never patched
    by editing the sealed row.
    """
    move = row.get("movedTo")
    if not move:
        return row["target"]
    if moves.get(row["target"]) != move.get("path"):
        raise AssertionError(f"unproven move declaration for {row['target']}: {move}")
    if not (move.get("reason") or "").strip() or not (move.get("by") or {}).get("commit"):
        raise AssertionError(f"move declaration without reason or commit: {row['target']}")
    return move["path"]


def summary_line(stdout: str) -> dict[str, int]:
    line = next((l for l in stdout.splitlines() if l.startswith("RECORD_VERIFY scope=")), "")
    out: dict[str, int] = {}
    for token in line.split():
        if "=" in token:
            key, _, value = token.partition("=")
            if value.replace(",", "").isdigit():
                out[key] = int(value.replace(",", ""))
    return out


class RecordImportFidelityTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        if not MANIFEST.is_file():
            raise unittest.SkipTest(f"import manifest missing: {MANIFEST_REL}")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.rows = cls.manifest["entries"]

    def test_the_archive_still_equals_what_the_manifest_recorded(self) -> None:
        """Run the shipped verifier and refuse anything but its own OK token."""
        flags = ["--head"] + ([] if VOLUME.is_dir() else ["--offline"])
        result = run_verifier(*flags)
        tail = (result.stdout or "").strip().splitlines()
        self.assertEqual(result.returncode, 0,
                         f"record_import_verify {' '.join(flags)} exited "
                         f"{result.returncode}\n{(result.stdout or '').strip()}\n"
                         f"{(result.stderr or '').strip()}")
        self.assertIn("RECORD_VERIFY=OK", "\n".join(tail), f"no OK verdict in {tail[-3:]}")
        self.assertNotIn("FAIL:", result.stdout or "", "the verifier reported row-level failures")
        scope = "source+repo" if VOLUME.is_dir() else "repo-only"
        self.assertIn(f"scope={scope}", result.stdout or "",
                      "the verifier did not report which legs it actually ran")

    def test_every_repo_held_row_is_accounted_for(self) -> None:
        """worktree_verified must cover every row that claims a repository copy."""
        flags = ["--head"] + ([] if VOLUME.is_dir() else ["--offline"])
        counts = summary_line(run_verifier(*flags).stdout or "")
        expected = sum(1 for r in self.rows if r["action"] in REPO_HELD_ACTIONS)
        self.assertGreater(expected, 0, "the manifest holds no repo rows — the archive vanished")
        self.assertEqual(counts.get("worktree_verified"), expected,
                         f"{counts.get('worktree_verified')} files reconciled but the manifest "
                         f"claims {expected} repo-held rows (LANDED + ALREADY-IN-REPO)")
        self.assertEqual(counts.get("blob_absent"), 0,
                         f"{counts.get('blob_absent')} landed rows have no committed blob — "
                         "the archive is not fully in the repository")

    def test_recorded_hashes_match_the_files_on_disk(self) -> None:
        """Independent recomputation, not just the verifier's own bookkeeping."""
        wrong: list[str] = []
        moves = _verifier_module().archive_moves()
        for row in self.rows:
            if row["action"] not in REPO_HELD_ACTIONS:
                continue
            path = ROOT / held_path(row, moves)
            if not path.is_file():
                wrong.append(f"missing {row['target']}")
                continue
            data = path.read_bytes()
            # A row may declare that the repository copy was deliberately rewritten after the
            # import, and then carries its post-import size/crc. Checking such a row against
            # the ARCHIVED values cannot succeed by construction -- it asserts the thing the
            # declaration exists to deny. So a declared row is held to the declared values,
            # and an undeclared one is still held to the archive. Either way a real mismatch
            # is caught, which is the property this test is for.
            evolved = row.get("repoCrc32AfterImport") is not None
            want_crc = row["repoCrc32AfterImport"] if evolved else row["crc32"]
            want_size = row["repoBytesAfterImport"] if evolved else row["bytes"]
            if f"{zlib.crc32(data) & 0xFFFFFFFF:08x}" != want_crc:
                wrong.append(f"crc {row['target']}")
            if len(data) != want_size:
                wrong.append(f"size {row['target']}")
        self.assertEqual(wrong, [], f"{len(wrong)} archived files disagree with the manifest: "
                                   f"{wrong[:8]}")

    def test_the_frozen_subtree_is_protected_from_line_ending_normalisation(self) -> None:
        """`-text` must stay on the imported subtree, or eol=lf rewrites originals on add.

        Asserted on bytes rather than on `git check-attr` output, because the attribute
        engine's precedence is exactly what a parsing shortcut would get wrong: the rule
        has to win over the repo-wide `* text=auto eol=lf` and over `*.bat text eol=crlf`.
        """
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("docs/history/record-imports-2026-10-08/** -text", attrs,
                      "the byte-frozen import subtree lost its -text protection")
        self.assertIn("docs/history/archive-2026-10-19/taskpacks/03_DESIGN-LAB_* -text", attrs,
                      "the 2026-10-06 request pair lost its -text protection")
        protected = tuple(IMPORT_PREFIXES)
        offenders: list[str] = []
        checked = 0
        for row in self.rows:
            if row["action"] != "LANDED" or not row["target"].startswith(protected):
                continue
            data = (ROOT / row["target"]).read_bytes()
            if b"\r\n" not in data:
                continue
            checked += 1
            blob = subprocess.run(["git", "cat-file", "blob", f"HEAD:{row['target']}"],
                                  cwd=str(ROOT), capture_output=True)
            if blob.returncode != 0 or blob.stdout != data:
                offenders.append(row["target"])
        self.assertGreaterEqual(checked, 1,
                                "no CRLF-bearing landed file was checked — the protection is "
                                "untested, not proven")
        self.assertEqual(offenders, [],
                         f"{len(offenders)} CRLF originals were line-ending-normalised into "
                         f"the repository: {offenders[:5]}")


if __name__ == "__main__":
    unittest.main()
