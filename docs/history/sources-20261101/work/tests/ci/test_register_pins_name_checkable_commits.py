"""A register pin must name a commit a reader can check out, and the checker must not be fooled.

Twelve distinct hashes were pinned by 23 rows and contained by zero refs: pre-squash branch heads, three
of which (656e7d2, 8114d8e, 09c6dd2) GitHub has never received at all -- `GET /commits/<sha>/pulls` answers
422. `git cat-file` still answered for them, so every earlier "does this pin resolve?" check passed. The
distinction the gate now draws is containment by a ref, not existence of an object.

The three states are not interchangeable: 34 pins sit on the open PR branch and are legitimate today, and
an earlier count of "40 not ancestors of origin/main" would have failed a healthy register.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "audit"))

import register_pin_reachability as pins  # noqa: E402

REGISTER = "taskpacks/current/OPEN-TASK-REGISTER.md"
# the pre-cutover ledger, tracked byte-for-byte by the 2026-10-09 cutover record: 404,985 B, 65 pinned rows
ARCHIVE_REGISTER = ("taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/"
                    "taskpacks/current/OPEN-TASK-REGISTER.md")
# a commit that is on main; every clone of this repo contains it, ref-carried, so it is portable
ON_MAIN = "62f666ef36999b846ea1c9bcb075a0970be18933"


def scratch_repo(workdir: Path) -> tuple[Path, str, str]:
    """Build (repo, ref-carried sha, dangling sha) so ZERO_REFS is made rather than inherited.

    The fixture was `0600d6f680dd`, an object that exists in the author's clone and in no ref. On a fresh
    runner the object is simply absent, so the checker answered UNRESOLVABLE -- a different state, and the
    test asserted ZERO_REFS. `git commit-tree` produces an object that no ref contains on any machine that
    has git, which is exactly the condition this guard exists for, and the ref-carried sibling proves the
    other half without depending on this repository's history.
    """
    def run(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=workdir, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        assert result.returncode == 0, f"git {' '.join(args)}: {result.stdout}{result.stderr}"
        return result.stdout.strip()

    run("init", "-q", "-b", "main", ".")
    run("config", "user.email", "guard@example.invalid")
    run("config", "user.name", "guard")
    (workdir / "a.txt").write_text("seed\n", encoding="utf-8", newline="\n")
    run("add", "a.txt")
    run("commit", "-q", "-m", "seed")
    on_ref = run("rev-parse", "HEAD")
    dangling = run("commit-tree", run("rev-parse", "HEAD^{tree}"), "-m", "unreachable guard fixture")
    return workdir, on_ref, dangling


def _runtime_root() -> Path:
    p = REPO / ".project-local" / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


class Classification(unittest.TestCase):
    def test_a_landing_commit_is_reported_on_main(self) -> None:
        state, full, refs = pins.classify(REPO, ON_MAIN[:7])
        self.assertEqual("ON_MAIN", state, f"{full} {refs[:3]}")
        self.assertEqual(40, len(full))

    def test_a_squashed_branch_head_is_caught_by_containment_not_existence(self) -> None:
        workdir = Path(tempfile.mkdtemp(prefix="pin-dangling-", dir=str(_runtime_root())))
        try:
            repo, on_ref, dangling = scratch_repo(workdir)
            state, full, refs = pins.classify(repo, dangling[:12])
            self.assertEqual("ZERO_REFS", state, f"{full} unexpectedly has refs {refs[:3]}")
            self.assertEqual([], refs)
            self.assertEqual(0, subprocess.run(["git", "cat-file", "-e", full + "^{commit}"],
                                               cwd=repo, capture_output=True).returncode,
                             "the object exists; that is exactly why an existence test is not enough")
            carried, _, carried_refs = pins.classify(repo, on_ref[:12])
            self.assertNotEqual("ZERO_REFS", carried,
                                f"a commit carried by refs/heads/main read as having no refs: {carried_refs}")
            self.assertTrue(any("refs/heads/main" in r for r in carried_refs), carried_refs)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_an_unresolvable_token_is_its_own_state(self) -> None:
        state, full, refs = pins.classify(REPO, "deadbee")
        self.assertEqual("UNRESOLVABLE", state)
        self.assertEqual("", full)


class RowExtraction(unittest.TestCase):
    def test_a_bare_hash_without_the_marker_is_not_a_pin(self) -> None:
        rows = pins.rows_with_pins("| A | DONE | see 656e7d2 for the head |\n")
        self.assertEqual([], rows, "@ is what makes a hash a pin; the note must be able to name heads")

    def test_a_pin_is_attributed_to_its_row(self) -> None:
        rows = pins.rows_with_pins(f"| U20 | P1 | CLOSED@{ON_MAIN[:7]} | evidence |\n")
        self.assertEqual(1, len(rows))
        self.assertEqual(("U20", [ON_MAIN[:7]]), (rows[0][1], rows[0][2]))


class TheRealRegister(unittest.TestCase):
    def run_tool(self, *extra: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "audit"
                                                    / "register_pin_reachability.py"), *extra],
                              cwd=REPO, capture_output=True)
        return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")

    def test_every_live_pin_is_contained_by_a_ref(self) -> None:
        code, out = self.run_tool("--check")
        self.assertEqual(0, code, out)
        head = out.splitlines()[0]
        self.assertIn("PIN_REACHABILITY_PASS", head)
        self.assertNotIn("ZERO_REFS=", head, f"a dangling pin is still being counted: {head}")
        self.assertNotIn("UNRESOLVABLE=", head, f"an unresolvable token is still being counted: {head}")

    def test_the_checker_reports_a_bounded_pin_count(self) -> None:
        _code, out = self.run_tool()
        head = out.splitlines()[0]
        self.assertIn("pins=", head)
        self.assertIn("distinct_tokens=", head)
        self.assertIn("rows_with_pins=", head)

    def test_a_planted_dead_pin_turns_the_check_red(self) -> None:
        workdir = Path(tempfile.mkdtemp(prefix="pin-reachability-", dir=str(_runtime_root())))
        try:
            repo, _on_ref, dangling = scratch_repo(workdir)
            planted = workdir / "register.md"
            planted.write_text(f"| ID | Priority | Status | Work |\n|---|---|---|---|\n"
                               f"| X | P1 | DONE@{dangling[:12]} | planted dead pin |\n",
                               encoding="utf-8", newline="\n")
            code, out = self.run_tool("--register", str(planted), "--repo", str(repo), "--check")
            self.assertEqual(1, code, out)
            self.assertIn(f"ZERO_REFS {dangling[:12]}", out,
                          "the planted dangling pin must be named with the state that made it dead, on a "
                          "repo where that state was constructed rather than inherited from one box")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_a_file_with_no_pins_fails_instead_of_passing(self) -> None:
        workdir = Path(tempfile.mkdtemp(prefix="pin-empty-", dir=str(_runtime_root())))
        try:
            empty = workdir / "register.md"
            empty.write_text("| ID | Priority | Status | Work |\n|---|---|---|---|\n"
                             "| X | P1 | DONE | no pins here |\n", encoding="utf-8", newline="\n")
            code, out = self.run_tool("--register", str(empty), "--check")
            self.assertEqual(1, code, out)
            self.assertIn("rows_with_pins=0", out)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_the_register_itself_still_carries_many_pins(self) -> None:
        """A guard that could pass on an emptied file guards nothing -- so the floor sits on the ledger
        that has the pins, and the live one keeps a floor equal to what it actually carries.

        Measured 2026-10-11: the live register has 1 pinned row (WUI-00 -> 71b1ae86) because the 2026-10-09
        cutover replaced the 190-row multi-table ledger with the 25-row WUI table; the pre-cutover bytes
        survive tracked and the extractor finds 65 pinned rows in them. `>40` therefore stays as an absolute
        floor -- on the archived ledger, where the shape that produced it still exists -- while the live
        assertion names the pin it expects, so a register that loses its pins or a parser that stops reading
        them both go red. Nothing here was relaxed to green: the floor moved to the document it measures.
        """
        archived = (REPO / ARCHIVE_REGISTER).read_text(encoding="utf-8")
        self.assertGreater(len(pins.rows_with_pins(archived)), 40,
                           "the archived pre-cutover ledger is the positive control for this extractor; "
                           "if it no longer yields many pinned rows, the extractor changed, not the register")
        live = pins.rows_with_pins((REPO / REGISTER).read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(live), 1, f"the live register carries no pins at all: {live}")
        self.assertIn("WUI-00", [row[1] for row in live],
                      f"the one pin the live register carries is on WUI-00; the extractor lost it: {live}")


if __name__ == "__main__":
    unittest.main()
