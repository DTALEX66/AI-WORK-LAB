"""A directory-shaped `git check-ignore` probe proves nothing, and this repo must not reason with it.

Measured on this checkout: `git check-ignore -v --no-index services/` exits 0 and names `.gitignore:44`,
which is an EMPTY line, and it does the same for `docs/current/` and for `totally-made-up-dir/`. Git
answers a trailing-slash query by matching the blank line, so the verdict is independent of the tree. The
same query with a file inside the directory is honest: `services/orchestration/sidecar.py` exits 1 while
`.project-local/runs/x.json` exits 0.

Why this is pinned: a claim that some build-output directory "is not ignored, so it can be committed by
accident" was nearly written on the strength of a directory-shaped probe, and the register cites ignore
status for several surfaces. Asking about a file is the only form that discriminates.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def probe(path: str) -> int:
    return subprocess.run(["git", "check-ignore", "-v", "--no-index", "--", path],
                          cwd=REPO, capture_output=True).returncode


def directory_shaped_check_ignore_args(source: str) -> list[str]:
    """Directory-shaped string literals in a `git check-ignore` argument list.

    Read with `ast`, not by regexing quotes out of a text window: a window that starts mid-list (`["git",
    "check-ignore", ...]` is how every call site in this repo spells it) pairs the closing quote of one
    element with the opening quote of the next, and the first version of this scanner reported the wrong
    literals for exactly that reason. Operands built at runtime are out of reach and the test says so.
    """
    import ast

    found: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        sequence = node.args[0]
        if not isinstance(sequence, (ast.List, ast.Tuple)):
            continue
        words = [element.value for element in sequence.elts
                 if isinstance(element, ast.Constant) and isinstance(element.value, str)]
        if "check-ignore" not in words:
            continue
        found.extend(word for word in words if word.endswith("/") and not word.startswith("-"))
    return found


class IgnoreProbeShape(unittest.TestCase):
    def test_a_directory_shaped_probe_cannot_tell_a_tracked_directory_from_a_fabricated_one(self) -> None:
        """The rule is the indiscrimination, not this box's exit code.

        Measured 2026-10-11: on this Windows checkout `git check-ignore -v --no-index services/` exits 0 and
        names `.gitignore:44`, an EMPTY line, and answers the same for a directory that has never existed --
        which is what made the probe worthless. GitHub's Linux runner answers 1 for both. Asserting the exit
        code pinned a git version, so the stage was green here and red there over a fact about git rather than
        about this repository. What must hold on either runner is that the two queries cannot be told apart;
        if they ever differ, a directory-shaped probe has become meaningful, and the call-site rule below
        still forbids relying on one until it is re-measured.
        """
        fabricated = probe("totally-made-up-dir-8f2c/")
        for tracked_dir in ("services/", "docs/current/", "tests/"):
            tracked_rc = probe(tracked_dir)
            self.assertEqual(fabricated, tracked_rc,
                             f"{tracked_dir} read as {tracked_rc} while a fabricated directory read as "
                             f"{fabricated}: the directory-shaped probe now discriminates, so re-measure the "
                             "rule before trusting it -- and still do not use it as evidence")

    def test_a_file_shaped_probe_discriminates_tracked_from_ignored(self) -> None:
        self.assertNotEqual(0, probe("services/orchestration/sidecar.py"),
                            "a tracked source file must not read as ignored")
        self.assertNotEqual(0, probe("apps/observer/web/index.html"),
                            "a deleted directory is NOT ignored; only a file-shaped probe can say that")
        self.assertEqual(0, probe(".project-local/runs/x.json"),
                         "the declared runtime root must read as ignored")
        self.assertEqual(0, probe("apps/token-monitor/src-tauri/target/release/app.exe"),
                         "Cargo build output is only ignored since the 2026-10-08 rule; this is that rule")

    def test_no_check_ignore_call_site_asks_about_a_directory(self) -> None:
        """Every ignore decision in tracked code must ask with a file-shaped path.

        The file set comes from git ls-files, not a filesystem walk: the repo's ignored roots hold deep
        archive paths and junctions that a recursive scan cannot even stat on this machine, and an
        untracked script has no place in a rule about shipped decisions. Limit stated honestly: only
        operands written as literals in a list argument are inspected, so a path assembled at runtime is
        not judged here -- which is why the four call sites in this repo are file-shaped by construction.
        """
        listing = subprocess.run(["git", "ls-files", "--", "*.py"], cwd=REPO, capture_output=True,
                                 check=True).stdout
        offenders = []
        for relative in [line.decode("utf-8", "replace").strip() for line in listing.splitlines()]:
            if not relative:
                continue
            text = (REPO / relative).read_text(encoding="utf-8", errors="replace")
            if "check-ignore" not in text:
                continue
            offenders.extend(f"{relative}: {literal}"
                             for literal in directory_shaped_check_ignore_args(text))
        self.assertEqual([], offenders,
                         "a check-ignore call site is asking about a directory-shaped path, which always "
                         "answers 'ignored'")

    def test_the_scanner_does_find_a_planted_directory_query(self) -> None:
        """Without this the scan above could be green because its pattern matches nothing."""
        planted = ('proc = subprocess.run(["git", "check-ignore", "-q", "--no-index", "build/"], cwd=root)\n'
                   'other = subprocess.run(["git", "check-ignore", "-q", str(root) + "/x.bin"])\n')
        self.assertEqual(["build/"], directory_shaped_check_ignore_args(planted))
        clean = 'subprocess.run(["git", "check-ignore", "-q", "--no-index", "build/out.bin"], cwd=root)\n'
        self.assertEqual([], directory_shaped_check_ignore_args(clean))


if __name__ == "__main__":
    unittest.main()
