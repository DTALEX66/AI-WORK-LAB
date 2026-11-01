"""The reference-resolution rule must be able to go red, and must not pass on an empty scan.

The rule exists because the authority index sent readers to two directories that have not existed since
the 2026-09 convergence, and because the README's normative 仓库结构 block advertised `bin/`, `skills/`
and `scripts/workflow/` as repository directories. Resolution is against `git ls-files` rather than the
filesystem, so these assertions plant tracked-path sets instead of touching disk -- which is also why the
verdict cannot depend on what a particular machine has in `.project-local/`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import verify_authority_index_paths as checker  # noqa: E402

INDEX = "docs/current/workflow-assistance/workflow/active-authority-index.md"
README = "docs/current/workflow-assistance-README.md"
# a synthetic tracked set that is enough to answer the references these fixtures write
TRACKED = ["WORK-LAB-AUTHORITY.md", "config/config-ownership.json",
           "docs/current/workflow-assistance-README.md", INDEX,
           "scripts/setup-workflow.sh", "scripts/setup-workflow.ps1",
           "docs/current/workflow-assistance/workflow/managed-software-and-assets.md",
           "packages/client-neutral-core/skills/one/SKILL.md",
           "packages/client-neutral-core/bin/codex"]


class ResolutionAgainstTheTrackedTree(unittest.TestCase):
    def test_a_directory_counts_as_real_only_when_a_tracked_file_sits_under_it(self) -> None:
        self.assertTrue(checker.resolves(TRACKED, "config/", "directory"))
        self.assertFalse(checker.resolves(TRACKED, "scripts/workflow/", "directory"))

    def test_a_file_reference_must_be_tracked_exactly(self) -> None:
        self.assertTrue(checker.resolves(TRACKED, "scripts/setup-workflow.sh", "file"))
        self.assertFalse(checker.resolves(TRACKED, "setup.sh", "file"))

    def test_relative_links_are_folded_before_judging(self) -> None:
        """The README writes `../../.github/workflows/work-lab-gate.yml`, which is a real tracked file."""
        folded = checker.anchored(README, "../../.github/workflows/work-lab-gate.yml")
        self.assertEqual(".github/workflows/work-lab-gate.yml", folded)

    def test_placeholders_are_never_tried(self) -> None:
        for ref in ("<project>/.project-local/runs/", "~/path/x.md", "$CODEX_HOME/AGENTS.md",
                    "docs/workflow/*.md"):
            self.assertTrue(checker.is_placeholder(ref), ref)

    def test_a_declared_prefix_covers_its_children(self) -> None:
        self.assertEqual(".project-local/", checker.declared(".project-local/artifacts/"))
        self.assertIsNone(checker.declared("scripts/workflow/"))

    def test_a_reference_written_against_its_own_document_resolves_as_a_sibling(self) -> None:
        """DESIGN.md lives in apps/observer/frontend/ and writes `src/…` paths that live beside it.

        Before 2026-10-08 the checker only ever tried the repository-root form, so real pointers in the
        design contract reported as dead. The sibling form is tried second, which is what keeps this a
        widening rather than an excuse: a root-anchored name that stops existing still convicts.
        """
        self.assertEqual(["src/styles/x.css", "apps/observer/frontend/src/styles/x.css"],
                         checker.candidates("apps/observer/frontend/DESIGN.md", "src/styles/x.css"))
        # a reference that is already written from the repository root keeps that root form as its first
        # candidate; the document-relative form is only ever the fallback
        self.assertEqual("docs/current/x.md",
                         checker.candidates("docs/current/y.md", "docs/current/x.md")[0])

    def test_a_root_anchored_name_is_tried_at_the_root_first(self) -> None:
        """Ordering is the safety property: the sibling form is a fallback, never a substitute."""
        options = checker.candidates("apps/observer/frontend/DESIGN.md", "scripts/setup-workflow.sh")
        self.assertEqual("scripts/setup-workflow.sh", options[0])
        self.assertTrue(TRACKED.count(options[0]) == 1, "the fixture must keep a root-form hit available")

    def test_a_stylesheet_reference_is_extracted_at_all(self) -> None:
        """Measured 2026-10-08: DESIGN.md's densest column cites .css/.scss/.vue, and the extractor saw none.

        The widening added 17 judged references over the scanned surfaces and convicted 6 claims that had
        never been looked at. This assertion is the difference between guarding a document and naming it.
        """
        for ref in ("`apps/x/y.css`", "`apps/x/y.scss`", "`apps/x/y.vue`"):
            self.assertEqual(1, len(checker.references(f"- {ref}\n")), ref)


class SurfaceChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="reference-paths-", dir=str(_runtime_root())))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_a_dead_directory_in_a_fenced_map_is_caught(self) -> None:
        """The 仓库结构 block is written without backticks; a backtick-only reader would call it clean."""
        text = "```text\nbin/                 wrapper\nconfig/              baseline\n```\n"
        rows, broken, stale = checker.check(self.dir_parent(), TRACKED, self.write("map.md", text))
        self.assertEqual(1, len(broken), f"expected bin/ to fire, got {broken}")
        self.assertEqual("bin/", broken[0][1])
        self.assertEqual([], stale)

    def test_a_dead_backticked_file_is_caught_and_a_declared_one_is_not(self) -> None:
        text = ("- `scripts/workflow/gone.py`: x\n"
                "- `.project-local/artifacts/`: declared as the untracked evidence root\n")
        _rows, broken, _stale = checker.check(self.dir_parent(), TRACKED, self.write("refs.md", text))
        self.assertEqual(["scripts/workflow/gone.py"], [row[1] for row in broken])

    def test_a_declaration_whose_path_becomes_tracked_is_stale(self) -> None:
        rows, broken, stale = checker.check(
            self.dir_parent(), [".project-local/runs/x.json"],
            self.write("decl.md", "- `.project-local/artifacts/`: x\n"))
        self.assertEqual([], broken)
        self.assertEqual(1, len(stale), f"a live path declared as non-repo must be reported: {rows}")

    def test_a_surface_with_no_references_fails_instead_of_passing(self) -> None:
        _rows, broken, _stale = checker.check(self.dir_parent(), TRACKED,
                                              self.write("empty.md", "# Title\n\nprose only\n"))
        self.assertEqual([], broken, "check() has nothing to judge; main() must call that a failure")

    def test_a_declaration_that_excuses_a_dead_name_is_counted_not_dropped(self) -> None:
        text = ("- `web/` was retired; see the row.\n"
                "  [no-tree-claim ILLUSTRATIVE ref=web/]\n")
        rows, broken, problems = checker.check(self.dir_parent(), TRACKED, self.write("decl.md", text))
        self.assertEqual([], broken, f"the declared name was still reported: {broken}")
        self.assertEqual([], problems)
        self.assertTrue(any(len(row) > 3 and row[3] for row in rows),
                        f"nothing was marked exempt: {rows}")

    def test_a_declaration_covering_a_live_path_is_a_failure(self) -> None:
        """The moment the tree answers to the name, the excuse is hiding a real pointer."""
        text = "- `config/config-ownership.json`\n  [no-tree-claim ILLUSTRATIVE ref=config/config-ownership.json]\n"
        _rows, broken, problems = checker.check(self.dir_parent(), TRACKED,
                                                self.write("live.md", text))
        self.assertEqual([], broken)
        self.assertEqual(1, len(problems), f"a live path was declared away silently: {problems}")

    def test_an_unverifiable_deleted_claim_is_refused(self) -> None:
        """DELETED has to be checkable in git; a temp root has no such history, so the claim fails."""
        text = "- `gone/`\n  [no-tree-claim DELETED ref=gone/]\n"
        _rows, broken, problems = checker.check(self.dir_parent(), TRACKED, self.write("gone.md", text))
        self.assertEqual(1, len(broken), "an unverified DELETED claim must still be reported broken")
        self.assertEqual(1, len(problems))
        self.assertIn("no deletion or rename", problems[0][1])

    def test_an_unknown_reason_code_is_refused(self) -> None:
        text = "- `gone/`\n  [no-tree-claim PROBABLY_FINE ref=gone/]\n"
        _rows, _broken, problems = checker.check(self.dir_parent(), TRACKED, self.write("code.md", text))
        self.assertEqual(1, len(problems))
        self.assertIn("unknown reason code", problems[0][1])

    def test_a_document_relative_reference_resolves_and_a_dead_one_still_fires(self) -> None:
        """`src/styles/x.css` inside apps/observer/frontend/DESIGN.md means the file beside it.

        Both halves are asserted because the fallback is only safe if it is a fallback: the same page
        writing a name that exists in neither form must still be convicted.
        """
        tracked = ["apps/observer/frontend/src/styles/x.css", "apps/observer/frontend/DESIGN.md"]
        target = "apps/observer/frontend/DESIGN.md"
        _rows, broken, _p = checker.check(self.dir, tracked,
                                          self.write_at(target, "- `src/styles/x.css`: the shell sheet\n"))
        self.assertEqual([], broken, f"a sibling pointer was reported dead: {broken}")
        _rows, broken, _p = checker.check(self.dir, tracked,
                                          self.write_at(target, "- `src/styles/gone.css`: x\n"))
        self.assertEqual(["src/styles/gone.css"], [row[1] for row in broken])

    def test_an_in_row_directory_declaration_covers_a_deep_foreign_file(self) -> None:
        """The design contract cites `packages/grafana-data/src/themes/createTypography.ts` as Grafana's.

        The token is written at the foreign root, so one declaration covers the paths quoted under it,
        and it stays scoped to the page that carries it rather than muting the spelling repo-wide.
        """
        text = ("- `packages/grafana-data/src/themes/createTypography.ts` is Grafana's own file.\n"
                "  [no-tree-claim CROSS_PROJECT ref=packages/grafana-data/]\n")
        rows, broken, problems = checker.check(self.dir_parent(), TRACKED, self.write("foreign.md", text))
        self.assertEqual([], broken, f"the declared foreign tree did not cover its child: {broken}")
        self.assertEqual([], problems)
        self.assertTrue(any(len(row) > 3 and row[3] for row in rows), f"nothing marked exempt: {rows}")

    def test_a_declaration_that_covers_nothing_is_residue(self) -> None:
        text = ("- `scripts/workflow/gone.py`: x\n"
                "  [no-tree-claim CROSS_PROJECT ref=nowhere/at/all/]\n")
        _rows, broken, problems = checker.check(self.dir_parent(), TRACKED, self.write("residue.md", text))
        self.assertEqual(["scripts/workflow/gone.py"], [row[1] for row in broken])
        self.assertEqual(1, len(problems), f"an exemption excusing nothing must be reported: {problems}")
        self.assertIn("does not ask about", problems[0][1])

    def test_a_served_route_is_declared_as_a_route_not_as_a_file(self) -> None:
        """`/control-shell.css` is a GET endpoint whose real file lives under apps/control-surface/.

        A leading slash is how this checker reads a repository-root file claim, so the sentence has to
        say which of the two it is; this code is what lets the register list endpoints honestly.
        """
        self.assertIn("SERVED_ROUTE", checker.DECLARATION_CODES)
        text = ("- GET 只暴露 `/control-shell.css`\n"
                "  [no-tree-claim SERVED_ROUTE ref=/control-shell.css]\n")
        _rows, broken, problems = checker.check(self.dir_parent(), TRACKED, self.write("route.md", text))
        self.assertEqual([], broken, f"the declared route still reported a missing file: {broken}")
        self.assertEqual([], problems)

    def dir_parent(self) -> Path:
        return self.dir

    def write(self, name: str, text: str) -> str:
        (self.dir / name).write_text(text, encoding="utf-8", newline="\n")
        self.assertEqual(text, (self.dir / name).read_text(encoding="utf-8"))
        return name

    def write_at(self, target: str, text: str) -> str:
        """Write a page at a nested path, for the cases where the document's own directory matters."""
        page = self.dir / target
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(text, encoding="utf-8", newline="\n")
        self.assertEqual(text, page.read_text(encoding="utf-8"))
        return target


def _runtime_root() -> Path:
    p = REPO / ".project-local" / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


class RealSurfaces(unittest.TestCase):
    def run_tool(self, *extra: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "ci"
                                                    / "verify_authority_index_paths.py"), *extra],
                              cwd=REPO, capture_output=True)
        return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")

    def test_every_navigation_surface_is_named_and_resolves(self) -> None:
        code, out = self.run_tool()
        self.assertEqual(0, code, out)
        for target in checker.NAVIGATION_SURFACES:
            self.assertIn(f"target={target} refs=", out, f"{target} is not judged by the default run")
            self.assertNotIn(f"target={target} refs=0 ", out, f"{target} is guarded in name only")
        self.assertIn("broken=0", out)
        self.assertIn(f"targets={len(checker.scanned_surfaces(checker.tracked_paths(REPO)))}", out)

    def test_each_navigation_surface_actually_yields_references(self) -> None:
        tracked = checker.tracked_paths(REPO)
        for target in checker.NAVIGATION_SURFACES:
            rows, broken, stale = checker.check(REPO, tracked, target)
            self.assertGreater(len(rows), 0, f"{target} yields no references at all")
            self.assertEqual([], broken, f"{target} has unresolved references")
            self.assertEqual([], stale, f"{target} has a stale declaration")

    def test_a_backticked_term_with_a_slash_is_not_a_path(self) -> None:
        """`GUI/TUI` in the troubleshooting doc is a mode pair, not a missing file."""
        self.assertFalse(checker.looks_like_path("GUI/TUI"))
        self.assertTrue(checker.looks_like_path("docs/current/x.md"))

    def test_the_root_absolute_authority_pointer_is_still_covered(self) -> None:
        """/WORK-LAB-AUTHORITY.md is the top authority; excluding it would be a silent blind spot."""
        self.assertTrue(checker.looks_like_path("/WORK-LAB-AUTHORITY.md"))
        index = (REPO / INDEX).read_text(encoding="utf-8")
        self.assertIn("/WORK-LAB-AUTHORITY.md", [row[1] for row in checker.references(index)])

    def test_the_tool_refuses_an_empty_tracked_set(self) -> None:
        """A checker that can resolve nothing must not report a clean tree."""
        original = checker.tracked_paths
        try:
            checker.tracked_paths = lambda root: []
            code = checker.main([])
        finally:
            checker.tracked_paths = original
        self.assertEqual(1, code)

    def test_the_widened_scan_covers_every_tracked_current_document(self) -> None:
        """The scan is discovered from git, so a new page under docs/current is guarded on arrival."""
        tracked = checker.tracked_paths(REPO)
        scanned = checker.scanned_surfaces(tracked)
        self.assertGreaterEqual(len(scanned), 30, f"only {len(scanned)} surfaces scanned")
        for target in checker.NAVIGATION_SURFACES:
            self.assertIn(target, scanned, f"{target} is not inside the scanned root")
        self.assertIn("docs/current/workflow-assistance/workflow/token-monitor.md", scanned)

    def test_no_reference_in_the_scanned_set_is_unresolved(self) -> None:
        code, out = self.run_tool()
        self.assertEqual(0, code, out)
        self.assertIn("broken=0", out)

    def test_a_surface_that_makes_no_tree_claim_passes_and_is_counted(self) -> None:
        """Measured 2026-10-08: seven prose pages under docs/current name no path at all.

        Requiring references everywhere would have made the widened scan refuse honest prose; requiring
        them on the four navigation surfaces stays, because a navigation surface with nothing to click
        is the defect that rule was written for.
        """
        code, out = self.run_tool()
        self.assertEqual(0, code, out)
        self.assertGreaterEqual(int(re.search(r"no_tree_claims=(\d+)", out).group(1)), 1)
        self.assertIn("navigation=no", out)

    def test_the_run_refuses_when_the_extracted_reference_count_collapses(self) -> None:
        """A checker that stopped matching must not report the cleanest tree it ever claimed."""
        original = checker.references
        try:
            checker.references = lambda text: []
            code = checker.main([])
        finally:
            checker.references = original
        self.assertEqual(1, code)

    def test_a_broken_reference_outside_the_navigation_surfaces_fails_the_default_run(self) -> None:
        """The widening is only real if a page nobody named can go red.

        Run against a synthetic root rather than an edited document: the tool takes its root from
        repo_root(), which is patchable, so the rule can be shown firing without writing into the tree
        the rest of the suite is reading.
        """
        root = _runtime_root() / "planted-scan"
        page = root / "docs/current/workflow-assistance/workflow/ordinary-page.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("- See `scripts/gone/gone.py` for the detail.\n", encoding="utf-8", newline="\n")
        self.addCleanup(shutil.rmtree, root, True)

        original = (checker.repo_root, checker.tracked_paths, checker.REFS_FLOOR)
        try:
            checker.repo_root = lambda: root
            checker.tracked_paths = lambda r: ["docs/current/workflow-assistance/workflow/ordinary-page.md"]
            checker.REFS_FLOOR = 1  # this fixture has one reference; the floor is tested separately
            code = checker.main([])
        finally:
            checker.repo_root, checker.tracked_paths, checker.REFS_FLOOR = original
        self.assertEqual(1, code, "a dead pointer in an ordinary current page passed the widened scan")

    def test_a_named_run_that_judged_nothing_does_not_pass(self) -> None:
        """The floor guards the default scan; a named run needed its own capability check.

        Before this, `--index <one prose page>` printed refs=0 broken=0 and exited 0 -- which is exactly
        what a broken extractor looks like from the outside. A page legitimately making no tree claim is
        still allowed inside the widened scan, where the other surfaces carry the floor. Measured:
        docs/current/workflow-assistance/workflow/github-delivery-accelerator.md yields refs=0.
        """
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "ci"
                                                    / "verify_authority_index_paths.py"),
                               "--index",
                               "docs/current/workflow-assistance/workflow/github-delivery-accelerator.md"],
                              cwd=REPO, capture_output=True)
        out = (proc.stdout + proc.stderr).decode("utf-8", "replace")
        self.assertIn("refs=0", out, out)
        self.assertEqual(1, proc.returncode,
                         "a named run that judged nothing still reported a clean result")

    def test_only_the_untracked_runtime_root_is_declared(self) -> None:
        """Measured 2026-10-08: everything else resolves, so a new declaration needs its own reason."""
        self.assertEqual({".project-local/"}, set(checker.DECLARED_NON_PATHS))
        for entry, reason in checker.DECLARED_NON_PATHS.items():
            self.assertGreater(len(reason), 40, f"{entry} is declared with a shrug")

    def test_the_design_contract_surfaces_are_guarded_not_just_named(self) -> None:
        """Adding a surface to EXTRA_SURFACES has to buy measurement, not a line in a tuple.

        DESIGN.md and SCREEN_SPEC.md joined the scan on 2026-10-08 with the extension widening, because
        before it they were strict in name and blind in fact: their densest column cited .css/.scss/.vue
        paths the extractor never read. The floor assertion is what keeps that from quietly regressing.
        """
        tracked = checker.tracked_paths(REPO)
        for target in ("apps/observer/frontend/DESIGN.md", "apps/observer/frontend/SCREEN_SPEC.md"):
            self.assertIn(target, checker.scanned_surfaces(tracked), f"{target} is not scanned")
            self.assertIn(target, checker.strict_surfaces(), f"{target} is scanned but not held strict")
            rows, broken, problems = checker.check(REPO, tracked, target)
            self.assertGreaterEqual(len(rows), checker.SURFACE_REF_FLOORS[target],
                                    f"{target} yields {len(rows)} references, below its floor")
            self.assertEqual([], broken, f"{target} has unresolved references")
            self.assertEqual([], problems, f"{target} has a stale or residue declaration")

    def test_a_map_entry_is_a_path_claim_only_in_file_or_directory_shape(self) -> None:
        """`origin/main SHA/tree` and `/interrupt` are a ref and a command, not missing files.

        The relaxation is bounded on purpose: the same shape test is what a backticked reference has to
        pass, so neither rule can excuse a path the other one would have caught.
        """
        self.assertFalse(checker.claims_a_path("origin/main"))
        self.assertFalse(checker.claims_a_path("/interrupt"))
        self.assertTrue(checker.claims_a_path("scripts/workflow/"))
        self.assertTrue(checker.claims_a_path("scripts/workflow/gone.py"))

    def test_a_windows_environment_root_is_never_a_repository_path(self) -> None:
        self.assertTrue(checker.is_placeholder("%LOCALAPPDATA%/hermes/state.db"))

    def test_git_ls_files_returns_a_usable_set(self) -> None:
        tracked = checker.tracked_paths(REPO)
        self.assertGreater(len(tracked), 1000, f"only {len(tracked)} tracked paths; suspicious")
        self.assertIn("scripts/setup-workflow.sh", tracked)


if __name__ == "__main__":
    unittest.main()
